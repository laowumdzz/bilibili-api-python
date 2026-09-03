# bilibili_api 离线单元测试：下载句柄关闭保障与 Api 响应解析
#
# 本文件属于无凭据快速路径：全部用例均为纯本地逻辑验证，
# 不触碰网络、不读取 BILI_* 环境变量、不依赖真实账号。
# 由 pytest 收集运行（uv run pytest），且不会被 conftest.py 打上 integration 标记。

import json

import pytest

from bilibili_api.exceptions import NetworkException
from bilibili_api.utils import _api as api_mod
from bilibili_api.utils._api import Api, bili_simple_download
from bilibili_api.utils._types import BiliAPIResponse


class FakeDownloadClient:
    """假下载客户端：按序返回预设数据块，记录 download_close 调用。"""

    def __init__(self, chunks: list[bytes], fail_at: int | None = None):
        self.chunks = list(chunks)
        self.fail_at = fail_at  # 返回该序号的数据块前抛出 RuntimeError
        self.closed = False
        self.close_cnt: int | None = None
        self.index = 0

    async def download_create(self, url: str, headers: dict) -> int:
        """记录创建请求并返回固定句柄号。"""
        return 42

    def download_content_length(self, cnt: int) -> int:
        """返回 0 走 content-length 不可信、依赖流结束退出的分支。"""
        return 0

    async def download_chunk(self, cnt: int) -> bytes:
        """按序返回数据块，可模拟中途异常；数据耗尽时抛 StopAsyncIteration。"""
        if self.fail_at is not None and self.index == self.fail_at:
            raise RuntimeError("模拟数据块读取失败")
        if self.index >= len(self.chunks):
            raise StopAsyncIteration
        chunk = self.chunks[self.index]
        self.index += 1
        return chunk

    async def download_close(self, cnt: int) -> None:
        """记录关闭调用及对应句柄号。"""
        self.closed = True
        self.close_cnt = cnt


def _make_resp(
    raw: bytes, headers: dict | None = None, code: int = 200, cookies: dict | None = None
) -> BiliAPIResponse:
    """构造离线用的假响应对象。"""
    return BiliAPIResponse(code=code, headers=headers or {}, cookies=cookies or {}, raw=raw, url="https://example.com")


async def test_download_close_called_on_chunk_error(tmp_path, monkeypatch):
    """download_chunk 中途抛非 StopAsyncIteration 异常时，download_close 仍被调用。"""
    big_chunk = b"x" * 70000  # 超过 64KB 缓冲阈值，先经 to_thread 落盘再模拟失败
    fake = FakeDownloadClient([big_chunk], fail_at=1)
    monkeypatch.setattr(api_mod, "get_client", lambda: fake)
    out = tmp_path / "out.bin"
    with pytest.raises(RuntimeError, match="模拟数据块读取失败"):
        await bili_simple_download("https://example.com/file", str(out), "测试下载")
    assert fake.closed is True
    assert fake.close_cnt == 42
    # 异常前已落盘的数据块保留在文件中
    assert out.read_bytes() == big_chunk


async def test_download_success_path(tmp_path, monkeypatch):
    """正常结束路径：全部数据块落盘且句柄被关闭。"""
    chunks = [b"a" * 70000, b"b" * 1000]  # 首块触发缓冲落盘，尾块走同步小写入
    fake = FakeDownloadClient(chunks)
    monkeypatch.setattr(api_mod, "get_client", lambda: fake)
    out = tmp_path / "out.bin"
    await bili_simple_download("https://example.com/file", str(out), "测试下载")
    assert fake.closed is True
    assert out.read_bytes() == b"".join(chunks)


def test_process_response_jsonp_bytes():
    """JSONP 包裹的 bytes 应提取出内层 JSON，行为与原 str 解析一致。"""
    api = Api(url="https://example.com", method="GET", params={"callback": "callback"})
    raw = b'callback({"code":0,"message":"0","data":{"x":1}})'
    assert api._process_response(_make_resp(raw), raw=True) == {
        "code": 0,
        "message": "0",
        "data": {"x": 1},
    }
    # 非 raw 模式自动提取 data 字段
    assert api._process_response(_make_resp(raw)) == {"x": 1}


def test_process_response_jsonp_bytes_with_unicode():
    """含多字节 UTF-8 字符的 JSONP bytes 解析结果正确。"""
    api = Api(url="https://example.com", method="GET", params={"callback": "callback"})
    payload = {"code": 0, "data": {"msg": "中文内容"}}
    raw = b"callback(" + json.dumps(payload, ensure_ascii=False).encode("utf-8") + b")"
    assert api._process_response(_make_resp(raw), raw=True) == payload


def test_process_response_plain_json_bytes():
    """普通 JSON bytes 直接解析，无需先解码为 str。"""
    api = Api(url="https://example.com", method="GET")
    raw = b'{"code":0,"data":{"y":2}}'
    assert api._process_response(_make_resp(raw), raw=True) == {"code": 0, "data": {"y": 2}}
    assert api._process_response(_make_resp(raw)) == {"y": 2}


def test_process_response_non_json_text_raises():
    """非 JSON 文本响应仍抛出 JSONDecodeError，与改造前行为一致。"""
    api = Api(url="https://example.com", method="GET")
    with pytest.raises(json.JSONDecodeError):
        api._process_response(_make_resp(b"<html>not json</html>"), raw=True)


def test_process_response_empty_body_returns_none():
    """content-length 为 0 的空响应返回 None。"""
    api = Api(url="https://example.com", method="GET")
    assert api._process_response(_make_resp(b"", headers={"content-length": "0"})) is None


def test_process_response_non_200_raises_network_exception():
    """非 200 状态码抛出 NetworkException，异常信息沿用 utf8_text() 路径。"""
    api = Api(url="https://example.com", method="GET")
    with pytest.raises(NetworkException):
        api._process_response(_make_resp(b"gateway error", code=502))


# ---------------------------------------------------------------- request_with_cookies


def _poll_like_body() -> bytes:
    """构造与二维码轮询接口同构的响应体（外层 code=0，data 内承载业务字段）。"""
    return json.dumps(
        {
            "code": 0,
            "message": "0",
            "ttl": 1,
            "data": {
                "url": "https://passport.biligame.com/x/passport-login/web/crossDomain?ticket=fake",
                "refresh_token": "fake-refresh-token",
                "timestamp": 1788414542857,
                "code": 0,
                "message": "",
            },
        }
    ).encode("utf-8")


class FakeRequestClient:
    """假请求客户端：返回预设的 BiliAPIResponse。"""

    def __init__(self, resp: BiliAPIResponse):
        self.resp = resp

    async def request(self, **config) -> BiliAPIResponse:
        """返回预设响应。"""
        return self.resp


def _patch_request_path(monkeypatch, resp: BiliAPIResponse) -> None:
    """离线隔离完整请求路径：假客户端 + 绕开会触发反爬联网的 _prepare_request。"""
    monkeypatch.setattr(api_mod, "get_client", lambda: FakeRequestClient(resp))

    async def _fake_prepare_request(self) -> dict:
        return {
            "method": self.method,
            "url": self.url,
            "params": {},
            "data": {},
            "files": {},
            "cookies": {},
            "headers": {},
            "proxy": None,
        }

    monkeypatch.setattr(api_mod.Api, "_prepare_request", _fake_prepare_request)


async def test_request_with_cookies_returns_data_and_cookies(monkeypatch):
    """非 raw 模式提取 data 字段，同时原样返回响应 Cookie（保留原名大小写）。"""
    _patch_request_path(
        monkeypatch,
        _make_resp(
            _poll_like_body(),
            cookies={
                "SESSDATA": "fake-sessdata",
                "bili_jct": "fake-jct",
                "DedeUserID": "fake-uid",
                "buvid3": "fake-b3",
            },
        ),
    )
    data, cookies = await Api(url="https://example.com/poll", method="GET").request_with_cookies()
    assert data["refresh_token"] == "fake-refresh-token"
    assert cookies == {
        "SESSDATA": "fake-sessdata",
        "bili_jct": "fake-jct",
        "DedeUserID": "fake-uid",
        "buvid3": "fake-b3",
    }


async def test_request_with_cookies_raw_returns_full_body(monkeypatch):
    """raw 模式返回完整解析后的 JSON 体，与 request(raw=True) 语义对齐。"""
    _patch_request_path(monkeypatch, _make_resp(_poll_like_body(), cookies={"SESSDATA": "x"}))
    body, _ = await Api(url="https://example.com/poll", method="GET").request_with_cookies(raw=True)
    assert body["code"] == 0
    assert body["data"]["url"].startswith("https://passport.biligame.com/")


async def test_request_with_cookies_no_set_cookie_returns_empty_dict(monkeypatch):
    """响应未下发 Cookie 时第 2 项为空字典，不报错。"""
    _patch_request_path(monkeypatch, _make_resp(_poll_like_body()))
    data, cookies = await Api(url="https://example.com/poll", method="GET").request_with_cookies()
    assert data is not None
    assert cookies == {}


async def test_request_still_returns_data_only(monkeypatch):
    """既有 request() 与 perf 直连入口 _request() 均不受影响：只返回处理结果。"""
    _patch_request_path(monkeypatch, _make_resp(_poll_like_body(), cookies={"SESSDATA": "fake-sessdata"}))
    ret = await Api(url="https://example.com/poll", method="GET").request()
    assert isinstance(ret, dict)
    assert ret["refresh_token"] == "fake-refresh-token"
    ret2 = await Api(url="https://example.com/poll", method="GET")._request()
    assert ret2 == ret
