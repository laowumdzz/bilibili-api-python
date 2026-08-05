# bilibili_api.homepage

from bilibili_api import homepage


async def test_a_get_top_photo():
    await homepage.get_top_photo()


async def test_b_get_links(credential):
    await homepage.get_links(credential)


async def test_c_get_popularize(credential):
    await homepage.get_popularize(credential)


async def test_d_get_videos(credential):
    await homepage.get_popularize(credential)
