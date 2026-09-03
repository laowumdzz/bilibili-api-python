"""pytest 全局配置与共享 fixtures。

离线用例（test_offline_*.py）不依赖本文件中的任何 fixture；
集成用例通过 credential fixture 获取登录态，凭据来源优先级：
--login 临时登录 > TEMP 缓存文件（bilibili_api_pytest_login.json，自动校验 / 刷新）
> BILI_* 环境变量 > 项目根目录的 .bilibili.cookie 文件。
全部来源不可用时 skip。
"""

import asyncio
import os
from pathlib import Path
import sys
import tempfile
import time
import warnings

import pytest

from bilibili_api import Credential, request_settings
from bilibili_api.login_v2 import (
    LoginCheck,
    PhoneNumber,
    QrCodeLogin,
    QrCodeLoginEvents,
    login_with_sms,
    send_sms,
)
from bilibili_api.utils._session import get_client
from bilibili_api.utils.geetest import Geetest, GeetestType
from scripts._login_cache import (
    CACHE_FIELDS,
    REQUIRED_FIELDS,
    CacheStatus,
    get_cache_path,
    load_cache,
    merge_credential_values,
    save_cache,
)

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

# 二维码登录：轮询间隔（秒）与连续超时上限（达到即中止）
_QR_POLL_INTERVAL = 2.0
_QR_MAX_TIMEOUTS = 3

# 极验滑块完成状态的轮询间隔（秒）
_GEETEST_POLL_INTERVAL = 0.5


class _LoginAbort(Exception):
    """临时登录中止（用户中断 / 连续超时 / 流程失败），原因描述不含凭据值。"""


class _SessionCredentialState:
    """会话级凭据装配状态：pytest_sessionstart 装配，credential fixture 消费。"""

    def __init__(self) -> None:
        # --login 登录成功的新凭据（优先级第 1 位，已同步写入缓存文件）
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


def _credential_to_fields(credential: Credential) -> dict[str, str | None]:
    """从 Credential 提取缓存契约字段（缺失字段为 None）。"""
    return {name: getattr(credential, name, None) for name in CACHE_FIELDS}


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
    """注册 --login 选项：交互式临时登录获取测试凭据（qrcode / phone）。"""
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
    """会话启动时装配凭据来源：--login 临时登录 + TEMP 缓存文件的读取与清理。

    本钩子只做交互式登录与纯本地文件操作（读取 / 格式校验 / 删除），
    缓存凭据的联网校验与刷新延迟到 credential fixture 实际需要时进行，
    保证纯离线运行不产生任何网络请求。
    """
    config = session.config
    login_type: str | None = config.getoption("--login")
    if login_type is not None:
        login_result = _run_temp_login(login_type, config)
        if login_result is not None:
            fields = {
                key: value
                for key, value in _credential_to_fields(login_result).items()
                if isinstance(value, str) and value
            }
            save_cache(fields)
            _SESSION_STATE.fresh_fields = fields
            _notify(config, f"临时登录成功，凭据已写入缓存文件：{get_cache_path()}")
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


async def _close_current_client() -> None:
    """关闭当前临时事件循环的请求客户端会话，避免 Unclosed session 告警。"""
    try:
        await get_client().close()
    except Exception:
        pass


def _show_qrcode(config: pytest.Config, login: QrCodeLogin) -> None:
    """在终端展示 ASCII 二维码；终端编码不支持时回退提示 TEMP 下的二维码图片。"""
    writer = config.get_terminal_writer()
    if writer is None:
        raise _LoginAbort("当前终端不可用，无法展示二维码")
    try:
        for line in login.get_qrcode_terminal().splitlines():
            writer.line(line)
        writer.line("请使用哔哩哔哩客户端扫描上方二维码登录（过期自动更换，连续 3 次超时后中止）")
    except UnicodeEncodeError:
        writer.line(f"当前终端无法显示二维码字符，请改扫图片：{Path(tempfile.gettempdir()) / 'qrcode.png'}")


async def _qrcode_login_flow(config: pytest.Config) -> Credential:
    """二维码扫码登录流程：生成 → 终端展示 → 轮询，超时自动续期（上限 3 次）。"""
    login = QrCodeLogin()
    timeout_count = 0
    try:
        await login.generate_qrcode()
        _show_qrcode(config, login)
        last_event: QrCodeLoginEvents | None = None
        while True:
            event = await login.check_state()
            if event is QrCodeLoginEvents.DONE:
                return login.get_credential()
            if event is QrCodeLoginEvents.TIMEOUT:
                timeout_count += 1
                if timeout_count >= _QR_MAX_TIMEOUTS:
                    raise _LoginAbort(f"二维码连续 {timeout_count} 次超时未确认")
                _notify(config, "二维码已过期，正在生成新的二维码，请重新扫码……")
                await login.generate_qrcode()
                _show_qrcode(config, login)
                last_event = None
                continue
            if event is QrCodeLoginEvents.CONF and last_event is not QrCodeLoginEvents.CONF:
                _notify(config, "已扫码，请在手机上确认登录……")
            last_event = event
            await asyncio.sleep(_QR_POLL_INTERVAL)
    finally:
        await _close_current_client()


async def _complete_geetest(config: pytest.Config, gt_type: GeetestType, started: list[Geetest]) -> Geetest:
    """生成极验验证并等待用户在浏览器完成，返回已完成的 Geetest 实例。"""
    geetest = Geetest()
    await geetest.generate_test(gt_type)
    geetest.start_geetest_server()
    started.append(geetest)
    _notify(config, f"请在浏览器打开并完成滑块验证：{geetest.get_geetest_server_url()}")
    # 完成标志由极验本地服务的 HTTP 线程置位，跨线程无法用 asyncio.Event 通知，只能轮询
    while not geetest.has_done():  # noqa: ASYNC110
        await asyncio.sleep(_GEETEST_POLL_INTERVAL)
    return geetest


async def _phone_login_flow(config: pytest.Config) -> Credential:
    """手机号短信验证码登录流程（含 LoginCheck 风控二次验证分支）。"""
    started_geetests: list[Geetest] = []
    try:
        country = _prompt(config, "地区码（回车默认 +86）：").strip() or "+86"
        number = _prompt(config, "手机号：").strip()
        if not number:
            raise _LoginAbort("未输入手机号")
        phone = PhoneNumber(number, country)
        geetest = await _complete_geetest(config, GeetestType.LOGIN, started_geetests)
        captcha_key = await send_sms(phone, geetest)
        _notify(config, "验证码短信已发送")
        code = _prompt(config, "短信验证码：").strip()
        if not code:
            raise _LoginAbort("未输入短信验证码")
        result = await login_with_sms(phone, code, captcha_key)
        if isinstance(result, LoginCheck):
            _notify(config, "账号触发风控二次验证，需要再完成一次短信验证")
            verify = await _complete_geetest(config, GeetestType.VERIFY, started_geetests)
            await result.send_sms(verify)
            _notify(config, "二次验证短信已发送")
            second_code = _prompt(config, "二次验证短信验证码：").strip()
            if not second_code:
                raise _LoginAbort("未输入二次验证码")
            return await result.complete_check(second_code)
        return result
    finally:
        for geetest in started_geetests:
            if geetest.thread is not None:
                try:
                    geetest.close_geetest_server()
                except Exception:
                    pass
        await _close_current_client()


def _run_temp_login(login_type: str, config: pytest.Config) -> Credential | None:
    """执行交互式临时登录；成功返回凭据，任何形式的中止 / 失败返回 None（不写缓存）。

    登录运行在独立的 asyncio.run 事件循环中（get_client 按循环维护会话池，
    临时循环关闭后不影响 pytest-asyncio 为各用例创建的循环）。
    """
    try:
        if login_type == "qrcode":
            return asyncio.run(_qrcode_login_flow(config))
        if login_type == "phone":
            return asyncio.run(_phone_login_flow(config))
        raise _LoginAbort(f"未知的登录方式：{login_type}")
    except _LoginAbort as exc:
        _notify(
            config,
            f"临时登录已中止（{exc}）：不写入缓存文件，需登录用例将按缓存 / 环境变量 / cookie 回退链处理",
            error=True,
        )
    except KeyboardInterrupt:
        _notify(
            config,
            "临时登录被用户中断：不写入缓存文件，需登录用例将按缓存 / 环境变量 / cookie 回退链处理",
            error=True,
        )
    except EOFError:
        _notify(
            config,
            "临时登录输入流已关闭（非交互终端？）：不写入缓存文件，需登录用例将按缓存 / 环境变量 / cookie 回退链处理",
            error=True,
        )
    except Exception as exc:
        _notify(
            config,
            f"临时登录失败（{type(exc).__name__}: {exc}）：不写入缓存文件，需登录用例将按缓存 / 环境变量 / cookie 回退链处理",
            error=True,
        )
    return None


async def _check_cache_valid(credential: Credential) -> bool:
    """check_valid 并在结束时关闭本循环的请求客户端会话。"""
    try:
        return await credential.check_valid()
    finally:
        await _close_current_client()


async def _refresh_credential(credential: Credential) -> None:
    """refresh 并在结束时关闭本循环的请求客户端会话。"""
    try:
        await credential.refresh()
    finally:
        await _close_current_client()


def _resolve_cache_usable_fields(config: pytest.Config) -> dict[str, str] | None:
    """对缓存凭据做联网校验与过期刷新；仅在 credential fixture 实际需要凭据时调用。

    Returns:
        dict[str, str] | None: 可用的缓存字段；缓存缺失 / 已清理 / 刷新失败时为 None（回退既有来源）

    Raises:
        pytest.skip: 缓存有效性无法验证（网络异常）时直接跳过需登录用例（保留缓存文件）
    """
    cached = _SESSION_STATE.cache_fields
    if cached is None:
        return None
    path = get_cache_path()
    credential = _build_credential(cached)
    try:
        valid = asyncio.run(_check_cache_valid(credential))
    except Exception as exc:
        _notify(
            config,
            f"提示：缓存凭据有效性验证失败（{type(exc).__name__}），保留缓存文件，本次跳过需登录用例",
        )
        pytest.skip("临时登录凭据缓存有效性无法验证（网络异常），跳过需登录用例")
    if valid:
        _notify(config, "提示：使用 TEMP 缓存的临时登录凭据（有效性校验通过）")
        return cached
    if not cached.get("ac_time_value"):
        path.unlink(missing_ok=True)
        warnings.warn(
            UserWarning("临时登录凭据已过期，且缓存缺少刷新材料（ac_time_value），已删除缓存文件"),
            stacklevel=2,
        )
        return None
    try:
        asyncio.run(_refresh_credential(credential))
    except Exception:
        path.unlink(missing_ok=True)
        warnings.warn(UserWarning("临时登录凭据已过期且刷新失败，已删除缓存文件"), stacklevel=2)
        return None
    refreshed = {
        key: value
        for key, value in _credential_to_fields(credential).items()
        if isinstance(value, str) and value
    }
    save_cache(refreshed, path)
    _notify(config, "提示：缓存凭据已过期，刷新成功并已回写缓存文件")
    return refreshed


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
        fields = merge_credential_values(_resolve_cache_usable_fields(config), _load_credential_values())
    if not all(fields.get(name) for name in REQUIRED_FIELDS):
        pytest.skip(
            "缺少登录凭据（--login 临时登录、TEMP 缓存、BILI_SESSDATA / BILI_CSRF / BILI_DEDEUSERID "
            "环境变量与 .bilibili.cookie 文件均不可用），跳过需登录用例"
        )
    return _build_credential(fields)
