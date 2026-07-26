"""Thread stack sizing for musl / small-stack platforms.

musl's default **pthread** stack is only **128 KiB**. That size is used by:

* Python ``threading.Thread`` / ``ThreadPoolExecutor`` workers
* (separately) Rust ``std::thread`` / Rayon — handled in the native module

``RUST_MIN_STACK`` and Rayon's ``stack_size`` do **not** change Python thread
stacks. When worker threads call into release-optimized layout/raster code,
128 KiB overflows → SIGSEGV (exit 139). The main thread usually has a full
process stack (``ulimit -s``), so single-threaded import/smoke can pass while
concurrent tests die.

We raise the default for *new* Python threads via ``threading.stack_size``.
"""

from __future__ import annotations

import sys
import sysconfig
import threading

# 8 MiB — matches RUST_MIN_STACK / Rayon worker stacks in the native module.
_WORKER_STACK = 8 * 1024 * 1024


def is_musl() -> bool:
    """Best-effort detection of a musl libc process (Alpine, musllinux wheels)."""
    if not sys.platform.startswith("linux"):
        return False
    host = (
        (sysconfig.get_config_var("HOST_GNU_TYPE") or "")
        + " "
        + (sysconfig.get_config_var("SOABI") or "")
        + " "
        + (sysconfig.get_config_var("EXT_SUFFIX") or "")
    )
    if "musl" in host.lower():
        return True
    try:
        with open("/proc/self/maps", encoding="utf-8", errors="ignore") as f:
            head = f.read(65536)
        return "ld-musl" in head or "/musl" in head
    except OSError:
        return False


def ensure_python_thread_stack(size: int = _WORKER_STACK) -> int | None:
    """Raise the stack size used for subsequently created Python threads.

    Returns the previous setting (bytes), or ``None`` if unavailable.
    Safe to call multiple times; no-ops if already >= ``size``.
    """
    try:
        prev = threading.stack_size()
    except (ValueError, RuntimeError, AttributeError):
        return None

    # 0 means "platform default".
    if prev != 0 and prev >= size:
        return prev

    try:
        threading.stack_size(size)
    except (ValueError, RuntimeError):
        return prev
    return prev


def ensure_for_runtime() -> None:
    """Call at package import: boost Python worker stacks when needed."""
    try:
        prev = threading.stack_size()
    except (ValueError, RuntimeError, AttributeError):
        return

    # Explicit tiny stack → always raise.
    if prev != 0 and prev < 512 * 1024:
        ensure_python_thread_stack(_WORKER_STACK)
        return

    # musl platform default (prev == 0 → ~128 KiB) must be raised.
    if is_musl():
        ensure_python_thread_stack(_WORKER_STACK)
