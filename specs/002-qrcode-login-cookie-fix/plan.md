# Implementation Plan: 修复网页端二维码登录凭据获取失效

**Branch**: `002-qrcode-login-cookie-fix` | **Date**: 2026-09-03 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/002-qrcode-login-cookie-fix/spec.md`

**Note**: This template is filled in by the `$speckit-plan` command; its definition describes the execution workflow.

## Summary

网页端二维码登录轮询接口（`x/passport-login/web/qrcode/poll`）登录成功时不再通过响应体 `url` 查询串下发 Cookie（该 url 已是无 Cookie 的 `crossDomain` 跳转链接），而是随响应标头 Set-Cookie 下发 5 个登录 Cookie。修复路线：`login_v2.py` WEB 通道 `check_state` 放弃 url 解析，改为读取**同一请求**响应中由服务端下发的 Cookie——三种客户端本就把 Set-Cookie 解析进 `BiliAPIResponse.cookies`（`{name: value}`），当前只是被 `Api` 统一链路丢弃；因此在 `Api` 上新增一个"返回处理结果 + 响应 Cookie"的请求方法（保持统一链路、日志与重试语义），登录侧大小写不敏感映射必需字段并构造 `Credential`，任一必需字段缺失时抛 `ArgsException`（消息不含字段值），不再出现"返回 DONE 但凭据为空"的假成功。

## Technical Context

**Language/Version**: Python ≥ 3.10（MUST 兼容 CPython 3.10，不使用更高版本独有特性）

**Primary Dependencies**: 现有栈——`dataclasses`（`Api` / `BiliAPIResponse`）、客户端抽象 `BiliAPIClient`（aiohttp / httpx / curl_cffi 三实现，均已填充 `BiliAPIResponse.cookies`）；不新增第三方依赖

**Storage**: N/A

**Testing**: pytest + pytest-asyncio。离线层：`tests/test_offline_login_v2.py`（check_state 状态与凭据构造）与 `tests/test_offline_api_core.py`（`Api` 新方法，沿用其 `_make_resp` + `monkeypatch.get_client` 的 fake client 手法）；真机验收：`scripts/qrcode_login.py` 与 `pytest --login qrcode`（特性 001 路径）

**Target Platform**: 跨平台 Python 库（Windows / macOS / Linux）

**Project Type**: library

**Performance Goals**: 不新增网络往返——直接使用 poll 响应自身的 Set-Cookie，不请求 `crossDomain` URL（该域名属 biligame，多一跳且非必需）

**Constraints**: `uv run python scripts/lint.py` 全绿（ruff / format / pyrefly / 类型棘轮只减不增 / 文档漂移）；新增公共方法需完整中文 docstring（Args / Returns / Raises）并重跑 `scripts/doc_gen.py`；凭据字段值不得出现在异常消息、日志或提交内容中

**Scale/Scope**: 改动面 5 处——`bilibili_api/utils/_api.py`（新增 cookie 感知请求方法）、`bilibili_api/login_v2.py`（WEB 分支凭据构造重写）、`tests/test_offline_login_v2.py` 与 `tests/test_offline_api_core.py`（离线用例）、`scripts/qrcode_login.py`（真机验收脚本补全轮询与校验）；另 `docs/modules/` 由 doc_gen 再生成

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| 原则 | 评估 | 结论 |
|------|------|------|
| I. 异步优先 | 新方法为 `async def`；无 `asyncio.run()`、无同步阻塞 | PASS |
| II. 声明式 API 定义 | 不新增接口（复用既有 poll JSON 条目）；请求继续走 `Api` 统一链路（这正是选择扩展 `Api` 而非直连 client 的原因）；全部关键字传参；无硬编码凭据 | PASS |
| III. 质量门禁 | 新公共方法附完整中文 docstring + 全量类型注解；实现后跑 `lint.py` 与 `doc_gen.py`；类型棘轮只减不增 | PASS（按计划执行） |
| IV. 分层测试 | 新用例全部离线（fake client / monkeypatch，无网络无凭据）；真机验收走既有 `--login` 集成路径 | PASS |
| V. 兼容性控制 | `Api.request()` 现有签名与返回不变，新方法纯增量；`check_state` 对外签名与事件枚举不变；Python 3.10 语法；修 bug 与测试按提交粒度拆分 | PASS |
| 凭据安全 | `ArgsException` 消息只含缺失字段名；离线用例使用伪造值；真实凭据不入库 | PASS |

无违例，无需填写 Complexity Tracking。

**Phase 1 设计后复评**（2026-09-03）：`request_with_cookies` 契约（contracts/api.md）保持 `async def` 与统一链路；错误契约显式禁止凭据值入消息；quickstart 三级验证与分层测试边界一致。全部原则维持 PASS，无新增违例。

## Project Structure

### Documentation (this feature)

```text
specs/002-qrcode-login-cookie-fix/
├── plan.md              # This file ($speckit-plan command output)
├── research.md          # Phase 0 output ($speckit-plan command)
├── data-model.md        # Phase 1 output ($speckit-plan command)
├── quickstart.md        # Phase 1 output ($speckit-plan command)
├── contracts/           # Phase 1 output ($speckit-plan command)
│   └── api.md           # 公共 API 行为契约（库类型项目的接口契约）
└── tasks.md             # Phase 2 output ($speckit-tasks command - NOT created by $speckit-plan)
```

### Source Code (repository root)

```text
bilibili_api/
├── login_v2.py                      # QrCodeLogin.check_state WEB 分支：凭据构造改为读响应 Cookie
└── utils/
    └── _api.py                      # Api 新增"处理结果 + 响应 Cookie"请求方法（重试链路复用 request() 语义）

tests/
├── test_offline_login_v2.py         # 扩展：check_state 四状态判定、凭据构造、缺字段报错（monkeypatch）
└── test_offline_api_core.py         # 扩展：Api 新方法返回 cookies、fake client 驱动

scripts/
└── qrcode_login.py                  # 真机验收脚本：补轮询循环与凭据有效性校验输出

docs/modules/                        # doc_gen.py 重新生成（不手改）
```

**Structure Decision**: 单库结构（本仓库固有形态），改动集中于请求核心 `_api.py` 与登录模块 `login_v2.py` 两点，测试落在既有离线测试文件内扩展，不引入新目录。
