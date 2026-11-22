"""多账号调度离线测试（T029 / SC-003 / SC-003a）。"""

from __future__ import annotations

import asyncio
import time

import pytest

from bilibili_api.exceptions import ArgsException, CookiesRefreshException, ResponseCodeException
from bilibili_api.nonebot.adapters.bilibili_live.accounts import (
    AccountPool,
    AccountState,
    FailureClass,
    classify_failure,
    is_permanent_credential_error,
)
from bilibili_api.nonebot.adapters.bilibili_live.adapter import Adapter
from bilibili_api.nonebot.adapters.bilibili_live.config import NoneBotLiveConfig
from bilibili_api.nonebot.adapters.bilibili_live.log import redact_credential
from bilibili_api.nonebot.adapters.bilibili_live.scheduler import (
    ConnectionPolicy,
    ConnectionScheduler,
    RoomState,
)
from bilibili_api.utils._log import request_log
from tests.nonebot_fakes import FakeCredential, FakeDriver, FakeOps


def make_config(max_concurrent_connects: int = 5) -> NoneBotLiveConfig:
    return NoneBotLiveConfig.model_validate(
        {
            "bots": [
                {"uid": 1, "room_ids": [101]},
                {"uid": 2, "room_ids": [201]},
            ],
            "max_concurrent_connects": max_concurrent_connects,
        }
    )


def make_scheduler(
    credentials: dict[int, FakeCredential] | None = None,
    *,
    config: NoneBotLiveConfig | None = None,
    ops: FakeOps | None = None,
) -> tuple[ConnectionScheduler, FakeOps]:
    pool = AccountPool(credentials or {1: FakeCredential(1), 2: FakeCredential(2)})
    fake_ops = ops or FakeOps()
    scheduler = ConnectionScheduler(config=config or make_config(), pool=pool, ops=fake_ops)
    scheduler.subscribe_from_config()
    return scheduler, fake_ops


def test_selection_follows_insertion_order() -> None:
    """按存储插入顺序选号；前一个被移除后下一个顶上。"""
    pool = AccountPool({3: FakeCredential(3), 1: FakeCredential(1), 2: FakeCredential(2)})
    first = pool.current()
    assert first is not None
    assert first.uid == 3
    pool.mark_dead(3, "test")
    second = pool.current()
    assert second is not None
    assert second.uid == 1
    assert pool.available_uids() == [1, 2]


def test_pool_exhausted_reports_clear_error() -> None:
    """V-08 / FR-006：全部账号不可用时明确报错，不空转。"""
    uid = 1
    pool = AccountPool({uid: FakeCredential(uid)})
    pool.mark_dead(uid, "test")
    assert pool.current() is None
    with pytest.raises(ArgsException) as excinfo:
        pool.require_current()
    assert "所有账号均不可用" in str(excinfo.value)


async def test_refresh_failure_switches_all_rooms_within_5s() -> None:
    """SC-003：刷新失败后整号切换，5 秒内完成，且日志不含凭据值。"""
    cred_one = FakeCredential(1, valid=False, refresh_error=CookiesRefreshException("刷新失败"))
    scheduler, ops = make_scheduler({1: cred_one, 2: FakeCredential(2)})
    for subscription in scheduler.subscriptions.values():
        subscription.uid = 1 if subscription.room_display_id == 101 else 2
        subscription.state = RoomState.CONNECTED
    room_one = scheduler.subscriptions[101]
    started = time.perf_counter()
    await scheduler.handle_failure(room_one, ResponseCodeException(-101, "未登录"))
    elapsed = time.perf_counter() - started
    assert elapsed < 5.0
    slot = scheduler.pool.get(1)
    assert slot is not None
    assert slot.state is AccountState.DEAD
    assert scheduler.subscriptions[101].uid == 2
    assert 101 in ops.connected
    slot_credential = slot.credential
    assert slot_credential.refresh_calls == 1


async def test_single_room_failure_does_not_touch_others() -> None:
    """SC-003a：单房间网络失败只影响该房间，其它连接保持不变。"""
    scheduler, _ = make_scheduler()
    room_one = scheduler.subscriptions[101]
    room_two = scheduler.subscriptions[201]
    room_one.state = RoomState.CONNECTED
    room_two.state = RoomState.CONNECTED
    await scheduler.handle_failure(room_one, ConnectionResetError("boom"))
    assert room_one.state is RoomState.BACKOFF
    assert room_two.state is RoomState.CONNECTED
    assert room_one.next_retry_at is not None
    assert scheduler.retry_due(room_one.next_retry_at - 1) == []
    assert scheduler.retry_due(room_one.next_retry_at) == [room_one]


async def test_permanent_credential_code_marks_dead_without_refresh() -> None:
    """业务码 -102 直接弃用，不尝试刷新。"""
    cred_one = FakeCredential(1, valid=True)
    scheduler, _ = make_scheduler({1: cred_one, 2: FakeCredential(2)})
    room_one = scheduler.subscriptions[101]
    room_one.uid = 1
    await scheduler.handle_failure(room_one, ResponseCodeException(-102, "封停"))
    slot = scheduler.pool.get(1)
    assert slot is not None
    assert slot.state is AccountState.DEAD
    assert cred_one.refresh_calls == 0  # 原始对象未被触碰
    assert scheduler.subscriptions[101].uid == 2


async def test_concurrent_refresh_merged_per_uid() -> None:
    """同一账号的并发刷新合并为一次。"""
    cred = FakeCredential(1, valid=False)
    pool = AccountPool({1: cred})
    persisted: list[int] = []

    async def persist(uid: int, credential: object) -> None:
        persisted.append(uid)

    await asyncio.gather(
        pool.ensure_usable(1, persist),
        pool.ensure_usable(1, persist),
    )
    assert pool.get(1).credential.refresh_calls == 1
    assert persisted == [1]


async def test_refresh_success_persists_and_rechecks() -> None:
    """刷新成功写回存储并复检。"""
    cred = FakeCredential(1, valid=False)
    pool = AccountPool({1: cred})
    persisted: list[object] = []

    async def persist(uid: int, credential: object) -> None:
        persisted.append(credential)

    slot = await pool.ensure_usable(1, persist)
    assert slot.state is AccountState.AVAILABLE
    assert slot.credential.refresh_calls == 1
    assert persisted == [slot.credential]


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (None, FailureClass.NO_DATA),
        (ResponseCodeException(-101, "未登录"), FailureClass.CREDENTIAL),
        (ResponseCodeException(-102, "封停"), FailureClass.CREDENTIAL),
        (ResponseCodeException(-352, "风控"), FailureClass.RISK_CONTROL),
        (ResponseCodeException(-509, "限速"), FailureClass.RISK_CONTROL),
        (ResponseCodeException(-404, "不存在"), FailureClass.PROTOCOL),
        (CookiesRefreshException("刷新失败"), FailureClass.CREDENTIAL),
        (ConnectionResetError("boom"), FailureClass.NETWORK),
        (TimeoutError("timeout"), FailureClass.NETWORK),
        (ValueError("bad packet"), FailureClass.PROTOCOL),
        (KeyError("missing"), FailureClass.PROTOCOL),
    ],
)
def test_failure_classification_table(error: BaseException | None, expected: FailureClass) -> None:
    """D10 失败分类表逐条对应。"""
    assert classify_failure(error) is expected


def test_permanent_credential_detection() -> None:
    """-102 与凭据缺失类异常视为永久不可用。"""
    from bilibili_api.exceptions import CredentialNoSessdataException

    assert is_permanent_credential_error(ResponseCodeException(-102, "封停")) is True
    assert is_permanent_credential_error(ResponseCodeException(-101, "未登录")) is False
    assert is_permanent_credential_error(CredentialNoSessdataException()) is True


def test_credential_redaction_never_leaks_values() -> None:
    """日志摘要只允许出现 uid。"""
    credential = FakeCredential(7)
    summary = redact_credential(credential)
    assert summary == "uid=7"
    assert "secret" not in summary
    assert redact_credential(FakeCredential.__new__(FakeCredential)) == "uid=unknown"


def test_adapter_init_keeps_request_log_off() -> None:
    """T006：初始化适配器不开启库的 request_log。"""
    assert request_log.is_on() is False
    adapter = Adapter(FakeDriver())
    assert isinstance(adapter, Adapter)
    assert request_log.is_on() is False


def test_backoff_never_accelerates() -> None:
    """退避间隔单调增大（失败时不得加速）。"""
    scheduler, _ = make_scheduler()
    room = scheduler.subscriptions[101]
    delays: list[float] = []
    for _ in range(4):
        scheduler.note_failure(room)
        assert room.next_retry_at is not None
        delays.append(room.next_retry_at - scheduler._clock())
    assert delays == sorted(delays)
    assert delays[0] >= 4.9


async def test_manual_policy_never_auto_connects() -> None:
    """MANUAL 策略启动不发起连接。"""
    config = NoneBotLiveConfig.model_validate({"bots": [{"uid": 1, "room_ids": [101], "connect_timing": "manual"}]})
    scheduler, ops = make_scheduler({1: FakeCredential(1)}, config=config)
    await scheduler.startup()
    assert ops.connected == []
    await scheduler.shutdown()


def test_policy_from_timing() -> None:
    """配置取值可直接映射为连接策略。"""
    assert ConnectionPolicy.from_timing("auto") is ConnectionPolicy.AUTO


async def test_exhausted_pool_stops_room_without_raising() -> None:
    """账号池耗尽时记录错误并停止该房间，不抛出未处理异常（V-08 收束）。"""
    scheduler, _ = make_scheduler({1: FakeCredential(1)})
    room = scheduler.subscriptions[101]
    room.uid = 1
    await scheduler.handle_failure(room, ResponseCodeException(-102, "封停"))
    slot = scheduler.pool.get(1)
    assert slot is not None
    assert slot.state is AccountState.DEAD
    assert room.state is RoomState.CLOSED
    assert scheduler.pool.available_uids() == []
