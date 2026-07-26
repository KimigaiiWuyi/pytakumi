# Product test suite

Baseline: **≥ 100** collected tests; CI enforces `pytest --collect-only` count ≥ 80.

## Layout

| Module | Focus |
| --- | --- |
| `helpers.py` | PNG/JPEG/WebP/ICO/raw probes, solid PNG fixture, color asserts |
| `conftest.py` | Geist fonts, `Renderer`, tiny PNG fixtures |
| `test_package.py` | Exports / version |
| `test_errors.py` | Invalid formats, depth, fonts, animation |
| `test_formats_all.py` | png/jpeg/webp/ico/raw, dithering, dpr |
| `test_layout_geometry.py` | Absolute swatches, grid columns, cascade |
| `test_images.py` | `images={}`, list form, bytes, data-URL |
| `test_fonts.py` | register_font, font_families, helpers fonts= |
| `test_html_advanced.py` | document+style, presets, tw, multi sheets |
| `test_animation.py` | webp/gif/apng, dict scenes, NodeTree |
| `test_measure.py` | measure tree shape |
| `test_api_product.py` | html/text/md_to_pic product paths |
| `test_concurrency.py` | Thread-safety: shared Renderer/NodeTree, font register vs paint, image/stylesheet cache, high-level APIs, error paths, raw-byte identity; free-threaded 3.14t stress |
| `test_stack.py` | musl / `threading.stack_size` boost (Python worker stacks) |
| `conftest.py` | Sets `threading.stack_size(8MiB)` before pools (musl 128KiB default) |
| `test_markdown_unit.py` | MD→HTML without paint |
| `test_util.py` | escape, templates, extract_styles |
| `test_svg.py` | SVG backend |
| `test_nodes_product.py` | builders + module render |
| `test_time_and_debug.py` | time_ms, cache knobs |
| plus legacy | `test_render/html/markdown/node/api_helpers/bench_smoke` |

## Run

```bash
maturin develop --release
pytest -q
pytest tests/test_layout_geometry.py -q   # subset
```

Color-critical checks use `format="raw"` so assertions do not depend on encoder dithering.
