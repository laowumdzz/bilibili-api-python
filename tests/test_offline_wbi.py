# bilibili_api WbiManager 反爬虫签名的离线单元测试
#
# 本文件属于无凭据快速路径：全部用例均为纯本地逻辑验证，
# 不触碰网络、不读取 BILI_* 环境变量、不依赖真实账号。
# 密钥获取相关用例通过 mock 打桩底层请求客户端（bilibili_api.utils._wbi.get_client），
# 并在每个用例前后重置 WbiManager 类级缓存，避免用例间相互污染。

import asyncio
import hashlib
import re
import time
from unittest.mock import patch
import urllib.parse

import pytest

from bilibili_api.utils._wbi import WbiManager

# 固定的测试密钥对（img_key + sub_key），用于向量比对与签名校验
IMG_KEY = "7cd084941338484aae1ad9425b84077c"
SUB_KEY = "4932caff0ff746eab6f01bf08b70ac45"


def _reference_mixin_key(orig: str) -> str:
    """独立参考实现：按 MIXIN_KEY_ENC_TAB 重排后截取前 32 位（手工计算基准）。"""
    return "".join(orig[i] for i in WbiManager.MIXIN_KEY_ENC_TAB)[:32]


def _reference_w_rid(params: dict, mixin_key: str) -> str:
    """独立参考实现：按 key 排序 + 过滤 !'()* + urlencode 后拼接 mixin_key 计算 MD5。"""
    filtered = {k: "".join(ch for ch in str(v) if ch not in "!'()*") for k, v in sorted(params.items())}
    query = urllib.parse.urlencode(filtered)
    return hashlib.md5((query + mixin_key).encode()).hexdigest()


def _patch_get_client(call_counter: list[int]) -> patch:
    """构造对 bilibili_api.utils._wbi.get_client 的 patch，返回计数请求次数的 mock 客户端。"""
    nav_data = {
        "data": {
            "wbi_img": {
                "img_url": f"https://i0.hdslb.com/bfs/wbi/{IMG_KEY}.png",
                "sub_url": f"https://i0.hdslb.com/bfs/wbi/{SUB_KEY}.png",
            }
        }
    }

    class _FakeResponse:
        def json(self) -> dict:
            return nav_data

    class _FakeClient:
        async def request(self, **kwargs) -> _FakeResponse:
            call_counter.append(1)
            return _FakeResponse()

    return patch("bilibili_api.utils._wbi.get_client", return_value=_FakeClient())


@pytest.fixture(autouse=True)
def reset_wbi_cache():
    """每个用例前后重置类级缓存与惰性锁，避免用例间相互污染。"""
    WbiManager.invalidate()
    WbiManager._lock = None
    yield
    WbiManager.invalidate()
    WbiManager._lock = None


def test_get_mixin_key_known_vector():
    """_get_mixin_key 输出应为 32 位，且与按 MIXIN_KEY_ENC_TAB 手工计算的结果一致。"""
    orig = IMG_KEY + SUB_KEY
    result = WbiManager._get_mixin_key(orig)
    assert len(result) == 32
    assert result == _reference_mixin_key(orig)
    # 混淆表本身应为 64 项且索引全部落在 [0, 64) 内（否则重排会越界）
    assert len(WbiManager.MIXIN_KEY_ENC_TAB) == 64
    assert all(0 <= i < 64 for i in WbiManager.MIXIN_KEY_ENC_TAB)


def test_enc_wbi_contains_wts_and_w_rid():
    """_enc_wbi 结果应含 wts 与 32 位十六进制 w_rid，且 w_rid 与独立参考实现一致。"""
    params: dict[str, str | int] = {"foo": "114", "514": "514", "zab": "cd"}
    result = WbiManager._enc_wbi(params, img_key=IMG_KEY, sub_key=SUB_KEY)
    # 签名过程中所有值均被转为过滤后的字符串，wts 也不例外
    assert result["wts"].isdigit()
    assert abs(int(result["wts"]) - time.time()) < 10
    assert re.fullmatch(r"[0-9a-f]{32}", result["w_rid"])
    # 原有参数保留（值统一转为过滤后的字符串）
    assert result["foo"] == "114"
    assert result["514"] == "514"
    assert result["zab"] == "cd"
    # 用签名时的实际 wts 复核参考实现，确保签名算法（排序 + 过滤 + urlencode + MD5）一致
    signed = {k: v for k, v in result.items() if k != "w_rid"}
    assert result["w_rid"] == _reference_w_rid(signed, _reference_mixin_key(IMG_KEY + SUB_KEY))


def test_enc_wbi_filters_special_chars():
    """_enc_wbi 应在签名前过滤参数值中的 !'()* 字符。"""
    params: dict[str, str | int] = {"text": "hello!'()*world", "keep": "abc"}
    result = WbiManager._enc_wbi(params, img_key=IMG_KEY, sub_key=SUB_KEY)
    assert result["text"] == "helloworld"  # 特殊字符全部被过滤
    assert result["keep"] == "abc"
    signed = {k: v for k, v in result.items() if k != "w_rid"}
    assert result["w_rid"] == _reference_w_rid(signed, _reference_mixin_key(IMG_KEY + SUB_KEY))


def test_enc_wbi_clears_stale_w_rid():
    """参数中已含旧 w_rid 时应先清除再重签，不残留旧签名参与计算。"""
    stale = "0" * 32
    params: dict[str, str | int] = {"foo": "bar", "w_rid": stale}
    result = WbiManager._enc_wbi(params, img_key=IMG_KEY, sub_key=SUB_KEY)
    assert result["w_rid"] != stale
    assert re.fullmatch(r"[0-9a-f]{32}", result["w_rid"])
    # 旧 w_rid 未参与签名：结果应与不含旧值的签名一致（同 wts 下）
    signed = {k: v for k, v in result.items() if k != "w_rid"}
    assert result["w_rid"] == _reference_w_rid(signed, _reference_mixin_key(IMG_KEY + SUB_KEY))


def test_invalidate_resets_cache_state():
    """invalidate() 应清空类级缓存的密钥与时间戳（不触发网络请求）。"""
    WbiManager._img_key = "test-img-key"
    WbiManager._sub_key = "test-sub-key"
    WbiManager._mixin_key = "test-mixin-key"
    WbiManager._cache_ts = time.time()
    assert not WbiManager._keys_expired()
    WbiManager.invalidate()
    assert WbiManager._img_key == ""
    assert WbiManager._sub_key == ""
    assert WbiManager._mixin_key == ""
    assert WbiManager._cache_ts == 0.0
    assert WbiManager._keys_expired()


async def test_get_wbi_keys_cached_within_ttl():
    """TTL 有效期内连续两次 _get_wbi_keys 应命中缓存，仅请求一次 nav。"""
    calls: list[int] = []
    with _patch_get_client(calls):
        img_key, sub_key = await WbiManager._get_wbi_keys()
        assert (img_key, sub_key) == (IMG_KEY, SUB_KEY)
        assert WbiManager._mixin_key == _reference_mixin_key(IMG_KEY + SUB_KEY)
        # 第二次调用应直接命中缓存，不再触发新的客户端请求
        again = await WbiManager._get_wbi_keys()
    assert again == (IMG_KEY, SUB_KEY)
    assert len(calls) == 1


async def test_get_wbi_keys_expired_refetch():
    """缓存超过 6 小时 TTL 后应重新请求 nav 获取密钥。"""
    calls: list[int] = []
    with _patch_get_client(calls):
        await WbiManager._get_wbi_keys()
        assert len(calls) == 1
        # 人为把时间戳回拨至超出 TTL，模拟过期
        WbiManager._cache_ts = time.time() - WbiManager.WBI_KEYS_TTL - 1
        assert WbiManager._keys_expired()
        await WbiManager._get_wbi_keys()
    assert len(calls) == 2


async def test_get_end_result_default_web_location():
    """get_end_result 未提供 web_location 时应补充默认值 444.8 并完成签名。"""
    calls: list[int] = []
    with _patch_get_client(calls):
        result = await WbiManager.get_end_result({"foo": "bar"})
    assert result["web_location"] == "444.8"
    assert re.fullmatch(r"[0-9a-f]{32}", result["w_rid"])
    assert "wts" in result


async def test_get_end_result_keeps_existing_web_location():
    """参数已含 web_location 时 get_end_result 不应覆盖，且签名包含该自定义值。"""
    calls: list[int] = []
    with _patch_get_client(calls):
        result = await WbiManager.get_end_result({"foo": "bar", "web_location": "1550101"})
    assert result["web_location"] == "1550101"
    signed = {k: v for k, v in result.items() if k != "w_rid"}
    assert result["w_rid"] == _reference_w_rid(signed, _reference_mixin_key(IMG_KEY + SUB_KEY))


async def test_get_mixin_key_uses_cache():
    """get_mixin_key 应返回缓存的 32 位密钥，且多次调用只请求一次 nav。"""
    calls: list[int] = []
    with _patch_get_client(calls):
        first = await WbiManager.get_mixin_key()
        second = await WbiManager.get_mixin_key()
    assert len(first) == 32
    assert first == second == _reference_mixin_key(IMG_KEY + SUB_KEY)
    assert len(calls) == 1


async def test_concurrent_signatures_single_flight():
    """并发多次签名（双重检查锁单飞）应只触发一次 nav 请求。"""
    calls: list[int] = []
    with _patch_get_client(calls):
        results = await asyncio.gather(*(WbiManager.get_end_result({"i": i}) for i in range(8)))
    assert len(calls) == 1
    assert all(re.fullmatch(r"[0-9a-f]{32}", r["w_rid"]) for r in results)
    assert all(r["web_location"] == "444.8" for r in results)
