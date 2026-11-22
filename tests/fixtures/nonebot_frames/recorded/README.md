# 真实录制帧（第二组样本）

本目录的 `*.jsonl` 来自 2026-11-22 对两个真实直播间的只读录制
（`scripts/record_nonebot_frames.py`），用途是校验合成样本之外的**结构真实性**：
字段布局、`cmd` 取值与嵌套层级都取自线上帧，个人内容字段已替换为占位值。

## 采集信息

| 房间 | 真实房间号 | 时间（本机时区） | 时长 | 产出 | 本目录保留 |
|------|-----------|------------------|------|------|-----------|
| `6` | `7734200` | `2026-11-22T23:03:46` | 90 秒 | 8 `cmd` / 28 帧 | 6 已建模 + 2 未建模 |
| `21452505` | `21452505` | `2026-11-22T23:06:47` | 90 秒 | 13 `cmd` / 358 帧 | 2 已建模 + 2 未建模 |

两个房间录制时均 `live_status=1`，均使用匿名凭据（`LOG_IN_NOTICE` 帧即为匿名提示）。
每 `cmd` 只保留首帧。

## 脱敏与精简（相对 `raw/`）

- 用户名 / 头像 / uid 由录制脚本替换为 `user` / 序号（本目录内 `uid` 为 `2`、`3`、`123` 等占位值）。
- `DANMU_MSG` 的弹幕正文、`user_hash`、`id_str`，以及 `info[2]` 中残留的真实昵称与 uid 已人工替换；
  只保留真实字段布局（**无顶层 `data`**、`cmd` 无 `:4:0:2:2:1` 后缀、`info[0][15]` 内嵌 `extra` / `user`）。
- `ENTRY_EFFECT` 的 `copy_writing` / `copy_writing_v2` 中的真实昵称替换为 `<%user%>`；
  `POPULAR_RANK_CHANGED` 的跳转 URL 中 `anchorId` 归零。
- `STOP_LIVE_ROOM_LIST` 的房间号截取前 3 个；`LIKE_INFO_V3_CLICK` 的 `uname_color`
  被脱敏脚本误替换为 `user`，已改为空串（字段类型为 `str`）。

## 覆盖与缺口

| 类别 | 覆盖 |
|------|------|
| 已录制且已建模 | `DANMU_MSG`、`LIKE_INFO_V3_CLICK`、`LIKE_INFO_V3_UPDATE`、`ONLINE_RANK_COUNT`、`POPULAR_RANK_CHANGED`、`ROOM_REAL_TIME_MESSAGE_UPDATE`、`STOP_LIVE_ROOM_LIST`、`WATCHED_CHANGE` |
| 已录制但未建模 | `ENTRY_EFFECT`、`HOT_ROOM_NOTIFY`、`LOG_IN_NOTICE`、`POPULARITY_CHANGE`（真实流量存在；适配器按未知 `cmd` 记录并跳过，见 `test_recorded_unknown_commands_are_skipped`） |
| 已录制但**未入库** | `INTERACT_WORD_V2`、`ONLINE_RANK_V3`（betterproto 载荷内的 base64 含真实昵称 / 头像 URL，需 pb 级重编码才能安全入库；已在录制会话中确认可正确解析，结构覆盖由合成样本承担）；`NOTICE_MSG`（`msg_common` / `msg_self` 内嵌真实昵称） |
| 仍只有合成样本 | `HOT_RANK_SETTLEMENT`、`ROOM_ADMINS` 等低频 `cmd`：两个 90 秒录制窗口内均未出现，仅由 `../*.jsonl` 合成样本覆盖（research D13） |

## 约束

- 不得把 `raw/` 的原始帧直接放进本目录：原始帧仍含他人昵称、弹幕正文与哈希。
- 用例只读本目录，不触网（`tests/test_offline_nonebot_frames.py`）。
- 修改样本必须同步更新 `tests/test_offline_nonebot_frames.py` 的 `RECORDED_EXPECTATIONS` 快照。
