# Research: 修复网页端二维码登录凭据获取失效

**Feature**: 002-qrcode-login-cookie-fix | **Date**: 2026-09-03

本文件记录 Phase 0 调研结论。全部结论基于本仓库源码核实与用户提供的真机抓包（2026-09-03 实测 poll 响应体与 Set-Cookie 行为）。

## 背景事实（已核实）

1. **缺陷现场**：`bilibili_api/login_v2.py:489-507`（`QrCodeLogin.check_state` WEB 分支）从 `events["url"]` 的查询串拆 `SESSDATA` / `bili_jct` / `DedeUserID`。服务端现状：登录成功时 `data.url` 是 `passport.biligame.com/.../crossDomain?...` 跳转链接，查询串不含任何 Cookie；真正的 5 个登录 Cookie 随响应标头 Set-Cookie 下发（用户实测）。旧逻辑拆出的三个变量全为空串，`Credential` 以空字段构造，`check_state` 仍返回 DONE——"假成功"。
2. **数据已在手边**：`BiliAPIResponse`（`bilibili_api/utils/_types.py:218`）自带 `cookies: dict` 字段，三种客户端均已把**本响应**的 Set-Cookie 解析进去：
   - `AioHTTPClient.py:253-255`：`resp.cookies`（SimpleCookie）→ `{name: value}`
   - `CurlCFFIClient.py:234-236`：`resp.cookies.jar` 遍历
   - `HTTPXClient.py:291-293`：`resp.cookies.jar` 遍历
   即 5 个 Cookie 会以原始大小写（`SESSDATA` / `bili_jct` / `DedeUserID` 等）完整出现在 `resp.cookies`。
3. **headers 通道不可用**：三个客户端把多值响应头折叠进普通 `dict`（`for key, item in resp.headers.items(): resp_headers[key] = item`），后值覆盖前值——`headers["set-cookie"]` 只剩 5 条中的最后一条。
4. **`Api` 链路丢弃响应对象**：`utils/_api.py` 的 `_request()` 内部持有 `BiliAPIResponse`，但 `request()` / `result` 只向上返回 `_process_response` 处理后的 JSON。
5. **库内既有惯用法**：`login_v2.py` 已有 4 处直连 `client.request(...)` 后读 `resp.cookies` 的先例（74-90 行 SMS token 交换、279 / 320 行旧流程、617-624 行 safecenter 换 Cookie）——均因 `Api` 拿不回 Cookie 而绕开统一链路。
6. **异常体系**：`ArgsException(msg)` 存在于 `bilibili_api/exceptions/_simple.py:92` 并从包根导出，语义即"调用参数错误"（此处指服务端响应缺少构造凭据所必需的数据）。
7. **离线测试基建**：`tests/test_offline_api_core.py` 已有 `_make_resp(raw, headers, code)` 构造 `BiliAPIResponse` + `monkeypatch.setattr(api_mod, "get_client", ...)` 的 fake client 手法，可直接扩展驱动新方法的离线用例；`tests/test_offline_login_v2.py` 已覆盖 `QrCodeLogin` 初始状态与枚举。

## 决策

### D1: Cookie 数据来源 = poll 响应自身的 `BiliAPIResponse.cookies`

**Decision**: 登录凭据从**同一次** poll 请求的响应 Cookie（Set-Cookie 解析结果）取得。

**Rationale**: 用户实测 poll 响应本身即下发全部 5 个登录 Cookie，数据现成、无额外请求；`BiliAPIResponse.cookies` 由三客户端一致填充，是唯一不经改动即可拿到完整 Cookie 集合的通道。

**Alternatives considered**:

- *请求 `data.url` 的 crossDomain 链接再收获 Cookie*：多一跳网络往返，且域名在 `passport.biligame.com`（游戏通行证域），行为不受控；仅当 B 站未来又改为"crossDomain 响应才下发 Cookie"时作为回退手段记录，本期不采用。
- *解析 `resp.headers["set-cookie"]`*：不可行——客户端把多值头折叠成普通 dict，5 个 Cookie 会丢 4 个（见背景事实 3）；若走此路需同时改三个客户端的头采集结构，波及面远大于收益。

### D2: 暴露方式 = `Api` 新增"处理结果 + 响应 Cookie"请求方法

**Decision**: 在 `Api` 上新增公共异步方法（工作名 `request_with_cookies(raw: bool = False)`，返回 `(处理后的响应数据, 本响应下发的 Cookie: dict)`；最终命名与签名在 tasks/实现时定稿），内部复用 `_request` / 重试链路；`login_v2.py` WEB 分支改用它。

**Rationale**: 保持宪法 II 的统一链路（日志事件、代理传递、客户端选择、-403 重试语义全部继承）；一处扩展解决一类问题；`check_state` 现有调用本就走 `Api`（480 行），改动是对称替换。`raw` 语义与 `request()` 对齐（poll 响应外层 code 恒为 0、内层 `data.code` 承载状态，用默认 `raw=False` 取 `data` 字段即可，与现状一致）。

**Alternatives considered**:

- *直连 `get_client().request(...)`*（仿 617-624 行 SMS 惯用法）：改动最小、有同文件先例，但绕开统一链路（宪法 II 字面冲突，且丢失请求日志 / 代理 plumbed 行为），并使"绕过 Api 取 Cookie"的第 5 处复制粘贴继续增殖。现有 4 处属历史存量，本期不扩边重构（记为后续机会）。
- *`Api.request()` 加 `full_response=True` 参数返回 `BiliAPIResponse`*：调用方需自行解析 JSON 与错误码检查，绕过 `_process_response` 的 `ResponseCodeException` / 状态码校验，语义割裂。
- *可变出参 / `Api` 实例属性回填*：与 wbi 重试循环组合时易错（中间尝试会覆盖），显式返回值最稳。

### D3: 字段映射 = Cookie 名大小写不敏感 → Credential 字段

**Decision**: 将响应 Cookie 名统一小写后映射：`sessdata` / `bili_jct` / `dedeuserid` 为必需（对应服务端 `SESSDATA` / `bili_jct` / `DedeUserID`），`buvid3` / `buvid4` 出现则顺手填充（缺省由反爬自动生成兜底，不强制）；`ac_time_value` 仍取响应体 `data.refresh_token`。

**Rationale**: 规格 FR-001 / FR-005；`Credential.__init__` 字段名恰好与 Cookie 小写名一致（`utils/_credential.py:46`）；buvid 与"库内自动生成"假设一致（spec Assumptions）。

### D4: 缺字段行为 = 抛 `ArgsException`，消息只含字段名

**Decision**: 任一必需字段（sessdata / bili_jct / dedeuserid / ac_time_value）为空或缺失时，构造 `Credential` 前抛 `ArgsException`，消息形如"二维码登录响应缺少必要字段: …"（仅字段名）；`self.__credential` 不被赋值，`has_done()` 保持 False。

**Rationale**: 规格 FR-004 / FR-008；`has_done()` 基于 `bool(self.__credential)`，先校验后赋值即天然满足"不出现 DONE 但凭据为空"（User Story 2 场景 3）。

### D5: 修改边界 = WEB 分支最小重写，TV 分支与状态判定不动

**Decision**: 仅重写 WEB 分支 `else:` 内的凭据构造；86101 / 86090 / 86038 三个状态分支与 TV 通道（`raw=True` + 结构化 `cookie_info`）保持原样。

**Rationale**: 规格 FR-006 / FR-007；TV 通道工作正常（其响应的 Cookie 在响应体内，不受本次服务端变更影响）。

## 风险与开放点（移交 tasks/实现）

- **B 站接口再变**：poll 响应形态是外部依赖，测试须以契约形式钉住（离线 fake 响应），真机验收（quickstart.md）作为最终判据。
- **客户端 Cookie 解析差异**：三客户端 jar 实现不同（aiohttp SimpleCookie vs httpx/curl_cffi cookiejar），离线用例覆盖库内新方法的映射逻辑即可；真机验收在默认客户端（curl_cffi 优先）下进行。
- **`scripts/qrcode_login.py`**：现为未提交的最小骨架（仅 generate），验收前需补轮询循环与凭据校验输出，属实现任务而非本计划约束。
