"""Pixel / geometry probes for layout correctness.

These checks are intentionally geometric (color swatches, bars, flex boxes)
rather than OCR, so they work offline and stay deterministic.
"""

from __future__ import annotations

import io
import struct
from dataclasses import dataclass
from typing import Sequence

@dataclass
class Probe:
    name: str
    x: int
    y: int
    expected_rgb: tuple[int, int, int]
    tol: int = 40


@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str


def png_size(data: bytes) -> tuple[int, int]:
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("not a PNG")
    w, h = struct.unpack(">II", data[16:24])
    return int(w), int(h)


def open_png(data: bytes):
    from PIL import Image

    return Image.open(io.BytesIO(data)).convert("RGB")


def sample(img, x: int, y: int) -> tuple[int, int, int]:
    x = max(0, min(img.width - 1, x))
    y = max(0, min(img.height - 1, y))
    px = img.getpixel((x, y))
    return int(px[0]), int(px[1]), int(px[2])


def near(a: Sequence[int], b: Sequence[int], tol: int) -> bool:
    return all(abs(int(x) - int(y)) <= tol for x, y in zip(a, b))


def check_layout_probe(png: bytes) -> list[CheckResult]:
    """Checks for fixtures/layout_check.html (600x400)."""
    results: list[CheckResult] = []
    try:
        w, h = png_size(png)
    except Exception as e:
        return [CheckResult("png", False, str(e))]

    results.append(
        CheckResult("size", w == 600 and h == 400, f"got {w}x{h}, expected 600x400")
    )
    img = open_png(png)

    probes = [
        Probe("swatch_red", 60, 60, (239, 68, 68), 55),
        Probe("swatch_green", 160, 60, (34, 197, 94), 55),
        Probe("swatch_blue", 260, 60, (59, 130, 246), 55),
        Probe("bar_fill", 80, 142, (245, 158, 11), 60),  # 70% amber fill
        Probe("bar_emptyish", 520, 142, (31, 41, 55), 70),  # track region
        Probe("box_a_center", 105, 225, (15, 23, 42), 50),
        Probe("bg", 300, 30, (17, 24, 39), 50),
    ]
    for p in probes:
        got = sample(img, p.x, p.y)
        ok = near(got, p.expected_rgb, p.tol)
        results.append(
            CheckResult(
                p.name,
                ok,
                f"@({p.x},{p.y}) got={got} expected≈{p.expected_rgb} tol={p.tol}",
            )
        )

    # Flex row: three boxes equally spaced. Sample near the top-left of each
    # panel (not the glyph center) so letter pixels do not false-fail.
    left = sample(img, 40, 200)
    mid = sample(img, 235, 200)
    right = sample(img, 430, 200)
    darkish = lambda c: c[0] < 80 and c[1] < 90 and c[2] < 110
    results.append(
        CheckResult(
            "flex_three_boxes",
            darkish(left) and darkish(mid) and darkish(right),
            f"panel L/M/R={left}/{mid}/{right}",
        )
    )
    return results


def check_simple_card(png: bytes, width: int = 800, height: int = 420) -> list[CheckResult]:
    results: list[CheckResult] = []
    try:
        w, h = png_size(png)
    except Exception as e:
        return [CheckResult("png", False, str(e))]
    results.append(CheckResult("size", w == width and h == height, f"got {w}x{h}"))
    img = open_png(png)
    # Dark navy-ish background near top-left content area.
    c = sample(img, 40, 40)
    dark = c[2] > c[0]  # bluish dark gradient
    not_white = sum(c) < 500
    results.append(CheckResult("bg_not_blank", not_white and dark or sum(c) < 200, f"bg={c}"))
    # Should not be pure black failure (all zero) nor pure white.
    extrema_ok = min(c) > 0 or max(sample(img, width // 2, height // 2)) > 20
    results.append(CheckResult("has_signal", extrema_ok, f"sample={c}"))
    return results


def summarize(results: list[CheckResult]) -> tuple[int, int, str]:
    passed = sum(1 for r in results if r.passed)
    total = len(results)
    lines = [f"  [{'PASS' if r.passed else 'FAIL'}] {r.name}: {r.detail}" for r in results]
    return passed, total, "\n".join(lines)
