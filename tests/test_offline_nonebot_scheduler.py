"""连接时机与规模节流的离线测试（T036 / SC-004 / SC-012 / FR-021）。"""

from __future__ import annotations

import asyncio

from bilibili_api.exceptions import NetworkException
from bilibili_api.nonebot.adapters.bilibili_live.accounts import AccountPool, FailureClass
from bilibili_api.nonebot.adapters.bilibili_live.config import NoneBotLiveConfig
from bilibili_api.nonebot.adapters.bilibili_live.scheduler import (
    ConnectionPolicy,
    ConnectionScheduler,
    RoomState,
)
from tests.nonebot_fakes import FakeCredential, FakeOps


class FakeClock:
    """可控单调时钟与休眠记录器。"""

    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps: list[float] = []

    def __call__(self) -> float:
        return self.now

    async def sleep(self, delay: float) -> None:
        self.sleeps.append(delay)
        self.now += delay


def build_scheduler(
    rooms: list[int],
    *,
    timing: str = "on",
    max_concurrent_connects: int = 5,
    ops: FakeOps | None = None,
) -> tuple[ConnectionScheduler, FakeOps, FakeClock]:
    config = NoneBotLiveConfig.model_validate(
        {
            "bots": [{"uid": 1, "room_ids": rooms, "connect_timing": timing}],
            "max_concurrent_connects": max_concurrent_connects,
            "poll_interval": 60,
            "min_poll_interval": 2,
        }
    )
    pool = AccountPool({1: FakeCredential(1)})
    fake_ops = ops or FakeOps()
    clock = FakeClock()
    scheduler = ConnectionScheduler(config=config, pool=pool, ops=fake_ops, clock=clock, sleep=clock.sleep)
    scheduler.subscribe_from_config()
    return scheduler, fake_ops, clock


async def test_on_policy_connects_all_rooms_at_startup() -> None:
    """ON：启动即对全部房间建连。"""
    scheduler, ops, _ = build_scheduler([101, 102, 103])
    await scheduler.startup()
    try:
        assert sorted(ops.connected) == [101, 102, 103]
        assert all(subscription.state is RoomState.CONNECTED for subscription in scheduler.subscriptions.values())
    finally:
        await scheduler.shutdown()


async def test_auto_policy_connects_when_live_and_disconnects_when_off() -> None:
    """AUTO：开播一个周期内连接，下播后断开。"""
    scheduler, ops, _ = build_scheduler([101], timing="auto")
    ops.status[101] = 1
    await scheduler.poll_once()
    subscription = scheduler.subscriptions[101]
    assert subscription.state is RoomState.CONNECTED
    assert ops.connected == [101]
    ops.status[101] = 0
    await scheduler.poll_once()
    assert subscription.state is RoomState.IDLE
    assert ops.disconnected == [101]


async def test_auto_policy_does_not_connect_when_offline() -> None:
    """AUTO：未开播不连接。"""
    scheduler, ops, _ = build_scheduler([101], timing="auto")
    await scheduler.poll_once()
    assert ops.connected == []
    assert scheduler.subscriptions[101].state is RoomState.IDLE


async def test_poll_throttle_between_requests() -> None:
    """SC-004：同轮相邻查询间隔不小于 `min_poll_interval`。"""
    scheduler, ops, clock = build_scheduler([101, 102, 103], timing="auto")
    await scheduler.poll_once()
    assert clock.sleeps == [2, 2]
    assert ops.status_calls == [101, 102, 103]


async def test_poll_failure_backs_off_and_never_accelerates() -> None:
    """查询失败只退避，不加速；退避未到期时不再发请求。"""
    scheduler, ops, clock = build_scheduler([101], timing="auto")
    ops.status_error = NetworkException(412, "风控")
    await scheduler.poll_once()
    subscription = scheduler.subscriptions[101]
    assert subscription.state is RoomState.BACKOFF
    assert subscription.next_retry_at is not None
    first_delay = subscription.next_retry_at - clock.now
    assert first_delay > 0
    await scheduler.poll_once()
    assert ops.status_calls == [101]
    clock.now = subscription.next_retry_at or clock.now
    ops.status_error = NetworkException(412, "风控")
    await scheduler.poll_once()
    assert len(ops.status_calls) == 2
    second_delay = (subscription.next_retry_at or 0) - clock.now
    assert second_delay >= first_delay


async def test_auto_failure_classified_as_network_or_risk_control() -> None:
    """风控 / 网络失败进入退避；协议错误不改变状态。"""
    scheduler, ops, _ = build_scheduler([101], timing="auto")
    ops.status_error = ValueError("bad json")
    await scheduler.poll_once()
    assert scheduler.subscriptions[101].state is RoomState.IDLE
    assert FailureClass.PROTOCOL is not FailureClass.NETWORK


async def test_connect_concurrency_limited_for_50_rooms() -> None:
    """SC-012：50 房间启动建连不超过 `max_concurrent_connects`。"""
    rooms = list(range(1000, 1050))
    scheduler, ops, _ = build_scheduler(rooms, max_concurrent_connects=5)
    ops.connect_delay = 0.001
    await scheduler.startup()
    assert ops.peak <= 5
    assert ops.peak >= 2
    assert len(ops.connected) == 50
    await scheduler.shutdown()
    assert all(subscription.state is RoomState.CLOSED for subscription in scheduler.subscriptions.values())
    assert len(ops.disconnected) == 50
    assert scheduler._background == set()


async def test_shutdown_is_idempotent_and_stops_reconnect() -> None:
    """FR-017：关闭后不再重连，重复关闭无副作用。"""
    scheduler, ops, clock = build_scheduler([101])
    ops.connect_error = NetworkException(0, "boom")
    await scheduler.startup()
    subscription = scheduler.subscriptions[101]
    assert subscription.state is RoomState.BACKOFF
    await scheduler.shutdown()
    connected_before = list(ops.connected)
    clock.now += 10_000
    await asyncio.sleep(0)
    assert ops.connected == connected_before
    await scheduler.shutdown()
    assert subscription.state is RoomState.CLOSED


async def test_manual_policy_requires_explicit_connect() -> None:
    """MANUAL：不自动连接，可显式强制连接。"""
    scheduler, ops, _ = build_scheduler([101], timing="manual")
    await scheduler.connect(scheduler.subscriptions[101])
    assert ops.connected == []
    await scheduler.connect(scheduler.subscriptions[101], force=True)
    assert ops.connected == [101]
    await scheduler.shutdown()


async def test_auto_startup_spawns_poller() -> None:
    """AUTO 启动轮询器，关闭时清理后台任务。"""
    scheduler, _, _ = build_scheduler([101], timing="auto")
    await scheduler.startup()
    assert len(scheduler._background) == 1
    await scheduler.shutdown()
    assert scheduler._background == set()


async def test_retry_due_only_returns_expired_backoff() -> None:
    """退避未到时不重连，到期后返回待重连项。"""
    scheduler, _ops, _clock = build_scheduler([101])
    subscription = scheduler.subscriptions[101]
    scheduler.note_failure(subscription)
    due_at = subscription.next_retry_at or 0
    assert scheduler.retry_due(due_at - 1) == []
    assert scheduler.retry_due(due_at) == [subscription]


def test_policy_values_match_config() -> None:
    """策略枚举与配置取值一致。"""
    assert ConnectionPolicy.ON.value == "on"
    assert ConnectionPolicy.AUTO.value == "auto"
    assert ConnectionPolicy.MANUAL.value == "manual"
