"""Takumi — render HTML, Markdown, and node trees to images without a browser."""

from __future__ import annotations


# Raise Python thread stacks on musl *before* any ThreadPoolExecutor work.
# (RUST_MIN_STACK / Rayon only affect Rust threads — not Python workers.)
from pytakumi._stack import ensure_for_runtime as _ensure_thread_stacks

_ensure_thread_stacks()

from pytakumi._native import (  # noqa: E402
    NodeTree,
    Renderer,
    __version__,
    container,
    from_html,
    image_node,
    render,
    render_html,
    set_glyph_cache_max_bytes,
    supports_free_threading,
    text_node,
)
from pytakumi.api import Format, html_to_pic, md_to_pic, render_markdown, text_to_pic  # noqa: E402
from pytakumi.markdown import markdown_to_html, wrap_markdown_html  # noqa: E402

__all__ = [
    "Format",
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
    "supports_free_threading",
    "text_node",
    "text_to_pic",
    "wrap_markdown_html",
]


def __getattr__(name: str) -> object:  # pragma: no cover
    if name == "__version__":
        return __version__
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
