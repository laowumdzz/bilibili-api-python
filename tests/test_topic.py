# bilibili_api.topic

import pytest

from bilibili_api import topic
from bilibili_api.exceptions.ResponseCodeException import ResponseCodeException


@pytest.fixture(scope="module")
def t(credential) -> topic.Topic:
    return topic.Topic(66571, credential)


@pytest.mark.cred1
async def test_a_Topic_get_info(t):
    await t.get_info()


@pytest.mark.cred1
async def test_b_Topic_get_cards(t):
    await t.get_cards(sort_by=topic.TopicCardsSortBy.NEW)


@pytest.mark.cred2
async def test_c_Topic_like(t):
    # 可逆写配对单用例：点赞后取消点赞，结束态为未点赞（FR-006 配对恢复）
    try:
        await t.like(status=True)
        await t.like(status=False)
    except ResponseCodeException as e:
        # 65004：重复点赞；65006：取消未点赞（幂等目标态，容忍）
        if e.code not in (65004, 65006):
            raise e


@pytest.mark.cred2
async def test_d_Topic_set_favorite(t):
    # 可逆写配对单用例：收藏后取消收藏，结束态为未收藏（FR-006 配对恢复）
    await t.set_favorite(status=True)
    await t.set_favorite(status=False)


@pytest.mark.cred1
async def test_e_get_hot_topics():
    await topic.get_hot_topics()


@pytest.mark.cred1
async def test_f_search_topic():
    await topic.search_topic("bilibili-api")
