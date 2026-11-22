"""公共符号与事件取值语义的离线测试（T017 / contracts/adapter-public-api.md）。"""

from __future__ import annotations

import pytest

from bilibili_api.exceptions import ArgsException
import bilibili_api.nonebot.adapters.bilibili_live as impl
from bilibili_api.nonebot.adapters.bilibili_live.bot import OpenBot, WebBot
from bilibili_api.nonebot.adapters.bilibili_live.event import (
    DanmakuEvent,
    HeartbeatEvent,
    SuperChatEvent,
    UserEnterEvent,
)
from bilibili_api.nonebot.adapters.bilibili_live.message import Message, MessageSegment
import nonebot.adapters.bilibili_live as compat

EVENT_CLASSES = [
    "AreaRankChangedEvent",
    "ChangeRoomInfoEvent",
    "DanmakuEvent",
    "GiftStarProcessEvent",
    "GuardBuyEvent",
    "GuardBuyToastEvent",
    "HeartbeatEvent",
    "HotRankChangedEvent",
    "HotRankSettlementEvent",
    "InteractionDanmaku",
    "InteractionFollow",
    "InteractionGift",
    "InteractionLike",
    "InteractionShare",
    "InteractionVote",
    "LikeEvent",
    "LikeInfoUpdateEvent",
    "OnlineRankCountEvent",
    "OnlineRankEvent",
    "OnlineRankTopEvent",
    "OpenLiveEndEvent",
    "OpenLiveStartEvent",
    "PopularRankChangedEvent",
    "RoomAdminEntranceEvent",
    "RoomAdminRevokeEvent",
    "RoomAdminsEvent",
    "RoomBlockMsgEvent",
    "RoomChangeEvent",
    "RoomRealTimeMessageUpdateEvent",
    "RoomSilentOffEvent",
    "RoomSilentOnEvent",
    "RoomSkinMsgEvent",
    "SendGiftEvent",
    "SpecialGiftEvent",
    "StopLiveRoomListEvent",
    "SuperChatEvent",
    "UserEnterEvent",
    "UserFollowEvent",
    "UserShareEvent",
    "WatchedChangeEvent",
    "WebLiveStartEvent",
]

BASE_CLASSES = ["Event", "MessageEvent", "NoticeEvent", "MetaEvent", "WebOnlyEvent", "OpenplatformOnlyEvent"]

MODEL_CLASSES = [
    "AdminLevel",
    "Badge",
    "BatchComboSend",
    "BlindGift",
    "ComboInfo",
    "DanmakuCombo",
    "Frame",
    "Game",
    "Gender",
    "GuardLevel",
    "LiveStatus",
    "MasterData",
    "MasterExp",
    "MasterInfo",
    "MasterLevel",
    "Medal",
    "NewPendants",
    "OfficialVerify",
    "OfficialVerifyType",
    "Rank",
    "RankChangeMsg",
    "Room",
    "RoomNews",
    "SilentUser",
    "SilentUserListData",
    "SpecialGift",
    "StudioInfo",
    "User",
    "UserRoomStatus",
    "VoteCombo",
    "VoteOption",
]

EXCEPTION_CLASSES = ["AdapterException", "ActionFailed", "ApiNotAvailable", "NetworkError"]


def test_public_symbols() -> None:
    """SC-001：公共符号 100% 可导入且名称一致。"""
    symbols = EVENT_CLASSES + BASE_CLASSES + MODEL_CLASSES + EXCEPTION_CLASSES
    symbols += ["Adapter", "WebBot", "OpenBot", "Message", "MessageSegment"]
    missing = [name for name in symbols if not hasattr(compat, name)]
    assert missing == []
    impl_missing = [name for name in symbols if not hasattr(impl, name)]
    assert impl_missing == []
    assert len(EVENT_CLASSES) == 41
    assert len(BASE_CLASSES) == 6
    assert len(MODEL_CLASSES) == 31


def test_two_import_paths_share_objects() -> None:
    """两条导入路径取到同一批对象（`is` 为真）。"""
    for name in EVENT_CLASSES + MODEL_CLASSES + EXCEPTION_CLASSES + ["Adapter", "WebBot", "OpenBot", "Message"]:
        assert getattr(compat, name) is getattr(impl, name), name


def test_message_segments() -> None:
    """消息与消息段基本行为。"""
    message = Message("hi") + MessageSegment.at(123)
    assert message[0].is_text()
    assert str(MessageSegment.at(123)) == "<at:123>"
    assert str(MessageSegment.emoticon("doge")) == "<emoticon:doge>"


def test_open_bot_rejected() -> None:
    """FR-018：OpenBot 实例化即抛明确错误。"""
    with pytest.raises(ArgsException) as excinfo:
        OpenBot(object(), "1")
    assert "开放平台形态尚未支持" in str(excinfo.value)


def test_event_value_semantics() -> None:
    """事件取值方法：user_id / session_id / event_name / is_tome。"""
    import json

    extra = json.dumps(
        {"emots": None, "send_from_me": False, "reply_mid": 0, "reply_uname": "", "reply_uname_color": ""}
    )
    danmaku = DanmakuEvent.model_validate(
        {
            "cmd": "DANMU_MSG:4:0:2:2:1",
            "room_id": 999,
            "info": [
                [
                    0,
                    1,
                    25,
                    0,
                    1700000000000,
                    0,
                    0,
                    "",
                    0,
                    0,
                    0,
                    "",
                    0,
                    None,
                    {"text": "x"},
                    {
                        "extra": extra,
                        "user": {"uid": 123, "base": {"face": "f", "name": "user", "name_color": 0}, "medal": None},
                    },
                ],
                "hello",
            ],
        }
    )
    assert danmaku.get_user_id() == "123"
    assert danmaku.get_session_id() == "999_123"
    assert danmaku.get_event_name() == "danmaku"
    assert danmaku.get_type() == "message"
    assert danmaku.is_tome() is False
    danmaku.to_me = True
    assert danmaku.is_tome() is True

    super_chat = SuperChatEvent.model_validate(
        {
            "cmd": "SUPER_CHAT_MESSAGE",
            "room_id": 999,
            "data": {
                "id": 1,
                "uid": 456,
                "user_info": {"face": "f", "uname": "user", "name_color": 0},
                "message": "sc",
                "price": 30,
                "start_time": 1,
                "end_time": 2,
                "medal_info": None,
            },
        }
    )
    assert super_chat.get_session_id() == "999_456_1"
    assert super_chat.get_event_name() == "super_chat"

    enter = UserEnterEvent.model_validate(
        {
            "cmd": "INTERACT_WORD",
            "room_id": 999,
            "data": {
                "msg_type": 1,
                "timestamp": 1,
                "trigger_time": 1,
                "uid": 7,
                "uname": "u",
                "uname_color": "",
                "fans_medal": None,
            },
        }
    )
    assert enter.get_user_id() == "7"
    assert enter.get_event_name() == "user_enter"
    with pytest.raises(ValueError, match="no context"):
        enter.get_session_id()

    heartbeat = HeartbeatEvent(popularity=1, room_id=999)
    assert heartbeat.get_type() == "metaevent"
    assert heartbeat.get_event_name() == "heartbeat"


def test_web_bot_api_whitelist() -> None:
    """`_call_api` 只分发公共属性；私有名抛 ApiNotAvailable。"""
    import asyncio

    from bilibili_api.nonebot.adapters.bilibili_live.exception import ApiNotAvailable

    async def run() -> None:
        adapter = impl.Adapter.__new__(impl.Adapter)
        bot = WebBot(adapter, self_id="1")
        with pytest.raises(ApiNotAvailable):
            await impl.Adapter._call_api(adapter, bot, "_private")
        with pytest.raises(ApiNotAvailable):
            await impl.Adapter._call_api(adapter, bot, "not_exists")

    asyncio.run(run())
