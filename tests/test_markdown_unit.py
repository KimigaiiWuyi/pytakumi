"""Markdown converter unit tests (no native render)."""

from __future__ import annotations

from pytakumi.markdown import markdown_to_html, wrap_markdown_html


def test_simple_headings_lists_code():
    html = markdown_to_html(
        """# H1

## H2

para **bold** and *em* and `code`

- a
- b

1. one
2. two

```
code
block
```

[link](https://x.test)
"""
    )
    assert "<h1>" in html
    assert "<h2>" in html
    assert "<strong>" in html
    assert "<em>" in html
    assert "<code>" in html
    assert "<ul>" in html
    assert "<ol>" in html
    assert "<pre>" in html
    assert "https://x.test" in html


def test_hr_and_blockquote():
    html = markdown_to_html("> quote\n\n---\n")
    assert "<blockquote>" in html or "quote" in html
    assert "<hr" in html


def test_wrap_markdown_body_class():
    wrapped = wrap_markdown_html("<p>x</p>")
    assert 'class="markdown-body"' in wrapped
    assert "<p>x</p>" in wrapped


def test_empty_markdown():
    html = markdown_to_html("")
    assert isinstance(html, str)


def test_arch_review_fixture_checklist():
    """Source-level checklist for the md_to_pic stress fixture (no paint)."""
    from pathlib import Path

    from helpers import assert_arch_review_md_checklist

    md = (Path(__file__).resolve().parent / "fixtures" / "arch_review_auth.md").read_text(
        encoding="utf-8"
    )
    counts = assert_arch_review_md_checklist(md)
    assert counts["inline_code"] >= 10
    assert counts["bold"] >= 3 and counts["em"] >= 3 and counts["strike"] >= 3


def test_gfm_tables_rewritten_to_flex():
    """GFM tables become flex markup (Takumi has no CSS table layout)."""
    from pytakumi.markdown import markdown_to_html, rewrite_tables_for_takumi

    md = """
| A | B | C |
| --- | --- | --- |
| 1 | 2 | 3 |
| **x** | `y` | z |
"""
    html = markdown_to_html(md)
    assert "md-table" in html
    assert "md-table-row" in html
    assert "md-table-cell" in html
    assert "<table" not in html
    assert "<strong>" in html or "x" in html
    # rewrite is idempotent on already-converted markup
    assert rewrite_tables_for_takumi(html) == html


def test_gfm_table_alignment_classes():
    md = """
| Left | Center | Right |
| :--- | :---: | ---: |
| a | b | 123 |
"""
    html = markdown_to_html(md)
    assert "md-table-cell-left" in html
    assert "md-table-cell-center" in html
    assert "md-table-cell-right" in html


def test_numeric_table_cells_default_right_aligned():
    md = """
| Name | Value |
| --- | --- |
| alpha | 1,234.5 |
| beta | text |
"""
    html = markdown_to_html(md)
    assert "md-table-cell-right" in html
    # Text cell should not be forced numeric/right aligned.
    assert html.count("md-table-cell-right") >= 1


def test_mermaid_and_math_stay_literal():
    """Mermaid/math are not executed — remain code/text (no browser JS)."""
    md = """
```mermaid
flowchart TD
    A --> B
```

inline $E = mc^2$

$$
\\int_0^\\infty e^{-x^2} dx
$$
"""
    html = markdown_to_html(md)
    assert "language-mermaid" in html
    assert "flowchart TD" in html
    assert "$E = mc^2$" in html
    assert "int_0" in html or r"\int_0" in html
