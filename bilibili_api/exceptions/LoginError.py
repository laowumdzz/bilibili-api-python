"""
bilibili_api.exceptions.LoginError

登录流程出错时抛出（如密码错误、二维码过期、短信验证失败）。

历史上承载 LoginError 类定义，重构并入 _simple.py 后本模块仅为兼容历史子模块
导入路径的薄层：仅 re-export 同一类对象（与包级导出为同一对象），不含任何
类定义。
"""

from ._simple import LoginError as LoginError

__all__ = ["LoginError"]
