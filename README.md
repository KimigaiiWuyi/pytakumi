# pytakumi

**Python bindings for [Takumi](https://github.com/kane50613/takumi)** — a Rust layout engine that turns HTML, Markdown, and node trees into images **without a headless browser**.

| | |
| --- | --- |
| **Upstream engine** | [kane50613/takumi](https://github.com/kane50613/takumi) · docs [takumi.kane.tw/docs](https://takumi.kane.tw/docs/) |
| **This repo** | PyO3 / maturin bindings + high-level helpers (`html_to_pic` / `text_to_pic` / `md_to_pic`) |
| **Python** | 3.10 – 3.14 (GIL) **and free-threaded 3.14t** (not 3.13t) |
| **Platforms** | Windows / macOS / Linux (x86_64 & ARM64; manylinux **and** musllinux) |
| **License** | MIT OR Apache-2.0 (same dual license as Takumi) |

```text
pytakumi/                    ← this project (Python package name: pytakumi)
  vendor/takumi/             ← git submodule → github.com/kane50613/takumi
  src/                       ← Rust FFI (PyO3)
  python/pytakumi/           ← Python API + templates
```

The engine is **compiled into** the native extension at build time. End users of a published wheel do **not** need Rust, a browser, or the submodule.

> **Not a browser.** No JavaScript, no full CSSOM, no arbitrary live websites. Best for OG cards, Markdown documents, bot messages, and controlled HTML/CSS templates. Prefer Playwright when you need Chromium fidelity.

---

## Install

```bash
pip install pytakumi
pip install "pytakumi[markdown]"   # optional: better Markdown via markdown-it-py
```

**Note:** PyPI publish is optional/CI-driven. Until wheels are published, install from source (below).

### From source

```bash
git clone --recurse-submodules <this-repo-url> pytakumi
cd pytakumi
python -m venv .venv
# Windows: .\.venv\Scripts\Activate.ps1
source .venv/bin/activate
pip install maturin pytest markdown-it-py
maturin develop --release
pytest -q
```

Requirements: **Rust 1.91+** (`rust-toolchain.toml`), **Python ≥ 3.10**, submodule initialized:

```bash
git submodule update --init --recursive
```

Engine pin lives at `vendor/takumi` — see [docs/SUBMODULE.md](./docs/SUBMODULE.md).

---

## Quick start

### High-level helpers (recommended)

````python
from pytakumi import html_to_pic, text_to_pic, md_to_pic

# 1) HTML fragment → PNG
open("hello.png", "wb").write(
    html_to_pic(
        """
        <div style="width:100%;height:100%;display:flex;align-items:center;
                    justify-content:center;background:#0f172a;color:#fff;
                    font-size:48px">Hello pytakumi</div>
        """,
        width=800,
        height=400,
    )
)

# 2) Plain text card template (dark / light)
open("text.png", "wb").write(
    text_to_pic(
        "服务正常\n延迟 12ms",
        title="巡检日报",
        eyebrow="STATUS",
        footer="pytakumi",
        theme="dark",
        width=720,
    )
)

# 3) Markdown → image (GitHub README-style CSS template)
open("md.png", "wb").write(
    md_to_pic(
        """# Report

Status: **ok**

- item A
- item B

```python
print("hi")
```
""",
        width=800,
    )
)
````

### Low-level `Renderer` (cache reuse)

```python
from pytakumi import Renderer, from_html

r = Renderer(cache_max_bytes=64 * 1024 * 1024)
r.register_font(open("NotoSansSC-Regular.otf", "rb").read(), name="Noto Sans SC")

png = r.render_html(
    '<div style="font-family:Noto Sans SC;font-size:40px;padding:40px">你好</div>',
    width=400,
    height=120,
)

# Parse once, render many times
tree = from_html('<div class="card">Hi</div>')
png = r.render(tree, width=400, height=200, stylesheets=[".card{padding:24px;color:#111}"])
```

### Formats

| Kind | Values |
| --- | --- |
| Static | `png` (default), `jpeg`, `webp`, `ico`, `raw` |
| Animation | `webp`, `apng`, `gif` via `Renderer.render_animation` |
| Vector | `Renderer.render_svg` → SVG string |

---

## API surface

| Symbol | Role |
| --- | --- |
| **`html_to_pic`** | HTML document/fragment → image bytes |
| **`text_to_pic`** | Plain text + card template → image |
| **`md_to_pic`** | Markdown + GitHub-style template → image |
| `render_markdown` | Alias of `md_to_pic` (compat) |
| `Renderer` | Cached engine: `render`, `render_html`, `render_svg`, `measure`, `render_animation`, `register_font` |
| `from_html` / `NodeTree` | HTML → opaque node tree |
| `container` / `text_node` / `image_node` | Build trees in Python |
| `render` / `render_html` | One-shot helpers (new ephemeral renderer) |
| `set_glyph_cache_max_bytes` | Process-wide glyph cache (call before first render) |

Templates for Markdown/text live under `python/pytakumi/templates/`.

### Fonts

Only a **Latin last-resort** face is embedded. Register CJK and other faces yourself:

```python
from pytakumi import Renderer, set_glyph_cache_max_bytes

set_glyph_cache_max_bytes(64 * 1024 * 1024)  # before first render for CJK
r = Renderer()
r.register_font(open("msyh.ttc", "rb").read(), name="Microsoft YaHei")
```

Reuse **one** `Renderer` per process/worker so fonts and image caches stay warm.

---

## Origin & relationship to Takumi

| Piece | Source |
| --- | --- |
| Layout / CSS / raster / SVG engine | **[kane50613/takumi](https://github.com/kane50613/takumi)** (Rust monorepo) |
| Official docs / playground | [takumi.kane.tw](https://takumi.kane.tw) |
| Node / WASM bindings (upstream) | `takumi-js`, `@takumi-rs/core`, `@takumi-rs/wasm` |
| **This project** | Independent **Python** packaging: submodule pin + PyO3 + helpers |

`pytakumi` is **not** an official release of the Takumi authors unless they adopt it. Engine updates:

```bash
cd vendor/takumi && git fetch && git checkout <tag-or-commit>
cd ../.. && git add vendor/takumi && git commit -m "chore: bump engine"
maturin develop --release && pytest -q
```

维护者文档（结构 / CI / 交接 / 踩坑）：**[docs/README.md](./docs/README.md)**。  
另见 [docs/SUBMODULE.md](./docs/SUBMODULE.md)、[docs/PACKAGING.md](./docs/PACKAGING.md)、[docs/FOOTPRINT.md](./docs/FOOTPRINT.md)。

---

## Development

```bash
maturin develop --release
pytest -q
cargo clippy --all-targets -- -D warnings
```

### Tests (product suite)

**117+ cases** covering formats, layout geometry (raw-pixel probes), fonts, images, HTML/CSS, animation, SVG, measure, high-level APIs, concurrency, errors, and utilities.

```bash
pytest -q
# see tests/README.md for module map
```

| Area | Modules |
| --- | --- |
| Formats / density / dither | `test_formats_all.py` |
| Geometry & color correctness | `test_layout_geometry.py` (uses `format=raw`) |
| Images (dict/list/data-URL/bytes) | `test_images.py` |
| Fonts | `test_fonts.py` |
| HTML advanced | `test_html_advanced.py` |
| Animation gif/apng/webp | `test_animation.py` |
| `html_to_pic` / `text_to_pic` / `md_to_pic` | `test_api_product.py` |
| Thread-pool concurrency | `test_concurrency.py` |
| Errors & invalid inputs | `test_errors.py` |
| Package exports | `test_package.py` |
| … | plus markdown/nodes/svg/measure/util/legacy files |

CI fails if collected tests drop below **80**. Free-threaded **3.14t** is supported (`gil_used=false`, shared `Renderer` is thread-safe; see `tests/test_concurrency.py`). Still out of scope: free-threaded **3.13t**, full Chromium visual SSIM, and multi-arch green without Actions.

### Benchmarks

```bash
pip install -e ".[bench]"
playwright install chromium   # optional
python benchmarks/run_bench.py --iters 10 --workers 4 --jobs 8
```

Primary fixture: Desktop `stamina_card.html_test2.html` (1150×850). See [docs/BENCHMARKS.md](./docs/BENCHMARKS.md).

### CI / CD

| Workflow | Purpose |
| --- | --- |
| [`.github/workflows/ci.yml`](./.github/workflows/ci.yml) | Lint + **Ubuntu/Windows/macOS × Python 3.10–3.14** (+ **Linux 3.14t**) source build + `pytest`; Clippy; Linux wheel smoke |
| [`.github/workflows/wheels.yml`](./.github/workflows/wheels.yml) | **cibuildwheel**: CPython 3.10–3.14 **and cp314t** × (x86_64 & ARM64); Linux manylinux+musllinux; **each wheel is pytest’d**; sdist; **PyPI on `v*` tags** |

| 文档 | 内容 |
| --- | --- |
| **[docs/CI.md](./docs/CI.md)** | 矩阵、Publish 条件、**关键配置清单** |
| **[docs/PITFALLS.md](./docs/PITFALLS.md)** | musl 栈、tag、macos-13、Trusted Publisher 等踩坑 |
| **[docs/HANDOVER.md](./docs/HANDOVER.md)** | 交接与发版步骤 |
| [docs/PACKAGING.md](./docs/PACKAGING.md) | wheel / free-threaded / musl 技术细节 |

Checkout uses **`submodules: recursive`**. Publish needs GitHub Environment `pypi` + PyPI Trusted Publisher；**全部 matrix job 成功**后才会跑 Publish。

---

## Layout vs Playwright

| | pytakumi (Takumi engine) | Playwright |
| --- | --- | --- |
| Startup | Library load | Browser process |
| Memory | Low (caches configurable) | High |
| HTML/CSS | Subset, static | Full browser |
| JavaScript | No | Yes |
| Best for | Cards, Markdown, templates | Arbitrary live pages |

---

## License

MIT OR Apache-2.0 — see [LICENSE-MIT](./LICENSE-MIT) and [LICENSE-APACHE](./LICENSE-APACHE).

Upstream engine: [kane50613/takumi](https://github.com/kane50613/takumi) (MIT OR Apache-2.0).
