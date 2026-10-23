"""
bilibili_api.exceptions.GeetestException

极验验证码处理出错时抛出（如验证失败、服务不可用）。

历史上承载 GeetestException 类定义，重构并入 _simple.py 后本模块仅为兼容历史子模块
导入路径的薄层：仅 re-export 同一类对象（与包级导出为同一对象），不含任何
类定义。
"""

from ._simple import GeetestException as GeetestException

__all__ = ["GeetestException"]
