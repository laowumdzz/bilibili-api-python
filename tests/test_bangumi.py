# bilibili_api.bangumi

from bilibili_api import bangumi
from bilibili_api.bangumi import IndexFilter as IF

b = bangumi.Bangumi(28231846)
ep = bangumi.Episode(374717)


async def test_a_Bangumi_get_meta():
    await b.get_meta()


async def test_b_Bangumi_get_short_comment_list():
    await b.get_short_comment_list()


async def test_c_Bangumi_get_long_comment_list():
    await b.get_long_comment_list()


async def test_d_Bangumi_get_episode_list():
    await b.get_episode_list()


async def test_e_Bangumi_get_stat():
    await b.get_stat()


async def test_f_Episode_get_episode_info():
    await ep.get_episode_info()


async def test_g_Bangumi_get_overview():
    await b.get_overview()


# 港澳台 ep 测试 START
# e = bangumi.Bangumi(epid=562695, oversea=True)  # 港澳台番剧


# # e = bangumi.Bangumi(media_id=28338523, oversea=True)  # 港澳台番剧
# # e = bangumi.Bangumi(epid=674709)  # 内地番剧


# async def test_oversea_gangaotai_get_item():
#     await e.get_episode_list()


# async def test_oversea_gangaotai_get_bangumi():
#     await e.get_meta()


# async def test_oversea_Bangumi_get_episode_list():
#     await e.get_episode_list()


# async def test_oversea_Bangumi_get_stat():
#     await e.get_stat()


# async def test_h_Bangumi_get_episodes():
#     await b.get_episodes()


async def test_get_bangumi_index():
    filters = bangumi.IndexFilterMeta.Anime(
        area=IF.Area.JAPAN,
        year=IF.make_time_filter(start=2019, end=2022, include_end=True),
        season=IF.Season.SPRING,
        style=IF.Style.Anime.NOVEL,
    )
    await bangumi.get_index_info(filters=filters, order=IF.Order.FOLLOWER, sort=IF.Sort.ASC, pn=2, ps=20)


# 港澳台 ep 测试 END
