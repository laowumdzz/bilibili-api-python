# bilibili_api dynamic/opus turn_to_article 映射缓存 None 防护离线单元测试
#
# 本文件属于无凭据快速路径：全部用例均为纯本地逻辑验证，
# 不触碰网络、不读取 BILI_* 环境变量、不依赖真实账号。
# 覆盖：两次读缓存之间映射条目恰好过期（1 小时 TTL 窗口）被淘汰时，
# turn_to_article 不得以 cvid=None 构造 Article，须抛 ArgsException。

import pytest

from bilibili_api.dynamic import Dynamic
from bilibili_api.exceptions import ArgsException
from bilibili_api.opus import Opus
from bilibili_api.utils import cache_pool


@pytest.fixture(autouse=True)
def _clean_dynamic2article():
    """用例前后清空 dynamic2article，避免污染其他用例（自愈型缓存，无副作用）。"""
    cache_pool.dynamic2article.clear()
    yield
    cache_pool.dynamic2article.clear()


def _simulate_entry_expiring_between_reads(monkeypatch):
    """第一次读命中（绕过 get_info 分支），第二次读返回 None（模拟条目恰在窗口内过期）。"""
    values = iter([456, None])
    monkeypatch.setattr(cache_pool.dynamic2article, "get", lambda key: next(values))


async def test_dynamic_turn_to_article_raises_on_expired_entry(monkeypatch):
    _simulate_entry_expiring_between_reads(monkeypatch)
    with pytest.raises(ArgsException):
        await Dynamic(dynamic_id=123).turn_to_article()


async def test_opus_turn_to_article_raises_on_expired_entry(monkeypatch):
    _simulate_entry_expiring_between_reads(monkeypatch)
    with pytest.raises(ArgsException):
        await Opus(opus_id=123).turn_to_article()
