"""Takumi — render HTML, Markdown, and node trees to images without a browser."""

from __future__ import annotations

from typing import Any

from pytakumi._native import (
    NodeTree,
    Renderer,
    __version__,
    container,
    from_html,
    image_node,
    render,
    render_html,
    set_glyph_cache_max_bytes,
    text_node,
)
from pytakumi.api import html_to_pic, md_to_pic, text_to_pic
from pytakumi.markdown import markdown_to_html, render_markdown, wrap_markdown_html

__all__ = [
    "NodeTree",
    "Renderer",
    "__version__",
    "container",
    "from_html",
    "html_to_pic",
    "image_node",
    "markdown_to_html",
    "md_to_pic",
    "render",
    "render_html",
    "render_markdown",
    "set_glyph_cache_max_bytes",
    "text_node",
    "text_to_pic",
    "wrap_markdown_html",
]


def __getattr__(name: str) -> Any:  # pragma: no cover
    if name == "__version__":
        return __version__
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
