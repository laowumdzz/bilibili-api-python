"""bilibili_api.video — 视频相关接口。"""

"""
bilibili_api.video

视频相关操作

注意，同时存在 page_index 和 cid 的参数，两者至少提供一个。
"""

import datetime
from inspect import iscoroutine, isfunction
import json
import os
import re
from typing import TYPE_CHECKING, Any

from yarl import URL

from . import user
from .exceptions import (
    ArgsException,
    DanmakuClosedException,
    NetworkException,
    ResponseCodeException,
)
from .utils._danmaku_parse import parse_danmaku_segment, parse_danmaku_view
from .utils.aid_bvid_transformer import aid2bvid, bvid2aid
from .utils.BytesReader import BytesReader
from .utils.danmaku import Danmaku, SpecialDanmaku
from .utils.network import Api, Credential
from .utils.utils import get_api, raise_for_statement

if TYPE_CHECKING:
    # 仅供类型检查：运行时 Episode 在 turn_to_episode 内导入（破解 video ↔ bangumi 循环依赖）
    from .bangumi import Episode

API = get_api("video")


async def get_cid_info(cid: int):
    """
    获取 cid 信息 (对应的视频，具体分 P 序号，up 等)

    Returns:
        dict: 调用 https://hd.biliplus.com 的 API 返回的结果
    """
    api = API["info"]["cid_info"]
    params = {"cid": cid}
    return await Api(**api).update_params(**params).result


# re-export：以下导入为公共 API 的一部分，__all__ 保护其不被 F401 移除
from ._video_appeal import DanmakuOperatorType, VideoAppealReasonType
from ._video_download import (
    AudioQuality,
    AudioStreamDownloadURL,
    FLVStreamDownloadURL,
    MP4StreamDownloadURL,
    VideoCodecs,
    VideoDownloadURLDataDetecter,
    VideoQuality,
    VideoStreamDownloadURL,
)
from ._video_monitor import VideoOnlineMonitor
from .utils.AsyncEvent import AsyncEvent
from .utils.network import BiliWsMsgType, get_client

__all__ = [
    "API",
    "AsyncEvent",
    "AudioQuality",
    "AudioStreamDownloadURL",
    "BiliWsMsgType",
    "DanmakuOperatorType",
    "FLVStreamDownloadURL",
    "MP4StreamDownloadURL",
    "Video",
    "VideoAppealReasonType",
    "VideoCodecs",
    "VideoDownloadURLDataDetecter",
    "VideoOnlineMonitor",
    "VideoQuality",
    "VideoStreamDownloadURL",
    "get_cid_info",
    "get_client",
]


class Video:
    """
    视频类，各种对视频的操作均在里面。
    """

    def __init__(
        self,
        bvid: str | None = None,
        aid: int | None = None,
        credential: Credential | None = None,
    ):
        """
        Args:
            bvid       (str | None, optional)       : BV 号. bvid 和 aid 必须提供其中之一。

            aid        (int | None, optional)       : AV 号. bvid 和 aid 必须提供其中之一。

            credential (Credential | None, optional): Credential 类. Defaults to None.
        """
        # ID 检查
        if bvid is not None:
            self.set_bvid(bvid)
        elif aid is not None:
            self.set_aid(aid)
        else:
            # 未提供任一 ID
            raise ArgsException("请至少提供 bvid 和 aid 中的其中一个参数。")

        # 未提供 credential 时初始化该类
        self.credential: Credential = Credential() if credential is None else credential

        # 用于存储视频信息，避免接口依赖视频信息时重复调用
        self.__info: dict | None = None

    def set_bvid(self, bvid: str) -> None:
        """
        设置 bvid。

        Args:
            bvid (str):   要设置的 bvid。
        """
        # 检查 bvid 是否有效
        if not re.search("^BV[a-zA-Z0-9]{10}$", bvid):
            raise ArgsException("bvid 提供错误，必须是以 BV 开头的纯字母和数字组成的 12 位字符串（大小写敏感）。")
        self.__bvid = bvid
        self.__aid = bvid2aid(bvid)

    def get_bvid(self) -> str:
        """
        获取 BVID。

        Returns:
            str: BVID。
        """
        return self.__bvid

    def set_aid(self, aid: int) -> None:
        """
        设置 aid。

        Args:
            aid (int): AV 号。
        """
        if aid <= 0:
            raise ArgsException("aid 不能小于或等于 0。")

        self.__aid = aid
        self.__bvid = aid2bvid(aid)

    def get_aid(self) -> int:
        """
        获取 AID。

        Returns:
            int: aid。
        """
        return self.__aid

    async def __get_bvid(self) -> str:
        res = self.get_bvid()
        if iscoroutine(res):
            return await res
        return res

    async def __get_aid(self) -> str:
        res = self.get_aid()
        if iscoroutine(res):
            return await res
        return res

    async def get_info(self) -> dict:
        """
        获取视频信息。

        Returns:
            dict: 调用 API 返回的结果。
        """
        api = API["info"]["info"]
        params = {"bvid": await self.__get_bvid(), "aid": await self.__get_aid()}
        resp = await Api(**api, credential=self.credential).update_params(**params).result
        # 存入 self.__info 中以备后续调用
        self.__info = resp
        return resp

    async def is_episode(self) -> bool:
        """
        判断视频是否是番剧

        Returns:
            bool: 是否是番剧
        """
        info = await self.__get_info_cached()
        if not info.get("redirect_url"):
            return False
        url = URL(info.get("redirect_url"))
        if url.host == "www.bilibili.com" and len(url.parts) >= 3:
            if url.parts[1] == "bangumi" and url.parts[2] == "play":
                return True
        return False

    async def turn_to_episode(self) -> "Episode":
        """
        将视频转换为番剧

        Returns:
            Episode: 番剧对象
        """
        from .bangumi import Episode

        raise_for_statement(await self.is_episode(), "视频不属于番剧")

        info = await self.__get_info_cached()
        url = URL(info.get("redirect_url"))
        epid = int(url.parts[3][2:])
        return Episode(epid=epid)

    async def get_detail(self) -> dict:
        """
        获取视频详细信息

        Returns:
            dict: 调用 API 返回的结果。
        """
        api = API["info"]["detail"]
        params = {
            "bvid": await self.__get_bvid(),
            "aid": await self.__get_aid(),
            "need_operation_card": 0,
            "need_elec": 0,
        }
        return await Api(**api, credential=self.credential).update_params(**params).result

    async def __get_info_cached(self) -> dict:
        """
        获取视频信息，如果已获取过则使用之前获取的信息，没有则重新获取。

        Returns:
            dict: 调用 API 返回的结果。
        """
        if self.__info is None:
            return await self.get_info()
        return self.__info

    # get_stat 403/404 https://github.com/SocialSisterYi/bilibili-API-collect/issues/797 等恢复
    # async def get_stat(self) -> dict:
    #     """
    #     获取视频统计数据（播放量，点赞数等）。

    #     Returns:
    #         dict: 调用 API 返回的结果。
    #     """
    #     api = API["info"]["stat"]
    #     params = {"bvid": await self.__get_bvid(), "aid": await self.__get_aid()}
    #     return await Api(**api, credential=self.credential).update_params(**params).result

    async def get_up_mid(self) -> int:
        """
        获取视频 up 主的 mid。

        Returns:
            int: up_mid
        """
        info = await self.__get_info_cached()
        return info["owner"]["mid"]

    async def get_tags(self, page_index: int | None = 0, cid: int | None = None) -> list[dict]:
        """
        获取视频标签。

        Args:
            page_index (int | None): 分 P 序号. Defaults to 0.

            cid        (int | None): 分 P 编码. Defaults to None.

        Returns:
            List[dict]: 调用 API 返回的结果。
        """
        if cid is None:
            if page_index is None:
                raise ArgsException("page_index 和 cid 至少提供一个。")

            cid = await self.get_cid(page_index=page_index)
        api = API["info"]["tags"]
        params = {
            "bvid": await self.__get_bvid(),
            "aid": await self.__get_aid(),
            "cid": cid,
        }
        return await Api(**api, credential=self.credential).update_params(**params).result

    async def get_chargers(self) -> dict:
        """
        获取视频充电用户。

        Returns:
            dict: 调用 API 返回的结果。
        """
        info = await self.__get_info_cached()
        mid = info["owner"]["mid"]
        api = API["info"]["chargers"]
        params = {
            "aid": await self.__get_aid(),
            "bvid": await self.__get_bvid(),
            "mid": mid,
        }
        return await Api(**api, credential=self.credential).update_params(**params).result

    async def get_pages(self) -> list[dict]:
        """
        获取分 P 信息。

        Returns:
            dict: 调用 API 返回的结果。
        """
        api = API["info"]["pages"]
        params = {"aid": await self.__get_aid(), "bvid": await self.__get_bvid()}
        return await Api(**api, credential=self.credential).update_params(**params).result

    async def __get_cid_by_index(self, page_index: int) -> int:
        """
        根据分 p 号获取 cid。

        Args:
            page_index (int):   分 P 号，从 0 开始。

        Returns:
            int: cid 分 P 的唯一 ID。
        """
        if page_index < 0:
            raise ArgsException("分 p 号必须大于或等于 0。")

        info = await self.__get_info_cached()
        pages = info["pages"]

        if len(pages) <= page_index:
            raise ArgsException("不存在该分 p。")

        page = pages[page_index]
        cid = page["cid"]
        return cid

    async def get_video_snapshot(
        self,
        cid: int | None = None,
        json_index: bool = False,
        pvideo: bool = True,
    ) -> dict:
        """
        获取视频快照(视频各个时间段的截图拼图)

        Args:
            cid(int): 分 P CID(可选)

            json_index(bool): json 数组截取时间表 True 为需要，False 不需要

            pvideo(bool): 是否只获取预览

        Returns:
            dict: 调用 API 返回的结果,数据中 Url 没有 http 头
        """
        params: dict[str, Any] = {"aid": await self.__get_aid()}
        if pvideo:
            api = API["info"]["video_snapshot_pvideo"]
        else:
            params["bvid"] = await self.__get_bvid()
            if json_index:
                params["index"] = 1
            if cid:
                params["cid"] = cid
            api = API["info"]["video_snapshot"]
        return await Api(**api, credential=self.credential).update_params(**params).result

    async def get_cid(self, page_index: int) -> int:
        """
        获取稿件 cid

        Args:
            page_index(int): 分 P

        Returns:
            int: cid
        """
        return await self.__get_cid_by_index(page_index)

    async def get_download_url(
        self,
        page_index: int | None = None,
        cid: int | None = None,
        html5: bool = False,
    ) -> dict:
        """
        获取视频下载信息。

        返回结果可以传入 `VideoDownloadURLDataDetecter` 进行解析。

        page_index 和 cid 至少提供其中一个，其中 cid 优先级最高

        Args:
            page_index (int | None, optional) : 分 P 号，从 0 开始。Defaults to None

            cid        (int | None, optional) : 分 P 的 ID。Defaults to None

            html5      (bool, optional)       : 是否选择移动端 HTML5 播放流（仅支持 MP4 格式）此时获得的媒体流访问无需鉴权。

        Returns:
            dict: 调用 API 返回的结果。
        """
        if cid is None:
            if page_index is None:
                raise ArgsException("page_index 和 cid 至少提供一个。")

            cid = await self.__get_cid_by_index(page_index)

        api = API["info"]["playurl"]
        params = {
            "qn": "127",
            "fnval": 4048,
            "fnver": 0,
            "fourk": 1,
            "gaia_source": "pre-load",
            "isGaiaAvoided": "true",
            "avid": await self.__get_aid(),
            "bvid": await self.__get_bvid(),
            "cid": cid,
            "from_client": "BROWSER",
            "web_location": 1315873,
        }
        if html5:
            params["platform"] = "html5"
            params["high_quality"] = "1"
        return await Api(**api, credential=self.credential, wbi=True).update_params(**params).result

    async def get_related(self) -> dict:
        """
        获取相关视频信息。

        Returns:
            dict: 调用 API 返回的结果。
        """
        api = API["info"]["related"]
        params = {"aid": await self.__get_aid(), "bvid": await self.__get_bvid()}
        return await Api(**api, credential=self.credential).update_params(**params).result

    async def get_relation(self) -> dict:
        """
        获取用户与视频的关系

        Returns:
            dict: 调用 API 返回的结果。
        """
        self.credential.raise_for_no_sessdata()
        api = API["info"]["relation"]
        params = {"aid": await self.__get_aid(), "bvid": await self.__get_bvid()}
        return await Api(**api, credential=self.credential).update_params(**params).result

    async def has_liked(self) -> bool:
        """
        视频是否点赞过。

        Returns:
            bool: 视频是否点赞过。
        """
        self.credential.raise_for_no_sessdata()

        api = API["info"]["has_liked"]
        params = {"bvid": await self.__get_bvid(), "aid": await self.__get_aid()}
        return await Api(**api, credential=self.credential).update_params(**params).result

    async def get_pay_coins(self) -> int:
        """
        获取视频已投币数量。

        Returns:
            int: 视频已投币数量。
        """
        self.credential.raise_for_no_sessdata()

        api = API["info"]["get_pay_coins"]
        params = {"bvid": await self.__get_bvid(), "aid": await self.__get_aid()}
        return (await Api(**api, credential=self.credential).update_params(**params).result)["multiply"]

    async def has_favoured(self) -> bool:
        """
        是否已收藏。

        Returns:
            bool: 视频是否已收藏。
        """
        self.credential.raise_for_no_sessdata()

        api = API["info"]["has_favoured"]
        params = {"bvid": await self.__get_bvid(), "aid": await self.__get_aid()}
        return (await Api(**api, credential=self.credential).update_params(**params).result)["favoured"]

    async def is_forbid_note(self) -> bool:
        """
        是否禁止笔记。

        Returns:
            bool: 是否禁止笔记。
        """
        api = API["info"]["is_forbid"]
        params = {"aid": await self.__get_aid()}
        return (await Api(**api, credential=self.credential).update_params(**params).result)["forbid_note_entrance"]

    async def get_private_notes_list(self) -> list:
        """
        获取稿件私有笔记列表。

        Returns:
            list: note_Ids。
        """
        self.credential.raise_for_no_sessdata()

        api = API["info"]["private_notes"]
        params = {"oid": await self.__get_aid(), "oid_type": 0}
        return (await Api(**api, credential=self.credential).update_params(**params).result)["noteIds"]

    async def get_public_notes_list(self, pn: int, ps: int) -> dict:
        """
        获取稿件公开笔记列表。

        Args:
            pn (int): 页码

            ps (int): 每页项数

        Returns:
            dict: 调用 API 返回的结果。
        """

        api = API["info"]["public_notes"]
        params = {"oid": await self.__get_aid(), "oid_type": 0, "pn": pn, "ps": ps}
        return await Api(**api, credential=self.credential).update_params(**params).result

    async def get_ai_conclusion(
        self,
        cid: int | None = None,
        page_index: int | None = None,
        up_mid: int | None = None,
    ) -> dict:
        """
        获取稿件 AI 总结结果。

        cid 和 page_index 至少提供其中一个，其中 cid 优先级最高

        Args:
            cid (Optional, int): 分 P 的 cid。

            page_index (Optional, int): 分 P 号，从 0 开始。

            up_mid (Optional, int): up 主的 mid。

        Returns:
            dict: 调用 API 返回的结果。
        """
        if cid is None:
            if page_index is None:
                raise ArgsException("page_index 和 cid 至少提供一个。")

            cid = await self.__get_cid_by_index(page_index)

        api = API["info"]["ai_conclusion"]
        params = {
            "aid": await self.__get_aid(),
            "bvid": await self.__get_bvid(),
            "cid": cid,
            "up_mid": await self.get_up_mid() if up_mid is None else up_mid,
            "web_location": "333.788",
        }
        return await Api(**api, credential=self.credential).update_params(**params).result

    async def get_danmaku_view(self, page_index: int | None = None, cid: int | None = None) -> dict:
        """
        获取弹幕设置、特殊弹幕、弹幕数量、弹幕分段等信息。

        Args:
            page_index (int, optional): 分 P 号，从 0 开始。Defaults to None

            cid        (int, optional): 分 P 的 ID。Defaults to None

        Returns:
            dict: 调用 API 返回的结果。
        """
        if cid is None:
            if page_index is None:
                raise ArgsException("page_index 和 cid 至少提供一个。")

            cid = await self.__get_cid_by_index(page_index)

        api = API["danmaku"]["view"]
        params = {"type": 1, "oid": cid, "pid": await self.__get_aid()}

        try:
            resp_data = await Api(**api, credential=self.credential).update_params(**params).request(byte=True)
        except (NetworkException, ResponseCodeException) as e:
            raise NetworkException(-1, str(e)) from e

        return parse_danmaku_view(resp_data)

    async def get_danmakus(
        self,
        page_index: int = 0,
        date: datetime.date | None = None,
        cid: int | None = None,
        from_seg: int | None = None,
        to_seg: int | None = None,
    ) -> list[Danmaku]:
        """
        获取弹幕。

        Args:
            page_index (int, optional): 分 P 号，从 0 开始。Defaults to None

            date       (datetime.Date | None, optional): 指定日期后为获取历史弹幕，精确到年月日。Defaults to None.

            cid        (int | None, optional): 分 P 的 ID。Defaults to None

            from_seg (int, optional): 从第几段开始(0 开始编号，None 为从第一段开始，一段 6 分钟). Defaults to None.

            to_seg (int, optional): 到第几段结束(0 开始编号，None 为到最后一段，包含编号的段，一段 6 分钟). Defaults to None.

        Returns:
            List[Danmaku]: Danmaku 类的列表。

        注意：
            - 1. 段数可以通过视频时长计算。6分钟为一段。
            - 2. `from_seg` 和 `to_seg` 仅对 `date == None` 的时候有效果。
            - 3. 例：取前 `12` 分钟的弹幕：`from_seg=0, to_seg=1`
        """
        if date is not None:
            self.credential.raise_for_no_sessdata()

        if cid is None:
            if page_index is None:
                raise ArgsException("page_index 和 cid 至少提供一个。")

            cid = await self.__get_cid_by_index(page_index)

        aid = await self.__get_aid()
        params: dict[str, Any] = {"oid": cid, "type": 1, "pid": aid}
        if date is not None:
            # 获取历史弹幕
            api = API["danmaku"]["get_history_danmaku"]
            params["date"] = date.strftime("%Y-%m-%d")
            params["type"] = 1
            from_seg = to_seg = 0
        else:
            api = API["danmaku"]["get_danmaku"]
            if from_seg is None:
                from_seg = 0
            if to_seg is None:
                info = await self.__get_info_cached()
                for p in info["pages"]:
                    if p["cid"] == cid:
                        to_seg = p["duration"] // 360 + 1

        danmakus = []

        for seg in range(from_seg, to_seg + 1):
            if date is None:
                # 仅当获取当前弹幕时需要该参数
                params["segment_index"] = seg + 1
            try:
                data = await Api(**api, credential=self.credential).update_params(**params).request(byte=True)
            except (NetworkException, ResponseCodeException) as e:
                raise NetworkException(-1, str(e)) from e

            if data == b"\x10\x01":
                # 视频弹幕被关闭
                raise DanmakuClosedException()

            danmakus.extend(parse_danmaku_segment(data))
        return danmakus

    async def get_special_dms(self, page_index: int = 0, cid: int | None = None) -> list[SpecialDanmaku]:
        """
        获取特殊弹幕

        Args:
            page_index (int, optional)       : 分 P 号. Defaults to 0.

            cid        (int | None, optional): 分 P id. Defaults to None.

        Returns:
            List[SpecialDanmaku]: 调用接口解析后的结果
        """
        if cid is None:
            if page_index is None:
                raise ArgsException("page_index 和 cid 至少提供一个。")

            cid = await self.__get_cid_by_index(page_index)

        view = await self.get_danmaku_view(cid=cid)
        if not view.get("special_dms"):
            return []
        dms: list[SpecialDanmaku] = []
        for special_dms in view["special_dms"]:
            dm_content = await Api(url=special_dms, method="GET", credential=self.credential).request(byte=True)
            reader = BytesReader(dm_content)
            while not reader.has_end():
                spec_dm = SpecialDanmaku("")
                type_ = reader.varint() >> 3
                if type_ == 1:
                    reader_ = BytesReader(reader.bytes_string())
                    while not reader_.has_end():
                        type__ = reader_.varint() >> 3
                        if type__ == 1:
                            spec_dm.id_ = reader_.varint()
                        elif type__ == 3:
                            spec_dm.mode = reader_.varint()
                        elif type__ == 4:
                            reader_.varint()
                        elif type__ == 5:
                            reader_.varint()
                        elif type__ == 6:
                            reader_.string()
                        elif type__ == 7:
                            spec_dm.content = reader_.string()
                        elif type__ == 8:
                            reader_.varint()
                        elif type__ == 11:
                            spec_dm.pool = reader_.varint()
                        elif type__ == 12:
                            spec_dm.id_str = reader_.string()
                        else:
                            continue
                else:
                    continue
                dms.append(spec_dm)
        return dms

    async def get_history_danmaku_index(
        self,
        page_index: int | None = None,
        date: datetime.date | None = None,
        cid: int | None = None,
    ) -> list[str] | None:
        """
        获取特定月份存在历史弹幕的日期。

        Args:
            page_index (int | None, optional): 分 P 号，从 0 开始。Defaults to None

            date       (datetime.date | None): 精确到年月. Defaults to None。

            cid        (int | None, optional): 分 P 的 ID。Defaults to None

        Returns:
            None | List[str]: 调用 API 返回的结果。不存在时为 None。
        """
        if date is None:
            raise ArgsException("请提供 date 参数")

        self.credential.raise_for_no_sessdata()

        if cid is None:
            if page_index is None:
                raise ArgsException("page_index 和 cid 至少提供一个。")

            cid = await self.__get_cid_by_index(page_index)

        api = API["danmaku"]["get_history_danmaku_index"]
        params = {"oid": cid, "month": date.strftime("%Y-%m"), "type": 1}
        return await Api(**api, credential=self.credential).update_params(**params).result

    async def has_liked_danmakus(
        self,
        page_index: int | None = None,
        ids: list[int] | None = None,
        cid: int | None = None,
    ) -> dict:
        """
        是否已点赞弹幕。

        Args:
            page_index (int | None, optional): 分 P 号，从 0 开始。Defaults to None

            ids        (List[int] | None): 要查询的弹幕 ID 列表。

            cid        (int | None, optional): 分 P 的 ID。Defaults to None

        Returns:
            dict: 调用 API 返回的结果。
        """
        if ids is None or len(ids) == 0:
            raise ArgsException("请提供 ids 参数并至少有一个元素")

        self.credential.raise_for_no_sessdata()

        if cid is None:
            if page_index is None:
                raise ArgsException("page_index 和 cid 至少提供一个。")

            cid = await self.__get_cid_by_index(page_index)

        api = API["danmaku"]["has_liked_danmaku"]
        params = {"oid": cid, "ids": ",".join(ids)}  # type: ignore
        return await Api(**api, credential=self.credential).update_params(**params).result

    async def send_danmaku(
        self,
        page_index: int | None = None,
        danmaku: Danmaku | None = None,
        cid: int | None = None,
    ) -> dict:
        """
        发送弹幕。

        Args:
            page_index (int | None, optional): 分 P 号，从 0 开始。Defaults to None

            danmaku    (Danmaku | None)      : Danmaku 类。

            cid        (int | None, optional): 分 P 的 ID。Defaults to None

        Returns:
            dict: 调用 API 返回的结果。
        """

        if danmaku is None:
            raise ArgsException("请提供 danmaku 参数")

        self.credential.raise_for_no_sessdata()
        self.credential.raise_for_no_bili_jct()

        if cid is None:
            if page_index is None:
                raise ArgsException("page_index 和 cid 至少提供一个。")

            cid = await self.__get_cid_by_index(page_index)

        api = API["danmaku"]["send_danmaku"]

        if danmaku.is_sub:
            pool = 1
        else:
            pool = 0
        data = {
            "type": 1,
            "oid": cid,
            "msg": danmaku.text,
            "aid": await self.__get_aid(),
            "bvid": await self.__get_bvid(),
            "progress": int(danmaku.dm_time * 1000),
            "color": int(danmaku.color, 16),
            "fontsize": danmaku.font_size,
            "pool": pool,
            "mode": danmaku.mode,
            "plat": 1,
        }
        return await Api(**api, credential=self.credential).update_data(**data).result

    async def get_danmaku_xml(self, page_index: int | None = None, cid: int | None = None) -> str:
        """
        获取所有弹幕的 xml 源文件（非装填）

        Args:
            page_index (int, optional)       : 分 P 序号. Defaults to 0.

            cid        (int | None, optional): cid. Defaults to None.

        Return:
            str: xml 文件源
        """
        if cid is None:
            if page_index is None:
                raise ArgsException("page_index 和 cid 至少提供一个。")

            cid = await self.__get_cid_by_index(page_index)
        url = f"https://comment.bilibili.com/{cid}.xml"
        return (await Api(url=url, method="GET").request(byte=True)).decode("utf-8")

    async def like_danmaku(
        self,
        page_index: int | None = None,
        dmid: int | None = None,
        status: bool | None = True,
        cid: int | None = None,
    ) -> dict:
        """
        点赞弹幕。

        Args:
            page_index (int | None, optional) : 分 P 号，从 0 开始。Defaults to None

            dmid       (int | None)           : 弹幕 ID。

            status     (bool | None, optional): 点赞状态。Defaults to True

            cid        (int | None, optional) : 分 P 的 ID。Defaults to None

        Returns:
            dict: 调用 API 返回的结果。
        """
        if dmid is None:
            raise ArgsException("请提供 dmid 参数")

        self.credential.raise_for_no_sessdata()
        self.credential.raise_for_no_bili_jct()

        if cid is None:
            if page_index is None:
                raise ArgsException("page_index 和 cid 至少提供一个。")

            cid = await self.__get_cid_by_index(page_index)

        api = API["danmaku"]["like_danmaku"]

        data = {
            "dmid": dmid,
            "oid": cid,
            "op": 1 if status else 2,
            "platform": "web_player",
        }
        return await Api(**api, credential=self.credential).update_data(**data).result

    async def get_online(self, cid: int | None = None, page_index: int | None = 0) -> dict:
        """
        获取实时在线人数

        Returns:
            dict: 调用 API 返回的结果。
        """
        api = API["info"]["online"]
        params = {
            "aid": await self.__get_aid(),
            "bvid": await self.__get_bvid(),
            "cid": (cid if cid is not None else await self.get_cid(page_index=page_index)),
        }
        return await Api(**api, credential=self.credential).update_params(**params).result

    async def operate_danmaku(
        self,
        page_index: int | None = None,
        dmids: list[int] | None = None,
        cid: int | None = None,
        type_: DanmakuOperatorType | None = None,
    ) -> dict:
        """
        操作弹幕

        Args:
            page_index (int | None, optional)      : 分 P 号，从 0 开始。Defaults to None

            dmids      (List[int] | None)          : 弹幕 ID 列表。

            cid        (int | None, optional)      : 分 P 的 ID。Defaults to None

            type_      (DanmakuOperatorType | None): 操作类型

        Returns:
            dict: 调用 API 返回的结果。
        """

        if dmids is None or len(dmids) == 0:
            raise ArgsException("请提供 dmid 参数")

        if type_ is None:
            raise ArgsException("请提供 type_ 参数")

        self.credential.raise_for_no_sessdata()
        self.credential.raise_for_no_bili_jct()

        if cid is None:
            if page_index is None:
                raise ArgsException("page_index 和 cid 至少提供一个。")

            cid = await self.__get_cid_by_index(page_index)

        api = API["danmaku"]["edit_danmaku"]

        data = {
            "type": 1,
            "dmids": ",".join(str(x) for x in dmids),
            "oid": cid,
            "state": type_.value,
        }

        return await Api(**api, credential=self.credential).update_data(**data).result

    async def like(self, status: bool = True) -> dict:
        """
        点赞视频。

        Args:
            status (bool, optional): 点赞状态。Defaults to True.

        Returns:
            dict: 调用 API 返回的结果。
        """
        self.credential.raise_for_no_sessdata()
        self.credential.raise_for_no_bili_jct()

        api = API["operate"]["like"]
        data = {"aid": await self.__get_aid(), "like": 1 if status else 2}
        return await Api(**api, credential=self.credential).update_data(**data).result

    async def pay_coin(self, num: int = 1, like: bool = False) -> dict:
        """
        投币。

        Args:
            num  (int, optional) : 硬币数量，为 1 ~ 2 个。Defaults to 1.

            like (bool, optional): 是否同时点赞。Defaults to False.

        Returns:
            dict: 调用 API 返回的结果。
        """
        self.credential.raise_for_no_sessdata()
        self.credential.raise_for_no_bili_jct()

        if num not in (1, 2):
            raise ArgsException("投币数量只能是 1 ~ 2 个。")

        api = API["operate"]["coin"]
        data = {
            "aid": await self.__get_aid(),
            "bvid": await self.__get_bvid(),
            "multiply": num,
            "like": 1 if like else 0,
        }
        return await Api(**api, credential=self.credential).update_data(**data).result

    async def share(self) -> int:
        """
        分享视频

        Returns:
            int: 当前分享数
        """
        api = API["operate"]["share"]
        data = {
            "bvid": await self.__get_bvid(),
            "aid": await self.__get_aid(),
            "csrf": self.credential.bili_jct,
        }
        return await Api(**api, credential=self.credential).update_data(**data).result

    async def triple(self) -> dict:
        """
        给阿婆主送上一键三连

        Returns:
            dict: 调用 API 返回的结果
        """
        api = API["operate"]["yjsl"]
        data = {"bvid": await self.__get_bvid(), "aid": await self.__get_aid()}
        return await Api(**api, credential=self.credential).update_data(**data).result

    async def add_tag(self, name: str) -> dict:
        """
        添加标签。

        Args:
            name (str): 标签名字。

        Returns:
            dict: 调用 API 返回的结果。会返回标签 ID。
        """
        self.credential.raise_for_no_sessdata()
        self.credential.raise_for_no_bili_jct()

        api = API["operate"]["add_tag"]
        data = {
            "aid": await self.__get_aid(),
            "bvid": await self.__get_bvid(),
            "tag_name": name,
        }
        return await Api(**api, credential=self.credential).update_data(**data).result

    async def delete_tag(self, tag_id: int) -> dict:
        """
        删除标签。

        Args:
            tag_id (int): 标签 ID。

        Returns:
            dict: 调用 API 返回的结果。
        """
        self.credential.raise_for_no_sessdata()
        self.credential.raise_for_no_bili_jct()

        api = API["operate"]["del_tag"]

        data = {
            "tag_id": tag_id,
            "aid": await self.__get_aid(),
            "bvid": await self.__get_bvid(),
        }
        return await Api(**api, credential=self.credential).update_data(**data).result

    async def appeal(self, reason: Any, detail: str):
        """
        投诉稿件

        Args:
            reason (Any): 投诉类型。传入 VideoAppealReasonType 中的项目即可。

            detail (str): 详情信息。

        Returns:
            dict: 调用 API 返回的结果
        """
        api = API["operate"]["appeal"]
        data = {"aid": await self.__get_aid(), "desc": detail}
        if isfunction(reason):
            reason = reason()
        if isinstance(reason, int):
            reason = {"tid": reason}
        data.update(reason)
        # XXX: 暂不支持上传附件
        return await Api(**api, credential=self.credential).update_data(**data).result

    async def set_favorite(
        self, add_media_ids: list[int] | None = None, del_media_ids: list[int] | None = None
    ) -> dict:
        """
        设置视频收藏状况。

        **如果视频是番剧 `await is_bangumi()`，请转为 `Episode` 类收藏**

        Args:
            add_media_ids (List[int] | None, optional): 要添加到的收藏夹 ID. Defaults to None（等价于 []）.

            del_media_ids (List[int] | None, optional): 要移出的收藏夹 ID. Defaults to None（等价于 []）.

        Returns:
            dict: 调用 API 返回结果。
        """
        add_media_ids = [] if add_media_ids is None else add_media_ids
        del_media_ids = [] if del_media_ids is None else del_media_ids
        if len(add_media_ids) + len(del_media_ids) == 0:
            raise ArgsException("对收藏夹无修改。请至少提供 add_media_ids 和 del_media_ids 中的其中一个。")

        self.credential.raise_for_no_sessdata()
        self.credential.raise_for_no_bili_jct()

        api = API["operate"]["favorite"]
        data = {
            "rid": await self.__get_aid(),
            "type": 2,
            "add_media_ids": ",".join(str(x) for x in add_media_ids),
            "del_media_ids": ",".join(str(x) for x in del_media_ids),
        }
        return await Api(**api, credential=self.credential).update_data(**data).result

    async def get_subtitle(
        self,
        cid: int | None = None,
    ) -> dict:
        """
        获取字幕信息

        Args:
            cid (int | None): 分 P ID,从视频信息中获取

        Returns:
            dict: 调用 API 返回的结果
        """
        if cid is None:
            raise ArgsException("需要 cid")

        return (await self.get_player_info(cid=cid)).get("subtitle")

    async def get_player_info(
        self,
        cid: int | None = None,
        epid: int | None = None,
    ) -> dict:
        """
        获取视频上一次播放的记录，字幕和地区信息。需要分集的 cid, 返回数据中含有json字幕的链接

        Args:
            cid (int | None): 分 P ID,从视频信息中获取

            epid (int | None): 番剧分集 ID,从番剧信息中获取

        Returns:
            dict: 调用 API 返回的结果
        """
        if cid is None:
            raise ArgsException("需要 cid")
        api = API["info"]["get_player_info"]

        params = {
            "aid": await self.__get_aid(),
            "cid": cid,
            "isGaiaAvoided": False,
            "web_location": 1315873,
        }

        if epid:
            params["epid"] = epid

        return await Api(**api, credential=self.credential).update_params(**params).result

    async def submit_subtitle(
        self,
        lan: str,
        data: dict,
        submit: bool,
        sign: bool,
        page_index: int | None = None,
        cid: int | None = None,
    ) -> dict:
        """
        上传字幕

        字幕数据 data 参考：

        ```json
        {
          "font_size": "float: 字体大小，默认 0.4",
          "font_color": "str: 字体颜色，默认 \"#FFFFFF\"",
          "background_alpha": "float: 背景不透明度，默认 0.5",
          "background_color": "str: 背景颜色，默认 \"#9C27B0\"",
          "Stroke": "str: 描边，目前作用未知，默认为 \"none\"",
          "body": [
            {
              "from": "int: 字幕开始时间（秒）",
              "to": "int: 字幕结束时间（秒）",
              "location": "int: 字幕位置，默认为 2",
              "content": "str: 字幕内容"
            }
          ]
        }
        ```

        Args:
            lan        (str)                 : 字幕语言代码，参考 https://s1.hdslb.com/bfs/subtitle/subtitle_lan.json

            data       (dict)                : 字幕数据

            submit     (bool)                : 是否提交，不提交为草稿

            sign       (bool)                : 是否署名

            page_index (int | None, optional): 分 P 索引. Defaults to None.

            cid        (int | None, optional): 分 P id. Defaults to None.

        Returns:
            dict: API 调用返回结果

        """
        if cid is None:
            if page_index is None:
                raise ArgsException("page_index 和 cid 至少提供一个。")

            cid = await self.__get_cid_by_index(page_index)

        self.credential.raise_for_no_sessdata()
        self.credential.raise_for_no_bili_jct()

        api = API["operate"]["submit_subtitle"]

        # lan check，应该是这里面的语言代码
        with open(
            os.path.join(os.path.dirname(__file__), "data/subtitle_lan.json"),
            encoding="utf-8",
        ) as f:
            subtitle_lans = json.load(f)
            for lan_template in subtitle_lans:
                if lan_template["lan"] == lan:
                    break
            else:
                raise ArgsException("lan 参数错误，请参见 https://s1.hdslb.com/bfs/subtitle/subtitle_lan.json")

        payload = {
            "type": 1,
            "oid": cid,
            "lan": lan,
            "data": json.dumps(data),
            "submit": submit,
            "sign": sign,
            "bvid": await self.__get_bvid(),
        }

        return await Api(**api, credential=self.credential).update_data(**payload).result

    async def get_danmaku_snapshot(self) -> dict:
        """
        获取弹幕快照

        Returns:
            dict: 调用 API 返回的结果
        """
        api = API["danmaku"]["snapshot"]

        params = {"aid": await self.__get_aid()}

        return await Api(**api, credential=self.credential).update_params(**params).result

    async def recall_danmaku(
        self,
        page_index: int | None = None,
        dmid: int = 0,
        cid: int | None = None,
    ) -> dict:
        """
        撤回弹幕

        Args:
            page_index(int | None, optional): 分 P 号

            dmid(int)      : 弹幕 id

            cid(int | None, optional)       : 分 P 编码
        Returns:
            dict: 调用 API 返回的结果
        """
        if cid is None:
            if page_index is None:
                raise ArgsException("page_index 和 cid 至少提供一个。")

            cid = await self.__get_cid_by_index(page_index)

        self.credential.raise_for_no_sessdata()
        self.credential.raise_for_no_bili_jct()

        api = API["danmaku"]["recall"]
        data = {"dmid": dmid, "cid": cid}

        return await Api(**api, credential=self.credential).update_data(**data).result

    async def get_pbp(self, page_index: int | None = None, cid: int | None = None) -> dict:
        """
        获取高能进度条

        Args:
            page_index(int | None): 分 P 号

            cid(int | None)       : 分 P 编码

        Returns:
            dict: 调用 API 返回的结果
        """
        if cid is None:
            if page_index is None:
                raise ArgsException("page_index 和 cid 至少提供一个。")

            cid = await self.__get_cid_by_index(page_index)

        api = API["info"]["pbp"]
        params = {"cid": cid}
        return await Api(**api, credential=self.credential).update_params(**params).request(raw=True)

    async def add_to_toview(self) -> dict:
        """
        添加视频至稍后再看列表

        Returns:
            dict: 调用 API 返回的结果
        """
        self.credential.raise_for_no_sessdata()
        self.credential.raise_for_no_bili_jct()
        api = get_api("toview")["operate"]["add"]
        datas = {
            "aid": await self.__get_aid(),
        }
        return await Api(**api, credential=self.credential).update_data(**datas).result

    async def delete_from_toview(self) -> dict:
        """
        从稍后再看列表删除视频

        Returns:
            dict: 调用 API 返回的结果
        """
        self.credential.raise_for_no_sessdata()
        self.credential.raise_for_no_bili_jct()
        api = get_api("toview")["operate"]["del"]
        datas = {"viewed": "false", "aid": await self.__get_aid()}
        return await Api(**api, credential=self.credential).update_data(**datas).result

    async def report_watch_history(self, progress: int = 0, page_index: int | None = 0, cid: int | None = None) -> dict:
        """
        上报观看历史
        Args:
            progress        (int):          观看进度 (单位 秒)
            page_index      (int | None):   分 P 序号
            cid             (int | None):   分 P ID,从视频信息中获取

        Returns:
            dict: 调用 API 返回的结果
        """

        if cid is None:
            if page_index is None:
                raise ArgsException("page_index 和 cid 至少提供一个。")

            cid = await self.get_cid(page_index=page_index)

        api = get_api("video")["operate"]["report_history"]
        data = {
            "aid": self.get_aid(),
            "cid": cid,
            "progress": progress,
            "csrf": self.credential.bili_jct,
        }
        return await Api(**api, credential=self.credential).update_data(**data).request(raw=True)

    async def report_start_watching(self, page_index: int | None = 0) -> dict:
        """
        上报开始观看
        该接口亦被用于计算播放量, 播放量更新不是实时的
        该接口使用似乎存在 200 播放限制, 请勿滥用!
        Args:
            page_index      (int | None):   分 P 序号

        Returns:
            dict: 调用 API 返回的结果
        """
        self_info = await user.get_self_info(self.credential)

        if page_index is None:
            raise ArgsException("必须提供 page_index")

        cid = await self.get_cid(page_index=page_index)

        api = get_api("video")["operate"]["report_start_watching"]
        data = {
            "aid": await self.__get_aid(),
            "cid": cid,
            "mid": self_info["mid"],
            "part": page_index,
            "csrf": self.credential.bili_jct,
        }
        return await Api(**api, credential=self.credential).update_data(**data).request(raw=True)
