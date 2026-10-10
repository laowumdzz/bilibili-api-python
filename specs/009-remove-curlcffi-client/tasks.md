# Tasks: 移除 CurlCFFI 客户端适配

**Input**: Design documents from `/specs/009-remove-curlcffi-client/`

**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/client-selection.md, quickstart.md

**Tests**: 包含测试任务——spec FR-007 显式要求离线三场景覆盖（新增 `tests/test_offline_client_selection.py`），并要求清理既有 curl 用例。测试先行的任务以"红 → 实现 → 绿"标注。

**Organization**: 任务按用户故事分组（US1 无感自动回退 / US2 迁移指引 / US3 一致性收尾），每个故事可独立实现与验证。提交策略遵循 research.md R6 的三笔拆分（refactor! / docs / 宪法修订），各提交任务已标注归属。

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- 单项目布局：库源码 `bilibili_api/`、测试 `tests/`、文档 `docs/`（`docs/modules/` 为 doc_gen 生成域，禁止手编）、规格 `specs/009-remove-curlcffi-client/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: 建立改造前基线，确保后续"红/绿"判定有可信参照

- [x] T001 运行 `uv sync` 与 `uv run pytest -m "not integration"` 确认当前全绿，记录通过用例数与 curl 相关用例数（timeout 语义 4 例 + WS 泄漏 4 例）作为基线，写入本任务完成说明

**Checkpoint**: 基线全绿，改造起点可信

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: 本特性为移除型改造，无共享前置基础设施

无任务——`bilibili_api/__init__.py` 的 `__register_all_clients()` 为数据驱动机制（research.md R1），清单缩短后自动适应，不需要任何铺垫性改动。用户故事可直接开始。

---

## Phase 3: User Story 1 - 未显式选择客户端的用户无感继续使用 (Priority: P1) 🎯 MVP

**Goal**: 删除 CurlCFFI 适配与自动选择链登记，自动选择回落为 aiohttp > httpx；依赖声明清理；既有离线测试去 curl 化；FR-007 场景①②离线覆盖

**Independent Test**: `uv run pytest tests/test_offline_client_selection.py` 场景①②通过 + 离线全量绿 + `uv run python -c` 抽查默认选中 `aiohttp`（quickstart.md §2/§3）

### Tests for User Story 1 ⚠️ 先写先红

- [x] T002 [US1] 编写 `tests/test_offline_client_selection.py` 场景①②并运行确认失败（红）：①清单契约——`ALL_PROVIDED_CLIENTS` 恰为 aiohttp、httpx 两项且 aiohttp 在前、不含 curl（依 contracts/client-selection.md §1），并以打桩模拟 curl_cffi 第三方库可导入、断言其不触发任何注册或选择（spec 边界"已装但不探测"，data-model C5）；②回退与默认选择——以 importlib 打桩模拟第三方库可/不可导入，验证倒序注册后默认选中 aiohttp、aiohttp 缺失回退 httpx、全部缺失时 `get_client()` 抛 `ArgsException` 且消息含 `(aiohttp|httpx)`（现文本含 curl_cffi，必红）

### Implementation for User Story 1

- [x] T003 [US1] 编辑 `bilibili_api/clients/__init__.py`：`ALL_PROVIDED_CLIENTS` 移除 curl_cffi 条目（保留 aiohttp `{chunk_size: 262144}` 与 httpx `{http2: False, chunk_size: 262144}`；先改清单再删文件，避免 `__register_all_clients` 对已删适配模块的二次导入炸裂，research.md R1）
- [x] T004 [US1] 删除 `bilibili_api/clients/CurlCFFIClient.py`（干净移除，无报错桩——澄清裁决；删除后导入该模块应为标准 `ModuleNotFoundError`）
- [x] T005 [US1] 编辑 `bilibili_api/utils/_session.py`：`get_selected_client()` / `get_available_settings()` / `get_client()` 三处"尚未安装"提示文本 `$ pip3 install (curl_cffi|httpx|aiohttp)` 统一改为 `$ pip3 install (aiohttp|httpx)`（contracts §3.2，文案为契约）
- [x] T006 [P] [US1] 编辑 `tests/conftest.py` `_install_request_counter()`：包装清单移除 `("bilibili_api.clients.CurlCFFIClient", "CurlCFFIClient")` 项，docstring"对三个内置客户端"改"对两个内置客户端"（data-model T1）
- [x] T007 [P] [US1] 编辑 `tests/test_offline_client_timeout_semantics.py`：删除 `TestCurlCFFIClientTimeout` 类、`CurlCFFIClient` 顶层导入、`CURL_CFFI_INFINITE` 常量与模块 docstring 中 curl_cffi 归一化注记（含 2026-08-29 实测背景行）；aiohttp / httpx 用例与断言全部保留（data-model T2）
- [x] T008 [P] [US1] 编辑 `tests/test_offline_ws_handle_leak.py`：删除 `HAS_CURL_CFFI` 探测块、`FakeCurlWs`、`make_bare_curl_client()` 与 4 个 `skipif(not HAS_CURL_CFFI)` 用例；aiohttp 4 用例保留（data-model T3）
- [x] T009 [US1] 编辑 `pyproject.toml` dev 组删除 `curl-cffi>=0.16.3`、`requirements.txt` 删除 `curl_cffi>=0.8.1` 行，随后 `uv sync` 再生 `uv.lock`（不手改锁文件）；验证 `uv pip list | grep -i curl` 无输出（research.md R3）
- [x] T010 [US1] 运行 `uv run python scripts/doc_gen.py` 重生成 `docs/modules/client.md`，确认 CurlCFFIClient 段消失（生成域文件随源码自动缩减，禁止手编）
- [x] T011 [US1] 验证转绿：`uv run pytest -m "not integration"` 全绿（T002 场景①②通过、既有 aiohttp/httpx 用例数与基线一致）+ `uv run python -c` 抽查默认选中 `aiohttp`、`get_registered_clients()` 为 aiohttp/httpx（quickstart §3 前两断言）

**Checkpoint**: User Story 1 独立达成——未显式选择的下游自动改用 aiohttp，离线全量绿，环境无 curl-cffi。**此检查点不提交**（提交在 US2 完成后按 research R6 合并为一笔 refactor!）。

---

## Phase 4: User Story 2 - 曾显式使用 CurlCFFI 的用户获得清晰迁移指引 (Priority: P2)

**Goal**: 按名称选择未注册客户端时报错列出已注册清单（FR-003）；干净移除与同名自定义注册的回归锚定（FR-005）；完成 refactor! 主提交（FR-008）

**Independent Test**: `uv run pytest tests/test_offline_client_selection.py` 场景③通过 + `select_client("curl_cffi")` 报错文案与 contracts §3.1 逐字一致

### Tests for User Story 2 ⚠️ 先写先红

- [x] T012 [US2] 向 `tests/test_offline_client_selection.py` 追加场景③并运行确认消息断言失败（红）：a) 干净移除回归——`importlib.import_module("bilibili_api.clients.CurlCFFIClient")` 抛 `ModuleNotFoundError`（T004 后即绿，作永久锚）；b) 迁移指引——`select_client("curl_cffi")` 抛 `ArgsException` 且消息含 `当前已注册的客户端：aiohttp, httpx`（现消息无清单，必红；断言顺序为字典序，与契约 §3.1 排序规则一致）；c) 同名自定义注册——`register_client("curl_cffi", <BiliAPIClient stub>)` 后 `select_client("curl_cffi")` 正常选中、用例结束 `unregister_client("curl_cffi")` 还原（FR-005；注意还原后重选回 aiohttp，避免污染后续用例）

### Implementation for User Story 2

- [x] T013 [US2] 编辑 `bilibili_api/utils/_session.py` `select_client()`：未注册消息增强为 `未注册过 {name}。当前已注册的客户端：{", ".join(sorted(sessions.keys()))}（或通过 register_client() 注册自定义客户端）。`，清单按字典序排序输出（确定性消息、不依赖注册顺序）；`sessions` 为空时退化为既有"尚未安装"文本；异常类型保持 `ArgsException`，签名不变（research.md R2 文案即契约，contracts §3.1）
- [x] T014 [US2] 验证并完成主提交：`uv run pytest tests/test_offline_client_selection.py` 全绿（T012 转绿）后，将库代码（`bilibili_api/clients/`、`bilibili_api/utils/_session.py`）、依赖（`pyproject.toml`、`requirements.txt`、`uv.lock`）、测试（`tests/` 四文件）与重生成页 `docs/modules/client.md` 以 `refactor!: 移除 CurlCFFI 客户端适配` 提交，BREAKING CHANGE footer 载明影响面与迁移方式（改用 aiohttp/httpx，或 register_client 自行接入；FR-008，research R6 提交①；Conventional Commits hook 强制校验格式）

**Checkpoint**: User Stories 1 AND 2 独立达成——运行时行为（回退 + 报错指引）完整落地，refactor! 主提交入库。

---

## Phase 5: User Story 3 - 维护者获得一处不留残留的一致性收尾 (Priority: P3)

**Goal**: 用户文档、门面与治理文本与库实态一致（FR-006）；变更记录承载迁移指引；宪法修订消除原则 I 事实漂移

**Independent Test**: quickstart.md §4 足迹检索 0 有效引用 + §6 文档一致性核对逐项通过

### Implementation for User Story 3

- [x] T015 [P] [US3] 编辑 `README.md`：删除 L44 特性清单 curl 项、L74-75 curl_cffi 安装行、L164 `select_client("curl_cffi")` 示例、L169-175 impersonate 整段；L65 安装候选项与 L157 优先级改为 aiohttp > httpx（data-model U1）
- [x] T016 [P] [US3] 编辑 `docs/README.md`：与 T015 镜像同步（L44/61/70-71/153/160/165-171），完成后与 README.md 逐段比对无漂移（data-model U2）
- [x] T017 [P] [US3] 编辑 `docs/request_client.md`：对比表删 curl_cffi 行（L13）与 impersonate 说明（L17/22）；L22/49/51/93/129 泛述更新；L229-251 自定义客户端教程重写语境——curl_cffi 明确标注为"第三方自定义接入示例（内置已不再携带，自定义接入仍然可行）"，删除"模块默认携带 CurlCFFIClient"表述（research R5，data-model U3）
- [x] T018 [P] [US3] 编辑 `docs/configuration.md`：设置支持表删除 curl_cffi 列与 impersonate 行，http2 行保留（httpx 仍支持）（data-model U4）
- [x] T019 [P] [US3] 编辑 `docs/examples/audio.md`：`from curl_cffi import requests` 改用 aiohttp 示例，L29 注释改"bilibili-api 默认使用 aiohttp 作为请求客户端"（data-model U5）
- [x] T020 [P] [US3] 编辑 `.github/ISSUE_TEMPLATE/troubleshooting.md`：L24 请求库候选项删 curl_cffi（data-model U6）
- [x] T021 [P] [US3] 编辑 `AGENTS.md` 6 处：L7 概览、L51 结构树、L105 优先级、L180 uv sync 清单、L288 陷阱、L295 关键依赖表，全部同步为 aiohttp > httpx 两客户端实态（data-model G1）
- [x] T022 [US3] 在 `CHANGELOGS/` 新增未发布版本节（发布时再定版本号，spec Assumptions 明确版本语义不约束本特性）：记录移除事项、影响面与迁移指引（照录 contracts §5 三行表），标注 BREAKING CHANGE（data-model U8）
- [x] T023 [US3] 以 `docs: 同步移除 CurlCFFI 的用户文档与治理文本表述` 提交 T015–T022 产物（research R6 提交②；README/docs 门面文件允许手工编辑，`docs/modules/` 生成域不在本笔范围）
- [x] T024 [US3] 修订 `.specify/memory/constitution.md`：原则 I 优先级链 `curl_cffi > aiohttp > httpx` 改为 `aiohttp > httpx`（L33），版本 1.0.1 → 1.0.2，文件头部附 Sync Impact Report（版本变化、修订原则、无迁移事项）（research R6，宪法 Governance 条款）
- [x] T025 [US3] 以 `docs: amend constitution to v1.0.2 客户端优先级随移除 CurlCFFI 适配更新` 独立提交 T024（宪法要求修订 MUST 独立提交，research R6 提交③）

**Checkpoint**: 全部用户故事达成——库行为、用户文档、治理文本三方一致。

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: 全量验收与收口

- [x] T026 运行 `uv run python scripts/lint.py` 全量门禁确认全绿（ruff check → format → 阻断检查 → pyrefly → 类型棘轮 → 文档漂移校验；宪法 III 红线）
- [x] T027 按 `specs/009-remove-curlcffi-client/quickstart.md` 复跑 §1–§7 全部场景并逐项记录结果（§5 真机冒烟需凭据，缺凭据时记录 skip 原因不阻塞；§5 可选最小环境步骤按其前提条件决定是否执行）
- [x] T028 执行 quickstart §4 足迹检索确认 0 有效引用（豁免清单见 data-model §6；含 uv.lock 与 docs/modules/client.md 的 REGEN/SYNC 核对）
- [x] T029 凭据环境执行 `uv run pytest -m cred0` 与 `uv run pytest -m readonly` 真机冒烟（SC-002；cred0 层预算 ≤ 30 请求不变，计数器挂钩仍覆盖两个内置客户端）

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: 无依赖，立即开始
- **Foundational (Phase 2)**: 空——无阻断项
- **US1 (Phase 3)**: 依赖 T001 基线；T003 → T004 顺序强制（先改清单后删文件，防二次导入炸裂）；T006/T007/T008 可并行；T009 依赖 T003（清单改完再 sync 才安全）；T010 依赖 T004；T011 收口
- **US2 (Phase 4)**: 依赖 US1 完成（场景③的 ModuleNotFoundError 断言以 T004 为前提）；T012 先红 → T013 实现 → T014 提交
- **US3 (Phase 5)**: 依赖 T014（提交①后才有干净的 docs 提交基底）；T015–T021 全部可并行（互不同文件）；T022 → T023 提交②；T024 → T025 提交③
- **Polish (Phase 6)**: 依赖 T025 全部提交完成

### User Story Dependencies

- **US1 (P1)**: 仅依赖基线，不依赖其他故事 —— MVP
- **US2 (P2)**: 依赖 US1 的删除产物（T004），语义上是同一移除动作的报错指引面
- **US3 (P3)**: 依赖 US1+US2 代码面定型（文档描述的是最终行为）

### Parallel Opportunities

- US1 内：T006 / T007 / T008（三个不同测试文件）
- US3 内：T015–T021（七个不同文档文件）
- 跨故事不可并行：US2 依赖 US1，US3 依赖 US1+US2（单人顺序执行即为默认路径）

---

## Parallel Example: User Story 1

```bash
# T003–T005 完成后，三个测试清理任务并行执行：
Task: "conftest.py 计数器清单与 docstring（tests/conftest.py）"
Task: "timeout 语义去 curl 化（tests/test_offline_client_timeout_semantics.py）"
Task: "WS 泄漏用例去 curl 化（tests/test_offline_ws_handle_leak.py）"
```

## Parallel Example: User Story 3

```bash
# 七个文档任务互不同文件，可并行：
Task: "README.md"; Task: "docs/README.md"; Task: "docs/request_client.md"
Task: "docs/configuration.md"; Task: "docs/examples/audio.md"
Task: ".github/ISSUE_TEMPLATE/troubleshooting.md"; Task: "AGENTS.md"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. 完成 Phase 1 基线（T001）
2. 完成 Phase 3 全部（T002–T011）
3. **STOP and VALIDATE**: `uv run pytest -m "not integration"` 全绿 + 默认选中 aiohttp 抽查
4. 此时库已可用但报错指引未增强、文档未同步——不建议在此停点发布

### Incremental Delivery

1. T001 基线 → 2. US1 移除与回退（MVP）→ 3. US2 报错指引 + refactor! 主提交 → 4. US3 文档/治理/宪法三笔收尾 → 5. Polish 全量门禁与 quickstart 复跑

### 提交纪律（research R6）

- 提交①（T014）：`refactor!:` 库代码 + 依赖 + 测试 + 生成页 —— BREAKING CHANGE footer
- 提交②（T023）：`docs:` 用户文档 + 门面 + CHANGELOGS
- 提交③（T025）：`docs: amend constitution to v1.0.2` —— 宪法修订独立提交
- 一个提交只做一件事；不 push（用户明确要求时才推送）

## Notes

- 测试先行任务（T002/T012）必须先运行确认"红"再进入实现，转绿在 T011/T014 验证
- `docs/modules/` 为 doc_gen 生成域，任何改动经 `scripts/doc_gen.py` 而非手编（AGENTS 红线）
- 全部新测试遵守离线红线：无网络请求、无真实凭据、不改账号状态（宪法 IV）
- 每个任务或逻辑组完成后运行对应层级的 pytest 快速反馈；Phase 6 统一收口

---

## Implementation Completion Record（2026-10-11，speckit-implement 执行留痕）

- **T001 基线**：`uv sync` 后 curl-cffi 0.16.3 在环境；离线全量 281 passed / 1 skipped（PyQt6 缺失，无关）/ 289 deselected。curl 相关用例实测为 timeout 语义 3 例（`TestCurlCFFIClientTimeout`）+ WS 泄漏 4 例 = 7 例（本文件与 data-model 写 4+4=8，以实测为准）。
- **T002 红**：场景①②共 5 用例全部失败（清单含 curl / 默认选中 curl_cffi / 文案不符），红确认有效。
- **T010**：`doc_gen.py` 重生成为 no-op——`docs/modules/client.md` 记录的是 `client.py`（IP 终端模块），clients 包从未进入 doc_gen 生成域（data-model U7 假设与实态不符）；HEAD 下 docs/ 仅手写页 `docs/request_client.md` 含 CurlCFFI。漂移校验自然通过。
- **T011**：离线全量 279 passed（281 − 7 curl 用例 + 5 新增场景①②用例）；`get_registered_clients()` 为 aiohttp/httpx，默认选中 aiohttp，`CurlCFFIClient` 导入 ModuleNotFoundError。
- **T012 红**：仅 ③b 消息断言红（现消息无清单），③a/③c 已绿作永久回归锚。
- **T014**：主提交经 pre-commit 修正两处 ruff（`Callable` 导入源、import 排序）后入库为 b3d03ec，并 amend 并入 ruff format 对 `_session.py` / `conftest.py` 的微调；`select_client` 的 Raises docstring 多行续行触发 doc_gen `parse_docstring` IndexError，按库内单行约定改写后随 dc986da 入库（含再生成的 `docs/modules/bilibili_api.md`；生成页由此出现一条 doc_gen 对"无 Returns 节函数"解析 Raises 的既有局限产生的空行，属工具侧已知行为，不在本特性范围）。
- **T023**：docs 提交 c925033（8 文件）；`docs/README.md` 的 pip 安装命令段存在特性 008 遗留的上游地址漂移（不在本特性足迹，未处理）。
- **T025**：宪法修订独立提交 8e58da0（v1.0.2，头部 Sync Impact Report）。特性 005 遗留的 v1.0.1 未提交修订先行以 d233ae1 独立补记入库，保持本笔范围纯净。
- **T026**：`uv run python scripts/lint.py` 全绿（ruff check / format / tests+scripts 阻断 / pyrefly 0 错误 / 棘轮 / 文档漂移"docs/modules/ 无漂移"；mypy 缓存落后提示为既有降级路径）。
- **T027**：§1 依赖清洁通过（env 与 pyproject/requirements/uv.lock 均无 curl）；§2 离线全量 282 passed / 1 skipped（PyQt6）；§3 抽查全部符合期望（registered=[aiohttp,httpx]、default=aiohttp、契约报错文案逐字吻合、ModuleNotFoundError、`get_client()` 返回 AioHTTPClient）；§4 见 T028；§5 见 T029；§6 镜像/治理/变更记录核对逐项通过；§7 门禁见 T026。
- **T028**：足迹检索 0 "描述为可用客户端"的有效引用。字面命中分类：specs/001/002/005/008/009-*（豁免归档）、CHANGELOGS/v17、v18（豁免历史）与 UNRELEASED.md（移除记录本体）、docs/request_client.md 6 处（R5 裁决的"第三方自定义接入示例"教学语境）、.specify/memory/constitution.md 2 处（Sync Impact Report 修订记载，from→to 历史描述）、tests/test_offline_client_selection.py 12 处（FR-007 要求的移除契约锚定，断言其不可用）。检索另发现并修复 1 处计划外真实残留：`bilibili_api/clients/AioHTTPClient.py` ws_send 注释引用已删除类（fc6757b）。quickstart §4 的 `^./` 过滤模式在 Windows Git Bash 路径输出下不匹配，本次以等效过滤复核。
- **T029**：本机无凭据（无 `.bilibili.cookie` / BILI_* / TEMP 缓存），cred0：5 passed / 7 skipped / 0 failed；readonly：4 passed / 2 skipped / 0 failed——缺凭据自动 skip 符合设计。通过的匿名反爬链路用例实际经 aiohttp 默认路径发起真机请求（buvid / bili_ticket / wbi 预取正常），即默认选中路径的可用性已在真机验证。观察项：解释器退出时 aiohttp "Unclosed client session" GC 告警（会话池按事件循环缓存、进程退出未显式关闭的既有生命周期表现，随默认客户端切换为 aiohttp 而显现，零失败、不阻塞验收，留待独立特性跟进）。

**提交序列**：d233ae1（前置：宪法 v1.0.1 补记）→ b3d03ec（refactor! 主提交）→ c925033（docs 用户文档/治理）→ 8e58da0（宪法 v1.0.2）→ dc986da（docstring 单行兼容修复）→ fc6757b（注释残留清理）。
