# bilibili_api.video_zone

from bilibili_api import video_zone


def test_a_get_zone_info_by_tid():
    video_zone.get_zone_info_by_tid(0)


def test_b_get_zone_info_by_name():
    video_zone.get_zone_info_by_name("鬼畜")


async def test_c_get_zone_top10():
    await video_zone.get_zone_top10(tid=3)


async def test_d_get_zone_new_videos():
    await video_zone.get_zone_new_videos(tid=3)


async def test_e_get_zone_new_videos_count():
    await video_zone.get_zone_videos_count_today()


def test_f_get_zone_list():
    video_zone.get_zone_list()


def test_g_get_zone_list_sub():
    video_zone.get_zone_list_sub()


async def test_g_get_zone_hot_tags():
    await video_zone.get_zone_hot_tags(tid=33)
