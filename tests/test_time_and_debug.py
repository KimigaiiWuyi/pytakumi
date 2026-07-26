"""time_ms, cache sizes, glyph cache."""

from __future__ import annotations

from helpers import assert_png, full_bleed


def test_time_ms_static_frame(renderer):
    # No animation styles; time_ms should still succeed
    png = renderer.render_html(full_bleed("#202020"), width=24, height=24, time_ms=500)
    assert_png(png, width=24, height=24)


def test_renderer_cache_max_bytes_zero():
    from pytakumi import Renderer

    r = Renderer(cache_max_bytes=0)
    png = r.render_html(full_bleed("#111"), width=16, height=16)
    assert_png(png, width=16, height=16)


def test_renderer_large_cache():
    from pytakumi import Renderer

    r = Renderer(cache_max_bytes=32 * 1024 * 1024)
    png = r.render_html(full_bleed("#222"), width=16, height=16)
    assert_png(png, width=16, height=16)


def test_set_glyph_cache_values():
    from pytakumi import set_glyph_cache_max_bytes

    set_glyph_cache_max_bytes(0)
    set_glyph_cache_max_bytes(8 * 1024 * 1024)
    set_glyph_cache_max_bytes(64 * 1024 * 1024)
