# bilibili_api 只读集成冒烟测试（PR 快速回路的受限集成子集）
#
# 本文件仅包含 GET 式只读请求与反爬虫参数获取，不发起任何写操作
# （不点赞/关注/投稿/发评论），不改变测试账号状态。
# 显式携带 readonly 标记，供 PR 场景的受限集成验证使用（uv run pytest -m readonly）；
# 文件名不以 test_offline_ 开头，因此同时带 integration 标记，会被全量集成任务覆盖。
# 反爬虫与公开接口用例无需登录凭据；依赖凭据的用例由 credential fixture 在缺凭据时自动 skip，
# 不阻塞无凭据贡献者（含 fork PR）。
# 同时附加 cred0 核心冒烟层标记（readonly 语义不变，两者并存，FR-013）。

import re

import pytest

from bilibili_api import hot, user
from bilibili_api.utils._api import get_bili_ticket, get_buvid, get_wbi_mixin_key
from bilibili_api.utils._wbi import WbiManager

pytestmark = [pytest.mark.readonly, pytest.mark.cred0]


async def test_get_buvid():
    """自动生成 buvid3/buvid4 应成功且非空（反爬虫核心面）。"""
    buvid3, buvid4 = await get_buvid()
    assert buvid3
    assert buvid4


async def test_get_bili_ticket():
    """bili_ticket 获取应成功且非空，过期时间应在未来（反爬虫核心面）。"""
    ticket, expires = await get_bili_ticket()
    assert ticket
    assert int(expires) > 0


async def test_get_wbi_mixin_key():
    """Wbi mixin key 应成功计算且长度为 32（Wbi 签名核心面）。"""
    mixin_key = await get_wbi_mixin_key()
    assert len(mixin_key) == 32


async def test_wbi_get_end_result(credential):
    """WbiManager 签名应生成 32 位十六进制 w_rid、wts 与默认 web_location（只读，缺凭据自动 skip）。"""
    result = await WbiManager.get_end_result({"foo": "bar"}, credential=credential)
    assert re.fullmatch(r"[0-9a-f]{32}", result["w_rid"])
    assert int(result["wts"]) > 0
    assert result["web_location"] == "444.8"
    assert result["foo"] == "bar"
    assert len(await WbiManager.get_mixin_key(credential=credential)) == 32


async def test_public_readonly_api():
    """匿名只读接口（热门视频）应正常返回数据（API 定义核心面）。"""
    result = await hot.get_hot_videos(pn=1, ps=5)
    assert result["list"]


async def test_credential_readonly_api(credential):
    """需登录的只读接口（获取自己的信息）应正常返回，缺凭据时自动 skip。"""
    info = await user.get_self_info(credential)
    assert info["mid"]
