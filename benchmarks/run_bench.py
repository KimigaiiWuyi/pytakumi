#!/usr/bin/env python3
"""Comparative performance benchmark: pillow / playwright / htmlkit / takumi.

Primary fixture: Desktop stamina_card.html_test2.html (1150×850).

Measures for every backend:
  - cold first render
  - warm sequential mean/p50/p95
  - concurrent throughput (thread pool; per-thread instances when needed)
  - RSS setup / peak
  - basic layout sanity (size + non-blank)

Pillow uses the **same width/height** and simulates card paint by repeating
rectangle + text draws (not HTML layout).

Usage:
  python benchmarks/run_bench.py
  python benchmarks/run_bench.py --iters 15 --workers 4 --jobs 16 --pillow-loops 80
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from backends import Backend, select_backends  # noqa: E402
from layout_checks import png_size, summarize  # noqa: E402
from layout_checks import CheckResult, open_png, sample  # noqa: E402

OUT = ROOT / "output" / "benchmarks"

# Official test2 card size from the HTML body CSS.
TEST2_WIDTH = 1150
TEST2_HEIGHT = 850

TEST2_CANDIDATES = [
    Path.home() / "Desktop" / "stamina_card.html_test2.html",
    Path.home() / "Desktop" / "T" / "stamina_card.html_test2.html",
    ROOT / "benchmarks" / "fixtures" / "stamina_card.html_test2.html",
]


@dataclass
class TimingStats:
    cold_ms: float
    mean_ms: float
    p50_ms: float
    p95_ms: float
    min_ms: float
    max_ms: float
    iters: int


@dataclass
class ConcurrencyStats:
    workers: int
    jobs: int
    total_s: float
    throughput_rps: float
    errors: int
    mode: str  # "thread-pool-shared" | "thread-pool-per-worker" | "serial-fallback"


@dataclass
class MemoryStats:
    rss_before_mb: float
    rss_after_setup_mb: float
    rss_after_warm_mb: float
    rss_peak_concurrent_mb: float
    delta_setup_mb: float
    delta_warm_mb: float


@dataclass
class BackendReport:
    backend: str
    available: bool
    skip_reason: str = ""
    timing: TimingStats | None = None
    concurrency: ConcurrencyStats | None = None
    memory: MemoryStats | None = None
    layout: dict = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    notes: str = ""


def rss_mb() -> float:
    try:
        import psutil

        return psutil.Process().memory_info().rss / (1024 * 1024)
    except Exception:
        return -1.0


def pct(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    k = (len(s) - 1) * p
    f = int(k)
    c = min(f + 1, len(s) - 1)
    if f == c:
        return s[f]
    return s[f] + (s[c] - s[f]) * (k - f)


def time_render(backend: Backend, html: str, width: int, height: int) -> tuple[bytes, float]:
    t0 = time.perf_counter()
    png = backend.render(html, width, height)
    dt = (time.perf_counter() - t0) * 1000.0
    return png, dt


def load_test2() -> tuple[str, int, int, Path]:
    for path in TEST2_CANDIDATES:
        if path.is_file():
            return path.read_text(encoding="utf-8", errors="replace"), TEST2_WIDTH, TEST2_HEIGHT, path
    raise FileNotFoundError(
        "stamina_card.html_test2.html not found. Place it on Desktop or under benchmarks/fixtures/."
    )


def check_test2_card(png: bytes, width: int, height: int) -> list[CheckResult]:
    """Sanity checks for the stamina card (not full visual regression)."""
    results: list[CheckResult] = []
    try:
        w, h = png_size(png)
    except Exception as e:
        return [CheckResult("png", False, str(e))]
    results.append(CheckResult("size", w == width and h == height, f"got {w}x{h}, expected {width}x{height}"))
    img = open_png(png)
    # Corners / mid should not be pure white failure plate.
    samples = [
        ("tl", sample(img, 30, 30)),
        ("tr", sample(img, width - 40, 40)),
        ("bl", sample(img, 80, height - 80)),
        ("mid", sample(img, width // 2, height // 2)),
    ]
    # Non-white plate is enough; pure black footer is valid paint.
    for name, c in samples:
        non_white = not (c[0] > 250 and c[1] > 250 and c[2] > 250)
        results.append(CheckResult(f"signal_{name}", non_white, f"rgb={c}"))
    # Dark theme expected somewhere in left HUD region.
    hud = sample(img, 120, 200)
    results.append(
        CheckResult(
            "left_hud_darkish",
            hud[0] < 180 and hud[1] < 180,
            f"rgb={hud}",
        )
    )
    return results


def run_concurrent(
    backend: Backend,
    html: str,
    width: int,
    height: int,
    *,
    workers: int,
    jobs: int,
) -> tuple[ConcurrencyStats, float, list[str]]:
    """Return (stats, peak_rss_mb, errors)."""
    errors: list[str] = []
    peak = rss_mb()
    peak_lock = threading.Lock()

    if backend.thread_safe:
        mode = "thread-pool-shared"
        shared = backend

        def job(_i: int) -> float:
            nonlocal peak
            _, ms = time_render(shared, html, width, height)
            with peak_lock:
                peak = max(peak, rss_mb())
            return ms

        t0 = time.perf_counter()
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futs = [pool.submit(job, i) for i in range(jobs)]
            for fut in as_completed(futs):
                try:
                    fut.result()
                except Exception as e:
                    errors.append(f"concurrent: {e}")
        total_s = time.perf_counter() - t0
        return (
            ConcurrencyStats(
                workers=workers,
                jobs=jobs,
                total_s=total_s,
                throughput_rps=((jobs - len(errors)) / total_s) if total_s > 0 else 0.0,
                errors=len(errors),
                mode=mode,
            ),
            peak,
            errors,
        )

    # Per-worker backend instances (Playwright, htmlkit, etc.)
    mode = "thread-pool-per-worker"
    local = threading.local()

    def worker_backend() -> Backend:
        b = getattr(local, "backend", None)
        if b is None:
            b = backend.clone_for_worker()
            local.backend = b
        return b

    def job(_i: int) -> float:
        nonlocal peak
        b = worker_backend()
        _, ms = time_render(b, html, width, height)
        with peak_lock:
            peak = max(peak, rss_mb())
        return ms

    workers_alive: list[Backend] = []
    workers_lock = threading.Lock()

    def job_tracked(i: int) -> float:
        b = worker_backend()
        with workers_lock:
            if b not in workers_alive:
                workers_alive.append(b)
        return job(i)

    t0 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futs = [pool.submit(job_tracked, i) for i in range(jobs)]
        for fut in as_completed(futs):
            try:
                fut.result()
            except Exception as e:
                errors.append(f"concurrent: {e}")
    total_s = time.perf_counter() - t0

    for b in workers_alive:
        try:
            b.teardown()
        except Exception as e:
            errors.append(f"worker teardown: {e}")

    conc_err = len([e for e in errors if e.startswith("concurrent")])
    return (
        ConcurrencyStats(
            workers=workers,
            jobs=jobs,
            total_s=total_s,
            throughput_rps=((jobs - conc_err) / total_s) if total_s > 0 else 0.0,
            errors=conc_err,
            mode=mode,
        ),
        peak,
        errors,
    )


def run_backend(
    backend: Backend,
    *,
    html: str,
    width: int,
    height: int,
    fixture_path: Path,
    iters: int,
    workers: int,
    concurrent_jobs: int,
) -> BackendReport:
    report = BackendReport(
        backend=backend.name,
        available=True,
        notes=f"fixture={fixture_path.name} canvas={width}x{height}",
    )
    if backend.name == "pillow" and hasattr(backend, "draw_loops"):
        report.notes += f" pillow_loops={backend.draw_loops}"

    rss0 = rss_mb()
    try:
        backend.setup()
    except Exception as e:
        report.available = False
        report.skip_reason = f"setup failed: {e}"
        report.errors.append(traceback.format_exc())
        return report
    rss1 = rss_mb()

    try:
        png0, cold_ms = time_render(backend, html, width, height)
        (OUT / f"{backend.name}_test2.png").write_bytes(png0)

        times: list[float] = []
        last = png0
        for _ in range(iters):
            last, ms = time_render(backend, html, width, height)
            times.append(ms)
        (OUT / f"{backend.name}_test2_warm.png").write_bytes(last)

        report.timing = TimingStats(
            cold_ms=cold_ms,
            mean_ms=statistics.fmean(times),
            p50_ms=pct(times, 0.50),
            p95_ms=pct(times, 0.95),
            min_ms=min(times),
            max_ms=max(times),
            iters=len(times),
        )
        rss2 = rss_mb()

        conc, peak, conc_errors = run_concurrent(
            backend,
            html,
            width,
            height,
            workers=workers,
            jobs=concurrent_jobs,
        )
        report.concurrency = conc
        report.errors.extend(conc_errors[:8])
        report.memory = MemoryStats(
            rss_before_mb=rss0,
            rss_after_setup_mb=rss1,
            rss_after_warm_mb=rss2,
            rss_peak_concurrent_mb=peak,
            delta_setup_mb=(rss1 - rss0) if rss0 >= 0 else -1,
            delta_warm_mb=(rss2 - rss1) if rss1 >= 0 else -1,
        )

        results = check_test2_card(png0, width, height)
        p, t, detail = summarize(results)
        report.layout = {
            "test2_card": {
                "passed": p,
                "total": t,
                "detail": detail,
                "png_bytes": len(png0),
            }
        }
    except Exception:
        report.errors.append(traceback.format_exc())
        report.skip_reason = "run failed"
    finally:
        try:
            backend.teardown()
        except Exception as e:
            report.errors.append(f"teardown: {e}")

    return report


def print_report(reports: list[BackendReport], width: int, height: int) -> None:
    print("\n" + "=" * 88)
    print(f"TEST2 CARD BENCHMARK  ({width}×{height})")
    print("=" * 88)
    header = (
        f"{'backend':<12} {'cold_ms':>9} {'mean_ms':>9} {'p95_ms':>9} "
        f"{'rps':>8} {'workers':>7} {'mode':<22} {'setupΔMB':>9} {'peakMB':>8} {'layout':>8}"
    )
    print(header)
    print("-" * len(header))
    for r in reports:
        if not r.available or r.timing is None:
            print(f"{r.backend:<12} SKIP ({r.skip_reason})")
            continue
        t = r.timing
        c = r.concurrency
        m = r.memory
        layout = r.layout.get("test2_card", {})
        layout_s = f"{layout.get('passed', 0)}/{layout.get('total', 0)}"
        print(
            f"{r.backend:<12} "
            f"{t.cold_ms:9.1f} "
            f"{t.mean_ms:9.2f} "
            f"{t.p95_ms:9.2f} "
            f"{(c.throughput_rps if c else 0):8.2f} "
            f"{(c.workers if c else 0):7d} "
            f"{(c.mode if c else '-'):<22} "
            f"{(m.delta_setup_mb if m else 0):9.1f} "
            f"{(m.rss_peak_concurrent_mb if m else 0):8.1f} "
            f"{layout_s:>8}"
        )
        if r.notes:
            print(f"             note: {r.notes}")

    print("\n" + "=" * 88)
    print("LAYOUT DETAIL")
    print("=" * 88)
    for r in reports:
        if not r.layout:
            continue
        print(f"\n## {r.backend}")
        for name, block in r.layout.items():
            print(f"[{name}] {block.get('passed')}/{block.get('total')}  bytes={block.get('png_bytes')}")
            print(block.get("detail", ""))
        if r.errors:
            print("errors (truncated):")
            for e in r.errors[:3]:
                print(" -", e.splitlines()[-1][:180])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="test2 HTML card backend benchmark")
    parser.add_argument("--backends", default="pytakumi,htmlkit,playwright,pillow")
    parser.add_argument("--iters", type=int, default=10, help="warm sequential iterations")
    parser.add_argument("--workers", type=int, default=4, help="concurrent worker threads")
    parser.add_argument("--jobs", type=int, default=12, help="total concurrent render jobs")
    parser.add_argument(
        "--pillow-loops",
        type=int,
        default=80,
        help="Pillow: how many rectangle+text paint iterations per render",
    )
    parser.add_argument("--json", type=Path, default=None)
    args = parser.parse_args(argv)

    OUT.mkdir(parents=True, exist_ok=True)
    try:
        html, width, height, fixture_path = load_test2()
    except FileNotFoundError as e:
        print(e, file=sys.stderr)
        return 2

    print(f"Fixture: {fixture_path}")
    print(f"Canvas:  {width}×{height}  html_bytes={len(html.encode('utf-8'))}")
    print(f"iters={args.iters} workers={args.workers} jobs={args.jobs} pillow_loops={args.pillow_loops}")

    names = {x.strip() for x in args.backends.split(",") if x.strip()}
    backends = select_backends(names, pillow_loops=args.pillow_loops)
    if not backends:
        print("No backends available.", file=sys.stderr)
        return 2

    reports: list[BackendReport] = []
    for b in backends:
        print(f"\n>>> running {b.name} ...")
        reports.append(
            run_backend(
                b,
                html=html,
                width=width,
                height=height,
                fixture_path=fixture_path,
                iters=args.iters,
                workers=args.workers,
                concurrent_jobs=args.jobs,
            )
        )

    order = ["pytakumi", "htmlkit", "playwright", "pillow"]
    reports.sort(key=lambda r: order.index(r.backend) if r.backend in order else 99)
    print_report(reports, width, height)

    out_json = args.json or (OUT / "report_test2.json")
    out_json.write_text(
        json.dumps([asdict(r) for r in reports], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"\nJSON report: {out_json}")
    print(f"Artifacts:   {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
