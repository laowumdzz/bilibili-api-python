"""
bilibili_api.nonebot.adapters.bilibili_live.exception

适配器自有异常。

NoneBot 侧异常（`AdapterException` / `ActionFailed` / `ApiNotAvailable` /
`NetworkError`）直接复用 `nonebot.exception` 的定义，保证插件侧
`except` 判断与上游一致；库侧异常（凭据、网络、响应码）不在这里重复定义，
由业务代码直接透传 `bilibili_api.exceptions` 中的类型。
"""

from __future__ import annotations

from nonebot.exception import (  # re-export：公共 API 的一部分
    ActionFailed as BaseActionFailed,
)
from nonebot.exception import (
    AdapterException,
)
from nonebot.exception import (
    ApiNotAvailable as BaseApiNotAvailable,
)
from nonebot.exception import (
    NetworkError as BaseNetworkError,
)

__all__ = [
    "ActionFailed",
    "AdapterException",
    "ApiNotAvailable",
    "BilibiliLiveAdapterException",
    "InteractionEndException",
    "NetworkError",
]


class InteractionEndException(Exception):
    """开放平台互动玩法结束信号（本特性不产生，保留类型以兼容上游导入）。"""

    def __init__(self, game_id: str, timestamp: int) -> None:
        """
        Args:
            game_id (str): 玩法 id。
            timestamp (int): 结束时间戳。
        """
        self.game_id = game_id
        self.timestamp = timestamp


class BilibiliLiveAdapterException(AdapterException):
    """适配器异常基类。"""

    def __init__(self) -> None:
        super().__init__("bilibili Live")


class ApiNotAvailable(BaseApiNotAvailable, BilibiliLiveAdapterException):
    """调用了适配器不提供（或私有）的 API。"""


class ActionFailed(BaseActionFailed, BilibiliLiveAdapterException):
    """远端接口返回业务错误码。"""

    code: int
    message: str

    def __init__(self, code: int, message: str) -> None:
        """
        Args:
            code (int): 业务错误码。
            message (str): 错误信息。
        """
        self.code = code
        self.message = message

    def __repr__(self) -> str:
        return f"ActionFailed(code={self.code!r}, message={self.message!r})"


class NetworkError(BilibiliLiveAdapterException, BaseNetworkError):
    """适配器视角的网络错误（库已统一包装为 `NetworkException`，此处保留类型）。"""
