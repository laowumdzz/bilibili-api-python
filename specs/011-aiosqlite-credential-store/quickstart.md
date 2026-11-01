# Quickstart: 基于 aiosqlite 的凭据存储管理器实现

**Feature**: `011-aiosqlite-credential-store` | **Date**: 2026-11-01

端到端验收步骤。全程离线：不触外网、不用真实凭据、不改 B 站账号状态。接口细节见 [contracts/credential-store-api.md](./contracts/credential-store-api.md)，数据布局见 [data-model.md](./data-model.md)。

## 前置条件

1. 依赖就绪：`uv sync`（platformdirs 已入库）；确认 `uv.lock` 含 platformdirs / aiosqlite / pycryptodomex。
2. Credential 前置修复已合入（research.md D1）：`uv run python -c "from bilibili_api.utils._credential import Credential; print(Credential(sessdata='x', dedeuserid='1').model_dump_json())"` 能输出 JSON 而非抛 `ValueError`。

## V1: 离线测试套件全绿（对应 FR-011 / SC-005）

```bash
uv run pytest tests/test_offline_credential_store_sqlite.py -v
```

**预期**：全部 PASS。覆盖面须包含：增删改查回环、auto_persist 语义、同进程双实例与子进程两级"重启"恢复、插入顺序（乱序 uid + order_seq）、加密静态检查、密钥丢失 / 损坏、库截断 / 破坏、schema 版本不匹配、异常消息脱敏断言、50 账号 load 计时上限。

## V2: 跨进程重启恢复（SC-001）

用两段独立进程模拟"写入 → 完全重启 → 读出"（脚本由 tasks 阶段随测试提供，此处只描述行为口径）：

1. 进程 A：向自定义路径库写入 3 条乱序 uid 凭据（如 300 → 5 → 42），退出。
2. 进程 B：对同一库 `load()`，断言：`len == 3`、`get_all_uids()` 的首元素为 `300`（最早添加者，与 uid 数值序无关）、逐条取出字段与写入一致。

**预期**：全程无人工干预、无外网请求；两进程均只打印 uid 与布尔量，不打印凭据字段值。

## V3: 落盘零明文（SC-002 / FR-005）

对 V2 产出的库文件做二进制检索（假字段值 `fake_sessdata` / `fake_bili_jct` / `fake_dedeuserid` / `fake_buvid3` / `fake_buvid4` / `fake_ac_time_value`）：

```bash
grep -c "fake_sessdata" <db_path> || echo "0 hits"
```

**预期**：6 个假字段值 0 命中；文件头可见 `BACS` 魔数与 SQLite 头（结构存在、内容不可读）。

## V4: 密钥丢失显式失败（SC-003 / FR-006）

删除 `credentials.key` 后再次 `load()`：

**预期**：抛 `CredentialStoreCorruptException`，消息含"密钥"与"重新添加账号"字样、不含凭据值；库文件本体未被删除或清空。将 key 文件替换为随机垃圾字节 → 同样显式失败。

## V5: 库损坏与版本不匹配显式失败（US3 / FR-008 / FR-012）

1. 将库文件截断一半或覆写随机字节 → `load()` 抛 `CredentialStoreCorruptException`，且不自动重建文件。
2. 用 sqlite3 工具把 `meta.schema_version` 改为 `999` → `load()` 抛 `CredentialStoreVersionMismatchException`。

## V6: 合入门禁（SC-005 / 宪章 III）

```bash
uv run python scripts/lint.py
uv run --with "mypy==1.18.2" python scripts/doc_gen.py
uv run pytest -m "not integration"
```

**预期**：门禁全绿（ruff / pyrefly / 棘轮 / 文档漂移）；`docs/modules/` 出现 `SQLiteCredentialStoreManager` 与三个新异常的文档；离线全量测试零回归。

## V7: gitignore 兜底（FR-007）

确认 `.gitignore` 含存储文件与密钥文件条目；`git status` 不出现 `credentials.db` / `credentials.key`（默认位置在用户数据目录本就不在仓库内，此条为自定义路径落入仓库目录时的兜底）。

## 验收记录（2026-11-01，实现阶段）

| 项 | 结果 | 证据 |
|----|------|------|
| V1 套件全绿 | ✅ | `uv run pytest tests/test_offline_credential_store_sqlite.py` 19 passed：增删改查回环 / auto_persist / 同进程 + 子进程双级重启 / 乱序插入序 / 加密静态检查 / 密钥丢失损坏 / 库截断破坏 / 版本不匹配 / persist 回滚 / 跨 loop 防御 / 消息脱敏 / 50 账号计时 |
| V2 跨进程重启恢复 | ✅ | 两段独立子进程演示：进程 A 写入 300→5→42 后退出；进程 B `load()` 后 `len==3`、`get_all_uids()` 首元素 300（插入序，与 uid 数值序无关）、逐字段一致；全程仅打印 uid 与布尔量 |
| V3 落盘零明文 | ✅ | 二进制检索 6 个假字段值均 0 命中；文件头可见 `SQLite format 3` 与每记录 `BACS` 魔数 |
| V4 密钥丢失显式失败 | ✅ | 删除 key 后 `load()` 抛 `CredentialStoreCorruptException`，消息含"密钥""重新添加账号"、零凭据值，库文件字节不变；key 写为垃圾字节同样显式失败且不静默重建 |
| V5 库损坏 / 版本不匹配 | ✅ | 覆写垃圾字节 → `CredentialStoreCorruptException` 且文件不被重建；`meta.schema_version="999"` → `CredentialStoreVersionMismatchException`（消息含双方版本号） |
| V6 门禁 + 文档 | ✅⚠️ | doc_gen（mypy==1.18.2）重生成：`docs/modules/bilibili_api.md` 出现 `SQLiteCredentialStoreManager` 与三个新异常章节，STRICT 口径漂移 0；`uv run pytest -m "not integration"` 367 passed / 1 skipped。`scripts/lint.py` 的 ruff / pyrefly / 棘轮步被**本分支既有 WIP 项**阻断（见 tasks.md T015 注记），本特性文件零新增违规 |
| V7 gitignore 兜底 | ✅ | `git check-ignore -v credentials.db credentials.key` 命中新增两条；`git status` 无存储 / 密钥文件出现 |
