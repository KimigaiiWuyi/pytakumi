"""Concurrent render safety (product multi-worker scenarios)."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed

from helpers import assert_png, full_bleed


def test_shared_renderer_thread_pool(renderer):
    def job(i: int) -> bytes:
        color = f"#{(i * 40) % 255:02x}2030"
        return renderer.render_html(full_bleed(color), width=64, height=48)

    with ThreadPoolExecutor(max_workers=4) as pool:
        futs = [pool.submit(job, i) for i in range(12)]
        results = [f.result() for f in as_completed(futs)]

    assert len(results) == 12
    for png in results:
        assert_png(png, width=64, height=48)


def test_html_to_pic_parallel_default_renderer():
    from pytakumi import html_to_pic

    def job(i: int) -> bytes:
        return html_to_pic(
            full_bleed("#102030", f"color:#fff;font-size:12px"),
            width=80,
            height=40,
        )

    with ThreadPoolExecutor(max_workers=3) as pool:
        outs = list(pool.map(job, range(9)))
    assert all(o[:8] == b"\x89PNG\r\n\x1a\n" for o in outs)


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

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(work, range(8)))
    assert any(k == "m" for k, _ in results)
    assert any(k == "r" for k, _ in results)
