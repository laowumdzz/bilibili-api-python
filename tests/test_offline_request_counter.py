# 请求计数 / 预算 / 412 判据 + cred2 清理残留判据离线单测（不触网、不依赖真实凭据）

import warnings

import pytest

from tests import conftest
from tests.conftest import _RequestCounter


class _FakeWriter:
    """记录终端输出的假 writer（区分普通行与红色错误行）。"""

    def __init__(self) -> None:
        self.lines: list[str] = []
        self.error_lines: list[str] = []

    def line(self, msg: str, **kwargs: object) -> None:
        self.lines.append(msg)
        if kwargs.get("red"):
            self.error_lines.append(msg)


class _FakeConfig:
    def __init__(self) -> None:
        self.writer = _FakeWriter()

    def get_terminal_writer(self) -> _FakeWriter:
        return self.writer


class _FakeSession:
    """duck-typed pytest.Session：提供 config 与可写 exitstatus。"""

    def __init__(self, exitstatus: pytest.ExitCode) -> None:
        self.config = _FakeConfig()
        self.exitstatus = exitstatus


def _clear_switches(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("BILI_COUNT_REQUESTS", "BILI_ABORT_ON_RISK", "BILI_REQUEST_BUDGET"):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture(autouse=True)
def _reset_cleanup_residues():
    conftest._CLEANUP_RESIDUES.clear()
    yield
    conftest._CLEANUP_RESIDUES.clear()


def test_counter_disabled_by_default(monkeypatch: pytest.MonkeyPatch):
    _clear_switches(monkeypatch)
    counter = _RequestCounter()
    assert counter.enabled is False
    assert counter.abort_on_risk is False
    assert counter.budget == 0
    assert counter.failure_reasons() == []


def test_budget_implies_counting_and_fails_when_exceeded(monkeypatch: pytest.MonkeyPatch):
    _clear_switches(monkeypatch)
    monkeypatch.setenv("BILI_REQUEST_BUDGET", "30")
    counter = _RequestCounter()
    assert counter.enabled is True
    assert "预算上限 30" in counter.summary_lines()[0]
    for _ in range(30):
        counter.record_request("https://api.bilibili.com/x/test")
    assert counter.failure_reasons() == []
    counter.record_request("https://api.bilibili.com/x/test")
    assert counter.failure_reasons() == ["总请求数 31 超出预算上限 30"]


def test_invalid_budget_raises_usage_error(monkeypatch: pytest.MonkeyPatch):
    _clear_switches(monkeypatch)
    monkeypatch.setenv("BILI_REQUEST_BUDGET", "abc")
    with pytest.raises(pytest.UsageError, match=r"BILI_REQUEST_BUDGET"):
        _RequestCounter()


def test_risk_count_fails_only_with_abort_switch(monkeypatch: pytest.MonkeyPatch):
    _clear_switches(monkeypatch)
    monkeypatch.setenv("BILI_COUNT_REQUESTS", "1")
    counter = _RequestCounter()
    counter.record_risk()
    assert counter.failure_reasons() == []

    monkeypatch.setenv("BILI_ABORT_ON_RISK", "1")
    aborting = _RequestCounter()
    aborting.record_risk()
    reasons = aborting.failure_reasons()
    assert len(reasons) == 1
    assert "412" in reasons[0]


def test_sessionfinish_marks_budget_overrun_as_failure(monkeypatch: pytest.MonkeyPatch):
    _clear_switches(monkeypatch)
    monkeypatch.setenv("BILI_REQUEST_BUDGET", "1")
    counter = _RequestCounter()
    counter.record_request("https://api.bilibili.com/x/test")
    counter.record_request("https://api.bilibili.com/x/test")
    monkeypatch.setattr(conftest, "_REQUEST_COUNTER", counter)
    session = _FakeSession(pytest.ExitCode.OK)

    conftest.pytest_sessionfinish(session, session.exitstatus)

    assert session.exitstatus == pytest.ExitCode.TESTS_FAILED
    assert any("超出预算上限" in line for line in session.config.writer.error_lines)


def test_sessionfinish_marks_412_as_failure_even_if_abort_was_swallowed(monkeypatch: pytest.MonkeyPatch):
    _clear_switches(monkeypatch)
    monkeypatch.setenv("BILI_COUNT_REQUESTS", "1")
    monkeypatch.setenv("BILI_ABORT_ON_RISK", "1")
    counter = _RequestCounter()
    counter.record_risk()
    monkeypatch.setattr(conftest, "_REQUEST_COUNTER", counter)
    session = _FakeSession(pytest.ExitCode.OK)

    conftest.pytest_sessionfinish(session, session.exitstatus)

    assert session.exitstatus == pytest.ExitCode.TESTS_FAILED
    assert any("412 类风控响应" in line for line in session.config.writer.lines)


def test_sessionfinish_keeps_nonzero_exitstatus(monkeypatch: pytest.MonkeyPatch):
    _clear_switches(monkeypatch)
    monkeypatch.setenv("BILI_REQUEST_BUDGET", "1")
    counter = _RequestCounter()
    counter.record_request("https://api.bilibili.com/x/test")
    counter.record_request("https://api.bilibili.com/x/test")
    monkeypatch.setattr(conftest, "_REQUEST_COUNTER", counter)
    session = _FakeSession(pytest.ExitCode.INTERRUPTED)

    conftest.pytest_sessionfinish(session, session.exitstatus)

    assert session.exitstatus == pytest.ExitCode.INTERRUPTED


def test_sessionfinish_prints_nothing_when_disabled(monkeypatch: pytest.MonkeyPatch):
    _clear_switches(monkeypatch)
    counter = _RequestCounter()
    monkeypatch.setattr(conftest, "_REQUEST_COUNTER", counter)
    session = _FakeSession(pytest.ExitCode.OK)

    conftest.pytest_sessionfinish(session, session.exitstatus)

    assert session.exitstatus == pytest.ExitCode.OK
    assert session.config.writer.lines == []


async def _cleanup_ok() -> None:
    return None


async def _cleanup_fail() -> None:
    raise RuntimeError("deliberate cleanup failure")


async def test_retry_cleanup_records_specific_residue():
    with pytest.warns(UserWarning, match=r"评论 rpid=1（oid=2）"):
        await conftest._retry_cleanup(
            "评论 rpid=1（oid=2）",
            _cleanup_fail,
            nodeid="tests/test_comment.py::test_b_comment_lifecycle",
            attempts=1,
        )

    assert len(conftest._CLEANUP_RESIDUES) == 1
    residue = conftest._CLEANUP_RESIDUES[0]
    assert residue.nodeid == "tests/test_comment.py::test_b_comment_lifecycle"
    assert residue.describe == "评论 rpid=1（oid=2）"
    assert isinstance(residue.last_exc, RuntimeError)


async def test_retry_cleanup_success_records_nothing():
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        await conftest._retry_cleanup(
            "视频点赞残留（aid=1）",
            _cleanup_ok,
            nodeid="tests/test_video.py::test_v_Video_like",
            attempts=1,
        )

    assert caught == []
    assert conftest._CLEANUP_RESIDUES == []


def test_sessionfinish_fails_on_cleanup_residue_without_counter(monkeypatch: pytest.MonkeyPatch):
    _clear_switches(monkeypatch)
    conftest._CLEANUP_RESIDUES.append(
        conftest._CleanupResidue(
            nodeid="tests/test_video.py::test_v_Video_like",
            describe="视频点赞残留（aid=1）",
            last_exc=RuntimeError("deliberate cleanup failure"),
        )
    )
    monkeypatch.setattr(conftest, "_REQUEST_COUNTER", _RequestCounter())
    session = _FakeSession(pytest.ExitCode.OK)

    conftest.pytest_sessionfinish(session, session.exitstatus)

    assert session.exitstatus == pytest.ExitCode.TESTS_FAILED
    error_output = "\n".join(session.config.writer.error_lines)
    assert "六态零残留" in error_output
    assert "test_v_Video_like" in error_output
    assert "视频点赞残留（aid=1）" in error_output


def test_sessionfinish_keeps_original_failure_with_cleanup_residue(monkeypatch: pytest.MonkeyPatch):
    _clear_switches(monkeypatch)
    conftest._CLEANUP_RESIDUES.append(
        conftest._CleanupResidue(
            nodeid="tests/test_video.py::test_zb_Video_toview_lifecycle",
            describe="稍后再看残留（aid=1）",
            last_exc=RuntimeError("deliberate cleanup failure"),
        )
    )
    monkeypatch.setattr(conftest, "_REQUEST_COUNTER", _RequestCounter())
    session = _FakeSession(pytest.ExitCode.TESTS_FAILED)

    conftest.pytest_sessionfinish(session, session.exitstatus)

    assert session.exitstatus == pytest.ExitCode.TESTS_FAILED
    assert any("稍后再看残留（aid=1）" in line for line in session.config.writer.error_lines)
