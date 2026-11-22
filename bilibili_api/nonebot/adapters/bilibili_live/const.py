"""
bilibili_api.nonebot.adapters.bilibili_live.const

端点引用与时间常量。

端点一律以 `bilibili_api/data/api/live.json` 的键名引用（经 `get_api("live")`
解析），不在适配器内硬编码 URL（research D5 / 宪章 II）。
"""

from __future__ import annotations

from typing import Any

from ....utils.utils import get_api

# 端点键名（`<section>.<key>`），与 data/api/live.json 的层级一一对应
API_GET_ROOM_INFO = "live_info.get_info"
API_GET_USER_ROOM_STATUS = "live_info.get_room_info_old"
API_GET_MASTER_INFO = "live_info.info"
API_SEND_DANMAKU = "operate.send_danmaku"
API_ADD_SILENT_USER = "operate.add_block"
API_GET_SILENT_USER_LIST = "info.black_list"
API_DEL_SILENT_USER = "silent_user_manage.del_room_block_user"
API_DANMU_INFO = "info.danmu_info"
API_ROOM_PLAY_INFO = "info.room_play_info"

# 时间常量（秒）
HEARTBEAT_INTERVAL = 30
"""弹幕 WebSocket 心跳发送间隔。"""

RECONNECT_INTERVAL = 5.0
"""重连退避基数（指数退避起始值）。"""

MAX_BACKOFF_INTERVAL = 300.0
"""重连退避上限。"""

HEARTBEAT_TIMEOUT = 90.0
"""超过该时长未收到心跳回复即判定连接失活。"""

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/102.0.0.0 Safari/537.36"
)
"""WebSocket 握手使用的 UA（保持与上游一致）。"""


def get_endpoint(key: str) -> dict[str, Any]:
    """
    按 `data/api/live.json` 的 `<section>.<key>` 键名取出端点定义。

    Args:
        key (str): 形如 `live_info.get_info` 的键名。

    Returns:
        dict[str, Any]: 端点定义（url / method / params / verify 等），可直接
        展开为 `Api(**endpoint)`。

    Raises:
        KeyError: 键名不存在于 live.json。
        bilibili_api.exceptions.StatementException: live.json 结构不符合预期。
    """
    section, name = key.split(".", 1)
    api: dict[str, Any] = get_api("live")
    return api[section][name]
