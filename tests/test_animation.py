"""Animation formats and scene shapes."""

from __future__ import annotations

import pytest

from helpers import assert_webp


def _scenes():
    return [
        (
            {
                "type": "container",
                "style": {"width": "100%", "height": "100%", "background": "#ff0000"},
                "children": [],
            },
            80,
        ),
        (
            {
                "type": "container",
                "style": {"width": "100%", "height": "100%", "background": "#0000ff"},
                "children": [],
            },
            80,
        ),
    ]


def test_animation_webp(renderer):
    data = renderer.render_animation(_scenes(), width=48, height=48, fps=10, format="webp")
    assert_webp(data)


def test_animation_dict_scenes(renderer):
    scenes = [
        {"node": _scenes()[0][0], "duration_ms": 60},
        {"node": _scenes()[1][0], "durationMs": 60},
    ]
    data = renderer.render_animation(scenes, width=32, height=32, fps=8, format="webp", lossless=True)
    assert_webp(data)


@pytest.mark.parametrize("fmt", ["gif", "apng"])
def test_animation_gif_apng(renderer, fmt):
    data = renderer.render_animation(_scenes(), width=32, height=32, fps=5, format=fmt)
    assert isinstance(data, (bytes, bytearray))
    assert len(data) > 32
    if fmt == "gif":
        assert data[:3] == b"GIF" or data[:6] in (b"GIF87a", b"GIF89a")
    # APNG is PNG-based
    if fmt == "apng":
        assert data[:8] == b"\x89PNG\r\n\x1a\n"


def test_animation_with_nodetree(renderer):
    from pytakumi import container

    a = container([], style={"width": "100%", "height": "100%", "background": "#0f0"})
    b = container([], style={"width": "100%", "height": "100%", "background": "#00f"})
    data = renderer.render_animation([(a, 50), (b, 50)], width=24, height=24, fps=10)
    assert_webp(data)
