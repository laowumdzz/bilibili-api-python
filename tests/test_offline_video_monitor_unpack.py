"""
Offline 测试：VideoOnlineMonitor 私有方法 __pack / __unpack 的打包解包回环。

覆盖场景：
- 单包回环：__pack 打包 → __unpack 解包，字段往返一致。
- 多包粘包：多个 __pack 结果直接拼接（不同长度、不同类型），
  __unpack 必须逐包正确解析（对应 CODE_REVIEW 遗留 #10 的越界问题）。
- 载荷类型覆盖：dict / list / 空对象，模拟心跳反馈、弹幕、认证响应。

纯本地逻辑，不触网、无凭据依赖。
"""

import json

import pytest

from bilibili_api._video_monitor import VideoOnlineMonitor

# __pack / __unpack 为 @staticmethod，通过 name mangling 直接访问，无需构造实例。
_pack = VideoOnlineMonitor._VideoOnlineMonitor__pack
_unpack = VideoOnlineMonitor._VideoOnlineMonitor__unpack

Datapack = VideoOnlineMonitor.Datapack


def test_unpack_single_packet_round_trip():
    """单包回环：类型、编号、载荷均往返一致。"""
    payload = {"code": 0, "data": {"room": {"online": 42}}}
    packet = _pack(Datapack.SERVER_HEARTBEAT, 3, json.dumps(payload).encode())

    (item,) = _unpack(packet)

    assert item["type"] == Datapack.SERVER_HEARTBEAT.value
    assert item["number"] == 3
    assert item["data"] == payload


def test_unpack_danmaku_list_payload():
    """弹幕包载荷为 JSON 列表，解包后保持列表结构。"""
    payload = ["0.5,1,25,16777215,1700000000,0,abcdef12", "测试弹幕文本"]
    packet = _pack(Datapack.DANMAKU, 7, json.dumps(payload, ensure_ascii=False).encode())

    (item,) = _unpack(packet)

    assert item["type"] == Datapack.DANMAKU.value
    assert item["number"] == 7
    assert item["data"] == payload


def test_unpack_multi_packet_sticky_stream():
    """多包粘包：三个不同长度、不同类型的包拼接后须逐包正确解析。"""
    cases = [
        # (类型, 编号, 载荷)——刻意使用差异明显的载荷长度暴露切片越界/错位。
        (Datapack.SERVER_VERIFY, 1, {"code": 0}),
        (
            Datapack.SERVER_HEARTBEAT,
            2,
            {
                "data": {
                    "room": {
                        "online": 123456,
                        "room_id": 987654321,
                        "description": "心跳反馈包含较长的嵌套 JSON 载荷，用于验证跨包边界解析",
                    }
                }
            },
        ),
        (Datapack.DANMAKU, 3, ["1.25,1,25,65535,1700000001,1,fedcba98", "短"]),
    ]

    stream = b"".join(
        _pack(data_type, number, json.dumps(payload, ensure_ascii=False).encode())
        for data_type, number, payload in cases
    )

    result = _unpack(stream)

    assert len(result) == len(cases)
    for item, (data_type, number, payload) in zip(result, cases, strict=True):
        assert item["type"] == data_type.value
        assert item["number"] == number
        assert item["data"] == payload


def test_unpack_multi_packet_identical_packets():
    """同构包粘包：即便每包头相同，也须按各自长度推进而非重复解析首包。"""
    payload = {"data": {"room": {"online": 1}}}
    packet = _pack(Datapack.SERVER_HEARTBEAT, 9, json.dumps(payload).encode())

    result = _unpack(packet * 4)

    assert len(result) == 4
    for item in result:
        assert item["type"] == Datapack.SERVER_HEARTBEAT.value
        assert item["number"] == 9
        assert item["data"] == payload


def test_unpack_empty_data():
    """空数据解包返回空元组，不抛异常。"""
    assert _unpack(b"") == ()


def test_unpack_truncated_tail_does_not_raise():
    """尾部残缺 1..17 字节（不足一个完整头部）时须安全终止，不抛 struct.error。"""
    for length in (1, 15, 16, 17):
        assert _unpack(b"\x00" * length) == ()


def test_unpack_valid_packet_followed_by_truncated_tail():
    """完整包 + 残缺尾部粘包：完整包正常解析，残缺尾部安全丢弃不抛异常。"""
    payload = {"code": 0}
    packet = _pack(Datapack.SERVER_VERIFY, 5, json.dumps(payload).encode())

    (item,) = _unpack(packet + b"\x01\x02\x03")

    assert item["type"] == Datapack.SERVER_VERIFY.value
    assert item["number"] == 5
    assert item["data"] == payload


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
