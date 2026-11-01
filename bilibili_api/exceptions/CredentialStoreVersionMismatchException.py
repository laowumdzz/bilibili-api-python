"""
bilibili_api.exceptions.CredentialStoreVersionMismatchException

凭据存储 schema 版本与当前实现不匹配时抛出。
"""

from __future__ import annotations

from .CredentialStoreException import CredentialStoreException


class CredentialStoreVersionMismatchException(CredentialStoreException):
    """
    凭据存储 schema 版本不匹配异常。

    库文件中的 schema 版本高于或低于当前实现支持的版本时抛出（明确失败
    优于静默兼容），消息包含双方版本号与升级提示，不包含任何凭据字段值。
    """

    def __init__(self, msg: str = "凭据存储 schema 版本与当前实现不匹配，请使用匹配版本的程序处理该库文件。") -> None:
        """
        构造凭据存储 schema 版本不匹配异常。

        Args:
            msg (str, optional): 异常消息；应包含双方版本号与升级提示，
                不包含任何凭据字段值. Defaults to 通用提示。
        """
        super().__init__(msg)
        self.msg = msg
