"""bilibili_api._video_download — 视频下载相关类型和解析。"""

from dataclasses import dataclass
from enum import Enum
from functools import cmp_to_key


class VideoQuality(Enum):
    """
    视频的视频流分辨率枚举

    - _360P: 流畅 360P
    - _480P: 清晰 480P
    - _720P: 高清 720P60
    - _1080P: 高清 1080P
    - AI_REPAIR: 智能修复（人工智能修复画质）
    - _1080P_PLUS: 高清 1080P 高码率
    - _1080P_60: 高清 1080P 60 帧码率
    - _4K: 超清 4K
    - HDR: 真彩 HDR
    - DOLBY: 杜比视界
    - _8K: 超高清 8K
    """

    _360P = 16
    _480P = 32
    _720P = 64
    _1080P = 80
    AI_REPAIR = 100
    _1080P_PLUS = 112
    _1080P_60 = 116
    _4K = 120
    HDR = 125
    DOLBY = 126
    _8K = 127


class VideoCodecs(Enum):
    """
    视频的视频流编码枚举

    - HEV: HEVC(H.265)
    - AVC: AVC(H.264)
    - AV1: AV1
    - UNKNOWN: 未知
    """

    HEV = ("hev", "hvc")
    AVC = ("avc",)
    AV1 = ("av01", "av1")
    UNKNOWN = ()


class AudioQuality(Enum):
    """
    视频的音频流清晰度枚举

    - _64K: 64K
    - _132K: 132K
    - _192K: 192K
    - HI_RES: Hi-Res 无损
    - DOLBY: 杜比全景声
    """

    _64K = 30216
    _132K = 30232
    DOLBY = 30250
    HI_RES = 30251
    _192K = 30280


@dataclass
class VideoStreamDownloadURL:
    """
    (@dataclass)

    视频流 URL 类

    Attributes:
        url (str): 视频流 url
        video_quality (VideoQuality): 视频流清晰度
        video_codecs (VideoCodecs) : 视频流编码
        backup_url (list[str]): 备用链接
        bandwidth (int): 码率
        codecs (str): 视频流详细编码
        frame_rate (float): 帧率
        scale (tuple[int, int]): 画面尺寸
        sar (tuple[int, int]): 采样纵横比
        mime_type (str): MIME 类型
        segment_base_initialization (str): SegmentBase.Initialization
        segment_base_index_range (str): SegmentBase.indexRange
    """

    url: str
    video_quality: VideoQuality
    video_codecs: VideoCodecs
    backup_url: list[str]
    bandwidth: int
    codecs: str
    frame_rate: float
    scale: tuple[int, int]
    sar: tuple[int, int]
    mime_type: str
    segment_base_initialization: str
    segment_base_index_range: str


@dataclass
class AudioStreamDownloadURL:
    """
    (@dataclass)

    音频流 URL 类

    Attributes:
        url (str): 音频流 url
        audio_quality (AudioQuality): 音频流清晰度
        backup_url (list[str]): 备用链接
        bandwidth (int): 码率
        codecs (str): 视频流详细编码
        mime_type (str): MIME 类型
        segment_base_initialization (str): SegmentBase.Initialization
        segment_base_index_range (str): SegmentBase.indexRange
    """

    url: str
    audio_quality: AudioQuality
    backup_url: list[str]
    bandwidth: int
    codecs: str
    mime_type: str
    segment_base_initialization: str
    segment_base_index_range: str


@dataclass
class FLVStreamDownloadURL:
    """
    (@dataclass)

    FLV 视频流

    Attributes:
        url           (str): FLV 流 url
    """

    url: str


@dataclass
class MP4StreamDownloadURL:
    """
    (@dataclass)

    MP4 视频流

    Attributes:
        url           (str): HTML5 mp4 视频流
    """

    url: str


class VideoDownloadURLDataDetecter:
    """
    `Video.get_download_url` 返回结果解析类。

    在调用 `Video.get_download_url` 之后可以将代入 `VideoDownloadURLDataDetecter`，此类将一键解析。

    目前支持:
      - 视频清晰度: 360P, 480P, 720P, 1080P, 1080P 高码率, 1080P 60 帧, 4K, HDR, 杜比视界, 8K
      - 视频编码: HEVC(H.265), AVC(H.264), AV1
      - 音频清晰度: 64K, 132K, Hi-Res 无损音效, 杜比全景声, 192K
      - FLV 视频流
      - 番剧/课程试看视频流
    """

    def __init__(self, data: dict):
        """
        Args:
            data (dict): `Video.get_download_url` 返回的结果
        """
        self.__data = data
        if self.__data.get("video_info"):  # bangumi
            self.__data = self.__data["video_info"]

    def check_video_and_audio_stream(self) -> bool:
        """
        判断是否为 DASH （音视频分离）

        Returns:
            bool: 是否为 DASH
        """
        if "dash" in self.__data.keys():
            return True
        return False

    def check_flv_mp4_stream(self) -> bool:
        """
        判断是否为 FLV / MP4 流

        Returns:
            bool: 是否为 FLV / MP4 流
        """
        if "durl" in self.__data.keys():
            return True
        return False

    def detect_all(self):
        """
        解析并返回所有数据

        Returns:
            List[VideoStreamDownloadURL | AudioStreamDownloadURL | FLVStreamDownloadURL | HTML5MP4DownloadURL | EpisodeTryMP4DownloadURL]: 所有的视频/音频流
        """
        return self.detect()

    def detect(
        self,
        video_max_quality: VideoQuality = VideoQuality._8K,
        audio_max_quality: AudioQuality = AudioQuality._192K,
        video_min_quality: VideoQuality = VideoQuality._360P,
        audio_min_quality: AudioQuality = AudioQuality._64K,
        video_accepted_qualities: list[VideoQuality] = [
            item for _, item in VideoQuality.__dict__.items() if isinstance(item, VideoQuality)
        ],
        audio_accepted_qualities: list[AudioQuality] = [
            item for _, item in AudioQuality.__dict__.items() if isinstance(item, AudioQuality)
        ],
        codecs: list[VideoCodecs] = [VideoCodecs.AV1, VideoCodecs.AVC, VideoCodecs.HEV, VideoCodecs.UNKNOWN],
        no_dolby_video: bool = False,
        no_dolby_audio: bool = False,
        no_hdr: bool = False,
        no_hires: bool = False,
    ) -> list[VideoStreamDownloadURL | AudioStreamDownloadURL | FLVStreamDownloadURL | MP4StreamDownloadURL]:
        """
        解析数据

        Args:
            video_max_quality       (VideoQuality, optional)      : 设置提取的视频流清晰度最大值，设置此参数绝对不会禁止 HDR/杜比. Defaults to VideoQuality._8K.

            audio_max_quality       (AudioQuality, optional)      : 设置提取的音频流清晰度最大值. 设置此参数绝对不会禁止 Hi-Res/杜比. Defaults to AudioQuality._192K.

            video_min_quality       (VideoQuality, optional)      : 设置提取的视频流清晰度最小值，设置此参数绝对不会禁止 HDR/杜比. Defaults to VideoQuality._360P.

            audio_min_quality       (AudioQuality, optional)      : 设置提取的音频流清晰度最小值. 设置此参数绝对不会禁止 Hi-Res/杜比. Defaults to AudioQuality._64K.

            video_accepted_qualities(List[VideoQuality], optional): 设置允许的所有视频流清晰度. Defaults to ALL.

            audio_accepted_qualities(List[AudioQuality], optional): 设置允许的所有音频清晰度. Defaults to ALL.

            codecs                  (List[VideoCodecs], optional) : 设置所有允许提取出来的视频编码. 此项不会忽略 HDR/杜比. Defaults to ALL codecs.

            no_dolby_video          (bool, optional)              : 是否禁止提取杜比视界视频流. Defaults to False.

            no_dolby_audio          (bool, optional)              : 是否禁止提取杜比全景声音频流. Defaults to False.

            no_hdr                  (bool, optional)              : 是否禁止提取 HDR 视频流. Defaults to False.

            no_hires                (bool, optional)              : 是否禁止提取 Hi-Res 音频流. Defaults to False.

        Returns:
            List[VideoStreamDownloadURL | AudioStreamDownloadURL | FLVStreamDownloadURL | HTML5MP4DownloadURL | EpisodeTryMP4DownloadURL]: 提取出来的视频/音频流

        **参数仅能在音视频流分离的情况下产生作用，flv / mp4 流下以下参数均没有作用**
        """
        if "durl" in self.__data.keys():
            if self.__data["format"].startswith("flv"):
                # FLV 视频流
                return [FLVStreamDownloadURL(url=self.__data["durl"][0]["url"])]
            else:
                # MP4 视频流
                return [MP4StreamDownloadURL(url=self.__data["durl"][0]["url"])]
        else:
            # 正常情况
            streams = []
            videos_data = self.__data["dash"]["video"]
            audios_data = self.__data["dash"].get("audio")
            flac_data = self.__data["dash"].get("flac")
            dolby_data = self.__data["dash"].get("dolby")
            for video_data in videos_data:
                video_stream_url = video_data["base_url"]
                video_stream_quality = VideoQuality(video_data["id"])
                if video_stream_quality == VideoQuality.HDR and no_hdr:
                    continue
                if video_stream_quality == VideoQuality.DOLBY and no_dolby_video:
                    continue
                if (
                    video_stream_quality != VideoQuality.DOLBY
                    and video_stream_quality != VideoQuality.HDR
                    and video_stream_quality.value > video_max_quality.value
                ):
                    continue
                if (
                    video_stream_quality != VideoQuality.DOLBY
                    and video_stream_quality != VideoQuality.HDR
                    and video_stream_quality.value < video_min_quality.value
                ):
                    continue
                if (
                    video_stream_quality != VideoQuality.DOLBY
                    and video_stream_quality != VideoQuality.HDR
                    and (video_stream_quality not in video_accepted_qualities)
                ):
                    continue
                video_stream_codecs = VideoCodecs.UNKNOWN
                for val in codecs:
                    for key in val.value:
                        if key in video_data["codecs"]:
                            video_stream_codecs = val
                if VideoCodecs.UNKNOWN not in codecs and video_stream_codecs == VideoCodecs.UNKNOWN:
                    continue
                video_stream = VideoStreamDownloadURL(
                    url=video_stream_url,
                    video_quality=video_stream_quality,
                    video_codecs=video_stream_codecs,
                    backup_url=video_data["backup_url"],
                    bandwidth=video_data["bandwidth"],
                    codecs=video_data["codecs"],
                    frame_rate=float(video_data["frame_rate"]),
                    scale=(video_data["width"], video_data["height"]),
                    sar=tuple([int(x) for x in video_data["sar"].split(":")] if ":" in video_data["sar"] else (1, 1)),
                    mime_type=video_data["mime_type"],
                    segment_base_initialization=video_data["segment_base"]["initialization"],
                    segment_base_index_range=video_data["segment_base"]["index_range"],
                )
                streams.append(video_stream)
            if audios_data:
                for audio_data in audios_data:
                    audio_stream_url = audio_data["base_url"]
                    audio_stream_quality = AudioQuality(audio_data["id"])
                    if audio_stream_quality.value > audio_max_quality.value:
                        continue
                    if audio_stream_quality.value < audio_min_quality.value:
                        continue
                    if audio_stream_quality not in audio_accepted_qualities:
                        continue
                    audio_stream = AudioStreamDownloadURL(
                        url=audio_stream_url,
                        audio_quality=audio_stream_quality,
                        backup_url=audio_data["backup_url"],
                        bandwidth=audio_data["bandwidth"],
                        codecs=audio_data["codecs"],
                        mime_type=audio_data["mime_type"],
                        segment_base_initialization=audio_data["segment_base"]["initialization"],
                        segment_base_index_range=audio_data["segment_base"]["index_range"],
                    )
                    streams.append(audio_stream)
            if flac_data and (not no_hires):
                if flac_data["audio"]:
                    flac_stream_url = flac_data["audio"]["base_url"]
                    flac_stream_quality = AudioQuality(flac_data["audio"]["id"])
                    flac_stream = AudioStreamDownloadURL(
                        url=flac_stream_url,
                        audio_quality=flac_stream_quality,
                        backup_url=flac_data["audio"]["backup_url"],
                        bandwidth=flac_data["audio"]["bandwidth"],
                        codecs=flac_data["audio"]["codecs"],
                        mime_type=flac_data["audio"]["mime_type"],
                        segment_base_initialization=flac_data["audio"]["segment_base"]["initialization"],
                        segment_base_index_range=flac_data["audio"]["segment_base"]["index_range"],
                    )
                    streams.append(flac_stream)
            if dolby_data and (not no_dolby_audio):
                if dolby_data["audio"]:
                    dolby_stream_data = dolby_data["audio"][0]
                    dolby_stream_url = dolby_stream_data["base_url"]
                    dolby_stream_quality = AudioQuality(dolby_stream_data["id"])
                    dolby_stream = AudioStreamDownloadURL(
                        url=dolby_stream_url,
                        audio_quality=dolby_stream_quality,
                        backup_url=dolby_stream_data["backup_url"],
                        bandwidth=dolby_stream_data["bandwidth"],
                        codecs=dolby_stream_data["codecs"],
                        mime_type=dolby_stream_data["mime_type"],
                        segment_base_initialization=dolby_stream_data["segment_base"]["initialization"],
                        segment_base_index_range=dolby_stream_data["segment_base"]["index_range"],
                    )
                    streams.append(dolby_stream)
            return streams

    def detect_best_streams(
        self,
        video_max_quality: VideoQuality = VideoQuality._8K,
        audio_max_quality: AudioQuality = AudioQuality._192K,
        video_min_quality: VideoQuality = VideoQuality._360P,
        audio_min_quality: AudioQuality = AudioQuality._64K,
        video_accepted_qualities: list[VideoQuality] = [
            item for _, item in VideoQuality.__dict__.items() if isinstance(item, VideoQuality)
        ],
        audio_accepted_qualities: list[AudioQuality] = [
            item for _, item in AudioQuality.__dict__.items() if isinstance(item, AudioQuality)
        ],
        codecs: list[VideoCodecs] = [VideoCodecs.AV1, VideoCodecs.AVC, VideoCodecs.HEV, VideoCodecs.UNKNOWN],
        no_dolby_video: bool = False,
        no_dolby_audio: bool = False,
        no_hdr: bool = False,
        no_hires: bool = False,
    ) -> list[VideoStreamDownloadURL | AudioStreamDownloadURL | FLVStreamDownloadURL | MP4StreamDownloadURL]:
        """
        提取出分辨率、音质等信息最好的音视频流。

        Args:
            video_max_quality       (VideoQuality)                : 设置提取的视频流清晰度最大值，设置此参数绝对不会禁止 HDR/杜比. Defaults to VideoQuality._8K.

            audio_max_quality       (AudioQuality)                : 设置提取的音频流清晰度最大值. 设置此参数绝对不会禁止 Hi-Res/杜比. Defaults to AudioQuality._192K.

            video_min_quality       (VideoQuality, optional)      : 设置提取的视频流清晰度最小值，设置此参数绝对不会禁止 HDR/杜比. Defaults to VideoQuality._360P.

            audio_min_quality       (AudioQuality, optional)      : 设置提取的音频流清晰度最小值. 设置此参数绝对不会禁止 Hi-Res/杜比. Defaults to AudioQuality._64K.

            video_accepted_qualities(List[VideoQuality], optional): 设置允许的所有视频流清晰度. Defaults to ALL.

            audio_accepted_qualities(List[AudioQuality], optional): 设置允许的所有音频清晰度. Defaults to ALL.

            codecs                  (List[VideoCodecs])           : 设置所有允许提取出来的视频编码. 在数组中越靠前的编码选择优先级越高. 此项不会忽略 HDR/杜比. Defaults to [VideoCodecs.AV1, VideoCodecs.AVC, VideoCodecs.HEV].

            no_dolby_video          (bool)                        : 是否禁止提取杜比视界视频流. Defaults to False.

            no_dolby_audio          (bool)                        : 是否禁止提取杜比全景声音频流. Defaults to False.

            no_hdr                  (bool)                        : 是否禁止提取 HDR 视频流. Defaults to False.

            no_hires                (bool)                        : 是否禁止提取 Hi-Res 音频流. Defaults to False.

        Returns:
            List[VideoStreamDownloadURL | AudioStreamDownloadURL | FLVStreamDownloadURL | HTML5MP4DownloadURL | None]: FLV 视频流 / HTML5 MP4 视频流 / 番剧或课程试看 MP4 视频流返回 `[FLVStreamDownloadURL | HTML5MP4StreamDownloadURL | EpisodeTryMP4DownloadURL]`, 否则为 `[VideoStreamDownloadURL, AudioStreamDownloadURL]`, 如果未匹配上任何合适的流则对应的位置位 `None`

        **以上参数仅能在音视频流分离的情况下产生作用，flv / mp4 试看流 / html5 mp4 流下以下参数均没有作用**
        """
        if self.check_flv_mp4_stream():
            return self.detect_all()
        else:
            data = self.detect(
                video_max_quality=video_max_quality,
                audio_max_quality=audio_max_quality,
                video_min_quality=video_min_quality,
                audio_min_quality=audio_min_quality,
                video_accepted_qualities=video_accepted_qualities,
                audio_accepted_qualities=audio_accepted_qualities,
                codecs=codecs,
                no_dolby_video=no_dolby_video,
                no_dolby_audio=no_dolby_audio,
                no_hires=no_hires,
                no_hdr=no_hdr,
            )
            video_streams = []
            audio_streams = []
            for stream in data:
                if isinstance(stream, VideoStreamDownloadURL):
                    video_streams.append(stream)
                if isinstance(stream, AudioStreamDownloadURL):
                    audio_streams.append(stream)

            def video_stream_cmp(s1: VideoStreamDownloadURL, s2: VideoStreamDownloadURL):
                # 杜比/HDR 优先
                if s1.video_quality == VideoQuality.DOLBY and (not no_dolby_video):
                    return 1
                elif s2.video_quality == VideoQuality.DOLBY and (not no_dolby_video):
                    return -1
                elif s1.video_quality == VideoQuality.HDR and (not no_hdr):
                    return 1
                elif s2.video_quality == VideoQuality.HDR and (not no_hdr):
                    return -1
                if s1.video_quality.value != s2.video_quality.value:
                    return s1.video_quality.value - s2.video_quality.value
                    # Detect the high quality stream to the end.
                elif s1.video_codecs.value != s2.video_codecs.value:
                    return codecs.index(s2.video_codecs) - codecs.index(s1.video_codecs)
                return -1

            def audio_stream_cmp(s1: AudioStreamDownloadURL, s2: AudioStreamDownloadURL):
                # 杜比/Hi-Res 优先
                if s1.audio_quality == AudioQuality.DOLBY and (not no_dolby_audio):
                    return 1
                if s2.audio_quality == AudioQuality.DOLBY and (not no_dolby_audio):
                    return -1
                if s1.audio_quality == AudioQuality.HI_RES and (not no_hires):
                    return 1
                if s2.audio_quality == AudioQuality.HI_RES and (not no_hires):
                    return -1
                return s1.audio_quality.value - s2.audio_quality.value

            video_streams.sort(key=cmp_to_key(video_stream_cmp), reverse=True)
            audio_streams.sort(key=cmp_to_key(audio_stream_cmp), reverse=True)
            if len(video_streams) == 0:
                video_streams = [None]
            if len(audio_streams) == 0:
                audio_streams = [None]
            return [video_streams[0], audio_streams[0]]
