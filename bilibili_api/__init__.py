"""
bilibili_api

哔哩哔哩的各种 API 调用便捷整合（视频、动态、直播等），另外附加一些常用的功能。

 (默认已导入所有子模块，例如 `bilibili_api.video`, `bilibili_api.user`)
"""

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
from . import (
    activity,
    app,
    article,
    article_category,
    ass,
    audio,
    audio_uploader,
    bangumi,
    black_room,
    channel_series,
    cheese,
    client,
    comment,
    creative_center,
    dynamic,
    emoji,
    favorite_list,
    festival,
    game,
    garb,
    homepage,
    hot,
    interactive_video,
    live,
    live_area,
    login_v2,
    manga,
    music,
    note,
    opus,
    rank,
    search,
    session,
    show,
    topic,
    user,
    video,
    video_tag,
    video_uploader,
    video_zone,
    vote,
    watchroom,
)

BILIBILI_API_VERSION = "17.4.2"


def __register_all_clients():
    import importlib

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
