"""
bilibili_api.exceptions.ResponseException

请求响应不符合预期时抛出（如无法解析响应内容）。

历史上承载 ResponseException 类定义，重构并入 _simple.py 后本模块仅为兼容历史子模块
导入路径的薄层：仅 re-export 同一类对象（与包级导出为同一对象），不含任何
类定义。
"""

from ._simple import ResponseException as ResponseException

__all__ = ["ResponseException"]
