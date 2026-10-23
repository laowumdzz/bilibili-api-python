"""
bilibili_api.exceptions.ArgsException

调用参数错误时抛出（如缺少必要参数、参数组合不合法）。

历史上承载 ArgsException 类定义，重构并入 _simple.py 后本模块仅为兼容历史子模块
导入路径的薄层：仅 re-export 同一类对象（与包级导出为同一对象），不含任何
类定义。
"""

from ._simple import ArgsException as ArgsException

__all__ = ["ArgsException"]
