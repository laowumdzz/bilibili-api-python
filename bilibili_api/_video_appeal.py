"""bilibili_api._video_appeal — 视频投诉相关类型。"""

from enum import Enum


class DanmakuOperatorType(Enum):
    """
    弹幕操作枚举

    + DELETE - 删除弹幕
    + PROTECT - 保护弹幕
    + UNPROTECT - 取消保护弹幕
    """

    DELETE = 1
    PROTECT = 2
    UNPROTECT = 3


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

    def ILLEGAL():
        return 2

    def PRON():
        return 3

    def VULGAR():
        return 4

    def GAMBLED_SCAMS():
        return 5

    def VIOLENT():
        return 6

    def PERSONAL_ATTACK():
        return 7

    def BAD_FOR_YOUNGS():
        return 10000

    def CLICKBAIT():
        return 10013

    def POLITICAL_RUMORS():
        return 10014

    def SOCIAL_RUMORS():
        return 10015

    def UNREAL_EVENT():
        return 10017

    def OTHER():
        return 1

    def LEAD_WAR():
        return 9

    def CANNOT_CHARGE():
        return 10

    def ILLEGAL_POPULARIZE():
        return 10018

    def ILLEGAL_OTHER():
        return 10019

    def DANGEROUS():
        return 10020

    def OTHER_NEW():
        return 10022

    def COOPERATE_INFRINGEMENT():
        return 10023

    def INFRINGEMENT():
        return 10024

    def VIDEO_INFRINGEMENT():
        return 10026

    def DISCOMFORT():
        return 10021

    def ILLEGAL_URL():
        return 10025

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
