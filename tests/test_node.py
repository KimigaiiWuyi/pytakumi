from __future__ import annotations

from pytakumi import NodeTree, container, from_html, image_node, text_node


def test_from_html_repr():
    tree = from_html("<div>hi</div>")
    assert isinstance(tree, NodeTree)
    assert "NodeTree" in repr(tree)


def test_text_and_container():
    t = text_node("hello", tw="text-xl", class_name="title")
    c = container([t], style={"display": "flex"})
    assert "container" in repr(c)
    assert "text" in repr(t)


def test_image_node_url():
    img = image_node("https://example.com/a.png", width=100, height=50)
    assert "image" in repr(img)
