"""
bilibili_api.nonebot.adapters.bilibili_live.packet

直播弹幕 WebSocket 帧编解码。

协议头固定 16 字节：`>I2H2I`（总长、头长、协议版本、操作码、序号）。载荷按
`protocol_version` 选择 zlib / brotli 解压，解压结果可继续包含多帧。畸形帧
（长度小于头长、长度超出缓冲、头长不等于 16）一律丢弃并停止解析本段数据，
不得进入死循环。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
import json
import struct
from typing import Any
import zlib

import brotli

HEADER_LENGTH = 16
"""协议头固定长度（字节）。"""


class ProtocolVersion(IntEnum):
    """载荷协议版本。"""

    Normal = 0
    """原始 JSON。"""
    Heartbeat = 1
    """心跳 / 鉴权（JSON 载荷，但按该版本标识）。"""
    Zlib = 2
    """zlib 压缩，解压后为多帧。"""
    Brotli = 3
    """brotli 压缩，解压后为多帧。"""


class OpCode(IntEnum):
    """操作码。"""

    Heartbeat = 2
    """心跳。"""
    HeartbeatReply = 3
    """心跳回复（人气值）。"""
    Command = 5
    """业务命令。"""
    Auth = 7
    """鉴权。"""
    AuthReply = 8
    """鉴权回复。"""


@dataclass
class Packet:
    """一个弹幕协议帧。"""

    length: int
    """含 16 字节头的总长度。"""
    header_length: int
    """头长度（接收帧恒为 16）。"""
    protocol_version: ProtocolVersion
    """载荷协议版本。"""
    opcode: OpCode
    """操作码。"""
    seq: int
    """序号（心跳与鉴权使用固定值）。"""
    payload: bytes
    """载荷，长度恒为 `length - header_length`。"""

    @property
    def data(self) -> bytes:
        """
        载荷的兼容别名（与上游 `Packet.data` 同名）。

        Returns:
            bytes: 与 `payload` 相同的字节串。
        """
        return self.payload

    @classmethod
    def new(
        cls,
        opcode: OpCode,
        seq: int,
        data: dict[str, Any],
        protocol_version: ProtocolVersion = ProtocolVersion.Normal,
    ) -> Packet:
        """
        构造 JSON 载荷帧。

        Args:
            opcode (OpCode): 操作码。
            seq (int): 序号。
            data (dict[str, Any]): JSON 可序列化载荷。
            protocol_version (ProtocolVersion, optional): 协议版本. Defaults to `Normal`.

        Returns:
            Packet: 新帧。
        """
        raw = json.dumps(data, ensure_ascii=False).encode("utf-8")
        return cls(
            length=len(raw) + HEADER_LENGTH,
            header_length=HEADER_LENGTH,
            protocol_version=protocol_version,
            opcode=opcode,
            seq=seq,
            payload=raw,
        )

    @classmethod
    def new_binary(
        cls,
        opcode: OpCode,
        seq: int,
        data: bytes,
        protocol_version: ProtocolVersion = ProtocolVersion.Normal,
    ) -> Packet:
        """
        构造二进制载荷帧。

        Args:
            opcode (OpCode): 操作码。
            seq (int): 序号。
            data (bytes): 原始载荷。
            protocol_version (ProtocolVersion, optional): 协议版本. Defaults to `Normal`.

        Returns:
            Packet: 新帧。
        """
        return cls(
            length=len(data) + HEADER_LENGTH,
            header_length=HEADER_LENGTH,
            protocol_version=protocol_version,
            opcode=opcode,
            seq=seq,
            payload=data,
        )

    def to_bytes(self) -> bytes:
        """
        序列化为可发送的字节串。

        Returns:
            bytes: 头 + 载荷。
        """
        header = struct.pack(
            ">I2H2I",
            self.length,
            self.header_length,
            self.protocol_version.value,
            self.opcode.value,
            self.seq,
        )
        return header + self.payload

    @classmethod
    def from_bytes(cls, payload: bytes) -> Packet:
        """
        从字节串解析单个帧。

        Args:
            payload (bytes): 至少包含完整 16 字节头。

        Returns:
            Packet: 解析出的帧（载荷按 `length` 切片）。

        Raises:
            ValueError: 数据不足、头长不为 16、声明长度小于头长或超出缓冲。
        """
        if len(payload) < HEADER_LENGTH:
            raise ValueError("Data too short to be a valid packet")
        length, header_length, protocol_version, opcode, seq = struct.unpack(">I2H2I", payload[:HEADER_LENGTH])
        if header_length != HEADER_LENGTH:
            raise ValueError(f"Unsupported header length: {header_length}")
        if length < HEADER_LENGTH or length > len(payload):
            raise ValueError(f"Malformed packet length: {length}, buffer length: {len(payload)}")
        return cls(
            length=length,
            header_length=header_length,
            protocol_version=ProtocolVersion(protocol_version),
            opcode=OpCode(opcode),
            seq=seq,
            payload=payload[HEADER_LENGTH:length],
        )

    def decode_data(self) -> dict[str, Any] | list[Packet]:
        """
        解码载荷。

        Returns:
            dict[str, Any] | list[Packet]: 压缩帧返回内嵌帧列表；心跳回复返回
            `popularity` / `payload`；其余返回 JSON 字典。

        Raises:
            ValueError: 压缩算法不受支持或 JSON 解析失败。
        """
        if self.protocol_version == ProtocolVersion.Zlib:
            return self._parse_multiple_packets(zlib.decompress(self.payload))
        if self.protocol_version == ProtocolVersion.Brotli:
            return self._parse_multiple_packets(brotli.decompress(self.payload))
        if self.opcode == OpCode.HeartbeatReply:
            return {
                "popularity": int.from_bytes(self.payload[0:4], "big"),
                "payload": self.payload[4:],
            }
        return json.loads(self.payload.decode("utf-8"))

    def decode_dict(self) -> dict[str, Any]:
        """
        解码载荷并收窄为字典。

        Returns:
            dict[str, Any]: 解码结果。

        Raises:
            ValueError: 解码结果不是字典（如压缩帧解出多帧列表）。
        """
        decoded = self.decode_data()
        if not isinstance(decoded, dict):
            raise ValueError("Decoded data is not a dictionary")
        return decoded

    @classmethod
    def _parse_multiple_packets(cls, data: bytes) -> list[Packet]:
        """
        解析解压后的多帧数据。

        畸形长度（小于头长或超出剩余缓冲）会终止解析并返回已解析的帧，
        保证 `offset` 单调前进、不进入死循环。

        Args:
            data (bytes): 解压后的原始字节。

        Returns:
            list[Packet]: 已解析的帧列表。
        """
        packets: list[Packet] = []
        offset = 0
        while offset < len(data):
            if len(data) - offset < HEADER_LENGTH:
                break
            length, header_length, protocol_version, opcode, seq = struct.unpack(
                ">I2H2I", data[offset : offset + HEADER_LENGTH]
            )
            if header_length != HEADER_LENGTH or length < HEADER_LENGTH or offset + length > len(data):
                break
            packets.append(
                cls(
                    length=length,
                    header_length=header_length,
                    protocol_version=ProtocolVersion(protocol_version),
                    opcode=OpCode(opcode),
                    seq=seq,
                    payload=data[offset + HEADER_LENGTH : offset + length],
                )
            )
            offset += length
        return packets


def new_auth_packet(room_id: int, uid: int, token: str, buvid3: str) -> Packet:
    """
    构造鉴权帧。

    Args:
        room_id (int): 真实房间号。
        uid (int): 登录 uid，匿名连接为 0。
        token (str): `info.danmu_info` 下发的 token。
        buvid3 (str): buvid3（库反爬链路提供）。

    Returns:
        Packet: 鉴权帧。
    """
    data = {
        "uid": uid,
        "roomid": room_id,
        "protover": 3,
        "buvid": buvid3,
        "platform": "web",
        "type": 2,
        "key": token,
    }
    return Packet.new(OpCode.Auth, 1, data, ProtocolVersion.Heartbeat)
