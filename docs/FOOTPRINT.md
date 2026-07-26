# Dependency & binary footprint

Measured on a Windows checkout of **pytakumi** (engine submodule pin around takumi `a6f69ba`).

## What users download (`pip install pytakumi`)

| Artifact | Approx size | Notes |
| --- | ---: | --- |
| Native extension (`.pyd` / `.so`) | **~6.9 MB** (uncompressed) | Release-built `_native` (LTO); contains the Rust engine |
| Pure Python + templates | **~30 KB** | `api.py`, CSS templates, stubs |
| **Wheel (win_amd64 cp313, measured)** | **~3.3 MB** | `pytakumi-0.1.0-cp313-cp313-win_amd64.whl` |
| Runtime pip deps (default) | **0** | `dependencies = []` |
| Optional `pytakumi[markdown]` | **~0.1–1 MB** | `markdown-it-py` only |

No Chromium. No system font package required (you may register fonts).

### Comparison (order of magnitude)

| Package | Typical install / runtime weight |
| --- | --- |
| **pytakumi** wheel | ~7–10 MB native |
| Playwright + Chromium | Python pkg + **100–300+ MB** browser |
| htmlkit / litehtml wheel | often several MB native + fontconfig |
| Pillow | few MB, no HTML layout |

## What developers keep on disk (source tree)

| Path | Size (MB) | Role |
| --- | ---: | --- |
| `vendor/takumi` total (with `.git`) | ~70 | Submodule clone |
| `vendor/takumi` excl. `.git` | **~33.5** | Working tree |
| └ `assets/` (fonts, sample images) | **~20** | Build-time fonts / fixtures (not all ship in wheel) |
| └ core crates (`takumi*`) sources | ~11 | Engine code |
| └ test fixtures (e.g. fixtures-generated) | varies | Tests only |
| `python/` + `src/` | small | Bindings |
| Cargo registry build (`target/`) | **hundreds of MB** | Local compile cache only |
| Resolved Cargo packages | **~182 crates** | Compile graph (parley, taffy, skrifa, image, …) |

### Assets note

Most of the submodule bulk is **`vendor/takumi/assets`** (fonts/images used by engine tests and embedded last-resort faces). The published **wheel does not ship the whole assets tree**—only what is linked into the binary (e.g. embedded Geist last-resort) plus the Python package.

## Memory at runtime (from earlier benches)

| Scenario | Order of magnitude |
| --- | --- |
| Import + default `Renderer` setup | tens of MB RSS (fonts/caches configurable) |
| Warm OG card | low tens of ms; process RSS often **&lt; 100–200 MB** depending on cache |
| Playwright for same job | much higher cold start; browser process memory |

Tune with `Renderer(cache_max_bytes=...)` and `set_glyph_cache_max_bytes(...)`.

## Re-measure locally

```powershell
# extension after maturin develop --release
Get-Item .venv\Lib\site-packages\pytakumi\*.pyd | Select Name, Length

# submodule tree without .git
Get-ChildItem vendor\takumi -Recurse -File |
  Where-Object { $_.FullName -notmatch '\\\.git\\' } |
  Measure-Object Length -Sum
```
