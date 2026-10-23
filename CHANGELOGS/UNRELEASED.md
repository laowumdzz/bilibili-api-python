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

## Fixed

### fix(exceptions): 恢复 17 个按类异常子模块导入路径兼容层

此前的异常重构将 17 个按类拆分的异常模块并入 `exceptions/_simple.py`，包级导出（`from bilibili_api.exceptions import ...`）与 `__all__` 保持不变，但按类子模块导入路径以 `ModuleNotFoundError` 失败，且该兼容性破坏未在变更记录中告知。本次恢复全部 17 条历史导入路径（与首次提交 `99648df` 一致）：

| 恢复的导入路径（`bilibili_api.exceptions.` 前缀） |
|---------------------------------------------------|
| `ArgsException`、`CredentialNoAcTimeValueException`、`CredentialNoBiliJctException`、`CredentialNoBuvid3Exception`、`CredentialNoBuvid4Exception`、`CredentialNoDedeUserIDException`、`CredentialNoSessdataException`、`DanmakuClosedException`、`DynamicExceedImagesException`、`GeetestException`、`InitialStateException`、`LiveException`、`LoginError`、`ResponseException`、`StatementException`、`VideoUploadException`、`WbiRetryTimesExceedException` |

**兼容层语义：**

- 17 个薄兼容模块仅 re-export `_simple.py` 中的同一类对象（`from ._simple import X as X`），不含任何类定义；异常类的定义、继承关系与构造签名零改动，子模块路径与包级导入得到的类对象严格同一（`is` 判定为真），`except` 精确捕获在两种导入写法下行为一致。
- 包级导入面与 `__all__`（22 项）保持不变；`__init__.py` 中 17 个类改为经各自薄子模块导入（与首次提交的导入结构一致），以在包初始化时缓存子模块，避免 Python 导入机制的子模块属性重绑定影响包级导出。
- 未来如需废弃这些兼容路径，须另行裁决并在变更记录中告知。
