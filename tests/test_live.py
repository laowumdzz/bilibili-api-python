# bilibili_api.live

import random
import time

import pytest

from bilibili_api import live
from bilibili_api.exceptions import ResponseCodeException
from bilibili_api.utils.danmaku import Danmaku


@pytest.fixture(scope="module")
def room(credential) -> live.LiveRoom:
    return live.LiveRoom(22544798, credential)


async def test_a_get_room_info(room):
    await room.get_room_info()


async def test_b_get_room_play_info(room):
    await room.get_room_play_info()


async def test_c_get_room_play_info_v2(room):
    await room.get_room_play_info_v2()


async def test_d_get_room_play_url(room):
    await room.get_room_play_url()


async def test_e_get_user_info_in_room(room):
    await room.get_user_info_in_room()


async def test_f_get_dahanghai(room):
    await room.get_dahanghai()


async def test_g_get_serven_rank(room):
    await room.get_seven_rank()


async def test_h_get_fans_medal_rank(room):
    await room.get_fans_medal_rank()


async def test_i_get_self_info(credential):
    await live.get_self_info(credential)


async def test_j_get_danmu_info(room):
    await room.get_danmu_info()


async def test_k_ban_user(room):
    try:
        await room.ban_user(1, 1)
    except ResponseCodeException as e:
        # 1200000 / 100004：当前账号非该直播间房管，无禁言权限（账号状态问题，非本库 bug）
        if e.code not in (1200000, 100004):
            raise e


black_list = None


async def test_l_get_black_list(room):
    global black_list
    try:
        black_list = await room.get_black_list()
    except ResponseCodeException as e:
        # 10002 / 100004：当前账号非该直播间管理员，无黑名单权限（账号状态问题，非本库 bug）
        if e.code not in (10002, 100004):
            raise e


async def test_m_unban_user(room):
    if black_list is None:
        return
    for item in black_list["data"]:
        if item["tuid"] == 1:
            await room.unban_user(item["id"])
            return


async def test_n_send_danmaku(room):
    await room.send_danmaku(Danmaku(f"test_{random.randint(10000, 99999)}"))


async def test_p_sign_up_dahanghai(room):
    await room.sign_up_dahanghai()


async def test_q_send_gift_from_bag(room):
    try:
        await room.send_gift_from_bag(5702480, 255051127, 30607, 1)
    except ResponseCodeException as e:
        if e.code != 200161:
            raise e


async def test_r_receive_reward(room):
    await room.receive_reward(2)


async def test_s_get_general_info(room):
    await room.get_general_info()


# async def test_update_news(room):
#     await room.update_news("hello\nit's me")


async def test_t_get_self_live_info(credential):
    await live.get_self_live_info(credential)


async def test_u_get_self_guards(credential):
    await live.get_self_dahanghai_info(credential=credential)


async def test_v_get_self_bag(credential):
    try:
        await live.get_self_bag(credential)
    except ResponseCodeException as e:
        # 40000：上游背包接口偶发网络异常（上游风控/服务问题，非本库 bug）
        if e.code != 40000:
            raise e


async def test_w_get_gift_config():
    await live.get_gift_config()


async def test_x_get_gift_common(room):
    await room.get_gift_common()


# async def test_y_get_gift_sepcial(room):
#     await room.get_gift_special(tab_id=2)


async def test_z_send_gift_gold(room):
    try:
        await room.send_gift_gold(5702480, 31060, 1, 100)
    except ResponseCodeException as e:
        if e.code not in (200013, 200036):
            raise e


async def test_za_send_gift_silver(room):
    try:
        await room.send_gift_silver(5702480, 1, 1, 100)
    except ResponseCodeException as e:
        if e.code not in (200013, 200036):
            raise e


async def test_zb_get_area_info():
    await live.get_area_info()


async def test_zc_get_gaonengbang(room):
    await room.get_gaonengbang()


async def test_zc_get_live_followers_info(credential):
    await live.get_live_followers_info(credential=credential)


async def test_zd_get_unlive_followers_info(credential):
    await live.get_unlive_followers_info(page=1, credential=credential)


async def test_ze_get_following_live(credential):
    await live.create_live_reserve(
        credential=credential,
        title="测试",
        start_time=round(time.time()) + (60 * 60 * 4),
    )


async def test_zf_get_get_popular_ticket_num(room):
    await room.get_popular_ticket_num()


async def test_zg_popular_rank_free_score_incr(room):
    await room.send_popular_ticket()


async def test_zh_get_emoticons(room):
    await room.get_emoticons()


async def test_zi_send_emoticon(room):
    await room.send_danmaku(Danmaku("official_147"))
