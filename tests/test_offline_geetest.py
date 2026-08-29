# bilibili_api.utils.geetest 离线单元测试
#
# 本文件属于无凭据快速路径：全部用例均为纯本地逻辑验证，
# 不触碰网络、不读取 BILI_* 环境变量、不依赖真实账号。
# 仅覆盖不触网的纯本地部分：枚举、数据结构、验证码状态机、
# 本地验证页 urlhandler 的回调解析；启动本地服务/生成验证码等触网入口不测。

import pytest

from bilibili_api.exceptions import GeetestException
from bilibili_api.utils.geetest import Geetest, GeetestMeta, GeetestType


def test_geetest_type_values():
    """极验类型枚举值应保持稳定（与 login.json 的键对应）。"""
    assert GeetestType.LOGIN.value == "password"
    assert GeetestType.VERIFY.value == "safecenter"


def test_geetest_meta_defaults():
    """GeetestMeta 的完成字段应默认为空字符串。"""
    meta = GeetestMeta(gt="gt", challenge="ch", token="tk")
    assert meta.seccode == ""
    assert meta.validate == ""


def test_geetest_state_machine():
    """未完成验证时 get_result 抛错，complete_test 后可取回完整结果。"""
    geetest = Geetest()
    geetest.gt = "gt-value"
    geetest.challenge = "challenge-value"
    geetest.key = "token-value"

    assert geetest.has_done() is False
    with pytest.raises(GeetestException):
        geetest.get_result()

    # get_info 在完成前后均可获取基础字段
    info = geetest.get_info()
    assert info == GeetestMeta(gt="gt-value", challenge="challenge-value", token="token-value")

    geetest.complete_test(validate="v-result", seccode="s-result|0")
    assert geetest.has_done() is True
    result = geetest.get_result()
    assert result.validate == "v-result"
    assert result.seccode == "s-result|0"
    assert result.token == "token-value"


def test_urlhandler_result_callback_parses_validate_and_seccode():
    """result 回调链接应解析出 validate / seccode 并标记完成。"""
    geetest = Geetest()
    assert geetest.has_done() is False

    html_source = geetest._geetest_urlhandler("/result/validate=abc123&seccode=xyz%7C0", "text/html")
    assert html_source  # 返回完成页内容
    assert geetest.validate == "abc123"
    assert geetest.seccode == "xyz|0"  # %7C 应被还原为 |
    assert geetest.has_done() is True


def test_urlhandler_index_page_injects_gt_and_challenge():
    """首页应注入当前 gt / challenge 值。"""
    geetest = Geetest()
    geetest.gt = "GT-OFFLINE"
    geetest.challenge = "CH-OFFLINE"

    html_source = geetest._geetest_urlhandler("/", "text/html")
    assert '"GT-OFFLINE"' in html_source
    assert '"CH-OFFLINE"' in html_source
    # 占位符必须被替换掉
    assert "{ Python_Interface: GT }" not in html_source
    assert "{ Python_Interface: CHALLENGE }" not in html_source


def test_urlhandler_unknown_path_returns_empty():
    """未知路径应返回空字符串。"""
    geetest = Geetest()
    assert geetest._geetest_urlhandler("/nonexistent.css", "text/css") == ""
