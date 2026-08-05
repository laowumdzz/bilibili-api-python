# bilibili_api.app

from bilibili_api import app


async def test_a_get_loading_images(credential):
    await app.get_loading_images(credential=credential)


async def test_b_get_loading_images_special(credential):
    await app.get_loading_images_special(credential=credential)
