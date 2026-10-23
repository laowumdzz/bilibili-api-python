---
description: "Task list for feature 010-review-defect-fixes"
---

# Tasks: 评审缺陷修复

**Input**: Design documents from `/specs/010-review-defect-fixes/`

**Prerequisites**: plan.md、spec.md（五个用户故事 P1–P3）、research.md（D1–D8）、data-model.md、contracts/、quickstart.md

**Tests**: 规格明确要求（FR-007：每项修复 MUST 附离线回归测试；SC-001：用例须能区分修复前后）。每个故事采用"先写用例 → 验证缺陷态失败 → 实现 → 复跑通过"顺序。

**Organization**: 按用户故事分组（US1–US5 对应缺陷 1–5），每个故事独立可测、独立提交（宪法 V：一个提交只做一件事）。

## Format: `[ID] [P?] [Story] Description`

- **[P]**: 可并行（不同文件、无未完成依赖）
- **[Story]**: 所属用户故事（US1–US5）
- 描述含确切文件路径

## Path Conventions

单项目库结构：`bilibili_api/`（包根）、`scripts/`、`tests/`、`CHANGELOGS/` 均在仓库根。

---

## Phase 1: Setup（基线确认）

**Purpose**: 确认特性分支基线干净，后续失败可归因于本特性改动

- [x] T001 在特性分支 `010-review-defect-fixes` 上运行 `uv run pytest -m "not integration"` 与 `uv run python scripts/lint.py`，确认基线全绿（现状核查基于 HEAD `2e2fd63`，门禁应为绿；若基线已红先停下排查）

---

## Phase 2: Foundational（跨故事阻塞项）

**无跨故事阻塞项**。五项修复互不依赖：US1/US2/US3 同文件不同区域（`bilibili_api/utils/_api.py` + `tests/test_offline_api_core.py`，建议按序执行避免同文件冲突），US4/US5 完全独立（异常包 / 同步脚本），US4、US5 可与 US1–US3 并行推进。

---

## Phase 3: User Story 1 - 扫码登录轮询 dict 参数序列化 (Priority: P1) 🎯 MVP

**Goal**: 默认客户端下网页扫码登录轮询请求成功发出；统一请求准备层把"值为字典"的查询参数序列化为紧凑 JSON 字符串（FR-001 / FR-002）。

**Independent Test**: quickstart.md 第 1 节 US1 相关用例（含本地回环客户端编码边界用例）在缺陷态失败、修复后通过。

### Tests for User Story 1（先写，验证缺陷态失败）

- [x] T002 [US1] 在 `tests/test_offline_api_core.py` 新增统一层用例：构造含 dict 值查询参数的 `Api`，断言 `_prepare_request()` 输出中该参数为紧凑 JSON 字符串（`separators=(",", ":")`、非 ASCII 以 UTF-8 原文保留、无 Python repr 单引号形态）、标量与 bool→int 参数不受影响；在缺陷态运行确认失败
- [x] T003 [US1] 在 `tests/test_offline_login_v2.py` 新增本地回环用例（research.md D7）：`127.0.0.1` 随机端口起 aiohttp 服务器，monkeypatch `API["qrcode"]["web"]["get_events"]["url"]` 指向回环地址，驱动真实 `QrCodeLogin` 生成→轮询链路（凭据/网络均不出本机），断言服务端收到的查询参数全部为标量、`x-bili-locale-json` / `x-bili-device-req-json` 为合法紧凑 JSON 字符串；在缺陷态运行确认因客户端编码 `TypeError` 失败（服务端收不到请求）

### Implementation for User Story 1

- [x] T004 [US1] 在 `bilibili_api/utils/_api.py` 的 `_prepare_request()` params 归一化循环增加 dict 分支：`json.dumps(value, ensure_ascii=False, separators=(",", ":"))`，置于 bool 分支之后（bool→int 优先级不变）、None 剔除之前；序列化异常自然传播不吞掉；`bilibili_api/login_v2.py` 调用点保持 dict 字面量不动（research.md D1/D2）
- [x] T005 [US1] 复跑 T002/T003 用例通过，`uv run pytest tests/test_offline_api_core.py tests/test_offline_login_v2.py` 全绿后提交（`fix(utils): 请求准备统一层将 dict 值查询参数序列化为紧凑 JSON`）

**Checkpoint**: 扫码登录主链路修复完成，MVP 可交付（真机验收项见 quickstart.md 第 4 节，具备条件时补验）

---

## Phase 4: User Story 2 - 构造参数请求头保留 (Priority: P2)

**Goal**: 构造参数显式传入的自定义请求头原样送达，不再被 `__post_init__` 清空（FR-003）。

**Independent Test**: quickstart.md 第 1 节 US2 用例（请求准备边界断言头的名称与值原样保留）在缺陷态失败、修复后通过。

### Tests for User Story 2（先写，验证缺陷态失败）

- [x] T006 [US2] 在 `tests/test_offline_api_core.py` 新增请求头用例：构造 `Api(headers={...})` 后断言 `_prepare_request()` 输出中每个头的名称与值原样保留（含 `login_v2.py:646` 同形的 User-Agent / Referer 场景）；补回归断言——未传 headers 时仍回落全局 `HEADERS`、`update_headers` 整体替换语义不变；在缺陷态运行确认失败（值为空串）

### Implementation for User Story 2

- [x] T007 [US2] 在 `bilibili_api/utils/_api.py` 的 `__post_init__()` 中将 headers 占位清空（`dict.fromkeys(self.headers.keys(), "")`）改为值保留浅拷贝（`dict(self.headers)`）；data / params / files 占位清空不动（research.md D3）
- [x] T008 [US2] 复跑 T006 用例通过，`uv run pytest tests/test_offline_api_core.py` 全绿后提交（`fix(utils): Api 构造参数传入的请求头不再被占位清空`）

**Checkpoint**: 短信风控交换分支请求头修复完成

---

## Phase 5: User Story 3 - 请求体布尔值归位 (Priority: P2)

**Goal**: 请求体中的布尔值转为 0/1 后保留在请求体，不再错位写入查询参数（FR-004）。

**Independent Test**: quickstart.md 第 1 节 US3 用例（请求准备边界断言布尔字段位置）在缺陷态失败、修复后通过。

### Tests for User Story 3（先写，验证缺陷态失败）

- [x] T009 [US3] 在 `tests/test_offline_api_core.py` 新增请求体布尔用例：布尔与普通字段混合构造 `Api` 的 data，断言 `_prepare_request()` 输出中布尔字段以 0/1 保留在 data、params 不含该键；补回归断言——data 的 None 字段剔除、params 的 bool→int、`json_body=True` 整体序列化行为均不变；在缺陷态运行确认失败

### Implementation for User Story 3

- [x] T010 [US3] 在 `bilibili_api/utils/_api.py` 的 `_prepare_request()` data 归一化循环中，布尔分支写入目标由 `new_params[key]` 改为 `new_data[key]`（单行修正，research.md D4）
- [x] T011 [US3] 复跑 T009 用例通过，`uv run pytest tests/test_offline_api_core.py` 全绿后提交（`fix(utils): 请求体布尔值转为 0/1 后保留在请求体而非查询参数`）

**Checkpoint**: 公开调用链潜伏缺陷修复完成

---

## Phase 6: User Story 4 - 异常子模块导入路径恢复 (Priority: P2)

**Goal**: 恢复 17 个按类异常子模块导入路径（薄兼容层，仅 re-export），包级导入面不变，CHANGELOGS 留痕（FR-005）。

**Independent Test**: quickstart.md 第 1 节 US4 用例（22 条历史路径逐一导入、`is` 同一、`__all__` 不变）通过。

### Implementation for User Story 4

- [x] T012 [P] [US4] 在 `bilibili_api/exceptions/` 新增 17 个薄兼容模块（与既有 5 个真实模块同层平铺，不用 compat/ 子目录——plan.md Structure Decision）：`ArgsException.py`、`CredentialNoAcTimeValueException.py`、`CredentialNoBiliJctException.py`、`CredentialNoBuvid3Exception.py`、`CredentialNoBuvid4Exception.py`、`CredentialNoDedeUserIDException.py`、`CredentialNoSessdataException.py`、`DanmakuClosedException.py`、`DynamicExceedImagesException.py`、`GeetestException.py`、`InitialStateException.py`、`LiveException.py`、`LoginError.py`、`ResponseException.py`、`StatementException.py`、`VideoUploadException.py`、`WbiRetryTimesExceedException.py`；每个模块仅含说明性中文 docstring（历史承载类定义、重构后仅 re-export 同一类对象）+ `from ._simple import <Name> as <Name>` + `__all__ = ["<Name>"]`（data-model.md 实体 2 结构）；`__init__.py` 与 `_simple.py` 零改动
- [x] T013 [US4] 新增 `tests/test_offline_exceptions_compat.py`：以 `importlib.import_module` 逐一导入 data-model.md 实体 2 的全部 22 条历史子模块路径，断言导入成功、模块内类与包级导出 `is` 同一、`bilibili_api.exceptions.__all__` 集合与修复前完全一致（22 项）；运行确认通过
- [x] T014 [P] [US4] 在 `CHANGELOGS/UNRELEASED.md` 增加兼容性恢复条目：说明恢复了哪 17 个导入路径、背景（重构并入 `_simple.py` 造成未告知的兼容破坏）、薄兼容层语义（仅 re-export，未来如需废弃须另行裁决）（contracts/exception-import-paths.md 变更记录义务）
- [x] T015 [US4] `uv run pytest tests/test_offline_exceptions_compat.py` 通过且 `uv run python scripts/lint.py` 全绿（重点确认 pyrefly 对 17 个新模块零报错、`docs/modules/` 零漂移——research.md D5 已实证无文档影响）后提交（`fix(exceptions): 恢复 17 个按类异常子模块导入路径兼容层`）

**Checkpoint**: 下游按子模块路径导入异常类不再断裂

---

## Phase 7: User Story 5 - registry 同步类别映射补齐与兜底 (Priority: P3)

**Goal**: `CATEGORY_FILE` 补 `broadcast` / `cheese` / `opus` 三类别；未映射类别"跳过 + 按类别聚合告警"不再 `KeyError`（FR-006）。

**Independent Test**: quickstart.md 第 1 节 US5 用例（tmp fixture registry：未映射跳过告警、三类别落位）通过；第 3 节真实 registry dry-run 计数与修复前语义一致（609 已存在、0 新增、0 无映射跳过）。

### Implementation for User Story 5

- [x] T016 [US5] 在 `scripts/sync_api_registry.py` 的 `CATEGORY_FILE` 按字母序补三项映射：`"broadcast": "broadcast"`、`"cheese": "cheese"`、`"opus": "opus"`（cheese / opus 落既有 `bilibili_api/data/api/` 文件，broadcast 无既有文件时经同步惰性新建——本任务不创建 `broadcast.json`）
- [x] T017 [US5] 在 `scripts/sync_api_registry.py` 的 `main()` 主循环 `known_urls` / `used_urls` 检查之后、`resolve_target()` 之前增加类别可解析检查（类别在 `CATEGORY_FILE` 命中或 `(类别, 子主题)` 在 `SUBTOPIC_OVERRIDES` 命中），不可解析时按类别聚合计数并跳过；循环后对每个未映射类别输出 `logger.warning`（含类别名与条目数）；汇总 info 行增加"无映射跳过"计数，与"已存在跳过"可区分（research.md D6 / data-model.md 实体 3 状态机）
- [x] T018 [US5] 新增 `tests/test_offline_sync_api_registry.py`：以 `importlib.util.spec_from_file_location` 按文件路径加载 `scripts/sync_api_registry.py`，monkeypatch 其 `REGISTRY_DIR` / `API_DIR` 模块常量指向 tmp fixture——用例覆盖：未映射虚构类别条目被跳过且 `caplog` 捕获含类别名与条目数的 warning（进程不崩溃）；`broadcast` / `cheese` / `opus` 三类别解析到正确目标文件（broadcast 走新建文件路径）；已存在 URL 条目依旧跳过；dry-run 不写任何文件
- [x] T019 [US5] `uv run pytest tests/test_offline_sync_api_registry.py` 通过；对本机真实 registry 跑 `uv run python scripts/sync_api_registry.py --dry-run`，确认计数与修复前语义一致（609 已存在、0 新增、0 无映射跳过、无 WARNING、不产生 `broadcast.json`，SC-004 修订口径）后提交（`fix(scripts): 同步脚本补齐 broadcast/cheese/opus 类别映射并兜底未映射类别告警`）

**Checkpoint**: 同步脚本对未来 registry 新类别稳健

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: 全量验证与收口

- [x] T020 运行 `uv run python scripts/lint.py` 全量门禁（ruff / 阻断检查 / pyrefly 零容忍 / 棘轮 / 文档漂移）确认全绿（SC-002）
- [x] T021 运行 `uv run pytest -m "not integration"` 离线全量零失败（SC-002）
- [x] T022 运行 `uv run --with "mypy==1.18.2" python scripts/doc_gen.py` 重生成并确认 `docs/modules/` 零漂移（宪法 III；预期无变化——本特性不改公共 docstring，兼容模块不进文档，research.md D5）
- [x] T023 按 `specs/010-review-defect-fixes/quickstart.md` 完整走查第 1–3 节并勾选完成判据；第 4 节真机扫码项（SC-001）不具备条件时登记为待补验，不阻塞特性收口（spec Assumptions）

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1（基线）**: 无依赖，立即开始；T001 红则停止排查
- **Phase 2**: 无 foundational 任务，直接进入故事阶段
- **US1–US5**: 逻辑上互不依赖，均可在基线后开始；但 **US1/US2/US3 共享 `bilibili_api/utils/_api.py` 与 `tests/test_offline_api_core.py`，必须按序执行**（US1 → US2 → US3，同文件避免冲突）；**US4 / US5 与 US1–US3 无共享文件，可并行推进**
- **Phase 8**: 依赖全部所需故事完成

### User Story Dependencies

- **US1 (P1)**: 无依赖 — MVP
- **US2 (P2)**: 建议在 US1 后（同文件）；独立语义上无依赖
- **US3 (P2)**: 建议在 US2 后（同文件）；独立语义上无依赖
- **US4 (P2)**: 无共享文件，可随时并行
- **US5 (P3)**: 无共享文件，可随时并行

### Within Each User Story

- 测试先行：先写用例并在缺陷态验证失败（SC-001 区分力要求）
- 实现 → 复跑用例 → 门禁相关子集 → 提交（每故事恰好一个提交）

### Parallel Opportunities

- US4（T012–T015）与 US5（T016–T019）整体可并行，也可与 US1–US3 并行
- T012 与 T014 不同文件可并行（T013 依赖 T012 完成后运行才有干净的通过态）

---

## Parallel Example: US4 + US5 与 US1–US3 并行

```bash
# 开发者/会话 A（按序）：
Task T002-T005 (US1, _api.py + 测试)
Task T006-T008 (US2, 同文件)
Task T009-T011 (US3, 同文件)

# 开发者/会话 B（独立文件，可并行）：
Task T012-T015 (US4, exceptions/ + CHANGELOGS)
Task T016-T019 (US5, scripts/ + 新测试)
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. T001 基线确认
2. T002–T005 完成扫码登录主链路修复（P1，唯一"完全性故障"）
3. **STOP and VALIDATE**: quickstart 第 1 节 US1 用例 + 真机扫码（具备条件时）

### Incremental Delivery

1. 基线 → US1（主链路，MVP）→ US2 → US3（同文件按序）→ US4 / US5（可穿插并行）→ Phase 8 收口
2. 每个故事独立提交、独立可测，任意中途停下均已交付完整修复

---

## Notes

- [P] 任务 = 不同文件且无未完成依赖；US1–US3 因同文件不标 [P]
- US1–US5 对应 spec 缺陷 1–5；FR 映射：US1→FR-001/002、US2→FR-003、US3→FR-004、US4→FR-005、US5→FR-006，测试要求见 FR-007
- 本地回环测试（T003）属离线边界：127.0.0.1 本机通信、零凭据、零账号状态（research.md D7 / contracts/request-preparation.md）
- 提交信息遵循 Conventional Commits（Git Hook 校验）；不主动 push

---

## Implementation Record（2026-10-23，T024 补录 2026-10-24）

全部任务 T001–T024 完成并勾选。本地 `main` 提交（不 push）：

| 提交 | 内容 |
|------|------|
| `0cda11a` | `fix(utils)`: T002–T005 请求准备统一层 dict 值查询参数序列化为紧凑 JSON（US1） |
| `1c0187a` | `fix(utils)`: T006–T008 构造参数请求头不再被占位清空（US2） |
| `d2b9e90` | `fix(utils)`: T009–T011 请求体布尔值 0/1 保留在请求体（US3） |
| `acedca0` | `fix(test)`: T002/T003 衍生修复——回环用例结束后按当前循环清理全局会话池条目，消除对会话池生命周期回归的跨用例污染 |
| `634a4bf` | `fix(exceptions)`: T012–T015 恢复 17 个按类异常子模块导入路径兼容层（US4） |
| `e4ab653` | `fix(scripts)`: T016–T019 同步脚本补齐 broadcast/cheese/opus 映射并兜底未映射类别告警（US5） |
| `f9f7efc` | `docs(010)`: 特性 010 规格设计文档入库并勾选 T001–T023 |
| `154c8fb` | `docs`: T024 宪法 v1.2.1 修订入库（离线用例外网边界与本机回环例外澄清） |
| `30874e8` | `docs`: T024 AGENTS.md 离线用例边界对齐宪法 v1.2.1（紧随宪法修订独立提交，沿 v1.2.0 先例） |

### 与任务文本的偏差（已核验必要）

1. **T001 分支口径**：任务文本要求"特性分支 `010-review-defect-fixes`"，按本仓库既有工作流（本地 `main` 直提、无 dev/特性分支）在 `main` HEAD `3de2bf6` 执行基线核查，基线全绿。
2. **T012 `__init__.py` 零改动**：任务预设 17 个薄兼容模块即可满足不变式，但实证发现——包初始化不加载子模块时，后经 `importlib` 加载的同名子模块会被导入机制重绑定到包属性，同进程内"先子模块路径、后包级"的导入序列将得到模块对象而使 `except` 精确捕获失效（历史首次提交因 `__init__` 直接从同名子模块导入而无此问题）。故将 `__init__.py` 中 17 个类改为经各自薄子模块导入（包级导入面与 `__all__` 集合不变），系满足 FR-005 行为要求的必要调整。
3. **T023 第 4 节真机项**：本会话无扫码环境，已按 spec Assumptions 登记为待补验（见 quickstart.md 完成判据），不阻塞收口。

### 终态验证

- `uv run pytest -m "not integration"`：345 passed / 1 skipped，零失败。
- `uv run python scripts/lint.py`：ruff / 阻断检查 / pyrefly 零容忍 / 棘轮 / 文档漂移全绿。
- `uv run --with "mypy==1.18.2" python scripts/doc_gen.py`：`docs/modules/` 零漂移（17 个兼容模块不进文档）。
- 真实 registry `--dry-run`：609 已存在 / 0 重复 / 0 无映射跳过 / 0 新增，无 WARNING，无 `broadcast.json`。

---

## Phase 9: Convergence

- [x] T024 以独立提交入库宪法 v1.2.1 修订与 AGENTS.md 离线边界对齐（提交信息 `docs: amend constitution to v1.2.1 ...`，正文说明离线用例"禁止网络请求"澄清为"禁止外网请求"及本机回环例外；AGENTS.md 对齐可并入该笔或紧随其后独立提交）per spec Clarifications Session 2026-10-23 C1 裁决 / Constitution Governance (partial)
