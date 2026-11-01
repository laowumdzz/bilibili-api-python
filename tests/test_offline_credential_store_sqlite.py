# bilibili_api 凭据存储管理器（SQLiteCredentialStoreManager）离线测试
#
# 本文件属于无凭据快速路径（宪法 IV 离线层）：全部用例仅操作本地临时目录
# 文件与本地子进程，不触外网、不使用真实凭据、不改变任何账号状态。
# 覆盖：
# - US1 持久化：增删改查回环、auto_persist 语义、同进程与跨进程两级"重启"
#   恢复、乱序 uid 插入顺序（order_seq）、性能预算（SC-004）、单例与路径冲突
# - US2 落盘静态加密：零明文、透明回环、密钥自动生成、密钥丢失 / 损坏显式失败
# - US3 异常防御：库损坏 / 版本不匹配显式失败、uid 校验、persist 失败回滚、
#   跨事件循环防御、异常消息脱敏

from __future__ import annotations

import asyncio
from pathlib import Path
import sqlite3
import subprocess
import sys
import time

import pytest

from bilibili_api.exceptions import (
    ArgsException,
    CredentialStoreCorruptException,
    CredentialStoreVersionMismatchException,
)
from bilibili_api.utils._credential import Credential
from bilibili_api.utils.credential_store_sqlite import SQLiteCredentialStoreManager

# 仓库根目录：子进程以它为 cwd，保证 bilibili_api 可导入
_REPO_ROOT = Path(__file__).resolve().parents[1]

# 插入顺序跨进程验证用的乱序 uid 序列（先 300 后 5 后 42；uid 数值序 ≠ 插入序）
_ORDER_UIDS = (300, 5, 42)

# 性能预算（SC-004，宽上限防回归而非基准测试）
_PERF_ACCOUNT_COUNT = 50
_LOAD_BUDGET_SECONDS = 3.0
_SINGLE_OP_BUDGET_SECONDS = 1.0

# 跨进程脚本（SC-001）：两段独立进程模拟"写入 → 完全重启 → 读出"。
# 仅打印条数与布尔量，不打印任何凭据字段值（quickstart V2 口径）。
_SUBPROCESS_SCRIPT = r"""
import asyncio
import sys

from bilibili_api.utils._credential import Credential
from bilibili_api.utils.credential_store_sqlite import SQLiteCredentialStoreManager


class _SubStore(SQLiteCredentialStoreManager):
    pass


def _cred(uid):
    return Credential(
        sessdata="fake_sessdata_%d" % uid,
        bili_jct="fake_bili_jct_%d" % uid,
        buvid3="fake_buvid3_%d" % uid,
        buvid4="fake_buvid4_%d" % uid,
        dedeuserid=str(uid),
        ac_time_value="fake_ac_time_value_%d" % uid,
    )


def main():
    mode = sys.argv[1]
    db_path = sys.argv[2]
    key_path = sys.argv[3]

    async def run():
        store = _SubStore(db_path=db_path, key_path=key_path)
        try:
            if mode == "write":
                for uid in (300, 5, 42):
                    assert await store.add_credential(uid, _cred(uid)) is True
                print("WROTE", len(store), True)
            else:
                await store.load()
                uids = await store.get_all_uids()
                assert uids == [300, 5, 42], uids
                first = await store.get_credential()
                assert first is not None and first.dedeuserid == "300"
                for uid in uids:
                    cred = await store.get_credential(uid)
                    assert cred is not None
                    assert cred.sessdata == "fake_sessdata_%d" % uid
                    assert cred.get_cookies().get("bili_jct") == "fake_bili_jct_%d" % uid
                print("READ", len(uids), True)
        finally:
            await store.close()

    asyncio.run(run())


main()
"""


def _make_store_class() -> type[SQLiteCredentialStoreManager]:
    """
    生成独立的局部子类。

    基类单例按具体子类隔离（各子类自有 _instance），每个用例使用独立子类即
    获得独立单例，避免用例间单例与事件循环绑定互相污染（research.md D9）。

    Returns:
        type[SQLiteCredentialStoreManager]: 新的子类。
    """

    class _IsolatedStore(SQLiteCredentialStoreManager):
        pass

    return _IsolatedStore


def _clear_singleton(store_cls: type[SQLiteCredentialStoreManager]) -> None:
    """
    清除子类单例（同进程"重启"模拟的组成部分）。

    Args:
        store_cls (type[SQLiteCredentialStoreManager]): 目标子类。
    """
    if "_instance" in store_cls.__dict__:
        delattr(store_cls, "_instance")


def _force_stop_connection(store: SQLiteCredentialStoreManager) -> None:
    """
    强制停掉实例遗留的 aiosqlite 后台线程（测试兜底清理）。

    事件循环已关闭而连接未及 close() 时（如跨事件循环防御用例），aiosqlite
    的非 daemon 线程会阻塞进程退出；经其同步 stop() 兜底停止。

    Args:
        store (SQLiteCredentialStoreManager): 目标实例。
    """
    connection = store._connection
    if connection is not None:
        connection.stop()
        store._connection = None
        store._connection_loop = None


def _fake_credential(uid: int, suffix: str = "") -> Credential:
    """
    构造假凭据（离线测试专用，字段值均为可辨识假数据）。

    Args:
        uid (int): 用户 ID。
        suffix (str, optional): 字段值后缀，用于在同用例内区分不同凭据. Defaults to "".

    Returns:
        Credential: 假凭据实例。
    """
    tail = f"_{suffix}" if suffix else ""
    return Credential(
        sessdata=f"fake_sessdata_{uid}{tail}",
        bili_jct=f"fake_bili_jct_{uid}{tail}",
        buvid3=f"fake_buvid3_{uid}{tail}",
        buvid4=f"fake_buvid4_{uid}{tail}",
        dedeuserid=str(uid),
        ac_time_value=f"fake_ac_time_value_{uid}{tail}",
    )


def _run_subprocess_mode(mode: str, db_path: Path, key_path: Path) -> str:
    """
    以独立子进程执行写入或读出脚本（跨进程"完全重启"证明，SC-001）。

    Args:
        mode (str): "write"（写入 3 条乱序 uid 后退出）或 "read"（读出并断言）。
        db_path (Path): 数据库文件路径。
        key_path (Path): 密钥文件路径。

    Returns:
        str: 子进程 stdout。

    Raises:
        AssertionError: 子进程以非零状态退出。
    """
    completed = subprocess.run(
        [sys.executable, "-c", _SUBPROCESS_SCRIPT, mode, str(db_path), str(key_path)],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
        check=False,
    )
    assert completed.returncode == 0, f"子进程({mode})失败：{completed.stdout}\n{completed.stderr}"
    return completed.stdout


async def test_us1_add_get_cover_remove_miss(tmp_path: Path) -> None:
    """US1 ①：add/get 回环一致；同 uid 覆盖返回 False；remove 未命中返回 False。"""
    db = tmp_path / "credentials.db"
    key = tmp_path / "credentials.key"
    store_cls = _make_store_class()
    store = store_cls(db_path=db, key_path=key)
    try:
        cred = _fake_credential(1)
        assert await store.add_credential(1, cred) is True
        got = await store.get_credential(1)
        assert got is not None
        assert got.sessdata == cred.sessdata
        assert got.dedeuserid == "1"
        assert got.get_cookies().get("bili_jct") == cred.get_cookies().get("bili_jct")
        # 覆盖：同 uid 再添加返回 False，值为新凭据
        replacement = _fake_credential(1, suffix="new")
        assert await store.add_credential(1, replacement) is False
        got2 = await store.get_credential(1)
        assert got2 is not None
        assert got2.sessdata == replacement.sessdata
        # remove 未命中
        assert await store.remove_credential(999) is False
        assert len(store) == 1
        # remove 命中
        assert await store.remove_credential(1) is True
        assert await store.get_credential(1) is None
        assert len(store) == 0
    finally:
        await store.close()


async def test_us1_auto_persist_semantics(tmp_path: Path) -> None:
    """US1 ②：auto_persist=False 仅内存生效、存储文件不变；auto_persist=True 落盘。"""
    db = tmp_path / "credentials.db"
    key = tmp_path / "credentials.key"
    store_cls = _make_store_class()
    store = store_cls(db_path=db, key_path=key)
    try:
        assert await store.add_credential(1, _fake_credential(1)) is True
        snapshot = db.read_bytes()
        assert snapshot
        await store.add_credential(2, _fake_credential(2), auto_persist=False)
        assert db.read_bytes() == snapshot
        assert len(store) == 2
    finally:
        await store.close()
    _clear_singleton(store_cls)
    store2 = store_cls(db_path=db, key_path=key)
    try:
        await store2.load()
        assert await store2.get_credential(2) is None
        assert await store2.get_credential(1) is not None
        await store2.add_credential(2, _fake_credential(2), auto_persist=True)
    finally:
        await store2.close()
    _clear_singleton(store_cls)
    store3 = store_cls(db_path=db, key_path=key)
    try:
        await store3.load()
        assert len(store3) == 2
        got = await store3.get_credential(2)
        assert got is not None
        assert got.sessdata == "fake_sessdata_2"
    finally:
        await store3.close()


async def test_us1_same_process_restart_recovery(tmp_path: Path) -> None:
    """US1 ③a：清理单例后重建实例（同进程"重启"），全量恢复且插入序保持。"""
    db = tmp_path / "credentials.db"
    key = tmp_path / "credentials.key"
    store_cls = _make_store_class()
    store = store_cls(db_path=db, key_path=key)
    try:
        for uid in _ORDER_UIDS:
            assert await store.add_credential(uid, _fake_credential(uid)) is True
    finally:
        await store.close()
    _clear_singleton(store_cls)
    store2 = store_cls(db_path=db, key_path=key)
    try:
        await store2.load()
        assert len(store2) == len(_ORDER_UIDS)
        assert await store2.get_all_uids() == list(_ORDER_UIDS)
        first = await store2.get_credential()
        assert first is not None
        assert first.dedeuserid == str(_ORDER_UIDS[0])
        for uid in _ORDER_UIDS:
            cred = await store2.get_credential(uid)
            assert cred is not None
            assert cred.sessdata == f"fake_sessdata_{uid}"
        # 恢复后插入序延续：新添加者排在最后，get_credential(None) 仍为最早者
        assert await store2.add_credential(7, _fake_credential(7)) is True
        assert (await store2.get_all_uids())[-1] == 7
        first_after = await store2.get_credential()
        assert first_after is not None
        assert first_after.dedeuserid == "300"
    finally:
        await store2.close()


async def test_us1_cross_process_restart_recovery(tmp_path: Path) -> None:
    """US1 ③b：独立子进程两段式运行（写入退出 / 读出断言），SC-001 跨进程恢复。"""
    db = tmp_path / "credentials.db"
    key = tmp_path / "credentials.key"
    await asyncio.to_thread(_run_subprocess_mode, "write", db, key)
    assert db.read_bytes()
    output = await asyncio.to_thread(_run_subprocess_mode, "read", db, key)
    assert "True" in output


async def test_us1_insertion_order_persisted(tmp_path: Path) -> None:
    """US1 ④：乱序 uid（300→5→42）下 get_all_uids() 与 get_credential(None) 均按添加序。"""
    db = tmp_path / "credentials.db"
    key = tmp_path / "credentials.key"
    store_cls = _make_store_class()
    store = store_cls(db_path=db, key_path=key)
    try:
        for uid in _ORDER_UIDS:
            await store.add_credential(uid, _fake_credential(uid))
        assert await store.get_all_uids() == list(_ORDER_UIDS)
    finally:
        await store.close()
    _clear_singleton(store_cls)
    store2 = store_cls(db_path=db, key_path=key)
    try:
        await store2.load()
        assert await store2.get_all_uids() == list(_ORDER_UIDS)
        first = await store2.get_credential()
        assert first is not None
        assert first.dedeuserid == "300"
    finally:
        await store2.close()


async def test_us1_performance_budget(tmp_path: Path) -> None:
    """US1 ⑤：50 账号 load < 3 秒、单条增删 < 1 秒（SC-004，宽上限防回归）。"""
    db = tmp_path / "credentials.db"
    key = tmp_path / "credentials.key"
    store_cls = _make_store_class()
    store = store_cls(db_path=db, key_path=key)
    try:
        start = time.perf_counter()
        for uid in range(1, _PERF_ACCOUNT_COUNT + 1):
            await store.add_credential(uid, _fake_credential(uid))
        add_elapsed = time.perf_counter() - start
        assert add_elapsed < _PERF_ACCOUNT_COUNT * _SINGLE_OP_BUDGET_SECONDS
        assert len(store) == _PERF_ACCOUNT_COUNT
    finally:
        await store.close()
    _clear_singleton(store_cls)
    store2 = store_cls(db_path=db, key_path=key)
    try:
        start = time.perf_counter()
        await store2.load()
        assert time.perf_counter() - start < _LOAD_BUDGET_SECONDS
        assert len(store2) == _PERF_ACCOUNT_COUNT
        start = time.perf_counter()
        assert await store2.remove_credential(_PERF_ACCOUNT_COUNT) is True
        assert time.perf_counter() - start < _SINGLE_OP_BUDGET_SECONDS
    finally:
        await store2.close()


async def test_us1_singleton_and_path_conflict(tmp_path: Path) -> None:
    """US1 ⑥：同类二次实例化为同一对象；冲突路径抛 ArgsException（D8）。"""
    db = tmp_path / "credentials.db"
    key = tmp_path / "credentials.key"
    store_cls = _make_store_class()
    store = store_cls(db_path=db, key_path=key)
    try:
        assert store_cls() is store
        assert store_cls(db_path=db, key_path=key) is store
        with pytest.raises(ArgsException):
            store_cls(db_path=tmp_path / "other.db")
        with pytest.raises(ArgsException):
            store_cls(key_path=tmp_path / "other.key")
        # 不同子类是彼此独立的单例
        other_cls = _make_store_class()
        other_store = other_cls(db_path=db, key_path=key)
        assert other_store is not store
        await other_store.close()
    finally:
        await store.close()


async def test_us2_no_plaintext_on_disk(tmp_path: Path) -> None:
    """US2 ①：落盘内容零明文——6 个假字段值二进制检索 0 命中（SC-002）。"""
    uid = 777666555
    db = tmp_path / "credentials.db"
    key = tmp_path / "credentials.key"
    store_cls = _make_store_class()
    store = store_cls(db_path=db, key_path=key)
    try:
        await store.add_credential(uid, _fake_credential(uid))
    finally:
        await store.close()
    blob = db.read_bytes()
    # 结构存在性正对照：SQLite 文件头与每记录 BACS 魔数可见（内容不可读）
    assert b"SQLite format 3" in blob
    assert b"BACS" in blob
    for needle in (
        f"fake_sessdata_{uid}".encode(),
        f"fake_bili_jct_{uid}".encode(),
        f"fake_buvid3_{uid}".encode(),
        f"fake_buvid4_{uid}".encode(),
        f"fake_ac_time_value_{uid}".encode(),
        str(uid).encode("utf-8"),  # dedeuserid 以二进制整数落盘，ASCII 串不应出现
    ):
        assert needle not in blob, f"落盘内容出现明文：{needle!r}"


async def test_us2_transparent_roundtrip(tmp_path: Path) -> None:
    """US2 ②：加密对上层透明——重新 load 后逐字段与写入值一致。"""
    uid = 4242
    db = tmp_path / "credentials.db"
    key = tmp_path / "credentials.key"
    store_cls = _make_store_class()
    store = store_cls(db_path=db, key_path=key)
    try:
        await store.add_credential(uid, _fake_credential(uid))
    finally:
        await store.close()
    _clear_singleton(store_cls)
    store2 = store_cls(db_path=db, key_path=key)
    try:
        await store2.load()
        got = await store2.get_credential(uid)
        assert got is not None
        expected = _fake_credential(uid)
        assert got.sessdata == expected.sessdata
        assert got.bili_jct == expected.bili_jct
        assert got.buvid3 == expected.buvid3
        assert got.buvid4 == expected.buvid4
        assert got.dedeuserid == expected.dedeuserid
        assert got.ac_time_value == expected.ac_time_value
    finally:
        await store2.close()


async def test_us2_key_auto_generated(tmp_path: Path) -> None:
    """US2 ③：首次使用自动生成密钥文件（仅本地、随库同目录），PEM 且不含凭据值。"""
    uid = 5150
    db = tmp_path / "credentials.db"
    key = tmp_path / "credentials.key"
    assert not key.exists()
    store_cls = _make_store_class()
    store = store_cls(db_path=db, key_path=key)
    try:
        await store.add_credential(uid, _fake_credential(uid))
    finally:
        await store.close()
    assert key.exists()
    pem = key.read_bytes()
    assert pem.startswith(b"-----BEGIN")
    for needle in (f"fake_sessdata_{uid}", f"fake_bili_jct_{uid}", f"fake_ac_time_value_{uid}"):
        assert needle.encode("utf-8") not in pem


async def test_us2_key_missing_explicit_failure(tmp_path: Path) -> None:
    """US2 ④：密钥文件删除后 load 显式失败（消息含"重新添加账号"、不含凭据值），库文件不清空。"""
    uid = 6060
    db = tmp_path / "credentials.db"
    key = tmp_path / "credentials.key"
    store_cls = _make_store_class()
    store = store_cls(db_path=db, key_path=key)
    try:
        await store.add_credential(uid, _fake_credential(uid))
    finally:
        await store.close()
    _clear_singleton(store_cls)
    key.unlink()
    snapshot = db.read_bytes()
    store2 = store_cls(db_path=db, key_path=key)
    try:
        with pytest.raises(CredentialStoreCorruptException) as exc_info:
            await store2.load()
        message = str(exc_info.value)
        assert "密钥" in message
        assert "重新添加账号" in message
        assert f"fake_sessdata_{uid}" not in message
        assert f"fake_bili_jct_{uid}" not in message
        assert db.read_bytes() == snapshot
    finally:
        await store2.close()


async def test_us2_key_garbage_explicit_failure(tmp_path: Path) -> None:
    """US2 ⑤：密钥文件写为随机垃圾字节 → 显式失败、不静默重建。"""
    uid = 7070
    db = tmp_path / "credentials.db"
    key = tmp_path / "credentials.key"
    store_cls = _make_store_class()
    store = store_cls(db_path=db, key_path=key)
    try:
        await store.add_credential(uid, _fake_credential(uid))
    finally:
        await store.close()
    _clear_singleton(store_cls)
    garbage = b"\xde\xad\xbe\xef" * 32
    key.write_bytes(garbage)
    db_snapshot = db.read_bytes()
    store2 = store_cls(db_path=db, key_path=key)
    try:
        with pytest.raises(CredentialStoreCorruptException) as exc_info:
            await store2.load()
        assert f"fake_sessdata_{uid}" not in str(exc_info.value)
        assert key.read_bytes() == garbage
        assert db.read_bytes() == db_snapshot
    finally:
        await store2.close()


def _tamper_meta(db_path: Path, key: str, value: str) -> None:
    """
    以本地 sqlite3 连接篡改 meta 表指定键值（测试专用同步操作）。

    Args:
        db_path (Path): 数据库文件路径（须无活动连接）。
        key (str): meta 键名。
        value (str): 篡改后的值。
    """
    connection = sqlite3.connect(db_path)
    try:
        connection.execute("UPDATE meta SET value = ? WHERE key = ?", (value, key))
        connection.commit()
    finally:
        connection.close()


async def test_us3_corrupt_db_explicit_failure(tmp_path: Path) -> None:
    """US3 ①：库文件截断一半 / 覆写随机字节后 load 显式失败且不被静默清空或重建（FR-008）。"""
    uid = 8080
    db = tmp_path / "credentials.db"
    key = tmp_path / "credentials.key"
    store_cls = _make_store_class()
    store = store_cls(db_path=db, key_path=key)
    try:
        await store.add_credential(uid, _fake_credential(uid))
    finally:
        await store.close()
    _clear_singleton(store_cls)
    # 截断一半
    original = db.read_bytes()
    truncated = original[: len(original) // 2]
    db.write_bytes(truncated)
    store2 = store_cls(db_path=db, key_path=key)
    try:
        with pytest.raises(CredentialStoreCorruptException) as exc_info:
            await store2.load()
        assert f"fake_sessdata_{uid}" not in str(exc_info.value)
        assert db.read_bytes() == truncated
    finally:
        await store2.close()
    _clear_singleton(store_cls)
    # 随机字节覆写
    random_bytes = b"\x00\xffbird" * 37
    db.write_bytes(random_bytes)
    store3 = store_cls(db_path=db, key_path=key)
    try:
        with pytest.raises(CredentialStoreCorruptException):
            await store3.load()
        assert db.read_bytes() == random_bytes
    finally:
        await store3.close()


async def test_us3_store_format_mismatch(tmp_path: Path) -> None:
    """US3 ②：篡改 meta 的 store_format 值 → CredentialStoreCorruptException。"""
    uid = 9090
    db = tmp_path / "credentials.db"
    key = tmp_path / "credentials.key"
    store_cls = _make_store_class()
    store = store_cls(db_path=db, key_path=key)
    try:
        await store.add_credential(uid, _fake_credential(uid))
    finally:
        await store.close()
    _clear_singleton(store_cls)
    _tamper_meta(db, "store_format", "some-other-store")
    store2 = store_cls(db_path=db, key_path=key)
    try:
        with pytest.raises(CredentialStoreCorruptException):
            await store2.load()
    finally:
        await store2.close()


async def test_us3_schema_version_mismatch(tmp_path: Path) -> None:
    """US3 ③：schema_version 改为 "999" 与 "0" → 均抛 CredentialStoreVersionMismatchException（FR-012）。"""
    uid = 1010
    db = tmp_path / "credentials.db"
    key = tmp_path / "credentials.key"
    store_cls = _make_store_class()
    store = store_cls(db_path=db, key_path=key)
    try:
        await store.add_credential(uid, _fake_credential(uid))
    finally:
        await store.close()
    _clear_singleton(store_cls)
    for tampered_version in ("999", "0"):
        _tamper_meta(db, "schema_version", tampered_version)
        instance = store_cls(db_path=db, key_path=key)
        try:
            with pytest.raises(CredentialStoreVersionMismatchException) as exc_info:
                await instance.load()
            message = str(exc_info.value)
            assert tampered_version in message
            assert f"fake_sessdata_{uid}" not in message
        finally:
            await instance.close()
        _clear_singleton(store_cls)


async def test_us3_uid_dedeuserid_mismatch_no_record(tmp_path: Path) -> None:
    """US3 ④：uid 与 dedeuserid 不一致 → 基类 ValueError 原样传播且存储文件无新增记录。"""
    uid = 1
    db = tmp_path / "credentials.db"
    key = tmp_path / "credentials.key"
    store_cls = _make_store_class()
    store = store_cls(db_path=db, key_path=key)
    try:
        await store.add_credential(uid, _fake_credential(uid))
        snapshot = db.read_bytes()
        mismatched = Credential(sessdata="fake_sessdata_bad", bili_jct="fake_bili_jct_bad", dedeuserid="999")
        with pytest.raises(ValueError, match="不一致"):
            await store.add_credential(2, mismatched)
        assert db.read_bytes() == snapshot
        assert len(store) == 1
        assert await store.get_credential(999) is None
        # dedeuserid 缺失同样原样传播
        with pytest.raises(ValueError, match="缺少 dedeuserid"):
            await store.add_credential(3, Credential(sessdata="fake_sessdata_bad"))
        assert len(store) == 1
    finally:
        await store.close()


async def test_us3_persist_failure_rollback(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """US3 ⑤：persist 失败 → 原生 OSError 原样传播（不包装、不吞并）且内存态无未落盘残留（FR-004）。"""
    db = tmp_path / "credentials.db"
    key = tmp_path / "credentials.key"
    store_cls = _make_store_class()
    store = store_cls(db_path=db, key_path=key)
    try:
        await store.add_credential(1, _fake_credential(1))
        snapshot = db.read_bytes()

        async def boom(credentials: dict[int, Credential]) -> None:
            """模拟磁盘写入失败。"""
            raise OSError("模拟磁盘写入失败")

        # 变体 a：store_data 抛 OSError → 原样传播、内存回滚
        monkeypatch.setattr(store, "store_data", boom)
        with pytest.raises(OSError, match="模拟磁盘写入失败") as exc_info:
            await store.add_credential(2, _fake_credential(2))
        assert "模拟磁盘写入失败" in str(exc_info.value)
        assert len(store) == 1
        assert await store.get_credential(2) is None
        assert await store.get_credential(1) is not None
        assert db.read_bytes() == snapshot

        # 变体 b：数据库路径的父级为同名文件（不可写路径）→ mkdir 抛 FileExistsError(OSError)
        blocker = tmp_path / "blocker"
        blocker.write_bytes(b"not a directory")
        blocked_cls = _make_store_class()
        blocked = blocked_cls(db_path=blocker / "credentials.db", key_path=tmp_path / "blocked.key")
        with pytest.raises((FileExistsError, NotADirectoryError)):
            await blocked.add_credential(5, _fake_credential(5))
        assert len(blocked) == 0

        # 回滚后存储链路不受损：解除注入恢复正常写入
        monkeypatch.undo()
        assert await store.add_credential(2, _fake_credential(2)) is True
        assert len(store) == 2
    finally:
        await store.close()


async def test_us3_error_messages_sanitized(tmp_path: Path) -> None:
    """US3 ⑥：触发各类异常时消息不含任何假凭据值（脱敏总断言）。"""
    uid = 31337
    secrets = (
        f"fake_sessdata_{uid}",
        f"fake_bili_jct_{uid}",
        f"fake_buvid3_{uid}",
        f"fake_buvid4_{uid}",
        f"fake_ac_time_value_{uid}",
    )
    db = tmp_path / "credentials.db"
    key = tmp_path / "credentials.key"
    store_cls = _make_store_class()
    store = store_cls(db_path=db, key_path=key)
    try:
        await store.add_credential(uid, _fake_credential(uid))
    finally:
        await store.close()
    db_snapshot = db.read_bytes()
    key_snapshot = key.read_bytes()
    messages: list[str] = []

    # ① 库损坏
    _clear_singleton(store_cls)
    db.write_bytes(b"garbage-not-sqlite")
    instance = store_cls(db_path=db, key_path=key)
    try:
        with pytest.raises(CredentialStoreCorruptException) as exc_info:
            await instance.load()
        messages.append(str(exc_info.value))
    finally:
        await instance.close()
    db.write_bytes(db_snapshot)

    # ② 版本不匹配
    _clear_singleton(store_cls)
    _tamper_meta(db, "schema_version", "999")
    instance = store_cls(db_path=db, key_path=key)
    try:
        with pytest.raises(CredentialStoreVersionMismatchException) as exc_info:
            await instance.load()
        messages.append(str(exc_info.value))
    finally:
        await instance.close()
    db.write_bytes(db_snapshot)

    # ③ 库标识不符
    _clear_singleton(store_cls)
    _tamper_meta(db, "store_format", "some-other-store")
    instance = store_cls(db_path=db, key_path=key)
    try:
        with pytest.raises(CredentialStoreCorruptException) as exc_info:
            await instance.load()
        messages.append(str(exc_info.value))
    finally:
        await instance.close()
    db.write_bytes(db_snapshot)

    # ④ 密钥丢失
    _clear_singleton(store_cls)
    key.unlink()
    instance = store_cls(db_path=db, key_path=key)
    try:
        with pytest.raises(CredentialStoreCorruptException) as exc_info:
            await instance.load()
        messages.append(str(exc_info.value))
    finally:
        await instance.close()
    key.write_bytes(key_snapshot)

    # ⑤ persist 失败与 uid 不一致（内存态场景）
    _clear_singleton(store_cls)
    store2 = store_cls(db_path=db, key_path=key)

    async def boom(credentials: dict[int, Credential]) -> None:
        """模拟磁盘写入失败。"""
        raise OSError("模拟磁盘写入失败")

    try:
        await store2.load()
        mismatched = Credential(sessdata=f"fake_sessdata_{uid}", dedeuserid="999")
        with pytest.raises(ValueError, match="不一致") as exc_info:
            await store2.add_credential(2, mismatched)
        messages.append(str(exc_info.value))
        store2.store_data = boom
        with pytest.raises(OSError, match="模拟磁盘写入失败") as exc_info:
            await store2.add_credential(3, _fake_credential(3))
        messages.append(str(exc_info.value))
    finally:
        await store2.close()

    for message in messages:
        for secret in secrets:
            assert secret not in message, f"异常消息泄露凭据值：{message!r}"


def test_us3_cross_loop_defense(tmp_path: Path) -> None:
    """US3 ⑦：同一实例先后在两个事件循环中执行操作 → 第二次抛 ArgsException（FR-009 / D7）。"""
    db = tmp_path / "credentials.db"
    key = tmp_path / "credentials.key"
    store_cls = _make_store_class()
    store = store_cls(db_path=db, key_path=key)

    async def _second_load() -> None:
        await store.load()

    try:
        asyncio.run(store.load())
        with pytest.raises(ArgsException):
            asyncio.run(_second_load())
    finally:
        _force_stop_connection(store)
