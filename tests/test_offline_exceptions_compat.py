# bilibili_api.exceptions 兼容性离线单元测试
#
# 本文件属于无凭据快速路径：全部用例均为纯本地导入验证，
# 不触碰网络、不读取凭据、不依赖真实账号。
# 覆盖：首次提交存在过的全部 22 条按类异常子模块导入路径逐一可导入、
# 模块内类与包级导出为同一对象（is 判定）、包级 __all__ 集合不变
# （specs/010-review-defect-fixes FR-005 / SC-003）。

import importlib

import pytest

import bilibili_api.exceptions as exceptions_pkg

# 首次提交（99648df）存在过的全部按类异常子模块路径（specs/010-review-defect-fixes
# data-model.md 实体 2）：5 个自有模块原生存在，17 个经薄兼容模块恢复。
HISTORICAL_PATHS = [
    "ApiException",
    "ArgsException",
    "CookiesRefreshException",
    "CredentialNoAcTimeValueException",
    "CredentialNoBiliJctException",
    "CredentialNoBuvid3Exception",
    "CredentialNoBuvid4Exception",
    "CredentialNoDedeUserIDException",
    "CredentialNoSessdataException",
    "DanmakuClosedException",
    "DynamicExceedImagesException",
    "ExClimbWuzhiException",
    "GeetestException",
    "InitialStateException",
    "LiveException",
    "LoginError",
    "NetworkException",
    "ResponseCodeException",
    "ResponseException",
    "StatementException",
    "VideoUploadException",
    "WbiRetryTimesExceedException",
]

# 经薄兼容模块（仅 re-export _simple 中的类）恢复的 17 条路径
THIN_COMPAT_PATHS = [
    "ArgsException",
    "CredentialNoAcTimeValueException",
    "CredentialNoBiliJctException",
    "CredentialNoBuvid3Exception",
    "CredentialNoBuvid4Exception",
    "CredentialNoDedeUserIDException",
    "CredentialNoSessdataException",
    "DanmakuClosedException",
    "DynamicExceedImagesException",
    "GeetestException",
    "InitialStateException",
    "LiveException",
    "LoginError",
    "ResponseException",
    "StatementException",
    "VideoUploadException",
    "WbiRetryTimesExceedException",
]


@pytest.mark.parametrize("name", HISTORICAL_PATHS)
def test_historical_submodule_path_importable_and_identical(name):
    """任一历史子模块路径均可导入，且模块内类与包级导出为同一对象（except 精确捕获行为一致）。"""
    module = importlib.import_module(f"bilibili_api.exceptions.{name}")
    assert getattr(module, name) is getattr(exceptions_pkg, name)


@pytest.mark.parametrize("name", THIN_COMPAT_PATHS)
def test_thin_compat_module_shape(name):
    """薄兼容模块仅 re-export：__all__ 恰含类名自身，模块内无多余定义。"""
    module = importlib.import_module(f"bilibili_api.exceptions.{name}")
    assert module.__all__ == [name]
    assert module.__name__ == f"bilibili_api.exceptions.{name}"


def test_package_all_unchanged():
    """包级 __all__ 集合与修复前完全一致（22 项）。"""
    assert set(exceptions_pkg.__all__) == set(HISTORICAL_PATHS)
