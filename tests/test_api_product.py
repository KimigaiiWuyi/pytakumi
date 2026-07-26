"""Product-grade coverage for html_to_pic / text_to_pic / md_to_pic."""

from __future__ import annotations

import pytest

from helpers import assert_jpeg, assert_png, assert_webp, full_bleed


def test_html_to_pic_css_kwarg(renderer):
    from pytakumi import html_to_pic

    png = html_to_pic(
        '<div class="c"></div>',
        width=50,
        height=50,
        css=".c{width:100%;height:100%;background:#192a56}",
        renderer=renderer,
    )
    assert_png(png, width=50, height=50)


def test_html_to_pic_formats(renderer):
    from pytakumi import html_to_pic

    html = full_bleed("#334455")
    assert_png(html_to_pic(html, width=40, height=30, renderer=renderer))
    assert_jpeg(html_to_pic(html, width=40, height=30, format="jpeg", quality=70, renderer=renderer))
    assert_webp(html_to_pic(html, width=40, height=30, format="webp", lossless=True, renderer=renderer))


def test_html_to_pic_extracts_embedded_style():
    from pytakumi import html_to_pic

    doc = """
    <html><head><style>
      .box { width:100%; height:100%; background:#e84118; }
    </style></head>
    <body><div class="box"></div></body></html>
    """
    png = html_to_pic(doc, width=60, height=40)
    assert_png(png, width=60, height=40)


def test_text_to_pic_escapes_html():
    from pytakumi import text_to_pic

    png = text_to_pic(
        '<script>alert(1)</script> & "quotes"',
        title="<b>title</b>",
        eyebrow="E",
        footer="f",
        width=500,
        height=280,
    )
    assert_png(png, width=500, height=280)


def test_text_to_pic_themes_and_auto_height():
    from pytakumi import text_to_pic

    dark = text_to_pic("hello", theme="dark", width=400, height=200)
    light = text_to_pic("hello", theme="light", width=400, height=200)
    auto = text_to_pic("a\nb\nc\nd\ne", width=400)  # height auto
    assert_png(dark, width=400, height=200)
    assert_png(light, width=400, height=200)
    w, h = assert_png(auto)
    assert w == 400
    assert h >= 360


def test_md_to_pic_features(renderer):
    from pytakumi import md_to_pic

    md = """# Heading 1

## Heading 2

Paragraph with **bold**, *em*, and `code`.

- list a
- list b

1. one
2. two

> quote

---

| Col | Val |
| --- | --- |
| a | 1 |

```python
x = 1
```

[link](https://example.com)
"""
    png = md_to_pic(md, width=720, renderer=renderer)
    w, h = assert_png(png)
    assert w == 720
    assert h > 200


def test_md_to_pic_dark_fixed_size(renderer):
    from pytakumi import md_to_pic

    png = md_to_pic("# Dark mode\n\nok", width=480, height=320, dark=True, renderer=renderer)
    assert_png(png, width=480, height=320)


def test_md_to_pic_extra_css(renderer):
    from pytakumi import md_to_pic

    png = md_to_pic(
        "# X",
        width=300,
        height=200,
        css=".markdown-body{padding:8px}",
        renderer=renderer,
    )
    assert_png(png, width=300, height=200)


def test_render_markdown_alias(renderer):
    from pytakumi import md_to_pic, render_markdown

    a = md_to_pic("# A", width=200, height=120, renderer=renderer)
    b = render_markdown("# A", width=200, height=120, renderer=renderer)
    assert_png(a)
    assert_png(b)
    # Same pipeline → identical dimensions
    from helpers import assert_png as ap

    assert ap(a)[0] == ap(b)[0]


def test_reuse_renderer_across_helpers(renderer, geist_font_bytes):
    from pytakumi import html_to_pic, md_to_pic, text_to_pic

    fonts = [{"data": geist_font_bytes, "name": "Geist"}]
    for fn in (
        lambda: html_to_pic(full_bleed("#111"), width=40, height=40, renderer=renderer),
        lambda: text_to_pic("x", width=200, height=120, renderer=renderer),
        lambda: md_to_pic("# y", width=200, height=120, renderer=renderer),
    ):
        assert_png(fn())


def test_html_to_pic_dpr(renderer):
    from pytakumi import html_to_pic

    png = html_to_pic(
        full_bleed("#000"),
        width=50,
        height=40,
        device_pixel_ratio=2,
        renderer=renderer,
    )
    assert_png(png, width=50, height=40)
