"""
bilibili_api.exceptions.CredentialNoBiliJctException

凭据缺少有效的 bili_jct（csrf token）时抛出，写操作均需要该字段。

历史上承载 CredentialNoBiliJctException 类定义，重构并入 _simple.py 后本模块仅为兼容历史子模块
导入路径的薄层：仅 re-export 同一类对象（与包级导出为同一对象），不含任何
类定义。
"""

from ._simple import CredentialNoBiliJctException as CredentialNoBiliJctException

__all__ = ["CredentialNoBiliJctException"]
