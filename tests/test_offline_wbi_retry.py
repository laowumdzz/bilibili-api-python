# bilibili_api Wbi -403 重试恢复路径的离线单元测试
#
# 本文件属于无凭据快速路径：全部用例均为纯本地逻辑验证，
# 不触碰网络、不读取 BILI_* 环境变量、不依赖真实账号。
# 通过 mock 打桩底层请求客户端（bilibili_api.utils._api.get_client），
# 令其按序返回预设的 code=-403 / code=0 响应，验证 Api.request 会先经
# recalculate_wbi 重试、重试耗尽后抛出 WbiRetryTimesExceedException，
# 以及重试成功后正常返回的场景。不改动 bilibili_api/utils/_api.py 现有逻辑。

import json

import pytest

from bilibili_api.exceptions import ResponseCodeException, WbiRetryTimesExceedException
from bilibili_api.utils import _api as api_mod
from bilibili_api.utils import _wbi as wbi_mod
from bilibili_api.utils._api import Api
from bilibili_api.utils._log import request_log
from bilibili_api.utils._types import BiliAPIResponse, request_settings
from bilibili_api.utils._wbi import WbiManager

# 固定的测试密钥对（img_key + sub_key），供 nav 打桩返回
IMG_KEY = "7cd084941338484aae1ad9425b84077c"
SUB_KEY = "4932caff0ff746eab6f01bf08b70ac45"

# 预设的业务接口响应体
RESP_403 = json.dumps({"code": -403, "message": "账号未登录"}).encode("utf-8")
RESP_400 = json.dumps({"code": -400, "message": "请求错误"}).encode("utf-8")
RESP_OK = json.dumps({"code": 0, "message": "0", "data": {"ok": 1}}).encode("utf-8")


def _api_resp(raw: bytes) -> BiliAPIResponse:
    """构造离线用的业务接口假响应（HTTP 状态码恒为 200，错误体现在 JSON code 中）。"""
    return BiliAPIResponse(code=200, headers={}, cookies={}, raw=raw, url="https://example.com")


class RetryEnv:
    """一次测试的打桩计数环境：业务请求、nav 密钥请求与 recalculate_wbi 调用次数。"""

    def __init__(self):
        self.api_calls = 0
        self.nav_calls = 0
        self.recalc_calls = 0


def _install_retry_env(monkeypatch: pytest.MonkeyPatch, responses: list[bytes]) -> RetryEnv:
    """打桩 Api.request 重试测试所需的全部外部依赖，返回计数环境。

    Args:
        monkeypatch  (pytest.MonkeyPatch): pytest 的 monkeypatch fixture。
        responses    (list[bytes]): 业务接口按序返回的响应体，耗尽后重复最后一项。

    Returns:
        RetryEnv: 各依赖的调用计数器。
    """
    env = RetryEnv()

    class _ApiClient:
        """业务接口假客户端：按序返回预设响应并计数。"""

        async def request(self, **kwargs) -> BiliAPIResponse:
            env.api_calls += 1
            index = min(env.api_calls, len(responses)) - 1
            return _api_resp(responses[index])

    class _NavResponse:
        def json(self) -> dict:
            return {
                "data": {
                    "wbi_img": {
                        "img_url": f"https://i0.hdslb.com/bfs/wbi/{IMG_KEY}.png",
                        "sub_url": f"https://i0.hdslb.com/bfs/wbi/{SUB_KEY}.png",
                    }
                }
            }

    class _NavClient:
        """nav 密钥接口假客户端：返回固定密钥对并计数。"""

        async def request(self, **kwargs) -> _NavResponse:
            env.nav_calls += 1
            return _NavResponse()

    async def _fake_get_buvid() -> tuple[str, str]:
        return ("test-buvid3", "test-buvid4")

    async def _fake_get_bili_ticket(credential=None) -> tuple[str, str]:
        return ("test-bili-ticket", "0")

    original_recalculate_wbi = api_mod.recalculate_wbi

    def _counting_recalculate_wbi() -> None:
        env.recalc_calls += 1
        original_recalculate_wbi()

    monkeypatch.setattr(api_mod, "get_client", lambda: _ApiClient())
    monkeypatch.setattr(api_mod, "get_buvid", _fake_get_buvid)
    monkeypatch.setattr(api_mod, "get_bili_ticket", _fake_get_bili_ticket)
    monkeypatch.setattr(api_mod, "recalculate_wbi", _counting_recalculate_wbi)
    monkeypatch.setattr(wbi_mod, "get_client", lambda: _NavClient())
    return env


def _make_wbi_api(wbi: bool = True) -> Api:
    """构造走 wbi 鉴权的 GET 请求 Api 对象。"""
    return Api(url="https://example.com/api", method="GET", wbi=wbi).update_params(foo="bar")


@pytest.fixture(autouse=True)
def reset_wbi_retry_state():
    """每个用例前后固定重试次数并重置 WbiManager 类级缓存，避免用例间相互污染。"""
    original_times = request_settings.get_wbi_retry_times()
    request_settings.set_wbi_retry_times(3)
    WbiManager.invalidate()
    WbiManager._lock = None
    yield
    request_settings.set_wbi_retry_times(original_times)
    WbiManager.invalidate()
    WbiManager._lock = None


async def test_wbi_403_retries_then_raises_when_exhausted(monkeypatch):
    """连续 -403 时应每次先经 recalculate_wbi 重试，耗尽后抛出 WbiRetryTimesExceedException。"""
    env = _install_retry_env(monkeypatch, [RESP_403])
    api = _make_wbi_api()
    with pytest.raises(WbiRetryTimesExceedException):
        await api.request()
    # 重试 3 次：3 次业务请求全部 -403，每次失败后都先调用了 recalculate_wbi
    assert env.api_calls == 3
    assert env.recalc_calls == 3
    # 每次 invalidate 后，下一次签名都会重新请求 nav 获取密钥
    assert env.nav_calls == 3


async def test_wbi_403_retry_success_returns_data(monkeypatch):
    """首次 -403 经 recalculate_wbi 重试后成功，应正常返回 data 且不再继续重试。"""
    env = _install_retry_env(monkeypatch, [RESP_403, RESP_OK])
    api = _make_wbi_api()
    result = await api.request()
    assert result == {"ok": 1}
    # 第 1 次失败后重试成功：共 2 次业务请求、1 次 recalculate_wbi、2 次 nav（含失效后重取）
    assert env.api_calls == 2
    assert env.recalc_calls == 1
    assert env.nav_calls == 2


async def test_non_wbi_403_raises_directly(monkeypatch):
    """未启用 wbi 鉴权的请求收到 -403 应直接抛 ResponseCodeException，不进入重试。"""
    env = _install_retry_env(monkeypatch, [RESP_403])
    api = _make_wbi_api(wbi=False)
    with pytest.raises(ResponseCodeException) as exc_info:
        await api.request()
    assert exc_info.value.code == -403
    assert env.api_calls == 1
    assert env.recalc_calls == 0
    assert env.nav_calls == 0


async def test_retry_attempts_share_request_id(monkeypatch):
    """-403 重试的多次尝试应共享同一请求 id，且重试事件携带该 id 供日志回溯。"""
    _install_retry_env(monkeypatch, [RESP_403, RESP_OK])
    captured: list[tuple[str, int]] = []

    @request_log.on("API_REQUEST")
    def on_request(desc: str, data: dict) -> None:
        captured.append(("API_REQUEST", data["id"]))

    @request_log.on("ANTI_SPIDER")
    def on_retry(desc: str, data: dict) -> None:
        # ANTI_SPIDER 事件存在无 id 的变体（如 _wbi 获取密钥的消息），仅捕获携带 id 的重试事件
        if "id" in data:
            captured.append(("ANTI_SPIDER", data["id"]))

    api = _make_wbi_api()
    try:
        assert await api.request() == {"ok": 1}
    finally:
        request_log.remove_event_listener("API_REQUEST", on_request)
        request_log.remove_event_listener("ANTI_SPIDER", on_retry)

    req_ids = [rid for evt, rid in captured if evt == "API_REQUEST"]
    retry_ids = [rid for evt, rid in captured if evt == "ANTI_SPIDER"]
    assert len(req_ids) == 2  # 首次失败 + 重试成功，共 2 次尝试
    assert len(set(req_ids)) == 1  # 所有尝试共享同一请求 id
    assert retry_ids == req_ids[:1]  # 重试事件携带同一 id（1 次重试事件）


async def test_wbi_non_403_error_raises_directly(monkeypatch):
    """启用 wbi 鉴权但错误码非 -403 时应直接抛 ResponseCodeException，不进入重试。"""
    env = _install_retry_env(monkeypatch, [RESP_400])
    api = _make_wbi_api()
    with pytest.raises(ResponseCodeException) as exc_info:
        await api.request()
    assert exc_info.value.code == -400
    assert env.api_calls == 1
    assert env.recalc_calls == 0
    # 首次签名仍会请求一次 nav 密钥
    assert env.nav_calls == 1
