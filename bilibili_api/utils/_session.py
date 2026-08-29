"""
bilibili_api.utils._session — 会话管理和客户端注册。
"""

from abc import ABC, abstractmethod
import asyncio
import atexit
from typing import Any
from weakref import WeakKeyDictionary

from ..exceptions import ArgsException
from ._log import request_log
from ._types import (
    DEFAULT_SETTINGS,
    BiliAPIFile,
    BiliAPIResponse,
    BiliWsMsgType,
    request_settings,
)
from .utils import raise_for_statement

sessions: dict[str, type["BiliAPIClient"]] = {}
# 内层使用弱引用字典：以事件循环对象为键，循环销毁后条目自动移除，
# 避免已销毁循环对应的整套客户端无法 GC；CPython 事件循环对象支持弱引用。
session_pool: dict[str, WeakKeyDictionary[asyncio.AbstractEventLoop, "BiliAPIClient"]] = {}
lazy_settings: dict[str, WeakKeyDictionary[asyncio.AbstractEventLoop, dict[str, Any]]] = {}
client_settings: dict[str, list] = {}
selected_client: str = ""


def _get_current_loop() -> asyncio.AbstractEventLoop:
    """
    获取当前事件循环。

    优先使用运行中的事件循环；非异步上下文调用时复用当前线程已绑定的事件循环，
    无绑定时保持惰性创建策略新建一个并绑定，不引入跨循环对象复用。

    Returns:
        asyncio.AbstractEventLoop: 当前事件循环
    """
    try:
        return asyncio.get_running_loop()
    except RuntimeError:
        pass
    try:
        return asyncio.get_event_loop()
    except Exception:
        # 无可用循环时新建并绑定（等价于弃用的 get_event_loop 的原行为，且无弃用警告）
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop


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

    @staticmethod
    def _log_request(
        method: str,
        url: str,
        params: dict,
        data: dict | str | bytes,
        files: dict[str, BiliAPIFile],
        headers: dict,
        cookies: dict,
        allow_redirects: bool,
    ) -> None:
        """
        分发请求日志事件，供各请求客户端实现复用。

        Args:
            method          (str)                  : 请求方法。
            url             (str)                  : 请求地址。
            params          (dict)                 : 请求参数。
            data            (dict | str | bytes)   : 请求数据。
            files           (dict[str, BiliAPIFile]): 请求文件。
            headers         (dict)                 : 请求头。
            cookies         (dict)                 : 请求 Cookies。
            allow_redirects (bool)                 : 是否允许重定向。
        """
        request_log.dispatch(
            "REQUEST",
            "发起请求",
            {
                "method": method,
                "url": url,
                "params": params,
                "data": data,
                "files": files,
                "headers": headers,
                "cookies": cookies,
                "allow_redirects": allow_redirects,
            },
        )

    @staticmethod
    def _log_response(resp: BiliAPIResponse) -> None:
        """
        分发响应日志事件，供各请求客户端实现复用。

        Args:
            resp (BiliAPIResponse): 统一响应对象。
        """
        request_log.dispatch(
            "RESPONSE",
            "获得响应",
            {
                "code": resp.code,
                "headers": resp.headers,
                "cookies": resp.cookies,
                "data": resp.raw,
                "url": resp.url,
            },
        )

    @staticmethod
    def _open_request_files(files: dict[str, BiliAPIFile]) -> tuple[dict, list]:
        """
        将 BiliAPIFile 字典转换为 requests 风格的文件元组字典。

        传文件句柄而非整体读入内存，请求完成后由调用方统一关闭句柄。

        Args:
            files (dict[str, BiliAPIFile]): 请求文件。

        Returns:
            tuple[dict, list]: (requests 风格文件字典, 已打开的文件句柄列表)。
        """
        opened_files = []
        requests_like_files = {}
        for key, item in files.items():
            f = open(item.path, "rb")
            opened_files.append(f)
            requests_like_files[key] = (
                item.path,
                f,
                item.mime_type,
            )
        return requests_like_files, opened_files

    @staticmethod
    def _close_request_files(opened_files: list) -> None:
        """
        关闭 _open_request_files 打开的全部文件句柄。

        Args:
            opened_files (list): 已打开的文件句柄列表。
        """
        for f in opened_files:
            f.close()

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
        params: dict | None = None,
        data: dict | str | bytes | None = None,
        files: dict[str, BiliAPIFile] | None = None,
        headers: dict | None = None,
        cookies: dict | None = None,
        allow_redirects: bool = True,
        proxy: str | None = None,
    ) -> BiliAPIResponse:
        """
        进行 HTTP 请求

        Args:
            method (str, optional): 请求方法. Defaults to "".
            url (str, optional): 请求地址. Defaults to "".
            params (dict | None, optional): 请求参数. Defaults to None（等价于 {}）.
            data (Union[dict, str, bytes] | None, optional): 请求数据. Defaults to None（等价于 {}）.
            files (Dict[str, BiliAPIFile] | None, optional): 请求文件. Defaults to None（等价于 {}）.
            headers (dict | None, optional): 请求头. Defaults to None（等价于 {}）.
            cookies (dict | None, optional): 请求 Cookies. Defaults to None（等价于 {}）.
            allow_redirects (bool, optional): 是否允许重定向. Defaults to True.
            proxy (str | None, optional): 本次请求使用的代理地址. Defaults to None.

        Returns:
            BiliAPIResponse: 响应对象

        Note: 无需实现 data 为 str 且 files 不为空的情况。
            proxy 为 None 时沿用客户端自身配置（即全局 `request_settings` 的代理），
            非 None 时本次请求单独使用该代理，不得修改任何全局/实例级长期配置。
            第三方自定义客户端可不实现该参数，`Api` 请求前会自动探测并降级。
        """
        raise NotImplementedError

    @abstractmethod
    async def download_create(
        self,
        url: str = "",
        headers: dict | None = None,
    ) -> int:
        """
        开始下载文件

        Args:
            url     (str, optional) : 请求地址. Defaults to "".
            headers (dict | None, optional): 请求头. Defaults to None（等价于 {}）.

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
    async def ws_create(self, url: str = "", params: dict | None = None, headers: dict | None = None) -> int:
        """
        创建 WebSocket 连接

        Args:
            url (str, optional): WebSocket 地址. Defaults to "".
            params (dict | None, optional): WebSocket 参数. Defaults to None（等价于 {}）.
            headers (dict | None, optional): WebSocket 头. Defaults to None（等价于 {}）.

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


def register_client(name: str, cls: type, settings: dict | None = None) -> None:
    """
    注册请求客户端并切换，可用于用户自定义请求客户端。

    Args:
        name     (str): 请求客户端类型名称，用户自定义命名。
        cls      (type): 基于 BiliAPIClient 重写后的请求客户端类。
        settings (dict | None): 请求客户端在基础设置外的其他设置，键为设置名称，值为设置默认值。Defaults to None（等价于 {}）.
    """
    settings = {} if settings is None else settings
    global sessions, session_pool, lazy_settings
    raise_for_statement(issubclass(cls, BiliAPIClient), "传入的类型需要继承 BiliAPIClient")
    sessions[name] = cls
    session_pool[name] = WeakKeyDictionary()
    select_client(name)
    for key, value in settings.items():
        request_settings.set(key, value)
    client_settings[name] = DEFAULT_SETTINGS.copy()
    client_settings[name] += list(settings.keys())
    lazy_settings[name] = WeakKeyDictionary()


def unregister_client(name: str) -> None:
    """
    取消注册请求客户端，可用于用户自定义请求客户端。

    Args:
        name (str): 请求客户端类型名称，用户自定义命名。
    """
    global sessions, session_pool, lazy_settings, client_settings
    try:
        sessions.pop(name)
        session_pool.pop(name)
    except KeyError as e:
        raise ArgsException("未找到指定请求客户端。") from e
    # 同步清理客户端设置与惰性设置条目，避免注销后残留泄漏；
    # 历史版本仅弹出 sessions / session_pool，遗留了这两处条目。
    client_settings.pop(name, None)
    lazy_settings.pop(name, None)


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
        for name, value in lazy_settings[selected_client].get(loop, {}).items():
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
    程序退出清理操作：遍历关闭全部登记过的（客户端名称, 事件循环）条目。

    事件循环键以弱引用持有，已销毁的循环会自动从池中移除，
    因此此处仅需遍历仍存活的循环条目；单个客户端关闭失败不影响其余条目。
    """
    for pool in session_pool.values():
        # 先快照再遍历，避免关闭过程中弱引用回调引起的字典变更干扰迭代。
        for loop, client in list(pool.items()):
            try:
                if loop.is_closed():
                    continue
                loop.run_until_complete(client.close())
            except Exception:
                # 退出阶段循环可能已被销毁/关闭失败，跳过即可。
                continue


################################################## END Session Management ##################################################
