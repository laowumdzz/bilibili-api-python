"""
bilibili_api.clients.NoneBotClient

由 NoneBot 驱动承载的 `BiliAPIClient` 实现（HTTP + WebSocket + 流式下载）。

适配器启动时经 `register_client("nonebot", NoneBotClient, {...})` 注册并选中，
使用户配置的 `DRIVER` 继续生效。本模块 MUST NOT 被 `clients/__init__.py` 或包根
预导入：未安装 nonebot2 时，导入 `bilibili_api` 必须仍然成功。
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator, AsyncIterator, Awaitable, Callable
from contextlib import AsyncExitStack, suppress
from dataclasses import dataclass, field
from http.cookies import SimpleCookie
import os
from typing import IO, Any, cast
import warnings

from multidict import CIMultiDict
from nonebot.drivers import (
    URL,
    Driver,
    HTTPClientMixin,
    Request,
    Response,
    Timeout,
    WebSocket,
    WebSocketClientMixin,
)
from nonebot.exception import WebSocketClosed

import nonebot

from ..exceptions import ArgsException, NetworkException
from ..utils.network import BiliAPIClient, BiliAPIFile, BiliAPIResponse, BiliWsMsgType


def _is_transport_error(error: BaseException) -> bool:
    """
    判断异常是否属于传输层错误。

    内置超时 / 连接类异常按类型判断；aiohttp / httpx 的异常按模块名前缀判断，
    避免为可选依赖引入静态类型依赖，也避免把编程错误误判为网络故障。

    Args:
        error (BaseException): 待判断的异常。

    Returns:
        bool: 是否属于传输层错误。
    """
    if isinstance(error, (asyncio.TimeoutError, TimeoutError, ConnectionError, OSError)):
        return True
    module = type(error).__module__.split(".", 1)[0]
    return module in {"aiohttp", "httpx"}


def driver_name(driver: object) -> str:
    """
    取驱动的可读名称（用于能力缺失的错误文本）。

    Args:
        driver (object): 驱动实例。

    Returns:
        str: `driver.type` 存在且非空时取该值，否则取类名。
    """
    driver_type = getattr(driver, "type", None)
    if isinstance(driver_type, str) and driver_type:
        return driver_type
    return type(driver).__name__


def ensure_websocket_support(driver: object) -> None:
    """
    校验驱动是否具备 WebSocket 能力（V-10 / FR-012）。

    Args:
        driver (object): 驱动实例。

    Raises:
        ArgsException: 驱动未实现 `WebSocketClientMixin`；文本含当前驱动名，
            并说明需要支持 WebSocket 的驱动。
    """
    if not isinstance(driver, WebSocketClientMixin):
        raise ArgsException(
            f"当前驱动 {driver_name(driver)} 不支持 WebSocket，弹幕连接无法建立。"
            "请改用同时实现 HTTP 与 WebSocket 的驱动（如 nonebot2 的 aiohttp 驱动）。"
        )


def _resolve_driver() -> Driver:
    """
    取 NoneBot 全局驱动。

    Returns:
        Driver: 全局驱动实例。

    Raises:
        ArgsException: NoneBot 尚未初始化或驱动不可用。
    """
    try:
        driver = nonebot.get_driver()
    except Exception as e:
        raise ArgsException("无法获取 NoneBot 驱动：请先完成 nonebot.init() 再启动 bilibili_live 适配器。") from e
    if not isinstance(driver, HTTPClientMixin):
        raise ArgsException(f"当前驱动 {driver_name(driver)} 不支持 HTTP，无法承载 bilibili_live 适配器的请求。")
    return driver


def _to_bytes(content: str | bytes | None) -> bytes:
    """
    把驱动响应内容归一为 bytes。

    Args:
        content (str | bytes | None): 驱动返回的内容。

    Returns:
        bytes: UTF-8 编码后的字节串；`None` 视为空。
    """
    if content is None:
        return b""
    if isinstance(content, str):
        return content.encode("utf-8")
    return content


def _lower_headers(headers: CIMultiDict[str]) -> dict[str, str]:
    """
    把驱动响应头转为键全小写的普通字典。

    `bilibili_api` 的响应处理按 `content-length` 等小写键查表，因此必须统一。

    Args:
        headers (CIMultiDict[str]): 驱动响应头。

    Returns:
        dict[str, str]: 键全小写的头字典；同名头后者覆盖前者。
    """
    result: dict[str, str] = {}
    for key, value in headers.items():
        result[str(key).lower()] = str(value)
    return result


def _parse_set_cookies(headers: CIMultiDict[str]) -> dict[str, str]:
    """
    从响应头逐条解析 `Set-Cookie`。

    驱动响应不提供 cookies 属性，只能自行解析；使用 `SimpleCookie` 以正确处理
    `Expires` 中的逗号。

    Args:
        headers (CIMultiDict[str]): 驱动响应头。

    Returns:
        dict[str, str]: cookie 名称到值的映射。
    """
    raw_headers = [str(item) for item in headers.getall("set-cookie", [])]
    cookies: dict[str, str] = {}
    for header in raw_headers:
        jar = SimpleCookie()
        try:
            jar.load(header)
        except Exception:
            continue
        for key, morsel in jar.items():
            cookies[key] = morsel.value
    return cookies


@dataclass
class _DownloadHandle:
    """进行中的流式下载句柄。"""

    chunks: AsyncIterator[bytes]
    closable: Any = None
    content_length: int = 0
    closed: bool = False


@dataclass
class _WsHandle:
    """一条 WebSocket 连接的句柄。"""

    stack: AsyncExitStack
    websocket: WebSocket
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    closed: bool = False


async def _iterate_bytes(raw: bytes, chunk_size: int) -> AsyncIterator[bytes]:
    """
    把整包字节按块切分（`stream_request` 不可用时的降级路径）。

    Args:
        raw (bytes): 完整响应体。
        chunk_size (int): 分块大小。

    Yields:
        bytes: 每块数据。
    """
    for offset in range(0, len(raw), chunk_size):
        yield raw[offset : offset + chunk_size]


class NoneBotClient(BiliAPIClient):
    """
    由 NoneBot 驱动承载的请求客户端。

    驱动层能力限制（驱动强加，非实现缺陷）：最终 URL 不可得、重定向中途 cookie
    丢失、`verify_ssl` / `trust_env` 不可配、无连接池、控制帧不可见。详见
    `specs/012-nonebot-adapter-fusion/contracts/client-bridge.md` §7。
    """

    def __init__(
        self,
        proxy: str = "",
        timeout: float = 0.0,
        verify_ssl: bool = True,
        trust_env: bool = True,
        chunk_size: int = 262144,
        session: object | None = None,
    ) -> None:
        """
        Args:
            proxy (str, optional): 代理地址；空串归一为 `None`（沿用驱动默认）. Defaults to "".
            timeout (float, optional): 请求超时（秒），`<= 0` 表示不限时. Defaults to 0.0.
            verify_ssl (bool, optional): 是否验证 SSL；驱动不支持，仅保存并告警. Defaults to True.
            trust_env (bool, optional): 是否读取环境代理；aiohttp 驱动硬编码 `True`，仅保存并告警. Defaults to True.
            chunk_size (int, optional): 流式下载分块大小（字节）. Defaults to 262144.
            session (object, optional): 仅接受 `nonebot.drivers.Driver` 实例. Defaults to None.

        Raises:
            TypeError: `session` 非 `Driver` 实例。
            ArgsException: 无法解析驱动，或驱动缺少 HTTP 能力。
        """
        if session is not None and not isinstance(session, Driver):
            raise TypeError("session 只接受 nonebot.drivers.Driver 实例（可通过 set_session() 注入）")
        self.__driver: Driver = session if session is not None else _resolve_driver()
        if not isinstance(self.__driver, HTTPClientMixin):
            raise ArgsException(
                f"当前驱动 {driver_name(self.__driver)} 不支持 HTTP，无法承载 bilibili_live 适配器的请求。"
            )
        self.__proxy: str | None = proxy or None
        self.__timeout: float = timeout
        self.__verify_ssl: bool = verify_ssl
        self.__trust_env: bool = trust_env
        self.__chunk_size: int = chunk_size
        self.__downloads: dict[int, _DownloadHandle] = {}
        self.__download_cnt: int = 0
        self.__wss: dict[int, _WsHandle] = {}
        self.__ws_cnt: int = 0
        self.__warned_verify_ssl: bool = False
        self.__warned_trust_env: bool = False
        if not verify_ssl:
            self.__warn_verify_ssl()

    def __warn_verify_ssl(self) -> None:
        """驱动不支持关闭 SSL 校验，首次设置时告警一次。"""
        if self.__warned_verify_ssl:
            return
        self.__warned_verify_ssl = True
        warnings.warn(
            "NoneBot 驱动不支持 verify_ssl 配置，该参数仅被保存而不会生效。",
            UserWarning,
            stacklevel=2,
        )

    def __warn_trust_env(self) -> None:
        """驱动不支持 trust_env 配置，首次设置时告警一次。"""
        if self.__warned_trust_env:
            return
        self.__warned_trust_env = True
        warnings.warn(
            "NoneBot aiohttp 驱动固定 trust_env=True，trust_env 参数仅被保存而不会生效。",
            UserWarning,
            stacklevel=2,
        )

    def get_wrapped_session(self) -> Driver:
        """
        获取封装的会话对象。

        Note: 语义与内置客户端不同——返回驱动对象本身，而非具体 HTTP 会话。

        Returns:
            Driver: NoneBot 驱动实例。
        """
        return self.__driver

    def set_proxy(self, proxy: str = "") -> None:
        """
        设置代理地址。

        Args:
            proxy (str, optional): 代理地址；空串表示不覆盖驱动默认. Defaults to "".
        """
        self.__proxy = proxy or None

    def set_timeout(self, timeout: float = 0.0) -> None:
        """
        设置请求超时。

        Args:
            timeout (float, optional): 超时秒数，`<= 0` 表示不限时. Defaults to 0.0.
        """
        self.__timeout = timeout

    def set_verify_ssl(self, verify_ssl: bool = True) -> None:
        """
        设置是否验证 SSL（驱动不支持，仅保存并在关闭时告警）。

        Args:
            verify_ssl (bool, optional): 是否验证 SSL. Defaults to True.
        """
        self.__verify_ssl = verify_ssl
        if not verify_ssl:
            self.__warn_verify_ssl()

    def set_trust_env(self, trust_env: bool = True) -> None:
        """
        设置 `trust_env`（驱动不支持，仅保存并在关闭时告警）。

        Args:
            trust_env (bool, optional): 是否读取环境代理. Defaults to True.
        """
        self.__trust_env = trust_env
        if not trust_env:
            self.__warn_trust_env()

    def set_chunk_size(self, chunk_size: int = 262144) -> None:
        """
        设置下载分块大小。

        Args:
            chunk_size (int, optional): 分块大小（字节）. Defaults to 262144.
        """
        self.__chunk_size = chunk_size

    def __request_timeout(self) -> Timeout | None:
        """
        构造 HTTP 请求超时（`<= 0` 归一为不限时）。

        Returns:
            Timeout | None: 超时配置，`None` 表示不限时。
        """
        if self.__timeout <= 0:
            return None
        return Timeout(total=self.__timeout, connect=self.__timeout, read=self.__timeout, close=self.__timeout)

    def __ws_timeout(self) -> Timeout | None:
        """
        构造 WebSocket 超时：`read` 必须为 `None`，否则空闲即超时。

        Returns:
            Timeout | None: 超时配置，`None` 表示不限时。
        """
        if self.__timeout <= 0:
            return None
        return Timeout(total=self.__timeout, connect=self.__timeout, read=None, close=self.__timeout)

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
        经 NoneBot 驱动发起 HTTP 请求。

        Args:
            method (str, optional): 请求方法；空串归一为 `GET`. Defaults to "".
            url (str, optional): 请求地址. Defaults to "".
            params (dict | None, optional): 查询参数（由 `Request` 合并进 URL）. Defaults to None.
            data (dict | str | bytes | None, optional): `str` / `bytes` 走 `content`，
                `dict` 走表单 `data`. Defaults to None.
            files (dict[str, BiliAPIFile] | None, optional): 上传文件；句柄在请求结束后关闭. Defaults to None.
            headers (dict | None, optional): 请求头. Defaults to None.
            cookies (dict | None, optional): 请求 cookies；值为 `None` 的键剔除. Defaults to None.
            allow_redirects (bool, optional): 驱动始终跟随重定向，该参数被忽略. Defaults to True.
            proxy (str | None, optional): 本次请求的代理；`None` 沿用客户端配置. Defaults to None.

        Returns:
            BiliAPIResponse: 响应对象（非 2xx 不抛异常；头键统一小写；cookies 由
            `Set-Cookie` 逐条解析；`url` 为请求 URL）。

        Raises:
            NotImplementedError: `data` 为 `str` 且 `files` 非空。
            NetworkException: 传输层异常（超时 / 连接失败 / 第三方客户端异常）。
        """
        method = method or "GET"
        cookies_dict = {str(key): str(value) for key, value in (cookies or {}).items() if value is not None}
        request_files: dict[str, Any] | None = None
        opened_files: list[IO[bytes]] = []
        content: str | bytes | None = None
        form: dict | None = None
        if files:
            if isinstance(data, str):
                raise NotImplementedError("data 为 str 时不支持同时上传 files")
            request_files = {}
            for key, item in files.items():
                handle = open(item.path, "rb")
                opened_files.append(handle)
                request_files[key] = (os.path.basename(item.path), handle, item.mime_type or "application/octet-stream")
            form = dict(data or {})
        elif isinstance(data, str | bytes):
            content = data
        elif isinstance(data, dict):
            form = data or None
        request = Request(
            method=method,
            url=URL(url),
            params=params or None,
            headers=headers or None,
            cookies=cookies_dict or None,
            content=content,
            data=form,
            files=request_files,
            timeout=self.__request_timeout(),
            proxy=proxy if proxy is not None else self.__proxy,
        )
        http = cast(HTTPClientMixin, self.__driver)
        try:
            response: Response = await http.request(request)
        except Exception as e:
            if not _is_transport_error(e):
                raise
            # 只保留异常类型与消息：不含 cookie / 凭据（它们在请求头里，不进入异常文本）
            raise NetworkException(0, f"传输层错误（{type(e).__name__}）：{e}") from e
        finally:
            for handle in opened_files:
                handle.close()
        return BiliAPIResponse(
            code=response.status_code,
            headers=_lower_headers(response.headers),
            cookies=_parse_set_cookies(response.headers),
            raw=_to_bytes(response.content),
            url=str(request.url),
        )

    async def download_create(self, url: str = "", headers: dict | None = None) -> int:
        """
        开始流式下载。

        Args:
            url (str, optional): 下载地址. Defaults to "".
            headers (dict | None, optional): 请求头. Defaults to None.

        Returns:
            int: 下载编号。

        Raises:
            NetworkException: 建立下载请求失败。
        """
        self.__download_cnt += 1
        cnt = self.__download_cnt
        request = Request(
            method="GET",
            url=URL(url),
            headers=headers or None,
            timeout=self.__request_timeout(),
            proxy=self.__proxy,
        )
        http = cast(HTTPClientMixin, self.__driver)
        stream_factory = getattr(http, "stream_request", None)
        if stream_factory is not None:
            generator: AsyncGenerator[Response, None] = cast(Any, stream_factory)(request, chunk_size=self.__chunk_size)
            try:
                first = await anext(generator)
            except Exception as e:
                if not _is_transport_error(e):
                    raise
                raise NetworkException(0, f"传输层错误（{type(e).__name__}）：{e}") from e

            async def chunks() -> AsyncIterator[bytes]:
                yield _to_bytes(first.content)
                async for response in generator:
                    yield _to_bytes(response.content)

            self.__downloads[cnt] = _DownloadHandle(
                chunks=chunks(),
                closable=generator,
                content_length=int(_lower_headers(first.headers).get("content-length", "0") or 0),
            )
        else:  # pragma: no cover - 当前两个驱动都实现了 stream_request
            response = await self.request(url=url, headers=headers)
            self.__downloads[cnt] = _DownloadHandle(
                chunks=_iterate_bytes(response.raw, self.__chunk_size),
                content_length=len(response.raw),
            )
        return cnt

    async def download_chunk(self, cnt: int) -> bytes:
        """
        取下一块下载数据。

        Args:
            cnt (int): 下载编号。

        Returns:
            bytes: 数据块；下载已结束或句柄不存在时为空字节。
        """
        handle = self.__downloads.get(cnt)
        if handle is None or handle.closed:
            return b""
        try:
            return await anext(handle.chunks)
        except StopAsyncIteration:
            return b""

    def download_content_length(self, cnt: int) -> int:
        """
        取下载总字节数。

        Args:
            cnt (int): 下载编号。

        Returns:
            int: 响应头声明的总长度；句柄不存在时为 0。
        """
        handle = self.__downloads.get(cnt)
        return 0 if handle is None else handle.content_length

    async def download_close(self, cnt: int) -> None:
        """
        结束下载（幂等）。

        Args:
            cnt (int): 下载编号。
        """
        handle = self.__downloads.pop(cnt, None)
        if handle is None or handle.closed:
            return
        handle.closed = True
        with suppress(Exception):
            close_chunks = getattr(handle.chunks, "aclose", None)
            if close_chunks is not None:
                await cast(Callable[[], Awaitable[None]], close_chunks)()
        if handle.closable is not None:
            with suppress(Exception):
                await handle.closable.aclose()

    async def ws_create(self, url: str = "", params: dict | None = None, headers: dict | None = None) -> int:
        """
        创建 WebSocket 连接。

        Args:
            url (str, optional): WebSocket 地址. Defaults to "".
            params (dict | None, optional): 查询参数. Defaults to None.
            headers (dict | None, optional): 请求头（cookies 需由调用方以 `Cookie` 头携带）. Defaults to None.

        Returns:
            int: 连接编号。

        Raises:
            ArgsException: 驱动不支持 WebSocket（文本含驱动名）。
        """
        ensure_websocket_support(self.__driver)
        request = Request(
            method="GET",
            url=URL(url),
            params=params or None,
            headers=headers or None,
            timeout=self.__ws_timeout(),
            proxy=self.__proxy,
        )
        self.__ws_cnt += 1
        cnt = self.__ws_cnt
        stack = AsyncExitStack()
        try:
            websocket = await stack.enter_async_context(cast(WebSocketClientMixin, self.__driver).websocket(request))
        except BaseException:
            await stack.aclose()
            raise
        self.__wss[cnt] = _WsHandle(stack=stack, websocket=websocket)
        return cnt

    async def ws_send(self, cnt: int, data: bytes) -> None:
        """
        发送 WebSocket 数据；句柄不存在或已关闭时静默返回。

        Args:
            cnt (int): 连接编号。
            data (bytes): 二进制数据。
        """
        handle = self.__wss.get(cnt)
        if handle is None or handle.closed:
            return
        await handle.websocket.send_bytes(data)

    async def ws_recv(self, cnt: int) -> tuple[bytes, BiliWsMsgType]:
        """
        接收 WebSocket 数据。

        同一句柄的调用用接收锁串行化（aiohttp 对并发 `receive()` 直接 `RuntimeError`）。
        控制帧（PING / PONG）由驱动转为 `TypeError`，此处跳过并继续等待数据帧。

        Args:
            cnt (int): 连接编号。

        Returns:
            tuple[bytes, BiliWsMsgType]: 数据与状态；句柄不存在或已关闭时为
            `(b"", CLOSED)`；关闭码 1000 / 1001 映射为 `CLOSED`。

        Raises:
            WebSocketClosed: 其它关闭码（含 1006），交由上层重连逻辑处理。
        """
        handle = self.__wss.get(cnt)
        if handle is None or handle.closed:
            return b"", BiliWsMsgType.CLOSED
        async with handle.lock:
            current = self.__wss.get(cnt)
            if current is None or current.closed:
                return b"", BiliWsMsgType.CLOSED
            while True:
                try:
                    message = await current.websocket.receive()
                except WebSocketClosed as e:
                    if e.code in (1000, 1001):
                        return b"", BiliWsMsgType.CLOSED
                    raise
                except TypeError:
                    # 驱动对 PING / PONG / 关闭帧抛 TypeError；这些帧对上层不可见，跳过
                    continue
                if isinstance(message, str):
                    return message.encode("utf-8"), BiliWsMsgType.TEXT
                if isinstance(message, bytes):
                    return message, BiliWsMsgType.BINARY
                return b"", BiliWsMsgType.BINARY

    async def ws_close(self, cnt: int) -> None:
        """
        关闭 WebSocket 连接（幂等）。

        关闭顺序固定为「close → 等读锁 → 退上下文」，避免接收方未退出就销毁底层
        会话而被上层判为传输错误。

        Args:
            cnt (int): 连接编号。
        """
        handle = self.__wss.pop(cnt, None)
        if handle is None or handle.closed:
            return
        handle.closed = True
        with suppress(Exception):
            await handle.websocket.close(1000, "")
        with suppress(asyncio.TimeoutError):
            await asyncio.wait_for(handle.lock.acquire(), timeout=5)
            handle.lock.release()
        with suppress(Exception):
            await handle.stack.aclose()

    async def close(self) -> None:
        """
        关闭全部下载与 WebSocket 连接。

        驱动对象不属于本客户端，不会被关闭。
        """
        for cnt in list(self.__downloads):
            await self.download_close(cnt)
        for cnt in list(self.__wss):
            await self.ws_close(cnt)
