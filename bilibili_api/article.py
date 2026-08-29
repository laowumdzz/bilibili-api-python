"""
bilibili_api.article

专栏相关
"""

from copy import copy
from enum import Enum
import html
import re
from typing import TYPE_CHECKING, TypeVar, overload
from urllib.parse import unquote

from bs4 import BeautifulSoup, element
import yaml
from yarl import URL

from . import dynamic, opus
from .exceptions import ApiException
from .utils import cache_pool
from .utils.network import Api, Credential
from .utils.utils import get_api

if TYPE_CHECKING:
    # 仅供类型检查：运行时 Note 在 turn_to_note 内导入（破解 article ↔ note 循环依赖）
    from .note import Note

API = get_api("article")

# 文章颜色表
ARTICLE_COLOR_MAP = {
    "default": "222222",
    "blue-01": "56c1fe",
    "lblue-01": "73fdea",
    "green-01": "89fa4e",
    "yellow-01": "fff359",
    "pink-01": "ff968d",
    "purple-01": "ff8cc6",
    "blue-02": "02a2ff",
    "lblue-02": "18e7cf",
    "green-02": "60d837",
    "yellow-02": "fbe231",
    "pink-02": "ff654e",
    "purple-02": "ef5fa8",
    "blue-03": "0176ba",
    "lblue-03": "068f86",
    "green-03": "1db100",
    "yellow-03": "f8ba00",
    "pink-03": "ee230d",
    "purple-03": "cb297a",
    "blue-04": "004e80",
    "lblue-04": "017c76",
    "green-04": "017001",
    "yellow-04": "ff9201",
    "pink-04": "b41700",
    "purple-04": "99195e",
    "gray-01": "d6d5d5",
    "gray-02": "929292",
    "gray-03": "5f5f5f",
}


class ArticleRankingType(Enum):
    """
    专栏排行榜类型枚举。

    + MONTH: 月榜
    + WEEK: 周榜
    + DAY_BEFORE_YESTERDAY: 前日榜
    + YESTERDAY: 昨日榜
    """

    MONTH = 1
    WEEK = 2
    DAY_BEFORE_YESTERDAY = 4
    YESTERDAY = 3


ArticleT = TypeVar("ArticleT", bound="Article")


async def get_article_rank(
    rank_type: ArticleRankingType = ArticleRankingType.YESTERDAY,
):
    """
    获取专栏排行榜

    Args:
        rank_type (ArticleRankingType): 排行榜类别. Defaults to ArticleRankingType.YESTERDAY.

    Returns:
        dict: 调用 API 返回的结果
    """
    api = API["info"]["rank"]
    params = {"cid": rank_type.value}
    return await Api(**api).update_params(**params).result


class ArticleList:
    """
    文集类

    Attributes:
        credential (Credential): 凭据类
    """

    def __init__(self, rlid: int, credential: Credential | None = None):
        """
        Args:
            rlid       (int)                        : 文集 id

            credential (Credential | None, optional): 凭据类. Defaults to None.
        """
        self.__rlid = rlid
        self.credential: Credential = credential

    def get_rlid(self) -> int:
        """
        获取 rlid

        Returns:
            int: rlid
        """
        return self.__rlid

    async def get_content(self) -> dict:
        """
        获取专栏文集文章列表

        Returns:
            dict: 调用 API 返回的结果
        """
        credential = self.credential if self.credential is not None else Credential()

        api = API["info"]["list"]
        params = {"id": self.__rlid}
        return await Api(**api, credential=credential).update_params(**params).result


class Article:
    """
    专栏类

    Attributes:
        credential (Credential): 凭据类
    """

    def __init__(self, cvid: int, credential: Credential | None = None):
        """
        Args:
            cvid       (int)                        : cv 号

            credential (Credential | None, optional): 凭据. Defaults to None.
        """
        self.__children: list[Node] = []
        self.credential: Credential = credential if credential is not None else Credential()
        self.__meta = None
        self.__cvid = cvid
        self.__has_parsed: bool = False
        self.__get_all_data: dict = None

    async def turn_to_dynamic(self) -> "dynamic.Dynamic":
        """
        将专栏转为对应动态（评论、点赞等数据专栏/动态/图文共享）

        专栏完全包含于动态，因此此函数绝对成功。

        转换后可查看“赞和转发”列表。

        Returns:
            Dynamic: 动态实例
        """
        if cache_pool.article2dynamic.get(self.get_cvid()) is None:
            await self.get_all()
        return dynamic.Dynamic(
            dynamic_id=cache_pool.article2dynamic.get(self.get_cvid()),
            credential=self.credential,
        )

    async def turn_to_opus(self) -> "opus.Opus":
        """
        将专栏转为对应图文（评论、点赞等数据专栏/动态/图文共享）

        专栏完全包含于图文，因此此函数绝对成功。

        转换后可查看“赞和转发”列表。

        Returns:
            Opus: 动态实例
        """
        if cache_pool.article2dynamic.get(self.get_cvid()) is None:
            await self.get_all()
        return opus.Opus(
            opus_id=cache_pool.article2dynamic.get(self.get_cvid()),
            credential=self.credential,
        )

    async def is_note(self) -> bool:
        """
        判断专栏是否为笔记

        Returns:
            bool: 是否为笔记
        """
        if cache_pool.article_is_note.get(self.get_cvid()) is None:
            await self.get_all()
        return cache_pool.article_is_note.get(self.get_cvid())

    def turn_to_note(self) -> "Note":
        """
        将专栏转为笔记，不会核验。如需核验使用 `await is_note()`

        Returns:
            Note: 笔记实例
        """
        # 函数内导入以破解 article ↔ note 循环依赖
        from .note import Note, NoteType

        return Note(cvid=self.get_cvid(), note_type=NoteType.PUBLIC, credential=self.credential)

    def get_cvid(self) -> int:
        """
        获取 cvid

        Returns:
            int: cvid
        """
        return self.__cvid

    def markdown(self) -> str:
        """
        转换为 Markdown

        请先调用 fetch_content()

        Returns:
            str: Markdown 内容
        """
        if not self.__has_parsed:
            raise ApiException("请先调用 fetch_content()")

        content = ""

        for node in self.__children:
            try:
                markdown_text = node.markdown()
            except Exception:
                continue
            else:
                content += markdown_text

        meta_yaml = yaml.safe_dump(self.__meta, allow_unicode=True)
        content = f"---\n{meta_yaml}\n---\n\n{content}"
        return content

    def json(self) -> dict:
        """
        转换为 JSON 数据

        请先调用 fetch_content()

        Returns:
            dict: JSON 数据
        """
        if not self.__has_parsed:
            raise ApiException("请先调用 fetch_content()")

        return {
            "type": "Article",
            "meta": self.__meta,
            "children": [x.json() for x in self.__children],
        }

    async def fetch_content(self) -> None:
        """
        获取并解析专栏内容

        该返回不会返回任何值，调用该方法后请再调用 `self.markdown()` 或 `self.json()` 来获取你需要的值。
        """

        resp = await self.get_all()

        document = BeautifulSoup(f"<div>{resp['readInfo']['content']}</div>", "lxml")

        async def parse(el: BeautifulSoup):
            """
            递归解析专栏 HTML 元素为节点树。

            按标签名分发：段落/标题/样式 span/引用块/图文 figure/列表/链接/公式等，
            各分支构造对应的 Node 子类并递归解析子元素。

            Args:
                el (BeautifulSoup): 待解析的 HTML 元素

            Returns:
                list[Node]: 解析出的节点列表
            """
            node_list = []

            for e in el.contents:  # type: ignore
                if type(e) is element.NavigableString:
                    # 文本节点
                    node = TextNode(e)  # type: ignore
                    node_list.append(node)
                    continue

                e: BeautifulSoup = e
                if e.name == "p":
                    # 段落
                    node = ParagraphNode()
                    node_list.append(node)

                    if "style" in e.attrs:
                        if "text-align: center" in e.attrs["style"]:
                            node.align = "center"

                        elif "text-align: right" in e.attrs["style"]:
                            node.align = "right"

                        else:
                            node.align = "left"

                    node.children = await parse(e)

                elif e.name == "h1":
                    # 标题
                    node = HeadingNode()
                    node_list.append(node)

                    node.children = await parse(e)

                elif e.name == "strong":
                    # 粗体
                    node = BoldNode()
                    node_list.append(node)

                    node.children = await parse(e)

                elif e.name == "span":
                    # 各种样式
                    if "style" in e.attrs:
                        style = e.attrs["style"]

                        if "text-decoration: line-through" in style:
                            # 删除线
                            node = DelNode()
                            node_list.append(node)

                            node.children = await parse(e)
                        if e.text != "":
                            node_list += await parse(e)

                    elif "class" in e.attrs:
                        className = e.attrs["class"][0]

                        if "font-size" in className:
                            # 字体大小
                            node = FontSizeNode()
                            node_list.append(node)

                            node.size = int(re.search(r"font-size-(\d\d)", className)[1])  # type: ignore
                            node.children = await parse(e)

                        elif "color" in className:
                            # 字体颜色
                            node = ColorNode()
                            node_list.append(node)

                            color_text = re.search("color-(.*);?", className)[1]  # type: ignore
                            node.color = ARTICLE_COLOR_MAP[color_text]

                            node.children = await parse(e)
                        else:
                            if e.text != "":
                                node_list += await parse(e)

                elif e.name == "blockquote":
                    # 引用块
                    # print(e.text)
                    node = BlockquoteNode()
                    node_list.append(node)
                    node.children = await parse(e)

                elif e.name == "figure":
                    if "class" in e.attrs:
                        className = e.attrs["class"]

                        if "img-box" in className:
                            img_el: BeautifulSoup = e.find("img")  # type: ignore
                            if img_el is None:
                                pass
                            elif "class" in img_el.attrs:
                                className = img_el.attrs["class"]

                                if "cut-off" in className:
                                    # 分割线
                                    node = SeparatorNode()
                                    node_list.append(node)

                                if "aid" in img_el.attrs:
                                    # 各种卡片
                                    aid = img_el.attrs["aid"]

                                    if "video-card" in className:
                                        # 视频卡片，考虑有两列视频
                                        for a in aid.split(","):
                                            node = VideoCardNode()
                                            node_list.append(node)

                                            node.aid = int(a)

                                    elif "article-card" in className:
                                        # 文章卡片
                                        node = ArticleCardNode()
                                        node_list.append(node)

                                        node.cvid = int(aid)

                                    elif "fanju-card" in className:
                                        # 番剧卡片
                                        node = BangumiCardNode()
                                        node_list.append(node)

                                        node.epid = int(aid[2:])

                                    elif "music-card" in className:
                                        # 音乐卡片
                                        node = MusicCardNode()
                                        node_list.append(node)

                                        node.auid = int(aid[2:])

                                    elif "shop-card" in className:
                                        # 会员购卡片
                                        node = ShopCardNode()
                                        node_list.append(node)

                                        node.pwid = int(aid[2:])

                                    elif "caricature-card" in className:
                                        # 漫画卡片，考虑有两列

                                        for i in aid.split(","):
                                            node = ComicCardNode()
                                            node_list.append(node)

                                            node.mcid = int(i)

                                    elif "live-card" in className:
                                        # 直播卡片
                                        node = LiveCardNode()
                                        node_list.append(node)

                                        node.room_id = int(aid)

                                if "seamless" in className:
                                    # 图片节点
                                    node = ImageNode()
                                    node_list.append(node)

                                    node.url = e.find("img").attrs["data-src"]  # type: ignore

                                    figcaption_el: BeautifulSoup = e.find("figcaption")  # type: ignore

                                    if figcaption_el:
                                        if figcaption_el.contents:
                                            node.alt = figcaption_el.contents[0]  # type: ignore
                            else:
                                # 图片节点
                                node = ImageNode()
                                node_list.append(node)

                                node.url = e.find("img").attrs["src"]  # type: ignore

                                figcaption_el: BeautifulSoup = e.find("figcaption")  # type: ignore

                                if figcaption_el:
                                    if figcaption_el.contents:
                                        node.alt = figcaption_el.contents[0]  # type: ignore

                        elif "code-box" in className:
                            # 代码块
                            node = CodeNode()
                            node_list.append(node)

                            pre_el: BeautifulSoup = e.find("pre")  # type: ignore
                            node.lang = pre_el.attrs["data-lang"].split("@")[0].lower()
                            node.code = unquote(pre_el.attrs["codecontent"])

                elif e.name == "ol":
                    # 有序列表
                    node = OlNode()
                    node_list.append(node)

                    node.children = await parse(e)

                elif e.name == "li":
                    # 列表元素
                    node = LiNode()
                    node_list.append(node)

                    node.children = await parse(e)

                elif e.name == "ul":
                    # 无序列表
                    node = UlNode()
                    node_list.append(node)

                    node.children = await parse(e)

                elif e.name == "a":
                    # 超链接
                    if len(e.contents) == 0:
                        from .utils.parse_link import ResourceType, parse_link

                        parse_link_res = await parse_link(e.attrs["href"])
                        if parse_link_res[1] == ResourceType.VIDEO:
                            node = VideoCardNode()
                            node.aid = parse_link_res[0].get_aid()
                            node_list.append(node)
                        elif parse_link_res[1] == ResourceType.AUDIO:
                            node = MusicCardNode()
                            node.auid = parse_link_res[0].get_auid()
                            node_list.append(node)
                        elif parse_link_res[1] == ResourceType.LIVE:
                            node = LiveCardNode()
                            node.room_id = parse_link_res[0].room_display_id
                            node_list.append(node)
                        elif parse_link_res[1] == ResourceType.ARTICLE:
                            node = ArticleCardNode()
                            node.cvid = parse_link_res[0].get_cvid()
                            node_list.append(node)
                        else:
                            # XXX: 暂不支持其他的站内链接
                            pass
                    else:
                        node = AnchorNode()
                        node_list.append(node)

                        node.url = e.attrs["href"]
                        node.text = e.contents[0]  # type: ignore

                elif e.name == "img":
                    className = e.attrs.get("class") or []

                    if "latex" in className:
                        # 公式
                        node = LatexNode()
                        node.code = unquote(e["alt"])  # type: ignore
                        node_list.append(node)
                    else:
                        # 图片
                        node = ImageNode()
                        node.url = e.attrs.get("data-src")  # type: ignore
                        node_list.append(node)

                elif e.name == "div":
                    node_list += await parse(e)

            return node_list

        # 文章元数据
        self.__meta = copy(resp["readInfo"])
        del self.__meta["content"]

        self.__children = await parse(document.find("div"))
        self.__has_parsed = True

    async def get_info(self) -> dict:
        """
        获取专栏信息

        Returns:
            dict: 调用 API 返回的结果
        """

        api = API["info"]["view"]
        params = {"id": self.__cvid}
        return await Api(**api, credential=self.credential).update_params(**params).result

    async def get_detail(self) -> dict:
        """
        获取专栏详细信息

        Returns:
            dict: 调用 API 返回的结果
        """

        api = API["info"]["detail"]
        params = {"id": self.__cvid}
        return await Api(**api, credential=self.credential).update_params(**params).result

    async def get_all(self) -> dict:
        """
        一次性获取专栏尽可能详细数据，包括原始内容、标签、发布时间、标题、相关专栏推荐等

        Returns:
            dict: 调用 API 返回的结果
        """
        if not self.__get_all_data:
            self.__get_all_data = {"readInfo": await self.get_detail()}
            dyn_id = self.__get_all_data["readInfo"]["dyn_id_str"]
            cache_pool.article2dynamic.set(self.__cvid, dyn_id)
            cache_pool.dynamic2article.set(dyn_id, self.__cvid)
            cache_pool.dynamic_is_article.set(dyn_id, True)
            cache_pool.dynamic_is_opus.set(dyn_id, True)
            cache_pool.article_is_note.set(
                self.get_cvid(), self.__get_all_data["readInfo"]["category"]["id"] in [41, 42]
            )
        return self.__get_all_data

    async def set_like(self, status: bool = True) -> dict:
        """
        设置专栏点赞状态

        Args:
            status (bool, optional): 点赞状态. Defaults to True

        Returns:
            dict: 调用 API 返回的结果
        """
        self.credential.raise_for_no_sessdata()

        api = API["operate"]["like"]
        data = {"id": self.__cvid, "type": 1 if status else 2}
        return await Api(**api, credential=self.credential).update_data(**data).result

    async def set_favorite(self, status: bool = True) -> dict:
        """
        设置专栏收藏状态

        Args:
            status (bool, optional): 收藏状态. Defaults to True

        Returns:
            dict: 调用 API 返回的结果
        """
        self.credential.raise_for_no_sessdata()

        api = API["operate"]["add_favorite"] if status else API["operate"]["del_favorite"]

        data = {"id": self.__cvid}
        return await Api(**api, credential=self.credential).update_data(**data).result

    async def add_coins(self) -> dict:
        """
        给专栏投币，目前只能投一个

        Returns:
            dict: 调用 API 返回的结果
        """
        self.credential.raise_for_no_sessdata()

        upid = (await self.get_info())["mid"]
        api = API["operate"]["coin"]
        data = {"aid": self.__cvid, "multiply": 1, "upid": upid, "avtype": 2}
        return await Api(**api, credential=self.credential).update_data(**data).result

    # TODO: 专栏上传/编辑/删除


class Node:
    """专栏内容节点基类，子类需实现 markdown() 与 json() 序列化方法。"""

    def __init__(self):
        """节点基类无属性，无需初始化。"""
        pass

    @overload
    def markdown(self) -> str:  # type: ignore
        """将节点转换为 Markdown 文本。"""
        pass

    @overload
    def json(self) -> dict:  # type: ignore
        """将节点转换为 JSON 数据。"""
        pass


class ParagraphNode(Node):
    """段落节点，记录对齐方式并包裹子节点。"""

    def __init__(self):
        """初始化子节点列表与默认对齐方式（左对齐）。"""
        self.children = []
        self.align = "left"

    def markdown(self):
        """
        序列化为 Markdown 段落文本

        Returns:
            str: Markdown 内容
        """
        content = "".join([node.markdown() for node in self.children])
        return content + "\n\n"

    def json(self):
        """
        序列化为 JSON 数据

        Returns:
            dict: 含 type 与 children 字段
        """
        return {
            "type": "ParagraphNode",
            "children": [x.json() for x in self.children],
        }


class HeadingNode(Node):
    """标题节点（h1），以二级标题形式输出。"""

    def __init__(self):
        """初始化子节点列表。"""
        self.children = []

    def markdown(self):
        """
        序列化为 Markdown 二级标题

        Returns:
            str: Markdown 内容，子节点为空时返回空字符串
        """
        text = "".join([node.markdown() for node in self.children])
        if len(text) == 0:
            return ""
        return f"## {text}\n\n"

    def json(self):
        """
        序列化为 JSON 数据

        Returns:
            dict: 含 type 与 children 字段
        """
        return {
            "type": "HeadingNode",
            "children": [x.json() for x in self.children],
        }


class BlockquoteNode(Node):
    """引用块节点，每行以 > 前缀输出。"""

    def __init__(self):
        """初始化子节点列表。"""
        self.children = []

    def markdown(self):
        """
        序列化为 Markdown 引用块

        Returns:
            str: Markdown 内容
        """
        t = "".join([node.markdown() for node in self.children])
        # 填补空白行的 > 并加上标识符
        t = "\n".join(["> " + line for line in t.split("\n")]) + "\n\n"

        return t

    def json(self):
        """
        序列化为 JSON 数据

        Returns:
            dict: 含 type 与 children 字段
        """
        return {
            "type": "BlockquoteNode",
            "children": [x.json() for x in self.children],
        }


class ItalicNode(Node):
    """斜体节点，包裹子节点并以 *text* 形式输出。"""

    def __init__(self):
        """初始化子节点列表。"""
        self.children = []

    def markdown(self):
        """
        序列化为 Markdown 斜体文本

        Returns:
            str: Markdown 内容，子节点为空时返回空字符串
        """
        text = "".join([node.markdown() for node in self.children])
        if len(text) == 0:
            return ""
        return f" *{text}* "

    def json(self):
        """
        序列化为 JSON 数据

        Returns:
            dict: 含 type 与 children 字段
        """
        return {
            "type": "ItalicNode",
            "children": [x.json() for x in self.children],
        }


class BoldNode(Node):
    """加粗节点，包裹子节点并以 **text** 形式输出。"""

    def __init__(self):
        """初始化子节点列表。"""
        self.children = []

    def markdown(self):
        """
        序列化为 Markdown 加粗文本

        Returns:
            str: Markdown 内容，子节点为空时返回空字符串
        """
        t = "".join([node.markdown() for node in self.children])
        if len(t) == 0:
            return ""
        return f" **{t.lstrip().rstrip()}** "

    def json(self):
        """
        序列化为 JSON 数据

        Returns:
            dict: 含 type 与 children 字段
        """
        return {
            "type": "BoldNode",
            "children": [x.json() for x in self.children],
        }


class DelNode(Node):
    """删除线节点，包裹子节点并以 ~~text~~ 形式输出。"""

    def __init__(self):
        """初始化子节点列表。"""
        self.children = []

    def markdown(self):
        """
        序列化为 Markdown 删除线文本

        Returns:
            str: Markdown 内容，子节点为空时返回空字符串
        """
        text = "".join([node.markdown() for node in self.children])
        if len(text) == 0:
            return ""
        return f" ~~{text}~~ "

    def json(self):
        """
        序列化为 JSON 数据

        Returns:
            dict: 含 type 与 children 字段
        """
        return {
            "type": "DelNode",
            "children": [x.json() for x in self.children],
        }


class UnderlineNode(Node):
    """下划线节点，包裹子节点并以 LaTeX \\underline{} 形式输出。"""

    def __init__(self):
        """初始化子节点列表。"""
        self.children = []

    def markdown(self):
        """
        序列化为 Markdown 下划线文本（LaTeX 语法）

        Returns:
            str: Markdown 内容，子节点为空时返回空字符串
        """
        text = "".join([node.markdown() for node in self.children])
        if len(text) == 0:
            return ""
        return " $\\underline{" + text + "}$ "

    def json(self):
        """
        序列化为 JSON 数据

        Returns:
            dict: 含 type 与 children 字段
        """
        return {
            "type": "UnderlineNode",
            "children": [x.json() for x in self.children],
        }


class UlNode(Node):
    """无序列表节点，子节点以 - 前缀逐行输出。"""

    def __init__(self):
        """初始化子节点列表。"""
        self.children = []

    def markdown(self):
        """
        序列化为 Markdown 无序列表

        Returns:
            str: Markdown 内容
        """
        return "\n".join(["- " + node.markdown() for node in self.children])

    def json(self):
        """
        序列化为 JSON 数据

        Returns:
            dict: 含 type 与 children 字段
        """
        return {
            "type": "UlNode",
            "children": [x.json() for x in self.children],
        }


class OlNode(Node):
    """有序列表节点，子节点按序号逐行输出。"""

    def __init__(self):
        """初始化子节点列表。"""
        self.children = []

    def markdown(self):
        """
        序列化为 Markdown 有序列表

        Returns:
            str: Markdown 内容
        """
        t = []
        for i, node in enumerate(self.children):
            t.append(f"{i + 1}. {node.markdown()}")
        return "\n".join(t)

    def json(self):
        """
        序列化为 JSON 数据

        Returns:
            dict: 含 type 与 children 字段
        """
        return {
            "type": "OlNode",
            "children": [x.json() for x in self.children],
        }


class LiNode(Node):
    """列表项节点，作为 UlNode/OlNode 的子节点。"""

    def __init__(self):
        """初始化子节点列表。"""
        self.children = []

    def markdown(self):
        """
        序列化为 Markdown 文本（列表前缀由父节点添加）

        Returns:
            str: Markdown 内容
        """
        return "".join([node.markdown() for node in self.children])

    def json(self):
        """
        序列化为 JSON 数据

        Returns:
            dict: 含 type 与 children 字段
        """
        return {
            "type": "LiNode",
            "children": [x.json() for x in self.children],
        }


class ColorNode(Node):
    """文字颜色节点，记录颜色值并透传子节点的 Markdown 输出。"""

    def __init__(self):
        """初始化颜色值（默认黑色）与子节点列表。"""
        self.color = "000000"
        self.children = []

    def markdown(self):
        """
        序列化为 Markdown 文本（Markdown 无颜色语法，仅透传子节点内容）

        Returns:
            str: Markdown 内容
        """
        return "".join([node.markdown() for node in self.children])

    def json(self):
        """
        序列化为 JSON 数据

        Returns:
            dict: 含 type、color 与 children 字段
        """
        return {
            "type": "ColorNode",
            "color": self.color,
            "children": [x.json() for x in self.children],
        }


class FontSizeNode(Node):
    """字号节点，记录字号并透传子节点的 Markdown 输出。"""

    def __init__(self):
        """初始化字号（默认 16）与子节点列表。"""
        self.size = 16
        self.children = []

    def markdown(self):
        """
        序列化为 Markdown 文本（Markdown 无字号语法，仅透传子节点内容）

        Returns:
            str: Markdown 内容
        """
        return "".join([node.markdown() for node in self.children])

    def json(self):
        """
        序列化为 JSON 数据

        Returns:
            dict: 含 type、size 与 children 字段
        """
        return {
            "type": "FontSizeNode",
            "size": self.size,
            "children": [x.json() for x in self.children],
        }


# 特殊节点，即无子节点


class TextNode(Node):
    """纯文本节点，无子节点。"""

    def __init__(self, text: str):
        """
        Args:
            text (str): 文本内容
        """
        self.text = text

    def markdown(self):
        """
        序列化为 Markdown 文本，处理空格/不间断空格并转义 Markdown 特殊字符

        Returns:
            str: Markdown 内容
        """
        txt = self.text
        txt = txt.replace("\t", " ")
        txt = txt.replace(" ", "&emsp;")
        txt = txt.replace(chr(160), "&emsp;")
        special_chars = ["\\", "*", "$", "<", ">", "|", "~", "_"]
        for c in special_chars:
            txt = txt.replace(c, "\\" + c)
        return txt

    def json(self):
        """
        序列化为 JSON 数据

        Returns:
            dict: 含 type 与 text 字段
        """
        return {"type": "TextNode", "text": self.text}


class ImageNode(Node):
    """图片节点，无子节点。"""

    def __init__(self):
        """初始化图片 URL 与替代文本。"""
        self.url = ""
        self.alt = ""

    def markdown(self):
        """
        序列化为 Markdown 图片语法，协议缺失时自动补全 https，并转义 alt 中的方括号

        Returns:
            str: Markdown 图片文本
        """
        if URL(self.url).scheme == "":
            self.url = "https:" + self.url
        alt = self.alt.replace("[", "\\[")
        return f"![{alt}]({self.url})\n\n"

    def json(self):
        """
        序列化为 JSON 数据，协议缺失时自动补全 https

        Returns:
            dict: 含 type、url 与 alt 字段
        """
        if URL(self.url).scheme == "":
            self.url = "https:" + self.url
        return {"type": "ImageNode", "url": self.url, "alt": self.alt}


class LatexNode(Node):
    """LaTeX 公式节点，无子节点；含换行时按块级公式输出，否则按行内公式输出。"""

    def __init__(self):
        """初始化公式代码。"""
        self.code = ""

    def markdown(self):
        """
        序列化为 Markdown 公式（$$...$$ 或 $...$）

        Returns:
            str: Markdown 公式文本
        """
        if "\n" in self.code:
            # 块级公式
            return f"$$\n{self.code}\n$$"
        else:
            # 行内公式
            return f"${self.code}$"

    def json(self):
        """
        序列化为 JSON 数据

        Returns:
            dict: 含 type 与 code 字段
        """
        return {"type": "LatexNode", "code": self.code}


class CodeNode(Node):
    """代码块节点，无子节点，记录代码内容与语言。"""

    def __init__(self):
        """初始化代码内容与语言。"""
        self.code = ""
        self.lang = ""

    def markdown(self):
        """
        序列化为 Markdown 代码块（先反转义 HTML 实体）

        Returns:
            str: Markdown 代码块文本
        """
        self.code = html.unescape(self.code)
        return f"```{self.lang if self.lang else ''}\n{self.code}\n```\n\n"

    def json(self):
        """
        序列化为 JSON 数据（先反转义 HTML 实体）

        Returns:
            dict: 含 type、code 与 lang 字段
        """
        self.code = html.unescape(self.code)
        return {"type": "CodeNode", "code": self.code, "lang": self.lang}


# 卡片


class VideoCardNode(Node):
    """视频卡片节点，无子节点，记录稿件 aid。"""

    def __init__(self):
        """初始化稿件 aid。"""
        self.aid = 0

    def markdown(self):
        """
        序列化为指向视频页的 Markdown 链接

        Returns:
            str: Markdown 链接文本
        """
        return f"[视频 av{self.aid}](https://www.bilibili.com/av{self.aid})\n\n"

    def json(self):
        """
        序列化为 JSON 数据

        Returns:
            dict: 含 type 与 aid 字段
        """
        return {"type": "VideoCardNode", "aid": self.aid}


class ArticleCardNode(Node):
    """文章卡片节点，无子节点，记录专栏 cvid。"""

    def __init__(self):
        """初始化专栏 cvid。"""
        self.cvid = 0

    def markdown(self):
        """
        序列化为指向专栏页的 Markdown 链接

        Returns:
            str: Markdown 链接文本
        """
        return f"[文章 cv{self.cvid}](https://www.bilibili.com/read/cv{self.cvid})\n\n"

    def json(self):
        """
        序列化为 JSON 数据

        Returns:
            dict: 含 type 与 cvid 字段
        """
        return {"type": "ArticleCardNode", "cvid": self.cvid}


class BangumiCardNode(Node):
    """番剧卡片节点，无子节点，记录剧集 epid。"""

    def __init__(self):
        """初始化剧集 epid。"""
        self.epid = 0

    def markdown(self):
        """
        序列化为指向番剧播放页的 Markdown 链接

        Returns:
            str: Markdown 链接文本
        """
        return f"[番剧 ep{self.epid}](https://www.bilibili.com/bangumi/play/ep{self.epid})\n\n"

    def json(self):
        """
        序列化为 JSON 数据

        Returns:
            dict: 含 type 与 epid 字段
        """
        return {"type": "BangumiCardNode", "epid": self.epid}


class MusicCardNode(Node):
    """音乐卡片节点，无子节点，记录音频 auid。"""

    def __init__(self):
        """初始化音频 auid。"""
        self.auid = 0

    def markdown(self):
        """
        序列化为指向音频页的 Markdown 链接

        Returns:
            str: Markdown 链接文本
        """
        return f"[音乐 au{self.auid}](https://www.bilibili.com/audio/au{self.auid})\n\n"

    def json(self):
        """
        序列化为 JSON 数据

        Returns:
            dict: 含 type 与 auid 字段
        """
        return {"type": "MusicCardNode", "auid": self.auid}


class ShopCardNode(Node):
    """会员购卡片节点，无子节点，记录商品 pwid。"""

    def __init__(self):
        """初始化商品 pwid。"""
        self.pwid = 0

    def markdown(self):
        """
        序列化为指向会员购商品页的 Markdown 链接

        Returns:
            str: Markdown 链接文本
        """
        return f"[会员购 {self.pwid}](https://show.bilibili.com/platform/detail.html?id={self.pwid})\n\n"

    def json(self):
        """
        序列化为 JSON 数据

        Returns:
            dict: 含 type 与 pwid 字段
        """
        return {"type": "ShopCardNode", "pwid": self.pwid}


class ComicCardNode(Node):
    """漫画卡片节点，无子节点，记录漫画 mcid。"""

    def __init__(self):
        """初始化漫画 mcid。"""
        self.mcid = 0

    def markdown(self):
        """
        序列化为指向漫画详情页的 Markdown 链接

        Returns:
            str: Markdown 链接文本
        """
        return f"[漫画 mc{self.mcid}](https://manga.bilibili.com/m/detail/mc{self.mcid})\n\n"

    def json(self):
        """
        序列化为 JSON 数据

        Returns:
            dict: 含 type 与 mcid 字段
        """
        return {"type": "ComicCardNode", "mcid": self.mcid}


class LiveCardNode(Node):
    """直播卡片节点，无子节点，记录直播间 room_id。"""

    def __init__(self):
        """初始化直播间 room_id。"""
        self.room_id = 0

    def markdown(self):
        """
        序列化为指向直播间的 Markdown 链接

        Returns:
            str: Markdown 链接文本
        """
        return f"[直播 {self.room_id}](https://live.bilibili.com/{self.room_id})\n\n"

    def json(self):
        """
        序列化为 JSON 数据

        Returns:
            dict: 含 type 与 room_id 字段
        """
        return {"type": "LiveCardNode", "room_id": self.room_id}


class AnchorNode(Node):
    """超链接节点，无子节点，记录链接地址与显示文本。"""

    def __init__(self):
        """初始化链接地址与显示文本。"""
        self.url = ""
        self.text = ""

    def markdown(self):
        """
        序列化为 Markdown 链接，转义显示文本中的方括号

        Returns:
            str: Markdown 链接文本
        """
        text = self.text.replace("[", "\\[")
        return f"[{text}]({self.url})"

    def json(self):
        """
        序列化为 JSON 数据

        Returns:
            dict: 含 type、url 与 text 字段
        """
        return {"type": "AnchorNode", "url": self.url, "text": self.text}


class SeparatorNode(Node):
    """分割线节点，无子节点。"""

    def __init__(self):
        """分割线节点无属性，无需初始化。"""
        pass

    def markdown(self):
        """
        序列化为 Markdown 分割线

        Returns:
            str: Markdown 分割线文本
        """
        return "\n------\n"

    def json(self):
        """
        序列化为 JSON 数据

        Returns:
            dict: 仅含 type 字段
        """
        return {"type": "SeparatorNode"}
