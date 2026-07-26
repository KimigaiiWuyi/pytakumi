"""Pure-Python utility coverage."""

from __future__ import annotations

import pytest

from pytakumi._util import (
    escape,
    extract_styles_and_body,
    load_template,
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
