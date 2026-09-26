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
async def test_c_Topic_like(t, teardown_retry):
    # 可逆写配对单用例：点赞后取消点赞，结束态为未点赞（FR-006 配对恢复）；取消点赞为
    # teardown 级清理义务（finally + teardown_retry，失败明确残留警告）
    changed = False
    try:
        try:
            await t.like(status=True)
        except ResponseCodeException as e:
            # 65004：初始已点赞，状态未变，无需恢复
            if e.code != 65004:
                raise e
        else:
            changed = True
    finally:
        if changed:
            await teardown_retry("话题点赞残留（topic_id=66571）", lambda: t.like(status=False))


@pytest.mark.cred2
async def test_d_Topic_set_favorite(t, teardown_retry):
    # 可逆写配对单用例：收藏后取消收藏，结束态为未收藏（FR-006 配对恢复）；取消收藏为
    # teardown 级清理义务（finally + teardown_retry，失败明确残留警告）
    changed = False
    try:
        await t.set_favorite(status=True)
        changed = True
    finally:
        if changed:
            await teardown_retry("话题收藏残留（topic_id=66571）", lambda: t.set_favorite(status=False))


@pytest.mark.cred1
async def test_e_get_hot_topics():
    await topic.get_hot_topics()


@pytest.mark.cred1
async def test_f_search_topic():
    await topic.search_topic("bilibili-api")
