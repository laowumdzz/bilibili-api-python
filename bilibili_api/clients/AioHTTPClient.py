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
        return self.__session

    def set_proxy(self, proxy: str = "") -> None:
        self.__use_args = True
        self.__args["proxy"] = proxy

    def set_timeout(self, timeout: float = 0) -> None:
        self.__use_args = True
        self.__args["timeout"] = timeout

    def set_verify_ssl(self, verify_ssl: bool = True) -> None:
        self.__use_args = True
        self.__args["verify_ssl"] = verify_ssl
        self.__need_update_session = True

    def set_trust_env(self, trust_env: bool = True) -> None:
        self.__use_args = True
        self.__args["trust_env"] = trust_env
        self.__need_update_session = True

    def set_chunk_size(self, chunk_size: int = 262144) -> None:
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
                proxy=self.__args["proxy"],
                timeout=aiohttp.ClientTimeout(self.__args["timeout"]),
            )
        else:
            resp = await session.request(
                method=method,
                url=url,
                params=params,
                data=data,
                headers=headers,
                cookies=cookies,
                allow_redirects=allow_redirects,
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
        resp.release()
        await resp.wait_for_close()
        return bili_api_resp

    async def download_create(
        self,
        url: str = "",
        headers: dict = {},
    ) -> int:
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
        resp = self.__downloads[cnt]
        data = await anext(resp.content.iter_chunked(self.__chunk_size))
        request_log.dispatch(
            "DWN_PART",
            "收到部分下载数据",
            {"id": cnt, "length": len(data)},
        )
        return data

    def download_content_length(self, cnt: int) -> int:
        resp = self.__downloads[cnt]
        return int(resp.headers.get("content-length", "0"))

    async def download_close(self, cnt: int) -> None:
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
        msg = await self.__wss[cnt].receive()
        request_log.dispatch(
            "WS_RECV",
            "收到 WebSocket 数据",
            {"id": cnt, "data": msg.data, "flags": msg.type.value},
        )
        return msg.data, BiliWsMsgType(msg.type.value)

    async def ws_send(self, cnt: int, data: bytes) -> None:
        request_log.dispatch(
            "WS_SEND",
            "发送 WebSocket 数据",
            {"id": cnt, "data": data},
        )
        return await self.__wss[cnt].send_bytes(data)

    async def ws_close(self, cnt: int) -> None:
        request_log.dispatch(
            "WS_CLOSE",
            "关闭 WebSocket 请求",
            {"id": cnt},
        )
        return await self.__wss[cnt].close()

    async def close(self):
        if self.__session is not None:
            await self.__session.close()
            self.__session = None

    __init__.__doc__ = BiliAPIClient.__init__.__doc__
    get_wrapped_session.__doc__ = BiliAPIClient.get_wrapped_session.__doc__
    set_proxy.__doc__ = BiliAPIClient.set_proxy.__doc__
    set_timeout.__doc__ = BiliAPIClient.set_timeout.__doc__
    set_verify_ssl.__doc__ = BiliAPIClient.set_verify_ssl.__doc__
    set_trust_env.__doc__ = BiliAPIClient.set_trust_env.__doc__
    request.__doc__ = BiliAPIClient.request.__doc__
    download_create.__doc__ = BiliAPIClient.download_create.__doc__
    download_chunk.__doc__ = BiliAPIClient.download_chunk.__doc__
    download_content_length.__doc__ = BiliAPIClient.download_content_length.__doc__
    ws_create.__doc__ = BiliAPIClient.ws_create.__doc__
    ws_recv.__doc__ = BiliAPIClient.ws_recv.__doc__
    ws_send.__doc__ = BiliAPIClient.ws_send.__doc__
    ws_close.__doc__ = BiliAPIClient.ws_close.__doc__
    close.__doc__ = BiliAPIClient.close.__doc__
