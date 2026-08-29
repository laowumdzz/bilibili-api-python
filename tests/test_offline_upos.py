# bilibili_api.utils.upos 离线单元测试
#
# 本文件属于无凭据快速路径：全部用例均为纯本地逻辑验证，
# 不触碰网络、不读取 BILI_* 环境变量、不依赖真实账号。
# 覆盖：分块上传参数构建、分块并发上传调度与失败重试（用假任务工厂隔离网络）。

import asyncio

from bilibili_api.utils.upos import build_chunk_upload_params, upload_chunks_with_retry


def test_build_chunk_upload_params():
    """分块上传查询参数应按 upos 约定构建（partNumber 从 1 起）。"""
    params = build_chunk_upload_params(
        upload_id="UPID123",
        chunk_number=2,
        total_chunk_count=5,
        chunk_size=1024,
        offset=2048,
        total_size=5000,
    )
    assert params == {
        "partNumber": "3",
        "uploadId": "UPID123",
        "chunk": "2",
        "chunks": "5",
        "size": "1024",
        "start": "2048",
        "end": "3072",
        "total": 5000,
    }


async def test_upload_chunks_all_success():
    """全部分块一次成功时应按分块数调度且返回总分块数。"""
    seen: list[tuple[int, int]] = []

    async def make_chunk_task(offset: int, chunk_number: int, total_chunk_count: int) -> dict:
        seen.append((offset, chunk_number))
        await asyncio.sleep(0)
        return {"ok": True, "offset": offset, "chunk_number": chunk_number}

    # 文件 10 字节、分块 4 字节 → 3 个分块（0/4/8）
    total = await upload_chunks_with_retry(file_size=10, chunk_size=4, threads=2, make_chunk_task=make_chunk_task)
    assert total == 3
    assert sorted(seen) == [(0, 0), (4, 1), (8, 2)]


async def test_upload_chunks_retries_failed_chunk():
    """失败的分块应被重新入队重试，且每个分块最终都被上传成功。"""
    attempts: dict[int, int] = {}

    async def make_chunk_task(offset: int, chunk_number: int, total_chunk_count: int) -> dict:
        attempts[offset] = attempts.get(offset, 0) + 1
        await asyncio.sleep(0)
        # offset=4 的分块首次尝试失败，重试后成功
        ok = not (offset == 4 and attempts[offset] == 1)
        return {"ok": ok, "offset": offset, "chunk_number": chunk_number}

    total = await upload_chunks_with_retry(file_size=8, chunk_size=4, threads=1, make_chunk_task=make_chunk_task)
    assert total == 2
    assert attempts == {0: 1, 4: 2}, "失败分块应恰好重试一次"


async def test_upload_chunks_empty_file():
    """空文件不应产生任何分块。"""

    async def make_chunk_task(offset: int, chunk_number: int, total_chunk_count: int) -> dict:
        raise AssertionError("空文件不应调度任何分块")

    total = await upload_chunks_with_retry(file_size=0, chunk_size=4, threads=2, make_chunk_task=make_chunk_task)
    assert total == 0
