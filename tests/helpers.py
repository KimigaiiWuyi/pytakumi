"""Shared assertions and tiny fixtures for product-grade tests."""

from __future__ import annotations

import re
import struct
import zlib
from typing import Sequence


# --- Markdown fixture checklist (arch_review_auth.md) -------------------


def assert_arch_review_md_checklist(md: str) -> dict[str, int]:
    """Validate the 14 stress-test elements required of arch_review_auth.md.

    Returns a small counts dict for debugging; raises AssertionError on miss.
    """
    # Strip fenced blocks before counting inline code / emphasis that may
    # appear inside code (language samples use * and ` heavily).
    body = re.sub(r"```.*?```", "", md, flags=re.DOTALL)

    h2 = re.findall(r"(?m)^## .+", md)
    h3 = re.findall(r"(?m)^### .+", md)
    assert len(h2) >= 3, f"H2 < 3: {h2}"
    assert len(h3) >= 4, f"H3 < 4: {h3}"

    fence_langs = re.findall(r"(?m)^```([^\n`]*)\s*$", md)
    # closing fences are empty strings
    open_langs = [x.strip() for x in fence_langs if x.strip()]
    for lang in ("python", "typescript", "bash"):
        assert lang in open_langs, f"missing fenced lang {lang}: {open_langs}"
    assert any(x == "296:301:src/auth.py" for x in open_langs), open_langs
    assert sum(1 for x in open_langs if x in ("python", "typescript", "bash")) >= 3

    # GFM tables: blank line, header, sep, ≥3 data rows, blank line; 3 columns
    table_pat = re.compile(
        r"\n\n"
        r"(\|[^\n]+\|\n)"
        r"(\|[-:| ]+\|\n)"
        r"((?:\|[^\n]+\|\n){3,})"
        r"\n",
    )
    tables = table_pat.findall("\n" + md if not md.startswith("\n") else md)
    # also allow EOF without trailing blank after last table content via softer check
    if len(tables) < 2:
        # fallback: count header/sep pairs with 3 pipes framing 3 cells
        soft = re.findall(
            r"(?m)^(\|[^|\n]+\|[^|\n]+\|[^|\n]+\|)\n(\|[-: ]+\|[-: ]+\|[-: ]+\|)\n"
            r"((?:\|[^|\n]+\|[^|\n]+\|[^|\n]+\|\n){3,})",
            md,
        )
        assert len(soft) >= 2, f"GFM tables (3col×≥3rows) < 2: found {len(tables)}/{len(soft)}"
        tables = soft  # type: ignore[assignment]
    else:
        for header, sep, rows in tables:
            cols = [c for c in header.strip().strip("|").split("|")]
            assert len(cols) == 3, f"table not 3-col: {header!r}"
            data_rows = [r for r in rows.strip().splitlines() if r.startswith("|")]
            assert len(data_rows) >= 3, f"table data rows < 3: {rows!r}"

    assert "flowchart TD" in md
    assert "quadrantChart" in md
    assert '"session/resume"' in md and "[0.4, 0.65]" in md

    inline_codes = re.findall(r"(?<!`)`([^`\n]+)`(?!`)", body)
    assert len(inline_codes) >= 10, f"inline code < 10: {len(inline_codes)} {inline_codes}"
    assert any(c.startswith("/etc") or "/etc/" in c for c in inline_codes), inline_codes
    # Windows path with backslashes as written in the fixture source
    assert any("C:" in c and "Users" in c for c in inline_codes), inline_codes
    assert any("bar" in c and "baz.py" in c for c in inline_codes), inline_codes

    ul_items = re.findall(r"(?m)^[-*] .+", md)
    ol_items = re.findall(r"(?m)^\d+\. .+", md)
    nested_ul = re.findall(r"(?m)^  [-*] .+", md)
    nested_ol = re.findall(r"(?m)^   \d+\. .+", md)
    # ≥2 unordered lists and ≥2 ordered lists: approximate by requiring
    # enough items and at least two separate list "starts" after blank lines.
    ul_starts = len(re.findall(r"(?m)(?:\n\n|^)[-*] ", md))
    ol_starts = len(re.findall(r"(?m)(?:\n\n|^)\d+\. ", md))
    assert ul_starts >= 2 and ol_starts >= 2, (ul_starts, ol_starts, ul_items, ol_items)
    assert nested_ul and nested_ol, (nested_ul, nested_ol)

    bq = re.findall(r"(?m)^> .+", md)
    assert len(bq) >= 2, bq
    assert re.search(r"(?m)^> \[!NOTE\]", md)

    bold = re.findall(r"\*\*[^*]+\*\*", body)
    em = re.findall(r"(?<!\*)\*([^*]+)\*(?!\*)", body)
    strike = re.findall(r"~~[^~]+~~", body)
    assert len(bold) >= 3, bold
    assert len(em) >= 3, em
    assert len(strike) >= 3, strike

    links = re.findall(r"\[[^\]]+\]\([^)]+\)", md)
    assert len(links) >= 2, links
    assert re.search(r"(?m)(?<![(\[])https?://\S+", md)

    assert "$E = mc^2$" in md
    assert r"\int_0^\infty" in md
    assert "$$" in md

    # 中英混排 technical terms
    for term in ("OAuth", "RBAC", "JWT"):
        assert term in md, term

    return {
        "h2": len(h2),
        "h3": len(h3),
        "fences": len(open_langs),
        "inline_code": len(inline_codes),
        "bold": len(bold),
        "em": len(em),
        "strike": len(strike),
        "links": len(links),
        "ul_starts": ul_starts,
        "ol_starts": ol_starts,
    }


# --- Image codec probes -------------------------------------------------


def assert_png(data: bytes, *, width: int | None = None, height: int | None = None) -> tuple[int, int]:
    assert isinstance(data, (bytes, bytearray)), type(data)
    assert data[:8] == b"\x89PNG\r\n\x1a\n", data[:16]
    w, h = struct.unpack(">II", data[16:24])
    if width is not None:
        assert w == width, (w, width)
    if height is not None:
        assert h == height, (h, height)
    return int(w), int(h)


def assert_jpeg(data: bytes) -> None:
    assert data[:2] == b"\xff\xd8", data[:8]
    assert data[-2:] == b"\xff\xd9" or b"\xff\xd9" in data[-32:]


def assert_webp(data: bytes) -> None:
    assert data[:4] == b"RIFF", data[:12]
    assert data[8:12] == b"WEBP", data[8:16]


def assert_ico(data: bytes) -> None:
    # ICO header: reserved=0, type=1, count>=1
    assert len(data) >= 6
    reserved, ico_type, count = struct.unpack("<HHH", data[:6])
    assert reserved == 0
    assert ico_type in (1, 2)
    assert count >= 1


def assert_raw_rgba(data: bytes, width: int, height: int) -> None:
    assert len(data) == width * height * 4, (len(data), width, height)


def raw_pixel(data: bytes, width: int, x: int, y: int) -> tuple[int, int, int, int]:
    i = (y * width + x) * 4
    return data[i], data[i + 1], data[i + 2], data[i + 3]


def assert_near_rgb(
    got: Sequence[int],
    expected: Sequence[int],
    *,
    tol: int = 8,
    label: str = "",
) -> None:
    assert len(got) >= 3 and len(expected) >= 3
    for a, b in zip(got[:3], expected[:3]):
        if abs(int(a) - int(b)) > tol:
            raise AssertionError(f"{label} got={tuple(got[:3])} expected≈{tuple(expected[:3])} tol={tol}")


# --- Minimal PNG (no Pillow) --------------------------------------------


def solid_png_bytes(width: int, height: int, rgba: tuple[int, int, int, int] = (255, 0, 0, 255)) -> bytes:
    """Encode a solid-color RGBA PNG without third-party deps."""
    r, g, b, a = rgba
    raw_rows = bytearray()
    row = bytes([r, g, b, a]) * width
    for _ in range(height):
        raw_rows.append(0)  # filter None
        raw_rows.extend(row)

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)  # 8-bit RGBA
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(bytes(raw_rows), 9))
        + chunk(b"IEND", b"")
    )


# --- HTML snippets ------------------------------------------------------


def full_bleed(color: str, extra: str = "") -> str:
    return (
        f'<div style="width:100%;height:100%;background:{color};'
        f'display:flex;align-items:center;justify-content:center;{extra}"></div>'
    )


def color_swatch_html() -> str:
    """Absolute positioned RGB swatches for geometry tests (200×100)."""
    return """
    <div style="width:200px;height:100px;position:relative;background:#000000">
      <div style="position:absolute;left:0;top:0;width:50px;height:50px;background:#ff0000"></div>
      <div style="position:absolute;left:50px;top:0;width:50px;height:50px;background:#00ff00"></div>
      <div style="position:absolute;left:100px;top:0;width:50px;height:50px;background:#0000ff"></div>
      <div style="position:absolute;left:150px;top:0;width:50px;height:50px;background:#ffffff"></div>
    </div>
    """
