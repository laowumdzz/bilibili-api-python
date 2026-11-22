from __future__ import annotations

from enum import IntEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .._pydantic import field_before


class GuardLevel(IntEnum):
    """
    1: 总督
    2: 提督
    3: 舰长
    """

    No = 0
    Guard1 = 1
    Guard2 = 2
    Guard3 = 3


class Medal(BaseModel):
    """粉丝勋章。"""

    # 网页帧同时存在 `is_light`（上游字段名）与 `is_lighted`（规范别名）两种写法，
    # 双写法都接受；`is_lighted` 为规范名称（FR-010a）。
    model_config = ConfigDict(populate_by_name=True)

    name: str
    level: int
    is_light: bool = Field(..., alias="is_lighted")
    guard_level: GuardLevel = GuardLevel.No


class WebMedal(Medal):
    """网页粉丝勋章（含颜色与主播信息）。"""

    anchor_uid: int = Field(..., alias="target_id")
    anchor_room_id: int | None = Field(None, alias="anchor_roomid")
    anchor_name: str | None = Field(None, alias="anchor_uname")
    score: int | None = None
    color_start: int = Field(..., alias="medal_color_border")
    color_end: int = Field(..., alias="medal_color_end")
    color_border: int = Field(..., alias="medal_color_start")
    color: int = Field(..., alias="medal_color")
    guard_icon: str | None = None
    honor_icon: str | None = None


class User(BaseModel):
    """用户信息。"""

    uid: int
    name: str
    face: str = ""
    open_id: str = ""
    name_color: int | None = None
    is_admin: bool | None = None
    special: str | None = None
    medal: WebMedal | Medal | None = None


class SpecialGift(BaseModel):
    """特殊礼物条目。"""

    action: str
    content: str
    has_join: bool
    id: str
    num: int
    storm_gif: str
    time: int

    @field_before("has_join")
    @classmethod
    def validate(cls, value: Any) -> Any:
        """把原始帧归一为事件字段。"""
        return bool(value)


class Rank(BaseModel):
    """榜单条目。"""

    uid: int
    face: str
    score: str
    uname: str
    rank: int
    guard_level: GuardLevel = GuardLevel.No


class RankChangeMsg(BaseModel):
    """名次变化消息。"""

    msg: str
    rank: int


class BatchComboSend(BaseModel):
    """批量连击礼物信息。"""

    action: str
    batch_combo_id: str
    batch_combo_num: int
    gift_id: int
    gift_name: str
    gift_num: int
    uid: int
    uname: str


class ComboInfo(BaseModel):
    """连击信息。"""

    combo_base_num: int
    combo_count: int
    combo_id: str
    combo_timeout: int


class BlindGift(BaseModel):
    """盲盒礼物。"""

    blind_gift_id: int
    status: bool


class VoteOption(BaseModel):
    """投票选项"""

    idx: int
    """选项索引"""
    desc: str
    """选项内容"""
    cnt: int
    """票数"""
    percent: int
    """显示占比"""


class VoteCombo(BaseModel):
    """投票状态展示"""

    id: int
    """标识id，同VoteOption.idx"""
    status: int
    """状态，同InteractionVote.status"""
    content: str
    """投票选项内容"""
    cnt: str
    """弹幕计数"""
    guide: str
    """引导文本，通常为空字符串"""
    left_duration: int
    """剩余时间"""
    fade_duration: int
    """渐变持续时间"""
    prefix_icon: str
    """投票选项图标"""


class DanmakuCombo(BaseModel):
    """连续发送弹幕事件信息"""

    id: int
    """标识 ID"""
    status: int
    """状态"""
    content: str
    """重复的弹幕内容"""
    cnt: int
    """重复数量"""
    guide: str
    """标题词"""
    left_duration: int
    """左移时长"""
    fade_duration: int
    """淡化时长"""


# class SkinConfig(BaseModel):
#     """直播间皮肤配置"""
#     pass  # 待调查具体字段


# class RoomBlockUser(BaseModel):
#     """被禁言的用户信息"""
#     uid: int
#     """禁言用户 mid"""
#     uname: str
#     """禁言用户名"""
#     # dmscore: int  # 弹幕分数 - 待调查
#     # operator: int  # 操作者 - 待调查
