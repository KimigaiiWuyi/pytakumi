"""Error handling and invalid inputs."""

from __future__ import annotations

import pytest

from helpers import full_bleed


def test_unknown_static_format(renderer):
    with pytest.raises(ValueError, match="unknown output format"):
        renderer.render({"type": "container", "children": []}, width=8, height=8, format="bmp")


def test_unknown_animation_format(renderer):
    with pytest.raises(ValueError, match="unknown animation format"):
        renderer.render_animation(
            [({"type": "container", "children": []}, 50)],
            width=16,
            height=16,
            fps=5,
            format="mp4",
        )


def test_unknown_dithering(renderer):
    with pytest.raises(ValueError, match="unknown dithering"):
        renderer.render(
            {"type": "container", "style": {"width": "100%", "height": "100%", "background": "#000"}, "children": []},
            width=8,
            height=8,
            dithering="not-a-algo",
        )


def test_invalid_node_type(renderer):
    with pytest.raises(Exception):
        renderer.render({"type": "spaceship", "children": []}, width=8, height=8)


def test_from_html_max_depth_exceeded():
    from pytakumi import from_html

    deep = "<div>" * 20 + "x" + "</div>" * 20
    with pytest.raises(Exception):
        from_html(deep, max_depth=3)


def test_invalid_lang(renderer):
    with pytest.raises(Exception):
        renderer.render_html(
            full_bleed("#111"),
            width=20,
            height=20,
            lang="not a real language tag!!!!!",
        )


def test_image_node_bad_src_type():
    from pytakumi import image_node

    with pytest.raises(TypeError):
        image_node(12345)  # type: ignore[arg-type]


def test_html_to_pic_invalid_font_entry():
    from pytakumi import html_to_pic

    with pytest.raises((TypeError, ValueError)):
        html_to_pic(full_bleed("#000"), width=20, height=20, fonts=[{"name": "x"}])  # type: ignore[list-item]


def test_empty_animation_rejected(renderer):
    with pytest.raises(Exception):
        renderer.render_animation([], width=16, height=16, fps=10)
