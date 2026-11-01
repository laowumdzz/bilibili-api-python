from __future__ import annotations

from abc import ABC, abstractmethod
import asyncio
from typing import ClassVar

from typing_extensions import Self

from ._credential import Credential  # 直接取源定义：避免经 login_v2 急切加载惰性子模块（test_package_import_is_lazy）


class BaseCredentialStoreManager(ABC):
    """
    凭据存储管理器基类
    单例模式: 每个具体子类各有一个单例
    注意: 实例与事件循环绑定，请在同一 loop 内使用。
    """

    _instance: ClassVar[BaseCredentialStoreManager | None] = None

    def __new__(cls) -> Self:
        instance = cls.__dict__.get("_instance")
        if instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance  # type: ignore[return-value]

    def __init__(self) -> None:
        """
        初始化管理器
        """
        if getattr(self, "_ready", False):
            return
        self._setup_once()
        self._ready = True

    @classmethod
    @abstractmethod
    async def read_data(cls) -> dict[int, Credential]:
        """
        读出所有持久化数据凭证并实例化管理器返回
        不验证凭证是否过期或可用,只读
        """

    async def add_credential(self, uid: int, credential: Credential, auto_persist: bool = True) -> bool:
        """
        添加或覆盖一条凭据。

        Args:
            uid: 用户 ID, 须与 credential.dedeuserid 一致。
            credential: 凭据实例。
            auto_persist: 是否自动持久化。

        Returns:
            bool: True 为新 uid, False 为覆盖了同 uid 的旧记录。

        Raises:
            ValueError: uid 与 credential.dedeuserid 不一致。
        """
        dedeuserid = credential.dedeuserid
        if not dedeuserid:
            raise ValueError("credential 缺少 dedeuserid")
        if dedeuserid != str(uid):
            raise ValueError(f"uid({uid}) 与 dedeuserid({dedeuserid}) 不一致")

        async with self._lock:
            is_new = uid not in self._credentials
            self._credentials[uid] = credential.model_copy(deep=True)
        if auto_persist:
            await self._persist()
        return is_new

    async def get_credential(self, uid: int | None = None) -> Credential | None:
        """
        取出凭据。

        Args:
            uid: 用户 ID; 为 None 时取插入顺序的第一条

        Returns:
            Credential | None: 命中记录；无命中或管理器为空时为 None。
        """
        async with self._lock:
            result = self._credentials.get(uid) if uid is not None else next(iter(self._credentials.values()), None)
            return None if result is None else result.model_copy(deep=True)

    async def remove_credential(self, uid: int, auto_persist: bool = True) -> bool:
        """
        移除凭据。

        Args:
            uid: 用户 ID。
            auto_persist: 是否自动持久化。

        Returns:
            bool: 是否移除成功。
        """
        async with self._lock:
            if uid not in self._credentials:
                return False
            del self._credentials[uid]
        if auto_persist:
            await self._persist()
        return True

    @abstractmethod
    async def store_data(self, credentials: dict[int, Credential]) -> None:
        """持久化给定快照；失败抛异常。"""

    def _setup_once(self) -> None:
        self._credentials: dict[int, Credential] = {}
        self._lock = asyncio.Lock()
        self._persist_lock = asyncio.Lock()

    @classmethod
    async def load(cls) -> Self:
        inst = cls()
        data = await cls.read_data()
        async with inst._lock:
            inst._credentials = dict(data)
        return inst

    async def _snapshot(self) -> dict[int, Credential]:
        async with self._lock:
            return {k: v.model_copy(deep=True) for k, v in self._credentials.items()}

    async def _persist(self) -> None:
        async with self._persist_lock:
            await self.store_data(await self._snapshot())

    def __len__(self) -> int:
        return len(self._credentials)

    async def get_all_uids(self) -> list[int]:
        async with self._lock:
            return list(self._credentials)
