"""
bilibili_api.exceptions.InitialStateException

未能从页面获取到初始状态（__initial_state）时抛出。

历史上承载 InitialStateException 类定义，重构并入 _simple.py 后本模块仅为兼容历史子模块
导入路径的薄层：仅 re-export 同一类对象（与包级导出为同一对象），不含任何
类定义。
"""

from ._simple import InitialStateException as InitialStateException

__all__ = ["InitialStateException"]
