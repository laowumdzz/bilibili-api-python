# bilibili_api 离线冒烟/单元测试
#
# 本文件属于无凭据快速路径：全部用例均为纯本地逻辑验证，
# 不触碰网络、不读取 BILI_* 环境变量、不依赖真实账号。
# 由 pytest 收集运行（uv run pytest），且不会被 conftest.py 打上 integration 标记。

import pytest

from bilibili_api.utils.aid_bvid_transformer import aid2bvid, bvid2aid
from bilibili_api.utils.utils import chunk, img_auto_scheme, join, to_form_urlencoded
from bilibili_api.utils.varint import read_varint

# 已知 aid/bvid 对应关系（BV1N34y1Y7ds <-> 811248323 与 test_video.py 中一致）
KNOWN_PAIRS = [
    (811248323, "BV1N34y1Y7ds"),
    (170001, "BV17x411w7KC"),
    (455017605, "BV1Q541167Qg"),
]


def test_bvid2aid_known_pairs():
    """已知 BV 号应转换出对应 AV 号。"""
    for aid, bvid in KNOWN_PAIRS:
        assert bvid2aid(bvid) == aid


def test_aid2bvid_known_pairs():
    """已知 AV 号应转换出对应 BV 号。"""
    for aid, bvid in KNOWN_PAIRS:
        assert aid2bvid(aid) == bvid


def test_aid_bvid_roundtrip():
    """aid -> bvid -> aid 往返转换应保持一致。"""
    for aid in [1, 2, 170001, 811248323, 1350882325]:
        assert bvid2aid(aid2bvid(aid)) == aid


def test_read_varint_single_byte():
    """单字节 varint：最高位为 0 时立即结束。"""
    assert read_varint(b"\x00") == (0, 1)
    assert read_varint(b"\x01") == (1, 1)
    assert read_varint(b"\x7f") == (127, 1)


def test_read_varint_multi_byte():
    """多字节 varint：最高位为 1 表示后续还有字节。"""
    assert read_varint(b"\x80\x01") == (128, 2)
    assert read_varint(b"\xac\x02") == (300, 2)
    assert read_varint(b"\xff\x7f") == (16383, 2)


def test_read_varint_trailing_bytes_ignored():
    """varint 结束后的多余字节不应被读取。"""
    value, length = read_varint(b"\xac\x02\xde\xad\xbe\xef")
    assert (value, length) == (300, 2)


def test_join():
    """join 应以分隔符连接数组元素（元素转为字符串）。"""
    assert join(",", [1, 2, 3]) == "1,2,3"
    assert join("", ["a", "b"]) == "ab"
    assert join("-", []) == ""


def test_chunk():
    """chunk 应按指定大小切分数组，尾部不足一块时保留。"""
    assert chunk([1, 2, 3, 4], 2) == [[1, 2], [3, 4]]
    assert chunk([1, 2, 3, 4, 5], 2) == [[1, 2], [3, 4], [5]]
    assert chunk([], 3) == []


def test_chunk_invalid_size():
    """chunk 的 size <= 0 应抛出异常。"""
    with pytest.raises(Exception, match="size"):
        chunk([1, 2], 0)


def test_img_auto_scheme():
    """img_auto_scheme 应为 // 开头的链接补全 https scheme。"""
    assert img_auto_scheme("//i0.hdslb.com/a.jpg") == "https://i0.hdslb.com/a.jpg"
    assert img_auto_scheme("https://example.com/a.jpg") == "https://example.com/a.jpg"
    assert img_auto_scheme("http://example.com/a.jpg") == "http://example.com/a.jpg"


def test_to_form_urlencoded():
    """to_form_urlencoded 应输出表单编码字符串并转义特殊字符。"""
    assert to_form_urlencoded({"a": 1, "b": "x y"}) == "a=1&b=x%20y"
    assert to_form_urlencoded({"url": "a/b"}) == "url=a%2Fb"


def test_live_import_compatibility():
    """live.py 拆分后，关键公开符号仍可从 bilibili_api.live 导入且指向实际定义。"""
    from bilibili_api import _live_danmaku
    from bilibili_api import live
    from bilibili_api.live import (
        LiveCodec,
        LiveDanmaku,
        LiveFormat,
        LiveProtocol,
        LiveRoom,
        ScreenResolution,
        get_area_info,
        get_gift_config,
        get_self_info,
        parse_interact_word_v2,
        parse_online_rank_v3,
        parse_user_info,
    )

    # re-export 符号应与 _live_danmaku 中的定义同一对象（而非重复定义）
    assert LiveDanmaku is _live_danmaku.LiveDanmaku
    assert parse_user_info is _live_danmaku.parse_user_info
    assert parse_interact_word_v2 is _live_danmaku.parse_interact_word_v2
    assert parse_online_rank_v3 is _live_danmaku.parse_online_rank_v3

    # 模块属性访问路径（bilibili_api.live.X）同样可用
    for name in [
        "LiveCodec",
        "LiveDanmaku",
        "LiveFormat",
        "LiveProtocol",
        "LiveRoom",
        "ScreenResolution",
        "get_area_info",
        "get_gift_config",
        "get_self_info",
        "parse_interact_word_v2",
        "parse_online_rank_v3",
        "parse_user_info",
    ]:
        assert getattr(live, name) is not None

    assert LiveCodec and LiveFormat and LiveProtocol and ScreenResolution and LiveRoom
