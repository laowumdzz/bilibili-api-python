# Implementation Plan: 移除 CurlCFFI 客户端适配

**Branch**: `009-remove-curlcffi-client` | **Date**: 2026-10-11 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/009-remove-curlcffi-client/spec.md`

**Note**: 本项目维护者既有实践为本地 `main` 直提交（宪法开发工作流第 1 条允许维护性直提交）；Branch 字段仅承载特性目录标识，不强制切分支。

## Summary

将 CurlCFFI 从库的内置请求客户端适配中整体移除（干净移除，无报错桩，不设废弃过渡期）：删除适配实现与自动选择链登记，自动选择回落为 aiohttp > httpx（aiohttp 为运行时硬依赖，正常安装路径下恒有可用内置客户端）；同步清理开发依赖声明与锁文件、离线测试中的 curl 用例并新增 FR-007 要求的三场景离线覆盖、全部面向用户文档与治理文本中的"可用选项"表述；错误信息按 FR-003/FR-009 更新；宪法原则 I 的优先级链描述按修订程序以独立提交同步。移除的是内置适配，自定义客户端注册机制（含注册同名实现）不变。

## Technical Context

**Language/Version**: Python ≥ 3.10（CPython 3.10 兼容，不引入更高版本特性）；当前版本 19.2.2（`bilibili_api/__init__.py` `BILIBILI_API_VERSION`）

**Primary Dependencies**: 无新增依赖。移除对象：dev 组 `curl-cffi>=0.16.3`（`pyproject.toml`）与 `requirements.txt` 的 `curl_cffi>=0.8.1`；运行时依赖 `[project.dependencies]` 从未包含 curl-cffi（`aiohttp>=3.9` 为唯一硬性 HTTP 客户端依赖，保证内置客户端恒可用）

**Storage**: N/A（不涉及数据存储）

**Testing**: pytest（离线 `tests/test_offline_*.py` 无凭据；集成由 conftest 自动分层）；本特性改造 2 个既有离线文件 + 新增 1 个离线文件；验收含 `uv run python scripts/lint.py` 全量门禁（末尾文档漂移校验会拦截 `docs/modules/client.md` 未重生成）

**Target Platform**: 纯 Python 库（Windows / Linux / macOS；PyInstaller hook 存在但不涉及客户端清单）

**Project Type**: library

**Performance Goals**: N/A（纯移除；剩余客户端行为语义不变）

**Constraints**: 干净移除不留报错桩（澄清裁决）；历史 CHANGELOG（v17/v18）、`REFACTORING.spec.md`、既往 specs 归档不回改；错误提示不得残留 curl_cffi 安装指引；`uv.lock` 不手改（随 `uv sync` 再生）

**Scale/Scope**: 合计 21 处触点（库代码 4：1 删除 3 编辑；依赖 3：pyproject / requirements 编辑 + uv.lock 再生；测试 4：3 改 1 增；用户文档 8：README、docs/README、request_client、configuration、audio、troubleshooting 编辑 + CHANGELOGS 新节 + docs/modules/client.md 重生成；治理 2：AGENTS、宪法修订），明细以 [data-model.md](./data-model.md) 为权威口径

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| 宪章原则 | 评估 | 结论 |
|---|---|---|
| I. 异步优先 | 全部改动发生在 `BiliAPIClient` 抽象层内部（clients 包与 `_session.py`），不绕过抽象层；剩余优先级 aiohttp > httpx 保持相对顺序；aiohttp 为硬性运行时依赖，库恒有内置客户端可用，"尚未安装"错误路径保留 | ✅ 通过 |
| II. 声明式 API 定义 | 不触碰 `data/api/*.json` 与 API 调用链路 | ✅ N/A |
| III. 质量门禁 | 实现后必须 `uv run python scripts/lint.py` 全绿；删除 `CurlCFFIClient.py` 会改变生成页 `docs/modules/client.md`，必须重跑 `scripts/doc_gen.py` 并入库（漂移校验兜底）；不新增公共函数则无 docstring 义务，`select_client` 错误信息增强不改签名 | ✅ 通过（附 doc_gen 重生成义务） |
| IV. 分层测试 | 仅动离线测试（无网络、无凭据）：删 curl 用例 + 新增 FR-007 三场景；新增文件遵守离线红线（可经 importlib/模块表注入模拟，不发真实请求）；readonly/集成子集不受影响 | ✅ 通过 |
| V. 兼容性与破坏性变更 | 本特性即破坏性变更，按规范以 `BREAKING CHANGE` footer 标注并更新变更记录（FR-008）；剩余客户端接口零变更；版本号递增由发布流程决定（spec 范围外）；错误信息增强仅追加内容不改既有异常类型（`ArgsException`） | ✅ 通过（BREAKING CHANGE 标注义务） |
| 凭据安全红线 | 不涉及凭据 | ✅ N/A |
| 反爬集中管理 | 不触碰 `utils/_api.py` / `utils/_anti_spider.py`（其 `get_client()` 调用经抽象层自动获得新选择结果） | ✅ N/A |

**无违规项，无需 Complexity Tracking 表。**（Phase 1 复检：设计未引入新违规，结论不变。）

## Project Structure

### Documentation (this feature)

```text
specs/009-remove-curlcffi-client/
├── plan.md                        # 本文件 ($speckit-plan command output)
├── research.md                    # Phase 0：机制分析与决策记录 ($speckit-plan)
├── data-model.md                  # Phase 1：移除足迹清单模型（触点 → 现状 → 目标态）($speckit-plan)
├── quickstart.md                  # Phase 1：验收实操指南 ($speckit-plan)
├── contracts/
│   └── client-selection.md        # Phase 1：移除后的客户端选择公共契约 ($speckit-plan)
└── tasks.md                       # Phase 2 output ($speckit-tasks - NOT created by $speckit-plan)
```

### Source Code (repository root)

```text
bilibili_api/
├── clients/
│   ├── CurlCFFIClient.py          # 删除（适配实现，干净移除）
│   └── __init__.py                # 编辑：ALL_PROVIDED_CLIENTS 移除 curl 条目
├── utils/
│   └── _session.py                # 编辑：3 处"尚未安装"提示文本改为 (aiohttp|httpx)；
│                                  #   select_client 未注册消息增强（列出已注册客户端）
└── __init__.py                    # 不改：__register_all_clients 倒序注册机制自动适应清单缩短
docs/
├── modules/client.md              # 重生成（doc_gen 产物，随 CurlCFFIClient 删除自动缩减）
├── README.md                      # 编辑：安装/优先级/示例/impersonate 段
├── request_client.md              # 编辑：对比表删 curl 行；自定义客户端教程重写语境
├── configuration.md               # 编辑：设置支持表删 curl 列
└── examples/audio.md              # 编辑：示例改用 aiohttp/httpx
README.md                          # 编辑：与 docs/README.md 镜像内容同步
.github/ISSUE_TEMPLATE/troubleshooting.md  # 编辑：请求库候选项删 curl_cffi
tests/
├── conftest.py                    # 编辑：请求计数器包装清单删 curl 项（含 docstring"三个"→"两个"）
├── test_offline_client_timeout_semantics.py  # 编辑：删 TestCurlCFFIClientTimeout 与 curl 注记
├── test_offline_ws_handle_leak.py # 编辑：删 curl 四用例 / FakeCurlWs / make_bare_curl_client / HAS_CURL_CFFI
└── test_offline_client_selection.py  # 新增：FR-007 三场景离线覆盖
pyproject.toml                     # 编辑：dev 组删 curl-cffi
requirements.txt                   # 编辑：删 curl_cffi 行
uv.lock                            # 再生（uv sync，不手改；curl-cffi 无其他引用方，将整条消失）
AGENTS.md                          # 编辑：概览/结构树/优先级/uv sync 清单/陷阱/依赖表 5 处
.specify/memory/constitution.md    # 修订：原则 I 优先级链描述（独立提交，v1.0.1 → v1.0.2）
CHANGELOGS/                        # 新增本期条目（v19.2.2 之后的新版节，历史文件不回改）
```

**Structure Decision**: 移除型特性，无新增源码目录；触点收敛于 clients 包、_session 错误文本、离线测试与文档/治理文本。`bilibili_api/__init__.py` 的 `__register_all_clients()` 为数据驱动的倒序注册机制，清单缩短后自动适应，无需改动。历史记录类文件（CHANGELOGS/v17、v18，REFACTORING.spec.md，specs/001/002/005/008 归档）按 spec FR-006 豁免不回改。

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

无违规项，本表留空。
