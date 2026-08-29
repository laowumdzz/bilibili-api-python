"""
bilibili_api.utils.cache_pool — 缓存池。

提供轻量级 TTL + LRU 缓存工具（TTLCache / cached_async），
以及 article ↔ dynamic 等映射的模块级缓存（均为有界 TTLCache）。
"""

import asyncio
from collections import OrderedDict
from collections.abc import Callable
from functools import wraps
import time
from typing import Any


class TTLCache:
    """
    轻量级 TTL + LRU 缓存。

    非线程安全，适用于单事件循环/单线程场景（本库的典型使用方式）。
    命中时会把条目移到队尾（最近使用），超出 maxsize 时淘汰最久未使用的条目。

    Args:
        maxsize (int): 最大条目数. Defaults to 1024.
        ttl (float): 条目有效期（秒），<= 0 表示永不过期. Defaults to 3600.0.
    """

    def __init__(self, maxsize: int = 1024, ttl: float = 3600.0):
        self.__maxsize = maxsize
        self.__ttl = ttl
        self.__data: OrderedDict[Any, tuple[float, Any]] = OrderedDict()

    def get(self, key: Any) -> Any:
        """
        获取缓存值，未命中或已过期时返回 None 并清理过期条目。

        Args:
            key (Any): 缓存键

        Returns:
            Any: 缓存值；未命中返回 None。
        """
        item = self.__data.get(key)
        if item is None:
            return None
        expires, value = item
        if self.__ttl > 0 and time.monotonic() > expires:
            del self.__data[key]
            return None
        self.__data.move_to_end(key)
        return value

    def set(self, key: Any, value: Any) -> None:
        """
        写入缓存值，超出 maxsize 时淘汰最久未使用的条目。

        Args:
            key   (Any): 缓存键
            value (Any): 缓存值
        """
        expires = time.monotonic() + self.__ttl if self.__ttl > 0 else float("inf")
        self.__data[key] = (expires, value)
        self.__data.move_to_end(key)
        while len(self.__data) > self.__maxsize:
            self.__data.popitem(last=False)

    def invalidate(self, key: Any) -> None:
        """
        删除指定缓存条目。

        Args:
            key (Any): 缓存键
        """
        self.__data.pop(key, None)

    def clear(self) -> None:
        """清空全部缓存。"""
        self.__data.clear()

    def __contains__(self, key: Any) -> bool:
        return self.get(key) is not None

    def __len__(self) -> int:
        return len(self.__data)


def _make_hashable(value: Any) -> Any:
    """
    把常见的不可哈希结构（dict/list/set）递归转换为可哈希结构，用于构造缓存键。

    Args:
        value (Any): 任意值

    Returns:
        Any: 可哈希的等价结构
    """
    if isinstance(value, dict):
        return tuple(sorted((k, _make_hashable(v)) for k, v in value.items()))
    if isinstance(value, (list, tuple)):
        return tuple(_make_hashable(v) for v in value)
    if isinstance(value, (set, frozenset)):
        return frozenset(_make_hashable(v) for v in value)
    return value


def cached_async(ttl: float = 300.0, maxsize: int = 256) -> Callable:
    """
    为无副作用的异步函数提供 opt-in 的 TTL + LRU 结果缓存装饰器。

    缓存键由函数的位置参数与关键字参数构造，仅适用于只读查询类函数，
    严禁用于会改变账号/服务端状态的写操作接口。

    具备并发单飞（single-flight）语义：缓存未命中时，同一缓存键的并发调用
    共享同一个 in-flight 任务，底层函数仅实际执行一次；任务失败时不写入缓存，
    异常传播给所有等待者，且下一次调用会重新执行。
    in-flight 表随装饰器闭包持有（每个被装饰函数独立），与 TTLCache 相同，
    非线程安全，适用于单事件循环场景，不引入额外锁。

    Args:
        ttl (float): 缓存有效期（秒）. Defaults to 300.0.
        maxsize (int): 最大缓存条目数. Defaults to 256.

    Returns:
        Callable: 装饰器。被装饰函数的返回值可通过 `func.cache` 访问其 TTLCache。
    """

    def decorator(func: Callable) -> Callable:
        cache = TTLCache(maxsize=maxsize, ttl=ttl)
        # 每个缓存键对应的 in-flight 任务，用于并发单飞去重。
        in_flight: dict[Any, asyncio.Task[Any]] = {}

        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            key = (_make_hashable(args), _make_hashable(kwargs))
            result = cache.get(key)
            if result is not None:
                return result
            task = in_flight.get(key)
            if task is not None:
                # 已有同键任务在执行：直接共享其结果（或异常）
                return await task
            task = asyncio.get_running_loop().create_task(func(*args, **kwargs))
            in_flight[key] = task
            try:
                result = await task
            finally:
                # 无论成功还是失败，均从 in-flight 表移除（失败不缓存，下次重新执行）
                in_flight.pop(key, None)
            if result is not None:
                cache.set(key, result)
            return result

        wrapper.cache = cache  # type: ignore[attr-defined]
        return wrapper

    return decorator


# article ↔ dynamic 等映射的模块级缓存：均为有界（4096 条）+ 1 小时 TTL，
# 避免长期运行单调增长。访问统一走 TTLCache 的 get()/set()/invalidate() 接口。
article2dynamic: TTLCache = TTLCache(maxsize=4096, ttl=3600.0)
dynamic2article: TTLCache = TTLCache(maxsize=4096, ttl=3600.0)
article_is_note: TTLCache = TTLCache(maxsize=4096, ttl=3600.0)
dynamic_is_article: TTLCache = TTLCache(maxsize=4096, ttl=3600.0)
dynamic_is_opus: TTLCache = TTLCache(maxsize=4096, ttl=3600.0)
