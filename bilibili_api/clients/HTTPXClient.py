"""
bilibili_api.clients.httpx

HTTPXClient 实现
"""

import asyncio
from collections.abc import AsyncGenerator

import httpx  # pylint: disable=E0401

from ..exceptions import ApiException
from ..utils.network import (
    BiliAPIClient,
    BiliAPIFile,
    BiliAPIResponse,
    request_log,
)


class HTTPXClient(BiliAPIClient):
    """
    httpx 模块请求客户端
    """

    def __init__(
        self,
        proxy: str = "",
        timeout: float = 0.0,
        verify_ssl: bool = True,
        trust_env: bool = True,
        http2: bool = False,
        chunk_size: int = 262144,
        session: httpx.AsyncClient | None = None,
    ) -> None:
        """
        Args:
            proxy (str, optional): 代理地址. Defaults to "".
            timeout (float, optional): 请求超时时间. Defaults to 0.0.
            verify_ssl (bool, optional): 是否验证 SSL. Defaults to True.
            trust_env (bool, optional): `trust_env`. Defaults to True.
            http2 (bool, optional): 是否使用 HTTP2. Defaults to False.
            chunk_size (int, optional): 下载分块大小（字节）. Defaults to 262144.
            session (object, optional): 会话对象. Defaults to None.

        Note: 仅当用户只提供 `session` 参数且用户中途未调用 `set_xxx` 函数才使用用户提供的 `session`。
        """
        self.__proxy = proxy
        self.__timeout = timeout
        self.__verify_ssl = verify_ssl
        self.__trust_env = trust_env
        self.__http2 = http2
        self.__chunk_size = chunk_size
        if session:
            self.__session = session
        else:
            self.__session = self.__create_session()
        self.__downloads: dict[int, httpx.Response] = {}
        self.__download_iter: dict[int, AsyncGenerator] = {}
        self.__download_cnt: int = 0

    def __create_session(self) -> httpx.AsyncClient:
        """
        按当前配置创建新的 AsyncClient。

        Returns:
            httpx.AsyncClient: 新会话
        """
        return httpx.AsyncClient(
            timeout=self.__timeout,
            proxy=self.__proxy if self.__proxy != "" else None,
            verify=self.__verify_ssl,
            trust_env=self.__trust_env,
            http2=self.__http2,
            # 连接池参数：总连接数上限 100，保活连接上限 20（与 httpx 默认值一致，显式声明便于调优）
            limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
        )

    def __recreate_session(self) -> None:
        """
        重建会话并异步关闭旧会话，避免连接泄漏。
        """
        old_session = self.__session
        self.__session = self.__create_session()
        try:
            asyncio.get_running_loop().create_task(old_session.aclose())
        except RuntimeError:
            # 当前无运行中的事件循环时无法异步关闭，交由 GC 处理
            pass

    def get_wrapped_session(self) -> httpx.AsyncClient:
        """
        获取封装的第三方会话对象

        Returns:
            httpx.AsyncClient: 第三方会话对象
        """
        return self.__session

    def set_proxy(self, proxy: str = "") -> None:
        """
        设置代理地址

        Args:
            proxy (str, optional): 代理地址. Defaults to "".
        """
        self.__proxy = proxy
        self.__recreate_session()

    def set_timeout(self, timeout: float = 0.0) -> None:
        """
        设置请求超时时间

        Args:
            timeout (float, optional): 请求超时时间. Defaults to 0.0.
        """
        self.__timeout = timeout
        self.__session.timeout = timeout

    def set_verify_ssl(self, verify_ssl: bool = True) -> None:
        """
        设置是否验证 SSL

        Args:
            verify_ssl (bool, optional): 是否验证 SSL. Defaults to True.
        """
        self.__verify_ssl = verify_ssl
        self.__recreate_session()

    def set_trust_env(self, trust_env: bool = True) -> None:
        """
        设置 `trust_env`

        Args:
            trust_env (bool, optional): `trust_env`. Defaults to True.
        """
        self.__trust_env = trust_env
        self.__session.trust_env = trust_env

    def set_http2(self, http2: bool = False) -> None:
        """
        设置是否使用 http2.

        Args:
            http2 (bool, optional): 是否使用 http2. Defaults to False.
        """
        self.__http2 = http2
        self.__recreate_session()

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

        Note: 无需实现 data 为 str 且 files 不为空的情况。
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
        opened_files = []
        if files != {}:
            requests_like_files = {}
            for key, item in files.items():
                # 传文件句柄而非整体读入内存，请求完成后统一关闭
                f = open(item.path, "rb")
                opened_files.append(f)
                requests_like_files[key] = (
                    item.path,
                    f,
                    item.mime_type,
                )
            files = requests_like_files
        try:
            resp: httpx.Response = await self.__session.request(
                method=method,
                url=url,
                params=params,
                data=data,
                files=files,
                headers=headers,
                cookies=cookies,
                follow_redirects=allow_redirects,
            )
        finally:
            for f in opened_files:
                f.close()
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
        req = self.__session.build_request(method="GET", url=url, headers=headers)
        self.__downloads[self.__download_cnt] = await self.__session.send(req, stream=True, follow_redirects=True)
        self.__download_iter[self.__download_cnt] = self.__downloads[self.__download_cnt].aiter_bytes(self.__chunk_size)
        return self.__download_cnt

    async def download_chunk(self, cnt: int) -> bytes:
        """
        下载部分文件

        Args:
            cnt    (int): 下载编号

        Returns:
            bytes: 字节
        """
        iter = self.__download_iter[cnt]
        data = await anext(iter)
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
        del self.__download_iter[cnt]
        request_log.dispatch(
            "DWN_CLOSE",
            "结束下载",
            {"id": cnt},
        )

    async def ws_create(self, *args, **kwargs) -> None:
        """
        httpx 库暂未实现 WebSocket。相关讨论：<https://github.com/encode/httpx/issues/304>
        """
        raise ApiException("httpx 库暂未实现 WebSocket。相关讨论：<https://github.com/encode/httpx/issues/304>")

    async def ws_send(self, *args, **kwargs) -> None:
        """
        httpx 库暂未实现 WebSocket。相关讨论：<https://github.com/encode/httpx/issues/304>
        """
        raise ApiException("httpx 库暂未实现 WebSocket。相关讨论：<https://github.com/encode/httpx/issues/304>")

    async def ws_recv(self, *args, **kwargs) -> None:
        """
        httpx 库暂未实现 WebSocket。相关讨论：<https://github.com/encode/httpx/issues/304>
        """
        raise ApiException("httpx 库暂未实现 WebSocket。相关讨论：<https://github.com/encode/httpx/issues/304>")

    async def ws_close(self, *args, **kwargs) -> None:
        """
        httpx 库暂未实现 WebSocket。相关讨论：<https://github.com/encode/httpx/issues/304>
        """
        raise ApiException("httpx 库暂未实现 WebSocket。相关讨论：<https://github.com/encode/httpx/issues/304>")

    async def close(self) -> None:
        """
        关闭请求客户端，即关闭封装的第三方会话对象
        """
        await self.__session.aclose()
