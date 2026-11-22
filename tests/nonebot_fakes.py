"""NoneBot 适配器离线测试共用的假对象（驱动 / WebSocket / 凭据 / 调度动作）。"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
import copy
import logging
from typing import Any

from nonebot.drivers import Driver, HTTPClientMixin, Request, Response, WebSocketClientMixin
from nonebot.internal.driver._lifespan import Lifespan


class FakeWebSocket:
    """按队列返回消息的假 WebSocket。"""

    def __init__(self, messages: list[Any] | None = None) -> None:
        self.messages: list[Any] = list(messages or [])
        self.sent: list[bytes] = []
        self.closed = False
        self.close_code: int | None = None
        self.receive_started = asyncio.Event()

    async def receive(self) -> str | bytes:
        self.receive_started.set()
        if not self.messages:
            await asyncio.sleep(3600)
            raise AssertionError("unreachable")
        item = self.messages.pop(0)
        if isinstance(item, BaseException):
            raise item
        return item

    async def send_bytes(self, data: bytes) -> None:
        self.sent.append(data)

    async def close(self, code: int = 1000, reason: str = "") -> None:
        self.close_code = code
        self.closed = True


class FakeDriver(Driver, HTTPClientMixin, WebSocketClientMixin):
    """同时实现 HTTP 与 WebSocket 能力的假驱动。"""

    type = "fake-driver"

    def __init__(self) -> None:
        self.responses: list[Response | BaseException] = []
        self.requests: list[Request] = []
        self.websockets: list[FakeWebSocket] = []
        self.stream_chunks: list[bytes] = []
        self.stream_headers: list[tuple[str, str]] = []
        self.stream_closed = False
        self._lifespan = Lifespan()
        self._bots: dict[str, object] = {}

    @property
    def logger(self) -> logging.Logger:
        return logging.getLogger("fake-driver")

    async def run(self) -> None:
        return None

    def get_session(self) -> object:
        return self

    async def request(self, setup: Request) -> Response:
        self.requests.append(setup)
        item = self.responses.pop(0)
        if isinstance(item, BaseException):
            raise item
        return item

    async def stream_request(self, setup: Request, *, chunk_size: int = 1024) -> AsyncGenerator[Response, None]:
        self.requests.append(setup)
        try:
            for index, chunk in enumerate(self.stream_chunks):
                headers = self.stream_headers if index == 0 else []
                yield Response(200, headers=headers, content=chunk, request=setup)
        finally:
            self.stream_closed = True

    @asynccontextmanager
    async def websocket(self, setup: Request) -> AsyncGenerator[FakeWebSocket, None]:
        self.requests.append(setup)
        websocket = self.websockets.pop(0)
        yield websocket


class HttpOnlyDriver(Driver, HTTPClientMixin):
    """只实现 HTTP 的假驱动（模拟纯 httpx 驱动）。"""

    type = "http-only"

    def __init__(self) -> None:
        self.requests: list[Request] = []
        self._lifespan = Lifespan()
        self._bots: dict[str, object] = {}

    @property
    def logger(self) -> logging.Logger:
        return logging.getLogger("http-only")

    async def run(self) -> None:
        return None

    def get_session(self) -> object:
        return self

    async def request(self, setup: Request) -> Response:
        self.requests.append(setup)
        return Response(200, content=b"{}")

    async def stream_request(self, setup: Request, *, chunk_size: int = 1024) -> AsyncGenerator[Response, None]:
        yield Response(200, content=b"")


class FakeCredential:
    """可按脚本失效 / 刷新成功或失败的假凭据。"""

    def __init__(
        self,
        uid: int,
        *,
        valid: bool = True,
        refresh_error: BaseException | None = None,
        after_refresh_valid: bool = True,
    ) -> None:
        self.dedeuserid = str(uid)
        self.sessdata = f"secret-sessdata-{uid}"
        self.bili_jct = f"secret-jct-{uid}"
        self.valid = valid
        self.refresh_error = refresh_error
        self.after_refresh_valid = after_refresh_valid
        self.refresh_calls = 0
        self.check_calls = 0

    async def check_valid(self) -> bool:
        self.check_calls += 1
        await asyncio.sleep(0)
        return self.valid

    async def refresh(self) -> None:
        self.refresh_calls += 1
        await asyncio.sleep(0)
        if self.refresh_error is not None:
            raise self.refresh_error
        self.valid = self.after_refresh_valid

    def model_copy(self, deep: bool = False) -> FakeCredential:
        clone = FakeCredential(
            int(self.dedeuserid),
            valid=self.valid,
            refresh_error=self.refresh_error,
            after_refresh_valid=self.after_refresh_valid,
        )
        return copy.deepcopy(clone) if deep else clone

    def get_cookies(self) -> dict[str, str]:
        return {"SESSDATA": self.sessdata, "bili_jct": self.bili_jct, "DedeUserID": self.dedeuserid}

    def __str__(self) -> str:
        return f"FakeCredential({self.dedeuserid})"


class FakeOps:
    """调度器外部动作的假实现。"""

    def __init__(self) -> None:
        self.connected: list[int] = []
        self.disconnected: list[int] = []
        self.concurrent = 0
        self.peak = 0
        self.status: dict[int, int] = {}
        self.connect_error: BaseException | None = None
        self.connect_delay = 0.0
        self.status_error: BaseException | None = None
        self.status_calls: list[int] = []

    async def connect(self, subscription: Any) -> None:
        self.concurrent += 1
        self.peak = max(self.peak, self.concurrent)
        try:
            if self.connect_delay:
                await asyncio.sleep(self.connect_delay)
            if self.connect_error is not None:
                error = self.connect_error
                self.connect_error = None
                raise error
            self.connected.append(subscription.room_display_id)
        finally:
            self.concurrent -= 1

    async def disconnect(self, subscription: Any) -> None:
        self.disconnected.append(subscription.room_display_id)

    async def live_status(self, room_display_id: int) -> int:
        self.status_calls.append(room_display_id)
        if self.status_error is not None:
            error = self.status_error
            self.status_error = None
            raise error
        return self.status.get(room_display_id, 0)


class FakeStore:
    """只实现读取接口的假凭据存储。"""

    def __init__(self, credentials: dict[int, Any]) -> None:
        self.credentials = credentials

    async def get_all_uids(self) -> list[int]:
        return list(self.credentials)

    async def get_credential(self, uid: int) -> Any:
        return self.credentials.get(uid)
