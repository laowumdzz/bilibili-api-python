"""
bilibili_api.utils.sync

同步执行异步函数
"""

import asyncio
from asyncio.futures import Future as AsyncioFuture
from collections.abc import Coroutine
from concurrent.futures import Future as ConcurrentFuture
from concurrent.futures import ThreadPoolExecutor
from typing import Any, TypeVar

T = TypeVar("T")


def __ensure_event_loop() -> asyncio.AbstractEventLoop:
    """
    确保当前线程有可用的事件循环。

    存在运行中的循环时直接返回；否则复用当前线程已绑定的事件循环，
    无绑定时以 `new_event_loop()` + `set_event_loop()` 新建并绑定，
    保持“无循环时新建、有运行中循环则复用”的原语义。
    探测优先走 `get_running_loop()`，仅在无运行中循环时才回退到 `get_event_loop()`
    复用已绑定循环（保留其复用语义），其异常创建行为改由显式新建替代。

    Returns:
        asyncio.AbstractEventLoop: 当前可用的事件循环。
    """
    try:
        return asyncio.get_running_loop()
    except RuntimeError:
        pass
    try:
        return asyncio.get_event_loop()
    except Exception:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop


def sync(coroutine: Coroutine[Any, Any, T] | AsyncioFuture | ConcurrentFuture) -> T:
    """
    同步执行异步函数，使用可参考 [同步执行异步代码](https://nemo2011.github.io/bilibili-api/#/sync-executor)

    Args:
        obj (Coroutine | Future): 异步函数

    Returns:
        Any: 该异步函数的返回值
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return __ensure_event_loop().run_until_complete(coroutine)
    else:
        with ThreadPoolExecutor() as executor:
            return executor.submit(lambda x: __ensure_event_loop().run_until_complete(x), coroutine).result()
