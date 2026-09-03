# scripts/_login_cache.py 离线单元测试
#
# 本文件属于无凭据快速路径：全部用例均为纯本地逻辑验证，
# 不触碰网络、不读取 BILI_* 环境变量、不依赖真实账号、不导入 bilibili_api。
# 覆盖：缓存路径解析、编码↔读取往返、坏文件判定（空文件 / 坏 base64 /
# 非 JSON / 顶层非对象 / 缺必需键 / 空串字段）、凭据来源优先级合并各分支。

import base64
import json
from pathlib import Path
import tempfile

from scripts._login_cache import (
    CACHE_FILENAME,
    CacheStatus,
    encode_credential_cache,
    get_cache_path,
    load_cache,
    merge_credential_values,
    save_cache,
)

# 结构合法的样例字段（纯虚构占位值，非真实凭据）
SAMPLE_FIELDS = {
    "sessdata": "sample-sessdata",
    "bili_jct": "sample-jct",
    "dedeuserid": "42",
    "ac_time_value": "sample-refresh-token",
    "buvid3": "sample-buvid3",
    "unknown_field": "should-be-dropped",
}


def _b64(text: str) -> str:
    """把明文编码为缓存文件使用的 base64 形态。"""
    return base64.b64encode(text.encode("utf-8")).decode("ascii")


def test_cache_path_uses_tempdir_and_fixed_name():
    """缓存路径应为系统 TEMP 目录 + 固定文件名。"""
    assert get_cache_path() == Path(tempfile.gettempdir()) / CACHE_FILENAME


def test_encode_drops_missing_empty_and_unknown_fields():
    """None / 空串 / 契约外字段不应写入编码结果。"""
    encoded = encode_credential_cache(
        {
            "sessdata": "a",
            "bili_jct": None,
            "dedeuserid": "",
            "ac_time_value": "b",
            "buvid3": None,
            "buvid4": "",
            "not-a-field": "c",
        }
    )
    decoded = json.loads(base64.b64decode(encoded).decode("utf-8"))
    assert decoded == {"sessdata": "a", "ac_time_value": "b"}


def test_encode_produces_single_line_ascii():
    """编码结果应为单行 ASCII（base64）字符串。"""
    encoded = encode_credential_cache(SAMPLE_FIELDS)
    assert encoded.isascii()
    assert "\n" not in encoded
    encoded.encode("ascii")


def test_save_and_load_roundtrip(tmp_path):
    """save → load 应无损往返，且必需三键保留。"""
    target = tmp_path / CACHE_FILENAME
    saved = save_cache(SAMPLE_FIELDS, target)
    assert saved == target
    result = load_cache(target)
    assert result.status is CacheStatus.OK
    assert result.fields == {
        "sessdata": "sample-sessdata",
        "bili_jct": "sample-jct",
        "dedeuserid": "42",
        "ac_time_value": "sample-refresh-token",
        "buvid3": "sample-buvid3",
    }


def test_save_overwrites_previous_content(tmp_path):
    """后一次 save 应整体覆盖前一次内容。"""
    target = tmp_path / CACHE_FILENAME
    save_cache(SAMPLE_FIELDS, target)
    save_cache({"sessdata": "new", "bili_jct": "new", "dedeuserid": "43"}, target)
    result = load_cache(target)
    assert result.status is CacheStatus.OK
    assert result.fields == {"sessdata": "new", "bili_jct": "new", "dedeuserid": "43"}


def test_load_absent_when_file_missing(tmp_path):
    """文件不存在时应判 absent。"""
    result = load_cache(tmp_path / CACHE_FILENAME)
    assert result.status is CacheStatus.ABSENT
    assert result.fields == {}


def test_load_empty_file_is_corrupt(tmp_path):
    """空文件（含纯空白）应判 corrupt。"""
    target = tmp_path / CACHE_FILENAME
    target.write_text("   \n\t\n", encoding="utf-8")
    result = load_cache(target)
    assert result.status is CacheStatus.CORRUPT
    assert result.fields == {}


def test_load_invalid_base64_is_corrupt(tmp_path):
    """内容无法 base64 解码时应判 corrupt。"""
    target = tmp_path / CACHE_FILENAME
    target.write_text("not-a-valid-base64-$$$", encoding="utf-8")
    result = load_cache(target)
    assert result.status is CacheStatus.CORRUPT


def test_load_non_json_payload_is_corrupt(tmp_path):
    """base64 解码后不是 JSON 文本时应判 corrupt。"""
    target = tmp_path / CACHE_FILENAME
    target.write_text(_b64("not json at all"), encoding="utf-8")
    assert load_cache(target).status is CacheStatus.CORRUPT


def test_load_non_object_json_is_corrupt(tmp_path):
    """JSON 顶层为数组 / 标量时应判 corrupt。"""
    target = tmp_path / CACHE_FILENAME
    target.write_text(_b64("[1, 2, 3]"), encoding="utf-8")
    assert load_cache(target).status is CacheStatus.CORRUPT
    target.write_text(_b64("42"), encoding="utf-8")
    assert load_cache(target).status is CacheStatus.CORRUPT


def test_load_missing_required_keys_is_corrupt(tmp_path):
    """缺少任一必需键时应判 corrupt，原因应点名缺失键。"""
    target = tmp_path / CACHE_FILENAME
    target.write_text(_b64(json.dumps({"sessdata": "a", "bili_jct": "b"})), encoding="utf-8")
    result = load_cache(target)
    assert result.status is CacheStatus.CORRUPT
    assert "dedeuserid" in result.reason


def test_load_empty_string_fields_equal_missing(tmp_path):
    """必需键值为空串等同缺失，应判 corrupt。"""
    target = tmp_path / CACHE_FILENAME
    payload = {"sessdata": "", "bili_jct": "b", "dedeuserid": "c"}
    target.write_text(_b64(json.dumps(payload)), encoding="utf-8")
    assert load_cache(target).status is CacheStatus.CORRUPT


def test_load_tolerates_surrounding_whitespace(tmp_path):
    """内容首尾的空白（如换行）不影响合法性。"""
    target = tmp_path / CACHE_FILENAME
    encoded = encode_credential_cache(SAMPLE_FIELDS)
    target.write_text(f"\n{encoded}\n", encoding="utf-8")
    assert load_cache(target).status is CacheStatus.OK


def test_load_optional_fields_are_not_required(tmp_path):
    """可选键（ac_time_value / buvid3 / buvid4）缺失不影响合法性。"""
    target = tmp_path / CACHE_FILENAME
    target.write_text(_b64(json.dumps({"sessdata": "a", "bili_jct": "b", "dedeuserid": "c"})), encoding="utf-8")
    result = load_cache(target)
    assert result.status is CacheStatus.OK
    assert result.fields == {"sessdata": "a", "bili_jct": "b", "dedeuserid": "c"}


def test_merge_higher_priority_source_wins_per_field():
    """参数顺序即优先级：高优先级来源逐字段覆盖低优先级来源。"""
    merged = merge_credential_values(
        {"sessdata": "fresh", "bili_jct": "fresh-jct"},
        {"sessdata": "cached", "dedeuserid": "42", "ac_time_value": "token"},
        {"sessdata": "env", "bili_jct": "env-jct", "dedeuserid": "1", "buvid3": "env-buvid3"},
    )
    assert merged == {
        "sessdata": "fresh",
        "bili_jct": "fresh-jct",
        "dedeuserid": "42",
        "ac_time_value": "token",
        "buvid3": "env-buvid3",
    }


def test_merge_skips_none_empty_and_unknown():
    """合并时应跳过 None / 空串 / 契约外字段。"""
    merged = merge_credential_values(
        {"sessdata": None, "bili_jct": "", "dedeuserid": "42", "hacked": "x"},
    )
    assert merged == {"dedeuserid": "42"}


def test_merge_ignores_absent_sources():
    """None / 空来源应整体忽略；全部为空时结果为空。"""
    assert merge_credential_values(None, {}, None) == {}
    assert merge_credential_values(None, {}, {"sessdata": "a", "bili_jct": "b", "dedeuserid": "c"}) == {
        "sessdata": "a",
        "bili_jct": "b",
        "dedeuserid": "c",
    }
