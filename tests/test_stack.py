"""Python thread stack sizing (musl / small-stack platforms)."""

from __future__ import annotations

import threading

from pytakumi._stack import (
    _WORKER_STACK,
    ensure_for_runtime,
    ensure_python_thread_stack,
    is_musl,
)


def test_ensure_python_thread_stack_raises_or_keeps_large():
    prev = ensure_python_thread_stack(_WORKER_STACK)
    # After ensure, new setting should be large enough (or platform rejected).
    try:
        cur = threading.stack_size()
    except (ValueError, RuntimeError):
        return
    if cur != 0:
        assert cur >= 512 * 1024
    # restore is best-effort only
    if prev is not None and prev != 0:
        try:
            threading.stack_size(prev)
        except (ValueError, RuntimeError):
            ensure_python_thread_stack(_WORKER_STACK)


def test_ensure_for_runtime_idempotent():
    ensure_for_runtime()
    ensure_for_runtime()
    try:
        cur = threading.stack_size()
    except (ValueError, RuntimeError):
        return
    if is_musl() and cur != 0:
        assert cur >= 512 * 1024


def test_package_import_runs_stack_hook():
    # Importing pytakumi should have already applied musl boost if needed.
    import pytakumi

    assert pytakumi.__version__
    if is_musl():
        cur = threading.stack_size()
        assert cur == 0 or cur >= 512 * 1024
