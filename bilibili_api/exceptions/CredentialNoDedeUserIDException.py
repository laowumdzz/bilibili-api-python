"""
bilibili_api.exceptions.CredentialNoDedeUserIDException

凭据缺少有效的 dedeuserid（当前登录用户 ID）时抛出。

历史上承载 CredentialNoDedeUserIDException 类定义，重构并入 _simple.py 后本模块仅为兼容历史子模块
导入路径的薄层：仅 re-export 同一类对象（与包级导出为同一对象），不含任何
类定义。
"""

from ._simple import CredentialNoDedeUserIDException as CredentialNoDedeUserIDException

__all__ = ["CredentialNoDedeUserIDException"]
