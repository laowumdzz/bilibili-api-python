# bilibili_api.__init__

import asyncio

import pytest

from bilibili_api import get_real_url, parse_link

# 由约 40 个全量 URL 采样为 20 个代表性形态（research R8）：每种链接形态保留一个代表，
# 遍历规模收敛以匹配 cred1 请求预算，循环体内 0.5s 节流。
# 注：favlist 与 space.bilibili.com 网页形态上游解析已失效（恒返回 -1），不纳入采样。
parse_link_urls = [
    "av82054919",
    "BV1XJ41157tQ",
    "https://www.bilibili.com/video/BV1XJ41157tQ",
    "https://www.bilibili.com/bangumi/media/md28237119",
    "https://www.bilibili.com/bangumi/play/ss41410",
    "ml966613735",
    "https://www.bilibili.com/medialist/detail/ml966613735",
    "https://www.bilibili.com/cheese/play/ep790",
    "au800841",
    "https://www.bilibili.com/audio/am10624",
    "cv17809055",
    "https://www.bilibili.com/read/readlist/rl207146",
    "https://live.bilibili.com/558830935",
    "https://space.bilibili.com/558830935/channel/seriesdetail?sid=2972810",
    "https://t.bilibili.com/892599074330509334",
    "https://www.bilibili.com/opus/767674573455884292",
    "https://manga.bilibili.com/detail/mc32020",
    "uid558830935",
    "https://www.bilibili.com/v/topic/detail/?topic_id=57290",
    "https://www.bilibili.com/blackroom/ban/2670821",
]


@pytest.mark.cred1
async def test_a_parse_link(credential):
    for url in parse_link_urls:
        result = await parse_link(url, credential)
        assert result[0] != -1, f"解析失败：{url}"
        await asyncio.sleep(0.5)


@pytest.mark.cred1
async def test_b_get_real_url():
    await get_real_url("https://b23.tv/mx00St")
