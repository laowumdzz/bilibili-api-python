# Implementation Plan: 测试登录凭证流程迁移至独立脚本

**Branch**: `003-login-cache-script` | **Date**: 2026-09-03 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/003-login-cache-script/spec.md`

## Summary

把目前内嵌在 `tests/conftest.py` 的 `--login` 临时登录流程（二维码扫码 / 短信+极验交互、缓存联网校验与过期刷新）迁移到独立可运行的 `scripts/login_and_cache.py`，纯缓存契约逻辑平移到 `scripts/_login_cache.py`。`tests/conftest.py` 瘦身为凭据装配 + 回退链，登录实现经 `scripts.login_and_cache` 模块导入复用；`--login` 入口行为完全兼容，缓存文件契约（specs/001）不变。

## Technical Context

**Language/Version**: Python ≥ 3.10（CPython 3.10 兼容，uv 管理的 `.venv`）

**Primary Dependencies**: `bilibili_api.login_v2`（QrCodeLogin / PhoneNumber / send_sms / login_with_sms / LoginCheck）、`bilibili_api.utils.geetest`（Geetest）、`bilibili_api.Credential`；标准库 `asyncio` / `argparse` / `base64` / `json` / `tempfile`。无新增第三方依赖。

**Storage**: 系统 TEMP 目录缓存文件 `bilibili_api_pytest_login.json`（base64(UTF-8 JSON)，契约见 [specs/001-pytest-temp-login/contracts/cache-file-format.md](../001-pytest-temp-login/contracts/cache-file-format.md)，本特性不变更）

**Testing**: pytest（离线快速路径 `uv run pytest -m "not integration"`；门禁 `uv run python scripts/lint.py` 对 `tests/` 与 `scripts/` 均执行 ruff 阻断检查）

**Target Platform**: 开发者本机交互终端（Windows / macOS / Linux）

**Project Type**: Python 库 + 开发脚本（`scripts/` 下命令行工具）

**Performance Goals**: 不适用（交互式登录，耗时由用户扫码 / 输入验证码决定）

**Constraints**: 全部输出不得含凭据字段值（FR-006）；登录中止不得写 / 破坏缓存（FR-005）；`--login` 行为完全兼容（FR-003）；缓存契约不变更

**Scale/Scope**: 单用户交互工具；迁移范围 1 个新脚本 + 1 个纯逻辑模块平移 + conftest 瘦身 + 1 个离线测试导入行更新 + pyproject 两处小改

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| 原则 | 结论 | 说明 |
|------|------|------|
| I. 异步优先 | ✅ 通过 | 登录流程保持 `async def`；`asyncio.run()` 仅出现在脚本入口与 conftest 装配处（均为"调用方"，非库代码），与现状一致 |
| II. 声明式 API 定义 | ✅ 通过 | 不新增 API 端点；脚本只消费 `login_v2` 既有异步接口与 `Credential` |
| III. 质量门禁 | ✅ 通过 | 新代码经 `ruff check ./tests/ ./scripts/` 阻断；`scripts/login_and_cache.py` 需在 pyproject 增加 T201 豁免（交互式 CLI 输出，与 lint.py 等既有脚本同例）；pyrefly 仅覆盖 `bilibili_api/`，范围不变；不触及 doc_gen / docs/modules/（脚本不在生成范围） |
| IV. 分层测试 | ✅ 通过 | 纯缓存逻辑平移后仍不导入 bilibili_api，离线用例 `test_offline_login_cache.py` 仅改导入行、纯度不变；登录脚本为开发工具而非测试用例 |
| V. 兼容性与破坏性变更 | ✅ 通过 | `--login` 入口保留且行为兼容，无破坏性变更；代码兼容 3.10 |

**Phase 1 设计后复核**：✅ 无新增违规。模块拆分（`scripts/_login_cache.py` 纯逻辑 + `scripts/login_and_cache.py` 流程/CLI）不引入复杂度违规，见 Complexity Tracking（为空）。

## Project Structure

### Documentation (this feature)

```text
specs/003-login-cache-script/
├── plan.md              # 本文件
├── research.md          # Phase 0 输出
├── data-model.md        # Phase 1 输出
├── quickstart.md        # Phase 1 输出
├── contracts/           # Phase 1 输出（CLI 契约 + 模块导入面契约）
│   ├── cli.md
│   └── module-api.md
└── tasks.md             # Phase 2 输出（$speckit-tasks 生成，本命令不创建）
```

### Source Code (repository root)

```text
scripts/
├── login_and_cache.py   # 新增：登录流程（扫码/短信/极验）+ 缓存校验刷新 + CLI 入口
└── _login_cache.py      # 平移自 tests/_login_cache.py：纯缓存契约逻辑（不导入 bilibili_api，内容不变）

tests/
├── conftest.py                  # 瘦身：保留 credential fixture、回退链、限速/超时；登录实现改为导入 scripts.login_and_cache
├── _login_cache.py              # 删除（消费者全部迁往 scripts.*）
└── test_offline_login_cache.py  # 导入行更新：tests._login_cache → scripts._login_cache

pyproject.toml            # 两处小改：per-file-ignores 增加 scripts/login_and_cache.py = ["T201"]；isort known-first-party 增加 "scripts"
```

**Structure Decision**: 库代码 `bilibili_api/` 完全不动（登录工具属开发脚本，不入库、不进文档生成）。共享逻辑以 `scripts/` 命名空间包承载：`tests/__init__.py` 已保证 pytest 将项目根插入 sys.path，`scripts/` 无需 `__init__.py`（命名空间包即可导入）；脚本直接运行时自包含，无 sys.path hack。

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

（空——无宪法违规）
