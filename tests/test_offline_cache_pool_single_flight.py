# bilibili_api cache_pool 并发单飞与映射缓存有界化离线单元测试
#
# 本文件属于无凭据快速路径：全部用例均为纯本地逻辑验证，
# 不触碰网络、不读取 BILI_* 环境变量、不依赖真实账号。
# 覆盖 cached_async 单飞（含异常传播与失败不缓存）、模块级映射缓存的有界性。

import asyncio

from bilibili_api.utils import cache_pool
from bilibili_api.utils.cache_pool import TTLCache, cached_async

MODULE_MAPPING_NAMES = (
    "article2dynamic",
    "dynamic2article",
    "article_is_note",
    "dynamic_is_article",
    "dynamic_is_opus",
)


async def test_cached_async_single_flight_same_key():
    """同一键的 20 个并发调用应共享同一次底层执行，仅实际请求 1 次。"""
    call_count = 0

    @cached_async(ttl=60.0, maxsize=4)
    async def fake_api(key: int):
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.05)  # 模拟慢请求，放大并发窗口
        return {"key": key, "seq": call_count}

    results = await asyncio.gather(*(fake_api(1) for _ in range(20)))
    assert call_count == 1
    assert all(r == {"key": 1, "seq": 1} for r in results)
    # 全部等待者拿到的是同一份结果对象
    assert all(r is results[0] for r in results)
    # 单飞结束后再次调用应命中缓存，而非重新执行
    again = await fake_api(1)
    assert call_count == 1
    assert again is results[0]


async def test_cached_async_single_flight_exception():
    """底层抛异常时所有并发等待者都应收到异常，且失败结果不被缓存。"""
    call_count = 0

    @cached_async(ttl=60.0, maxsize=4)
    async def flaky_api(should_fail: bool):
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.02)
        if should_fail:
            raise ValueError("boom")
        return "ok"

    results = await asyncio.gather(flaky_api(True), flaky_api(True), flaky_api(True), return_exceptions=True)
    assert all(isinstance(r, ValueError) for r in results)
    assert call_count == 1  # 失败任务也只执行了一次

    # 失败不缓存、in-flight 表已清理：下一次调用重新执行
    assert await flaky_api(False) == "ok"
    assert call_count == 2
    assert await flaky_api(False) == "ok"
    assert call_count == 2  # 成功结果已缓存


async def test_cached_async_single_flight_distinct_keys_parallel():
    """不同键的并发调用应各自独立执行，互不合并。"""
    call_count = 0

    @cached_async(ttl=60.0, maxsize=8)
    async def fake_api(key: int):
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.01)
        return key * 10

    results = await asyncio.gather(*(fake_api(i) for i in range(4) for _ in range(3)))
    assert call_count == 4
    assert results == [i * 10 for i in range(4) for _ in range(3)]


def test_module_mappings_are_bounded_ttl_caches():
    """5 个模块级映射应均为有界 + 带 TTL 的 TTLCache 实例。"""
    for name in MODULE_MAPPING_NAMES:
        cache = getattr(cache_pool, name)
        assert isinstance(cache, TTLCache), f"{name} 应为 TTLCache"


def test_module_mapping_bounded_length():
    """模块级映射写入超过 maxsize 后，长度不得超过 maxsize（4096）。"""
    maxsize = 4096
    cache = cache_pool.article2dynamic
    # 该映射为自愈型缓存（缺失时会重新拉取填充），测试前后清空无副作用
    cache.clear()
    try:
        for i in range(maxsize + 100):
            cache.set(i, f"dyn-{i}")
        assert len(cache) <= maxsize
        # 最早写入的条目应已被 LRU 淘汰，最新写入的仍在
        assert cache.get(0) is None
        assert cache.get(maxsize + 99) == f"dyn-{maxsize + 99}"
    finally:
        cache.clear()
