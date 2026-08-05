# bilibili_api.app

from bilibili_api import app
from bilibili_api.exceptions.ResponseCodeException import ResponseCodeException


async def test_a_get_loading_images(credential):
    await app.get_loading_images(credential=credential)


async def test_b_get_loading_images_special(credential):
    try:
        await app.get_loading_images_special(credential=credential)
    except ResponseCodeException as e:
        # -404：上游开屏特殊接口已下线（非本库 bug）
        if e.code != -404:
            raise e
