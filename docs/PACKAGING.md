# Packaging & distribution

维护者总览请先读：**[CI.md](./CI.md)**、**[PITFALLS.md](./PITFALLS.md)**、**[HANDOVER.md](./HANDOVER.md)**、**[ARCHITECTURE.md](./ARCHITECTURE.md)**。  
本文侧重：用户安装、wheel 矩阵、free-threaded、musl 栈修复细节。

## Can users just `pip install pytakumi`?

**Yes — once a matching wheel is published.** Runtime needs only CPython 3.10–3.14; no Rust, no browser, no submodule.

```bash
pip install pytakumi
pip install "pytakumi[markdown]"   # better Markdown (markdown-it-py)
```

## Source builds (contributors)

```bash
git clone --recurse-submodules <this-repo>
cd pytakumi
python -m venv .venv && source .venv/bin/activate
pip install maturin
maturin develop --release
```

Engine lives at `vendor/takumi` (git submodule). See [SUBMODULE.md](./SUBMODULE.md).

## High-level APIs

```python
from pytakumi import html_to_pic, text_to_pic, md_to_pic

png = html_to_pic("<div style='padding:40px'>Hello</div>", width=600, height=200)
png = text_to_pic("状态正常", title="日报", theme="dark", width=720)
png = md_to_pic("# Title\n\n- item", width=800)  # GitHub README style
```

## Multi-platform wheels

CI (`.github/workflows/wheels.yml`) uses **cibuildwheel on every OS** (not maturin for a single host Python). Each wheel is built for **CPython 3.10–3.14**, installed into a clean venv, and run through the full `pytest` suite.

| Platform | Arch runners | Wheel tags (typical) | Notes |
| --- | --- | --- | --- |
| Linux | `ubuntu-latest` (x86_64), `ubuntu-24.04-arm` (aarch64) | `manylinux_2_28_*` **and** `musllinux_1_2_*` | **One job per arch** builds both glibc and musl wheels. |
| macOS | `macos-15-intel` (x86_64), `macos-14` (arm64) | `macosx_11_0_x86_64`, `macosx_11_0_arm64` | **Not** `macos-13` (retired / no runners). Intel uses `macos-15-intel`. |
| Windows | `windows-latest` (AMD64), `windows-11-arm` (ARM64) | `win_amd64`, `win_arm64` | Same multi-version + test policy as other OSes. |
| sdist | ubuntu | `*.tar.gz` | Includes `vendor/takumi` for source builds. |

Checkout always uses `submodules: recursive`.

### Free-threaded CPython (`cp314t`)

| Item | Detail |
| --- | --- |
| Built | **Yes** — `cp314t-*` on all OS/arch matrix entries (via `enable = ["cpython-freethreading"]`). |
| Not built | **`cp313t`** (experimental free-threaded 3.13; skipped deliberately). |
| Native module | `#[pymodule(gil_used = false)]`; `Renderer` / `NodeTree` are `#[pyclass(frozen)]` and `Send + Sync`. |
| Shared state | Fonts: `ArcSwap` + registration `Mutex`; images/styles: engine `ResourceCache` (quick_cache sync); glyphs: process-global sync cache; Rayon pool: 8 MiB stacks on import. |
| Python helper | `default_renderer()` uses double-checked locking (free-thread safe singleton). |
| Tests | `tests/test_concurrency.py` — shared Renderer/NodeTree, concurrent `register_font`, bitwise-identical raw frames, animation, default-renderer singleton; heavier worker counts when GIL is disabled. |
| Public flag | `pytakumi.supports_free_threading is True`. |

### What is *not* published

| Variant | Status |
| --- | --- |
| Free-threaded **3.13t** (`cp313t`) | Skipped (prefer stable 3.14t only). |
| PyPy, 32-bit (`i686`, `win32`) | Skipped. |
| `universal2` macOS | Not built; publish separate x86_64 and arm64 wheels. |

### musl stack fix (required for musllinux / Alpine)

musl’s default **pthread stack is 128 KiB**. Symptom under cibuildwheel:  
`import-ok` succeeds (main thread has a large process stack), then full `pytest` **SIGSEGV (139)** when native code runs with more stack depth / worker threads.

| Thread kind | Stack control |
| --- | --- |
| Main / process | `ulimit -s` |
| **Any new pthread** (Python workers, many C libs) | **`pthread_setattr_default_np`** (native module on Linux) |
| **Python** `threading` / `ThreadPoolExecutor` | **`threading.stack_size(8 MiB)`** |
| **Rust** `std::thread` / Rayon | `RUST_MIN_STACK` + Rayon `stack_size` |

Mitigations in this package:

1. **Native** (`src/lib.rs`): on Linux, `pthread_setattr_default_np` + Rayon 8 MiB + `RUST_MIN_STACK`.
2. **`pytakumi._stack`**: at import, on musl, `threading.stack_size(8 MiB)`.
3. **`tests/conftest.py`**: same for the suite.
4. **`scripts/cibw_test.py`**: **one process** — stack setup, HTML smoke, animation smoke, then pytest (avoids split `python -c` / `pytest` processes).
5. **musllinux override**: `LTO=false`, `opt-level=2` (smaller frames).
6. Default release profile: thin LTO (non-musl).

Users who spawn threads *before* `import pytakumi`:

```python
import threading
threading.stack_size(8 * 1024 * 1024)
```
