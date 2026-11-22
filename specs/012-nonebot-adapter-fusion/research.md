# Research: NoneBot 直播适配器融合

**Feature**: `012-nonebot-adapter-fusion` | **Date**: 2026-11-22

本文件记录 plan 阶段已经裁决的技术决策、依据与被否掉的备选。每条都标注证据来源（代码位置 / 实验 / 上游实测），便于后续复核。

## D1. 代码落位与双导入路径

**Decision**: 实现代码放 `bilibili_api/nonebot/adapters/bilibili_live/`；仓库根新增 `nonebot/adapters/bilibili_live/__init__.py` 作为**纯转发**入口；两者由同一发行物交付。

**Rationale**:
- 库内路径被现有门禁自动覆盖：`scripts/lint.py:27-35` 对 `./bilibili_api/` 跑 `ruff check` 与 `ruff format --check`，`pyproject.toml` 的 pyrefly `project-includes=["bilibili_api/**"]` 同样覆盖，`doc_gen` 也按包扫描。无需新增排除项（FR-019）。
- 顶层 `nonebot/` 只承担导入路径兼容，逻辑为零，风险面最小。

**Alternatives considered**:
- 只保留 `bilibili_api.nonebot...`：破坏所有下游插件 import，与 FR-001 冲突。
- 全部代码放顶层 `nonebot/adapters/bilibili_live/`：需把 ruff / pyrefly / doc_gen 的检查范围都改到该目录，且与已安装 nonebot2 同名，工具解析易混淆；收益为零（因为仍要维护一层路径）。
- 迁移到 src 布局：牵动仓库全部路径假设（lint 路径、pyinstaller hook、doc_gen），超出本特性范围。

## D2. 单个 wheel 同时交付两个路径（实验验证）

**Decision**: 在 `[tool.setuptools] packages` 中同时登记 `bilibili_api.nonebot.*` 与 `nonebot.adapters.bilibili_live`，**不**提供 `nonebot/__init__.py`。

**Rationale（实验结论，非推断）**:
1. 构建出的 wheel 同时包含 `bilibili_api/...` 与 `nonebot/adapters/bilibili_live/__init__.py`，且不含 `nonebot/__init__.py`。
2. 先安装一个模拟的 `nonebot` 包（含 `__init__.py`）再安装本 wheel，两者在 site-packages 中干净合并，`import nonebot` 仍取到真实包。
3. 转发层与库内路径取到的是同一类对象（`DanmakuEvent is Same` → `True`），`isinstance` 不受路径影响。
4. `uv pip install -e .` 的 editable 安装下，`import nonebot.adapters.bilibili_live` 同样可用——**开发期不需要先打 wheel 才能跑测试**。

**Consequences**: 版本升级时若删除/重命名转发的符号，必须同步更新转发层；转发层不得引入逻辑（否则两条路径行为可能漂移）。

## D3. HTTP/WebSocket 归属：NoneBot 驱动承载的 `BiliAPIClient`

**Decision**: 新增 `bilibili_api/clients/NoneBotClient.py`（驱动承载的 `BiliAPIClient` 实现，含 4 个 `ws_*` 方法）；适配器启动时经 `register_client()` 注册并选中，仅当当前没有已选客户端时才接管。

**Rationale**:
- 宪章 I 要求 HTTP 必须经 `BiliAPIClient`，自定义客户端必须经 `register_client()`；宪章「反爬集中管理」要求 WBI/buvid 只能在 `_wbi` / `_anti_spider` 里。
- 上游适配器现在直接用 NoneBot 驱动的 `Request` / `self.websocket(...)`，并且自带 `wbi.py` 与 buvid 获取——两者都必须删掉，否则违反宪章。
- 用户 `DRIVER` 配置必须继续生效（spec 澄清 Q1 = A），因此客户端实现由驱动承载，而不是固定用 aiohttp。
- `register_client()` 会立即选中（`bilibili_api/utils/_session.py`），因此"仅当无已选客户端时安装"是保持 FR-011 与"自定义客户端可整体替换"同时成立的唯一做法。

**Alternatives considered**:
- 固定用库内置 aiohttp 客户端：用户 `DRIVER` 失效，与澄清结论冲突。
- 双实现可配：两套传输都要测，收益不抵成本。

**Risks**: 驱动不支持 WebSocket 时必须启动期报错（FR-012）；`select_client()` 是进程全局，适配器不得在用户已选客户端时强抢。

## D4. 保留适配器的事件层与 betterproto

**Decision**: 弹幕帧解包、`cmd` 注册表、41 个事件类与 `pb/` 生成代码保持上游形态；仅网络层与凭据层下沉。

**Rationale**:
- `event.py:31-39` 直接以 betterproto 的 `Message` 作为事件字段类型（`COMMAND_TO_PB` 恰好注册 `INTERACT_WORD_V2`、`ONLINE_RANK_V3` 两条）。
- 库内 `_live_danmaku.parse_*` 产出的是字典（手写 varint 解析），改用它意味着重写这两个 cmd 的事件字段形状——属破坏性变更，且无法保证字段语义等价。
- 上游只在这两处用 betterproto，依赖面可控（`betterproto>=1.2.5,<2`）。

**Alternatives considered**: 全量改用 `LiveDanmaku` + `pb_decoded`（spec 已作为"深度复用"选项被否）；混合两套解析（同时引入两套逻辑，维护成本最高）。

## D5. 端点复用现有 `data/api/live.json`

**Decision**: 适配器的 8 个 REST 调用全部映射到已有 JSON 键，不修改 registry，也不手工编辑 JSON。

**Rationale（逐条核对）**:

| 上游调用 | 现有键 |
|---|---|
| `live_user/v1/Master/info` | `live_info.info` |
| `room/v1/Room/get_info` | `live_info.get_info` |
| `room/v1/Room/getRoomInfoOld` | `live_info.get_room_info_old` |
| `msg/send` | `operate.send_danmaku` |
| `banned/AddSilentUser` | `operate.add_block` |
| `banned/GetSilentUserList` | `info.black_list` |
| `banned_service/v1/Silent/del_room_block_user` | `silent_user_manage.del_room_block_user` |
| `xlive/web-room/v1/index/getDanmuInfo` | `info.danmu_info` |

nav（WBI 密钥）与 buvid 由库内 `_wbi` / `_anti_spider` 负责，适配器不直接调用。

## D6. 配置形态与破坏性变更

**Decision**: `BILIBILI_LIVE_BOTS` 保留变量名，但每项改为 `{"uid": ..., "room_ids": [...]}`；cookie 字符串与开放平台字段均**显式拒绝**。

**Rationale**: spec 澄清 Q2 选定"只认存储"。凭据存储是账号唯一事实源，账号的添加顺序即选号顺序，多账号切换才有确定语义；隐式接受 cookie 会制造两个事实源。

**Consequences**: 破坏性变更，提交需 `BREAKING CHANGE`；README 必须给出迁移步骤；错误文本必须含迁移指引（SC-011）。

## D7. 门禁范围调整

**Decision**: 在 `pyproject.toml` 的 pyrefly `project-includes` 增加 `nonebot/**`，在 `scripts/lint.py` 的 ruff 目标中增加 `./nonebot/`；**不新增任何 exclude / 忽略规则**。

**Rationale**: 转发层虽只有一行，但仍是仓库代码；把它纳入同一门禁可以避免"新增豁免"的口子（FR-019 / SC-005）。适配器实现位于 `bilibili_api/` 下，已自动覆盖。

**Consequences**: `nonebot2` 与 `betterproto` 必须进入 dev 依赖组，否则 pyrefly / pytest 在 CI 上无法解析导入。

## D8. 自动化测试口径

**Decision**: 全部离线用例（4 个文件）+ 1 个只读集成用例。

**Rationale**:
- 上游零测试（CI 只在 release 时构建发布），回归基线只能自建：用固定帧样本 + 事件字段快照锁死 41 个事件的行为，并把三处缺陷帧作为显式回归样本（SC-010）。
- 真实弹幕连接属集成层：只读、缺凭据跳过、单次运行受 `BILI_RATELIMIT` 约束；不触碰 cred2/cred3 语义。

**Consequences**: 帧样本需要人工从真实帧中采集并脱敏（不得含真实 uid 以外的个人信息也可保留，但不得含凭据）。

## D9. 账号读取与刷新次序（库实现细节决定）

**Decision**: 启动流程固定为「构造/取用存储单例 → `await store.load()` → 校验配置里每个 uid 是否存在」；刷新流程固定为「`check_valid()` → 为 `False` 时直接 `refresh()` → 写回存储 → 重新校验」，**不调用 `check_refresh()` 作为前置判断**。

**Rationale（源码核对）**:
- `store_data()` 会 `DELETE FROM credential` 后按内存快照整表重写（`credential_store_sqlite.py:203-211`），而单例初始内存为空且 `load()` 不会自动执行——**先 `add_credential` 再 `load` 会把库里其它账号全删掉**。
- `Credential.refresh()` 原地修改自身（`_credential.py:265-273`），但 `get_credential()` 返回的是深拷贝（`credential_store.py:82-84`），因此刷新后必须 `add_credential(uid, cred)` 才能持久化；否则下次启动拿到的是已作废的旧 token。
- `check_refresh()` 对过期会话会抛 `ResponseCodeException(-101)` 而不是返回 `False`（`_credential.py:256-263` + `_api.py:329-335`），不能当作布尔判断使用；`check_valid()` 因为 `ignore_code` 才会稳定返回 `False`。
- `_confirm_refresh` 在刷新接口成功之后才执行（`_credential.py:401`），它失败时旧 token 已失效且新 token 未返回——**确认失败按"账号已死"处理，不重试**。
- `add_credential` 要求 `dedeuserid == str(uid)` 精确相等（`credential_store.py:59-63`），且返回 `False` 表示覆盖成功而非失败。

**Consequences**: 刷新必须按 uid 串行化（`refresh()` 无内部锁，并发刷新同一账号会互相作废）；适配器需要一层 per-uid 的刷新合并。

## D10. 失败分类信号表（固定到常量表，可被离线用例断言）

**Decision**: 按下列映射实现 `FailureClass`，不得使用「一律重连」兜底。

| 信号 | 类别 | 处理 |
|---|---|---|
| `CredentialNoSessdataException`、`CredentialNoBiliJctException` | 凭据不可用 | 无法刷新，直接整号切换 |
| `CredentialNoAcTimeValueException` | 不可刷新 | 当前可用但不可刷新，首次鉴权失败即换号 |
| `CredentialNoDedeUserIDException` / `CredentialNoBuvid3Exception` / `CredentialNoBuvid4Exception` | 凭据不完整 | 整号切换并提示重新添加 |
| 业务码 `-101`（未登录）、`-111`（csrf 失败）、`-102`（封停） | 凭据类 | 先刷新；`-102` 为永久不可用直接弃用 |
| 刷新过程中的 `CookiesRefreshException` / 确认阶段异常 | 凭据类 | 账号标记 `DEAD`，整号切换 |
| HTTP `412`、业务码 `-352` / `-412` / `-509` | 风控/限速 | 房间级指数退避，不换号、不加速 |
| wbi 接口 `-403` 重试耗尽（`WbiRetryTimesExceedException`） | 风控 | 退避后重试，必要时 `recalculate_wbi()` |
| 传输层异常（超时、DNS、连接重置，含 aiohttp/httpx 原始异常） | 瞬时网络 | 房间级退避重连 |
| WBI 密钥获取的 `JSONDecodeError` / `KeyError`（`_wbi.py:142-151` 不检查状态码） | 协议/反爬 | 记录 + 退避，视作连接类 |
| `Content-Length: 0` 返回 `None` | 无数据 | 跳过本轮，不算失败 |

**Rationale**: 这些阈值直接来自库的异常构造点（`_api.py:227-344`、`_credential.py:256-411`、`_wbi.py`）；不基于实测就无法区分"账号死了"与"这一轮被限速"。

**Consequences**: 分类常量表放在 `accounts.py`，离线用例用假异常逐条断言，避免回归时把风控误判为换号。

## D11. AUTO 开播检测端点

**Decision**: 用 `LiveRoom.get_room_play_info()`（`live.json` 的 `info.room_play_info`）读 `live_status`：`0` 未开播、`1` 直播中、`2` 轮播。

**Rationale（实测）**:
- 该端点 `verify:false`、无 wbi、只需 `room_id`，用空凭据也能查；同一路径返回 `room_id` / `short_id` / `uid` / `live_status`，顺带完成长短号归一。
- 对照：`get_room_info()`（`getInfoByRoom`）在实测中即使带真实房间号也返回 HTTP 200 + `{"code":-352}`，不适合做轮询。
- `get_room_id()` 的缓存永不过期（`live.py:214-226`），因此长短号归一每个房间只做一次，轮询只查状态。

**Consequences**: 轮询用**空凭据**发起，避免把开播检测绑定到某个账号的登录态与风控画像上（库仍会附带 cookie，空凭据最干净）。

## D12. 凭据泄漏面清单

**Decision**: 适配器禁止开启库的 `request_log`；任何日志只允许出现 uid 与脱敏摘要，禁止直接记录 `Credential` 对象。

**Rationale（源码核对）**:
- `Credential.__str__` 打印全部字段（`_credential.py:307-308`），pydantic v2 的 `repr` 同样展开字段值。
- `Api._request_pair` 派发的 `API_REQUEST` 事件包含 `Credential` 对象（`_api.py:350-354`），`REQUEST`/`RESPONSE` 事件包含完整 cookie（`_session.py:114-147`）；`request_log` 一旦打开即写入日志。
- 这三处都不是适配器能改的库行为，只能通过「不开启 + 不打印」规避。

**Consequences**: `log.py` 需要提供脱敏帮助函数；离线用例增加一条"开启日志后断言输出中检索不到凭据值"的回归断言（仅覆盖适配器自身日志）。

## D13. 帧样本来源（避免“用被测代码自己造期望值”）

**Decision**: 帧样本分两层来源，且两层都要留痕：

1. **录制层（一次性）**：实现阶段用只读集成连接（`readonly` 语义、手动触发、不发送任何内容）把真实帧写入 `tests/fixtures/nonebot_frames/raw/`，记录采集日期与房间号；凭据字段不进入帧（弹幕帧本身不含 SESSDATA，但仍需过一遍脱敏脚本剔除用户隐私字段）。
2. **合成层（可提交）**：由录制帧经脱敏与精简得到的最小帧，按 `cmd` 一项一文件，作为离线用例的快照输入；三处缺陷帧（无 `data` 的 `DANMU_MSG`、`SUPER_CHAT_MESSAGE`、带 `is_light` 勋章的 `INTERACT_WORD`）单独标注来源。

**Rationale**: 只用合成帧会退化成「用实现反推期望」；只用真实帧则无法覆盖低频 `cmd`（如 `HOT_RANK_SETTLEMENT`）。两层结合既保证真实性，又保证覆盖率。

**Consequences**: 需要一个 `scripts/record_nonebot_frames.py`（只读、人工执行、不入 CI）；离线用例只读 `fixtures/`，不触网。

**执行结果（T062，2026-11-22）**: 已按决策完成两轮 90 秒只读录制：房间 `6`（真实 `7734200`，8 `cmd` / 28 帧）与房间 `21452505`（13 `cmd` / 358 帧），两轮均 `live_status=1`、匿名凭据。人工脱敏后作为第二组样本入库 `tests/fixtures/nonebot_frames/recorded/`（每 `cmd` 首帧，8 个已建模 + 4 个未建模）。

- 已录到并覆盖（8 个已建模 `cmd`）：`DANMU_MSG`（确证线上网页帧**无顶层 `data`**、`cmd` 无 `:4:0:2:2:1` 后缀、用户信息内嵌在 `info[0][15]`）、`LIKE_INFO_V3_CLICK`、`LIKE_INFO_V3_UPDATE`、`ONLINE_RANK_COUNT`、`POPULAR_RANK_CHANGED`、`ROOM_REAL_TIME_MESSAGE_UPDATE`、`STOP_LIVE_ROOM_LIST`、`WATCHED_CHANGE`。
- 录制会话内验证可解析、但**未入库**的 pb 帧：`INTERACT_WORD_V2`（157 帧，全部产出 `UserEnterEvent`）、`ONLINE_RANK_V3`（11 帧，全部产出 `OnlineRankEvent`）。未入库原因：betterproto 载荷的 base64 内含真实昵称与头像 URL，需 pb 级重编码才能安全提交；结构覆盖由合成样本承担，解析能力以上述实测为准。
- 未录到的低频 `cmd`：`HOT_RANK_SETTLEMENT`、`ROOM_ADMINS` 在两轮录制窗口内均未出现，仍只由合成样本覆盖。它们只在热榜结算 / 房管变更时下发，短窗口录制无法保证命中，因此没有为它们编造“真实帧”，缺口在 `recorded/README.md` 中登记。
- 真实流量中的未建模 `cmd`：`ENTRY_EFFECT`（48 帧）、`LOG_IN_NOTICE`、`HOT_ROOM_NOTIFY`、`POPULARITY_CHANGE`（上游 0.2.6 未建模，本特性不扩充事件表）。样本入库并由 `test_recorded_unknown_commands_are_skipped` 锁定“记录并跳过、不中断后续分发”的行为；`NOTICE_MSG` 因正文内嵌真实昵称（`<%昵称%>`）未入库。
- 原始录制仍不入库；`recorded/` 只保留人工剔除昵称、弹幕正文与哈希后的结构帧。录制的 `LOG_IN_NOTICE` 帧同时佐证了 D15 的“匿名可连”判定（其正文即“未登录无法查看他人昵称”提示）。

## D14. 驱动桥接的实测结论（含两条自我更正）

**Decision**: 采用 `AsyncExitStack` 持有 `driver.websocket(...)` 上下文；WS 读取只用 `receive()`；关闭码 1000/1001 映射为 `CLOSED`、其余抛出；下载走 `stream_request`；`nonebot2` 下限提到 `>=2.5.0`。

**Rationale（nonebot2 2.5.0 / aiohttp 3.14.3 / httpx 0.28.1 源码核对）**:
- `WebSocket.receive()` 永不返回关闭帧，关闭一律表现为 `WebSocketClosed(code, reason)`；`receive_bytes()` 对文本帧抛 `TypeError`，因此只能用 `receive()` 再按 `str`/`bytes` 分派。
- 关闭码 1000/1001 若也抛异常，会把正常断开判成错误并触发多余重连；1006 等异常码必须抛出才能进入重连路径。
- aiohttp 对并发 `receive()` 直接 `RuntimeError`，因此每个句柄需要一把接收锁；关闭要先 close、等读锁释放、再退上下文，避免接收方未退出就销毁会话。
- WS 的 `read` 超时不能设：库默认 `timeout=30.0` 一旦透传成 `read`，空闲 30 秒就会超时，与长连接语义冲突。
- 纯 `httpx` 驱动只实现 `HTTPClientMixin`，没有 `websocket` 属性——**弹幕链路在纯 httpx 驱动下根本无法建立**，必须启动期明确报错。
- `HTTPClientMixin.stream_request()` 在 aiohttp 与 httpx 驱动上都有，因此 `download_*` 可以真流式（**更正我先前契约里"整包缓冲再切片"的判断**，那个代价不存在）。
- 2.4.3 及更早的 aiohttp 驱动在 `WSMsgType.CLOSED` 上会漏出 `TypeError`，2.5.0 才修；为避免在旧版本上出现"读循环异常而非正常关闭"的隐性故障，直接把依赖下限提到 2.5.0。

**Alternatives considered**:
- 每连接一个 owner task + 队列（进入/退出同任务，最稳）：作为 AsyncExitStack 实测出问题时的备选，不做默认，避免 50 房间多出 50 个常驻任务。
- 手工 `__aenter__`/`__aexit__`：异常路径容易少退出一次，否决。

**Consequences（驱动强加的限制，必须写进文档）**：最终 URL 不可得（`get_real_url()` 会退化）、重定向中途 cookie 丢失、`verify_ssl`/`trust_env` 无法配置、无连接池、控制帧不可见。这些都不是实现缺陷，而是驱动抽象层面的事实。



## D15. 集成冒烟标记口径实测结论（T057）

**Decision**: `tests/test_nonebot_live.py` 只声明 `integration`，不声明 `readonly`，也不声明 `cred1`；不取 `credential` fixture。

**Rationale（2026-11-22 实测）**:
- `LiveRoom.get_room_play_info()` / `get_danmu_info` 在匿名凭据（`Credential()`）下均可用；候选房间（6 / 21452505 / 544853）能解析出真实房间号与弹幕服务器。
- 以匿名身份建立真实弹幕连接并收到了业务事件，用例通过（`uv run pytest tests/test_nonebot_live.py -q` → `1 passed`）。
- 宪章 IV 把 `readonly` 限定为 GET 式读请求，WS 订阅不属于该范围，因此不声明 `readonly`；匿名可连，故无需登录态，也就不声明 `cred1`。

**Consequences**: 该用例默认随 `pytest` 全量运行（集成层），每周 `-m "cred0 or cred1 or cred2"` 任务不会收集它；缺网络或候选房间均未开播时 `skip`，不误报失败。

## D16. `_pydantic.py`：校验装饰器的类型化收窄（T064）

**Decision**: 保留 `bilibili_api/nonebot/adapters/bilibili_live/_pydantic.py` 作为私有模块（不进入公共导出），`config.py` / `event.py` / `models/event.py` 统一从它取 `model_before` / `model_after` / `field_before`。

**Rationale（类型检查零容忍下的取舍）**:
- pydantic 的 `model_validator(...)` / `field_validator(...)` 在类型层返回「装饰器 | None」，直接当装饰器用会被 pyrefly 判定为不可调用；本特性的校验器共 17 处（`event.py` 12 处 `model_before`、`config.py` 2 组 `model_before` / `model_after`、`models/event.py` 1 处 `field_before`）。
- 项目已整体退役存量类型豁免（AGENTS.md「类型检查零容忍」），逐处 `# type: ignore` 或 `cast` 会把类型噪声扩散到业务代码，且难以在 pydantic 升级后回收。
- 收窄集中在 42 行模块内：运行时仍是 pydantic 原装饰器（不改变行为），类型层变成确定的 `Callable[[Any], Any]`，三处调用方各多一行 import。
- 该文件不在 plan.md 的文件清单内，属实现阶段补齐。合并回调用方会在 3 个文件里重复同一别名、同一段解释与同一处 pydantic 依赖，收益为负。

**Consequences**: 多一个私有文件；`__all__` 只有类型别名与三个装饰器构造函数，不进入 `bilibili_api.nonebot.adapters.bilibili_live` 的公共符号；若 pydantic 修正存根返回类型，可整模块删除并把调用点换回原生装饰器。
