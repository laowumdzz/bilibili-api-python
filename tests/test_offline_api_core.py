# bilibili_api 离线单元测试：下载句柄关闭保障与 Api 响应解析
#
# 本文件属于无凭据快速路径：全部用例均为纯本地逻辑验证，
# 不触碰网络、不读取 BILI_* 环境变量、不依赖真实账号。
# 由 pytest 收集运行（uv run pytest），且不会被 conftest.py 打上 integration 标记。

import pytest

from bilibili_api.utils import _api as api_mod
from bilibili_api.utils._api import bili_simple_download


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
