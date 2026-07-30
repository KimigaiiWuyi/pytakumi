"""Shared helpers for high-level render APIs."""

from __future__ import annotations

import html as html_lib
import re
import threading
from pathlib import Path
from collections.abc import Mapping, Sequence
from typing import Any

from pytakumi._native import Renderer

_TEMPLATES = Path(__file__).resolve().parent / "templates"

# Process-wide default renderer (lazy). Double-checked locking so free-threaded
# CPython does not race two constructors into the global slot.
_default_renderer: Renderer | None = None
_default_renderer_lock = threading.Lock()


def default_renderer() -> Renderer:
    global _default_renderer
    r = _default_renderer
    if r is not None:
        return r
    with _default_renderer_lock:
        if _default_renderer is None:
            _default_renderer = Renderer()
        return _default_renderer


def load_template(name: str) -> str:
    path = _TEMPLATES / name
    return path.read_text(encoding="utf-8")


def escape(text: str) -> str:
    return html_lib.escape(text, quote=True)


def register_fonts(
    renderer: Renderer,
    fonts: Sequence[bytes | Mapping[str, Any]] | None,
) -> None:
    if not fonts:
        return
    for item in fonts:
        if isinstance(item, (bytes, bytearray)):
            _ = renderer.register_font(bytes(item))
            continue
        if not isinstance(item, Mapping):
            raise TypeError("fonts entries must be bytes or mapping with data=")
        data = item.get("data")
        if data is None:
            raise ValueError("font dict requires 'data' bytes")
        _ = renderer.register_font(
            bytes(data),
            name=item.get("name"),
            weight=item.get("weight"),
            style=item.get("style"),
            subset_of=item.get("subset_of") or item.get("subsetOf"),
            generic=item.get("generic"),
        )


def resolve_renderer(
    renderer: Renderer | None,
    fonts: Sequence[bytes | Mapping[str, Any]] | None,
) -> Renderer:
    if renderer is not None:
        register_fonts(renderer, fonts)
        return renderer
    if fonts:
        # Don't pollute the process default with one-shot fonts.
        r = Renderer()
        register_fonts(r, fonts)
        return r
    return default_renderer()


def normalize_device_pixel_ratio(device_pixel_ratio: float | None) -> float:
    """Validate a caller-supplied device pixel ratio.

    ``None`` means the engine default (1.0). Zero, negative, and non-finite
    values are rejected because the CSS viewport is computed as
    ``device_size / ratio``; an invalid ratio would produce nonsensical CSS
    sizes instead of a clear caller error.
    """
    if device_pixel_ratio is None:
        return 1.0
    ratio = float(device_pixel_ratio)
    if ratio <= 0.0 or ratio != ratio or ratio == float("inf"):
        raise ValueError("device_pixel_ratio must be a positive finite number")
    return ratio


def extract_styles_and_body(
    html: str,
    width: int | None,
    height: int | None,
    device_pixel_ratio: float | None = None,
    overflow: str = "hidden",
) -> tuple[list[str], str]:
    """Pull <style> blocks out and wrap body content for Takumi.

    ``width`` / ``height`` are *device* pixels, matching ``Renderer.render_html``.
    The injected root wrapper is laid out in CSS pixels, and Takumi's CSS
    viewport equals ``size / device_pixel_ratio``. When a high-DPI ratio is
    active the wrapper size is therefore scaled down by the same ratio; forcing
    it to the raw device-pixel value would overflow the viewport and clip the
    right/bottom edge of the content.

    ``overflow`` controls the root wrapper clipping behavior. ``hidden`` keeps
    fixed-size renders predictable; ``visible`` lets content paint outside the
    root box when the caller explicitly wants it.
    """
    if overflow not in ("hidden", "visible"):
        raise ValueError("overflow must be 'hidden' or 'visible'")

    styles: list[str] = re.findall(r"<style[^>]*>(.*?)</style>", html, flags=re.I | re.S)
    body_m = re.search(r"<body[^>]*>(.*?)</body>", html, flags=re.I | re.S)
    body = body_m.group(1) if body_m else html
    body = re.sub(r"<script[^>]*>.*?</script>", "", body, flags=re.I | re.S)
    body = re.sub(r"<style[^>]*>.*?</style>", "", body, flags=re.I | re.S)

    dpr = normalize_device_pixel_ratio(device_pixel_ratio)

    def _css_px(value: int | None) -> str | None:
        if value is None:
            return None
        css = value / dpr
        if float(css).is_integer():
            return str(int(css))
        return f"{css:g}"

    size_bits = []
    css_width = _css_px(width)
    if css_width is not None:
        size_bits.append(f"width:{css_width}px")
    css_height = _css_px(height)
    if css_height is not None:
        size_bits.append(f"height:{css_height}px")
    size_css = ";".join(size_bits)
    if size_css:
        size_css += ";"

    for i, sheet in enumerate(styles):
        styles[i] = re.sub(
            r"(?m)(^|[,\s])(?:html|body)(\s*[,{])",
            r"\1.pytakumi-root\2",
            sheet,
        )
        styles[i] = re.sub(r"@import\s+url\([^)]+\)\s*;?", "", styles[i], flags=re.I)

    wrapped = (
        f'<div class="pytakumi-root" style="{size_css}box-sizing:border-box;'
        f'position:relative;overflow:{overflow}">{body}</div>'
    )
    return styles, wrapped
