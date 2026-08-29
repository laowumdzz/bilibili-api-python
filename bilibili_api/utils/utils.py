"""
bilibili_api.utils.utils

通用工具库。
"""

import ast
from datetime import datetime
import json
import os
import random
from typing import TypeVar
from urllib.parse import quote

from ..exceptions import ApiException, ArgsException, StatementException

# get_api 的模块级缓存：field -> 已解析的 JSON 文件内容。
# API 定义文件为静态只读数据，首次加载后复用，避免每次调用重复磁盘 I/O 与 JSON 解析。
_api_cache: dict[str, dict] = {}


def get_api(field: str, *args) -> dict:
    """
    获取 API。

    首次调用时加载并缓存对应的 JSON 文件，后续调用直接命中缓存。
    返回的叶子节点为浅拷贝，调用方对其顶层键的修改不会污染缓存，
    但不应原地修改其嵌套结构。

    Args:
        field (str): API 所属分类，即 data/api 下的文件名（不含后缀名）

    Returns:
        dict, 该 API 的内容。
    """
    field_lower = field.lower()
    data = _api_cache.get(field_lower)
    if data is None:
        path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "api", f"{field_lower}.json"))
        if not os.path.exists(path):
            return {}
        with open(path, encoding="utf8") as f:
            data = json.load(f)
        _api_cache[field_lower] = data
    for arg in args:
        data = data[arg]
    if isinstance(data, dict):
        return data.copy()
    return data


# crack_uid 使用的 CRC32 查找表，提升为模块级常量避免每次调用重建。


def _build_crc_table() -> list[int]:
    """构建 crack_uid 所需的 256 项 CRC32 查找表。"""
    crctable = [0] * 256
    for i in range(256):
        crcreg = i
        for _ in range(8):
            if (crcreg & 1) != 0:
                crcreg = 0xEDB88320 ^ (crcreg >> 1)
            else:
                crcreg >>= 1
        crctable[i] = crcreg
    return crctable


_CRC_TABLE = _build_crc_table()


def crack_uid(crc32: str):
    """
    弹幕中的 CRC32 ID 转换成用户 UID。

    警告，破解后的 UID 不一定准确，有存在误差，仅供参考。

    代码翻译自：https://github.com/esterTion/BiliBili_crc2mid。

    Args:
        crc32 (str):  crc32 计算摘要后的 UID。

    Returns:
        int, 真实用户 UID，不一定准确。
    """
    crctable = _CRC_TABLE
    __index = [None] * 4

    def __crc32(input_):
        if not isinstance(input_, str):
            input_ = str(input_)
        crcstart = 0xFFFFFFFF
        len_ = len(input_)
        for i in range(len_):
            index = (crcstart ^ ord(input_[i])) & 0xFF
            crcstart = (crcstart >> 8) ^ crctable[index]
        return crcstart

    def __crc32lastindex(input_):
        if not isinstance(input_, str):
            input_ = str(input_)
        crcstart = 0xFFFFFFFF
        len_ = len(input_)
        index = None
        for i in range(len_):
            index = (crcstart ^ ord(input_[i])) & 0xFF
            crcstart = (crcstart >> 8) ^ crctable[index]
        return index

    def __getcrcindex(t):
        for i in range(256):
            if crctable[i] >> 24 == t:
                return i
        return -1

    def __deepCheck(i, index):
        tc = 0x00
        str_ = ""
        hash_ = __crc32(i)
        tc = hash_ & 0xFF ^ index[2]
        if not (57 >= tc >= 48):
            return [0]
        str_ += str(tc - 48)
        hash_ = crctable[index[2]] ^ (hash_ >> 8)

        tc = hash_ & 0xFF ^ index[1]
        if not (57 >= tc >= 48):
            return [0]
        str_ += str(tc - 48)
        hash_ = crctable[index[1]] ^ (hash_ >> 8)

        tc = hash_ & 0xFF ^ index[0]
        if not (57 >= tc >= 48):
            return [0]
        str_ += str(tc - 48)
        hash_ = crctable[index[0]] ^ (hash_ >> 8)

        return [1, str_]

    ht = int(crc32, 16) ^ 0xFFFFFFFF
    i = 3
    while i >= 0:
        __index[3 - i] = __getcrcindex(ht >> (i * 8))
        # pylint: disable=invalid-sequence-index
        snum = crctable[__index[3 - i]]
        ht ^= snum >> ((3 - i) * 8)
        i -= 1
    for i in range(10000000):
        lastindex = __crc32lastindex(i)
        if lastindex == __index[3]:
            deepCheckData = __deepCheck(i, __index)
            if deepCheckData[0]:
                break
    if i == 10000000:
        return -1
    return str(i) + deepCheckData[1]


def join(seperator: str, array: list):
    """
    用指定字符连接数组

    Args:
        seperator (str) : 分隔字符

        array     (list): 数组

    Returns:
        str: 连接结果
    """
    return seperator.join(str(x) for x in array)


ChunkT = TypeVar("ChunkT", list, list)


def chunk(arr: ChunkT, size: int) -> list[ChunkT]:
    if size <= 0:
        raise ArgsException('Parameter "size" must greater than 0')

    result = []
    temp = []

    for i in range(len(arr)):
        temp.append(arr[i])

        if i % size == size - 1:
            result.append(temp)
            temp = []

    if temp:
        result.append(temp)

    return result


def get_deviceid(separator: str = "-", is_lowercase: bool = False) -> str:
    """
    获取随机 deviceid (dev_id)

    Args:
        separator (str)  : 分隔符 默认为 "-"

        is_lowercase (bool) : 是否以小写形式 默认为False

    参考: https://github.com/SocialSisterYi/bilibili-API-collect/blob/master/docs/message/private_msg.md#发送私信web端

    Returns:
        str: device_id
    """
    template = ["xxxxxxxx", "xxxx", "4xxx", "yxxx", "xxxxxxxxxxxx"]
    dev_id_group = []
    for i in range(len(template)):
        s = ""
        group = template[i]
        for k in group:
            rand: int = int(16 * random.random())
            if k in "xy":
                if k == "x":
                    s += hex(rand)[2:]
                else:
                    s += hex(3 & rand | 8)[2:]
            else:
                s += "4"
        dev_id_group.append(s)
    res = join(separator, dev_id_group)
    return res if is_lowercase else res.upper()


def raise_for_statement(statement: bool, msg: str = "未满足条件") -> None:
    if not statement:
        raise StatementException(msg=msg)


def to_form_urlencoded(data: dict) -> str:
    temp = []
    for [k, v] in data.items():
        temp.append(f"{k}={quote(str(v)).replace('/', '%2F')}")

    return "&".join(temp)


def to_timestamps(time_start, time_end):
    """
    将两个日期字符串转换为整数时间戳 (int) 元组，并验证时间顺序。

    Returns:
        tuple: (int,int)
    """
    try:
        # 将输入字符串解析为 datetime 对象
        start_dt = datetime.strptime(time_start, "%Y-%m-%d")
        end_dt = datetime.strptime(time_end, "%Y-%m-%d")

        # 验证起始时间是否早于结束时间
        if start_dt >= end_dt:
            raise ValueError("起始时间必须早于结束时间。")

        # 转换为时间戳并返回
        return int(start_dt.timestamp()), int(end_dt.timestamp())
    except ValueError as e:
        # 捕获日期格式错误或自定义错误消息
        raise ValueError(f"输入错误: {e}. 请确保使用 'YYYY-MM-DD' 格式，并且起始时间早于结束时间。") from e


def img_auto_scheme(url: str) -> str:
    """
    自动补全图片链接的 scheme

    Returns:
        str: 带有 scheme 的 url
    """
    if url.startswith("//"):
        return "https:" + url
    return url


def restricted_eval(expression: str):
    """
    受限表达式求值（eval() 的安全替代）。

    仅支持常量（bool / int / float）与算术、比较、布尔、一元（not / 正负号）运算，
    函数调用、属性访问、标识符引用、下标等其余语法一律拒绝。
    用于求值来自远端、不可信任的互动视频脚本表达式，调用前须先完成
    变量替换与 JS 语法转换（如 && -> and、|| -> or）。

    Args:
        expression (str): 待求值的表达式

    Returns:
        表达式求值结果。

    Raises:
        ApiException: 表达式语法非法或包含不允许的语法时抛出。
    """
    try:
        # 去除首尾空白，避免 eval 模式下的 ast.parse 将前导空格误报为缩进错误
        node = ast.parse(expression.strip(), mode="eval").body
    except (SyntaxError, ValueError, RecursionError) as e:
        raise ApiException(f"拒绝求值非法表达式: {e}") from None
    return _eval_safe_node(node)


def _eval_safe_node(node: ast.AST):
    """递归求值 restricted_eval 白名单内的 AST 节点。"""
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (bool, int, float)):
            return node.value
        raise ApiException(f"拒绝求值类型为 {type(node.value).__name__} 的常量")
    if isinstance(node, ast.BoolOp):
        # 保持 Python 短路求值语义：返回决定结果的操作数
        if isinstance(node.op, ast.And):
            result = True
            for value_node in node.values:
                result = _eval_safe_node(value_node)
                if not result:
                    break
            return result
        if isinstance(node.op, ast.Or):
            result = False
            for value_node in node.values:
                result = _eval_safe_node(value_node)
                if result:
                    break
            return result
        raise ApiException(f"拒绝求值布尔运算符 {type(node.op).__name__}")
    if isinstance(node, ast.UnaryOp):
        operand = _eval_safe_node(node.operand)
        if isinstance(node.op, ast.Not):
            return not operand
        if isinstance(node.op, ast.USub):
            return -operand
        if isinstance(node.op, ast.UAdd):
            return +operand
        raise ApiException(f"拒绝求值一元运算符 {type(node.op).__name__}")
    if isinstance(node, ast.BinOp):
        if isinstance(node.op, ast.Pow):
            # 先静态检查指数，避免先求值超大指数造成计算资源耗尽
            exponent = _safe_pow_exponent(node.right)
            return _eval_safe_node(node.left) ** exponent
        left = _eval_safe_node(node.left)
        right = _eval_safe_node(node.right)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        if isinstance(node.op, ast.Div):
            return left / right
        if isinstance(node.op, ast.FloorDiv):
            return left // right
        if isinstance(node.op, ast.Mod):
            return left % right
        raise ApiException(f"拒绝求值运算符 {type(node.op).__name__}")
    if isinstance(node, ast.Compare):
        left = _eval_safe_node(node.left)
        for op, comparator in zip(node.ops, node.comparators, strict=True):
            right = _eval_safe_node(comparator)
            if isinstance(op, ast.Eq):
                passed = left == right
            elif isinstance(op, ast.NotEq):
                passed = left != right
            elif isinstance(op, ast.Lt):
                passed = left < right
            elif isinstance(op, ast.LtE):
                passed = left <= right
            elif isinstance(op, ast.Gt):
                passed = left > right
            elif isinstance(op, ast.GtE):
                passed = left >= right
            else:
                raise ApiException(f"拒绝求值比较运算符 {type(op).__name__}")
            if not passed:
                return False
            left = right
        return True
    raise ApiException(f"拒绝求值表达式中的非法语法 {type(node).__name__}")


def _safe_pow_exponent(node: ast.AST) -> int | float:
    """静态校验幂运算指数：仅允许绝对值不超过 64 的数字常量，防止超大指数运算拖垮进程。"""
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        return -_safe_pow_exponent(node.operand)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
        if abs(node.value) > 64:
            raise ApiException("拒绝求值指数超过 64 的幂运算")
        return node.value
    raise ApiException("拒绝求值指数非常量的幂运算")
