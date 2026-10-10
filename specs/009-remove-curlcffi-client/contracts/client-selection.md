# Phase 1 Contract: 客户端选择公共契约（移除后）

**Feature**: 009-remove-curlcffi-client | **Date**: 2026-10-11

本契约定义移除 CurlCFFI 内置适配后，库对下游暴露的客户端选择公共表面的可观察行为。它是 `tasks` 实现与 `quickstart` 验收的比对基准；实现不得偏离此处声明的行为（含错误消息文案）。

## 1. 内置客户端清单与优先级

| 客户端 | 注册名 | 声明设置项 | 优先级 |
|--------|--------|-----------|--------|
| `bilibili_api.clients.AioHTTPClient.AioHTTPClient` | `aiohttp` | `chunk_size` | 1（最高，默认） |
| `bilibili_api.clients.HTTPXClient.HTTPXClient` | `httpx` | `http2`, `chunk_size` | 2 |

- `curl_cffi` 不再出现在任何内置清单、注册结果或文档中（`impersonate` 设置面随之消亡；`http2` 由 httpx 保留）。
- 优先级语义：`ALL_PROVIDED_CLIENTS` 清单顺序即优先级序，注册时倒序遍历、最后注册者胜出为默认选中客户端。
- 默认选择结果：环境中 aiohttp 可导入 → `aiohttp`；仅 httpx 可导入 → `httpx`；两者皆无 → 无选中（见 §3 错误路径）。

## 2. 公开符号面变更（破坏性）

| 变更前 | 变更后 |
|--------|--------|
| `import bilibili_api.clients.CurlCFFIClient` | 抛 `ModuleNotFoundError`（标准语义，无兼容桩） |
| `from bilibili_api.clients import CurlCFFIClient` | 抛 `ImportError`（属性不存在，标准语义） |
| `select_client("curl_cffi")`（未注册自定义同名时） | 抛 `bilibili_api.exceptions.ArgsException`，消息见 §3 |
| `request_settings.set("impersonate", ...)` | 文档不再提供该入口；机制层不做名称校验，行为不承诺（勿用） |

## 3. 错误路径契约（消息文案为契约内容）

### 3.1 按名称选择未注册客户端 —— `select_client(name)`

```text
未注册过 {name}。当前已注册的客户端：{registered}（或通过 register_client() 注册自定义客户端）。
```

- `{registered}` 为当前已注册客户端名列表**按字典序排序（sorted）**后以 `", "` 连接（含用户自定义注册项；排序保证消息确定性，不依赖注册顺序）。
- 无任何已注册客户端时退化为既有"尚未安装"文本（§3.2）。
- 异常类型：`ArgsException`（不变）。

### 3.2 无可用内置客户端 —— `get_client()` / `get_selected_client()` / `get_available_settings()`

```text
尚未安装第三方请求库或未注册自定义第三方请求库。
$ pip3 install (aiohttp|httpx)
```

- 异常类型：`ArgsException`（不变）；三处文案一致。

## 4. 自定义客户端机制（不变契约）

- `register_client(name, cls, settings=None)`：注册任意名称的实现，**包括**注册名为 `curl_cffi` 的自定义实现——库不以"名称已废弃"为由拒绝；注册即选中该客户端（现行语义）。
- `select_client(name)` / `unregister_client(name)` / `get_registered_clients()` / `get_registered_available_settings()`：签名与语义均不变。
- 自定义客户端仍须实现 `BiliAPIClient` 抽象接口。

## 5. 迁移指引（承载于变更记录与文档，不承载于运行时报错桩）

| 原用法 | 迁移方式 |
|--------|----------|
| 未显式选择（曾默认 curl_cffi） | 无需改码；升级后自动改用 aiohttp |
| `select_client("curl_cffi")` | 改为 `"aiohttp"` / `"httpx"`，或经 `register_client()` 自行接入 curl_cffi |
| 直接导入 `CurlCFFIClient` 定制 | 改用 `AioHTTPClient` / `HTTPXClient`，或参照 `docs/request_client.md` 自定义客户端教程自行封装 |

## 6. 版本与告知义务

- 本次移除为破坏性变更：提交以 `refactor!:` + `BREAKING CHANGE` footer 标注；`CHANGELOGS/` 新版本节载明影响面与上表迁移指引。
- 剩余客户端（aiohttp / httpx）的全部既有行为（请求、超时归一化、WS 关闭清理、下载、会话池复用）保持不变，由既有离线用例继续锚定。
