# bilibili_api 离线单元测试：WebSocket 句柄泄漏回归
#
# 本文件属于无凭据快速路径：全部用例均使用可控的假连接对象验证纯本地逻辑，
# 不触碰网络、不读取 BILI_* 环境变量、不依赖真实账号。

from bilibili_api.clients.AioHTTPClient import AioHTTPClient
from bilibili_api.utils._types import BiliWsMsgType

# 反复重连模拟次数：关闭 N 个连接后内部字典不应残留任何条目
RECONNECT_TIMES = 8


class FakeAioWs:
    """aiohttp.ClientWebSocketResponse 的可控替身，仅记录调用。"""

    def __init__(self) -> None:
        self.closed = False

    async def close(self) -> bool:
        self.closed = True
        return True

    async def receive(self):  # pragma: no cover
        raise AssertionError("不应在关闭后仍读取假连接")

    async def send_bytes(self, data: bytes) -> None:  # pragma: no cover
        raise AssertionError("不应在关闭后仍向假连接发送数据")


async def test_aiohttp_ws_close_removes_entry_and_no_leak():
    """AioHTTPClient 反复创建/关闭 ws 后，内部 __wss 字典不得单调累积。"""
    client = AioHTTPClient()
    for _ in range(RECONNECT_TIMES):
        fake_ws = FakeAioWs()
        client._AioHTTPClient__wss[client._AioHTTPClient__ws_cnt + 1] = fake_ws
        client._AioHTTPClient__ws_cnt += 1
        cnt = client._AioHTTPClient__ws_cnt
        await client.ws_close(cnt)
        assert fake_ws.closed, "ws_close 应实际关闭底层连接"
        assert cnt not in client._AioHTTPClient__wss, "关闭后条目应从内部字典移除"
    assert len(client._AioHTTPClient__wss) == 0


async def test_aiohttp_ws_close_idempotent():
    """AioHTTPClient 重复关闭同一连接应静默跳过而非抛 KeyError。"""
    client = AioHTTPClient()
    fake_ws = FakeAioWs()
    client._AioHTTPClient__wss[1] = fake_ws
    await client.ws_close(1)
    await client.ws_close(1)  # 第二次关闭不应抛异常
    assert len(client._AioHTTPClient__wss) == 0


async def test_aiohttp_ws_recv_after_close_returns_closed():
    """AioHTTPClient 关闭并清理后，ws_recv 应返回 CLOSED 状态而非抛 KeyError。"""
    client = AioHTTPClient()
    client._AioHTTPClient__wss[1] = FakeAioWs()
    await client.ws_close(1)
    data, flag = await client.ws_recv(1)
    assert data == b""
    assert flag == BiliWsMsgType.CLOSED


async def test_aiohttp_ws_send_after_close_silently_skipped():
    """AioHTTPClient 关闭并清理后，ws_send 应静默跳过而非抛 KeyError。"""
    client = AioHTTPClient()
    client._AioHTTPClient__wss[1] = FakeAioWs()
    await client.ws_close(1)
    await client.ws_send(1, b"test")  # 不应抛异常
