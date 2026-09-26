# bilibili_api.favorite_list

import random

import pytest

from bilibili_api import bvid2aid, favorite_list, video

UID = 1666311555
AIDS = [bvid2aid("BV1yQ4y117m3"), 975842744]


@pytest.mark.cred1
async def test_a_get_video_favorite_list(credential):
    await favorite_list.get_video_favorite_list(UID, credential=credential)


@pytest.mark.cred1
async def test_b_get_video_favorite_list_content(credential):
    await favorite_list.get_video_favorite_list_content(1195349595, credential=credential)


@pytest.mark.cred1
async def test_c_get_topic_favorite_list(credential):
    await favorite_list.get_topic_favorite_list(credential=credential)


@pytest.mark.cred1
async def test_d_get_article_favorite_list(credential):
    await favorite_list.get_article_favorite_list(credential=credential)


# async def test_e_get_album_favorite_list(credential):
#     await favorite_list.get_album_favorite_list(credential=credential)


@pytest.mark.cred1
async def test_f_get_course_favorite_list(credential):
    await favorite_list.get_course_favorite_list(credential=credential)


@pytest.mark.cred1
async def test_g_get_note_favorite_list(credential):
    await favorite_list.get_note_favorite_list(credential=credential)


# async def test_o_favorite_list_info():
#     await favorite_list.FavoriteList(media_id=media_id).get_info()


# async def test_p_favorite_list_content_ids():
#     await favorite_list.FavoriteList(media_id=media_id).get_content_ids_info()
# FIXME: Github上运行失败


@pytest.mark.cred1
async def test_get_favorite_collected_1(credential):
    await favorite_list.get_favorite_collected(UID, credential=credential)


@pytest.mark.cred1
async def test_get_favorite_collected_2(credential):
    await favorite_list.get_favorite_collected(UID, 1, 20, credential)


@pytest.mark.cred2
async def test_h_favorite_list_lifecycle(credential, teardown_retry):
    """收藏夹完整生命周期：创建 → 收藏视频 → 改名 → 复制 → 移动 → 清空 → 删除内容 → 删除（自清理，cred2）。

    原链路依赖 media_id / default_media_id 跨用例全局变量，合并为单用例后顺序无关（FR-009，
    research R4）；临时收藏夹在 finally 中删除（teardown 级清理义务，FR-006），删除收藏夹
    会连带移除其中的测试收藏条目，恢复账号收藏状态。
    """
    rnd = random.randint(100000, 999999)
    src = await favorite_list.create_video_favorite_list(f"TESTING_{rnd}", "", False, credential=credential)
    src_id = src["id"]
    dst_id: int | None = None
    try:
        dst = await favorite_list.create_video_favorite_list(f"TESTING_DST_{rnd}", "", False, credential=credential)
        dst_id = dst["id"]

        # 收藏两个视频到源收藏夹
        for aid in AIDS:
            v = video.Video(aid=aid, credential=credential)
            await v.set_favorite([src_id])

        # 改名
        rnd_name = random.randint(100000, 999999)
        await favorite_list.modify_video_favorite_list(src_id, f"TESTING_{rnd_name}", credential=credential)

        # 复制 / 移动到目标收藏夹
        await favorite_list.copy_video_favorite_list_content(src_id, dst_id, [AIDS[0]], credential=credential)
        await favorite_list.move_video_favorite_list_content(src_id, dst_id, [AIDS[1]], credential=credential)

        # 清空源收藏夹
        await favorite_list.clean_video_favorite_list_content(src_id, credential)

        # 从目标收藏夹删除单条内容
        await favorite_list.delete_video_favorite_list_content(dst_id, [AIDS[0]], credential=credential)
    finally:
        # teardown 级清理义务（FR-006）：删除两个临时收藏夹，失败重试后告警
        for fid in (src_id, dst_id):
            if fid is None:
                continue
            await teardown_retry(
                f"临时收藏夹 {fid}",
                lambda fid=fid: favorite_list.delete_video_favorite_list([fid], credential),
            )
