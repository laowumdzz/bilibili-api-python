# bilibili_api 业务模块离线面单元测试
#
# 本文件属于无凭据快速路径：全部用例均为纯本地逻辑验证，
# 不触碰网络、不读取 BILI_* 环境变量、不依赖真实账号。
# 覆盖 opus / channel_series / garb / music / audio_uploader 五个模块
# 中不触网的纯本地入口（枚举、构造参数校验、本地数据结构转换）。

import pytest

from bilibili_api import Credential
from bilibili_api.audio_uploader import (
    AudioUploader,
    AudioUploaderEvents,
    AuthorInfo,
    SongCategories,
    SongMeta,
)
from bilibili_api.channel_series import ChannelOrder, ChannelSeries, ChannelSeriesType, channel_meta_cache
from bilibili_api.dynamic import Dynamic
from bilibili_api.exceptions import StatementException
from bilibili_api.garb import DLC, GarbSortType, GarbType, dlc_lottery_id
from bilibili_api.music import MusicIndexTags, MusicOrder
from bilibili_api.opus import Opus
from bilibili_api.utils.picture import Picture

CREDENTIAL = Credential()


# ---------------------------------------------------------------- opus


def test_opus_id_and_turn_to_dynamic():
    """Opus 的 id 存取与无网络转换为动态（图文与动态 id 一致）。"""
    opus = Opus(767674573455884292, credential=CREDENTIAL)
    assert opus.get_opus_id() == 767674573455884292
    assert opus.credential is CREDENTIAL

    dynamic = opus.turn_to_dynamic()
    assert isinstance(dynamic, Dynamic)
    assert dynamic.get_dynamic_id() == 767674573455884292

    # 未传凭据时应回退为空 Credential
    assert isinstance(Opus(1).credential, Credential)


# ---------------------------------------------------------------- channel_series


def test_channel_series_enums():
    """合集/列表类型与排序枚举值保持稳定。"""
    assert ChannelSeriesType.SERIES.value == 0
    assert ChannelSeriesType.SEASON.value == 1
    assert ChannelOrder.DEFAULT.value == "false"
    assert ChannelOrder.CHANGE.value == "true"


def test_channel_series_requires_valid_id():
    """id_ 缺省（-1）时构造应抛 StatementException。"""
    with pytest.raises(StatementException):
        ChannelSeries(uid=1, type_=ChannelSeriesType.SERIES)


def test_channel_series_basic_fields_and_meta_cache():
    """构造字段、类型回读与 channel_meta_cache 命中。"""
    cs = ChannelSeries(uid=123, type_=ChannelSeriesType.SERIES, id_=456, credential=CREDENTIAL)
    assert cs.get_id() == 456
    assert cs.get_type() == ChannelSeriesType.SERIES
    assert cs.is_new == 0
    assert cs.meta is None
    assert cs.owner.get_uid() == 123

    # 预置元信息缓存后，构造同 key 实例应直接命中
    cache_key = f"{ChannelSeriesType.SEASON.value}-777"
    channel_meta_cache[cache_key] = {"name": "离线缓存的合集名"}
    try:
        cached = ChannelSeries(uid=1, type_=ChannelSeriesType.SEASON, id_=777)
        assert cached.meta == {"name": "离线缓存的合集名"}
        assert cached.is_new == 1
    finally:
        channel_meta_cache.pop(cache_key, None)


# ---------------------------------------------------------------- garb


def test_garb_enums():
    """收藏集类型与排序枚举值保持稳定。"""
    assert GarbType.GARB.value == {"group_id": 0, "part_id": 6}
    assert GarbType.PENDANT.value == {"group_id": 22, "part_id": 1}
    assert GarbType.CARD.value == {"group_id": 5, "part_id": 2}
    assert [sort.value for sort in GarbSortType] == [0, 1, 2]


def test_dlc_act_id_and_lottery_cache():
    """DLC 的 act_id 存取、重置，以及 dlc_lottery_id 全局缓存命中。"""
    dlc = DLC(act_id=154, credential=CREDENTIAL)
    assert dlc.get_act_id() == 154

    dlc.set_act_id(act_id=233)
    assert dlc.get_act_id() == 233

    # 全局缓存中存在 lottery_id 时，构造即应命中
    dlc_lottery_id[42] = "LOT-42"
    try:
        cached = DLC(act_id=42)
        assert cached._DLC__lottery_id == "LOT-42"
    finally:
        dlc_lottery_id.pop(42, None)

    # 未传凭据时应回退为空 Credential
    assert isinstance(DLC(act_id=1).credential, Credential)


# ---------------------------------------------------------------- music


def test_music_order_and_index_tags():
    """音乐排序枚举与索引标签枚举值保持稳定。"""
    assert MusicOrder.NEW.value == 1
    assert MusicOrder.HOT.value == 2

    assert MusicIndexTags.Lang.ALL.value == ""
    assert MusicIndexTags.Lang.CHINESE.value == 3
    assert MusicIndexTags.Lang.KOREA.value == 61

    assert MusicIndexTags.Genre.ALL.value == ""
    assert MusicIndexTags.Genre.POPULAR.value == 1
    assert MusicIndexTags.Genre.JAZZ.value == 19
    assert MusicIndexTags.Genre.OTHER.value == 23


# ---------------------------------------------------------------- audio_uploader


def _offline_cover() -> Picture:
    """构造一个离线占位 Picture 封面（不触网）。"""
    return Picture(content=b"fake-image-bytes", width=600, height=600, imageType="png")


def _valid_meta(**overrides) -> SongMeta:
    """构造一份能通过 _check_meta 的最小合法元数据。"""
    meta = SongMeta(
        title="离线测试歌曲",
        desc="离线测试描述",
        tags="标签一,标签二",
        content_type=SongCategories.ContentType.MUSIC,
        song_type=SongCategories.SongType.HUMAN_SINGING,
        creation_type=SongCategories.CreationType.ORIGINAL,
        language=SongCategories.Language.CHINESE,
        singer=[AuthorInfo(name="离线歌手", uid=1)],
        cover=_offline_cover(),
    )
    for key, value in overrides.items():
        setattr(meta, key, value)
    return meta


def _make_uploader(tmp_path, meta: SongMeta) -> AudioUploader:
    """在临时目录创建一个占位音频文件并构造 AudioUploader。"""
    fake_audio = tmp_path / "offline_audio.flac"
    fake_audio.write_bytes(b"\x00" * 16)
    return AudioUploader(path=str(fake_audio), meta=meta, credential=CREDENTIAL)


def test_song_categories_and_events_values():
    """歌曲分类与上传事件枚举值保持稳定。"""
    assert SongCategories.ContentType.MUSIC.value == 1
    assert SongCategories.SongType.HUMAN_SINGING.value == 3
    assert SongCategories.SongType.PURE_MUSIC.value == 6
    assert SongCategories.Language.CHINESE.value == 32
    assert AudioUploaderEvents.COMPLETED.value == "COMPLETE"
    assert AudioUploaderEvents.ABORTED.value == "ABORTED"


def test_song_meta_defaults():
    """SongMeta 的可选字段默认值应为空列表/None。"""
    meta = SongMeta(
        title="t",
        desc="d",
        tags=[],
        content_type=SongCategories.ContentType.AUDIO_PROGRAM,
        song_type=SongCategories.AudioType.RADIO_DRAMA,
        creation_type=SongCategories.CreationType.ORIGINAL,
    )
    assert meta.singer == []
    assert meta.cover is None
    assert meta.lrc is None
    assert meta.is_bgm is True


def test_check_meta_passes_and_splits_tags(tmp_path):
    """合法元数据通过校验，且字符串标签被拆分为列表。"""
    uploader = _make_uploader(tmp_path, _valid_meta())
    uploader._check_meta()
    assert uploader.meta.tags == ["标签一", "标签二"]


def test_check_meta_rejects_empty_tags(tmp_path):
    """空标签应被拒绝。"""
    uploader = _make_uploader(tmp_path, _valid_meta(tags=[]))
    with pytest.raises(StatementException):
        uploader._check_meta()


def test_check_meta_rejects_missing_title(tmp_path):
    """缺少标题应被拒绝。"""
    uploader = _make_uploader(tmp_path, _valid_meta(title=None))
    with pytest.raises(StatementException):
        uploader._check_meta()


def test_check_meta_rejects_non_picture_cover(tmp_path):
    """封面非 Picture（如 URL 字符串）或缺失时应被拒绝。"""
    uploader = _make_uploader(tmp_path, _valid_meta(cover="https://example.com/cover.png"))
    with pytest.raises(StatementException):
        uploader._check_meta()

    uploader_no_cover = _make_uploader(tmp_path, _valid_meta(cover=None))
    with pytest.raises(StatementException):
        uploader_no_cover._check_meta()


def test_check_meta_music_requires_language(tmp_path):
    """MUSIC 内容类型必须提供语言标签。"""
    uploader = _make_uploader(tmp_path, _valid_meta(language=None))
    with pytest.raises(StatementException):
        uploader._check_meta()
