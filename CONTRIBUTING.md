# Contributing

## Setup

`maturin develop` **requires a virtualenv**. CI builds a wheel with `maturin build`
and `pip install`s it (avoids rustup component races on some runners).

```bash
git clone --recurse-submodules <repo>
cd pytakumi
python -m venv .venv && source .venv/bin/activate  # Windows: .\.venv\Scripts\Activate.ps1
pip install maturin pytest markdown-it-py pillow
maturin develop --release
# or: maturin build --release -o dist && pip install dist/*.whl
pytest -q
```

Do not set `PYTHONPATH=python` when testing: that shadows the installed package and
drops `pytakumi._native`.

`rust-toolchain.toml` pins **1.91.0 only** (no clippy/rustfmt components). Add those
with `rustup component add clippy rustfmt` locally if you need them.

## Before a PR

1. `pytest -q`
2. `cargo clippy --all-targets -- -D warnings` (optional locally; CI runs it)
3. If you touch the engine pin: update `vendor/takumi` submodule and note the commit in the PR

## Engine updates

See [docs/SUBMODULE.md](./docs/SUBMODULE.md).

## Layout of the repo

| Path | Role |
| --- | --- |
| `vendor/takumi` | Upstream engine submodule |
| `src/` | PyO3 bindings |
| `python/pytakumi/` | Public Python API |
| `tests/` | Unit / integration tests |
| `benchmarks/` | Optional multi-backend perf harness |
| `.github/workflows/` | CI + wheels |
