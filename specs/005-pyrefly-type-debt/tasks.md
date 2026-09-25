---
description: "Task list for feature 005-pyrefly-type-debt"
---

# Tasks: 清零 pyrefly 存量类型错误（1064 条）

**Input**: Design documents from `/specs/005-pyrefly-type-debt/`

**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: 未请求新增测试用例；各批次验证消费既有离线用例（`uv run pytest -m "not integration"`）与 quickstart.md 场景。

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each feature slice.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

单项目结构：库源码 `bilibili_api/`，配置 `pyproject.toml`，门禁脚本 `scripts/type_ratchet.py`，验证指南 `specs/005-pyrefly-type-debt/quickstart.md`。批次验收三连（每个清扫批次任务内含，不再重复展开）：

```bash
uv run pyrefly check ./bilibili_api/ --error bad-argument-type,bad-assignment,bad-function-definition,bad-index,bad-override,bad-return,missing-attribute,not-iterable,unsupported-operation --output-format min-text --color never | grep -c "^ERROR"   # 总数下降且逐码无回升
uv run python scripts/lint.py        # 全绿
uv run pytest -m "not integration"   # 全绿
```

某错误码实测归零时：**同批次**删除 `scripts/type_ratchet.py` `BASELINE` 该键 + 删除 `pyproject.toml` `[tool.pyrefly.errors]` 该行 + 复跑门禁（宪法 III，spec FR-003）。批次内预期计数为 2026-09-25 实测参考值，迁移可能使错误在码间转移，以"总数下降且无码回升"为准（research.md R8）。

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: 口径校准，使基线与实测一致（spec 场景 1）

- [X] T001 校准 `scripts/type_ratchet.py` 基线：`bad-argument-type` 69 → 68（实测值，无源码变更）；运行 `uv run python scripts/type_ratchet.py` 确认通过且无下调提示

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: 根因 A 的中心化解法——先建类型化结果访问器，再谈任何模块迁移

**⚠️ CRITICAL**: 未完成 T002/T003 前，不得开始任何模块清扫批次（US2）

- [X] T002 在 `bilibili_api/utils/_api.py` 的 `Api` 类新增类型化结果访问器（`result_dict`，list/str 等姊妹访问器按试点需要增量添加）：内部完成一次 isinstance 中心收窄（cast 处附误报/收窄依据注释，research.md R2）；`request()`/`result` 原样保留；完整中文 docstring（Args/Returns/Raises）+ 全面类型注解；跑批次验收三连
- [X] T003 [P] 试点批次：全量清理 `bilibili_api/emoji.py`（7 条，含 `credential: Credential = None` 注解修正）、`bilibili_api/hot.py`（5 条）、`bilibili_api/music.py`（1 条）——调用点迁移到访问器，验证 T002 设计可用；预期 bad-function-definition 降至 14；批次验收三连

**Checkpoint**: 地基就绪，访问器 API 经试点验证；模块清扫可开始（顺序执行，见依赖说明）

---

## Phase 3: User Story 2 - 按批次推进棘轮（模块清扫） (Priority: P1)

**Goal**: 60 文件存量逐批清零，每批独立门禁绿 + 棘轮下降（spec User Story 2 / FR-002/FR-006）

**Independent Test**: 每批跑批次验收三连；总计数严格下降且无任何错误码回升

**执行规则**：批次按下列顺序**串行**执行（每批都要编辑 `scripts/type_ratchet.py` 基线，文件冲突不可并行）；每文件**一次触碰**完成"调用点迁移 + 该文件根因 B/C 修复"（plan.md Structure Decision）；标注"⚠️ 先行提交"的任务须在本批第一个提交完成（独立提交，真 bug/残留码与类型修复分离，spec FR-005/FR-009）。

- [X] T004 [US2] 批次：`bilibili_api/login_v2.py` 全清（73 条；bad-index 55 主体）
- [X] T005 [US2] 批次：`bilibili_api/_live_danmaku.py` 全清（67 条；根因 B——protobuf 解码累加器，异构值类型是设计意图，按开放式形状注解，禁 cast 消音）
- [X] T006 [US2] 批次：`bilibili_api/user.py` 全清（65 条）
- [X] T007 [US2] 批次：`bilibili_api/live.py` 全清（64 条）
- [X] T008 [US2] 批次：`bilibili_api/bangumi.py` 全清（64 条；含 bad-override 15、`year: str = -1` 类注解矛盾 5、cursor 矛盾 ⚠️ 先行提交 T029、not-iterable 2——本批后 not-iterable 仅剩 audio_uploader 的 11 条）
- [X] T009 [US2] 批次：`bilibili_api/video.py` 全清（60 条）
- [X] T010 [US2] 批次：`bilibili_api/video_uploader.py` 全清（53 条；⚠️ 先行提交 T033 `__dict__` 方法处置）
- [X] T011 [US2] 批次：`bilibili_api/dynamic.py` 全清（41 条；⚠️ 先行提交 T030 之 dynamic 形状修正）
- [X] T012 [US2] 批次：`bilibili_api/cheese.py` 全清（38 条；⚠️ 先行提交 T027 漏 await 修复）
- [X] T013 [US2] 批次：`bilibili_api/watchroom.py` 全清（33 条）
- [X] T014 [US2] 批次：`bilibili_api/audio_uploader.py` 全清（31 条；完成后 **not-iterable 应归零 → 成对退役**）
- [X] T015 [US2] 批次：`bilibili_api/utils/geetest.py`（29）+ `bilibili_api/utils/_danmaku_parse.py`（25）全清（根因 B 同族：极验/弹幕解析累加器）
- [X] T016 [US2] 批次：`bilibili_api/creative_center.py`（24）+ `bilibili_api/session.py`（22）全清（session ⚠️ 先行提交 T032 `on` 参数名对齐；creative_center ⚠️ 先行提交 T030 之 keyword 形状修正）
- [X] T017 [US2] 批次：`bilibili_api/favorite_list.py`（20）+ `bilibili_api/article.py`（20）+ `bilibili_api/garb.py`（19）+ `bilibili_api/channel_series.py`（19）全清（channel_series ⚠️ 先行提交 T026 漏 await 修复）
- [X] T018 [US2] 批次：`bilibili_api/rank.py`（18）+ `bilibili_api/interactive_video.py`（17）+ `bilibili_api/video_tag.py`（14）+ `bilibili_api/black_room.py`（14）全清
- [X] T019 [US2] 批次：`bilibili_api/utils/_anti_spider.py`（13）+ `bilibili_api/comment.py`（13）+ `bilibili_api/manga.py`（12）+ `bilibili_api/game.py`（12）+ `bilibili_api/_video_monitor.py`（12）全清（comment ⚠️ 先行提交 T030 之 pictures 形状修正）
- [X] T020 [US2] 批次：`bilibili_api/utils/_credential.py`（11）+ `bilibili_api/search.py`（11）+ `bilibili_api/opus.py`（11）+ `bilibili_api/vote.py`（10）+ `bilibili_api/tools/ivitools/player.py`（10）+ `bilibili_api/homepage.py`（10）全清（search.py 含最后 1 条 bad-function-definition（rank 的 1 条已随 T018 清除）；完成后 **bad-function-definition 应归零 → 成对退役**）
- [X] T021 [US2] 批次：`bilibili_api/video_zone.py`（9）+ `bilibili_api/note.py`（9）+ `bilibili_api/audio.py`（9）+ `bilibili_api/utils/upos.py`（7）+ `bilibili_api/utils/parse_link.py`（6）+ `bilibili_api/topic.py`（6）+ `bilibili_api/clients/HTTPXClient.py`（6）+ `bilibili_api/_video_download.py`（6）全清（upos ⚠️ 先行提交 T028；完成后 **bad-override 应归零 → 成对退役**）
- [X] T022 [US2] 尾批：剩余 15 个小文件全清（38 条）：`utils/initial_state.py`、`utils/aid_bvid_transformer.py`、`utils/utils.py`、`utils/_api.py`、`clients/CurlCFFIClient.py`、`live_area.py`、`utils/user_render_data.py`、`show.py`、`client.py`、`activity.py`、`utils/picture.py`、`utils/AsyncEvent.py`、`utils/_wbi.py`、`clients/AioHTTPClient.py`、`article_category.py`（路径均相对 `bilibili_api/`；完成后 **全部剩余错误码应归零，逐码成对退役**）

**Checkpoint**: 强制全码检查输出 0 条 ERROR；9 个豁免码全部退役

---

## Phase 4: User Story 1 - 门禁恢复全额拦截（终态） (Priority: P1)

**Goal**: 豁免表与棘轮基线清空，类型门禁恢复对全部错误码的默认拦截（spec User Story 1 / FR-010）

**Independent Test**: quickstart.md 场景 4（终态六断言）+ 场景 5（负向拦截）

- [X] T023 [US1] 终态验证与注释终态化：确认各码成对退役动作（含 T022 末批逐码退役）已全部完成后，验证 `scripts/type_ratchet.py` `BASELINE` 为空字典且空基线状态下脚本正常运行通过、`pyproject.toml` `[tool.pyrefly.errors]` 已无条目；将两处表头/模块注释更新为"豁免已退役"现状（退役动作归属各宿主批次执行，本任务只做终验与注释收口，spec FR-010）
- [X] T024 [US1] 负向拦截验证（quickstart 场景 5）：临时注入一条 bad-return（如注解 dict 的函数 `return 1`）→ 默认 `uv run pyrefly check ./bilibili_api/` 报错且 `uv run python scripts/lint.py` 非零退出并指出文件行号；撤销注入后恢复全绿
- [X] T025 [US1] 终态全量验证（quickstart 场景 4 六条断言逐项执行并记录结果）

---

## Phase 5: User Story 3 - 真 bug 修复与公共 API 兼容 (Priority: P2)

**Goal**: 类型错误背后的运行时 bug 独立修复；公共 API 零破坏（spec User Story 3 / FR-005）

**Independent Test**: 每项修复独立提交后离线测试全绿；quickstart 场景 3 签名抽查无收窄

**执行时机**：本组任务在 Phase 2 完成后即可并行启动（文件互不相同），但**必须不晚于其宿主文件的清扫批次落地**（依赖表："≤ 批次"），作为该批次第一个提交。

- [X] T026 [P] [US3] 修复 `bilibili_api/channel_series.py:231` 漏 `await`（`ChannelSeries(...).get_meta()["total"]` → 协程直接下标，运行时 TypeError）；独立提交（≤ T017）
- [X] T027 [P] [US3] 修复 `bilibili_api/cheese.py:345` 漏 `await`（`self.get_meta()["duration"] // 360`）；独立提交（≤ T012）
- [X] T028 [P] [US3] 修正 `bilibili_api/utils/upos.py:95` `asyncio.create_task` 参数类型（`Awaitable[dict]` vs `Coroutine`，注解/收窄层面修正，不改行为）（≤ T021）
- [X] T029 [P] [US3] 现场定性与修正 `bilibili_api/bangumi.py:1174/1199` `cursor` int/str 注解矛盾（注解放宽或调用修正，二选一论证后执行，记录到类型层纠错清单）（≤ T008）
- [X] T030 [P] [US3] dict 形状注解修正三处：`bilibili_api/dynamic.py:597-604`（pics/topic/common_card）、`bilibili_api/comment.py:383`（pictures）、`bilibili_api/creative_center.py:672`（keyword）（≤ T011/T019/T016）
- [X] T031 [US3] 公共 API 兼容终审：quickstart 场景 3 签名抽查（`video.Video.get_info` / `user.User.get_videos` / `live.LiveRoom.get_room_info` 等）+ 汇总全程"类型层纠错"清单（data-model: RealBugSplit.compat_impact），确认破坏性变更为零

---

## Phase 6: User Story 4 - 残留码收编与注释清理 (Priority: P3)

**Goal**: 3 条残留码修复归零，KNOWN_RESIDUAL 与配置注释与现状一致（spec User Story 4 / FR-008）

**Independent Test**: 强制全码检查无 bad-override-mutable-attribute / bad-override-param-name；`grep KNOWN_RESIDUAL scripts/type_ratchet.py` 无残留描述

- [X] T032 [P] [US4] `bilibili_api/session.py:465` `Session.on(event_type)` 与父类 `AsyncEvent.on(event_name)` 参数名不一致处置：按 research.md R6 优先序——①对齐 + 兼容垫层（旧参数名吸收进 kwargs + deprecate）→ ②全库检索确认无关键字调用后改名 → ③局部忽略 + 依据注释；独立提交（≤ T016）
- [X] T033 [P] [US4] `bilibili_api/video_uploader.py:322/497` `__dict__` 方法处置：全库检索调用点（实例属性访问走类型槽位，预期死代码）→ 改名 `to_dict()` 或移除；独立提交（≤ T010）
- [X] T034 [US4] 清理 `scripts/type_ratchet.py` `KNOWN_RESIDUAL` 集合与相关注释、`pyproject.toml` 豁免表表头注释中残留码描述（与 T032/T033 同批落地于先行提交窗口：T032/T033 合入后 3 条残留码即归零，无需保留集合与对冲描述）

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: 文档再生、全量验证、交付核查

- [X] T035 运行 `uv run python scripts/doc_gen.py` 再生文档，`git status --short docs/` 确认无漂移（宪法 III；公共符号注解/docstring 已在各批次更新，此处终验）
- [X] T036 走查 quickstart.md 全部场景（0-5）并逐项记录结果；`uv run python scripts/lint.py` 全绿 + `uv run pytest -m "not integration"` 全绿终验
- [X] T037 交付核查：提交序列一事一提交、Conventional Commits 格式（Git Hook 校验）、无凭据泄漏、基线全程无上调（`git log -p scripts/type_ratchet.py` 复核 BASELINE 变更只减不增）、cast/局部忽略纪律抽查（逐处附依据注释，spec FR-004）

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: 无依赖，立即执行
- **Foundational (Phase 2)**: 依赖 T001；T003 依赖 T002；**阻塞所有清扫批次**
- **US2 (Phase 3)**: T004–T022 **严格串行**（每批编辑同一基线文件 `scripts/type_ratchet.py`，不可并行）
- **US3 (Phase 5) / US4 (Phase 6)**: 依赖 Phase 2 完成；组内任务文件互不相同可并行；单项落地时点受"≤ 宿主批次"约束（见各任务）
- **US1 (Phase 4)**: T023 依赖 T022 + T032/T033（残留码归零）；T024/T025 依赖 T023
- **Polish (Phase 7)**: 依赖全部前序阶段

### 推荐执行序列（单人串行）

```text
T001 → T002 → T003
  → T026 T027 T028 T029 T030 T032 T033 → T034
                                          （真 bug + 残留码先行提交窗口：前 7 项文件互异可任意顺序；
                                            T034 编辑 type_ratchet.py/pyproject 注释，紧随 T032/T033 同批收尾）
  → T004 → T005 → … → T022               （模块清扫串行链；对应批次吸收先行提交后的剩余存量）
  → T023 → T024 → T025 → T031
  → T035 → T036 → T037
```

### 退役时点预期（参考，非承诺）

not-iterable @ T014 · bad-function-definition @ T020 · bad-override @ T021 ·
missing-attribute / bad-assignment / bad-argument-type / bad-return / bad-index /
unsupported-operation @ T022 及此前批次陆续归零（实际以逐批实测为准）

### Parallel Opportunities

- T003 单独可并行于 T002 的文档收尾
- T026–T030、T032–T033 七项先行提交窗口：不同文件、无相互依赖，可并行
- 清扫批次之间**不可**并行（基线文件冲突）

---

## Parallel Example: 先行提交窗口

```bash
# Phase 2 完成后，以下任务可并行推进（不同文件，各自独立提交）：
Task: "T026 修复 channel_series.py:231 漏 await"
Task: "T027 修复 cheese.py:345 漏 await"
Task: "T032 session.py on 参数名对齐 + 兼容垫层"
Task: "T033 video_uploader.py __dict__ 方法处置"
```

---

## Implementation Strategy

### MVP First（首个可合入切片）

1. T001 校准 + T002 地基 + T003 试点 → 机制验证（13 条存量消灭，访问器 API 定型）
2. T026/T027 两处漏 await 真 bug 修复 → 下游可用性立即改善
3. **STOP and VALIDATE**: quickstart 场景 1/2/3 走查

### Incremental Delivery

每个清扫批次都是独立可合入增量（门禁绿 + 棘轮下降）；任意时点停下，仓库都处于合法中间态（spec SC-006）。全部批次完成后 US1 终态动作收口。

### 单人节奏

串行链按 T004→T022 推进，每批一个（或一组相邻）提交；先行提交窗口集中在清扫链开始前完成，避免中途切文件。

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- 批次编号映射（research.md R3 / data-model.md 的批次视角）：批次 0=T001（校准）、批次 1=T002（地基）、批次 2=T003（试点）、批次 2..N=T004–T022（模块清扫）、批次 F=T023+T034+T035–T037（终态与收尾）
- 预期计数来自 2026-09-25 实测（research.md 附录）；错误在码间转移属正常，验收看总数与逐码无回升
- cast/Any 纪律：仅中心收窄点（T002）与逐处论证的误报允许，附依据注释（spec FR-004，research.md R5）
- pyrefly 保持 1.2.0 不升级；如必须升级先重测口径（research.md R4）
- Commit after each task or logical group；真 bug / 行为修复与类型修复分提交（宪法 V）
