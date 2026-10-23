# Contract: registry 同步脚本 CLI

**Feature**: 010-review-defect-fixes | **契约对象**：`scripts/sync_api_registry.py` 的命令行行为（维护者视角）

本契约固化修复 5（FR-006 / SC-004）。类别映射增量与条目分流状态机见 [data-model.md](../data-model.md) 实体 3。

## 调用与退出码

```bash
uv run python scripts/sync_api_registry.py --dry-run   # 预览，不写任何文件
uv run python scripts/sync_api_registry.py             # 执行同步（纯增量写入）
```

| 退出码 | 语义 |
|--------|------|
| 0 | 成功（含"全部条目已存在、零新增"与"存在未映射类别跳过"的场景——跳过并告警不是失败） |
| 1 | registry 不可用（目录缺失 / 为空 / 结构不完整），输出含获取指引 |

## 类别行为契约

- **已映射类别**（本特性后含 `broadcast` / `cheese` / `opus` 共 36 项）：条目经 `resolve_target` 落位；`cheese` → 既有 `cheese.json`，`opus` → 既有 `opus.json`，`broadcast` → 目标文件无既有时经同步新建（惰性，不预先创建）。
- **未映射类别**（兜底，新增）：条目显式跳过，不崩溃（不抛 `KeyError`）；按类别聚合输出 `WARNING` 日志，**含类别名与条目数**；汇总 info 行含"无映射跳过"计数，与"已存在跳过"可区分。

## 输出形态

汇总行（INFO）：`registry REST 条目 N：已存在 A，registry 内重复 B，无映射跳过 C，本次新增 D`；每个未映射类别一行（WARNING）：`跳过未映射类别 <类别>：<条目数> 条待同步条目`。

## 不变量（本特性不改变）

- 纯增量：URL 已存在的条目一律不动；`gRPC` 目录与 `method=OTHER` 条目跳过；registry 的 `doc_source` / `notes` 等元数据不进入接口定义。
- 当前全量 registry（基线 `df7a5f6`）的预览计数语义与修复前一致：609 已存在、0 新增、0 无映射跳过、无未映射告警（三类别条目全部命中"已存在"；汇总行新增"无映射跳过"计数项为设计内变更，SC-004 修订口径）。
- registry 目录缺失 / 为空时仍以退出码 1 失败并打印获取指引（不因兜底逻辑放宽）。

## 验证锚点

- 离线：`tests/test_offline_sync_api_registry.py`（tmp fixture registry：映射落位、未映射跳过告警、三类别解析；`importlib.util.spec_from_file_location` 加载脚本，monkeypatch `REGISTRY_DIR` / `API_DIR` 模块常量）。
- 本机手动：对本机真实 registry 跑 `--dry-run`，比对计数与修复前语义一致（SC-004 修订口径，步骤见 [quickstart.md](../quickstart.md)）。
