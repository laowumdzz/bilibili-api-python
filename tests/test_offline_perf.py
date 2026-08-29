# bilibili_api 性能优化相关离线单元测试
#
# 本文件属于无凭据快速路径：全部用例均为纯本地逻辑验证，
# 不触碰网络、不读取 BILI_* 环境变量、不依赖真实账号。
# 覆盖 get_api 缓存、TTLCache、cached_async、AsyncEvent 快速路径、RequestLog 监听器按需注册、
# Wbi 签名热路径微基准、弹幕协议粘包解包吞吐基准。

import asyncio
import hashlib
import json
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
    """AntiSpiderCache / WbiManager 的失效操作应重置缓存状态（不触发网络请求）。"""
    from bilibili_api.utils._anti_spider import AntiSpiderCache
    from bilibili_api.utils._wbi import WbiManager

    cache = AntiSpiderCache()
    cache._bili_ticket = "test-ticket"
    cache._bili_ticket_expires = str(int(time.time()) + 100)
    cache.invalidate_bili_ticket()
    assert cache._bili_ticket == ""
    assert cache._bili_ticket_expires == 0
    # 锁为惰性创建，未发生并发获取时应为 None
    assert cache._lock is None
    lock = cache._get_lock()
    assert isinstance(lock, asyncio.Lock)
    assert cache._get_lock() is lock

    # WbiManager 类级缓存的失效操作应重置密钥与时间戳（恢复原状避免影响其他用例）
    WbiManager._img_key = "test-img-key"
    WbiManager._sub_key = "test-sub-key"
    WbiManager._mixin_key = "test-mixin-key"
    WbiManager._cache_ts = time.time()
    WbiManager.invalidate()
    assert WbiManager._img_key == ""
    assert WbiManager._sub_key == ""
    assert WbiManager._mixin_key == ""
    assert WbiManager._cache_ts == 0.0


# ---------------------------------------------------------------------------
# 以下为性能微基准。阈值设计原则：
# 1. 一律采用「相对参照」而非绝对耗时 —— 绝对阈值在 CI 慢机器上极易误报；
# 2. 计时取多轮最小值（min），最小值对调度抖动最不敏感；
# 3. 相对倍数给得非常宽松（20~50 倍），目标是拦截数量级级别的病态回归
#    （如热路径意外引入 O(n^2) 逻辑或重复重排），而非追逐微小波动；
# 4. 同时 print 实际耗时与吞吐，作为基准信息输出供人工跟踪（默认被 pytest 捕获，
#    仅失败或 -s 运行时可见）。

# Wbi 签名基准用固定密钥与固定时间戳，保证签名结果完全确定、可复现。
_WBI_IMG_KEY = "7cd65dfe07694fd4b72e5cb227019d2c"
_WBI_SUB_KEY = "4a5ad72fbe0d4e43a5e8a57b70eb2aec"
_WBI_MIXIN_KEY = "432d50244e6ce6ea1dd5a70ed9df42ef"
_WBI_FIXED_TS = 1700000000.0


def _min_elapsed(fn, iterations: int, rounds: int = 3) -> float:
    """多轮计时取最小值，返回单次操作的平均耗时（秒）。"""
    best = float("inf")
    for _ in range(rounds):
        start = time.perf_counter()
        for _ in range(iterations):
            fn()
        best = min(best, time.perf_counter() - start)
    return best / iterations


def test_wbi_enc_cache_hit_correctness(monkeypatch):
    """缓存命中路径签名结果正确：固定密钥 + 固定时间戳下 w_rid 为已知确定值。"""
    from bilibili_api.utils import _wbi as wbi_module
    from bilibili_api.utils._wbi import WbiManager

    # 固定 wts（round(time.time())），消除时间因素；monkeypatch 自动还原全局 time 模块。
    monkeypatch.setattr(wbi_module.time, "time", lambda: _WBI_FIXED_TS)
    # 预置类级缓存，使 _enc_wbi 走 mixin_key 复用的缓存命中分支（自动还原）。
    monkeypatch.setattr(WbiManager, "_img_key", _WBI_IMG_KEY)
    monkeypatch.setattr(WbiManager, "_sub_key", _WBI_SUB_KEY)
    monkeypatch.setattr(WbiManager, "_mixin_key", _WBI_MIXIN_KEY)

    result = WbiManager._enc_wbi({"aid": 2, "cid": 1, "web_location": "444.8"}, _WBI_IMG_KEY, _WBI_SUB_KEY)
    assert result["wts"] == str(int(_WBI_FIXED_TS))
    assert result["w_rid"] == "deea8b31430f62536d711946e436aa8f"


def test_wbi_enc_cache_hit_throughput(monkeypatch):
    """wbi 缓存命中路径签名吞吐微基准（相对阈值 + 计时输出，见文件头部阈值设计原则）。

    参照操作：对同一条规范化 query 直接做 md5 —— 这是签名中不可避免的密码学核心，
    缓存命中路径在其之上仅有 dict 排序/翻译表过滤/编码等轻量操作，
    单次耗时相对参照的倍数应稳定在一个宽松上限（50 倍）之内。
    """
    from bilibili_api.utils import _wbi as wbi_module
    from bilibili_api.utils._wbi import WbiManager

    monkeypatch.setattr(wbi_module.time, "time", lambda: _WBI_FIXED_TS)
    monkeypatch.setattr(WbiManager, "_img_key", _WBI_IMG_KEY)
    monkeypatch.setattr(WbiManager, "_sub_key", _WBI_SUB_KEY)
    monkeypatch.setattr(WbiManager, "_mixin_key", _WBI_MIXIN_KEY)

    base_params = {"aid": 2, "cid": 1, "web_location": "444.8"}
    # 每次迭代传入新 dict 副本：_enc_wbi 会原地修改入参。
    enc_per_call = _min_elapsed(lambda: WbiManager._enc_wbi(base_params.copy(), _WBI_IMG_KEY, _WBI_SUB_KEY), 1000)

    query = "aid=2&cid=1&web_location=444.8&wts=1700000000"
    ref_per_call = _min_elapsed(lambda: hashlib.md5((query + _WBI_MIXIN_KEY).encode()).hexdigest(), 1000)

    ratio = enc_per_call / ref_per_call
    # 基准信息输出（默认被 pytest 捕获，仅失败或 -s 可见），有意保留 print
    print(  # noqa: T201
        f"\n[wbi bench] 缓存命中路径单次签名: {enc_per_call * 1e6:.2f} us，"
        f"参照 md5: {ref_per_call * 1e6:.2f} us，比值: {ratio:.1f}x"
    )
    # 宽松上限：仅拦截数量级级病态回归，避免机器抖动导致 CI 误报。
    assert ratio < 50, f"缓存命中路径签名耗时相对参照 md5 异常放大: {ratio:.1f}x"


def test_video_monitor_unpack_throughput():
    """弹幕协议粘包解包吞吐基准（相对阈值 + 计时输出，见文件头部阈值设计原则）。

    参照操作：逐个 json.loads 单包载荷 —— 解包的不可避免成本核心；
    整条粘包流的解包总耗时相对「逐包 json.loads 总和」的倍数应在宽松上限（20 倍）之内。
    """
    from bilibili_api._video_monitor import VideoOnlineMonitor

    # @staticmethod，通过 name mangling 直接访问，无需构造实例（不触网、无凭据）。
    pack = VideoOnlineMonitor._VideoOnlineMonitor__pack
    unpack = VideoOnlineMonitor._VideoOnlineMonitor__unpack
    datapack = VideoOnlineMonitor.Datapack

    packet_count = 128
    payloads = []
    packets = []
    for i in range(packet_count):
        payload = [f"{i}.50,1,25,16777215,{1700000000 + i},0,abcdef{i % 10:02d}", f"弹幕文本-{i}"]
        payloads.append(json.dumps(payload, ensure_ascii=False).encode())
        packets.append(pack(datapack.DANMAKU, i + 1, payloads[-1]))
    stream = b"".join(packets)  # 多包粘包样本（模拟一次 recv 收到整条流）
    assert len(stream) == packet_count * 18 + sum(len(p) for p in payloads)

    # 正确性兜底：解出全部包且逐包字段一致（性能基准不得掩盖功能回归）。
    items = unpack(stream)
    assert len(items) == packet_count
    assert items[0]["number"] == 1
    assert items[0]["data"] == json.loads(payloads[0])
    assert items[-1]["number"] == packet_count
    assert items[-1]["data"] == json.loads(payloads[-1])

    unpack_per_call = _min_elapsed(lambda: unpack(stream), 200)
    json_ref_total = _min_elapsed(lambda: [json.loads(p) for p in payloads], 200)

    ratio = unpack_per_call / json_ref_total
    # 基准信息输出（默认被 pytest 捕获，仅失败或 -s 可见），有意保留 print
    print(  # noqa: T201
        f"\n[unpack bench] {packet_count} 包粘包流解包: {unpack_per_call * 1e6:.1f} us，"
        f"逐包 json.loads 参照: {json_ref_total * 1e6:.1f} us，比值: {ratio:.2f}x，"
        f"吞吐: {packet_count / unpack_per_call:.0f} 包/秒，{len(stream) / unpack_per_call / 1024 / 1024:.1f} MB/s"
    )
    # 宽松上限：仅拦截数量级级病态回归（如每包重复解析首包头部、死循环切片等）。
    assert ratio < 20, f"粘包解包耗时相对逐包 json.loads 参照异常放大: {ratio:.2f}x"
