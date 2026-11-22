"""
bilibili_api.nonebot.adapters.bilibili_live.config

适配器配置模型与校验。

账号唯一事实源是库的凭据存储：配置只以 `uid` 引用存储中的账号。上游 0.2.6
的 cookie 字符串与开放平台字段被**显式拒绝**，错误文本同时给出迁移指引
（contracts/config.schema.md §3）。所有校验在启动期完成，失败即报错，不做
静默降级（FR-022）。
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from ....exceptions import ArgsException
from ._pydantic import model_after, model_before

ConnectionTiming = Literal["on", "auto", "manual"]
"""连接时机取值：注册即连 / 开播才连 / 手动连。"""

MIGRATION_GUIDANCE = (
    "账号配置已改为 uid 引用。请先把账号写入库的凭据存储，再在 BILIBILI_LIVE_BOTS 中用 uid 引用：\n"
    "  from bilibili_api.utils.credential_store_sqlite import SQLiteCredentialStoreManager\n"
    "  from bilibili_api.utils.network import Credential\n"
    "  store = await SQLiteCredentialStoreManager.load()\n"
    "  await store.add_credential(\n"
    "      uid=<你的 uid>,\n"
    "      credential=Credential(sessdata=..., bili_jct=..., dedeuserid='<你的 uid>'),\n"
    "  )\n"
    "  # 然后把 BILIBILI_LIVE_BOTS 写成：\n"
    '  BILIBILI_LIVE_BOTS=\'[{"uid": <你的 uid>, "room_ids": [544853]}]\'\n'
    "迁移步骤详见 README 的「从上游适配器迁移」一节。"
)

OPEN_PLATFORM_GUIDANCE = (
    "开放平台形态尚未支持：本次只融合网页弹幕（WebBot）链路，开放平台 Bot、身份码与互动玩法"
    "已拆到后续特性。请删除 access_key / access_secret / app_id / identify_codes 字段，"
    "改用 uid + room_ids 的网页链路配置。"
)

_COOKIE_FIELDS = frozenset(
    {
        "cookie",
        "cookies",
        "sessdata",
        "bili_jct",
        "buvid3",
        "buvid4",
        "dedeuserid",
        "ac_time_value",
    }
)
_OPEN_PLATFORM_FIELDS = frozenset(
    {
        "access_key",
        "access_secret",
        "app_key",
        "app_secret",
        "app_id",
        "identify_codes",
        "identify_code",
    }
)


def _check_forbidden_fields(raw: Any) -> None:
    """
    校验原始配置中不出现凭据类与开放平台字段（V-01 / V-02）。

    Args:
        raw (Any): 尚未交给 pydantic 的原始配置项。

    Raises:
        ArgsException: 出现凭据类或开放平台字段；错误文本只含字段名与迁移指引，
            不回显字段值。
    """
    if not isinstance(raw, dict):
        return
    keys = {str(key).lower() for key in raw}
    if keys & _OPEN_PLATFORM_FIELDS:
        found = "、".join(sorted(keys & _OPEN_PLATFORM_FIELDS))
        raise ArgsException(f"配置出现开放平台字段 {found}。{OPEN_PLATFORM_GUIDANCE}")
    if keys & _COOKIE_FIELDS:
        found = "、".join(sorted(keys & _COOKIE_FIELDS))
        raise ArgsException(f"配置出现凭据类字段 {found}。{MIGRATION_GUIDANCE}")


def _format_validation_error(exc: ValidationError) -> str:
    """
    格式化 pydantic 校验错误，剔除可能回显输入值的部分。

    Args:
        exc (ValidationError): 校验错误。

    Returns:
        str: `字段路径: 原因` 形式的摘要。
    """
    parts: list[str] = []
    for error in exc.errors():
        location = ".".join(str(piece) for piece in error.get("loc", ()))
        message = str(error.get("msg", ""))
        parts.append(f"{location or '<root>'}: {message}")
    return "；".join(parts)


class BotAccountConfig(BaseModel):
    """一代账号的监听声明。"""

    model_config = ConfigDict(extra="forbid")

    uid: int = Field(..., gt=0)
    """凭据存储中的账号 uid，必须已存在于存储中。"""
    room_ids: list[int] = Field(..., min_length=1)
    """要监听的直播间号；长短号均可，启动时归一为真实房间号后去重。"""
    connect_timing: ConnectionTiming | None = None
    """连接时机；`None` 表示继承全局配置。"""

    @model_before
    @classmethod
    def _reject_forbidden(cls, data: Any) -> Any:
        _check_forbidden_fields(data)
        return data

    @model_after
    def _validate_room_ids(self) -> BotAccountConfig:
        for room_id in self.room_ids:
            if room_id <= 0:
                raise ValueError(f"room_ids 中出现非法房间号 {room_id}（uid={self.uid}），必须是正整数")
        return self


class NoneBotLiveConfig(BaseModel):
    """适配器配置根。"""

    model_config = ConfigDict(extra="forbid")

    bots: list[BotAccountConfig] = Field(..., min_length=1)
    """账号与房间声明；至少 1 项，同一 uid 不得重复。"""
    connect_timing: ConnectionTiming = "on"
    """全局默认连接时机，可被单项覆盖。"""
    poll_interval: float = 60
    """AUTO 每房间一轮的间隔（秒）。"""
    min_poll_interval: float = 2
    """同轮相邻请求的最小间隔（秒），硬下限 2。"""
    max_rooms: int = 50
    """全局唯一房间数上限（去重后计）。"""
    max_concurrent_connects: int = 5
    """同时在连（握手 / 鉴权中）的连接数上限。"""
    db_path: str | None = None
    """凭据存储数据库路径覆盖；`None` 使用库默认目录。"""
    key_path: str | None = None
    """凭据存储密钥路径覆盖；`None` 使用库默认目录。"""

    @model_before
    @classmethod
    def _reject_forbidden(cls, data: Any) -> Any:
        _check_forbidden_fields(data)
        return data

    @model_after
    def _validate(self) -> NoneBotLiveConfig:
        seen: set[int] = set()
        duplicated: list[int] = []
        for bot in self.bots:
            if bot.uid in seen:
                duplicated.append(bot.uid)
            seen.add(bot.uid)
        if duplicated:
            raise ValueError(f"同一 uid 被重复声明：{sorted(set(duplicated))}")
        if self.min_poll_interval < 2:
            raise ValueError(
                f"min_poll_interval 实际取值 {self.min_poll_interval}，小于硬下限 2；允许范围：min_poll_interval ≥ 2"
            )
        if self.poll_interval < self.min_poll_interval:
            raise ValueError(
                f"poll_interval 实际取值 {self.poll_interval}，小于 min_poll_interval "
                f"实际取值 {self.min_poll_interval}；允许范围：poll_interval ≥ min_poll_interval"
            )
        if self.max_rooms < 1:
            raise ValueError(f"max_rooms 实际取值 {self.max_rooms}；允许范围：max_rooms ≥ 1")
        if self.max_concurrent_connects < 1 or self.max_concurrent_connects > self.max_rooms:
            raise ValueError(
                f"max_concurrent_connects 实际取值 {self.max_concurrent_connects}，"
                f"max_rooms 实际取值 {self.max_rooms}；"
                "允许范围：1 ≤ max_concurrent_connects ≤ max_rooms"
            )
        return self

    def resolve_connect_timing(self, bot: BotAccountConfig) -> ConnectionTiming:
        """
        取某个账号实际生效的连接时机。

        Args:
            bot (BotAccountConfig): 账号声明。

        Returns:
            ConnectionTiming: 账号覆盖值，未设置时为全局默认值。
        """
        return bot.connect_timing if bot.connect_timing is not None else self.connect_timing

    def unique_display_room_ids(self) -> list[int]:
        """
        按声明顺序返回去重后的房间号（未归一）。

        Returns:
            list[int]: 去重后的房间号列表。
        """
        ordered: list[int] = []
        for bot in self.bots:
            for room_id in bot.room_ids:
                if room_id not in ordered:
                    ordered.append(room_id)
        return ordered

    def check_room_scale(self, room_count: int) -> None:
        """
        校验去重后的房间数量不超过 `max_rooms`（V-05）。

        Args:
            room_count (int): 去重后的真实房间数量。

        Raises:
            ArgsException: 超出上限；错误文本含实际数量、上限与超出数量。
        """
        if room_count > self.max_rooms:
            raise ArgsException(
                f"房间数量超出上限：实际 {room_count} 个，上限 max_rooms={self.max_rooms}，"
                f"超出 {room_count - self.max_rooms} 个。请减少 room_ids 或提高 max_rooms。"
            )


class Config(BaseModel):
    """NoneBot 插件配置载体（环境变量 `BILIBILI_LIVE_BOTS`）。"""

    bilibili_live_bots: list[dict[str, Any]] | dict[str, Any] | str = Field(default_factory=list)
    """原始配置；JSON 数组或含 `bots` 字段的对象，两种形态都接受。"""


def parse_config(raw: Any) -> NoneBotLiveConfig:
    """
    把原始配置归一为 `NoneBotLiveConfig`。

    Args:
        raw (Any): JSON 数组、含 `bots` 字段的对象、其 JSON 字符串，或已构造的配置。

    Returns:
        NoneBotLiveConfig: 校验通过的配置。

    Raises:
        ArgsException: 形态不合法或字段校验失败；错误文本指明具体项与修正方式。
    """
    if isinstance(raw, NoneBotLiveConfig):
        return raw
    if isinstance(raw, str):
        import json

        try:
            raw = json.loads(raw)
        except ValueError as e:
            raise ArgsException(f"BILIBILI_LIVE_BOTS 不是合法 JSON：{e}") from e
    if isinstance(raw, list):
        payload: dict[str, Any] = {"bots": raw}
    elif isinstance(raw, dict):
        _check_forbidden_fields(raw)
        payload = dict(raw)
    else:
        raise ArgsException(
            f"BILIBILI_LIVE_BOTS 必须是 JSON 数组或含 bots 字段的对象，当前类型为 {type(raw).__name__}。"
        )
    for item in payload.get("bots", []) if isinstance(payload.get("bots"), list) else []:
        _check_forbidden_fields(item)
    try:
        return NoneBotLiveConfig.model_validate(payload)
    except ValidationError as e:
        raise ArgsException(f"适配器配置校验失败：{_format_validation_error(e)}") from None
