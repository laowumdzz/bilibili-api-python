"""
bilibili_api.exceptions.CredentialNoSessdataException

凭据缺少有效的 sessdata（登录会话）时抛出，登录态操作均需要该字段。

历史上承载 CredentialNoSessdataException 类定义，重构并入 _simple.py 后本模块仅为兼容历史子模块
导入路径的薄层：仅 re-export 同一类对象（与包级导出为同一对象），不含任何
类定义。
"""

from ._simple import CredentialNoSessdataException as CredentialNoSessdataException

__all__ = ["CredentialNoSessdataException"]
