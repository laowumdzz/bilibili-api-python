"""pytest 全局配置与共享 fixtures。

离线用例（test_offline_*.py）不依赖本文件中的任何 fixture；
集成用例通过 credential fixture 获取登录态，凭据来源优先级：
--login 临时登录（实现委托 scripts/login_and_cache.py，本文件仅注入 pytest 终端 I/O 接缝）
> TEMP 缓存文件（自动校验 / 刷新）> BILI_* 环境变量 > 项目根目录的 .bilibili.cookie 文件。
全部来源不可用时 skip。
"""

from functools import partial
import os
from pathlib import Path
import sys
import time
import warnings

import pytest

from bilibili_api import Credential, request_settings
from scripts._login_cache import REQUIRED_FIELDS, CacheStatus, get_cache_path, load_cache, merge_credential_values
from scripts.login_and_cache import CacheCheckStatus, check_cache, run_temp_login

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


class _SessionCredentialState:
    """会话级凭据装配状态：pytest_sessionstart 装配，credential fixture 消费。"""

    def __init__(self) -> None:
        # --login 登录成功的新凭据（优先级第 1 位，登录实现内部已同步写入缓存文件）
        self.fresh_fields: dict[str, str] | None = None
        # 缓存文件中格式合法的凭据（尚未联网校验，等待 fixture 按需校验 / 刷新）
        self.cache_fields: dict[str, str] | None = None


_SESSION_STATE = _SessionCredentialState()


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


def _build_credential(fields: dict[str, str | None]) -> Credential:
    """由字段集合构建 Credential（缺失字段保持 None）。"""
    return Credential(
        sessdata=fields.get("sessdata"),
        bili_jct=fields.get("bili_jct"),
        buvid3=fields.get("buvid3"),
        buvid4=fields.get("buvid4"),
        dedeuserid=fields.get("dedeuserid"),
        ac_time_value=fields.get("ac_time_value"),
    )


def _notify(config: pytest.Config, message: str, *, error: bool = False) -> None:
    """向 pytest 终端输出一条用户可见消息（绕过用例级输出捕获，不含凭据值）。"""
    writer = config.get_terminal_writer()
    if writer is not None:
        writer.line(message, red=error, bold=True)


def _prompt(config: pytest.Config, message: str) -> str:
    """经终端 writer 显示提示后从真实 stdin 读取一行输入（均绕过用例级输出捕获）。"""
    writer = config.get_terminal_writer()
    if writer is not None:
        writer.write(message, flush=True)
    else:
        sys.stderr.write(message)
    return _read_line()


def _read_line() -> str:
    """读取一行用户输入；pytest 输出捕获期间 sys.stdin 被替换为只读守卫，回退到解释器原始 stdin。"""
    try:
        line = sys.stdin.readline()
    except OSError:
        original = sys.__stdin__
        if original is None:
            raise EOFError("stdin 不可用") from None
        line = original.readline()
    return line.rstrip("\r\n")


def pytest_addoption(parser: pytest.Parser) -> None:
    """注册 --login 选项：交互式临时登录获取测试凭据（实现由 scripts/login_and_cache.py 提供）。"""
    group = parser.getgroup("bilibili-login", "B 站临时登录")
    group.addoption(
        "--login",
        action="store",
        default=None,
        choices=["phone", "qrcode"],
        metavar="TYPE",
        help="临时登录获取测试凭据：qrcode 扫码 / phone 短信验证码；成功后写入 TEMP 缓存文件供后续运行复用",
    )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """为离线文件之外的所有用例自动打 integration 标记。"""
    for item in items:
        if not os.path.basename(str(item.path)).startswith("test_offline_"):
            item.add_marker(pytest.mark.integration)


def pytest_sessionstart(session: pytest.Session) -> None:
    """会话启动时装配凭据来源：--login 临时登录（委托脚本模块）+ TEMP 缓存文件的读取与清理。

    本钩子只做交互式登录与纯本地文件操作（读取 / 格式校验 / 删除），
    缓存凭据的联网校验与刷新延迟到 credential fixture 实际需要时进行，
    保证纯离线运行不产生任何网络请求。
    """
    config = session.config
    login_type: str | None = config.getoption("--login")
    if login_type is not None:
        fields = run_temp_login(login_type, notify=partial(_notify, config), prompt=partial(_prompt, config))
        if fields is not None:
            _SESSION_STATE.fresh_fields = fields
            return
    # --login 未传入或已中止：读取既有缓存文件（仅本地读取与格式校验）
    result = load_cache()
    if result.status is CacheStatus.ABSENT:
        _notify(
            config,
            f"提示：临时登录凭据缓存文件不存在（{get_cache_path()}），"
            "需登录用例将回退到 BILI_* 环境变量 / .bilibili.cookie 来源",
        )
    elif result.status is CacheStatus.CORRUPT:
        get_cache_path().unlink(missing_ok=True)
        _notify(
            config,
            f"错误：临时登录凭据缓存文件内容不合法（{result.reason}），已删除该文件，"
            "需登录用例将回退到 BILI_* 环境变量 / .bilibili.cookie 来源",
            error=True,
        )
    else:
        _SESSION_STATE.cache_fields = result.fields


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
def credential(request: pytest.FixtureRequest) -> Credential:
    """构建 Credential：--login 新登录 > TEMP 缓存（校验 / 刷新）> BILI_* 环境变量 > .bilibili.cookie；全部不可用时 skip。"""
    config = request.config
    if _SESSION_STATE.fresh_fields is not None:
        fields = merge_credential_values(_SESSION_STATE.fresh_fields, _load_credential_values())
    else:
        check = check_cache(_SESSION_STATE.cache_fields, notify=partial(_notify, config))
        cached_fields: dict[str, str] | None = None
        if check.status is CacheCheckStatus.NETWORK_ERROR:
            pytest.skip("临时登录凭据缓存有效性无法验证（网络异常），跳过需登录用例")
        if check.status is CacheCheckStatus.EXPIRED_NO_MATERIAL:
            warnings.warn(
                UserWarning("临时登录凭据已过期，且缓存缺少刷新材料（ac_time_value），已删除缓存文件"),
                stacklevel=2,
            )
        elif check.status is CacheCheckStatus.REFRESH_FAILED:
            warnings.warn(UserWarning("临时登录凭据已过期且刷新失败，已删除缓存文件"), stacklevel=2)
        else:
            cached_fields = check.fields or None
        fields = merge_credential_values(cached_fields, _load_credential_values())
    if not all(fields.get(name) for name in REQUIRED_FIELDS):
        pytest.skip(
            "缺少登录凭据（--login 临时登录、TEMP 缓存、BILI_SESSDATA / BILI_CSRF / BILI_DEDEUSERID "
            "环境变量与 .bilibili.cookie 文件均不可用），跳过需登录用例"
        )
    return _build_credential(fields)
