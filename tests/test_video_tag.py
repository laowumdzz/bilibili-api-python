# bilibili_api.video_tag

import pytest

from bilibili_api import video_tag


@pytest.fixture(scope="module")
def tag(credential) -> video_tag.Tag:
    return video_tag.Tag(tag_name="真白花音", credential=credential)


@pytest.mark.cred1
async def test_a_get_tag_info(tag):
    await tag.get_tag_info()


@pytest.mark.cred1
async def test_b_get_similar_tags(tag):
    await tag.get_similar_tags()


# async def test_c_get_cards(tag):
#     await tag.get_cards()


@pytest.mark.cred2
async def test_d_subscribe_tag(tag, teardown_retry):
    # 可逆写配对单用例：订阅后立即取消订阅（FR-006 配对恢复，FR-009 顺序无关）；
    # 取消订阅为 teardown 级清理义务（finally + teardown_retry，失败明确残留警告）
    changed = False
    try:
        await tag.subscribe_tag()
        changed = True
    finally:
        if changed:
            await teardown_retry("标签订阅残留（tag_name=真白花音）", tag.unsubscribe_tag)
