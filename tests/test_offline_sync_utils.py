# bilibili_api.utils.sync 离线单元测试（补充缺口）
#
# 本文件属于无凭据快速路径：全部用例均为纯本地逻辑验证，
# 不触碰网络、不读取 BILI_* 环境变量、不依赖真实账号。
# 基础的“无循环返回结果 / 循环复用 / 运行中循环走线程池”用例已在
# test_offline_session_lifecycle.py 覆盖，此处仅补缺口：
# ConcurrentFuture 支持、异常传播。

from concurrent.futures import Future as ConcurrentFuture
import sys
import threading

import pytest

from bilibili_api.utils.sync import sync


async def _fail_coro() -> int:
    """抛出异常的测试协程。"""
    raise ValueError("sync 应传播协程内部异常")


@pytest.mark.skipif(
    sys.version_info >= (3, 14),
    reason="Python 3.14 起 asyncio 不再接受 concurrent.futures.Future（sync 包装器已知兼容性问题，已在任务报告记录）",
)
def test_sync_accepts_concurrent_future():
    """sync 应支持 concurrent.futures.Future（无运行中循环场景）。"""
    future: ConcurrentFuture = ConcurrentFuture()
    future.set_result(2024)

    def worker(results: list) -> None:
        results.append(sync(future))

    results: list = []
    thread = threading.Thread(target=worker, args=(results,))
    thread.start()
    thread.join()
    assert results == [2024]


def test_sync_propagates_exception_without_running_loop():
    """无运行中循环时，协程内部异常应原样抛出。"""

    errors: list = []

    def worker() -> None:
        try:
            sync(_fail_coro())
        except ValueError as e:
            errors.append(e)

    thread = threading.Thread(target=worker)
    thread.start()
    thread.join()
    assert len(errors) == 1
    assert str(errors[0]) == "sync 应传播协程内部异常"


async def test_sync_propagates_exception_inside_running_loop():
    """有运行中循环时，协程内部异常同样应原样抛出。"""
    with pytest.raises(ValueError, match="sync 应传播协程内部异常"):
        sync(_fail_coro())
