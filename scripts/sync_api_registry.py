"""bilibili-api-registry → bilibili_api/data/api 增量同步脚本。

从项目目录下的 bilibili-api-registry 子项目（bilibili-api-collect 文档
抽取的接口注册表）读取 REST 接口定义，将本项目 data/api 中尚不存在的
接口以新增顶层 section 的方式合并进对应 JSON 文件。

同步原则：

- 纯增量：已存在的接口（按规范化 URL 判断）一律不动，仅追加缺失项；
  gRPC（本项目无运行时支持）与 method=OTHER（网页地址等）条目跳过。
- 字节级保留：既有文件只做文本插入（在最后一个 `}` 前追加新 section），
  不重排、不重格式化，避免无关 diff。
- 键名生成：取 URL 路径最后一个非泛型段（跳过 v1/v2/纯数字），驼峰转
  下划线；同 section 内冲突时追加 _2/_3。
- verify 推断：registry notes 含 SESSDATA/Cookie/access_key/登录 时
  标记 ``"verify": true``，否则省略该键（默认 False）。
- 认证等额外说明折入 comment / 参数描述；registry 的 doc_source、
  notes 等字段不得进入 JSON（``Api(**api)`` 不接受未知键）。

用法：``uv run python scripts/sync_api_registry.py [--dry-run]``
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent
REGISTRY_DIR = REPO_ROOT / "bilibili-api-registry"
API_DIR = REPO_ROOT / "bilibili_api" / "data" / "api"

VALID_METHODS = {"GET", "POST", "PUT", "DELETE", "PATCH"}

# registry 类别 → 本项目 data/api 文件名（不含 .json）。
# 无对应文件的类别（misc/electric/vip 等）按 registry 类别名新建文件。
CATEGORY_FILE: dict[str, str] = {
    "activity": "activity",
    "album": "album",
    "APP_widget": "app",
    "article": "article",
    "audio": "audio",
    "bangumi": "bangumi",
    "blackroom": "black-room",
    "clientinfo": "clientinfo",
    "comment": "common",
    "creativecenter": "creative_center",
    "customerservice": "customerservice",
    "danmaku": "video",
    "dynamic": "dynamic",
    "electric": "electric",
    "emoji": "emoji",
    "fav": "favorite-list",
    "garb": "garb",
    "historytoview": "toview",
    "live": "live",
    "login": "login",
    "manga": "manga",
    "message": "session",
    "misc": "misc",
    "newbie_exam": "newbie_exam",
    "note": "note",
    "search": "search",
    "teenager": "teenager",
    "user": "user",
    "video": "video",
    "video_ranking": "rank",
    "vip": "vip",
    "wallet": "wallet",
    "web_widget": "web_widget",
}

# (类别, 子主题) 级定向覆盖：(文件名, section 名)。
SUBTOPIC_OVERRIDES: dict[tuple[str, str], tuple[str, str]] = {
    ("video", "tags"): ("video_tag", "tags"),
    ("video", "interact_video"): ("interactive_video", "interact_video"),
}

# section 名固定加类别前缀的类别（避免与目标文件的泛名 section 混淆）。
SECTION_PREFIX: dict[str, str] = {
    "comment": "comment",
    "danmaku": "danmaku",
}

# registry 参数类型 → 本项目 params 描述的类型前缀。
TYPE_MAP: dict[str, str] = {
    "num": "int",
    "str": "str",
    "bool": "bool",
    "array": "list",
    "object": "dict",
    "unknown": "str",
}

AUTH_RE = re.compile(r"sessdata|cookie|access_key|登录", re.IGNORECASE)
GENERIC_SEGMENTS = {"v0", "v1", "v2", "v3"}

# 不得用作接口键名：与 Api 字段/叶子判定结构冲突（如 section 下出现
# {"url": {…}} 会被校验逻辑误判为叶子）。
RESERVED_KEYS = {
    "url",
    "method",
    "verify",
    "params",
    "data",
    "comment",
    "files",
    "headers",
    "credential",
}


def norm_url(url: str) -> str:
    """规范化 URL 用于去重比对（去协议/域名/查询串，统一小写）。"""
    u = re.sub(r"^\w+://", "", url.strip())
    return u.split("?")[0].rstrip("/").lower()


def key_from_url(url: str) -> str:
    """从 URL 路径生成接口键名：最后一个非泛型、非保留段，驼峰转下划线。"""
    segments = [s for s in urlsplit(url).path.split("/") if s]
    key = ""
    for seg in reversed(segments):
        if seg.lower() in GENERIC_SEGMENTS or seg.isdigit():
            continue
        candidate = re.sub(r"(?<=[a-z0-9])([A-Z])", r"_\1", seg).lower()
        candidate = re.sub(r"[^a-z0-9_]", "_", candidate).strip("_")
        if not candidate or candidate in RESERVED_KEYS:
            continue
        key = candidate
        break
    if not key:
        key = re.sub(r"[^a-z0-9_]", "_", urlsplit(url).netloc.split(".")[0]).strip("_")
    return key or "endpoint"


def param_desc(param: dict) -> str:
    """将 registry 参数条目转为本项目 ``类型: 描述`` 格式。"""
    parts = [str(param.get("description", "")).strip()]
    note = str(param.get("note", "")).strip()
    if note and note not in parts:
        parts.append(note)
    default = param.get("default")
    if default is not None and str(default).strip():
        parts.append(f"默认 {default}")
    desc = "；".join(part for part in parts if part)
    if param.get("required"):
        desc = f"必填，{desc}" if desc else "必填"
    ptype = TYPE_MAP.get(str(param.get("type", "unknown")), "str")
    return f"{ptype}: {desc}" if desc else f"{ptype}:"


def build_entry(endpoint: dict) -> dict:
    """将 registry endpoint 转为本项目 data/api 条目（键序与既有文件一致）。"""
    entry: dict = {"url": endpoint["url"], "method": endpoint["method"]}
    if AUTH_RE.search(endpoint.get("notes", "") or ""):
        entry["verify"] = True
    params = {p["name"]: param_desc(p) for p in endpoint.get("params", [])}
    if params:
        entry["params"] = params
    entry["comment"] = endpoint.get("name", "")
    return entry


def load_registry() -> list[dict]:
    """加载 registry 全部 REST 条目（排除 gRPC 目录与 method=OTHER）。

    每个条目附加 _category / _subtopic 元数据供目标解析使用。
    """
    endpoints: list[dict] = []
    for file in sorted(REGISTRY_DIR.rglob("*.json")):
        if file.name == "schema.json" or "scripts" in file.parts or "grpc" in file.parts:
            continue
        data = json.loads(file.read_text(encoding="utf-8"))
        for endpoint in data.get("endpoints", []):
            if endpoint.get("endpoint_type") != "rest" or endpoint["method"] not in VALID_METHODS:
                continue
            endpoint["_category"] = data["category"]
            endpoint["_subtopic"] = data.get("subtopic", "")
            endpoints.append(endpoint)
    return endpoints


def load_current_files() -> tuple[dict[str, str], set[str], dict[str, set[str]]]:
    """读取 data/api 全部文件原文与既有顶层 section 名，收集已存在 URL 集。"""
    raws: dict[str, str] = {}
    known_urls: set[str] = set()
    file_sections: dict[str, set[str]] = {}
    for file in sorted(API_DIR.glob("*.json")):
        raw = file.read_bytes().decode("utf-8")
        data = json.loads(raw)
        raws[file.stem] = raw
        file_sections[file.stem] = set(data.keys())
        for section_apis in data.values():
            if not isinstance(section_apis, dict):
                continue
            for value in section_apis.values():
                if isinstance(value, dict) and "url" in value:
                    known_urls.add(norm_url(value["url"]))
    return raws, known_urls, file_sections


def normalize_section(name: str, category: str) -> str:
    """section 名归一为小写 snake_case（QR→qr、statistics&data→statistics_data）。"""
    normalized = re.sub(r"(?<=[a-z0-9])([A-Z])", r"_\1", name).lower()
    normalized = re.sub(r"[^a-z0-9_]", "_", normalized).strip("_")
    return normalized or category.lower()


def resolve_target(endpoint: dict, file_sections: dict[str, set[str]]) -> tuple[str, str]:
    """解析 registry 条目 → (目标文件名, section 名)。

    section 与目标文件既有顶层键（含本轮已追加的）冲突时退回
    ``类别_子主题`` 命名，避免覆盖或语义混淆。
    """
    category = endpoint["_category"]
    subtopic = endpoint["_subtopic"]
    file_name, section = SUBTOPIC_OVERRIDES.get((category, subtopic), (CATEGORY_FILE[category], subtopic))
    prefix = SECTION_PREFIX.get(category)
    if prefix and not section.startswith(prefix):
        section = f"{prefix}_{section}"
    section = normalize_section(section, category)
    sections = file_sections.setdefault(file_name, set())
    if section in sections:
        fallback = f"{category.lower()}_{subtopic}" if subtopic else category.lower()
        fallback = normalize_section(fallback, category)
        n = 2
        while fallback in sections:
            fallback = f"{category.lower()}_{subtopic}_{n}"
            fallback = normalize_section(fallback, category)
            n += 1
        section = fallback
    sections.add(section)
    return file_name, section


def append_sections(raw: str, sections: dict[str, dict]) -> str:
    """在 JSON 文本最后一个 `}` 前追加新顶层 section，其余字节原样保留。"""
    newline = "\r\n" if "\r\n" in raw else "\n"
    body = json.dumps(sections, ensure_ascii=False, indent=2)
    body = body[len("{\n") : -len("\n}")].replace("\n", newline)
    match = re.search(r"\}[ \t\r\n]*$", raw)
    if match is None or not raw[: match.start()].rstrip().endswith("}"):
        raise ValueError("文件结构异常：未找到顶层收尾大括号")
    head = raw[: match.start()].rstrip()
    tail = raw[match.start() :]
    return head + "," + newline + body + newline + tail


def check_no_dup_keys(pairs: list[tuple[str, object]]) -> dict:
    """json.loads 的 object_pairs_hook：检测重复键。"""
    keys = [k for k, _ in pairs]
    dups = {k for k in keys if keys.count(k) > 1}
    if dups:
        raise ValueError(f"发现重复键: {dups}")
    return dict(pairs)


def validate_output(name: str, text: str) -> int:
    """校验写入前的最终文本：可解析、无重复键、叶子结构合法；返回叶子数。"""
    data = json.loads(text, object_pairs_hook=check_no_dup_keys)
    count = 0

    def walk(node: dict) -> None:
        nonlocal count
        if "url" in node:
            count += 1
            assert node["url"].startswith("http"), f"{name}: url 非法 {node['url']}"
            assert node["method"].upper() in VALID_METHODS, f"{name}: method 非法"
            for payload_key in ("params", "data"):
                if payload_key in node:
                    assert isinstance(node[payload_key], (dict, str))
            return
        for value in node.values():
            if isinstance(value, dict):
                walk(value)

    walk(data)
    return count


def count_leaves(text: str) -> int:
    """统计既有 JSON 文本的接口叶子数（不做结构校验，仅作前后对比）。"""
    data = json.loads(text)
    count = 0

    def walk(node: dict) -> None:
        nonlocal count
        if "url" in node:
            count += 1
            return
        for value in node.values():
            if isinstance(value, dict):
                walk(value)

    walk(data)
    return count


def main(argv: list[str]) -> int:
    """执行同步；返回 0 表示成功。"""
    dry_run = "--dry-run" in argv
    endpoints = load_registry()
    raws, known_urls, file_sections = load_current_files()

    # 文件名 → {section: {键: 条目}}（保持 registry 遍历顺序，确定性输出）。
    file_additions: dict[str, dict[str, dict]] = {}
    target_cache: dict[tuple[str, str], tuple[str, str]] = {}
    used_urls: set[str] = set()
    used_keys: set[tuple[str, str, str]] = set()
    skipped_known = skipped_dup = 0

    for endpoint in endpoints:
        norm = norm_url(endpoint["url"])
        if norm in known_urls:
            skipped_known += 1
            continue
        if norm in used_urls:
            skipped_dup += 1
            continue
        used_urls.add(norm)

        file_name, section = target_cache.get((endpoint["_category"], endpoint["_subtopic"])) or resolve_target(
            endpoint, file_sections
        )
        target_cache[(endpoint["_category"], endpoint["_subtopic"])] = (file_name, section)
        key = key_from_url(endpoint["url"])
        base_key, n = key, 1
        while (file_name, section, key) in used_keys:
            n += 1
            key = f"{base_key}_{n}"
        used_keys.add((file_name, section, key))
        file_additions.setdefault(file_name, {}).setdefault(section, {})[key] = build_entry(endpoint)

    total = sum(len(eps) for secs in file_additions.values() for eps in secs.values())
    logger.info(
        "registry REST 条目 %d：已存在 %d，registry 内重复 %d，本次新增 %d",
        len(endpoints),
        skipped_known,
        skipped_dup,
        total,
    )

    for file_name in sorted(file_additions):
        sections = file_additions[file_name]
        added = sum(len(eps) for eps in sections.values())
        if file_name in raws:
            new_text = append_sections(raws[file_name], sections)
            before = count_leaves(raws[file_name])
        else:
            body = json.dumps(sections, ensure_ascii=False, indent=2)
            new_text = body.replace("\n", "\r\n") + "\r\n"
            before = 0
        leaves = validate_output(file_name, new_text)
        assert leaves == before + added, f"{file_name}: 叶子数不符 {leaves} != {before}+{added}"
        logger.info(
            "%-22s +%3d 接口，sections: %s%s",
            file_name + ".json",
            added,
            ", ".join(sections),
            "（新文件）" if not before else "",
        )
        if not dry_run:
            (API_DIR / f"{file_name}.json").write_bytes(new_text.encode("utf-8"))

    if dry_run:
        logger.info("dry-run：未写入任何文件")
    else:
        logger.info("同步完成：%d 个文件写入 %d 个新接口", len(file_additions), total)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
