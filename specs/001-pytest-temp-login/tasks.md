---
description: "Task list for feature 001-pytest-temp-login"
---

# Tasks: pytest 临时登录凭据（--login）

**Input**: Design documents from `/specs/001-pytest-temp-login/`（spec.md / plan.md / research.md / data-model.md / contracts/ / quickstart.md）

**Prerequisites**: plan.md ✅ spec.md ✅ research.md ✅ data-model.md ✅ contracts/ ✅

**Tests**: 离线单元测试为本特性交付物的一部分（宪法 IV 分层测试要求纯逻辑必须有离线覆盖，见 plan.md Testing 节）；交互式登录流程按 quickstart.md 手工场景验证，不写自动化集成用例。

**Organization**: 任务按用户故事分组；每个故事可独立实现、独立验证。MVP = User Story 1。

## Format: `[ID] [P?] [Story] Description`

- **[P]**: 可并行（不同文件、无未完成依赖）
- **[Story]**: 所属用户故事（US1–US4，映射 spec.md）
- 所有路径相对仓库根目录；实现语言 Python ≥ 3.10；命令一律 `uv run` 前缀

## Path Conventions

本项目为单仓库：测试基建在 `tests/`，库源码在 `bilibili_api/`（本特性**零改动**）。

---

## Phase 1: Setup（共享基础设施）

**Purpose**: 新模块骨架与常量约定

- [x] T001 创建 `tests/_login_cache.py` 模块骨架：文件名常量 `bilibili_api_pytest_login.json` 与路径解析函数（基于 `tempfile.gettempdir()`，见 contracts/cache-file-format.md）；全模块中文 docstring + 完整类型注解（ruff/pyrefly 可过）

---

## Phase 2: Foundational（阻塞性前置，全部故事依赖）

**Purpose**: 纯函数层（可离线单测）+ pytest 选项注册

- [x] T002 在 `tests/_login_cache.py` 实现凭据编码函数：`dict[str, str | None] → base64(UTF-8 JSON)` 字符串（contracts/cache-file-format.md 内容格式）
- [x] T003 在 `tests/_login_cache.py` 实现缓存读取与合法性判定：输入路径，输出 `absent / corrupt / 合法字段 dict` 四类结果（判定规则=合法性判定 1–4 条；corrupt 分支的异常与返回文本不得包含文件内容）
- [x] T004 在 `tests/_login_cache.py` 实现凭据来源优先级合并纯函数：`--login 新凭据 > 缓存字段 > 环境变量/cookie 合并结果`（后者沿用 conftest 现行 `_load_credential_values()` 的产出结构；见 data-model.md CredentialSource）
- [x] T005 [P] 编写离线单元测试 `tests/test_offline_login_cache.py`：编码↔解码 roundtrip、坏 base64、非 JSON、顶层非对象、缺三必需键、空串字段、优先级合并各分支；全程无网络无真实凭据（宪法 IV）
- [x] T006 [P] 在 `tests/conftest.py` 注册 `pytest_addoption` 的 `--login` 选项（`choices=["phone", "qrcode"]`），非法值由 pytest 直接报用法错误退出（FR-002 / contracts/cli-option.md C2）

**Checkpoint**: 纯逻辑可离线验证全绿；`--login` 参数可被 pytest 识别与拒绝非法值。

---

## Phase 3: User Story 1 - 扫码临时登录执行全量测试 (Priority: P1) 🎯 MVP

**Goal**: `pytest --login qrcode` 扫码 → 凭据写入 TEMP 缓存 → 本次以新凭据执行全部用例

**Independent Test**: quickstart.md 场景 2（无凭据环境执行 `uv run pytest --login qrcode`，扫码后集成用例执行、`$TEMP` 出现 base64 缓存文件）

### Implementation for User Story 1

- [x] T007 [US1] 改造 `tests/conftest.py` 的 `credential` fixture：会话级解析链接入——`--login` 传入时无条件走登录编排（即使缓存有效也不跳过，C1），成功后调用 T002 编码写入缓存并以新凭据为第 1 优先级；不传时链路暂保持现状（本故事零回归）
- [x] T008 [US1] 在 `tests/conftest.py` 实现二维码登录编排（`asyncio.run` 包裹，research.md D2/D3）：`QrCodeLogin()` → `generate_qrcode()` → 终端打印 `get_qrcode_terminal()` → ~2s 轮询 `check_state()`：SCAN/CONF 等待、TIMEOUT 重新生成并提示（连续 3 次中止）、DONE 取 `get_credential()`
- [x] T009 [US1] 在 `tests/conftest.py` 实现登录中止路径（C3）：用户中断 / 3 次超时 / 登录异常 → 一条清晰提示、不写缓存、既有缓存原状、离线用例照常执行

**Checkpoint**: `uv run pytest --login qrcode`（quickstart 场景 2）与零回归（场景 0）均符合预期。

---

## Phase 4: User Story 2 - 手机号短信验证码临时登录 (Priority: P2)

**Goal**: `pytest --login phone` 完成短信验证码登录，缓存与执行行为与扫码通道一致

**Independent Test**: quickstart.md 场景 2'（输入手机号 → 浏览器完成极验 → 输入短信验证码 → 集成用例执行）

### Implementation for User Story 2

- [x] T010 [US2] 在 `tests/conftest.py` 实现短信登录编排（research.md D4）：`input()` 收集国家码（默认 `+86`）与手机号 → `Geetest().generate_test(GeetestType.LOGIN)` + `start_geetest_server()` → 终端打印 `get_geetest_server_url()` → 轮询 `has_done()` → `send_sms()` 得 captcha_key → `input()` 收验证码 → `login_with_sms()`
- [x] T011 [US2] 在 `tests/conftest.py` 实现 `LoginCheck` 风控二次验证分支：`fetch_info()` → `GeetestType.VERIFY` 极验 → `LoginCheck.send_sms()` → `input()` 二次验证码 → `complete_check()`；`finally` 中关闭极验本地服务；失败/中断走 T009 同款中止路径

**Checkpoint**: `uv run pytest --login phone`（quickstart 场景 2'）符合预期；扫码通道不受影响。

---

## Phase 5: User Story 3 - 后续运行自动复用缓存凭据 (Priority: P3)

**Goal**: 不带 `--login` 的普通运行读取缓存：有效直接用（零交互），过期则刷新并回写

**Independent Test**: quickstart.md 场景 3（缓存有效时 `uv run pytest -m integration` 全程无交互）；场景 7 前半支（刷新成功路径）

### Implementation for User Story 3

- [x] T012 [US3] 在 `tests/conftest.py` 为 `credential` fixture 增加缓存分支（优先级 2，data-model.md）：T003 读取 → 合法 → `asyncio.run(check_valid())` 判定 → 有效则以缓存凭据执行全部用例（C4 第 3 行）；`absent/corrupt` 暂按回退既有链路处理（细化在 US4）
- [x] T013 [US3] 在 `tests/conftest.py` 实现过期刷新成功路径（research.md D5 / FR-011）：`check_valid()` 为 False 且缓存含 `ac_time_value` → `Credential.refresh()` → 成功后以刷新凭据继续执行并用 T002 回写缓存文件

**Checkpoint**: quickstart 场景 3 通过；构造过期凭据（场景 7）时刷新成功支符合预期。

---

## Phase 6: User Story 4 - 缓存异常时的安全降级 (Priority: P4)

**Goal**: 缺失 / 损坏 / 过期不可刷新三态下进程不崩溃、反馈明确、凭据用例全跳过

**Independent Test**: quickstart.md 场景 4（损坏）、场景 5（缺失）、场景 7 后半支（刷新失败）

### Implementation for User Story 4

- [x] T014 [US4] 在 `tests/conftest.py` 实现 absent 分支（FR-007）：终端一条「缓存凭据文件不存在」类提示 → 回退 env/cookie → 最终无凭据则 `pytest.skip`（沿用现行 skip 文案风格）
- [x] T015 [US4] 在 `tests/conftest.py` 实现 corrupt 分支（FR-008）：一条错误 + `Path.unlink()` 删除缓存 → 回退既有链路 → 最终无凭据 skip
- [x] T016 [US4] 在 `tests/conftest.py` 实现刷新失败分支（FR-012）：无 `ac_time_value` 或 `refresh()` 抛异常 → `warnings.warn(UserWarning)` 一条警告 + 删除缓存 + 需凭据用例 skip、进程正常结束
- [x] T017 [US4] 在 `tests/conftest.py` 实现无法验证分支（FR-013）：`check_valid()` 抛网络类异常 → 一条提示 + skip，**不删除**缓存文件
- [x] T018 [US4] 消息安全审查：核对 `tests/conftest.py` 与 `tests/_login_cache.py` 全部提示/错误/警告/异常文本，确认不含任何凭据字段值（FR-014 / SC-006）

**Checkpoint**: quickstart 场景 4、5、7（失败支）全部符合预期。

---

## Phase 7: Polish & Cross-Cutting Concerns

- [x] T019 [P] 更新 `AGENTS.md`「测试」一节：凭据来源优先级加入 TEMP 缓存（第 2 位）并补 `--login` 用法示例（与 contracts/cli-option.md 一致）
- [x] T020 [P] 按 quickstart.md 场景 0–7 执行端到端手工验证并记录结果（重点：Windows + Git Bash 下终端二维码显示，research.md D10）
  - 已程序化验证：场景 0（缺失提示 + 离线全过）、1（离线单测 17 项全绿）、2 渲染支（终端 ASCII 二维码 + 提示行 + 轮询挂起，未扫码前终止不写缓存）、2' 中止支（EOF 输入 → 中止提示 + 不写缓存 + 离线照常）、4（损坏 → 报错 + 删除 + 继续）、5（缺失 + 无回退源 → skip）、6（非法值退出码 4）、7 刷新失败半支（UserWarning + 删除 + skip，含一次真实联网 check_valid）
  - 留作用户真机验收：场景 2 扫码确认与缓存落盘、2' 完整短信登录、3 有效凭据复用、7 刷新成功半支（均需真实 B 站账号 / 手机）
  - 实现侧发现并修复：pytest 捕获期 `sys.stdin` 被替换导致 `input()` 抛 OSError，改为经终端 writer 提示 + 原始 stdin（`sys.__stdin__` 回退）读取；Windows Proactor 下 curl_cffi 会输出一条固有的 selector 线程警告（上游行为，不影响请求）
- [x] T021 运行全量门禁 `uv run python scripts/lint.py` 与 `uv run pytest -m "not integration"`，确认全绿且类型棘轮基线无增长
- [x] T022 按 Conventional Commits 拆分提交（`feat` 测试基建 / `test` 离线用例 / `docs` AGENTS.md），一个提交只做一件事（宪法 V）

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: 无依赖，立即开始
- **Foundational (Phase 2)**: 依赖 Phase 1；**阻塞全部用户故事**
- **User Stories (Phase 3–6)**: 均依赖 Phase 2 完成
  - US1 → US2 → US3 → US4 按优先级顺序推进（同文件 conftest.py 为主，串行最稳）
  - US2 依赖 T009（复用中止路径）；US3 依赖 T007（解析链骨架）；US4 依赖 T012/T013（在其分支上细化降级）
- **Polish (Phase 7)**: 依赖全部所需故事完成

### User Story Dependencies

- **US1 (P1)**: Phase 2 后即可开始——MVP，不依赖其他故事
- **US2 (P2)**: 复用 US1 的写缓存与中止路径（T007/T009），缓存契约一致
- **US3 (P3)**: 复用 US1 建立的解析链接入点（T007）
- **US4 (P4)**: 在 US3 的缓存分支（T012/T013）上补齐四个降级出口

### Within Each User Story

- 纯函数（tests/_login_cache.py）先于 conftest 编排（消费方）
- 登录编排先于降级分支
- 每故事完成即跑 quickstart 对应场景独立验证

### Parallel Opportunities

- Phase 2：T005（tests/test_offline_login_cache.py）与 T006（tests/conftest.py）不同文件可并行
- Phase 7：T019（AGENTS.md）与 T020（手工验证）可并行
- 其余任务集中在 tests/conftest.py 单文件内，建议串行

---

## Parallel Example: Phase 2

```bash
# 不同文件、互不依赖，可同时开工：
Task: "T005 编写离线单元测试 tests/test_offline_login_cache.py"
Task: "T006 在 tests/conftest.py 注册 --login 选项"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Phase 1 + Phase 2 → 纯逻辑可离线验证、选项可识别
2. Phase 3 (US1) → `--login qrcode` 端到端可用
3. **STOP and VALIDATE**: quickstart 场景 0（零回归）+ 场景 2（扫码主路径）
4. 此时已可交付：无凭据环境一次扫码跑全量测试

### Incremental Delivery

1. Foundation → 2. US1（MVP）→ 3. US2（短信备选通道）→ 4. US3（免二次登录复用）→ 5. US4（异常降级兜底）→ 6. Polish（文档/门禁/提交）
   每步交付独立价值且不破坏前序行为。

---

## Notes

- [P] = 不同文件且无未完成依赖；本特性主战场是 `tests/conftest.py`，多数任务串行
- 实现细节依据：research.md D1–D10（决议编号在任务中引用）
- 宪法红线自查点：库代码零改动（I/II）、离线用例无网络（IV）、消息无凭据值（安全）、`uv run python scripts/lint.py` 全绿（III）
- 验证主战场是 quickstart.md 手工场景，不在 CI 内新增交互式用例
