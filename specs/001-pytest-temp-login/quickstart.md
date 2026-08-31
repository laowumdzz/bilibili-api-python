# Quickstart: pytest 临时登录凭据（--login）验证指南

**Feature**: 001-pytest-temp-login | **Date**: 2026-08-31

端到端验证本特性可用的可执行场景。命令均从仓库根目录发起（`uv run` 前缀，Windows Git Bash 同样适用）。

## 前置条件

- 已 `uv sync`（依赖齐全）；网络可达 bilibili.com；
- 一部装有 B 站 App 的手机（场景 2 / 3 需要），或一个可收短信的手机号（场景 2' 需要）；
- 观察缓存文件：路径为 `%TEMP%\bilibili_api_pytest_login.json`（Windows）或 `$TMPDIR/bilibili_api_pytest_login.json`（Unix），格式见 [contracts/cache-file-format.md](contracts/cache-file-format.md)。

## 场景 0：零回归（无 `--login`、无缓存）

```bash
rm -f "$TEMP/bilibili_api_pytest_login.json"    # 确保无缓存
uv run pytest -m "not integration"
```

**预期**：输出一条「缓存凭据文件不存在」类提示；离线用例全部执行；无任何交互；与特性引入前输出无实质差异（本仓库若存在 `.bilibili.cookie`，集成用例仍照常由它驱动）。

## 场景 1：离线单元测试

```bash
uv run pytest tests/test_offline_login_cache.py
```

**预期**：全绿——覆盖编解码、必需字段判定（空串/缺键/坏 base64/非对象 JSON）、凭据来源优先级合并等纯逻辑，全程无网络。

## 场景 2：扫码临时登录（主路径）

```bash
uv run pytest --login qrcode -m "not integration and not readonly" # 或按需选择用例子集
```

**预期**：终端出现 ASCII 二维码 → 手机扫码确认 → 测试以新登录态执行集成用例；结束后缓存文件存在，内容为一行 base64（`base64 -d` 后为含 `sessdata` 等键的 JSON）。若放置不扫，二维码超时后应自动换新并提示，连续 3 次后进程明确中止且**不产生**缓存文件。

## 场景 2'：手机号短信临时登录（备选通道）

```bash
uv run pytest --login phone -m "not integration and not readonly"
```

**预期**：按提示输入手机号（回车默认 +86）→ 终端给出本地极验链接，浏览器完成滑块 → 收到短信并输入验证码 → 登录成功后续表现与场景 2 一致。若触发风控二次验证，按提示再完成一次验证码输入。

## 场景 3：缓存复用（免二次登录）

```bash
uv run pytest -m integration   # 不带 --login
```

**预期**：全程零交互（不再出现二维码/输入提示），需凭据用例使用缓存凭据执行；缓存文件保持不变。

## 场景 4：内容损坏 → 删除 + 报错 + 跳过

```bash
echo "not-a-valid-base64-$$$" > "$TEMP/bilibili_api_pytest_login.json"
mv .bilibili.cookie /tmp/ 2>/dev/null || true   # 隔离既有来源，观察纯降级路径（可选）
unset BILI_SESSDATA BILI_CSRF BILI_DEDEUSERID
uv run pytest -m integration
```

**预期**：输出一条「缓存内容不合法，已删除」类错误；文件从磁盘消失；需凭据用例 skip；进程正常结束。验证后还原 `.bilibili.cookie`。

## 场景 5：缓存缺失 → 提示 + 跳过

```bash
rm -f "$TEMP/bilibili_api_pytest_login.json"
# 同场景 4 隔离 env / cookie 来源
uv run pytest -m integration
```

**预期**：一条「缓存凭据文件不存在」提示；需凭据用例 skip；离线用例不受影响。

## 场景 6：非法参数值

```bash
uv run pytest --login email
```

**预期**：立即以用法错误退出（如 `usage error` + 合法取值说明），不收集用例、不产生任何交互与缓存读写。

## 场景 7：过期凭据 → 刷新（可选，难以主动构造）

构造方式（二选一）：等待凭据自然过期；或将缓存中 `sessdata` 替换为另一账号失效值但保留结构（手工改 base64 内容）。

```bash
uv run pytest -m integration
```

**预期（刷新成功）**：无警告，用例执行，缓存文件被更新（mtime 变化）。
**预期（刷新失败，如无 `ac_time_value` 或令牌不可用）**：一条 warning 呈现 + 文件被删除 + 需凭据用例 skip + 进程正常结束。

## 完成判定

- 场景 0–6 全部符合预期，场景 7 至少验证「刷新失败」半支；
- `uv run python scripts/lint.py` 全绿；
- 全程任何终端输出中不出现凭据字段明文值。
