# bilibili-api-python 重构规格文件

> 版本: 1.1  
> 日期: 2026-08-04  
> 项目: bilibili-api-python v17.4.2  
> 基线 commit: `16373f3` (chore: 替换 pylint/mypy 为 ruff + pyrefly)  
> 修正记录: v1.1 修正了 Phase 1 异常分类、Phase 2 行号/HEADERS归属/遗漏函数/ABC冗余docstring、Phase 3 签名变更评估、Phase 5 可变默认参数计数

---

## 总览

本项目总计 **35,031 行** Python 源码（`bilibili_api/` + `tools/`），`network.py`（2422 行）和 `video.py`（2672 行）两个文件占总量 14.5%。以下按 **依赖拓扑顺序** 排列 8 个阶段，每个阶段独立可交付、可测试。前序阶段完成后才启动后续。

### 阶段依赖图

```
Phase 1 (exceptions) ──────────────────────────────────────────────┐
Phase 2 (network.py 拆分) ← 依赖 Phase 1 的异常类位置变更 ──────┤
Phase 3 (全局状态封装) ← 依赖 Phase 2 的新模块边界 ─────────────┤
Phase 4 (type hints 现代化) ← 全局文本替换，无功能依赖 ─────────┤
Phase 5 (可变默认参数修复) ← 可与 Phase 4 并行 ──────────────────┤
Phase 6 (eval 替换 + 安全修复) ← 单点修改 ──────────────────────┤
Phase 7 (裸异常捕获收紧) ← 可与 Phase 4-6 并行 ─────────────────┤
Phase 8 (video.py 拆分) ← 依赖 Phase 2/3 完成后网络层稳定 ───────┘
```

---

## Phase 1: 异常类合并 [P0]

### 目标

将 `exceptions/` 目录下 22 个独立文件合并为 3 个文件，减少文件数和 import 膨胀。

### 现状

```
bilibili_api/exceptions/
├── __init__.py              # 22 个 from .XXX import *
├── ApiException.py           # 基类，8 行
├── ArgsException.py          # 10 行
├── CookiesRefreshException.py
├── CredentialNoAcTimeValueException.py
├── CredentialNoBiliJctException.py
├── CredentialNoBuvid3Exception.py
├── CredentialNoBuvid4Exception.py
├── CredentialNoDedeUserIDException.py
├── CredentialNoSessdataException.py
├── DanmakuClosedException.py
├── DynamicExceedImagesException.py
├── ExClimbWuzhiException.py
├── GeetestException.py
├── InitialStateException.py
├── LiveException.py
├── LoginError.py
├── NetworkException.py        # 有自定义 __init__(status, msg)
├── ResponseCodeException.py  # 有自定义 __init__(code, msg, raw)
├── ResponseException.py
├── StatementException.py
├── VideoUploadException.py
└── WbiRetryTimesExceedException.py
```

### 源码审计结论

全部 22 个异常类都重写了 `__init__`，但签名和行为差异显著。分为三类：

| 类别 | 数量 | 特征 |
|------|------|------|
| **模式 A — 无参构造** | 9 | `def __init__(self): self.msg = "xxx"; super().__init__()` |
| **模式 B — 有参构造** | 7 | `def __init__(self, msg="xxx"): super().__init__(msg)` |
| **模式 C — 有参但忽略参数** | 1 | `def __init__(self, msg: str = ""): self.msg = "验证码处理错误"; super().__init__()` |
| **特殊签名** | 5 | 详见下方 |

**5 个保留独立文件的异常（特殊签名或自定义 `__str__`）：**

| 异常 | `__init__` 签名 | 特殊之处 |
|------|----------------|---------|
| `ApiException` | `(self, msg: str = "异常")` | 基类 |
| `NetworkException` | `(self, status: int, msg: str)` | 双参数 |
| `ResponseCodeException` | `(self, code: int, msg: str, raw: dict = None)` | 三参数 + raw |
| `ExClimbWuzhiException` | `(self, code: int, msg: str)` | 双参数（v1.0 遗漏） |
| `CookiesRefreshException` | `(self, msg: str = "Cookies 刷新错误。")` | 自定义 `__str__`（v1.0 遗漏） |

### 改动方案

#### 1.1 创建 `exceptions/_simple.py`

将 17 个异常合并到这一个文件（模式 A × 9 + 模式 B × 7 + 模式 C × 1）：

```python
"""bilibili_api.exceptions._simple — 简单异常集合"""
from . import ApiException


# ── 模式 A: 无参构造，硬编码 msg (9 个) ──────────────────────

class CredentialNoAcTimeValueException(ApiException):
    def __init__(self):
        self.msg = "未传入有效的 ac_time_value"
        super().__init__()

class CredentialNoBiliJctException(ApiException):
    def __init__(self):
        self.msg = "未传入有效的 bili_jct"
        super().__init__()

class CredentialNoBuvid3Exception(ApiException):
    def __init__(self):
        self.msg = "未传入有效的 buvid3"
        super().__init__()

class CredentialNoBuvid4Exception(ApiException):
    def __init__(self):
        self.msg = "未传入有效的 buvid4"
        super().__init__()

class CredentialNoDedeUserIDException(ApiException):
    def __init__(self):
        self.msg = "未传入有效的 dedeuserid"
        super().__init__()

class CredentialNoSessdataException(ApiException):
    def __init__(self):
        self.msg = "未传入有效的 sessdata"
        super().__init__()

class DanmakuClosedException(ApiException):
    def __init__(self):
        self.msg = "弹幕已关闭"
        super().__init__()

class DynamicExceedImagesException(ApiException):
    def __init__(self):
        self.msg = "动态携带图片数超过上限"
        super().__init__()

class WbiRetryTimesExceedException(ApiException):
    def __init__(self):
        self.msg = "WBI 重试次数超限"
        super().__init__()


# ── 模式 B: 有参构造 (7 个) ──────────────────────────────────

class ArgsException(ApiException):
    def __init__(self, msg="参数错误"):
        super().__init__(msg)

class InitialStateException(ApiException):
    def __init__(self, msg="未获取到初始状态"):
        super().__init__(msg)

class LiveException(ApiException):
    def __init__(self, msg="直播间异常"):
        super().__init__(msg)

class LoginError(ApiException):
    def __init__(self, msg="登录错误"):
        super().__init__(msg)

class ResponseException(ApiException):
    def __init__(self, msg="响应错误"):
        super().__init__(msg)

class StatementException(ApiException):
    def __init__(self, msg="声明错误"):
        super().__init__(msg)

class VideoUploadException(ApiException):
    def __init__(self, msg="上传错误"):
        super().__init__(msg)


# ── 模式 C: 有参但忽略参数 (1 个) ───────────────────────────

class GeetestException(ApiException):
    def __init__(self, msg: str = ""):
        self.msg = "验证码处理错误"
        super().__init__()
```

#### 1.2 保留 5 个独立文件

`ApiException.py`、`NetworkException.py`、`ResponseCodeException.py`、`ExClimbWuzhiException.py`、`CookiesRefreshException.py`。

#### 1.3 重写 `exceptions/__init__.py`

```python
from .ApiException import ApiException
from .NetworkException import NetworkException
from .ResponseCodeException import ResponseCodeException
from .ExClimbWuzhiException import ExClimbWuzhiException
from .CookiesRefreshException import CookiesRefreshException
from ._simple import (
    ArgsException,
    CredentialNoAcTimeValueException,
    CredentialNoBiliJctException,
    CredentialNoBuvid3Exception,
    CredentialNoBuvid4Exception,
    CredentialNoDedeUserIDException,
    CredentialNoSessdataException,
    DanmakuClosedException,
    DynamicExceedImagesException,
    GeetestException,
    InitialStateException,
    LiveException,
    LoginError,
    ResponseException,
    StatementException,
    VideoUploadException,
    WbiRetryTimesExceedException,
)
```

#### 1.4 删除 17 个旧文件

删除：`ArgsException.py`、`CredentialNoAcTimeValueException.py`、`CredentialNoBiliJctException.py`、`CredentialNoBuvid3Exception.py`、`CredentialNoBuvid4Exception.py`、`CredentialNoDedeUserIDException.py`、`CredentialNoSessdataException.py`、`DanmakuClosedException.py`、`DynamicExceedImagesException.py`、`GeetestException.py`、`InitialStateException.py`、`LiveException.py`、`LoginError.py`、`ResponseException.py`、`StatementException.py`、`VideoUploadException.py`、`WbiRetryTimesExceedException.py`

保留：`ApiException.py`、`NetworkException.py`、`ResponseCodeException.py`、`ExClimbWuzhiException.py`、`CookiesRefreshException.py`

### 影响范围

| 受影响文件 | 改动类型 | 说明 |
|-----------|----------|------|
| `exceptions/__init__.py` | **重写** | 重新导出 |
| `exceptions/_simple.py` | **新建** | 17 个异常 |
| `exceptions/*.py` (17 个) | **删除** | 被合并 |
| `exceptions/ApiException.py` | 保留 | 基类不动 |
| `exceptions/NetworkException.py` | 保留 | 双参数 `(status, msg)` |
| `exceptions/ResponseCodeException.py` | 保留 | 三参数 `(code, msg, raw)` |
| `exceptions/ExClimbWuzhiException.py` | 保留 | 双参数 `(code, msg)` |
| `exceptions/CookiesRefreshException.py` | 保留 | 自定义 `__str__` |
| 所有 import 路径如 `from .exceptions.NetworkException import NetworkException` 的文件 | **无改动** | `__init__.py` 重新导出保证向后兼容 |

**零破坏性变更**：所有外部 import 路径保持不变，因为 `__init__.py` 的 re-export 保持一致。

### 验证

```bash
cd /root/.openclaw/workspace/bilibili-api-python
python3 -c "from bilibili_api.exceptions import *; print('OK')"
ruff check bilibili_api/
```

---

## Phase 2: network.py 拆分 [P0]

### 目标

将 `utils/network.py`（2422 行）拆分为 6 个职责明确的模块。

### 现状

`network.py` 当前结构（已校准行号）：

| 区域 | 行范围 | 行数 | 职责 |
|------|--------|------|------|
| imports | 1-50 | 50 | 全部依赖 |
| Logger (RequestLog + request_log 实例) | 51-230 | 180 | 请求日志 |
| RequestSettings + DEFAULT_SETTINGS | 244-434 | 190 | 请求设置（含冗长 getter/setter） |
| BiliAPIResponse / BiliWsMsgType / BiliAPIFile | 438-510 | 72 | 数据类 |
| BiliAPIClient ABC + 注册/选择函数 | 514-960 | 446 | 会话管理（**⚠️ docstring 内嵌副本占 ~210 行，见 2.2.3 注意**） |
| Credential 类 | 1148-1570 | 422 | 凭据 + cookies 刷新 |
| APPKEY/APPSEC + HEADERS + 反爬虫 | 1575-2095 | 520 | buvid/wbi/sign/ticket + UA 常量 |
| Api class + bili_simple_download | 2099-2422 | 323 | API 请求核心 |

### 改动方案

#### 2.1 拆分为以下文件

```
bilibili_api/utils/
├── network.py          # 薄壳 re-export，保持向后兼容
├── _log.py             # RequestLog 类 + request_log 实例 (~180 行)
├── _session.py         # BiliAPIClient ABC + 注册/选择 + 全局变量 (~450 行；删除内嵌 docstring 副本后 ~240 行)
├── _types.py           # BiliAPIResponse, BiliWsMsgType, BiliAPIFile, RequestSettings (~200 行)
├── _credential.py      # Credential 类 + cookies 刷新 (~420 行)
├── _anti_spider.py     # buvid/wbi/sign/ticket/mixin + HEADERS + APPKEY/APPSEC (~520 行)
└── _api.py             # Api 类 + bili_simple_download (~320 行)
```

#### 2.2 逐步迁移步骤

**Step 2.2.1 — 提取 `_types.py`**
- 移动 `BiliAPIResponse`、`BiliWsMsgType`、`BiliAPIFile` dataclass 定义
- 移动 `RequestSettings` 类

**Step 2.2.2 — 提取 `_log.py`**
- 移动 `RequestLog` 类
- 移动 `request_log` 实例

**Step 2.2.3 — 提取 `_session.py`**
- 移动 `BiliAPIClient` ABC
- 移动 `sessions`、`session_pool`、`lazy_settings`、`client_settings`、`selected_client` 全局变量
- 移动 `register_client`、`unregister_client`、`select_client`、`get_selected_client`、`get_available_settings`、`get_registered_clients`、`get_registered_available_settings`、`get_client`、`get_session`、`set_session` 函数
- 移动 `DEFAULT_SETTINGS`、`__clean` atexit handler
- 此文件 import `_types.py` 和 `_log.py`
- **⚠️ 关键清理**：`BiliAPIClient` 类的 docstring 内嵌了一个完整的类定义副本（L519-938），约 210 行纯文本重复。**删除这段 docstring 副本**，只保留原始的简洁中文描述。这将使 `_session.py` 从 ~450 行降到 ~240 行。

**Step 2.2.4 — 提取 `_credential.py`**
- 移动 `Credential` 类（L1148-1570）
- 移动 `_check_valid`、`_check_cookies`、`_getCorrespondPath`、`_get_refresh_csrf`、`_refresh_cookies`、`_confirm_refresh`
- 此文件 import `_session.py`（用到 `get_client`）
- import `_types.py`（`HEADERS` 将在 `_anti_spider.py` 中，通过 `_anti_spider.py` 间接获取；或直接 import `_anti_spider.py` 的 `HEADERS`）
- import `_anti_spider.py`（用到 `API` 字典 = `get_api("credential")`，其 URL 拼接用 `APPKEY`/`APPSEC`）

**Step 2.2.5 — 提取 `_anti_spider.py`**
- 移动 `APPKEY`、`APPSEC` 常量（L1575-1576）
- 移动 `HEADERS` 常量（L1577-1580）— **HEADERS 本质是反爬虫 UA 伪装，跟随反爬虫拆分更合理**
- 移动 `API = get_api("credential")`（L1581）
- 移动 `_get_spi_buvid`、`_active_buvid`（含内嵌的 murmur3_x64_128 纯 Python 实现 ~80 行，以及 ~200 行硬编码浏览器指纹 payload）、`_get_nav`、`_get_mixin_key`、`_enc_wbi`、`_enc_dm`、`_enc_sign`、`_get_bili_ticket`
- 移动以下公开函数：
  - `get_buvid()` (async)
  - `refresh_buvid()` (sync)
  - `get_bili_ticket()` (async)
  - `refresh_bili_ticket()` (sync)
  - `recalculate_wbi()` (sync)
  - `get_wbi_mixin_key()` (async) — **v1.0 遗漏，v1.1 补充**
- 此文件 import `_session.py`（`get_client`）、`_types.py`（如有需要）、`_log.py`（`request_log`）

**Step 2.2.6 — 提取 `_api.py`**
- 移动 `Api` 类全部代码（L2099-2415）
- 移动 `bili_simple_download` 函数（L2417-2422）
- 此文件 import `_session.py`（`get_client`）、`_anti_spider.py`（`get_buvid`、`get_wbi_mixin_key`、`get_bili_ticket`、`_enc_wbi`、`_enc_dm`、`_enc_sign`）、`_credential.py`（`Credential`）、`_types.py`（`HEADERS`）、`_log.py`（`request_log`）、exceptions

**Step 2.2.7 — 重写 `network.py` 为薄壳**

```python
"""
bilibili_api.utils.network — 兼容性 re-export。

所有实现已拆分到 _types / _log / _session / _credential / _anti_spider / _api。
此文件仅保持向后兼容的 import 路径。
"""
from ._types import *
from ._log import *
from ._session import *
from ._credential import *
from ._anti_spider import *
from ._api import *
```

**重要**：`from ._xxx import *` 要求各子模块定义 `__all__`，只导出公开 API，避免暴露内部符号。

### 影响范围

| 受影响文件 | 改动类型 | 说明 |
|-----------|----------|------|
| `utils/network.py` | **重写** | 变为 re-export 壳 |
| `utils/_types.py` | **新建** | dataclass + RequestSettings |
| `utils/_log.py` | **新建** | RequestLog |
| `utils/_session.py` | **新建** | 会话管理 + BiliAPIClient ABC（删除内嵌 docstring 副本） |
| `utils/_credential.py` | **新建** | Credential + cookies 刷新 |
| `utils/_anti_spider.py` | **新建** | 反爬虫全部逻辑 + HEADERS + APPKEY/APPSEC |
| `utils/_api.py` | **新建** | Api 类 |
| **44 个业务模块** (activity ~ watchroom) | **无改动** | 全部通过 `from .utils.network import ...`，re-export 兼容 |
| **3 个 client 实现** (AioHTTP/CurlCFFI/HTTPX) | **无改动** | 同理 |
| `__init__.py` | **无改动** | 同理 |
| `tests/` | **无改动** | 同理 |

**零破坏性变更**：所有 import 路径保持不变。

### 内部依赖关系（新模块间）

```
_types.py      ← 无内部依赖
_log.py        ← 无内部依赖
_session.py    ← _types.py, _log.py
_credential.py ← _session.py, _anti_spider.py, exceptions
_anti_spider.py← _session.py, _types.py (可选), _log.py, exceptions
_api.py        ← _session.py, _anti_spider.py, _credential.py, _types.py, _log.py, exceptions
network.py     ← 全部 re-export
```

### 验证

```bash
python3 -c "
from bilibili_api.utils.network import (
    Credential, Api, BiliAPIClient, BiliAPIResponse, BiliWsMsgType,
    BiliAPIFile, request_settings, request_log, register_client,
    get_client, get_session, set_session, select_client,
    get_buvid, get_bili_ticket, recalculate_wbi, refresh_buvid,
    bili_simple_download, HEADERS, get_selected_client,
    get_available_settings, get_registered_clients,
    get_registered_available_settings, unregister_client,
    get_wbi_mixin_key,
)
print('All exports OK')
"
ruff check bilibili_api/utils/
```

---

## Phase 3: 全局状态封装 [P0]

### 目标

消除 30+ 处模块级 `global` 变量，用类或 `functools.cached_property` 替代，解决并发安全问题。

### 现状

全局变量分布：

| 文件 | 全局变量 | 用途 | 并发风险 |
|------|---------|------|---------|
| `utils/_anti_spider.py` (原 network.py) | `__buvid3`, `__buvid4` | buvid 缓存 | ⚠️ 高：多协程可能同时触发刷新 |
| `utils/_anti_spider.py` | `__bili_ticket`, `__bili_ticket_expires` | bili_ticket 缓存 | ⚠️ 高：过期判断无锁 |
| `utils/_anti_spider.py` | `__wbi_mixin_key` | wbi mixin key 缓存 | ⚠️ 高：-403 重试时重算 |
| `utils/_session.py` (原 network.py) | `sessions`, `session_pool`, `lazy_settings`, `client_settings`, `selected_client` | 会话管理 | ⚠️ 中：已有隐式按 event loop 隔离 |
| `dynamic.py` | `uname2uid`, `uid2uname` | 用户名 ↔ UID 映射缓存 | ⚠️ 低：只读写入不重叠 |
| `bangumi.py` | `bangumi_md_to_ss`, `bangumi_ss_to_md`, `episode_data_cache` | 番剧映射缓存 | ⚠️ 低 |
| `cheese.py` | `cheese_video_meta_cache` | 课程元数据缓存 | ⚠️ 低 |
| `watchroom.py` | `watch_room_bangumi_cache` | 观看室番剧缓存 | ⚠️ 低 |
| `channel_series.py` | `channel_meta_cache` | 频道合集缓存 | ⚠️ 低 |
| `garb.py` | `dlc_properties` | 装扮 DLC 属性缓存 | ⚠️ 低 |
| `live_area.py` | `live_area_data` | 直播分区数据缓存 | ⚠️ 低 |
| `utils/cache_pool.py` | `article2dynamic` 等 5 个 dict | 文章↔动态映射 | ⚠️ 中：多模块共享写入 |

### 改动方案

#### 3.1 反爬虫缓存 → `AntiSpiderCache` 类（Phase 2 后在 `_anti_spider.py` 中改）

```python
class AntiSpiderCache:
    """线程/协程安全的反爬虫参数缓存"""
    def __init__(self):
        self._buvid3: str = ""
        self._buvid4: str = ""
        self._bili_ticket: str = ""
        self._bili_ticket_expires: int = 0
        self._wbi_mixin_key: str = ""
        self._lock = asyncio.Lock()

    async def get_buvid(self) -> tuple[str, str]: ...
    async def get_bili_ticket(self) -> tuple[str, str]: ...
    async def get_wbi_mixin_key(self) -> str: ...
    def invalidate_buvid(self) -> None: ...
    def invalidate_bili_ticket(self) -> None: ...
    def invalidate_wbi(self) -> None: ...

anti_spider_cache = AntiSpiderCache()
```

- `refresh_buvid()` 等公开函数改为调用 `anti_spider_cache.invalidate_xxx()`
- `get_buvid()` 等改为 `await anti_spider_cache.get_buvid()`
- **签名无变更**：`get_buvid()`、`get_bili_ticket()`、`get_wbi_mixin_key()` 当前已经是 `async def`，`refresh_buvid()`、`refresh_bili_ticket()`、`recalculate_wbi()` 当前已经是 `def`（同步，只做状态清除），封装为 `invalidate_*` 保持同步。

#### 3.2 业务模块缓存 → 模块级 `_Cache` 类

每个有全局缓存的模块创建一个简单的缓存类：

```python
# dynamic.py
class _DynamicCache:
    uid2uname: dict[int, str] = {}
    uname2uid: dict[str, int] = {}

_cache = _DynamicCache()
```

**保持全局实例**，但类型更清晰。不强制加锁（这些是低风险的懒加载缓存）。

#### 3.3 `cache_pool.py` → 类型标注加强

给现有的裸 dict 加类型标注：

```python
article2dynamic: dict[int, str] = {}
dynamic2article: dict[int, int] = {}
article_is_note: dict[int, bool] = {}
dynamic_is_article: dict[int, bool] = {}
dynamic_is_opus: dict[int, bool] = {}
```

### 影响范围

| 受影响文件 | 改动类型 | 说明 |
|-----------|----------|------|
| `utils/_anti_spider.py` | **重构** | `AntiSpiderCache` 类 |
| `utils/network.py` (re-export) | 无改动 | re-export 不变 |
| `utils/_api.py` | **修改** | 调用 `anti_spider_cache` |
| `utils/_credential.py` | **修改** | `get_buvid_cookies()` 中调用 `anti_spider_cache.get_buvid()` |
| **所有用 `get_buvid` / `get_bili_ticket` 的文件** | **无改动** | 这些函数保持 async 签名不变 |
| `dynamic.py` | **小改** | `_DynamicCache` 类 |
| `bangumi.py` | **小改** | `_BangumiCache` 类 |
| `cheese.py` | **小改** | `_CheeseCache` 类 |
| `watchroom.py` | **小改** | `_WatchroomCache` 类 |
| `channel_series.py` | **小改** | `_ChannelCache` 类 |
| `garb.py` | **小改** | `_GarbCache` 类 |
| `live_area.py` | **小改** | `_LiveAreaCache` 类 |
| `utils/cache_pool.py` | **小改** | 加类型标注 |
| `article.py` / `note.py` / `opus.py` / `dynamic.py` | **无改动** | `cache_pool` 属性名不变 |
| `__init__.py` | **无改动** | re-export 函数签名不变 |
| **外部用户代码** | **零破坏性** | 所有公开签名保持不变 |

### ⚠️ 签名变更评估（v1.1 修正）

**结论：不存在同步→异步的破坏性变更。**

| 函数 | 当前签名 | 封装后签名 | 变更 |
|------|---------|-----------|------|
| `get_buvid()` | `async def` | `async def` (委托给 `anti_spider_cache.get_buvid()`) | 无 |
| `get_bili_ticket()` | `async def` | `async def` | 无 |
| `get_wbi_mixin_key()` | `async def` | `async def` | 无 |
| `refresh_buvid()` | `def` (同步) | `def` (委托给 `anti_spider_cache.invalidate_buvid()`) | 无 |
| `refresh_bili_ticket()` | `def` (同步) | `def` | 无 |
| `recalculate_wbi()` | `def` (同步) | `def` (委托给 `anti_spider_cache.invalidate_wbi()`) | 无 |

v1.0 的 spec 错误地声称 `get_buvid()` 等是同步函数、封装后变为异步。实际上它们一直都是 async，`refresh_*` / `recalculate_*` 一直都是同步且只做状态清除。封装进 `AntiSpiderCache` 不会改变任何公开签名。

### 验证

```bash
ruff check bilibili_api/
python3 -c "
import inspect
from bilibili_api.utils.network import get_buvid, refresh_buvid, get_wbi_mixin_key
assert inspect.iscoroutinefunction(get_buvid), 'get_buvid should be async'
assert not inspect.iscoroutinefunction(refresh_buvid), 'refresh_buvid should be sync'
assert inspect.iscoroutinefunction(get_wbi_mixin_key), 'get_wbi_mixin_key should be async'
print('signature verification OK')
"
```

---

## Phase 4: Type Hints 现代化 [P2]

### 目标

将旧式 `typing` 模块注解迁移到 Python 3.10+ 内置语法。

### 现状

39 个文件使用 `from typing import Dict, List, Optional, Tuple, Union`。（注：`clients/` 下的 3 个文件和 `tools/` 下的文件也可能受影响，实际总数可能略多。）

### 改动方案

#### 4.1 批量替换规则

| 旧写法 | 新写法 |
|--------|--------|
| `Dict[K, V]` | `dict[K, V]` |
| `List[T]` | `list[T]` |
| `Tuple[T1, T2]` | `tuple[T1, T2]` |
| `Optional[T]` | `T \| None` |
| `Union[A, B]` | `A \| B` |

#### 4.2 执行方式

使用 `ruff` 的 `UP` 规则集自动完成：

```bash
# 在 pyproject.toml 中添加：
[tool.ruff.lint]
select = ["E", "F", "W", "UP"]   # 新增 UP
ignore = ["E501"]

# 然后执行自动修复：
ruff check --fix bilibili_api/
```

#### 4.3 手动处理

- 函数签名中 `Union[str, None]` 等同于 `str | None`，ruff `UP007` 会处理
- `from typing import ...` 中不再需要的 import，ruff `F401` 会移除
- `_session.py` 中 `asyncio.AbstractEventLoop` 等 runtime 引用保持不变

### 影响范围

| 受影响文件 | 改动类型 | 说明 |
|-----------|----------|------|
| **~39+ 个 .py 文件** | **自动修改** | ruff `UP` 规则集 |
| `pyproject.toml` | **小改** | lint.select 新增 `"UP"` |
| 所有 42 个测试文件 | **无改动** | tests 已有 `per-file-ignores` |
| `__init__.py` | **自动修改** | `Union` → `\|` |
| `utils/network.py` (re-export 壳) | **自动修改** | 但其内容全是 re-export，无类型注解 |

### 验证

```bash
ruff check bilibili_api/
python3 -c "import bilibili_api; print('import OK')"
```

---

## Phase 5: 可变默认参数修复 [P2]

### 目标

消除 `params: dict = {}`、`headers: dict = {}` 等可变默认参数。

### 现状

共约 **30 处**可变默认参数（v1.0 估计 ~10 处，严重不足）：

| 文件 | 位置 | 可变默认参数 | 数量 |
|------|------|-------------|------|
| `utils/_session.py` (原 network.py, BiliAPIClient ABC) | L600, L602, L603, L604, L683, L820, L822, L823, L850, L902 | `params: dict = {}`, `data: Union[dict, str, bytes] = {}`, `files: Dict[str, BiliAPIFile] = {}`, `headers: dict = {}`, `cookies: dict = {}` | 10 |
| `utils/_credential.py` (原 network.py, Credential) | L1368 | `cookies: dict = {}` | 1 |
| `clients/AioHTTPClient.py` | L80, L81, L83, L177, L228 | `params: dict = {}`, `data: Union[dict, str, bytes] = {}`, `headers: dict = {}` | 5 |
| `clients/CurlCFFIClient.py` | L105, L106, L108, L186, L232 | `params: dict = {}`, `data: Union[dict, str, bytes] = {}`, `headers: dict = {}` | 5 |
| `clients/HTTPXClient.py` | L113, L114, L116, L184 | `params: dict = {}`, `data: Union[dict, str, bytes] = {}`, `headers: dict = {}` | 4 |
| `interactive_video.py` | L812 | `stream_detecting_params: dict = {}` | 1 |

### 改动方案

替换为 `None` 并在函数体内处理：

```python
# 之前
async def request(self, params: dict = {}, headers: dict = {}): ...

# 之后
async def request(self, params: dict | None = None, headers: dict | None = None):
    params = params or {}
    headers = headers or {}
    ...
```

#### ruff 自动修复

```bash
# 启用 B006 规则
[tool.ruff.lint]
select = ["E", "F", "W", "UP", "B"]   # 新增 B
ignore = ["E501"]
```

`ruff check --fix` 会自动处理大部分情况。**手动确认** `data: Union[dict, str, bytes] = {}` 的替换——因为空 dict 和空 bytes 语义不同，可能需要 `data: Union[dict, str, bytes] | None = None`。

### 影响范围

| 受影响文件 | 改动类型 | 说明 |
|-----------|----------|------|
| `utils/_session.py` (Phase 2 后) | **修改** | BiliAPIClient ABC 签名 (10 处) |
| `utils/_credential.py` | **修改** | `from_cookies` (1 处) |
| `clients/AioHTTPClient.py` | **修改** | request / download_create / ws_create (5 处) |
| `clients/CurlCFFIClient.py` | **修改** | 同上 (5 处) |
| `clients/HTTPXClient.py` | **修改** | 同上 (4 处) |
| `interactive_video.py` | **修改** | stream_detecting_params (1 处) |
| `pyproject.toml` | **小改** | lint.select 新增 `"B"` |

**⚠️ 破坏性**：`BiliAPIClient` 是 ABC，其子类签名必须匹配。但 `None` 默认值对调用者完全透明（传入 `{}` 仍然有效），所以**实际上零破坏**。

### 验证

```bash
ruff check bilibili_api/
python3 -c "from bilibili_api.utils.network import get_client; print('ABC intact')"
```

---

## Phase 6: eval() 替换 + 安全修复 [P2]

### 目标

消除 `__init__.py` 中的 `eval()` 调用。

### 现状

`bilibili_api/__init__.py` 第 95-97 行：

```python
def __register_all_clients():
    import importlib
    from .clients import ALL_PROVIDED_CLIENTS
    for module, client, settings in ALL_PROVIDED_CLIENTS[::-1]:
        try:
            importlib.import_module(module)
        except ModuleNotFoundError:
            continue
        client_module = importlib.import_module(
            name=f".clients.{client}", package="bilibili_api"
        )
        client_class = eval(f"client_module.{client}")  # ← 不安全
        register_client(module, client_class, settings)
```

### 改动方案

```python
client_class = getattr(client_module, client)
```

一行替换。`getattr` 比 `eval` 更安全、更快、类型检查友好。

### 影响范围

| 受影响文件 | 改动类型 | 说明 |
|-----------|----------|------|
| `bilibili_api/__init__.py` | **单行修改** | `eval()` → `getattr()` |

零破坏性变更。

### 验证

```bash
python3 -c "from bilibili_api import get_selected_client; print('client registration OK')"
```

---

## Phase 7: 裸异常捕获收紧 [P3]

### 目标

将 18 处 `except Exception` 替换为具体异常类型。

### 现状

| 文件 | 裸异常数 | 建议捕获类型 |
|------|---------|-------------|
| `video_uploader.py` | 11 | `NetworkException`, `ResponseCodeException`, `CancelledError` |
| `video.py` | 2 | `NetworkException`, `ResponseException` |
| `utils/_api.py` (原 network.py L2384) | 1 | `ResponseCodeException`（已有该逻辑，可能冗余） |
| `utils/_session.py` (原 network.py L1090) | 1 | `AttributeError`（已有，无需改） |
| `utils/parse_link.py` | 2 | `ResponseCodeException`, `NetworkException` |
| `utils/initial_state.py` | 1 | `NetworkException`, `ResponseException` |
| `utils/short.py` | 1 | `NetworkException`, `ResponseException` |
| `utils/upos.py` | 1 | `NetworkException` |
| `utils/AsyncEvent.py` | 1 | 保留（事件分发不应中断） |

### 改动方案

逐文件分析 `except Exception` 上下文，替换为：

1. **网络/请求相关** → `NetworkException, ResponseException, ResponseCodeException`
2. **取消操作** → `asyncio.exceptions.CancelledError`（单独捕获，不继承 Exception）
3. **事件分发/日志** → 保留 `Exception`（这是有意为之的全局兜底）
4. **`except Exception as e: raise e`** → 删除（冗余代码）

### 影响范围

| 受影响文件 | 改动类型 | 说明 |
|-----------|----------|------|
| `video_uploader.py` | **11 处修改** | 上传逻辑的异常细化 |
| `video.py` | **2 处修改** | |
| `utils/_api.py` | **1 处修改** | |
| `utils/parse_link.py` | **2 处修改** | |
| `utils/initial_state.py` | **1 处修改** | |
| `utils/short.py` | **1 处修改** | |
| `utils/upos.py` | **1 处修改** | |

**零破坏性变更**：更窄的 catch 只会让更多异常正确传播，不会吞掉新类型。

### 验证

```bash
ruff check bilibili_api/
python3 -m pytest tests/ -x  # 如果有可运行的测试
```

---

## Phase 8: video.py 拆分 [P4]

### 目标

将 `video.py`（2672 行）拆分为更小的模块。

### 现状

| 区域 | 行范围 | 职责 |
|------|--------|------|
| imports + helpers | 1-130 | get_cid_info 等 |
| `DanmakuOperatorType` enum | 53-60 | |
| `VideoAppealReasonType` | 67-140 | 投诉原因 |
| `Video` class | 145-1840 | 主类，~1700 行 |
| `VideoOnlineMonitor` | 1845-2160 | 视频在线监控，~400 行 |
| Quality/Codecs enums | 2164-2228 | |
| Download URL dataclasses | 2228-2310 | |
| `VideoDownloadURLDataDetecter` | 2320-2672 | 下载 URL 解析，~350 行 |

### 改动方案

#### 8.1 拆分结构

```
bilibili_api/
├── video.py              # 薄壳 re-export + Video 主类（精简到 ~1200 行）
├── _video_appeal.py       # VideoAppealReasonType (~80 行)
├── _video_monitor.py      # VideoOnlineMonitor (~400 行)
├── _video_download.py     # 下载 URL 相关的 dataclass + DataDetecter (~500 行)
```

#### 8.2 详细步骤

**Step 8.2.1** — 提取 `VideoAppealReasonType` 到 `_video_appeal.py`
- 包含 `DanmakuOperatorType`（与投诉相关）

**Step 8.2.2** — 提取 `VideoOnlineMonitor` 到 `_video_monitor.py`
- 依赖：`Video` 类（前向引用）
- 依赖：`utils/network`（`get_client`, `BiliWsMsgType`）
- 依赖：`BytesReader`
- 依赖：`utils/danmaku`（`Danmaku`, `SpecialDanmaku`）

**Step 8.2.3** — 提取下载相关到 `_video_download.py`
- `VideoQuality`、`VideoCodecs`、`AudioQuality` enums
- `VideoStreamDownloadURL`、`AudioStreamDownloadURL`、`FLVStreamDownloadURL`、`MP4StreamDownloadURL` dataclasses
- `VideoDownloadURLDataDetecter` 类
- 依赖：`yarl.URL`

**Step 8.2.4** — 重写 `video.py`
- 保留 `Video` 主类
- re-export 子模块的公开符号

### 影响范围

| 受影响文件 | 改动类型 | 说明 |
|-----------|----------|------|
| `video.py` | **重构** | Video 主类保留 + re-export |
| `bilibili_api/_video_appeal.py` | **新建** | |
| `bilibili_api/_video_monitor.py` | **新建** | |
| `bilibili_api/_video_download.py` | **新建** | |
| `pyproject.toml` | **小改** | setuptools.packages 新增条目（或通配符） |
| `__init__.py` | **无改动** | 已有 `from . import video` |
| `ass.py` | **无改动** | 通过 `from .video import Video`，re-export 兼容 |
| `tests/test_video.py` | **无改动** | 通过 `from bilibili_api import video` |
| `tools/ivitools/download.py` | **无改动** | `from bilibili_api import video` |

**零破坏性变更**：所有公开 import 路径不变。

### 验证

```bash
python3 -c "
from bilibili_api.video import Video, VideoOnlineMonitor, VideoDownloadURLDataDetecter, VideoAppealReasonType
print('video re-export OK')
"
ruff check bilibili_api/video.py bilibili_api/_video_*.py
```

---

## 执行顺序总结

| 顺序 | Phase | 优先级 | 预估工时 | 破坏性 | 可并行 |
|------|-------|--------|---------|--------|--------|
| 1 | Phase 1: 异常合并 | P0 | 1h | 无 | — |
| 2 | Phase 2: network.py 拆分 | P0 | 3h | 无 | — |
| 3 | Phase 3: 全局状态封装 | P0 | 2h | 无 | — |
| 4 | Phase 4: Type hints 现代化 | P2 | 0.5h | 无 | ✅ 与 5-7 |
| 5 | Phase 5: 可变默认参数 | P2 | 0.5h | 无 | ✅ 与 4, 6, 7 |
| 6 | Phase 6: eval 替换 | P2 | 5min | 无 | ✅ 与 4, 5, 7 |
| 7 | Phase 7: 裸异常捕获 | P3 | 1.5h | 无 | ✅ 与 4, 5, 6 |
| 8 | Phase 8: video.py 拆分 | P4 | 2h | 无 | — |

**总预估：~10.5 小时**（P0 串行 ~6h，其余可并行 ~4.5h）

---

## 风险与回退

1. **Phase 2 风险最高**：2422 行拆分需要逐函数验证 import。回退方案：保留原 `network.py`，新模块作为 `network_new/` 目录实验，通过 CI 对比运行。
2. **Phase 3 签名无变更**（v1.1 修正）：所有公开函数保持当前签名不变（async 仍 async，同步仍同步），零破坏性。
3. **Phase 4-5 ruff 自动修复**：执行前 `git stash`，修复后 `git diff --stat` 审查。

---

## 每阶段完成后必须执行的验证命令

```bash
# 1. ruff lint
ruff check bilibili_api/

# 2. import 完整性
python3 -c "import bilibili_api; print(f'v{bilibili_api.BILIBILI_API_VERSION}')"

# 3. 核心导出验证
python3 -c "
from bilibili_api import (
    Credential, Api, sync, Video, User, Dynamic,
    HEADERS, request_settings, request_log,
    ApiException, NetworkException, ResponseCodeException,
)
print('core exports OK')
"

# 4. 客户端注册验证
python3 -c "
from bilibili_api import get_selected_client
name, cls = get_selected_client()
print(f'client: {name} ({cls.__name__})')
"

# 5. git commit（每个 Phase 一个 commit）
git add -A && git commit -m "refactor: Phase X - 描述"
```

---

## 附录：需要更新 `pyproject.toml` 的位置

```toml
# Phase 4: 新增 UP 规则集
[tool.ruff.lint]
select = ["E", "F", "W", "UP"]

# Phase 5: 新增 B 规则集
select = ["E", "F", "W", "UP", "B"]

# Phase 8: 确保 packages 覆盖新文件（或确认通配符已生效）
[tool.setuptools]
packages = [
    "bilibili_api",
    "bilibili_api.utils",
    "bilibili_api.exceptions",
    "bilibili_api.clients",
    "bilibili_api.tools",
    "bilibili_api.tools.ivitools",
    "bilibili_api.tools.parser",
    "bilibili_api._pyinstaller",
    # 注意：_video_*.py 和 utils/_*.py 在 bilibili_api/ 和 bilibili_api/utils/ 下
    # 不需要额外添加，已由上层的 bilibili_api / bilibili_api.utils 覆盖
]
```
