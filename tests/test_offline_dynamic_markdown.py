# bilibili_api 动态 markdown 渲染离线单元测试
#
# 本文件属于无凭据快速路径：全部用例均为纯本地逻辑验证，
# 不触碰网络、不读取 BILI_* 环境变量、不依赖真实账号。
# 由 pytest 收集运行（uv run pytest），且不会被 conftest.py 打上 integration 标记。

from bilibili_api.dynamic import Dynamic


def _fake_archive_info() -> dict:
    """
    构造"按投稿"类型的假动态 info（major.type 非 MAJOR_TYPE_OPUS，
    投稿条目含 cover / jump_url / title，jump_url 以 // 开头）。
    """
    return {
        "item": {
            "id_str": "123456",
            "modules": {
                "module_dynamic": {
                    "major": {
                        "type": "MAJOR_TYPE_ARCHIVE",
                        "archive": {
                            "cover": "//i0.hdslb.com/bfs/archive/test_cover.jpg",
                            "jump_url": "//www.bilibili.com/video/BV1xx411c7mD",
                            "title": "测试视频标题",
                        },
                    },
                },
            },
        },
    }


async def test_markdown_archive_major_renders():
    """按投稿分支的 markdown 渲染不应抛异常，输出应包含标题与补全后的链接。"""
    dynamic = Dynamic(dynamic_id=123456)

    async def fake_get_info() -> dict:
        return _fake_archive_info()

    dynamic.get_info = fake_get_info

    result = await dynamic.markdown()

    assert "测试视频标题" in result
    # // 开头的 jump_url 应补全为 https: 前缀
    assert "<https://www.bilibili.com/video/BV1xx411c7mD>" in result
    assert "//i0.hdslb.com/bfs/archive/test_cover.jpg" in result
