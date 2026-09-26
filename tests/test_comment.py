# bilibili_api.comment

import asyncio
import random

import pytest

from bilibili_api import comment, user

AID = 271


@pytest.mark.cred1
async def test_a_get_comments():
    await comment.get_comments(oid=AID, type_=comment.CommentResourceType.VIDEO)


@pytest.mark.cred2
async def test_b_comment_lifecycle(credential, teardown_retry):
    """评论完整生命周期：发送 → 回复 → 点赞 → 点踩 → 子评论读 → 删除（自清理，cred2）。

    发布目标动态解析为账号自有视频（FR-008 公开发布类改道，research R5：
    get_self_info 取 mid → User(mid).get_videos() 取首个 aid，不硬编码），
    不在任何第三方内容上公开发布测试评论；无自有视频时条件跳过。
    """
    self_info = await user.get_self_info(credential)
    mid = int(self_info["mid"])
    own = await user.User(mid, credential=credential).get_videos()
    vlist = own["list"]["vlist"]
    if not vlist:
        pytest.skip("账号当前无自有视频，评论生命周期无自有发布目标，条件跳过（FR-008）")
    oid = int(vlist[0]["aid"])

    result = await comment.send_comment(
        "测试" + str(random.random()),
        oid=oid,
        type_=comment.CommentResourceType.VIDEO,
        credential=credential,
    )
    rpid = result["rpid"]
    reply_rpid: int | None = None
    try:
        # 根评论建立到可被回复存在服务端索引延迟，等待后再回复（12006 没有该评论防护）
        await asyncio.sleep(1)
        reply = await comment.send_comment(
            "测试回复评论" + str(random.random()),
            oid=oid,
            type_=comment.CommentResourceType.VIDEO,
            root=rpid,
            credential=credential,
        )
        reply_rpid = reply["rpid"]
        await asyncio.sleep(1)
        cmt = comment.Comment(
            oid=oid,
            type_=comment.CommentResourceType.VIDEO,
            rpid=rpid,
            credential=credential,
        )
        await cmt.like()
        await cmt.hate()
        # 子评论读取（原 test_f_get_sub_comments 并入生命周期）
        await cmt.get_sub_comments()
    finally:
        # teardown 级清理义务（FR-006）：先删回复，再删根评论，失败重试后告警
        if reply_rpid is not None:
            reply_cmt = comment.Comment(
                oid=oid,
                type_=comment.CommentResourceType.VIDEO,
                rpid=reply_rpid,
                credential=credential,
            )
            await teardown_retry(f"评论回复 rpid={reply_rpid}（oid={oid}）", reply_cmt.delete)
        root_cmt = comment.Comment(
            oid=oid,
            type_=comment.CommentResourceType.VIDEO,
            rpid=rpid,
            credential=credential,
        )
        await teardown_retry(f"根评论 rpid={rpid}（oid={oid}）", root_cmt.delete)


# 举报评论不测试
