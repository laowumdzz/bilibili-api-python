# bilibili_api.watchroom

import pytest

from bilibili_api import watchroom

SEASON_ID = 113
EPISODE_ID = 1678


@pytest.mark.cred1
async def test_a_match(credential):
    await watchroom.match(
        season_id=SEASON_ID,
        season_type=watchroom.SeasonType.ANIME,
        credential=credential,
    )


@pytest.mark.cred2
async def test_b_watchroom_lifecycle(credential, teardown_retry):
    """观影房间完整生命周期：创建 → 加入 → 分享 → 进度上报 → 关闭 / 重开 → 发送消息 → 关闭清理（cred2）。

    原链路依赖 room 跨用例全局变量，合并为单用例后顺序无关（FR-009，research R4）；
    房间在 finally 中关闭（teardown 级清理义务，FR-006）。
    """
    room = await watchroom.create(season_id=SEASON_ID, episode_id=EPISODE_ID, is_open=False, credential=credential)
    try:
        await room.join()
        await room.share()
        await room.progress(60, 0)
        await room.progress(30, 1)
        await room.close()
        await room.open()
        await room.send(
            watchroom.Message("测试")
            + watchroom.Message("测试2")
            + watchroom.MessageSegment("测试3")
            + watchroom.MessageSegment("doge", True)
        )
    finally:
        await teardown_retry("观影房间关闭", room.close)
