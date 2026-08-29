"""
bilibili_api.utils._wbi — Wbi 反爬虫签名。

从外部 fork 移植的 WbiManager 签名实现，并补充了带 6 小时 TTL 与协程锁的密钥缓存，
避免每次签名都请求 nav 接口触发风控。
"""

import asyncio
from functools import reduce
import hashlib
import time
from typing import ClassVar
import urllib.parse

from ._credential import Credential
from ._log import request_log
from ._session import get_client
from ._types import API

__all__ = ["WbiManager"]


class WbiManager:
    """
    Wbi 签名管理器，调用 `get_end_result` 即可完成参数签名。

    内部通过 nav 接口获取 `img_key` / `sub_key`，并以类级缓存 + 双重检查锁
    保证缓存有效期内 nav 只请求一次（并发安全）。缓存过期或调用 `invalidate()`
    后，下次签名时自动重新获取。
    """

    # wbi 密钥缓存有效期（秒），沿用原反爬虫缓存的 6 小时，减少对 -403 重试的依赖
    WBI_KEYS_TTL: ClassVar[int] = 6 * 3600

    # Wbi 混淆密钥索引表：按该顺序从 img_key+sub_key 拼接串中重排字符
    # fmt: off
    MIXIN_KEY_ENC_TAB: ClassVar[list[int]] = [
        46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35, 27, 43, 5, 49,
        33, 9, 42, 19, 29, 28, 14, 39, 12, 38, 41, 13, 37, 48, 7, 16, 24, 55, 40,
        61, 26, 17, 0, 1, 60, 51, 30, 4, 22, 25, 54, 21, 56, 59, 6, 63, 57, 62, 11,
        36, 20, 34, 44, 52,
    ]
    # fmt: on

    # 请求 nav 接口使用的独立请求头（模拟较新的 Chrome/Edge 浏览器）
    HEADERS: ClassVar[dict[str, str]] = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0",
        "Referer": "https://www.bilibili.com/",
        "Origin": "http://www.bilibili.com",
    }

    # 类级密钥缓存及时间戳
    _img_key: str = ""
    _sub_key: str = ""
    _mixin_key: str = ""
    _cache_ts: float = 0.0
    # 惰性创建，避免 sync() 包装器跨事件循环复用时 RuntimeError
    _lock: asyncio.Lock | None = None

    @classmethod
    def _get_lock(cls) -> asyncio.Lock:
        """获取（必要时惰性创建）协程锁。"""
        if cls._lock is None:
            cls._lock = asyncio.Lock()
        return cls._lock

    @classmethod
    def _keys_expired(cls) -> bool:
        """判断缓存的 wbi 密钥是否为空或已超过 TTL。"""
        return cls._img_key == "" or cls._sub_key == "" or time.time() - cls._cache_ts > cls.WBI_KEYS_TTL

    @classmethod
    async def get_end_result(
        cls,
        params: dict,
        credential: Credential | None = None,
    ) -> dict[str, str | int]:
        """
        为请求参数完成 wbi 签名：补充默认 `web_location`，获取（缓存的）密钥并计算 `w_rid`。

        web_location 因为没被列入参数可能炸一些接口 比如 video.get_ai_conclusion
        但 video.get_download_url 的 web_location 不是这东西
        旧实现默认提供 1550101，具体哪些接口适用也不清楚；
        现默认值采用 fork 实现的 "444.8"，已有 `web_location` 时不覆盖。

        Args:
            params     (dict): 待签名参数，原地修改并返回
            credential (Credential | None, optional): 凭据. Defaults to None.

        Returns:
            dict[str, str | int]: 追加了 `web_location` / `wts` / `w_rid` 并排序过滤后的参数
        """
        if not params.get("web_location"):
            params["web_location"] = "444.8"
        img_key, sub_key = await cls._get_wbi_keys(credential)
        return cls._enc_wbi(params, img_key, sub_key)

    @classmethod
    async def get_mixin_key(cls, credential: Credential | None = None) -> str:
        """
        获取（缓存的）32 位 wbi mixin key。

        Args:
            credential (Credential | None, optional): 凭据. Defaults to None.

        Returns:
            str: 32 位 mixin key
        """
        await cls._get_wbi_keys(credential)
        return cls._mixin_key

    @classmethod
    def invalidate(cls) -> None:
        """作废缓存的 wbi 密钥与时间戳，下次签名时重新获取。"""
        cls._img_key = ""
        cls._sub_key = ""
        cls._mixin_key = ""
        cls._cache_ts = 0.0

    @classmethod
    async def _get_wbi_keys(cls, credential: Credential | None = None) -> tuple[str, str]:
        """
        获取最新的 img_key 和 sub_key，缓存有效期内直接复用（双重检查锁避免并发重复获取）。

        Args:
            credential (Credential | None, optional): 凭据. Defaults to None.

        Returns:
            tuple[str, str]: img_key, sub_key
        """
        if not cls._keys_expired():
            return cls._img_key, cls._sub_key
        async with cls._get_lock():
            if not cls._keys_expired():
                return cls._img_key, cls._sub_key
            credential = credential if credential else Credential()
            api: dict[str, str] = API["info"]["valid"]
            client = get_client()
            nav_data: dict = (
                await client.request(
                    method="GET",
                    url=api["url"],
                    headers=cls.HEADERS.copy(),
                    cookies=credential.get_cookies(),
                )
            ).json()["data"]
            img_key: str = nav_data["wbi_img"]["img_url"].rsplit("/", 1)[1].split(".")[0]
            sub_key: str = nav_data["wbi_img"]["sub_url"].rsplit("/", 1)[1].split(".")[0]
            cls._img_key = img_key
            cls._sub_key = sub_key
            cls._mixin_key = cls._get_mixin_key(img_key + sub_key)
            cls._cache_ts = time.time()
            request_log.dispatch(
                "ANTI_SPIDER",
                "反爬虫",
                {"msg": f"获取 wbi keys: img [{img_key}] sub [{sub_key}]"},
            )
        return cls._img_key, cls._sub_key

    @classmethod
    def _get_mixin_key(cls, orig: str) -> str:
        """
        对 img_key + sub_key 进行字符顺序打乱编码。

        Args:
            orig (str): img_key + sub_key 拼接串

        Returns:
            str: 打乱后截取的前 32 位字符
        """
        return reduce(lambda s, i: s + orig[i], cls.MIXIN_KEY_ENC_TAB, "")[:32]

    @classmethod
    def _enc_wbi(cls, params: dict[str, str | int], img_key: str, sub_key: str) -> dict[str, str | int]:
        """
        为请求参数进行 wbi 签名。

        Args:
            params  (dict[str, str | int]): 待签名参数
            img_key (str): 通过分解 img_url 获取
            sub_key (str): 通过分解 sub_url 获取

        Returns:
            dict[str, str | int]: params 原有参数及加密后的 `w_rid` 值
        """
        mixin_key = cls._get_mixin_key(img_key + sub_key)
        params.pop("w_rid", None)  # -403 重试时先把原有 w_rid 去除
        params["wts"] = round(time.time())  # 添加 wts 字段
        params = dict(sorted(params.items()))  # 按照 key 重排参数
        # 过滤 value 中的 "!'()*" 字符
        params = {k: "".join(filter(lambda x: x not in "!'()*", str(v))) for k, v in params.items()}
        query = urllib.parse.urlencode(params)  # 序列化参数
        params["w_rid"] = hashlib.md5((query + mixin_key).encode()).hexdigest()  # 计算 w_rid
        return params
