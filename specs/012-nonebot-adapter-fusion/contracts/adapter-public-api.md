# Contract: 适配器公共 API

**Feature**: `012-nonebot-adapter-fusion` | **Scope**: `nonebot.adapters.bilibili_live`（与 `bilibili_api.nonebot.adapters.bilibili_live` 为同一批对象）

本契约锁定「现有插件零改动」的判定口径（FR-001 / SC-001）。所有符号必须可导入、名称一致，且两条导入路径取到的必须是**同一个对象**（`is` 为真），以保证 `isinstance` 与注册表判断不受导入路径影响。

## 1. 导入与身份

```python
from nonebot.adapters.bilibili_live import DanmakuEvent
from bilibili_api.nonebot.adapters.bilibili_live import DanmakuEvent as Same

assert DanmakuEvent is Same          # 转发层只做再导出，不复制类
```

- 实现位于 `bilibili_api/nonebot/adapters/bilibili_live/`；`nonebot/adapters/bilibili_live/__init__.py` 只允许出现显式再导出（`X as X` 形式），不得含逻辑。
- 未安装 `nonebot2` 时，导入 `bilibili_api` 必须仍然成功；只有导入适配器子包时才允许因缺少依赖而失败。

## 2. 顶层符号清单

### 2.1 适配器与 Bot

| 符号 | 类型 | 本特性状态 |
|------|------|-----------|
| `Adapter` | `nonebot.adapters.Adapter` 子类 | 完整实现（WebBot 链路） |
| `WebBot` | 适配器 `Bot` 子类 | 完整实现 |
| `OpenBot` | 适配器 `Bot` 子类 | **保留符号**：实例化/启动时抛“开放平台形态尚未支持”的明确错误（FR-018），不得半可用 |

### 2.2 事件基类与标记类（6 个）

`Event`、`MessageEvent`、`NoticeEvent`、`MetaEvent`、`WebOnlyEvent`、`OpenplatformOnlyEvent`

### 2.3 可实例化事件（41 个）

消息类（2）：`DanmakuEvent`、`SuperChatEvent`

元事件（1）：`HeartbeatEvent`

通知类（38）：`UserEnterEvent`、`UserFollowEvent`、`UserShareEvent`、`GuardBuyEvent`、`GuardBuyToastEvent`、`SendGiftEvent`、`GiftStarProcessEvent`、`SpecialGiftEvent`、`LikeEvent`、`InteractionVote`、`InteractionDanmaku`、`InteractionFollow`、`InteractionGift`、`InteractionShare`、`InteractionLike`、`WebLiveStartEvent`、`OpenLiveStartEvent`、`OpenLiveEndEvent`、`OnlineRankEvent`、`OnlineRankCountEvent`、`OnlineRankTopEvent`、`LikeInfoUpdateEvent`、`WatchedChangeEvent`、`StopLiveRoomListEvent`、`RoomRealTimeMessageUpdateEvent`、`PopularRankChangedEvent`、`HotRankChangedEvent`、`HotRankSettlementEvent`、`AreaRankChangedEvent`、`RoomChangeEvent`、`ChangeRoomInfoEvent`、`RoomSkinMsgEvent`、`RoomSilentOnEvent`、`RoomSilentOffEvent`、`RoomBlockMsgEvent`、`RoomAdminsEvent`、`RoomAdminEntranceEvent`、`RoomAdminRevokeEvent`

> 两个 `OpenLive*` 事件类保留定义以保导入兼容，但本特性不产生它们（无开放平台链路）。

### 2.4 消息与异常

- `Message`、`MessageSegment`（`nonebot.adapters` 的 dataclass 子类，需 `nonebot2>=2.4.2`）
- `AdapterException`、`ActionFailed`、`ApiNotAvailable`、`NetworkError`

### 2.5 数据模型（31 个）

`AdminLevel`、`Badge`、`BatchComboSend`、`BlindGift`、`ComboInfo`、`DanmakuCombo`、`Frame`、`Game`、`Gender`、`GuardLevel`、`LiveStatus`、`MasterData`、`MasterExp`、`MasterInfo`、`MasterLevel`、`Medal`、`NewPendants`、`OfficialVerify`、`OfficialVerifyType`、`Rank`、`RankChangeMsg`、`Room`、`RoomNews`、`SilentUser`、`SilentUserListData`、`SpecialGift`、`StudioInfo`、`User`、`UserRoomStatus`、`VoteCombo`、`VoteOption`

`WebMedal` 与 `Bot`、`Config`、`Packet` 维持上游的“非顶层导出”状态。

## 3. Bot 行为契约

### 3.1 `WebBot` API 方法（`call_api` 可调用的公共属性）

| 方法 | 语义 | 落库实现 |
|------|------|----------|
| `send_danmaku(room_id, message, mode=1, reply_mid=0)` | 发送公开弹幕 | `Api(operate.send_danmaku)` + 库 csrf 注入 |
| `get_room_info(room_id)` | 房间详情 | `Api(live_info.get_info)` |
| `get_user_room_status(mid)` | 用户直播状态 | `Api(live_info.get_room_info_old)` |
| `get_master_info(uid)` | 主播信息 | `Api(live_info.info)` |
| `add_silent_user(room_id, tuid, hour, msg="", visit_id="")` | 禁言 | `Api(operate.add_block)` |
| `get_silent_user_list(room_id, ps=1, visit_id="")` | 禁言列表 | `Api(info.black_list)` |
| `del_silent_user(room_id, silent_id, visit_id="")` | 解除禁言 | `Api(silent_user_manage.del_room_block_user)` |

- 全部方法保持关键字可用、参数默认值不变；返回值为对应模型对象（`Room`、`MasterData` 等），与上游一致。
- `Bot.send(event, message)` 仅发送公开弹幕；`reply_message` / `at` 段推导 `reply_mid` 的规则保持上游行为。
- `_call_api` 只分发公共属性；私有名或未注册名抛 `ApiNotAvailable`（与上游一致）。

### 3.2 事件取值方法

| 方法 | 行为 |
|------|------|
| `event.get_user_id()` | 网页事件返回 `uid`；开放平台事件保留 `open_id` 优先逻辑（本次无产出路径） |
| `event.get_session_id()` | 仅 `DanmakuEvent`（`room_uid`）与 `SuperChatEvent`（`room_uid_id`）实现；其余抛 `ValueError` |
| `event.get_type()` | `message` / `notice` / `metaevent` |
| `event.get_event_name()` | 与上游表一致（如 `danmaku`、`send_gift`、`guard_buy`） |
| `event.is_tome()` | `DanmakuEvent` 与 `SuperChatEvent` 按上游规则；其余默认 `False` |

### 3.3 事件字段兼容性

- 字段名与嵌套模型形状与上游 0.2.6 一致；`INTERACT_WORD_V2` / `ONLINE_RANK_V3` 的字段仍为 betterproto 生成的 `Message` 类型。
- 修复项（FR-010a）只改变“能否产生事件”与勋章点亮状态取值，不重命名任何公共字段：
  - 网页 `DANMU_MSG`：接受无顶层 `data` 的帧，字段仍从 `info` 解析。
  - `SuperChatEvent`：`message_id` / `price` 取值改为不触发预求值错误的写法。
  - 勋章：`is_light` 与 `is_lighted` 双写法都接受，`is_lighted` 为规范字段。

## 4. 生命周期契约

| 阶段 | 必须发生 | 必须不发生 |
|------|----------|-----------|
| `adapter.startup` | 校验配置 → 取账号 → 按策略建立订阅 | 任何网络请求先于配置校验 |
| 运行中 | 心跳保活、退避重连、事件分发 | 单个处理器异常终止房间循环 |
| `adapter.shutdown` | 取消全部任务、关闭连接与客户端、幂等 | 遗留任务或在关闭后重连 |
