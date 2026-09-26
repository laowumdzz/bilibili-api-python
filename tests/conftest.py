"""pytest 全局配置与共享 fixtures。

离线用例（test_offline_*.py）不依赖本文件中的任何 fixture；
集成用例通过 credential fixture 获取登录态，凭据来源优先级：
--login 临时登录（实现委托 scripts/login_and_cache.py，本文件仅注入 pytest 终端 I/O 接缝）
> TEMP 缓存文件（自动校验 / 刷新）> BILI_* 环境变量 > 项目根目录的 .bilibili.cookie 文件。
全部来源不可用时 skip。

集成用例间隔由 BILI_RATELIMIT 控制，缺省 1.5 秒（单账号安全默认值）；
显式设置该环境变量（含 0 关闭限速）按设置值生效。
"""

import asyncio
from functools import partial
import json
import os
from pathlib import Path
import re
import sys
import time
from urllib.parse import urlsplit
import warnings

import pytest

from bilibili_api import Credential, request_settings
from scripts._login_cache import REQUIRED_FIELDS, CacheStatus, get_cache_path, load_cache, merge_credential_values
from scripts.login_and_cache import CacheCheckStatus, check_cache, run_temp_login

# 集成用例之间的最小间隔秒数（沿用旧运行器语义）。缺省 1.5 为单账号安全默认值
# （特性 007 FR-010 / research R3，与 CI 既有配置一致）；显式设置 BILI_RATELIMIT
# （含 0 关闭限速）按设置值生效，覆盖语义不变。
RATELIMIT = float(os.getenv("BILI_RATELIMIT", 1.5))

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

# cred 分层标记全集（特性 007，"恰好一层"判据）
_CRED_MARKERS = ("cred0", "cred1", "cred2", "cred3")


class _RiskControlAbort(KeyboardInterrupt):
    """BILI_ABORT_ON_RISK=1 时检测到 412 类风控响应，中止整个测试会话。

    继承 KeyboardInterrupt 以复用 pytest 的会话中断语义：库代码的
    `except Exception` 不会吞掉它，pytest 以 Interrupted 状态结束会话
    （exit code 2），sessionfinish 钩子照常执行、计数摘要照常输出。
    """


class _RequestCounter:
    """会话级请求计数器（contracts §6）：per-send 全计数 + 412 类风控响应统计。

    计数口径为服务端视角全计数：对实际发送的每次 HTTP 请求计 1（含重试
    每次尝试与反爬参数预取；凭据链校验 / 刷新请求计入总数），WebSocket
    连接建立计 1、连接内消息与心跳不计。仅输出计数与域名维度汇总，
    不输出任何凭据值。
    """

    def __init__(self) -> None:
        self.enabled = os.getenv("BILI_COUNT_REQUESTS") == "1"
        self.abort_on_risk = os.getenv("BILI_ABORT_ON_RISK") == "1"
        self.total = 0
        self.by_domain: dict[str, int] = {}
        self.risk_total = 0

    def record_request(self, url: str) -> None:
        """记录一次实际发送的请求（url 仅用于域名维度归并，不落日志）。"""
        self.total += 1
        domain = urlsplit(url).netloc or "unknown"
        self.by_domain[domain] = self.by_domain.get(domain, 0) + 1

    def record_risk(self) -> None:
        """记录一次 412 类风控响应（HTTP 412 状态码或 -352 等效错误码）。"""
        self.risk_total += 1

    def summary_lines(self) -> list[str]:
        """生成终端摘要输出行（总计数 + 域名维度汇总 + 风控计数单列）。"""
        lines = [f"请求计数摘要：总请求数 {self.total}"]
        for domain, count in sorted(self.by_domain.items(), key=lambda kv: (-kv[1], kv[0])):
            lines.append(f"  {domain}: {count}")
        lines.append(f"412 类风控响应（HTTP 412 / -352 等效码）：{self.risk_total}")
        return lines


_REQUEST_COUNTER: _RequestCounter | None = None


def _inspect_risk_response(resp: object, url: str) -> None:
    """检查单个响应是否为 412 类风控响应，必要时计数并按开关中止会话。

    判定：HTTP 状态码 412，或响应体 JSON 携带 -352 等效风控错误码。
    """
    counter = _REQUEST_COUNTER
    assert counter is not None
    is_risk = getattr(resp, "code", None) == 412
    if not is_risk:
        raw = getattr(resp, "raw", None)
        if raw:
            try:
                body = json.loads(raw)
            except (ValueError, UnicodeDecodeError):
                body = None
            is_risk = isinstance(body, dict) and body.get("code") == -352
    if not is_risk:
        return
    counter.record_risk()
    if counter.abort_on_risk:
        raise _RiskControlAbort(
            f"检测到 412 类风控响应（BILI_ABORT_ON_RISK=1），已中止整个测试会话：{url}"
        )


def _install_request_counter() -> None:
    """在请求客户端抽象层安装 per-send 计数与风控响应挂钩。

    对三个内置客户端的 request / ws_create / download_create 做类级包装：
    request 每次调用计 1 并检查风控响应（重试的每次尝试自然各计 1），
    ws_create（连接建立）与 download_create（每次下载）各计 1；
    连接内消息与心跳不经过这些方法，不计入。缺省（两个开关均未设置）
    不安装任何挂钩，零开销。
    """
    global _REQUEST_COUNTER
    counter = _RequestCounter()
    _REQUEST_COUNTER = counter
    if not counter.enabled and not counter.abort_on_risk:
        return
    import importlib

    # 逐客户端导入并包装：未安装的客户端库（如 curl_cffi）跳过即可
    client_specs = [
        ("bilibili_api.clients.AioHTTPClient", "AioHTTPClient"),
        ("bilibili_api.clients.CurlCFFIClient", "CurlCFFIClient"),
        ("bilibili_api.clients.HTTPXClient", "HTTPXClient"),
    ]

    def _extract_url(args: tuple[object, ...], kwargs: dict[str, object], index: int) -> str:
        url = kwargs.get("url")
        if url is None and len(args) > index:
            url = args[index]
        return str(url) if url else ""

    def _wrap(cls: type, name: str, *, url_index: int, inspect: bool) -> None:
        original = getattr(cls, name)
        if getattr(original, "_bili_count_wrapped", False):
            return

        async def wrapped(self: object, *args: object, **kwargs: object) -> object:
            counter.record_request(_extract_url(args, kwargs, url_index))
            resp = await original(self, *args, **kwargs)
            if inspect:
                _inspect_risk_response(resp, _extract_url(args, kwargs, url_index))
            return resp

        wrapped._bili_count_wrapped = True  # type: ignore[attr-defined]
        setattr(cls, name, wrapped)

    for module_name, class_name in client_specs:
        try:
            cls = getattr(importlib.import_module(module_name), class_name)
        except ImportError:
            continue
        _wrap(cls, "request", url_index=1, inspect=True)
        # ws_create / download_create 的 url 是 self 后第一个位置参数
        _wrap(cls, "ws_create", url_index=0, inspect=False)
        _wrap(cls, "download_create", url_index=0, inspect=False)


def _check_tier_marking(config: pytest.Config, items: list[pytest.Item]) -> None:
    """收集期漏标 / 错标防护（特性 007 FR-001，contracts §4）。

    经 item.fixturenames 传递闭包识别需凭据用例（闭包含模块级 fixture 对
    credential 的间接依赖）：未携带任一 cred 标记、或携带多个 cred 标记
    （违反"恰好一层"）均告警（消息含文件与用例名，不含凭据值）；
    BILI_STRICT_TIERS=1 时升级为收集错误中止会话。收集期实现保证
    --collect-only 下同样生效。
    """
    violations: list[str] = []
    for item in items:
        fixturenames = getattr(item, "fixturenames", None)
        if fixturenames is None or "credential" not in fixturenames:
            continue
        tiers = [name for name in _CRED_MARKERS if item.get_closest_marker(name) is not None]
        if not tiers:
            violations.append(f"{item.nodeid}: 需凭据用例未标注任何 cred 层级标记（cred0-cred3）")
        elif len(tiers) > 1:
            violations.append(f"{item.nodeid}: 携带多个 cred 层级标记（{'/'.join(tiers)}），违反恰好一层约束")
    if not violations:
        return
    if os.getenv("BILI_STRICT_TIERS") == "1":
        raise pytest.UsageError(
            "BILI_STRICT_TIERS=1 严格模式下发现 cred 分层标注问题（共 "
            f"{len(violations)} 处）：\n" + "\n".join(violations)
        )
    for violation in violations:
        warnings.warn(UserWarning(violation), stacklevel=2)


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


def _cred3_markexpr_present(markexpr: str | None) -> bool:
    """判断 -m 表达式是否含 token cred3（contracts §3：含 cred3 即保留，混排表达式同样生效）。"""
    if not markexpr:
        return False
    return re.search(r"\bcred3\b", markexpr) is not None


def _deselect_cred3(config: pytest.Config, items: list[pytest.Item]) -> None:
    """cred3 收集期剔除（特性 007 FR-003 / contracts §3）。

    -m 表达式不含 cred3 token 时（含无 -m 的默认运行），收集阶段即剔除
    （deselect，非 skip）全部 cred3 用例，并向终端输出一行剔除计数提示；
    显式点名（-m cred3 或混排表达式含 cred3）时保留。
    """
    if _cred3_markexpr_present(config.option.markexpr):
        return
    deselected = [item for item in items if item.get_closest_marker("cred3") is not None]
    if not deselected:
        return
    config.hook.pytest_deselected(items=deselected)
    items[:] = [item for item in items if item.get_closest_marker("cred3") is None]
    _notify(config, f"已排除 {len(deselected)} 个 cred3 高危用例（显式执行：pytest -m cred3）")


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """为离线文件之外的所有用例自动打 integration 标记，并执行 cred 分层收集期检查。"""
    for item in items:
        if not os.path.basename(str(item.path)).startswith("test_offline_"):
            item.add_marker(pytest.mark.integration)
    # 漏标 / 错标防护 MUST 先于 cred3 收集剔除执行，保证被剔除的 cred3 用例同样受检（FR-001 / T051）
    _check_tier_marking(config, items)
    # cred3 高危层默认收集即排除（FR-003 / contracts §3）
    _deselect_cred3(config, items)


def pytest_sessionstart(session: pytest.Session) -> None:
    """会话启动时装配凭据来源：--login 临时登录（委托脚本模块）+ TEMP 缓存文件的读取与清理。

    本钩子只做交互式登录与纯本地文件操作（读取 / 格式校验 / 删除），
    缓存凭据的联网校验与刷新延迟到 credential fixture 实际需要时进行，
    保证纯离线运行不产生任何网络请求。
    """
    config = session.config
    # 请求计数器 / 风控中止开关装配（缺省关闭，零开销）
    _install_request_counter()
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


def pytest_sessionfinish(session: pytest.Session, exitstatus: int | pytest.ExitCode) -> None:
    """会话结束时输出请求计数摘要（仅 BILI_COUNT_REQUESTS=1 启用时；不含任何凭据值）。"""
    counter = _REQUEST_COUNTER
    if counter is None or not counter.enabled:
        return
    for line in counter.summary_lines():
        _notify(session.config, line)


@pytest.fixture(scope="session", autouse=True)
def test_env() -> None:
    """全会话生效的请求超时设置（沿用旧运行器 request_settings.set_timeout(100)）。"""
    request_settings.set_timeout(100)


@pytest.fixture(autouse=True)
def ratelimit(request: pytest.FixtureRequest):
    """集成用例之间按 BILI_RATELIMIT 限速。

    缺省 1.5 秒（单账号安全默认值，FR-010）；显式设置 BILI_RATELIMIT
    （含 0 关闭限速）按设置值生效。仅对 integration 标记用例生效。
    """
    yield
    if RATELIMIT > 0 and request.node.get_closest_marker("integration"):
        time.sleep(RATELIMIT)


@pytest.fixture
def teardown_retry():
    """teardown 级清理义务辅助（特性 007 FR-006）。

    cred2 生命周期用例在用例内 try/finally 中调用：执行单个清理步骤，失败
    有限重试，重试耗尽后发出含具体残留物描述的 UserWarning，不掩盖用例
    原始失败（finally 中的清理失败只告警、不上抛）。

    Returns:
        Callable: ``async def _retry(describe: str, step: Callable[[], Awaitable[None]], attempts: int = 3)``，
        describe 为含具体残留物标识的描述（如资源 ID），step 为清理协程工厂。
    """

    async def _retry(describe: str, step, attempts: int = 3) -> None:
        last_exc: Exception | None = None
        for _ in range(attempts):
            try:
                await step()
                return
            except Exception as e:  # 清理兜底：任何清理失败都不得逃逸掩盖原始失败
                last_exc = e
                await asyncio.sleep(1.0)
        warnings.warn(
            UserWarning(f"清理步骤重试 {attempts} 次仍失败，可能残留：{describe}（最后错误：{last_exc!r}）"),
            stacklevel=2,
        )

    return _retry


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
