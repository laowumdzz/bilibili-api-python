# Quickstart: 修复网页端二维码登录凭据获取失效

**Feature**: 002-qrcode-login-cookie-fix | **Date**: 2026-09-03

三级验证：离线（无网络无凭据，CI 可跑）→ 门禁 → 真机端到端。行为判据见 [contracts/api.md](contracts/api.md)，字段映射与状态机见 [data-model.md](data-model.md)。

## 0. 前置

```bash
uv sync                                   # 确保 .venv 就绪
```

## 1. 离线验证（无需凭据、无网络）

```bash
uv run pytest tests/test_offline_login_v2.py tests/test_offline_api_core.py -v
uv run pytest -m "not integration"        # 全量离线回归
```

**期望**：

- 新增用例全绿，覆盖：`Api.request_with_cookies` 经 fake client 返回 `(处理数据, cookies)`；`check_state` 四状态判定不变；DONE 时凭据四项必需字段非空；缺任一必需字段抛 `ArgsException` 且消息不含字段值；Cookie 名大小写不敏感映射；buvid 机会性填充。
- 既有离线用例零失败（SC-003）。

## 2. 门禁

```bash
uv run python scripts/lint.py
uv run python scripts/doc_gen.py && git diff --exit-code docs/modules/
```

**期望**：全绿；类型棘轮只减不增；`docs/modules/` 与新 docstring 无漂移。

## 3. 真机端到端（需要手机 B 站 App，人工扫码）

### 3a. 验收脚本

```bash
uv run python scripts/qrcode_login.py
```

**期望流程**：终端渲染二维码 → 手机扫码并确认 → 脚本轮询至完成 → 输出凭据四项必需字段的**非空性校验结果**（只打印"已取得/为空"或字段名与长度，不打印值）→ 用凭据调用一个需登录态的只读接口并输出"登录身份已识别"。

> 脚本当前为最小骨架（仅生成二维码），轮询与校验部分随实现任务补全。

**通过判据（SC-001 / SC-002）**：凭据四项字段全部非空；只读接口识别登录身份；不再出现"提示成功但凭据为空"。

### 3b. 联动复验（特性 001 路径）

```bash
uv run pytest --login qrcode -m "not integration"
```

**期望**：扫码确认后凭据成功写入 TEMP 缓存文件、后续用例零交互复用（此为特性 001 被本缺陷阻塞的"扫码确认落缓存"验收项，修复后应恢复可用）。

### 3c. 异常路径抽查（可选）

轮询过程中在手机上**取消**确认或等待二维码过期：期望分别维持 CONF / TIMEOUT 状态行为不变（FR-006）。
