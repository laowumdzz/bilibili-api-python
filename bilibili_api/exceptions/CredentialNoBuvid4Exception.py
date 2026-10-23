"""
bilibili_api.exceptions.CredentialNoBuvid4Exception

凭据缺少有效的 buvid4（设备指纹）时抛出。

历史上承载 CredentialNoBuvid4Exception 类定义，重构并入 _simple.py 后本模块仅为兼容历史子模块
导入路径的薄层：仅 re-export 同一类对象（与包级导出为同一对象），不含任何
类定义。
"""

from ._simple import CredentialNoBuvid4Exception as CredentialNoBuvid4Exception

__all__ = ["CredentialNoBuvid4Exception"]
