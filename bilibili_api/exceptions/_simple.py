"""bilibili_api.exceptions._simple — 简单异常集合"""

from .ApiException import ApiException

# ── 模式 A: 无参构造，硬编码 msg (9 个) ──────────────────────


class CredentialNoAcTimeValueException(ApiException):
    def __init__(self):
        super().__init__()
        self.msg = "未传入有效的 ac_time_value"


class CredentialNoBiliJctException(ApiException):
    def __init__(self):
        super().__init__()
        self.msg = "未传入有效的 bili_jct"


class CredentialNoBuvid3Exception(ApiException):
    def __init__(self):
        super().__init__()
        self.msg = "未传入有效的 buvid3"


class CredentialNoBuvid4Exception(ApiException):
    def __init__(self):
        super().__init__()
        self.msg = "未传入有效的 buvid4"


class CredentialNoDedeUserIDException(ApiException):
    def __init__(self):
        super().__init__()
        self.msg = "未传入有效的 dedeuserid"


class CredentialNoSessdataException(ApiException):
    def __init__(self):
        super().__init__()
        self.msg = "未传入有效的 sessdata"


class DanmakuClosedException(ApiException):
    def __init__(self):
        super().__init__()
        self.msg = "弹幕已关闭"


class DynamicExceedImagesException(ApiException):
    def __init__(self):
        super().__init__()
        self.msg = "动态携带图片数超过上限"


class WbiRetryTimesExceedException(ApiException):
    def __init__(self):
        super().__init__()
        self.msg = "WBI 重试次数超限"


# ── 模式 B: 有参构造 (7 个) ──────────────────────────────────


class ArgsException(ApiException):
    def __init__(self, msg="参数错误"):
        super().__init__(msg)


class InitialStateException(ApiException):
    def __init__(self, msg="未获取到初始状态"):
        super().__init__(msg)


class LiveException(ApiException):
    def __init__(self, msg="直播间异常"):
        super().__init__(msg)


class LoginError(ApiException):
    def __init__(self, msg="登录错误"):
        super().__init__(msg)


class ResponseException(ApiException):
    def __init__(self, msg="响应错误"):
        super().__init__(msg)


class StatementException(ApiException):
    def __init__(self, msg="声明错误"):
        super().__init__(msg)


class VideoUploadException(ApiException):
    def __init__(self, msg="上传错误"):
        super().__init__(msg)


# ── 模式 C: 有参默认文案 (1 个) ───────────────────────────


class GeetestException(ApiException):
    def __init__(self, msg: str = ""):
        super().__init__()
        self.msg = msg if msg else "验证码处理错误"
