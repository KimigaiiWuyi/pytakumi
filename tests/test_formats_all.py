"""All static output formats and density options."""

from __future__ import annotations

import pytest

from helpers import (
    assert_ico,
    assert_jpeg,
    assert_near_rgb,
    assert_png,
    assert_raw_rgba,
    assert_webp,
    full_bleed,
    raw_pixel,
)


def _solid(renderer, color: str, **kw):
    return renderer.render_html(full_bleed(color), width=32, height=24, **kw)


def test_png_default(renderer):
    data = _solid(renderer, "#112233")
    assert_png(data, width=32, height=24)


def test_jpeg(renderer):
    data = _solid(renderer, "#ff0000", format="jpeg", quality=85)
    assert_jpeg(data)


def test_webp_lossless_and_lossy(renderer):
    lossless = _solid(renderer, "#00ff00", format="webp", lossless=True)
    assert_webp(lossless)
    lossy = _solid(renderer, "#00ff00", format="webp", quality=70, lossless=False)
    assert_webp(lossy)


def test_ico(renderer):
    # ICO path may restrict size; use small square
    data = renderer.render_html(full_bleed("#0000ff"), width=32, height=32, format="ico")
    assert_ico(data)


def test_raw_exact_color(renderer):
    raw = _solid(renderer, "#ff0000", format="raw")
    assert_raw_rgba(raw, 32, 24)
    # Center pixel should be pure red (straight alpha)
    r, g, b, a = raw_pixel(raw, 32, 16, 12)
    assert_near_rgb((r, g, b), (255, 0, 0), tol=2)
    assert a == 255


def test_device_pixel_ratio_accepted(renderer):
    # DPR is forwarded to the engine viewport; assert it does not error and
    # still produces a valid frame at the requested CSS viewport size.
    png1 = _solid(renderer, "#abcdef", device_pixel_ratio=1)
    png2 = _solid(renderer, "#abcdef", device_pixel_ratio=2)
    assert_png(png1, width=32, height=24)
    assert_png(png2, width=32, height=24)


def test_jpg_alias(renderer):
    data = _solid(renderer, "#123456", format="jpg", quality=50)
    assert_jpeg(data)


def test_draw_debug_border_still_valid_png(renderer):
    data = _solid(renderer, "#222222", draw_debug_border=True)
    assert_png(data, width=32, height=24)


@pytest.mark.parametrize("algo", ["none", "ordered-bayer", "floyd-steinberg"])
def test_dithering_options(renderer, algo):
    data = _solid(renderer, "#808080", dithering=algo)
    assert_png(data, width=32, height=24)
