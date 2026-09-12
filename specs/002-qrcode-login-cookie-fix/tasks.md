---

description: "Task list for feature implementation"
---

# Tasks: 修复网页端二维码登录凭据获取失效

**Input**: Design documents from `/specs/002-qrcode-login-cookie-fix/`

**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: spec.md 的 SC-003 / SC-004 明确要求离线测试覆盖，故包含测试任务（离线层，无网络无凭据；真机验收为人工任务）。

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g. US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Single project**: 库源码 `bilibili_api/`、测试 `tests/`、脚本 `scripts/` 均在仓库根下（见 plan.md Project Structure）

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: 确认环境与回归基线

- [x] T001 运行 `uv sync` 后执行 `uv run pytest -m "not integration"`，确认既有离线用例全绿并以此作为本特性的回归基线（改动前快照）

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: `Api` 统一链路的 Cookie 感知能力——US1 / US2 / US3 全部依赖

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [x] T002 在 `bilibili_api/utils/_api.py` 的 `Api` 类新增公共方法 `request_with_cookies(raw: bool = False) -> tuple[int | str | dict | bytes | None, dict]`：内部在 `_request` 返回处理结果的同时携带**最终响应**的 `resp.cookies`，复用 `request()` 的 -403 wbi 重试链路（重试后返回最终成功那次响应的 cookies）；`raw` 语义与 `request()` 对齐；不得改动既有 `request()` / `result` 的签名与返回；附完整中文 docstring（Args / Returns / Raises）与全量类型注解（契约：specs/002-qrcode-login-cookie-fix/contracts/api.md §1，决策依据：research.md D2）
- [x] T003 在 `tests/test_offline_api_core.py` 扩展离线用例（沿用 `_make_resp` + `monkeypatch.setattr(api_mod, "get_client", ...)` 的 fake client 手法）：(a) 返回 `(data 字段提取结果, cookies)` 二元组且 cookies 保持服务端原名大小写；(b) `raw=True` 返回完整解析后的 JSON 体；(c) 响应无 Set-Cookie（cookies 为空 dict）时正常返回；(d) 既有 `request()` 行为不受影响

**Checkpoint**: Cookie 感知请求能力就绪且离线验证通过，用户故事实现可以开始

---

## Phase 3: User Story 1 - 扫码确认后获得可用登录凭据 (Priority: P1) 🎯 MVP

**Goal**: WEB 通道 `check_state` 成功路径改为读取响应 Cookie 构造凭据，消除"返回 DONE 但凭据为空"

**Independent Test**: 离线——T005 模拟响应断言凭据四项必需字段非空；真机——`uv run python scripts/qrcode_login.py` 扫码确认后输出非空性校验与登录身份识别（quickstart.md §3a）

### Implementation for User Story 1

- [x] T004 [US1] 重写 `bilibili_api/login_v2.py` 中 `QrCodeLogin.check_state` WEB 分支的成功路径（现 488-508 行）：请求改用 `await Api(credential=Credential(), **api).update_params(**params).request_with_cookies()`（默认 `raw=False`，与现状 `.result` 的 data 提取语义一致）；响应 Cookie 名统一小写后映射——sessdata / bili_jct / dedeuserid 必需、buvid3 / buvid4 机会性填充，`ac_time_value` 取响应体 `data.refresh_token`；**删除 url 查询串解析逻辑，不得残留为可达代码**（FR-002）；同步更新 `check_state` docstring（凭据来源 + Raises 说明）；保持关键字传参风格（映射表与不变式：specs/002-qrcode-login-cookie-fix/data-model.md §1 / §4）
- [x] T005 [US1] 在 `tests/test_offline_login_v2.py` 新增离线用例（monkeypatch 模拟 `request_with_cookies` 返回值，无网络无真实凭据）：成功响应（data.code=0 + `data.refresh_token`）搭配 `{SESSDATA, bili_jct, DedeUserID, buvid3, buvid4}`（服务端原名大小写）→ 返回 `QrCodeLoginEvents.DONE` 且 `get_credential()` 四项必需字段非空、buvid 已填充；另覆盖 Cookie 名全小写与混合大小写形态（FR-005）；覆盖成功后重复轮询的幂等（凭据不被清空）
- [x] T006 [P] [US1] 补全 `scripts/qrcode_login.py` 真机验收脚本：`generate_qrcode()` 后循环 `check_state()`（SCAN / CONF / TIMEOUT 打印状态），DONE 后仅输出各字段**非空性与长度**校验结果（严禁打印任何凭据值，FR-008），并用凭据调用一个需登录态的只读接口输出"登录身份已识别"（脚本只使用既有公共 API，可与 T004 并行编写）

**Checkpoint**: User Story 1 独立可测——离线 T005 全绿 + 真机 T006 扫码成功即 MVP 达成

---

## Phase 4: User Story 2 - 凭据不完整时明确报错 (Priority: P2)

**Goal**: 必需字段缺失时抛 `ArgsException`（消息只含字段名），杜绝"假成功"

**Independent Test**: 离线——T008 缺字段场景断言异常类型、消息内容约束与 `has_done()` 保持 False

### Implementation for User Story 2

- [x] T007 [US2] 在 `bilibili_api/login_v2.py` WEB 分支凭据构造前增加必需字段校验（依赖 T004 的重写结果，同文件顺序执行）：sessdata / bili_jct / dedeuserid / ac_time_value 任一缺失或为空串 → 在给 `self.__credential` 赋值**之前**抛 `ArgsException`，消息形如"二维码登录响应缺少必要字段: …"仅含缺失字段名（契约：specs/002-qrcode-login-cookie-fix/contracts/api.md §3）
- [x] T008 [US2] 在 `tests/test_offline_login_v2.py` 新增离线用例：分别缺少每个必需字段（含 `refresh_token` 缺失、字段值为空串两种形态）时抛 `ArgsException`；断言消息包含缺失字段名、不包含用例中使用的伪造字段值；断言抛出后 `login.has_done()` 为 `False`（T005 完成后同文件追加，不可与之并行）

**Checkpoint**: User Story 2 独立可测——离线异常契约用例全绿

---

## Phase 5: User Story 3 - 既有登录流程无回归 (Priority: P3)

**Goal**: 状态判定与 TV 通道行为零变化

**Independent Test**: 离线——T009/T010 回归用例 + T011 全量离线回归零失败

### Implementation for User Story 3

- [x] T009 [US3] 在 `tests/test_offline_login_v2.py` 新增状态判定回归用例：模拟 `data.code` 为 86101 / 86090 / 86038 → 分别返回 SCAN / CONF / TIMEOUT，且三次轮询全程不读写凭据（FR-006）
- [x] T010 [US3] 在 `tests/test_offline_login_v2.py` 新增 TV 通道回归用例：monkeypatch `Api.request(raw=True)` 返回结构化 `cookie_info.cookies` 响应，断言 TV 凭据构造路径与现状一致、不受 WEB 分支改动影响（FR-007；T009 之后同文件顺序执行）
- [x] T011 [US3] 运行 `uv run pytest -m "not integration"` 全量离线回归，确认零失败（SC-003）；如有失败先修复再进入 Polish

**Checkpoint**: 全部用户故事独立功能达成

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: 门禁、文档、验收与提交

- [x] T012 [P] 运行 `uv run python scripts/doc_gen.py` 重新生成 `docs/modules/`（T002 / T004 / T007 的 docstring 变更后必须重生成，不手改 docs/）
- [x] T013 运行 `uv run python scripts/lint.py` 全量门禁至全绿：ruff check / ruff format / pyrefly / 类型豁免存量棘轮只减不增（如新方法引入类型错误须当场修复，基线只向下更新）/ 文档漂移校验
- [x] T014 按 `specs/002-qrcode-login-cookie-fix/quickstart.md` §1 / §2 执行离线与门禁级验证并记录结果
- [ ] T015 （人工，需手机 B 站 App）按 quickstart.md §3 真机验收：扫码确认 → 凭据四项非空 → 只读接口识别登录身份；随后复验 `uv run pytest --login qrcode -m "not integration"`（特性 001"扫码确认落缓存"验收项，修复后应恢复可用）
- [x] T016 按"一个提交只做一件事"拆分提交（本地 main 直提交，Conventional Commits 钩子校验）：① `fix(login): 网页端二维码登录改从轮询响应 Set-Cookie 构造凭据`（`bilibili_api/utils/_api.py` + `bilibili_api/login_v2.py` + `docs/` 重生成）；② `test: 新增二维码登录凭据构造离线用例`（`tests/` 两个文件）；③ `chore: 补全扫码登录真机验收脚本`（`scripts/qrcode_login.py`）
- [ ] T017 真机验收（T015）通过后，以 `docs(specs): 归档 002-qrcode-login-cookie-fix 规格与实现任务清单` 提交归档 specs/002 目录

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3+)**: All depend on Foundational phase completion
  - US1 → US2 为同文件（`bilibili_api/login_v2.py`）同一函数的顺序依赖，必须按优先级串行
  - US3 的回归用例在 US1 + US2 完成后才具备完整守护价值
- **Polish (Phase 6)**: Depends on all user stories being complete（T015 / T017 另依赖人工真机扫码）

### User Story Dependencies

- **User Story 1 (P1)**: 依赖 Phase 2（T002/T003）；不依赖其他故事——MVP
- **User Story 2 (P2)**: 依赖 US1 的 T004（同一代码路径的守卫逻辑）
- **User Story 3 (P3)**: 逻辑上独立（纯测试守护），建议在 US1 + US2 后执行以获得完整回归面

### Within Each User Story

- 实现先于其验证用例的运行（用例可按契约先行编写，先红后绿）
- 同文件任务串行（T004 → T007；T005 → T008 → T009 → T010 均在 `tests/test_offline_login_v2.py`）
- 每个故事完成后在 Checkpoint 独立验证再前进

### Parallel Opportunities

- T006（`scripts/qrcode_login.py`）与 T004 / T005 并行——不同文件且仅依赖既有公共 API
- T012（doc_gen）可与 T011 的回归运行并行（不同产物）
- 其余任务因同文件或依赖链串行

---

## Parallel Example: User Story 1

```bash
# T004 与 T006 可并行（不同文件，后者只依赖既有公共 API）：
Task: "重写 check_state WEB 分支成功路径 in bilibili_api/login_v2.py"
Task: "补全真机验收脚本 in scripts/qrcode_login.py"

# T005 需在 T004 落地后运行（针对新行为断言）。
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup（基线确认）
2. Complete Phase 2: Foundational（`Api.request_with_cookies`）
3. Complete Phase 3: User Story 1（核心修复）
4. **STOP and VALIDATE**: 离线 T005 全绿 + 真机 T006 扫码取得非空凭据——缺陷已消除，可独立交付

### Incremental Delivery

1. Setup + Foundational → Cookie 感知能力就绪
2. Add User Story 1 → 独立验证（MVP!）
3. Add User Story 2 → 异常契约独立验证
4. Add User Story 3 → 回归面独立验证
5. Polish：门禁 / 文档 / 真机验收 / 分提交 / 归档

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- 离线用例一律使用伪造 Cookie 值，严禁引入真实凭据（宪法 IV / 凭据安全）
- 异常消息与脚本输出严禁出现凭据字段值（FR-008）
- 修 bug（库代码）与加测试按宪法 V 拆分为独立提交
- 真机验收（T015）需要用户配合扫码，完成前不得勾选
