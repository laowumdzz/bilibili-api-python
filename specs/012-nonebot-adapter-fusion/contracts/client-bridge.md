# Contract: NoneBot 驱动 ↔ `BiliAPIClient` 桥接

**Feature**: `012-nonebot-adapter-fusion` | **实现**: `bilibili_api/clients/NoneBotClient.py`

本契约定义「由 NoneBot 驱动承载的客户端」必须满足的语义，是宪章 I（HTTP 必须经抽象层）与澄清 Q1（`DRIVER` 继续生效）的落地点。所有结论均已在 nonebot2 2.5.0 + aiohttp 3.14.3 / httpx 0.28.1 环境中核对过源码。

## 0. 前置事实（决定了下面所有写法）

| 事实 | 影响 |
|---|---|
| 驱动的 `Response` **没有** `cookies`、没有最终 `url`、没有 `history` | cookies 必须自己从 `Set-Cookie` 头解析；`url` 只能用请求 URL |
| 两个驱动都**始终跟随重定向**，`Request` 无 `allow_redirects` 字段 | 无法关闭重定向；重定向中途设置的 cookie 拿不到 |
| `verify_ssl` / `trust_env` 在驱动层**无对应能力** | 只能保存并告警，不能假装支持 |
| `httpx` 驱动只实现 `HTTPClientMixin`，没有 `websocket` 属性 | **纯 httpx 驱动无法跑弹幕连接**，必须启动期报错 |
| `WebSocket.receive()` 从不返回关闭帧，而是抛 `WebSocketClosed(code, reason)` | 关闭映射必须基于异常码，不能用返回值 |
| `receive_bytes()` 对文本帧抛 `TypeError`；`receive()` 对 PING/PONG 抛 `TypeError` | 只能用 `receive()`，且控制帧不可见 |
| `HTTPClientMixin.stream_request()` 两个驱动都有 | `download_*` 可以真流式，无需整包缓冲 |
| 每次 `driver.request()` 都会新建并关闭会话 | 无连接池；50 房间轮询会有 FD 抖动，但不影响正确性 |

## 1. 安装与选中

- 适配器在 `startup` 阶段（必须在事件循环内、`nonebot.init` 之后）构造并注册。
- `register_client(name, cls, settings)` 会**立即选中**且要求 `settings` 的每个键都是构造参数名；因此：
  - 驱动对象**不得**经 `settings` 传入（会被写进全局 `request_settings` 并回放给其它客户端），只能经 `session=driver` 或类属性注入。
  - 适配器默认接管选择（spec Assumptions）；接管时 `INFO` 记录一条不含凭据的日志。
- 本模块 MUST NOT 被 `clients/__init__.py` 或包根 eager import（FR-002）。
- 依赖下限 `nonebot2>=2.5.0`：2.4.3 及更早的 aiohttp 驱动在收到 `WSMsgType.CLOSED` 时会漏出 `TypeError`，导致弹幕读循环异常而非正常关闭；2.5.0 才修正（详见 §6）。

## 2. 构造参数映射

| ABC 参数 | 处理 |
|---|---|
| `proxy` | 空串归一为 `None`（httpx 对 `proxy=""` 直接 `ValueError`）；`None` 表示不覆盖驱动默认 |
| `timeout` | `<= 0` 视为不限时；转成 `Timeout(total=t, connect=t, read=t, close=t)`，**不得**把 `0.0` 直接透传（aiohttp 视为立即超时） |
| `verify_ssl` | 仅保存；驱动不支持，首次 `False` 时告警一次 |
| `trust_env` | 仅保存；aiohttp 驱动硬编码 `True` |
| `session` | 只接受 `nonebot.drivers.Driver` 实例（库的 `set_session` 通道）；其它对象立即 `TypeError` |
| `get_wrapped_session()` | 返回驱动对象（或驱动未解析时的 `None`）；语义与内置客户端不同，需在文档注明 |

驱动解析：`nonebot.get_driver()` 取全局驱动；缺 `HTTPClientMixin` → `ArgsException`；需要 WS 时缺 `WebSocketClientMixin` → `ArgsException`（含当前驱动名）。**不要**解析 `driver.type` 字符串做能力判断。

## 3. `request()` 映射

| 库参数 | 到 `Request` |
|---|---|
| `method` | 空串归一为 `"GET"` |
| `url` + `params` | `Request` 构造时会把 `params` 合进 URL，**不要**再手动拼一次 |
| `headers` | 透传 |
| `cookies` | 转 `dict[str, str]`；值为 `None` 的键剔除 |
| `data` 为 `str` / `bytes` | 走 `content`（库把 JSON 序列化成 str 后就放在这里） |
| `data` 为 `dict` | 走 `data`（表单） |
| `files` | 手工打开文件、`filename=basename(path)`，并在 `finally` 关闭句柄（驱动不关）；`data` 为 `str` 且 `files` 非空 → `NotImplementedError`（ABC 明确不要求） |
| `allow_redirects` | 无对应字段，忽略（驱动始终跟随） |
| `proxy` | 归一空串后透传 |

**响应映射**

| `BiliAPIResponse` | 来源 |
|---|---|
| `code` | `Response.status_code`（非 2xx 不抛异常） |
| `headers` | 转普通 dict 并**统一小写键**（`_api.py` 按 `"content-length"` 大小写敏感查表） |
| `cookies` | 逐条解析 `headers` 中的 `Set-Cookie`（用 `http.cookies.SimpleCookie`，能正确处理 `Expires` 里的逗号）；多个同名头都要读到 |
| `raw` | `Response.content`；若驱动给 `str` 则 UTF-8 编码 |
| `url` | 请求 URL（最终 URL 不可得，见 §7） |

传输层异常（`aiohttp.ClientError`、`httpx` 异常、`asyncio.TimeoutError`）MUST 归一为库的 `NetworkException`，不得把第三方异常类型泄漏给上层。

## 4. `download_*` 映射（流式）

| 方法 | 实现 |
|---|---|
| `download_create(url, headers)` | 取 `driver.stream_request(Request(...), chunk_size=self._chunk_size)`；`await anext(gen)` 拿到首块与响应头，记录 `content-length`，返回句柄 |
| `download_chunk(cnt)` | 先返回首块，其后每次 `await anext(gen)`；`StopAsyncIteration` 时返回 `b""` |
| `download_content_length(cnt)` | 创建时记录的 `content-length`（缺省 0） |
| `download_close(cnt)` | `await gen.aclose()` 并移除句柄；重复调用无副作用 |

**说明**：这是真流式，内存占用与文件大小无关（`stream_request` 按 `chunk_size` 重新切块）。若某驱动缺 `stream_request`（不在当前两个驱动之列），退化为 `request()` 后切片，并在文档标注内存代价。

## 5. `ws_*` 映射

| 方法 | 实现 |
|---|---|
| `ws_create(url, params, headers)` | 句柄自增；`stack = AsyncExitStack()`；`ws = await stack.enter_async_context(driver.websocket(Request("GET", URL(url), params=..., headers=..., timeout=<WS 专用>, proxy=...)))`；`__aenter__` 失败时 `await stack.aclose()` 后原样抛出 |
| `ws_send(cnt, data)` | 句柄不存在或已关闭 → 静默返回；否则 `await ws.send_bytes(data)` |
| `ws_recv(cnt)` | 见 §6；同一句柄的调用用 `asyncio.Lock` 串行化（aiohttp 对并发 `receive()` 直接 `RuntimeError`） |
| `ws_close(cnt)` | 先 `pop` 出句柄（序列化关闭、天然幂等）→ `await ws.close(1000, "")` → 等待读锁释放（最多 5 秒，超时则继续）→ `await stack.aclose()` |

**WS 超时**：`read` MUST 为 `None`。库默认 `timeout=30.0`；若透传成 `read`，aiohttp 会得到 `ws_receive=30`，空闲 30 秒就会抛超时——弹幕连接的存活由库自己的心跳超时判据负责。

**关闭与取消安全**：`ws_close` 会被心跳任务或 `disconnect()` 在另一个任务里调用，而 `ws_recv` 可能正挂在 `receive()` 上。因此关闭顺序固定为「close → 等读锁 → aclose 上下文」，保证不会在接收方未退出时销毁底层会话（否则会被上层判为传输错误并触发多余重连）。

**备选方案（仅在实测 AsyncExitStack 出现驱动兼容问题时启用）**：每个连接起一个 owner task 持有 `async with driver.websocket(...)`，帧经 `asyncio.Queue` 交给 `ws_recv`。它保证进入/退出在同一任务，跨任何驱动都最稳；代价是每连接一个任务与一个有界队列。契约为「优先 A（ExitStack），A 出问题改 C」，不得使用手工 `__aenter__/__aexit__`（异常路径容易少退出一次）。

## 6. `ws_recv` 语义与消息映射

```
msg = await ws.receive()
```

| 驱动结果 | 返回 |
|---|---|
| `str` | `(msg.encode("utf-8"), TEXT)` |
| `bytes` | `(msg, BINARY)` —— 弹幕主路径 |
| `WebSocketClosed` 且 `code in (1000, 1001)` | `(b"", CLOSED)`（正常关闭/服务端离开） |
| `WebSocketClosed` 其它码（含 `1006`） | **原样抛出**，交给上层重连逻辑 |
| 句柄不存在或已关闭 | `(b"", CLOSED)` |
| `PING` / `PONG` / 关闭帧 / 续帧 | 不可见（驱动自动应答或已转成异常） |

**为什么异常码 1000/1001 要映射成 CLOSED 而不是抛出**：上层 `disconnect()` 会先置状态再关闭连接；若所有关闭都抛异常，正常断开会被误判为错误状态并触发重连。

**2.4.x 兼容**：`nonebot2<2.5.0` 的 aiohttp 驱动在收到 `WSMsgType.CLOSED` 时可能让 `receive()` 抛 `TypeError`。本特性直接把下限提到 `>=2.5.0`，不做兜底捕获（避免把真正的编程错误吞掉）。

## 7. 驱动强加的限制（必须在文档中写明）

| 限制 | 后果 | 缓解 |
|---|---|---|
| 最终 URL 不可得 | `utils/short.get_real_url()` 这类依赖重定向结果的工具会退化 | 文档标注；需要时用户自行注册原生客户端 |
| 重定向中途设置的 cookie 丢失 | 依赖重定向写 cookie 的流程不可用（当前登录/刷新链路都是直连 POST，不受影响） | 同上 |
| `verify_ssl` / `trust_env` 不可配 | 自签证书场景不可用 | 保存参数并告警，不静默假装生效 |
| 无连接池 | 高频轮询有 FD/延迟开销 | 轮询按 ≥2 秒节流；不为此提前做池化 |
| 控制帧不可见 | 无法透传 PING/PONG | 弹幕协议的心跳是业务层二进制帧，不受影响 |

## 8. 验收要点

| 编号 | 场景 | 期望 |
|---|---|---|
| C-01 | 假驱动调用 `request` | `params`/`cookies`/`content`/`data` 落到正确字段，文件句柄被关闭 |
| C-02 | 假驱动返回 302 后 200 | `code` 为 200；`url` 为原始 URL（限制已记录） |
| C-03 | 响应含两条 `Set-Cookie` 与一条带 `Expires` 的 cookie | 全部解析出来，`Expires` 的逗号不破坏解析 |
| C-04 | 假驱动返回非 2xx | 不抛异常，`code` 为状态码，`headers` 键统一小写 |
| C-05 | 假驱动 WS 发文本帧 / 二进制帧 | 分别得到 `TEXT` / `BINARY` 与原始字节 |
| C-06 | 假驱动 WS 抛 `WebSocketClosed(1000)` / `(1006)` | 前者 `CLOSED`，后者原样抛出 |
| C-07 | 同一句柄并发 `ws_recv` | 串行化，不触发驱动级 `RuntimeError` |
| C-08 | 读取中取消任务后 `ws_close` | 连接释放且可重复调用 |
| C-09 | 驱动缺 `WebSocketClientMixin`（如纯 httpx） | 启动期 `ArgsException`，文本含驱动名 |
| C-10 | `stream_request` 下载 | 分块返回，`content_length` 与实际一致，关闭幂等 |
| C-11 | 未安装 nonebot2 | `import bilibili_api` 成功，仅导入适配器时报缺依赖 |
