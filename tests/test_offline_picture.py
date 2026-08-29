# bilibili_api.utils.picture 离线单元测试
#
# 本文件属于无凭据快速路径：全部用例均为纯本地逻辑验证（使用 PIL 内存生成图片），
# 不触碰网络、不读取 BILI_* 环境变量、不依赖真实账号。
# 覆盖：默认值与字符串表示、from_content / from_file / to_file 往返、
# to_json 结构、convert_format 与 resize 的尺寸元数据。

import io
import os
import tempfile

from PIL import Image

from bilibili_api.utils.picture import Picture

# 测试用图片尺寸
WIDTH = 24
HEIGHT = 16


def make_png_bytes(width: int = WIDTH, height: int = HEIGHT, color=(251, 114, 153)) -> bytes:
    """用 PIL 在内存中生成指定尺寸的纯色 PNG 字节。"""
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), color).save(buffer, format="PNG")
    return buffer.getvalue()


def test_picture_default_fields():
    """默认构造的 Picture 各字段应为占位默认值。"""
    pic = Picture()
    assert pic.height == -1
    assert pic.width == -1
    assert pic.imageType == ""
    assert pic.url == ""
    assert pic.content == b""
    # str / repr 不应包含 content（可能很大），且格式稳定
    assert "Picture(" in str(pic)
    assert repr(pic) == str(pic)


def test_picture_from_content_reads_meta():
    """from_content 应正确解析宽高与格式，并填充 size。"""
    pic = Picture.from_content(make_png_bytes(), "png")
    assert pic.width == WIDTH
    assert pic.height == HEIGHT
    assert pic.imageType == "png"
    assert pic.size >= 0
    assert pic.url.startswith("bytes://")


def test_picture_from_file_and_to_file_roundtrip():
    """from_file 加载与 to_file 保存应往返一致。"""
    tmp_dir = tempfile.gettempdir()
    src_path = os.path.join(tmp_dir, "offline_picture_src.png")
    out_path = os.path.join(tmp_dir, "offline_picture_out.png")
    with open(src_path, "wb") as f:
        f.write(make_png_bytes())

    pic = Picture.from_file(src_path)
    assert pic.width == WIDTH
    assert pic.height == HEIGHT
    assert pic.url == "file://" + src_path

    pic.to_file(out_path)
    assert os.path.exists(out_path)
    with Image.open(out_path) as img:
        assert img.size == (WIDTH, HEIGHT)


def test_picture_to_json_structure():
    """to_json 应返回含图片元信息的单元素列表结构。"""
    pic = Picture.from_content(make_png_bytes(), "png")
    data = pic.to_json()
    assert isinstance(data, list)
    assert len(data) == 1
    item = data[0]
    assert item["img_src"] == pic.url
    assert item["img_width"] == WIDTH
    assert item["img_height"] == HEIGHT
    assert item["img_size"] == pic.size


def test_picture_convert_format():
    """convert_format 应转换容器格式并更新元数据。"""
    pic = Picture.from_content(make_png_bytes(), "png")
    pic.convert_format("webp")
    assert pic.imageType == "webp"
    assert pic.width == WIDTH
    assert pic.height == HEIGHT
    # 转换后的内容应能被 PIL 识别为 WEBP
    with Image.open(io.BytesIO(pic.content)) as img:
        assert img.format == "WEBP"


def test_picture_resize():
    """resize 应更新图片尺寸与元数据。"""
    pic = Picture.from_content(make_png_bytes(), "png")
    pic.resize(8, 4)
    assert pic.width == 8
    assert pic.height == 4
    with Image.open(io.BytesIO(pic.content)) as img:
        assert img.size == (8, 4)
