# 项目架构与背景

## 1. 项目是什么

**pytakumi** 是 [Takumi](https://github.com/kane50613/takumi) 布局/渲染引擎的 **独立 Python 绑定与打包仓库**。

| 概念 | 说明 |
| --- | --- |
| 引擎 | Rust 实现的 HTML/CSS 子集 → 图片（PNG/JPEG/WebP/…），**无浏览器** |
| 本仓库 | PyO3 + maturin 的 FFI、高层 API（`html_to_pic` / `text_to_pic` / `md_to_pic`）、测试与多平台 wheel 发布 |
| 包名 | PyPI：`pytakumi` |
| 引擎位置 | `vendor/takumi`（git submodule → `kane50613/takumi`） |
| 官方关系 | **非** Takumi 官方发布，除非上游采纳；许可证与引擎一致（MIT OR Apache-2.0） |

### 适合 / 不适合

| 适合 | 不适合 |
| --- | --- |
| OG 卡片、机器人消息、Markdown 文档图 | 任意活网站 + 完整浏览器行为 |
| 可控 HTML/CSS 模板 | 需要完整 JS / 完整 CSSOM |
| 服务端批量出图、无 Chromium 依赖 | 与 Chromium 像素级一致（请用 Playwright） |

终端用户安装 **预编译 wheel** 时：**不需要** Rust、浏览器、子模块。

---

## 2. 运行时分层

```text
┌─────────────────────────────────────────────────────────┐
│  用户 Python 代码                                        │
│  html_to_pic / text_to_pic / md_to_pic / Renderer       │
└───────────────────────────┬─────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────┐
│  python/pytakumi/   纯 Python                            │
│  api.py, markdown.py, _util.py, _stack.py, templates/   │
└───────────────────────────┬─────────────────────────────┘
                            │ import
┌───────────────────────────▼─────────────────────────────┐
│  pytakumi._native   (maturin 编出的 cdylib)               │
│  src/*.rs  PyO3：Renderer, NodeTree, from_html, …       │
└───────────────────────────┬─────────────────────────────┘
                            │ path 依赖
┌───────────────────────────▼─────────────────────────────┐
│  vendor/takumi/   引擎 monorepo                          │
│  takumi / takumi-core / takumi-raster / takumi-html …   │
└─────────────────────────────────────────────────────────┘
```

**关键不变量**

1. 引擎在 **编译期** 链进扩展；wheel 里只有 `.so`/`.pyd` + 少量 Python/模板。  
2. 发布 wheel 时 `git checkout` **必须** `submodules: recursive`，否则 maturin 编不过。  
3. pytest **不要** 把 `python/` 放进 `pythonpath` 去盖住已安装的 `site-packages` 包（会找不到 `_native`）。

---

## 3. 仓库目录结构

```text
pytakumi/
├── README.md                 # 用户向：安装、API、开发入口
├── docs/                     # 维护者文档（本目录）
├── pyproject.toml            # 包元数据 + maturin + cibuildwheel + pytest
├── Cargo.toml / Cargo.lock   # Rust 绑定 crate（cdylib: _native）
├── rust-toolchain.toml       # 锁定 rustc（当前 1.91.x，勿乱加 clippy 组件）
├── build.rs                  # 检查 vendor/takumi 是否存在
├── src/                      # PyO3 绑定（唯一手写 Rust 业务）
│   ├── lib.rs                # 模块入口、线程栈、gil_used=false
│   ├── renderer.rs           # Renderer / render / 动画等
│   ├── node.rs               # NodeTree / from_html / builders
│   ├── options.rs / error.rs
├── python/pytakumi/          # 发布进 wheel 的 Python 包
│   ├── __init__.py           # 导出 + 调用 _stack
│   ├── api.py                # 高层 API
│   ├── markdown.py / _util.py
│   ├── _stack.py             # musl 上 Python 线程栈
│   ├── templates/            # Markdown/文本卡片 CSS
│   └── py.typed + *.pyi
├── vendor/takumi/            # 子模块：引擎源码（勿当普通拷贝目录）
├── tests/                    # 产品测试（≥80 collect；含并发 / free-threaded）
├── benchmarks/               # 可选基准
├── scripts/
│   ├── cibw_test.py          # ★ Linux wheel 测试入口（单进程）
│   └── …
└── .github/workflows/
    ├── ci.yml                # PR/push：多平台源码测 + clippy + smoke
    └── wheels.yml            # 发版：全平台 wheel + sdist + PyPI
```

### 与「源码树 Python」的区别

| 场景 | 用的包 |
| --- | --- |
| `maturin develop` / `pip install dist/*.whl` | `site-packages` 里的包 + 编译好的 `_native` |
| 错误配置 `pythonpath = ["python"]` | 可能 import 到源码树、**没有** `_native` → CI 红 |

`pyproject.toml` 里 `pythonpath = ["tests"]` 仅服务测试辅助模块，**不要**再加 `python/`。

---

## 4. 核心 API 与状态

| 符号 | 角色 |
| --- | --- |
| `html_to_pic` / `text_to_pic` / `md_to_pic` | 高层一站式出图 |
| `Renderer` | 可复用：字体与资源缓存；**可跨线程共享**（free-threaded 安全） |
| `from_html` / `NodeTree` | 解析一次、多次渲染 |
| `set_glyph_cache_max_bytes` | 进程级字形缓存预算（宜在首次渲染前调用） |
| `supports_free_threading` | 恒为 `True`（模块声明 `gil_used = false`） |

### 线程与缓存（实现要点）

- `Renderer`：`#[pyclass(frozen)]`，内部 `Arc` + `ArcSwap`（字体）+ `Mutex`（注册）+ 引擎侧同步 `ResourceCache`。  
- 模块：`#[pymodule(gil_used = false)]`，支持 **3.14t** free-threaded。  
- 进程默认 `Renderer`（`_util.default_renderer`）：双重检查锁，避免 free-threaded 下双初始化。  
- **栈**：见 [PITFALLS.md](./PITFALLS.md) / [PACKAGING.md](./PACKAGING.md)——Python 线程栈 ≠ Rust `RUST_MIN_STACK`。

---

## 5. 构建产物

| 产物 | 工具 | 用户是否需要 Rust |
| --- | --- | --- |
| wheel（`.whl`） | maturin + cibuildwheel | 否 |
| sdist（`.tar.gz`） | maturin sdist | 是（含 `vendor/takumi`） |
| 本地开发 | `maturin develop --release` | 是 |

Python：**3.10–3.14**（GIL）+ **cp314t**（free-threaded）。不发布 **cp313t**。

平台细节见 [CI.md](./CI.md) 与 [PACKAGING.md](./PACKAGING.md)。

---

## 6. 相关上游

| 资源 | URL |
| --- | --- |
| 引擎仓库 | https://github.com/kane50613/takumi |
| 引擎文档 / Playground | https://takumi.kane.tw |
| 本绑定仓库 | https://github.com/KimigaiiWuyi/pytakumi |

升引擎流程：[SUBMODULE.md](./SUBMODULE.md)。
