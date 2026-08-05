# bilibili_api.ass

from bilibili_api import ass, video

v = video.Video("BV1or4y1u7fk")


async def test_a_ass_danmakus_protobuf():
    await ass.make_ass_file_danmakus_protobuf(v, page=0, out="danmakus_protobuf.ass")


async def test_b_ass_danmakus_xml():
    await ass.make_ass_file_danmakus_xml(v, page=0, out="danmakus_xml.ass")


async def test_base_ass_json_data(credential):
    a = await ass.request_subtitle_languages(v, credential=credential)
    assert await a.request_ass_data_str() is not None
    assert a.to_srt() is not None
    assert a.to_ass() is not None
    assert a.to_lrc() is not None
    assert a.to_simple_json() is not None
    assert a.to_simple_json_str() is not None


async def test_c_ass_subtitle(credential):
    await ass.make_ass_file_subtitle(v, lan_name="中文（中国）", out="subtitle.ass", credential=credential)


async def test_c_srt_subtitle(credential):
    await ass.make_srt_file_subtitle(v, lan_name="中文（中国）", out="subtitle.srt", credential=credential)


async def test_c_lrc_subtitle(credential):
    await ass.make_lrc_file_subtitle(v, lan_name="中文（中国）", out="subtitle.lrc", credential=credential)


async def test_c_json_subtitle(credential):
    await ass.make_simple_json_file_subtitle(v, lan_name="中文（中国）", out="subtitle.json", credential=credential)
