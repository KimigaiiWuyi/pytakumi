"""Shared helpers for high-level render APIs."""

from __future__ import annotations

import html as html_lib
import re
import threading
from pathlib import Path
from typing import Any, Mapping, Sequence

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
            renderer.register_font(bytes(item))
        elif isinstance(item, Mapping):
            data = item.get("data")
            if data is None:
                raise ValueError("font dict requires 'data' bytes")
            renderer.register_font(
                bytes(data),
                name=item.get("name"),
                weight=item.get("weight"),
                style=item.get("style"),
                subset_of=item.get("subset_of") or item.get("subsetOf"),
                generic=item.get("generic"),
            )
        else:
            raise TypeError("fonts entries must be bytes or mapping with data=")


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


def extract_styles_and_body(html: str, width: int | None, height: int | None) -> tuple[list[str], str]:
    """Pull <style> blocks out and wrap body content for Takumi."""
    styles = re.findall(r"<style[^>]*>(.*?)</style>", html, flags=re.I | re.S)
    body_m = re.search(r"<body[^>]*>(.*?)</body>", html, flags=re.I | re.S)
    body = body_m.group(1) if body_m else html
    body = re.sub(r"<script[^>]*>.*?</script>", "", body, flags=re.I | re.S)
    body = re.sub(r"<style[^>]*>.*?</style>", "", body, flags=re.I | re.S)

    size_bits = []
    if width is not None:
        size_bits.append(f"width:{int(width)}px")
    if height is not None:
        size_bits.append(f"height:{int(height)}px")
    size_css = ";".join(size_bits)
    if size_css:
        size_css += ";"

    for i, sheet in enumerate(styles):
        styles[i] = re.sub(r"(?m)(^|[,\s])body(\s*[,{])", r"\1.pytakumi-root\2", sheet)
        styles[i] = re.sub(r"@import\s+url\([^)]+\)\s*;?", "", styles[i], flags=re.I)

    wrapped = (
        f'<div class="pytakumi-root" style="{size_css}box-sizing:border-box;'
        f'position:relative;overflow:hidden">{body}</div>'
    )
    return styles, wrapped
