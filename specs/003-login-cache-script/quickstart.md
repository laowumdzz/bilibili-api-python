# Quickstart 验证指南: 测试登录凭证流程迁移至独立脚本

**Date**: 2026-09-03 | **Spec**: [spec.md](spec.md) | **Contracts**: [cli.md](contracts/cli.md) · [module-api.md](contracts/module-api.md)

按序执行以下场景即可端到端验收。真机交互场景（扫码 / 短信）需人工参与；其余可全自动。

## 前置条件

- uv 环境就绪：`uv sync`（含 dev 依赖）
- 工作区干净（验收涉及缓存文件与提示输出对照）

## 场景 1: 离线快速路径与门禁（全自动）

```bash
uv run pytest -m "not integration"
uv run python scripts/lint.py
```

**预期**: 离线用例全绿（含迁移后的 `test_offline_login_cache.py`，其导入已指向 `scripts._login_cache`）；门禁全绿（ruff 对 `tests/`、`scripts/` 阻断通过，pyrefly / 棘轮 / 文档漂移不受影响）。

## 场景 2: 脚本用法错误路径（全自动）

```bash
uv run python scripts/login_and_cache.py
```

**预期**: 输出用法提示（qrcode / phone 二选一），退出码 2，不出现任何二维码或输入提示。

## 场景 3: 独立脚本扫码登录 + 缓存写入（真机，US1）

```bash
uv run python scripts/login_and_cache.py qrcode
```

**预期**:
1. 终端渲染二维码并提示扫码；手机确认后输出登录成功与缓存文件路径，退出码 0。
2. 全程输出不含凭据字段值（对照 [contracts/cli.md](contracts/cli.md) 输出约束）。
3. 用 `uv run python -c "from scripts._login_cache import load_cache, CacheStatus; r = load_cache(); print(r.status)"` 确认缓存可读且合法（应输出 `CacheStatus.OK`，不打印字段值）。

## 场景 4: 测试零交互复用缓存（真机，US1）

```bash
uv run pytest tests/test_readonly_smoke.py -m integration -v
```

**预期**: 需登录用例自动使用缓存凭据（输出"使用 TEMP 缓存的临时登录凭据（有效性校验通过）"类提示），无任何登录交互。

## 场景 5: 测试命令 `--login` 行为兼容（真机，US2）

```bash
uv run pytest tests/test_readonly_smoke.py -m integration --login qrcode
```

**预期**: 交互流程、成功提示（含缓存路径）、中止行为与迁移前一致；对照基线见 [research.md](../003-login-cache-script/research.md) R8。补充抽查中止语义：出现二维码后按 Ctrl+C，确认提示"临时登录被用户中断"、退出测试流程且既有缓存文件未被修改。

## 场景 6: 统一缓存刷新（真机，US3，可选）

构造过期缓存（人工将缓存内容替换为过期凭据 + 真实 `ac_time_value`），分别经脚本与测试两入口触发，确认：过期 → 刷新成功 → 回写缓存，两入口提示语义一致；缺少 `ac_time_value` 的过期缓存被删除并回退到环境变量 / cookie 来源。

**预期**: 两入口处理结果与消息语义一致（状态机见 [data-model.md](data-model.md) E3）。

## 验收对照

| 场景 | 对应验收 |
|------|---------|
| 1 | SC-005（离线测试与门禁全绿） |
| 2 | FR-001（无参输出用法并退出，spec 澄清 Q1） |
| 3 | FR-001 / FR-002 / FR-006 / US1 场景 1（立即写缓存，spec 澄清 Q2） |
| 4 | US1 场景 2 / SC-001（零交互复用） |
| 5 | FR-003 / FR-005 / US2 / SC-002（行为兼容、中止不写缓存） |
| 6 | FR-004 / US3 / SC-003（统一缓存与刷新逻辑） |
