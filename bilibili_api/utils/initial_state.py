"""
bilibili_api.utils.initial_state

用于获取页码的初始化信息
"""

from enum import Enum
import json
from typing import Literal, cast, overload
from urllib.parse import unquote

from ..exceptions import InitialStateException
from .network import Api, Credential


class InitialDataType(Enum):
    """
    识别返回类型
    """

    INITIAL_STATE = "window.__INITIAL_STATE__"
    NEXT_DATA = "__NEXT_DATA__"
    RENDER_DATA = "__RENDER_DATA__"


def find_json(content: str) -> tuple[int, InitialDataType] | tuple[Literal[-1], None]:
    patterns = [
        ("window.__INITIAL_STATE__=", InitialDataType.INITIAL_STATE),
        ('window.__initialState = JSON.parse("', InitialDataType.INITIAL_STATE),
        ("window.__initialState = ", InitialDataType.INITIAL_STATE),
        ('<script id="__NEXT_DATA__" type="application/json">', InitialDataType.NEXT_DATA),
        ('<script id="__RENDER_DATA__" type="application/json">', InitialDataType.RENDER_DATA),
        ("<script>window._render_data_ = ", InitialDataType.RENDER_DATA),
    ]
    for pattern, content_type in patterns:
        pos = content.find(pattern)
        if pos != -1:
            pos += len(pattern)
            return pos, content_type
    return -1, None


def _parse_detected_content(detected_content: str) -> dict:
    """
    解析检测出的 JSON 内容，兼容 percent-encoding 场景。
    """
    decoder = json.JSONDecoder()

    # 常见场景：内容直接就是 JSON 或 JSON 后跟脚本标签。
    try:
        return decoder.raw_decode(detected_content)[0]
    except json.JSONDecodeError:
        pass

    # fallback：部分页面会把 JSON 做 percent-encoding 后塞进 script 标签。
    decoded_content = unquote(detected_content)
    return decoder.raw_decode(decoded_content)[0]


@overload
async def get_initial_state(
    url: str, credential: Credential | None = ..., strict: Literal[True] = ...
) -> tuple[dict, InitialDataType]: ...


@overload
async def get_initial_state(
    url: str, credential: Credential | None = ..., strict: Literal[False] = ...
) -> tuple[None, None]: ...


async def get_initial_state(
    url: str, credential: Credential | None = None, strict: bool = True
) -> tuple[dict, InitialDataType] | tuple[None, None]:
    """
    异步获取初始化信息

    Args:
        url (str): 链接

        credential (Credential | None, optional): 用户凭证. Defaults to None（新建空凭证）.

        strict (bool): 无结果时报错。Defaults to True.
    """
    credential = credential if credential else Credential()
    # byte=True 契约收窄：该模式返回原始字节流（唯一收窄点）
    resp = cast(
        bytes,
        await Api(url=url, method="GET", credential=credential, comment="[获取初始化信息]").request(byte=True),
    )
    content = resp.decode("utf-8")
    pos, content_type = find_json(content)
    if content_type is None:
        # find_json 契约：仅未命中时返回 None
        if strict:
            raise InitialStateException("未找到相关信息")
        return None, None
    try:
        detected_content = content[pos:].strip().strip("\n").strip("\r")
        if detected_content.startswith('{\\"'):  # 暂时都是字典
            detected_content = detected_content.replace('\\"', '"')  # 存在转义且不在正文内
        content = _parse_detected_content(detected_content)
    except json.JSONDecodeError as e:
        raise InitialStateException("信息解析错误") from e
    return content, content_type
