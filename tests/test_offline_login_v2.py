# bilibili_api.login_v2 离线单元测试
#
# 本文件属于无凭据快速路径：全部用例均为纯本地逻辑验证，
# 不触碰网络、不读取 BILI_* 环境变量、不依赖真实账号。
# 覆盖：地区代码表查询、手机号校验、二维码登录初始状态、
# LoginCheck 链接解析、RSA 密码加密往返；发送验证码/实际登录等触网入口不测。

import base64

from Cryptodome.Cipher import PKCS1_v1_5
from Cryptodome.PublicKey import RSA
import pytest

from bilibili_api.exceptions import StatementException
from bilibili_api.login_v2 import (
    LoginCheck,
    PhoneNumber,
    QrCodeLogin,
    QrCodeLoginChannel,
    QrCodeLoginEvents,
    encrypt,
    get_code_by_country,
    get_countries_list,
    get_id_by_code,
    have_code,
    have_country,
    search_countries,
)

# 由内置地区表保证存在的样例：中国大陆 +86
MAINLAND_NAME = "中国大陆"


# ---------------------------------------------------------------- 地区代码表


def test_get_countries_list_shape():
    """地区列表应非空且每项含 name / id / code 字段。"""
    countries = get_countries_list()
    assert len(countries) > 0
    for country in countries:
        assert set(country.keys()) == {"name", "id", "code"}
        assert isinstance(country["code"], int)


def test_search_countries_by_name_and_code():
    """按名称与按区号（含 + 前缀）都能搜索到地区。"""
    by_name = search_countries("中国")
    assert any(country["name"] == MAINLAND_NAME for country in by_name)

    by_code = search_countries("+86")
    assert any(country["code"] == 86 for country in by_code)
    # 去前导 + 后与 code 做前缀匹配，不应命中无关地区名分支的副作用
    by_code_plain = search_countries("86")
    assert any(country["code"] == 86 for country in by_code_plain)
    # 不存在的区号/名称应返回空列表且不抛异常
    assert search_countries("+99999-离线测试") == []


def test_have_country_and_have_code():
    """地区/区号存在性判断。"""
    assert have_country(MAINLAND_NAME) is True
    assert have_country("不存在的地区名称-离线测试") is False

    assert have_code(86) is True
    assert have_code("+86") is True
    assert have_code(99999) is False
    # 非法字符串代码应抛 ValueError
    with pytest.raises(ValueError, match="地区代码参数错误"):
        have_code("abc")
    # 非 str / int 类型直接返回 False
    assert have_code(None) is False  # type: ignore


def test_get_code_by_country_and_get_id_by_code():
    """地区名 ↔ 区号 ↔ 地区 id 的互查。"""
    code = get_code_by_country(MAINLAND_NAME)
    assert code == 86
    assert get_code_by_country("不存在的地区名称-离线测试") == -1

    country_id = get_id_by_code(code)
    assert country_id != -1
    assert get_id_by_code(99999) == -1


# ---------------------------------------------------------------- 手机号


def test_phone_number_validation():
    """合法区号/地区名可构造，号码中的连字符应被去除。"""
    phone = PhoneNumber("138-0013-8000", "+86")
    assert phone.number == "13800138000"
    assert phone.code == 86
    assert phone.id_ != -1
    assert "+86" in str(phone)

    phone_by_name = PhoneNumber("13800138000", MAINLAND_NAME)
    assert phone_by_name.code == 86


def test_phone_number_invalid_region_raises():
    """非法地区/区号应抛 ValueError。"""
    with pytest.raises(ValueError, match="地区代码或地区名错误"):
        PhoneNumber("13800138000", "+99999")


# ---------------------------------------------------------------- 二维码登录初始状态


def test_qrcode_login_initial_state():
    """未生成二维码时各状态接口应为初始值。"""
    login = QrCodeLogin(platform=QrCodeLoginChannel.WEB)
    assert login.has_qrcode() is False
    assert login.has_done() is False
    assert login.get_qrcode_picture() is None
    assert login.get_qrcode_terminal() == ""
    # 未完成登录时不得获取凭据
    with pytest.raises(StatementException):
        login.get_credential()


def test_qrcode_login_enums():
    """二维码登录渠道与事件枚举值保持稳定。"""
    assert QrCodeLoginChannel.WEB.value == "web"
    assert QrCodeLoginChannel.TV.value == "tv"
    assert {event.value for event in QrCodeLoginEvents} == {"scan", "confirm", "timeout", "done"}


# ---------------------------------------------------------------- LoginCheck 链接解析


def test_login_check_parses_check_url():
    """LoginCheck 应从验证链接中提取 tmp_token 与 request_id。"""
    url = "https://passport.bilibili.com/risk/verify?tmp_token=fake-token-123&request_id=req-456"
    check = LoginCheck(url)
    assert check._LoginCheck__token == "fake-token-123"
    assert check._LoginCheck__id == "req-456"

    # 无 request_id 的链接也能解析
    check_no_id = LoginCheck("https://passport.bilibili.com/risk/verify?tmp_token=only-token")
    assert check_no_id._LoginCheck__token == "only-token"
    assert check_no_id._LoginCheck__id is None


# ---------------------------------------------------------------- RSA 密码加密


def test_encrypt_roundtrip_with_generated_rsa_key():
    """encrypt 的密文用对应私钥解密后应还原为 hash + 密码。"""
    key = RSA.generate(1024)
    public_pem = key.publickey().export_key().decode("utf-8")

    hash_ = "offline-hash"
    password = "offline-password"
    encrypted = encrypt(hash_, public_pem, password)

    # PKCS1_v1_5 带随机填充，密文不可直接比较，用私钥解密验证
    decryptor = PKCS1_v1_5.new(key)
    plain = decryptor.decrypt(base64.b64decode(encrypted), sentinel=b"FAILED")
    assert plain.decode("utf-8") == hash_ + password
