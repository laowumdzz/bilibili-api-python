# Contract: 配置 schema 与校验错误

**Feature**: `012-nonebot-adapter-fusion` | **载体**: NoneBot 插件配置（环境变量 `BILIBILI_LIVE_BOTS`）

配置是一个 JSON 数组（或含 `bots` 字段的对象，两种形态都接受），每项声明「用哪个账号监听哪些房间」。**账号只能是凭据存储里的 uid**，这是与上游 0.2.6 的破坏性差异（FR-004）。

## 1. 合法示例

```dotenv
BILIBILI_LIVE_BOTS='[
  {"uid": 10001, "room_ids": [544853, 21452505]},
  {"uid": 10002, "room_ids": [544853], "connect_timing": "auto"}
]'
```

等价的对象形态：

```dotenv
BILIBILI_LIVE_BOTS='{
  "connect_timing": "auto",
  "poll_interval": 60,
  "min_poll_interval": 2,
  "bots": [
    {"uid": 10001, "room_ids": [544853]}
  ]
}'
```

## 2. 字段与默认值

| 字段 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `uid` | int | — | 必填；必须存在于凭据存储 |
| `room_ids` | int[] | — | 必填；长短号均可，归一后去重 |
| `connect_timing` | `"on"` / `"auto"` / `"manual"` | 继承全局，全局默认 `"on"` | 连接时机 |
| `poll_interval` | float（秒） | `60` | AUTO 每房间一轮间隔 |
| `min_poll_interval` | float（秒） | `2` | 同轮相邻请求最小间隔；硬下限 2 |
| `max_rooms` | int | `50` | 去重后房间数上限 |
| `max_concurrent_connects` | int | `5` | 同时在连（握手/鉴权中）上限，≥ 1 且 ≤ `max_rooms` |
| `db_path` | str | 库默认目录 | 凭据存储数据库路径覆盖 |
| `key_path` | str | 库默认目录 | 凭据存储密钥路径覆盖 |

## 3. 非法配置与错误契约

所有校验错误必须在**启动期**抛出，且错误文本同时满足「指出哪一项错了」与「告诉用户怎么改」（FR-022 / SC-011）。任何情况下错误文本不得包含凭据字段值。

| 场景 | 触发条件 | 错误文本必须包含 |
|------|----------|------------------|
| 上游式 cookie 配置 | 任一项出现 `cookie` / `sessdata` / `bili_jct` 等键 | 「已改为 uid 引用」+ 写入凭据存储的调用示例 + uid 引用写法 |
| 开放平台配置 | 出现 `access_key` / `access_secret` / `app_id` / `identify_codes` | 「开放平台形态尚未支持」+ 指向后续特性 |
| 账号缺失 | `uid` 不在 `get_all_uids()` 中 | 缺失的 uid 列表 + 提示先写入凭据存储 |
| 账号重复 | 同一 `uid` 出现多次 | 重复的 uid |
| 房间超限 | 去重后房间数 > `max_rooms` | 实际数量、上限、超出的数量 |
| 轮询参数非法 | `min_poll_interval < 2` 或 `poll_interval < min_poll_interval` | 实际取值与允许范围 |
| 建连并发参数非法 | `max_concurrent_connects < 1` 或 `> max_rooms` | 实际取值与允许范围 |
| 房间号非法 | 非正整数 | 非法值所在项与字段名 |
| 驱动不支持 WebSocket | 启动时驱动缺 `WebSocketClientMixin` | 当前驱动名 + 需要支持 WebSocket 的驱动 |

## 4. 兼容性说明

- 上游的 `cookie` + `room_ids` 形态**不再可用**，属破坏性变更：提交信息须带 `BREAKING CHANGE`，README 给出迁移步骤。
- `access_key` 等开放平台字段不是“忽略即可”，而是**显式拒绝**，避免用户以为已生效（FR-018）。
- 环境变量名保持 `BILIBILI_LIVE_BOTS`，降低迁移成本。
