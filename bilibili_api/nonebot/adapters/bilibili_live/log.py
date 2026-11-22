"""
bilibili_api.nonebot.adapters.bilibili_live.log

适配器日志封装与凭据脱敏。

库既有的 `request_log` 会输出完整 `Credential` 与 cookie（research D12），
适配器 MUST NOT 开启；本模块只提供不含凭据字段值的摘要生成入口。
"""

from __future__ import annotations

from typing import Any

from nonebot.utils import logger_wrapper

log = logger_wrapper("bilibili Live")

_CREDENTIAL_FIELDS = (
    "sessdata",
    "bili_jct",
    "buvid3",
    "buvid4",
    "dedeuserid",
    "ac_time_value",
    "access_key",
    "access_secret",
    "app_secret",
    "cookie",
)


def redact_credential(value: Any) -> str:
    """
    生成可安全写入日志 / 异常文本的凭据摘要。

    摘要只允许出现账号 uid；任何凭据字段值（含 `Credential` 的
    `sessdata` / `bili_jct` / `buvid*` / `ac_time_value`）都不得输出。

    Args:
        value (Any): 凭据对象、uid、uid 字符串或 `None`。

    Returns:
        str: `uid=<uid>` 形式的安全摘要；无法解析出 uid 时为 `uid=unknown`。

    Note: 返回值会进入 NoneBot 的 loguru 风格日志，不能含尖括号，否则会被
    当作颜色标签解析。
    """
    if value is None:
        return "uid=none"
    if isinstance(value, bool):
        return "uid=unknown"
    if isinstance(value, int):
        return f"uid={value}"
    if isinstance(value, str):
        return f"uid={value}" if value.isdigit() else "uid=unknown"
    uid = getattr(value, "dedeuserid", None)
    if isinstance(uid, int):
        return f"uid={uid}"
    if isinstance(uid, str) and uid.isdigit():
        return f"uid={uid}"
    return "uid=unknown"
