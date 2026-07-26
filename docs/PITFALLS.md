# 踩坑记录与注意事项

本文汇总 **2025–2026 发版与 CI 实战** 中反复踩到的坑。改 CI / 打 tag / 动 musl 前请通读。

---

## 1. 发版与 Git（最高频）

### 1.1 tag 必须钉在「含修复的 commit」上

| 错误 | 后果 |
| --- | --- |
| 本地改完 **未 push** 就 `git tag` + `git push --tags` | Actions 编的是远端旧代码 |
| master 已推新 commit，但 tag 仍指旧 sha | 日志里永远是「旧行为」 |
| 用 Annotated/Lightweight 均可，但 **push 的必须是新 tag → 新 sha** | — |

**正确：**

```bash
git pull
git log -1 --oneline          # 确认 sha
ls scripts/cibw_test.py       # 确认关键文件在这一版
git tag v0.x.y
git push origin v0.x.y
```

**如何确认 Actions 跑的是新逻辑：**  
Linux 日志应出现：

```text
cibw_test: threading.stack_size=...
cibw_test: import-ok ...
cibw_test: render-ok ...
cibw_test: animation-ok ...
```

若只有：

```text
import-ok 0.1.0
# 然后直接 pytest 或立刻 SIGSEGV
```

且 **没有** `cibw_test:` 前缀 → **跑的还是拆成两段的旧 test-command**（旧 tag）。

### 1.2 改代码 ≠ Actions 会变

讨论里「日志还是旧命令」往往是：

- 远端 tag 的 tree 里 **确实没有** `scripts/cibw_test.py`，或  
- test-command 仍是 `python -c import` + 另起 `pytest`  

用 GitHub 网页打开：  
`https://github.com/<owner>/pytakumi/blob/<tag>/scripts/cibw_test.py`  
404 就说明该 tag 不含修复。

---

## 2. musl / musllinux SIGSEGV（exit 139）

### 2.1 症状

```text
import-ok 0.1.0
Segmentation fault (core dumped)   # pytest 中
AUDITWHEEL_PLAT=musllinux_1_2_x86_64  或  ..._aarch64
```

- **manylinux（glibc）**：通常全绿  
- **musllinux**：import 常成功，一跑完整测试（尤其动画 / 并发）就 139  

### 2.2 根因（务必分清三种栈）

| 栈 | 谁创建 | 默认（musl） | 谁负责加大 |
| --- | --- | --- | --- |
| 主线程 / 进程 | 进程 | 常与 `ulimit -s` 相关（可达数 MiB） | `ulimit -s unlimited` |
| **Python** `threading` / `ThreadPoolExecutor` | **pthread** | **128 KiB** | `threading.stack_size(8MiB)` + **`pthread_setattr_default_np`** |
| **Rust** Rayon / `std::thread` | Rust | 受 musl 默认影响 | `RUST_MIN_STACK` + Rayon `stack_size` |

**只设 `RUST_MIN_STACK` 救不了 Python 工作线程。**  
**`python -c "import …"` 与 `pytest` 是两个进程**，前一个进程里设的 `threading.stack_size` **不会**传给后一个。

### 2.3 已落地的修复（不要拆掉）

| 层级 | 文件 / 配置 |
| --- | --- |
| Native | `src/lib.rs`：`pthread_setattr_default_np` + Rayon 8MiB + `RUST_MIN_STACK` |
| Python 包 | `python/pytakumi/_stack.py`，`__init__.py` 里 `ensure_for_runtime()` |
| 测试 | `tests/conftest.py` 开头 `threading.stack_size(8<<20)` |
| Wheel 测试入口 | **`scripts/cibw_test.py` 单进程** smoke + pytest |
| Workflow | `CIBW_TEST_COMMAND` → `cibw_test.py`（强制） |
| musl 构建 | `LTO=false`、`opt-level=2`、`codegen-units=16`（`[[tool.cibuildwheel.overrides]]`） |
| 非 musl release | `Cargo.toml`：`lto = "thin"`（避免 fat LTO 过大栈帧） |

### 2.4 用户侧（Alpine / 多线程）

若业务在 **import 之前** 就建了线程池：

```python
import threading
threading.stack_size(8 * 1024 * 1024)
import pytakumi  # 其后创建的线程会更大
```

---

## 3. Rust / 编译

### 3.1 Edition 2024：`extern` 必须 unsafe

```text
error: extern blocks must be unsafe
```

正确：

```rust
unsafe extern "C" {
    fn pthread_setattr_default_np(...);
}
```

### 3.2 `rust-toolchain.toml` 不要列 clippy

在 toml 里写 `components = ["clippy"]` 易在 CI 触发 rustup 冲突。  
Clippy 只在需要的 job 里用 `dtolnay/rust-toolchain` 的 `components: clippy` 安装。

### 3.3 子模块缺失

`build.rs` 会硬失败。始终：

```bash
git clone --recurse-submodules …
# 或
git submodule update --init --recursive
```

Actions：`submodules: recursive`。

### 3.4 Linux 容器内没有主机 Rust

cibuildwheel 的 manylinux/musllinux **容器** 必须 `CIBW_BEFORE_ALL_LINUX` 里 rustup；并保证 `PATH` 含 `$HOME/.cargo/bin`。

---

## 4. GitHub Actions Runner

### 4.1 `macos-13` 已不可用

```text
Requested labels: macos-13
Waiting for a runner to pick up this job...
```

→ 会 **永久或长时间排队**，拖死整个 Wheels（含 Publish）。  

**正确：** `macos-15-intel`（x86_64）+ `macos-14`（arm64）。  
参考：[GitHub Changelog – macOS 13 closing down](https://github.blog/changelog/2025-09-19-github-actions-macos-13-runner-image-is-closing-down/)。

### 4.2 Windows ARM / 大矩阵

`windows-11-arm` 在免费额度上可能慢或不稳定；`fail-fast: false` 时其它 job 仍会跑，但 **Publish 仍要全部 success**。

### 4.3 矩阵失败 ⇒ 没有 Publish

```yaml
publish:
  needs: [linux, macos, windows, sdist]
```

任一 failure / cancelled / 一直 queued → **Publish 不会跑**。  
这与 Trusted Publisher 是否配置 **无关**。

---

## 5. 测试与导入

### 5.1 不要让源码树盖住已安装包

错误：`pythonpath` 包含 `python/`，pytest 优先加载无 `_native` 的源码树。  

正确：`pythonpath = ["tests"]` only（见 `pyproject.toml`）。

### 5.2 CI 用 wheel 安装再测

优先 `maturin build` + `pip install dist/*.whl`，贴近用户，减少 `maturin develop` + rustup 副作用。

### 5.3 free-threaded

- 支持：**cp314t**  
- 不支持：**cp313t**（skip）  
- 模块：`gil_used = false`；类：`frozen` + 可共享 `Renderer`  
- 并发测试：`tests/test_concurrency.py`  

---

## 6. cibuildwheel 配置陷阱

| 陷阱 | 说明 |
| --- | --- |
| GHA `CIBW_*` 覆盖 pyproject | 改 test-command 时 **workflow 与 pyproject 一起改** |
| 拆进程测试 | `python -c import` 与 `pytest` 分离 → 栈/环境不共享 → musl 假绿 import、真红 pytest |
| 覆盖 environment 时丢 PATH | musl override 需自带 `PATH=$HOME/.cargo/bin:$PATH` |
| 只 skip 不修 | 可应急，但用户要求 musllinux 时必须保留栈修复链 |

---

## 7. 历史事件时间线（便于查 tag）

| 阶段 | 现象 | 处理 |
| --- | --- | --- |
| 初版 tag | musllinux x86_64 pytest 139 | 尝试 RUST_MIN_STACK / Rayon 栈 |
| 加重并发测试后 | musllinux aarch64 也 139；import 仍 ok | 认识到 **Python 线程栈** |
| 误 skip 全部 musl | 矩阵绿但无 Alpine wheel | 用户要求恢复 musllinux |
| 旧 tag 日志 | 仍是 split import/pytest | 本地修复未进 tag |
| `extern "C"` | Rust 2024 编不过 | `unsafe extern "C"` |
| macos-13 | 永久 queued | 换 `macos-15-intel` |
| Publish 缺失 | needs 未全绿 | 先修矩阵，不是重配 PyPI |

---

## 8. 快速诊断表

| 日志特征 | 优先检查 |
| --- | --- |
| `extern blocks must be unsafe` | `src/lib.rs` edition 2024 FFI |
| `import-ok` 后立刻 139，无 `cibw_test:` | tag 是否过旧；是否未用 `cibw_test.py` |
| `cibw_test: render-ok` 失败 | 主线程栈 / 渲染路径 / LTO |
| `animation-ok` 失败 | Rayon / 动画 / 栈 |
| pytest 中途 139 | 并发测试、线程栈、是否 musl |
| `Waiting for runner` + macos-13 | 换 `macos-15-intel` |
| 全平台绿但无 Publish | 是否 `v*` tag；needs 是否真全绿；Environment |
| Publish 红 OIDC | Trusted Publisher 的 workflow 路径、env 名 `pypi` |
| `submodule` / `vendor/takumi` missing | checkout recursive / 本地 submodule init |

---

## 9. 相关代码锚点

```text
src/lib.rs                 # ensure_worker_stacks, pthread_setattr_default_np
python/pytakumi/_stack.py  # is_musl, threading.stack_size
python/pytakumi/__init__.py
tests/conftest.py
scripts/cibw_test.py
pyproject.toml             # [tool.cibuildwheel*]
.github/workflows/wheels.yml
.github/workflows/ci.yml
```

更完整的矩阵与发布条件：[CI.md](./CI.md)。  
打包用户向说明：[PACKAGING.md](./PACKAGING.md)。
