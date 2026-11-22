# Quickstart: NoneBot 直播适配器融合验收

**Feature**: `012-nonebot-adapter-fusion` | **Date**: 2026-11-22

本文件只写「怎么验收」，不写实现。命令均在仓库根执行，环境由 uv 管理。

## 0. 前置

```bash
uv sync                      # 安装依赖（含 dev 组）
uv run python install.py     # 初始化 Git Hooks（首次）
```

- 需凭据的步骤另见 §5，其余全部离线可跑。
- 未安装 NoneBot 运行时时，`import bilibili_api` 必须仍然成功。

## 1. 导入与身份（SC-001 / FR-001）

```bash
uv run python -X utf8 -c "import nonebot.adapters.bilibili_live as a, bilibili_api.nonebot.adapters.bilibili_live as b; print(a.DanmakuEvent is b.DanmakuEvent)"
```

期望：输出 `True`；随后导入清单脚本（`tests/test_offline_nonebot_events.py::test_public_symbols`）逐项校验 41 个事件类、6 个基类、31 个模型、4 个异常、2 个消息类是否存在。

## 2. 事件保真与缺陷修复（SC-002 / SC-010）

```bash
uv run pytest tests/test_offline_nonebot_events.py tests/test_offline_nonebot_frames.py -q
```

覆盖点：

| 样本 | 期望 |
|------|------|
| 网页 `DANMU_MSG`（无顶层 `data`） | 产出 `DanmakuEvent`，字段与快照一致 |
| `SUPER_CHAT_MESSAGE` / `_JPN` | 产出 `SuperChatEvent`，不再抛 `KeyError` |
| 带粉丝勋章的 `INTERACT_WORD` / `SEND_GIFT` / `LIKE_INFO_V3_CLICK` | 产出事件，`is_lighted` 与原始 `is_light` 一致 |
| `INTERACT_WORD_V2` / `ONLINE_RANK_V3` | betterproto 字段解出且形状不变 |
| 畸形帧 / 未知 `cmd` | 记录并跳过，不影响后续帧 |
| 真实录制帧（`tests/fixtures/nonebot_frames/recorded/`） | 8 个已建模 `cmd` 结构回放与快照一致；`ENTRY_EFFECT` / `POPULARITY_CHANGE` 等未建模 `cmd` 只记录并跳过 |

## 3. 配置校验（SC-011 / V-01..V-10）

```bash
uv run pytest tests/test_offline_nonebot_config.py -q
```

逐项构造非法配置，断言错误文本满足 `contracts/config.schema.md` §3：cookie 配置、开放平台配置、缺失 uid、重复 uid、房间超限、轮询参数越界、驱动不支持 WebSocket。**断言错误文本中不含任何凭据字段值**。

## 4. 调度与连接时机（SC-003 / SC-003a / SC-004 / SC-012）

```bash
uv run pytest tests/test_offline_nonebot_scheduler.py -q
```

| 场景 | 断言要点 |
|------|----------|
| 首个账号刷新失败 | 该账号名下全部房间切到下一账号，5 秒内恢复，日志凭据零命中 |
| 单房间心跳超时 | 仅该房间重连，其它房间连接数不变 |
| AUTO 开播/下播 | 开播后一个轮询周期内连接、下播后断开 |
| 50 房间 | 同时在建连接数不超过 `max_concurrent_connects`；关闭后任务与连接归零，且等待超过一个退避窗口后不再重连 |
| 存储加载次序 | 适配器封装层先 `load()` 再校验/写回：预置两个账号后启动，账号数不得被清空（research D9 的回归锁） |
| 凭据日志 | 打开适配器调试日志跑一遍切换流程，输出中凭据字段命中数为 0 |

用假时钟与假客户端驱动，不触网。

## 5. 真实连接冒烟（集成层）

```bash
uv run pytest tests/test_nonebot_live.py -q          # 匿名可连则直接跑；需登录时缺凭据自动跳过
uv run pytest tests/test_nonebot_live.py -q --login qrcode   # 需要时临时登录
```

验收口径：建立一次真实弹幕连接，收到至少一帧业务事件后主动断开；不发送任何弹幕、不做任何写操作。标记口径按宪章 IV：WS 订阅不属于 GET 式读请求，因此**不声明 `readonly`**；匿名不可连时改为 `integration` + `cred1` 并走 `credential` fixture。

## 6. 打包完整性（SC-007）

```bash
uv build --wheel
uv run python -X utf8 -c "import zipfile,glob; w=sorted(glob.glob('dist/*.whl'))[-1]; n=zipfile.ZipFile(w).namelist(); print([x for x in n if x.startswith('nonebot/')][:5]); print('bilibili_api/nonebot/adapters/bilibili_live/__init__.py' in n)"
```

期望：同时出现 `nonebot/adapters/bilibili_live/__init__.py` 与库内实现路径；`nonebot/__init__.py` **不出现**（不得覆盖真实 nonebot2）。

## 7. 门禁与文档（SC-005 / SC-006）

```bash
uv run python scripts/lint.py
uv run --with "mypy==1.18.2" python scripts/doc_gen.py
git diff --exit-code docs/modules
```

期望：ruff / pyrefly / 类型棘轮 / 文档漂移全绿；`pyproject.toml` 与 `scripts/lint.py` 中没有针对适配器目录的新增排除项。

## 8. 许可与归属（SC-008）

```bash
uv run python -X utf8 -c "import pathlib;t=pathlib.Path('THIRD_PARTY_NOTICES.md').read_text(encoding='utf-8');print(all(k in t for k in ('nonebot-adapter-bilibili-live','MIT','3f2c9bc2e74e02eaeb1a2192335f84eb3391782e','MingxuanGame')))"
```

期望：输出 `True`；README 首屏仍保留 fork 来源声明，并新增本融合的来源说明。

## 9. 破坏性变更告知（SC-011）

README / 迁移段必须给出两段可复制内容：

1. 把账号写入凭据存储的调用示例；
2. 用 `uid` 改写 `BILIBILI_LIVE_BOTS` 的前后对照。

运行 §3 的用例可同时验证「旧配置会失败且提示指向这两段」。
