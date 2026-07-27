#!/usr/bin/env python3
"""Concurrent QPS benchmark for md_to_pic using the arch-review fixture.

Example:
  python scripts/bench_md_to_pic_qps.py
  python scripts/bench_md_to_pic_qps.py --jobs 10000 --workers 32
  python scripts/bench_md_to_pic_qps.py --jobs 10000 --workers 64 --height 1200
"""

from __future__ import annotations

import argparse
import os
import struct
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "arch_review_auth.md"


def _png_size(data: bytes) -> tuple[int, int]:
    return struct.unpack(">II", data[16:24])


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--jobs", type=int, default=10_000, help="total render jobs")
    p.add_argument(
        "--workers",
        type=int,
        default=max(8, (os.cpu_count() or 4) * 2),
        help="thread pool size (concurrent workers)",
    )
    p.add_argument("--width", type=int, default=900)
    p.add_argument(
        "--height",
        type=int,
        default=None,
        help="fixed height (default: auto / None — full document)",
    )
    p.add_argument("--warmup", type=int, default=4)
    p.add_argument("--dark", action="store_true")
    p.add_argument(
        "--no-cjk-font",
        action="store_true",
        help="do not load Microsoft YaHei even if present",
    )
    args = p.parse_args()

    if not FIXTURE.is_file():
        print(f"fixture missing: {FIXTURE}", file=sys.stderr)
        return 2

    from pytakumi import Renderer, md_to_pic

    md = FIXTURE.read_text(encoding="utf-8")
    print(f"fixture: {FIXTURE.name}  lines={len(md.splitlines())}  chars={len(md)}")
    print(f"jobs={args.jobs}  workers={args.workers}  width={args.width}  height={args.height}")
    print(f"gil: {getattr(sys, '_is_gil_enabled', lambda: 'n/a')()}")

    fonts = None
    font_families = None
    yahei = Path(r"C:\Windows\Fonts\msyh.ttc")
    if not args.no_cjk_font and yahei.is_file():
        fonts = [{"data": yahei.read_bytes(), "name": "msyh"}]
        font_families = ["msyh"]
        print(f"font: {yahei}")
    else:
        print("font: default (no CJK inject)")

    renderer = Renderer()
    kw: dict = {
        "width": args.width,
        "height": args.height,
        "dark": args.dark,
        "renderer": renderer,
        "fonts": fonts,
        "font_families": font_families,
    }
    # drop None fonts keys for cleaner call
    if fonts is None:
        kw.pop("fonts")
        kw.pop("font_families")

    # warmup + sample size
    t0 = time.perf_counter()
    sample = md_to_pic(md, **kw)
    warm_s = time.perf_counter() - t0
    w, h = _png_size(sample)
    print(f"warmup: {warm_s*1000:.1f} ms  png={w}x{h}  bytes={len(sample)}")
    for _ in range(max(0, args.warmup - 1)):
        md_to_pic(md, **kw)

    errors: list[str] = []
    err_lock = threading.Lock()
    ok = 0
    ok_lock = threading.Lock()

    def one(i: int) -> int:
        try:
            out = md_to_pic(md, **kw)
            if out[:8] != b"\x89PNG\r\n\x1a\n":
                raise ValueError(f"not png job={i}")
            return len(out)
        except Exception as e:
            with err_lock:
                if len(errors) < 8:
                    errors.append(f"job {i}: {type(e).__name__}: {e}")
            raise

    # true barrier: all tasks submitted to pool of `workers`
    print(f"\n--- concurrent run: {args.jobs} jobs / {args.workers} workers ---")
    t_start = time.perf_counter()
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futs = [pool.submit(one, i) for i in range(args.jobs)]
        for fut in as_completed(futs):
            try:
                fut.result()
                with ok_lock:
                    ok += 1
            except Exception:
                pass
    t_end = time.perf_counter()
    total_s = t_end - t_start
    qps = ok / total_s if total_s > 0 else 0.0
    fail = args.jobs - ok

    print()
    print("========== RESULT ==========")
    print(f"  total jobs : {args.jobs}")
    print(f"  workers    : {args.workers}")
    print(f"  succeeded  : {ok}")
    print(f"  failed     : {fail}")
    print(f"  wall time  : {total_s:.3f} s")
    print(f"  QPS        : {qps:.2f} renders/s")
    print(f"  avg latency: {(total_s / ok * 1000) if ok else 0:.2f} ms/job  (wall/ok)")
    print(f"  png size  : {w}x{h}")
    if errors:
        print("  sample errors:")
        for e in errors:
            print(f"    - {e}")
    print("============================")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
