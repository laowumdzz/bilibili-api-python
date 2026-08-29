"""
bilibili_api.clients.aiohttp

AioHTTPClient 实现
"""

import os

import aiohttp  # pylint: disable=E0401

from ..utils.network import (
    BiliAPIClient,
    BiliAPIFile,
    BiliAPIResponse,
    BiliWsMsgType,
    request_log,
)


class AioHTTPClient(BiliAPIClient):
    """
    aiohttp 模块请求客户端
    """

    def __init__(
        self,
        proxy="",
        timeout=0,
        verify_ssl=True,
        trust_env=True,
        chunk_size: int = 262144,
        session: aiohttp.ClientSession | None = None,
    ):
        """
        Args:
            proxy (str, optional): 代理地址. Defaults to "".
            timeout (float, optional): 请求超时时间. Defaults to 0.
            verify_ssl (bool, optional): 是否验证 SSL. Defaults to True.
            trust_env (bool, optional): `trust_env`. Defaults to True.
            chunk_size (int, optional): 下载分块大小（字节）. Defaults to 262144.
            session (aiohttp.ClientSession, optional): 会话对象. Defaults to None.

        Note: 仅当用户只提供 `session` 参数且用户中途未调用 `set_xxx` 函数才使用用户提供的 `session`。
        """
        self.__args: dict = {
            "proxy": proxy,
            "timeout": timeout,
            "verify_ssl": verify_ssl,
            "trust_env": trust_env,
        }
        self.__use_args: bool = True
        self.__need_update_session: bool = False
        self.__chunk_size: int = chunk_size
        # session 惰性创建，确保绑定首次使用时的事件循环
        self.__session: aiohttp.ClientSession | None = session
        if session:
            self.__use_args = False
        self.__wss: dict[int, aiohttp.ClientWebSocketResponse] = {}
        self.__ws_cnt: int = 0
        self.__downloads: dict[int, aiohttp.ClientResponse] = {}
        self.__download_cnt: int = 0

    async def __ensure_session(self) -> aiohttp.ClientSession:
        """
        获取当前可用的 ClientSession，必要时惰性创建/重建。

        Returns:
            aiohttp.ClientSession: 当前会话
        """
        if self.__need_update_session:
            if self.__session is not None:
                await self.__session.close()
            self.__session = None
            self.__need_update_session = False
        if self.__session is None:
            self.__session = aiohttp.ClientSession(
                trust_env=self.__args["trust_env"],
                connector=aiohttp.TCPConnector(
                    verify_ssl=self.__args["verify_ssl"],
                    # 连接池参数：总连接数上限 100，单主机不设上限（爬虫场景多为同一域名高并发），DNS 缓存 300 秒
                    limit=100,
                    limit_per_host=0,
                    ttl_dns_cache=300,
                ),
            )
        return self.__session

    def get_wrapped_session(self) -> aiohttp.ClientSession | None:
        """
        获取封装的第三方会话对象

        Returns:
            aiohttp.ClientSession | None: 第三方会话对象，未创建时为 None
        """
        return self.__session

    def set_proxy(self, proxy: str = "") -> None:
        """
        设置代理地址

        Args:
            proxy (str, optional): 代理地址. Defaults to "".
        """
        self.__use_args = True
        self.__args["proxy"] = proxy

    def set_timeout(self, timeout: float = 0) -> None:
        """
        设置请求超时时间

        Args:
            timeout (float, optional): 请求超时时间. Defaults to 0.
        """
        self.__use_args = True
        self.__args["timeout"] = timeout

    def set_verify_ssl(self, verify_ssl: bool = True) -> None:
        """
        设置是否验证 SSL

        Args:
            verify_ssl (bool, optional): 是否验证 SSL. Defaults to True.
        """
        self.__use_args = True
        self.__args["verify_ssl"] = verify_ssl
        self.__need_update_session = True

    def set_trust_env(self, trust_env: bool = True) -> None:
        """
        设置 `trust_env`

        Args:
            trust_env (bool, optional): `trust_env`. Defaults to True.
        """
        self.__use_args = True
        self.__args["trust_env"] = trust_env
        self.__need_update_session = True

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
        proxy: str | None = None,
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
            proxy (str | None, optional): 本次请求使用的代理地址. Defaults to None.

        Returns:
            BiliAPIResponse: 响应对象

        Note: 无需实现 data 为 str 且 files 不为空的情况。
            proxy 为 None 时沿用客户端配置的代理，非 None 时仅本次请求生效（aiohttp 原生支持）。
        """
        self._log_request(method, url, params, data, files, headers, cookies, allow_redirects)
        if self.__need_update_session or self.__session is None:
            session = await self.__ensure_session()
        else:
            session = self.__session
        if files:
            form = aiohttp.FormData()
            if isinstance(data, str):
                raise NotImplementedError
            for key, value in data.items():
                form.add_field(name=key, value=value)
            for key, value in files.items():
                # 传文件句柄而非整体读入内存，由 aiohttp 流式发送并在完成后关闭
                form.add_field(
                    name=key,
                    value=open(value.path, "rb"),
                    content_type=value.mime_type,
                    filename=os.path.basename(value.path),
                )
            data = form
        if self.__use_args:
            resp = await session.request(
                method=method,
                url=url,
                params=params,
                data=data,
                headers=headers,
                cookies=cookies,
                allow_redirects=allow_redirects,
                # 本次请求显式指定的代理优先，否则沿用客户端配置的代理（现有行为不变）
                proxy=proxy if proxy is not None else self.__args["proxy"],
                timeout=aiohttp.ClientTimeout(self.__args["timeout"]),
            )
        else:
            # 用户提供会话时不干预其默认配置，仅在显式传入代理时附加（proxy=None 与不传等价）
            resp = await session.request(
                method=method,
                url=url,
                params=params,
                data=data,
                headers=headers,
                cookies=cookies,
                allow_redirects=allow_redirects,
                proxy=proxy,
            )
        resp_code = resp.status
        resp_headers = {}
        for key, item in resp.headers.items():
            resp_headers[key] = item
        resp_cookies = {}
        for key, item in resp.cookies.items():
            resp_cookies[key] = item.value
        bili_api_resp = BiliAPIResponse(
            code=resp_code,
            headers=resp_headers,
            cookies=resp_cookies,
            raw=await resp.read(),
            url=str(resp.url),
        )
        self._log_response(bili_api_resp)
        resp.release()
        await resp.wait_for_close()
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
        session = await self.__ensure_session()
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
        self.__downloads[self.__download_cnt] = await session.get(url=url, headers=headers)
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
        data = await anext(resp.content.iter_chunked(self.__chunk_size))
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
        resp.release()
        await resp.wait_for_close()
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
        session = await self.__ensure_session()
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
        self.__wss[self.__ws_cnt] = await session.ws_connect(url=url, params=params, headers=headers)
        return self.__ws_cnt

    async def ws_recv(self, cnt: int) -> tuple[bytes, BiliWsMsgType]:
        """
        接受 WebSocket 数据

        Args:
            cnt (int): WebSocket 连接编号

        Returns:
            Tuple[bytes, BiliWsMsgType]: WebSocket 数据和状态

        Note: 连接已被关闭并清理（`ws_close` 后）时，返回 `(b"", BiliWsMsgType.CLOSED)`，
        保持关闭状态可查询，不会因内部字典条目已移除而抛出 KeyError。
        """
        ws = self.__wss.get(cnt)
        if ws is None:
            # 条目不存在说明连接已关闭并被清理，返回 CLOSED 保持既有语义
            return (b"", BiliWsMsgType.CLOSED)
        msg = await ws.receive()
        request_log.dispatch(
            "WS_RECV",
            "收到 WebSocket 数据",
            {"id": cnt, "data": msg.data, "flags": msg.type.value},
        )
        return msg.data, BiliWsMsgType(msg.type.value)

    async def ws_send(self, cnt: int, data: bytes) -> None:
        """
        发送 WebSocket 数据，连接已关闭并清理时静默跳过

        Args:
            cnt (int): WebSocket 连接编号
            data (bytes): WebSocket 数据
        """
        request_log.dispatch(
            "WS_SEND",
            "发送 WebSocket 数据",
            {"id": cnt, "data": data},
        )
        ws = self.__wss.get(cnt)
        if ws is None:
            # 条目不存在说明连接已关闭并被清理，静默跳过（与 CurlCFFIClient 行为一致）
            return
        await ws.send_bytes(data)

    async def ws_close(self, cnt: int) -> None:
        """
        关闭 WebSocket 连接，重复关闭时静默跳过，并从内部字典移除条目避免句柄泄漏。

        Args:
            cnt (int): WebSocket 连接编号
        """
        request_log.dispatch(
            "WS_CLOSE",
            "关闭 WebSocket 请求",
            {"id": cnt},
        )
        ws = self.__wss.pop(cnt, None)
        if ws is None:
            # 条目不存在说明已关闭并清理过，静默跳过，避免反复重连场景下单调累积泄漏条目。
            # 关闭后 `ws_recv` 对不存在的条目返回 CLOSED，既有语义不受影响。
            return
        await ws.close()

    async def close(self):
        """
        关闭请求客户端，即关闭封装的第三方会话对象
        """
        if self.__session is not None:
            await self.__session.close()
            self.__session = None
