# Tasks: 集成测试按重要程度分级重构（凭证账号保护）

**Input**: Design documents from `/specs/007-credential-test-tiers/`

**Prerequisites**: plan.md ✓ spec.md ✓ research.md ✓ data-model.md ✓ contracts/test-tier-selection.md ✓ quickstart.md ✓（.specify/memory/constitution.md 已核对）

**Tests**: 本特性对象即测试套件本身；各故事自带独立验证任务（对应 quickstart V1–V7），另为 conftest 收集排除 / 漏标防护逻辑新增一个离线单测任务（T043，符合项目 test_offline_* 惯例与宪法 IV）。

**Organization**: 按用户故事分阶段（US1 cred0 冒烟 → US2 cred1 读回归 → US3 cred2 写生命周期 → US4 cred3 门控 → US5 顺序无关 → US6 默认限速），映射底稿为 data-model.md 权威分层映射表。

## Format: `[ID] [P?] [Story] Description`

- **[P]**: 可并行（不同文件、无未完成依赖）
- **[Story]**: 归属用户故事（US1–US6）
- 每个任务含精确文件路径

## Path Conventions

单项目结构：改造收敛于 `tests/`、`pyproject.toml`、`AGENTS.md`、`.github/workflows/ci.yml`（见 plan.md Project Structure）。

---

## Phase 1: Setup（共享基础设施）

**Purpose**: 分层标记体系就位

- [x] T001 [P] 在 `pyproject.toml` 的 `[tool.pytest.ini_options] markers` 注册 cred0 / cred1 / cred2 / cred3 四个 marker（描述文案照抄 `specs/007-credential-test-tiers/contracts/test-tier-selection.md` §1），运行 `uv run pytest --markers` 确认四个 marker 注册生效且无 PytestUnknownMarkWarning

---

## Phase 2: Foundational（阻塞性前置）

**Purpose**: 所有故事共用的 conftest 基础设施

**⚠️ CRITICAL**: 本阶段完成前不得开始任何用户故事阶段

- [x] T002 在 `tests/conftest.py` 的 `pytest_collection_modifyitems` 中实现漏标与错标防护（FR-001，contracts §4）：经 `item.fixturenames` 传递闭包识别需凭据用例（闭包含模块级 fixture 对 credential 的间接依赖），收集期检查——未携带任一 cred 标记、或携带多个 cred 标记（违反"恰好一层"）均发 UserWarning（消息含文件与用例名、不含凭据值）；`BILI_STRICT_TIERS=1` 时升级为收集错误中止会话。收集期实现保证 `--collect-only` 下同样生效（T051 依赖）。过渡期说明：分层标注分阶段进行，中间态告警噪音属预期，严格模式仅在 Phase 9 终态启用
- [x] T003 在 `tests/conftest.py` 实现请求计数器与风控响应统计（contracts §6）：`BILI_COUNT_REQUESTS=1` 时在请求客户端抽象层挂钩 per-send 计数——计数口径为服务端视角全计数（对 bilibili 域名实际发送的每次 HTTP 请求计 1，含重试每次尝试与反爬参数预取；凭据链校验/刷新请求计入总数；WebSocket 连接建立计 1、连接内消息与心跳不计），会话结束时经 terminal writer 在终端摘要输出总计数与域名维度汇总（禁用 print，遵守宪法 III）；同时统计 412 类风控响应（HTTP 412 状态码与 -352 等效风控错误码）并在摘要单列输出；`BILI_ABORT_ON_RISK=1` 时首个 412 类响应即中止整个会话（FR-005"发生即中止"的执行机制，中止开关独立于计数开关）；缺省关闭零开销

**Checkpoint**: 标记已注册、漏标可发现、请求可计数——故事阶段可开始

---

## Phase 3: User Story 1 - 一条命令跑通核心冒烟层 (Priority: P1) 🎯 MVP

**Goal**: cred0 核心冒烟层就位：`uv run pytest -m cred0` 单命令全绿（spec US1 / FR-004）

**Independent Test**: `BILI_COUNT_REQUESTS=1 uv run pytest -m cred0` 全部通过、零写操作、计数器读数 ≤ 30（quickstart V1）

- [x] T004 [P] [US1] `tests/test_readonly_smoke.py` 附加 cred0 标记（模块级 pytestmark 追加 `pytest.mark.cred0`，保留 readonly 标记不删，FR-013）
- [x] T005 [P] [US1] `tests/test_video.py` 为 get_info / get_pages / get_tags 三个用例加用例级 `@pytest.mark.cred0` 标记（data-model cred0 表）
- [x] T006 [P] [US1] `tests/test_user.py` 为 get_user_info / get_relation_info 两个用例加 `@pytest.mark.cred0`
- [x] T007 [P] [US1] `tests/test_search.py` 为基础搜索用例（test_a）加 `@pytest.mark.cred0`
- [x] T008 [US1] US1 独立验证（quickstart V1 / SC-001）：`BILI_COUNT_REQUESTS=1 uv run pytest -m cred0` 全绿、除缺凭据外零跳过、读数 ≤ 30，结果记录于 `specs/007-credential-test-tiers/quickstart.md` 验收核对表

**Checkpoint**: MVP 达成——单账号下核心冒烟层一条命令稳定全绿

---

## Phase 4: User Story 2 - 核心读回归层全绿 (Priority: P2)

**Goal**: cred1 读回归层就位：cred0+cred1 累加运行全绿、零 412、≤400 请求（spec US2 / FR-005）

**Independent Test**: `BILI_COUNT_REQUESTS=1 uv run pytest -m "cred0 or cred1"` 全绿零 412、读数 ≤ 400、≤30 分钟（quickstart V2；最终验收以默认限速执行，见 T048 后复跑）

⚠️ 重构期间安全提示：在 T036（cred3 收集排除）落地前，验证一律带 `-m` 选择运行，禁止不带 `-m` 的默认全量运行（高危用例尚未门控）

- [x] T009 [US2] `tests/test_video.py` 其余全部读用例加 `@pytest.mark.cred1`（弹幕 view/list/history/xml/snapshot/index、pbp、字幕、related、chargers、has_liked、get_pay_coins、has_favoured、relation、online、snapshot、get_cid_info；写用例留待 US3/US4 不动）
- [x] T010 [P] [US2] `tests/test_user.py` 其余全部读用例（约 39 个）加 `@pytest.mark.cred1`
- [x] T011 [P] [US2] `tests/test_dynamic.py` 全部读用例加 `@pytest.mark.cred1`（set_like 留 US3）
- [x] T012 [P] [US2] `tests/test_live.py` 全部读用例加 `@pytest.mark.cred1`（写用例留 US3/US4）
- [x] T013 [P] [US2] `tests/test_comment.py` get_comments 加 `@pytest.mark.cred1`；`tests/test_favorite_list.py` 全部读接口加 `@pytest.mark.cred1`（生命周期留 US3）
- [x] T014 [P] [US2] `tests/test_session.py` 九个读接口加 `@pytest.mark.cred1`（send_msg 留 US4）
- [x] T015 [P] [US2] `tests/test_search.py` 其余 8 个用例与 `tests/test_note.py` 全部 6 个用例加 `@pytest.mark.cred1`
- [x] T016 [P] [US2] `tests/test_homepage.py`（顺手删除 test_d 中对 get_popularize 的重复调用）、`tests/test_app.py`、`tests/test_show.py` 全部用例加 `@pytest.mark.cred1`
- [x] T017 [P] [US2] `tests/test_article.py` / `tests/test_audio.py` / `tests/test_topic.py` / `tests/test_video_tag.py` / `tests/test_manga.py` 各自读用例加 `@pytest.mark.cred1`（写用例留 US3/US4）
- [x] T018 [P] [US2] `tests/test_interactive_video.py` 读用例加 `@pytest.mark.cred1`，图遍历用例循环体内加 `await asyncio.sleep(0.5)` 节流（research R8；mark_score 留 US3）
- [x] T019 [US2] `tests/test_rank.py`：其余用例加 `@pytest.mark.cred1`；test_a 由 24 个 RankType 全遍历改为采样 5 个代表分区（含默认 + 边缘类型）；test_j 采样 3 个漫画榜；get_music_rank_list 与 phase 消费链合并为单用例（消除 phase_id 全局依赖）；全部循环体内加 0.5s 节流（subscribe_music_rank 留 US4）
- [x] T020 [US2] `tests/test_root_functions.py`：parse_link 用例由约 40 个 URL 采样为 20 个代表性形态、循环内加 0.5s 节流，两用例加 `@pytest.mark.cred1`（research R8）
- [x] T021 [P] [US2] `tests/test_ass.py` 生成的本地文件（.ass/.srt/.lrc/.json）改用 pytest `tmp_path` 写入，不再污染仓库工作目录（research R10）
- [x] T022 [P] [US2] `git mv tests/test_initial_state.py tests/test_offline_initial_state.py`——纯本地解析用例离线化，摘除 integration 标记与限速（宪法 IV 修正，research R10）
- [x] T023 [US2] US2 独立验证（quickstart V2 / SC-002 / SC-007）：`BILI_COUNT_REQUESTS=1 BILI_ABORT_ON_RISK=1 uv run pytest -m "cred0 or cred1"` 全绿、摘要 412 类风控计数 = 0（含 -352 等效码，FR-005 全统计口径；任一发生则会话已中止、该次运行判为验收失败）、读数 ≤ 400；T047 完成后以默认限速复跑确认时长 ≤ 30 分钟

**Checkpoint**: 冒烟 + 读回归两层全绿，重要读覆盖收敛到预算内

---

## Phase 5: User Story 3 - 写操作生命周期层自清理 (Priority: P3)

**Goal**: cred2 写生命周期层就位：每个写用例配对恢复 + teardown 级清理义务，六态零残留（spec US3 / FR-006 / FR-008 / FR-009）

**Independent Test**: cred0–cred2 累加运行全绿；运行前后账号六态（关注/收藏/点赞/评论/弹幕/稍后再看）逐项比对零差异（quickstart V3）

teardown 义务（FR-006，适用于本阶段全部生命周期任务）：无论用例成功、失败、超时或中断，清理步骤 MUST 照常运行；清理失败有限重试后输出含具体残留物的警告

- [x] T024 [P] [US3] `tests/test_comment.py` 评论链（send→reply→like→hate→delete）合并为单个生命周期用例并加 `@pytest.mark.cred2`：目标运行时动态解析自有视频（`get_self_info` 取 mid → `User(mid).get_videos()` 取首个 aid，禁硬编码，缺失则条件跳过并说明原因——FR-008，替换现行 av271 目标）；消除 comment_id 全局变量
- [x] T025 [P] [US3] `tests/test_favorite_list.py` 收藏夹链（create→set_favorite→modify→copy→move→clean→delete）合并为单个生命周期用例并加 `@pytest.mark.cred2`；消除 media_id / default_media_id 全局变量
- [x] T026 [P] [US3] `tests/test_watchroom.py` 观影房链（create→join→share→progress→close→send msgs）合并为单个生命周期用例并加 `@pytest.mark.cred2`；消除 room 全局变量
- [x] T027 [P] [US3] `tests/test_video.py` 写用例改造并加 `@pytest.mark.cred2`：like(True/False)、set_favorite add/remove、add_to_toview/delete_from_toview 三组各自成配对单用例；report_watch_history、report_start_watching 标 cred2（自身状态类白名单，用例注释成文依据）
- [x] T028 [P] [US3] `tests/test_user.py` modify_relation 订阅→取关闭环单用例加 `@pytest.mark.cred2`（消除对后续用例的顺序依赖注释）
- [x] T029 [P] [US3] `tests/test_article.py` set_like(True/False) 与 set_favorite(True/False)（补取消收藏调用）配对单用例加 `@pytest.mark.cred2`；add_coins 留 US4
- [x] T030 [P] [US3] `tests/test_topic.py` like on/off 与 fav on/off 配对单用例加 `@pytest.mark.cred2`
- [x] T031 [P] [US3] `tests/test_video_tag.py` subscribe/unsubscribe、`tests/test_manga.py` follow(True/False) 配对单用例加 `@pytest.mark.cred2`
- [x] T032 [P] [US3] `tests/test_dynamic.py` set_like(True/False)（补取消点赞调用）配对单用例加 `@pytest.mark.cred2`
- [x] T033 [P] [US3] `tests/test_live.py` sign_up_dahanghai 与 receive_reward 加 `@pytest.mark.cred2`（自身状态类白名单，用例注释引用 data-model 安全策略表）
- [x] T034 [P] [US3] `tests/test_interactive_video.py` mark_score 加 `@pytest.mark.cred2`（自身状态类白名单注释）
- [x] T035 [US3] US3 独立验证（quickstart V3 / SC-003）：运行前采集六态基线 → `uv run pytest -m "cred0 or cred1 or cred2"` 全绿 → 运行后逐项比对六态零残留

**Checkpoint**: 三层常规验证（cred0–cred2）完整，账号状态可完全恢复

---

## Phase 6: User Story 4 - 高危操作显式门控 (Priority: P4)

**Goal**: cred3 高危层默认收集即排除，仅显式点名可执行（spec US4 / FR-003 / FR-007）

**Independent Test**: 默认 `--collect-only` 收集结果 cred3 用例数 = 0 且终端出现剔除计数提示行；`-m cred3` 时正常收集（quickstart V4；验收不真机执行 cred3）

⚠️ 执行顺序红线：T036（收集排除逻辑）MUST 先于本阶段全部标注任务落地，防止标注后默认运行仍执行高危用例

- [x] T036 [US4] `tests/conftest.py` 实现 cred3 收集期排除（contracts §3）：在现有 `pytest_collection_modifyitems` 中新增规则——`config.option.markexpr` 含 token `cred3` 时保留，否则收集阶段剔除（deselect，非 skip）全部 cred3 用例，并经 terminal writer 输出一行剔除计数提示（如"已排除 N 个 cred3 高危用例（显式执行：pytest -m cred3）"）。同钩子内执行顺序：T002 的漏标/错标检查 MUST 先于本剔除规则，保证被剔除的 cred3 用例标注同样受检（T051 依赖）
- [x] T037 [P] [US4] `tests/test_video.py` send_danmaku、pay_coin、triple 加 `@pytest.mark.cred3`（无删除配对 / 资源消耗类，data-model 安全策略表）
- [x] T038 [P] [US4] `tests/test_live.py` 高危组加 `@pytest.mark.cred3`：弹幕发送 ×2、金/银/背包礼物、人气票、create_live_reserve；get_black_list→ban→unban 链（black_list 全局变量）合并为单用例后标 cred3
- [x] T039 [P] [US4] `tests/test_session.py` send_msg 加 `@pytest.mark.cred3`
- [x] T040 [P] [US4] `tests/test_creative_center.py` 整文件加模块级 `pytestmark = pytest.mark.cred3`（身份特定类，FR-007）
- [x] T041 [P] [US4] `tests/test_rank.py` subscribe_music_rank、`tests/test_user.py` clear_toview_list 与 delete_viewed_videos_from_toview 加 `@pytest.mark.cred3`（公开发布无清理 / 破坏性类）
- [x] T042 [P] [US4] `tests/test_vote.py` create→update 合并为单用例（消除 vote_id 全局依赖）并加 `@pytest.mark.cred3`（无删除 API）
- [x] T043 [P] [US4] 新增 `tests/test_offline_cred_tier_selection.py` 离线单测：构造带/不带 cred3 标记的收集项 × markexpr 含/不含 cred3 的四象限断言 deselect 行为与剔除计数；漏标（零 cred 标记）与错标（多 cred 标记）防护判定逻辑（不触网、不依赖真实凭据，符合宪法 IV 离线层边界）
- [x] T044 [US4] US4 独立验证（quickstart V4 / SC-004）：默认 `uv run pytest --collect-only -q` 输出剔除计数提示行（N > 0）；`uv run pytest -m cred3 --collect-only -q` 收集数恰为 N，两者互证"收集即排除"（收集节点 ID 不含 marker 名，禁用 `grep -c cred3` 口径）

**Checkpoint**: 高危操作与常规路径物理隔离，默认运行物理安全

---

## Phase 7: User Story 5 - 顺序无关、任意子集可独立运行 (Priority: P5)

**Goal**: 跨用例全局变量依赖清零，任意子集单跑可过（spec US5 / FR-009）

**Independent Test**: 生命周期用例与各层抽样用例 `-k` / 文件级单跑 100% 通过（quickstart V5）

- [x] T045 [US5] 全局变量依赖终检：`grep -n` 扫描 `tests/*.py` 中残留的模块级可变资源 ID（comment_id / media_id / default_media_id / room / vote_id / phase_id / black_list），逐一确认已在 US3/US4/US2 阶段消除或就地收敛，清理残留引用
- [x] T046 [US5] US5 独立验证（quickstart V5 / SC-005）：单跑评论生命周期、收藏夹生命周期、watchroom 生命周期用例 + 从 cred0/cred1/cred2 各抽 2 个普通用例以 `-k` 单跑，全部通过

**Checkpoint**: 子集运行与层级选择任意组合均不因顺序依赖失败

---

## Phase 8: User Story 6 - 凭据用例默认安全限速 (Priority: P6)

**Goal**: 默认间隔非零安全值，覆盖语义保留（spec US6 / FR-010）

**Independent Test**: 不设环境变量时相邻凭据用例存在默认间隔；`BILI_RATELIMIT=0` 覆盖后间隔消失（contracts §5）

- [x] T047 [US6] `tests/conftest.py` 将 `RATELIMIT` 缺省值由 0 改为 1.5（`float(os.getenv("BILI_RATELIMIT", 1.5))`，显式设置含 0 照常生效）；同步更新文件头部 docstring 说明默认值与覆盖语义（research R3）
- [x] T048 [US6] US6 独立验证：不设 env 运行 `uv run pytest -m cred0` 观察相邻用例间默认间隔生效（对照运行时长）；设 `BILI_RATELIMIT=0` 复跑确认覆盖生效；随后以默认限速复跑 T023 口径确认 cred0+cred1 ≤ 30 分钟（SC-002 时长项）

**Checkpoint**: 裸跑环境（无任何 env）下风控安全有默认保障

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: 文档、CI、门禁与全量验收

- [x] T049 [P] 重写 `AGENTS.md` 测试节（FR-014）：四级体系与各级判据、命令矩阵（照抄 contracts §2）、账号安全策略五类判定表 + 白名单治理（封闭枚举/证据义务/从严回退，照抄 data-model）、限速默认 1.5 与覆盖、请求计数口径、已知集成覆盖缺口条目（login_v2 集成、视频上传链路——spec Assumptions 指定的追踪去向）
- [x] T050 [P] 核对 `.github/workflows/ci.yml`：readonly 任务行为不变（`pytest -m readonly`）；schedule/manual 的 integration 任务改用 `pytest -m "cred0 or cred1 or cred2"` 口径（保持可回退注释）
- [x] T051 以 `BILI_STRICT_TIERS=1 uv run pytest --collect-only -q` 终态检查零漏标与零错标（FR-001"恰好一层"严格门禁；收集期检查对全部用例生效——含被剔除的 cred3 用例，无需凭据与网络，退出码 0 即通过）
- [x] T052 运行 `uv run python scripts/lint.py` 全绿（宪法 III 强制门禁：ruff check / format / tests-scripts 阻断检查 / pyrefly / 文档漂移）
- [x] T053 全量验收：按 `specs/007-credential-test-tiers/quickstart.md` V1–V7 逐场景执行，结果回填验收核对表（SC-001 ~ SC-007 全项），V4 采用收集口径不真机执行 cred3
- [x] T054 [P] 映射表漂移终检：以 `grep -c "pytest.mark.cred" tests/*.py` 统计各文件标注数，与 `specs/007-credential-test-tiers/data-model.md` 权威分层映射表逐文件比对，修正任一侧漂移

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: 无依赖，立即开始
- **Foundational (Phase 2)**: 依赖 Phase 1；阻塞全部用户故事
- **US1 (Phase 3)**: 依赖 Phase 2（标记注册 + 计数器供验证用）
- **US2 (Phase 4)**: 依赖 Phase 2；标注可与 US1 并行（不同文件），验证建议在 US1 后（累加命令含 cred0）
- **US3 (Phase 5)**: 依赖 Phase 2；文件与 US2 重叠（video/user/live 等混合文件），同文件任务须串行
- **US4 (Phase 6)**: 依赖 Phase 2；**T036 收集排除逻辑 MUST 先于本阶段任何 cred3 标注**（安全红线）；此前各阶段验证一律带 `-m` 选择运行
- **US5 (Phase 7)**: 依赖 US2/US3/US4 的合并与改道完成（其验证对象正是这些改造）
- **US6 (Phase 8)**: 仅依赖 Phase 2（conftest）；可与其后任意阶段并行，但 US2 的时长验收（T048 末步）依赖本阶段
- **Polish (Phase 9)**: 依赖全部故事完成

### User Story Dependencies

- US1 → US2 → US3 为递进交付（层选择累加验证），US4 可与 US2/US3 并行推进（不同用例组），US5 汇总验证依赖前四者，US6 独立基础设施
- 实施顺序建议（单人）：T001–T036 严格顺序推进 → T037 之后同阶段内 [P] 任务可并行 → US5 → US6 → Polish

### Parallel Opportunities

- Phase 3：T004–T007 四个文件互不重叠，可并行
- Phase 4：T010–T018 多数文件互不重叠（T009/T019/T020 同文件改造较大宜独占），可分组并行
- Phase 5：T024–T034 各任务文件互不重叠，可并行
- Phase 6：T036 完成后 T037–T043 全部可并行
- Phase 9：T049/T050/T054 与 T051/T052 可并行

---

## Parallel Example: Phase 6（T036 落地后）

```text
Task: "T037 test_video.py send_danmaku/pay_coin/triple 标 cred3"
Task: "T038 test_live.py 高危组标 cred3 + black_list 链合并"
Task: "T039 test_session.py send_msg 标 cred3"
Task: "T040 test_creative_center.py 整文件标 cred3"
Task: "T041 rank/user 破坏性与残留用例标 cred3"
Task: "T042 test_vote.py 合并单用例标 cred3"
Task: "T043 新增 tests/test_offline_cred_tier_selection.py"
```

---

## Implementation Strategy

### MVP First（User Story 1 Only）

1. Phase 1 + Phase 2（标记注册 + 漏标防护 + 计数器）
2. Phase 3（cred0 12 用例标注）
3. **STOP and VALIDATE**: `BILI_COUNT_REQUESTS=1 uv run pytest -m cred0` 全绿 ≤30 请求——单账号核心冒烟层交付

### Incremental Delivery

1. MVP（cred0）→ 2. cred1 读回归全绿 → 3. cred2 六态零残留 → 4. cred3 物理隔离 → 5. 子集任意可跑 → 6. 默认限速安全 → 7. 文档 / CI / 门禁 / 全量验收

### 单人顺序执行

严格按 T 编号推进；每个 Checkpoint 停下做独立验证后再前进。

---

## Notes

- [P] = 不同文件且无未完成依赖；同文件多任务（如 conftest 的 T002/T003/T036/T047、test_video 的 T005/T009/T027/T037）须串行
- 提交粒度（宪法 V）：一个提交只做一件事——建议按 Phase 分组提交（test / chore 类型），改造与文档分开
- 凭据红线：任何任务不得在提交内容或日志输出凭据值（宪法 IV / 技术安全约束）
- 验收运行环境口径（SC-002）：默认限速 + 单一共享账号；cred3 永不真机执行
- `tests/conftest.py` 的既有凭据装配链（--login > TEMP 缓存 > BILI_* > .bilibili.cookie）与缺凭据 skip 语义全程不动
- 离线套件行为基线：T022 更名后 `uv run pytest -m "not integration"` 用例数 +2（原 initial_state 2 个并入），其余结果应与重构前一致

---

## Phase 10: Convergence

**Purpose**: $speckit-converge 差距收敛（2026-09-26，实现与 V1–V7 验收完成后的独立核验产出；核验证据：严格模式收集检查零漏标零错标、535/572 收集 + 37 个 cred3 剔除、离线套件 281 通过 0 失败）

- [X] T055 补齐 8 个配对型 cred2 写用例的 teardown 级清理义务与恢复断言 per FR-006 / US3 / 检查单 CHK021 裁决（partial）：`tests/test_video.py`（点赞 on/off、稍后再看增删）、`tests/test_article.py`（set_like / set_favorite）、`tests/test_dynamic.py`（set_like）、`tests/test_topic.py`（like / set_favorite）、`tests/test_video_tag.py`（订阅 / 取消）、`tests/test_manga.py`（set_follow_manga）、`tests/test_user.py`（modify_relation 订阅 / 取关）——恢复调用移入 try/finally（或经 conftest 的 teardown_retry），恢复结果加断言或失败时明确残留警告；参照已达标的 `tests/test_video.py` set_favorite 用例（双向断言）与三个生命周期用例（try/finally + teardown_retry）写法
- [X] T056 修正 `tests/test_live.py` 直播预约用例名实不符 per T038（partial）：test_ze_get_following_live 实际调用 create_live_reserve（重构遗留旧名），改名为 test_zf_create_live_reserve 或按意图恢复 following 读取断言为独立用例
- [X] T057 修正 `tests/test_user.py` test_l_User_get_followings 调用错位 per US2 读回归覆盖（unrequested）：用例名为 get_followings 实际调用 get_followers()，followings 接口在 cred1 层未被真实行使，修正调用为 get_followings 并核对返回结构断言
- [X] T058 去除 `tests/test_creative_center.py` test_m / test_n 完全重复用例 per 宪法 IV 分层测试质量（unrequested）：两用例逐字重复，合并为单用例，保持 cred3 模块标注不变

---

## Phase 11: Convergence

**Purpose**: $speckit-converge 二轮收敛（2026-09-26，T055–T058 完成提交 218de80 后的独立核验产出；核验证据：四项收敛任务实施达标、严格模式收集零漏标零错标、535/571 收集 + 36 个 cred3 剔除、lint.py 全量门禁全绿）

- [ ] T059 复跑受 T055 / T057 影响的验收使 SC-002 / SC-003 在最终代码上闭合 per SC-002 / SC-003（partial）：V2 / V3 验收记录基于改动前用例体，8 个 cred2 配对用例（新增恢复断言与 changed 标志位）与 1 个 cred1 用例（test_l_User_get_followings 新增 list 结构断言）改造后未复跑；V3 期间已两次遭遇状态传播延迟类问题（评论根索引延迟、live 504），新增断言（如点赞后立即 has_liked 读回）存在同类抖动风险——以默认限速运行 `BILI_COUNT_REQUESTS=1 BILI_ABORT_ON_RISK=1 uv run pytest -m "cred0 or cred1 or cred2"` 全绿（V3 口径含六态零残留抽查），结果回填 quickstart.md 验收记录（V2 / V3 追加复跑条目，注明基于 218de80 后代码）
- [X] T060 同步 data-model.md cred3 权威映射表与代码现状 per FR-002 / T054 映射表双向不漂移义务（partial）：cred3 节缺 `test_article.py` add_coins（资源消耗类，research R7）与 `test_audio.py` add_coins（资源消耗类，research R7）两行；`test_creative_center.py` 行 "整文件（19 用例）" 应更正为 18（T058 去重后）——代码侧归层均正确（用例注释已引据），仅权威表漂移
