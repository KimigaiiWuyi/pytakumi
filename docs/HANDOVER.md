# 交接手册（Maintainers）

面向：**接手本仓库的维护者 / 发版负责人**。  
用户向安装与 API 见根目录 [README.md](../README.md)。

---

## 1. 5 分钟认知

| 问题 | 答案 |
| --- | --- |
| 这是什么？ | Takumi 引擎的 **Python 绑定 + 多平台 wheel 发布** |
| 引擎在哪？ | `vendor/takumi` **git submodule**（不是拷贝糊进去的） |
| 用户怎么装？ | `pip install pytakumi`（要有匹配 wheel） |
| 怎么发版？ | 修代码 → push master → **在该 commit 上打 `v*` tag 并 push tag** → 等 Wheels 全绿 → 自动 Publish |
| PyPI 怎么登？ | GitHub **Trusted Publisher**（OIDC），不是在 CI 里塞密码 |
| 最容易翻车的点？ | ① tag 打在旧 commit ② musl 栈 ③ `macos-13` 无 runner ④ 子模块没 init ⑤ Publish 因前置 job 失败被跳过 |

必读：[ARCHITECTURE.md](./ARCHITECTURE.md) · [CI.md](./CI.md) · [PITFALLS.md](./PITFALLS.md)

---

## 2. 账号与权限（交接时逐项确认）

| 资源 | 用途 | 交接动作 |
| --- | --- | --- |
| GitHub 仓库 `KimigaiiWuyi/pytakumi` | 代码、Actions | 加入 Collaborator / 转移 Owner |
| GitHub Environment **`pypi`** | Publish job `environment: pypi` | 确认存在；保护规则是否要审批 |
| PyPI 项目 **`pytakumi`** | 发包 | 确认 Trusted Publisher：repo + `wheels.yml` + env `pypi` |
| 无长期 PyPI API Token 依赖 | OIDC | 一般 **不需要** 在 Secrets 里放 token |

Trusted Publisher 字段应对齐：

- Repository: `…/pytakumi`  
- Workflow: `.github/workflows/wheels.yml`  
- Environment: `pypi`  

---

## 3. 本地开发环境

### 3.1 依赖

- **Python** ≥ 3.10（开发常用 3.12/3.13）  
- **Rust** 1.91+（与 `rust-toolchain.toml` 一致）  
- Git + 子模块  

```bash
git clone --recurse-submodules https://github.com/KimigaiiWuyi/pytakumi.git
cd pytakumi
python -m venv .venv
# Windows: .\.venv\Scripts\Activate.ps1
source .venv/bin/activate
pip install maturin pytest markdown-it-py
maturin develop --release
pytest -q
cargo clippy --all-targets -- -D warnings
```

### 3.2 日常改动落点

| 改什么 | 改哪里 |
| --- | --- |
| Python API / 模板 | `python/pytakumi/` |
| FFI / 线程栈 / 模块标志 | `src/` |
| 引擎版本 | `vendor/takumi` checkout → commit 指针 |
| 测什么 | `tests/` |
| 打哪些 wheel / musl 参数 | `pyproject.toml` + `.github/workflows/wheels.yml` |
| Linux 测入口 | **`scripts/cibw_test.py`** + workflow 里 `CIBW_TEST_COMMAND` |

### 3.3 升取引擎

见 [SUBMODULE.md](./SUBMODULE.md)。升完必须：

```bash
maturin develop --release && pytest -q
```

---

## 4. 测试

| 命令 | 说明 |
| --- | --- |
| `pytest -q` | 全量产品测试 |
| `python scripts/cibw_test.py` | 模拟 Linux wheel 测试入口（含 smoke） |
| collect ≥ 80 | CI 硬门槛 |

重点目录：

- `tests/test_concurrency.py` — 共享 Renderer / free-threaded 压力  
- `tests/test_stack.py` — 栈配置  
- `tests/conftest.py` — **最先** 设置 `threading.stack_size(8MiB)`  

模块地图：`tests/README.md`。

---

## 5. 发版标准流程（照做）

### 5.1 发版前

- [ ] `master` 绿（`ci.yml`）  
- [ ] 版本号：`pyproject.toml` / `Cargo.toml` 的 `version` 一致（当前流程以包元数据为准）  
- [ ] `git status` 干净；**确认要发布的修复已在 `origin/master`**  
- [ ] 本地：`maturin develop --release && pytest -q`  
- [ ] （可选）`python scripts/cibw_test.py`  

### 5.2 打 tag（★ 最容易错）

```bash
git pull origin master
git log -1 --oneline          # 记下 sha，确认含 scripts/cibw_test.py
git tag v0.1.x                # 必须在这个 sha 上打
git push origin v0.1.x        # 推的是 tag，不是只 push master
```

**错误示范**

- 本地改完没 push 就 tag  
- tag 打在旧 commit 上再 push tag  
- 修了 master 却重推旧 tag（需 delete tag 再打，且团队知情）  

### 5.3 盯 Actions

打开 **Wheels** workflow（由 tag 触发）：

1. Linux ×2、macOS ×2、Windows ×2、sdist 是否全绿  
2. Linux 日志是否出现 **`cibw_test: render-ok` / `animation-ok`**  
3. macOS x86_64 是否在 **`macos-15-intel`**（不是 macos-13）  
4. 全绿后是否出现 **Publish to PyPI** 且成功  
5. PyPI 页面版本是否更新  

### 5.4 若 Publish 没出现

见 [CI.md §5](./CI.md) 与 [PITFALLS.md](./PITFALLS.md)：  
几乎一定是 **前置 job 未全部 success**，而不是 Trusted Publisher「没配上」。

---

## 6. 回滚与热修

| 场景 | 建议 |
| --- | --- |
| 错误版本已上 PyPI | 发 **更高版本号** 修复版；PyPI 一般不删正式版 |
| 仅 CI 矩阵坏、代码逻辑对 | 只改 workflow/pyproject，再打 patch tag |
| 引擎回归 | 回退 `vendor/takumi` 指针 + 测 + 发 patch |

---

## 7. 联系与边界

| 边界 | 说明 |
| --- | --- |
| 引擎 bug | 优先在上游 `kane50613/takumi` 修，再 bump 子模块 |
| 绑定 / 打包 / 栈 / CI | 本仓库 |
| 非目标 | 完整浏览器、cp313t、32 位、PyPy（当前 skip） |

---

## 8. 交接当天 checklist

- [ ] 仓库写权限  
- [ ] 能打开 Actions 日志  
- [ ] GitHub Environment `pypi` 可见  
- [ ] PyPI 项目 Owner/Maintainer + Trusted Publisher 条目正确  
- [ ] 本地能 `maturin develop` + `pytest`  
- [ ] 读完 [PITFALLS.md](./PITFALLS.md)  
- [ ] 会打 tag 发版并验证 Publish  

---

## 9. 文档地图

| 文档 | 用途 |
| --- | --- |
| [ARCHITECTURE.md](./ARCHITECTURE.md) | 背景与结构 |
| [CI.md](./CI.md) | CI 全表与关键配置 |
| [PITFALLS.md](./PITFALLS.md) | 踩坑 |
| [PACKAGING.md](./PACKAGING.md) | wheel / musl / free-threaded 技术细节 |
| [SUBMODULE.md](./SUBMODULE.md) | 引擎子模块 |
| [FOOTPRINT.md](./FOOTPRINT.md) | 体积 |
| [BENCHMARKS.md](./BENCHMARKS.md) | 基准 |
