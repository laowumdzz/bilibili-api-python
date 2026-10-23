# Quickstart: 评审缺陷修复验收

**Feature**: 010-review-defect-fixes | **Date**: 2026-10-23

分层验收步骤。无凭据环境以第 1–3 节为完成判据（宪法 IV / spec Assumptions）；真机项（第 4 节）具备条件时补验。行为契约细节见 [contracts/](contracts/)，规则表见 [data-model.md](data-model.md)。

## 前置条件

```bash
uv sync                                   # 安装依赖
# registry（同步脚本相关验收需要；离线用例不需要，测试用 tmp fixture 自包含）
git -C bilibili-api-registry log --oneline -1   # 应为 df7a5f6 基线
```

## 1. 离线回归（逐项验证五项修复，SC-002 / FR-007）

```bash
uv run pytest tests/test_offline_api_core.py tests/test_offline_login_v2.py \
              tests/test_offline_exceptions_compat.py tests/test_offline_sync_api_registry.py -v
```

预期通过的关键用例（对应关系）：

| 修复 | 用例主题 | 断言位置 |
|------|----------|----------|
| 1 扫码轮询 | 本地回环服务器驱动真实 `check_state()` 全链路 | 客户端编码边界：服务端收到的查询参数全为标量，`x-bili-locale-json` / `x-bili-device-req-json` 为合法紧凑 JSON 字符串 |
| 1 统一层 | `_prepare_request` 对 dict 值参数输出 JSON 字符串 | 请求准备边界 |
| 2 请求头 | 构造传入 headers 值原样保留、交换分支头非空 | 请求准备边界 |
| 3 布尔 | data 布尔 0/1 留在请求体、params 不含该键、None 剔除与 params bool→int 不回归 | 请求准备边界 |
| 4 异常路径 | 22 条历史子模块路径逐一导入、`is` 同一、`__all__` 不变 | 导入边界 |
| 5 同步兜底 | tmp registry：未映射类别跳过 + 告警（含类别名与条目数）、三类别正确落位 | 脚本主流程 |

**修复前失败性抽查**（验证用例确有区分力，SC-001）：`git stash` 保存修复后回到缺陷态（或对 `bilibili_api/utils/_api.py` 的三处修复点做临时还原），仅跑扫码轮回环用例与 data 布尔用例——应失败；恢复后重跑——应通过。

## 2. 全量门禁（SC-002）

```bash
uv run pytest -m "not integration"      # 离线全量零失败
uv run python scripts/lint.py           # ruff / 阻断检查 / pyrefly / 棘轮 / 文档漂移全绿
```

## 3. 同步脚本真机口径（SC-004，对本机真实 registry）

```bash
uv run python scripts/sync_api_registry.py --dry-run
```

预期：计数与修复前语义一致——`registry REST 条目 609：已存在 609，registry 内重复 0，无映射跳过 0，本次新增 0`（汇总行新增"无映射跳过"计数项为设计内变更），`dry-run：未写入任何文件`；无 WARNING；`bilibili_api/data/api/` 无 `broadcast.json` 产生。

## 4. 真机验收（SC-001，需扫码环境）

```bash
uv run python scripts/login_and_cache.py qrcode   # 生成 → 扫码 → 轮询 → 凭据缓存全流程
uv run pytest -m cred0                             # 核心冒烟全绿（可选）
```

预期：轮询不再抛 `TypeError`，扫码后状态正常推进至成功，凭据写入 TEMP 缓存。

## 完成判据汇总

- [x] 第 1 节全部用例通过，且抽查证明扫码轮回环用例与布尔用例在缺陷态失败（2026-10-23：US1–US3 各用例在实现前逐项验证缺陷态失败）
- [x] 第 2 节门禁全绿（含 `docs/modules/` 零漂移）（2026-10-23：`scripts/lint.py` 全绿 + 离线全量 345 passed / 1 skipped）
- [x] 第 3 节 dry-run 计数与修复前语义一致，无未映射告警（2026-10-23：609 已存在 / 0 重复 / 0 无映射跳过 / 0 新增，无 WARNING，无 `broadcast.json`）
- [ ] （具备条件时）第 4 节真机扫码成功 —— **待补验**：本会话无扫码环境，SC-001 真机项不阻塞收口（spec Assumptions），具备条件时执行 `uv run python scripts/login_and_cache.py qrcode` 补验
- [x] `CHANGELOGS/UNRELEASED.md` 含异常导入路径恢复条目（FR-005）
