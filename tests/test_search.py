# bilibili_api.search

import pytest

from bilibili_api import search, video_zone


@pytest.mark.cred0
async def test_a_search():
    await search.search("这是他的笑容发生的变化")


@pytest.mark.cred1
async def test_b_search_by_type():
    await search.search_by_type("丸子叨叨叨", search.SearchObjectType.USER)


@pytest.mark.cred1
async def test_c_get_hot_search_keywords():
    await search.get_hot_search_keywords()


@pytest.mark.cred1
async def test_d_get_default_search_keyword():
    await search.get_default_search_keyword()


@pytest.mark.cred1
async def test_e_get_suggest_keywords():
    await search.get_suggest_keywords("gswdm")


@pytest.mark.cred1
async def test_f_search_by_order():
    await search.search_by_type(
        "小马宝莉",
        search_type=search.SearchObjectType.VIDEO,
        order_type=search.OrderVideo.SCORES,
        time_range=10,
        video_zone_type=video_zone.VideoZoneTypes.DOUGA_MMD,
        page=1,
    )


@pytest.mark.cred1
async def test_g_search_game():
    await search.search_games("原神")


@pytest.mark.cred1
async def test_h_search_manga(credential):
    await search.search_manga("来自深渊", credential=credential)


@pytest.mark.cred1
async def test_i_search_cheese():
    await search.search_cheese("Python")
