"""bilibili_api._video_appeal — 视频投诉相关类型。"""
from enum import Enum

class DanmakuOperatorType(Enum):
    """
    弹幕操作枚举

    + DELETE - 删除弹幕
    + PROTECT - 保护弹幕
    + UNPROTECT - 取消保护弹幕
    """

class VideoAppealReasonType:
    """
    视频投诉原因枚举

    注意: 每一项均为函数，部分项有参数，没有参数的函数无需调用函数，直接传入即可，有参数的函数请调用结果之后传入。

    - ILLEGAL(): 违法违禁
    - PRON(): 色情
    - VULGAR(): 低俗
    - GAMBLED_SCAMS(): 赌博诈骗
    - VIOLENT(): 血腥暴力
    - PERSONAL_ATTACK(): 人身攻击
    - PLAGIARISM(bvid: str): 与站内其他视频撞车
    - BAD_FOR_YOUNGS(): 青少年不良信息
    - CLICKBAIT(): 不良封面/标题
    - POLITICAL_RUMORS(): 涉政谣言
    - SOCIAL_RUMORS(): 涉社会事件谣言
    - UNREAL_EVENT(): 虚假不实消息
    - OTHER(): 有其他问题
    - LEAD_WAR(): 引战
    - CANNOT_CHARGE(): 不能参加充电
    - UNREAL_COPYRIGHT(source: str): 转载/自制类型错误
    - ILLEGAL_POPULARIZE(): 违规推广
    - ILLEGAL_OTHER(): 其他不规范行为
    - DANGEROUS(): 危险行为
    - OTHER_NEW(): 其他
    - COOPERATE_INFRINGEMENT(): 企业商誉侵权
    - INFRINGEMENT(): 侵权申诉
    - VIDEO_INFRINGEMENT(): 盗搬稿件-路人举报
    - DISCOMFORT(): 观感不适
    - ILLEGAL_URL(): 违法信息外链
    """

    ILLEGAL = lambda: 2
    PRON = lambda: 3
    VULGAR = lambda: 4
    GAMBLED_SCAMS = lambda: 5
    VIOLENT = lambda: 6
    PERSONAL_ATTACK = lambda: 7
    BAD_FOR_YOUNGS = lambda: 10000
    CLICKBAIT = lambda: 10013
    POLITICAL_RUMORS = lambda: 10014
    SOCIAL_RUMORS = lambda: 10015
    UNREAL_EVENT = lambda: 10017
    OTHER = lambda: 1
    LEAD_WAR = lambda: 9
    CANNOT_CHARGE = lambda: 10
    ILLEGAL_POPULARIZE = lambda: 10018
    ILLEGAL_OTHER = lambda: 10019
    DANGEROUS = lambda: 10020
    OTHER_NEW = lambda: 10022
    COOPERATE_INFRINGEMENT = lambda: 10023
    INFRINGEMENT = lambda: 10024
    VIDEO_INFRINGEMENT = lambda: 10026
    DISCOMFORT = lambda: 10021
    ILLEGAL_URL = lambda: 10025

    @staticmethod
    def PLAGIARISM(bvid: str):
        """
        与站内其他视频撞车

        Args:
            bvid (str): 撞车对象
        """
        return {"tid": 8, "撞车对象": bvid}

    @staticmethod
    def UNREAL_COPYRIGHT(source: str):
        """
        转载/自制类型错误

        Args:
            source (str): 原创视频出处
        """
        return {"tid": 52, "出处": source}

