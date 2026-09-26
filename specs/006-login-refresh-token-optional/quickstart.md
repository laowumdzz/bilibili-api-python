# Quickstart: 验证扫码登录不再强制 ac_time_value 非空

> Phase 1 输出。 runnable 验证指南：离线用例证明新行为与回归，门禁证明工程合规，真机验收证明端到端无回归。"B 站不下发 refresh_token"无法人为构造，该场景由离线 mock 用例覆盖（SC-001）。

## 前置

```bash
uv sync                                   # 建好 .venv（含 dev 组）
# 无需任何 BILI_* 凭据即可完成下述离线验证与门禁
```

## 1. 离线行为验证（核心，无网络无凭据）

```bash
uv run pytest tests/test_offline_login_v2.py -v
```

预期关键用例：

- 新行为用例（由旧 `test_check_state_web_missing_refresh_token_raises` 反转 + 新增空串场景）：mock 响应 Cookie 齐全、无 `refresh_token`（或为 `""`）→ `check_state()` 返回 `DONE`、`get_credential()` 成功、`sessdata` / `bili_jct` / `dedeuserid` 为下发值、`ac_time_value == ""`、`credential.has_ac_time_value() is False`。
- 回归保留用例：缺任一必需 Cookie / Cookie 空串 → 仍抛 `ArgsException` 且消息含字段名不含值；TV 通道凭据构造、SCAN / CONF / TIMEOUT 判定、DONE 幂等不变。

```bash
uv run pytest tests/test_offline_login_cache.py -v   # 缓存链路回归：可选键缺失合法性等
uv run pytest -m "not integration"                   # 全量离线套件
```

## 2. 工程门禁（宪法 III，含文档联动）

```bash
uv run python scripts/doc_gen.py        # check_state docstring 已变更，必须先再生成
uv run python scripts/lint.py           # ruff → format → pyrefly → 棘轮 → 文档漂移，须全绿
```

## 3. 真机端到端验收（正常下发场景无回归，SC-003）

```bash
uv run python scripts/login_and_cache.py qrcode
```

预期：终端出码 → 手机扫码确认 → 提示"临时登录成功，凭据已写入缓存文件"→ 退出码 0。随后：

```bash
uv run pytest -m readonly
```

预期：凭据被识别（缓存文件含 ac_time_value 键的正常场景全字段可用）；再跑一次 `uv run pytest -m integration` 观察缓存校验 / 刷新链路无异常（可选，注意限速）。

验收要点对照：行为契约见 [contracts/library-api.md](contracts/library-api.md)，字段分层与校验矩阵见 [data-model.md](data-model.md)。

## 4. 完成判据

- [ ] 离线新行为用例通过（缺 / 空 refresh_token → DONE + 空值凭据）
- [ ] 必需 Cookie 报错、TV、状态判定、缓存链路回归用例全部通过
- [ ] `scripts/lint.py` 全绿（docstring 已同步、docs/modules 无漂移）
- [ ] 真机扫码登录成功、退出码 0、缓存写入、readonly 集成用例通过
