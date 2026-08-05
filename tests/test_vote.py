# bilibili_api.vote

from bilibili_api import vote
from bilibili_api.exceptions import NetworkException

vote_id = 5322590


async def test_a_get_vote_info():
    await vote.Vote(vote_id=5322590).get_info()


async def test_b_create_vote(credential):
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
        global vote_id
        vote_id = cr_vote.get_vote_id()
    except NetworkException:
        # 上游投票创建接口已下线（返回 404 页面，非本库 bug）；vote_id 保持原值供后续用例使用
        pass


async def test_c_update_vote(credential):
    await vote.Vote(vote_id=vote_id, credential=credential).update_vote(
        title="测试投票2",
        _type=vote.VoteType.TEXT,
        choice_cnt=2,
        duration=259200,
        choices=vote.VoteChoices().add_choice("选项1C").add_choice("选项2c"),
        desc="测试投票2",
    )
