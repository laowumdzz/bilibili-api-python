"""帧回放与三处缺陷回归的离线测试（T019 / T058 / SC-002 / SC-009 / SC-010）。"""

from __future__ import annotations

import json
import pathlib
import time

import pytest

from bilibili_api.nonebot.adapters.bilibili_live.adapter import Adapter
from bilibili_api.nonebot.adapters.bilibili_live.bot import WebBot
from bilibili_api.nonebot.adapters.bilibili_live.event import packet_to_event
from bilibili_api.nonebot.adapters.bilibili_live.models.event import Medal
from bilibili_api.nonebot.adapters.bilibili_live.packet import OpCode, Packet, ProtocolVersion
from bilibili_api.nonebot.adapters.bilibili_live.scheduler import RoomSubscription
from tests.nonebot_fakes import FakeDriver

FIXTURE_DIR = pathlib.Path(__file__).parent / "fixtures" / "nonebot_frames"
RECORDED_DIR = FIXTURE_DIR / "recorded"
ROOM_ID = 999

# (fixture 文件, 行号, 事件类名, 关键字段快照)
EXPECTATIONS: list[tuple[str, int, str, dict[str, object]]] = [
    ("AREA_RANK_CHANGED", 0, "AreaRankChangedEvent", {"rank": 1, "rank_name": "r"}),
    ("CHANGE_ROOM_INFO", 0, "ChangeRoomInfoEvent", {"background": "bg"}),
    ("DANMU_MSG", 0, "DanmakuEvent", {"content": "hello world", "sender.uid": 123}),
    ("DM_INTERACTION", 0, "InteractionVote", {"type": 101, "question": "q"}),
    ("DM_INTERACTION", 1, "InteractionDanmaku", {"type": 102}),
    ("DM_INTERACTION", 2, "InteractionFollow", {"type": 103, "cnt": 1}),
    ("DM_INTERACTION", 3, "InteractionGift", {"type": 104, "gift_id": 1}),
    ("DM_INTERACTION", 4, "InteractionShare", {"type": 105}),
    ("DM_INTERACTION", 5, "InteractionLike", {"type": 106}),
    ("GIFT_STAR_PROCESS", 0, "GiftStarProcessEvent", {"tip": "star"}),
    ("GUARD_BUY", 0, "GuardBuyEvent", {"uid": 9, "gift_name": "舰长"}),
    ("HEARTBEAT", 0, "HeartbeatEvent", {"popularity": 1234}),
    ("HOT_RANK_CHANGED", 0, "HotRankChangedEvent", {"rank": 1, "area_name": "a"}),
    ("HOT_RANK_CHANGED_V2", 0, "HotRankChangedEvent", {"rank": 1}),
    ("HOT_RANK_SETTLEMENT", 0, "HotRankSettlementEvent", {"uname": "u", "rank": 1}),
    ("HOT_RANK_SETTLEMENT_V2", 0, "HotRankSettlementEvent", {"uname": "u"}),
    ("INTERACT_WORD", 0, "UserEnterEvent", {"uid": 7, "msg_type": 1}),
    ("INTERACT_WORD", 1, "UserFollowEvent", {"uid": 7, "msg_type": 2}),
    ("INTERACT_WORD", 2, "UserShareEvent", {"uid": 7, "msg_type": 3}),
    ("INTERACT_WORD_V2", 0, "UserEnterEvent", {"uid": 21, "msg_type": "1"}),
    ("INTERACT_WORD_V2", 1, "UserFollowEvent", {"uid": 22, "msg_type": "2"}),
    ("INTERACT_WORD_V2", 2, "UserShareEvent", {"uid": 23, "msg_type": "3"}),
    ("LIKE_INFO_V3_CLICK", 0, "LikeEvent", {"uname": "liker", "uid": 12}),
    ("LIKE_INFO_V3_UPDATE", 0, "LikeInfoUpdateEvent", {"click_count": 100}),
    ("LIVE", 0, "WebLiveStartEvent", {"live_platform": "web"}),
    ("LIVE_OPEN_PLATFORM_LIVE_END", 0, "OpenLiveEndEvent", {"area_name": "area"}),
    ("LIVE_OPEN_PLATFORM_LIVE_START", 0, "OpenLiveStartEvent", {"area_name": "area"}),
    ("ONLINE_RANK_COUNT", 0, "OnlineRankCountEvent", {"count": 10}),
    ("ONLINE_RANK_TOP3", 0, "OnlineRankTopEvent", {"top.0.msg": "m"}),
    ("ONLINE_RANK_V2", 0, "OnlineRankEvent", {"rank_type": "gold", "online_list.0.uname": "u"}),
    ("ONLINE_RANK_V3", 0, "OnlineRankEvent", {"rank_type": "gold", "online_list.0.uname": "u"}),
    ("POPULAR_RANK_CHANGED", 0, "PopularRankChangedEvent", {"rank": 1, "uid": 1}),
    ("room_admin_entrance", 0, "RoomAdminEntranceEvent", {"uid": 14}),
    ("ROOM_ADMIN_REVOKE", 0, "RoomAdminRevokeEvent", {"uid": 15}),
    ("ROOM_ADMINS", 0, "RoomAdminsEvent", {"uids": [1, 2]}),
    ("ROOM_BLOCK_MSG", 0, "RoomBlockMsgEvent", {"uname": "blocked", "uid": 13}),
    ("ROOM_CHANGE", 0, "RoomChangeEvent", {"title": "t", "live_key": "k"}),
    ("ROOM_REAL_TIME_MESSAGE_UPDATE", 0, "RoomRealTimeMessageUpdateEvent", {"fans": 1, "fans_club": 2}),
    ("ROOM_SILENT_OFF", 0, "RoomSilentOffEvent", {"level": 1}),
    ("ROOM_SILENT_ON", 0, "RoomSilentOnEvent", {"second": 60}),
    ("ROOM_SKIN_MSG", 0, "RoomSkinMsgEvent", {"skin_id": 1}),
    ("SEND_GIFT", 0, "SendGiftEvent", {"gift_name": "辣条", "num": 2}),
    ("SPECIAL_GIFT", 0, "SpecialGiftEvent", {"gifts.gift.action": "start"}),
    ("STOP_LIVE_ROOM_LIST", 0, "StopLiveRoomListEvent", {"room_id_list": [1, 2]}),
    ("SUPER_CHAT_MESSAGE", 0, "SuperChatEvent", {"id": 42, "price": 30}),
    ("SUPER_CHAT_MESSAGE_JPN", 0, "SuperChatEvent", {"id": 43, "price": 50, "message_jpn": "sc jp trans"}),
    ("USER_TOAST_MSG", 0, "GuardBuyToastEvent", {"toast_msg": "toast"}),
    ("WATCHED_CHANGE", 0, "WatchedChangeEvent", {"num": 1000}),
]

EVENT_CLASSES = [expectation[2] for expectation in EXPECTATIONS]

# 第二组样本：2026-11-22 房间 6（7734200）与房间 21452505 只读录制后人工脱敏
# （见 recorded/README.md）；(fixture 文件, 事件类名, 关键字段快照)
RECORDED_EXPECTATIONS: list[tuple[str, str, dict[str, object]]] = [
    ("DANMU_MSG", "DanmakuEvent", {"content": "recorded hello", "sender.uid": 123, "sender.name": "user"}),
    ("LIKE_INFO_V3_CLICK", "LikeEvent", {"uname": "user", "uid": 2, "like_text": "为主播点赞了"}),
    ("LIKE_INFO_V3_UPDATE", "LikeInfoUpdateEvent", {"click_count": 30411629}),
    ("ONLINE_RANK_COUNT", "OnlineRankCountEvent", {"count": 1044}),
    ("POPULAR_RANK_CHANGED", "PopularRankChangedEvent", {"rank": 0, "uid": 1}),
    ("ROOM_REAL_TIME_MESSAGE_UPDATE", "RoomRealTimeMessageUpdateEvent", {"fans": 18193849, "fans_club": 826}),
    ("STOP_LIVE_ROOM_LIST", "StopLiveRoomListEvent", {"room_id_list": [1722167807, 1741631397, 22473142]}),
    ("WATCHED_CHANGE", "WatchedChangeEvent", {"num": 355421029, "text_large": "35542.1万人看过"}),
]

UNMODELLED_RECORDED: tuple[str, ...] = ("ENTRY_EFFECT", "HOT_ROOM_NOTIFY", "LOG_IN_NOTICE", "POPULARITY_CHANGE")
"""真实流量中出现、但上游 0.2.6 事件层未建模的 `cmd`。"""


def load_recorded_frame(stem: str) -> dict:
    """
    读取 `recorded/` 目录内某 `cmd` 的首帧。

    Args:
        stem (str): 文件名（不含扩展名）。

    Returns:
        dict: 帧 JSON。
    """
    lines = [
        json.loads(line) for line in (RECORDED_DIR / f"{stem}.jsonl").read_text(encoding="utf-8").splitlines() if line
    ]
    return lines[0]


def load_frame(stem: str, index: int) -> dict:
    """
    读取指定 cmd 文件的第 `index` 帧。

    Args:
        stem (str): 文件名（不含扩展名）。
        index (int): 行号。

    Returns:
        dict: 帧 JSON。
    """
    lines = [
        json.loads(line) for line in (FIXTURE_DIR / f"{stem}.jsonl").read_text(encoding="utf-8").splitlines() if line
    ]
    return lines[index]


def make_packet(stem: str, frame: dict) -> Packet:
    """
    把帧包装成协议帧（心跳走 opcode=3 的二进制载荷）。

    Args:
        stem (str): 文件名。
        frame (dict): 帧 JSON。

    Returns:
        Packet: 协议帧。
    """
    if stem == "HEARTBEAT":
        popularity = int(frame["popularity"])
        return Packet(
            length=20,
            header_length=16,
            protocol_version=ProtocolVersion.Normal,
            opcode=OpCode.HeartbeatReply,
            seq=0,
            payload=popularity.to_bytes(4, "big"),
        )
    return Packet.from_bytes(Packet.new(OpCode.Command, 0, frame).to_bytes())


def read_path(value: object, path: str) -> object:
    """
    按点号路径读取属性 / 索引。

    Args:
        value (object): 起始对象。
        path (str): 形如 `online_list.0.uname` 的路径。

    Returns:
        object: 读取结果。
    """
    current = value
    for part in path.split("."):
        if isinstance(current, list):
            current = current[int(part)]
        elif isinstance(current, dict):
            current = current[part]
        else:
            current = getattr(current, part)
    return current


@pytest.mark.parametrize(("stem", "index", "class_name", "snapshot"), EXPECTATIONS)
def test_frame_replay(stem: str, index: int, class_name: str, snapshot: dict[str, object]) -> None:
    """SC-002：固定帧样本回放的事件类型与关键字段与快照一致。"""
    event = packet_to_event(make_packet(stem, load_frame(stem, index)), room_id=ROOM_ID)
    assert type(event).__name__ == class_name
    assert event.room_id == ROOM_ID
    for path, expected in snapshot.items():
        assert read_path(event, path) == expected, f"{class_name}.{path}"


def test_all_41_event_classes_covered() -> None:
    """41 个可实例化事件类均有帧样本覆盖。"""
    assert len(EVENT_CLASSES) == 48  # 部分事件类由多个 cmd / 变体重复覆盖
    assert len(set(EVENT_CLASSES)) == 41


@pytest.mark.parametrize(("stem", "class_name", "snapshot"), RECORDED_EXPECTATIONS)
def test_recorded_frame_replay(stem: str, class_name: str, snapshot: dict[str, object]) -> None:
    """真实录制帧回放：事件类型与关键字段与快照一致（结构真实性校验）。"""
    frame = load_recorded_frame(stem)
    packet = Packet.from_bytes(Packet.new(OpCode.Command, 0, frame).to_bytes())
    event = packet_to_event(packet, room_id=ROOM_ID)
    assert type(event).__name__ == class_name
    for path, expected in snapshot.items():
        assert read_path(event, path) == expected, f"{class_name}.{path}"


def test_recorded_group_covers_recorded_commands() -> None:
    """第二组样本锁定清单：8 个已建模 cmd + 4 个未建模 cmd。"""
    assert [stem for stem, _, _ in RECORDED_EXPECTATIONS] == [
        "DANMU_MSG",
        "LIKE_INFO_V3_CLICK",
        "LIKE_INFO_V3_UPDATE",
        "ONLINE_RANK_COUNT",
        "POPULAR_RANK_CHANGED",
        "ROOM_REAL_TIME_MESSAGE_UPDATE",
        "STOP_LIVE_ROOM_LIST",
        "WATCHED_CHANGE",
    ]
    for stem in UNMODELLED_RECORDED:
        assert load_recorded_frame(stem)["cmd"] == stem


def test_recorded_web_danmaku_shape() -> None:
    """真实网页 DANMU_MSG：无顶层 `data`、`cmd` 无后缀、`info[0][15]` 内嵌 extra / user。"""
    frame = load_recorded_frame("DANMU_MSG")
    assert "data" not in frame
    assert frame["cmd"] == "DANMU_MSG"
    assert isinstance(frame["info"][0], list)
    assert isinstance(frame["info"][0][15], dict)
    assert "extra" in frame["info"][0][15]
    assert "user" in frame["info"][0][15]


async def test_recorded_unknown_commands_are_skipped() -> None:
    """真实流量中的未建模 cmd 只记录并跳过，不中断后续帧分发。"""
    adapter = Adapter(FakeDriver())
    bot = WebBot(adapter, self_id="1")
    adapter.bot_connect(bot)
    subscription = RoomSubscription(room_display_id=ROOM_ID, room_real_id=ROOM_ID, uid=1)
    delivered: list[str] = []

    async def fake_handle(event) -> None:  # type: ignore[no-untyped-def]
        delivered.append(type(event).__name__)

    bot._handle_event = fake_handle  # type: ignore[method-assign]
    for stem in (*UNMODELLED_RECORDED, "DANMU_MSG"):
        packet = Packet.new(OpCode.Command, 0, load_recorded_frame(stem))
        await adapter._handle_ws_message(subscription, packet.to_bytes())
    assert delivered == ["DanmakuEvent"]


def test_defect1_web_danmaku_without_top_level_data() -> None:
    """FR-010a 缺陷 1：网页 DANMU_MSG（无顶层 data）必须产出事件。"""
    frame = load_frame("DANMU_MSG", 0)
    assert "data" not in frame
    assert frame["cmd"].startswith("DANMU_MSG:")  # cmd 后缀归一
    event = packet_to_event(make_packet("DANMU_MSG", frame), room_id=ROOM_ID)
    assert type(event).__name__ == "DanmakuEvent"
    assert event.content == "hello world"
    assert event.get_session_id() == "999_123"


def test_defect2_super_chat_variants_no_key_error() -> None:
    """FR-010a 缺陷 2：中 / 日文醒目留言均不再触发 KeyError。"""
    for stem, expected_price in (("SUPER_CHAT_MESSAGE", 30), ("SUPER_CHAT_MESSAGE_JPN", 50)):
        event = packet_to_event(make_packet(stem, load_frame(stem, 0)), room_id=ROOM_ID)
        assert type(event).__name__ == "SuperChatEvent"
        assert event.price == expected_price


def test_defect3_medal_accepts_is_light_and_is_lighted() -> None:
    """FR-010a 缺陷 3：勋章双写法都接受，`is_lighted` 为规范别名。"""
    event = packet_to_event(make_packet("INTERACT_WORD", load_frame("INTERACT_WORD", 0)), room_id=ROOM_ID)
    medal = event.fans_medal
    assert medal is not None
    assert medal.is_light is True
    assert medal.model_dump(by_alias=True)["is_lighted"] is True
    by_name = Medal(name="m", level=1, is_light=True)
    by_alias = Medal.model_validate({"name": "m", "level": 1, "is_lighted": False})
    assert by_name.is_light is True
    assert by_alias.is_light is False


def test_unknown_command_raises_for_caller() -> None:
    """未知 cmd 由调用方捕获；解析函数本身明确报错。"""
    packet = Packet.from_bytes(
        Packet.new(OpCode.Command, 0, {"cmd": "UNKNOWN_CMD", "data": {}, "room_id": ROOM_ID}).to_bytes()
    )
    with pytest.raises(RuntimeError):
        packet_to_event(packet, room_id=ROOM_ID)


def test_open_platform_command_without_data_raises() -> None:
    """开放平台命令缺少 data 字段仍视为错误，但网页帧不再被误判。"""
    packet = Packet.from_bytes(
        Packet.new(OpCode.Command, 0, {"cmd": "LIVE_OPEN_PLATFORM_DM", "room_id": ROOM_ID}).to_bytes()
    )
    with pytest.raises(RuntimeError):
        packet_to_event(packet, room_id=ROOM_ID)


async def test_malformed_frame_skipped_and_next_frame_dispatched() -> None:
    """畸形帧只记录不中断：后续帧照常分发。"""
    adapter = Adapter(FakeDriver())
    bot = WebBot(adapter, self_id="1")
    adapter.bot_connect(bot)
    subscription = RoomSubscription(room_display_id=ROOM_ID, room_real_id=ROOM_ID, uid=1)
    delivered: list[str] = []

    async def fake_handle(event) -> None:  # type: ignore[no-untyped-def]
        delivered.append(type(event).__name__)
        if len(delivered) == 1:
            raise RuntimeError("handler failed")

    bot._handle_event = fake_handle  # type: ignore[method-assign]
    malformed = b"\x00\x00\x00\x0f" + b"\x00" * 11
    await adapter._handle_ws_message(subscription, malformed)
    assert delivered == []
    valid = Packet.new(OpCode.Command, 0, load_frame("DANMU_MSG", 0)).to_bytes()
    await adapter._handle_ws_message(subscription, valid)
    assert delivered == ["DanmakuEvent"]
    second = Packet.new(OpCode.Command, 0, load_frame("SUPER_CHAT_MESSAGE", 0)).to_bytes()
    await adapter._handle_ws_message(subscription, second)
    assert delivered == ["DanmakuEvent", "SuperChatEvent"]


def test_1000_frames_under_one_second_and_in_order() -> None:
    """SC-009：1000 帧回放 ≤ 1 秒，事件顺序与输入顺序一致。"""
    packets: list[tuple[Packet, str]] = []
    for repeat in range(1000):
        stem, index, class_name, _ = EXPECTATIONS[repeat % len(EXPECTATIONS)]
        packets.append((make_packet(stem, load_frame(stem, index)), class_name))
    started = time.perf_counter()
    produced = [type(packet_to_event(packet, room_id=ROOM_ID)).__name__ for packet, _ in packets]
    elapsed = time.perf_counter() - started
    assert elapsed < 1.0
    assert produced == [class_name for _, class_name in packets]
