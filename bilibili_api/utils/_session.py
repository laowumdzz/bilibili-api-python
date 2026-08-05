"""
bilibili_api.utils._session — 会话管理和客户端注册。
"""

from abc import ABC, abstractmethod
import asyncio
import atexit
from typing import Any

from ..exceptions import ArgsException
from ._types import (
    DEFAULT_SETTINGS,
    BiliAPIFile,
    BiliAPIResponse,
    BiliWsMsgType,
    request_settings,
)
from .utils import raise_for_statement

sessions: dict[str, type["BiliAPIClient"]] = {}
session_pool: dict[str, dict[asyncio.AbstractEventLoop, "BiliAPIClient"]] = {}
lazy_settings: dict[str, dict[asyncio.AbstractEventLoop, dict[str, Any]]] = {}
client_settings: dict[str, list] = {}
selected_client: str = ""


def _get_current_loop() -> asyncio.AbstractEventLoop:
    """
    获取当前事件循环。

    优先使用运行中的事件循环，非异步上下文调用时回退到 get_event_loop。

    Returns:
        asyncio.AbstractEventLoop: 当前事件循环
    """
    try:
        return asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.get_event_loop()


class BiliAPIClient(ABC):
    """
    请求客户端抽象类。通过对第三方模块请求客户端的封装令模块可对其进行调用。
    """

    @abstractmethod
    def __init__(
        self,
        proxy: str = "",
        timeout: float = 0.0,
        verify_ssl: bool = True,
        trust_env: bool = True,
        session: object | None = None,
    ) -> None:
        """
        Args:
            proxy (str, optional): 代理地址. Defaults to "".
            timeout (float, optional): 请求超时时间. Defaults to 0.0.
            verify_ssl (bool, optional): 是否验证 SSL. Defaults to True.
            trust_env (bool, optional): `trust_env`. Defaults to True.
            session (object, optional): 会话对象. Defaults to None.

        Note: 仅当用户只提供 `session` 参数且用户中途未调用 `set_xxx` 函数才使用用户提供的 `session`。
        """
        raise NotImplementedError

    @abstractmethod
    def get_wrapped_session(self) -> object:
        """
        获取封装的第三方会话对象

        Returns:
            object: 第三方会话对象
        """
        raise NotImplementedError

    @abstractmethod
    def set_timeout(self, timeout: float = 0.0) -> None:
        """
        设置请求超时时间

        Args:
            timeout (float, optional): 请求超时时间. Defaults to 0.0.
        """
        raise NotImplementedError

    @abstractmethod
    def set_proxy(self, proxy: str = "") -> None:
        """
        设置代理地址

        Args:
            proxy (str, optional): 代理地址. Defaults to "".
        """
        raise NotImplementedError

    @abstractmethod
    def set_verify_ssl(self, verify_ssl: bool = True) -> None:
        """
        设置是否验证 SSL

        Args:
            verify_ssl (bool, optional): 是否验证 SSL. Defaults to True.
        """
        raise NotImplementedError

    @abstractmethod
    def set_trust_env(self, trust_env: bool = True) -> None:
        """
        设置 `trust_env`

        Args:
            trust_env (bool, optional): `trust_env`. Defaults to True.
        """
        raise NotImplementedError

    @abstractmethod
    async def request(
        self,
        method: str = "",
        url: str = "",
        params: dict = {},
        data: dict | str | bytes = {},
        files: dict[str, BiliAPIFile] = {},
        headers: dict = {},
        cookies: dict = {},
        allow_redirects: bool = True,
    ) -> BiliAPIResponse:
        """
        进行 HTTP 请求

        Args:
            method (str, optional): 请求方法. Defaults to "".
            url (str, optional): 请求地址. Defaults to "".
            params (dict, optional): 请求参数. Defaults to {}.
            data (Union[dict, str, bytes], optional): 请求数据. Defaults to {}.
            files (Dict[str, BiliAPIFile], optional): 请求文件. Defaults to {}.
            headers (dict, optional): 请求头. Defaults to {}.
            cookies (dict, optional): 请求 Cookies. Defaults to {}.
            allow_redirects (bool, optional): 是否允许重定向. Defaults to True.

        Returns:
            BiliAPIResponse: 响应对象

        Note: 无需实现 data 为 str 且 files 不为空的情况。
        """
        raise NotImplementedError

    @abstractmethod
    async def download_create(
        self,
        url: str = "",
        headers: dict = {},
    ) -> int:
        """
        开始下载文件

        Args:
            url     (str, optional) : 请求地址. Defaults to "".
            headers (dict, optional): 请求头. Defaults to {}.

        Returns:
            int: 下载编号，用于后续操作。
        """
        raise NotImplementedError

    @abstractmethod
    async def download_chunk(self, cnt: int) -> bytes:
        """
        下载部分文件

        Args:
            cnt    (int): 下载编号

        Returns:
            bytes: 字节
        """
        raise NotImplementedError

    @abstractmethod
    def download_content_length(self, cnt: int) -> int:
        """
        获取下载总字节数

        Args:
            cnt    (int): 下载编号

        Returns:
            int: 下载总字节数
        """
        raise NotImplementedError

    @abstractmethod
    async def download_close(self, cnt: int) -> None:
        """
        结束下载

        Args:
            cnt    (int): 下载编号
        """
        raise NotImplementedError

    @abstractmethod
    async def ws_create(self, url: str = "", params: dict = {}, headers: dict = {}) -> int:
        """
        创建 WebSocket 连接

        Args:
            url (str, optional): WebSocket 地址. Defaults to "".
            params (dict, optional): WebSocket 参数. Defaults to {}.
            headers (dict, optional): WebSocket 头. Defaults to {}.

        Returns:
            int: WebSocket 连接编号，用于后续操作。
        """
        raise NotImplementedError

    @abstractmethod
    async def ws_send(self, cnt: int, data: bytes) -> None:
        """
        发送 WebSocket 数据

        Args:
            cnt (int): WebSocket 连接编号
            data (bytes): WebSocket 数据
        """
        raise NotImplementedError

    @abstractmethod
    async def ws_recv(self, cnt: int) -> tuple[bytes, BiliWsMsgType]:
        """
        接受 WebSocket 数据

        Args:
            cnt (int): WebSocket 连接编号

        Returns:
            Tuple[bytes, BiliWsMsgType]: WebSocket 数据和状态

        Note: 建议实现此函数时支持其他线程关闭不阻塞，除基础状态同时实现 CLOSING, CLOSED。
        """
        raise NotImplementedError

    @abstractmethod
    async def ws_close(self, cnt: int) -> None:
        """
        关闭 WebSocket 连接

        Args:
            cnt (int): WebSocket 连接编号
        """
        raise NotImplementedError

    @abstractmethod
    async def close(self):
        """
        关闭请求客户端，即关闭封装的第三方会话对象
        """
        raise NotImplementedError


def register_client(name: str, cls: type, settings: dict = {}) -> None:
    """
    注册请求客户端并切换，可用于用户自定义请求客户端。

    Args:
        name     (str): 请求客户端类型名称，用户自定义命名。
        cls      (type): 基于 BiliAPIClient 重写后的请求客户端类。
        settings (dict): 请求客户端在基础设置外的其他设置，键为设置名称，值为设置默认值。Defaults to {}.
    """
    global sessions, session_pool, lazy_settings
    raise_for_statement(issubclass(cls, BiliAPIClient), "传入的类型需要继承 BiliAPIClient")
    sessions[name] = cls
    session_pool[name] = {}
    select_client(name)
    for key, value in settings.items():
        request_settings.set(key, value)
    client_settings[name] = DEFAULT_SETTINGS.copy()
    client_settings[name] += list(settings.keys())
    lazy_settings[name] = {}


def unregister_client(name: str) -> None:
    """
    取消注册请求客户端，可用于用户自定义请求客户端。

    Args:
        name (str): 请求客户端类型名称，用户自定义命名。
    """
    global sessions, session_pool
    try:
        sessions.pop(name)
        session_pool.pop(name)
    except KeyError:
        raise ArgsException("未找到指定请求客户端。")


def select_client(name: str) -> None:
    """
    选择模块使用的注册过的请求客户端，可用于用户自定义请求客户端。

    Args:
        name (str): 请求客户端类型名称，用户自定义命名。
    """
    if not sessions.get(name):
        raise ArgsException(f"未注册过 {name}。")
    global selected_client
    selected_client = name


def get_selected_client() -> tuple[str, type[BiliAPIClient]]:
    """
    获取用户选择的请求客户端名称和对应的类

    Returns:
        Tuple[str, Type[BiliAPIClient]]: 第 0 项为客户端名称，第 1 项为对应的类
    """
    if selected_client == "":
        raise ArgsException(
            "尚未安装第三方请求库或未注册自定义第三方请求库。\n$ pip3 install (curl_cffi|httpx|aiohttp)"
        )
    return selected_client, sessions[selected_client]


def get_available_settings() -> list[str]:
    """
    获取当前支持的设置项

    Returns:
        List[str]: 支持的设置项名称
    """
    if selected_client == "":
        raise ArgsException(
            "尚未安装第三方请求库或未注册自定义第三方请求库。\n$ pip3 install (curl_cffi|httpx|aiohttp)"
        )
    return client_settings[selected_client]


def get_registered_clients() -> dict[str, type[BiliAPIClient]]:
    """
    获取所有注册过的 BiliAPIClient

    Returns:
        Dict[str, Type[BiliAPIClient]]: 注册过的 BiliAPIClient
    """
    return sessions


def get_registered_available_settings() -> dict[str, list[str]]:
    """
    获取所有注册过的 BiliAPIClient 所支持的设置项

    Returns:
        Dict[str, List[str]]: 所有注册过的 BiliAPIClient 所支持的设置项
    """
    return client_settings


def get_client() -> BiliAPIClient:
    """
    在当前事件循环下获取模块正在使用的请求客户端

    Returns:
        BiliAPIClient: 请求客户端
    """
    if selected_client == "":
        raise ArgsException(
            "尚未安装第三方请求库或未注册自定义第三方请求库。\n$ pip3 install (curl_cffi|httpx|aiohttp)"
        )
    global session_pool
    pool = session_pool.get(selected_client)
    if pool is None:
        raise ArgsException("未找到用户指定的请求客户端。")
    loop = _get_current_loop()
    session = pool.get(loop)
    if session is None:
        kwargs = {}
        for piece in client_settings[selected_client]:
            kwargs[piece] = request_settings.get(piece)
        session = sessions[selected_client](**kwargs)
        session_pool[selected_client][loop] = session
        lazy_settings[selected_client][loop] = {}
    else:
        for name, value in lazy_settings[selected_client][loop].items():
            try:
                session.__getattribute__(f"set_{name}")(value)
            except AttributeError:
                pass
            except Exception as e:
                raise e
        lazy_settings[selected_client][loop] = {}
    return session


def get_session() -> object:
    """
    在当前事件循环下获取请求客户端的会话对象。

    Returns:
        object: 会话对象
    """
    return get_client().get_wrapped_session()


def set_session(session: object) -> None:
    """
    在当前事件循环下设置请求客户端的会话对象。

    Args:
        session (object): 会话对象
    """
    global session_pool
    pool = session_pool.get(selected_client)
    if not pool:
        raise ArgsException("未找到用户指定的请求客户端。")
    loop = _get_current_loop()
    session_pool[selected_client][loop] = sessions[selected_client](session=session)


@atexit.register
def __clean() -> None:
    """
    程序退出清理操作。
    """
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        return

    async def __clean_task():
        for _, pool in session_pool.items():
            for _, client in pool.items():
                await client.close()

    if loop.is_closed():
        loop.run_until_complete(__clean_task())
    else:
        loop.create_task(__clean_task())  # noqa: RUF006  TODO: __clean 整体逻辑待重构


################################################## END Session Management ##################################################
