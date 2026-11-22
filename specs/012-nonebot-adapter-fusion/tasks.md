---
description: "Task list for feature 012-nonebot-adapter-fusion"
---

# Tasks: NoneBot 直播适配器融合

**Input**: Design documents from `/specs/012-nonebot-adapter-fusion/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: 本特性在 spec 中明确要求测试分层（FR-020）与可度量的缺陷回归（SC-010），因此每个用户故事都包含测试任务，且**测试先写**（先失败再实现）。

**Organization**: 任务按用户故事分组，每个故事可独立实现与验收。

## Format: `[ID] [P?] [Story] Description`

- **[P]**: 可与同阶段其它任务并行（不同文件、无未完成依赖）
- **[Story]**: 所属用户故事（US1–US5），Setup / Foundational / Polish 阶段不带此标签
- 所有任务都带确切文件路径

## Path Conventions

沿用 plan.md 的仓库结构（库 + 同仓适配器）：

- 实现代码：`bilibili_api/nonebot/adapters/bilibili_live/`
- 驱动桥接：`bilibili_api/clients/NoneBotClient.py`
- 兼容转发入口：`nonebot/adapters/bilibili_live/__init__.py`
- 测试：`tests/`，帧样本 `tests/fixtures/nonebot_frames/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: 清场、建骨架、把新目录纳入依赖与门禁

- [X] T001 清理历史残留：删除 `bilibili_api/nonebot/adapters/**/__pycache__`、`temp/pkgtest/` 与 `temp/tpl.json`，确认 `git status` 只剩本特性目标文件
- [X] T002 建立目录骨架：`bilibili_api/nonebot/__init__.py`、`bilibili_api/nonebot/adapters/__init__.py`、`bilibili_api/nonebot/adapters/bilibili_live/__init__.py`、`bilibili_api/nonebot/adapters/bilibili_live/models/__init__.py`、`bilibili_api/nonebot/adapters/bilibili_live/pb/__init__.py`
- [X] T003 更新 `pyproject.toml`：新增 `[project.optional-dependencies] nonebot = ["nonebot2>=2.5.0", "betterproto>=1.2.5,<2"]`；`[dependency-groups] dev` 加入同两项（门禁需要能解析导入）；`[tool.setuptools] packages` 追加 `bilibili_api.nonebot`、`bilibili_api.nonebot.adapters`、`bilibili_api.nonebot.adapters.bilibili_live` 及其 `models`/`pb` 子包、`nonebot.adapters.bilibili_live`；`[tool.pyrefly] project-includes` 追加 `nonebot/**`
- [X] T004 更新 `scripts/lint.py`：`ruff check` 与 `ruff format --check` 目标从 `./bilibili_api/` 扩为 `./bilibili_api/ ./nonebot/`（不新增任何 exclude）；随后单独跑一次 `uv run pyrefly check` 验证 pyrefly 能接受 PEP 420 命名空间片段（`nonebot/` 无 `__init__.py`）：若报错，改为在 `[tool.pyrefly] project-includes` 用 `nonebot/adapters/bilibili_live/**` 精确包含，并在 `specs/012-nonebot-adapter-fusion/research.md` 补一条决策记录，**不得**用 `ignore`/`exclude` 绕过
- [X] T005 [P] 搬运 protobuf 生成代码：`pb/{fans_club,interact_word_v2,online_rank_v3,user_dagw}.py` → `bilibili_api/nonebot/adapters/bilibili_live/pb/`；`protos/*.proto` → 仓库根 `protos/`，仅调整相对导入
- [X] T006 [P] 实现 `bilibili_api/nonebot/adapters/bilibili_live/log.py`：适配器 logger 包装 + `redact_credential()`（只允许输出 uid，禁止输出任何凭据字段值，research D12）；同时保证适配器从不调用库的 `request_log.set_on(True)`，并在 `tests/test_offline_nonebot_accounts.py` 增加一条断言：初始化适配器后 `request_log` 仍处于关闭状态

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: 所有用户故事共同依赖的传输、解包与配置基础

**⚠️ CRITICAL**: 本阶段完成前，任何用户故事都无法运行

- [X] T007 实现 `bilibili_api/clients/NoneBotClient.py` 构造与参数映射：`proxy` 空串归一为 `None`、`timeout <= 0` 视为不限、`verify_ssl`/`trust_env` 仅保存并告警、`session` 只接受 `nonebot.drivers.Driver`（contracts/client-bridge.md §2）
- [X] T008 [P] 实现 `bilibili_api/clients/NoneBotClient.py` 的 `request()`：`params` 交给 `Request` 合并、`data` 的 `str/bytes` 走 `content`、`dict` 走 `data`、`files` 手动打开并在 `finally` 关闭且 `filename=basename`、响应 `headers` 键统一小写、`Set-Cookie` 逐条解析为 `cookies`、`url` 取请求 URL（contracts/client-bridge.md §3）
- [X] T009 实现 `bilibili_api/clients/NoneBotClient.py` 的 `download_*`：基于 `driver.stream_request()` 的流式实现，`download_close` 幂等（contracts/client-bridge.md §4；依赖 T008 的同文件改动，故不并行）
- [X] T010 实现 `bilibili_api/clients/NoneBotClient.py` 的 `ws_*`：`AsyncExitStack` 持有 `driver.websocket()`、每句柄接收锁、`receive()` 后按 `str`/`bytes` 分派、关闭码 `1000/1001` → `CLOSED` 其余抛出、WS 超时 `read=None`（contracts/client-bridge.md §5–§6）
- [X] T011 实现客户端注册与驱动能力检测：在 `bilibili_api/nonebot/adapters/bilibili_live/adapter.py` 中经 `register_client("nonebot", NoneBotClient, {...})` 接管选择并记录 INFO；在 `bilibili_api/clients/NoneBotClient.py` 中对缺 `HTTPClientMixin`/`WebSocketClientMixin` 抛 `ArgsException` 且文本含当前驱动名（contracts/client-bridge.md §1、§7；FR-012）
- [X] T012 移植 `bilibili_api/nonebot/adapters/bilibili_live/packet.py`：16 字节头解析、`protover=2` 用 `zlib`、`protover=3` 用 `brotli`，畸形 `length` 直接丢弃不得死循环（data-model.md `DanmakuFrame.length`、`DanmakuFrame.header_length`、`DanmakuFrame.proto_version`、`DanmakuFrame.opcode`、`DanmakuFrame.payload`；`payload` 长度恒为 `length - header_length`）
- [X] T013 [P] 移植 `models/{__init__,event,room,user_manage,open}.py` 与 `message.py` 到 `bilibili_api/nonebot/adapters/bilibili_live/`，仅改导入路径并按 `nonebot2>=2.5.0` 适配
- [X] T014 实现 `bilibili_api/nonebot/adapters/bilibili_live/config.py` 并同步新增 `tests/test_offline_nonebot_config.py`：配置根与每项账号声明、显式字段语义（禁止隐式联合推断），覆盖 data-model.md 校验规则 V-02..V-06、V-10、V-11（V-01 的 cookie 拒绝与迁移文案由 T052 专测，避免重复）；承载约束见 data-model.md `NoneBotLiveConfig.bots`、`NoneBotLiveConfig.max_rooms`、`NoneBotLiveConfig.max_concurrent_connects`、`NoneBotLiveConfig.poll_interval`、`NoneBotLiveConfig.min_poll_interval`、`NoneBotLiveConfig.db_path`、`NoneBotLiveConfig.key_path`、`BotAccountConfig.uid`、`BotAccountConfig.room_ids`；错误文本契约见 contracts/config.schema.md §3
- [X] T015 [P] 实现 `bilibili_api/nonebot/adapters/bilibili_live/exception.py`：适配器自有异常（`AdapterException`/`ActionFailed`/`ApiNotAvailable`/`NetworkError`），能复用库异常类型的直接复用
- [X] T016 [P] 实现 `bilibili_api/nonebot/adapters/bilibili_live/const.py`：端点仅保留 `data/api/live.json` 键名引用与时间常量，删除上游硬编码 URL（research D5）

**Checkpoint**: 传输层、解包、模型、配置就绪，用户故事可并行开工

---

## Phase 3: User Story 1 - 网页弹幕 Bot 代码级平移接入 (Priority: P1) 🎯 MVP

**Goal**: `nonebot.adapters.bilibili_live` 可导入、事件可产出、三处上游缺陷被修掉

**Independent Test**: 离线回放固定帧样本，断言 41 个事件类与两条导入路径对象同一性；不触网、不用凭据

### Tests for User Story 1 ⚠️（先写，先失败）

- [X] T017 [P] [US1] `tests/test_offline_nonebot_events.py::test_public_symbols`：公共符号清单（适配器/Bot/6 基类/41 事件/31 模型/4 异常/2 消息）+ `nonebot.adapters.bilibili_live.X is bilibili_api.nonebot.adapters.bilibili_live.X`（contracts/adapter-public-api.md §1–§2）
- [X] T018 [P] [US1] 帧样本与录制脚本：`scripts/record_nonebot_frames.py`（只读、人工执行、不入 CI）与 `tests/fixtures/nonebot_frames/`（脱敏后按 cmd 分文件，research D13）
- [X] T019 [P] [US1] `tests/test_offline_nonebot_frames.py`：41 个 cmd 一一对应事件类型与关键字段快照；三处缺陷帧（无 `data` 的 `DANMU_MSG`、`SUPER_CHAT_MESSAGE`、带 `is_light` 勋章）必须产出事件（SC-010）；畸形帧/未知 cmd 只记录不中断

### Implementation for User Story 1

- [X] T020 [US1] 移植 `bilibili_api/nonebot/adapters/bilibili_live/event.py`：`@cmd` 注册表、41 个事件类与 validators；`EventEnvelope.cmd` 的 `DANMU_MSG:*` 后缀归一（data-model.md `EventEnvelope.cmd`）
- [X] T021 [US1] 修复缺陷 1：`bilibili_api/nonebot/adapters/bilibili_live/event.py` 的 `packet_to_event` 不再要求顶层 `data` 键，网页 `DANMU_MSG`（`{"cmd":..,"info":[..]}`）正常入事件（FR-010a）
- [X] T022 [US1] 修复缺陷 2：`bilibili_api/nonebot/adapters/bilibili_live/event.py` 中 `SuperChatEvent` 的 `message_id`/`price` 取值不再触发 `KeyError`，中/日文变体均覆盖（FR-010a）
- [X] T023 [US1] 修复缺陷 3：`bilibili_api/nonebot/adapters/bilibili_live/models/event.py` 与 `event.py` 的勋章校验同时接受 `is_light` 与 `is_lighted`，`is_lighted` 为规范字段（FR-010a）
- [X] T024 [US1] 实现 `bilibili_api/nonebot/adapters/bilibili_live/bot.py` 的 `Bot` 基类：`_handle_event`、`_check_to_me`、`get_user_id`/`get_session_id` 等事件取值语义（contracts/adapter-public-api.md §3.2；WebBot 的 API 方法留到 T044）
- [X] T025 [US1] 实现 `bilibili_api/nonebot/adapters/bilibili_live/adapter.py` 房间监听：长短号归一后建连（归一失败按 V-07 标记该房间失败并告警，其余房间继续）、每房间独立任务、帧→事件分发、**建连并发节流**（同时在连握手/鉴权数不超过 `max_concurrent_connects`，用分批或信号量实现）；状态与字段见 data-model.md `RoomSubscription.room_display_id`、`RoomSubscription.room_real_id`、`RoomSubscription.state`、`RoomSubscription.retry_count`、`RoomSubscription.last_frame_at`、`NoneBotLiveConfig.max_concurrent_connects`
- [X] T026 [US1] 事件分发隔离：`bilibili_api/nonebot/adapters/bilibili_live/adapter.py` 中单个处理器异常不得终止该房间后续分发，同房间事件保持到达顺序（FR-014）
- [X] T027 [US1] 实现转发入口 `nonebot/adapters/bilibili_live/__init__.py`：全部为显式再导出（`X as X`），不得含逻辑（contracts/adapter-public-api.md §1；FR-001）
- [X] T028 [US1] 关闭流程：`bilibili_api/nonebot/adapters/bilibili_live/adapter.py` 取消全部房间任务、关闭连接与客户端、可重复安全调用（FR-017；data-model.md `RoomSubscription.tasks`）

**Checkpoint**: MVP 达成——插件可导入、事件可回放验证，尚未接入真实连接

---

## Phase 4: User Story 2 - 多账号凭据与自动切换 (Priority: P2)

**Goal**: 账号唯一事实源在库凭据存储；按插入顺序选号；凭据失效先刷新、失败整号切换

**Independent Test**: 用假存储与假时钟驱动账号池，构造「首个账号刷新失败」与「单房间心跳超时」，断言切换范围与日志脱敏

### Tests for User Story 2 ⚠️

- [X] T029 [P] [US2] `tests/test_offline_nonebot_accounts.py`：选号顺序、刷新失败整号切换（区分「刷新失败即切」与「退避中切」两条路径，前者按 SC-003 的 5 秒内完成断言）、单房间失败不连带、`-102` 直接弃用、刷新并发合并、账号池全 `dead` 时按 V-08 明确报错、`request_log` 仍关闭、日志凭据零命中（SC-003、SC-003a）

### Implementation for User Story 2

- [X] T030 [US2] 实现 `bilibili_api/nonebot/adapters/bilibili_live/accounts.py` 的 `AccountSlot` / `AccountPool`：`order` 来自 `get_all_uids()` 的插入顺序，`cursor`/`dead` 驱动选择，`last_error` 只存脱敏摘要（data-model.md `AccountPool.order`、`AccountPool.cursor`、`AccountPool.dead`、`AccountSlot.last_error`）
- [X] T031 [US2] 接入凭据存储：`bilibili_api/nonebot/adapters/bilibili_live/adapter.py` 启动顺序固定为「取单例 → `await load()` → 校验 uid 存在」，凭据取深拷贝，刷新后 `add_credential(uid, cred)` 写回（data-model.md `AccountSlot.uid`、`AccountSlot.credential`；research D9）
- [X] T032 [US2] 实现 `bilibili_api/nonebot/adapters/bilibili_live/accounts.py` 的 `FailureClass` 常量表与分类函数，逐条对应 research D10（禁止「一律重连」兜底）
- [X] T033 [US2] 实现刷新流程：`bilibili_api/nonebot/adapters/bilibili_live/accounts.py` 中 `check_valid()` → `refresh()` → 写回 → 复检；按 uid 串行化；刷新确认阶段失败视为账号死亡且不重试（research D9）
- [X] T034 [US2] 实现整号切换：`bilibili_api/nonebot/adapters/bilibili_live/accounts.py` 在 `AccountState` 迁移时把该账号名下全部房间迁到下一可用账号；账号池全部 `dead` 时按 V-08 以明确错误收束（data-model.md `AccountState`、`AccountSlot.state`、`RoomSubscription.uid`）
- [X] T035 [US2] 存储异常处理：`bilibili_api/nonebot/adapters/bilibili_live/adapter.py` 对 `CredentialStoreCorruptException` / `CredentialStoreVersionMismatchException` / 跨循环 `ArgsException` 原样透传并在启动期报错，不静默重建（data-model.md 校验规则 V-09）

**Checkpoint**: 多账号可用，账号级失败不再拖累单房间故障

---

## Phase 5: User Story 3 - 连接时机策略 (Priority: P3)

**Goal**: ON / AUTO / MANUAL 三态可控，AUTO 按开播状态连断且节流

**Independent Test**: 以可控时钟与假房间状态源驱动策略机，断言开播/下播/启动/关闭四个时点的动作序列

### Tests for User Story 3 ⚠️

- [X] T036 [P] [US3] `tests/test_offline_nonebot_scheduler.py`：三策略动作序列、开播一个周期内连、下播断开、请求间隔下限、50 房间建连节流（同时在连数不超过 `max_concurrent_connects`）、关闭后任务与连接归零且**等待超过一个退避窗口后仍不再重连**（SC-004、SC-012、FR-021）

### Implementation for User Story 3

- [X] T037 [US3] 实现 `bilibili_api/nonebot/adapters/bilibili_live/scheduler.py` 的 `ConnectionPolicy` 三态与房间订阅编排（data-model.md `ConnectionPolicy`、`BotAccountConfig.connect_timing`）
- [X] T038 [US3] 实现 AUTO 开播检测：`bilibili_api/nonebot/adapters/bilibili_live/scheduler.py` 用 `LiveRoom.get_room_play_info()` 读 `live_status`（0/1/2），以空凭据轮询（research D11；data-model.md `RoomSubscription.room_display_id`）
- [X] T039 [US3] 实现全局节流：`bilibili_api/nonebot/adapters/bilibili_live/scheduler.py` 中同轮相邻请求间隔 ≥ `min_poll_interval`，每房间一轮 `poll_interval`（data-model.md `NoneBotLiveConfig.min_poll_interval`、`NoneBotLiveConfig.poll_interval`）
- [X] T040 [US3] 实现失败退避：`bilibili_api/nonebot/adapters/bilibili_live/scheduler.py` 对 `RISK_CONTROL` / `NETWORK` 类按指数退避且不得加速（data-model.md `FailureClass`、`RoomSubscription.next_retry_at`）
- [X] T041 [US3] 实现规模与去重：`bilibili_api/nonebot/adapters/bilibili_live/scheduler.py` 归一后房间数超 `max_rooms` 启动期报错（V-05），同一真实房间去重并告警（data-model.md `NoneBotLiveConfig.max_rooms`）
- [X] T042 [US3] 实现关闭/重载清理：`bilibili_api/nonebot/adapters/bilibili_live/scheduler.py` 停止轮询器、取消任务、关闭连接，重复调用无副作用（FR-017）

**Checkpoint**: 三种策略均可独立验收，AUTO 不会打爆接口

---

## Phase 6: User Story 4 - 适配器 API 调用复用库能力 (Priority: P4)

**Goal**: 7 个 REST 能力经库抽象层与反爬链路发出，未登录时抛项目异常

**Independent Test**: 注册假客户端捕获请求，断言反爬参数/登录态由库注入、适配器零直连；未登录路径抛 `CredentialNo*Exception`

### Tests for User Story 4 ⚠️

- [X] T043 [P] [US4] `tests/test_offline_nonebot_client.py`：C-01..C-11（contracts/client-bridge.md §8）+ 适配器 API 请求经假客户端发出、参数与返回模型正确、未登录异常类型正确

### Implementation for User Story 4

- [X] T044 [US4] 实现 `bilibili_api/nonebot/adapters/bilibili_live/bot.py` 的 `WebBot` 7 个方法，全部走 `Api(**API[...]).update_params(...)` 且使用关键字参数（contracts/adapter-public-api.md §3.1；FR-011）
- [X] T045 [US4] 实现 `bilibili_api/nonebot/adapters/bilibili_live/bot.py` 的 `Bot.send` 与 `reply_mid` 推导、`_call_api` 白名单语义（私有名/未知名 → `ApiNotAvailable`）（contracts/adapter-public-api.md §3.1）
- [X] T046 [US4] 未登录与缺字段路径：`bilibili_api/nonebot/adapters/bilibili_live/bot.py` 统一抛项目异常（`CredentialNoSessdataException` / `CredentialNoBiliJctException` 等），不得泄漏第三方异常（FR-011；contracts/client-bridge.md §7）
- [X] T047 [US4] 删除适配器自带的反爬实现：移除 `bilibili_api/nonebot/adapters/bilibili_live/wbi.py` 与 buvid 获取逻辑，改由库 `_wbi` / `_anti_spider` 提供；全仓检索确认无残留签名实现（FR-013）
- [X] T048 [US4] 驱动异常归一：`bilibili_api/clients/NoneBotClient.py` 把 `aiohttp`/`httpx`/超时异常转换为 `NetworkException`，文本脱敏（contracts/client-bridge.md §3）

**Checkpoint**: 适配器与库共用一套登录态、客户端与反爬链路

---

## Phase 7: User Story 5 - 融合的许可与归属合规 (Priority: P5)

**Goal**: 上游 MIT 来源可追溯、仓库仍为 GPL、迁移说明可执行

**Independent Test**: 仓库内可检索到来源 URL、基线版本与 commit、MIT 全文、版权行；旧配置启动即失败并指向迁移说明

- [X] T049 [P] [US5] 新增 `THIRD_PARTY_NOTICES.md`：上游 MIT 全文、`Copyright (c) 2025 MingxuanGame`、来源 URL、基线版本 0.2.6 与 commit `3f2c9bc2e74e02eaeb1a2192335f84eb3391782e`（SC-008）
- [X] T050 [P] [US5] 更新 `README.md`：保留 fork 来源声明，新增融合来源段与迁移步骤（写入凭据存储示例 + `uid` 改写前后对照；SC-011）
- [X] T051 [US5] 保留 `OpenBot` 符号但禁止使用：`bilibili_api/nonebot/adapters/bilibili_live/bot.py` 与 `__init__.py` 中实例化/启动即抛「开放平台形态尚未支持」明确错误（FR-018；contracts/adapter-public-api.md §2.1）
- [X] T052 [US5] 迁移验收：`tests/test_offline_nonebot_config.py` 中断言上游式 cookie 配置（V-01）启动失败并指向 README 迁移段，且全程零网络请求（SC-011）

**Checkpoint**: 许可合规、破坏性变更告知到位

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: 门禁、文档、打包与提交拆分

- [X] T053 为公共类与方法补中文 docstring（Args/Returns/Raises），覆盖 `bilibili_api/nonebot/adapters/bilibili_live/` 与 `bilibili_api/clients/NoneBotClient.py` 的公共符号
- [X] T054 [P] 运行 `uv run --with "mypy==1.18.2" python scripts/doc_gen.py` 并提交 `docs/modules/` 变更（禁止手改）
- [X] T055 运行 `uv run pytest -m "not integration"` 与 `uv run python scripts/lint.py`，确保零豁免全绿（SC-005、SC-006；须在 T054 之后执行，避免文档写入与漂移校验竞争）
- [X] T056 打包验收：`uv build --wheel` 后断言 wheel 同时含 `nonebot/adapters/bilibili_live/__init__.py` 与 `bilibili_api/nonebot/adapters/bilibili_live/__init__.py`，且**不含** `nonebot/__init__.py`（SC-007）
- [X] T057 新增集成用例 `tests/test_nonebot_live.py`：真实连接收至少一帧后主动断开，不发任何写操作。标记与凭据口径（严格按宪章 IV）：**先实测匿名连接**（`LiveDanmaku` 允许 uid=0 匿名）——匿名可连则只声明 `integration`，**不声明 `readonly`**（宪章把 readonly 限定为 GET 式读请求，WS 订阅不属于该范围）；匿名不可连则必须经 `tests/conftest.py` 的 `credential` fixture 取登录态（禁止自行读环境变量或 cookie 文件）并同时声明 `integration` + `cred1`。判定结果写入 `specs/012-nonebot-adapter-fusion/research.md`
- [X] T058 性能基线：在 `tests/test_offline_nonebot_frames.py` 中回放 1000 帧断言 ≤ 1 秒且顺序一致（SC-009）
- [X] T059 提交拆分（涉及 `bilibili_api/nonebot/`、`bilibili_api/clients/NoneBotClient.py`、`nonebot/adapters/bilibili_live/`、`pyproject.toml`、`scripts/lint.py`、`tests/`、`docs/modules/`、`CHANGELOGS/`、`THIRD_PARTY_NOTICES.md`、`README.md`）：先把 `bilibili_api/__init__.py` 的 `BILIBILI_API_VERSION` 提升到 `21.0.0`（破坏性变更，单一版本源）并更新 `CHANGELOGS/`；再按 `docs(spec)` 规格入库、`feat(nonebot)` 适配器主体、`fix(nonebot)` 三处上游缺陷、`test(nonebot)` 测试与样本、`build` 依赖与打包拆分提交；含破坏性变更的提交带 `BREAKING CHANGE: 配置由 cookie 改为凭据存储 uid 引用`
- [X] T060 按 `specs/012-nonebot-adapter-fusion/quickstart.md` 逐节走查并勾选，记录未覆盖项

---

## Dependencies & Execution Order

### 阶段依赖

```text
Phase 1 Setup
   └─> Phase 2 Foundational（阻塞所有故事）
          ├─> Phase 3 US1 (P1, MVP)
          ├─> Phase 4 US2 (P2)  ← 依赖 US1 的 RoomSubscription 与 Foundational 的配置
          ├─> Phase 5 US3 (P3)  ← 依赖 US1 的房间订阅与 US2 的账号池
          ├─> Phase 6 US4 (P4)  ← 依赖 US1 的 bot.py 骨架与 Foundational 的客户端
          └─> Phase 7 US5 (P5)  ← 可与 US2–US4 并行
                 └─> Phase 8 Polish（依赖全部故事）
```

### 故事内与故事间关键依赖

- T010（ws_*）→ T025（房间监听）→ T026（分发）
- T014（配置）→ T031（凭据加载校验）→ T033（刷新）→ T034（整号切换）
- T037（策略）→ T038（开播检测）→ T039（节流）→ T041（规模上限）
- T020（event.py）→ T021/T022/T023（三处缺陷）→ T019（回放用例转绿）
- T044（API 方法）依赖 T011（客户端注册）与 T016（端点键名）

### 并行机会

- Setup：T005、T006 并行
- Foundational：T008、T013、T015、T016 并行（不同文件）；T009/T010 与 T008 同文件，必须串行
- US1：T017、T018、T019 并行写测试（三个不同文件）；T021、T022、T023 三处缺陷修复并行（T021/T022 同文件不同函数，可与 T023 并行，彼此串行）
- US2：T032（分类表）与 T035（存储异常）可与 T030/T031 并行
- US5：T049、T050 与其它故事并行

---

## Parallel Execution Examples

**Foundational 并行包（4 个任务同时开工）**

```text
T008 request()        → bilibili_api/clients/NoneBotClient.py
T013 models+message   → bilibili_api/nonebot/adapters/bilibili_live/
T015 exception.py     → bilibili_api/nonebot/adapters/bilibili_live/exception.py
T016 const.py         → bilibili_api/nonebot/adapters/bilibili_live/const.py
```

**US1 测试三文件并行**

```text
T017 公共符号身份   → tests/test_offline_nonebot_events.py
T018 帧样本与录制   → scripts/record_nonebot_frames.py + tests/fixtures/nonebot_frames/
T019 帧回放与缺陷帧 → tests/test_offline_nonebot_frames.py
```

**US1 缺陷修复（T023 与 T021/T022 并行）**

```text
T021 DANMU_MSG 守卫  → event.py packet_to_event
T022 SuperChat 取值  → event.py SuperChatEvent
T023 勋章 is_light   → models/event.py + event.py validators
```

**US2 并行（测试与独立模块）**

```text
T029 accounts 测试    → tests/test_offline_nonebot_accounts.py
T032 FailureClass     → accounts.py 常量表
T035 存储异常透传      → adapter.py 启动路径
```

---

## Implementation Strategy

### MVP First（只做 US1）

1. Phase 1 + Phase 2 全部完成
2. Phase 3（US1）完成 → 离线回放全绿、导入身份一致、三处缺陷修复
3. **在此停下验收**：此时适配器可导入、事件层可信，但还不能真实连接

### Incremental Delivery

| 增量 | 内容 | 可验收结论 |
|------|------|-----------|
| 1 | Setup + Foundational | 传输层与配置可单测，库导入不受影响 |
| 2 | + US1 | 现有插件零改动可导入；事件层回归基线建立 |
| 3 | + US2 | 多账号与切换可用；凭据零回显 |
| 4 | + US3 | ON/AUTO/MANUAL 可用；轮询不触发风控 |
| 5 | + US4 | 7 个 REST 能力与库共用反爬链路 |
| 6 | + US5 + Polish | 许可合规、门禁全绿、wheel 内容正确、可发布 |

### 任务总量

- 总计 **60** 个任务：Setup 6、Foundational 10、US1 12、US2 7、US3 7、US4 6、US5 4、Polish 8
- 标记 [P] 的任务 **15** 个

---

## 执行记录（$speckit-implement，2026-11-22）

### 提交拆分（本地 `nonebot` 分支，未推送）

| commit | 说明 |
|--------|------|
| `66d23b2` | `release(nonebot)!` 版本提升 21.0.0 + `CHANGELOGS/v21.md`（含 `BREAKING CHANGE`） |
| `21ae8e6` | `build(nonebot)` 可选依赖 / 打包条目 / 门禁范围 / `protos/` |
| `52a1ac7` | `docs(spec)` 规格与设计文档 |
| `6af316c` | `feat(nonebot)` 适配器主体（传输 / 账号 / 调度 / 事件 / 配置） |
| `81a5c41` | `fix(nonebot)` 上游 0.2.6 三处缺陷 |
| `2c8ae3f` | `test(nonebot)` 离线回归 + 帧样本 + 真实连接冒烟 + 录制脚本 |
| `f0ab976` | `docs(nonebot)` 归属声明与迁移说明 |

### T057 判定

匿名连接可用（实测 `uv run pytest tests/test_nonebot_live.py -q` → `1 passed`），
最终只声明 `integration`，不声明 `readonly` / `cred1`；结论已写入 `research.md` D15。

### T060 quickstart 走查结果

| 小节 | 结果 |
|------|------|
| §1 导入与身份 | `True`（41 事件 / 6 基类 / 31 模型 / 4 异常 / 2 消息 + Adapter / WebBot / OpenBot） |
| §2 事件保真与缺陷修复 | `tests/test_offline_nonebot_events.py` + `..._frames.py` 62 passed（48 帧样本 / 41 事件类） |
| §3 配置校验 | `tests/test_offline_nonebot_config.py` 21 passed |
| §4 调度与连接时机 | `tests/test_offline_nonebot_scheduler.py` 12 passed |
| §5 真实连接冒烟 | `tests/test_nonebot_live.py` 1 passed（匿名） |
| §6 打包完整性 | wheel `bilibili_api_python-21.0.0-py3-none-any.whl`：含两条路径、无 `nonebot/__init__.py`；解包后两条导入路径均可导入且对象同一 |
| §7 门禁与文档 | `uv run python scripts/lint.py` 全绿；`docs/modules/` 无漂移 |
| §8 许可与归属 | `THIRD_PARTY_NOTICES.md` 四项关键字全部命中 |
| §9 破坏性变更告知 | README 迁移段含「写入凭据存储」示例与 uid 前后对照；配置用例断言错误文本指向 README |

**未覆盖 / 已知限制**：

- 帧样本为合成最小帧（48 行）而非全量真实录制；真实录制脚本已交付，`raw/`
  按设计不入库。低频 cmd（如 `HOT_RANK_SETTLEMENT`）尚无真实帧佐证。
- 提交拆分中 `feat` 与 `fix` 为同一实现的两个提交，中间提交未逐次运行全量门禁；
  最终状态（`HEAD`）全量离线用例与门禁全绿。
- `docs/modules/` 未新增适配器条目：`doc_gen` 仅扫描 `bilibili_api` 顶层模块，
  与既有子包（`utils` / `exceptions`）处理一致，不构成本特性的手工文档。
