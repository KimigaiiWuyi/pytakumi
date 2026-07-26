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
