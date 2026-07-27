"""Markdown parsing helpers (shared by md_to_pic / legacy render_markdown)."""

from __future__ import annotations

import re
from typing import Any, Mapping, Sequence

# Re-export high-level API for backwards compatibility.
# (render_markdown implemented at bottom to avoid circular imports at type-check time)


def markdown_to_html(source: str, *, renderer: str | None = None) -> str:
    """Convert Markdown to HTML.

    Uses ``markdown-it-py`` when installed (``pip install pytakumi[markdown]``).
    Falls back to a tiny built-in converter for headings, paragraphs, lists,
    code fences, and emphasis so tests work without optional deps.

    Post-processes GFM ``<table>`` into flex markup because the Takumi layout
    engine does not implement CSS table layout (``display: table`` / ``table-cell``).

    **Not supported as rich render** (left as code/text by design, no browser JS):

    - Mermaid fenced blocks (`` ```mermaid ``) → ``<pre><code class="language-mermaid">``
    - Math (``$...$`` / ``$$...$$``) → plain text; no KaTeX/MathJax
    """
    try:
        from markdown_it import MarkdownIt
    except ImportError:
        return rewrite_tables_for_takumi(_simple_markdown_to_html(source))

    md = MarkdownIt(renderer or "commonmark", {"html": False, "linkify": False})
    try:
        md = md.enable("strikethrough").enable("table")
    except Exception:
        pass
    return rewrite_tables_for_takumi(md.render(source))


def rewrite_tables_for_takumi(html: str) -> str:
    """Rewrite ``<table>…</table>`` into flex-row markup Takumi can paint.

    Upstream GitHub-ish CSS uses ``table { display: block }`` (scroll wrapper).
    Combined with no CSS table layout in the engine, native ``<table>`` collapses
    into a single inline run of cell text. Flex rows restore a readable grid.
    """
    if "<table" not in html:
        return html

    def _cell_htmls(row_inner: str) -> list[str]:
        return re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", row_inner, flags=re.I | re.S)

    def _repl_table(match: re.Match[str]) -> str:
        table = match.group(0)
        rows = re.findall(r"<tr[^>]*>(.*?)</tr>", table, flags=re.I | re.S)
        if not rows:
            return table

        parsed: list[tuple[list[str], bool]] = []
        for row in rows:
            cells = _cell_htmls(row)
            if not cells:
                continue
            is_header = bool(re.search(r"<th\b", row, flags=re.I))
            parsed.append((cells, is_header))
        if not parsed:
            return table

        n_cols = max(len(c) for c, _ in parsed)
        if n_cols == 0:
            return table

        parts = ['<div class="md-table" role="table">']
        for r_i, (cells, is_header) in enumerate(parsed):
            # pad short rows
            while len(cells) < n_cols:
                cells.append("")
            row_cls = "md-table-row md-table-header" if is_header else "md-table-row"
            if not is_header and r_i % 2 == 0:
                row_cls += " md-table-row-alt"
            parts.append(f'<div class="{row_cls}" role="row">')
            for c_i, cell in enumerate(cells):
                cell_cls = "md-table-cell md-table-th" if is_header else "md-table-cell"
                if c_i < n_cols - 1:
                    cell_cls += " md-table-cell-border"
                parts.append(f'<div class="{cell_cls}" role="cell">{cell}</div>')
            parts.append("</div>")
        parts.append("</div>")
        return "".join(parts)

    # Non-greedy, non-nested tables (markdown-it output is flat).
    return re.sub(r"<table\b[^>]*>.*?</table>", _repl_table, html, flags=re.I | re.S)


def _simple_markdown_to_html(source: str) -> str:
    """Very small Markdown subset → HTML (no external deps)."""
    import html as html_lib
    import re

    lines = source.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    out: list[str] = []
    in_code = False
    code_lang = ""
    code_buf: list[str] = []
    in_ul = False
    in_ol = False
    para: list[str] = []

    def flush_para() -> None:
        nonlocal para
        if para:
            text = " ".join(para)
            out.append(f"<p>{_inline(text)}</p>")
            para = []

    def close_lists() -> None:
        nonlocal in_ul, in_ol
        if in_ul:
            out.append("</ul>")
            in_ul = False
        if in_ol:
            out.append("</ol>")
            in_ol = False

    def _inline(text: str) -> str:
        text = html_lib.escape(text)
        text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
        text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
        text = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", text)
        text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', text)
        return text

    for raw in lines:
        if raw.startswith("```"):
            flush_para()
            close_lists()
            if not in_code:
                in_code = True
                code_lang = raw[3:].strip()
                code_buf = []
            else:
                code = html_lib.escape("\n".join(code_buf))
                cls = f' class="language-{html_lib.escape(code_lang)}"' if code_lang else ""
                out.append(f"<pre><code{cls}>{code}</code></pre>")
                in_code = False
            continue
        if in_code:
            code_buf.append(raw)
            continue

        if not raw.strip():
            flush_para()
            close_lists()
            continue

        heading = re.match(r"^(#{1,6})\s+(.*)$", raw)
        if heading:
            flush_para()
            close_lists()
            level = len(heading.group(1))
            out.append(f"<h{level}>{_inline(heading.group(2))}</h{level}>")
            continue

        if re.match(r"^(-{3,}|\*{3,}|_{3,})$", raw.strip()):
            flush_para()
            close_lists()
            out.append("<hr />")
            continue

        ul = re.match(r"^[-*+]\s+(.*)$", raw)
        if ul:
            flush_para()
            if in_ol:
                out.append("</ol>")
                in_ol = False
            if not in_ul:
                out.append("<ul>")
                in_ul = True
            out.append(f"<li>{_inline(ul.group(1))}</li>")
            continue

        ol = re.match(r"^(\d+)\.\s+(.*)$", raw)
        if ol:
            flush_para()
            if in_ul:
                out.append("</ul>")
                in_ul = False
            if not in_ol:
                out.append("<ol>")
                in_ol = True
            out.append(f"<li>{_inline(ol.group(2))}</li>")
            continue

        close_lists()
        para.append(raw.strip())

    flush_para()
    close_lists()
    if in_code:
        code = html_lib.escape("\n".join(code_buf))
        out.append(f"<pre><code>{code}</code></pre>")
    return "\n".join(out)


def wrap_markdown_html(body_html: str, *, class_name: str = "markdown-body") -> str:
    """Wrap fragment HTML in a root container used by the default stylesheet."""
    return f'<div class="{class_name}">{body_html}</div>'


def render_markdown(
    source: str,
    *,
    width: int = 800,
    height: int | None = None,
    format: str = "png",
    quality: int | None = None,
    lossless: bool | None = None,
    stylesheets: Sequence[str] | None = None,
    css: str | None = None,
    images: Mapping[str, bytes] | Sequence[Mapping[str, Any]] | None = None,
    renderer=None,
    device_pixel_ratio: float | None = None,
    font_families: Sequence[str] | None = None,
    lang: str | None = None,
    dark: bool = False,
) -> bytes:
    """Legacy alias for :func:`takumi.md_to_pic` (GitHub-style template)."""
    from pytakumi.api import md_to_pic

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
    )
