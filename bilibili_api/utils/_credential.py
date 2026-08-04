"""
bilibili_api.utils._credential — 凭据管理和 Cookies 刷新。
"""

import binascii
import re
import time
import urllib.parse
import uuid

from Cryptodome.Cipher import PKCS1_OAEP
from Cryptodome.Hash import SHA256
from Cryptodome.PublicKey import RSA

from ..exceptions import (
    CookiesRefreshException,
    CredentialNoAcTimeValueException,
    CredentialNoBiliJctException,
    CredentialNoBuvid3Exception,
    CredentialNoBuvid4Exception,
    CredentialNoDedeUserIDException,
    CredentialNoSessdataException,
)
from ._session import get_client
from ._types import API, HEADERS


# Lazy imports to avoid circular dependency with _api
def _get_get_buvid():
    from ._api import get_buvid

    return get_buvid


def _get_Api():
    from ._api import Api

    return Api


class Credential:
    """
    凭据类，用于各种请求操作的验证。
    """

    def __init__(
        self,
        sessdata: str | None = None,
        bili_jct: str | None = None,
        buvid3: str | None = None,
        buvid4: str | None = None,
        dedeuserid: str | None = None,
        ac_time_value: str | None = None,
        proxy: str | None = None,
        **kwargs,
    ) -> None:
        """
        各字段获取方式查看：https://nemo2011.github.io/bilibili-api/#/get-credential.md

        Args:
            sessdata   (str | None, optional): 浏览器 Cookies 中的 SESSDATA 字段值. Defaults to None.

            bili_jct   (str | None, optional): 浏览器 Cookies 中的 bili_jct 字段值. Defaults to None.

            buvid3     (str | None, optional): 浏览器 Cookies 中的 BUVID3 字段值. Defaults to None.

            buvid4     (str | None, optional): 浏览器 Cookies 中的 BUVID4 字段值. Defaults to None.

            dedeuserid (str | None, optional): 浏览器 Cookies 中的 DedeUserID 字段值. Defaults to None.

            ac_time_value (str | None, optional): 浏览器 Cookies 中的 ac_time_value 字段值. Defaults to None.

            proxy (str | None, optional): 凭据类可选择携带的代理. Defaults to None.
        """
        self.sessdata = (
            None if sessdata is None else (sessdata if sessdata.find("%") != -1 else urllib.parse.quote(sessdata))
        )
        self.bili_jct = bili_jct
        self.buvid3 = buvid3
        self.buvid4 = buvid4
        self.dedeuserid = dedeuserid
        self.ac_time_value = ac_time_value
        self.proxy = proxy

        for key, value in kwargs.items():
            setattr(self, key, value)

    def get_cookies(self) -> dict:
        """
        获取请求 Cookies 字典

        Returns:
            dict: 请求 Cookies 字典
        """
        cookies = {
            "SESSDATA": self.sessdata if self.sessdata else "",
            "buvid3": self.buvid3 if self.buvid3 else "",
            "buvid4": self.buvid4 if self.buvid4 else "",
            "bili_jct": self.bili_jct if self.bili_jct else "",
            "ac_time_value": self.ac_time_value if self.ac_time_value else "",
        }
        if self.dedeuserid:
            cookies.update({"DedeUserID": self.dedeuserid})

        for key, value in self.__dict__.items():
            if key not in cookies and value is not None:
                cookies[key] = value
        if cookies.get("proxy"):
            # 从 cookies 中剔除 proxy 字段，否则在发出请求时 cookie 会带上 proxy ，如果 proxy 不为空。
            cookies.pop("proxy")
        return cookies

    async def get_buvid_cookies(self) -> dict:
        """
        获取请求 Cookies 字典，自动补充 buvid 字段

        Returns:
            dict: 请求 Cookies 字典
        """
        cookies = {
            "SESSDATA": self.sessdata if self.sessdata else "",
            "buvid3": self.buvid3 if self.buvid3 else (await _get_get_buvid()())[0],
            "buvid4": self.buvid4 if self.buvid4 else (await _get_get_buvid()())[1],
            "bili_jct": self.bili_jct if self.bili_jct else "",
            "ac_time_value": self.ac_time_value if self.ac_time_value else "",
        }
        if self.dedeuserid:
            cookies.update({"DedeUserID": self.dedeuserid})

        return cookies

    def has_dedeuserid(self) -> bool:
        """
        是否提供 dedeuserid。

        Returns:
            bool: 是否提供 dedeuserid。
        """
        return self.dedeuserid is not None and self.dedeuserid != ""

    def has_sessdata(self) -> bool:
        """
        是否提供 sessdata。

        Returns:
            bool: 是否提供 sessdata。
        """
        return self.sessdata is not None and self.sessdata != ""

    def has_bili_jct(self) -> bool:
        """
        是否提供 bili_jct。

        Returns:
            bool: 是否提供 bili_jct。
        """
        return self.bili_jct is not None and self.bili_jct != ""

    def has_buvid3(self) -> bool:
        """
        是否提供 buvid3

        Returns:
            bool: 是否提供 buvid3
        """
        return self.buvid3 is not None and self.buvid3 != ""

    def has_buvid4(self) -> bool:
        """
        是否提供 buvid4

        Returns:
            bool: 是否提供 buvid4
        """
        return self.buvid4 is not None and self.buvid4 != ""

    def has_ac_time_value(self) -> bool:
        """
        是否提供 ac_time_value

        Returns:
            bool: 是否提供 ac_time_value
        """
        return self.ac_time_value is not None and self.ac_time_value != ""

    def raise_for_no_sessdata(self):
        """
        没有提供 sessdata 则抛出异常。
        """
        if not self.has_sessdata():
            raise CredentialNoSessdataException()

    def raise_for_no_bili_jct(self):
        """
        没有提供 bili_jct 则抛出异常。
        """
        if not self.has_bili_jct():
            raise CredentialNoBiliJctException()

    def raise_for_no_buvid3(self):
        """
        没有提供 buvid3 时抛出异常。
        """
        if not self.has_buvid3():
            raise CredentialNoBuvid3Exception()

    def raise_for_no_buvid4(self):
        """
        没有提供 buvid3 时抛出异常。
        """
        if not self.has_buvid4():
            raise CredentialNoBuvid4Exception()

    def raise_for_no_dedeuserid(self):
        """
        没有提供 DedeUserID 时抛出异常。
        """
        if not self.has_dedeuserid():
            raise CredentialNoDedeUserIDException()

    def raise_for_no_ac_time_value(self):
        """
        没有提供 ac_time_value 时抛出异常。
        """
        if not self.has_ac_time_value():
            raise CredentialNoAcTimeValueException()

    async def check_valid(self):
        """
        检查 cookies 是否有效

        Returns:
            bool: cookies 是否有效
        """
        return await _check_valid(self)

    async def check_refresh(self) -> bool:
        """
        检查是否需要刷新 cookies

        Returns:
            bool: cookies 是否需要刷新
        """
        return await _check_cookies(self)

    async def refresh(self) -> None:
        """
        刷新 cookies
        """
        new_cred: Credential = await _refresh_cookies(self)
        self.sessdata = new_cred.sessdata
        self.bili_jct = new_cred.bili_jct
        self.dedeuserid = new_cred.dedeuserid
        self.ac_time_value = new_cred.ac_time_value

    @staticmethod
    def from_cookies(cookies: dict = {}) -> "Credential":
        """
        从 cookies 新建 Credential

        Args:
            cookies (dict, optional): Cookies. Defaults to {}.

        Returns:
            Credential: 凭据类
        """
        c = Credential()
        c.sessdata = cookies.get("SESSDATA")
        c.bili_jct = cookies.get("bili_jct")
        c.buvid3 = cookies.get("buvid3")
        c.buvid4 = cookies.get("buvid4")
        c.dedeuserid = cookies.get("DedeUserID")
        c.ac_time_value = cookies.get("ac_time_value")

        for key, value in cookies.items():
            if key not in [
                "SESSDATA",
                "bili_jct",
                "buvid3",
                "buvid4",
                "DedeUserID",
                "ac_time_value",
            ]:
                setattr(c, key, value)
        return c

    def __str__(self):
        return f"SESSDATA: {self.sessdata}; bili_jct: {self.bili_jct}; buvid3: {self.buvid3}; buvid4: {self.buvid4}; DedeUserID: {self.dedeuserid}; ac_time_value: {self.ac_time_value}"


"""
Cookies 刷新相关

感谢 bilibili-API-collect 提供的刷新 Cookies 的思路

https://socialsisteryi.github.io/bilibili-API-collect/docs/login/cookie_refresh.html
"""


async def _check_valid(credential: Credential) -> bool:
    api = API["info"]["valid"]
    return (await _get_Api()(**api, credential=credential).result)["isLogin"]


async def _check_cookies(credential: Credential) -> bool:
    api = API["info"]["check_cookies"]
    return (await _get_Api()(**api, credential=credential).result)["refresh"]


def _getCorrespondPath() -> str:
    key = RSA.importKey(
        """\
-----BEGIN PUBLIC KEY-----
MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQDLgd2OAkcGVtoE3ThUREbio0Eg
Uc/prcajMKXvkCKFCWhJYJcLkcM2DKKcSeFpD/j6Boy538YXnR6VhcuUJOhH2x71
nzPjfdTcqMz7djHum0qSZA0AyCBDABUqCrfNgCiJ00Ra7GmRj+YCK1NJEuewlb40
JNrRuoEUXpabUzGB8QIDAQAB
-----END PUBLIC KEY-----"""
    )
    ts = round(time.time() * 1000)
    cipher = PKCS1_OAEP.new(key, SHA256)
    encrypted = cipher.encrypt(f"refresh_{ts}".encode())
    return binascii.b2a_hex(encrypted).decode()


async def _get_refresh_csrf(credential: Credential) -> str:
    correspond_path = _getCorrespondPath()
    api = API["operate"]["get_refresh_csrf"]
    cookies = credential.get_cookies()
    cookies["buvid3"] = str(uuid.uuid1())
    client = get_client()
    resp = await client.request(
        method="GET",
        url=api["url"].replace("{correspondPath}", correspond_path),
        cookies=cookies,
        headers=HEADERS.copy(),
    )
    if resp.code == 404:
        raise CookiesRefreshException("correspondPath 过期或错误。")
    elif resp.code == 200:
        text = resp.utf8_text()
        refresh_csrf = re.findall('<div id="1-name">(.+?)</div>', text)[0]
        return refresh_csrf
    elif resp.code != 200:
        raise CookiesRefreshException("获取刷新 Cookies 的 csrf 失败。")


async def _refresh_cookies(credential: Credential) -> Credential:
    api = API["operate"]["refresh_cookies"]
    credential.raise_for_no_bili_jct()
    credential.raise_for_no_ac_time_value()
    refresh_csrf = await _get_refresh_csrf(credential)
    data = {
        "csrf": credential.bili_jct,
        "refresh_csrf": refresh_csrf,
        "refresh_token": credential.ac_time_value,
        "source": "main_web",
    }
    cookies = credential.get_cookies()
    cookies["buvid3"] = str(uuid.uuid1())
    client = get_client()
    resp = await client.request(
        method="POST",
        url=api["url"],
        cookies=cookies,
        data=data,
        headers=HEADERS.copy(),
    )
    if resp.code != 200 or resp.json()["code"] != 0:
        raise CookiesRefreshException("刷新 Cookies 失败")
    new_credential = Credential(
        sessdata=resp.cookies["SESSDATA"],
        bili_jct=resp.cookies["bili_jct"],
        dedeuserid=resp.cookies["DedeUserID"],
        ac_time_value=resp.json()["data"]["refresh_token"],
    )
    await _confirm_refresh(credential, new_credential)
    return new_credential


async def _confirm_refresh(old_credential: Credential, new_credential: Credential) -> None:
    api = API["operate"]["confirm_refresh"]
    data = {
        "csrf": new_credential.bili_jct,
        "refresh_token": old_credential.ac_time_value,
    }
    await _get_Api()(**api, credential=new_credential).update_data(**data).result


################################################## END Credential ##################################################
