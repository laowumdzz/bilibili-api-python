# bilibili_api.vote

from bilibili_api import vote

vote_id = 5322590


async def test_a_get_vote_info():
    await vote.Vote(vote_id=5322590).get_info()


async def test_b_create_vote(credential):
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


async def test_c_update_vote(credential):
    await vote.Vote(vote_id=vote_id, credential=credential).update_vote(
        title="测试投票2",
        _type=vote.VoteType.TEXT,
        choice_cnt=2,
        duration=259200,
        choices=vote.VoteChoices().add_choice("选项1C").add_choice("选项2c"),
        desc="测试投票2",
    )
