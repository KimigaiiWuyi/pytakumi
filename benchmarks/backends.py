"""Render backends for comparative benchmarks.

Primary workload: stamina_card.html_test2.html at 1150×850.

Each backend exposes:
  name, available(), setup(), teardown(), render(html, width, height) -> bytes
  thread_safe: if False, harness uses per-thread setup via worker factories.
"""

from __future__ import annotations

import asyncio
import io
import re
import threading
from abc import ABC, abstractmethod
from pathlib import Path


class Backend(ABC):
    name: str
    # True: shared instance is safe across threads.
    # False: harness creates one instance per worker thread.
    thread_safe: bool = True

    @abstractmethod
    def available(self) -> tuple[bool, str]:
        """Return (ok, reason)."""

    def setup(self) -> None:
        return None

    def teardown(self) -> None:
        return None

    @abstractmethod
    def render(self, html: str, width: int, height: int) -> bytes:
        """Return PNG bytes."""

    def clone_for_worker(self) -> "Backend":
        """Fresh backend for a worker thread (used when not thread_safe)."""
        return self.__class__()


def _extract_styles_and_body(html: str, width: int, height: int) -> tuple[list[str], str]:
    styles = re.findall(r"<style[^>]*>(.*?)</style>", html, flags=re.I | re.S)
    body_m = re.search(r"<body[^>]*>(.*?)</body>", html, flags=re.I | re.S)
    body = body_m.group(1) if body_m else html
    body = re.sub(r"<script[^>]*>.*?</script>", "", body, flags=re.I | re.S)
    body = re.sub(r"<style[^>]*>.*?</style>", "", body, flags=re.I | re.S)
    wrapped = (
        f'<div class="bench-root" style="width:{width}px;height:{height}px;'
        f'position:relative;overflow:hidden">'
        f"{body}</div>"
    )
    sheets: list[str] = []
    for sheet in styles:
        sheet2 = re.sub(r"(?m)(^|[,\s])body(\s*[,{])", r"\1.bench-root\2", sheet)
        sheet2 = re.sub(r"@import\s+url\([^)]+\)\s*;?", "", sheet2, flags=re.I)
        sheets.append(sheet2)
    return sheets, wrapped


def _register_cjk_fonts(renderer) -> None:
    for path, name in [
        (r"C:\Windows\Fonts\msyh.ttc", "Microsoft YaHei"),
        (r"C:\Windows\Fonts\simhei.ttf", "SimHei"),
    ]:
        p = Path(path)
        if p.is_file():
            data = p.read_bytes()
            renderer.register_font(data, name=name)
            renderer.register_font(data, name="Source Han Sans CN")
            break


class TakumiBackend(Backend):
    name = "pytakumi"
    thread_safe = True  # Renderer releases GIL; safe to share after fonts registered

    def __init__(self) -> None:
        self._renderer = None

    def available(self) -> tuple[bool, str]:
        try:
            import pytakumi  # noqa: F401

            return True, f"pytakumi {getattr(__import__('pytakumi'), '__version__', '?')}"
        except Exception as e:
            return False, str(e)

    def setup(self) -> None:
        from pytakumi import Renderer, set_glyph_cache_max_bytes

        set_glyph_cache_max_bytes(64 * 1024 * 1024)
        self._renderer = Renderer(cache_max_bytes=128 * 1024 * 1024)
        _register_cjk_fonts(self._renderer)

    def clone_for_worker(self) -> "TakumiBackend":
        # Sharing one Renderer is preferred; still provide clone if requested.
        b = TakumiBackend()
        b.setup()
        return b

    def render(self, html: str, width: int, height: int) -> bytes:
        assert self._renderer is not None
        sheets, body = _extract_styles_and_body(html, width, height)
        return self._renderer.render_html(
            body,
            width=width,
            height=height,
            format="png",
            stylesheets=sheets or None,
        )


class HtmlkitBackend(Backend):
    name = "htmlkit"
    # Prefer per-worker instances so concurrent asyncio.run does not share state.
    thread_safe = False

    def available(self) -> tuple[bool, str]:
        try:
            import htmlkit  # noqa: F401

            return True, "htmlkit/pyhtmlrender"
        except Exception as e:
            return False, str(e)

    def setup(self) -> None:
        from htmlkit import init_fontconfig

        try:
            init_fontconfig()
        except Exception:
            pass

    def clone_for_worker(self) -> "HtmlkitBackend":
        b = HtmlkitBackend()
        b.setup()
        return b

    def render(self, html: str, width: int, height: int) -> bytes:
        from htmlkit import html_to_pic

        return asyncio.run(
            html_to_pic(
                html,
                max_width=float(width),
                device_height=float(height),
                allow_refit=False,
                image_format="png",
                default_font_size=16.0,
                font_name="Microsoft YaHei",
            )
        )


class PlaywrightBackend(Backend):
    name = "playwright"
    # sync API is greenlet-bound — each worker needs its own instance.
    thread_safe = False

    def __init__(self) -> None:
        self._playwright = None
        self._browser = None
        self._context = None

    def available(self) -> tuple[bool, str]:
        try:
            import playwright  # noqa: F401

            return True, "playwright (per-thread browser for concurrency)"
        except Exception as e:
            return False, str(e)

    def setup(self) -> None:
        from playwright.sync_api import sync_playwright

        self._playwright = sync_playwright().start()
        last_err: Exception | None = None
        self._browser = None
        for kwargs in (
            {"headless": True},
            {"channel": "msedge", "headless": True},
            {"channel": "chrome", "headless": True},
        ):
            try:
                self._browser = self._playwright.chromium.launch(**kwargs)
                break
            except Exception as e:  # noqa: PERF203
                last_err = e
        if self._browser is None:
            self._playwright.stop()
            self._playwright = None
            raise RuntimeError(
                f"playwright browser launch failed ({last_err}); "
                "run: playwright install chromium"
            ) from last_err
        self._context = self._browser.new_context(
            viewport={"width": 1280, "height": 900},
            device_scale_factor=1,
        )

    def teardown(self) -> None:
        if self._context is not None:
            try:
                self._context.close()
            except Exception:
                pass
        if self._browser is not None:
            try:
                self._browser.close()
            except Exception:
                pass
        if self._playwright is not None:
            try:
                self._playwright.stop()
            except Exception:
                pass
        self._context = self._browser = self._playwright = None

    def clone_for_worker(self) -> "PlaywrightBackend":
        b = PlaywrightBackend()
        b.setup()
        return b

    def render(self, html: str, width: int, height: int) -> bytes:
        assert self._context is not None
        page = self._context.new_page()
        try:
            page.set_viewport_size({"width": width, "height": height})
            page.set_content(html, wait_until="load")
            return page.screenshot(
                type="png",
                clip={"x": 0, "y": 0, "width": width, "height": height},
            )
        finally:
            page.close()


class PillowBackend(Backend):
    """Same canvas size as HTML backends.

    Does **not** parse HTML. Simulates a card-like workload by repeatedly
    drawing rectangles + CJK/Latin text for ``draw_loops`` iterations
    (default 80), approximating multi-layer UI paint cost.
    """

    name = "pillow"
    thread_safe = True

    def __init__(self, draw_loops: int = 80) -> None:
        self.draw_loops = draw_loops
        self._font_large = None
        self._font_mid = None
        self._font_small = None
        self._labels: list[str] = []

    def available(self) -> tuple[bool, str]:
        try:
            from PIL import Image, ImageDraw, ImageFont  # noqa: F401

            return True, f"Pillow (manual draw ×{self.draw_loops}, not HTML)"
        except Exception as e:
            return False, str(e)

    def setup(self) -> None:
        from PIL import ImageFont

        self._font_large = ImageFont.load_default()
        self._font_mid = ImageFont.load_default()
        self._font_small = ImageFont.load_default()
        for candidate in (r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\arial.ttf"):
            p = Path(candidate)
            if not p.is_file():
                continue
            try:
                self._font_large = ImageFont.truetype(str(p), 40)
                self._font_mid = ImageFont.truetype(str(p), 28)
                self._font_small = ImageFont.truetype(str(p), 18)
                break
            except Exception:
                continue
        self._labels = [
            "鸣潮体力",
            "今日未签到！",
            "活跃度未满！",
            "每日状态",
            "回满时间：漂泊者该上潮了",
            "结晶波片 240/240",
            "结晶单质 480/480",
            "活跃度 0/100",
            "维 UID:129101216",
            "战歌重奏 0/3",
            "先约电台 Lv.0",
            "千道门扉 0",
            "逆境深塔 18/18",
            "冥歌海墟 0/0",
        ]

    def clone_for_worker(self) -> "PillowBackend":
        b = PillowBackend(draw_loops=self.draw_loops)
        b.setup()
        return b

    def render(self, html: str, width: int, height: int) -> bytes:
        from PIL import Image, ImageDraw

        # Touch html so callers pass the same payload; optional label scrape.
        scraped = re.findall(r">([^<]{2,40})<", re.sub(r"data:image/[^\"']+", "", html or ""))
        labels = [t.strip() for t in scraped if t.strip()][:20] or self._labels

        img = Image.new("RGBA", (width, height), (15, 17, 21, 255))
        draw = ImageDraw.Draw(img)

        # Background gradient bands
        for y in range(0, height, 2):
            t = y / max(height - 1, 1)
            r = int(15 + 25 * t)
            g = int(17 + 20 * t)
            b = int(21 + 35 * t)
            draw.line([(0, y), (width, y)], fill=(r, g, b, 255))

        loops = max(1, self.draw_loops)
        for i in range(loops):
            # Left HUD-ish cards
            y0 = 80 + (i * 17) % max(height - 200, 1)
            x0 = 40 + (i % 3) * 8
            w = 420
            h = 72
            draw.rounded_rectangle(
                (x0, y0, x0 + w, y0 + h),
                radius=10,
                fill=(0, 0, 0, 100 + (i % 40)),
                outline=(255, 255, 255, 40),
                width=2,
            )
            # Progress bar track + fill
            draw.rectangle((x0 + 70, y0 + 48, x0 + w - 20, y0 + 58), fill=(40, 40, 50, 200))
            fill_w = int((w - 90) * ((i % 10) + 1) / 10)
            draw.rectangle(
                (x0 + 70, y0 + 48, x0 + 70 + fill_w, y0 + 58),
                fill=(255, 77, 79, 230),
            )
            # Icon placeholder
            draw.ellipse((x0 + 12, y0 + 12, x0 + 56, y0 + 56), fill=(80, 120, 180, 220))

            label = labels[i % len(labels)]
            draw.text((x0 + 70, y0 + 10), label, fill=(255, 255, 255, 240), font=self._font_mid)

            # Right-side character stand-in rects
            rx = width - 380 + (i % 5) * 6
            ry = 40 + (i * 11) % max(height - 300, 1)
            draw.rounded_rectangle(
                (rx, ry, rx + 300, ry + 40),
                radius=8,
                outline=(200, 200, 220, 80),
                width=1,
            )
            draw.text((rx + 12, ry + 8), f"layer-{i}", fill=(220, 220, 230, 180), font=self._font_small)

        # Footer strip
        draw.rectangle((0, height - 160, width, height), fill=(0, 0, 0, 180))
        draw.ellipse((40, height - 140, 150, height - 30), outline=(255, 200, 100, 200), width=3)
        draw.text((170, height - 120), "维", fill=(255, 255, 255, 255), font=self._font_large)
        draw.text((170, height - 70), "UID: 129101216", fill=(212, 177, 99, 255), font=self._font_mid)
        for j, name in enumerate(["战歌重奏", "先约电台", "千道门扉", "逆境深塔", "冥歌海墟"]):
            x = 420 + j * 140
            draw.text((x, height - 110), "0/0", fill=(255, 255, 255, 255), font=self._font_large)
            draw.text((x, height - 60), name, fill=(200, 200, 200, 220), font=self._font_small)

        draw.text((40, 30), "Pillow baseline · same canvas · no HTML", fill=(125, 211, 252, 255), font=self._font_small)

        buf = io.BytesIO()
        img.convert("RGB").save(buf, format="PNG", optimize=False)
        return buf.getvalue()


def all_backends(*, pillow_loops: int = 80) -> list[Backend]:
    return [
        TakumiBackend(),
        HtmlkitBackend(),
        PlaywrightBackend(),
        PillowBackend(draw_loops=pillow_loops),
    ]


def select_backends(names: set[str] | None = None, *, pillow_loops: int = 80) -> list[Backend]:
    selected = []
    for b in all_backends(pillow_loops=pillow_loops):
        if names is not None and b.name not in names:
            continue
        ok, reason = b.available()
        if ok:
            if isinstance(b, PillowBackend):
                b.draw_loops = pillow_loops
            selected.append(b)
        else:
            print(f"[skip] {b.name}: {reason}")
    return selected
