"""
bilibili_api

哔哩哔哩的各种 API 调用便捷整合（视频、动态、直播等），另外附加一些常用的功能。

（功能子模块如 `bilibili_api.video`、`bilibili_api.user` 为惰性导入，首次访问时加载）
"""

from typing import TYPE_CHECKING
import importlib

# 注意：本文件导入顺序经过精心设计以避免循环引用，禁止 isort 重排（I001 已在 pyproject 中豁免）
from .utils.aid_bvid_transformer import aid2bvid, bvid2aid
from .utils.AsyncEvent import AsyncEvent
from .utils.danmaku import Danmaku, DmFontSize, DmMode, SpecialDanmaku
from .utils.geetest import Geetest, GeetestMeta, GeetestType
from .utils.network import (
    HEADERS,
    # api
    Api,
    BiliAPIClient,
    BiliAPIFile,
    # session
    BiliAPIResponse,
    BiliWsMsgType,
    # credential
    Credential,
    bili_simple_download,
    get_available_settings,
    get_bili_ticket,
    # anti spider
    get_buvid,
    get_client,
    get_registered_available_settings,
    get_registered_clients,
    get_selected_client,
    get_session,
    recalculate_wbi,
    refresh_bili_ticket,
    refresh_buvid,
    register_client,
    # log
    request_log,
    # settings
    request_settings,
    select_client,
    set_session,
    unregister_client,
)
from .utils.parse_link import ResourceType, parse_link
from .utils.picture import Picture
from .utils.short import get_real_url
from .utils.sync import sync
from .exceptions import (
    ApiException,
    ArgsException,
    CookiesRefreshException,
    CredentialNoAcTimeValueException,
    CredentialNoBiliJctException,
    CredentialNoBuvid3Exception,
    CredentialNoBuvid4Exception,
    CredentialNoDedeUserIDException,
    CredentialNoSessdataException,
    DanmakuClosedException,
    DynamicExceedImagesException,
    ExClimbWuzhiException,
    GeetestException,
    LiveException,
    LoginError,
    NetworkException,
    ResponseCodeException,
    ResponseException,
    StatementException,
    VideoUploadException,
    WbiRetryTimesExceedException,
)

# 功能子模块改为惰性导入（PEP 562）：首次访问时才加载，降低 import 时间与初始内存占用。
# 前提：子模块间的循环依赖已解耦（article↔note、dynamic↔article、dynamic↔opus、
# video↔bangumi、user↔channel_series 的顶层名称导入已改为函数内导入），
# 任一子模块均可作为首个入口独立加载。
_LAZY_SUBMODULES = [
    "activity",
    "app",
    "article",
    "article_category",
    "ass",
    "audio",
    "audio_uploader",
    "bangumi",
    "black_room",
    "channel_series",
    "cheese",
    "client",
    "comment",
    "creative_center",
    "dynamic",
    "emoji",
    "favorite_list",
    "festival",
    "game",
    "garb",
    "homepage",
    "hot",
    "interactive_video",
    "live",
    "live_area",
    "login_v2",
    "manga",
    "music",
    "note",
    "opus",
    "rank",
    "search",
    "session",
    "show",
    "topic",
    "user",
    "video",
    "video_tag",
    "video_uploader",
    "video_zone",
    "vote",
    "watchroom",
]

if TYPE_CHECKING:
    from . import (
        activity as activity,
        app as app,
        article as article,
        article_category as article_category,
        ass as ass,
        audio as audio,
        audio_uploader as audio_uploader,
        bangumi as bangumi,
        black_room as black_room,
        channel_series as channel_series,
        cheese as cheese,
        client as client,
        comment as comment,
        creative_center as creative_center,
        dynamic as dynamic,
        emoji as emoji,
        favorite_list as favorite_list,
        festival as festival,
        game as game,
        garb as garb,
        homepage as homepage,
        hot as hot,
        interactive_video as interactive_video,
        live as live,
        live_area as live_area,
        login_v2 as login_v2,
        manga as manga,
        music as music,
        note as note,
        opus as opus,
        rank as rank,
        search as search,
        session as session,
        show as show,
        topic as topic,
        user as user,
        video as video,
        video_tag as video_tag,
        video_uploader as video_uploader,
        video_zone as video_zone,
        vote as vote,
        watchroom as watchroom,
    )

BILIBILI_API_VERSION = "19.2.2"


def __register_all_clients():
    from .clients import ALL_PROVIDED_CLIENTS

    for module, client_name, settings in ALL_PROVIDED_CLIENTS[::-1]:
        try:
            importlib.import_module(module)
        except ModuleNotFoundError:
            continue
        client_module = importlib.import_module(name=f".clients.{client_name}", package="bilibili_api")
        client_class = getattr(client_module, client_name)
        register_client(module, client_class, settings)


__register_all_clients()


def __getattr__(name: str):
    """
    PEP 562 模块级 __getattr__：惰性导入功能子模块。

    Args:
        name (str): 属性名

    Returns:
        Any: 对应的子模块对象

    Raises:
        AttributeError: 属性不存在时
    """
    if name in _LAZY_SUBMODULES:
        module = importlib.import_module(f".{name}", __name__)
        globals()[name] = module  # 缓存，后续访问不再走 __getattr__
        return module
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    """
    补全惰性子模块的 dir() 输出。

    Returns:
        List[str]: 模块属性名列表
    """
    return sorted(set(globals().keys()) | set(_LAZY_SUBMODULES))


__all__ = [
    "BILIBILI_API_VERSION",
    "HEADERS",
    "Api",
    "ApiException",
    "ArgsException",
    "AsyncEvent",
    "BiliAPIClient",
    "BiliAPIFile",
    "BiliAPIResponse",
    "BiliWsMsgType",
    "CookiesRefreshException",
    "Credential",
    "CredentialNoAcTimeValueException",
    "CredentialNoBiliJctException",
    "CredentialNoBuvid3Exception",
    "CredentialNoBuvid4Exception",
    "CredentialNoDedeUserIDException",
    "CredentialNoSessdataException",
    "Danmaku",
    "DanmakuClosedException",
    "DmFontSize",
    "DmMode",
    "DynamicExceedImagesException",
    "ExClimbWuzhiException",
    "Geetest",
    "GeetestException",
    "GeetestMeta",
    "GeetestType",
    "LiveException",
    "LoginError",
    "NetworkException",
    "Picture",
    "ResourceType",
    "ResponseCodeException",
    "ResponseException",
    "SpecialDanmaku",
    "StatementException",
    "VideoUploadException",
    "WbiRetryTimesExceedException",
    "activity",
    "aid2bvid",
    "app",
    "article",
    "article_category",
    "ass",
    "audio",
    "audio_uploader",
    "bangumi",
    "bili_simple_download",
    "black_room",
    "bvid2aid",
    "channel_series",
    "cheese",
    "client",
    "comment",
    "creative_center",
    "dynamic",
    "emoji",
    "favorite_list",
    "festival",
    "game",
    "garb",
    "get_available_settings",
    "get_bili_ticket",
    "get_buvid",
    "get_client",
    "get_real_url",
    "get_registered_available_settings",
    "get_registered_clients",
    "get_selected_client",
    "get_session",
    "homepage",
    "hot",
    "interactive_video",
    "live",
    "live_area",
    "login_v2",
    "manga",
    "music",
    "note",
    "opus",
    "parse_link",
    "rank",
    "recalculate_wbi",
    "refresh_bili_ticket",
    "refresh_buvid",
    "register_client",
    "request_log",
    "request_settings",
    "search",
    "select_client",
    "session",
    "set_session",
    "show",
    "sync",
    "topic",
    "unregister_client",
    "user",
    "video",
    "video_tag",
    "video_uploader",
    "video_zone",
    "vote",
    "watchroom",
]
