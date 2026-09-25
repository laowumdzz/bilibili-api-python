"""
bilibili_api.utils._api — API 请求核心。
"""

import asyncio
from dataclasses import dataclass, field
from inspect import Parameter, signature
import itertools
import json
import re
from typing import cast

from ..exceptions import (
    NetworkException,
    ResponseCodeException,
    WbiRetryTimesExceedException,
)
from ._anti_spider import (
    _enc_dm,
    _enc_sign,
    anti_spider_cache,
)
from ._credential import Credential
from ._log import request_log
from ._session import BiliAPIClient, get_client
from ._types import HEADERS, BiliAPIFile, BiliAPIResponse, request_settings
from ._wbi import WbiManager

_api_request_id = itertools.count(1)
"""API_REQUEST / API_RESPONSE 事件共用的请求编号计数器（与 WS_ / DWN_ 事件的 id 模式一致）。

同一逻辑请求的所有 -403 重试尝试共享同一 id；API_REQUEST 事件的 payload 为
发起时刻的快照拷贝（含新增 id 键），不再是 Api 实例 __dict__ 的活引用。
"""


def refresh_buvid() -> None:
    """刷新模块自动生成的 buvid3 和 buvid4"""
    anti_spider_cache.invalidate_buvid()


def refresh_bili_ticket() -> None:
    """刷新 bili_ticket"""
    anti_spider_cache.invalidate_bili_ticket()


def recalculate_wbi() -> None:
    """重新计算 wbi 的参数"""
    WbiManager.invalidate()


async def get_buvid() -> tuple[str, str]:
    """
    获取 buvid3 和 buvid4

    Returns:
        Tuple[str, str]: 第 0 项为 buvid3，第 1 项为 buvid4。
    """
    return await anti_spider_cache.get_buvid()


async def get_bili_ticket(credential: Credential | None = None) -> tuple[str, str]:
    """
    获取 bili_ticket

    Args:
        credential (Credential, optional): 凭据. Defaults to None.

    Returns:
        Tuple[str, str]: bili_ticket, bili_ticket_expires
    """
    return await anti_spider_cache.get_bili_ticket(credential)


async def get_wbi_mixin_key(credential: Credential | None = None) -> str:
    """
    获取 wbi mixin key

    Args:
        credential (Credential, optional): 凭据. Defaults to None.

    Returns:
        str: wbi mixin key
    """
    return await WbiManager.get_mixin_key(credential)


_CLIENT_REQUEST_PROXY_SUPPORT: dict[type, bool] = {}

# JSONP 响应提取正则：模块级预编译，直接匹配原始 bytes，避免每次请求重复编译
_JSONP_RE = re.compile(rb"^.*?({.*}).*$", re.S)


def _client_request_supports_proxy(client: BiliAPIClient) -> bool:
    """
    判断请求客户端的 request 方法是否支持 proxy 关键字参数。

    通过 `register_client` 注册的第三方自定义客户端可能未实现 proxy 参数，
    因此基于签名内省探测，结果按客户端类缓存，每类仅探测一次。
    接受 `**kwargs` 的实现视为支持。

    Args:
        client (BiliAPIClient): 请求客户端。

    Returns:
        bool: request 方法是否支持 proxy 关键字参数。
    """
    cls = type(client)
    support = _CLIENT_REQUEST_PROXY_SUPPORT.get(cls)
    if support is None:
        try:
            params = signature(client.request).parameters
        except (TypeError, ValueError):
            support = False
        else:
            support = "proxy" in params or any(param.kind is Parameter.VAR_KEYWORD for param in params.values())
        _CLIENT_REQUEST_PROXY_SUPPORT[cls] = support
    return support


@dataclass
class Api:
    """
    用于请求的 Api 类，几乎所有 http 请求皆由此发出。

    Args:
        url (str): 请求地址

        method (str): 请求方法

        comment (str, optional): 注释. Defaults to "".

        wbi (bool, optional): 是否使用 wbi 鉴权 (`w_rid` / `wts`). Defaults to False.

        dm (bool, optional): 是否使用参数进一步的 wbi 鉴权 (`dm_xxx`)，有关鼠标/键盘操作记录. Defaults to False.

        verify (bool, optional): 是否验证凭据. Defaults to False.

        no_csrf (bool, optional): 是否不使用 csrf. Defaults to False.

        json_body (bool, optional): 是否使用 json 作为载荷. Defaults to False.

        ignore_code (bool, optional): 是否忽略返回值 code 的检验. Defaults to False.

        sign (bool, optional): 是否使用 APP 鉴权. Defaults to False.

        data (dict, optional): 请求载荷. Defaults to {}.

        params (dict, optional): 请求参数. Defaults to {}.

        files (dict[str, BiliAPIFile], optional): 附带文件. Defaults to {}.

        headers (dict, optional): 自定义的请求头. Defaults to {}.

        credential (Credential, optional): 凭据. Defaults to Credential().
    """

    url: str
    method: str
    comment: str = ""
    wbi: bool = False
    dm: bool = False
    verify: bool = False
    no_csrf: bool = False
    json_body: bool = False
    ignore_code: bool = False
    sign: bool = False
    data: dict = field(default_factory=dict)
    params: dict = field(default_factory=dict)
    files: dict[str, BiliAPIFile] = field(default_factory=dict)
    headers: dict = field(default_factory=dict)
    credential: Credential = field(default_factory=Credential)

    def __post_init__(self) -> None:
        self.method = self.method.upper()
        self.original_data = self.data.copy()
        self.original_params = self.params.copy()
        self.data = dict.fromkeys(self.data.keys(), "")
        self.params = dict.fromkeys(self.params.keys(), "")
        self.files = dict.fromkeys(self.files.keys(), "")
        self.headers = dict.fromkeys(self.headers.keys(), "")
        self.credential = self.credential if self.credential else Credential()

    def update_data(self, **kwargs) -> "Api":
        """
        更新 data

        Returns:
            Api: 返回自身
        """
        self.data = kwargs
        return self

    def update_params(self, **kwargs) -> "Api":
        """
        更新 params

        Returns:
            Api: 返回自身
        """
        self.params = kwargs
        return self

    def update_files(self, **kwargs) -> "Api":
        """
        更新 files

        Returns:
            Api: 返回自身
        """
        self.files = kwargs
        return self

    def update_headers(self, **kwargs) -> "Api":
        """
        更新 headers

        Returns:
            Api: 返回自身
        """
        self.headers = kwargs
        return self

    async def _prepare_request(self) -> dict:
        # 处理 bool
        new_params, new_data = {}, {}
        for key, value in self.params.items():
            if isinstance(value, bool):
                new_params[key] = int(value)
            elif value is not None:
                new_params[key] = value
        for key, value in self.data.items():
            if isinstance(value, bool):
                new_params[key] = int(value)
            elif value is not None:
                new_data[key] = value
        self.params, self.data = new_params, new_data
        # 如果接口需要 Credential 且未传入 sessdata 鉴权则报错
        if self.verify:
            self.credential.raise_for_no_sessdata()
        # 请求为非 GET 且 no_csrf 不为 True 时要求 bili_jct
        if self.method != "GET" and not self.no_csrf:
            self.credential.raise_for_no_bili_jct()
        # jsonp
        if self.params.get("jsonp") == "jsonp":
            self.params["callback"] = "callback"
        # 鼠标移动 wbi 风控 (这东西不放在前面工作不了)
        # (https://github.com/Nemo2011/bilibili-api/issues/595)
        if self.dm:
            self.params = _enc_dm(self.params)
        # 普遍存在的 wbi 鉴权
        if self.wbi:
            self.params = await WbiManager.get_end_result(self.params, self.credential)
        # 自动添加 csrf
        if (not self.no_csrf and self.verify and self.method in ["POST", "DELETE", "PATCH"]) and isinstance(
            self.data, dict
        ):
            self.data["csrf"] = self.credential.bili_jct
            self.data["csrf_token"] = self.credential.bili_jct
        # 处理 cookies
        cookies = self.credential.get_cookies()
        if (cookies["buvid3"] == "" or cookies["buvid4"] == "") and request_settings.get_enable_auto_buvid():
            buvids = await get_buvid()
            cookies["buvid3"] = buvids[0]
            cookies["buvid4"] = buvids[1]
        cookies["opus-goback"] = "1"
        # bili_ticket
        if request_settings.get_enable_bili_ticket():
            cookies["bili_ticket"], cookies["bili_ticket_expires"] = await get_bili_ticket(self.credential)
        # APP 鉴权
        if self.sign:
            if self.method in ["POST", "DELETE", "PATCH"]:
                self.data = _enc_sign(self.data)
            else:
                self.params = _enc_sign(self.params)
        # 初步 params
        config = {
            "method": self.method,
            "url": self.url,
            "params": self.params,
            "data": self.data,
            "files": self.files,
            "cookies": cookies,
            "headers": HEADERS.copy() if len(self.headers) == 0 else self.headers,
            # 凭据携带的代理按请求传递，不再切换全局 request_settings；None 表示沿用全局代理
            "proxy": self.credential.proxy,
        }
        # json_body
        if self.json_body:
            config["headers"]["Content-Type"] = "application/json"
            config["data"] = json.dumps(config["data"])

        return config

    def _process_response(self, resp: BiliAPIResponse, raw: bool = False) -> int | str | dict | None:
        # 检查状态码
        if resp.code != 200:
            raise NetworkException(resp.code, resp.utf8_text())
        # 检查响应头 Content-Length
        content_length = resp.headers.get("content-length")
        if content_length and int(content_length) == 0:
            return None
        # 提取 json（直接解析原始 bytes，省去先全量解码为 str 的中间串）
        if "callback" in self.params:
            # JSONP 请求
            resp_data: dict = json.loads(_JSONP_RE.match(resp.raw).group(1))
        else:
            # JSON
            resp_data: dict = json.loads(resp.raw)
        if raw:
            return resp_data
        # 检查状态
        OK = resp_data.get("OK")
        if not self.ignore_code:
            if OK is None:
                code = resp_data.get("code")
                if code is None:
                    raise ResponseCodeException(-1, "API 返回数据未含 code 字段", resp_data)
                if code != 0:
                    msg = resp_data.get("msg")
                    if msg is None:
                        msg = resp_data.get("message")
                    if msg is None:
                        msg = "接口未返回错误信息"
                    raise ResponseCodeException(code, msg, resp_data)
            elif OK != 1:
                raise ResponseCodeException(-1, "API 返回数据 OK 不为 1", resp_data)
        # 自动提取 data / result 字段
        real_data = resp_data
        if OK is None:
            real_data = resp_data.get("data")
            if real_data is None:
                real_data = resp_data.get("result")
        return real_data

    async def _request_pair(
        self, raw: bool = False, byte: bool = False, request_id: int | None = None
    ) -> tuple[int | str | dict | bytes | None, dict]:
        api_id = request_id if request_id is not None else next(_api_request_id)
        request_log.dispatch(
            "API_REQUEST",
            "Api 发起请求",
            {**self.__dict__, "id": api_id},
        )
        config: dict = await self._prepare_request()
        client: BiliAPIClient = get_client()
        # 第三方自定义客户端可能未实现 proxy 参数，不支持时降级为沿用客户端配置的代理
        if not _client_request_supports_proxy(client):
            config.pop("proxy", None)
        resp: BiliAPIResponse = await client.request(**config)
        ret: int | str | dict | bytes | None
        if byte:
            ret = resp.raw
        else:
            ret = self._process_response(resp=resp, raw=raw)
        request_log.dispatch(
            "API_RESPONSE",
            "Api 获得响应",
            {"id": api_id, "result": ret},
        )
        return ret, resp.cookies

    async def _request(
        self, raw: bool = False, byte: bool = False, request_id: int | None = None
    ) -> int | str | dict | bytes | None:
        ret, _ = await self._request_pair(raw=raw, byte=byte, request_id=request_id)
        return ret

    async def _request_with_retry(
        self, raw: bool = False, byte: bool = False
    ) -> tuple[int | str | dict | bytes | None, dict]:
        times = request_settings.get_wbi_retry_times()
        loop = times
        # 同一逻辑请求的所有重试尝试共享同一请求 id，便于日志按 id 关联配对
        request_id = next(_api_request_id)
        while loop != 0:
            if loop != times:
                request_log.dispatch(
                    "ANTI_SPIDER",
                    "反爬虫",
                    {"msg": f"wbi 第 {times - loop} 次重试", "id": request_id},
                )
            loop -= 1
            try:
                return await self._request_pair(raw=raw, byte=byte, request_id=request_id)
            except ResponseCodeException as e:
                # -403 时尝试重新获取 wbi_mixin_key 可能过期了
                if e.code == -403 and self.wbi:
                    recalculate_wbi()
                    continue
                # 不是 -403 错误直接报错
                raise
        raise WbiRetryTimesExceedException()

    async def request(self, raw: bool = False, byte: bool = False) -> int | str | dict | bytes | None:
        """
        向接口发送请求。

        Args:
            raw  (bool): 是否不提取 data 或 result 字段。 Defaults to False.
            byte (bool): 是否直接返回字节数据。 Defaults to False.

        Returns:
            int | str | dict | bytes | None: 接口未返回数据时，返回 None，否则返回该接口提供的 data 或 result 字段的数据。
        """
        ret, _ = await self._request_with_retry(raw=raw, byte=byte)
        return ret

    async def request_with_cookies(self, raw: bool = False) -> tuple[int | str | dict | bytes | None, dict]:
        """
        向接口发送请求，并在返回处理结果的同时携带本响应由服务端下发的 Cookie。

        请求链路与 request() 完全一致（状态码校验、code 校验、data / result
        字段提取、-403 时的 wbi 重试）；区别仅在返回值为二元组，适用于需要读取
        响应 Set-Cookie 的场景（如网页端二维码扫码登录）。Cookie 名保持服务端
        原始大小写；响应未下发 Cookie 时第 2 项为空字典；发生重试时返回最终
        成功那次响应的 Cookie。

        Args:
            raw (bool): 是否不提取 data 或 result 字段。 Defaults to False.

        Returns:
            tuple[int | str | dict | bytes | None, dict]: 第 1 项与 request(raw=...) 的返回一致；第 2 项为本响应下发的 Cookie 字典。

        Raises:
            NetworkException: 网络错误或响应码非 200。
            ResponseCodeException: 接口返回错误码。
            WbiRetryTimesExceedException: wbi 重试次数超限。
        """
        return await self._request_with_retry(raw=raw)

    async def result_dict(self) -> dict:
        """
        获取请求结果并收窄为 dict 类型返回。

        供声明返回 dict 的接口调用点使用的链尾类型化访问器：请求链路与
        request() 完全一致（状态码校验、code 校验、data / result 字段提取、
        -403 时的 wbi 重试），仅在返回前做一次中心化类型收窄。收窄逻辑
        集中在此处，替代在约 380 个业务模块调用点散落 cast（spec
        005-pyrefly-type-debt FR-004）。request() / result 的联合返回类型
        与行为保持不变，本访问器为纯增量选项。

        Returns:
            dict: 接口返回的 data 或 result 字段数据。

        Raises:
            NetworkException: 网络错误或响应码非 200。
            ResponseCodeException: 接口返回错误码。
            WbiRetryTimesExceedException: wbi 重试次数超限。
        """
        result = await self.request()
        if isinstance(result, dict):
            return result
        # 中心收窄点（全局唯一批量豁口，research.md R2）：request() 的诚实联合类型
        # （int | str | dict | bytes | None）在此按"声明返回 dict 的端点契约"收窄。
        # 声明 -> dict 的端点运行时恒返回 JSON 对象（dict）；个别端点的空响应会
        # 透传 None，与既有 request() 行为一致。收窄用 cast 而非 isinstance 抛错，
        # 保持零运行时变更；若未来端点普查证实可升级为显式异常，须按行为变更
        # 单独评估（research.md R2 备选项 ③）。
        return cast(dict, result)

    async def result_list(self) -> list:
        """
        获取请求结果并收窄为 list 类型返回。

        供声明返回 list 的接口调用点使用的链尾类型化访问器，请求链路与
        收窄策略与 result_dict() 完全一致（中心化收窄，research.md R2）。

        Returns:
            list: 接口返回的 data 或 result 字段数据。

        Raises:
            NetworkException: 网络错误或响应码非 200。
            ResponseCodeException: 接口返回错误码。
            WbiRetryTimesExceedException: wbi 重试次数超限。
        """
        result = await self.request()
        if isinstance(result, list):
            return result
        # 中心收窄点（全局唯一批量豁口，research.md R2）：与 result_dict 同理，
        # 按"声明返回 list 的端点契约"收窄，保持零运行时变更
        return cast(list, result)

    @property
    async def result(self) -> int | str | dict | bytes | None:
        """
        获取请求结果
        """
        return await self.request()


async def bili_simple_download(url: str, out: str, intro: str):
    """
    适用于下载 bilibili 链接的简易终端下载函数

    默认会携带 HEADERS 访问链接，避免 403

    用途举例：下载 video.get_download_url 返回结果中的链接

    Args:
        url   (str): 链接
        out   (str): 输出地址
        intro (str): 下载简述
    """
    client = get_client()
    dwn_id = await client.download_create(url, HEADERS)
    bts = 0
    tot = client.download_content_length(dwn_id)
    # 缓冲写入：累积到 64KB 再落盘，减少系统调用次数
    flush_size = 65536
    try:
        # out 为调用方指定的下载输出路径，属下载函数固有形态
        # mimosa-ignore
        with open(out, "wb") as file:
            buffer = bytearray()
            while True:
                try:
                    chunk = await client.download_chunk(cnt=dwn_id)
                except StopAsyncIteration:
                    # 流结束（content-length 缺失或不准确时的安全退出路径）
                    break
                if chunk == b"":
                    break
                buffer.extend(chunk)
                bts += len(chunk)
                if len(buffer) >= flush_size:
                    # 大块落盘经线程池执行，避免同步阻塞 IO 占用事件循环；
                    # 转为不可变 bytes 再交给线程，规避 bytearray 跨线程共享风险
                    await asyncio.to_thread(file.write, bytes(buffer))
                    buffer.clear()
                if tot and bts >= tot:
                    break
            if buffer:
                # 尾块不足一个缓冲阈值，体量小，直接同步写入，避免额外线程调度开销
                file.write(buffer)
    finally:
        # 任何异常路径（含 download_chunk 抛出非 StopAsyncIteration 异常）都需关闭下载句柄，防止泄漏；
        # 清理自身若抛异常会顶替下载主流程的原始异常、掩盖真正故障原因，故此处吞掉清理异常。
        try:
            await client.download_close(cnt=dwn_id)
        except Exception:
            pass


################################################## END Api ##################################################
