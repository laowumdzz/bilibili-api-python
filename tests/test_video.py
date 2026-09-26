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


@pytest.mark.cred1
async def test_a_Video_set_bvid(video):
    # 设置正确 bvid
    video.set_bvid(BVID)
    assert video.get_bvid() == BVID, "bvid 应该被修改"
    assert video.get_aid() == AID, "aid 应该从 bvid 转换"

    # 设置错误 bvid
    with pytest.raises(exceptions.ArgsException):
        video.set_bvid("BVajsdoiajinsodn")
    video.set_bvid(BVID)


@pytest.mark.cred1
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


@pytest.mark.cred1
async def test_f_Video_get_download_url(video):
    try:
        await video.get_download_url(0)
    except ResponseCodeException as e:
        if e.code != -404:
            raise e


@pytest.mark.cred1
async def test_g_Video_get_chargers(video):
    await video.get_chargers()


@pytest.mark.cred0
async def test_h_Video_get_pages(video):
    await video.get_pages()


@pytest.mark.cred1
async def test_i_Video_get_related(video):
    await video.get_related()


@pytest.mark.cred1
async def test_j_Video_has_liked(video):
    await video.has_liked()


@pytest.mark.cred1
async def test_k_Video_get_pay_coins(video):
    await video.get_pay_coins()


@pytest.mark.cred1
async def test_l_Video_has_favoured(video):
    await video.has_favoured()


@pytest.mark.cred1
async def test_n_Video_get_danmaku_view(video):
    await video.get_danmaku_view(0)


@pytest.mark.cred1
async def test_o_Video_get_danmaku(video):
    await video.get_danmakus(0)


@pytest.mark.cred1
async def test_p_Video_get_danmaku_history(video):
    await video.get_danmakus(0, date=datetime.date(2023, 1, 1))


@pytest.mark.cred1
async def test_q_Video_get_danmaku_xml(video):
    await video.get_danmaku_xml(0)


@pytest.mark.cred1
async def test_r_Video_get_danmaku_snapshot(video):
    await video.get_danmaku_snapshot()


@pytest.mark.cred1
async def test_s_Video_get_pbp(video):
    try:
        await video.get_pbp(0)
    except exceptions.NetworkException as e:
        # 404：上游 bvc.bilivideo.com pbp 数据接口对部分 cid 已下线（非本库 bug）
        if e.status != 404:
            raise e


@pytest.mark.cred1
async def test_t_Video_get_history_danmaku_index(video):
    await video.get_history_danmaku_index(0, datetime.date(2022, 9, 1))


@pytest.mark.cred3
async def test_u_Video_send_danmaku(video):
    dm = Danmaku("TESTING" + str(int(time.time())))
    await video.send_danmaku(0, dm)


@pytest.mark.cred2
async def test_v_Video_like(video):
    # 可逆写配对单用例：点赞后立即取消点赞（FR-006 配对恢复）
    try:
        await video.like(True)

        # Clean up
        await video.like(False)
    except ResponseCodeException as e:
        # 忽略已点赞和未点赞
        if e.code not in (65004, 65006):
            raise e


@pytest.mark.cred3
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


@pytest.mark.cred2
async def test_za_Video_set_favorite(video, credential):
    # 可逆写配对单用例：先探测初始收藏态，两个方向各完成一次收藏 / 取消收藏配对，
    # 结束态与初始态一致（FR-006 配对恢复；无条件移除会挤掉预存收藏）
    # 使用本账号自己的收藏夹，避免依赖其他账号的硬编码收藏夹 id
    fav_list = await favorite_list.get_video_favorite_list(int(credential.dedeuserid), credential=credential)
    media_id = fav_list["list"][0]["id"]
    was_favoured = await video.has_favoured()
    if was_favoured:
        # 初始已收藏：移除 → 断言生效 → 加回（恢复初始态）
        await video.set_favorite(del_media_ids=[media_id])
        assert not await video.has_favoured(), "移除收藏后 has_favoured 应为 False"
        await video.set_favorite([media_id])
        assert await video.has_favoured(), "加回收藏后 has_favoured 应为 True"
    else:
        # 初始未收藏：收藏 → 断言生效 → 移除（恢复初始态）
        await video.set_favorite([media_id])
        assert await video.has_favoured(), "收藏后 has_favoured 应为 True"
        await video.set_favorite(del_media_ids=[media_id])
        assert not await video.has_favoured(), "取消收藏后 has_favoured 应为 False"


@pytest.mark.cred2
async def test_zb_Video_toview_lifecycle(video):
    # 可逆写配对单用例：加入稍后再看后立即删除（FR-006 配对恢复）
    await video.add_to_toview()
    await video.delete_from_toview()


@pytest.mark.cred1
async def test_zd_video_snapshot(video):
    await video.get_video_snapshot(pvideo=False)


@pytest.mark.cred1
async def test_zf_get_subtitle(credential):
    videos = video_m.Video(aid=288571926, credential=credential)
    await videos.get_subtitle(cid=281031471)


@pytest.mark.cred3
async def test_zg_triple(video):
    await video.triple()


@pytest.mark.cred1
async def test_zh_get_cid_info():
    try:
        await video_m.get_cid_info(62131)
    except exceptions.NetworkException as e:
        # 500：上游 hd.biliplus.com 第三方 cid 查询服务已失效（非本库 bug）
        if e.status != 500:
            raise e


@pytest.mark.cred1
async def test_zi_get_ai_conclusion(video):
    await video.get_ai_conclusion(0)


@pytest.mark.cred1
async def test_zj_get_relation(video):
    await video.get_relation()


@pytest.mark.cred1
async def test_zk_get_online(video):
    await video.get_online()


@pytest.mark.cred2
async def test_zl_report_watch_history(video):
    # 自身状态类白名单（data-model 安全策略表）：不可逆但仅自身可见（历史记录），
    # 不属于六态清单、无对外发布形态，成文归 cred2
    await video.report_watch_history()


@pytest.mark.cred2
async def test_zm_report_start_watching(video):
    # 自身状态类白名单（data-model 安全策略表）：不可逆但仅自身可见（观看上报），
    # 不属于六态清单、无对外发布形态，成文归 cred2
    await video.report_start_watching()
