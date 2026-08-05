# bilibili_api 性能优化相关离线单元测试
#
# 本文件属于无凭据快速路径：全部用例均为纯本地逻辑验证，
# 不触碰网络、不读取 BILI_* 环境变量、不依赖真实账号。
# 覆盖 get_api 缓存、TTLCache、cached_async、AsyncEvent 快速路径、RequestLog 监听器按需注册。

import asyncio
import subprocess
import sys
import time

from bilibili_api.utils._log import RequestLog
from bilibili_api.utils.AsyncEvent import AsyncEvent
from bilibili_api.utils.cache_pool import TTLCache, cached_async
from bilibili_api.utils.utils import _CRC_TABLE, _api_cache, get_api


def test_package_import_is_lazy():
    """import bilibili_api 不应急切加载任何功能子模块（子进程验证纯净导入环境）。"""
    code = (
        "import sys, bilibili_api; "
        "lazy = set(bilibili_api._LAZY_SUBMODULES); "
        "loaded = {m.split('.')[1] for m in sys.modules "
        "if m.startswith('bilibili_api.') and m.split('.')[1] in lazy}; "
        "assert not loaded, loaded"
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_lazy_submodule_access_loads_module():
    """访问惰性子模块属性应触发加载并返回同名模块（子进程验证首个入口可独立加载）。"""
    code = (
        "import bilibili_api; "
        "assert bilibili_api.video.__name__ == 'bilibili_api.video'; "
        "from bilibili_api import user; "
        "assert user.__name__ == 'bilibili_api.user'"
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_parse_link_lazy_submodules():
    """parse_link 模块导入不应预加载功能子模块，_ensure_submodules 应能惰性填充类名。"""
    from bilibili_api.utils import parse_link as pl_module

    # 模块自身可导入且入口函数可用（子模块是否已加载取决于测试收集顺序，不在此断言）
    assert callable(pl_module.parse_link)
    pl_module._ensure_submodules()
    assert pl_module._SUBMODULES_IMPORTED is True
    assert pl_module.Video.__name__ == "Video"
    assert pl_module.Episode.__name__ == "Episode"


def test_crc_table_built_once():
    """CRC32 查找表应为 256 项的模块级常量，且数值正确。"""
    assert len(_CRC_TABLE) == 256
    # 用独立实现校验前几项
    poly = 0xEDB88320
    for i in range(256):
        reg = i
        for _ in range(8):
            reg = poly ^ (reg >> 1) if reg & 1 else reg >> 1
        assert _CRC_TABLE[i] == reg


def test_get_api_cache_hit():
    """重复调用 get_api 应命中模块级缓存且结果一致。"""
    first = get_api("video")
    assert "video" in _api_cache
    second = get_api("video")
    assert first == second
    # 返回值为缓存顶层 dict 的浅拷贝，与缓存内容一致但非同一对象
    assert second is not _api_cache["video"]
    assert second == _api_cache["video"]


def test_get_api_leaf_shallow_copy():
    """带路径参数的 get_api 应返回叶子节点的浅拷贝，修改不污染缓存。"""
    leaf = get_api("video", "info", "detail")
    assert isinstance(leaf, dict)
    leaf["__pollution__"] = True
    assert "__pollution__" not in _api_cache["video"]["info"]["detail"]


def test_get_api_missing_field():
    """不存在的 API 分类应返回空 dict。"""
    assert get_api("__not_exist_field__") == {}


def test_ttl_cache_basic():
    """TTLCache 基本读写、命中与失效。"""
    cache = TTLCache(maxsize=2, ttl=60.0)
    cache.set("a", 1)
    assert cache.get("a") == 1
    assert "a" in cache
    assert len(cache) == 1
    cache.invalidate("a")
    assert cache.get("a") is None
    assert len(cache) == 0


def test_ttl_cache_expiry():
    """TTLCache 条目过期后应返回 None 并被清理。"""
    cache = TTLCache(maxsize=2, ttl=0.01)
    cache.set("a", 1)
    time.sleep(0.02)
    assert cache.get("a") is None
    assert len(cache) == 0


def test_ttl_cache_lru_eviction():
    """TTLCache 超出 maxsize 时应淘汰最久未使用的条目。"""
    cache = TTLCache(maxsize=2, ttl=60.0)
    cache.set("a", 1)
    cache.set("b", 2)
    cache.get("a")  # 访问 a，使 b 成为最久未使用
    cache.set("c", 3)
    assert cache.get("b") is None
    assert cache.get("a") == 1
    assert cache.get("c") == 3


async def test_cached_async_caches_result():
    """cached_async 应对相同参数复用结果，不同参数分别计算。"""
    calls = []

    @cached_async(ttl=60.0, maxsize=4)
    async def fake_api(aid: int, params: dict):
        calls.append((aid, params))
        return {"aid": aid}

    r1 = await fake_api(1, {"pn": 1})
    r2 = await fake_api(1, {"pn": 1})
    r3 = await fake_api(2, {"pn": 1})
    assert r1 == r2 == {"aid": 1}
    assert r3 == {"aid": 2}
    assert len(calls) == 2  # 相同参数只实际执行一次


async def test_cached_async_none_not_cached():
    """cached_async 不缓存 None 结果（对应接口无数据时每次重新请求）。"""
    calls = []

    @cached_async(ttl=60.0, maxsize=4)
    async def fake_api():
        calls.append(1)
        return None

    await fake_api()
    await fake_api()
    assert len(calls) == 2


def test_async_event_dispatch_no_listener_fast_path():
    """无监听器时 dispatch 应直接返回（不抛异常）。"""
    event = AsyncEvent()
    event.dispatch("ANY_EVENT", {"k": "v"})


def test_async_event_dispatch_listener():
    """有监听器时 dispatch 应触发同步回调。"""
    event = AsyncEvent()
    received = []

    @event.on("PING")
    def handler(data: dict):
        received.append(data)

    event.dispatch("ping", {"n": 1})
    assert received == [{"n": 1}]


def test_async_event_ignore():
    """被忽略的事件不应触发监听器。"""
    event = AsyncEvent()
    received = []

    @event.on("PING")
    def handler(data: dict):
        received.append(data)

    event.ignore_event("PING")
    event.dispatch("PING", {"n": 1})
    assert received == []


def test_request_log_listener_only_when_on():
    """RequestLog 关闭时不注册内部监听器，开启时注册，再次关闭时移除。"""
    log = RequestLog()
    assert log.is_on() is False
    log.dispatch("API_REQUEST", "desc", {"k": 1})  # 关闭状态下分发不报错
    log.set_on(True)
    assert log.is_on() is True
    log.set_on(False)
    assert log.is_on() is False
    log.dispatch("API_REQUEST", "desc", {"k": 1})


def test_request_log_user_listener_independent():
    """用户自行注册的监听器不受日志开关影响。"""
    log = RequestLog()
    received = []

    @log.on("REQUEST")
    def handler(desc: str, data: dict):
        received.append(desc)

    log.dispatch("REQUEST", "发起请求", {"url": "x"})
    assert received == ["发起请求"]


async def test_anti_spider_cache_invalidate_state():
    """AntiSpiderCache 的失效操作应重置缓存状态（不触发网络请求）。"""
    from bilibili_api.utils._anti_spider import AntiSpiderCache

    cache = AntiSpiderCache()
    cache._wbi_mixin_key = "test-key"
    cache._wbi_mixin_key_ts = int(time.time())
    cache._bili_ticket = "test-ticket"
    cache._bili_ticket_expires = str(int(time.time()) + 100)
    cache.invalidate_wbi()
    cache.invalidate_bili_ticket()
    assert cache._wbi_mixin_key == ""
    assert cache._wbi_mixin_key_ts == 0
    assert cache._bili_ticket == ""
    assert cache._bili_ticket_expires == 0
    # 锁为惰性创建，未发生并发获取时应为 None
    assert cache._lock is None
    lock = cache._get_lock()
    assert isinstance(lock, asyncio.Lock)
    assert cache._get_lock() is lock
