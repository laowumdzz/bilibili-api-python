"""
bilibili_api.exceptions.DanmakuClosedException

弹幕功能已关闭时抛出（如发送弹幕接口返回弹幕被关闭）。

历史上承载 DanmakuClosedException 类定义，重构并入 _simple.py 后本模块仅为兼容历史子模块
导入路径的薄层：仅 re-export 同一类对象（与包级导出为同一对象），不含任何
类定义。
"""

from ._simple import DanmakuClosedException as DanmakuClosedException

__all__ = ["DanmakuClosedException"]
