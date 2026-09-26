# bilibili_api.session

import pytest

from bilibili_api import ResponseCodeException, session


@pytest.mark.cred1
async def test_a_fetch_session_msgs(credential):
    await session.fetch_session_msgs(12076317, credential)


@pytest.mark.cred1
async def test_b_get_sessions(credential):
    await session.get_sessions(credential)


@pytest.mark.cred1
async def test_c_get_new_sessions(credential):
    await session.new_sessions(credential)


@pytest.mark.cred3
async def test_d_send_msg(credential):
    try:
        await session.send_msg(credential, 1666311555, session.EventType.TEXT, "THIS IS A TEST MSG. ")
        # 660303135 表示有意见[doge]
    except ResponseCodeException as e:
        # 21026：频率限制；21047：陌生人消息条数限制（账号关系状态问题，非本库 bug）
        if e.code not in (21026, 21047):
            raise e


@pytest.mark.cred1
async def test_e_get_likes(credential):
    await session.get_likes(credential)


@pytest.mark.cred1
async def test_f_get_replies(credential):
    await session.get_replies(credential)


@pytest.mark.cred1
async def test_g_get_system_messages(credential):
    await session.get_system_messages(credential)


@pytest.mark.cred1
async def test_h_get_unread_messages(credential):
    await session.get_unread_messages(credential)


@pytest.mark.cred1
async def test_i_get_session_configs(credential):
    await session.get_session_settings(credential)


@pytest.mark.cred1
async def test_j_get_session_detail(credential):
    await session.get_session_detail(credential, 12076317, 1)
