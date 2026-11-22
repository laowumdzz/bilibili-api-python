# Data Model: NoneBot 直播适配器融合

**Feature**: `012-nonebot-adapter-fusion` | **Date**: 2026-11-22 | **Spec**: [spec.md](./spec.md)

本文件定义本特性新增或改造的实体、字段、约束与状态机。库既有实体（`Credential`、凭据存储、`BiliAPIClient`、`LiveRoom`）不在此重复定义，只在“复用约束”中标注对接点。

## 1. 配置实体

### 1.1 `NoneBotLiveConfig`（适配器配置根）

承载于 NoneBot 插件配置（环境变量 `BILIBILI_LIVE_BOTS` 为 JSON 数组），字段全部走显式名称，不做隐式联合推断（FR-022）。

| 字段 | 类型 | 必填 | 默认 | 约束 |
|------|------|------|------|------|
| `bots` | `list[BotAccountConfig]` | 是 | — | 至少 1 项；同一 `uid` 不得重复出现 |
| `connect_timing` | `"on" \| "auto" \| "manual"` | 否 | `"on"` | 全局默认值，可被单项覆盖（FR-007） |
| `poll_interval` | `float`（秒） | 否 | `60` | ≥ `min_poll_interval`；AUTO 每房间一轮的间隔（FR-008） |
| `min_poll_interval` | `float`（秒） | 否 | `2` | 同轮相邻请求的最小间隔，硬下限 2 秒（FR-008） |
| `max_rooms` | `int` | 否 | `50` | 全局唯一房间数上限（去重后计），超过即启动期报错（FR-023） |
| `max_concurrent_connects` | `int` | 否 | `5` | 同时在连（握手/鉴权中）的连接数上限，≥ 1；用于建连节流（FR-023） |
| `db_path` | `str \| None` | 否 | `None` | 覆盖凭据存储数据库路径（FR-016），`None` 表示库默认目录 |
| `key_path` | `str \| None` | 否 | `None` | 覆盖凭据存储密钥路径（FR-016） |

### 1.2 `BotAccountConfig`（一代账号的监听声明）

| 字段 | 类型 | 必填 | 默认 | 约束 |
|------|------|------|------|------|
| `uid` | `int` | 是 | — | 必须存在于凭据存储，否则启动期报错并列出缺失 uid（FR-004 边界） |
| `room_ids` | `list[int]` | 是 | — | 长短号均可；启动时归一为真实房间号后去重 |
| `connect_timing` | `"on" \| "auto" \| "manual" \| None` | 否 | `None` | `None` 表示继承全局值 |

**禁止字段**：`cookie`、`sessdata`、`bili_jct`、`access_key`、`access_secret`、`app_id`、`identify_codes`。

- 出现任何 cookie 类字段 → 启动期报错 + 迁移指引（FR-004 / SC-011）。
- 出现开放平台字段（`access_key` / `app_secret` / `app_id` / `identify_codes`）→ 启动期报错，说明该形态延后（FR-018）。

## 2. 运行期实体

### 2.1 `AccountSlot`（账号槽位）

| 字段 | 类型 | 说明 |
|------|------|------|
| `uid` | `int` | 存储主键，与 `Credential.dedeuserid` 必须一致（库既有约束） |
| `credential` | `Credential` | 从存储取得的深拷贝快照；刷新成功后需写回存储 |
| `state` | `AccountState` | 见 3.1 |
| `last_error` | `str \| None` | 脱敏后的错误摘要（不得含凭据字段值） |

**复用约束**：`BaseCredentialStoreManager` 为按子类单例且绑定事件循环；**启动时必须先 `await store.load()` 再校验/新增账号**——`store_data()` 是「整表删除后重写」，单例初始内存为空，顺序颠倒会清空其它账号（research D9）。`get_credential()` 返回深拷贝，刷新后必须显式 `add_credential(uid, new_cred, auto_persist=True)` 才持久化；`add_credential` 返回 `False` 表示覆盖成功而非失败。

### 2.2 `AccountPool`（有序账号池）

| 字段 | 类型 | 说明 |
|------|------|------|
| `order` | `list[int]` | 来自 `get_all_uids()` 的插入顺序（FR-005） |
| `cursor` | `int` | 当前选中的索引；初始 0 |
| `dead` | `set[int]` | 本轮运行内已判定不可用（刷新失败 / 存储已移除）的 uid |

**选择规则**：按 `order` 从 `cursor` 起找第一个不在 `dead` 中的 uid；全部为 `dead` → 抛“所有账号不可用”错误（FR-006）。

### 2.3 `RoomSubscription`（房间订阅）

| 字段 | 类型 | 说明 |
|------|------|------|
| `room_display_id` | `int` | 配置里写的房间号（可能是短号） |
| `room_real_id` | `int \| None` | 归一后的真实房间号；未解析时为空 |
| `uid` | `int` | 当前承载账号 |
| `state` | `RoomState` | 见 3.2 |
| `retry_count` | `int` | 连续失败次数，用于退避上限 |
| `next_retry_at` | `float \| None` | 退避截止时刻（单调时钟） |
| `last_frame_at` | `float \| None` | 最近收帧时刻，用于心跳超时判定 |
| `tasks` | `set[Task]` | 该房间拥有的连接/心跳任务，关闭时必须取消 |

**唯一性**：`room_real_id` 在单进程内唯一；同一真实房间出现两次（短号 + 长号）→ 保留一条并告警。

### 2.4 `DanmakuFrame`（弹幕帧，协议实体）

| 字段 | 类型 | 说明 |
|------|------|------|
| `length` | `int` | 含 16 字节头（`>I`） |
| `header_length` | `int` | 恒为 16（解析但按协议固定切片） |
| `proto_version` | `0 \| 1 \| 2 \| 3` | 0 原始 JSON / 1 心跳 / 2 zlib / 3 brotli |
| `opcode` | `2 \| 3 \| 5 \| 7 \| 8` | 心跳 / 心跳回复 / 命令 / 鉴权 / 鉴权回复 |
| `seq` | `int` | 心跳与鉴权帧用固定值 |
| `payload` | `bytes` | `length - header_length` 字节 |

**约束**：`length` 小于等于 16 或大于剩余缓冲 → 判为畸形帧，记录并丢弃，不得进入死循环（FR-021 边界）；`protover=2` 用标准库 `zlib`，`protover=3` 用 `brotli`。

### 2.5 `EventEnvelope`（事件投递单元）

| 字段 | 类型 | 说明 |
|------|------|------|
| `cmd` | `str` | 帧内 `cmd`（`DANMU_MSG:4:0:2:2:1` 一类后缀归一为 `DANMU_MSG`） |
| `room_real_id` | `int` | 来源房间 |
| `raw` | `dict` | 原始 JSON（或 protobuf 解出的 dict） |
| `model` | `type[Event]` | 由 `COMMAND_TO_EVENT` 注册表决定 |

### 2.6 `BotType` / `EventFamily`

沿用上游层次，不新增类型：

- `BotType`: `web`（本特性唯一实现），`open`（延后，配置出现即报错）。
- `EventFamily`: `message` / `notice` / `metaevent`，与 `get_type()` 对应。
- `WebOnlyEvent` / `OpenplatformOnlyEvent` 标记类保留定义，本特性只产生前者可达的事件。

## 3. 状态机

### 3.1 `AccountState`

```text
AVAILABLE ──(凭据类失败)──> REFRESHING ──(刷新成功)──> AVAILABLE
                                   └──(刷新失败)──> DEAD
DEAD ──(运维移除/重新添加账号后重启)──> AVAILABLE
```

- 进入 `DEAD` 必须把该账号名下所有 `RoomSubscription` 迁移到下一个可用账号（FR-006 凭据类整号切换）。
- `REFRESHING` 期间同一账号的并发请求 MUST 合并为一次刷新（避免风暴）。

### 3.2 `RoomState`

```text
IDLE ──(策略允许)──> CONNECTING ──(鉴权成功)──> CONNECTED
CONNECTED ──(连接类失败/心跳超时)──> BACKOFF ──(退避到期)──> CONNECTING
CONNECTED ──(下播且策略为 auto)──> CLOSING ──> IDLE
任意状态 ──(整体关闭)──> CLOSED（不可再迁移）
```

- `BACKOFF` 采用指数退避（基数 5 秒，上限可配），MUST NOT 在失败时缩短间隔。
- `CLOSED` 是终态；关闭流程要求所有 `tasks` 已取消、连接已释放、重复关闭无副作用（FR-017）。

### 3.3 `ConnectionPolicy`（连接时机）

| 取值 | 启动动作 | 开播变化 | 下播变化 | 手动接口 |
|------|----------|----------|----------|----------|
| `on` | 立即对全部房间 `CONNECTING` | 无 | 连接保持（由断线重连处理） | 可显式断开/重连 |
| `auto` | 仅启动轮询器，房间保持 `IDLE` | 一个轮询周期内进入 `CONNECTING` | `CLOSING` → `IDLE`，等待下次开播 | 可强制连接（临时覆盖策略） |
| `manual` | 不做任何连接 | 不动作 | 不动作 | 必须显式连接 |

## 4. 失败分类实体

### 4.1 `FailureClass`（FR-006 判别基础）

| 类别 | 典型信号 | 处理 |
|------|----------|------|
| `CREDENTIAL` | `CredentialNoSessdataException` / `CredentialNoBiliJctException` / `CredentialNoDedeUserIDException` / `CredentialNoBuvid3Exception` / `CredentialNoBuvid4Exception`；业务码 `-101` / `-111` / `-102`；刷新失败（`CookiesRefreshException`、确认阶段异常） | 先刷新（`-102` 与缺字段类直接弃用）；失败则账号 `DEAD`，整号切换 |
| `UNREFRESHABLE` | `CredentialNoAcTimeValueException` | 可继续只读，但标记不可刷新；首次鉴权失败即换号 |
| `RISK_CONTROL` | HTTP `412`、业务码 `-352` / `-412` / `-509`、wbi `-403` 重试耗尽（`WbiRetryTimesExceedException`） | 该房间指数退避；不换号、不加速 |
| `NETWORK` | `NetworkException`、连接被关闭、握手失败、传输层原始异常（超时/DNS/重置） | 该房间按退避重连，连续失败达上限后按需换号 |
| `PROTOCOL` | 畸形帧、未知 `cmd`、protobuf 解码失败、WBI 密钥获取的 JSON/Key 错误 | 丢弃当前帧/事件并记录；不改变连接状态 |
| `NO_DATA` | `Content-Length: 0` 导致返回 `None` | 跳过本轮，不计失败 |

> 完整映射与处置见 [research.md](./research.md) D9–D12。分类常量表必须可被离线用例直接断言（禁止“一律重连”兜底）。

## 5. 校验规则汇总

| 编号 | 规则 | 关联需求 | 失败表现 |
|------|------|----------|----------|
| V-01 | 配置含 cookie 类字段 | FR-004 / SC-011 | 启动失败 + 迁移步骤 |
| V-02 | 配置含开放平台字段 | FR-018 | 启动失败 + “尚未支持”说明 |
| V-03 | 引用的 uid 不在存储中 | FR-004 边界 | 启动失败 + 缺失 uid 列表 |
| V-04 | 同一 uid 重复声明 | FR-022 | 启动失败 + 重复 uid |
| V-05 | 去重后房间数 > `max_rooms` | FR-023 | 启动失败 + 超出数量 |
| V-06 | `poll_interval < min_poll_interval` 或 `min_poll_interval < 2` | FR-008 | 启动失败 + 实际取值 |
| V-07 | 房间号解析失败（接口无真实房间号） | FR-009 | 该房间标记失败并告警，其余房间继续 |
| V-08 | 无可用账号 | FR-006 | 明确错误收束，不空转 |
| V-09 | 凭据存储损坏 / 版本不匹配 / 跨循环访问 | 库既有约束 | 透传库异常，不吞掉 |
| V-10 | 驱动不支持 WebSocket | FR-012 | 启动期明确报错 |
| V-11 | `max_concurrent_connects < 1` 或大于 `max_rooms` | FR-023 | 启动失败 + 实际取值与允许范围 |

## 6. 复用约束（与库现有实体的对接点）

| 库实体 | 适配器用法 | 约束 |
|--------|-----------|------|
| `Credential` | 唯一登录态表示；`refresh()` 后写回存储 | 不得在日志/异常/repr 中输出字段值 |
| `BaseCredentialStoreManager` / `SQLiteCredentialStoreManager` | 账号注册表与落盘 | 单例、绑定事件循环、`uid` 必须等于 `dedeuserid` |
| `BiliAPIClient` | 所有 HTTP 与 WebSocket | 适配器只经 `get_client()` / `register_client()`，不自建会话 |
| `Api` + `data/api/live.json` | 8 个 REST 端点 | 必须用关键字参数、`Api(**api).update_params(...)` 链路 |
| `_wbi` / `_anti_spider` | WBI 签名、buvid、bili_ticket | 适配器不得自带签名或指纹实现 |
| `LiveRoom` | 房间号归一与开播状态查询（AUTO） | 用 `get_room_play_info()` 读 `live_status`（0/1/2），以空凭据轮询；不复用其弹幕连接 |
| `request_log`（`utils/_log.py`） | —— | 适配器 MUST NOT 开启：库的请求事件直接携带 `Credential` 与 cookie，开启即泄漏（research D12） |
| `bilibili_api/exceptions` | 错误语义 | 凭据/网络/响应码异常直接透传或包装为适配器异常 |
