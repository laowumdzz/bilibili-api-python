"""
bilibili_api.utils._types — 数据类和请求设置。
"""

from dataclasses import dataclass
from enum import Enum
import json
from typing import Any

from .utils import get_api


class RequestSettings:
    def __init__(self):
        self.__settings: dict = {
            "proxy": "",
            "timeout": 30.0,
            "verify_ssl": True,
            "trust_env": True,
        }
        self.__wbi_retry_times = 3
        self.__enable_auto_buvid = True
        self.__enable_bili_ticket = False

    def get(self, name: str) -> Any:
        """
        获取某项设置

        不可用于 `wbi_retry_times` `enable_auto_buvid` `enable_bili_ticket`

        默认设置名称：`proxy` `timeout` `verify_ssl` `trust_env`

        Args:
            name (str): 设置名称

        Returns:
            Any: 设置的值
        """
        return self.__settings[name]

    def set(self, name: str, value: Any) -> None:
        """
        设置某项设置

        不可用于 `wbi_retry_times` `enable_auto_buvid` `enable_bili_ticket`

        默认设置名称：`proxy` `timeout` `verify_ssl` `trust_env`

        Args:
            name  (str): 设置名称
            value (str): 设置的值
        """
        if value == self.__settings.get(name):
            return
        self.__settings[name] = value
        from ._session import lazy_settings

        for _, pool in lazy_settings.items():
            for _, client in pool.items():
                client[name] = value

    def get_proxy(self) -> str:
        """
        获取设置的代理

        Returns:
            str: 代理地址. Defaults to "".
        """
        return self.get("proxy")

    def set_proxy(self, proxy: str):
        """
        修改设置的代理

        Args:
            proxy (str): 代理地址
        """
        self.set("proxy", proxy)

    def get_timeout(self) -> float:
        """
        获取设置的 web 请求超时时间

        Returns:
            float: 超时时间（秒），`<= 0` 表示不限时. Defaults to 30.0.
        """
        return self.get("timeout")

    def set_timeout(self, timeout: float):
        """
        修改设置的 web 请求超时时间（秒）。
        `timeout <= 0` 表示不限时（三种请求客户端均已归一化为各自底层库的无限时表示）。
        默认值为 30.0。

        Args:
            timeout (float): 超时时间（秒），`<= 0` 表示不限时
        """
        self.set("timeout", timeout)

    def get_verify_ssl(self) -> bool:
        """
        获取设置的是否验证 SSL

        Returns:
            bool: 是否验证 SSL. Defaults to True.
        """
        return self.get("verify_ssl")

    def set_verify_ssl(self, verify_ssl: bool):
        """
        修改设置的是否验证 SSL

        Args:
            verify_ssl (bool): 是否验证 SSL
        """
        self.set("verify_ssl", verify_ssl)

    def get_trust_env(self) -> bool:
        """
        获取设置的 `trust_env`

        Returns:
            bool: `trust_env`. Defaults to True.
        """
        return self.get("trust_env")

    def set_trust_env(self, trust_env: bool):
        """
        修改设置的 `trust_env`

        Args:
            verify_ssl (bool): `trust_env`
        """
        self.set("trust_env", trust_env)

    def get_wbi_retry_times(self) -> int:
        """
        获取设置的 wbi 重试次数

        Returns:
            int: wbi 重试次数. Defaults to 3.
        """
        return self.__wbi_retry_times

    def set_wbi_retry_times(self, wbi_retry_times: int) -> None:
        """
        修改设置的 wbi 重试次数

        Args:
            wbi_retry_times (int): wbi 重试次数.
        """
        self.__wbi_retry_times = wbi_retry_times

    def get_enable_auto_buvid(self) -> bool:
        """
        获取设置的是否自动生成 buvid

        Returns:
            bool: 是否自动生成 buvid. Defaults to True.
        """
        return self.__enable_auto_buvid

    def set_enable_auto_buvid(self, enable_auto_buvid: bool) -> None:
        """
        设置是否自动生成 buvid

        Args:
            enable_auto_buvid (bool): 是否自动生成 buvid.
        """
        self.__enable_auto_buvid = enable_auto_buvid

    def get_enable_bili_ticket(self) -> bool:
        """
        获取设置的是否使用 bili_ticket

        Returns:
            bool: 是否使用 bili_ticket. Defaults to True.
        """
        return self.__enable_bili_ticket

    def set_enable_bili_ticket(self, enable_bili_ticket: bool) -> None:
        """
        设置是否使用 bili_ticket

        Args:
            enable_bili_ticket (bool): 是否使用 bili_ticket.
        """
        self.__enable_bili_ticket = enable_bili_ticket

    def get_all(self) -> dict:
        """
        获取目前所有的设置项

        不可用于 `wbi_retry_times` `enable_auto_buvid` `enable_bili_ticket`

        Returns:
            dict: 所有的设置项
        """
        return self.__settings


request_settings = RequestSettings()
"请求参数设置"
request_settings.__doc__ = "请求参数设置"

DEFAULT_SETTINGS = ["proxy", "timeout", "verify_ssl", "trust_env"]

APPKEY = "***"
APPSEC = "59b43e04ad6965f34319062b478f83dd"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0",
    "Referer": "https://www.bilibili.com",
}
API = get_api("credential")


@dataclass
class BiliAPIResponse:
    """
    响应对象类。

    Attributes:
        code    (int)  : 响应码
        headers (dict) : 响应头
        cookies (dict) : 当前状态的 cookies
        raw     (bytes): 响应数据
        url     (str)  : 当前 url
    """

    code: int
    headers: dict
    cookies: dict
    raw: bytes
    url: str

    def utf8_text(self) -> str:
        """
        转为 utf8 文字

        Returns:
            str: utf8 文字
        """
        return self.raw.decode("utf-8")

    def json(self) -> object:
        """
        解析 json

        Returns:
            object: 解析后的 json
        """
        return json.loads(self.utf8_text())


class BiliWsMsgType(Enum):
    """
    WebSocket 状态枚举

    - CONTINUATION: 延续
    - TEXT: 文字
    - BINARY: 字节
    - PING: ping
    - PONG: pong
    - CLOSE: 关闭

    - CLOSING: 正在关闭
    - CLOSED: 已关闭
    """

    CONTINUATION = 0x0
    TEXT = 0x1
    BINARY = 0x2
    PING = 0x9
    PONG = 0xA
    CLOSE = 0x8
    CLOSING = 0x100
    CLOSED = 0x101


@dataclass
class BiliAPIFile:
    """
    上传文件类。

    Attributes:
        path      (str): 文件地址
        mime_type (str): 文件类型
    """

    def __init__(self, path: str = "", mime_type: str | None = None):
        """
        Args:
            path      (str): 文件地址. Defaults to "".
            mime_type (str, optional): 文件类型. Defaults to None.
        """
        self.path = path
        self.mime_type = mime_type
