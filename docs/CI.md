# CI / CD 配置说明

## 1. 总览

| Workflow | 文件 | 触发 | 作用 |
| --- | --- | --- | --- |
| **CI** | `.github/workflows/ci.yml` | `push` master/main、`pull_request`、手动 | 语法、多 OS×Python 源码构建+pytest、Clippy、Linux 单 wheel smoke |
| **Wheels** | `.github/workflows/wheels.yml` | **`v*` tag**、手动、部分路径 PR | 全平台 wheel + sdist；**tag 上全部成功后 Publish 到 PyPI** |

**发版主路径 = 推 `v*` tag → Wheels 全绿 → Publish。**  
Trusted Publisher 配好后 **没有** 单独的「只 publish」workflow；publish 是 Wheels 的最后一个 job。

---

## 2. CI（`ci.yml`）— 日常质量门

| Job | 内容 | 重要程度 |
| --- | --- | --- |
| `lint-python` | `compileall` + ast | 低 |
| `test` 矩阵 | `ubuntu/windows/macos` × **3.10–3.14**；另 **Ubuntu × 3.14t** | **高** |
| `clippy` | `cargo clippy -- -D warnings` | 高 |
| `wheel-smoke` | maturin-action 打 Linux 单 wheel + pytest | 中 |

测试步骤要点：

- `submodules: recursive`  
- **Rust 1.91.0**（`dtolnay/rust-toolchain`）  
- `maturin build --release` → `pip install dist/*.whl`（接近用户安装，少用 `develop` 踩 rustup）  
- collect 数 **≥ 80**  

`rust-toolchain.toml` **只 pin channel**，不要在里面写 `clippy` 组件（CI 上易 rustup 冲突）；需要 clippy 的 job 用 action 装组件。

---

## 3. Wheels（`wheels.yml`）— 发版矩阵

### 3.1 触发

```yaml
on:
  push:
    tags: ["v*"]      # 发版
  workflow_dispatch:  # 手动验证
  pull_request:       # 仅当 Cargo/src/python/scripts/tests/vendor/pyproject/workflow 变更
```

### 3.2 Jobs 与依赖（★ 决定有没有 Publish）

```text
linux (x86_64) ──┐
linux (aarch64) ─┤
macos (x86_64) ──┼──► publish  (仅 refs/tags/v* 且 needs 全部 success)
macos (arm64)  ──┤
windows (AMD64) ─┤
windows (ARM64) ─┤
sdist ───────────┘
```

```yaml
publish:
  needs: [linux, macos, windows, sdist]
  if: startsWith(github.ref, 'refs/tags/v')
  environment: pypi
  permissions:
    id-token: write   # Trusted Publisher / OIDC
```

| 现象 | 原因 |
| --- | --- |
| 没有 Publish job / 一直 skipped | **任一** `needs` job 失败、取消、或一直排队；或不是 `v*` tag |
| Publish 等审批 | GitHub Environment `pypi` 开了 protection（当前仓库默认可为空） |
| Trusted Publisher 配了仍无包 | 先看 **wheels 是否全绿**；再对 PyPI 上的 workflow 路径、环境名 |

### 3.3 平台 × Runner × 架构（★ 易过时）

| Job 名 | `runs-on` | `CIBW_ARCHS` / 说明 |
| --- | --- | --- |
| Linux x86_64 | `ubuntu-latest` | `x86_64` → manylinux + musllinux |
| Linux aarch64 | `ubuntu-24.04-arm` | `aarch64` |
| macOS x86_64 | **`macos-15-intel`** | `x86_64`（**禁止**再用 `macos-13`，已退役会无限排队） |
| macOS arm64 | `macos-14` | `arm64` |
| Windows AMD64 | `windows-latest` | `AMD64` |
| Windows ARM64 | `windows-11-arm` | `ARM64`（免费额度可能受限） |

### 3.4 Python 版本（`pyproject.toml` `[tool.cibuildwheel]`）

| 配置 | 值 | 含义 |
| --- | --- | --- |
| `enable` | `cpython-freethreading` | 允许打 free-threaded wheel |
| `build` | `cp310-*` … `cp314-*` **`cp314t-*`** | 3.10–3.14 + **仅 3.14t** |
| `skip` | `pp*`、`*i686`、`win32`、`cp313t-*` | 无 PyPy / 32 位 / **不要 3.13t** |

每个 wheel：干净 venv 安装 → 跑测试（Linux 用 `scripts/cibw_test.py`）。

### 3.5 Linux 特有：Rust + 测试入口（★ 极重要）

容器内 **没有** 主机 Rust，必须：

```yaml
CIBW_BEFORE_ALL_LINUX: rustup 安装 1.91.0
CIBW_ENVIRONMENT_LINUX: PATH=…/.cargo/bin:… RUST_MIN_STACK=8388608
```

**测试命令必须单进程**（写在 `wheels.yml` 的 `CIBW_TEST_COMMAND`，避免 tag 漏配置）：

```bash
ulimit -s unlimited   # 尽量抬主线程栈
export CIBW_PROJECT={project}
python {project}/scripts/cibw_test.py
```

`scripts/cibw_test.py` 顺序：

1. `threading.stack_size(8MiB)`  
2. `import pytakumi`（触发 native 栈初始化）  
3. `html_to_pic` smoke → **`render-ok`**  
4. `render_animation` smoke → **`animation-ok`**  
5. 全量 `pytest tests`  

日志里若只有 `import-ok` 而没有 `cibw_test:` 前缀，说明跑的是 **旧 commit**。

Workflow 里还有：

```yaml
- name: Verify cibw test runner is present
  run: test -f scripts/cibw_test.py
```

### 3.6 musllinux 构建覆盖（`pyproject.toml`）

```toml
[[tool.cibuildwheel.overrides]]
select = "*-musllinux_*"
environment = {
  RUST_MIN_STACK = "8388608",
  CARGO_PROFILE_RELEASE_LTO = "false",
  CARGO_PROFILE_RELEASE_CODEGEN_UNITS = "16",
  CARGO_PROFILE_RELEASE_OPT_LEVEL = "2",
}
```

缩小栈帧；再配合 native / Python 栈修复（[PITFALLS.md](./PITFALLS.md)）。

### 3.7 全局环境

| 变量 | 作用 |
| --- | --- |
| `RUST_MIN_STACK=8388608` | Rust `std::thread` / 影响 Rayon 默认栈 |
| `MACOSX_DEPLOYMENT_TARGET=11.0` | macOS 最低部署版本 |

---

## 4. 配置分散在哪里（改之前先看清）

| 关注点 | 位置 |
| --- | --- |
| 打哪些 Python / skip | `pyproject.toml` → `[tool.cibuildwheel]` |
| Linux before-all / musl override / 默认 test-command | `pyproject.toml` → `[tool.cibuildwheel.linux]` + `overrides` |
| **强制** Linux 测试入口、runner 矩阵、Publish | **`.github/workflows/wheels.yml`** |
| 栈行为（运行时） | `src/lib.rs`、`python/pytakumi/_stack.py`、`tests/conftest.py` |
| 子模块 | `.gitmodules` + checkout `submodules: recursive` |
| Rust 版本 | `rust-toolchain.toml` + workflow 里 1.91.0 |

**注意：** GHA 里设置的 `CIBW_*` 环境变量会 **覆盖** pyproject 同名项。  
`wheels.yml` 已用 `CIBW_TEST_COMMAND` 钉死 Linux 测试；改测试入口时 **workflow 与 pyproject 一起改**。

---

## 5. 发布到 PyPI（Trusted Publisher）

### 5.1 仓库侧（已设计）

- Job：`publish`  
- `environment: pypi`（GitHub Environments 里需存在同名环境）  
- `permissions: id-token: write`  
- Action：`pypa/gh-action-pypi-publish`  
- 输入：各 job 上传的 `wheels-*` / `sdist` artifact  

### 5.2 PyPI 侧（维护者配置）

Trusted Publisher 大致应对：

| 字段 | 期望值 |
| --- | --- |
| Owner | `KimigaiiWuyi`（或当前 org/user） |
| Repository | `pytakumi` |
| Workflow | `.github/workflows/wheels.yml`（或 UI 要求的文件名形式） |
| Environment | `pypi` |

包名：`pytakumi`。

### 5.3 成功路径 checklist

1. `master` 上修复已 push。  
2. **在该 commit 上** `git tag vX.Y.Z && git push origin vX.Y.Z`。  
3. Wheels 所有平台 job **全部 success**（含 macos-15-intel、双 Linux）。  
4. 出现 **Publish to PyPI** 且为 success。  
5. https://pypi.org/project/pytakumi/ 有新版本。

---

## 6. 最关键配置速查（Checklist）

发版 / 改 CI 前自问：

1. **tag 是否指向含 `scripts/cibw_test.py` 与最新 `src/lib.rs` 的 commit？**  
2. **Linux 是否仍用 `CIBW_TEST_COMMAND` → `cibw_test.py`？**（禁止再拆成 `python -c import` + 另起 `pytest`）  
3. **macOS x86_64 是否为 `macos-15-intel`？**（禁止 `macos-13`）  
4. **checkout 是否 `submodules: recursive`？**  
5. **Rust 是否 1.91？** 容器内是否 rustup？  
6. **`cp314t` 开、`cp313t` 关？**  
7. **musllinux 是否仍有 LTO=false override + 栈相关代码？**  
8. **Publish 的 needs 是否会因任一矩阵失败而整段跳过？**  
9. **Edition 2024：`extern "C"` 必须写成 `unsafe extern "C"`。**  
10. **改 `pythonpath` 时绝不能让源码树盖住已安装 wheel。**

---

## 7. 相关文件一览

```text
.github/workflows/ci.yml
.github/workflows/wheels.yml
pyproject.toml          # [tool.cibuildwheel*] [tool.maturin] [tool.pytest]
rust-toolchain.toml
scripts/cibw_test.py
src/lib.rs
python/pytakumi/_stack.py
tests/conftest.py
docs/PITFALLS.md
docs/PACKAGING.md
docs/HANDOVER.md
```
