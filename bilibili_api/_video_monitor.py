"""bilibili_api._video_monitor — 视频在线监控。"""

import asyncio
from enum import Enum
import json
import logging
import struct

from .exceptions import ArgsException
from .utils.aid_bvid_transformer import bvid2aid
from .utils.AsyncEvent import AsyncEvent
from .utils.danmaku import Danmaku
from .utils.network import Api, BiliWsMsgType, Credential, get_client
from .utils.utils import get_api

API = get_api("video")


class VideoOnlineMonitor(AsyncEvent):
    """
    视频在线人数实时监测。

    示例代码：

    ```python
    import asyncio
    from bilibili_api import video

    # 实例化
    r = video.VideoOnlineMonitor("BV1Bf4y1Q7QP")

    # 装饰器方法注册事件监听器
    @r.on("ONLINE")
    async def handler(data):
        print(data)

    # 函数方法注册事件监听器
    async def handler2(data):
        print(data)

    r.add_event_listener("ONLINE", handler2)

    asyncio.get_event_loop().run_until_complete(r.connect())
    ```

    Extends: AsyncEvent

    Logger: VideoOnlineMonitor().logger

    Events:
        ONLINE：        在线人数更新。  CallbackData: dict。
        DANMAKU：       收到实时弹幕。  CallbackData: Danmaku。
        DISCONNECTED：  正常断开连接。  CallbackData: None。
        ERROR:          发生错误。     CallbackData: None。
        CONNECTED:      成功连接。     CallbackData: None。
    """

    class Datapack(Enum):
        """
        数据包类型枚举。

        + CLIENT_VERIFY   : 客户端发送验证信息。
        + SERVER_VERIFY   : 服务端响应验证信息。
        + CLIENT_HEARTBEAT: 客户端发送心跳包。
        + SERVER_HEARTBEAT: 服务端响应心跳包。
        + DANMAKU         : 实时弹幕更新。
        """

        CLIENT_VERIFY = 0x7
        SERVER_VERIFY = 0x8
        CLIENT_HEARTBEAT = 0x2
        SERVER_HEARTBEAT = 0x3
        DANMAKU = 0x3E8

    def __init__(
        self,
        bvid: str | None = None,
        aid: int | None = None,
        page_index: int = 0,
        credential: Credential | None = None,
        debug: bool = False,
    ):
        """
        Args:
            bvid       (str | None, optional)       : BVID. Defaults to None.

            aid        (int | None, optional)       : AID. Defaults to None.

            page_index (int, optional)              : 分 P 序号. Defaults to 0.

            credential (Credential | None, optional): Credential 类. Defaults to None.

            debug      (bool, optional)             : 调试模式，将输出更详细信息. Defaults to False.
        """
        super().__init__()
        self.credential: Credential = credential if credential else Credential()
        # 懒导入避免与 video 模块循环引用
        from .video import Video

        self.__video = Video(bvid, aid, credential=credential)

        # 智能选择在 log 中展示的 ID。
        id_showed = None
        if bvid is not None:
            id_showed = bvid
        else:
            id_showed = aid

        # logger 初始化
        self.logger = logging.getLogger(f"VideoOnlineMonitor-{id_showed}")
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter("[" + str(id_showed) + "][%(asctime)s][%(levelname)s] %(message)s"))
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO if not debug else logging.DEBUG)

        self.__page_index = page_index
        self.__tasks = []

    async def connect(self):
        """
        连接服务器
        """
        await self.__main()

    async def disconnect(self):
        """
        断开服务器
        """
        self.logger.info("主动断开连接。")
        self.dispatch("DISCONNECTED")
        await self.__cancel_all_tasks()
        await self.__client.ws_close(self.__ws)

    async def __main(self):
        """
        入口。
        """
        # 获取分 P id
        pages = await self.__video.get_pages()
        if self.__page_index >= len(pages):
            raise ArgsException("不存在该分 P。")
        cid = pages[self.__page_index]["cid"]

        # 获取服务器信息
        bvid = self.__video.get_bvid()
        self.__bvid = await bvid if asyncio.iscoroutine(bvid) else bvid
        self.logger.debug(f"准备连接：{self.__bvid}")
        self.logger.debug("获取服务器信息中...")

        api = API["info"]["video_online_broadcast_servers"]
        resp = await Api(**api, credential=self.credential).result

        uri = f"wss://{resp['domain']}:{resp['wss_port']}/sub"
        self.__heartbeat_interval = resp["heartbeat"]
        self.logger.debug(f"服务器信息获取成功，URI：{uri}")

        # 连接服务器
        self.logger.debug("准备连接服务器...")
        self.__client = get_client()
        self.__ws = await self.__client.ws_create(uri)

        # 发送认证信息
        self.logger.debug("服务器连接成功，准备发送认证信息...")
        verify_info = {
            "room_id": f"video://{bvid2aid(self.__bvid)}/{cid}",
            "platform": "web",
            "accepts": [1000, 1015],
        }
        verify_info = json.dumps(verify_info, separators=(",", ":"))
        await self.__client.ws_send(
            self.__ws,
            self.__pack(VideoOnlineMonitor.Datapack.CLIENT_VERIFY, 1, verify_info.encode()),
        )

        # 循环接收消息
        while True:
            try:
                data, flag = await self.__client.ws_recv(self.__ws)
            except Exception:
                self.logger.warning("连接被异常断开")
                await self.__cancel_all_tasks()
                self.dispatch("ERROR", "")
                break
            if flag == BiliWsMsgType.BINARY:
                data = self.__unpack(data)
                self.logger.debug(f"收到消息：{data}")
                await self.__handle_data(data)  # type: ignore
            elif flag == BiliWsMsgType.CLOSED:
                break

    async def __handle_data(self, data: list[dict]):
        """
        处理数据。

        Args:
            data (List[dict]): 收到的数据（已解析好）。
        """
        for d in data:
            if d["type"] == VideoOnlineMonitor.Datapack.SERVER_VERIFY.value:
                # 服务器认证反馈。
                if d["data"]["code"] == 0:
                    # 创建心跳 Task
                    heartbeat = asyncio.create_task(self.__heartbeat_task())
                    self.__tasks.append(heartbeat)

                    self.logger.info("连接服务器并验证成功")

            elif d["type"] == VideoOnlineMonitor.Datapack.SERVER_HEARTBEAT.value:
                # 心跳包反馈，同时包含在线人数。
                self.logger.debug(f"收到服务器心跳包反馈，编号：{d['number']}")
                self.logger.info(f"实时观看人数：{d['data']['data']['room']['online']}")
                self.dispatch("ONLINE", d["data"])

            elif d["type"] == VideoOnlineMonitor.Datapack.DANMAKU.value:
                # 实时弹幕。
                info = d["data"][0].split(",")
                text = d["data"][1]
                if info[5] == "0":
                    is_sub = False
                else:
                    is_sub = True
                dm = Danmaku(
                    dm_time=float(info[0]),
                    send_time=int(info[4]),
                    crc32_id=info[6],
                    color=info[3],
                    mode=info[1],
                    font_size=info[2],
                    is_sub=is_sub,
                    text=text,
                )
                self.logger.info(f"收到实时弹幕：{dm.text}")
                self.dispatch("DANMAKU", dm)

            else:
                # 未知类型数据包
                self.logger.warning("收到未知的数据包类型，无法解析：" + json.dumps(d))

    async def __heartbeat_task(self):
        """
        心跳 Task。
        """
        index = 2
        while True:
            self.logger.debug(f"发送心跳包，编号：{index}")
            await self.__client.ws_send(
                self.__ws,
                self.__pack(
                    VideoOnlineMonitor.Datapack.CLIENT_HEARTBEAT,
                    index,
                    b"[object Object]",
                ),
            )
            index += 1
            await asyncio.sleep(self.__heartbeat_interval)

    async def __cancel_all_tasks(self):
        """
        取消所有 Task。
        """
        for task in self.__tasks:
            task.cancel()

    @staticmethod
    def __pack(data_type: Datapack, number: int, data: bytes):
        """
        打包数据。

        # 数据包格式：

        16B 头部:

        | offset(bytes) | length(bytes) | type | description         |
        | ------------- | ------------- | ---- | ------------------- |
        | 0             | 4             | I    | 数据包长度           |
        | 4             | 4             | I    | 固定 0x00120001      |
        | 8             | 4             | I    | 数据包类型           |
        | 12            | 4             | I    | 递增数据包编号        |
        | 16            | 2             | H    | 固定 0x0000           |

        之后是有效载荷。

        # 数据包类型表：

        + 0x7    客户端发送认证信息
        + 0x8    服务端回应认证结果
        + 0x2    客户端发送心跳包，有效载荷：'[object Object]'
        + 0x3    服务端回应心跳包，会带上在线人数等信息，返回 JSON
        + 0x3e8  实时弹幕更新，返回列表，[0]弹幕信息，[1]弹幕文本

        Args:
            data_type (VideoOnlineMonitor.DataType):  数据包类型枚举。

        Returns:
            bytes: 打包好的数据。
        """
        packed_data = bytearray()
        packed_data += struct.pack(">I", 0x00120001)
        packed_data += struct.pack(">I", data_type.value)
        packed_data += struct.pack(">I", number)
        packed_data += struct.pack(">H", 0)
        packed_data += data
        packed_data = struct.pack(">I", len(packed_data) + 4) + packed_data
        return bytes(packed_data)

    @staticmethod
    def __unpack(data: bytes):
        """
        解包数据。

        Args:
            data (bytes):  原始数据。

        Returns:
            tuple(dict): 解包后的数据。
        """
        offset = 0
        real_data = []
        while offset < len(data):
            region_header = struct.unpack(">IIII", data[:16])
            region_data = data[offset : offset + region_header[0]]
            real_data.append(
                {
                    "type": region_header[2],
                    "number": region_header[3],
                    "data": json.loads(region_data[offset + 18 : offset + 18 + (region_header[0] - 16)]),
                }
            )
            offset += region_header[0]
        return tuple(real_data)
