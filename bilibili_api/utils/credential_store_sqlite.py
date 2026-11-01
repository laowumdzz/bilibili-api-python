"""
bilibili_api.utils.credential_store_sqlite

基于 aiosqlite 的凭据存储管理器实现。

凭据按 UID 落盘单文件 SQLite 数据库，插入顺序跨进程保持；默认位置经
platformdirs 解析为 OS 标准应用数据目录，路径可显式覆盖。每个具体子类
单例（继承基类语义），连接惰性创建并绑定首次使用的事件循环。
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path
import sqlite3

import aiosqlite
from Cryptodome.Cipher import AES, PKCS1_OAEP
from Cryptodome.Hash import SHA256
from Cryptodome.PublicKey import RSA
from Cryptodome.Random import get_random_bytes
import platformdirs
from typing_extensions import Self

from ..exceptions import (
    ArgsException,
    CredentialStoreCorruptException,
    CredentialStoreVersionMismatchException,
)
from ._credential import Credential
from .credential_store import BaseCredentialStoreManager

# 默认存储目录与文件名（research.md D4）
_DEFAULT_APP_DIR_NAME = "bilibili-api"
_DEFAULT_DB_FILENAME = "credentials.db"
_DEFAULT_KEY_FILENAME = "credentials.key"

# 库标识与 schema 版本（research.md D3 / data-model.md meta 表）
_STORE_FORMAT = "bilibili-api-credential-store"
_SCHEMA_VERSION = "1"

# 加密 BLOB 布局常量（research.md D2 / data-model.md）：
# BLOB = 魔数(4B) + nonce(12B) + RSA 封装的一次性 AES-256 数据密钥 + 密文 + GCM tag(16B)
_BLOB_MAGIC = b"BACS"
_NONCE_BYTES = 12
_TAG_BYTES = 16
_DEK_BYTES = 32
_RSA_KEY_BITS = 2048

logger = logging.getLogger(__name__)


class SQLiteCredentialStoreManager(BaseCredentialStoreManager):
    """
    基于 aiosqlite 的凭据存储管理器。

    单例模式：每个具体子类各有一个实例（基类强制）。构造参数 db_path /
    key_path 仅在首次实例化时生效；后续以不同路径重复实例化将抛出
    ArgsException。实例与事件循环绑定：连接在首次数据库操作时惰性创建，
    之后跨事件循环使用会显式抛出 ArgsException。
    """

    def __new__(
        cls,
        db_path: str | Path | None = None,
        key_path: str | Path | None = None,
    ) -> Self:
        """
        创建或返回本子类的单例实例（路径参数交由 __init__ 处理）。

        Args:
            db_path (str | Path | None, optional): 数据库文件路径. Defaults to None.
            key_path (str | Path | None, optional): 密钥文件路径. Defaults to None.

        Returns:
            Self: 本子类的单例实例。
        """
        return super().__new__(cls)

    def __init__(
        self,
        db_path: str | Path | None = None,
        key_path: str | Path | None = None,
    ) -> None:
        """
        初始化管理器。

        首次实例化时解析并固定存储路径；后续实例化返回单例，传入与已配置
        不同的路径将抛出 ArgsException（防止调用方误以为新参数生效）。

        Args:
            db_path (str | Path | None, optional): 数据库文件路径；None 时取
                platformdirs 默认目录下的 credentials.db. Defaults to None.
            key_path (str | Path | None, optional): 密钥文件路径；None 时取
                数据库同目录下的 credentials.key. Defaults to None.

        Raises:
            ArgsException: 非首次实例化时传入了与已配置不同的路径。
        """
        first_init = not getattr(self, "_ready", False)
        super().__init__()
        if first_init:
            self._connection: aiosqlite.Connection | None = None
            self._connection_loop: asyncio.AbstractEventLoop | None = None
            self._connect_lock: asyncio.Lock = asyncio.Lock()
            self._closed: bool = False
            self._configured_db_path: Path = self._resolve_db_path(db_path)
            self._configured_key_path: Path = self._resolve_key_path(key_path)
        else:
            if db_path is not None and self._normalize_path(db_path) != self._configured_db_path:
                raise ArgsException(
                    f"凭据存储管理器为单例，已配置数据库路径 {self._configured_db_path}，"
                    f"不接受冲突路径 {self._normalize_path(db_path)}"
                )
            if key_path is not None and self._normalize_path(key_path) != self._configured_key_path:
                raise ArgsException(
                    f"凭据存储管理器为单例，已配置密钥路径 {self._configured_key_path}，"
                    f"不接受冲突路径 {self._normalize_path(key_path)}"
                )

    @property
    def db_path(self) -> Path:
        """
        实际生效的数据库文件路径（默认解析后的绝对路径）。

        Returns:
            Path: 数据库文件路径。
        """
        return self._configured_db_path

    @property
    def key_path(self) -> Path:
        """
        实际生效的密钥文件路径（默认解析后的绝对路径）。

        Returns:
            Path: 密钥文件路径。
        """
        return self._configured_key_path

    async def close(self) -> None:
        """
        显式关闭数据库连接（实现附加 API，基类无此方法；幂等）。

        关闭后实例不可再用于 IO，需重建实例（清除子类单例后重新构造）。

        Raises:
            ArgsException: 在与连接绑定的不同的其他事件循环中调用。
        """
        if self._closed:
            return
        if self._connection is not None:
            current_loop = asyncio.get_running_loop()
            if self._connection_loop is not current_loop:
                raise ArgsException("凭据存储管理器已绑定其他事件循环，无法在当前事件循环中关闭。")
            await self._connection.close()
            self._connection = None
            self._connection_loop = None
        self._closed = True

    @classmethod
    async def read_data(cls) -> dict[int, Credential]:
        """
        读出所有持久化数据凭证并实例化管理器返回。

        不验证凭证是否过期或可用，只读；记录按插入顺序（order_seq 升序）返回。
        经 cls() 取单例后复用实例连接与配置（research.md D8）。

        Returns:
            dict[int, Credential]: 全部持久化凭据，键为 uid，按插入顺序排列。
        """
        inst = cls()
        connection = await inst._open_database()
        cursor = await connection.execute("SELECT uid, order_seq, data_enc FROM credential ORDER BY order_seq")
        rows = await cursor.fetchall()
        await cursor.close()
        result: dict[int, Credential] = {}
        if rows:
            # 仅在存在记录时要求密钥：空库 / 首次使用视为新钥正常创建（契约 Edge Case，不报错）
            key = await inst._load_key(connection, generate_if_missing=False)
            for uid, _order_seq, data_enc in rows:
                result[int(uid)] = await inst._decode_record(data_enc, key)
        logger.info("凭据存储已加载 %d 条记录（%s）", len(result), inst.db_path)
        return result

    async def store_data(self, credentials: dict[int, Credential]) -> None:
        """
        持久化给定快照；失败抛异常。

        单事务内全量重写 credential 表：DELETE 后按内存快照顺序以
        MAX(order_seq)+1 重排 INSERT，并更新 meta（原子，FR-004）。失败时
        回滚事务，上一次落盘数据不受影响。

        Args:
            credentials (dict[int, Credential]): 内存态凭据快照，按插入顺序排列。
        """
        connection = await self._open_database()
        key = await self._load_key(connection, generate_if_missing=True)
        try:
            await connection.execute("DELETE FROM credential")
            order_seq = 0
            for uid, credential in credentials.items():
                order_seq += 1
                data_enc = await self._encode_record(credential, key)
                await connection.execute(
                    "INSERT INTO credential(uid, order_seq, data_enc) VALUES(?, ?, ?)",
                    (uid, order_seq, data_enc),
                )
            await connection.execute(
                "INSERT OR REPLACE INTO meta(key, value) VALUES('store_format', ?)",
                (_STORE_FORMAT,),
            )
            await connection.execute(
                "INSERT OR REPLACE INTO meta(key, value) VALUES('schema_version', ?)",
                (_SCHEMA_VERSION,),
            )
            await connection.commit()
        except Exception:
            await connection.rollback()
            raise
        logger.info("凭据存储已持久化 %d 条记录（%s）", len(credentials), self.db_path)

    async def add_credential(self, uid: int, credential: Credential, auto_persist: bool = True) -> bool:
        """
        添加或覆盖一条凭据（覆写基类以增加落盘失败回滚，FR-004）。

        校验、返回值与加锁语义与基类一致（FR-002）；auto_persist 落盘失败时
        回滚该 uid 的内存态（新增则回删、覆盖则还原旧值）后重抛原异常，
        保证内存态不受损。

        Args:
            uid (int): 用户 ID，须与 credential.dedeuserid 一致。
            credential (Credential): 凭据实例。
            auto_persist (bool, optional): 是否自动持久化. Defaults to True.

        Returns:
            bool: True 为新 uid，False 为覆盖了同 uid 的旧记录。

        Raises:
            ValueError: uid 与 credential.dedeuserid 不一致（基类校验，原样传播）。
            ArgsException: 跨事件循环使用实例。
        """
        self._ensure_same_loop()
        dedeuserid = credential.dedeuserid
        if not dedeuserid:
            raise ValueError("credential 缺少 dedeuserid")
        if dedeuserid != str(uid):
            raise ValueError(f"uid({uid}) 与 dedeuserid({dedeuserid}) 不一致")
        async with self._lock:
            had_old = uid in self._credentials
            old = self._credentials.get(uid)
            is_new = not had_old
            self._credentials[uid] = credential.model_copy(deep=True)
        if auto_persist:
            try:
                await self._persist()
            except Exception:
                async with self._lock:
                    if had_old and old is not None:
                        self._credentials[uid] = old
                    else:
                        self._credentials.pop(uid, None)
                raise
        logger.info("凭据存储已%s uid=%d（%s）", "覆盖" if not is_new else "添加", uid, self.db_path)
        return is_new

    async def remove_credential(self, uid: int, auto_persist: bool = True) -> bool:
        """
        移除凭据（覆写基类以增加落盘失败回滚，FR-004）。

        校验、返回值与加锁语义与基类一致（FR-002）；auto_persist 落盘失败时
        将该 uid 放回内存后重抛原异常，保证内存态不受损。

        Args:
            uid (int): 用户 ID。
            auto_persist (bool, optional): 是否自动持久化. Defaults to True.

        Returns:
            bool: 是否移除成功。

        Raises:
            ArgsException: 跨事件循环使用实例。
        """
        self._ensure_same_loop()
        async with self._lock:
            if uid not in self._credentials:
                return False
            removed = self._credentials.pop(uid)
        if auto_persist:
            try:
                await self._persist()
            except Exception:
                async with self._lock:
                    self._credentials[uid] = removed
                raise
        logger.info("凭据存储已移除 uid=%d（%s）", uid, self.db_path)
        return True

    async def _open_database(self) -> aiosqlite.Connection:
        """
        打开数据库并完成打开期校验（建表、meta 校验、错误映射，FR-008 / FR-012）。

        Returns:
            aiosqlite.Connection: 完成打开期校验的数据库连接。

        Raises:
            CredentialStoreCorruptException: 库文件损坏 / 不可读 / 非本库格式。
            CredentialStoreVersionMismatchException: schema 版本不匹配。
        """
        connection = await self._get_connection()
        try:
            await self._ensure_schema(connection)
            await self._validate_meta(connection)
        except sqlite3.Error as exc:
            raise CredentialStoreCorruptException(
                self._corrupt_message(self.db_path, f"库文件损坏或不可读（{type(exc).__name__}）")
            ) from exc
        return connection

    async def _validate_meta(self, connection: aiosqlite.Connection) -> None:
        """
        校验 meta 元数据：库标识与 schema 版本（research.md D3）。

        Args:
            connection (aiosqlite.Connection): 已建表的数据库连接。

        Raises:
            CredentialStoreCorruptException: store_format 缺失或不符。
            CredentialStoreVersionMismatchException: schema_version 高于或
                低于当前实现支持的版本（v1 阶段对称处理）。
        """
        cursor = await connection.execute("SELECT key, value FROM meta")
        # sqlite3.Row 的类型 stub 不暴露元组解包形态，dict() 直接收敛会误报重载不匹配；
        # 按 (key, value) 二元对显式收敛（SELECT 列序即该顺序）。
        rows: dict[str, str] = {str(key): str(value) for key, value in await cursor.fetchall()}
        await cursor.close()
        store_format = rows.get("store_format")
        if store_format is None:
            raise CredentialStoreCorruptException(self._corrupt_message(self.db_path, "库标识缺失"))
        if store_format != _STORE_FORMAT:
            raise CredentialStoreCorruptException(self._corrupt_message(self.db_path, "非本库格式"))
        schema_version = rows.get("schema_version")
        if schema_version != _SCHEMA_VERSION:
            raise CredentialStoreVersionMismatchException(
                f"凭据存储 schema 版本不匹配（{self.db_path}）：库版本 {schema_version or '缺失'}，"
                f"当前程序支持版本 {_SCHEMA_VERSION}；请使用匹配版本的程序处理该库文件。"
            )

    def _ensure_same_loop(self) -> None:
        """
        校验当前事件循环与连接绑定的循环一致（提前于基类锁使用，research.md D7）。

        Raises:
            ArgsException: 实例已绑定其他事件循环。
        """
        if self._connection_loop is not None:
            current_loop = asyncio.get_running_loop()
            if self._connection_loop is not current_loop:
                raise ArgsException("凭据存储管理器实例与事件循环绑定，请在同一事件循环内使用。")

    async def _ensure_schema(self, connection: aiosqlite.Connection) -> None:
        """
        确保库表结构与元数据就绪（幂等）。

        首次连接时建表（IF NOT EXISTS）并写入 store_format / schema_version；
        已有 meta 行时不覆盖（防篡改场景被静默修复，校验见 T012）。

        Args:
            connection (aiosqlite.Connection): 数据库连接。
        """
        await connection.execute("CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        await connection.execute(
            "CREATE TABLE IF NOT EXISTS credential("
            "uid INTEGER PRIMARY KEY, "
            "order_seq INTEGER NOT NULL UNIQUE, "
            "data_enc BLOB NOT NULL)"
        )
        cursor = await connection.execute("SELECT value FROM meta WHERE key = 'store_format'")
        row = await cursor.fetchone()
        await cursor.close()
        if row is None:
            await connection.execute(
                "INSERT OR IGNORE INTO meta(key, value) VALUES('store_format', ?)",
                (_STORE_FORMAT,),
            )
            await connection.execute(
                "INSERT OR IGNORE INTO meta(key, value) VALUES('schema_version', ?)",
                (_SCHEMA_VERSION,),
            )
            await connection.commit()

    async def _encode_record(self, credential: Credential, key: RSA.RsaKey) -> bytes:
        """
        编码单条凭据为加密落盘 BLOB（research.md D2）。

        每记录随机生成一次性 AES-256 数据密钥，凭据 JSON 明文经 AES-256-GCM
        加密（随机 12 字节 nonce），数据密钥经 RSA-2048-OAEP(SHA-256) 封装。
        BLOB = 魔数 b"BACS" + nonce(12B) + wrapped DEK(256B) + 密文 + tag(16B)。

        Args:
            credential (Credential): 待编码凭据。
            key (RSA.RsaKey): RSA 密钥（用于封装数据密钥）。

        Returns:
            bytes: 加密落盘 BLOB。
        """
        plaintext = credential.model_dump_json().encode("utf-8")
        dek = get_random_bytes(_DEK_BYTES)
        nonce = get_random_bytes(_NONCE_BYTES)
        cipher = AES.new(dek, AES.MODE_GCM, nonce=nonce)
        ciphertext, tag = cipher.encrypt_and_digest(plaintext)
        wrapped_dek = PKCS1_OAEP.new(key, SHA256).encrypt(dek)
        return _BLOB_MAGIC + nonce + wrapped_dek + ciphertext + tag

    async def _decode_record(self, blob: bytes, key: RSA.RsaKey) -> Credential:
        """
        解码单条加密落盘 BLOB 为凭据。

        魔数不符 / 布局不符 / RSA 解封装失败 / GCM 认证失败 / JSON 解析失败
        均抛 CredentialStoreCorruptException（不静默读出坏数据）。不校验凭据
        是否过期或可用（基类契约，只读重建）。

        Args:
            blob (bytes): 加密落盘 BLOB。
            key (RSA.RsaKey): RSA 密钥（用于解封装数据密钥）。

        Returns:
            Credential: 重建的凭据实例。

        Raises:
            CredentialStoreCorruptException: 记录格式损坏或解密失败。
        """
        data = bytes(blob)
        header_len = len(_BLOB_MAGIC) + _NONCE_BYTES + key.size_in_bytes() + _TAG_BYTES
        if not data.startswith(_BLOB_MAGIC) or len(data) < header_len:
            raise CredentialStoreCorruptException(self._corrupt_message(self.db_path, "记录格式损坏或非本库格式"))
        offset = len(_BLOB_MAGIC)
        nonce = data[offset : offset + _NONCE_BYTES]
        offset += _NONCE_BYTES
        wrapped_dek = data[offset : offset + key.size_in_bytes()]
        offset += key.size_in_bytes()
        ciphertext = data[offset:-_TAG_BYTES]
        tag = data[-_TAG_BYTES:]
        try:
            dek = PKCS1_OAEP.new(key, SHA256).decrypt(wrapped_dek)
            cipher = AES.new(dek, AES.MODE_GCM, nonce=nonce)
            plaintext = cipher.decrypt_and_verify(ciphertext, tag)
        except ValueError as exc:
            raise CredentialStoreCorruptException(self._corrupt_message(self.db_path, "记录解密失败")) from exc
        try:
            parsed = json.loads(plaintext.decode("utf-8"))
            return Credential(**parsed)
        except (TypeError, ValueError) as exc:
            raise CredentialStoreCorruptException(self._corrupt_message(self.db_path, "记录数据损坏")) from exc

    async def _load_key(self, connection: aiosqlite.Connection, generate_if_missing: bool) -> RSA.RsaKey:
        """
        载入 RSA 密钥；允许时在密钥文件缺失且库无存量记录的前提下生成新钥。

        密钥文件存在但 PEM 解析失败一律抛 CredentialStoreCorruptException，
        不静默重建（FR-006）；编码路径生成新钥前须确认库中无存量记录，防止
        密钥丢失后落盘静默重建可读历史。

        Args:
            connection (aiosqlite.Connection): 数据库连接（生成前查存量记录用）。
            generate_if_missing (bool): 密钥文件缺失时是否允许生成新钥（解码
                路径必须为 False，否则存量数据将被无声抛弃）。

        Returns:
            RSA.RsaKey: 可用的 RSA 密钥。

        Raises:
            CredentialStoreCorruptException: 密钥文件缺失（不允许生成时）、
                损坏，或缺失但库中已有存量记录。
        """
        key_path = self._configured_key_path
        if key_path.exists():
            try:
                return RSA.import_key(key_path.read_bytes())
            except (OSError, TypeError, ValueError, IndexError) as exc:
                raise CredentialStoreCorruptException(
                    f"凭据存储密钥不可用（{key_path}）：密钥文件损坏或非 PEM 格式，需重新添加账号。"
                ) from exc
        if not generate_if_missing:
            raise CredentialStoreCorruptException(
                f"凭据存储密钥不可用（{key_path}）：密钥文件缺失，存量数据不可解密，需重新添加账号。"
            )
        cursor = await connection.execute("SELECT COUNT(*) FROM credential")
        row = await cursor.fetchone()
        await cursor.close()
        if row is not None and int(row[0]) > 0:
            raise CredentialStoreCorruptException(
                f"凭据存储密钥不可用（{key_path}）：密钥文件缺失且库中存在存量记录，需重新添加账号。"
            )
        key = RSA.generate(_RSA_KEY_BITS)
        parent = key_path.parent
        if not parent.is_dir():
            parent.mkdir(parents=True, exist_ok=True)
        key_path.write_bytes(key.export_key(format="PEM"))
        _restrict_key_permissions(key_path)
        logger.info("已生成凭据存储密钥文件（%s）", key_path)
        return key

    @staticmethod
    def _corrupt_message(db_path: Path, category: str) -> str:
        """
        集中构造库损坏类错误消息（统一脱敏：只含路径与原因类别）。

        Args:
            db_path (Path): 数据库文件路径。
            category (str): 原因类别描述（不含任何凭据字段值）。

        Returns:
            str: 脱敏后的错误消息。
        """
        return f"凭据存储库不可用（{db_path}）：{category}，存量数据不可读，需重新添加账号。"

    async def _get_connection(self) -> aiosqlite.Connection:
        """
        获取（惰性创建）aiosqlite 连接，并校验事件循环一致性。

        首次调用时创建连接并记录当前事件循环；后续调用校验当前事件循环与
        绑定循环一致，不一致时显式抛出 ArgsException。

        Returns:
            aiosqlite.Connection: 可用的数据库连接。

        Raises:
            ArgsException: 实例已关闭，或当前事件循环与连接绑定的循环不一致。
        """
        current_loop = asyncio.get_running_loop()
        if self._closed:
            raise ArgsException("凭据存储管理器已关闭，无法再执行 IO 操作；请重建实例。")
        if self._connection is not None and self._connection_loop is not current_loop:
            raise ArgsException("凭据存储管理器实例与事件循环绑定，请在同一事件循环内使用。")
        async with self._connect_lock:
            connection = self._connection
            if connection is None:
                parent = self._configured_db_path.parent
                if not parent.is_dir():
                    parent.mkdir(parents=True, exist_ok=True)
                connection = await aiosqlite.connect(self._configured_db_path)
                self._connection = connection
                self._connection_loop = current_loop
            return connection

    def _resolve_db_path(self, db_path: str | Path | None) -> Path:
        """
        解析数据库文件路径。

        Args:
            db_path (str | Path | None): 调用方传入的路径；None 时取默认目录。

        Returns:
            Path: 归一化后的数据库文件绝对路径。
        """
        if db_path is None:
            return Path(platformdirs.user_data_dir(_DEFAULT_APP_DIR_NAME, appauthor=False)) / _DEFAULT_DB_FILENAME
        return self._normalize_path(db_path)

    def _resolve_key_path(self, key_path: str | Path | None) -> Path:
        """
        解析密钥文件路径。

        Args:
            key_path (str | Path | None): 调用方传入的路径；None 时取数据库
                同目录下的默认文件名（密钥与数据库同目录，data-model.md）。

        Returns:
            Path: 归一化后的密钥文件绝对路径。
        """
        if key_path is None:
            return self._configured_db_path.parent / _DEFAULT_KEY_FILENAME
        return self._normalize_path(key_path)

    @staticmethod
    def _normalize_path(path: str | Path) -> Path:
        """
        归一化路径（展开用户目录并解析为绝对路径），用于配置一致性比较。

        Args:
            path (str | Path): 原始路径。

        Returns:
            Path: 归一化后的绝对路径。
        """
        return Path(path).expanduser().resolve()


def _restrict_key_permissions(key_path: Path) -> None:
    """
    尽力收紧密钥文件权限（POSIX 下 0600；Windows 无 POSIX 权限位，跳过）。

    Args:
        key_path (Path): 密钥文件路径。
    """
    if os.name == "posix":
        try:
            os.chmod(key_path, 0o600)
        except OSError:
            logger.warning("密钥文件权限收紧失败（%s）", key_path)
