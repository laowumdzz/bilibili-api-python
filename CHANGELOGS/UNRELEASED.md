# 未发布（Unreleased）

> 本节记录已入库但尚未发布版本的变更；发布时再定版本号，并将本节内容并入对应版本的 CHANGELOGS 文件。

## ⚠️ BREAKING CHANGE

### refactor!: 移除 CurlCFFI 客户端适配

内置不再携带 CurlCFFI 客户端适配实现，自动选择链回落为 `aiohttp` > `httpx`（`aiohttp` 为运行时硬依赖，正常安装路径下恒有可用内置客户端）。移除的是内置适配，自定义客户端注册机制（含注册与已移除客户端同名的实现）保持不变。

**影响面与迁移方式：**

| 原用法 | 迁移方式 |
|--------|----------|
| 未显式选择（曾默认 curl_cffi） | 无需改码；升级后自动改用 aiohttp |
| `select_client("curl_cffi")` | 改为 `"aiohttp"` / `"httpx"`，或经 `register_client()` 自行接入 curl_cffi |
| 直接导入 `CurlCFFIClient` 定制 | 改用 `AioHTTPClient` / `HTTPXClient`，或参照 `docs/request_client.md` 自定义客户端教程自行封装 |

**行为细节：**

- `import bilibili_api.clients.CurlCFFIClient` 现以标准 `ModuleNotFoundError` 失败（干净移除，无报错桩）。
- `select_client()` 选择未注册的客户端名时，异常信息会列出当前已注册的客户端清单（字典序）并给出 `register_client()` 自定义注册提示。
- `impersonate` 设置随 curl_cffi 适配一并消亡；`http2` 设置由 httpx 客户端保留。
- 开发依赖（dev 组）不再包含 `curl-cffi`；运行时依赖从未包含它。
