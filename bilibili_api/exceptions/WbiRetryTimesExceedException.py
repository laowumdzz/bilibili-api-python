"""
bilibili_api.exceptions.WbiRetryTimesExceedException

WBI 签名校验失败重试次数超过上限时抛出。

历史上承载 WbiRetryTimesExceedException 类定义，重构并入 _simple.py 后本模块仅为兼容历史子模块
导入路径的薄层：仅 re-export 同一类对象（与包级导出为同一对象），不含任何
类定义。
"""

from ._simple import WbiRetryTimesExceedException as WbiRetryTimesExceedException

__all__ = ["WbiRetryTimesExceedException"]
