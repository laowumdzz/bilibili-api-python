"""LiveDanmaku 心跳定时的离线行为用例（虚拟时钟，不触网、无凭据）。

用可注入的虚拟时钟锁定心跳的核心语义：
1. WebSocket 心跳连接后立即发送首次心跳包，收到心跳响应后约 30 秒发送下一次；
2. 超时窗口内收到心跳响应则不触发 TIMEOUT；
3. 发出心跳包后 30 秒窗口内无响应，触发 TIMEOUT 事件且心跳任务退出；
4. Web 端心跳连接后立即发送，此后每 60 秒发送一次。

这些用例与定时实现细节无关（无论是每秒递减计数器还是截止时间式一次性定时），
只约束可观测行为：心跳发送时刻、超时窗口长度与事件触发。
"""

import asyncio
import struct

import pytest

from bilibili_api import live as live_module
from bilibili_api.live import LiveDanmaku


class FakeClock:
    """虚拟时钟：接管 ``asyncio.sleep``，由测试显式推进时间并唤醒到期的等待者。

    心跳任务调用 ``asyncio.sleep(delay)`` 时会挂起，直到测试调用
    ``advance_to`` / ``pump_until`` 把虚拟时间推进到其唤醒时刻才被唤醒，
    从而精确控制“响应到达时刻”与“超时判定时刻”的相对关系。
    """

    def __init__(self) -> None:
        self.now = 1000.0
        self._sleepers: list[tuple[float, asyncio.Future]] = []
        self._real_sleep = asyncio.sleep

    async def sleep(self, delay: float) -> None:
        """``asyncio.sleep`` 替身：挂起到虚拟时间推进至唤醒时刻。"""
        if delay <= 0:
            await self._real_sleep(0)
            return
        wake_at = self.now + delay
        fut = asyncio.get_running_loop().create_future()
        self._sleepers.append((wake_at, fut))
        self._sleepers.sort(key=lambda item: item[0])
        await fut

    def advance_to(self, target: float) -> None:
        """把虚拟时间推进到 target，并唤醒所有唤醒时刻已到的等待者。"""
        if target > self.now:
            self.now = target
        ready = [fut for wake_at, fut in self._sleepers if wake_at <= self.now]
        self._sleepers = [(wake_at, fut) for wake_at, fut in self._sleepers if wake_at > self.now]
        for fut in ready:
            if not fut.done():
                fut.set_result(None)

    async def pump_until(self, cond, max_steps: int = 5000) -> bool:
        """反复“唤醒最早到期的等待者 → 让出控制权”，直到条件成立。

        Args:
            cond      (Callable)  : 返回 bool 的无参条件函数。
            max_steps (int)       : 最大推进步数，防止实现缺陷导致死循环。

        Returns:
            bool: 条件是否在步数上限内成立。
        """
        for _ in range(max_steps):
            if cond():
                return True
            if self._sleepers:
                self.advance_to(self._sleepers[0][0])
            await self._real_sleep(0)
        return cond()


@pytest.fixture
async def clock(monkeypatch):
    """注入虚拟时钟：替换 asyncio.sleep 与事件循环的 time()。"""
    fake_clock = FakeClock()
    loop = asyncio.get_running_loop()
    monkeypatch.setattr(loop, "time", lambda: fake_clock.now)
    monkeypatch.setattr(asyncio, "sleep", fake_clock.sleep)
    return fake_clock


class FakeWsClient:
    """记录心跳包发送时刻（虚拟时间）的假请求客户端。"""

    def __init__(self, clock: FakeClock) -> None:
        self._clock = clock
        self.sends: list[tuple[float, bytes]] = []

    async def ws_send(self, ws, data: bytes) -> None:
        self.sends.append((self._clock.now, data))


class FakeApi:
    """假 Api：记录 Web 端心跳请求发起时刻（虚拟时间），不发起真实网络请求。"""

    call_times: list[float] = []
    _clock: FakeClock | None = None

    def __init__(self, *args, **kwargs) -> None:
        assert FakeApi._clock is not None
        FakeApi.call_times.append(FakeApi._clock.now)

    def update_params(self, **kwargs) -> "FakeApi":
        return self

    @property
    def result(self):
        return self._noop()

    @staticmethod
    async def _noop() -> dict:
        return {"code": 0}


def build_heartbeat_response_packet(view: int = 233) -> bytes:
    """手工构造一个心跳响应数据包（协议版本 1 / 数据包类型 3）。

    不使用 ``LiveDanmaku.pack`` 构造，因为其校验不允许响应类数据包类型。
    """
    body = struct.pack(">I", view)
    header = struct.pack(
        ">IHHII",
        16 + len(body),
        0,
        LiveDanmaku.PROTOCOL_VERSION_HEARTBEAT,
        LiveDanmaku.DATAPACK_TYPE_HEARTBEAT_RESPONSE,
        1,
    )
    return header + body


def make_danmaku(clock: FakeClock) -> LiveDanmaku:
    """构造未真正连接网络的 LiveDanmaku，并注入假 WebSocket 客户端。"""
    danmaku = LiveDanmaku(room_display_id=1)
    danmaku._LiveDanmaku__room_real_id = 1  # type: ignore[attr-defined]
    danmaku._LiveDanmaku__ws = object()  # type: ignore[attr-defined]
    danmaku._LiveDanmaku__client = FakeWsClient(clock)  # type: ignore[attr-defined]
    return danmaku


async def receive_heartbeat_response(danmaku: LiveDanmaku) -> None:
    """模拟服务端心跳响应到达（走真实的数据包处理路径）。"""
    await danmaku._LiveDanmaku__handle_data(build_heartbeat_response_packet())  # type: ignore[attr-defined]


async def test_ws_heartbeat_sent_immediately_and_periodically(clock):
    """心跳连接后立即发送首次心跳包；每次收到响应后约 30 秒发送下一次。"""
    danmaku = make_danmaku(clock)
    # 模拟连接建立时的计时器重置（原实现依赖该状态立即发送首次心跳）
    danmaku._LiveDanmaku__heartbeat_timer = 0  # type: ignore[attr-defined]
    danmaku._LiveDanmaku__heartbeat_timer_web = 0  # type: ignore[attr-defined]
    client = danmaku._LiveDanmaku__client  # type: ignore[attr-defined]

    task = asyncio.create_task(danmaku._LiveDanmaku__heartbeat())  # type: ignore[attr-defined]
    try:
        assert await clock.pump_until(lambda: len(client.sends) >= 1), "应立即发送首次心跳包"
        first_send_at = client.sends[0][0]
        assert first_send_at == pytest.approx(clock.now, abs=1.0)

        # 首次心跳立刻收到响应 → 下一次心跳应在响应后约 30 秒
        await receive_heartbeat_response(danmaku)
        assert await clock.pump_until(lambda: len(client.sends) >= 2), "收到响应后约 30 秒应发送第二次心跳"
        assert client.sends[1][0] - first_send_at == pytest.approx(30.0, abs=1.0)

        # 再次响应 → 第三次心跳继续按 30 秒周期发送
        await receive_heartbeat_response(danmaku)
        assert await clock.pump_until(lambda: len(client.sends) >= 3), "心跳应按周期持续发送"
        assert client.sends[2][0] - first_send_at == pytest.approx(60.0, abs=1.0)

        # 心跳包内容固定且非空
        assert all(data == client.sends[0][1] and data for _, data in client.sends)
    finally:
        task.cancel()
        try:
            await task
        except (asyncio.CancelledError, Exception):
            pass


async def test_ws_heartbeat_response_within_window_prevents_timeout(clock):
    """超时窗口内收到心跳响应则不触发 TIMEOUT，且下一次心跳以响应时刻重新计时。"""
    danmaku = make_danmaku(clock)
    danmaku._LiveDanmaku__heartbeat_timer = 0  # type: ignore[attr-defined]
    client = danmaku._LiveDanmaku__client  # type: ignore[attr-defined]

    timed_out = []

    async def on_timeout(data):
        timed_out.append(clock.now)

    danmaku.add_event_listener("TIMEOUT", on_timeout)

    task = asyncio.create_task(danmaku._LiveDanmaku__heartbeat())  # type: ignore[attr-defined]
    try:
        assert await clock.pump_until(lambda: len(client.sends) >= 1)
        first_send_at = client.sends[0][0]
        # 等待心跳任务进入等待状态（注册唤醒目标）
        assert await clock.pump_until(lambda: clock._sleepers)

        # 把时钟推进到发送后 1 秒（未越过心跳任务的唤醒点），再模拟响应到达（仍在 30 秒窗口内）
        clock.advance_to(first_send_at + 1)
        await receive_heartbeat_response(danmaku)

        # 推进远超原超时窗口：不应触发 TIMEOUT，且下一次心跳按响应时刻重新计时
        assert await clock.pump_until(lambda: len(client.sends) >= 2), "窗口内响应后应继续发送下一次心跳"
        assert timed_out == [], "窗口内收到响应不应触发 TIMEOUT"
        second_send_at = client.sends[1][0]
        assert second_send_at - first_send_at == pytest.approx(31.0, abs=1.5)
        assert not task.done(), "心跳任务不应退出"
    finally:
        task.cancel()
        try:
            await task
        except (asyncio.CancelledError, Exception):
            pass


async def test_ws_heartbeat_timeout_dispatched_without_response(clock):
    """发出心跳后 30 秒窗口内无响应：触发 TIMEOUT 事件且心跳任务退出。"""
    danmaku = make_danmaku(clock)
    danmaku._LiveDanmaku__heartbeat_timer = 0  # type: ignore[attr-defined]
    client = danmaku._LiveDanmaku__client  # type: ignore[attr-defined]

    timed_out = []

    async def on_timeout(data):
        timed_out.append(clock.now)

    danmaku.add_event_listener("TIMEOUT", on_timeout)

    task = asyncio.create_task(danmaku._LiveDanmaku__heartbeat())  # type: ignore[attr-defined]
    assert await clock.pump_until(lambda: len(client.sends) >= 1)
    first_send_at = client.sends[0][0]

    # 不发送任何响应，推进直至超时判定
    assert await clock.pump_until(lambda: timed_out), "30 秒无响应应触发 TIMEOUT 事件"
    assert len(timed_out) == 1
    assert timed_out[0] - first_send_at == pytest.approx(30.0, abs=1.0)
    # 超时后心跳任务应退出，且窗口内未重复发送心跳包
    assert await clock.pump_until(lambda: task.done())
    assert len(client.sends) == 1


async def test_web_heartbeat_sent_immediately_and_every_60s(clock, monkeypatch):
    """Web 端心跳连接后立即发送，此后每 60 秒发送一次。"""
    FakeApi.call_times = []
    FakeApi._clock = clock
    monkeypatch.setattr(live_module, "Api", FakeApi)

    danmaku = make_danmaku(clock)
    danmaku._LiveDanmaku__heartbeat_timer_web = 0  # type: ignore[attr-defined]

    task = asyncio.create_task(danmaku._LiveDanmaku__heartbeat_web())  # type: ignore[attr-defined]
    try:
        assert await clock.pump_until(lambda: len(FakeApi.call_times) >= 1), "应立即发送首次 Web 心跳"
        first_at = FakeApi.call_times[0]
        assert first_at == pytest.approx(clock.now, abs=1.0)

        assert await clock.pump_until(lambda: len(FakeApi.call_times) >= 2), "约 60 秒后应发送第二次 Web 心跳"
        assert FakeApi.call_times[1] - first_at == pytest.approx(60.0, abs=1.0)

        assert await clock.pump_until(lambda: len(FakeApi.call_times) >= 3), "Web 心跳应按 60 秒周期持续发送"
        assert FakeApi.call_times[2] - first_at == pytest.approx(120.0, abs=1.0)
    finally:
        task.cancel()
        try:
            await task
        except (asyncio.CancelledError, Exception):
            pass
