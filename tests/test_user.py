# bilibili_api.user

import asyncio

import pytest

from bilibili_api import user
from bilibili_api.exceptions import NetworkException
from bilibili_api.exceptions.ResponseCodeException import ResponseCodeException

UID4 = 166311555
UID_Model_Test = 12344667

page_num = 1
per_page_item = 10


@pytest.fixture(scope="module")
def u(credential) -> user.User:
    return user.User(UID_Model_Test, credential=credential)


async def test_a_User_get_user_info(u):
    await u.get_user_info()


async def test_b_User_get_relation_info(u):
    await u.get_relation_info()


async def test_c_User_get_up_info(u):
    await u.get_up_stat()


async def test_d_User_get_live_info(u):
    await u.get_live_info()


async def test_e_User_get_videos(u):
    await u.get_videos()


async def test_e_User_get_media_list(u):
    await u.get_media_list()


async def test_f_User_get_audios(u):
    await u.get_audios()


async def test_g_User_get_articles(u):
    await u.get_articles()


async def test_h_User_article_list(u):
    await u.get_article_list()


async def test_l_User_get_dynamics(u):
    try:
        await u.get_dynamics()
    except NetworkException:
        # 上游 api.vc.bilibili.com 空间动态接口已下线（返回 404 页面，非本库 bug）
        pass


# async def test_j_User_subscribed_bangumis(u):
#    await u.get_subscribed_bangumi()


async def test_k_User_get_followers(u):
    await u.get_followers()


async def test_l_User_get_followings(u):
    try:
        await u.get_followers()
    except ResponseCodeException as e:
        if e.code != 22115:
            raise e


async def test_m_User_get_all_followers(u):
    await u.get_all_followings()


async def test_n_User_get_cheese(u):
    await u.get_cheese()


async def test_o_User_get_channel_series(u):
    await u.get_channels()


async def test_p_User_get_channel_video_series(u):
    await u.get_channel_videos_series(589023)


async def test_q_User_get_channel_video_season(u):
    await u.get_channel_videos_season(193515)


async def test_r_User_get_top_followers(u):
    await u.top_followers()


async def test_s_User_get_overview_stat(u):
    await u.get_overview_stat()


async def test_t_User_modify_relation(u):
    # 后面 test_r_set_subscribe_group 会用到
    await u.modify_relation(user.RelationType.SUBSCRIBE)
    await u.modify_relation(user.RelationType.UNSUBSCRIBE)
    await asyncio.sleep(0.5)


async def test_u_User_get_elec_user_monthly(u):
    await u.get_elec_user_monthly()


# async def test_u_create_subscribe_group(credential):
#     name = f"TEST{random.randint(100000, 999999)}"
#     result = await user.create_subscribe_group(name, credential)
#     subscribe_id = result["tagid"]
#     return result


# async def test_v_rename_subscribe_group(credential):
#     name = f"TEST{random.randint(100000, 999999)}"
#     result = await user.rename_subscribe_group(subscribe_id, name, credential)
#     return result


# async def test_w_set_subscribe_group(credential):
#     result = await user.set_subscribe_group([UID], [subscribe_id], credential)
#     return result


# async def test_x_delete_subscribe_group(credential):
#     result = await user.delete_subscribe_group(subscribe_id, credential)
#     return result
# FIXME: 关注分组API问题


async def test_y_get_self_info(credential):
    await user.get_self_info(credential)


async def test_z_get_self_history(credential):
    await user.get_self_history(page_num, per_page_item, credential)


async def test_z_get_self_history_new(credential):
    await user.get_self_history_new(credential)


# test_za_get_self_events 已移除：user.get_self_events 已从库中删除（上游接口下线）


async def test_zb_get_self_coins(credential):
    await user.get_self_coins(credential)


async def test_zc_get_toview_list(credential):
    await user.get_toview_list(credential)


async def test_zd_delete_viewed_video_in_toview_list(credential):
    await user.delete_viewed_videos_from_toview(credential)


async def test_ze_clean_toview_list(credential):
    await user.clear_toview_list(credential)


# async def test_zf_get_space_notice(u):
#     await u.get_space_notice()
# FIXME: 重试达到最大次数


async def test_zg_get_album(u):
    await u.get_album()


async def test_zh_get_user_fav_tag():
    try:
        await user.User(UID4).get_user_fav_tag()
    except ResponseCodeException as e:
        if e.code != 53013:
            # 用户隐私未公开
            raise e


async def test_zi_get_user_medal(u):
    await u.get_user_medal()


async def test_zj_get_user_top_videos(u):
    try:
        await u.get_top_videos()
    except ResponseCodeException as e:
        if e.code != 53016:
            # 没有置顶视频
            raise e


async def test_zk_get_reservation(u):
    await u.get_reservation()


async def test_zl_name2uid(credential):
    await user.name2uid("田所こうじ", credential=credential)


# series_id = None

# async def test_zm_create_channel_series(credential):
#     global series_id
#     data = await user.create_channel_series(name="什么都没有", credential=credential)
#     series_id = data["series_id"]
#     return data


# async def test_zo_add_video_to_channal_series(credential):
#     return await user.add_aids_to_series(series_id=series_id, aids=[bvid2aid("BV1fG4y1g7wE")], credential=credential)


# async def test_zp_del_video_from_channel_series(credential):
#     return await user.del_aids_from_series(series_id=series_id, aids=[bvid2aid("BV1fG4y1g7wE")], credential=credential)


# async def test_zq_del_channel_series(credential):
#     return await user.del_channel_series(series_id=series_id, credential=credential)
# 迁移至test_channel_series


async def test_zr_get_self_same_followings(u):
    await u.get_self_same_followers()


async def test_zs_get_self_black_list(credential):
    await user.get_self_black_list(credential)


async def test_zt_get_self_friends(credential):
    await user.get_self_friends(credential)


async def test_zu_get_self_whisper_followings(credential):
    await user.get_self_whisper_followings(credential)


async def test_zv_get_self_special_followings(credential):
    await user.get_self_special_followings(credential)


async def test_zw_get_self_jury_info(credential):
    await user.get_self_jury_info(credential)


async def test_zx_get_relation(u):
    await u.get_relation()


async def test_zy_get_masterpiece(u):
    await u.get_masterpiece()


async def test_zz_get_login_log(credential):
    await user.get_self_login_log(credential)


async def test_zza_get_moral_log(credential):
    await user.get_self_moral_log(credential)


async def test_zzb_get_exp_log(credential):
    await user.get_self_experience_log(credential)
