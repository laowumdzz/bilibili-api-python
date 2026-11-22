"""NoneBot 驱动承载客户端的离线契约测试（T043 / client-bridge.md §8）。"""

from __future__ import annotations

import asyncio
import json
import pathlib
from typing import Any
import warnings

from nonebot.drivers import Response
from nonebot.exception import WebSocketClosed
import pytest

from bilibili_api.clients.NoneBotClient import NoneBotClient, ensure_websocket_support
from bilibili_api.exceptions import ArgsException, NetworkException
from bilibili_api.utils.network import BiliAPIFile, BiliAPIResponse, BiliWsMsgType
from tests.nonebot_fakes import FakeDriver, FakeWebSocket, HttpOnlyDriver


def make_client(driver: object) -> NoneBotClient:
    return NoneBotClient(session=driver)


async def test_c01_request_mapping_and_file_close(tmp_path: pathlib.Path) -> None:
    """C-01：params / cookies / content / data / files 落到正确字段，文件句柄被关闭。"""
    driver = FakeDriver()
    driver.responses.append(Response(200, content=b"{}"))
    upload = tmp_path / "a.bin"
    upload.write_bytes(b"payload")
    client = make_client(driver)
    await client.request(
        method="post",
        url="https://example.com/api",
        params={"a": 1},
        cookies={"SESSDATA": "x", "empty": None},
        headers={"X-Test": "1"},
        data={"k": "v"},
        files={"file": BiliAPIFile(path=str(upload), mime_type="application/octet-stream")},
    )
    request = driver.requests[-1]
    assert request.method == "POST"
    assert request.url.query.get("a") == "1"
    assert request.headers["X-Test"] == "1"
    assert {cookie.name: cookie.value for cookie in request.cookies} == {"SESSDATA": "x"}
    assert request.data == {"k": "v"}
    assert request.files is not None
    assert request.files[0][1][0] == "a.bin"
    assert request.files[0][1][1].closed is True


async def test_c01_str_data_goes_to_content() -> None:
    """C-01：字符串载荷走 `content`（库把 JSON 序列化后放在 data 里）。"""
    driver = FakeDriver()
    driver.responses.append(Response(200, content=b"{}"))
    client = make_client(driver)
    await client.request(method="POST", url="https://example.com", data='{"a": 1}')
    request = driver.requests[-1]
    assert request.content == '{"a": 1}'
    assert request.data is None


async def test_c02_redirect_url_is_request_url() -> None:
    """C-02：驱动已跟随重定向，`url` 返回请求 URL。"""
    driver = FakeDriver()
    driver.responses.append(Response(200, content=b"{}"))
    client = make_client(driver)
    response = await client.request(url="https://example.com/start")
    assert response.code == 200
    assert response.url == "https://example.com/start"


async def test_c03_set_cookie_parsing() -> None:
    """C-03：多条 `Set-Cookie` 与含 `Expires` 的 cookie 全部解析。"""
    driver = FakeDriver()
    driver.responses.append(
        Response(
            200,
            headers=[
                ("Set-Cookie", "a=1; Path=/"),
                ("Set-Cookie", "b=2; Expires=Wed, 21 Oct 2026 07:28:00 GMT; Path=/"),
            ],
            content=b"{}",
        )
    )
    client = make_client(driver)
    response = await client.request(url="https://example.com")
    assert response.cookies == {"a": "1", "b": "2"}


async def test_c04_non_2xx_and_lowercase_headers() -> None:
    """C-04：非 2xx 不抛异常，headers 键统一小写。"""
    driver = FakeDriver()
    driver.responses.append(Response(412, headers={"Content-Length": "0"}, content=b""))
    client = make_client(driver)
    response = await client.request(url="https://example.com")
    assert response.code == 412
    assert response.headers["content-length"] == "0"


async def test_c05_ws_text_and_binary() -> None:
    """C-05：文本帧 / 二进制帧分别得到 TEXT / BINARY。"""
    driver = FakeDriver()
    driver.websockets.append(FakeWebSocket(["text", b"bin"]))
    client = make_client(driver)
    cnt = await client.ws_create("wss://example.com/sub")
    text, text_flag = await client.ws_recv(cnt)
    binary, binary_flag = await client.ws_recv(cnt)
    assert (text, text_flag) == (b"text", BiliWsMsgType.TEXT)
    assert (binary, binary_flag) == (b"bin", BiliWsMsgType.BINARY)
    await client.ws_close(cnt)


async def test_c06_ws_close_codes() -> None:
    """C-06：关闭码 1000 映射为 CLOSED，1006 原样抛出。"""
    driver = FakeDriver()
    driver.websockets.append(FakeWebSocket([WebSocketClosed(1000)]))
    driver.websockets.append(FakeWebSocket([WebSocketClosed(1006)]))
    client = make_client(driver)
    first = await client.ws_create("wss://example.com/a")
    assert await client.ws_recv(first) == (b"", BiliWsMsgType.CLOSED)
    second = await client.ws_create("wss://example.com/b")
    with pytest.raises(WebSocketClosed):
        await client.ws_recv(second)


async def test_c07_concurrent_recv_serialized() -> None:
    """C-07：同一句柄并发 `ws_recv` 串行化。"""
    driver = FakeDriver()
    driver.websockets.append(FakeWebSocket([b"one", b"two"]))
    client = make_client(driver)
    cnt = await client.ws_create("wss://example.com/sub")
    results = await asyncio.gather(client.ws_recv(cnt), client.ws_recv(cnt))
    assert sorted(result[0] for result in results) == [b"one", b"two"]


async def test_c08_close_while_receiving() -> None:
    """C-08：读取中关闭连接可释放且可重复调用。"""
    driver = FakeDriver()
    websocket = FakeWebSocket([])
    driver.websockets.append(websocket)
    client = make_client(driver)
    cnt = await client.ws_create("wss://example.com/sub")
    receiver = asyncio.create_task(client.ws_recv(cnt))
    await websocket.receive_started.wait()
    await client.ws_close(cnt)
    receiver.cancel()
    with pytest.raises(asyncio.CancelledError):
        await receiver
    assert websocket.closed is True
    await client.ws_close(cnt)


async def test_c09_missing_websocket_capability() -> None:
    """C-09：驱动缺 WebSocket 能力时抛 ArgsException，文本含驱动名。"""
    driver = HttpOnlyDriver()
    client = make_client(driver)
    with pytest.raises(ArgsException) as excinfo:
        await client.ws_create("wss://example.com/sub")
    assert "http-only" in str(excinfo.value)
    with pytest.raises(ArgsException):
        ensure_websocket_support(driver)


async def test_c10_stream_download() -> None:
    """C-10：分块返回、content_length 一致、关闭幂等。"""
    driver = FakeDriver()
    driver.stream_chunks = [b"abc", b"def"]
    driver.stream_headers = [("Content-Length", "6")]
    client = make_client(driver)
    cnt = await client.download_create("https://example.com/file")
    assert client.download_content_length(cnt) == 6
    assert await client.download_chunk(cnt) == b"abc"
    assert await client.download_chunk(cnt) == b"def"
    assert await client.download_chunk(cnt) == b""
    await client.download_close(cnt)
    await client.download_close(cnt)
    assert driver.stream_closed is True


def test_c11_library_import_without_nonebot_client() -> None:
    """C-11：`bilibili_api` 不 eager 导入驱动承载客户端。"""
    import bilibili_api.clients as clients

    assert all("NoneBot" not in name for name, _, _ in clients.ALL_PROVIDED_CLIENTS)
    source = pathlib.Path(str(clients.__file__)).read_text(encoding="utf-8")
    assert "NoneBotClient" not in source
    assert "nonebot" not in source.lower()


async def test_transport_error_normalized() -> None:
    """传输层异常统一包装为 `NetworkException`。"""
    driver = FakeDriver()
    driver.responses.append(ConnectionResetError("boom"))
    client = make_client(driver)
    with pytest.raises(NetworkException):
        await client.request(url="https://example.com")


async def test_session_must_be_driver() -> None:
    """`session` 只接受驱动实例。"""
    with pytest.raises(TypeError):
        NoneBotClient(session=object())


async def test_verify_ssl_warning() -> None:
    """`verify_ssl=False` 仅保存并告警。"""
    driver = FakeDriver()
    with warnings.catch_warnings(record=True) as recorded:
        warnings.simplefilter("always")
        client = make_client(driver)
        client.set_verify_ssl(False)
    assert any("verify_ssl" in str(item.message) for item in recorded)


# ---------------------------------------------------------------------------
# T043：适配器 API 调用经库抽象层与反爬链路发出
# ---------------------------------------------------------------------------


class StubLibraryClient:
    """记录 `Api` 下发的请求并返回预设业务载荷。"""

    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.calls: list[dict] = []

    async def request(self, **kwargs):  # type: ignore[no-untyped-def]
        self.calls.append(kwargs)
        raw = json.dumps(self.payload, ensure_ascii=False).encode("utf-8")
        return BiliAPIResponse(
            code=200,
            headers={"content-length": str(len(raw))},
            cookies={},
            raw=raw,
            url=kwargs["url"],
        )


def make_web_bot(credential: Any) -> Any:
    from bilibili_api.nonebot.adapters.bilibili_live.adapter import Adapter
    from bilibili_api.nonebot.adapters.bilibili_live.bot import WebBot

    adapter = Adapter(FakeDriver())
    return WebBot(adapter, self_id="1", credential=credential)


def logged_in_credential() -> Any:
    from bilibili_api.utils.network import Credential

    return Credential(sessdata="sess", bili_jct="jct", buvid3="b3", buvid4="b4", dedeuserid="1")


async def test_web_bot_send_danmaku_uses_library_chain(monkeypatch: pytest.MonkeyPatch) -> None:
    """发弹幕经 `Api` 链路：URL / 方法 / 参数 / 登录态与 csrf 由库注入。"""
    from bilibili_api.utils import _api

    stub = StubLibraryClient({"code": 0, "data": {}})
    monkeypatch.setattr(_api, "get_client", lambda: stub)
    bot = make_web_bot(logged_in_credential())
    await bot.send_danmaku(room_id=999, msg="hi", reply_mid=5)
    call = stub.calls[0]
    assert call["method"] == "POST"
    assert call["url"] == "https://api.live.bilibili.com/msg/send"
    assert call["data"]["msg"] == "hi"
    assert call["data"]["roomid"] == 999
    assert call["data"]["reply_mid"] == 5
    assert call["data"]["csrf"] == "jct"
    assert call["data"]["csrf_token"] == "jct"
    assert call["cookies"]["SESSDATA"] == "sess"
    assert "w_rid" not in call["params"]


async def test_web_bot_get_user_room_status_returns_model(monkeypatch: pytest.MonkeyPatch) -> None:
    """返回值为对应模型对象（UserRoomStatus）。"""
    from bilibili_api.utils import _api

    stub = StubLibraryClient(
        {
            "code": 0,
            "data": {
                "roomStatus": 1,
                "roundStatus": 0,
                "live_status": 1,
                "url": "https://live.bilibili.com/1",
                "title": "t",
                "cover": "c",
                "online": 10,
                "roomid": 999,
                "broadcast_type": 0,
                "online_hidden": 0,
            },
        }
    )
    monkeypatch.setattr(_api, "get_client", lambda: stub)
    bot = make_web_bot(logged_in_credential())
    status = await bot.get_user_room_status(1)
    assert status.room_id == 999
    assert status.is_live == 1
    assert stub.calls[0]["url"] == "https://api.live.bilibili.com/room/v1/Room/getRoomInfoOld"
    assert stub.calls[0]["params"]["mid"] == 1


async def test_web_bot_get_silent_user_list(monkeypatch: pytest.MonkeyPatch) -> None:
    """禁言列表返回 SilentUserListData 且参数按契约传递。"""
    from bilibili_api.utils import _api

    stub = StubLibraryClient({"code": 0, "data": {"data": [], "total": 0, "total_page": 0}})
    monkeypatch.setattr(_api, "get_client", lambda: stub)
    bot = make_web_bot(logged_in_credential())
    result = await bot.get_silent_user_list(999, ps=2)
    assert result.total == 0
    call = stub.calls[0]
    assert call["url"] == "https://api.live.bilibili.com/xlive/web-ucenter/v1/banned/GetSilentUserList"
    assert call["data"]["ps"] == "2"
    assert call["data"]["room_id"] == "999"


async def test_web_bot_del_silent_user_uses_roomid_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """解禁接口使用 `roomid`（无下划线）与 `id` 参数。"""
    from bilibili_api.utils import _api

    stub = StubLibraryClient({"code": 0, "data": {}})
    monkeypatch.setattr(_api, "get_client", lambda: stub)
    bot = make_web_bot(logged_in_credential())
    await bot.del_silent_user(999, silent_id=77)
    call = stub.calls[0]
    assert call["data"]["roomid"] == "999"
    assert call["data"]["id"] == "77"
    assert call["data"]["csrf"] == "jct"


async def test_unlogged_send_danmaku_raises_project_exception() -> None:
    """未登录：抛项目异常，不泄漏第三方异常。"""
    from bilibili_api.exceptions import CredentialNoSessdataException
    from bilibili_api.utils.network import Credential

    bot = make_web_bot(Credential())
    with pytest.raises(CredentialNoSessdataException):
        await bot.send_danmaku(room_id=999, msg="hi")


async def test_missing_csrf_raises_project_exception() -> None:
    """缺少 bili_jct：抛项目异常。"""
    from bilibili_api.exceptions import CredentialNoBiliJctException
    from bilibili_api.utils.network import Credential

    bot = make_web_bot(Credential(sessdata="sess", buvid3="b3", buvid4="b4", dedeuserid="1"))
    with pytest.raises(CredentialNoBiliJctException):
        await bot.send_danmaku(room_id=999, msg="hi")


async def test_bot_send_derives_reply_mid() -> None:
    """`send` 按上游规则推导 reply_mid（AtSegment / Message 内的 at 段）。"""
    from types import SimpleNamespace

    from bilibili_api.nonebot.adapters.bilibili_live.message import Message, MessageSegment

    bot = make_web_bot(logged_in_credential())
    captured: list[dict] = []

    async def fake_send_danmaku(room_id: int, msg: str, mode: int = 1, reply_mid: int = 0) -> None:
        captured.append({"room_id": room_id, "msg": msg, "reply_mid": reply_mid})

    bot.send_danmaku = fake_send_danmaku  # type: ignore[method-assign]
    event = SimpleNamespace(room_id=999, get_user_id=lambda: "77")

    await bot.send(event, MessageSegment.at(42))
    assert captured[-1]["reply_mid"] == 42
    assert captured[-1]["msg"] == "<at:42>"

    await bot.send(event, "plain", reply_message=True)
    assert captured[-1]["reply_mid"] == 77

    message = Message("x") + MessageSegment.at(88)
    await bot.send(event, message)
    assert captured[-1]["reply_mid"] == 88
