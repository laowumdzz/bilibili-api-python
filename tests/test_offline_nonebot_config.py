"""适配器配置校验的离线测试（T014 / T052，contracts/config.schema.md §3）。"""

from __future__ import annotations

import json

import pytest

from bilibili_api.clients.NoneBotClient import ensure_websocket_support
from bilibili_api.exceptions import ArgsException
from bilibili_api.nonebot.adapters.bilibili_live.accounts import build_pool_from_store
from bilibili_api.nonebot.adapters.bilibili_live.config import (
    MIGRATION_GUIDANCE,
    BotAccountConfig,
    NoneBotLiveConfig,
    parse_config,
)
from bilibili_api.utils.network import Credential
from tests.nonebot_fakes import FakeStore, HttpOnlyDriver


def credential(uid: int) -> Credential:
    return Credential(sessdata=f"sess-{uid}", bili_jct=f"jct-{uid}", dedeuserid=str(uid))


def test_accepts_array_object_and_json_string() -> None:
    """数组、对象与 JSON 字符串三种形态都接受。"""
    from_array = parse_config([{"uid": 10001, "room_ids": [544853]}])
    from_object = parse_config({"bots": [{"uid": 10001, "room_ids": [544853]}], "poll_interval": 30})
    from_string = parse_config(json.dumps([{"uid": 10001, "room_ids": [544853]}]))
    assert from_array.bots[0].uid == 10001
    assert from_object.poll_interval == 30
    assert from_string.bots[0].room_ids == [544853]


def test_defaults_and_override() -> None:
    """默认值与账号级覆盖生效。"""
    config = parse_config(
        {"bots": [{"uid": 1, "room_ids": [2]}, {"uid": 3, "room_ids": [4], "connect_timing": "auto"}]}
    )
    assert config.connect_timing == "on"
    assert config.poll_interval == 60
    assert config.min_poll_interval == 2
    assert config.max_rooms == 50
    assert config.max_concurrent_connects == 5
    assert config.resolve_connect_timing(config.bots[1]) == "auto"
    assert config.resolve_connect_timing(config.bots[0]) == "on"


@pytest.mark.parametrize("field_name", ["cookie", "sessdata", "bili_jct", "dedeuserid"])
def test_v01_cookie_config_rejected_with_migration(field_name: str) -> None:
    """V-01 / SC-011：上游式 cookie 配置启动失败并给出可执行迁移步骤。"""
    secret = "SECRET-VALUE-MUST-NOT-LEAK"
    with pytest.raises(ArgsException) as excinfo:
        parse_config([{"uid": 10001, "room_ids": [1], field_name: secret}])
    message = str(excinfo.value)
    assert "已改为 uid 引用" in message
    assert "add_credential" in message
    assert "BILIBILI_LIVE_BOTS" in message
    assert "README" in message
    assert secret not in message


def test_v01_migration_guidance_is_complete() -> None:
    """迁移文案同时给出写存储示例与 uid 引用示例。"""
    assert "SQLiteCredentialStoreManager" in MIGRATION_GUIDANCE
    assert "add_credential" in MIGRATION_GUIDANCE
    assert '"uid"' in MIGRATION_GUIDANCE


@pytest.mark.parametrize("field_name", ["access_key", "access_secret", "app_id", "identify_codes"])
def test_v02_open_platform_config_rejected(field_name: str) -> None:
    """V-02 / FR-018：开放平台字段显式拒绝。"""
    secret = "ACCESS-SECRET"
    with pytest.raises(ArgsException) as excinfo:
        parse_config([{"uid": 10001, "room_ids": [1], field_name: secret}])
    message = str(excinfo.value)
    assert "开放平台形态尚未支持" in message
    assert secret not in message


async def test_v03_missing_uid_lists_uids() -> None:
    """V-03：引用不在存储中的 uid 时列出缺失 uid。"""
    store = FakeStore({10001: credential(10001)})
    config = NoneBotLiveConfig.model_validate(
        {"bots": [{"uid": 10001, "room_ids": [1]}, {"uid": 10002, "room_ids": [2]}]}
    )
    with pytest.raises(ArgsException) as excinfo:
        await build_pool_from_store(store, config)  # type: ignore[arg-type]
    message = str(excinfo.value)
    assert "10002" in message
    assert "add_credential" in message


async def test_v03_pool_order_follows_store_insertion() -> None:
    """账号池顺序取自存储插入顺序，且忽略未配置账号。"""
    store = FakeStore({30003: credential(30003), 10001: credential(10001), 20002: credential(20002)})
    config = NoneBotLiveConfig.model_validate(
        {"bots": [{"uid": 20002, "room_ids": [1]}, {"uid": 10001, "room_ids": [2]}]}
    )
    pool = await build_pool_from_store(store, config)  # type: ignore[arg-type]
    assert pool.all_uids() == [10001, 20002]
    current = pool.current()
    assert current is not None
    assert current.uid == 10001


def test_v04_duplicate_uid() -> None:
    """V-04：同一 uid 重复声明。"""
    with pytest.raises(ArgsException) as excinfo:
        parse_config([{"uid": 7, "room_ids": [1]}, {"uid": 7, "room_ids": [2]}])
    assert "7" in str(excinfo.value)
    assert "重复" in str(excinfo.value)


def test_v05_room_scale() -> None:
    """V-05：去重后房间数超过上限。"""
    config = parse_config({"bots": [{"uid": 1, "room_ids": [1]}], "max_rooms": 50})
    config.check_room_scale(50)
    with pytest.raises(ArgsException) as excinfo:
        config.check_room_scale(53)
    message = str(excinfo.value)
    assert "53" in message
    assert "50" in message
    assert "3" in message


def test_v06_poll_interval_bounds() -> None:
    """V-06：轮询参数越界，错误文本含实际取值与允许范围。"""
    with pytest.raises(ArgsException) as low:
        parse_config({"bots": [{"uid": 1, "room_ids": [1]}], "min_poll_interval": 1})
    assert "min_poll_interval" in str(low.value)
    assert "2" in str(low.value)
    with pytest.raises(ArgsException) as order:
        parse_config({"bots": [{"uid": 1, "room_ids": [1]}], "poll_interval": 1, "min_poll_interval": 5})
    assert "poll_interval" in str(order.value)
    assert "min_poll_interval" in str(order.value)


def test_v10_driver_without_websocket() -> None:
    """V-10：驱动不支持 WebSocket 时启动期报错并给出驱动名。"""
    with pytest.raises(ArgsException) as excinfo:
        ensure_websocket_support(HttpOnlyDriver())
    message = str(excinfo.value)
    assert "http-only" in message
    assert "WebSocket" in message


def test_v11_concurrent_connects_bounds() -> None:
    """V-11：`max_concurrent_connects` 小于 1 或大于 `max_rooms`。"""
    with pytest.raises(ArgsException) as low:
        parse_config({"bots": [{"uid": 1, "room_ids": [1]}], "max_concurrent_connects": 0})
    assert "max_concurrent_connects" in str(low.value)
    assert "0" in str(low.value)
    with pytest.raises(ArgsException) as high:
        parse_config({"bots": [{"uid": 1, "room_ids": [1]}], "max_rooms": 3, "max_concurrent_connects": 4})
    assert "max_concurrent_connects" in str(high.value)
    assert "4" in str(high.value)


def test_invalid_room_id_names_field_and_value() -> None:
    """非法房间号：错误文本含字段名与非法值。"""
    with pytest.raises(ArgsException) as excinfo:
        parse_config([{"uid": 1, "room_ids": [0]}])
    message = str(excinfo.value)
    assert "room_ids" in message
    assert "0" in message


def test_unknown_field_rejected() -> None:
    """未知字段显式报错，不做隐式推断（FR-022）。"""
    with pytest.raises(ArgsException) as excinfo:
        parse_config([{"uid": 1, "room_ids": [1], "unexpected": True}])
    assert "unexpected" in str(excinfo.value)


def test_bot_account_timing_none_inherits() -> None:
    """`connect_timing=None` 表示继承全局值。"""
    bot = BotAccountConfig.model_validate({"uid": 1, "room_ids": [2]})
    assert bot.connect_timing is None
