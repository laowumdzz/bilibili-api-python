# bilibili_api 离线单元测试：客户端注册池生命周期与 sync 事件循环行为回归
#
# 本文件属于无凭据快速路径：全部用例均为纯本地逻辑验证，
# 不触碰网络、不读取 BILI_* 环境变量、不依赖真实账号。

import asyncio
import gc
import threading

import pytest

from bilibili_api.exceptions import ArgsException
from bilibili_api.utils import _session
from bilibili_api.utils._session import BiliAPIClient, register_client, unregister_client
from bilibili_api.utils.sync import sync

# 创建-销毁事件循环的模拟次数：池内条目数不得单调增长
LOOP_CHURN_TIMES = 8


class _FakeClient(BiliAPIClient):
    """仅用于注册/注销流程验证的假客户端，全部方法为空实现。"""

    def __init__(self, proxy="", timeout=0.0, verify_ssl=True, trust_env=True, session=None) -> None:
        self._session = session

    def get_wrapped_session(self) -> object:
        return self._session

    def set_timeout(self, timeout: float = 0.0) -> None:
        pass

    def set_proxy(self, proxy: str = "") -> None:
        pass

    def set_verify_ssl(self, verify_ssl: bool = True) -> None:
        pass

    def set_trust_env(self, trust_env: bool = True) -> None:
        pass

    async def request(self, **kwargs) -> None:
        raise NotImplementedError

    async def download_create(self, url: str = "", headers: dict = {}) -> int:
        raise NotImplementedError

    async def download_chunk(self, cnt: int) -> bytes:
        raise NotImplementedError

    def download_content_length(self, cnt: int) -> int:
        return 0

    async def download_close(self, cnt: int) -> None:
        pass

    async def ws_create(self, url: str = "", params: dict = {}, headers: dict = {}) -> int:
        raise NotImplementedError

    async def ws_send(self, cnt: int, data: bytes) -> None:
        pass

    async def ws_recv(self, cnt: int):
        raise NotImplementedError

    async def ws_close(self, cnt: int) -> None:
        pass

    async def close(self):
        pass


def test_session_pool_does_not_leak_across_destroyed_loops():
    """反复创建-销毁事件循环后，session_pool 条目数不得增长（弱引用键自动清理）。"""
    pool = _session.session_pool["aiohttp"]
    baseline = len(pool)
    for _ in range(LOOP_CHURN_TIMES):
        loop = asyncio.new_event_loop()
        pool[loop] = object()
        del loop
        gc.collect()
    assert len(pool) == baseline


def test_lazy_settings_does_not_leak_across_destroyed_loops():
    """反复创建-销毁事件循环后，lazy_settings 条目数不得增长（弱引用键自动清理）。"""
    settings = _session.lazy_settings["aiohttp"]
    baseline = len(settings)
    for _ in range(LOOP_CHURN_TIMES):
        loop = asyncio.new_event_loop()
        settings[loop] = {}
        del loop
        gc.collect()
    assert len(settings) == baseline


def test_session_pool_reuses_same_loop_entry():
    """同一事件循环对象多次写入同一键时仅保留一个条目（复用语义不变）。"""
    pool = _session.session_pool["aiohttp"]
    loop = asyncio.new_event_loop()
    try:
        baseline = len(pool)
        pool[loop] = object()
        pool[loop] = object()
        assert len(pool) == baseline + 1
    finally:
        pool.pop(loop, None)


def test_unregister_client_cleans_all_registries():
    """unregister_client 应同步清理 sessions / session_pool / client_settings / lazy_settings。"""
    name = "offline_fake_client"
    register_client(name, _FakeClient)
    assert name in _session.sessions
    assert name in _session.session_pool
    assert name in _session.client_settings
    assert name in _session.lazy_settings

    unregister_client(name)

    assert name not in _session.sessions
    assert name not in _session.session_pool
    assert name not in _session.client_settings, "注销后不应遗留 client_settings 条目"
    assert name not in _session.lazy_settings, "注销后不应遗留 lazy_settings 条目"


def test_unregister_client_unknown_raises():
    """注销未注册的客户端应抛出 ArgsException。"""
    with pytest.raises(ArgsException):
        unregister_client("offline_never_registered_client")


async def _get_loop_id() -> int:
    """返回当前运行中事件循环的 id，用于验证循环复用。"""
    return id(asyncio.get_running_loop())


async def _get_value() -> int:
    return 42


def test_sync_returns_result_without_running_loop():
    """无运行中循环时，sync 应新建/复用循环并返回协程结果。"""

    def worker(results: list) -> None:
        results.append(sync(_get_value()))

    results: list = []
    thread = threading.Thread(target=worker, args=(results,))
    thread.start()
    thread.join()
    assert results == [42]


def test_sync_reuses_thread_bound_loop():
    """无循环线程首次调用新建循环后，后续调用应复用同一循环（不跨循环复用对象）。"""

    def worker(loop_ids: list) -> None:
        loop_ids.append(sync(_get_loop_id()))
        loop_ids.append(sync(_get_loop_id()))

    loop_ids: list = []
    thread = threading.Thread(target=worker, args=(loop_ids,))
    thread.start()
    thread.join()
    assert loop_ids[0] == loop_ids[1], "同一线程内连续调用应复用同一事件循环"


async def test_sync_inside_running_loop():
    """有运行中循环时调用 sync，应通过线程池执行并返回结果（既有语义）。"""
    assert sync(_get_value()) == 42
