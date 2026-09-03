"""独立登录凭据脚本：扫码 / 短信交互登录并把凭据写入 TEMP 缓存。

既可作为命令行脚本独立运行（``uv run python scripts/login_and_cache.py <qrcode|phone>``），
也可作为模块被 ``tests/conftest.py`` 导入复用——登录与缓存逻辑的单一实现，
交互输出 / 输入经 notify / prompt 接缝注入（命令行用控制台缺省实现，pytest 用终端 writer 包装）。

缓存文件契约沿用 specs/001-pytest-temp-login/contracts/cache-file-format.md（本脚本不变更）；
行为契约见 specs/003-login-cache-script/contracts/（cli.md / module-api.md）。
"""

from pathlib import Path
import sys

# 允许 `python scripts/login_and_cache.py` 直接运行：项目根需在 sys.path 上才能解析 scripts 命名空间包
_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import argparse
import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field
import enum
import tempfile

from bilibili_api import Credential
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

# 纯缓存契约逻辑的单一实现：re-export 供调用方单点导入（specs/003 contracts/module-api.md）
from scripts._login_cache import (  # noqa: F401
    CACHE_FIELDS,
    CACHE_FILENAME,
    REQUIRED_FIELDS,
    CacheLoadResult,
    CacheStatus,
    encode_credential_cache,
    get_cache_path,
    load_cache,
    merge_credential_values,
    save_cache,
)

# 登录交互 I/O 接缝：命令行用下方控制台缺省实现，pytest 注入终端 writer 包装（conftest._notify / _prompt）
NotifyFn = Callable[..., None]  # notify(message, *, error=False)
PromptFn = Callable[[str], str]

# 二维码登录：轮询间隔（秒）与连续超时上限（达到即中止）
_QR_POLL_INTERVAL = 2.0
_QR_MAX_TIMEOUTS = 3

# 极验滑块完成状态的轮询间隔（秒）
_GEETEST_POLL_INTERVAL = 0.5


class _LoginAbort(Exception):
    """临时登录中止（用户中断 / 连续超时 / 流程失败），原因描述不含凭据值。"""


def _console_notify(message: str, *, error: bool = False) -> None:
    """控制台缺省输出：普通提示写 stdout，错误提示写 stderr。"""
    print(message, file=sys.stderr if error else sys.stdout, flush=True)


def _console_prompt(message: str) -> str:
    """控制台缺省输入：显示提示后读取一行；输入流不可用时抛出 EOFError。"""
    print(message, file=sys.stdout, flush=True)
    try:
        line = sys.stdin.readline()
    except OSError:
        original = sys.__stdin__
        if original is None:
            raise EOFError("stdin 不可用") from None
        line = original.readline()
    return line.rstrip("\r\n")


async def _close_current_client() -> None:
    """关闭当前临时事件循环的请求客户端会话，避免 Unclosed session 告警。"""
    try:
        await get_client().close()
    except Exception:
        pass


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


def _show_qrcode(notify: NotifyFn, login: QrCodeLogin) -> None:
    """经 notify 逐行输出 ASCII 二维码；终端编码不支持时回退提示 TEMP 下的二维码图片。"""
    try:
        for line in login.get_qrcode_terminal().splitlines():
            notify(line)
        notify("请使用哔哩哔哩客户端扫描上方二维码登录（过期自动更换，连续 3 次超时后中止）")
    except UnicodeEncodeError:
        notify(f"当前终端无法显示二维码字符，请改扫图片：{Path(tempfile.gettempdir()) / 'qrcode.png'}")


async def _qrcode_login_flow(notify: NotifyFn) -> Credential:
    """二维码扫码登录流程：生成 → 终端展示 → 轮询，超时自动续期（上限 3 次）。"""
    login = QrCodeLogin()
    timeout_count = 0
    try:
        await login.generate_qrcode()
        _show_qrcode(notify, login)
        last_event: QrCodeLoginEvents | None = None
        while True:
            event = await login.check_state()
            if event is QrCodeLoginEvents.DONE:
                return login.get_credential()
            if event is QrCodeLoginEvents.TIMEOUT:
                timeout_count += 1
                if timeout_count >= _QR_MAX_TIMEOUTS:
                    raise _LoginAbort(f"二维码连续 {timeout_count} 次超时未确认")
                notify("二维码已过期，正在生成新的二维码，请重新扫码……")
                await login.generate_qrcode()
                _show_qrcode(notify, login)
                last_event = None
                continue
            if event is QrCodeLoginEvents.CONF and last_event is not QrCodeLoginEvents.CONF:
                notify("已扫码，请在手机上确认登录……")
            last_event = event
            await asyncio.sleep(_QR_POLL_INTERVAL)
    finally:
        await _close_current_client()


async def _complete_geetest(notify: NotifyFn, gt_type: GeetestType, started: list[Geetest]) -> Geetest:
    """生成极验验证并等待用户在浏览器完成，返回已完成的 Geetest 实例。"""
    geetest = Geetest()
    await geetest.generate_test(gt_type)
    geetest.start_geetest_server()
    started.append(geetest)
    notify(f"请在浏览器打开并完成滑块验证：{geetest.get_geetest_server_url()}")
    # 完成标志由极验本地服务的 HTTP 线程置位，跨线程无法用 asyncio.Event 通知，只能轮询
    while not geetest.has_done():  # noqa: ASYNC110
        await asyncio.sleep(_GEETEST_POLL_INTERVAL)
    return geetest


async def _phone_login_flow(notify: NotifyFn, prompt: PromptFn) -> Credential:
    """手机号短信验证码登录流程（含 LoginCheck 风控二次验证分支）。"""
    started_geetests: list[Geetest] = []
    try:
        country = prompt("地区码（回车默认 +86）：").strip() or "+86"
        number = prompt("手机号：").strip()
        if not number:
            raise _LoginAbort("未输入手机号")
        phone = PhoneNumber(number, country)
        geetest = await _complete_geetest(notify, GeetestType.LOGIN, started_geetests)
        captcha_key = await send_sms(phone, geetest)
        notify("验证码短信已发送")
        code = prompt("短信验证码：").strip()
        if not code:
            raise _LoginAbort("未输入短信验证码")
        result = await login_with_sms(phone, code, captcha_key)
        if isinstance(result, LoginCheck):
            notify("账号触发风控二次验证，需要再完成一次短信验证")
            verify = await _complete_geetest(notify, GeetestType.VERIFY, started_geetests)
            await result.send_sms(verify)
            notify("二次验证短信已发送")
            second_code = prompt("二次验证短信验证码：").strip()
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


def run_temp_login(login_type: str, *, notify: NotifyFn, prompt: PromptFn) -> dict[str, str] | None:
    """
    执行交互式临时登录；成功立即写入缓存文件并返回凭据字段集合，任何中止 / 失败返回 None（不写缓存）。

    登录运行在独立的 asyncio.run 事件循环中（get_client 按循环维护会话池，
    临时循环关闭后不影响调用方后续创建的事件循环）。

    Args:
        login_type (str): 登录方式，"qrcode"（扫码）或 "phone"（短信验证码）
        notify (NotifyFn): 输出接缝，调用形态 notify(message, *, error=False)
        prompt (PromptFn): 输入接缝，显示提示后读取一行原始输入

    Returns:
        dict[str, str] | None: 成功时为非空凭据字段集合（已同步写入缓存文件）；中止 / 失败时为 None
    """
    try:
        if login_type == "qrcode":
            credential = asyncio.run(_qrcode_login_flow(notify))
        elif login_type == "phone":
            credential = asyncio.run(_phone_login_flow(notify, prompt))
        else:
            raise _LoginAbort(f"未知的登录方式：{login_type}")
    except _LoginAbort as exc:
        notify(
            f"临时登录已中止（{exc}）：不写入缓存文件，需登录用例将按缓存 / 环境变量 / cookie 回退链处理", error=True
        )
        return None
    except KeyboardInterrupt:
        notify("临时登录被用户中断：不写入缓存文件，需登录用例将按缓存 / 环境变量 / cookie 回退链处理", error=True)
        return None
    except EOFError:
        notify(
            "临时登录输入流已关闭（非交互终端？）：不写入缓存文件，需登录用例将按缓存 / 环境变量 / cookie 回退链处理",
            error=True,
        )
        return None
    except Exception as exc:
        notify(
            f"临时登录失败（{type(exc).__name__}: {exc}）：不写入缓存文件，需登录用例将按缓存 / 环境变量 / cookie 回退链处理",
            error=True,
        )
        return None
    fields = {
        key: value for key, value in _credential_to_fields(credential).items() if isinstance(value, str) and value
    }
    save_cache(fields)
    notify(f"临时登录成功，凭据已写入缓存文件：{get_cache_path()}")
    return fields


class CacheCheckStatus(enum.Enum):
    """缓存凭据校验 / 刷新结果的六种终态（语义见 specs/003 data-model.md E3）。"""

    NO_CACHE = "no_cache"  # 无缓存可用（入参为空）
    VALID = "valid"  # 联网校验通过，可直接使用
    REFRESHED = "expired_refreshed"  # 已过期，刷新成功并回写缓存
    EXPIRED_NO_MATERIAL = "expired_no_material"  # 已过期且缺 ac_time_value，缓存文件已删除
    REFRESH_FAILED = "refresh_failed"  # 已过期且刷新失败，缓存文件已删除
    NETWORK_ERROR = "network_error"  # 有效性无法验证（网络异常），缓存文件保留


@dataclass
class CacheCheckResult:
    """
    缓存凭据校验 / 刷新结果。

    Attributes:
        status (CacheCheckStatus): 结果终态
        fields (dict[str, str]): VALID / REFRESHED 时的可用凭据字段集合，其余状态为空 dict
    """

    status: CacheCheckStatus
    fields: dict[str, str] = field(default_factory=dict)


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


def check_cache(fields: dict[str, str] | None, *, notify: NotifyFn) -> CacheCheckResult:
    """
    对缓存凭据做联网校验与过期刷新，返回富结果状态机；文件清理 / 回写在本函数内完成，
    调用方据 status 自行映射副作用（pytest 侧 skip / warn，见 contracts/module-api.md）。

    Args:
        fields (dict[str, str] | None): 缓存中读出的凭据字段集合；空值直接判 NO_CACHE（无网络请求）
        notify (NotifyFn): 输出接缝，调用形态 notify(message, *, error=False)

    Returns:
        CacheCheckResult: 终态与可用字段集合
    """
    if not fields:
        return CacheCheckResult(CacheCheckStatus.NO_CACHE)
    credential = _build_credential(fields)
    try:
        valid = asyncio.run(_check_cache_valid(credential))
    except Exception as exc:
        notify(f"提示：缓存凭据有效性验证失败（{type(exc).__name__}），保留缓存文件，本次跳过需登录用例")
        return CacheCheckResult(CacheCheckStatus.NETWORK_ERROR)
    if valid:
        notify("提示：使用 TEMP 缓存的临时登录凭据（有效性校验通过）")
        return CacheCheckResult(CacheCheckStatus.VALID, fields=fields)
    if not fields.get("ac_time_value"):
        get_cache_path().unlink(missing_ok=True)
        return CacheCheckResult(CacheCheckStatus.EXPIRED_NO_MATERIAL)
    try:
        asyncio.run(_refresh_credential(credential))
    except Exception:
        get_cache_path().unlink(missing_ok=True)
        return CacheCheckResult(CacheCheckStatus.REFRESH_FAILED)
    refreshed = {
        key: value for key, value in _credential_to_fields(credential).items() if isinstance(value, str) and value
    }
    save_cache(refreshed)
    notify("提示：缓存凭据已过期，刷新成功并已回写缓存文件")
    return CacheCheckResult(CacheCheckStatus.REFRESHED, fields=refreshed)


def main(argv: list[str] | None = None) -> int:
    """
    脚本命令行入口。

    Args:
        argv (list[str] | None): 命令行参数（不含程序名），缺省读取 sys.argv

    Returns:
        int: 0 登录成功；1 登录中止 / 失败；2 用法错误（由 argparse 直接退出）
    """
    parser = argparse.ArgumentParser(
        prog="login_and_cache",
        usage="login_and_cache <qrcode|phone>",
        description="交互式登录 B 站并把凭据写入 TEMP 缓存文件（bilibili_api_pytest_login.json），供测试运行复用",
    )
    parser.add_argument(
        "type",
        choices=("qrcode", "phone"),
        metavar="TYPE",
        help="登录方式：qrcode 扫码 / phone 短信验证码",
    )
    args = parser.parse_args(argv)
    fields = run_temp_login(args.type, notify=_console_notify, prompt=_console_prompt)
    return 0 if fields is not None else 1


if __name__ == "__main__":
    raise SystemExit(main())
