# bilibili_api.comment

import asyncio
import random

import pytest

from bilibili_api import comment

BVID = "BV1xx411c7Xg"
AID = 271

comment_id = None


@pytest.mark.cred1
async def test_a_get_comments():
    await comment.get_comments(oid=AID, type_=comment.CommentResourceType.VIDEO)


async def test_b_send_comment(credential):
    global comment_id
    result = await comment.send_comment(
        "测试" + str(random.random()),
        oid=AID,
        type_=comment.CommentResourceType.VIDEO,
        credential=credential,
    )
    comment_id = result["rpid"]
    await asyncio.sleep(1)
    result = await comment.send_comment(
        "测试回复评论" + str(random.random()),
        oid=AID,
        type_=comment.CommentResourceType.VIDEO,
        root=comment_id,
        credential=credential,
    )
    rpid = result["rpid"]
    await asyncio.sleep(1)
    await comment.send_comment(
        "测试回复评论的评论" + str(random.random()),
        oid=AID,
        type_=comment.CommentResourceType.VIDEO,
        root=comment_id,
        parent=rpid,
        credential=credential,
    )
    await asyncio.sleep(1)


async def test_c_like_comment(credential):
    cmt = comment.Comment(
        oid=AID,
        type_=comment.CommentResourceType.VIDEO,
        rpid=comment_id,
        credential=credential,
    )
    await cmt.like()


async def test_d_hate_comment(credential):
    cmt = comment.Comment(
        oid=AID,
        type_=comment.CommentResourceType.VIDEO,
        rpid=comment_id,
        credential=credential,
    )
    await cmt.hate()


# async def test_e_pin_comment(credential):
#     cmt = comment.Comment(
#         oid=AID,
#         type_=comment.CommentResourceType.VIDEO,
#         rpid=comment_id,
#         credential=credential,
#     )
#     try:
#         await cmt.pin()
#     except ResponseCodeException as e:
#         # -403  权限不足
#         if e.code not in (-403,):
#             raise e
# FIXME: 重试次数达到上限


async def test_f_get_sub_comments(credential):
    cmt = comment.Comment(
        oid=AID,
        type_=comment.CommentResourceType.VIDEO,
        rpid=comment_id,
        credential=credential,
    )
    await cmt.get_sub_comments()


async def test_g_delete_comment(credential):
    cmt = comment.Comment(
        oid=AID,
        type_=comment.CommentResourceType.VIDEO,
        rpid=comment_id,
        credential=credential,
    )
    await cmt.delete()


# 举报评论不测试
