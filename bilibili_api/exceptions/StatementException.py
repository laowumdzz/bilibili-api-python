"""
bilibili_api.exceptions.StatementException

API 定义语句（data/api/*.json）错误时抛出。

历史上承载 StatementException 类定义，重构并入 _simple.py 后本模块仅为兼容历史子模块
导入路径的薄层：仅 re-export 同一类对象（与包级导出为同一对象），不含任何
类定义。
"""

from ._simple import StatementException as StatementException

__all__ = ["StatementException"]
