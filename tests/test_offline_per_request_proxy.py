# bilibili_api per-request proxy 离线单元测试
#
# 本文件属于无凭据快速路径：全部用例均为纯本地逻辑验证，
# 不触碰网络、不读取 BILI_* 环境变量、不依赖真实账号。
# 覆盖：不同 Credential(proxy=...) 并发请求各自携带自己的代理且全局代理不变、
# 未实现 proxy 参数的第三方客户端兼容降级、代理探测缓存。

import asyncio

from bilibili_api import Credential, request_settings
from bilibili_api.utils import _api as api_module
from bilibili_api.utils._api import Api, _client_request_supports_proxy
from bilibili_api.utils._session import BiliAPIClient
from bilibili_api.utils._types import BiliAPIResponse, BiliWsMsgType

GLOBAL_PROXY = "http://global-proxy:8080"
PROXY_A = "http://proxy-a:1080"
PROXY_B = "http://proxy-b:1080"


def _ok_response(url: str) -> BiliAPIResponse:
    """构造一个可通过 _process_response 校验的假响应。"""
    return BiliAPIResponse(code=200, headers={}, cookies={}, raw=b'{"code": 0, "data": {}}', url=url)


class _BaseFakeClient(BiliAPIClient):
    """除 request 外全部空实现的假客户端基类。"""

    def __init__(self) -> None:
        self.records: list[dict] = []

    def get_wrapped_session(self) -> object:
        return None

    def set_timeout(self, timeout: float = 0.0) -> None:
        pass

    def set_proxy(self, proxy: str = "") -> None:
        pass

    def set_verify_ssl(self, verify_ssl: bool = True) -> None:
        pass

    def set_trust_env(self, trust_env: bool = True) -> None:
        pass

    async def download_create(self, url: str = "", headers: dict | None = None) -> int:
        return 0

    async def download_chunk(self, cnt: int) -> bytes:
        return b""

    def download_content_length(self, cnt: int) -> int:
        return 0

    async def download_close(self, cnt: int) -> None:
        pass

    async def ws_create(self, url: str = "", params: dict | None = None, headers: dict | None = None) -> int:
        return 0

    async def ws_send(self, cnt: int, data: bytes) -> None:
        pass

    async def ws_recv(self, cnt: int) -> tuple[bytes, BiliWsMsgType]:
        return b"", BiliWsMsgType.TEXT

    async def ws_close(self, cnt: int) -> None:
        pass

    async def close(self):
        pass


class ProxyCapturingClient(_BaseFakeClient):
    """支持 per-request proxy 的假客户端：记录每次请求的代理与当时的全局代理。"""

    async def request(
        self,
        method: str = "",
        url: str = "",
        params: dict | None = None,
        data: dict | str | bytes | None = None,
        files: dict | None = None,
        headers: dict | None = None,
        cookies: dict | None = None,
        allow_redirects: bool = True,
        proxy: str | None = None,
    ) -> BiliAPIResponse:
        await asyncio.sleep(0.02)  # 模拟慢请求，放大并发交错窗口
        self.records.append({"proxy": proxy, "global_proxy": request_settings.get_proxy()})
        return _ok_response(url)


class LegacyClient(_BaseFakeClient):
    """未实现 proxy 参数的第三方旧式客户端（旧 ABC 签名）。"""

    async def request(
        self,
        method: str = "",
        url: str = "",
        params: dict | None = None,
        data: dict | str | bytes | None = None,
        files: dict | None = None,
        headers: dict | None = None,
        cookies: dict | None = None,
        allow_redirects: bool = True,
    ) -> BiliAPIResponse:
        self.records.append({"global_proxy": request_settings.get_proxy()})
        return _ok_response(url)


def _make_api(proxy: str | None) -> Api:
    """构造携带指定代理凭据的只读 GET Api 实例。"""
    credential = Credential(sessdata="fake-sessdata", buvid3="fake-b3", buvid4="fake-b4", proxy=proxy)
    return Api(url="https://api.bilibili.com/fake", method="GET", credential=credential)


async def test_concurrent_credentials_use_own_proxies(monkeypatch):
    """两个不同代理的 Credential 并发请求：各自携带自己的代理，全局代理全程不变。"""
    client = ProxyCapturingClient()
    monkeypatch.setattr(api_module, "get_client", lambda: client)

    request_settings.set_proxy(GLOBAL_PROXY)
    set_proxy_calls: list[str] = []
    original_set_proxy = request_settings.set_proxy
    monkeypatch.setattr(
        request_settings, "set_proxy", lambda proxy: (set_proxy_calls.append(proxy), original_set_proxy(proxy))
    )
    try:
        await asyncio.gather(_make_api(PROXY_A).request(), _make_api(PROXY_B).request(), _make_api(None).request())
    finally:
        original_set_proxy("")  # 绕过 spy 复原全局代理，避免污染断言与其他用例

    assert len(client.records) == 3
    received = {record["proxy"] for record in client.records}
    assert received == {PROXY_A, PROXY_B, None}
    # 请求全程不得触碰全局代理：无 set_proxy 调用，且各请求时刻读到的全局代理均为原值
    assert set_proxy_calls == []
    assert all(record["global_proxy"] == GLOBAL_PROXY for record in client.records)
    assert request_settings.get_proxy() == ""  # finally 已复原


async def test_legacy_client_without_proxy_param_still_works(monkeypatch):
    """未实现 proxy 参数的第三方客户端应被自动探测降级，不报 TypeError。"""
    client = LegacyClient()
    monkeypatch.setattr(api_module, "get_client", lambda: client)
    request_settings.set_proxy(GLOBAL_PROXY)

    def forbid_set_proxy(proxy: str):
        raise AssertionError("不应修改全局代理")

    monkeypatch.setattr(request_settings, "set_proxy", forbid_set_proxy)
    try:
        assert _client_request_supports_proxy(client) is False
        # 凭据携带代理时也不应向旧式客户端传递 proxy 关键字，且全局代理不变
        await _make_api(PROXY_A).request()
    finally:
        request_settings.set("proxy", "")
    assert len(client.records) == 1
    assert client.records[0]["global_proxy"] == GLOBAL_PROXY


async def test_proxy_support_detection(monkeypatch):
    """探测结果应按客户端类缓存，且支持 **kwargs 的实现视为支持。"""

    class KwargsClient(_BaseFakeClient):
        async def request(self, **kwargs) -> BiliAPIResponse:
            return _ok_response("")

    capturing = ProxyCapturingClient()
    legacy = LegacyClient()
    kwargs_client = KwargsClient()
    assert _client_request_supports_proxy(capturing) is True
    assert _client_request_supports_proxy(legacy) is False
    assert _client_request_supports_proxy(kwargs_client) is True
    # 缓存命中：二次探测直接返回缓存值（不依赖 inspect 也可通过）
    assert api_module._CLIENT_REQUEST_PROXY_SUPPORT[type(capturing)] is True
    assert api_module._CLIENT_REQUEST_PROXY_SUPPORT[type(legacy)] is False
