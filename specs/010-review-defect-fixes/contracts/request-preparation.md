# Contract: 请求准备行为（Api params / data / headers）

**Feature**: 010-review-defect-fixes | **契约对象**：`bilibili_api.utils._api.Api` 的公开构造与请求准备行为（下游调用方视角）

本契约固化修复 1（FR-001 / FR-002）、修复 2（FR-003）、修复 3（FR-004）后的公开行为。规则表与状态转移的权威定义见 [data-model.md](../data-model.md) 实体 1。

## 构造与更新

```python
Api(url=..., method=..., headers={...}, data={...}, params={...}, ...)
    .update_params(**kwargs)   # 整体替换 params
    .update_data(**kwargs)     # 整体替换 data
    .update_headers(**kwargs)  # 整体替换 headers
```

- **headers（修复后契约）**：构造参数显式传入的请求头，名称与值原样送达服务端；值仅在调用方本人传空串时为空串。不要求调用方随后调用 `update_headers` 恢复。
- `update_*` 系列语义不变：整体替换，非合并。

## 查询参数（params）编码契约

- 值为 `bool`：编码为 `0` / `1`。
- **值为 `dict`（修复后契约）**：自动序列化为紧凑 JSON 字符串（`separators=(",", ":")`，非 ASCII 内容以 UTF-8 原文保留），以单一查询参数键值发送；不出现 Python dict repr 形态（单引号、逗号空格）。
- 值为 `None`：该键剔除。
- 其余标量（str / int / float）：原样编码。
- 序列化失败（dict 内含不可 JSON 序列化对象）：异常向调用方传播，按普通参数错误处理，不静默吞掉、不静默丢弃该键。

已知受益调用点：网页扫码登录轮询的 `x-bili-locale-json` / `x-bili-device-req-json`（`login_v2.QrCodeLogin.check_state`，调用点保持 dict 字面量传入）；已手工序列化为字符串的调用点（如 `user.py` / `dynamic.py` 的 `x-bili-device-req-json`）行为不变。

## 请求体（data）编码契约

- **值为 `bool`（修复后契约）**：转为 `0` / `1` 后保留在请求体；查询参数中不出现该键。
- 值为 `None`：该键剔除。
- 其余值：原样保留在请求体。
- `json_body=True`：归一化后的请求体整体 JSON 序列化，行为不变。

## 不变量（本特性不改变）

- 轮询状态映射（86101 待扫码 / 86090 已扫码待确认 / 86038 过期 / 其余按成功处理）、Set-Cookie 采集与凭据构造契约（特性 002 / 006：SESSDATA / bili_jct / DedeUserID 必需，`ac_time_value` 可选）。
- 全局 `HEADERS` 回落（未传自定义 headers 时）、Wbi / buvid / bili_ticket 反爬注入、csrf 自动追加、`-403` wbi 重试。
- 请求经统一链路 `Api(**api).update_params(**params).result`，客户端按 `aiohttp > httpx` 自动选择；dict 序列化发生在客户端编码之前，对全部内置与注册客户端一致生效。

## 验证锚点

- 离线：`tests/test_offline_api_core.py`（`_prepare_request` 输出断言）+ `tests/test_offline_login_v2.py`（本地回环客户端编码边界断言，见 [quickstart.md](../quickstart.md)）。
- 真机：`uv run python scripts/login_and_cache.py qrcode` 全流程（SC-001）。
