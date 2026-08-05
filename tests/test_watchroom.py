# bilibili_api.watchroom

from bilibili_api import watchroom

season_id = 113
episode_id = 1678
room: watchroom.WatchRoom | None = None


async def test_a_match(credential):
    await watchroom.match(
        season_id=season_id,
        season_type=watchroom.SeasonType.ANIME,
        credential=credential,
    )


async def test_b_create(credential):
    global room
    room = await watchroom.create(season_id=season_id, episode_id=episode_id, is_open=False, credential=credential)


async def test_c_join():
    assert room is not None, "test_b_create 未成功创建观影室"
    await room.join()


async def test_d_share():
    assert room is not None, "test_b_create 未成功创建观影室"
    await room.share()


async def test_e_progress():
    assert room is not None, "test_b_create 未成功创建观影室"
    await room.progress(60, 0)
    await room.progress(30, 1)


async def test_f_open_and_close():
    assert room is not None, "test_b_create 未成功创建观影室"
    await room.close()
    await room.open()


async def test_g_send():
    assert room is not None, "test_b_create 未成功创建观影室"
    await room.send(
        watchroom.Message("测试")
        + watchroom.Message("测试2")
        + watchroom.MessageSegment("测试3")
        + watchroom.MessageSegment("doge", True)
    )
