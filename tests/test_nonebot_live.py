"""真实弹幕连接冒烟（集成层，只读，匿名优先；不发任何写操作）。"""

from __future__ import annotations

import asyncio
from contextlib import suppress

import pytest

from bilibili_api.live import LiveDanmaku, LiveRoom
from bilibili_api.utils.network import Credential

pytestmark = pytest.mark.integration

CANDIDATE_ROOMS = (6, 21452505, 544853)
"""候选直播间（只读）：用于找一个当前正在直播的房间。"""

NON_BUSINESS_EVENTS = frozenset({"ALL", "VIEW", "VERIFICATION_SUCCESSFUL"})
"""连接层事件；真实业务帧指其余 cmd。"""


async def _find_live_room() -> int | None:
    """
    在候选房间中找一个正在直播的房间。

    Returns:
        int | None: 真实房间号；候选均未开播时为 `None`。
    """
    for room_display_id in CANDIDATE_ROOMS:
        try:
            info = await LiveRoom(room_display_id=room_display_id, credential=Credential()).get_room_play_info()
        except Exception:
            continue
        if int(info.get("live_status", 0)) == 1:
            return int(info["room_id"])
        await asyncio.sleep(0.5)
    return None


async def test_real_danmaku_connection_receives_business_frame() -> None:
    """建立一次真实弹幕连接，收到至少一帧业务事件后主动断开。

    匿名连接可用（research D15），因此本用例不取 `credential` fixture、不声明
    `readonly`（WS 订阅不属于 GET 式读请求），也不声明 cred 层级。
    """
    room_id = await _find_live_room()
    if room_id is None:
        pytest.skip("候选房间当前均未开播，跳过真实弹幕冒烟")
    danmaku = LiveDanmaku(room_display_id=room_id, credential=Credential())
    seen: list[str] = []
    received = asyncio.Event()

    @danmaku.on("ALL")
    async def on_event(event: dict) -> None:  # type: ignore[type-arg]
        name = str(event.get("type", ""))
        seen.append(name)
        if name not in NON_BUSINESS_EVENTS:
            received.set()

    task = asyncio.create_task(danmaku.connect())
    try:
        await asyncio.wait_for(received.wait(), timeout=90)
    finally:
        if danmaku.get_status() == LiveDanmaku.STATUS_ESTABLISHED:
            await danmaku.disconnect()
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task
    business = [name for name in seen if name not in NON_BUSINESS_EVENTS]
    assert business, f"未收到业务事件，仅收到连接层事件：{seen}"
