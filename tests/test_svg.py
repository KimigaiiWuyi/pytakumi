"""SVG backend checks."""

from __future__ import annotations


def test_render_svg_contains_geometry(renderer):
    svg = renderer.render_svg(
        {
            "type": "container",
            "style": {
                "width": "100%",
                "height": "100%",
                "background": "#eeeeee",
                "display": "flex",
                "alignItems": "center",
                "justifyContent": "center",
            },
            "children": [
                {
                    "type": "text",
                    "text": "SVG",
                    "style": {"fontFamily": "Geist", "fontSize": "32px", "color": "#111"},
                }
            ],
        },
        width=240,
        height=120,
    )
    low = svg.lower()
    assert "<svg" in low
    assert "</svg>" in low
    # Real vector backend emits shapes/paths/textish content
    assert any(tag in low for tag in ("<rect", "<path", "<g", "text"))


def test_render_svg_from_html(renderer):
    svg = renderer.render_svg(
        {
            "type": "container",
            "style": {"width": "100%", "height": "100%", "background": "red"},
            "children": [],
        },
        width=50,
        height=50,
    )
    assert "svg" in svg.lower()
