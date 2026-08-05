# bilibili_api.hot

from bilibili_api import hot
from bilibili_api.exceptions.ResponseCodeException import ResponseCodeException


async def test_b_get_hot_video():
    await hot.get_hot_videos()


async def test_c_get_85_popular_video():
    await hot.get_history_popular_videos()


async def test_d_get_weekly_hot_video_list():
    await hot.get_weekly_hot_videos_list()


async def test_e_get_weekly_hot_video_content():
    try:
        await hot.get_weekly_hot_videos(161)
    except ResponseCodeException as e:
        # 历史周榜数据可能已下线（上游接口数据变动，非本库 bug）
        if e.code != -404:
            raise e


async def test_f_get_hot_buzzwords():
    await hot.get_hot_buzzwords()
