# Backend benchmarks

Compare **takumi** with **htmlkit** (litehtml), **playwright** (Chromium/Edge), and **pillow** (manual draw baseline).

## Primary workload

**Desktop `stamina_card.html_test2.html` at 1150×850** (same canvas for every backend).

| Backend | What it does on each job |
| --- | --- |
| takumi / htmlkit / playwright | Full HTML+CSS render of test2 |
| pillow | **Same 1150×850**; does **not** parse HTML; paints background + **N loops** of rounded rects / progress bars / CJK text / footer (default N=80) |

## What is measured (all backends)

| Metric | Meaning |
| --- | --- |
| `cold_ms` | First render after setup |
| `mean_ms` / `p50` / `p95` | Warm sequential latency |
| `rps` | Concurrent throughput |
| concurrent mode | `thread-pool-shared` or `thread-pool-per-worker` (Playwright/htmlkit) |
| `setupΔMB` / `peakMB` | RSS during setup / concurrent peak |
| layout | test2 size + non-blank region probes |

## Run

```bash
cd pytakumi
# put stamina_card.html_test2.html on Desktop (or benchmarks/fixtures/)
python benchmarks/run_bench.py
python benchmarks/run_bench.py --iters 10 --workers 4 --jobs 12 --pillow-loops 80
```

Outputs:

- `output/benchmarks/report_test2.json`
- `output/benchmarks/<backend>_test2.png`

## Concurrency model

| Backend | Concurrent strategy |
| --- | --- |
| takumi | Shared `Renderer`, multi-thread pool |
| pillow | Shared painter, multi-thread pool |
| htmlkit | **Per-worker** instance + `asyncio.run` per job |
| playwright | **Per-worker** browser/context (sync API is greenlet-bound) |

## Sample numbers (Windows, CPython 3.13, test2 1150×850)

`iters=5` · `workers=4` · `jobs=8` · `pillow_loops=80`

| backend | cold_ms | mean_ms | p95_ms | concurrent rps | workers | mode | layout |
| --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| **takumi** | **309** | **292** | **327** | **7.1** | 4 | shared | 6/6 |
| htmlkit | 1077 | 945 | 967 | 2.8 | 4 | per-worker | 6/6 |
| playwright | 3348 | 3059 | 3088 | 0.67 | 4 | per-worker | 6/6 |
| pillow | 97 | 135 | 219 | 10.2 | 4 | shared | ~6/6 |

Pillow is fastest but **does not** produce the real card layout — only synthetic rect/text paint at the same size.

## Correctness fixtures (secondary)

- `fixtures/layout_check.html` — geometric swatches (used by smoke tests)
- `fixtures/simple_card.html` — small OG card
