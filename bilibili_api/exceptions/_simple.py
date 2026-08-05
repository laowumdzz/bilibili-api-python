"""bilibili_api.exceptions._simple — 简单异常集合"""

from .ApiException import ApiException

# ── 模式 A: 无参构造，硬编码 msg (9 个) ──────────────────────


class CredentialNoAcTimeValueException(ApiException):
    """凭据缺少有效的 ac_time_value 时抛出（刷新 cookies 需要该字段）。"""

    def __init__(self):
        """初始化异常并设置固定错误信息。"""
        super().__init__()
        self.msg = "未传入有效的 ac_time_value"


class CredentialNoBiliJctException(ApiException):
    """凭据缺少有效的 bili_jct（csrf token）时抛出，写操作均需要该字段。"""

    def __init__(self):
        """初始化异常并设置固定错误信息。"""
        super().__init__()
        self.msg = "未传入有效的 bili_jct"


class CredentialNoBuvid3Exception(ApiException):
    """凭据缺少有效的 buvid3（设备指纹）时抛出。"""

    def __init__(self):
        """初始化异常并设置固定错误信息。"""
        super().__init__()
        self.msg = "未传入有效的 buvid3"


class CredentialNoBuvid4Exception(ApiException):
    """凭据缺少有效的 buvid4（设备指纹）时抛出。"""

    def __init__(self):
        """初始化异常并设置固定错误信息。"""
        super().__init__()
        self.msg = "未传入有效的 buvid4"


class CredentialNoDedeUserIDException(ApiException):
    """凭据缺少有效的 dedeuserid（当前登录用户 ID）时抛出。"""

    def __init__(self):
        """初始化异常并设置固定错误信息。"""
        super().__init__()
        self.msg = "未传入有效的 dedeuserid"


class CredentialNoSessdataException(ApiException):
    """凭据缺少有效的 sessdata（登录会话）时抛出，登录态操作均需要该字段。"""

    def __init__(self):
        """初始化异常并设置固定错误信息。"""
        super().__init__()
        self.msg = "未传入有效的 sessdata"


class DanmakuClosedException(ApiException):
    """弹幕功能已关闭时抛出（如发送弹幕接口返回弹幕被关闭）。"""

    def __init__(self):
        """初始化异常并设置固定错误信息。"""
        super().__init__()
        self.msg = "弹幕已关闭"


class DynamicExceedImagesException(ApiException):
    """动态携带的图片数量超过上限时抛出。"""

    def __init__(self):
        """初始化异常并设置固定错误信息。"""
        super().__init__()
        self.msg = "动态携带图片数超过上限"


class WbiRetryTimesExceedException(ApiException):
    """WBI 签名校验失败重试次数超过上限时抛出。"""

    def __init__(self):
        """初始化异常并设置固定错误信息。"""
        super().__init__()
        self.msg = "WBI 重试次数超限"


# ── 模式 B: 有参构造 (7 个) ──────────────────────────────────


class ArgsException(ApiException):
    """调用参数错误时抛出（如缺少必要参数、参数组合不合法）。"""

    def __init__(self, msg="参数错误"):
        """
        Args:
            msg (str, optional): 错误信息. Defaults to "参数错误".
        """
        super().__init__(msg)


class InitialStateException(ApiException):
    """未能从页面获取到初始状态（__initial_state）时抛出。"""

    def __init__(self, msg="未获取到初始状态"):
        """
        Args:
            msg (str, optional): 错误信息. Defaults to "未获取到初始状态".
        """
        super().__init__(msg)


class LiveException(ApiException):
    """直播相关操作出错时抛出（如直播间不存在、操作被拒绝）。"""

    def __init__(self, msg="直播间异常"):
        """
        Args:
            msg (str, optional): 错误信息. Defaults to "直播间异常".
        """
        super().__init__(msg)


class LoginError(ApiException):
    """登录流程出错时抛出（如密码错误、二维码过期、短信验证失败）。"""

    def __init__(self, msg="登录错误"):
        """
        Args:
            msg (str, optional): 错误信息. Defaults to "登录错误".
        """
        super().__init__(msg)


class ResponseException(ApiException):
    """请求响应不符合预期时抛出（如无法解析响应内容）。"""

    def __init__(self, msg="响应错误"):
        """
        Args:
            msg (str, optional): 错误信息. Defaults to "响应错误".
        """
        super().__init__(msg)


class StatementException(ApiException):
    """API 定义语句（data/api/*.json）错误时抛出。"""

    def __init__(self, msg="声明错误"):
        """
        Args:
            msg (str, optional): 错误信息. Defaults to "声明错误".
        """
        super().__init__(msg)


class VideoUploadException(ApiException):
    """视频上传过程出错时抛出（如分片上传失败、提交被拒绝）。"""

    def __init__(self, msg="上传错误"):
        """
        Args:
            msg (str, optional): 错误信息. Defaults to "上传错误".
        """
        super().__init__(msg)


# ── 模式 C: 有参默认文案 (1 个) ───────────────────────────


class GeetestException(ApiException):
    """极验验证码处理出错时抛出（如验证失败、服务不可用）。"""

    def __init__(self, msg: str = ""):
        """
        Args:
            msg (str, optional): 错误信息，为空时使用默认文案. Defaults to "".
        """
        super().__init__()
        self.msg = msg if msg else "验证码处理错误"
