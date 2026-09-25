r"""
bilibili_api.live

直播相关
"""

from enum import Enum
import time
from typing import cast

# re-export：以下导入为公共 API 的一部分，__all__ 保护其不被 F401 移除
from ._live_danmaku import (
    LiveDanmaku,
    parse_interact_word_v2,
    parse_online_rank_v3,
    parse_user_info,
)
from .utils.danmaku import Danmaku
from .utils.network import Api, Credential
from .utils.utils import get_api

API = get_api("live")

__all__ = [
    "API",
    "LiveCodec",
    "LiveDanmaku",
    "LiveFormat",
    "LiveProtocol",
    "LiveRoom",
    "ScreenResolution",
    "create_live_reserve",
    "get_area_info",
    "get_gift_config",
    "get_live_followers_info",
    "get_self_bag",
    "get_self_dahanghai_info",
    "get_self_info",
    "get_self_live_info",
    "get_self_live_watching_history",
    "get_unlive_followers_info",
    "parse_interact_word_v2",
    "parse_online_rank_v3",
    "parse_user_info",
]


class ScreenResolution(Enum):
    """
    直播源清晰度。

    清晰度编号，4K 20000，原画 10000，蓝光（杜比）401，蓝光 400，超清 250，高清 150，流畅 80
    + FOUR_K        : 4K。
    + ORIGINAL      : 原画。
    + BLU_RAY_DOLBY : 蓝光（杜比）。
    + BLU_RAY       : 蓝光。
    + ULTRA_HD      : 超清。
    + HD            : 高清。
    + FLUENCY       : 流畅。
    """

    FOUR_K = 20000
    ORIGINAL = 10000
    BLU_RAY_DOLBY = 401
    BLU_RAY = 400
    ULTRA_HD = 250
    HD = 150
    FLUENCY = 80


class LiveProtocol(Enum):
    """
    直播源流协议。

    流协议，0 为 FLV 流，1 为 HLS 流。默认：0,1
    + FLV     : 0。
    + HLS     : 1。
    + DEFAULT : 0,1
    """

    FLV = 0
    HLS = 1
    DEFAULT = "0,1"


class LiveFormat(Enum):
    """
    直播源容器格式

    容器格式，0 为 flv 格式；1 为 ts 格式（仅限 hls 流）；2 为 fmp4 格式（仅限 hls 流）。默认：0,2
    + FLV       : 0。
    + TS        : 1。
    + FMP4      : 2。
    + DEFAULT   : 2。
    """

    FLV = 0
    TS = 1
    FMP4 = 2
    DEFAULT = "0,1,2"


class LiveCodec(Enum):
    """
    直播源视频编码

    视频编码，0 为 avc 编码，1 为 hevc 编码。默认：0,1
    + AVC       : 0。
    + HEVC      : 1。
    + DEFAULT   : 0,1。
    """

    AVC = 0
    HEVC = 1
    DEFAULT = "0,1"


class LiveRoom:
    """
    直播类，获取各种直播间的操作均在里边。

    Attributes:
        credential      (Credential): 凭据类

        room_display_id (int)       : 房间展示 id
    """

    def __init__(self, room_display_id: int, credential: Credential | None = None):
        """
        Args:
            room_display_id (int)                 : 房间展示 ID（即 URL 中的 ID）

            credential      (Credential, optional): 凭据. Defaults to None.
        """
        self.room_display_id = room_display_id

        if credential is None:
            self.credential: Credential = Credential()
        else:
            self.credential: Credential = credential

        self.__ruid = None
        self.__real_id = None

    async def start(self, area_id: int) -> dict:
        """
        开始直播

        Args:
            area_id (int): 直播分区id（子分区id）。可使用 live_area 模块查询。

        Returns:
            dict: 调用 API 返回的结果
        """
        api = API["info"]["start"]
        data = {
            "area_v2": area_id,
            "room_id": self.room_display_id,
            "platform": "pc_link",
            "csrf": self.credential.bili_jct,
            "csrf_token": self.credential.bili_jct,
        }
        resp = await Api(**api, credential=self.credential).update_data(**data).result_dict()
        return resp

    async def stop(self) -> dict:
        """
        关闭直播

        Returns:
            dict: 调用 API 返回的结果
        """
        api = API["info"]["stop"]
        data = {
            "room_id": self.room_display_id,
            "platform": "pc_link",
        }
        resp = await Api(**api, credential=self.credential).update_data(**data).result_dict()
        return resp

    async def get_room_play_info(self) -> dict:
        """
        获取房间信息（真实房间号，封禁情况等）

        Returns:
            dict: 调用 API 返回的结果
        """
        api = API["info"]["room_play_info"]
        params = {
            "room_id": self.room_display_id,
        }
        resp = await Api(**api, credential=self.credential).update_params(**params).result_dict()

        # 缓存真实房间 ID
        self.__ruid = resp["uid"]
        self.__real_id = resp["room_id"]
        return resp

    async def get_emoticons(self) -> dict:
        """
        获取本房间可用表情包

        Returns:
            dict: 调用 API 返回的结果
        """
        api = API["info"]["emoticons"]
        params = {
            "platform": "pc",
            "room_id": self.room_display_id,
        }
        resp = await Api(**api, credential=self.credential).update_params(**params).result_dict()
        return resp

    async def get_room_id(self) -> int:
        """
        获取直播间真实 id

        Returns:
            int: 直播间 id
        """
        if self.__real_id is None:
            await self.get_room_play_info()

        # get_room_play_info() 已确保 __real_id 赋值为 resp["room_id"]；await 之后
        # 属性收窄失效，此处为唯一收窄点
        return cast(int, self.__real_id)

    async def __get_ruid(self) -> int:
        """
        获取直播的 up 的 uid (ruid)，若有缓存则使用缓存
        """
        if self.__ruid is None:
            await self.get_room_play_info()

        return self.__ruid  # type: ignore

    async def get_ruid(self) -> int:
        """
        获取直播的 up 的 uid (ruid)

        Returns:
            int: ruid
        """
        return await self.__get_ruid()

    async def get_danmu_info(self) -> dict:
        """
        获取聊天弹幕服务器配置信息(websocket)

        Returns:
            dict: 调用 API 返回的结果
        """
        api = API["info"]["danmu_info"]
        params = {"id": await self.get_room_id(), "type": 0, "web_location": "444.8"}
        return await Api(**api, credential=self.credential).update_params(**params).result_dict()

    async def get_room_info(self) -> dict:
        """
        获取直播间信息（标题，简介等）

        Returns:
            dict: 调用 API 返回的结果
        """
        api = API["info"]["room_info"]
        params = {"room_id": self.room_display_id}
        return await Api(**api, credential=self.credential).update_params(**params).result_dict()

    async def get_fan_model(
        self,
        page_num: int = 1,
        target_id: int | None = None,
        roomId: int | None = None,
    ) -> dict:
        """
        获取自己的粉丝勋章信息

        如果带有房间号就返回是否具有的判断 has_medal

        如果带有主播 id ，就返回主播的粉丝牌，没有就返回 null

        Args:
            roomId    (int, optional)       : 指定房间，查询是否拥有此房间的粉丝牌

            target_id (int | None, optional): 指定返回一个主播的粉丝牌，留空就不返回

            page_num  (int | None, optional): 粉丝牌列表，默认 1

        Returns:
            dict: 调用 API 返回的结果
        """
        self.credential.raise_for_no_sessdata()

        api = API["info"]["live_info"]
        params = {
            "pageSize": 10,
            "page": page_num,
        }
        if roomId:
            params["roomId"] = roomId
        if target_id:
            params["target_id"] = target_id
        return await Api(**api, credential=self.credential).update_params(**params).result_dict()

    async def get_user_info_in_room(self) -> dict:
        """
        获取自己在直播间的信息（粉丝勋章等级，直播用户等级等）

        Returns:
            dict: 调用 API 返回的结果
        """
        self.credential.raise_for_no_sessdata()

        api = API["info"]["user_info_in_room"]
        params = {"room_id": self.room_display_id}
        return await Api(**api, credential=self.credential).update_params(**params).result_dict()

    async def get_popular_ticket_num(self) -> dict:
        """
        获取自己在直播间的人气票数量（付费人气票已赠送的量，免费人气票的持有量）

        Returns:
            dict: 调用 API 返回的结果
        """
        self.credential.raise_for_no_sessdata()

        api = API["info"]["popular_ticket"]
        params = {
            "ruid": await self.__get_ruid(),
            "surce": 0,
        }
        return await Api(**api, credential=self.credential).update_params(**params).result_dict()

    async def send_popular_ticket(self) -> dict:
        """
        赠送自己在直播间的所有免费人气票

        Returns:
            dict: 调用 API 返回的结果
        """
        self.credential.raise_for_no_sessdata()
        self.credential.raise_for_no_bili_jct()

        api = API["operate"]["send_popular_ticket"]
        params = {
            "ruid": await self.__get_ruid(),
            "visit_id": "",
        }
        return await Api(**api, credential=self.credential).update_params(**params).result_dict()

    async def get_dahanghai(self, page: int = 1) -> dict:
        """
        获取大航海列表

        Args:
            page (int, optional): 页码. Defaults to 1.

        Returns:
            dict: 调用 API 返回的结果
        """
        api = API["info"]["dahanghai"]
        params = {
            "roomid": self.room_display_id,
            "ruid": await self.__get_ruid(),
            "page_size": 30,
            "page": page,
        }
        return await Api(**api, credential=self.credential).update_params(**params).result_dict()

    async def get_gaonengbang(self, page: int = 1) -> dict:
        """
        获取高能榜列表

        Args:
            page (int, optional): 页码. Defaults to 1

        Returns:
            dict: 调用 API 返回的结果
        """
        api = API["info"]["gaonengbang"]
        params = {
            "roomId": self.room_display_id,
            "ruid": await self.__get_ruid(),
            "pageSize": 50,
            "page": page,
        }
        return await Api(**api, credential=self.credential).update_params(**params).result_dict()

    async def get_seven_rank(self) -> dict:
        """
        获取七日榜

        Returns:
            dict: 调用 API 返回的结果
        """
        api = API["info"]["seven_rank"]
        params = {
            "roomid": self.room_display_id,
            "ruid": await self.__get_ruid(),
        }
        return await Api(**api, credential=self.credential).update_params(**params).result_dict()

    async def get_fans_medal_rank(self) -> dict:
        """
        获取粉丝勋章排行

        Returns:
            dict: 调用 API 返回的结果
        """
        api = API["info"]["fans_medal_rank"]
        params = {"roomid": self.room_display_id, "ruid": await self.__get_ruid()}
        return await Api(**api, credential=self.credential).update_params(**params).result_dict()

    async def get_black_list(self, page: int = 1) -> dict:
        """
        获取黑名单列表

        Returns:
            dict: 调用 API 返回的结果
        """
        api = API["info"]["black_list"]
        params = {"room_id": self.room_display_id, "ps": page}

        return await Api(**api, credential=self.credential).update_params(**params).result_dict()

    async def get_room_play_url(self, screen_resolution: ScreenResolution = ScreenResolution.ORIGINAL) -> dict:
        """
        获取房间直播流列表

        Args:
            screen_resolution (ScreenResolution, optional): 清晰度. Defaults to ScreenResolution.ORIGINAL

        Returns:
            dict: 调用 API 返回的结果
        """
        api = API["info"]["room_play_url"]
        params = {
            "cid": self.room_display_id,
            "platform": "web",
            "qn": screen_resolution.value,
            "https_url_req": "1",
            "ptype": "16",
        }
        return await Api(**api, credential=self.credential).update_params(**params).result_dict()

    async def get_room_play_info_v2(
        self,
        live_protocol: LiveProtocol = LiveProtocol.DEFAULT,
        live_format: LiveFormat = LiveFormat.DEFAULT,
        live_codec: LiveCodec = LiveCodec.DEFAULT,
        live_qn: ScreenResolution = ScreenResolution.ORIGINAL,
    ) -> dict:
        """
        获取房间信息及可用清晰度列表

        Args:
            live_protocol (LiveProtocol, optional)    : 直播源流协议. Defaults to LiveProtocol.DEFAULT.

            live_format   (LiveFormat, optional)      : 直播源容器格式. Defaults to LiveFormat.DEFAULT.

            live_codec    (LiveCodec, optional)       : 直播源视频编码. Defaults to LiveCodec.DEFAULT.

            live_qn       (ScreenResolution, optional): 直播源清晰度. Defaults to ScreenResolution.ORIGINAL.

        Returns:
            dict: 调用 API 返回的结果
        """
        api = API["info"]["room_play_info_v2"]
        params = {
            "room_id": self.room_display_id,
            "platform": "web",
            "ptype": "16",
            "protocol": live_protocol.value,
            "format": live_format.value,
            "codec": live_codec.value,
            "qn": live_qn.value,
        }
        return await Api(**api, credential=self.credential).update_params(**params).result_dict()

    async def ban_user(self, uid: int, hour: int = -1) -> dict:
        """
        封禁用户

        Args:
            uid (int): 用户 UID
            hour (int): 禁言时长，-1为永久，0为直到本场结束

        Returns:
            dict: 调用 API 返回的结果
        """
        self.credential.raise_for_no_sessdata()

        api = API["operate"]["add_block"]
        data = {
            "room_id": self.room_display_id,
            "tuid": uid,
            "mobile_app": "web",
            "type": "2" if hour == 0 else "1",
            "hour": hour,
            "visit_id": "",
        }
        return await Api(**api, credential=self.credential).update_data(**data).result_dict()

    async def unban_user(self, uid: int) -> dict:
        """
        解封用户

        Args:
            uid (int): 用户 UID

        Returns:
            dict: 调用 API 返回的结果
        """
        self.credential.raise_for_no_sessdata()
        api = API["operate"]["del_block"]
        data = {
            "room_id": self.room_display_id,
            "tuid": uid,
            "visit_id": "",
        }
        return await Api(**api, credential=self.credential).update_data(**data).result_dict()

    async def send_danmaku(self, danmaku: Danmaku, room_id: int | None = None, reply_mid: int | None = None) -> dict:
        """
        直播间发送弹幕

        Args:
            danmaku (Danmaku): 弹幕类

            reply_mid (int, optional): @的 UID. Defaults to None.

        Returns:
            dict: 调用 API 返回的结果
        """
        self.credential.raise_for_no_sessdata()

        api = API["operate"]["send_danmaku"]
        if not room_id:
            room_id = (await self.get_room_play_info())["room_id"]

        data = {
            "mode": danmaku.mode,
            "msg": danmaku.text,
            "roomid": room_id,
            "bubble": 0,
            "rnd": int(time.time()),
            "color": int(danmaku.color, 16),
            "fontsize": danmaku.font_size,
        }
        if reply_mid:
            data["reply_mid"] = reply_mid
        return await Api(**api, credential=self.credential).update_data(**data).result_dict()

    async def send_emoticon(self, emoticon: Danmaku, room_id: int | None = None) -> dict:
        """
        直播间发送表情包

        Args:
            emoticon (Danmaku): text为表情包代号

        Returns:
            dict: 调用 API 返回的结果
        """
        self.credential.raise_for_no_sessdata()

        api = API["operate"]["send_emoticon"]
        if not room_id:
            room_id = (await self.get_room_play_info())["room_id"]

        data = {
            "mode": emoticon.mode,
            "msg": emoticon.text,
            "roomid": room_id,
            "bubble": 0,
            "dm_type": 1,
            "rnd": int(time.time()),
            "color": int(emoticon.color, 16),
            "fontsize": emoticon.font_size,
            "emoticonOptions": "[object Object]",
        }
        return await Api(**api, credential=self.credential).update_data(**data).result_dict()

    async def sign_up_dahanghai(self, task_id: int = 1447) -> dict:
        """
        大航海签到

        Args:
            task_id (int, optional): 签到任务 ID. Defaults to 1447

        Returns:
            dict: 调用 API 返回的结果
        """
        self.credential.raise_for_no_sessdata()
        self.credential.raise_for_no_bili_jct()

        api = API["operate"]["sign_up_dahanghai"]
        data = {
            "task_id": task_id,
            "uid": await self.__get_ruid(),
        }
        return await Api(**api, credential=self.credential).update_data(**data).result_dict()

    async def send_gift_from_bag(
        self,
        uid: int,
        bag_id: int,
        gift_id: int,
        gift_num: int,
        storm_beat_id: int = 0,
        price: int = 0,
    ) -> dict:
        """
        赠送包裹中的礼物，获取包裹信息可以使用 get_self_bag 方法

        Args:
            uid (int)                       : 赠送用户的 UID

            bag_id (int)                    : 礼物背包 ID

            gift_id (int)                   : 礼物 ID

            gift_num (int)                  : 礼物数量

            storm_beat_id (int, optional)   : 未知， Defaults to 0

            price (int, optional)           : 礼物单价，Defaults to 0

        Returns:
            dict: 调用 API 返回的结果
        """
        self.credential.raise_for_no_sessdata()
        self.credential.raise_for_no_bili_jct()

        api = API["operate"]["send_gift_from_bag"]
        data = {
            "uid": uid,
            "bag_id": bag_id,
            "gift_id": gift_id,
            "gift_num": gift_num,
            "platform": "pc",
            "send_ruid": 0,
            "storm_beat_id": storm_beat_id,
            "price": price,
            "biz_code": "live",
            "biz_id": self.room_display_id,
            "ruid": await self.__get_ruid(),
        }
        return await Api(**api, credential=self.credential).update_data(**data).result_dict()

    async def receive_reward(self, receive_type: int = 2) -> dict:
        """
        领取自己在某个直播间的航海日志奖励

        Args:
            receive_type (int) : 领取类型，Defaults to 2.

        Returns:
            dict: 调用 API 返回的结果
        """
        self.credential.raise_for_no_sessdata()

        api = API["operate"]["receive_reward"]
        data = {
            "ruid": await self.__get_ruid(),
            "receive_type": receive_type,
        }
        return await Api(**api, credential=self.credential).update_data(**data).result_dict()

    async def get_general_info(self, act_id: int = 100061) -> dict:
        """
        获取自己在该房间的大航海信息, 比如是否开通, 等级等

        Args:
            act_id (int, optional) : 未知，Defaults to 100061

        Returns:
            dict: 调用 API 返回的结果
        """
        self.credential.raise_for_no_sessdata()

        api = API["info"]["general_info"]
        params = {
            "actId": act_id,
            "roomId": self.room_display_id,
            "uid": await self.__get_ruid(),
        }
        return await Api(**api, credential=self.credential).update_params(**params).result_dict()

    async def update_news(self, content: str) -> dict:
        """
        更新公告

        Args:
            content (str): 最多 60 字符

        Returns:
            dict: 调用 API 返回的结果
        """
        self.credential.raise_for_no_sessdata()

        api = API["info"]["update_news"]
        params = {
            "content": content,
            "roomId": self.room_display_id,
            "uid": await self.__get_ruid(),
        }
        return await Api(**api, credential=self.credential).update_params(**params).result_dict()

    async def get_gift_common(self) -> dict:
        """
        获取当前直播间内的普通礼物列表

        Returns:
            dict: 调用 API 返回的结果
        """
        api_room_info = API["info"]["room_info"]
        params_room_info = {
            "room_id": self.room_display_id,
        }
        res_room_info = (
            await Api(**api_room_info, credential=self.credential).update_params(**params_room_info).result_dict()
        )
        area_id, area_parent_id = (
            res_room_info["room_info"]["area_id"],
            res_room_info["room_info"]["parent_area_id"],
        )

        api = API["info"]["gift_common"]
        params = {
            "room_id": self.room_display_id,
            "area_id": area_id,
            "area_parent_id": area_parent_id,
            "platform": "pc",
            "source": "live",
        }
        return await Api(**api, credential=self.credential).update_params(**params).result_dict()

    async def get_gift_special(self, tab_id: int) -> dict:
        """
        注：此 API 已失效，请使用 live.get_gift_config

        获取当前直播间内的特殊礼物列表

        Args:
            tab_id (int) : 2：特权礼物，3：定制礼物

        Returns:
            dict: 调用 API 返回的结果
        """
        api_room_info = API["info"]["room_info"]
        params_room_info = {
            "room_id": self.room_display_id,
        }
        res_room_info = (
            await Api(**api_room_info, credential=self.credential).update_params(**params_room_info).result_dict()
        )
        area_id, area_parent_id = (
            res_room_info["room_info"]["area_id"],
            res_room_info["room_info"]["parent_area_id"],
        )

        api = API["info"]["gift_special"]

        params = {
            "tab_id": tab_id,
            "area_id": area_id,
            "area_parent_id": area_parent_id,
            "room_id": await self.__get_ruid(),
            "source": "live",
            "platform": "pc",
            "build": 1,
        }
        return await Api(**api, credential=self.credential).update_params(**params).result_dict()

    async def send_gift_gold(self, uid: int, gift_id: int, gift_num: int, price: int, storm_beat_id: int = 0) -> dict:
        """
        赠送金瓜子礼物

        Args:
            uid           (int)          : 赠送用户的 UID

            gift_id       (int)          : 礼物 ID (可以通过 get_gift_common 或 get_gift_special 或 get_gift_config 获取)

            gift_num      (int)          : 赠送礼物数量

            price         (int)          : 礼物单价

            storm_beat_id (int, Optional): 未知，Defaults to 0

        Returns:
            dict: 调用 API 返回的结果
        """
        self.credential.raise_for_no_sessdata()
        self.credential.raise_for_no_bili_jct()

        api = API["operate"]["send_gift_gold"]
        data = {
            "uid": uid,
            "gift_id": gift_id,
            "gift_num": gift_num,
            "price": price,
            "ruid": await self.__get_ruid(),
            "biz_code": "live",
            "biz_id": self.room_display_id,
            "platform": "pc",
            "storm_beat_id": storm_beat_id,
            "send_ruid": 0,
            "coin_type": "gold",
            "bag_id": "0",
            "rnd": int(time.time()),
            "visit_id": "",
        }
        return await Api(**api, credential=self.credential).update_data(**data).result_dict()

    async def send_gift_silver(
        self,
        uid: int,
        gift_id: int,
        gift_num: int,
        price: int,
        storm_beat_id: int = 0,
    ) -> dict:
        """
        赠送银瓜子礼物

        Args:
            uid           (int)          : 赠送用户的 UID

            gift_id       (int)          : 礼物 ID (可以通过 get_gift_common 或 get_gift_special 或 get_gift_config 获取)

            gift_num      (int)          : 赠送礼物数量

            price         (int)          : 礼物单价

            storm_beat_id (int, Optional): 未知, Defaults to 0

        Returns:
            dict: 调用 API 返回的结果
        """
        self.credential.raise_for_no_sessdata()
        self.credential.raise_for_no_bili_jct()

        api = API["operate"]["send_gift_silver"]
        data = {
            "uid": uid,
            "gift_id": gift_id,
            "gift_num": gift_num,
            "price": price,
            "ruid": await self.__get_ruid(),
            "biz_code": "live",
            "biz_id": self.room_display_id,
            "platform": "pc",
            "storm_beat_id": storm_beat_id,
            "send_ruid": 0,
            "coin_type": "silver",
            "bag_id": 0,
            "rnd": int(time.time()),
            "visit_id": "",
        }
        return await Api(**api, credential=self.credential).update_data(**data).result_dict()


async def get_self_info(credential: Credential) -> dict:
    """
    获取自己直播等级、排行等信息

    Returns:
        dict: 调用 API 返回的结果
    """
    credential.raise_for_no_sessdata()

    api = API["info"]["user_info"]
    return await Api(**api, credential=credential).result_dict()


async def get_self_live_info(credential: Credential) -> dict:
    """
    获取自己的粉丝牌、大航海等信息

    Returns:
        dict: 调用 API 返回的结果
    """

    credential.raise_for_no_sessdata()

    api = API["info"]["live_info"]
    return await Api(**api, credential=credential).result_dict()


async def get_self_dahanghai_info(page: int = 1, page_size: int = 10, credential: Credential | None = None) -> dict:
    """
    获取自己开通的大航海信息

    Args:
        page      (int, optional): 页数. Defaults to 1.

        page_size (int, optional): 每页数量. Defaults to 10.

    Returns:
        dict: 调用 API 返回的结果

    总页数取得方法:

    ```python
    import math

    info = live.get_self_live_info(credential)
    pages = math.ceil(info['data']['guards'] / 10)
    ```
    """
    if credential is None:
        credential = Credential()

    credential.raise_for_no_sessdata()

    api = API["info"]["user_guards"]
    params = {"page": page, "page_size": page_size}
    return await Api(**api, credential=credential).update_params(**params).result_dict()


async def get_self_bag(credential: Credential) -> dict:
    """
    获取自己的直播礼物包裹信息

    Returns:
        dict: 调用 API 返回的结果
    """

    credential.raise_for_no_sessdata()

    api = API["info"]["bag_list"]
    return await Api(**api, credential=credential).result_dict()


async def get_gift_config(
    room_id: int | None = None,
    area_id: int | None = None,
    area_parent_id: int | None = None,
):
    """
    获取所有礼物的信息，包括礼物 id、名称、价格、等级等。

    同时填了 room_id、area_id、area_parent_id，则返回一个较小的 json，只包含该房间、该子区域、父区域的礼物。

    但即使限定了三个条件，仍然会返回约 1.5w 行的 json。不加限定则是 2.8w 行。

    Args:
        room_id (int, optional)         : 房间显示 ID. Defaults to None.
        area_id (int, optional)         : 子分区 ID. Defaults to None.
        area_parent_id (int, optional)  : 父分区 ID. Defaults to None.

    Returns:
        dict: 调用 API 返回的结果
    """
    api = API["info"]["gift_config"]
    params = {
        "platform": "pc",
        "source": "live",
        "room_id": room_id if room_id is not None else "",
        "area_id": area_id if area_id is not None else "",
        "area_parent_id": area_parent_id if area_parent_id is not None else "",
    }
    return await Api(**api).update_params(**params).result


async def get_area_info() -> dict:
    """
    获取所有分区信息

    Returns:
        dict: 调用 API 返回的结果
    """
    api = API["info"]["area_info"]
    return await Api(**api).result_dict()


async def get_live_followers_info(need_recommend: bool = True, credential: Credential | None = None) -> dict:
    """
    获取关注列表中正在直播的直播间信息，包括房间直播热度，房间名称及标题，清晰度，是否官方认证等信息。

    Args:
        need_recommend (bool, optional): 是否接受推荐直播间，Defaults to True

    Returns:
        dict: 调用 API 返回的结果
    """
    if credential is None:
        credential = Credential()

    credential.raise_for_no_sessdata()

    api = API["info"]["followers_live_info"]
    params = {"need_recommend": int(need_recommend), "filterRule": 0}
    return await Api(**api, credential=credential).update_params(**params).result_dict()


async def get_unlive_followers_info(page: int = 1, page_size: int = 30, credential: Credential | None = None) -> dict:
    """
    获取关注列表中未在直播的直播间信息，包括上次开播时间，上次开播的类别，直播间公告，是否有录播等。

    Args:
        page      (int, optional): 页码, Defaults to 1.

        page_size (int, optional): 每页数量 Defaults to 30.

    Returns:
        dict: 调用 API 返回的结果
    """
    if credential is None:
        credential = Credential()

    credential.raise_for_no_sessdata()

    api = API["info"]["followers_unlive_info"]
    params = {
        "page": page,
        "pagesize": page_size,
    }
    return await Api(**api, credential=credential).update_params(**params).result_dict()


async def create_live_reserve(title: str, start_time: int, credential: Credential) -> dict:
    """
    创建直播预约

    Args:
        title (str)         : 直播间标题

        start_time (int)    : 开播时间戳

    Returns:
        dict: 调用 API 返回的结果
    """
    credential.raise_for_no_sessdata()

    api = API["operate"]["create_reserve"]
    data = {
        "title": title,
        "type": 2,
        "live_plan_start_time": start_time,
        "stime": None,
        "from": 1,
    }
    return await Api(**api, credential=credential).update_data(**data).result_dict()


async def get_self_live_watching_history(credential: Credential) -> dict:
    """
    获取用户直播观看记录

    Args:
        credential (Credential): 凭据类

    Returns:
        dict: 调用 API 返回的结果
    """
    credential.raise_for_no_sessdata()

    api = API["info"]["live_history"]
    return await Api(**api, credential=credential).result_dict()
