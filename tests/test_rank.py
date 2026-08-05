# bilibili_api.rank

from bilibili_api import rank
from bilibili_api.rank import MangeRankType, RankDayType, RankType, VIPRankType

phase_id = None


async def test_a_get_rank():
    rank_types = [
        RankType.All,
        RankType.Original,
        RankType.Rookie,
        RankType.Bangumi,
        RankType.GuochuangAnime,
        RankType.Guochuang,
        RankType.Documentary,
        RankType.Douga,
        RankType.Music,
        RankType.Dance,
        RankType.Game,
        RankType.Knowledge,
        RankType.Technology,
        RankType.Sports,
        RankType.Car,
        RankType.Life,
        RankType.Food,
        RankType.Animal,
        RankType.Fashion,
        RankType.Ent,
        RankType.Cinephile,
        RankType.Movie,
        RankType.TV,
        RankType.Variety,
        RankType.Original,
    ]
    for rank_type in rank_types:
        await rank.get_rank(rank_type, RankDayType.WEEK)


async def test_f_music_rank_weekly_list():
    await rank.get_music_rank_list()


async def test_g_music_rank_weekly_details():
    await rank.get_music_rank_weekly_detail(1)


async def test_h_music_rank_weekly_contents():
    await rank.get_music_rank_weekly_musics(1)


async def test_i_get_vip_rank():
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


async def test_j_get_manga_rank(credential):
    for rank_type in MangeRankType:
        await rank.get_manga_rank(rank_type, credential=credential)


async def test_k_get_live_sailing_rank():
    await rank.get_live_sailing_rank()


async def test_l_get_live_hot_rank():
    await rank.get_live_hot_rank()


async def test_m_get_live_energy_user_rank():
    await rank.get_live_energy_user_rank()


async def test_n_get_live_rank():
    await rank.get_live_rank()


async def test_o_get_live_user_medal_rank():
    await rank.get_live_user_medal_rank()


async def test_p_subscribe_music_rank(credential):
    await rank.subscribe_music_rank(status=True, credential=credential)


async def test_q_get_playlet_rank_phases():
    phases = await rank.get_playlet_rank_phases()
    global phase_id
    phase_id = phases["editorChoicePhaseId"]


async def test_r_get_playlet_rank_info():
    assert phase_id is not None, "test_q_get_playlet_rank_phases 未成功获取 phase_id"
    await rank.get_playlet_rank_info(phase_id=phase_id)
