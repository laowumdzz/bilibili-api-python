"""
bilibili_api.note

笔记相关
"""

from enum import Enum
from html import unescape
import json
from typing import overload

import yaml
from yarl import URL

from . import article
from .exceptions import ApiException, ArgsException
from .utils import cache_pool
from .utils.initial_state import get_initial_state
from .utils.network import Api, Credential
from .utils.picture import Picture
from .utils.utils import get_api, img_auto_scheme, raise_for_statement

API = get_api("note")
API_ARTICLE = get_api("article")


async def upload_image(img: Picture, credential: Credential) -> dict:
    """
    上传笔记图片

    Args:
        img        (Picture)   : 图片
        credential (Credential): 凭据类

    Returns:
        dict: 调用 API 返回的结果
    """
    credential.raise_for_no_sessdata()
    credential.raise_for_no_bili_jct()
    api = API["operate"]["upload_img"]
    files = {"file": img._to_biliapifile()}
    return await Api(**api, credential=credential).update_files(**files).result


class NoteType(Enum):
    """
    笔记类型
    """

    PUBLIC = "public"
    PRIVATE = "private"


class Note:
    """
    笔记相关
    """

    def __init__(
        self,
        cvid: int | None = None,
        aid: int | None = None,
        note_id: int | None = None,
        note_type: NoteType = NoteType.PUBLIC,
        credential: Credential | None = None,
    ):
        """
        Args:
            cvid       (int)                  : 公开笔记 ID (对应专栏的 cvid) (公开笔记必要)

            aid        (int)                  : 稿件 ID（oid_type 为 0 时是 avid） (私有笔记必要)

            note_id    (int)                  : 私有笔记 ID (私有笔记必要)

            note_type  (str)                  : 笔记类型 (private, public)

            credential (Credential, optional) : Credential. Defaults to None.
        """
        self.__oid = -1
        self.__note_id = -1
        self.__cvid = -1
        # ID 和 type 检查
        if note_type == NoteType.PRIVATE:
            if not aid or not note_id:
                raise ArgsException("私有笔记需要 oid 和 note_id")
            self.__oid = aid
            self.__note_id = note_id
        elif note_type == NoteType.PUBLIC:
            if not cvid:
                raise ArgsException("公开笔记需要 cvid")
            self.__cvid = cvid
        else:
            raise ArgsException("type_ 只能是 public 或 private")

        self.__type = note_type

        # 未提供 credential 时初始化该类
        # 私有笔记需要 credential
        self.credential: Credential = Credential() if credential is None else credential

        # 用于存储视频信息，避免接口依赖视频信息时重复调用
        self.__info: dict | None = None

        # 用于存储正文的节点
        self.__children: list[Node] = []
        # 用于存储是否解析
        self.__has_parsed: bool = False
        # 用于存储转换为 markdown 和 json 时使用的信息
        self.__meta: dict = {}

    def get_cvid(self) -> int:
        """
        获取公开笔记 cvid

        Returns:
            int: 公开笔记 cvid
        """
        return self.__cvid

    def get_aid(self) -> int:
        """
        获取私有笔记对应视频 aid

        Returns:
            int: aid
        """
        return self.__oid

    def get_note_id(self) -> int:
        """
        获取私有笔记 note_id

        Returns:
            int: note_id
        """
        return self.__note_id

    def turn_to_article(self) -> "article.Article":
        """
        将笔记类转为专栏类。需要保证笔记是公开笔记。

        Returns:
            Note: 专栏类
        """
        raise_for_statement(self.__type == NoteType.PUBLIC)
        return article.Article(cvid=self.get_cvid(), credential=self.credential)

    async def get_info(self) -> dict:
        """
        获取笔记信息

        Returns:
            dict: 笔记信息
        """
        if self.__type == NoteType.PRIVATE:
            return await self.get_private_note_info()
        else:
            return await self.get_public_note_info()

    async def __get_info_cached(self) -> dict:
        """
        获取视频信息，如果已获取过则使用之前获取的信息，没有则重新获取。

        Returns:
            dict: 调用 API 返回的结果。
        """
        if self.__info is None:
            return await self.get_info()
        return self.__info

    async def get_private_note_info(self) -> dict:
        """
        获取私有笔记信息。

        Returns:
            dict: 调用 API 返回的结果。
        """
        raise_for_statement(self.__type == NoteType.PRIVATE)

        api = API["private"]["detail"]
        # oid 为 0 时指 avid
        params = {"oid": self.get_aid(), "note_id": self.get_note_id(), "oid_type": 0}
        resp = await Api(**api, credential=self.credential).update_params(**params).result
        # 存入 self.__info 中以备后续调用
        self.__info = resp
        return resp

    async def get_public_note_info(self) -> dict:
        """
        获取公有笔记信息。

        Returns:
            dict: 调用 API 返回的结果。
        """

        raise_for_statement(self.__type == NoteType.PUBLIC)

        api = API["public"]["detail"]
        params = {"cvid": self.get_cvid()}
        resp = await Api(**api, credential=self.credential).update_params(**params).result
        # 存入 self.__info 中以备后续调用
        self.__info = resp
        cache_pool.article_is_note[self.__cvid] = True
        return resp

    async def get_images_raw_info(self) -> list["dict"]:
        """
        获取笔记所有图片原始信息

        Returns:
            list: 图片信息
        """

        result = []
        content = (await self.__get_info_cached())["content"]
        for line in content:
            if isinstance(line["insert"], dict):
                if "imageUpload" in line["insert"]:
                    img_info = line["insert"]["imageUpload"]
                    result.append(img_info)
        return result

    async def get_images(self) -> list["Picture"]:
        """
        获取笔记所有图片并转为 Picture 类

        Returns:
            list: 图片信息
        """

        result = []
        images_raw_info = await self.get_images_raw_info()
        for image in images_raw_info:
            result.append(await Picture().load_url(url=img_auto_scheme(image["url"])))
        return result

    async def get_all(self) -> dict:
        """
        (仅供公开笔记)

        一次性获取专栏尽可能详细数据，包括原始内容、标签、发布时间、标题、相关专栏推荐等

        Returns:
            dict: 调用 API 返回的结果
        """
        raise_for_statement(self.__type == NoteType.PUBLIC)
        return await get_initial_state(f"https://www.bilibili.com/read/cv{self.__cvid}")

    async def set_like(self, status: bool = True) -> dict:
        """
        (仅供公开笔记)

        设置专栏点赞状态

        Args:
            status (bool, optional): 点赞状态. Defaults to True

        Returns:
            dict: 调用 API 返回的结果
        """
        raise_for_statement(self.__type == NoteType.PUBLIC)

        self.credential.raise_for_no_sessdata()

        api = API_ARTICLE["operate"]["like"]
        data = {"id": self.__cvid, "type": 1 if status else 2}
        return await Api(**api, credential=self.credential).update_data(**data).result

    async def set_favorite(self, status: bool = True) -> dict:
        """
        (仅供公开笔记)

        设置专栏收藏状态

        Args:
            status (bool, optional): 收藏状态. Defaults to True

        Returns:
            dict: 调用 API 返回的结果
        """
        raise_for_statement(self.__type == NoteType.PUBLIC)

        self.credential.raise_for_no_sessdata()

        api = API_ARTICLE["operate"]["add_favorite"] if status else API_ARTICLE["operate"]["del_favorite"]

        data = {"id": self.__cvid}
        return await Api(**api, credential=self.credential).update_data(**data).result

    async def add_coins(self) -> dict:
        """
        (仅供公开笔记)

        给笔记投币，目前只能投一个。

        Returns:
            dict: 调用 API 返回的结果
        """
        raise_for_statement(self.__type == NoteType.PUBLIC)

        self.credential.raise_for_no_sessdata()

        upid = (await self.get_info())["mid"]
        api = API_ARTICLE["operate"]["coin"]
        data = {"aid": self.__cvid, "multiply": 1, "upid": upid, "avtype": 2}
        return await Api(**api, credential=self.credential).update_data(**data).result

    async def fetch_content(self) -> None:
        """
        获取并解析笔记内容

        该返回不会返回任何值，调用该方法后请再调用 `self.markdown()` 或 `self.json()` 来获取你需要的值。
        """

        async def parse_note(data: list[dict]):
            """
            将笔记内容 JSON 逐字段解析为节点树，追加到 self.__children。

            Args:
                data (list[dict]): 笔记内容字段列表，每项含 insert（文本或图片/分割线）与可选 attributes（加粗/删除线等）
            """
            for field in data:
                if not isinstance(field["insert"], str):
                    if "imageUpload" in field["insert"].keys():
                        node = ImageNode()
                        node.url = field["insert"]["imageUpload"]["url"]
                        self.__children.append(node)
                    elif "cut-off" in field["insert"].keys():
                        node = ImageNode()
                        node.url = field["insert"]["cut-off"]["url"]
                        self.__children.append(node)
                else:
                    node = TextNode(field["insert"])
                    if "attributes" in field.keys():
                        if field["attributes"].get("bold"):
                            bold = BoldNode()
                            bold.children = [node]
                            node = bold
                        if field["attributes"].get("strike"):
                            delete = DelNode()
                            delete.children = [node]
                            node = delete
                        if field["attributes"].get("underline"):
                            underline = UnderlineNode()
                            underline.children = [node]
                            node = underline
                        if field["attributes"].get("background"):
                            # FIXME: 暂不支持背景颜色
                            pass
                        if field["attributes"].get("color") is not None:
                            color = ColorNode()
                            color.color = field["attributes"]["color"].replace("#", "")
                            color.children = [node]
                            node = color
                        if field["attributes"].get("size") is not None:
                            size = FontSizeNode()
                            size.size = field["attributes"]["size"]
                            size.children = [node]
                            node = size
                    else:
                        pass
                    self.__children.append(node)

        info = await self.get_info()
        content = info["content"]
        content = unescape(content)
        await parse_note(json.loads(content))
        self.__has_parsed = True
        self.__meta = await self.__get_info_cached()
        del self.__meta["content"]

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
                pass
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
            "type": "Note",
            "meta": self.__meta,
            "children": [x.json() for x in self.__children],
        }

    # TODO: 笔记上传/编辑/删除


class Node:
    """笔记内容节点基类，子类需实现 markdown() 与 json() 序列化方法。"""

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


class BoldNode(Node):
    """加粗节点，包裹子节点并以 **text** 形式输出。"""

    def __init__(self):
        """初始化子节点列表。"""
        self.children = []

    def markdown(self):
        """
        转换为 Markdown 加粗文本

        Returns:
            str: Markdown 内容，子节点为空时返回空字符串
        """
        t = "".join([node.markdown() for node in self.children])
        if len(t) == 0:
            return ""
        return f" **{t.lstrip().rstrip()}** "

    def json(self):
        """
        转换为 JSON 数据

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
        转换为 Markdown 删除线文本

        Returns:
            str: Markdown 内容，子节点为空时返回空字符串
        """
        text = "".join([node.markdown() for node in self.children])
        if len(text) == 0:
            return ""
        return f" ~~{text}~~"

    def json(self):
        """
        转换为 JSON 数据

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
        转换为 Markdown 下划线文本（LaTeX 语法）

        Returns:
            str: Markdown 内容，子节点为空时返回空字符串
        """
        text = "".join([node.markdown() for node in self.children])
        if len(text) == 0:
            return ""
        return " $\\underline{" + text + "}$ "


class ColorNode(Node):
    """文字颜色节点，记录颜色值并透传子节点的 Markdown 输出。"""

    def __init__(self):
        """初始化颜色值（默认黑色）与子节点列表。"""
        self.color = "000000"
        self.children = []

    def markdown(self):
        """
        转换为 Markdown 文本（Markdown 无颜色语法，仅透传子节点内容）

        Returns:
            str: Markdown 内容
        """
        return "".join([node.markdown() for node in self.children])

    def json(self):
        """
        转换为 JSON 数据

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
        转换为 Markdown 文本（Markdown 无字号语法，仅透传子节点内容）

        Returns:
            str: Markdown 内容
        """
        return "".join([node.markdown() for node in self.children])

    def json(self):
        """
        转换为 JSON 数据

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
        转换为 Markdown 文本

        Returns:
            str: 文本内容
        """
        return self.text

    def json(self):
        """
        转换为 JSON 数据

        Returns:
            dict: 含 type 与 text 字段
        """
        return {"type": "TextNode", "text": self.text}


class ImageNode(Node):
    """图片节点（含分割线图片），无子节点。"""

    def __init__(self):
        """初始化图片 URL 与替代文本。"""
        self.url = ""
        self.alt = ""

    def markdown(self):
        """
        转换为 Markdown 图片语法，协议缺失时自动补全 https，并转义 alt 中的方括号

        Returns:
            str: Markdown 图片文本
        """
        if URL(self.url).scheme == "":
            self.url = "https:" + self.url
        alt = self.alt.replace("[", "\\[")
        return f"![{alt}]({self.url})\n\n"

    def json(self):
        """
        转换为 JSON 数据，协议缺失时自动补全 https

        Returns:
            dict: 含 type、url 与 alt 字段
        """
        if URL(self.url).scheme == "":
            self.url = "https:" + self.url
        return {"type": "ImageNode", "url": self.url, "alt": self.alt}
