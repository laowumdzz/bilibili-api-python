# scripts/login_and_cache.py 离线单元测试
#
# 本文件属于无凭据快速路径：只验证纯本地可判定的行为（模块导入面、re-export 同一性、
# CLI 用法错误路径、check_cache 的无网络早返回分支与结果契约）。
# 导入被测模块会加载 bilibili_api，但不发起任何网络请求、不读取 BILI_* 环境变量、
# 不依赖真实账号、不改变任何账号状态。

import inspect

import pytest

import scripts._login_cache as pure
import scripts.login_and_cache as login_and_cache

# re-export 进 login_and_cache 的纯缓存契约公开名（contracts/module-api.md）
_REEXPORTED_NAMES = (
    "CACHE_FIELDS",
    "CACHE_FILENAME",
    "REQUIRED_FIELDS",
    "CacheLoadResult",
    "CacheStatus",
    "encode_credential_cache",
    "get_cache_path",
    "load_cache",
    "merge_credential_values",
    "save_cache",
)


def test_module_exports_public_api():
    """模块应导出 conftest 依赖的公共入口 run_temp_login 与 main。"""
    for name in ("run_temp_login", "main"):
        assert hasattr(login_and_cache, name), f"缺少公共导出：{name}"


def test_run_temp_login_signature_has_io_seam():
    """run_temp_login 应以关键字参数暴露 notify / prompt 两个 I/O 接缝。"""
    signature = inspect.signature(login_and_cache.run_temp_login)
    assert list(signature.parameters) == ["login_type", "notify", "prompt"]
    for name in ("notify", "prompt"):
        assert signature.parameters[name].kind is inspect.Parameter.KEYWORD_ONLY


def test_reexports_share_single_implementation():
    """login_and_cache 的纯缓存公开名应与 scripts._login_cache 为同一对象（单一实现）。"""
    for name in _REEXPORTED_NAMES:
        assert getattr(login_and_cache, name) is getattr(pure, name), f"re-export 非同一对象：{name}"


def test_cli_usage_error_exits_2_without_interaction(capsys):
    """无参调用 main 应以退出码 2 输出用法提示，且不进入任何交互。"""
    with pytest.raises(SystemExit) as excinfo:
        login_and_cache.main([])
    assert excinfo.value.code == 2
    captured = capsys.readouterr()
    assert "usage" in captured.err.lower()
    # 用法提示中应呈现两种登录方式取值
    assert "qrcode" in captured.err
    assert "phone" in captured.err


def test_check_cache_none_returns_no_cache_without_network(capsys):
    """check_cache(None) 应走无网络早返回分支：NO_CACHE、空字段、无输出。"""
    result = login_and_cache.check_cache(None, notify=lambda message, **kwargs: None)
    assert result.status is login_and_cache.CacheCheckStatus.NO_CACHE
    assert result.fields == {}
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_cache_check_status_enum_is_complete():
    """CacheCheckStatus 应恰好包含契约约定的六种终态。"""
    assert {status.name for status in login_and_cache.CacheCheckStatus} == {
        "NO_CACHE",
        "VALID",
        "REFRESHED",
        "EXPIRED_NO_MATERIAL",
        "REFRESH_FAILED",
        "NETWORK_ERROR",
    }


def test_cache_check_result_default_fields_empty():
    """CacheCheckResult 缺省字段应为空 dict（契约：仅 VALID / REFRESHED 携带字段）。"""
    result = login_and_cache.CacheCheckResult(login_and_cache.CacheCheckStatus.NETWORK_ERROR)
    assert result.fields == {}
