# bilibili_api API 定义文件离线校验（无凭据快速路径）
#
# 校验 data/api 下全部 JSON 定义的结构完整性：可正常加载，
# 每个接口叶子节点包含 url / method 且 method 为合法 HTTP 方法。
# 纯本地逻辑，不触碰网络、不依赖凭据；文件名以 test_offline_ 开头，
# 由 pytest 收集运行（uv run pytest），且不会被 conftest.py 打上 integration 标记。

import json
from pathlib import Path

import pytest

API_DIR = Path(__file__).resolve().parent.parent / "bilibili_api" / "data" / "api"

VALID_METHODS = {"GET", "POST", "PUT", "DELETE", "PATCH"}


def _iter_endpoints(node: dict, path: str = ""):
    """遍历 API 定义树，产出 (路径, 叶子接口字典)；含 url 键的节点视为接口叶子。"""
    if "url" in node:
        yield path, node
        return
    for key, value in node.items():
        if isinstance(value, dict):
            yield from _iter_endpoints(value, f"{path}.{key}" if path else key)


@pytest.fixture(scope="module")
def api_definitions() -> list[tuple[str, dict]]:
    """加载 data/api 下全部 JSON，返回 (文件名, 定义内容) 列表。"""
    files = sorted(API_DIR.glob("*.json"))
    assert files, "data/api 目录不应为空"
    definitions = []
    for file in files:
        definitions.append((file.name, json.loads(file.read_text(encoding="utf-8"))))
    return definitions


def test_api_definitions_loadable(api_definitions):
    """全部 API 定义 JSON 应可加载为 dict 且非空。"""
    for name, content in api_definitions:
        assert isinstance(content, dict), f"{name} 应为 JSON 对象"
        assert content, f"{name} 不应为空"


def test_api_definition_endpoints_well_formed(api_definitions):
    """每个接口叶子节点应包含合法 url 与 method（API 定义核心面）。"""
    endpoint_count = 0
    for name, content in api_definitions:
        for path, endpoint in _iter_endpoints(content):
            endpoint_count += 1
            assert endpoint["url"].startswith("http"), f"{name} 中 {path} 的 url 非法"
            method = endpoint.get("method", "").upper()
            assert method in VALID_METHODS, f"{name} 中 {path} 的 method 非法: {endpoint.get('method')}"
            for payload_key in ("params", "data"):
                if payload_key in endpoint:
                    # 允许 dict（参数模板）或 str（描述性注释，如 credential.json 的 operate.active）
                    assert isinstance(endpoint[payload_key], (dict, str)), (
                        f"{name} 中 {path} 的 {payload_key} 应为对象或字符串注释"
                    )
    assert endpoint_count > 0, "应至少解析出一个接口定义"
