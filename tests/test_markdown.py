from __future__ import annotations

import struct

from pytakumi import render_markdown
from pytakumi.markdown import markdown_to_html, wrap_markdown_html


def test_simple_markdown_to_html():
    html = markdown_to_html("# Title\n\nHello **world**\n\n- a\n- b\n")
    assert "<h1>" in html
    assert "<strong>" in html or "<p>" in html
    assert "<li>" in html


def test_wrap_markdown_html():
    wrapped = wrap_markdown_html("<p>hi</p>")
    assert 'class="markdown-body"' in wrapped


def test_render_markdown(renderer):
    md = """# Hello

This is a **markdown** document.

- item one
- item two

```python
print("hi")
```
"""
    png = render_markdown(md, width=600, height=None, renderer=renderer)
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    width, height = struct.unpack(">II", png[16:24])
    assert width == 600
    assert height > 100


def test_render_markdown_dark(renderer):
    png = render_markdown("# Dark", width=400, height=200, renderer=renderer, dark=True)
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
