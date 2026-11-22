"""
bilibili_api.nonebot.adapters.bilibili_live.accounts

多账号调度：账号池、失败分类、凭据刷新与整号切换。

账号唯一事实源是库的凭据存储；本模块只持有账号的深拷贝快照，刷新成功后通过
持久化回调写回存储（data-model.md §2.1 / research D9）。日志与异常文本只允许
出现 uid，不得出现任何凭据字段值。
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from enum import Enum
import json

from ....exceptions import (
    ArgsException,
    CookiesRefreshException,
    CredentialNoAcTimeValueException,
    CredentialNoBiliJctException,
    CredentialNoBuvid3Exception,
    CredentialNoBuvid4Exception,
    CredentialNoDedeUserIDException,
    CredentialNoSessdataException,
    NetworkException,
    ResponseCodeException,
    WbiRetryTimesExceedException,
)
from ....utils.credential_store import BaseCredentialStoreManager
from ....utils.network import Credential
from .config import NoneBotLiveConfig
from .log import log, redact_credential


async def build_pool_from_store(store: BaseCredentialStoreManager, config: NoneBotLiveConfig) -> AccountPool:
    """
    校验配置引用的 uid 均存在，并按存储插入顺序构造账号池。

    账号的新增与移除只经库的凭据存储完成；适配器每次启动重新读取存储以反映
    最新顺序与集合（FR-005）。

    Args:
        store (BaseCredentialStoreManager): 已 `load()` 的凭据存储。
        config (NoneBotLiveConfig): 适配器配置。

    Returns:
        AccountPool: 账号池。

    Raises:
        ArgsException: 存在缺失 uid（V-03）或无法读取凭据。
    """
    all_uids = await store.get_all_uids()
    configured = {bot.uid for bot in config.bots}
    missing = sorted(uid for uid in configured if uid not in all_uids)
    if missing:
        raise ArgsException(
            f"配置引用的 uid 不在凭据存储中：{missing}。"
            "请先用 SQLiteCredentialStoreManager.add_credential() 写入账号，"
            "再在 BILIBILI_LIVE_BOTS 中以 uid 引用（见 README 迁移步骤）。"
        )
    credentials: dict[int, Credential] = {}
    for uid in all_uids:
        if uid not in configured:
            continue
        credential = await store.get_credential(uid)
        if credential is None:
            raise ArgsException(f"无法从凭据存储读取 uid={uid} 的凭据")
        credentials[uid] = credential
    return AccountPool.from_store(credentials)


class AccountState(str, Enum):
    """账号状态。"""

    AVAILABLE = "available"
    """可用。"""
    REFRESHING = "refreshing"
    """刷新中（同一账号的并发刷新会合并）。"""
    DEAD = "dead"
    """本次运行内判定不可用，等待运维重新添加账号后重启。"""


class FailureClass(str, Enum):
    """失败分类（FR-006 / research D10）。"""

    CREDENTIAL = "credential"
    """登录态无效或刷新失败：整号切换。"""
    UNREFRESHABLE = "unrefreshable"
    """凭据可继续只读但不可刷新：首次鉴权失败即换号。"""
    RISK_CONTROL = "risk_control"
    """风控 / 限速：房间级指数退避，不换号、不加速。"""
    NETWORK = "network"
    """瞬时网络故障：房间级退避重连。"""
    PROTOCOL = "protocol"
    """协议 / 解码错误：丢弃当前帧或事件并记录，不改变连接状态。"""
    NO_DATA = "no_data"
    """无数据（`Content-Length: 0`）：跳过本轮，不计失败。"""


CREDENTIAL_EXCEPTIONS: tuple[type[BaseException], ...] = (
    CredentialNoSessdataException,
    CredentialNoBiliJctException,
    CredentialNoDedeUserIDException,
    CredentialNoBuvid3Exception,
    CredentialNoBuvid4Exception,
)
"""凭据不可用（直接整号切换）的异常集合。"""

UNREFRESHABLE_EXCEPTIONS: tuple[type[BaseException], ...] = (CredentialNoAcTimeValueException,)
"""可继续只读但不可刷新的异常集合。"""

CREDENTIAL_CODES: frozenset[int] = frozenset({-101, -111, -102})
"""凭据类业务码：未登录 / csrf 失败 / 封停。"""

PERMANENT_CREDENTIAL_CODES: frozenset[int] = frozenset({-102})
"""永久不可用的业务码（直接弃用，不尝试刷新）。"""

RISK_CONTROL_CODES: frozenset[int] = frozenset({-352, -412, -509})
"""风控 / 限速业务码。"""

RISK_CONTROL_STATUS: frozenset[int] = frozenset({412})
"""风控 / 限速 HTTP 状态码。"""


def classify_failure(error: BaseException | None) -> FailureClass:
    """
    把异常映射到失败分类（research D10 的逐条对应实现）。

    未识别的异常按 `PROTOCOL` 处理（记录并跳过），不使用「一律重连」兜底：
    重连只由明确的网络 / 风控信号触发。

    Args:
        error (BaseException | None): 失败原因；`None` 表示无数据。

    Returns:
        FailureClass: 失败分类。
    """
    if error is None:
        return FailureClass.NO_DATA
    if isinstance(error, UNREFRESHABLE_EXCEPTIONS):
        return FailureClass.UNREFRESHABLE
    if isinstance(error, CREDENTIAL_EXCEPTIONS):
        return FailureClass.CREDENTIAL
    if isinstance(error, CookiesRefreshException):
        return FailureClass.CREDENTIAL
    if isinstance(error, WbiRetryTimesExceedException):
        return FailureClass.RISK_CONTROL
    if isinstance(error, ResponseCodeException):
        if error.code in CREDENTIAL_CODES:
            return FailureClass.CREDENTIAL
        if error.code in RISK_CONTROL_CODES:
            return FailureClass.RISK_CONTROL
        return FailureClass.PROTOCOL
    if isinstance(error, NetworkException):
        if error.status in RISK_CONTROL_STATUS:
            return FailureClass.RISK_CONTROL
        return FailureClass.NETWORK
    if isinstance(error, (asyncio.TimeoutError, TimeoutError, ConnectionError, OSError)):
        return FailureClass.NETWORK
    if isinstance(error, json.JSONDecodeError | UnicodeDecodeError | ValueError | KeyError):
        return FailureClass.PROTOCOL
    return FailureClass.PROTOCOL


def is_permanent_credential_error(error: BaseException) -> bool:
    """
    判断是否为永久不可用的凭据错误（业务码 `-102` 等，直接弃用不刷新）。

    Args:
        error (BaseException): 失败原因。

    Returns:
        bool: 是否永久不可用。
    """
    if isinstance(error, ResponseCodeException):
        return error.code in PERMANENT_CREDENTIAL_CODES
    return isinstance(error, CREDENTIAL_EXCEPTIONS)


class AccountSlot:
    """账号槽位。"""

    def __init__(self, uid: int, credential: Credential) -> None:
        """
        Args:
            uid (int): 账号 uid（存储主键）。
            credential (Credential): 从存储取得的深拷贝快照。
        """
        self.uid = uid
        self.credential = credential
        self.state = AccountState.AVAILABLE
        self.last_error: str | None = None

    def __repr__(self) -> str:
        return f"AccountSlot({self.uid}, {self.state.value})"


class AccountPool:
    """有序账号池。"""

    def __init__(self, credentials: dict[int, Credential]) -> None:
        """
        Args:
            credentials (dict[int, Credential]): 按存储插入顺序排列的 uid → 凭据。
        """
        self.order: list[int] = list(credentials)
        self.cursor: int = 0
        self.dead: set[int] = set()
        self.slots: dict[int, AccountSlot] = {
            uid: AccountSlot(uid, credential.model_copy(deep=True)) for uid, credential in credentials.items()
        }
        self._refresh_locks: dict[int, asyncio.Lock] = {}

    @classmethod
    def from_store(cls, credentials: dict[int, Credential]) -> AccountPool:
        """
        由存储快照构造账号池（顺序即插入顺序）。

        Args:
            credentials (dict[int, Credential]): 按插入顺序排列的 uid → 凭据。

        Returns:
            AccountPool: 账号池。
        """
        return cls(credentials)

    def all_uids(self) -> list[int]:
        """
        返回账号池中的全部 uid（插入顺序）。

        Returns:
            list[int]: uid 列表。
        """
        return list(self.order)

    def get(self, uid: int) -> AccountSlot | None:
        """
        取指定 uid 的槽位。

        Args:
            uid (int): 账号 uid。

        Returns:
            AccountSlot | None: 槽位；不存在时为 `None`。
        """
        return self.slots.get(uid)

    def current(self) -> AccountSlot | None:
        """
        按插入顺序从 `cursor` 起取第一个可用账号。

        Returns:
            AccountSlot | None: 可用账号；全部为 `dead` 时为 `None`（V-08）。
        """
        for offset in range(len(self.order)):
            uid = self.order[(self.cursor + offset) % len(self.order)]
            slot = self.slots[uid]
            if slot.state != AccountState.DEAD:
                self.cursor = (self.cursor + offset) % len(self.order)
                return slot
        return None

    def require_current(self) -> AccountSlot:
        """
        取当前可用账号，全部不可用时抛出明确错误（V-08）。

        Returns:
            AccountSlot: 可用账号。

        Raises:
            ArgsException: 账号池已全部 `dead`。
        """
        slot = self.current()
        if slot is None:
            raise ArgsException("所有账号均不可用：请检查凭据存储并为相关账号重新添加有效凭据后重启。")
        return slot

    def next_after(self, uid: int) -> AccountSlot | None:
        """
        取 `uid` 之后的下一个可用账号。

        Args:
            uid (int): 当前账号 uid。

        Returns:
            AccountSlot | None: 下一个可用账号；没有时为 `None`。
        """
        if uid in self.order:
            self.cursor = (self.order.index(uid) + 1) % len(self.order)
        return self.current()

    def mark_dead(self, uid: int, reason: str) -> None:
        """
        标记账号不可用并记录脱敏摘要。

        Args:
            uid (int): 账号 uid。
            reason (str): 脱敏后的失败摘要（不得含凭据字段值）。
        """
        slot = self.slots.get(uid)
        if slot is None:
            return
        slot.state = AccountState.DEAD
        slot.last_error = reason
        self.dead.add(uid)
        log("ERROR", f"账号 {redact_credential(uid)} 已标记不可用：{reason}")

    def available_uids(self) -> list[int]:
        """
        返回当前仍可用的 uid 列表。

        Returns:
            list[int]: 可用 uid（插入顺序）。
        """
        return [uid for uid in self.order if self.slots[uid].state != AccountState.DEAD]

    async def ensure_usable(
        self,
        uid: int,
        persist: Callable[[int, Credential], Awaitable[None]],
    ) -> AccountSlot:
        """
        校验并（必要时）刷新账号凭据。

        流程固定为「`check_valid()` → 失败则 `refresh()` → 写回存储 → 复检」，不把
        `check_refresh()` 当前置判断（过期会话会抛异常而非返回 `False`，research D9）。
        刷新按 uid 串行化；刷新确认阶段失败视为账号死亡且不重试。

        Args:
            uid (int): 账号 uid。
            persist (Callable[[int, Credential], Awaitable[None]]): 刷新成功后的写回回调。

        Returns:
            AccountSlot: 可用账号槽位。

        Raises:
            ArgsException: 账号不存在或已被标记 `dead`。
            NetworkException: 校验时网络故障（不改变账号状态，交由房间级退避）。
            CookiesRefreshException: 刷新或复检失败（账号同时被标记 `dead`）。
        """
        slot = self.slots.get(uid)
        if slot is None:
            raise ArgsException(f"账号 {redact_credential(uid)} 不在账号池中")
        if slot.state == AccountState.DEAD:
            raise ArgsException(f"账号 {redact_credential(uid)} 已不可用")
        lock = self._refresh_locks.setdefault(uid, asyncio.Lock())
        async with lock:
            if slot.state == AccountState.DEAD:
                raise ArgsException(f"账号 {redact_credential(uid)} 已不可用")
            try:
                if await slot.credential.check_valid():
                    slot.state = AccountState.AVAILABLE
                    slot.last_error = None
                    return slot
            except NetworkException:
                slot.state = AccountState.AVAILABLE
                raise
            slot.state = AccountState.REFRESHING
            try:
                await slot.credential.refresh()
                await persist(uid, slot.credential)
                if not await slot.credential.check_valid():
                    raise CookiesRefreshException("刷新后复检失败")
            except NetworkException:
                # 刷新链路本身网络故障：账号未被判死，交由房间级退避重试
                slot.state = AccountState.AVAILABLE
                raise
            except Exception as e:
                self.mark_dead(uid, f"凭据刷新失败：{type(e).__name__}")
                raise CookiesRefreshException(f"账号 {redact_credential(uid)} 刷新失败") from e
            slot.state = AccountState.AVAILABLE
            slot.last_error = None
            log("INFO", f"账号 {redact_credential(uid)} 凭据刷新成功")
            return slot

    def credentials_snapshot(self) -> dict[int, Credential]:
        """
        返回当前全部账号的凭据深拷贝快照。

        Returns:
            dict[int, Credential]: uid → 凭据深拷贝。
        """
        return {uid: slot.credential.model_copy(deep=True) for uid, slot in self.slots.items()}
