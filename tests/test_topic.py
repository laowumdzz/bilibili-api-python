# bilibili_api.topic

import pytest

from bilibili_api import topic
from bilibili_api.exceptions.ResponseCodeException import ResponseCodeException


@pytest.fixture(scope="module")
def t(credential) -> topic.Topic:
    return topic.Topic(66571, credential)


async def test_a_Topic_get_info(t):
    await t.get_info()


async def test_b_Topic_get_cards(t):
    await t.get_cards(sort_by=topic.TopicCardsSortBy.NEW)


async def test_c_Topic_like(t):
    try:
        await t.like(status=False)
        await t.like(status=True)
    except ResponseCodeException as e:
        if e.code not in (65004,):
            raise e


async def test_d_Topic_set_favorite(t):
    await t.set_favorite(status=False)
    await t.set_favorite(status=True)


async def test_e_get_hot_topics():
    await topic.get_hot_topics()


async def test_f_search_topic():
    await topic.search_topic("bilibili-api")
