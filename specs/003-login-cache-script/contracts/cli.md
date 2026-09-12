# Contract: scripts/login_and_cache.py CLI

**Date**: 2026-09-03 | **Status**: 已批准（含 spec 澄清 Q1/Q2 裁定）

独立登录脚本的命令行契约。本脚本为开发者本机交互工具，不属于库公开 API。

## 用法

```bash
uv run python scripts/login_and_cache.py <qrcode|phone>
```

| 参数 | 必填 | 说明 |
|------|------|------|
| `TYPE`（位置参数） | 是 | 登录方式：`qrcode` 终端扫码 / `phone` 短信验证码；取值集合与 pytest `--login` 一致 |

## 行为契约

| 场景 | 行为 | 退出码 |
|------|------|--------|
| 无参 / 非法参数 | 输出用法提示，不进入任何交互 | 2 |
| 登录成功 | **立即**将凭据写入 TEMP 缓存文件（写入前不做联网校验，spec 澄清 Q2），输出成功提示（含缓存文件路径） | 0 |
| 登录中止（用户中断 / 二维码连续 3 次超时 / 流程失败 / 非交互终端 EOF） | 输出中止原因，**不写入、不破坏**既有缓存文件 | 1 |

## 交互流程

- **qrcode**: 终端渲染 ASCII 二维码 → 提示扫码 → 轮询至完成；二维码过期自动重生成（连续 3 次超时中止）；终端无法渲染时回退提示 TEMP 下二维码图片路径。
- **phone**: 地区码（回车默认 +86）→ 手机号 → 浏览器完成极验滑块 → 发送短信 → 输入验证码 → 登录；触发风控二次验证（`LoginCheck`）时再完成一次滑块 + 二次短信验证码。

## 输出约束

- 所有输出（stdout/stderr）MUST NOT 包含任何凭据字段值，只允许字段名与状态描述。
- 需要用户输入的提示写入 stdout 且立即刷新；错误 / 中止消息写入 stderr。

## 与缓存文件的关系

- 写入目标与格式契约与 pytest `--login` 完全一致（[specs/001-pytest-temp-login/contracts/cache-file-format.md](../../001-pytest-temp-login/contracts/cache-file-format.md)，不变更）。
- 写入即覆盖（同机后一次登录覆盖前一次）。
- 脚本成功写入后，后续 `uv run pytest`（不带 `--login`）零交互复用该缓存（有效性校验在测试运行时按需进行）。
