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


def test_cached_async_self_heals_stale_task_from_dead_loop():
    """旧循环被销毁后残留的 in-flight 任务：等待分支报 RuntimeError 时须现场自愈重跑。

    病理路径：前一事件循环中发起的调用尚未完成时循环被销毁，任务残留在
    in-flight 表中；新循环中 await 该任务会抛 RuntimeError。装饰器应清除残留条目并重新执行。
    """
    block_forever = True

    @cached_async(ttl=60.0, maxsize=4)
    async def flaky_api(key: int):
        if block_forever:
            # 永不返回：模拟上一循环执行到一半被销毁，任务留在 in-flight 表
            await asyncio.Event().wait()
        return {"key": key}

    # 在旧循环中发起调用，待 in-flight 登记后直接销毁循环（不等待任务完成）
    old_loop = asyncio.new_event_loop()
    stale_task = old_loop.create_task(flaky_api(1))
    old_loop.run_until_complete(asyncio.sleep(0.05))
    old_loop.close()
    assert not stale_task.done()  # 任务确实未完成，残留在 in-flight 表中

    block_forever = False  # 新循环中重跑时底层函数正常返回，验证自愈后拿到正确结果
    result = asyncio.run(flaky_api(1))
    assert result == {"key": 1}


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
