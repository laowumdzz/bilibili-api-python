# bilibili_api.video_tag

import pytest

from bilibili_api import video_tag


@pytest.fixture(scope="module")
def tag(credential) -> video_tag.Tag:
    return video_tag.Tag(tag_name="真白花音", credential=credential)


async def test_a_get_tag_info(tag):
    await tag.get_tag_info()


async def test_b_get_similar_tags(tag):
    await tag.get_similar_tags()


# async def test_c_get_cards(tag):
#     await tag.get_cards()


async def test_d_subscribe_tag(tag):
    await tag.subscribe_tag()


async def test_e_unsubscribe_tag(tag):
    await tag.unsubscribe_tag()
