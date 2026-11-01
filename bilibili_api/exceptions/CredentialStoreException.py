"""
bilibili_api.exceptions.CredentialStoreException

凭据存储管理器异常基类：存储模块各类异常（库损坏 / 版本不匹配等）的共同父类。
"""

from __future__ import annotations

from .ApiException import ApiException


class CredentialStoreException(ApiException):
    """
    凭据存储模块异常基类。

    凭据存储管理器（如 SQLiteCredentialStoreManager）抛出的存储层异常均继承
    本类，调用方可据此统一捕获存储相关错误。异常消息只包含文件路径与原因
    类别，不包含任何凭据字段值。
    """

    def __init__(self, msg: str = "凭据存储出现了错误，但是未说明具体原因。") -> None:
        """
        构造凭据存储异常。

        Args:
            msg (str, optional): 异常消息；只应包含文件路径与原因类别，
                不包含任何凭据字段值. Defaults to 通用提示。
        """
        super().__init__(msg)
        self.msg = msg
