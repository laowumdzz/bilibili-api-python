# bilibili_api.video

import asyncio
import datetime
import time

import pytest

from bilibili_api import exceptions, favorite_list
from bilibili_api import video as video_m
from bilibili_api.exceptions.ResponseCodeException import ResponseCodeException
from bilibili_api.utils.danmaku import Danmaku

BVID = "BV1N34y1Y7ds"
AID = 811248323


@pytest.fixture(scope="module")
def video(credential) -> video_m.Video:
    return video_m.Video(aid=AID, credential=credential)


async def test_a_Video_set_bvid(video):
    # 设置正确 bvid
    video.set_bvid(BVID)
    assert video.get_bvid() == BVID, "bvid 应该被修改"
    assert video.get_aid() == AID, "aid 应该从 bvid 转换"

    # 设置错误 bvid
    with pytest.raises(exceptions.ArgsException):
        video.set_bvid("BVajsdoiajinsodn")
    video.set_bvid(BVID)


async def test_b_Video_set_aid(video):
    # 设置正确 aid
    video.set_aid(AID)
    assert video.get_aid() == AID, "aid 应该被修改"
    assert video.get_bvid() == BVID, "bvid 应该从 aid 转换"

    # 设置错误 aid
    with pytest.raises(exceptions.ArgsException):
        video.set_aid(-1)
    video.set_aid(AID)


@pytest.mark.cred0
async def test_c_Video_get_info(video):
    await video.get_info()


# async def test_d_Video_get_stat(video):
#     await video.get_stat()


@pytest.mark.cred0
async def test_e_Video_get_tags(video):
    await video.get_tags()


async def test_f_Video_get_download_url(video):
    try:
        await video.get_download_url(0)
    except ResponseCodeException as e:
        if e.code != -404:
            raise e


async def test_g_Video_get_chargers(video):
    await video.get_chargers()


@pytest.mark.cred0
async def test_h_Video_get_pages(video):
    await video.get_pages()


async def test_i_Video_get_related(video):
    await video.get_related()


async def test_j_Video_has_liked(video):
    await video.has_liked()


async def test_k_Video_get_pay_coins(video):
    await video.get_pay_coins()


async def test_l_Video_has_favoured(video):
    await video.has_favoured()


async def test_n_Video_get_danmaku_view(video):
    await video.get_danmaku_view(0)


async def test_o_Video_get_danmaku(video):
    await video.get_danmakus(0)


async def test_p_Video_get_danmaku_history(video):
    await video.get_danmakus(0, date=datetime.date(2023, 1, 1))


async def test_q_Video_get_danmaku_xml(video):
    await video.get_danmaku_xml(0)


async def test_r_Video_get_danmaku_snapshot(video):
    await video.get_danmaku_snapshot()


async def test_s_Video_get_pbp(video):
    await video.get_pbp(0)


async def test_t_Video_get_history_danmaku_index(video):
    await video.get_history_danmaku_index(0, datetime.date(2022, 9, 1))


async def test_u_Video_send_danmaku(video):
    dm = Danmaku("TESTING" + str(int(time.time())))
    await video.send_danmaku(0, dm)


async def test_v_Video_like(video):
    try:
        await video.like(True)

        # Clean up
        await video.like(False)
    except ResponseCodeException as e:
        # 忽略已点赞和未点赞
        if e.code not in (65004, 65006):
            raise e


async def test_w_Video_pay_coin(video):
    try:
        await video.pay_coin(2)
    except ResponseCodeException as e:
        # 不接受以下错误 code
        # -104 硬币不足
        # 34005 视频投币上限
        if e.code not in (-104, 34005):
            raise e


# async def test_x_Video_add_tag(video):
#    try:
#        await video.add_tag("测试标签")
#    except ResponseCodeException as e:
#        # 16070  只有 UP 才能添加
#        if e.code != 16070:
#            raise e


# async def test_y_Video_del_tag(video):
#     try:
#         await video.delete_tag(99999999)
#     except ResponseCodeException as e:
#         # 16070  只有 UP 才能添加
#         if e.code != 16070:
#             raise e


# async def test_z_Video_subscribe_and_unsubscribe_tag(video):
#     await video.subscribe_tag(8583026)
#     await video.unsubscribe_tag(8583026)


async def test_za_Video_set_favorite(video, credential):
    # 使用本账号自己的收藏夹，避免依赖其他账号的硬编码收藏夹 id
    fav_list = await favorite_list.get_video_favorite_list(int(credential.dedeuserid), credential=credential)
    media_id = fav_list["list"][0]["id"]
    await video.set_favorite([media_id])
    await asyncio.sleep(0.5)
    await video.set_favorite(del_media_ids=[media_id])


async def test_zb_Video_add_to_toview(video):
    await video.add_to_toview()


async def test_zc_Video_delete_from_toview(video):
    await video.delete_from_toview()


async def test_zd_video_snapshot(video):
    await video.get_video_snapshot(pvideo=False)


async def test_zf_get_subtitle(credential):
    videos = video_m.Video(aid=288571926, credential=credential)
    await videos.get_subtitle(cid=281031471)


async def test_zg_triple(video):
    await video.triple()


async def test_zh_get_cid_info():
    await video_m.get_cid_info(62131)


async def test_zi_get_ai_conclusion(video):
    await video.get_ai_conclusion(0)


async def test_zj_get_relation(video):
    await video.get_relation()


async def test_zk_get_online(video):
    await video.get_online()


async def test_zl_report_watch_history(video):
    await video.report_watch_history()


async def test_zm_report_start_watching(video):
    await video.report_start_watching()
