# Packaging & distribution

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

CI (`.github/workflows/wheels.yml`) builds manylinux/musllinux, macOS, Windows for CPython 3.10–3.14 with `submodules: recursive`.
