"""
bilibili_api.nonebot.adapters.bilibili_live.scheduler

连接时机策略（ON / AUTO / MANUAL）与房间订阅编排。

状态机与时间推进分离：状态转移只由注入的时钟、休眠函数与 `SchedulerOps`
驱动，离线用例可用假时钟与假房间状态源逐时点断言动作序列（data-model.md §3.2–3.3）。

- `on`：启动即对全部房间建连；断线由退避重连处理。
- `auto`：仅启动轮询器，按 `live_status` 连 / 断；同轮相邻查询间隔不小于
  `min_poll_interval`，失败只退避不加速。
- `manual`：不做任何连接，只能由业务代码显式调用。
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from contextlib import suppress
from dataclasses import dataclass, field
from enum import Enum
import time
from typing import Any, Protocol

from ....exceptions import ArgsException
from .accounts import AccountPool, FailureClass, classify_failure, is_permanent_credential_error
from .config import ConnectionTiming, NoneBotLiveConfig
from .const import MAX_BACKOFF_INTERVAL, RECONNECT_INTERVAL
from .log import log, redact_credential


class ConnectionPolicy(str, Enum):
    """连接时机策略。"""

    ON = "on"
    """注册即连。"""
    AUTO = "auto"
    """开播才连（轮询判定）。"""
    MANUAL = "manual"
    """手动连。"""

    @classmethod
    def from_timing(cls, timing: ConnectionTiming) -> ConnectionPolicy:
        """
        由配置取值构造策略。

        Args:
            timing (ConnectionTiming): 配置取值。

        Returns:
            ConnectionPolicy: 对应策略。
        """
        return cls(timing)


class RoomState(str, Enum):
    """房间订阅状态。"""

    IDLE = "idle"
    """未连接，等待策略允许。"""
    CONNECTING = "connecting"
    """正在握手 / 鉴权（占用建连并发额度）。"""
    CONNECTED = "connected"
    """已鉴权并接收数据。"""
    BACKOFF = "backoff"
    """失败后退避中。"""
    CLOSING = "closing"
    """正在断开（如 AUTO 下播）。"""
    CLOSED = "closed"
    """终态：整体关闭后不可再迁移。"""


@dataclass
class RoomSubscription:
    """一条「房间 + 账号 + 连接」的运行单元。"""

    room_display_id: int
    """配置里写的房间号（可能是短号）。"""
    room_real_id: int | None = None
    """归一后的真实房间号；未解析时为空。"""
    uid: int | None = None
    """当前承载账号。"""
    policy: ConnectionPolicy = ConnectionPolicy.ON
    """连接时机策略。"""
    state: RoomState = RoomState.IDLE
    """当前状态。"""
    retry_count: int = 0
    """连续失败次数（用于指数退避）。"""
    next_retry_at: float | None = None
    """退避截止时刻（单调时钟）。"""
    last_frame_at: float | None = None
    """最近收帧时刻，用于心跳超时判定。"""
    tasks: set[asyncio.Task[Any]] = field(default_factory=set)
    """该房间拥有的连接 / 心跳任务，关闭时必须取消。"""

    @property
    def task_count(self) -> int:
        """
        返回该房间仍存活的任务数（供测试与关闭校验）。

        Returns:
            int: 未完成的任务数。
        """
        return len([task for task in self.tasks if not task.done()])


class SchedulerOps(Protocol):
    """调度器依赖的外部动作（由适配器实现，测试可替换为假实现）。"""

    async def connect(self, subscription: RoomSubscription) -> None:
        """
        建立并鉴权一条房间连接，返回后读取循环应已启动。

        Args:
            subscription (RoomSubscription): 目标订阅。
        """
        ...

    async def disconnect(self, subscription: RoomSubscription) -> None:
        """
        断开一条房间连接（幂等）。

        Args:
            subscription (RoomSubscription): 目标订阅。
        """
        ...

    async def live_status(self, room_display_id: int) -> int:
        """
        查询开播状态。

        Args:
            room_display_id (int): 房间号（长短号均可）。

        Returns:
            int: `0` 未开播、`1` 直播中、`2` 轮播。
        """
        ...


class ConnectionScheduler:
    """房间订阅编排器。"""

    def __init__(
        self,
        *,
        config: NoneBotLiveConfig,
        pool: AccountPool,
        ops: SchedulerOps,
        clock: Callable[[], float] | None = None,
        sleep: Callable[[float], Awaitable[None]] | None = None,
        persist_credential: Callable[[int, Any], Awaitable[None]] | None = None,
    ) -> None:
        """
        Args:
            config (NoneBotLiveConfig): 适配器配置。
            pool (AccountPool): 账号池。
            ops (SchedulerOps): 外部动作实现。
            clock (Callable[[], float] | None, optional): 单调时钟. Defaults to `time.monotonic`.
            sleep (Callable[[float], Awaitable[None]] | None, optional): 休眠函数. Defaults to `asyncio.sleep`.
            persist_credential (Callable[[int, Any], Awaitable[None]] | None, optional):
                刷新成功后的凭据写回回调. Defaults to None.
        """
        self.config = config
        self.pool = pool
        self.ops = ops
        self._clock = clock if clock is not None else time.monotonic
        self._sleep = sleep if sleep is not None else asyncio.sleep
        self._persist_credential = persist_credential
        self.subscriptions: dict[int, RoomSubscription] = {}
        self._semaphore = asyncio.Semaphore(config.max_concurrent_connects)
        self._closed = False
        self._background: set[asyncio.Task[Any]] = set()
        self._connect_calls = 0
        self._connect_peak = 0

    @property
    def connect_peak(self) -> int:
        """
        返回观测到的最大同时在连（握手 / 鉴权中）数量。

        Returns:
            int: 峰值并发数。
        """
        return self._connect_peak

    def register_room(self, room_display_id: int, policy: ConnectionPolicy) -> RoomSubscription:
        """
        注册房间订阅（已存在时返回既有项）。

        Args:
            room_display_id (int): 房间号。
            policy (ConnectionPolicy): 连接时机策略。

        Returns:
            RoomSubscription: 订阅对象。
        """
        subscription = self.subscriptions.get(room_display_id)
        if subscription is None:
            subscription = RoomSubscription(room_display_id=room_display_id, policy=policy)
            self.subscriptions[room_display_id] = subscription
        return subscription

    def subscribe_from_config(self) -> list[RoomSubscription]:
        """
        按配置注册全部房间（每个账号的连接时机单独解析）。

        Returns:
            list[RoomSubscription]: 注册后的订阅列表（声明顺序）。
        """
        subscriptions: list[RoomSubscription] = []
        for bot in self.config.bots:
            policy = ConnectionPolicy.from_timing(self.config.resolve_connect_timing(bot))
            for room_id in bot.room_ids:
                subscriptions.append(self.register_room(room_id, policy))
        return subscriptions

    async def startup(self) -> None:
        """
        按策略启动：ON 立即并发建连（受 `max_concurrent_connects` 节流）、
        AUTO 启动轮询、MANUAL 不动作。
        """
        on_rooms = [
            subscription for subscription in self.subscriptions.values() if subscription.policy is ConnectionPolicy.ON
        ]
        if on_rooms:
            await asyncio.gather(*(self.connect(subscription) for subscription in on_rooms))
            self._spawn(self._retry_loop())
        if any(subscription.policy is ConnectionPolicy.AUTO for subscription in self.subscriptions.values()):
            self._spawn(self._auto_loop())

    def _spawn(self, coroutine: Awaitable[None]) -> asyncio.Task[Any]:
        """
        创建并登记后台任务。

        Args:
            coroutine (Awaitable[None]): 协程。

        Returns:
            asyncio.Task[Any]: 任务对象。
        """
        task: asyncio.Task[Any] = asyncio.ensure_future(coroutine)
        self._background.add(task)
        task.add_done_callback(self._background.discard)
        return task

    async def connect(self, subscription: RoomSubscription, *, force: bool = False) -> None:
        """
        建立一条连接（受建连并发节流约束）。

        Args:
            subscription (RoomSubscription): 目标订阅。
            force (bool, optional): 忽略策略限制（手动强制连接）. Defaults to False.
        """
        if self._closed or subscription.state in (RoomState.CONNECTING, RoomState.CONNECTED, RoomState.CLOSED):
            return
        if subscription.policy is ConnectionPolicy.MANUAL and not force:
            return
        async with self._semaphore:
            if self._closed:
                return
            self._connect_calls += 1
            self._connect_peak = max(self._connect_peak, self._connect_calls)
            subscription.state = RoomState.CONNECTING
            try:
                await self.ops.connect(subscription)
            except Exception as e:
                await self.handle_failure(subscription, e)
            finally:
                self._connect_calls -= 1
            if subscription.state is RoomState.CONNECTING:
                subscription.state = RoomState.CONNECTED
                subscription.next_retry_at = None

    async def disconnect(self, subscription: RoomSubscription) -> None:
        """
        断开一条连接（幂等）。

        Args:
            subscription (RoomSubscription): 目标订阅。
        """
        if subscription.state is RoomState.CLOSED:
            return
        subscription.state = RoomState.CLOSING
        try:
            await self.ops.disconnect(subscription)
        except Exception as e:
            log("WARNING", f"房间 {subscription.room_display_id} 断开时出错：{type(e).__name__}")
        if subscription.state is RoomState.CLOSING:
            subscription.state = RoomState.IDLE

    async def handle_failure(self, subscription: RoomSubscription, error: BaseException) -> None:
        """
        按失败分类处理房间失败（FR-006：凭据类整号切换，连接类只影响单房间）。

        Args:
            subscription (RoomSubscription): 失败的订阅。
            error (BaseException): 失败原因。
        """
        failure = classify_failure(error)
        uid = subscription.uid
        log(
            "WARNING",
            f"房间 {subscription.room_display_id} 失败（{failure.value}，"
            f"账号 {redact_credential(uid)}）：{type(error).__name__}",
        )
        if failure in (FailureClass.CREDENTIAL, FailureClass.UNREFRESHABLE) and uid is not None:
            if failure is FailureClass.UNREFRESHABLE:
                # 可继续只读但不可刷新：首次鉴权失败即换号（research D10）
                self.pool.mark_dead(uid, f"凭据不可刷新：{type(error).__name__}")
                await self._migrate_or_close(subscription, uid)
                return
            if is_permanent_credential_error(error):
                # 永久不可用（如业务码 -102）直接弃用，不尝试刷新（research D10）
                self.pool.mark_dead(uid, f"凭据永久不可用：{type(error).__name__}")
                await self._migrate_or_close(subscription, uid)
                return
            if await self._refresh_or_switch(uid):
                # 刷新成功：账号继续可用，仅该房间按退避重连
                self.note_failure(subscription)
                return
            # 刷新失败：账号已判死，整号切换
            await self._migrate_or_close(subscription, uid)
            return
        if failure in (FailureClass.NETWORK, FailureClass.RISK_CONTROL):
            self.note_failure(subscription)
            return
        # PROTOCOL / NO_DATA：只记录，不改变连接状态
        if subscription.state in (RoomState.CONNECTING, RoomState.BACKOFF):
            subscription.state = RoomState.IDLE

    async def _migrate_or_close(self, subscription: RoomSubscription, uid: int) -> None:
        """
        整号切换；账号池耗尽时记录明确错误并停止该房间（不空转）。

        Args:
            subscription (RoomSubscription): 触发失败的订阅。
            uid (int): 已死亡账号 uid。
        """
        try:
            await self.migrate_account(uid)
        except ArgsException as e:
            log("ERROR", f"账号池已无可用账号，停止重连：{e}")
            subscription.state = RoomState.CLOSED

    async def _refresh_or_switch(self, uid: int) -> bool:
        """
        先尝试刷新凭据；失败时把账号标记为 `dead`。

        Args:
            uid (int): 账号 uid。

        Returns:
            bool: 刷新成功（账号仍可用）时为 `True`；账号已死亡时为 `False`。
        """
        slot = self.pool.get(uid)
        if slot is None:
            return False
        try:
            await self.pool.ensure_usable(uid, self._persist)
        except Exception:
            return False
        return True

    async def _persist(self, uid: int, credential: Any) -> None:
        """
        把刷新后的凭据写回存储（未注入回调时不做持久化）。

        Args:
            uid (int): 账号 uid。
            credential (Any): 刷新后的凭据。
        """
        if self._persist_credential is not None:
            await self._persist_credential(uid, credential)

    def note_failure(self, subscription: RoomSubscription) -> None:
        """
        进入指数退避（不得在失败时缩短间隔）。

        Args:
            subscription (RoomSubscription): 目标订阅。
        """
        delay = min(RECONNECT_INTERVAL * (2**subscription.retry_count), MAX_BACKOFF_INTERVAL)
        subscription.retry_count += 1
        subscription.state = RoomState.BACKOFF
        subscription.next_retry_at = self._clock() + delay

    def note_frame(self, subscription: RoomSubscription) -> None:
        """
        记录收帧：清除退避与失败计数。

        Args:
            subscription (RoomSubscription): 目标订阅。
        """
        subscription.last_frame_at = self._clock()
        subscription.retry_count = 0

    def retry_due(self, now: float) -> list[RoomSubscription]:
        """
        返回退避到期、可以重连的订阅（AUTO 房间由轮询负责）。

        Args:
            now (float): 当前单调时钟。

        Returns:
            list[RoomSubscription]: 待重连订阅。
        """
        due: list[RoomSubscription] = []
        for subscription in self.subscriptions.values():
            if subscription.policy is ConnectionPolicy.AUTO:
                continue
            if subscription.state is not RoomState.BACKOFF:
                continue
            if subscription.next_retry_at is None or subscription.next_retry_at <= now:
                subscription.state = RoomState.IDLE
                due.append(subscription)
        return due

    async def poll_once(self) -> list[RoomSubscription]:
        """
        执行一轮开播检测：同轮相邻请求间隔不小于 `min_poll_interval`。

        Returns:
            list[RoomSubscription]: 本轮处理过的订阅。
        """
        checked: list[RoomSubscription] = []
        first = True
        for subscription in list(self.subscriptions.values()):
            if self._closed:
                break
            if subscription.policy is not ConnectionPolicy.AUTO:
                continue
            if subscription.state in (RoomState.CONNECTING, RoomState.CLOSING, RoomState.CLOSED):
                continue
            now = self._clock()
            if subscription.next_retry_at is not None and now < subscription.next_retry_at:
                continue
            if not first:
                await self._sleep(self.config.min_poll_interval)
                now = self._clock()
            first = False
            try:
                status = await self.ops.live_status(subscription.room_display_id)
            except Exception as e:
                failure = classify_failure(e)
                if failure in (FailureClass.NETWORK, FailureClass.RISK_CONTROL):
                    self.note_failure(subscription)
                else:
                    log(
                        "WARNING",
                        f"房间 {subscription.room_display_id} 开播检测失败（{failure.value}）：{type(e).__name__}",
                    )
                checked.append(subscription)
                continue
            checked.append(subscription)
            if status in (1, 2):
                if subscription.state in (RoomState.IDLE, RoomState.BACKOFF):
                    await self.connect(subscription)
            elif status == 0 and subscription.state is RoomState.CONNECTED:
                await self.disconnect(subscription)
        return checked

    async def _auto_loop(self) -> None:
        """AUTO 轮询主循环：每轮之后等待 `poll_interval`。"""
        while not self._closed:
            await self.poll_once()
            await self._sleep(self.config.poll_interval)

    async def _retry_loop(self) -> None:
        """ON 策略的退避重连循环。"""
        while not self._closed:
            for subscription in self.retry_due(self._clock()):
                await self.connect(subscription)
            await self._sleep(1.0)

    async def migrate_account(self, dead_uid: int) -> None:
        """
        把一个已死亡账号名下的全部房间迁移到下一个可用账号并重连。

        Args:
            dead_uid (int): 已死亡账号 uid。

        Raises:
            ArgsException: 账号池已无可用账号（V-08）。
        """
        affected = [sub for sub in self.subscriptions.values() if sub.uid == dead_uid]
        if not affected:
            return
        next_slot = self.pool.next_after(dead_uid)
        if next_slot is None:
            raise ArgsException("所有账号均不可用：请检查凭据存储并为相关账号重新添加有效凭据后重启。")
        log(
            "WARNING",
            f"账号 {redact_credential(dead_uid)} 不可用，{len(affected)} 个房间切换到 "
            f"{redact_credential(next_slot.uid)}",
        )
        for subscription in affected:
            await self.disconnect(subscription)
            subscription.uid = next_slot.uid
            subscription.retry_count = 0
            subscription.next_retry_at = None
            if subscription.policy is not ConnectionPolicy.MANUAL and not self._closed:
                await self.connect(subscription)

    async def shutdown(self) -> None:
        """
        关闭编排器：停止轮询与重连、断开全部连接、取消后台任务（幂等）。
        """
        if self._closed:
            return
        self._closed = True
        for task in list(self._background):
            task.cancel()
        for task in list(self._background):
            with suppress(asyncio.CancelledError):
                await task
        self._background.clear()
        for subscription in self.subscriptions.values():
            for task in list(subscription.tasks):
                task.cancel()
            subscription.tasks.clear()
            if subscription.state is not RoomState.CLOSED:
                with suppress(Exception):
                    await self.ops.disconnect(subscription)
                subscription.state = RoomState.CLOSED
