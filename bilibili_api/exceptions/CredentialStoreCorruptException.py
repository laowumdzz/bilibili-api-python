"""
bilibili_api.exceptions.CredentialStoreCorruptException

凭据存储库损坏或不可读时抛出（库文件损坏 / 解密失败 / 密钥丢失或损坏）。
"""

from __future__ import annotations

from .CredentialStoreException import CredentialStoreException


class CredentialStoreCorruptException(CredentialStoreException):
    """
    凭据存储库损坏异常。

    语义统一为"存量数据不可读，需重新添加账号"，涵盖：数据库文件损坏 /
    截断 / 非本库格式、记录解密或认证失败、密钥文件丢失或损坏。
    抛出后不静默清空或重建存量数据；异常消息只包含文件路径与原因类别，
    不包含任何凭据字段值。
    """

    def __init__(self, msg: str = "凭据存储库损坏或密钥不可用：存量数据不可读，需重新添加账号。") -> None:
        """
        构造凭据存储库损坏异常。

        Args:
            msg (str, optional): 异常消息；只应包含文件路径与原因类别，
                不包含任何凭据字段值. Defaults to 通用提示。
        """
        super().__init__(msg)
        self.msg = msg
