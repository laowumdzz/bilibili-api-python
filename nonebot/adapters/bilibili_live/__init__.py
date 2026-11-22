"""
nonebot.adapters.bilibili_live

兼容导入入口：全部为显式再导出，不含任何逻辑。
实现位于 `bilibili_api.nonebot.adapters.bilibili_live`，两条路径取到同一批对象。
"""

from __future__ import annotations

from bilibili_api.nonebot.adapters.bilibili_live import (
    ActionFailed as ActionFailed,
)
from bilibili_api.nonebot.adapters.bilibili_live import (
    Adapter as Adapter,
)
from bilibili_api.nonebot.adapters.bilibili_live import (
    AdapterException as AdapterException,
)
from bilibili_api.nonebot.adapters.bilibili_live import (
    AdminLevel as AdminLevel,
)
from bilibili_api.nonebot.adapters.bilibili_live import (
    ApiNotAvailable as ApiNotAvailable,
)
from bilibili_api.nonebot.adapters.bilibili_live import (
    AreaRankChangedEvent as AreaRankChangedEvent,
)
from bilibili_api.nonebot.adapters.bilibili_live import (
    Badge as Badge,
)
from bilibili_api.nonebot.adapters.bilibili_live import (
    BatchComboSend as BatchComboSend,
)
from bilibili_api.nonebot.adapters.bilibili_live import (
    BlindGift as BlindGift,
)
from bilibili_api.nonebot.adapters.bilibili_live import (
    ChangeRoomInfoEvent as ChangeRoomInfoEvent,
)
from bilibili_api.nonebot.adapters.bilibili_live import (
    ComboInfo as ComboInfo,
)
from bilibili_api.nonebot.adapters.bilibili_live import (
    DanmakuCombo as DanmakuCombo,
)
from bilibili_api.nonebot.adapters.bilibili_live import (
    DanmakuEvent as DanmakuEvent,
)
from bilibili_api.nonebot.adapters.bilibili_live import (
    Event as Event,
)
from bilibili_api.nonebot.adapters.bilibili_live import (
    Frame as Frame,
)
from bilibili_api.nonebot.adapters.bilibili_live import (
    Game as Game,
)
from bilibili_api.nonebot.adapters.bilibili_live import (
    Gender as Gender,
)
from bilibili_api.nonebot.adapters.bilibili_live import (
    GiftStarProcessEvent as GiftStarProcessEvent,
)
from bilibili_api.nonebot.adapters.bilibili_live import (
    GuardBuyEvent as GuardBuyEvent,
)
from bilibili_api.nonebot.adapters.bilibili_live import (
    GuardBuyToastEvent as GuardBuyToastEvent,
)
from bilibili_api.nonebot.adapters.bilibili_live import (
    GuardLevel as GuardLevel,
)
from bilibili_api.nonebot.adapters.bilibili_live import (
    HeartbeatEvent as HeartbeatEvent,
)
from bilibili_api.nonebot.adapters.bilibili_live import (
    HotRankChangedEvent as HotRankChangedEvent,
)
from bilibili_api.nonebot.adapters.bilibili_live import (
    HotRankSettlementEvent as HotRankSettlementEvent,
)
from bilibili_api.nonebot.adapters.bilibili_live import (
    InteractionDanmaku as InteractionDanmaku,
)
from bilibili_api.nonebot.adapters.bilibili_live import (
    InteractionFollow as InteractionFollow,
)
from bilibili_api.nonebot.adapters.bilibili_live import (
    InteractionGift as InteractionGift,
)
from bilibili_api.nonebot.adapters.bilibili_live import (
    InteractionLike as InteractionLike,
)
from bilibili_api.nonebot.adapters.bilibili_live import (
    InteractionShare as InteractionShare,
)
from bilibili_api.nonebot.adapters.bilibili_live import (
    InteractionVote as InteractionVote,
)
from bilibili_api.nonebot.adapters.bilibili_live import (
    LikeEvent as LikeEvent,
)
from bilibili_api.nonebot.adapters.bilibili_live import (
    LikeInfoUpdateEvent as LikeInfoUpdateEvent,
)
from bilibili_api.nonebot.adapters.bilibili_live import (
    LiveStatus as LiveStatus,
)
from bilibili_api.nonebot.adapters.bilibili_live import (
    MasterData as MasterData,
)
from bilibili_api.nonebot.adapters.bilibili_live import (
    MasterExp as MasterExp,
)
from bilibili_api.nonebot.adapters.bilibili_live import (
    MasterInfo as MasterInfo,
)
from bilibili_api.nonebot.adapters.bilibili_live import (
    MasterLevel as MasterLevel,
)
from bilibili_api.nonebot.adapters.bilibili_live import (
    Medal as Medal,
)
from bilibili_api.nonebot.adapters.bilibili_live import (
    Message as Message,
)
from bilibili_api.nonebot.adapters.bilibili_live import (
    MessageEvent as MessageEvent,
)
from bilibili_api.nonebot.adapters.bilibili_live import (
    MessageSegment as MessageSegment,
)
from bilibili_api.nonebot.adapters.bilibili_live import (
    MetaEvent as MetaEvent,
)
from bilibili_api.nonebot.adapters.bilibili_live import (
    NetworkError as NetworkError,
)
from bilibili_api.nonebot.adapters.bilibili_live import (
    NewPendants as NewPendants,
)
from bilibili_api.nonebot.adapters.bilibili_live import (
    NoticeEvent as NoticeEvent,
)
from bilibili_api.nonebot.adapters.bilibili_live import (
    OfficialVerify as OfficialVerify,
)
from bilibili_api.nonebot.adapters.bilibili_live import (
    OfficialVerifyType as OfficialVerifyType,
)
from bilibili_api.nonebot.adapters.bilibili_live import (
    OnlineRankCountEvent as OnlineRankCountEvent,
)
from bilibili_api.nonebot.adapters.bilibili_live import (
    OnlineRankEvent as OnlineRankEvent,
)
from bilibili_api.nonebot.adapters.bilibili_live import (
    OnlineRankTopEvent as OnlineRankTopEvent,
)
from bilibili_api.nonebot.adapters.bilibili_live import (
    OpenBot as OpenBot,
)
from bilibili_api.nonebot.adapters.bilibili_live import (
    OpenLiveEndEvent as OpenLiveEndEvent,
)
from bilibili_api.nonebot.adapters.bilibili_live import (
    OpenLiveStartEvent as OpenLiveStartEvent,
)
from bilibili_api.nonebot.adapters.bilibili_live import (
    OpenplatformOnlyEvent as OpenplatformOnlyEvent,
)
from bilibili_api.nonebot.adapters.bilibili_live import (
    PopularRankChangedEvent as PopularRankChangedEvent,
)
from bilibili_api.nonebot.adapters.bilibili_live import (
    Rank as Rank,
)
from bilibili_api.nonebot.adapters.bilibili_live import (
    RankChangeMsg as RankChangeMsg,
)
from bilibili_api.nonebot.adapters.bilibili_live import (
    Room as Room,
)
from bilibili_api.nonebot.adapters.bilibili_live import (
    RoomAdminEntranceEvent as RoomAdminEntranceEvent,
)
from bilibili_api.nonebot.adapters.bilibili_live import (
    RoomAdminRevokeEvent as RoomAdminRevokeEvent,
)
from bilibili_api.nonebot.adapters.bilibili_live import (
    RoomAdminsEvent as RoomAdminsEvent,
)
from bilibili_api.nonebot.adapters.bilibili_live import (
    RoomBlockMsgEvent as RoomBlockMsgEvent,
)
from bilibili_api.nonebot.adapters.bilibili_live import (
    RoomChangeEvent as RoomChangeEvent,
)
from bilibili_api.nonebot.adapters.bilibili_live import (
    RoomNews as RoomNews,
)
from bilibili_api.nonebot.adapters.bilibili_live import (
    RoomRealTimeMessageUpdateEvent as RoomRealTimeMessageUpdateEvent,
)
from bilibili_api.nonebot.adapters.bilibili_live import (
    RoomSilentOffEvent as RoomSilentOffEvent,
)
from bilibili_api.nonebot.adapters.bilibili_live import (
    RoomSilentOnEvent as RoomSilentOnEvent,
)
from bilibili_api.nonebot.adapters.bilibili_live import (
    RoomSkinMsgEvent as RoomSkinMsgEvent,
)
from bilibili_api.nonebot.adapters.bilibili_live import (
    SendGiftEvent as SendGiftEvent,
)
from bilibili_api.nonebot.adapters.bilibili_live import (
    SilentUser as SilentUser,
)
from bilibili_api.nonebot.adapters.bilibili_live import (
    SilentUserListData as SilentUserListData,
)
from bilibili_api.nonebot.adapters.bilibili_live import (
    SpecialGift as SpecialGift,
)
from bilibili_api.nonebot.adapters.bilibili_live import (
    SpecialGiftEvent as SpecialGiftEvent,
)
from bilibili_api.nonebot.adapters.bilibili_live import (
    StopLiveRoomListEvent as StopLiveRoomListEvent,
)
from bilibili_api.nonebot.adapters.bilibili_live import (
    StudioInfo as StudioInfo,
)
from bilibili_api.nonebot.adapters.bilibili_live import (
    SuperChatEvent as SuperChatEvent,
)
from bilibili_api.nonebot.adapters.bilibili_live import (
    User as User,
)
from bilibili_api.nonebot.adapters.bilibili_live import (
    UserEnterEvent as UserEnterEvent,
)
from bilibili_api.nonebot.adapters.bilibili_live import (
    UserFollowEvent as UserFollowEvent,
)
from bilibili_api.nonebot.adapters.bilibili_live import (
    UserRoomStatus as UserRoomStatus,
)
from bilibili_api.nonebot.adapters.bilibili_live import (
    UserShareEvent as UserShareEvent,
)
from bilibili_api.nonebot.adapters.bilibili_live import (
    VoteCombo as VoteCombo,
)
from bilibili_api.nonebot.adapters.bilibili_live import (
    VoteOption as VoteOption,
)
from bilibili_api.nonebot.adapters.bilibili_live import (
    WatchedChangeEvent as WatchedChangeEvent,
)
from bilibili_api.nonebot.adapters.bilibili_live import (
    WebBot as WebBot,
)
from bilibili_api.nonebot.adapters.bilibili_live import (
    WebLiveStartEvent as WebLiveStartEvent,
)
from bilibili_api.nonebot.adapters.bilibili_live import (
    WebOnlyEvent as WebOnlyEvent,
)

__all__ = [
    "ActionFailed",
    "Adapter",
    "AdapterException",
    "AdminLevel",
    "ApiNotAvailable",
    "AreaRankChangedEvent",
    "Badge",
    "BatchComboSend",
    "BlindGift",
    "ChangeRoomInfoEvent",
    "ComboInfo",
    "DanmakuCombo",
    "DanmakuEvent",
    "Event",
    "Frame",
    "Game",
    "Gender",
    "GiftStarProcessEvent",
    "GuardBuyEvent",
    "GuardBuyToastEvent",
    "GuardLevel",
    "HeartbeatEvent",
    "HotRankChangedEvent",
    "HotRankSettlementEvent",
    "InteractionDanmaku",
    "InteractionFollow",
    "InteractionGift",
    "InteractionLike",
    "InteractionShare",
    "InteractionVote",
    "LikeEvent",
    "LikeInfoUpdateEvent",
    "LiveStatus",
    "MasterData",
    "MasterExp",
    "MasterInfo",
    "MasterLevel",
    "Medal",
    "Message",
    "MessageEvent",
    "MessageSegment",
    "MetaEvent",
    "NetworkError",
    "NewPendants",
    "NoticeEvent",
    "OfficialVerify",
    "OfficialVerifyType",
    "OnlineRankCountEvent",
    "OnlineRankEvent",
    "OnlineRankTopEvent",
    "OpenBot",
    "OpenLiveEndEvent",
    "OpenLiveStartEvent",
    "OpenplatformOnlyEvent",
    "PopularRankChangedEvent",
    "Rank",
    "RankChangeMsg",
    "Room",
    "RoomAdminEntranceEvent",
    "RoomAdminRevokeEvent",
    "RoomAdminsEvent",
    "RoomBlockMsgEvent",
    "RoomChangeEvent",
    "RoomNews",
    "RoomRealTimeMessageUpdateEvent",
    "RoomSilentOffEvent",
    "RoomSilentOnEvent",
    "RoomSkinMsgEvent",
    "SendGiftEvent",
    "SilentUser",
    "SilentUserListData",
    "SpecialGift",
    "SpecialGiftEvent",
    "StopLiveRoomListEvent",
    "StudioInfo",
    "SuperChatEvent",
    "User",
    "UserEnterEvent",
    "UserFollowEvent",
    "UserRoomStatus",
    "UserShareEvent",
    "VoteCombo",
    "VoteOption",
    "WatchedChangeEvent",
    "WebBot",
    "WebLiveStartEvent",
    "WebOnlyEvent",
]
