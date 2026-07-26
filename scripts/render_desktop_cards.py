"""Render Desktop stamina_card HTML files with Takumi and save PNGs."""

from __future__ import annotations

import re
import sys
import time
from pathlib import Path

DESKTOP = Path.home() / "Desktop"
OUT_DIR = Path(__file__).resolve().parents[1] / "output" / "desktop-cards"
WIDTH = 1150
HEIGHT = 850


def extract_styles_and_body(html: str) -> tuple[list[str], str]:
    styles = re.findall(r"<style[^>]*>(.*?)</style>", html, flags=re.I | re.S)
    # Drop head; keep body contents when present.
    body_m = re.search(r"<body[^>]*>(.*?)</body>", html, flags=re.I | re.S)
    body = body_m.group(1) if body_m else html
    # Remove remaining style/script tags from body.
    body = re.sub(r"<script[^>]*>.*?</script>", "", body, flags=re.I | re.S)
    body = re.sub(r"<style[^>]*>.*?</style>", "", body, flags=re.I | re.S)
    # Litehtml-oriented pages often rely on body size; wrap root.
    wrapped = (
        f'<div class="pytakumi-root" style="width:{WIDTH}px;height:{HEIGHT}px;'
        f'position:relative;overflow:hidden;background:#0f1115;color:white;'
        f"font-family:'Source Han Sans CN',sans-serif;font-size:16px;line-height:1.5\">"
        f"{body}</div>"
    )
    # Body rules won't match our wrapper; promote common body rules.
    promoted = []
    for sheet in styles:
        # Rewrite body { ... } onto .pytakumi-root for layout fidelity.
        sheet2 = re.sub(
            r"(?m)(^|[,\s])body(\s*[,{])",
            r"\1.pytakumi-root\2",
            sheet,
        )
        # @import almost never works offline; drop it to avoid fetch noise.
        sheet2 = re.sub(r"@import\s+url\([^)]+\)\s*;?", "", sheet2, flags=re.I)
        promoted.append(sheet2)
    return promoted, wrapped


def summarize_html(path: Path, html: str) -> dict:
    styles = re.findall(r"<style[^>]*>(.*?)</style>", html, flags=re.I | re.S)
    imgs = re.findall(r"""<img[^>]+src=["']([^"']+)""", html, flags=re.I)
    texts = re.findall(r">([^<]{1,80})<", re.sub(r"data:image/[^\"']+", "data:image/...", html))
    text_samples = [t.strip() for t in texts if t.strip() and not t.strip().startswith("{")]
    img_info = []
    for src in imgs[:12]:
        if src.startswith("data:"):
            kind = "data-url"
            size = len(src)
        elif src.startswith("http"):
            kind = "http"
            size = len(src)
        else:
            kind = "path"
            size = len(src)
        img_info.append({"kind": kind, "len": size, "prefix": src[:70]})
    return {
        "name": path.name,
        "bytes": path.stat().st_size,
        "styles": len(styles),
        "style_chars": sum(len(s) for s in styles),
        "images": len(imgs),
        "img_info": img_info,
        "text_samples": text_samples[:25],
    }


def main() -> int:
    from pytakumi import Renderer, set_glyph_cache_max_bytes

    set_glyph_cache_max_bytes(64 * 1024 * 1024)
    files = sorted(DESKTOP.glob("*.html*"))
    if not files:
        print("No HTML files on Desktop", file=sys.stderr)
        return 1

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    r = Renderer(cache_max_bytes=128 * 1024 * 1024)

    # Best-effort CJK fonts if present on Windows.
    font_candidates = [
        Path(r"C:\Windows\Fonts\msyh.ttc"),
        Path(r"C:\Windows\Fonts\msyhbd.ttc"),
        Path(r"C:\Windows\Fonts\simhei.ttf"),
        Path(r"C:\Windows\Fonts\SourceHanSansCN-Regular.otf"),
        Path(r"C:\Windows\Fonts\NotoSansSC-Regular.otf"),
    ]
    registered = []
    for fp in font_candidates:
        if fp.is_file():
            try:
                data = fp.read_bytes()
                name = "Source Han Sans CN" if "SourceHan" in fp.name or "Noto" in fp.name else "Microsoft YaHei"
                if "msyh" in fp.name.lower() or "simhei" in fp.name.lower():
                    name = "Microsoft YaHei"
                families = r.register_font(data, name=name)
                registered.append((str(fp), families))
                # Also alias the CSS family used by the cards.
                if name != "Source Han Sans CN":
                    r.register_font(data, name="Source Han Sans CN")
            except Exception as e:
                print(f"font skip {fp}: {e}")

    print("registered fonts:", registered)
    print("html files:", [f.name for f in files])

    for path in files:
        html = path.read_text(encoding="utf-8", errors="replace")
        summary = summarize_html(path, html)
        print("\n===", summary["name"], "===")
        print(
            f"size={summary['bytes']} styles={summary['styles']} "
            f"style_chars={summary['style_chars']} images={summary['images']}"
        )
        for info in summary["img_info"]:
            print(f"  img {info['kind']} len={info['len']} {info['prefix']!r}")
        print("  text:", summary["text_samples"][:15])

        sheets, body = extract_styles_and_body(html)
        out = OUT_DIR / (path.stem + ".png")
        t0 = time.perf_counter()
        try:
            png = r.render_html(
                body,
                width=WIDTH,
                height=HEIGHT,
                format="png",
                stylesheets=sheets,
            )
            out.write_bytes(png)
            dt = time.perf_counter() - t0
            print(f"  OK -> {out} ({len(png)} bytes, {dt:.2f}s)")
        except Exception as e:
            dt = time.perf_counter() - t0
            print(f"  FAIL after {dt:.2f}s: {type(e).__name__}: {e}")
            # Retry with stripped data URLs replaced by solid placeholders? keep failure visible.
            raise

    print("\nAll outputs in", OUT_DIR)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
