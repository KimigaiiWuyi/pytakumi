# Contributing

## Setup

```bash
git clone --recurse-submodules <repo>
cd pytakumi
python -m venv .venv && source .venv/bin/activate  # or Windows Activate.ps1
pip install maturin pytest markdown-it-py pillow
maturin develop --release
pytest -q
```

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
