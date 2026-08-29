# bilibili_api timeout 语义归一化离线单元测试
#
# 本文件属于无凭据快速路径：全部用例均为纯本地逻辑验证，
# 不触碰网络、不读取 BILI_* 环境变量、不依赖真实账号。
#
# 覆盖目标：三种请求客户端统一 "0 = 不限时" 语义。
# 实测背景（2026-08-29，httpx 0.28 / aiohttp 3.14.3 / curl_cffi 0.13）：
#   - httpx.Timeout(0.0) 是"立即超时"（connect/read 全为 0），与"不限时"相反；
#   - aiohttp 的 ceil_timeout 对 <= 0 视为"无超时"；
#   - curl_cffi 的 timeout=None 会被转换为 0，而 libcurl 中 TIMEOUT_MS=0 即"不限时"。
# 因此归一化目标分别为：httpx → None；aiohttp → None；curl_cffi → None。
# 实测注：httpx.AsyncClient(timeout=None) 会将属性折叠为 httpx.Timeout(None)
# （connect/read/write/pool 全为 None，即各项均不限时），而非保留 None 属性。

import aiohttp
import httpx

from bilibili_api.clients.AioHTTPClient import AioHTTPClient
from bilibili_api.clients.CurlCFFIClient import CurlCFFIClient
from bilibili_api.clients.HTTPXClient import HTTPXClient

# 无限时的统一表示：
# - httpx 会话的 timeout 属性折叠为 httpx.Timeout(None)（各项均不限时）；
# - aiohttp 请求路径的 timeout 参数为 None；
# - curl_cffi 会话的 timeout 属性为 None。
HTTPX_INFINITE = httpx.Timeout(None)
AIOHTTP_INFINITE = None
CURL_CFFI_INFINITE = None


class TestHTTPXClientTimeout:
    """HTTPXClient：<= 0 必须归一化为 None（无限时），避免 httpx 的"立即超时"语义。"""

    async def test_zero_timeout_on_init_means_infinite(self) -> None:
        client = HTTPXClient(timeout=0)
        try:
            assert client.get_wrapped_session().timeout == HTTPX_INFINITE
        finally:
            await client.close()

    async def test_set_timeout_zero_means_infinite(self) -> None:
        client = HTTPXClient(timeout=10.0)
        try:
            client.set_timeout(0)
            assert client.get_wrapped_session().timeout == HTTPX_INFINITE
            client.set_timeout(-1)
            assert client.get_wrapped_session().timeout == HTTPX_INFINITE
        finally:
            await client.close()

    async def test_positive_timeout_preserved(self) -> None:
        client = HTTPXClient(timeout=12.5)
        try:
            assert client.get_wrapped_session().timeout == httpx.Timeout(12.5)
        finally:
            await client.close()

    async def test_proxy_session_shares_normalization(self) -> None:
        """按代理缓存的辅助会话（__create_session）必须走同一归一化逻辑。"""
        client = HTTPXClient(timeout=0)
        try:
            proxy_session = client._HTTPXClient__create_session(proxy="http://127.0.0.1:1")
            try:
                assert proxy_session.timeout == HTTPX_INFINITE
            finally:
                await proxy_session.aclose()
        finally:
            await client.close()


class TestAioHTTPClientTimeout:
    """AioHTTPClient：<= 0 显式归一化为 None；实测 ceil_timeout 对 <= 0 本已视为无超时。"""

    def test_normalize_timeout_zero_is_none(self) -> None:
        normalize = AioHTTPClient._AioHTTPClient__normalize_timeout
        assert normalize(0) == AIOHTTP_INFINITE
        assert normalize(-5.0) == AIOHTTP_INFINITE

    def test_normalize_timeout_positive_is_client_timeout(self) -> None:
        normalize = AioHTTPClient._AioHTTPClient__normalize_timeout
        assert normalize(7.5) == aiohttp.ClientTimeout(total=7.5)

    def test_request_path_timeout_is_infinite_for_zero(self) -> None:
        """请求路径实际使用的 timeout 参数：0 → None（不限时）。"""
        client = AioHTTPClient(timeout=0)
        normalized = client._AioHTTPClient__normalize_timeout(client._AioHTTPClient__args["timeout"])
        assert normalized == AIOHTTP_INFINITE

    def test_request_path_timeout_after_set_timeout_zero(self) -> None:
        client = AioHTTPClient(timeout=30.0)
        client.set_timeout(0)
        normalized = client._AioHTTPClient__normalize_timeout(client._AioHTTPClient__args["timeout"])
        assert normalized == AIOHTTP_INFINITE


class TestCurlCFFIClientTimeout:
    """CurlCFFIClient：<= 0 归一化为 None；curl_cffi 将 None 转换为 0（libcurl 不限时）。"""

    async def test_zero_timeout_on_init_means_infinite(self) -> None:
        client = CurlCFFIClient(timeout=0)
        try:
            assert client.get_wrapped_session().timeout == CURL_CFFI_INFINITE
        finally:
            await client.close()

    async def test_set_timeout_zero_means_infinite(self) -> None:
        client = CurlCFFIClient(timeout=10.0)
        try:
            client.set_timeout(0)
            assert client.get_wrapped_session().timeout == CURL_CFFI_INFINITE
            client.set_timeout(-1)
            assert client.get_wrapped_session().timeout == CURL_CFFI_INFINITE
        finally:
            await client.close()

    async def test_positive_timeout_preserved(self) -> None:
        client = CurlCFFIClient(timeout=8.0)
        try:
            assert client.get_wrapped_session().timeout == 8.0
        finally:
            await client.close()
