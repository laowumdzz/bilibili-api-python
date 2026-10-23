"""
bilibili_api.exceptions.CredentialNoBuvid3Exception

凭据缺少有效的 buvid3（设备指纹）时抛出。

历史上承载 CredentialNoBuvid3Exception 类定义，重构并入 _simple.py 后本模块仅为兼容历史子模块
导入路径的薄层：仅 re-export 同一类对象（与包级导出为同一对象），不含任何
类定义。
"""

from ._simple import CredentialNoBuvid3Exception as CredentialNoBuvid3Exception

__all__ = ["CredentialNoBuvid3Exception"]
