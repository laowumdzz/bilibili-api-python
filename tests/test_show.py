# bilibili_api.show

from bilibili_api import show

PROJECT_ID = 75650


async def test_a_get_all_buyer_info(credential):
    await show.get_all_buyer_info(credential)


async def test_b_get_available_sessions():
    await show.get_available_sessions(PROJECT_ID)
