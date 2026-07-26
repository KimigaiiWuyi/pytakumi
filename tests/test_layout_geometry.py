"""Geometric / color layout probes (product correctness)."""

from __future__ import annotations

from helpers import (
    assert_near_rgb,
    assert_png,
    assert_raw_rgba,
    color_swatch_html,
    full_bleed,
    raw_pixel,
)


def test_swatches_absolute_positions(renderer):
    raw = renderer.render_html(
        color_swatch_html(),
        width=200,
        height=100,
        format="raw",
    )
    assert_raw_rgba(raw, 200, 100)
    # Sample centers of each 50×50 swatch
    assert_near_rgb(raw_pixel(raw, 200, 25, 25), (255, 0, 0), tol=5, label="red")
    assert_near_rgb(raw_pixel(raw, 200, 75, 25), (0, 255, 0), tol=5, label="green")
    assert_near_rgb(raw_pixel(raw, 200, 125, 25), (0, 0, 255), tol=5, label="blue")
    assert_near_rgb(raw_pixel(raw, 200, 175, 25), (255, 255, 255), tol=5, label="white")
    # Bottom black background
    assert_near_rgb(raw_pixel(raw, 200, 100, 75), (0, 0, 0), tol=5, label="bg")


def test_flex_center_text_region_not_blank(renderer):
    png = renderer.render_html(
        """
        <div style="width:100%;height:100%;display:flex;align-items:center;
                    justify-content:center;background:#0f172a;color:#f8fafc;
                    font-size:40px;font-family:Geist">OK</div>
        """,
        width=300,
        height=150,
    )
    assert_png(png, width=300, height=150)


def test_css_grid_three_columns(renderer):
    html = """
    <div style="width:100%;height:100%;display:grid;grid-template-columns:1fr 1fr 1fr;gap:0">
      <div style="background:#ff0000"></div>
      <div style="background:#00ff00"></div>
      <div style="background:#0000ff"></div>
    </div>
    """
    raw = renderer.render_html(html, width=300, height=60, format="raw")
    assert_near_rgb(raw_pixel(raw, 300, 50, 30), (255, 0, 0), tol=20, label="col1")
    assert_near_rgb(raw_pixel(raw, 300, 150, 30), (0, 255, 0), tol=20, label="col2")
    assert_near_rgb(raw_pixel(raw, 300, 250, 30), (0, 0, 255), tol=20, label="col3")


def test_stylesheet_class_selector(renderer):
    html = '<div class="box"></div>'
    css = ".box{width:100%;height:100%;background:#123456}"
    raw = renderer.render_html(html, width=40, height=40, format="raw", stylesheets=[css])
    # #123456
    assert_near_rgb(raw_pixel(raw, 40, 20, 20), (0x12, 0x34, 0x56), tol=8)


def test_inline_style_beats_stylesheet(renderer):
    html = '<div class="box" style="background:#ff00ff;width:100%;height:100%"></div>'
    css = ".box{background:#00ffff}"
    raw = renderer.render_html(html, width=20, height=20, format="raw", stylesheets=[css])
    assert_near_rgb(raw_pixel(raw, 20, 10, 10), (255, 0, 255), tol=8)


def test_transparent_root_png_has_alpha(renderer):
    # Semi-transparent red over default; PNG must keep alpha channel usable
    html = full_bleed("rgba(255,0,0,0.5)")
    png = renderer.render_html(html, width=16, height=16, format="png")
    assert_png(png, width=16, height=16)


def test_auto_height_content_sized(renderer):
    # Omit height: content should still produce a non-zero height image
    png = renderer.render_html(
        '<div style="padding:20px;background:#eee;font-family:Geist;font-size:20px">line1<br/>line2<br/>line3</div>',
        width=200,
    )
    w, h = assert_png(png)
    assert w == 200
    assert h > 40
