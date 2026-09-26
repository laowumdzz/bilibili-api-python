# bilibili_api.creative_center

import pytest

from bilibili_api import creative_center
from bilibili_api.exceptions import NetworkException, ResponseCodeException

# 创作中心全量接口需 UP 主身份（身份特定类，FR-007 / data-model 安全策略表），整文件标 cred3
pytestmark = pytest.mark.cred3


async def test_a_get_compare(credential):
    await creative_center.get_compare(credential)


async def test_b_get_graph(credential):
    await creative_center.get_graph(credential)


async def test_c_get_overview(credential):
    await creative_center.get_overview(credential)


async def test_d_get_video_survey(credential):
    await creative_center.get_video_survey(credential)


async def test_e_get_video_playanalysis(credential):
    await creative_center.get_video_playanalysis(credential)


async def test_f_get_video_source(credential):
    await creative_center.get_video_source(credential)


async def test_g_get_fan_overview(credential):
    await creative_center.get_fan_overview(credential)


async def test_h_get_fan_graph(credential):
    await creative_center.get_fan_graph(credential)


async def test_i_get_article_overview(credential):
    await creative_center.get_article_overview(credential)


async def test_j_get_article_graph(credential):
    await creative_center.get_article_graph(credential)


async def test_k_get_article_source(credential):
    try:
        await creative_center.get_article_source(credential)
    except NetworkException:
        # 上游 member.bilibili.com 文章数据来源接口已下线（返回 404 页面，非本库 bug）
        pass


async def test_l_get_article_rank(credential):
    await creative_center.get_article_rank(credential)


async def test_m_get_video_draft_upload_manager_info(credential):
    # 与原 test_n 逐字重复（T058），合并为单用例（宪法 IV 分层测试质量）
    await creative_center.get_video_draft_upload_manager_info(credential)


async def test_o_get_article_upload_manager_info(credential):
    await creative_center.get_article_upload_manager_info(credential)


async def test_p_get_article_list_upload_manager_info(credential):
    await creative_center.get_article_list_upload_manager_info(credential)


async def test_r_get_comments(credential):
    await creative_center.get_comments(credential)


async def test_s_get_recently_danmakus(credential):
    await creative_center.get_recently_danmakus(credential)


async def test_t_get_danmakus(credential):
    try:
        await creative_center.get_danmakus(credential, oid=914350440)  # BV1fG4y1g7wE 好像是测试号的视频？
    except ResponseCodeException as e:
        # -403：oid 对应视频不属于当前测试账号，无访问权限（测试数据属于原开发者账号）
        if e.code != -403:
            raise e
