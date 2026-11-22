"""弹幕帧编解码与畸形帧处理的离线测试（T012 / data-model.md §2.4）。"""

from __future__ import annotations

import base64
import json
import struct
import zlib

import brotli

from bilibili_api.nonebot.adapters.bilibili_live.event import packet_to_event
from bilibili_api.nonebot.adapters.bilibili_live.packet import (
    HEADER_LENGTH,
    OpCode,
    Packet,
    ProtocolVersion,
    new_auth_packet,
)


def make_header(length: int, header_length: int, version: int, opcode: int, seq: int) -> bytes:
    return struct.pack(">I2H2I", length, header_length, version, opcode, seq)


def test_roundtrip_json_packet() -> None:
    """JSON 帧序列化 / 反序列化一致。"""
    frame = {"cmd": "X", "data": {"a": 1}, "room_id": 999}
    packet = Packet.new(OpCode.Command, 7, frame)
    restored = Packet.from_bytes(packet.to_bytes())
    assert restored.length == packet.length
    assert restored.header_length == HEADER_LENGTH
    assert restored.protocol_version is ProtocolVersion.Normal
    assert restored.opcode is OpCode.Command
    assert restored.seq == 7
    assert restored.payload == packet.payload
    assert restored.decode_dict() == frame


def test_payload_length_is_length_minus_header() -> None:
    """载荷长度恒为 `length - header_length`。"""
    packet = Packet.new_binary(OpCode.Heartbeat, 0, b"abc")
    assert len(packet.payload) == packet.length - packet.header_length


def test_heartbeat_reply_decoding() -> None:
    """心跳回复解析出人气值。"""
    payload = (4321).to_bytes(4, "big") + b"tail"
    packet = Packet(
        length=HEADER_LENGTH + len(payload),
        header_length=HEADER_LENGTH,
        protocol_version=ProtocolVersion.Normal,
        opcode=OpCode.HeartbeatReply,
        seq=0,
        payload=payload,
    )
    decoded = packet.decode_dict()
    assert decoded["popularity"] == 4321
    assert decoded["payload"] == b"tail"


def test_zlib_compressed_multiple_packets() -> None:
    """protover=2：zlib 解压后解析多帧。"""
    inner_one = Packet.new(OpCode.Command, 0, {"cmd": "A", "room_id": 1}).to_bytes()
    inner_two = Packet.new(OpCode.Command, 0, {"cmd": "B", "room_id": 1}).to_bytes()
    compressed = zlib.compress(inner_one + inner_two)
    outer = Packet.new_binary(OpCode.Command, 0, compressed, ProtocolVersion.Zlib)
    decoded = outer.decode_data()
    assert isinstance(decoded, list)
    assert [packet.decode_dict()["cmd"] for packet in decoded] == ["A", "B"]


def test_brotli_compressed_multiple_packets() -> None:
    """protover=3：brotli 解压后解析多帧。"""
    inner = Packet.new(OpCode.Command, 0, {"cmd": "C", "room_id": 1}).to_bytes()
    outer = Packet.new_binary(OpCode.Command, 0, brotli.compress(inner), ProtocolVersion.Brotli)
    decoded = outer.decode_data()
    assert isinstance(decoded, list)
    assert decoded[0].decode_dict()["cmd"] == "C"


def test_malformed_length_does_not_loop() -> None:
    """畸形长度（小于头长 / 超出缓冲）终止解析，不进入死循环。"""
    compressed = zlib.compress(make_header(8, HEADER_LENGTH, 0, 5, 0))
    outer = Packet.new_binary(OpCode.Command, 0, compressed, ProtocolVersion.Zlib)
    assert outer.decode_data() == []
    too_long = zlib.compress(make_header(1000, HEADER_LENGTH, 0, 5, 0) + b"x")
    outer2 = Packet.new_binary(OpCode.Command, 0, too_long, ProtocolVersion.Zlib)
    assert outer2.decode_data() == []


def test_from_bytes_rejects_short_and_invalid_header() -> None:
    """头不足 16 字节、头长非 16、声明长度越界均抛 ValueError。"""
    import pytest

    with pytest.raises(ValueError, match="too short"):
        Packet.from_bytes(b"\x00" * 15)
    with pytest.raises(ValueError, match="header length"):
        Packet.from_bytes(make_header(16, 8, 0, 5, 0))
    with pytest.raises(ValueError, match="Malformed packet length"):
        Packet.from_bytes(make_header(100, HEADER_LENGTH, 0, 5, 0) + b"short")


def test_heartbeat_packet_has_empty_payload() -> None:
    """长度恰为头长（空载荷）的心跳帧是合法帧。"""
    packet = Packet.new_binary(OpCode.Heartbeat, 0, b"")
    restored = Packet.from_bytes(packet.to_bytes())
    assert restored.payload == b""
    assert restored.length == HEADER_LENGTH


def test_auth_packet_fields() -> None:
    """鉴权帧字段与上游一致。"""
    packet = new_auth_packet(room_id=999, uid=123, token="tok", buvid3="buvid")
    decoded = packet.decode_dict()
    assert decoded == {
        "uid": 123,
        "roomid": 999,
        "protover": 3,
        "buvid": "buvid",
        "platform": "web",
        "type": 2,
        "key": "tok",
    }
    assert packet.opcode is OpCode.Auth


def test_pb_command_decoding() -> None:
    """INTERACT_WORD_V2 走 betterproto 解码并产出事件。"""
    from bilibili_api.nonebot.adapters.bilibili_live.pb import InteractWordV2

    pb = InteractWordV2(uid=1, uname="u", msg_type=1, timestamp=2, trigger_time=2)
    frame = {
        "cmd": "INTERACT_WORD_V2",
        "data": {"pb": base64.b64encode(bytes(pb)).decode()},
        "room_id": 999,
    }
    packet = Packet.from_bytes(Packet.new(OpCode.Command, 0, frame).to_bytes())
    event = packet_to_event(packet, room_id=999)
    assert type(event).__name__ == "UserEnterEvent"
    assert event.uid == 1


def test_json_payload_is_utf8() -> None:
    """JSON 载荷按 UTF-8 往返，中文不丢失。"""
    packet = Packet.new(OpCode.Command, 0, {"cmd": "X", "text": "中文"})
    assert json.loads(packet.payload.decode("utf-8"))["text"] == "中文"
