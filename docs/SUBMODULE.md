# Engine submodule (`vendor/takumi`)

The Rust Takumi engine is vendored as a **git submodule**:

```text
pytakumi/
  vendor/takumi/     # → https://github.com/kane50613/takumi
  Cargo.toml         # path = "vendor/takumi/takumi"
  src/               # PyO3 bindings
```

## Clone

```bash
git clone --recurse-submodules https://github.com/<you>/pytakumi.git
# or after a normal clone:
git submodule update --init --recursive
```

## Update the engine

```bash
cd vendor/takumi
git fetch origin
git checkout <tag-or-commit>    # e.g. master, v2.5.0
cd ../..
git add vendor/takumi
git commit -m "chore: bump takumi engine to <rev>"

# Rebuild Python extension
maturin develop --release
pytest -q
```

## Build without sibling layout

With the submodule present, **no** `../takumi` sibling is required:

```bash
maturin develop --release
```

`build.rs` fails with a clear message if `vendor/takumi` is missing.
