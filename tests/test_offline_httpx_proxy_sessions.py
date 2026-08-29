# bilibili_api HTTPXClient 代理辅助会话治理离线单元测试
#
# 本文件属于无凭据快速路径：全部用例均为纯本地逻辑验证，
# 不触碰网络、不读取 BILI_* 环境变量、不依赖真实账号。
#
# 覆盖目标：
# 1. 配置漂移：set_timeout / set_verify_ssl / set_trust_env / set_http2 / set_proxy
#    变更后，按代理缓存的辅助会话必须整体作废（关闭并清空），下次请求按新配置惰性重建。
# 2. 无界增长：__proxy_sessions 有容量上限（OrderedDict 维护插入顺序），
#    超限时关闭并淘汰最旧条目。

import asyncio
from importlib.util import find_spec

import httpx

from bilibili_api.clients.HTTPXClient import HTTPXClient

PROXY_A = "http://proxy-a:1080"
PROXY_B = "http://proxy-b:1080"


def _seed_proxy_session(client: HTTPXClient, proxy: str) -> httpx.AsyncClient:
    """向辅助会话缓存注入一个按当前配置创建的会话（模拟经由 request 建立的缓存）。"""
    session = client._HTTPXClient__create_session(proxy=proxy)
    client._HTTPXClient__proxy_sessions[proxy] = session
    return session


async def _drain_scheduled_closes() -> None:
    """让 __drop_proxy_sessions 通过 create_task 调度的 aclose 得以执行。"""
    for _ in range(5):
        await asyncio.sleep(0)


async def test_config_change_drops_proxy_sessions():
    """各配置变更入口须关闭并清空辅助会话，避免辅助会话持旧配置。"""
    client = HTTPXClient(timeout=10.0)
    try:
        setters = [
            lambda: client.set_timeout(20.0),
            lambda: client.set_verify_ssl(False),
            lambda: client.set_trust_env(False),
            lambda: client.set_proxy("http://main-proxy:8080"),
        ]
        # http2=True 需要可选依赖 h2，缺失时无法构造会话，跳过该入口（其余入口已覆盖同一处置路径）
        if find_spec("h2") is not None:
            setters.append(lambda: client.set_http2(True))
        for setter in setters:
            old_a = _seed_proxy_session(client, PROXY_A)
            old_b = _seed_proxy_session(client, PROXY_B)
            setter()
            # 缓存立即清空（下次请求按新配置惰性重建）
            assert client._HTTPXClient__proxy_sessions == {}
            await _drain_scheduled_closes()
            # 旧辅助会话被异步关闭，连接池不泄漏
            assert old_a.is_closed
            assert old_b.is_closed
    finally:
        await client.close()


async def test_rebuilt_proxy_session_uses_new_config():
    """配置变更后（重新缓存的）辅助会话须按新配置创建，此处以超时为例。"""
    client = HTTPXClient(timeout=10.0)
    try:
        _seed_proxy_session(client, PROXY_A)
        client.set_timeout(3.0)
        await _drain_scheduled_closes()
        # 模拟下次经代理请求时的惰性重建：新会话携带新超时
        rebuilt = client._HTTPXClient__create_session(proxy=PROXY_A)
        try:
            assert rebuilt.timeout == httpx.Timeout(3.0)
        finally:
            await rebuilt.aclose()
    finally:
        await client.close()


async def test_proxy_session_capacity_evicts_oldest():
    """超出容量上限时关闭并淘汰最先插入的辅助会话，其余保留。"""
    client = HTTPXClient()
    try:
        capacity = HTTPXClient.PROXY_SESSION_CAPACITY
        proxies = [f"http://proxy-{i}:1080" for i in range(capacity + 1)]
        sessions = [_seed_proxy_session(client, proxy) for proxy in proxies]

        await client._HTTPXClient__evict_proxy_sessions_over_capacity()

        cache = client._HTTPXClient__proxy_sessions
        assert len(cache) == capacity
        # 最旧（最先插入）条目被淘汰且已关闭，其余条目原样保留
        assert proxies[0] not in cache
        assert sessions[0].is_closed
        for proxy, session in zip(proxies[1:], sessions[1:], strict=True):
            assert cache[proxy] is session
            assert not session.is_closed
    finally:
        await client.close()


async def test_close_closes_all_proxy_sessions():
    """close() 须关闭全部辅助会话并清空缓存（回归既有行为）。"""
    client = HTTPXClient()
    session_a = _seed_proxy_session(client, PROXY_A)
    session_b = _seed_proxy_session(client, PROXY_B)

    await client.close()

    assert session_a.is_closed
    assert session_b.is_closed
    assert client._HTTPXClient__proxy_sessions == {}


if __name__ == "__main__":
    import pytest

    pytest.main([__file__, "-v"])
