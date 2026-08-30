"""
bilibili_api.utils._log — 请求日志。
"""

import logging

from .AsyncEvent import AsyncEvent


class RequestLog(AsyncEvent):
    def __init__(self) -> None:
        super().__init__()
        self.logger: logging.Logger = logging.getLogger("bilibili-api-request")
        self.logger.setLevel(logging.INFO)
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter("[BILIBILI_API][%(asctime)s][%(levelname)s] %(message)s"))
            self.logger.addHandler(handler)
        self.__on = False
        self.__on_events: list[str] = [
            "API_REQUEST",
            "API_RESPONSE",
            "ANTI_SPIDER",
            "WS_CONNECT",
            "WS_RECV",
            "WS_SEND",
            "WS_CLOSE",
        ]
        self.__ignore_events: list[str] = []
        # 内部日志监听器仅在日志开启（set_on(True)）时注册，
        # 避免关闭状态下每次请求仍产生事件分发开销。

    def get_on_events(self) -> list[str]:
        """
        获取日志输出支持的事件类型

        Returns:
            List[str]: 日志输出支持的事件类型
        """
        return self.__on_events

    def set_on_events(self, events: list[str]) -> None:
        """
        设置日志输出支持的事件类型

        Args:
            events (List[str]): 日志输出支持的事件类型
        """
        self.__on_events = events

    def get_ignore_events(self) -> list[str]:
        """
        获取日志输出排除的事件类型

        Returns:
            List[str]: 日志输出排除的事件类型
        """
        return self.__ignore_events

    def set_ignore_events(self, events: list[str]) -> None:
        """
        设置日志输出排除的事件类型

        Args:
            events (List[str]): 日志输出排除的事件类型
        """
        self.__ignore_events = events

    def is_on(self) -> bool:
        """
        获取日志输出是否启用

        Returns:
            bool: 是否启用
        """
        return self.__on

    def set_on(self, status: bool) -> None:
        """
        设置日志输出是否启用

        Args:
            status (bool): 是否启用
        """
        if status and not self.__on:
            self.add_event_listener("__ALL__", self.__handle_events)
        elif not status and self.__on:
            self.remove_event_listener("__ALL__", self.__handle_events)
        self.__on = status

    def __handle_events(self, data: dict) -> None:
        evt = data["name"]
        desc, real_data = data["data"]
        if self.__on and evt in self.get_on_events() and evt not in self.get_ignore_events():
            # 注意：real_data 与具名事件监听器共享同一 dict 对象（异步监听器更以 task 延后执行），
            # 此处不得 pop/原地修改，否则异步监听器将读不到 id 等键。
            if evt.startswith("WS_"):
                ws_id = real_data.get("id")
                payload = {k: v for k, v in real_data.items() if k != "id"}
                self.logger.info(f"WS #{ws_id} {desc}: {payload}")
            elif evt.startswith("DWN_"):
                dwn_id = real_data.get("id")
                payload = {k: v for k, v in real_data.items() if k != "id"}
                self.logger.info(f"DWN #{dwn_id} {desc}: {payload}")
            elif evt.startswith("API_"):
                api_id = real_data.get("id")
                payload = {k: v for k, v in real_data.items() if k != "id"}
                self.logger.info(f"API #{api_id} {desc}: {payload}")
            elif evt == "ANTI_SPIDER":
                msg = f"{real_data['msg']}"
                if "id" in real_data:
                    msg = f"{msg}（API #{real_data['id']}）"
                self.logger.info(msg)
            else:
                self.logger.info(f"{desc}: {real_data}")


request_log = RequestLog()
"""
请求日志支持，默认支持输出到指定 I/O 对象。

可以添加更多监听器达到更多效果。

Logger: request_log.logger

Extends: AsyncEvent

Events:

- (模块自带 BiliAPIClient)
- REQUEST:     HTTP 请求。
- RESPONSE:    HTTP 响应。
- WS_CREATE:   新建的 Websocket 请求。
- WS_RECV:     获得到 WebSocket 请求。
- WS_SEND:     发送了 WebSocket 请求。
- WS_CLOSE:    关闭 WebSocket 请求。
- DWN_CREATE:  新建下载。
- DWN_PART:    部分下载。
- DWN_CLOSE:   结束下载。
- (Api)
- API_REQUEST: Api 请求。
- API_RESPONSE: Api 响应。
- (反爬虫)
- ANTI_SPIDER: 反爬虫相关信息。

CallbackData: 描述 (str) 数据 (dict)

示例：

``` python
@request_log.on("REQUEST")
async def handle(desc: str, data: dict) -> None:
    print(desc, data)
```

默认启用 Api 和 Anti-Spider 相关信息。
"""
request_log.__doc__ = """
请求日志支持，默认支持输出到指定 I/O 对象。

可以添加更多监听器达到更多效果。

Logger: request_log.logger

Extends: AsyncEvent

Events:

- (模块自带 BiliAPIClient)
- REQUEST:     HTTP 请求。
- RESPONSE:    HTTP 响应。
- WS_CREATE:   新建的 Websocket 请求。
- WS_RECV:     获得到 WebSocket 请求。
- WS_SEND:     发送了 WebSocket 请求。
- WS_CLOSE:    关闭 WebSocket 请求。
- DWN_CREATE:  新建下载。
- DWN_PART:    部分下载。
- DWN_CLOSE:   结束下载。
- (Api)
- API_REQUEST: Api 请求。
- API_RESPONSE: Api 响应。
- (反爬虫)
- ANTI_SPIDER: 反爬虫相关信息。

CallbackData: 描述 (str) 数据 (dict)

示例：

``` python
@request_log.on("REQUEST")
async def handle(desc: str, data: dict) -> None:
    print(desc, data)
```

默认启用 Api 和 Anti-Spider 相关信息。
"""


################################################## END Logger ##################################################
