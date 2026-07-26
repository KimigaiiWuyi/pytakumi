"""Node builder API product coverage."""

from __future__ import annotations

import pytest

from helpers import assert_png


def test_container_nesting_and_meta(renderer):
    from pytakumi import container, text_node

    child = text_node(
        "nested",
        style={"fontFamily": "Geist", "fontSize": "18px", "color": "#fff"},
        class_name="t",
        id="t1",
        lang="en",
    )
    root = container(
        [child],
        style={
            "width": "100%",
            "height": "100%",
            "display": "flex",
            "alignItems": "center",
            "justifyContent": "center",
            "background": "#2f3640",
        },
        tw="p-4",
        class_name="root",
        tag_name="section",
    )
    assert "container" in repr(root)
    assert "text" in repr(child)
    png = renderer.render(root, width=200, height=100)
    assert_png(png, width=200, height=100)


def test_image_node_url_and_render(renderer, red_png_bytes):
    from pytakumi import container, image_node

    img = image_node("https://example.invalid/x.png", width=10, height=10)
    assert "image" in repr(img)
    # Prefer bytes source that does not need network
    root = container(
        [image_node(red_png_bytes)],
        style={"width": "100%", "height": "100%"},
    )
    png = renderer.render(root, width=48, height=48)
    assert_png(png, width=48, height=48)


def test_dict_and_nodetree_interchange(renderer):
    from pytakumi import from_html

    tree = from_html('<div style="width:100%;height:100%;background:#445566"></div>')
    png = renderer.render(tree, width=30, height=30)
    assert_png(png, width=30, height=30)


def test_module_render_and_render_html(geist_font_bytes):
    from pytakumi import render, render_html

    node = {
        "type": "container",
        "style": {"width": "100%", "height": "100%", "background": "#010203"},
        "children": [],
    }
    assert_png(render(node, width=20, height=20, fonts=[geist_font_bytes]), width=20, height=20)
    assert_png(
        render_html(
            '<div style="width:100%;height:100%;background:#102030"></div>',
            width=20,
            height=20,
            fonts=[geist_font_bytes],
        ),
        width=20,
        height=20,
    )
