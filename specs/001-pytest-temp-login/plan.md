# Implementation Plan: pytest 临时登录凭据（--login）

**Branch**: `001-pytest-temp-login` | **Date**: 2026-08-31 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/001-pytest-temp-login/spec.md`

## Summary

为 pytest 测试套件新增可选命令行参数 `--login <phone|qrcode>`：显式传入时无条件执行交互式临时登录（二维码扫码或手机号短信验证码），取得的凭据以 base64 编码写入系统 TEMP 目录的固定名称缓存文件；此后每次测试运行自动尝试读取该缓存——缺失则提示并跳过、损坏则删除报错并跳过、合法则先验证有效性（过期尝试刷新，刷新失败警告+删除+跳过），并按「本次 `--login` > TEMP 缓存 > `BILI_*` 环境变量 > `.bilibili.cookie`」的优先级解析凭据。全部改动限于测试基建（`tests/`），不触碰库公开 API。

## Technical Context

**Language/Version**: Python ≥ 3.10（兼容 CPython 3.10，禁止更高版本独有特性）

**Primary Dependencies**:
- `pytest` + `pytest-asyncio`（`asyncio_mode = "auto"`，见 `pyproject.toml [tool.pytest.ini_options]`）
- `bilibili_api.login_v2`：`QrCodeLogin`（`generate_qrcode` / `get_qrcode_terminal` / `check_state` / `get_credential`）、`send_sms`、`login_with_sms`、`LoginCheck`、`PhoneNumber`
- `bilibili_api.utils.geetest.Geetest`（本地极验服务：`generate_test` / `start_geetest_server` / `get_geetest_server_url` / `has_done`）
- `bilibili_api.Credential`：`check_valid()`（isLogin）、`refresh()`（就地刷新，依赖 `ac_time_value`）
- `qrcode` / `qrcode_terminal`（已有依赖，终端二维码）
- 标准库：`tempfile.gettempdir()`（遵循 TEMP/TMP 环境变量）、`base64`、`json`

**Storage**: 本地文件——`tempfile.gettempdir()` 下固定名称的缓存文件（base64 编码的 JSON 凭据字段集合），详见 [contracts/cache-file-format.md](contracts/cache-file-format.md)

**Testing**: pytest。纯逻辑（编解码 / 坏文件判定 / 优先级合并 / 路径解析）放入 `tests/test_offline_login_cache.py` 离线验证；交互式登录与真实凭据生命周期走 [quickstart.md](quickstart.md) 手工场景

**Target Platform**: 开发者本机终端（Windows / Linux / macOS；本项目主要验证环境为 Windows + Git Bash）

**Project Type**: library 的**测试基建扩展**（conftest + 测试辅助模块），不是库公开接口的一部分

**Performance Goals**: N/A（无性能指标；登录轮询间隔约 2 秒，二维码续期上限 3 次）

**Constraints**:
- 凭据字段值不得出现在任何终端输出 / 日志 / 异常消息中（宪法凭据安全红线）
- 库代码（`bilibili_api/`）零改动；`asyncio.run()` 仅允许出现在 `tests/` 侧（宪法异步红线只约束库代码）
- 不带 `--login` 且无缓存文件时，行为与本特性引入前逐字节一致（零回归，SC-005）
- 通过 `uv run python scripts/lint.py` 全量门禁

**Scale/Scope**: 1 个 conftest 扩展 + 1 个纯函数辅助模块 + 1 个离线测试文件 + 文档补充（AGENTS.md 测试凭据来源一节），无新 B 站 API、无 data/api/*.json 变更

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| 宪章原则 | 评估 | 结论 |
|---------|------|------|
| I. 异步优先 | 不改库代码；登录/校验/刷新的 `asyncio.run()` 全部位于 `tests/conftest.py`（调用方角色，非库代码），事件循环隔离安全（见 research.md D2） | ✅ 通过 |
| II. 声明式 API 定义 | 不新增 B 站 API，`data/api/*.json` 零变更；全部复用 `login_v2` 与 `_credential` 既有接口 | ✅ 通过 |
| III. 质量门禁 | `uv run python scripts/lint.py` 必须全绿；`tests/` 新增函数附中文 docstring + 类型注解；不改 `bilibili_api/` 公开符号 → 无需重跑 doc_gen | ✅ 通过 |
| IV. 分层测试 | 新增离线用例只测纯本地逻辑（编解码/判定/合并），无网络无凭据，命名 `tests/test_offline_login_cache.py`；交互登录流程不经自动化集成用例覆盖，走 quickstart 手工验证；`credential` fixture 保留缺凭据 skip 语义 | ✅ 通过 |
| V. 兼容性 | 无库接口变更、无破坏性变更；conftest 既有 fixture 签名不变；`BILI_RATELIMIT` 限速语义不变 | ✅ 通过 |
| 技术与安全约束 | 凭据仅存于本机 TEMP（永不入库，`.gitignore` 无需变更）；所有提示/错误/警告消息只含状态描述不含凭据值；base64 为编码非加密已由 spec 声明接受；临时文件路径由 `tempfile.gettempdir()` 派生（无外部输入后缀，无白名单过滤义务） | ✅ 通过 |
| 开发工作流 | 遵循 Conventional Commits（`feat`/`test`/`docs` 拆分提交）；完成后跑全量门禁 | ✅ 通过 |

**Phase 1 复查**：设计产物（research.md / data-model.md / contracts/ / quickstart.md）未引入任何违反上述原则的元素；登录流程不触碰库代码、契约文档不含凭据样例值。门禁维持全绿。✅

## Project Structure

### Documentation (this feature)

```text
specs/001-pytest-temp-login/
├── plan.md              # This file ($speckit-plan command output)
├── research.md          # Phase 0 output ($speckit-plan command)
├── data-model.md        # Phase 1 output ($speckit-plan command)
├── quickstart.md        # Phase 1 output ($speckit-plan command)
├── contracts/           # Phase 1 output ($speckit-plan command)
│   ├── cli-option.md
│   └── cache-file-format.md
└── tasks.md             # Phase 2 output ($speckit-tasks command - NOT created by $speckit-plan)
```

### Source Code (repository root)

```text
tests/
├── conftest.py                    # 扩展：pytest_addoption(--login)、会话级凭据装配、
│                                  #       缓存读取/校验/刷新编排、提示/错误/警告输出
├── _login_cache.py                # 新增：纯函数模块——缓存路径解析、base64 编解码、
│                                  #       内容合法性判定、凭据来源优先级合并（可离线单测）
└── test_offline_login_cache.py    # 新增：离线单元测试（无网络、无真实凭据）
AGENTS.md                          # 文档补充：测试凭据来源增加 TEMP 缓存与 --login 说明
```

**Structure Decision**: 采用「conftest 编排 + 私有纯函数模块」而非独立 pip 可安装 pytest 插件：本特性只服务本仓库测试套件，conftest 的 `pytest_addoption` 已满足 CLI 参数需求（无需 entry-points 打包）；将可离线测试的纯逻辑抽到 `tests/_login_cache.py`（下划线前缀，不被 pytest 收集），使离线用例可直接 import 而无需导入 conftest（避免反模式）。库目录 `bilibili_api/` 保持零改动，天然规避 doc_gen / 类型棘轮 / 文档漂移门禁的连锁义务。

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

无宪法违规，不适用。
