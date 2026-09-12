# API Contract: 修复网页端二维码登录凭据获取失效

**Feature**: 002-qrcode-login-cookie-fix | **Date**: 2026-09-03

本项目为 Python 库，对外契约即公共 API 行为。本特性**不引入任何破坏性变更**：所有既有签名、返回类型、事件枚举值不变；新增一个 `Api` 公共方法，并收紧一个既有方法的行为不变式。

## 1. `Api` 新增方法：`request_with_cookies`（工作名，实现时可定稿命名）

```python
async def request_with_cookies(self, raw: bool = False) -> tuple[int | str | dict | bytes | None, dict]:
```

| 契约项 | 约定 |
|--------|------|
| 语义 | 与 `Api.request(raw=...)` 完全一致地发起请求并处理响应（状态码校验、code 校验、data/result 提取、-403 wbi 重试），区别仅在返回值额外携带**本次最终响应**由服务端下发的 Cookie |
| 返回 | 二元组 `(处理后的响应数据, cookies)`；`cookies` 为 `{cookie 名: 值}`，名字保持服务端原始大小写 |
| 重试 | 重试期间每次尝试若抛 `ResponseCodeException` 按既有规则处理；返回的 cookies 恒为**最终成功那次**响应的 |
| raw 语义 | 与 `request()` 对齐：`False` 提取 `data`/`result` 字段，`True` 返回完整解析后的 JSON 体 |
| 文档 | 完整中文 docstring（Args / Returns / Raises），进入 doc_gen 生成范围 |

**兼容性声明**：`request()` / `result` 签名与返回不变；新方法纯增量。

## 2. `QrCodeLogin.check_state`（WEB 通道行为契约，签名不变）

| 输入（poll 响应 `data.code`） | 返回 | 副作用 |
|------------------------------|------|--------|
| `86101` | `QrCodeLoginEvents.SCAN` | 无（不变） |
| `86090` | `QrCodeLoginEvents.CONF` | 无（不变） |
| `86038` | `QrCodeLoginEvents.TIMEOUT` | 无（不变） |
| `0` 且响应 Cookie 含全部必需字段 | `QrCodeLoginEvents.DONE` | 以响应 Cookie（大小写不敏感映射）+ `data.refresh_token` 构造并保存凭据 |
| `0` 但任一必需字段缺失/为空 | **Raises `ArgsException`** | 凭据不赋值，`has_done()` 保持 `False` |

**行为不变式（本特性核心）**：`check_state` 返回 `DONE` ⟹ `get_credential()` 可得 sessdata / bili_jct / dedeuserid / ac_time_value 全部非空的凭据。旧"url 查询串解析 Cookie"路径移除，不得残留为可达代码。

**TV 通道**：行为与现状完全一致（`raw=True` + `cookie_info` 结构化 Cookie），不在本契约变更范围。

## 3. 错误契约

| 场景 | 异常 | 消息约束 |
|------|------|----------|
| 登录成功响应缺少必需 Cookie 字段 | `ArgsException` | 仅含缺失**字段名**（如"二维码登录响应缺少必要字段: bili_jct, dedeuserid"），严禁出现任何 Cookie 字段**值** |

其余异常（网络、响应码等）沿用 `Api` 既有契约，不变。
