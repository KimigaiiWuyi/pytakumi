"""Layout measurement API."""

from __future__ import annotations


def test_measure_structure(renderer):
    node = {
        "type": "container",
        "style": {"padding": "12px", "display": "flex", "flexDirection": "column"},
        "children": [
            {"type": "text", "text": "Hello", "style": {"fontFamily": "Geist", "fontSize": "20px"}},
            {"type": "text", "text": "World", "style": {"fontFamily": "Geist", "fontSize": "16px"}},
        ],
    }
    m = renderer.measure(node, width=280)
    assert isinstance(m, dict)
    assert m["width"] > 0
    assert m["height"] > 0
    assert "children" in m
    assert isinstance(m["children"], list)
    assert "transform" in m


def test_measure_vs_render_height_sane(renderer):
    html = (
        '<div style="padding:16px;font-family:Geist;font-size:18px;background:#fff">'
        "A<br/>B<br/>C<br/>D</div>"
    )
    from pytakumi import from_html

    tree = from_html(html)
    m = renderer.measure(tree, width=200)
    png = renderer.render(tree, width=200)
    from helpers import assert_png

    _, h = assert_png(png)
    # Measured layout height should be positive and related to rendered height
    assert m["height"] > 0
    assert h >= int(m["height"]) - 2 or h > 40
