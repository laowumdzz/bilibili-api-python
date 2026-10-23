# Implementation Plan: 评审缺陷修复

**Branch**: `010-review-defect-fixes` | **Date**: 2026-10-23 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/010-review-defect-fixes/spec.md`

## Summary

一次收口修复 2026-10-23 全量代码评审发现的五项缺陷：(1) 扫码登录轮询 dict 参数在默认 aiohttp 客户端编码阶段抛 TypeError——在请求准备统一层把"值为字典"的查询参数序列化为紧凑 JSON 字符串；(2) 构造参数传入的自定义请求头被 `__post_init__` 清空为空串——改为保留原值；(3) 请求体布尔值错位写入查询参数——单行修正落入 `new_data`；(4) 17 个按类异常子模块导入路径断裂——恢复薄兼容模块（仅 re-export）并在 CHANGELOGS 留痕；(5) registry 同步类别映射缺 `broadcast` / `cheese` / `opus`——补齐映射并为未映射类别增加"跳过 + 告警"兜底。每项修复附离线回归测试，扫码轮询用例在客户端编码边界（本地回环服务器）断言实际外发查询参数。

## Technical Context

**Language/Version**: Python ≥ 3.10（MUST 兼容 CPython 3.10，禁用更高版本独有特性）

**Primary Dependencies**: aiohttp（默认客户端，运行时硬依赖）、httpx（可选客户端）；测试 pytest。无新增依赖。

**Storage**: N/A（纯库代码修复；`bilibili_api/data/api/*.json` 为声明式接口定义，本特性仅扩展同步脚本映射表，不手工编辑接口定义）

**Testing**: pytest 分层体系；本特性全部新增用例为离线层（`tests/test_offline_*.py`，不触外网、不用凭据、不改账号状态）。本地回环（`127.0.0.1` 随机端口）测试服务器属本机进程间通信，不离开本机。门禁 `uv run python scripts/lint.py` 全绿。

**Target Platform**: 跨平台 Python 异步库（下游 aiohttp / httpx 环境）

**Project Type**: library（B 站 API 异步封装库）

**Performance Goals**: N/A（正确性修复；参数序列化仅在值为字典时触发，标量参数路径零额外开销）

**Constraints**:
- 宪法 I：修复均在既有异步链路内，不新增同步阻塞。
- 宪法 II：不手工编辑 `data/api/*.json`；`broadcast.json` 仅在 registry 出现待同步新条目时经同步脚本惰性新建。
- 宪法 III：类型零容忍；公共函数完整中文 docstring；`doc_gen` 重生成（已实证：`exceptions/` 子模块位于 mypy 缓存子目录，doc_gen 顶层清单不遍历，17 个兼容模块不产生文档漂移）。
- 宪法 IV：新用例全部离线；真机验收走既有 cred 分层与登录脚本，无凭据环境以离线用例为完成判据。
- 宪法 V：异常子模块路径恢复即兼容性修复；`__post_init__` 请求头"清空→保留"是修复 FR-003 既定契约，非破坏性变更；提交遵循 Conventional Commits 且每项缺陷独立提交。

**Scale/Scope**: 源码改动 2 个文件（`bilibili_api/utils/_api.py`、`scripts/sync_api_registry.py`；`bilibili_api/login_v2.py` 无需改动——扫码轮询修复位于统一层，调用点参数保持 dict 形态）+ 新增 17 个异常兼容模块 + CHANGELOGS 留痕 + 4 组离线回归测试。

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| 宪章条款 | 状态 | 说明 |
|----------|------|------|
| I. 异步优先 | ✅ 通过 | 全部修复位于既有 `async` 请求准备链路与模块层；无 `asyncio.run()`、无同步阻塞、不经客户端抽象层新增直连 |
| II. 声明式 API 定义 | ✅ 通过 | 不新增接口定义；扫码轮询两个结构化参数已在既有 `login.json` 定义外以调用点参数传入，修复仅改编码形态；同步脚本映射表扩展符合 registry 单一事实源流程 |
| III. 质量门禁 | ✅ 通过 | `scripts/lint.py` 全绿为目标（SC-002）；类型零豁免；兼容模块不触发文档漂移（已实证 mypy 缓存目录形态） |
| IV. 分层测试 | ✅ 通过 | 全部新用例离线（本地回环不离开本机、零凭据、零账号状态；宪法 v1.2.1 已明确本机回环不视为网络请求）；真机项走既有 cred 分层与 `login_and_cache.py`，不在 CI |
| V. 兼容性与破坏性变更控制 | ✅ 通过 | 异常路径恢复为兼容性修复；请求头保留与请求体布尔归位均为修复公开契约（FR-003 / FR-004）；CHANGELOGS/UNRELEASED.md 留痕（FR-005）；一提交一事 |

**Phase 1 复评**：设计产物（research.md D1–D8、data-model.md、contracts/、quickstart.md）未引入任何宪章冲突；离线边界的"本地回环"解释已在 contracts/request-preparation.md 与 quickstart.md 中固化，并经宪法 v1.2.1 PATCH 修订（2026-10-23）正式明确。门禁维持全通过。

## Project Structure

### Documentation (this feature)

```text
specs/010-review-defect-fixes/
├── plan.md              # 本文件（$speckit-plan 输出）
├── research.md          # Phase 0 输出：8 项决策与备选方案
├── data-model.md        # Phase 1 输出：请求准备归一化规则 / 异常路径映射 / 类别映射
├── quickstart.md        # Phase 1 输出：分层验收步骤
├── contracts/
│   ├── request-preparation.md   # Api 请求准备行为契约（params/data/headers）
│   ├── exception-import-paths.md # 异常导入路径兼容契约（22 路径）
│   └── registry-sync.md         # 同步脚本 CLI 契约（退出码/输出/类别行为）
└── tasks.md             # Phase 2 输出（$speckit-tasks，本命令不创建）
```

### Source Code (repository root)

```text
bilibili_api/
├── utils/
│   └── _api.py                     # D1/D3/D4：_prepare_request 统一层修复
│     # - D1: params 归一化循环中 dict 值 → 紧凑 JSON 字符串
│     # - D3: __post_init__ 请求头占位清空 → 保留原值（copy）
│     # - D4: data 布尔值 → new_data（原错写 new_params）
├── exceptions/
│   ├── _simple.py                  # 不改动（类定义所在）
│   ├── ArgsException.py           # D5：新增 17 个薄兼容模块之一
│   ├── ...（其余 16 个，清单见 data-model.md）
│   └── __init__.py                 # 不改动（包级导出面保持不变）
└── data/api/
    ├── cheese.json                 # 既有文件（映射目标，本特性不改内容）
    ├── opus.json                   # 既有文件（映射目标，本特性不改内容）
    └── broadcast.json              # 不在本特性创建（registry 出现新条目时经同步惰性新建）

scripts/
└── sync_api_registry.py            # D6：CATEGORY_FILE 补三类别 + 未映射类别跳过告警

CHANGELOGS/
└── UNRELEASED.md                   # D5：异常导入路径恢复留痕

tests/
├── test_offline_api_core.py        # 扩展：params 序列化 / headers 保留 / data 布尔归位
├── test_offline_login_v2.py        # 扩展：扫码轮询本地回环客户端编码边界用例
├── test_offline_exceptions_compat.py # 新增：22 条历史导入路径逐一验证
└── test_offline_sync_api_registry.py # 新增：类别映射 / 未映射兜底 / 预览不变性
```

**Structure Decision**: 单项目库结构（仓库根即包根）。本特性不新建任何目录层级；改动集中在请求准备统一层（`bilibili_api/utils/_api.py`）、异常包（补 17 个平铺兼容模块，与既有 5 个真实模块同层）、同步脚本与离线测试。不采用 `exceptions/compat/` 子目录——历史上按类模块本就平铺于 `exceptions/` 下，子目录会改变导入路径语义。

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

无违反项，不适用。
