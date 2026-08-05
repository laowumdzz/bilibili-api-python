"""
bilibili_api.clients.curl_cffi

CurlCFFIClient 实现
"""

import asyncio
from select import select

import curl_cffi  # pylint: disable=E0401
from curl_cffi import requests  # pylint: disable=E0401

from ..utils.network import (
    BiliAPIClient,
    BiliAPIFile,
    BiliAPIResponse,
    BiliWsMsgType,
    request_log,
)


class CurlCFFIClient(BiliAPIClient):
    """
    curl_cffi 模块请求客户端
    """

    def __init__(
        self,
        proxy: str = "",
        timeout: float = 0.0,
        verify_ssl: bool = True,
        trust_env: bool = True,
        impersonate: str = "",
        http2: bool = False,
        chunk_size: int = 262144,
        session: requests.AsyncSession | None = None,
    ) -> None:
        """
        Args:
            proxy (str, optional): 代理地址. Defaults to "".
            timeout (float, optional): 请求超时时间. Defaults to 0.0.
            verify_ssl (bool, optional): 是否验证 SSL. Defaults to True.
            trust_env (bool, optional): `trust_env`. Defaults to True.
            impersonate (str, optional): 伪装的浏览器，可参考 curl_cffi 文档. Defaults to "".
            http2 (bool, optional): 是否使用 HTTP2. Defaults to False.
            chunk_size (int, optional): 下载分块大小（字节）. Defaults to 262144.
            session (object, optional): 会话对象. Defaults to None.

        Note: 仅当用户只提供 `session` 参数且用户中途未调用 `set_xxx` 函数才使用用户提供的 `session`。
        """
        self.__chunk_size: int = chunk_size
        if session:
            self.__session = session
        else:
            loop = asyncio.get_running_loop()
            self.__session = requests.AsyncSession(
                loop=loop,
                timeout=timeout,
                proxies={"all": proxy},
                verify=verify_ssl,
                trust_env=trust_env,
                impersonate=impersonate,
                http_version=(curl_cffi.CurlHttpVersion.V2_0 if http2 else None),
            )
        self.__ws: dict[int, requests.AsyncWebSocket] = {}
        self.__ws_cnt: int = 0
        self.__ws_need_close: dict[int, bool] = {}
        self.__ws_is_closed: dict[int, bool] = {}
        self.__downloads: dict[int, requests.Response] = {}
        self.__download_cnt: int = 0

    def get_wrapped_session(self) -> requests.AsyncSession:
        """
        获取封装的第三方会话对象

        Returns:
            requests.AsyncSession: 第三方会话对象
        """
        return self.__session

    def set_proxy(self, proxy: str = "") -> None:
        """
        设置代理地址

        Args:
            proxy (str, optional): 代理地址. Defaults to "".
        """
        self.__session.proxies = {"all": proxy}

    def set_timeout(self, timeout: float = 0.0) -> None:
        """
        设置请求超时时间

        Args:
            timeout (float, optional): 请求超时时间. Defaults to 0.0.
        """
        self.__session.timeout = timeout

    def set_verify_ssl(self, verify_ssl: bool = True) -> None:
        """
        设置是否验证 SSL

        Args:
            verify_ssl (bool, optional): 是否验证 SSL. Defaults to True.
        """
        self.__session.verify = verify_ssl

    def set_trust_env(self, trust_env: bool = True) -> None:
        """
        设置 `trust_env`

        Args:
            trust_env (bool, optional): `trust_env`. Defaults to True.
        """
        self.__session.trust_env = trust_env

    def set_impersonate(self, impersonate: str = "") -> None:
        """
        设置 curl_cffi 伪装的浏览器，可参考 curl_cffi 文档。

        Args:
            impersonate (str, optional): 伪装的浏览器. Defaults to "".
        """
        self.__session.impersonate = impersonate

    def set_http2(self, http2: bool = False) -> None:
        """
        设置是否使用 http2.

        Args:
            http2 (bool, optional): 是否使用 http2. Defaults to False.
        """
        self.__session.http_version = curl_cffi.CurlHttpVersion.V2_0 if http2 else None

    def set_chunk_size(self, chunk_size: int = 262144) -> None:
        """
        设置下载分块大小

        Args:
            chunk_size (int, optional): 下载分块大小（字节）. Defaults to 262144.
        """
        self.__chunk_size = chunk_size

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

        Note: 无需实现 data 为 str 且 files 不为空的情况。启用 impersonate 时会移除自定义 User-Agent。
        """
        if headers.get("User-Agent") and self.__session.impersonate != "":
            headers.pop("User-Agent")
        if headers.get("user-agent") and self.__session.impersonate != "":
            headers.pop("user-agent")
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
        if files != {}:
            cnt = 1
            multipart = curl_cffi.CurlMime()
            for key, item in files.items():
                multipart.addpart(
                    name=key,
                    content_type=item.mime_type,
                    filename=f"{cnt}.{item.path.split('.')[1]}",
                    local_path=item.path,
                )
                cnt += 1
        else:
            multipart = None
        resp = await self.__session.request(
            method=method,
            url=url,
            params=params,
            data=data,
            headers=headers,
            cookies=cookies,
            allow_redirects=allow_redirects,
            multipart=multipart,
        )
        if multipart:
            multipart.close()
        resp_header_items = resp.headers.multi_items()
        resp_headers = {}
        for item in resp_header_items:
            resp_headers[item[0]] = item[1]
        resp_cookies = {}
        for cookie in resp.cookies.jar:
            resp_cookies[cookie.name] = cookie.value
        bili_api_resp = BiliAPIResponse(
            code=resp.status_code,
            headers=resp_headers,
            cookies=resp_cookies,
            raw=resp.content,
            url=resp.url,
        )

        request_log.dispatch(
            "RESPONSE",
            "获得响应",
            {
                "code": bili_api_resp.code,
                "headers": bili_api_resp.headers,
                "cookies": bili_api_resp.cookies,
                "data": bili_api_resp.raw,
                "url": bili_api_resp.url,
            },
        )
        return bili_api_resp

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
        if headers.get("User-Agent") and self.__session.impersonate != "":
            headers.pop("User-Agent")
        if headers.get("user-agent") and self.__session.impersonate != "":
            headers.pop("user-agent")
        self.__download_cnt += 1
        request_log.dispatch(
            "DWN_CREATE",
            "开始下载",
            {
                "id": self.__download_cnt,
                "url": url,
                "headers": headers,
            },
        )
        self.__downloads[self.__download_cnt] = await self.__session.get(url=url, headers=headers, stream=True)
        return self.__download_cnt

    async def download_chunk(self, cnt: int) -> bytes:
        """
        下载部分文件

        Args:
            cnt    (int): 下载编号

        Returns:
            bytes: 字节
        """
        resp = self.__downloads[cnt]
        data = await anext(resp.aiter_content(self.__chunk_size))
        request_log.dispatch(
            "DWN_PART",
            "收到部分下载数据",
            {"id": cnt, "length": len(data)},
        )
        return data

    def download_content_length(self, cnt: int) -> int:
        """
        获取下载总字节数

        Args:
            cnt    (int): 下载编号

        Returns:
            int: 下载总字节数
        """
        resp = self.__downloads[cnt]
        return int(resp.headers.get("content-length", "0"))

    async def download_close(self, cnt: int) -> None:
        """
        结束下载

        Args:
            cnt    (int): 下载编号
        """
        resp = self.__downloads[cnt]
        await resp.aclose()
        del self.__downloads[cnt]
        request_log.dispatch(
            "DWN_CLOSE",
            "结束下载",
            {"id": cnt},
        )

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
        if headers.get("User-Agent") and self.__session.impersonate != "":
            headers.pop("User-Agent")
        if headers.get("user-agent") and self.__session.impersonate != "":
            headers.pop("user-agent")
        self.__ws_cnt += 1
        request_log.dispatch(
            "WS_CREATE",
            "开始 WebSocket 连接",
            {
                "id": self.__ws_cnt,
                "url": url,
                "params": params,
                "headers": headers,
            },
        )
        ws = await self.__session.ws_connect(url, params=params, headers=headers)
        self.__ws[self.__ws_cnt] = ws
        self.__ws_is_closed[self.__ws_cnt] = False
        self.__ws_need_close[self.__ws_cnt] = False
        return self.__ws_cnt

    async def ws_send(self, cnt: int, data: bytes) -> None:
        """
        发送 WebSocket 数据，连接处于关闭/待关闭状态时静默跳过

        Args:
            cnt (int): WebSocket 连接编号
            data (bytes): WebSocket 数据
        """
        if self.__ws_need_close[cnt] or self.__ws_is_closed[cnt]:
            return
        request_log.dispatch(
            "WS_SEND",
            "发送 WebSocket 数据",
            {"id": cnt, "data": data},
        )
        ws = self.__ws[cnt]
        await ws.send_binary(data)

    async def ws_recv(self, cnt: int) -> tuple[bytes, BiliWsMsgType]:
        """
        接受 WebSocket 数据，阻塞式读取直到收到完整帧

        Args:
            cnt (int): WebSocket 连接编号

        Returns:
            Tuple[bytes, BiliWsMsgType]: WebSocket 数据和状态

        Note: 支持其他线程关闭不阻塞，除基础状态同时实现 CLOSING, CLOSED。
        """
        ws = self.__ws[cnt]
        chunks = []
        flags = 0
        sock_fd = ws.curl.getinfo(curl_cffi.CurlInfo.ACTIVESOCKET)
        if sock_fd == curl_cffi.aio.CURL_SOCKET_BAD:
            raise curl_cffi.WebSocketError("Invalid active socket", curl_cffi.CurlECode.NO_CONNECTION_AVAILABLE)
        while True:
            if self.__ws_is_closed[cnt]:
                return (b"", BiliWsMsgType.CLOSED)
            if self.__ws_need_close[cnt]:
                return (b"", BiliWsMsgType.CLOSING)
            try:
                loop = self.__session.loop
                chunk, frame = await loop.run_in_executor(None, ws.curl.ws_recv)
                flags = frame.flags
                request_log.dispatch(
                    "WS_RECV",
                    "收到 WebSocket 数据",
                    {"id": cnt, "data": chunk, "flags": flags},
                )
                chunks.append(chunk)
                if frame.bytesleft == 0 and flags & curl_cffi.CurlWsFlag.CONT == 0:
                    break
            except curl_cffi.CurlError as e:
                if e.code == curl_cffi.CurlECode.AGAIN:
                    _, _, _ = select([sock_fd], [], [], 0.5)
                elif e.code == curl_cffi.CurlECode.GOT_NOTHING:
                    return (b"", BiliWsMsgType.CLOSED)
                else:
                    raise e
        if flags & curl_cffi.CurlWsFlag.CLOSE:
            return (b"", BiliWsMsgType.CLOSE)
        by = b"".join(chunks)
        if flags & curl_cffi.CurlWsFlag.TEXT:
            return (by, BiliWsMsgType.TEXT)
        if flags & curl_cffi.CurlWsFlag.PING:
            return (by, BiliWsMsgType.PING)
        return (by, BiliWsMsgType.BINARY)

    async def ws_close(self, cnt: int) -> None:
        """
        关闭 WebSocket 连接，重复关闭时静默跳过

        Args:
            cnt (int): WebSocket 连接编号
        """
        if self.__ws_need_close[cnt] or self.__ws_is_closed[cnt]:
            return
        ws = self.__ws[cnt]
        self.__ws_need_close[cnt] = True
        request_log.dispatch(
            "WS_CLOSE",
            "关闭 WebSocket 请求",
            {"id": cnt},
        )
        ws.terminate()  # It's better to terminate than close.
        self.__ws_is_closed[cnt] = True

    async def close(self) -> None:
        """
        关闭请求客户端，即关闭封装的第三方会话对象
        """
        await self.__session.close()
