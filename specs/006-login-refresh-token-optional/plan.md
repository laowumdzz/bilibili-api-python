# Implementation Plan: 扫码登录不再强制 ac_time_value（refresh_token）非空

**Branch**: `006-login-refresh-token-optional` | **Date**: 2026-09-26 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/006-login-refresh-token-optional/spec.md`

## Summary

放宽 WEB 通道二维码登录凭据构造的必需字段校验：`ac_time_value`（refresh_token）从必需字段降级为可选字段——B 站未下发或下发空值时登录照常成功、凭据照常构造，仅三个 Cookie 字段（SESSDATA / bili_jct / DedeUserID）保持必需。源码改动收敛在 `bilibili_api/login_v2.py` 的 `check_state()` WEB DONE 分支一处（必需字段元组移除 `ac_time_value`）及其 docstring；同步反转既有离线断言用例并新增空值与归一用例；`scripts/login_and_cache.py` 及缓存链路零代码改动（已天然兼容，作为回归锁定对象）。

## Technical Context

**Language/Version**: Python ≥ 3.10（不得使用更高版本独有特性）

**Primary Dependencies**: 无新增依赖。涉及模块：`bilibili_api/login_v2.py`（唯一源码改动点）、`bilibili_api/utils/_credential.py`（只读依赖其既有假值语义）、`scripts/login_and_cache.py`（行为验收对象，预计零改动）、`scripts/_login_cache.py`（零改动）

**Storage**: TEMP 目录登录缓存文件 `bilibili_api_pytest_login.json`（契约见 specs/001，本特性不变更）

**Testing**: pytest —— 离线单元测试（`tests/test_offline_login_v2.py`，复用既有 `_patch_web_poll` / `_FULL_FAKE_COOKIES` 辅助）+ 人工真机扫码验收

**Target Platform**: 跨平台 Python 库（Windows / Linux / macOS），uv 管理环境

**Project Type**: library（附带 scripts 工具脚本）

**Performance Goals**: N/A（无性能敏感面变化）

**Constraints**: `scripts/lint.py` 全链路门禁全绿；`check_state` 为公共方法，docstring 变更后必须重跑 `scripts/doc_gen.py`；异常消息不得包含任何凭据值；Python 3.10 兼容语法

**Scale/Scope**: 核心改动 1 处判断元组 + 1 段 docstring + 1 个离线用例反转 + 1~2 个新增空值离线用例；TV 通道 / 短信登录 / 密码登录 / 缓存链路零改动（回归用例锁定）

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| 原则 | 评估 | 结论 |
|------|------|------|
| I. 异步优先 | 改动点 `check_state()` 已为 `async def`，无新增同步阻塞、不触碰客户端抽象 | ✅ 通过 |
| II. 声明式 API 定义 | 不新增 API、不变更请求链路，仅调整响应解析后的字段校验集合 | ✅ 通过 |
| III. 质量门禁（NON-NEGOTIABLE） | `check_state` docstring 的 Raises 段描述四字段必需，行为变更后必须同步更新并重跑 `doc_gen.py`；lint 全链路（含 docs/modules 漂移校验）列入任务 | ✅ 通过（义务已列入任务） |
| IV. 分层测试 | 用例更新与新增全部落在离线层（无网络、无凭据、fake 值）；真机验收为只读人工步骤，不写入测试套件 | ✅ 通过 |
| V. 兼容性与破坏性变更 | 行为放宽（原抛异常场景改为成功），无接口签名变化，属非破坏性变更；`ArgsException` 保留给三 Cookie 字段；提交为单一 `fix` 提交 | ✅ 通过 |
| 凭据安全红线 | 异常消息沿用"仅字段名"现状；测试继续使用 `fake-*` 值；缓存文件永不写入空值键（既有非空过滤） | ✅ 通过 |

**Phase 1 后复评**: 设计产物（contracts/library-api.md、data-model.md）未引入新模块、新异常类型或新接口面，上述结论全部维持。

## Project Structure

### Documentation (this feature)

```text
specs/006-login-refresh-token-optional/
├── plan.md              # 本文件（$speckit-plan 输出）
├── research.md          # Phase 0 输出：决策与依据
├── data-model.md        # Phase 1 输出：凭据字段分层与校验矩阵
├── quickstart.md        # Phase 1 输出：验证指南
├── contracts/           # Phase 1 输出：library-api.md（QrCodeLogin WEB 通道行为契约）
└── tasks.md             # Phase 2 输出（$speckit-tasks，本命令不创建）
```

### Source Code (repository root)

```text
bilibili_api/
└── login_v2.py              # 唯一源码改动：check_state() WEB DONE 分支必需字段元组 + docstring
tests/
└── test_offline_login_v2.py # 用例反转（缺 refresh_token）+ 新增空值用例（全部离线）
scripts/
├── login_and_cache.py       # 行为验收对象（扫码流程成功写缓存），预计零代码改动
└── _login_cache.py          # 缓存契约单一实现，零改动（回归锁定）
docs/modules/                # doc_gen 再生成产物（docstring 变更联动，禁止手改）
```

**Structure Decision**: 单库结构（library + scripts + tests），无新增目录；本特性不产生新文件，只修改上述三个既有文件（其中 docs/ 为工具再生成）。

## Complexity Tracking

> 无宪法违规需要辩护，本表留空。
