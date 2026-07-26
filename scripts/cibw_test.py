#!/usr/bin/env python3
"""cibuildwheel test entry: stack setup + smoke render + full pytest.

Must run in **one process** so threading.stack_size / native pthread defaults
apply to workers that execute tests. A separate `python -c import` then `pytest`
does not share stack configuration.
"""

from __future__ import annotations

import os
import sys
import threading


def _main() -> int:
    stack = int(os.environ.get("RUST_MIN_STACK", str(8 * 1024 * 1024)))
    os.environ.setdefault("RUST_MIN_STACK", str(stack))

    # 1) Python threads created after this use a large stack (not musl 128KiB).
    try:
        threading.stack_size(stack)
        print(f"cibw_test: threading.stack_size={threading.stack_size()}", flush=True)
    except Exception as exc:  # noqa: BLE001
        print(f"cibw_test: threading.stack_size failed: {exc!r}", flush=True)

    # 2) Package import also applies _stack + native pthread_setattr_default_np.
    import pytakumi
    from pytakumi._stack import ensure_python_thread_stack, is_musl

    ensure_python_thread_stack(stack)
    print(
        f"cibw_test: import-ok version={pytakumi.__version__} musl={is_musl()} "
        f"stack={threading.stack_size()}",
        flush=True,
    )

    # 3) Single-thread smoke (main thread — same path as real paint).
    from pytakumi import html_to_pic

    png = html_to_pic(
        '<div style="width:100%;height:100%;background:#336699"></div>',
        width=64,
        height=48,
    )
    assert png[:8] == b"\x89PNG\r\n\x1a\n", png[:16]
    print(f"cibw_test: render-ok bytes={len(png)}", flush=True)

    # 4) Light animation (Rayon path) before full suite.
    from pytakumi import Renderer

    r = Renderer()
    scenes = [
        (
            {
                "type": "container",
                "style": {"width": "100%", "height": "100%", "background": "#ff0000"},
                "children": [],
            },
            40,
        ),
        (
            {
                "type": "container",
                "style": {"width": "100%", "height": "100%", "background": "#0000ff"},
                "children": [],
            },
            40,
        ),
    ]
    webp = r.render_animation(scenes, width=24, height=24, fps=5, format="webp")
    assert webp[:4] == b"RIFF", webp[:12]
    print(f"cibw_test: animation-ok bytes={len(webp)}", flush=True)

    # 5) Full product suite in this same process.
    project = os.environ.get("CIBW_PROJECT", "/project")
    test_path = os.path.join(project, "tests")
    if not os.path.isdir(test_path):
        # Local runs from repo root.
        test_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "tests")

    import pytest

    return int(pytest.main([test_path, "-q", "--tb=line"]))


if __name__ == "__main__":
    sys.exit(_main())
