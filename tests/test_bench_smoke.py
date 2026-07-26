"""Smoke tests for the benchmark harness (fast subset)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "benchmarks"))


def test_pytakumi_backend_and_layout_probe():
    from backends import TakumiBackend

    b = TakumiBackend()
    ok, reason = b.available()
    if not ok:
        pytest.skip(reason)
    b.setup()
    try:
        html = (ROOT / "benchmarks" / "fixtures" / "layout_check.html").read_text(encoding="utf-8")
        png = b.render(html, 600, 400)
        assert png[:8] == b"\x89PNG\r\n\x1a\n"
        assert len(png) > 500
        # Pixel probes need Pillow (optional bench extra).
        pytest.importorskip("PIL")
        from layout_checks import check_layout_probe, summarize

        results = check_layout_probe(png)
        passed, total, detail = summarize(results)
        assert passed >= max(1, total - 2), detail
    finally:
        b.teardown()


def test_pillow_same_canvas_and_loops():
    from backends import PillowBackend

    b = PillowBackend(draw_loops=10)
    ok, reason = b.available()
    if not ok:
        pytest.skip(reason)
    b.setup()
    # Same dimensions as stamina test2 card.
    png = b.render("<html><body>鸣潮体力</body></html>", 1150, 850)
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    assert len(png) > 1000


def test_load_test2_if_present():
    from run_bench import load_test2

    try:
        html, w, h, path = load_test2()
    except FileNotFoundError:
        pytest.skip("test2 html not on Desktop")
    assert w == 1150 and h == 850
    assert "hud" in html.lower() or "结晶" in html or "div" in html
    assert path.is_file()
