---

description: "Task list for 003-login-cache-script"
---

# Tasks: 测试登录凭证流程迁移至独立脚本

**Input**: Design documents from `/specs/003-login-cache-script/`

**Prerequisites**: [plan.md](plan.md) · [spec.md](spec.md) · [research.md](research.md) · [data-model.md](data-model.md) · [contracts/](contracts/) · [quickstart.md](quickstart.md)

**Tests**: 仅包含离线可验证的用例任务（项目分层测试约束：离线用例不得触网 / 用真实凭据）；真机行为一律走 [quickstart.md](quickstart.md) 人工验收，不在任务内造网络用例。

**Organization**: 按用户故事分组。US1 = 独立脚本可用（MVP）；US2 = 测试装配迁移与行为兼容；US3 = 两入口统一性核验。

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

本特性为库 + 开发脚本结构：新代码在 `scripts/`，测试装配在 `tests/`，库 `bilibili_api/` 零改动（见 plan.md Project Structure）。

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: 工具链配置，使后续新增脚本文件可通过 ruff 门禁

- [x] T001 在 pyproject.toml 注册新脚本豁免与首方分类：`[tool.ruff.lint.per-file-ignores]` 增加 `"scripts/login_and_cache.py" = ["T201"]`（附注释：交互式登录脚本，允许 print），`[tool.ruff.lint.isort] known-first-party` 增加 `"scripts"`（见 research.md R5/R6）
	- 完成：E402 已在全局 ignore 中，无需按文件豁免

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: 纯缓存逻辑就位——所有用户故事的共同前置

**⚠️ CRITICAL**: 本阶段完成前不得开始任何用户故事

- [x] T002 原样平移 `tests/_login_cache.py` → `scripts/_login_cache.py`（git mv，代码零改动），并把 `tests/test_offline_login_cache.py` 的导入行从 `tests._login_cache` 改为 `scripts._login_cache`；运行 `uv run pytest tests/test_offline_login_cache.py` 确认全绿
- [x] T003 创建 `scripts/login_and_cache.py` 模块骨架：中文模块 docstring（用途 / 用法 / 契约链接）、导入 `bilibili_api.login_v2` 与 `bilibili_api.utils.geetest` 依赖、定义 I/O 接缝类型 `NotifyFn` / `PromptFn` 与控制台缺省实现（notify → stdout，error → stderr；prompt → 提示后 input 读取）、re-export `scripts._login_cache` 全部公开名（见 contracts/module-api.md）；`uv run ruff check ./scripts/` 通过

**Checkpoint**: 基础就绪——离线用例绿、ruff 对 tests/ 与 scripts/ 通过，可开始用户故事

---

## Phase 3: User Story 1 - 独立脚本登录并缓存测试凭据 (Priority: P1) 🎯 MVP

**Goal**: `uv run python scripts/login_and_cache.py <qrcode|phone>` 可独立完成登录并把凭据写入既有 TEMP 缓存，测试运行零交互复用

**Independent Test**: 运行脚本完成扫码登录 → 缓存文件生成 → `uv run pytest tests/test_readonly_smoke.py -m integration` 零交互通过（quickstart 场景 2/3/4）

### Implementation for User Story 1

> T004–T007 修改同一文件 `scripts/login_and_cache.py`，按序执行

- [x] T004 [US1] 在 scripts/login_and_cache.py 实现扫码登录流程 `_qrcode_login_flow`：迁移 tests/conftest.py 同名逻辑（生成二维码 → 终端 ASCII 渲染 → 2 秒轮询 → DONE 返回凭据 / TIMEOUT 重生成且连续 3 次中止 / CONF 首次提示确认；UnicodeEncodeError 回退 TEMP 图片路径提示；finally 关闭当前客户端会话），I/O 经 notify/prompt 接缝（research.md R3）
- [x] T005 [US1] 在 scripts/login_and_cache.py 实现短信登录流程 `_phone_login_flow` 与极验辅助 `_complete_geetest`：地区码默认 +86、手机号输入、浏览器滑块（0.5 秒轮询完成标志）、send_sms、验证码输入、login_with_sms；LoginCheck 风控分支（二次滑块 + 二次短信 + complete_check）；finally 关闭极验服务与客户端会话
- [x] T006 [US1] 在 scripts/login_and_cache.py 实现 `run_temp_login(login_type, *, notify, prompt) -> dict[str, str] | None`：asyncio.run 驱动对应流程；**登录成功立即 save_cache 写缓存**（不做联网校验，spec 澄清 Q2）并返回字段集合；四类中止（流程失败 / Ctrl+C / EOF / 未知类型）经 notify 输出不含凭据值的原因并返回 None，不写不破坏既有缓存（contracts/module-api.md 兼容基线 = 原 conftest `_run_temp_login` 消息语义）
- [x] T007 [US1] 在 scripts/login_and_cache.py 实现 CLI 入口 `main()` 与 `if __name__ == "__main__"` 块：argparse 位置参数 `qrcode|phone`（choices 与 pytest `--login` 一致）；无参 / 非法参数输出用法并以退出码 2 结束（不进入交互）；成功退出码 0；中止 / 失败退出码 1（contracts/cli.md）；控制台缺省 I/O 接入 run_temp_login
- [x] T008 [P] [US1] 新增 tests/test_offline_login_and_cache.py 离线用例：模块导入面冒烟（run_temp_login 可导入、签名含 notify/prompt 关键字参数）、re-export 同一性（`scripts.login_and_cache` 的纯函数与 `scripts._login_cache` 为同一对象）、CLI 用法错误路径（无参调用 main() 抛 SystemExit 且码为 2）；运行 `uv run pytest tests/test_offline_login_and_cache.py` 全绿

**Checkpoint**: 独立执行 quickstart 场景 2（用法路径）与场景 3/4（真机扫码 + 零交互复用）通过——US1 单独交付可用 MVP；此时 tests/conftest.py 仍是旧实现，`--login` 行为不变

---

## Phase 4: User Story 2 - 测试命令登录入口行为不回归 (Priority: P2)

**Goal**: `--login qrcode|phone` 由脚本模块提供实现，行为与迁移前一致；conftest 不再含登录流程实现

**Independent Test**: 对照 research.md R8 基线执行 quickstart 场景 5（成功写缓存 / Ctrl+C 中止不写缓存 / 回退链不变），并确认 `uv run pytest -m "not integration"` 全绿

### Implementation for User Story 2

- [x] T009 [US2] 在 scripts/login_and_cache.py 实现缓存校验/刷新富结果状态机 `check_cache(fields, *, notify) -> CacheCheckResult`（`CacheCheckStatus` 六态：VALID / REFRESHED / EXPIRED_NO_MATERIAL / REFRESH_FAILED / NETWORK_ERROR / NO_CACHE）：联网 check_valid / refresh 在独立事件循环执行并关闭客户端会话；过期缺 ac_time_value 删缓存；刷新成功回写缓存；NETWORK_ERROR 保留缓存（data-model.md E3 状态机、contracts/module-api.md 契约）
- [x] T010 [US2] 重写 tests/conftest.py：删除登录流程实现（`_qrcode_login_flow` / `_phone_login_flow` / `_complete_geetest` / `_show_qrcode` / `_run_temp_login` / `_check_cache_valid` / `_refresh_credential` / `_resolve_cache_usable_fields` 及不再需要的导入），改为 `from scripts.login_and_cache import run_temp_login, check_cache, ...`；`_notify` / `_prompt` 保留为注入包装传入接缝；`pytest_sessionstart` / `credential` fixture 语义不变（fresh_fields 优先；check_cache 映射：NETWORK_ERROR → pytest.skip 保留缓存，EXPIRED_NO_MATERIAL / REFRESH_FAILED → warnings.warn，NO_CACHE → 回退链续行）；保留 pytest_addoption / pytest_collection_modifyitems / test_env / ratelimit 与模块 docstring 更新
- [x] T011 [P] [US2] 扩展 tests/test_offline_login_and_cache.py：`check_cache(None)` 无网络路径返回 NO_CACHE、`CacheCheckStatus` 六态枚举完备、`CacheCheckResult` 缺省字段形态（contracts/module-api.md）；运行该文件全绿

**Checkpoint**: `uv run pytest -m "not integration"` 与 `uv run pytest --collect-only` 正常；真机 quickstart 场景 5 通过（US1 + US2 均独立可用）

---

## Phase 5: User Story 3 - 两种入口共享统一的缓存与刷新逻辑 (Priority: P3)

**Goal**: 脚本入口与测试入口对缓存的处理结果与消息语义一致，无双实现漂移

**Independent Test**: 构造过期缓存后分别从两入口触发刷新，结果与提示一致（quickstart 场景 6）

### Implementation for User Story 3

- [ ] T012 [US3] 真机执行 quickstart 场景 6：构造过期凭据缓存（含 / 不含 ac_time_value 两种），分别经脚本入口与 `--login` / 普通测试入口触发，核对刷新回写与清理删除两路径的处理结果、消息语义一致；发现不一致仅做消息文本级对齐修正（scripts/login_and_cache.py 或 tests/conftest.py）
	- SKIP 待真机：需真实过期凭据与人工触发，自动化环境不可执行；R8 消息锚点核对（T013）已覆盖消息语义层面
- [x] T013 [P] [US3] 对照 research.md R8 基线清单做行为回归核对：`--login` 四类中止提示文本、缓存 absent / corrupt 处理、凭据回退链与字段级合并、输出无凭据值（FR-005/FR-006，覆盖脚本与 `--login` 两入口）；核对可对照 git 历史中迁移前的 tests/conftest.py 实现

**Checkpoint**: 全部用户故事完成，两入口行为一致（US3 验收场景 1/2 可复现）

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: 跨故事收尾

- [x] T014 [P] 在 AGENTS.md 的「测试」章节补充独立登录脚本一行说明（`uv run python scripts/login_and_cache.py qrcode|phone`，成功后凭据入 TEMP 缓存供测试复用），保持既有凭据来源优先级描述不变
- [x] T015 运行完整门禁并全绿：`uv run pytest -m "not integration"` + `uv run python scripts/lint.py`（SC-005）
	- 完成：268 passed / 2 skipped（跳过为既有条件跳过）；lint.py 全绿，另按棘轮提示下调 bad-index 286→280、unsupported-operation 186→184（bilibili_api 零改动，存量自然下降）
- [x] T016 按 quickstart.md 逐场景终验（真机场景按凭据可用性执行；至少完成场景 1/2 全自动项），勾选核对验收对照表
	- 完成：场景 1（离线 + 门禁）与场景 2（无参用法、退出码 2）已验证；场景 3–6 为真机项，本机无可扫账号，留待真机验收

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: 无依赖，立即开始
- **Foundational (Phase 2)**: 依赖 T001（T003 的模块文件需 T201 豁免先注册以保门禁绿）；T003 依赖 T002（re-export 目标必须先就位）——**阻塞所有用户故事**
- **US1 (Phase 3)**: 依赖 Phase 2；T004→T005→T006→T007 同文件按序，T008 依赖 T006/T007
- **US2 (Phase 4)**: 依赖 US1（conftest 导入的 run_temp_login 必须已存在）；T010 依赖 T009；T011 依赖 T009，可与 T010 并行
- **US3 (Phase 5)**: 依赖 US1 + US2（两入口均已迁移后才有"一致性"可验）
- **Polish (Phase 6)**: 依赖全部用户故事完成

### User Story Dependencies

- **US1 (P1)**: Foundational 后即可独立实施与验收（旧 conftest 不受影响，`--login` 行为全程不变）
- **US2 (P2)**: 依赖 US1 的模块 API；交付后 FR-003/FR-004/FR-007 全部成立
- **US3 (P3)**: 依赖 US1 + US2；属质量核验，失败时仅允许消息级对齐修正

### Parallel Opportunities

- T008 与 T004–T007 的后续收尾可并行（不同文件）；T011 与 T010 并行（不同文件）；T013 与 T012 并行（不同验收维度）；T014 与 T015 并行
- 同文件任务（T004–T007、T009–T010）严禁并行

---

## Parallel Example: User Story 2

```bash
# T009 完成后，以下两任务可并行（不同文件）：
Task: "T010 重写 tests/conftest.py（导入脚本模块，语义不变）"
Task: "T011 扩展 tests/test_offline_login_and_cache.py（check_cache 离线用例）"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. T001 → T002 → T003（基础就绪）
2. T004–T008（US1 完成）
3. **STOP and VALIDATE**: quickstart 场景 2/3/4——独立脚本已可用，测试运行照常（旧 conftest 逻辑未动）
4. 此时已可交付使用；US2/US3 属迁移收尾

### Incremental Delivery

1. 基础 → US1（MVP，独立脚本可用）→ US2（conftest 瘦身，FR-007 达成）→ US3（一致性核验）→ Polish
2. 每阶段一个逻辑提交组（遵循 Conventional Commits 与"一个提交只做一件事"）：
   - `refactor(login): 平移纯缓存逻辑至 scripts/_login_cache`（T002）
   - `feat(scripts): 新增独立登录凭据脚本 login_and_cache`（T003–T008）
   - `refactor(tests): conftest 登录流程迁移至脚本模块`（T009–T011）
   - `docs: 补充独立登录脚本说明`（T014）

### Notes

- 全程以 research.md R8 为行为兼容基线；任何可观察行为变化（除新增 CLI 外）都视为回归
- 真机任务（T012）无法自动化，凭据不可用时记录 SKIP 并在交付说明中注明
- 库代码 `bilibili_api/` 全程零改动；doc_gen / pyrefly / docs 漂移不受影响
