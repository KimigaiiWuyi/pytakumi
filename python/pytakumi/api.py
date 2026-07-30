"""High-level convenience APIs: html_to_pic / text_to_pic / md_to_pic."""

from __future__ import annotations

import warnings
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Literal

from pytakumi._native import Renderer
from pytakumi._util import (
    escape,
    extract_styles_and_body,
    load_template,
    resolve_renderer,
)
from pytakumi.markdown import markdown_to_html, wrap_markdown_html

Format = Literal["png", "jpeg", "jpg", "webp", "ico", "raw"]

__all__ = [
    "Format",
    "html_to_pic",
    "md_to_pic",
    "render_markdown",
    "text_to_pic",
]


def _maybe_save(data: bytes, save_to: str | Path | None) -> bytes:
    """Write *data* to *save_to* when given; always return *data*."""
    if save_to is not None:
        p = Path(save_to)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
    return data


def html_to_pic(
    html: str,
    *,
    width: int = 800,
    height: int | None = None,
    format: Format = "png",
    quality: int | None = None,
    lossless: bool | None = None,
    stylesheets: Sequence[str] | None = None,
    css: str | None = None,
    images: Mapping[str, bytes] | Sequence[Mapping[str, Any]] | None = None,
    fonts: Sequence[bytes | Mapping[str, Any]] | None = None,
    renderer: Renderer | None = None,
    device_pixel_ratio: float | None = None,
    font_families: Sequence[str] | None = None,
    lang: str | None = None,
    draw_debug_border: bool = False,
    max_depth: int | None = None,
    use_presets: bool = True,
    overflow: Literal["hidden", "visible"] = "hidden",
    save_to: str | Path | None = None,
) -> bytes:
    """Render an HTML fragment/document to image bytes.

    ``<style>`` blocks inside ``html`` are extracted and applied. Optional
    ``stylesheets`` / ``css`` are appended. ``<link rel="stylesheet">`` is not
    fetched; use ``<style>``, ``stylesheets=``, or ``css=`` instead.

    Parameters
    ----------
    html:
        HTML markup (full document or fragment).
    width / height:
        Output image size in **device pixels**. The CSS layout viewport is
        ``size / device_pixel_ratio``. Example: ``width=1600`` with
        ``device_pixel_ratio=2`` lays out as ``800px`` CSS width. Omit
        ``height`` to size the image to content height.
    format:
        ``png`` (default), ``jpeg``, ``webp``, ``ico``, or ``raw``.
    fonts:
        Font bytes or ``{"data": bytes, "name": str, ...}`` dicts registered
        on the renderer before paint.
    renderer:
        Reuse a :class:`Renderer` to share caches across calls.
    overflow:
        Root wrapper overflow: ``hidden`` (default) clips content that exceeds
        the fixed box; ``visible`` disables clipping.
    save_to:
        Optional file path. When set, the rendered bytes are also written to
        this path (parent directories created automatically).
    """
    r = resolve_renderer(renderer, fonts)
    extracted, body = extract_styles_and_body(
        html,
        width,
        height,
        device_pixel_ratio=device_pixel_ratio,
        overflow=overflow,
    )
    sheets = list(extracted)
    if stylesheets:
        sheets.extend(stylesheets)
    if css:
        sheets.append(css)

    data = r.render_html(
        body,
        width=width,
        height=height,
        format=format,
        quality=quality,
        lossless=lossless,
        stylesheets=sheets or None,
        images=images,
        draw_debug_border=draw_debug_border,
        device_pixel_ratio=device_pixel_ratio,
        font_families=list(font_families) if font_families is not None else None,
        lang=lang,
        max_depth=max_depth,
        use_presets=use_presets,
    )
    return _maybe_save(data, save_to)


def text_to_pic(
    text: str,
    *,
    width: int = 720,
    height: int | None = None,
    title: str | None = None,
    eyebrow: str | None = None,
    footer: str | None = None,
    theme: Literal["dark", "light"] = "dark",
    format: Format = "png",
    quality: int | None = None,
    lossless: bool | None = None,
    css: str | None = None,
    stylesheets: Sequence[str] | None = None,
    images: Mapping[str, bytes] | Sequence[Mapping[str, Any]] | None = None,
    fonts: Sequence[bytes | Mapping[str, Any]] | None = None,
    renderer: Renderer | None = None,
    device_pixel_ratio: float | None = None,
    font_families: Sequence[str] | None = None,
    lang: str | None = None,
    draw_debug_border: bool = False,
    max_depth: int | None = None,
    use_presets: bool = True,
    overflow: Literal["hidden", "visible"] = "hidden",
    save_to: str | Path | None = None,
) -> bytes:
    """Render plain text with a card template (not raw HTML).

    Parameters
    ----------
    text:
        Body text (newlines preserved).
    title / eyebrow / footer:
        Optional header/meta lines.
    theme:
        ``dark`` (default) or ``light``.
    width / height:
        Output image size in **device pixels**. The CSS layout viewport is
        ``size / device_pixel_ratio``. Omit ``height`` to size the card to
        content height; the template keeps a 360 CSS px minimum height.
    overflow:
        Root wrapper overflow: ``hidden`` (default) clips content that exceeds
        the fixed box; ``visible`` disables clipping.
    save_to:
        Optional file path. When set, the rendered bytes are also written to
        this path (parent directories created automatically).
    """
    root_class = "text-card light" if theme == "light" else "text-card"
    blocks: list[str] = [f'<div class="{root_class}">']
    if eyebrow:
        blocks.append(f'<div class="eyebrow">{escape(eyebrow)}</div>')
    if title:
        blocks.append(f'<div class="title">{escape(title)}</div>')
    blocks.append(f'<div class="body">{escape(text)}</div>')
    if footer:
        blocks.append(f'<div class="footer">{escape(footer)}</div>')
    blocks.append("</div>")
    html = "\n".join(blocks)

    sheet = load_template("text-card.css")
    sheets = [sheet]
    if stylesheets:
        sheets.extend(stylesheets)
    if css:
        sheets.append(css)

    return html_to_pic(
        html,
        width=width,
        height=height,
        format=format,
        quality=quality,
        lossless=lossless,
        stylesheets=sheets,
        images=images,
        fonts=fonts,
        renderer=renderer,
        device_pixel_ratio=device_pixel_ratio,
        font_families=font_families,
        lang=lang,
        draw_debug_border=draw_debug_border,
        max_depth=max_depth,
        use_presets=use_presets,
        overflow=overflow,
        save_to=save_to,
    )


def md_to_pic(
    md: str,
    *,
    width: int = 800,
    height: int | None = None,
    format: Format = "png",
    quality: int | None = None,
    lossless: bool | None = None,
    dark: bool = False,
    css: str | None = None,
    stylesheets: Sequence[str] | None = None,
    images: Mapping[str, bytes] | Sequence[Mapping[str, Any]] | None = None,
    fonts: Sequence[bytes | Mapping[str, Any]] | None = None,
    renderer: Renderer | None = None,
    device_pixel_ratio: float | None = None,
    font_families: Sequence[str] | None = None,
    lang: str | None = None,
    draw_debug_border: bool = False,
    max_depth: int | None = None,
    use_presets: bool = True,
    overflow: Literal["hidden", "visible"] = "hidden",
    save_to: str | Path | None = None,
) -> bytes:
    """Render Markdown as a GitHub-README-style document image.

    Uses ``markdown-it-py`` when installed (``pip install pytakumi[markdown]``),
    otherwise a built-in subset converter.

    Parameters
    ----------
    width / height:
        Output image size in **device pixels**. The CSS layout viewport is
        ``size / device_pixel_ratio``. Omit ``height`` to size the document to
        content height.
    overflow:
        Root wrapper overflow: ``hidden`` (default) clips content that exceeds
        a fixed box; ``visible`` disables clipping.
    save_to:
        Optional file path. When set, the rendered bytes are also written to
        this path (parent directories created automatically).
    """
    body_html = markdown_to_html(md)
    html = wrap_markdown_html(body_html)
    gh_css = load_template("github-markdown-dark.css" if dark else "github-markdown.css")
    sheets = [gh_css]
    if stylesheets:
        sheets.extend(stylesheets)
    if css:
        sheets.append(css)

    return html_to_pic(
        html,
        width=width,
        height=height,
        format=format,
        quality=quality,
        lossless=lossless,
        stylesheets=sheets,
        images=images,
        fonts=fonts,
        renderer=renderer,
        device_pixel_ratio=device_pixel_ratio,
        font_families=font_families,
        lang=lang,
        draw_debug_border=draw_debug_border,
        max_depth=max_depth,
        use_presets=use_presets,
        overflow=overflow,
        save_to=save_to,
    )


def render_markdown(
    source: str,
    *,
    width: int = 800,
    height: int | None = None,
    format: Format = "png",
    quality: int | None = None,
    lossless: bool | None = None,
    stylesheets: Sequence[str] | None = None,
    css: str | None = None,
    images: Mapping[str, bytes] | Sequence[Mapping[str, Any]] | None = None,
    renderer: Renderer | None = None,
    device_pixel_ratio: float | None = None,
    font_families: Sequence[str] | None = None,
    lang: str | None = None,
    dark: bool = False,
    overflow: Literal["hidden", "visible"] = "hidden",
    save_to: str | Path | None = None,
) -> bytes:
    """Deprecated alias for :func:`md_to_pic`. Use ``md_to_pic`` instead."""
    warnings.warn(
        "render_markdown is deprecated, use md_to_pic instead",
        DeprecationWarning,
        stacklevel=2,
    )
    return md_to_pic(
        source,
        width=width,
        height=height,
        format=format,
        quality=quality,
        lossless=lossless,
        dark=dark,
        css=css,
        stylesheets=stylesheets,
        images=images,
        renderer=renderer,
        device_pixel_ratio=device_pixel_ratio,
        font_families=font_families,
        lang=lang,
        overflow=overflow,
        save_to=save_to,
    )
