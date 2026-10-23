# bilibili_api 同步脚本（scripts/sync_api_registry.py）离线单元测试
#
# 本文件属于无凭据快速路径：全部用例均为纯本地逻辑验证，
# 不触碰网络、不读取凭据、不依赖真实账号。
# scripts/ 非包成员，按文件路径加载脚本模块；REGISTRY_DIR / API_DIR
# 指向 tmp fixture registry，自包含、新克隆环境可跑
# （specs/010-review-defect-fixes FR-006 / SC-004）。

import importlib.util
import json
import logging
from pathlib import Path

import pytest

SCRIPT_PATH = Path(__file__).resolve().parent.parent / "scripts" / "sync_api_registry.py"

# 既有 fixture 文件中预置的"已存在"接口 URL（cheese 类别）
EXISTING_CHEESE_URL = "https://api.bilibili.com/x/cheese/info"


def _load_script():
    """按文件路径加载同步脚本模块（scripts/ 非包成员，无既有先例）。"""
    spec = importlib.util.spec_from_file_location("sync_api_registry_under_test", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _endpoint(url: str, name: str = "测试接口") -> dict:
    """构造一条最小 REST registry 条目。"""
    return {"endpoint_type": "rest", "method": "GET", "url": url, "name": name, "params": [], "notes": ""}


def _write_registry(registry_dir: Path, category: str, subtopic: str, endpoints: list[dict]) -> None:
    """在 tmp registry 中写一个类别目录下的 subtopic JSON。"""
    folder = registry_dir / category
    folder.mkdir(parents=True, exist_ok=True)
    payload = {"category": category, "subtopic": subtopic, "endpoints": endpoints}
    (folder / f"{subtopic or 'index'}.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


@pytest.fixture
def sync_env(tmp_path, monkeypatch):
    """加载脚本并把 REGISTRY_DIR / API_DIR 指向 tmp fixture（自包含，不依赖真实 registry）。"""
    module = _load_script()
    registry_dir = tmp_path / "registry"
    api_dir = tmp_path / "api"
    api_dir.mkdir()
    # 既有接口定义文件：cheese / opus 各预置一条已存在 URL
    (api_dir / "cheese.json").write_text(
        json.dumps(
            {"cheese_info": {"info": {"url": EXISTING_CHEESE_URL, "method": "GET", "comment": "既有接口"}}},
            ensure_ascii=False,
            indent=2,
        )
        + "\r\n",
        encoding="utf-8",
    )
    (api_dir / "opus.json").write_text(
        json.dumps(
            {
                "opus_space": {
                    "space": {"url": "https://api.bilibili.com/x/opus/space", "method": "GET", "comment": "既有接口"}
                }
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\r\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "REGISTRY_DIR", registry_dir)
    monkeypatch.setattr(module, "API_DIR", api_dir)
    return module, registry_dir, api_dir


def test_unmapped_category_skipped_with_warning(sync_env, caplog):
    """映射表未覆盖的虚构类别条目被跳过：进程不崩溃，告警含类别名与条目数（FR-006）。"""
    module, registry_dir, api_dir = sync_env
    _write_registry(registry_dir, "weird_category", "thing", [_endpoint("https://api.bilibili.com/x/weird/thing")])
    with caplog.at_level(logging.INFO):
        rc = module.main([])
    assert rc == 0
    assert "跳过未映射类别 weird_category：1 条待同步条目" in caplog.text
    # 汇总行含独立的"无映射跳过"计数，与"已存在跳过"可区分
    assert "已存在 0，registry 内重复 0，无映射跳过 1，本次新增 0" in caplog.text
    # 不因映射缺失产生新文件
    assert not (api_dir / "weird_category.json").exists()


def test_three_categories_resolve_to_targets(sync_env, caplog):
    """broadcast / cheese / opus 三类别条目按补齐后的映射落位：broadcast 走新建文件路径（FR-006）。"""
    module, registry_dir, api_dir = sync_env
    _write_registry(
        registry_dir, "broadcast", "video_room", [_endpoint("https://api.bilibili.com/x/broadcast/room/info")]
    )
    _write_registry(registry_dir, "cheese", "videostream_url", [_endpoint("https://api.bilibili.com/x/cheese/vstream")])
    _write_registry(registry_dir, "opus", "rich_text_nodes", [_endpoint("https://api.bilibili.com/x/opus/rich")])
    with caplog.at_level(logging.INFO):
        rc = module.main([])
    assert rc == 0
    # broadcast 无既有文件，经同步惰性新建
    assert (api_dir / "broadcast.json").exists()
    broadcast = json.loads((api_dir / "broadcast.json").read_text(encoding="utf-8"))
    assert "video_room" in broadcast
    # cheese / opus 追加进既有文件且原内容保留
    cheese = json.loads((api_dir / "cheese.json").read_text(encoding="utf-8"))
    assert "cheese_info" in cheese
    assert "videostream_url" in cheese
    opus = json.loads((api_dir / "opus.json").read_text(encoding="utf-8"))
    assert "opus_space" in opus
    assert "rich_text_nodes" in opus
    assert "无映射跳过 0" in caplog.text


def test_existing_url_entry_skipped(sync_env, caplog):
    """URL 已存在于接口定义的条目依旧跳过不动（纯增量契约不变，FR-006）。"""
    module, registry_dir, api_dir = sync_env
    _write_registry(registry_dir, "cheese", "info", [_endpoint(EXISTING_CHEESE_URL)])
    before = (api_dir / "cheese.json").read_bytes()
    with caplog.at_level(logging.INFO):
        rc = module.main([])
    assert rc == 0
    assert "已存在 1" in caplog.text
    assert "本次新增 0" in caplog.text
    assert (api_dir / "cheese.json").read_bytes() == before


def test_dry_run_writes_nothing(sync_env, caplog):
    """预览模式不写任何文件：新类别也不产生 broadcast.json（契约：--dry-run 纯预览）。"""
    module, registry_dir, api_dir = sync_env
    _write_registry(
        registry_dir, "broadcast", "video_room", [_endpoint("https://api.bilibili.com/x/broadcast/room/info")]
    )
    before = {p.name: p.read_bytes() for p in api_dir.glob("*.json")}
    with caplog.at_level(logging.INFO):
        rc = module.main(["--dry-run"])
    assert rc == 0
    after = {p.name: p.read_bytes() for p in api_dir.glob("*.json")}
    assert before == after
    assert not (api_dir / "broadcast.json").exists()
    assert "dry-run：未写入任何文件" in caplog.text


def test_registry_dir_missing_fails_with_hint(sync_env, monkeypatch, caplog):
    """registry 目录缺失时以退出码 1 失败并输出获取指引（不因兜底逻辑放宽）。"""
    module, registry_dir, _api_dir = sync_env
    monkeypatch.setattr(module, "REGISTRY_DIR", registry_dir / "nonexistent")
    with caplog.at_level(logging.ERROR):
        rc = module.main([])
    assert rc == 1
    assert "bilibili-api-registry" in caplog.text
