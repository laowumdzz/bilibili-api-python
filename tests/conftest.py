"""pytest 全局配置与共享 fixtures。

离线用例（test_offline_*.py）不依赖本文件中的任何 fixture；
集成用例通过 credential fixture 获取登录态，凭据来源优先级：
BILI_* 环境变量 > 项目根目录的 .bilibili.cookie 文件（标准 Cookie 字符串，已加入 .gitignore）。
两者均缺失时 skip。
"""

import os
from pathlib import Path
import time

import pytest

from bilibili_api import Credential, request_settings

# 集成用例之间的最小间隔秒数，防止触发 412 风控（沿用旧运行器语义）
RATELIMIT = float(os.getenv("BILI_RATELIMIT", 0))

# 项目根目录下的 Cookie 文件（内容为浏览器导出的标准 Cookie 字符串）
COOKIE_FILE = Path(__file__).resolve().parent.parent / ".bilibili.cookie"

# Cookie 字段名 -> 内部凭据字段名
_COOKIE_FIELD_MAP = {
    "SESSDATA": "sessdata",
    "bili_jct": "bili_jct",
    "buvid3": "buvid3",
    "buvid4": "buvid4",
    "DedeUserID": "dedeuserid",
}


def _parse_cookie_file(path: Path) -> dict[str, str]:
    """解析 Cookie 文件为标准 Cookie 字符串，提取凭据相关字段。"""
    fields: dict[str, str] = {}
    for pair in path.read_text(encoding="utf-8").strip().split(";"):
        name, _, value = pair.strip().partition("=")
        if name in _COOKIE_FIELD_MAP and value:
            fields[_COOKIE_FIELD_MAP[name]] = value
    return fields


def _load_credential_values() -> dict[str, str | None]:
    """按优先级合并凭据来源：BILI_* 环境变量 > .bilibili.cookie 文件。"""
    values: dict[str, str | None] = {}
    if COOKIE_FILE.is_file():
        values.update(_parse_cookie_file(COOKIE_FILE))
    env_mapping = {
        "BILI_SESSDATA": "sessdata",
        "BILI_CSRF": "bili_jct",
        "BILI_BUVID3": "buvid3",
        "BILI_DEDEUSERID": "dedeuserid",
    }
    for env_name, field in env_mapping.items():
        if os.getenv(env_name):
            values[field] = os.getenv(env_name)
    return values


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
    """构建 Credential：优先读 BILI_* 环境变量，其次读 .bilibili.cookie 文件；均缺失时 skip。"""
    values = _load_credential_values()
    if not all(values.get(field) for field in ("sessdata", "bili_jct", "dedeuserid")):
        pytest.skip(
            "缺少登录凭据（BILI_SESSDATA / BILI_CSRF / BILI_DEDEUSERID 环境变量或 .bilibili.cookie 文件），跳过需登录用例"
        )
    return Credential(
        sessdata=values.get("sessdata"),
        bili_jct=values.get("bili_jct"),
        buvid3=values.get("buvid3"),
        buvid4=values.get("buvid4"),
        dedeuserid=values.get("dedeuserid"),
    )
