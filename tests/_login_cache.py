"""pytest 临时登录凭据缓存——纯本地逻辑工具集。

缓存文件为系统临时目录（``tempfile.gettempdir()``）下固定名称的
base64(UTF-8 JSON) 文件，格式契约见
specs/001-pytest-temp-login/contracts/cache-file-format.md。

本模块只包含无网络副作用的纯逻辑（路径解析 / 编解码 / 合法性判定 /
凭据来源优先级合并），不导入 bilibili_api，供离线单元测试直接导入。
"""

import base64
import binascii
from dataclasses import dataclass, field
import enum
import json
from pathlib import Path
import tempfile

# 缓存文件固定名称：同机后一次登录覆盖前一次，跨次测试运行按此名称寻回
CACHE_FILENAME = "bilibili_api_pytest_login.json"

# 缓存 JSON 中允许出现的全部凭据字段（均为 str；除必需三键外均可缺省）
CACHE_FIELDS = ("sessdata", "bili_jct", "dedeuserid", "ac_time_value", "buvid3", "buvid4")

# 必需字段：缺失任一（含空串）即判「内容不对」
REQUIRED_FIELDS = ("sessdata", "bili_jct", "dedeuserid")


def get_cache_path() -> Path:
    """
    解析缓存文件的固定路径（系统 TEMP 目录 + 固定文件名）。

    Returns:
        Path: 缓存文件完整路径
    """
    return Path(tempfile.gettempdir()) / CACHE_FILENAME


def encode_credential_cache(fields: dict[str, str | None]) -> str:
    """
    将凭据字段编码为缓存文件内容：base64(UTF-8 JSON)。

    None / 空串 / 契约外字段视为缺失，不写入 JSON；结果为单行 ASCII 字符串。

    Args:
        fields (dict[str, str | None]): 凭据字段集合（值可为 None）

    Returns:
        str: base64 编码后的文件内容
    """
    cleaned = {
        key: value
        for key, value in fields.items()
        if key in CACHE_FIELDS and isinstance(value, str) and value
    }
    payload = json.dumps(cleaned, ensure_ascii=False).encode("utf-8")
    return base64.b64encode(payload).decode("ascii")


class CacheStatus(enum.Enum):
    """缓存读取结果三态。"""

    ABSENT = "absent"
    CORRUPT = "corrupt"
    OK = "ok"


@dataclass
class CacheLoadResult:
    """
    缓存文件读取与合法性判定结果。

    Attributes:
        status (CacheStatus): absent（缺失）/ corrupt（内容不对）/ ok（合法）
        fields (dict[str, str]): 合法时的凭据字段集合；其余状态为空 dict
        reason (str): 面向用户的状态描述（绝不含文件内容或凭据字段值）
    """

    status: CacheStatus
    fields: dict[str, str] = field(default_factory=dict)
    reason: str = ""


def load_cache(path: Path | None = None) -> CacheLoadResult:
    """
    读取并按契约校验缓存文件，判定 absent / corrupt / 合法三态。

    校验规则（任一不满足即 corrupt，对应契约「合法性判定」1–4 条）：
    文件可读且非空 → base64 可解码 → 解码为 UTF-8 JSON 且顶层为对象 →
    必需三键存在且非空。

    Args:
        path (Path | None): 缓存文件路径，缺省使用 get_cache_path()

    Returns:
        CacheLoadResult: 三态结果与用户可读的原因描述
    """
    target = get_cache_path() if path is None else path
    try:
        content = target.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return CacheLoadResult(CacheStatus.ABSENT, reason="缓存文件不存在")
    except (OSError, UnicodeDecodeError):
        return CacheLoadResult(CacheStatus.CORRUPT, reason="文件无法按文本读取")
    if not content:
        return CacheLoadResult(CacheStatus.CORRUPT, reason="文件内容为空")
    try:
        raw = base64.b64decode(content, validate=True)
    except (binascii.Error, ValueError):
        return CacheLoadResult(CacheStatus.CORRUPT, reason="内容不是合法的 base64 文本")
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return CacheLoadResult(CacheStatus.CORRUPT, reason="内容不是合法的 UTF-8 JSON")
    if not isinstance(data, dict):
        return CacheLoadResult(CacheStatus.CORRUPT, reason="JSON 顶层不是对象")
    fields = {
        key: value
        for key, value in data.items()
        if key in CACHE_FIELDS and isinstance(value, str) and value
    }
    missing = [name for name in REQUIRED_FIELDS if name not in fields]
    if missing:
        return CacheLoadResult(CacheStatus.CORRUPT, reason=f"缺少必需字段（{' / '.join(missing)}）")
    return CacheLoadResult(CacheStatus.OK, fields=fields)


def save_cache(fields: dict[str, str | None], path: Path | None = None) -> Path:
    """
    将凭据字段编码后覆盖写入缓存文件。

    Args:
        fields (dict[str, str | None]): 凭据字段集合（None / 空串不写入）
        path (Path | None): 目标路径，缺省使用 get_cache_path()

    Returns:
        Path: 实际写入的路径
    """
    target = get_cache_path() if path is None else path
    target.write_text(encode_credential_cache(fields), encoding="ascii")
    return target


def merge_credential_values(*sources: dict[str, str | None] | None) -> dict[str, str | None]:
    """
    按优先级合并多个凭据来源（参数顺序即优先级，先高后低），字段级覆盖。

    跳过 None / 空串 / 契约外字段；空来源（None 或空 dict）整体忽略。

    Args:
        *sources: 依优先级从高到低排列的凭据字段集合

    Returns:
        dict[str, str | None]: 合并后的字段集合
    """
    merged: dict[str, str | None] = {}
    for source in sources:
        if not source:
            continue
        for key, value in source.items():
            if key in CACHE_FIELDS and isinstance(value, str) and value and key not in merged:
                merged[key] = value
    return merged
