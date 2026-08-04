"""
ivitools.download

下载互动视频
"""

from bilibili_api import interactive_video, sync, video


def download_interactive_video(bvid: str, out: str):
    ivideo = interactive_video.InteractiveVideo(bvid)
    downloader = interactive_video.InteractiveVideoDownloader(
        ivideo,
        out,
        stream_detecting_params={"codecs": [video.VideoCodecs.AVC]},
    )

    @downloader.on("START")
    async def on_start(data):
        pass

    @downloader.on("GET")
    async def on_get(data):
        pass

    @downloader.on("PREPARE_DOWNLOAD")
    async def on_prepare_download(data):
        pass

    @downloader.on("DOWNLOAD_PART")
    async def on_download_part(data):
        pass

    @downloader.on("DOWNLOAD_SUCCESS")
    async def on_download_success(adta):
        pass

    @downloader.on("PACKAGING")
    async def on_packaing(data):
        pass

    @downloader.on("SUCCESS")
    async def on_success(data):
        pass

    try:
        sync(downloader.start())
    except KeyboardInterrupt:
        sync(downloader.abort())
    except Exception as e:
        raise e
