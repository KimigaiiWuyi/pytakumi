from __future__ import annotations

import struct

import pytest


def _png_size(data: bytes) -> tuple[int, int]:
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    # IHDR: width/height at bytes 16..24
    width, height = struct.unpack(">II", data[16:24])
    return width, height


def test_render_dict_node(renderer):
    node = {
        "type": "container",
        "style": {
            "width": "100%",
            "height": "100%",
            "display": "flex",
            "alignItems": "center",
            "justifyContent": "center",
            "background": "#0f172a",
        },
        "children": [
            {
                "type": "text",
                "text": "Hello Takumi",
                "style": {"color": "#f8fafc", "fontSize": "48px", "fontFamily": "Geist"},
            }
        ],
    }
    png = renderer.render(node, width=400, height=200, format="png")
    assert isinstance(png, (bytes, bytearray))
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    assert _png_size(png) == (400, 200)


def test_render_helpers(renderer):
    from pytakumi import container, text_node

    root = container(
        [text_node("Hi", style={"fontSize": "32px", "color": "white", "fontFamily": "Geist"})],
        style={
            "width": "100%",
            "height": "100%",
            "display": "flex",
            "alignItems": "center",
            "justifyContent": "center",
            "backgroundColor": "#2563eb",
        },
    )
    png = renderer.render(root, width=320, height=160)
    assert _png_size(png) == (320, 160)


def test_render_webp_and_jpeg(renderer):
    node = {
        "type": "container",
        "style": {"width": "100%", "height": "100%", "background": "#f00"},
        "children": [],
    }
    webp = renderer.render(node, width=64, height=64, format="webp", lossless=True)
    assert webp[:4] == b"RIFF" and webp[8:12] == b"WEBP"

    jpeg = renderer.render(node, width=64, height=64, format="jpeg", quality=80)
    assert jpeg[:2] == b"\xff\xd8"


def test_render_raw(renderer):
    node = {
        "type": "container",
        "style": {"width": "100%", "height": "100%", "background": "#00ff00"},
        "children": [],
    }
    raw = renderer.render(node, width=10, height=5, format="raw")
    assert len(raw) == 10 * 5 * 4


def test_module_level_render(geist_font_bytes):
    from pytakumi import render

    node = {
        "type": "container",
        "style": {"width": "100%", "height": "100%", "background": "#111"},
        "children": [{"type": "text", "text": "x", "style": {"color": "#fff", "fontFamily": "Geist"}}],
    }
    png = render(node, width=100, height=50, fonts=[geist_font_bytes])
    assert png[:8] == b"\x89PNG\r\n\x1a\n"


def test_measure(renderer):
    node = {
        "type": "container",
        "style": {"padding": "10px"},
        "children": [{"type": "text", "text": "measure me", "style": {"fontFamily": "Geist"}}],
    }
    result = renderer.measure(node, width=300)
    assert "width" in result and "height" in result
    assert result["width"] > 0
    assert result["height"] > 0


def test_render_svg(renderer):
    node = {
        "type": "container",
        "style": {"width": "100%", "height": "100%", "background": "#eee"},
        "children": [{"type": "text", "text": "SVG", "style": {"fontFamily": "Geist", "fontSize": "24px"}}],
    }
    svg = renderer.render_svg(node, width=200, height=100)
    assert isinstance(svg, str)
    assert "<svg" in svg.lower()


def test_render_animation(renderer):
    scenes = [
        (
            {
                "type": "container",
                "style": {"width": "100%", "height": "100%", "background": "#f00"},
                "children": [],
            },
            100,
        ),
        (
            {
                "type": "container",
                "style": {"width": "100%", "height": "100%", "background": "#00f"},
                "children": [],
            },
            100,
        ),
    ]
    data = renderer.render_animation(scenes, width=40, height=40, fps=10, format="webp")
    assert data[:4] == b"RIFF"


def test_invalid_format(renderer):
    with pytest.raises(ValueError, match="unknown output format"):
        renderer.render(
            {"type": "container", "children": []},
            width=10,
            height=10,
            format="bmp",
        )


def test_glyph_cache_api():
    from pytakumi import set_glyph_cache_max_bytes

    set_glyph_cache_max_bytes(16 * 1024 * 1024)
