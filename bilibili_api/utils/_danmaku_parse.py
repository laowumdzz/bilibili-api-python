"""
bilibili_api.utils._danmaku_parse

弹幕 protobuf 二进制数据的公共解析逻辑。

`Video.get_danmaku_view` / `Video.get_danmakus` 与 `CheeseVideo` 的同名方法
共用此处的解析实现，避免重复代码。
"""

import json
from typing import Any

from ..exceptions import ResponseException
from .BytesReader import BytesReader
from .danmaku import Danmaku


def parse_danmaku_view(resp_data: bytes) -> dict:
    """
    解析弹幕 view 接口返回的 protobuf 二进制数据。

    对应 `get_danmaku_view` 的响应体，包含弹幕设置、特殊弹幕、
    弹幕数量、弹幕分段等信息。

    Args:
        resp_data (bytes): 接口返回的原始二进制数据。

    Returns:
        dict: 解析后的弹幕信息。
    """
    json_data: dict[str, Any] = {}
    reader = BytesReader(resp_data)

    # 解析二进制数据流

    def read_dm_seg(stream: bytes):
        reader_ = BytesReader(stream)
        data: dict[str, Any] = {}
        while not reader_.has_end():
            t = reader_.varint() >> 3
            if t == 1:
                data["page_size"] = reader_.varint()
            elif t == 2:
                data["total"] = reader_.varint()
            else:
                continue
        return data

    def read_flag(stream: bytes):
        reader_ = BytesReader(stream)
        data: dict[str, Any] = {}
        while not reader_.has_end():
            t = reader_.varint() >> 3
            if t == 1:
                data["rec_flag"] = reader_.varint()
            elif t == 2:
                data["rec_text"] = reader_.string()
            elif t == 3:
                data["rec_switch"] = reader_.varint()
            else:
                continue
        return data

    def read_command_danmakus(stream: bytes):
        reader_ = BytesReader(stream)
        data: dict[str, Any] = {}
        while not reader_.has_end():
            t = reader_.varint() >> 3
            if t == 1:
                data["id"] = reader_.varint()
            elif t == 2:
                data["oid"] = reader_.varint()
            elif t == 3:
                data["mid"] = reader_.varint()
            elif t == 4:
                data["commend"] = reader_.string()
            elif t == 5:
                data["content"] = reader_.string()
            elif t == 6:
                data["progress"] = reader_.varint()
            elif t == 7:
                data["ctime"] = reader_.string()
            elif t == 8:
                data["mtime"] = reader_.string()
            elif t == 9:
                data["extra"] = json.loads(reader_.string())
            elif t == 10:
                data["id_str"] = reader_.string()
            else:
                continue
        return data

    def read_settings(stream: bytes):
        reader_ = BytesReader(stream)
        data: dict[str, Any] = {}
        while not reader_.has_end():
            t = reader_.varint() >> 3
            if t == 1:
                data["dm_switch"] = reader_.bool()
            elif t == 2:
                data["ai_switch"] = reader_.bool()
            elif t == 3:
                data["ai_level"] = reader_.varint()
            elif t == 4:
                data["enable_top"] = reader_.bool()
            elif t == 5:
                data["enable_scroll"] = reader_.bool()
            elif t == 6:
                data["enable_bottom"] = reader_.bool()
            elif t == 7:
                data["enable_color"] = reader_.bool()
            elif t == 8:
                data["enable_special"] = reader_.bool()
            elif t == 9:
                data["prevent_shade"] = reader_.bool()
            elif t == 10:
                data["dmask"] = reader_.bool()
            elif t == 11:
                data["opacity"] = reader_.float(True)
            elif t == 12:
                data["dm_area"] = reader_.varint()
            elif t == 13:
                data["speed_plus"] = reader_.float(True)
            elif t == 14:
                data["font_size"] = reader_.float(True)
            elif t == 15:
                data["screen_sync"] = reader_.bool()
            elif t == 16:
                data["speed_sync"] = reader_.bool()
            elif t == 17:
                data["font_family"] = reader_.string()
            elif t == 18:
                data["bold"] = reader_.bool()
            elif t == 19:
                data["font_border"] = reader_.varint()
            elif t == 20:
                data["draw_type"] = reader_.string()
            elif t == 22 or t == 24 or t == 26:
                reader_.bool()
            elif t == 25:
                reader_.varint()
            elif t == 23:
                reader_.bytes_string()
            else:
                continue
        return data

    def read_image_danmakus(string: bytes):
        image_list = []
        reader_ = BytesReader(string)
        while not reader_.has_end():
            type_ = reader_.varint() >> 3
            if type_ == 1:
                details_dict: dict[str, Any] = {"texts": []}
                img_details = reader_.bytes_string()
                reader_details = BytesReader(img_details)
                while not reader_details.has_end():
                    type_details = reader_details.varint() >> 3
                    if type_details == 1:
                        details_dict["texts"].append(reader_details.string())
                    elif type_details == 2:
                        details_dict["image"] = reader_details.string()
                    elif type_details == 3:
                        id_string = reader_details.bytes_string()
                        id_reader = BytesReader(id_string)
                        while not id_reader.has_end():
                            type_id = id_reader.varint() >> 3
                            if type_id == 2:
                                details_dict["id"] = id_reader.varint()
                            else:
                                raise ResponseException("解析响应数据错误")
                image_list.append(details_dict)
            else:
                raise ResponseException("解析响应数据错误")
        return image_list

    while not reader.has_end():
        type_ = reader.varint() >> 3

        if type_ == 1:
            json_data["state"] = reader.varint()
        elif type_ == 2:
            json_data["text"] = reader.string()
        elif type_ == 3:
            json_data["text_side"] = reader.string()
        elif type_ == 4:
            json_data["dm_seg"] = read_dm_seg(reader.bytes_string())
        elif type_ == 5:
            json_data["flag"] = read_flag(reader.bytes_string())
        elif type_ == 6:
            if "special_dms" not in json_data:
                json_data["special_dms"] = []
            json_data["special_dms"].append(reader.string())
        elif type_ == 7:
            json_data["check_box"] = reader.bool()
        elif type_ == 8:
            json_data["count"] = reader.varint()
        elif type_ == 9:
            if "command_dms" not in json_data:
                json_data["command_dms"] = []
            json_data["command_dms"].append(read_command_danmakus(reader.bytes_string()))
        elif type_ == 10:
            json_data["dm_setting"] = read_settings(reader.bytes_string())
        elif type_ == 12:
            json_data["image_dms"] = read_image_danmakus(reader.bytes_string())
        # 如果没有对 14 的处理，在登录状态下请求含花式弹幕的视频（如 BV1HLz9BJEgi）
        # 会在 read_image_danmakus 中抛出“解析响应数据错误”。
        # 经二进制排查发现 14 是一段字符串，消费掉即可。
        elif type_ == 14:
            reader.bytes_string()
        else:
            continue
    return json_data


def parse_danmaku_segment(data: bytes) -> list[Danmaku]:
    """
    解析弹幕分段接口返回的 protobuf 二进制数据。

    对应 `get_danmakus` 单个分段的响应体。若响应为 `b"\\x10\\x01"`
    表示弹幕被关闭，应由调用方在调用前判断并抛出 DanmakuClosedException。

    Args:
        data (bytes): 单个弹幕分段的原始二进制数据。

    Returns:
        list[Danmaku]: 解析出的 Danmaku 列表。
    """
    danmakus = []

    reader = BytesReader(data)
    while not reader.has_end():
        type_ = reader.varint() >> 3
        if type_ != 1:
            if type_ == 4:
                reader.bytes_string()
                # 什么鬼？我用 protoc 解析出乱码！
            elif type_ == 5:
                # 大会员专属颜色
                reader.varint()
                reader.varint()
                reader.varint()
                reader.bytes_string()
            elif type_ == 13:
                # ???
                continue
            else:
                raise ResponseException("解析响应数据错误")

        dm = Danmaku("")
        dm_pack_data = reader.bytes_string()
        dm_reader = BytesReader(dm_pack_data)

        while not dm_reader.has_end():
            data_type = dm_reader.varint() >> 3

            if data_type == 1:
                dm.id_ = dm_reader.varint()
            elif data_type == 2:
                dm.dm_time = dm_reader.varint() / 1000
            elif data_type == 3:
                dm.mode = dm_reader.varint()
            elif data_type == 4:
                dm.font_size = dm_reader.varint()
            elif data_type == 5:
                color = dm_reader.varint()
                if color != 60001:
                    color = hex(color)[2:]
                else:
                    color = "special"
                dm.color = color
            elif data_type == 6:
                dm.crc32_id = dm_reader.string()
            elif data_type == 7:
                dm.text = dm_reader.string()
            elif data_type == 8:
                dm.send_time = dm_reader.varint()
            elif data_type == 9:
                dm.weight = dm_reader.varint()
            elif data_type == 10:
                dm.action = str(dm_reader.string())
            elif data_type == 11:
                dm.pool = dm_reader.varint()
            elif data_type == 12:
                dm.id_str = dm_reader.string()
            elif data_type == 13:
                dm.attr = dm_reader.varint()
            elif data_type == 14:
                dm.uid = dm_reader.varint()
            elif data_type == 15:
                dm_reader.varint()
            elif data_type == 20:
                dm_reader.bytes_string()
            elif data_type == 21:
                dm_reader.bytes_string()
            elif data_type == 22:
                dm_reader.bytes_string()
            elif data_type == 25:
                dm_reader.varint()
            elif data_type == 26:
                dm_reader.varint()
            else:
                break
        danmakus.append(dm)
    return danmakus
