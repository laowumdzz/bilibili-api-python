# Tasks: 扫码登录不再强制 ac_time_value（refresh_token）非空

**Input**: Design documents from `/specs/006-login-refresh-token-optional/`

**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/library-api.md, quickstart.md

**Tests**: 本特性的规格 FR-008 明确要求用例反转与新增（离线层），故包含测试任务；测试先行（红）→ 实现（绿）。

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- 单库结构：源码 `bilibili_api/`、脚本 `scripts/`、测试 `tests/`、文档 `docs/`（见 plan.md Project Structure）

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: 环境就绪

- [x] T001 运行 `uv sync` 确保 `.venv` 与 dev 组依赖（pytest / ruff / pyrefly / mypy）就绪（依赖清单见 pyproject.toml / uv.lock）
- [x] T002 基线确认：运行 `uv run pytest tests/test_offline_login_v2.py tests/test_offline_login_cache.py tests/test_offline_login_and_cache.py -q`，确认改动前三套离线测试全绿（记录基线，后续所有"照旧通过"以此为准）——基线 46 passed

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: 无跨用户故事阻塞项——本特性为单点行为修改（仅 `bilibili_api/login_v2.py` 一处源码 + 测试文件），无新增基础设施；Phase 1 基线确认即全部前提。

**Checkpoint**: 基线绿 → 用户故事实现可以开始

---

## Phase 3: User Story 1 - refresh_token 缺失时扫码登录仍成功 (Priority: P1) 🎯 MVP

**Goal**: WEB 通道扫码登录 DONE 分支的必需字段校验收窄为三个 Cookie 字段；ac_time_value 缺失 / 空串 / 空值时登录成功、凭据可用（spec §US1，FR-001 / FR-002 / FR-003）。

**Independent Test**: mock 响应（Cookie 齐全、无 refresh_token）驱动 `check_state()` → DONE + `get_credential()` 三 Cookie 非空 + `ac_time_value == ""`；`uv run pytest tests/test_offline_login_v2.py -k "check_state" -v` 全绿。

### Tests for User Story 1（先红后绿）

- [x] T003 [US1] 反转 `tests/test_offline_login_v2.py` 中的 `test_check_state_web_missing_refresh_token_raises`（约 218 行）：改为断言新行为——`check_state()` 返回 `DONE`、`get_credential()` 成功、`sessdata` / `bili_jct` / `dedeuserid` 等于下发值、`ac_time_value == ""`、`credential.has_ac_time_value() is False`；测试重命名为新语义（如 `test_check_state_web_missing_refresh_token_succeeds`），docstring 同步（沿用 `_patch_web_poll` / `_FULL_FAKE_COOKIES` 辅助，fake 值，离线无网络）
- [x] T004 [US1] 在 `tests/test_offline_login_v2.py` 新增空值与归一场景用例（依赖 T003 同文件先行）：① 响应体 `refresh_token: ""` → DONE + 空值凭据（spec §Edge Cases 第 1 条）；② `refresh_token` 为非字符串真值（如数字 `12345`）→ `str()` 归一为 `"12345"` 写入凭据、不视作空（spec §Edge Cases 第 2 条，data-model 校验矩阵末行）
- [x] T005 [US1] 修改 `bilibili_api/login_v2.py` 的 `QrCodeLogin.check_state()` WEB 通道 DONE 分支（依赖 T003 / T004 用例先红）：必需字段判定元组从 `("sessdata", "bili_jct", "dedeuserid", "ac_time_value")` 收窄为 `("sessdata", "bili_jct", "dedeuserid")`，`kwargs` 的 `ac_time_value` 归一表达式 `str(events.get("refresh_token") or "")` 原样保留（research D2）；同函数 docstring 的 `Raises:` 段同步为"仅 SESSDATA / bili_jct / DedeUserID 任一缺失或为空串时抛 ArgsException；ac_time_value 为可选字段，缺失 / 为空时凭据该字段为空串、不报错"（中文 docstring 规范，中英文间半角空格）
- [x] T006 [US1] 红→绿闭环验证：`uv run pytest tests/test_offline_login_v2.py -k "check_state" -v` 全绿，且 `test_check_state_web_done_builds_credential_from_set_cookies` 等既有用例不受影响——T003/T004 先红（2 failed）后实现转绿，14 passed 含全部既有回归用例

**Checkpoint**: US1 独立可验——mock 场景登录成功 + 空值凭据可用（SC-001 离线部分达成）

---

## Phase 4: User Story 2 - 空 ac_time_value 凭据的缓存链路行为不变 (Priority: P2)

**Goal**: 零产品代码改动的前提下，锁定缓存链路对"无 ac_time_value 键"凭据的既有语义（spec §US2，FR-005 / FR-006）。

**Independent Test**: `uv run pytest tests/test_offline_login_cache.py tests/test_offline_login_and_cache.py -q` 全绿；走查结论记录于勾选备注。

### Implementation for User Story 2

- [x] T007 [P] [US2] 核验缓存链路离线回归覆盖（`tests/test_offline_login_cache.py` + `tests/test_offline_login_and_cache.py`）：可选键（ac_time_value / buvid3 / buvid4）缺失不影响合法性、`CacheCheckStatus` 枚举完整（含 `EXPIRED_NO_MATERIAL`）、`check_cache(None)` 无网络早返回；如对"无 ac_time_value 键"三态覆盖不足则仅补断言，不改产品代码——勾选备注：三个枚举覆盖点均有既有用例锁定（`test_load_optional_fields_are_not_required` / `test_cache_check_status_enum_is_complete` / `test_check_cache_none_returns_no_cache_without_network`），覆盖充分，零补断言、零产品代码改动；EXPIRED 分支深入用例会触碰真实 TEMP 缓存文件，维持 003 既定的非副作用测试范围
- [x] T008 [P] [US2] 走查并确认 `scripts/login_and_cache.py` 与 `scripts/_login_cache.py` 无需改动：`run_temp_login` 的"仅保留非空字符串"过滤保证空 ac_time_value 不落盘（`save_cache` 为覆盖写入，旧值自然清除）；`check_cache` 的 `if not fields.get("ac_time_value")` 分支即 `EXPIRED_NO_MATERIAL` 终态，空值常态化后语义不变；结论（零改动成立）记录于勾选备注——勾选备注：零改动成立。`login_and_cache.py:241-243` 非空过滤 + `save_cache` 覆盖写 → 空 ac_time_value 不落盘；`:313-315` 真值判定使 `""` / 缺键 / `None` 三形态同走 `EXPIRED_NO_MATERIAL`；`_login_cache.py` 可选键编码契约（空值字段不写入）不变

**Checkpoint**: US2 独立可验——缓存链路对空值凭据三态（合法性 / 直接使用 / 过期删除回退）语义锁定

---

## Phase 5: User Story 3 - 必需字段校验与其余登录通道无回归 (Priority: P3)

**Goal**: 放宽范围不外溢：三 Cookie 缺失仍报错、TV / 短信 / 状态判定不变、真机端到端无回归（spec §US3，FR-004 / FR-007）。

**Independent Test**: `uv run pytest -m "not integration"` 全绿 + 真机扫码验收通过（quickstart §3）。

### Implementation for User Story 3

- [x] T009 [US3] 微调 `tests/test_offline_login_v2.py` 中 `test_check_state_web_done_builds_credential_from_set_cookies` 的 docstring 措辞："四项必需字段非空"改为"三项必需 Cookie 非空 + refresh_token 可选采集"（断言与逻辑不动，仅注释与规格口径对齐）
- [x] T010 [US3] 全量离线回归：`uv run pytest -m "not integration"` 全绿——缺 Cookie 报错（`test_check_state_web_missing_cookie_raises` / `test_check_state_web_empty_cookie_value_raises`）、TV 通道、SCAN / CONF / TIMEOUT 判定、DONE 幂等等既有用例全部照旧通过——271 passed, 1 skipped（既有 skip），0 failed
- [ ] T011 [US3] 真机端到端验收（quickstart §3，人工触发）：`uv run python scripts/login_and_cache.py qrcode` 扫码登录成功、退出码 0、缓存文件写入；随后 `uv run pytest -m readonly` 凭据被服务端识别（注意请求间隔防 412）——勾选备注：待人工执行（需手机扫码，无法由代理完成）。离线层等价验证已由 T003 / T004 mock 用例覆盖（spec §SC-001 / quickstart §1）；执行后如遇异常按 quickstart §3 排查

**Checkpoint**: 全部用户故事独立达成——放宽边界外无行为变化

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: 文档联动、门禁与入库（宪法 III / V）

- [x] T012 运行 `uv run python scripts/doc_gen.py` 再生成 `docs/modules/`（`check_state` docstring 已在 T005 变更；`docs/` 禁止手改）——再生成后与提交版本零差异（`Raises:` 空体为 doc_gen 既有渲染行为，非本次引入），docs/ 无手改
- [x] T013 运行 `uv run python scripts/lint.py` 全链路门禁全绿（ruff check → format → pyrefly → 棘轮 → 文档漂移校验）——ruff 通过、98 文件已格式化、pyrefly 0 错误、棘轮通过、docs/modules/ 无漂移
- [x] T014 提交一（一个提交只做一件事）：`fix(login_v2): 扫码登录不再强制 ac_time_value 非空`——仅含 `bilibili_api/login_v2.py` 与 `tests/test_offline_login_v2.py`（沿用本地 main 维护性直提交实践，见宪法开发工作流第 1 条）——提交 01d8e3d
- [x] T015 提交二：`chore(006): 勾选 tasks.md 全部任务并入库特性规格目录`——`specs/006-login-refresh-token-optional/` 全目录 + `.specify/feature.json`（沿用特性 005 入库实践）——勾选备注：feature.json 位于 `.specify/.gitignore` 忽略清单内（保持本地），与特性 005 实际入库内容一致（仅 specs 目录）；T011 待人工扫码验收，保留未勾选并已备注

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: 无依赖，立即开始；T001 → T002 顺序
- **Foundational (Phase 2)**: 无任务（声明性），Phase 1 基线即前提
- **User Stories (Phase 3-5)**: 均依赖 T002 基线绿
  - **US1 内部强顺序**：T003 → T004 → T005 → T006（同文件测试先行，红→绿）
  - **US2**：T007 / T008 可并行（不同文件，均零产品代码改动），与 US1 无文件冲突
  - **US3**：T009 → T010 顺序（T009 动测试文件须在 US1 完成后）；T011 真机验收依赖 T010
- **Polish (Phase 6)**: T012 依赖 T005（docstring 变更）；T013 依赖全部实现任务；T014 / T015 依赖 T013

### User Story Dependencies

- **User Story 1 (P1)**: 依赖 Phase 1——核心 MVP，无跨故事依赖
- **User Story 2 (P2)**: 依赖 Phase 1——零改动验证型，可与 US1 并行推进（结论在 US1 落地后复核一次更稳）
- **User Story 3 (P3)**: 依赖 US1 完成（T009 与 T003-T005 同文件；T010 回归含 US1 新用例）

### Parallel Opportunities

- T007 ∥ T008（US2 内，不同文件）
- US2（T007/T008）可与 US1（T003-T006）并行——互不触碰相同文件
- T014 与 T015 提交按顺序执行（git 索引互斥），不可并行

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. T001 → T002：环境与基线
2. T003 → T004 → T005 → T006：US1 红→绿闭环
3. **STOP and VALIDATE**: mock 场景登录成功 + 空值凭据（SC-001）——至此核心价值已交付

### Incremental Delivery

1. 基线（T001-T002）→ 2. US1（MVP）→ 3. US2（缓存语义锁定）→ 4. US3（回归 + 真机）→ 5. Polish（文档 / 门禁 / 入库）

---

## Notes

- [P] 任务 = 不同文件且无未完成依赖；同文件的测试任务（T003 → T004）必须顺序执行
- 测试任务先行且必须先红（T003 / T004 在 T005 前失败），实现后转绿（T006 复核）
- T007 / T008 / T009 为核验与措辞级任务，预期产物为零或最小 diff；若发现规格未覆盖的真实缺口（参见 checklists/login-behavior.md CHK021 的覆写语义探讨），先回规格补 FR 再实现
- 真机验收（T011）无法构造"B 站不下发 refresh_token"场景，该行为由 T003 / T004 的 mock 用例覆盖（spec §SC-001 / quickstart §1）
- 提交遵循 Conventional Commits（Git Hook 强制校验）；两笔提交严格分离代码与规格入库（宪法 V：一个提交只做一件事）
