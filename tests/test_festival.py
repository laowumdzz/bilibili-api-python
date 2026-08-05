# bilibili_api.festival

from bilibili_api import festival

fes = festival.Festival("genshin2023")


async def test_a_Festival_get_info():
    await fes.get_info()
