# bilibili_api.favorite_list

import random

from bilibili_api import bvid2aid, favorite_list, video

media_id = None
aids = [bvid2aid("BV1yQ4y117m3"), 975842744]
uid = 1666311555
default_media_id = 1626035955


async def test_a_get_video_favorite_list(credential):
    await favorite_list.get_video_favorite_list(uid, credential=credential)


async def test_b_get_video_favorite_list_content(credential):
    await favorite_list.get_video_favorite_list_content(1195349595, credential=credential)


async def test_c_get_topic_favorite_list(credential):
    await favorite_list.get_topic_favorite_list(credential=credential)


async def test_d_get_article_favorite_list(credential):
    await favorite_list.get_article_favorite_list(credential=credential)


# async def test_e_get_album_favorite_list(credential):
#     await favorite_list.get_album_favorite_list(credential=credential)


async def test_f_get_course_favorite_list(credential):
    await favorite_list.get_course_favorite_list(credential=credential)


async def test_g_get_note_favorite_list(credential):
    await favorite_list.get_note_favorite_list(credential=credential)


async def test_h_create_video_favorite_list(credential):
    # 创建两个临时收藏夹（源与目标），使后续复制/移动/删除链路自包含于本账号
    rnd_name = random.randint(100000, 999999)
    data = await favorite_list.create_video_favorite_list(f"TESTING_{rnd_name}", "", False, credential=credential)
    global media_id
    media_id = data["id"]
    data_dst = await favorite_list.create_video_favorite_list(
        f"TESTING_DST_{rnd_name}", "", False, credential=credential
    )
    global default_media_id
    default_media_id = data_dst["id"]

    # 收藏两个视频到源收藏夹，供后续复制/移动测试使用
    for aid in aids:
        v = video.Video(aid=aid, credential=credential)
        await v.set_favorite([media_id])


# async def test_o_favorite_list_info():
#     await favorite_list.FavoriteList(media_id=media_id).get_info()


# async def test_p_favorite_list_content_ids():
#     await favorite_list.FavoriteList(media_id=media_id).get_content_ids_info()
# FIXME: Github上运行失败


async def test_i_modify_video_favorite_list(credential):
    rnd_name = random.randint(100000, 999999)
    await favorite_list.modify_video_favorite_list(media_id, f"TESTING_{rnd_name}", credential=credential)


async def test_j_copy_video_favorite_list_content(credential):
    await favorite_list.copy_video_favorite_list_content(media_id, default_media_id, [aids[0]], credential=credential)


async def test_k_move_video_favorite_list_content(credential):
    await favorite_list.move_video_favorite_list_content(media_id, default_media_id, [aids[1]], credential=credential)


async def test_l_clean_video_favorite_list_content(credential):
    await favorite_list.clean_video_favorite_list_content(media_id, credential)


async def test_m_delete_video_favorite_list_content(credential):
    await favorite_list.delete_video_favorite_list_content(default_media_id, [aids[0]], credential=credential)


async def test_n_delete_video_favorite_list(credential):
    # 同时删除源与目标两个临时收藏夹，完成清理
    await favorite_list.delete_video_favorite_list([media_id, default_media_id], credential)


async def test_get_favorite_collected_1(credential):
    await favorite_list.get_favorite_collected(uid, credential=credential)


async def test_get_favorite_collected_2(credential):
    await favorite_list.get_favorite_collected(uid, 1, 20, credential)
