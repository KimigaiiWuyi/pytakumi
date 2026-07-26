"""HTML parsing, presets, nesting, styles extraction."""

from __future__ import annotations

import pytest

from helpers import assert_png, full_bleed


def test_full_document_with_style_tag(renderer):
    html = """
    <!DOCTYPE html>
    <html><head>
      <style>.x{width:100%;height:100%;background:#0a0;}</style>
    </head>
    <body><div class="x"></div></body></html>
    """
    from pytakumi import html_to_pic

    # html_to_pic extracts style tags
    png = html_to_pic(html, width=40, height=40, renderer=renderer)
    assert_png(png, width=40, height=40)


def test_from_html_presets_on_off(renderer):
    from pytakumi import from_html

    with_p = from_html("<h1>Title</h1>", use_presets=True)
    without = from_html("<h1>Title</h1>", use_presets=False)
    assert "NodeTree" in repr(with_p)
    assert "NodeTree" in repr(without)
    png = renderer.render(
        with_p,
        width=300,
        height=80,
        stylesheets=["h1,div,span{color:#111;font-family:Geist}"],
    )
    assert_png(png)


def test_render_html_max_depth_ok(renderer):
    nested = "<div style='padding:2px'>" * 10 + "deep" + "</div>" * 10
    png = renderer.render_html(nested, width=200, height=100, max_depth=32)
    assert_png(png)


def test_tailwind_arbitrary_and_utilities(renderer):
    html = """
    <div tw="w-full h-full flex items-center justify-center bg-slate-900">
      <span tw="text-white text-xl" style="font-family:Geist">tw</span>
    </div>
    """
    png = renderer.render_html(html, width=200, height=100)
    assert_png(png, width=200, height=100)


def test_pseudo_not_required_for_static(renderer):
    # Hover rules parse but must not crash static frame
    css = ".a:hover{color:red} .a{width:100%;height:100%;background:#333;color:#fff}"
    png = renderer.render_html('<div class="a">x</div>', width=80, height=40, stylesheets=[css])
    assert_png(png)


def test_multiple_stylesheets(renderer):
    png = renderer.render_html(
        '<div class="a b"></div>',
        width=30,
        height=30,
        stylesheets=[
            ".a{width:100%;height:100%}",
            ".b{background:#abcdef}",
        ],
    )
    assert_png(png, width=30, height=30)


def test_script_and_style_stripped_from_body(renderer):
    html = """
    <div style="width:100%;height:100%;background:#111;color:#fff;font-family:Geist">
      <script>alert(1)</script>
      <style>.x{color:red}</style>
      visible
    </div>
    """
    png = renderer.render_html(html, width=160, height=60)
    assert_png(png)


def test_lang_and_dir(renderer):
    png = renderer.render_html(
        full_bleed("#222", "color:#fff;font-family:Geist;font-size:18px"),
        width=100,
        height=50,
        lang="en",
    )
    assert_png(png)
