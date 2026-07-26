from __future__ import annotations

from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
ENGINE_ROOT = _ROOT / "vendor" / "takumi"
if not ENGINE_ROOT.is_dir():
    ENGINE_ROOT = _ROOT.parent / "takumi"

GEIST_FONT = ENGINE_ROOT / "assets" / "fonts" / "geist" / "geist-latin-wght-300-800.woff2"
GEIST_VAR = ENGINE_ROOT / "assets" / "fonts" / "geist" / "Geist[wght].woff2"


@pytest.fixture(scope="session")
def geist_font_bytes() -> bytes:
    if not GEIST_FONT.is_file():
        pytest.skip(f"fixture font not found: {GEIST_FONT}")
    return GEIST_FONT.read_bytes()


@pytest.fixture(scope="session")
def geist_var_font_bytes() -> bytes:
    if not GEIST_VAR.is_file():
        pytest.skip(f"variable font not found: {GEIST_VAR}")
    return GEIST_VAR.read_bytes()


@pytest.fixture
def renderer(geist_font_bytes: bytes):
    from pytakumi import Renderer

    r = Renderer()
    r.register_font(geist_font_bytes, name="Geist")
    return r


@pytest.fixture
def renderer_empty():
    from pytakumi import Renderer

    return Renderer()


@pytest.fixture(scope="session")
def red_png_bytes() -> bytes:
    from helpers import solid_png_bytes

    return solid_png_bytes(32, 32, (255, 0, 0, 255))


@pytest.fixture(scope="session")
def green_png_bytes() -> bytes:
    from helpers import solid_png_bytes

    return solid_png_bytes(16, 16, (0, 255, 0, 255))
