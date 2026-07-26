"""Concurrent render safety (GIL and free-threaded CPython).

These tests stress shared ``Renderer`` / ``NodeTree`` / default-renderer paths.
Failures typically show as crashes, ``Already borrowed``, hung workers, or
byte-level divergence across workers — not flaky timeouts.

Coverage matrix (what we deliberately hit):
  - Shared Renderer: render / render_html / measure / svg / animation
  - Shared NodeTree across threads (clone-on-read)
  - Font write path concurrent with render read path (ArcSwap + Mutex)
  - ResourceCache: concurrent image decode + stylesheet parse
  - Process default renderer singleton (double-checked lock)
  - High-level helpers: html_to_pic / text_to_pic / md_to_pic
  - Module-level render_html (ephemeral renderers)
  - Error paths concurrent (must not poison locks)
  - Bitwise-identical raw frames for pure solid fills
  - Free-threaded: higher worker counts + high-contention barrier test
"""

from __future__ import annotations

import hashlib
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable

import pytest

from helpers import assert_png, assert_webp, full_bleed


# ---------------------------------------------------------------------------
# Environment / scaling
# ---------------------------------------------------------------------------


def _is_free_threaded() -> bool:
    """True when running on free-threaded CPython with the GIL actually off."""
    gil_enabled = getattr(sys, "_is_gil_enabled", None)
    if callable(gil_enabled):
        try:
            return not gil_enabled()
        except Exception:
            pass
    try:
        import sysconfig

        # Build was compiled free-threaded; GIL may still be forced on via env.
        return bool(sysconfig.get_config_var("Py_GIL_DISABLED"))
    except Exception:
        return False


# Heavier under free-threaded: more workers expose races the GIL hides.
_FT = _is_free_threaded()
_WORKERS = 16 if _FT else 8
_ITERS = 48 if _FT else 24


class _ErrorBag:
    """Thread-safe exception bag (list.append is not free-thread-safe)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._items: list[BaseException] = []

    def add(self, exc: BaseException) -> None:
        with self._lock:
            self._items.append(exc)

    def raise_if_any(self) -> None:
        with self._lock:
            if self._items:
                raise AssertionError(f"{len(self._items)} worker failure(s): {self._items[:3]!r}")


def _run_threads(n: int, fn: Callable[[int], None], *, join_timeout: float = 90.0) -> None:
    """Start ``n`` threads that each call ``fn(i)``; fail on hang or worker error."""
    bag = _ErrorBag()
    barrier = threading.Barrier(n)

    def wrapper(i: int) -> None:
        try:
            barrier.wait(timeout=15)
            fn(i)
        except BaseException as e:  # noqa: BLE001 — re-raise via bag
            bag.add(e)

    threads = [threading.Thread(target=wrapper, args=(i,), name=f"worker-{i}") for i in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=join_timeout)
        assert not t.is_alive(), f"worker hung: {t.name}"
    bag.raise_if_any()


def _sha_set(blobs: list[bytes]) -> set[str]:
    return {hashlib.sha256(b).hexdigest() for b in blobs}


# ---------------------------------------------------------------------------
# Module / runtime flags
# ---------------------------------------------------------------------------


def test_module_declares_free_threading_support():
    from pytakumi import supports_free_threading
    from pytakumi._native import supports_free_threading as native_flag

    assert supports_free_threading is True
    assert native_flag is True


# ---------------------------------------------------------------------------
# Shared Renderer — basic parallel paint
# ---------------------------------------------------------------------------


def test_shared_renderer_thread_pool(renderer):
    def job(i: int) -> bytes:
        color = f"#{(i * 40) % 255:02x}2030"
        return renderer.render_html(full_bleed(color), width=64, height=48)

    with ThreadPoolExecutor(max_workers=_WORKERS) as pool:
        futs = [pool.submit(job, i) for i in range(_ITERS)]
        results = [f.result() for f in as_completed(futs)]

    assert len(results) == _ITERS
    for png in results:
        assert_png(png, width=64, height=48)


def test_shared_renderer_identical_raw_solid(renderer):
    """Solid fill (no text shaping) must be bitwise-identical across threads."""
    html = full_bleed("#336699")

    def job(_: int) -> bytes:
        return renderer.render_html(html, width=96, height=64, format="raw")

    with ThreadPoolExecutor(max_workers=_WORKERS) as pool:
        outs = list(pool.map(job, range(_ITERS)))

    assert len(_sha_set(outs)) == 1, "nondeterministic raw frames under concurrency"
    assert all(len(b) == 96 * 64 * 4 for b in outs)
    # Spot-check first pixel ≈ #336699
    assert outs[0][0] == 0x33 and outs[0][1] == 0x66 and outs[0][2] == 0x99


def test_parallel_measure_and_render(renderer):
    node = {
        "type": "container",
        "style": {"padding": "8px", "background": "#eee"},
        "children": [{"type": "text", "text": "parallel", "style": {"fontFamily": "Geist"}}],
    }

    def work(i: int):
        if i % 2 == 0:
            return ("m", renderer.measure(node, width=200))
        return ("r", renderer.render(node, width=200, height=80))

    with ThreadPoolExecutor(max_workers=_WORKERS) as pool:
        results = list(pool.map(work, range(_ITERS)))
    assert any(k == "m" for k, _ in results)
    assert any(k == "r" for k, _ in results)
    for k, v in results:
        if k == "r":
            assert_png(v, width=200, height=80)
        else:
            assert isinstance(v, dict)


# ---------------------------------------------------------------------------
# Shared NodeTree
# ---------------------------------------------------------------------------


def test_shared_nodetree_parallel_render(renderer):
    from pytakumi import from_html

    tree = from_html(full_bleed("#112233"))

    def job(_: int) -> bytes:
        return renderer.render(tree, width=120, height=60, format="raw")

    with ThreadPoolExecutor(max_workers=_WORKERS) as pool:
        outs = list(pool.map(job, range(_ITERS)))

    assert len(_sha_set(outs)) == 1
    assert all(len(b) == 120 * 60 * 4 for b in outs)


def test_parallel_from_html_and_render(renderer):
    """Each thread parses its own tree (no shared NodeTree) then paints."""

    def job(i: int) -> bytes:
        from pytakumi import from_html

        tree = from_html(full_bleed(f"#{i % 200:02x}4050"))
        return renderer.render(tree, width=64, height=40)

    with ThreadPoolExecutor(max_workers=_WORKERS) as pool:
        outs = list(pool.map(job, range(_ITERS)))
    assert all(o[:8] == b"\x89PNG\r\n\x1a\n" for o in outs)


# ---------------------------------------------------------------------------
# Font registry write vs render read
# ---------------------------------------------------------------------------


def test_parallel_register_font_and_render(renderer_empty, geist_font_bytes):
    """Font registration (write) concurrent with renders (read via ArcSwap)."""

    def worker(i: int) -> None:
        if i % 3 == 0:
            renderer_empty.register_font(geist_font_bytes, name=f"Geist-{i % 4}")
        png = renderer_empty.render_html(
            full_bleed(
                "#0a0a0a",
                "color:#fff;font-size:12px;font-family:Geist,Geist-0,Geist-1,sans-serif",
            ),
            width=72,
            height=40,
        )
        assert_png(png, width=72, height=40)

    _run_threads(_WORKERS, worker)

    # After the storm, a known registration must still work for paint.
    renderer_empty.register_font(geist_font_bytes, name="Geist-Final")
    png = renderer_empty.render_html(
        full_bleed("#111", "color:#fff;font-size:14px;font-family:Geist-Final"),
        width=80,
        height=40,
    )
    assert_png(png, width=80, height=40)


def test_parallel_same_font_name_register(renderer_empty, geist_font_bytes):
    """Many threads register the same logical name — must not crash or hang."""

    def worker(_: int) -> None:
        renderer_empty.register_font(geist_font_bytes, name="Geist")
        png = renderer_empty.render_html(
            full_bleed("#222", "color:#eee;font-size:12px;font-family:Geist"),
            width=48,
            height=32,
        )
        assert_png(png, width=48, height=32)

    _run_threads(_WORKERS, worker)


# ---------------------------------------------------------------------------
# ResourceCache — images + stylesheets
# ---------------------------------------------------------------------------


def test_parallel_shared_images_cache(renderer, red_png_bytes, green_png_bytes):
    """Concurrent image decode through the shared ResourceCache."""
    images = {"red": red_png_bytes, "green": green_png_bytes}
    html = (
        '<div style="width:100%;height:100%;display:flex">'
        '<img src="red" width="16" height="16"/>'
        '<img src="green" width="16" height="16"/>'
        "</div>"
    )

    def job(i: int) -> bytes:
        return renderer.render_html(html, width=64, height=32, images=images)

    with ThreadPoolExecutor(max_workers=_WORKERS) as pool:
        outs = list(pool.map(job, range(_ITERS)))
    for png in outs:
        assert_png(png, width=64, height=32)


def test_parallel_stylesheet_parse_cache(renderer):
    """Same stylesheet text parsed/cached under concurrent render_html."""
    sheet = ".box{width:100%;height:100%;background:#0f766e;}"

    def job(_: int) -> bytes:
        return renderer.render_html(
            '<div class="box"></div>',
            width=40,
            height=40,
            stylesheets=[sheet],
            format="raw",
        )

    with ThreadPoolExecutor(max_workers=_WORKERS) as pool:
        outs = list(pool.map(job, range(_ITERS)))
    assert len(_sha_set(outs)) == 1
    assert all(len(b) == 40 * 40 * 4 for b in outs)


def test_parallel_distinct_stylesheets(renderer):
    """Different CSS per thread — cache keys must not collide incorrectly."""

    def job(i: int) -> bytes:
        r = (i * 17) % 200 + 20
        sheet = f".c{{width:100%;height:100%;background:rgb({r},40,60);}}"
        return renderer.render_html(
            '<div class="c"></div>',
            width=32,
            height=32,
            stylesheets=[sheet],
            format="raw",
        )

    with ThreadPoolExecutor(max_workers=_WORKERS) as pool:
        outs = list(pool.map(job, range(_ITERS)))
    assert all(len(b) == 32 * 32 * 4 for b in outs)
    # Different inputs should not all collapse to one color (cache mix-up).
    assert len(_sha_set(outs)) > 1


# ---------------------------------------------------------------------------
# Animation (Rayon workers) + mixed surface
# ---------------------------------------------------------------------------


def test_parallel_animation_webp(renderer):
    scenes = [
        (
            {
                "type": "container",
                "style": {"width": "100%", "height": "100%", "background": "#ff0000"},
                "children": [],
            },
            40,
        ),
        (
            {
                "type": "container",
                "style": {"width": "100%", "height": "100%", "background": "#0000ff"},
                "children": [],
            },
            40,
        ),
    ]

    def job(_: int) -> bytes:
        return renderer.render_animation(scenes, width=32, height=32, fps=8, format="webp")

    n = max(8, _WORKERS)
    with ThreadPoolExecutor(max_workers=_WORKERS) as pool:
        outs = list(pool.map(job, range(n)))
    for data in outs:
        assert_webp(data)


def test_mixed_api_surface_parallel(renderer):
    """Mix render / render_html / measure / svg / animation on one Renderer."""
    node = {
        "type": "container",
        "style": {"width": "100%", "height": "100%", "background": "#1e293b"},
        "children": [
            {
                "type": "text",
                "text": "mix",
                "style": {"color": "#fff", "fontSize": "14px", "fontFamily": "Geist"},
            }
        ],
    }
    scenes = [(node, 30), (node, 30)]

    def work(i: int):
        k = i % 5
        if k == 0:
            return ("png", renderer.render(node, width=80, height=40))
        if k == 1:
            return ("html", renderer.render_html(full_bleed("#334155"), width=80, height=40))
        if k == 2:
            return ("m", renderer.measure(node, width=80))
        if k == 3:
            return ("svg", renderer.render_svg(node, width=80, height=40))
        return ("anim", renderer.render_animation(scenes, width=24, height=24, fps=5, format="webp"))

    with ThreadPoolExecutor(max_workers=_WORKERS) as pool:
        results = list(pool.map(work, range(_ITERS)))
    assert len(results) == _ITERS
    kinds = {k for k, _ in results}
    assert kinds == {"png", "html", "m", "svg", "anim"}


def test_parallel_jpeg_and_webp_formats(renderer):
    def job(i: int) -> bytes:
        fmt = "jpeg" if i % 2 == 0 else "webp"
        return renderer.render_html(full_bleed("#445566"), width=48, height=32, format=fmt)

    with ThreadPoolExecutor(max_workers=_WORKERS) as pool:
        outs = list(pool.map(job, range(_ITERS)))
    assert len(outs) == _ITERS
    assert all(isinstance(b, (bytes, bytearray)) and len(b) > 32 for b in outs)


# ---------------------------------------------------------------------------
# High-level Python helpers + module-level entry points
# ---------------------------------------------------------------------------


def test_html_to_pic_parallel_default_renderer():
    from pytakumi import html_to_pic

    def job(_: int) -> bytes:
        return html_to_pic(full_bleed("#102030"), width=80, height=40)

    with ThreadPoolExecutor(max_workers=_WORKERS) as pool:
        outs = list(pool.map(job, range(_ITERS)))
    assert all(o[:8] == b"\x89PNG\r\n\x1a\n" for o in outs)


def test_parallel_html_to_pic_shared_renderer(renderer):
    from pytakumi import html_to_pic

    def job(i: int) -> bytes:
        return html_to_pic(
            full_bleed(f"#{i % 200:02x}3040"),
            width=64,
            height=32,
            renderer=renderer,
        )

    with ThreadPoolExecutor(max_workers=_WORKERS) as pool:
        outs = list(pool.map(job, range(_ITERS)))
    assert all(o[:8] == b"\x89PNG\r\n\x1a\n" for o in outs)


def test_parallel_text_and_md_to_pic(renderer):
    from pytakumi import md_to_pic, text_to_pic

    def job(i: int) -> bytes:
        if i % 2 == 0:
            return text_to_pic(f"line-{i}", title="T", theme="dark", width=320, height=120, renderer=renderer)
        return md_to_pic(f"# H\n\n- item {i}\n", width=400, height=200, renderer=renderer)

    with ThreadPoolExecutor(max_workers=_WORKERS) as pool:
        outs = list(pool.map(job, range(max(12, _WORKERS))))
    assert all(o[:8] == b"\x89PNG\r\n\x1a\n" for o in outs)


def test_parallel_module_render_html(geist_font_bytes):
    from pytakumi import render_html

    def job(i: int) -> bytes:
        return render_html(
            full_bleed(f"#{(i * 3) % 200:02x}1020"),
            width=56,
            height=36,
            fonts=[geist_font_bytes],
        )

    with ThreadPoolExecutor(max_workers=_WORKERS) as pool:
        outs = list(pool.map(job, range(_ITERS)))
    assert all(o[:8] == b"\x89PNG\r\n\x1a\n" for o in outs)


def test_default_renderer_singleton_thread_safe():
    from pytakumi._util import default_renderer

    ids: list[int] = []
    lock = threading.Lock()
    n = _WORKERS

    def grab(i: int) -> None:
        r = default_renderer()
        with lock:
            ids.append(id(r))

    _run_threads(n, grab)
    assert len(ids) == n
    assert len(set(ids)) == 1


# ---------------------------------------------------------------------------
# Error paths under concurrency (must not poison locks)
# ---------------------------------------------------------------------------


def test_parallel_invalid_format_does_not_poison(renderer):
    """Failed calls must not leave the shared Renderer unusable."""
    bag = _ErrorBag()
    ok_count = {"n": 0}
    lock = threading.Lock()

    def worker(i: int) -> None:
        try:
            if i % 2 == 0:
                raised = False
                try:
                    renderer.render_html(full_bleed("#000"), width=16, height=16, format="not-a-format")
                except Exception:
                    raised = True
                assert raised, "expected invalid format to raise"
            else:
                png = renderer.render_html(full_bleed("#123456"), width=32, height=24)
                assert_png(png, width=32, height=24)
                with lock:
                    ok_count["n"] += 1
        except BaseException as e:  # noqa: BLE001
            bag.add(e)

    # Use pool (no barrier) so failures and successes interleave freely.
    with ThreadPoolExecutor(max_workers=_WORKERS) as pool:
        list(pool.map(worker, range(_ITERS)))
    bag.raise_if_any()
    assert ok_count["n"] >= _ITERS // 4

    # Renderer still healthy after storm.
    assert_png(renderer.render_html(full_bleed("#abcdef"), width=20, height=20), width=20, height=20)


def test_parallel_invalid_font_does_not_poison(renderer_empty):
    bag = _ErrorBag()

    def worker(i: int) -> None:
        try:
            if i % 2 == 0:
                raised = False
                try:
                    renderer_empty.register_font(b"not-a-font")
                except Exception:
                    raised = True
                assert raised, "expected invalid font to raise"
            else:
                png = renderer_empty.render_html(full_bleed("#010101"), width=24, height=24)
                assert_png(png, width=24, height=24)
        except BaseException as e:  # noqa: BLE001
            bag.add(e)

    with ThreadPoolExecutor(max_workers=_WORKERS) as pool:
        list(pool.map(worker, range(_ITERS)))
    bag.raise_if_any()


# ---------------------------------------------------------------------------
# Free-threaded-only (skipped on GIL builds)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not _FT, reason="free-threaded CPython only")
def test_free_threaded_runtime_flags():
    assert _is_free_threaded()
    from pytakumi import supports_free_threading

    assert supports_free_threading is True
    # GIL must actually be off for these stress tests to mean anything.
    assert not sys._is_gil_enabled()  # type: ignore[attr-defined]


@pytest.mark.skipif(not _FT, reason="free-threaded CPython only")
def test_free_threaded_high_contention_shared_renderer(renderer, red_png_bytes):
    """32 threads × multi-op mix: paint, images, stylesheets, measure."""
    images = {"r": red_png_bytes}
    n = 32

    def worker(i: int) -> None:
        for j in range(6):
            k = (i + j) % 4
            if k == 0:
                raw = renderer.render_html(
                    full_bleed(f"#{(i + j) % 255:02x}1020"),
                    width=48,
                    height=32,
                    format="raw",
                )
                assert len(raw) == 48 * 32 * 4
            elif k == 1:
                png = renderer.render_html(
                    '<div style="width:100%;height:100%"><img src="r" width="8" height="8"/></div>',
                    width=40,
                    height=24,
                    images=images,
                )
                assert_png(png, width=40, height=24)
            elif k == 2:
                sheet = f".x{{width:100%;height:100%;background:rgb({(i * 3) % 200},10,20);}}"
                raw = renderer.render_html(
                    '<div class="x"></div>',
                    width=24,
                    height=24,
                    stylesheets=[sheet],
                    format="raw",
                )
                assert len(raw) == 24 * 24 * 4
            else:
                m = renderer.measure(
                    {
                        "type": "container",
                        "style": {"padding": "4px", "background": "#111"},
                        "children": [{"type": "text", "text": f"t{i}", "style": {"fontFamily": "Geist"}}],
                    },
                    width=100,
                )
                assert isinstance(m, dict)

    _run_threads(n, worker, join_timeout=180.0)


@pytest.mark.skipif(not _FT, reason="free-threaded CPython only")
def test_free_threaded_register_font_storm(renderer_empty, geist_font_bytes):
    """Heavy concurrent register + paint reserved for no-GIL."""

    def worker(i: int) -> None:
        for j in range(4):
            renderer_empty.register_font(geist_font_bytes, name=f"F{i % 8}")
            png = renderer_empty.render_html(
                full_bleed(
                    f"#{(i + j) % 180:02x}2030",
                    f"color:#fff;font-size:11px;font-family:F{i % 8},sans-serif",
                ),
                width=40,
                height=28,
            )
            assert_png(png, width=40, height=28)

    _run_threads(24, worker, join_timeout=180.0)
