# bilibili_api.rank

import asyncio

import pytest

from bilibili_api import rank
from bilibili_api.rank import MangeRankType, RankDayType, RankType, VIPRankType


@pytest.mark.cred1
async def test_a_get_rank():
    """采样 5 个代表分区（含默认全站与老牌 / 较新边缘类型）+ 循环节流，替代全分区遍历（research R8）。"""
    rank_types = [
        RankType.All,  # 默认全站榜
        RankType.Original,  # 原创（老牌分区代表）
        RankType.Douga,  # 动画（经典内容分区代表）
        RankType.Cinephile,  # 影视（较新分区边缘代表）
        RankType.Rookie,  # 新人（边缘类型代表）
    ]
    for rank_type in rank_types:
        await rank.get_rank(rank_type, RankDayType.WEEK)
        await asyncio.sleep(0.5)


@pytest.mark.cred1
async def test_f_music_rank_weekly_list():
    await rank.get_music_rank_list()


@pytest.mark.cred1
async def test_g_music_rank_weekly_details():
    await rank.get_music_rank_weekly_detail(1)


@pytest.mark.cred1
async def test_h_music_rank_weekly_contents():
    await rank.get_music_rank_weekly_musics(1)


@pytest.mark.cred1
async def test_i_get_vip_rank():
    """大会员榜保留全量（账号 VIP 有效，research R8）+ 循环节流。"""
    need_test_ranks = [
        VIPRankType.VIP,
        VIPRankType.MOVIE,
        VIPRankType.TV,
        VIPRankType.VARIETY,
        VIPRankType.BANGUMI,
        VIPRankType.GUOCHUANG,
        VIPRankType.DOCUMENTARY,
    ]
    for rank_type in need_test_ranks:
        await rank.get_vip_rank(rank_type)
        await asyncio.sleep(0.5)


@pytest.mark.cred1
async def test_j_get_manga_rank(credential):
    """采样 3 个漫画榜（新作 / 日漫 / 国漫）+ 循环节流，替代全类型遍历（research R8）。"""
    rank_types = [
        MangeRankType.NEW,
        MangeRankType.JAPAN,
        MangeRankType.GUOCHUANG,
    ]
    for rank_type in rank_types:
        await rank.get_manga_rank(rank_type, credential=credential)
        await asyncio.sleep(0.5)


@pytest.mark.cred1
async def test_k_get_live_sailing_rank():
    await rank.get_live_sailing_rank()


@pytest.mark.cred1
async def test_l_get_live_hot_rank():
    await rank.get_live_hot_rank()


@pytest.mark.cred1
async def test_m_get_live_energy_user_rank():
    await rank.get_live_energy_user_rank()


@pytest.mark.cred1
async def test_n_get_live_rank():
    await rank.get_live_rank()


@pytest.mark.cred1
async def test_o_get_live_user_medal_rank():
    await rank.get_live_user_medal_rank()


async def test_p_subscribe_music_rank(credential):
    await rank.subscribe_music_rank(status=True, credential=credential)


@pytest.mark.cred1
async def test_q_get_playlet_rank_phases():
    """播放剧榜 phase 获取与消费链合并为单用例，消除 phase_id 跨用例全局依赖（FR-009 / research R4）。"""
    phases = await rank.get_playlet_rank_phases()
    phase_id = phases["editorChoicePhaseId"]
    assert phase_id is not None, "get_playlet_rank_phases 未返回 editorChoicePhaseId"
    await rank.get_playlet_rank_info(phase_id=phase_id)
