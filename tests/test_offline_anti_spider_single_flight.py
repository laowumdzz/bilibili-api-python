# bilibili_api.utils._anti_spider 并发单飞离线单元测试
#
# 本文件属于无凭据快速路径：全部用例均为纯本地逻辑验证，
# 不触碰网络、不读取 BILI_* 环境变量、不依赖真实账号。
# 通过 monkeypatch 替换请求客户端为计数器假客户端，断言
# N 个并发调用同一反爬虫参数获取只产生 1 次网络请求（单飞/双重检查锁）。

import asyncio

import pytest

from bilibili_api.utils import _anti_spider
from bilibili_api.utils._anti_spider import AntiSpiderCache
from bilibili_api.utils._types import API, BiliAPIResponse

# 并发调用数：放大竞态窗口，验证锁的单飞效果
CONCURRENCY = 12

SPI_URL = API["info"]["spi"]["url"]
ACTIVE_URL = API["operate"]["active"]["url"]
TICKET_URL = API["info"]["ticket"]["url"]


class _CountingFakeClient:
    """按 URL 分发固定响应并统计各接口调用次数的假客户端。"""

    def __init__(self) -> None:
        self.counts: dict[str, int] = {}

    def _respond(self, url: str, payload: str) -> BiliAPIResponse:
        self.counts[url] = self.counts.get(url, 0) + 1
        return BiliAPIResponse(code=200, headers={}, cookies={}, raw=payload.encode("utf-8"), url=url)

    async def request(self, method: str = "", url: str = "", **kwargs) -> BiliAPIResponse:
        # 模拟慢请求，放大并发竞态窗口
        await asyncio.sleep(0.02)
        if url == SPI_URL:
            return self._respond(url, '{"code": 0, "data": {"b_3": "fake-buvid3", "b_4": "fake-buvid4"}}')
        if url == ACTIVE_URL:
            return self._respond(url, '{"code": 0, "message": "0"}')
        if url == TICKET_URL:
            return self._respond(url, '{"code": 0, "data": {"ticket": "fake-ticket"}}')
        raise AssertionError(f"意外的请求地址: {url}")


@pytest.fixture
def counting_client(monkeypatch):
    """安装计数假客户端并返回它。"""
    client = _CountingFakeClient()
    monkeypatch.setattr(_anti_spider, "get_client", lambda: client)
    return client


async def test_concurrent_get_buvid_single_flight(counting_client):
    """N 个并发 get_buvid 只应触发 1 次 spi 请求与 1 次激活请求。"""
    cache = AntiSpiderCache()
    results = await asyncio.gather(*[cache.get_buvid() for _ in range(CONCURRENCY)])

    assert all(result == ("fake-buvid3", "fake-buvid4") for result in results)
    assert counting_client.counts.get(SPI_URL) == 1, "并发下 spi 接口只应请求一次"
    assert counting_client.counts.get(ACTIVE_URL) == 1, "并发下激活接口只应请求一次"

    # 缓存命中：再次调用不产生新请求
    await cache.get_buvid()
    assert counting_client.counts.get(SPI_URL) == 1


async def test_concurrent_get_bili_ticket_single_flight(counting_client):
    """N 个并发 get_bili_ticket 只应触发 1 次 ticket 请求。"""
    cache = AntiSpiderCache()
    results = await asyncio.gather(*[cache.get_bili_ticket() for _ in range(CONCURRENCY)])

    tickets = {ticket for ticket, _expires in results}
    assert tickets == {"fake-ticket"}
    assert counting_client.counts.get(TICKET_URL) == 1, "并发下 ticket 接口只应请求一次"

    # 缓存命中：未过期时再次调用不产生新请求
    ticket, expires = await cache.get_bili_ticket()
    assert ticket == "fake-ticket"
    assert int(expires) > 0
    assert counting_client.counts.get(TICKET_URL) == 1


async def test_invalidate_triggers_refetch(counting_client):
    """invalidate 后再次获取应重新发起请求。"""
    cache = AntiSpiderCache()

    await cache.get_buvid()
    cache.invalidate_buvid()
    await cache.get_buvid()
    assert counting_client.counts.get(SPI_URL) == 2, "作废后应重新获取 buvid"

    await cache.get_bili_ticket()
    cache.invalidate_bili_ticket()
    await cache.get_bili_ticket()
    assert counting_client.counts.get(TICKET_URL) == 2, "作废后应重新获取 bili_ticket"


async def test_expired_ticket_refetched(counting_client):
    """到期时间已过时应重新请求 ticket（无需显式 invalidate）。"""
    cache = AntiSpiderCache()
    await cache.get_bili_ticket()

    # 手工将到期时间拨回过去，模拟过期
    cache._bili_ticket_expires = 0
    await cache.get_bili_ticket()
    assert counting_client.counts.get(TICKET_URL) == 2
