# NoneBot 直播适配器帧样本

本目录的 `*.jsonl` 是适配器事件层回归用的**固定帧样本**：每个文件对应一个
`cmd`（同一 `cmd` 的多个变体按行排列），每行是一个可直接交给
`Packet.new(OpCode.Command, 0, frame)` 的 JSON 帧；`HEARTBEAT.jsonl` 例外，
它是心跳回复的人气值载荷（用例以 `opcode=3` 构造）。

## 来源

- **合成层（已入库）**：按上游 0.2.6 事件字段契约构造的最小合法帧，覆盖
  `contracts/adapter-public-api.md` 列出的 41 个可实例化事件类（48 行样本，
  部分事件类由多个 `cmd` / 变体重复覆盖），并单独覆盖三处缺陷帧：
  1. `DANMU_MSG.jsonl`：网页 `DANMU_MSG`（**无顶层 `data`**，`cmd` 带
     `:4:0:2:2:1` 后缀）；
  2. `SUPER_CHAT_MESSAGE*.jsonl`：中 / 日文醒目留言（`price` / `rmb` 双形态）；
  3. `INTERACT_WORD.jsonl`：带粉丝勋章的进场帧（`is_light` 写法）。
- **真实录制层（已入库，`recorded/`）**：2026-11-22 对房间 6 与 21452505 的只读
  录制后人工脱敏与精简的第二组样本，只校验结构真实性（字段布局 / `cmd` 取值），
  不重复覆盖全部事件类。来源、脱敏步骤与未入库帧的取舍见 `recorded/README.md`。
- **原始录制层（不入库，`raw/`）**：`scripts/record_nonebot_frames.py` 以匿名
  凭据只读连接真实直播间，将收到的帧脱敏后写入 `raw/`（该目录的 `.gitignore`
  排除全部文件）。放入 `recorded/` 前必须人工剔除昵称、弹幕正文与哈希。

## 约束

- 帧内不得包含任何凭据字段值；录制脚本会把用户名 / 头像 / uid 替换为占位值。
- 用例只读本目录，不触网（`tests/test_offline_nonebot_frames.py`）。
- 修改样本必须同步更新 `tests/test_offline_nonebot_frames.py` 的
  `EXPECTATIONS` / `RECORDED_EXPECTATIONS` 快照。
