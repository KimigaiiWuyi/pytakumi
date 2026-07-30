"""Pure-Python utility coverage."""

from __future__ import annotations

import pytest

from pytakumi._util import (
    escape,
    extract_styles_and_body,
    load_template,
    normalize_device_pixel_ratio,
    register_fonts,
    resolve_renderer,
)


def test_escape_entities():
    assert "&lt;" in escape("<a>")
    assert "&amp;" in escape("a&b")
    assert "&quot;" in escape('say "hi"')


def test_load_templates_exist():
    for name in (
        "github-markdown.css",
        "github-markdown-dark.css",
        "text-card.css",
    ):
        css = load_template(name)
        assert len(css) > 50
        assert "{" in css


def test_extract_styles_rewrites_body_and_strips_import():
    html = """
    <html><head><style>
    @import url('http://example.com/x.css');
    body { color: red; }
    .x { padding: 1px; }
    </style></head>
    <body><div class="x">hi<script>bad()</script></div></body></html>
    """
    styles, body = extract_styles_and_body(html, 100, 50)
    assert styles
    assert "@import" not in styles[0]
    assert "pytakumi-root" in styles[0] or "body" not in styles[0].split("{")[0]
    assert "script" not in body.lower() or "bad" not in body
    assert "pytakumi-root" in body
    assert "width:100px" in body
    assert "height:50px" in body


def test_extract_styles_scales_root_by_device_pixel_ratio():
    html = "<body><div>hi</div></body>"
    # width/height are device pixels; with dpr=2 the CSS viewport is half, so
    # the root wrapper must be sized in CSS pixels to avoid right-edge clipping.
    _styles, body = extract_styles_and_body(html, 1600, 1000, device_pixel_ratio=2)
    assert "width:800px" in body
    assert "height:500px" in body
    assert "width:1600px" not in body

    # No ratio (or ratio=1) keeps device pixels == CSS pixels.
    _styles, body = extract_styles_and_body(html, 1600, 1000)
    assert "width:1600px" in body
    assert "height:1000px" in body

    _styles, body = extract_styles_and_body(html, 1600, None, device_pixel_ratio=1)
    assert "width:1600px" in body
    assert "height:" not in body


def test_normalize_device_pixel_ratio_rejects_invalid_values():
    assert normalize_device_pixel_ratio(None) == 1.0
    assert normalize_device_pixel_ratio(2) == 2.0
    with pytest.raises(ValueError):
        normalize_device_pixel_ratio(0)
    with pytest.raises(ValueError):
        normalize_device_pixel_ratio(-1.5)
    with pytest.raises(ValueError):
        normalize_device_pixel_ratio(float("nan"))
    with pytest.raises(ValueError):
        normalize_device_pixel_ratio(float("inf"))


def test_extract_styles_rejects_invalid_device_pixel_ratio():
    html = "<body><div>hi</div></body>"
    with pytest.raises(ValueError):
        extract_styles_and_body(html, 100, 100, device_pixel_ratio=0)


def test_extract_styles_overflow_option():
    html = "<body><div>hi</div></body>"
    _styles, body = extract_styles_and_body(html, 100, 100, overflow="visible")
    assert "overflow:visible" in body
    assert "overflow:hidden" not in body

    _styles, body = extract_styles_and_body(html, 100, 100)
    assert "overflow:hidden" in body

    with pytest.raises(ValueError):
        extract_styles_and_body(html, 100, 100, overflow="scroll")


def test_extract_styles_rewrites_html_and_body_selectors():
    html = "<html><head><style>html, body { color: red; }</style></head><body>x</body></html>"
    styles, body = extract_styles_and_body(html, 100, None)
    assert styles
    assert ".pytakumi-root" in styles[0]
    assert "html" not in styles[0].split("{")[0]
    assert "body" not in styles[0].split("{")[0]
    assert "pytakumi-root" in body


def test_resolve_renderer_fonts(geist_font_bytes):
    from pytakumi import Renderer

    r = resolve_renderer(None, [{"data": geist_font_bytes, "name": "X"}])
    assert isinstance(r, Renderer)
    # default singleton path
    r2 = resolve_renderer(None, None)
    assert isinstance(r2, Renderer)


def test_register_fonts_bad_type():
    from pytakumi import Renderer

    r = Renderer()
    with pytest.raises(TypeError):
        register_fonts(r, [object()])  # type: ignore[list-item]


def test_register_fonts_missing_data():
    from pytakumi import Renderer

    r = Renderer()
    with pytest.raises(ValueError):
        register_fonts(r, [{"name": "x"}])
