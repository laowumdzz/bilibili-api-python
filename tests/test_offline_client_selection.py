"""
tests.test_offline_client_selection — 客户端选择公共契约离线测试（特性 009）。

覆盖 FR-007 要求的三场景（无网络、无凭据、不改账号状态）：

- 场景① 内置清单契约：`ALL_PROVIDED_CLIENTS` 恰为 aiohttp、httpx 两项且
  aiohttp 在前（contracts §1）；curl_cffi 第三方库可导入（打桩模拟已安装）
  也不触发任何注册或选择（spec 边界"已装但不探测"）。
- 场景② 回退与默认选择：倒序注册、最后注册者胜出——两客户端齐备时默认
  选中 aiohttp；aiohttp 缺失回退 httpx；全部缺失时走"尚未安装"错误路径
  （文案为契约，contracts §3.2）。
- 场景③ 干净移除与迁移指引：导入已移除适配模块抛 ModuleNotFoundError；
  按名称选择未注册客户端时报错列出已注册清单；同名自定义注册正常生效。

打桩说明：通过 monkeypatch 替换 `importlib.import_module` 模拟第三方库
可/不可导入，并将 `_session` 注册态重置为空以模拟全新环境；仅作用于本地
导入系统与模块状态，不发起任何真实请求。
"""

from collections.abc import Callable
import importlib
import sys
from unittest import mock

import pytest

import bilibili_api
from bilibili_api.clients import ALL_PROVIDED_CLIENTS
from bilibili_api.exceptions import ArgsException
from bilibili_api.utils import _session
from bilibili_api.utils._session import (
    BiliAPIClient,
    get_available_settings,
    get_client,
    get_registered_clients,
    get_selected_client,
    register_client,
    select_client,
    unregister_client,
)

# contracts/client-selection.md §3.2 的"尚未安装"文案（契约原文）。
CONTRACT_NOT_INSTALLED_MSG = "尚未安装第三方请求库或未注册自定义第三方请求库。\n$ pip3 install (aiohttp|httpx)"


def _re_register_all_clients() -> None:
    """重跑内置客户端注册流程（数据驱动机制，随 `ALL_PROVIDED_CLIENTS` 清单自动适应）。"""
    getattr(bilibili_api, "__register_all_clients")()


def _fake_import_missing(missing: set[str]) -> Callable:
    """
    构造一个把 `missing` 集合中顶层模块名伪装为不可导入的 import_module 替身。

    Args:
        missing (set[str]): 视为未安装的第三方库顶层模块名集合。

    Returns:
        Callable: 签名与 `importlib.import_module` 一致的替身函数。
    """
    real_import = importlib.import_module

    def fake_import(name: str, package: str | None = None):
        top = name.split(".")[0] if not name.startswith(".") else (package or "").split(".")[0]
        if top in missing:
            raise ModuleNotFoundError(f"No module named {top!r}", name=top)
        return real_import(name, package)

    return fake_import


@pytest.fixture
def fresh_registration(monkeypatch):
    """将 `_session` 注册态重置为空（模拟全新环境），用例结束由 monkeypatch 自动还原。"""
    monkeypatch.setattr(_session, "sessions", {})
    monkeypatch.setattr(_session, "session_pool", {})
    monkeypatch.setattr(_session, "client_settings", {})
    monkeypatch.setattr(_session, "lazy_settings", {})
    monkeypatch.setattr(_session, "selected_client", "")


# ---------------------------------------------------------------------------
# 场景①：内置清单契约（FR-001 + "已装但不探测"边界）
# ---------------------------------------------------------------------------


def test_scenario1_manifest_contract() -> None:
    """场景①：内置清单恰为 aiohttp、httpx 两项且 aiohttp 在前，声明设置项符合契约 §1。"""
    names = [module for module, _, _ in ALL_PROVIDED_CLIENTS]
    assert names == ["aiohttp", "httpx"]
    settings_by_name = {module: settings for module, _, settings in ALL_PROVIDED_CLIENTS}
    assert settings_by_name["aiohttp"] == {"chunk_size": 262144}
    assert settings_by_name["httpx"] == {"http2": False, "chunk_size": 262144}


def test_scenario1_installed_but_not_probed(fresh_registration, monkeypatch) -> None:
    """场景①：curl_cffi 第三方库可导入（打桩模拟已安装）也不触发任何注册或选择。"""
    monkeypatch.setattr(importlib, "import_module", _fake_import_missing(set()))
    with mock.patch.dict(sys.modules, {"curl_cffi": mock.MagicMock()}):
        _re_register_all_clients()
    assert "curl_cffi" not in get_registered_clients()
    assert sorted(get_registered_clients()) == ["aiohttp", "httpx"]
    assert get_selected_client()[0] != "curl_cffi"


# ---------------------------------------------------------------------------
# 场景②：回退与默认选择（FR-002 + FR-009 文案契约）
# ---------------------------------------------------------------------------


def test_scenario2_default_selection_is_aiohttp(fresh_registration, monkeypatch) -> None:
    """场景②：倒序注册、最后注册者胜出——两客户端齐备时默认选中 aiohttp。"""
    monkeypatch.setattr(importlib, "import_module", _fake_import_missing(set()))
    _re_register_all_clients()
    assert sorted(get_registered_clients()) == ["aiohttp", "httpx"]
    assert get_selected_client()[0] == "aiohttp"


def test_scenario2_fallback_to_httpx_when_aiohttp_missing(fresh_registration, monkeypatch) -> None:
    """场景②：aiohttp 不可导入时自动回退 httpx。"""
    monkeypatch.setattr(importlib, "import_module", _fake_import_missing({"aiohttp"}))
    _re_register_all_clients()
    assert sorted(get_registered_clients()) == ["httpx"]
    assert get_selected_client()[0] == "httpx"


def test_scenario2_all_missing_error_path(fresh_registration, monkeypatch) -> None:
    """场景②：全部缺失时走"尚未安装"错误路径，三处文案与契约 §3.2 逐字一致。"""
    monkeypatch.setattr(importlib, "import_module", _fake_import_missing({"aiohttp", "httpx"}))
    _re_register_all_clients()
    with pytest.raises(ArgsException) as selected_exc:
        get_selected_client()
    assert str(selected_exc.value) == CONTRACT_NOT_INSTALLED_MSG
    with pytest.raises(ArgsException) as settings_exc:
        get_available_settings()
    assert str(settings_exc.value) == CONTRACT_NOT_INSTALLED_MSG
    with pytest.raises(ArgsException) as client_exc:
        get_client()
    assert str(client_exc.value) == CONTRACT_NOT_INSTALLED_MSG


# ---------------------------------------------------------------------------
# 场景③：干净移除与迁移指引（FR-003 + FR-005 + 导入路径裁决）
# ---------------------------------------------------------------------------


class _StubCustomClient(BiliAPIClient):
    """同名自定义注册验证用的最小客户端桩（仅校验子类关系，不实例化）。"""


def test_scenario3_import_removed_module_raises_module_not_found() -> None:
    """场景③a：直接导入已移除适配模块以标准 ModuleNotFoundError 失败（无报错桩）。"""
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("bilibili_api.clients.CurlCFFIClient")


def test_scenario3_select_unregistered_lists_registered(fresh_registration, monkeypatch) -> None:
    """场景③b：按名称选择未注册客户端时报错列出已注册清单（字典序）与自定义注册提示。"""
    monkeypatch.setattr(importlib, "import_module", _fake_import_missing(set()))
    _re_register_all_clients()
    with pytest.raises(ArgsException) as exc_info:
        select_client("curl_cffi")
    message = str(exc_info.value)
    assert "当前已注册的客户端：aiohttp, httpx" in message
    assert "register_client()" in message


def test_scenario3_same_name_custom_register_accepted(fresh_registration, monkeypatch) -> None:
    """场景③c：注册与已移除客户端同名的自定义实现正常生效，注销后还原默认选择。"""
    monkeypatch.setattr(importlib, "import_module", _fake_import_missing(set()))
    _re_register_all_clients()
    register_client("curl_cffi", _StubCustomClient)
    select_client("curl_cffi")
    assert get_selected_client()[0] == "curl_cffi"
    assert get_selected_client()[1] is _StubCustomClient
    unregister_client("curl_cffi")
    select_client("aiohttp")
    assert get_selected_client()[0] == "aiohttp"
    assert "curl_cffi" not in get_registered_clients()
