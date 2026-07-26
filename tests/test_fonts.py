"""Font registration and font stack options."""

from __future__ import annotations

import pytest

from helpers import assert_png, full_bleed


def test_register_font_returns_families(renderer_empty, geist_font_bytes):
    families = renderer_empty.register_font(geist_font_bytes, name="Geist")
    assert isinstance(families, list)
    assert len(families) >= 1
    assert "name" in families[0]
    assert families[0]["name"]


def test_register_font_with_weight_override(renderer_empty, geist_font_bytes):
    families = renderer_empty.register_font(
        geist_font_bytes,
        name="GeistBoldish",
        weight=700,
        style="normal",
    )
    assert families


def test_font_families_option(renderer):
    png = renderer.render_html(
        '<div style="width:100%;height:100%;font-size:28px;color:#fff;background:#111">Aa</div>',
        width=120,
        height=60,
        font_families=["Geist"],
    )
    assert_png(png, width=120, height=60)


def test_module_render_html_with_fonts_list(geist_font_bytes):
    from pytakumi import render_html

    png = render_html(
        full_bleed("#222", "color:#fff;font-family:Geist;font-size:20px"),
        width=80,
        height=40,
        fonts=[geist_font_bytes],
    )
    assert_png(png, width=80, height=40)


def test_html_to_pic_fonts_dict(geist_font_bytes):
    from pytakumi import html_to_pic

    png = html_to_pic(
        full_bleed("#000", "color:white;font-family:Custom;font-size:18px"),
        width=100,
        height=50,
        fonts=[{"data": geist_font_bytes, "name": "Custom"}],
    )
    assert_png(png, width=100, height=50)


def test_invalid_font_bytes(renderer_empty):
    with pytest.raises(Exception):
        renderer_empty.register_font(b"not-a-font-file")
