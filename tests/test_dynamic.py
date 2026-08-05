# bilibili_api.dynamic

import pytest

from bilibili_api import ResponseCodeException, dynamic


@pytest.fixture(scope="module")
def dy(credential) -> dynamic.Dynamic:
    return dynamic.Dynamic(959229822831165446, credential=credential)


# async def test_a_send_dynamic(credential):
#     # 测试发送动态
#     print("测试立即发送纯文本动态")
#     text_dynamic_build = (
#         dynamic.BuildDynamic()
#         .add_text("测试立即发送纯文本动态")
#         .add_image(
#             Picture.from_file("./design/logo.png").upload_file_sync(
#                 credential=credential
#             )
#         )
#     )
#     dy = dynamic.Dynamic(
#         (await dynamic.send_dynamic(text_dynamic_build, credential=credential))[
#             "dyn_id"
#         ],
#         credential=credential,
#     )
#     print(dy.get_dynamic_id())
# 见L61


async def test_b_get_schedules_list(credential):
    await dynamic.get_schedules_list(credential=credential)


async def test_e_Dynamic_get_info(dy):
    await dy.get_info()


async def test_f_Dynamic_get_reposts(dy):
    await dy.get_reposts()


async def test_g_Dynamic_set_like(dy):
    try:
        await dy.set_like()
    except ResponseCodeException as e:
        if e.code != 65006:
            raise


# async def test_i_Dynamic_delete(dy):
#     await dy.delete()
# FIXME: 不知道为什么每一次自动删除都会出问题。单独跑一遍删除不会出问题。
# 暂时停止动态发送、删除相关操作


async def test_j_get_new_dynamic_users(credential):
    await dynamic.get_new_dynamic_users(credential)


async def test_k_get_live_users(credential):
    await dynamic.get_live_users(credential=credential)


async def test_l_get_dynamic_page_UPs_info(credential):
    await dynamic.get_dynamic_page_UPs_info(credential=credential)


async def test_m_get_dynamic_page_info_by_type(credential):
    await dynamic.get_dynamic_page_info(credential=credential, _type=dynamic.DynamicType.ALL)


async def test_n_get_dynamic_page_info_by_mid(credential):
    await dynamic.get_dynamic_page_info(credential=credential, host_mid=12434430)


async def test_p_get_reaction(dy):
    await dy.get_reaction()


async def test_q_get_lottery_info(dy):
    await dy.get_lottery_info()
