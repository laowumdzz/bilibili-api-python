# Implementation Plan: NoneBot 直播适配器融合

**Branch**: `nonebot` | **Date**: 2026-11-22 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/012-nonebot-adapter-fusion/spec.md`

## Summary

把 `nonebot-adapter-bilibili-live` 0.2.6（MIT，41 个可实例化事件、约 4k 行）融合进本仓库：适配器以 `nonebot.adapters.bilibili_live` 导入路径交付，实现代码落在 `bilibili_api/nonebot/adapters/bilibili_live/`，仓库根放一层只做转发的 `nonebot/adapters/bilibili_live/__init__.py`；登录态、账号与网络全部下沉到库——`Credential` + `SQLiteCredentialStoreManager` 管账号，`BiliAPIClient` 管 HTTP 与 WebSocket（默认实现由 NoneBot 驱动承载），反爬要素复用库内 WBI / buvid 实现；弹幕帧解包、事件模型与 betterproto 数据类型保留适配器既有形态，并修复上游 0.2.6 会让主路径失效的三处缺陷（网页 `DANMU_MSG` 被丢弃、醒目留言 `KeyError`、勋章字段校验失败）。新增多账号调度（按插入顺序选号、凭据失效刷新失败则整号切换）与三种连接时机（ON / AUTO / MANUAL），AUTO 逐个查询房间开播状态并全局节流。

## Technical Context

**Language/Version**: Python ≥ 3.10（宪章 V；上游 `target-version=py39` 的写法与 `typing_extensions.override` 全部按 3.10 基线改写）

**Primary Dependencies**:
- 新增可选依赖（`[project.optional-dependencies] nonebot`）：`nonebot2>=2.5.0`、`betterproto>=1.2.5,<2`
  - `nonebot2` 下限取 2.5.0 而非上游的 2.4.2：2.4.x 的 aiohttp 驱动在 `WSMsgType.CLOSED` 上会漏出 `TypeError`，会让弹幕读循环异常而非正常关闭（research D14）。
- 已有核心依赖直接复用：`brotli`（弹幕解压）、`pydantic`（事件与配置模型）、`aiosqlite` + `platformdirs`（凭据存储）、`aiohttp`（库默认客户端）
- 不引入 `zlib` 之外的压缩库（标准库覆盖 zlib/gzip）

**Storage**: 复用 `SQLiteCredentialStoreManager` 的加密落盘（RSA-2048 + AES-GCM，schema v1）；本特性不新增存储格式，也不做凭据迁移导入

**Testing**: pytest（`asyncio_mode=auto`）；离线用例覆盖帧解析/事件映射/调度器/配置校验；真实连接验收归集成层（只读语义、缺凭据自动跳过）

**Target Platform**: 跨平台库（开发 Windows，CI Linux Python 3.10 / 3.13）；NoneBot 侧要求驱动同时实现 `HTTPClientMixin` 与 `WebSocketClientMixin`（纯 httpx 驱动只能跑 REST、不能跑弹幕，启动期即报错）

**Project Type**: 库 + 同仓集成适配器（单一发行物，双导入路径）

**Performance Goals**: 1000 帧离线分发 ≤ 1 秒；单进程 50 房间；AUTO 轮询同轮相邻请求间隔 ≥ 2 秒、默认每房间 60 秒一轮

**Constraints**: 禁止上传 PyPI（宪章）；版本单一来源 `BILIBILI_API_VERSION`；pyrefly 零容忍、无新增豁免；`docs/modules/` 只能由 doc_gen 生成；任何日志/异常/事件 repr 不得出现凭据字段值

**Scale/Scope**: 约 4k 行上游代码移植 + 3 处缺陷修复；41 个事件类、8 个 REST 端点、4 种连接时机取值、≤ 50 房间/进程

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| 原则 | 判定 | 依据与落实方式 |
|------|------|----------------|
| I. 异步优先 | PASS | 适配器全异步；HTTP/WS 只经 `BiliAPIClient`；除驱动承载客户端实现内部外不得直接使用驱动；库代码无 `asyncio.run()` |
| II. 声明式 API 定义 | PASS | 适配器用到的 8 个端点全部已存在于 `bilibili_api/data/api/live.json`（`info.danmu_info`、`live_info.get_info`、`live_info.get_room_info_old`、`live_info.info`、`operate.send_danmaku`、`operate.add_block`、`info.black_list`、`silent_user_manage.del_room_block_user`），无需改 registry；适配器自带 `wbi.py` 与 buvid 获取逻辑删除，改走 `_wbi` / `_anti_spider` |
| III. 质量门禁 | PASS（需工作量） | 适配器目录扩入 ruff 与 pyrefly 检查范围（`nonebot/**` 加入 includes，不做 exclude）；公共能力补中文 docstring 后重跑 doc_gen；不新增类型豁免 |
| IV. 分层测试 | PASS | 离线用例只做纯本地逻辑（含本机回环允许范围）；真实 WS 连接归集成层且仅读；不触碰 cred2/cred3 语义，不改变账号状态 |
| V. 兼容性与破坏性变更 | PASS（有破坏性） | 配置形态由 cookie 字符串改为凭据存储 uid 引用属破坏性变更，提交信息须带 `BREAKING CHANGE`；错误一律用 `bilibili_api/exceptions`；一个提交一件事 |
| 技术与安全约束 | PASS | 保留 GPL-3.0-or-later 并新增上游 MIT 归属；凭据零回显；反爬集中管理；不用 `print()` |

**Gate 结论**: 无未申辩的违规项。唯一需要显式记账的是「双导入路径」与「保留 betterproto」两项复杂度，见 Complexity Tracking。

### Post-Design 复核（Phase 1 之后）

| 复核点 | 结论 | 依据 |
|--------|------|------|
| 原则 I：传输层是否绕开抽象 | 未绕开 | 适配器全部经 `get_client()`；唯一直接使用驱动的位置在 `NoneBotClient` 内部，符合「自定义客户端实现」例外 |
| 原则 I：异步是否被同步操作污染 | 未污染 | `download_*` 走 `stream_request`；无 `time.sleep` / 同步 HTTP |
| 原则 II：是否新增硬编码接口 | 未新增 | 8 个端点全在 `data/api/live.json`，无需改 registry（research D5） |
| 原则 V：异常体系 | 合规 | 驱动异常归一为 `NetworkException`；凭据/响应码异常直接透传（contracts/client-bridge.md §3） |
| 安全约束：凭据零回显 | 需专门约束 | 库自身 `request_log` 会携带 `Credential` 与 cookie，适配器 MUST NOT 开启（research D12） |
| 质量门禁：文档 | 工作量确认 | 适配器公共能力需补中文 docstring 并重跑 doc_gen；检查范围扩到 `nonebot/**`，不新增排除 |
| 依赖新增 | 已申辩 | `nonebot2>=2.5.0`（2.4.x 关闭帧缺陷）与 `betterproto>=1.2.5,<2`（事件字段类型）均为需求驱动，且置于可选 extra |

## Project Structure

### Documentation (this feature)

```text
specs/012-nonebot-adapter-fusion/
├── plan.md              # 本文件
├── research.md          # Phase 0 输出（决策与依据）
├── data-model.md        # Phase 1 输出（实体、状态机、校验规则）
├── quickstart.md        # Phase 1 输出（可执行验收步骤）
├── contracts/           # Phase 1 输出（对外契约）
│   ├── adapter-public-api.md
│   ├── config.schema.md
│   └── client-bridge.md
├── checklists/
│   └── requirements.md
└── tasks.md             # Phase 2 输出（$speckit-tasks 生成）
```

### Source Code (repository root)

```text
bilibili_api/
├── clients/
│   ├── __init__.py              # 现有内置客户端注册表（不得 eager import NoneBot 客户端）
│   └── NoneBotClient.py         # 新增：由 NoneBot 驱动承载的 BiliAPIClient 实现（含 4 个 ws_* 方法）
├── nonebot/                     # 新增：适配器实现（真正的代码）
│   ├── __init__.py
│   └── adapters/
│       ├── __init__.py
│       └── bilibili_live/
│           ├── __init__.py      # 公共符号再导出（与上游 0.2.6 一致）
│           ├── adapter.py       # Adapter：生命周期、房间监听、分发
│           ├── accounts.py      # 新增：多账号调度（选号/刷新/切换/失败分类）
│           ├── scheduler.py     # 新增：连接时机策略（ON / AUTO / MANUAL）与开播轮询
│           ├── bot.py           # Bot 基类 + WebBot（API 调用改走库）
│           ├── config.py        # 配置模型（uid 引用 + 房间 + 策略参数）
│           ├── const.py         # 端点与时间常量（端点改引 live.json 键名）
│           ├── event.py         # 事件模型与 cmd 注册表（含三处缺陷修复）
│           ├── exception.py     # 适配器自有异常（继承库异常体系可对齐部分）
│           ├── log.py           # logger 包装（凭据零回显）
│           ├── message.py       # Message / MessageSegment
│           ├── packet.py        # 帧编解码（zlib / brotli）
│           ├── models/{__init__,event,room,user_manage,open}.py
│           └── pb/{__init__,fans_club,interact_word_v2,online_rank_v3,user_dagw}.py
├── data/api/live.json           # 不改（端点已覆盖）
└── utils/                       # 复用：_credential / credential_store* / _wbi / _anti_spider / _session

nonebot/
└── adapters/
    └── bilibili_live/
        └── __init__.py          # 新增：仅转发的兼容入口（不实现逻辑）

tests/
├── test_offline_nonebot_events.py      # 帧样本 → 事件映射快照（含缺陷帧）
├── test_offline_nonebot_scheduler.py   # 选号 / 刷新失败切换 / 连接时机（假时钟）
├── test_offline_nonebot_config.py      # 配置校验与错误文案（cookie 拒绝、uid 缺失、超限）
├── test_offline_nonebot_packet.py      # 帧编解码与畸形帧
├── test_offline_nonebot_client.py      # 驱动承载客户端的请求/WS 语义（假驱动）
└── test_nonebot_live.py                # 集成（readonly）：真实连接接收一帧事件后退出

THIRD_PARTY_NOTICES.md                  # 新增：上游 MIT 全文、版权行、来源与基线 commit
```

**Structure Decision**: 采用「实现放在 `bilibili_api/nonebot/...`、根目录 `nonebot/adapters/bilibili_live/` 只做转发」的双路径结构。理由：库内路径自动被 ruff / pyrefly / doc_gen 覆盖，无需为代码本体开豁免；顶层 `nonebot` 片段只承担生态导入路径兼容，被打包实验证实可与真实 nonebot2 干净合并、且转发的类对象保持同一身份（`is` 为真）。驱动承载客户端单独成文件且不得被 `clients/__init__.py` 预先导入，避免未安装 nonebot2 时库无法导入。

## Complexity Tracking

| 复杂度 | 为什么需要 | 为什么更简单的方案不够 |
|--------|-----------|----------------------|
| 双导入路径（`bilibili_api.nonebot...` + `nonebot.adapters.bilibili_live`） | FR-001 要求现有插件零改动 | 只保留库内路径会让所有下游插件改 import；只保留 `nonebot.adapters` 路径则代码本体落在库检查范围外，需要新增 lint/类型排除，违反 FR-019 |
| 保留 betterproto 与 `pb/` 生成代码 | 事件字段类型直接是 `betterproto.Message`（`INTERACT_WORD_V2`、`ONLINE_RANK_V3`），替换会改变公共字段形状 | 改用库内 `pb_decoded` 字典需重写相关事件类字段，属破坏性变更且无法保证字段语义一致（spec 已裁决保留数据层） |
| 根目录新增 `nonebot/` 顶层目录 | 生态导入路径兼容 | 迁到 src 布局会牵动仓库全部路径假设（lint 路径、doc_gen、pyinstaller hook），超出本特性范围 |
