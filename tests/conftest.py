"""pytest 全局配置与共享 fixtures。

离线用例（test_offline_*.py）不依赖本文件中的任何 fixture；
集成用例通过 credential fixture 获取登录态，缺 BILI_* 环境变量时 skip。
"""

import os
import time

import pytest

from bilibili_api import Credential, request_settings

# 集成用例之间的最小间隔秒数，防止触发 412 风控（沿用旧运行器语义）
RATELIMIT = float(os.getenv("BILI_RATELIMIT", 0))

_REQUIRED_ENVS = ("BILI_SESSDATA", "BILI_CSRF", "BILI_DEDEUSERID")


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """为离线文件之外的所有用例自动打 integration 标记。"""
    for item in items:
        if not os.path.basename(str(item.path)).startswith("test_offline_"):
            item.add_marker(pytest.mark.integration)


@pytest.fixture(scope="session", autouse=True)
def test_env() -> None:
    """全会话生效的请求超时设置（沿用旧运行器 request_settings.set_timeout(100)）。"""
    request_settings.set_timeout(100)


@pytest.fixture(autouse=True)
def ratelimit(request: pytest.FixtureRequest):
    """集成用例之间按 BILI_RATELIMIT 限速。"""
    yield
    if RATELIMIT > 0 and request.node.get_closest_marker("integration"):
        time.sleep(RATELIMIT)


@pytest.fixture(scope="session")
def credential() -> Credential:
    """从环境变量构建 Credential；缺少必需环境变量时 skip 而非报错。"""
    if not all(os.getenv(name) for name in _REQUIRED_ENVS):
        pytest.skip("缺少 BILI_SESSDATA / BILI_CSRF / BILI_DEDEUSERID 环境变量，跳过需登录用例")
    return Credential(
        sessdata=os.getenv("BILI_SESSDATA"),
        bili_jct=os.getenv("BILI_CSRF"),
        buvid3=os.getenv("BILI_BUVID3"),
        dedeuserid=os.getenv("BILI_DEDEUSERID"),
    )
