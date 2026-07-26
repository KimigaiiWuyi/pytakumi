from __future__ import annotations

import struct

from pytakumi import from_html, render_html


def _png_size(data: bytes) -> tuple[int, int]:
    width, height = struct.unpack(">II", data[16:24])
    return width, height


def test_from_html_and_render(renderer):
    tree = from_html(
        '<div style="width:100%;height:100%;display:flex;align-items:center;'
        'justify-content:center;background:#111827;color:white;font-size:32px;'
        'font-family:Geist">Hello HTML</div>'
    )
    png = renderer.render(tree, width=360, height=180)
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    assert _png_size(png) == (360, 180)


def test_render_html_stylesheets(renderer):
    html = '<div class="card">Styled</div>'
    css = """
    .card {
      width: 100%;
      height: 100%;
      display: flex;
      align-items: center;
      justify-content: center;
      background: #0ea5e9;
      color: white;
      font-size: 28px;
      font-family: Geist;
    }
    """
    png = renderer.render_html(html, width=300, height=150, stylesheets=[css])
    assert _png_size(png) == (300, 150)


def test_module_render_html(geist_font_bytes):
    png = render_html(
        '<div style="width:100%;height:100%;background:red"></div>',
        width=50,
        height=50,
        fonts=[geist_font_bytes],
    )
    assert png[:8] == b"\x89PNG\r\n\x1a\n"


def test_tailwind_prop(renderer):
    tree = from_html(
        '<div tw="w-full h-full flex items-center justify-center bg-slate-900">'
        '<span tw="text-white text-2xl" style="font-family:Geist">tw</span></div>'
    )
    png = renderer.render(tree, width=240, height=120)
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
