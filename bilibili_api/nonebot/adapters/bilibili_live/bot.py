"""
bilibili_api.nonebot.adapters.bilibili_live.bot

适配器 Bot：事件取值语义与经库抽象的 API 调用。

`WebBot` 的 7 个 REST 方法全部走 `Api(**data/api/live.json)` 链路，登录态、csrf、
WBI 与 buvid 由库统一注入；适配器不再自带签名或指纹实现（FR-011 / FR-013）。
"""

from __future__ import annotations

import time
from typing import Any, cast

from nonebot.compat import type_validate_python
from nonebot.message import handle_event
from typing_extensions import override

from nonebot.adapters import Bot as BaseBot
from nonebot.adapters import Event as BaseEvent
from nonebot.adapters import Message as BaseMessage
from nonebot.adapters import MessageSegment as BaseMessageSegment

from ....exceptions import ArgsException
from ....utils.network import Api, Credential
from .const import (
    API_ADD_SILENT_USER,
    API_DEL_SILENT_USER,
    API_GET_MASTER_INFO,
    API_GET_ROOM_INFO,
    API_GET_SILENT_USER_LIST,
    API_GET_USER_ROOM_STATUS,
    API_SEND_DANMAKU,
    get_endpoint,
)
from .event import DanmakuEvent, Event, SuperChatEvent
from .log import log
from .message import AtSegment, MessageSegment
from .models.open import Game
from .models.room import MasterData, Room, UserRoomStatus
from .models.user_manage import SilentUserListData

OPEN_PLATFORM_UNSUPPORTED = (
    "开放平台形态尚未支持：本次融合只包含网页弹幕（WebBot）链路，"
    "OpenBot / 身份码 / 互动玩法已拆到后续特性。请改用 uid + room_ids 的网页配置。"
)


def _check_to_me(bot: Bot, event: Event) -> None:
    """
    按上游规则填充 `event.to_me`。

    Args:
        bot (Bot): 事件所属 Bot。
        event (Event): 待分发事件。
    """
    if isinstance(event, DanmakuEvent):
        event.to_me = int(bot.self_id) == event.reply_mid
    elif isinstance(event, SuperChatEvent):
        anchor: int | None = None
        if isinstance(bot, WebBot):
            anchor = bot.room_anchors.get(event.room_id)
            if anchor is None and event.room_id in bot.rooms:
                anchor = bot.rooms[event.room_id].uid
        event.to_me = anchor is not None and int(bot.self_id) == anchor


class Bot(BaseBot):
    """适配器 Bot 基类：事件先补 `to_me` 再交给 NoneBot 处理链。"""

    async def _handle_event(self, event: Event) -> None:
        """
        处理单个事件。

        Args:
            event (Event): 待分发事件。
        """
        _check_to_me(self, event)
        await handle_event(self, event)


class WebBot(Bot):
    """网页弹幕 Bot。"""

    rooms: dict[int, Room]
    """本 Bot 已知的房间信息缓存（按房间号索引）。"""
    room_anchors: dict[int, int]
    """房间号到主播 uid 的映射（用于醒目留言的 `to_me` 判定）。"""

    def __init__(
        self,
        adapter: Any,
        self_id: str,
        credential: Credential | None = None,
    ) -> None:
        """
        Args:
            adapter (Any): 所属适配器。
            self_id (str): 登录 uid 的字符串形式。
            credential (Credential | None, optional): 账号凭据；`None` 表示未登录
                （只读匿名能力仍可用）. Defaults to None.
        """
        super().__init__(adapter, self_id)
        self.credential: Credential = credential if credential is not None else Credential()
        self.rooms = {}
        self.room_anchors = {}
        self.room_anchors = {}

    async def send_danmaku(
        self,
        room_id: int,
        msg: str,
        mode: int = 1,
        reply_mid: int = 0,
    ) -> None:
        """
        发送公开弹幕。

        Args:
            room_id (int): 真实直播间号。
            msg (str): 弹幕内容。
            mode (int, optional): 弹幕模式（1 飞行 / 4 底部 / 5 顶部）. Defaults to 1.
            reply_mid (int, optional): 回复的用户 mid，`0` 表示不回复. Defaults to 0.

        Raises:
            CredentialNoSessdataException: 未登录。
            CredentialNoBiliJctException: 缺少 csrf 字段。
            ResponseCodeException: 接口返回业务错误码。
            NetworkException: 传输层错误。
        """
        api = get_endpoint(API_SEND_DANMAKU)
        data = {
            "mode": mode,
            "msg": msg,
            "roomid": room_id,
            "bubble": 0,
            "rnd": int(time.time()),
            "color": 16777215,
            "fontsize": 25,
            "reply_mid": reply_mid,
        }
        await Api(**api, credential=self.credential).update_data(**data).result_dict()

    async def get_room_info(self, room_id: int) -> Room:
        """
        获取房间详情。

        Args:
            room_id (int): 直播间号（长短号均可）。

        Returns:
            Room: 房间详情，并写入 `self.rooms` 缓存。

        Raises:
            ResponseCodeException: 接口返回业务错误码。
            NetworkException: 传输层错误。
        """
        api = get_endpoint(API_GET_ROOM_INFO)
        data = await Api(**api, credential=self.credential).update_params(room_id=room_id).result_dict()
        room = type_validate_python(Room, data)
        self.rooms[room.room_id] = room
        return room

    async def get_user_room_status(self, mid: int) -> UserRoomStatus:
        """
        获取用户对应的直播间状态。

        Args:
            mid (int): 目标用户 mid。

        Returns:
            UserRoomStatus: 用户直播间状态。

        Raises:
            ResponseCodeException: 接口返回业务错误码。
            NetworkException: 传输层错误。
        """
        api = get_endpoint(API_GET_USER_ROOM_STATUS)
        data = await Api(**api, credential=self.credential).update_params(mid=mid).result_dict()
        return type_validate_python(UserRoomStatus, data)

    async def get_master_info(self, uid: int) -> MasterData:
        """
        获取主播信息。

        Args:
            uid (int): 目标用户 mid。

        Returns:
            MasterData: 主播信息。

        Raises:
            ResponseCodeException: 接口返回业务错误码。
            NetworkException: 传输层错误。
        """
        api = get_endpoint(API_GET_MASTER_INFO)
        data = await Api(**api, credential=self.credential).update_params(uid=uid).result_dict()
        return type_validate_python(MasterData, data)

    async def add_silent_user(
        self,
        room_id: int,
        tuid: int,
        hour: int,
        msg: str = "",
        visit_id: str = "",
    ) -> None:
        """
        禁言观众。

        Args:
            room_id (int): 真实直播间号。
            tuid (int): 要禁言的用户 uid。
            hour (int): 禁言时长，`-1` 永久、`0` 本场直播。
            msg (str, optional): 触发禁言的弹幕内容. Defaults to "".
            visit_id (str, optional): 访问 ID. Defaults to "".

        Raises:
            CredentialNoSessdataException: 未登录。
            CredentialNoBiliJctException: 缺少 csrf 字段。
            ResponseCodeException: 接口返回业务错误码。
            NetworkException: 传输层错误。
        """
        api = get_endpoint(API_ADD_SILENT_USER)
        data = {
            "room_id": str(room_id),
            "tuid": str(tuid),
            "msg": msg,
            "mobile_app": "web",
            "hour": hour,
            "visit_id": visit_id,
        }
        await Api(**api, credential=self.credential).update_data(**data).result_dict()

    async def get_silent_user_list(self, room_id: int, ps: int = 1, visit_id: str = "") -> SilentUserListData:
        """
        查询直播间禁言列表。

        Args:
            room_id (int): 真实直播间号。
            ps (int, optional): 列表页码. Defaults to 1.
            visit_id (str, optional): 访问 ID. Defaults to "".

        Returns:
            SilentUserListData: 禁言用户列表。

        Raises:
            CredentialNoSessdataException: 未登录。
            CredentialNoBiliJctException: 缺少 csrf 字段。
            ResponseCodeException: 接口返回业务错误码。
            NetworkException: 传输层错误。
        """
        api = get_endpoint(API_GET_SILENT_USER_LIST)
        data = {
            "room_id": str(room_id),
            "ps": str(ps),
            "visit_id": visit_id,
        }
        result = await Api(**api, credential=self.credential).update_data(**data).result_dict()
        return type_validate_python(SilentUserListData, result)

    async def del_silent_user(self, room_id: int, silent_id: int, visit_id: str = "") -> None:
        """
        解除禁言。

        Args:
            room_id (int): 真实直播间号。
            silent_id (int): 禁言记录 id（由 `get_silent_user_list` 获取）。
            visit_id (str, optional): 访问 ID. Defaults to "".

        Raises:
            CredentialNoSessdataException: 未登录。
            CredentialNoBiliJctException: 缺少 csrf 字段。
            ResponseCodeException: 接口返回业务错误码。
            NetworkException: 传输层错误。
        """
        api = get_endpoint(API_DEL_SILENT_USER)
        data = {
            "roomid": str(room_id),
            "id": str(silent_id),
            "visit_id": visit_id,
        }
        await Api(**api, credential=self.credential).update_data(**data).result_dict()

    @override
    async def send(
        self,
        event: BaseEvent,
        message: str | BaseMessage | BaseMessageSegment,
        *,
        reply_message: bool = False,
        **kwargs: Any,
    ) -> Any:
        """
        发送消息（仅公开弹幕）。

        Args:
            event (BaseEvent): 事件对象（提供房间号与可选回复目标）。
            message (str | BaseMessage | BaseMessageSegment): 消息内容。
            reply_message (bool, optional): 是否回复消息发送者. Defaults to False.
            **kwargs (Any): 透传给 `send_danmaku` 的额外参数（如 `mode`）。

        Returns:
            Any: 发送结果（当前实现为 `None`）。
        """
        adapter_event = cast(Event, event)
        reply_mid = 0
        if reply_message:
            try:
                reply_mid = int(adapter_event.get_user_id())
            except ValueError:
                log("WARNING", "Event has no user_id, cannot reply")
        text: str | BaseMessage | BaseMessageSegment = message
        if isinstance(text, AtSegment):
            reply_mid = text.data.get("uid", 0)
        if isinstance(text, MessageSegment):
            text = str(text)
        elif isinstance(text, BaseMessageSegment):
            text = str(text)
        elif isinstance(text, BaseMessage):
            at_segments = [segment for segment in text if segment.type == "at"]
            reply_mid = at_segments[-1].data.get("uid", 0) if at_segments else 0
            text = "".join(str(segment) for segment in text)
        return await self.send_danmaku(
            room_id=adapter_event.room_id,
            msg=str(text),
            reply_mid=reply_mid,
            **kwargs,
        )


class OpenBot(Bot):
    """
    开放平台 Bot（保留符号，禁止使用）。

    开放平台形态已拆到后续特性；实例化即抛明确错误，不提供半可用连接（FR-018）。
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """
        Raises:
            ArgsException: 总是抛出，说明开放平台形态尚未支持。
        """
        raise ArgsException(OPEN_PLATFORM_UNSUPPORTED)

    @override
    async def send(
        self,
        event: BaseEvent,
        message: str | BaseMessage | BaseMessageSegment,
        **kwargs: Any,
    ) -> Any:
        """
        开放平台形态未实现。

        Args:
            event (BaseEvent): 事件对象。
            message (str | BaseMessage | BaseMessageSegment): 消息内容。
            **kwargs (Any): 其他参数。

        Raises:
            ArgsException: 总是抛出，说明开放平台形态尚未支持。
        """
        raise ArgsException(OPEN_PLATFORM_UNSUPPORTED)

    games: dict[int, Game]
    """保留字段声明（不产出实例）。"""
