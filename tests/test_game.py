# bilibili_api.game

from bilibili_api import game
from bilibili_api.exceptions.ResponseCodeException import ResponseCodeException

g = game.Game(105667)


async def test_a_Game_get_info():
    await g.get_info()


async def test_b_Game_get_up_info():
    await g.get_up_info()


async def test_c_Game_get_detail():
    await g.get_detail()


async def test_d_Game_get_wiki():
    try:
        await g.get_wiki()
    except ResponseCodeException as e:
        if e.code != -703:
            # 数据为空
            raise e


async def test_e_Game_get_videos():
    await g.get_videos()


# async def test_f_Game_get_score():
#     await g.get_score()
