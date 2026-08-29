# bilibili_api lstrip → removeprefix/removesuffix 修复回归离线单元测试
#
# 本文件属于无凭据快速路径：全部用例均为纯本地逻辑验证，
# 不触碰网络、不读取 BILI_* 环境变量、不依赖真实账号。
#
# 回归目标：历史上误用 str.lstrip/rstrip（按字符集剔除）会过度删减首尾字符，
# 已修复为 removeprefix/removesuffix（精确前后缀剔除），本文件防止回退。
#
# 覆盖：
# - opus.Opus.markdown 代码块语言标识 `removeprefix("language-")`（含/不含前缀）
# - game.game_name2id 的 wiki 标题 `removeprefix("https://wiki.biligame.com/wiki/")`
#   与模板属性 `removeprefix("WIKI域名=")`（含/不含前缀）
#
# 未覆盖（跳过原因）：
# - interactive_video.InteractiveVideoDownloader.__main 的 `removesuffix(".ivi")`：
#   该行深嵌于下载主流程，进入即产生文件系统副作用（删除已有 .ivi、创建 .tmp 目录）
#   并发起网络下载，无法在不触网、不动磁盘的前提下离线执行，故跳过。

from bilibili_api import game
from bilibili_api.opus import Opus


def _fake_opus_info(lang: str) -> dict:
    """构造仅含单个代码块段落的假图文 info（注入实例私有缓存，绕过 get_info 触网）。"""
    return {
        "item": {
            "basic": {"comment_type": 12, "rid_str": "1"},
            "modules": [
                {"module_title": {"text": "代码块测试"}},
                {
                    "module_content": {
                        "paragraphs": [
                            {
                                "para_type": 7,
                                "align": 0,
                                "code": {"lang": lang, "content": "print(1)"},
                            }
                        ]
                    }
                },
            ],
        },
    }


async def _render_opus_code_block(lang: str) -> str:
    opus = Opus(opus_id=123)
    # 预置私有缓存使 get_info 不触网，仅验证 markdown 的纯解析层
    opus._Opus__info = _fake_opus_info(lang)
    return await opus.markdown()


async def test_opus_markdown_strips_language_prefix():
    """含前缀：language- 前缀须被精确剔除，且不得误删语言名本身的字符。"""
    result = await _render_opus_code_block("language-python")
    assert "``` python\nprint(1)\n```" in result


async def test_opus_markdown_keeps_lang_without_prefix():
    """不含前缀：无前缀的语言标识原样保留（removeprefix 无副作用）。"""
    result = await _render_opus_code_block("rust")
    assert "``` rust\nprint(1)\n```" in result


def _patch_game_api(monkeypatch, opensearch_title: str) -> None:
    """以假 Api 替换 game 模块的 Api，返回预设的 opensearch 结果与 wiki 页面内容，全程不触网。"""

    class FakeApi:
        def __init__(self, url: str = "", method: str = "", **kwargs):
            self.url = url

        async def request(self, raw: bool = False, byte: bool = False):
            if "opensearch" in self.url:
                return ["", [], [], [opensearch_title]]
            # wiki 页面原始内容为 ASCII（中文“域名”以 \\u 转义），与线上数据形态一致；
            # 模板属性键为 “WIKI域名=”（WIKI + \u57df\u540d），命中后取其值作为游戏编码。
            return b"{{Infobox|WIKI\\u57df\\u540d=abw|Other=abc}}"

    monkeypatch.setattr(game, "Api", FakeApi)


async def test_game_name2id_strips_wiki_url_prefix(monkeypatch):
    """含前缀：完整 wiki 标题链接须精确剔除前缀。

    'abw' 三个字符均在旧 URL 的字符集中，若回退到 lstrip 会被整体误删为空串。
    """
    _patch_game_api(monkeypatch, "https://wiki.biligame.com/wiki/abw")
    assert await game.game_name2id("任意搜索词") == "abw"


async def test_game_name2id_title_without_prefix(monkeypatch):
    """不含前缀：无前缀的标题原样保留，模板属性解析不受影响。"""
    _patch_game_api(monkeypatch, "abw")
    assert await game.game_name2id("任意搜索词") == "abw"
