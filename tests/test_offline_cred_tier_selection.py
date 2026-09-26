# cred 分层选择器离线单测（特性 007 T043）

# 宪法 IV 离线层边界：不触网、不依赖真实凭据；以 duck-typed 收集项与配置对象
# 直接驱动 conftest 的收集期判定函数（与真实 pytest 运行共用同一实现）。

import pytest

from tests.conftest import _check_tier_marking, _cred3_markexpr_present, _deselect_cred3


class _FakeHook:
    """记录 pytest_deselected 调用的假钩子。"""

    def __init__(self) -> None:
        self.deselected: list[object] = []

    def pytest_deselected(self, items: list[object]) -> None:
        self.deselected.extend(items)


class _FakeWriter:
    """记录终端输出的假 terminal writer。"""

    def __init__(self) -> None:
        self.lines: list[str] = []

    def line(self, msg: str, **kwargs: object) -> None:
        self.lines.append(msg)


class _FakeOption:
    def __init__(self, markexpr: str | None) -> None:
        self.markexpr = markexpr


class _FakeConfig:
    """duck-typed pytest.Config：提供 markexpr、hook 与 terminal writer。"""

    def __init__(self, markexpr: str | None = None) -> None:
        self.option = _FakeOption(markexpr)
        self.hook = _FakeHook()
        self.writer = _FakeWriter()

    def get_terminal_writer(self) -> _FakeWriter:
        return self.writer


class _FakeItem:
    """duck-typed pytest.Item：提供 nodeid、fixturenames 与 cred 标记。"""

    def __init__(self, nodeid: str, fixturenames: list[str], marker_names: list[str]) -> None:
        self.nodeid = nodeid
        self.fixturenames = fixturenames
        self._marker_names = marker_names

    def get_closest_marker(self, name: str) -> object | None:
        return object() if name in self._marker_names else None


def test_cred3_markexpr_token_detection():
    """markexpr 含 cred3 token 的判定（含混排表达式）。"""
    assert not _cred3_markexpr_present(None)
    assert not _cred3_markexpr_present("")
    assert not _cred3_markexpr_present("cred0 or cred1")
    assert not _cred3_markexpr_present("cred0 or cred2")
    assert _cred3_markexpr_present("cred3")
    assert _cred3_markexpr_present("cred0 or cred3")
    assert _cred3_markexpr_present("not cred3")


def test_cred3_deselection_four_quadrants():
    """带 / 不带 cred3 标记的收集项 × markexpr 含 / 不含 cred3 的四象限断言。"""
    cred3_item = _FakeItem("tests/test_x.py::test_cred3", ["credential"], ["cred3"])
    normal_item = _FakeItem("tests/test_x.py::test_normal", ["credential"], ["cred1"])

    # 象限 1：默认运行（无 markexpr）→ cred3 剔除、普通保留、终端输出剔除计数
    config = _FakeConfig(markexpr=None)
    items = [cred3_item, normal_item]
    _deselect_cred3(config, items)
    assert items == [normal_item]
    assert config.hook.deselected == [cred3_item]
    assert any("1 个 cred3" in line for line in config.writer.lines)

    # 象限 2：显式 -m cred3 → 全部保留
    config = _FakeConfig(markexpr="cred3")
    items = [cred3_item, normal_item]
    _deselect_cred3(config, items)
    assert items == [cred3_item, normal_item]
    assert config.hook.deselected == []

    # 象限 3：无 cred3 标记 + 无 markexpr → 全部保留
    config = _FakeConfig(markexpr=None)
    items = [normal_item]
    _deselect_cred3(config, items)
    assert items == [normal_item]
    assert config.hook.deselected == []

    # 象限 4：无 cred3 标记 + markexpr 不含 cred3 → 全部保留
    config = _FakeConfig(markexpr="cred0 or cred1")
    items = [normal_item]
    _deselect_cred3(config, items)
    assert items == [normal_item]
    assert config.hook.deselected == []


def test_cred3_kept_in_mixed_markexpr():
    """-m "cred0 or cred3" 混排表达式按"含 cred3 即保留"处理（contracts §3）。"""
    cred3_item = _FakeItem("tests/test_x.py::test_cred3", ["credential"], ["cred3"])
    config = _FakeConfig(markexpr="cred0 or cred3")
    items = [cred3_item]
    _deselect_cred3(config, items)
    assert items == [cred3_item]
    assert config.hook.deselected == []


def test_cred3_deselection_noop_without_cred3_items():
    """无 cred3 用例时不输出剔除提示、不触发 deselect 钩子。"""
    normal_item = _FakeItem("tests/test_x.py::test_normal", ["credential"], ["cred1"])
    config = _FakeConfig(markexpr=None)
    _deselect_cred3(config, [normal_item])
    assert config.hook.deselected == []
    assert config.writer.lines == []


def test_tier_marking_leak_warning():
    """需凭据用例零 cred 标记 → UserWarning（消息含文件与用例名，不含凭据值）。"""
    leaked = _FakeItem("tests/test_x.py::test_leaked", ["credential"], [])
    marked = _FakeItem("tests/test_x.py::test_marked", ["credential"], ["cred1"])
    anonymous = _FakeItem("tests/test_x.py::test_anon", [], [])
    config = _FakeConfig(markexpr=None)
    with pytest.warns(UserWarning, match=r"test_x\.py::test_leaked"):
        _check_tier_marking(config, [leaked, marked, anonymous])
    # 告警消息不含任何凭据字段值
    assert "SESSDATA" not in str(config.writer.lines)


def test_tier_marking_multi_marker_warning():
    """携带多个 cred 标记（违反恰好一层）→ UserWarning。"""
    multi = _FakeItem("tests/test_x.py::test_multi", ["credential"], ["cred0", "cred1"])
    config = _FakeConfig(markexpr=None)
    with pytest.warns(UserWarning, match=r"多个 cred 层级标记"):
        _check_tier_marking(config, [multi])


def test_tier_marking_silent_when_all_marked_once():
    """全部需凭据用例恰好一层时零告警。"""
    items = [
        _FakeItem("tests/test_x.py::test_a", ["credential"], ["cred0"]),
        _FakeItem("tests/test_x.py::test_b", ["credential"], ["cred1"]),
        _FakeItem("tests/test_x.py::test_c", ["credential"], ["cred2"]),
        _FakeItem("tests/test_x.py::test_d", ["credential"], ["cred3"]),
        _FakeItem("tests/test_x.py::test_anon", [], []),
    ]
    config = _FakeConfig(markexpr=None)
    _check_tier_marking(config, items)
    assert config.writer.lines == []


def test_tier_marking_strict_mode_raises(monkeypatch: pytest.MonkeyPatch):
    """BILI_STRICT_TIERS=1 严格模式下违规升级为收集错误中止会话（不触网、不依赖真实凭据）。"""
    monkeypatch.setenv("BILI_STRICT_TIERS", "1")
    leaked = _FakeItem("tests/test_x.py::test_leaked", ["credential"], [])
    with pytest.raises(pytest.UsageError, match=r"test_leaked"):
        _check_tier_marking(_FakeConfig(markexpr=None), [leaked])
