# bilibili_api.vote

import pytest

from bilibili_api import vote
from bilibili_api.exceptions import NetworkException

FALLBACK_VOTE_ID = 5322590


@pytest.mark.cred1
async def test_a_get_vote_info():
    await vote.Vote(vote_id=FALLBACK_VOTE_ID).get_info()


@pytest.mark.cred3
async def test_b_vote_create_and_update(credential):
    """投票创建与更新合并单用例（cred3 公开发布类：无删除 API，消除 vote_id 全局依赖）。

    上游投票创建接口已下线（返回 404 页面，非本库 bug）；创建失败时以既有
    公开投票 ID 回退执行更新链路，保持接口调用覆盖。
    """
    vote_id = FALLBACK_VOTE_ID
    try:
        cr_vote = await vote.create_vote(
            title="测试投票",
            _type=vote.VoteType.TEXT,
            choice_cnt=2,
            duration=259200,
            choices=vote.VoteChoices().add_choice("选项1").add_choice("选项2"),
            credential=credential,
            desc="测试投票",
        )
        vote_id = cr_vote.get_vote_id()
    except NetworkException:
        # 上游投票创建接口已下线（返回 404 页面，非本库 bug）
        pass

    await vote.Vote(vote_id=vote_id, credential=credential).update_vote(
        title="测试投票2",
        _type=vote.VoteType.TEXT,
        choice_cnt=2,
        duration=259200,
        choices=vote.VoteChoices().add_choice("选项1C").add_choice("选项2c"),
        desc="测试投票2",
    )
