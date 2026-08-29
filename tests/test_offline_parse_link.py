# bilibili_api.utils.parse_link 离线单元测试
#
# 本文件属于无凭据快速路径：全部用例均为纯本地解析逻辑验证，
# 不触碰网络、不读取 BILI_* 环境变量、不依赖真实账号。
# 仅覆盖不发起请求的同步/纯本地分支；凡会触网的入口
# （get_real_url 短链展开、parse_video 的 get_info 探测等）一律不测。

from yarl import URL

from bilibili_api import Credential
from bilibili_api.article import Article, ArticleList
from bilibili_api.audio import Audio, AudioList
from bilibili_api.bangumi import Bangumi, Episode
from bilibili_api.black_room import BlackRoom
from bilibili_api.channel_series import ChannelSeries, ChannelSeriesType
from bilibili_api.cheese import CheeseVideo
from bilibili_api.dynamic import Dynamic
from bilibili_api.favorite_list import FavoriteList, FavoriteListType
from bilibili_api.game import Game
from bilibili_api.garb import DLC
from bilibili_api.live import LiveRoom
from bilibili_api.manga import Manga
from bilibili_api.note import Note
from bilibili_api.opus import Opus
from bilibili_api.topic import Topic
from bilibili_api.user import User
from bilibili_api.utils import parse_link as pl
from bilibili_api.utils.parse_link import ResourceType
from bilibili_api.video import Video

CREDENTIAL = Credential()


def u(link: str) -> URL:
    """将字符串转换为 yarl.URL 的简写。"""
    return URL(link)


# ---------------------------------------------------------------- 各类资源链接


def test_parse_bangumi():
    """md 链接应解析为 Bangumi，非番剧链接返回 -1。"""
    result = pl.parse_bangumi(u("https://www.bilibili.com/bangumi/media/md28229002/"), CREDENTIAL)
    assert isinstance(result, Bangumi)
    assert pl.parse_bangumi(u("https://www.bilibili.com/video/BV1xx411c7mD"), CREDENTIAL) == -1


async def test_parse_episode_ep_branch():
    """ep 前缀直接构造 Episode（不触网）；非播放页返回 -1。"""
    result = await pl.parse_episode(u("https://www.bilibili.com/bangumi/play/ep777777"), CREDENTIAL)
    assert isinstance(result, Episode)
    assert result.get_epid() == 777777
    assert await pl.parse_episode(u("https://www.bilibili.com/bangumi/media/md1"), CREDENTIAL) == -1


def test_parse_favorite_list():
    """medialist/detail 链接应解析为收藏夹。"""
    result = pl.parse_favorite_list(u("https://www.bilibili.com/medialist/detail/ml42"), CREDENTIAL)
    assert isinstance(result, FavoriteList)
    assert result.get_media_id() == 42
    assert pl.parse_favorite_list(u("https://www.bilibili.com/audio/au1"), CREDENTIAL) == -1


async def test_parse_cheese_video_ep_branch():
    """课程 ep 链接直接构造 CheeseVideo（不触网）。"""
    result = await pl.parse_cheese_video(u("https://www.bilibili.com/cheese/play/ep123"), CREDENTIAL)
    assert isinstance(result, CheeseVideo)
    assert await pl.parse_cheese_video(u("https://www.bilibili.com/cheese/other/ep123"), CREDENTIAL) == -1


def test_parse_audio_and_audio_list():
    """au 链接解析为音频、am 链接解析为歌单。"""
    audio = pl.parse_audio(u("https://www.bilibili.com/audio/au15664"), CREDENTIAL)
    assert isinstance(audio, Audio)
    assert audio.get_auid() == 15664

    audio_list = pl.parse_audio_list(u("https://www.bilibili.com/audio/am1024"), CREDENTIAL)
    assert isinstance(audio_list, AudioList)
    assert audio_list.get_amid() == 1024

    assert pl.parse_audio(u("https://www.bilibili.com/audio/am1"), CREDENTIAL) == -1
    assert pl.parse_audio_list(u("https://www.bilibili.com/audio/au1"), CREDENTIAL) == -1


def test_parse_article_and_article_list():
    """cv 专栏与 rl 文集链接解析。"""
    article = pl.parse_article(u("https://www.bilibili.com/read/cv1931892"), CREDENTIAL)
    assert isinstance(article, Article)
    assert article.get_cvid() == 1931892

    article_list = pl.parse_article_list(u("https://www.bilibili.com/read/readlist/rl77"), CREDENTIAL)
    assert isinstance(article_list, ArticleList)
    assert article_list.get_rlid() == 77

    assert pl.parse_article(u("https://www.bilibili.com/read/rl1"), CREDENTIAL) == -1


def test_parse_user():
    """空间链接解析为用户。"""
    user = pl.parse_user(u("https://space.bilibili.com/558830935"), CREDENTIAL)
    assert isinstance(user, User)
    assert user.get_uid() == 558830935
    assert pl.parse_user(u("https://www.bilibili.com/558830935"), CREDENTIAL) == -1


def test_parse_live():
    """直播链接解析为直播间。"""
    room = pl.parse_live(u("https://live.bilibili.com/21452505"), CREDENTIAL)
    assert isinstance(room, LiveRoom)
    assert room.room_display_id == 21452505
    assert pl.parse_live(u("https://www.bilibili.com/21452505"), CREDENTIAL) == -1


def test_parse_dynamic():
    """t.bilibili.com 动态链接解析。"""
    dynamic = pl.parse_dynamic(u("https://t.bilibili.com/767674573455884292"), CREDENTIAL)
    assert isinstance(dynamic, Dynamic)
    assert dynamic.get_dynamic_id() == 767674573455884292
    assert pl.parse_dynamic(u("https://www.bilibili.com/opus/1"), CREDENTIAL) == -1


def test_parse_black_room():
    """小黑屋链接解析（任意 host 下 path 匹配即可）。"""
    room = pl.parse_black_room(u("https://www.bilibili.com/blackroom/ban/12345"), CREDENTIAL)
    assert isinstance(room, BlackRoom)
    assert room.get_id() == 12345
    assert pl.parse_black_room(u("https://www.bilibili.com/blackroom/other/1"), CREDENTIAL) == -1


def test_parse_game():
    """biligame 详情页解析。"""
    game = pl.parse_game(u("https://www.biligame.com/detail/?id=102"), CREDENTIAL)
    assert isinstance(game, Game)
    assert pl.parse_game(u("https://www.biligame.com/detail/"), CREDENTIAL) == -1


def test_parse_topic():
    """话题详情页解析。"""
    topic = pl.parse_topic(u("https://www.bilibili.com/v/topic/detail/?topic_id=13"), CREDENTIAL)
    assert isinstance(topic, Topic)
    assert topic.get_topic_id() == 13
    assert pl.parse_topic(u("https://www.bilibili.com/v/topic/detail/"), CREDENTIAL) == -1


def test_parse_manga():
    """漫画详情页解析。"""
    manga = pl.parse_manga(u("https://manga.bilibili.com/detail/mc25717"), CREDENTIAL)
    assert isinstance(manga, Manga)
    assert pl.parse_manga(u("https://manga.bilibili.com/manga/mc25717"), CREDENTIAL) == -1


def test_parse_note():
    """公开笔记链接解析，缺少 cvid 返回 -1。"""
    note = pl.parse_note(u("https://www.bilibili.com/h5/note-app/view?cvid=21385583"), CREDENTIAL)
    assert isinstance(note, Note)
    assert note.get_cvid() == 21385583
    assert pl.parse_note(u("https://www.bilibili.com/h5/note-app/view"), CREDENTIAL) == -1


def test_parse_opus_dynamic():
    """图文链接解析为 Opus。"""
    opus = pl.parse_opus_dynamic(u("https://www.bilibili.com/opus/767674573455884292"), CREDENTIAL)
    assert isinstance(opus, Opus)
    assert opus.get_opus_id() == 767674573455884292
    assert pl.parse_opus_dynamic(u("https://www.bilibili.com/dynamic/1"), CREDENTIAL) == -1


def test_parse_garb():
    """收藏集活动页解析为 DLC。"""
    dlc = pl.parse_garb(u("https://www.bilibili.com/blackboard/activity-Mz9T5bO5Q3.html?id=154&type=dlc"), CREDENTIAL)
    assert isinstance(dlc, DLC)
    assert dlc.get_act_id() == 154
    assert pl.parse_garb(u("https://www.bilibili.com/blackboard/other.html?id=154"), CREDENTIAL) == -1


async def test_parse_festival_with_bvid():
    """festival 链接带 bvid 时直接构造 Video（不触网）。"""
    video = await pl.parse_festival(u("https://www.bilibili.com/festival/nianshizhiwang?bvid=BV1yt4y1Q7SS"), CREDENTIAL)
    assert isinstance(video, Video)
    assert video.get_bvid() == "BV1yt4y1Q7SS"
    # 无 bvid 且非 festival 路径时应返回 -1
    assert await pl.parse_festival(u("https://www.bilibili.com/other/path"), CREDENTIAL) == -1


# ---------------------------------------------------------------- 合集与列表


def test_parse_season_series_collectiondetail():
    """空间合集页（collectiondetail）解析为 SEASON 类合集。"""
    link = "https://space.bilibili.com/51537052/channel/collectiondetail?sid=22780&ctype=0"
    result = pl.parse_season_series(u(link), CREDENTIAL)
    assert isinstance(result, ChannelSeries)
    assert result.get_type() == ChannelSeriesType.SEASON
    assert result.get_id() == 22780


def test_parse_season_series_seriesdetail():
    """空间列表页（seriesdetail）解析为 SERIES 类列表。"""
    link = "https://space.bilibili.com/558830935/channel/seriesdetail?sid=2972810&ctype=0"
    result = pl.parse_season_series(u(link), CREDENTIAL)
    assert isinstance(result, ChannelSeries)
    assert result.get_type() == ChannelSeriesType.SERIES
    assert result.get_id() == 2972810


def test_parse_season_series_legacy_list_and_medialist():
    """主站旧版合集与新版合集链接解析。"""
    legacy = pl.parse_season_series(u("https://www.bilibili.com/list/660303135?sid=2908236"), CREDENTIAL)
    assert isinstance(legacy, ChannelSeries)
    assert legacy.get_type() == ChannelSeriesType.SERIES
    assert legacy.get_id() == 2908236

    medialist = pl.parse_season_series(
        u("https://www.bilibili.com/medialist/play/660303135?business=space&business_id=2908237"), CREDENTIAL
    )
    assert isinstance(medialist, ChannelSeries)
    assert medialist.get_id() == 2908237

    # uid 非法时返回 -1
    assert (
        pl.parse_season_series(u("https://space.bilibili.com/not_a_uid/channel/seriesdetail?sid=1"), CREDENTIAL) == -1
    )


def test_parse_season_series_root_path_returns_failed():
    """www.bilibili.com 根路径（无子路径段）应返回 -1 而非抛 IndexError。"""
    assert pl.parse_season_series(u("https://www.bilibili.com/"), CREDENTIAL) == -1


# ---------------------------------------------------------------- 空间收藏夹纯分支


async def test_parse_space_favorite_list_fid_branches():
    """favlist 链接的 fid/ctype 纯本地分支。"""
    # 纯数字 fid 无 ctype：视频收藏夹
    fav = await pl.parse_space_favorite_list(u("https://space.bilibili.com/1/favlist?fid=12345"), CREDENTIAL)
    assert isinstance(fav, tuple)
    assert fav[1] == ResourceType.FAVORITE_LIST
    assert fav[0].get_media_id() == 12345

    # ctype=11：视频收藏夹
    fav11 = await pl.parse_space_favorite_list(u("https://space.bilibili.com/1/favlist?fid=678&ctype=11"), CREDENTIAL)
    assert fav11[1] == ResourceType.FAVORITE_LIST
    assert fav11[0].get_media_id() == 678

    # ctype=21：合集（SEASON）
    season = await pl.parse_space_favorite_list(u("https://space.bilibili.com/1/favlist?fid=999&ctype=21"), CREDENTIAL)
    assert season[1] == ResourceType.CHANNEL_SERIES
    assert isinstance(season[0], ChannelSeries)

    # fid 为专栏收藏夹标识
    article_fav = await pl.parse_space_favorite_list(
        u(f"https://space.bilibili.com/1/favlist?fid={FavoriteListType.ARTICLE.value}"), CREDENTIAL
    )
    assert article_fav[1] == ResourceType.FAVORITE_LIST


# ---------------------------------------------------------------- 缩写名（不触网分支）


async def test_check_short_name_pure_branches():
    """ml/uid/cv/au/am/rl 缩写解析为对应资源对象。"""
    fav = await pl.check_short_name("ml42", CREDENTIAL)
    assert isinstance(fav, tuple)
    assert fav[1] == ResourceType.FAVORITE_LIST
    assert fav[0].get_media_id() == 42

    user = await pl.check_short_name("uid558830935", CREDENTIAL)
    assert user[1] == ResourceType.USER
    assert user[0].get_uid() == 558830935

    article = await pl.check_short_name("CV1931892", CREDENTIAL)
    assert article[1] == ResourceType.ARTICLE
    assert article[0].get_cvid() == 1931892

    audio = await pl.check_short_name("au15664", CREDENTIAL)
    assert audio[1] == ResourceType.AUDIO

    audio_list = await pl.check_short_name("am1024", CREDENTIAL)
    assert audio_list[1] == ResourceType.AUDIO_LIST

    article_list = await pl.check_short_name("rl77", CREDENTIAL)
    assert article_list[1] == ResourceType.ARTICLE_LIST

    # 无法识别的缩写返回 -1（避免使用 av/bv 前缀：那两个分支会触网）
    assert await pl.check_short_name("zz999", CREDENTIAL) == -1


# ---------------------------------------------------------------- parse_link 无网络入口


async def test_parse_link_blackroom_without_network(monkeypatch):
    """parse_link 主入口解析小黑屋链接时在触网前即返回。"""

    async def forbid_network(url, credential=None):
        raise AssertionError("parse_link 小黑屋分支不应触网")

    monkeypatch.setattr(pl, "get_real_url", forbid_network)
    obj, rtype = await pl.parse_link("https://www.bilibili.com/blackroom/ban/12345", credential=CREDENTIAL)
    assert rtype == ResourceType.BLACK_ROOM
    assert isinstance(obj, BlackRoom)
    assert obj.get_id() == 12345


async def test_parse_link_collectiondetail_without_network(monkeypatch):
    """parse_link 主入口解析合集链接时在触网前即返回。"""

    async def forbid_network(url, credential=None):
        raise AssertionError("parse_link 合集分支不应触网")

    monkeypatch.setattr(pl, "get_real_url", forbid_network)
    obj, rtype = await pl.parse_link(
        "https://space.bilibili.com/51537052/channel/collectiondetail?sid=22780", credential=CREDENTIAL
    )
    assert rtype == ResourceType.CHANNEL_SERIES
    assert isinstance(obj, ChannelSeries)
    assert obj.get_id() == 22780


async def test_parse_link_unresolvable_returns_failed(monkeypatch):
    """全部解析分支均不匹配的链接应返回 (-1, FAILED)（get_real_url 用恒等函数隔离）。"""

    async def identity(url, credential=None):
        return url

    monkeypatch.setattr(pl, "get_real_url", identity)
    obj, rtype = await pl.parse_link("https://www.bilibili.com/some/random/path", credential=CREDENTIAL)
    assert obj == -1
    assert rtype == ResourceType.FAILED


async def test_parse_link_root_url_returns_failed(monkeypatch):
    """www.bilibili.com 根路径应返回 (-1, FAILED) 而非 IndexError。"""

    async def identity(url, credential=None):
        return url

    monkeypatch.setattr(pl, "get_real_url", identity)
    obj, rtype = await pl.parse_link("https://www.bilibili.com/", credential=CREDENTIAL)
    assert obj == -1
    assert rtype == ResourceType.FAILED
