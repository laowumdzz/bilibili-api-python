# Data Model: 修复网页端二维码登录凭据获取失效

**Feature**: 002-qrcode-login-cookie-fix | **Date**: 2026-09-03

本特性不引入持久化存储；数据模型描述**一次成功轮询内的数据流转**：服务端下发的登录 Cookie 集 → 凭据字段映射 → 登录会话状态。

## 实体

### 1. 登录 Cookie 集（LoginCookieSet）

服务端在 poll 响应 Set-Cookie 标头下发的 Cookie 集合，经客户端解析后形态为 `{cookie 名: 值}`（原名大小写）。

| Cookie 名（服务端形态） | 映射目标（Credential 字段） | 必需性 |
|-------------------------|----------------------------|--------|
| `SESSDATA` | `sessdata` | 必需 |
| `bili_jct` | `bili_jct` | 必需 |
| `DedeUserID` | `dedeuserid` | 必需 |
| `buvid3` | `buvid3` | 可选（缺省由反爬自动生成兜底） |
| `buvid4` | `buvid4` | 可选（同上） |
| 其他（第 5 项及未来新增） | 忽略 | — |

**校验规则**（源自 FR-001 / FR-004 / FR-005）：

- 名字匹配大小写不敏感（统一小写后比对）。
- 必需字段缺失或值为空串 → 抛 `ArgsException`，消息仅含缺失字段名列表。
- Cookie 值原样保留，不做二次 URL 解码。

### 2. 轮询响应体（PollEvents，既有结构，仅作来源说明）

外层恒为 `{code: 0, message, ttl, data}`；登录状态在 `data.code`：`86101` 未扫码、`86090` 已扫码未确认、`86038` 过期、`0` 成功。成功时 `data.refresh_token` → 凭据 `ac_time_value`；`data.url` 为 crossDomain 跳转链接，**不再作为 Cookie 来源**（FR-002）。

### 3. 登录凭据（Credential，既有实体）

构造输入：sessdata / bili_jct / dedeuserid / ac_time_value 四项全部必需非空；buvid3 / buvid4 机会性填充。构造成功即视为登录完成。

### 4. 二维码登录会话状态机（QrCodeLogin，既有实体）

```text
[初始] --generate_qrcode--> [待扫码]
[待扫码] --check_state(data.code=86101)--> SCAN（不变）
[待扫码] --check_state(data.code=86090)--> CONF（不变）
[待扫码] --check_state(data.code=86038)--> TIMEOUT（不变）
[CONF]   --check_state(data.code=0)--> 校验 Cookie 集
    ├─ 必需字段齐全 → 赋值凭据 → DONE（不变式：返回 DONE 时凭据必已构造成功）
    └─ 任一必需字段缺失/为空 → ArgsException（凭据不赋值，会话停留原状态，has_done()=False）
[TV 通道] 独立路径：raw 响应 + data.cookie_info.cookies 结构化列表（不变）
```

**不变式**：

- `has_done() == True` ⟹ `get_credential()` 返回四项必需字段非空的凭据（消解"假成功"）。
- DONE / 异常之外的事件不读取、不写入凭据。
- 重复轮询成功态：幂等——每次以当次响应重新构造，凭据内容一致。
