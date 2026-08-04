"""
bilibili_api.utils._anti_spider — 反爬虫相关逻辑。
"""

import hashlib
import hmac
import io
import json
import random
import struct
import time
import urllib.parse
from functools import reduce

from ..exceptions import (
    ExClimbWuzhiException,
)

from ._session import get_client
from ._credential import Credential
from ._types import APPKEY, APPSEC, HEADERS, API

################################################## BEGIN Anti-Spider ##################################################


import asyncio

class AntiSpiderCache:
    """线程/协程安全的反爬虫参数缓存"""
    def __init__(self):
        self._buvid3: str = ""
        self._buvid4: str = ""
        self._bili_ticket: str = ""
        self._bili_ticket_expires: int = 0
        self._wbi_mixin_key: str = ""
        self._lock = asyncio.Lock()

    async def get_buvid(self):
        """获取 buvid3/buvid4，过期时自动刷新"""
        if self._buvid3 == "" or self._buvid4 == "":
            async with self._lock:
                if self._buvid3 == "" or self._buvid4 == "":
                    spi = await _get_spi_buvid()
                    self._buvid3 = spi["b_3"]
                    self._buvid4 = spi["b_4"]
                    await _active_buvid(self._buvid3, self._buvid4)
                    request_log.dispatch(
                        "ANTI_SPIDER",
                        "反爬虫",
                        {"msg": f"激活 buvid3 / buvid4 成功: 3 [{self._buvid3}] 4 [{self._buvid4}]"},
                    )
        return (self._buvid3, self._buvid4)

    async def get_bili_ticket(self, credential=None):
        """获取 bili_ticket，过期时自动刷新"""
        import time
        if time.time() > int(self._bili_ticket_expires):
            self.invalidate_bili_ticket()
        if self._bili_ticket == "":
            self._bili_ticket = await _get_bili_ticket(credential)
            self._bili_ticket_expires = str(int(time.time()) + 3 * 86400)
            request_log.dispatch(
                "ANTI_SPIDER",
                "反爬虫",
                {"msg": f"获取 bili_ticket 成功: [{self._bili_ticket}]"},
            )
        return self._bili_ticket, self._bili_ticket_expires

    async def get_wbi_mixin_key(self, credential=None):
        """获取 wbi mixin key，为空时自动计算"""
        if self._wbi_mixin_key == "":
            self._wbi_mixin_key = await _get_mixin_key(credential)
            request_log.dispatch(
                "ANTI_SPIDER",
                "反爬虫",
                {"msg": f"获取 wbi mixin key: [{self._wbi_mixin_key}]"},
            )
        return self._wbi_mixin_key

    def invalidate_buvid(self) -> None:
        self._buvid3 = ""
        self._buvid4 = ""

    def invalidate_bili_ticket(self) -> None:
        self._bili_ticket = ""
        self._bili_ticket_expires = 0

    def invalidate_wbi(self) -> None:
        self._wbi_mixin_key = ""


anti_spider_cache = AntiSpiderCache()


OE = [
    46,
    47,
    18,
    2,
    53,
    8,
    23,
    32,
    15,
    50,
    10,
    31,
    58,
    3,
    45,
    35,
    27,
    43,
    5,
    49,
    33,
    9,
    42,
    19,
    29,
    28,
    14,
    39,
    12,
    38,
    41,
    13,
    37,
    48,
    7,
    16,
    24,
    55,
    40,
    61,
    26,
    17,
    0,
    1,
    60,
    51,
    30,
    4,
    22,
    25,
    54,
    21,
    56,
    59,
    6,
    63,
    57,
    62,
    11,
    36,
    20,
    34,
    44,
    52,
]


async def _get_spi_buvid() -> dict:
    api = API["info"]["spi"]
    client = get_client()
    return (
        await client.request(method="GET", url=api["url"], headers=HEADERS.copy())
    ).json()["data"]


"""
思路来源：https://github.com/SocialSisterYi/bilibili-API-collect/issues/933
"""


async def _active_buvid(buvid3: str, buvid4: str) -> dict:
    MOD = 1 << 64

    def get_time_milli() -> int:
        return int(time.time() * 1000)

    def rotate_left(x: int, k: int) -> int:
        bin_str = bin(x)[2:].rjust(64, "0")
        return int(bin_str[k:] + bin_str[:k], base=2)

    def gen_uuid_infoc() -> str:
        t = get_time_milli() % 100000
        mp = list("123456789ABCDEF") + ["10"]
        pck = [8, 4, 4, 4, 12]
        gen_part = lambda x: "".join([random.choice(mp) for _ in range(x)])
        return "-".join([gen_part(l) for l in pck]) + str(t).ljust(5, "0") + "infoc"

    def gen_b_lsid() -> str:
        ret = ""
        for _ in range(8):
            ret += hex(random.randint(0, 15))[2:].upper()
        ret = f"{ret}_{hex(get_time_milli())[2:].upper()}"
        return ret

    def gen_buvid_fp(key: str, seed: int):
        source = io.BytesIO(bytes(key, "ascii"))
        m = murmur3_x64_128(source, seed)
        return f"{hex(m & (MOD - 1))[2:]}{hex(m >> 64)[2:]}"

    def murmur3_x64_128(source: io.BufferedIOBase, seed: int) -> str:
        C1 = 0x87C3_7B91_1142_53D5
        C2 = 0x4CF5_AD43_2745_937F
        C3 = 0x52DC_E729
        C4 = 0x3849_5AB5
        R1, R2, R3, M = 27, 31, 33, 5
        h1, h2 = seed, seed
        processed = 0
        while 1:
            read = source.read(16)
            processed += len(read)
            if len(read) == 16:
                k1 = struct.unpack("<q", read[:8])[0]
                k2 = struct.unpack("<q", read[8:])[0]
                h1 ^= rotate_left(k1 * C1 % MOD, R2) * C2 % MOD
                h1 = ((rotate_left(h1, R1) + h2) * M + C3) % MOD
                h2 ^= rotate_left(k2 * C2 % MOD, R3) * C1 % MOD
                h2 = ((rotate_left(h2, R2) + h1) * M + C4) % MOD
            elif len(read) == 0:
                h1 ^= processed
                h2 ^= processed
                h1 = (h1 + h2) % MOD
                h2 = (h2 + h1) % MOD
                h1 = fmix64(h1)
                h2 = fmix64(h2)
                h1 = (h1 + h2) % MOD
                h2 = (h2 + h1) % MOD
                return (h2 << 64) | h1
            else:
                k1 = 0
                k2 = 0
                if len(read) >= 15:
                    k2 ^= int(read[14]) << 48
                if len(read) >= 14:
                    k2 ^= int(read[13]) << 40
                if len(read) >= 13:
                    k2 ^= int(read[12]) << 32
                if len(read) >= 12:
                    k2 ^= int(read[11]) << 24
                if len(read) >= 11:
                    k2 ^= int(read[10]) << 16
                if len(read) >= 10:
                    k2 ^= int(read[9]) << 8
                if len(read) >= 9:
                    k2 ^= int(read[8])
                    k2 = rotate_left(k2 * C2 % MOD, R3) * C1 % MOD
                    h2 ^= k2
                if len(read) >= 8:
                    k1 ^= int(read[7]) << 56
                if len(read) >= 7:
                    k1 ^= int(read[6]) << 48
                if len(read) >= 6:
                    k1 ^= int(read[5]) << 40
                if len(read) >= 5:
                    k1 ^= int(read[4]) << 32
                if len(read) >= 4:
                    k1 ^= int(read[3]) << 24
                if len(read) >= 3:
                    k1 ^= int(read[2]) << 16
                if len(read) >= 2:
                    k1 ^= int(read[1]) << 8
                if len(read) >= 1:
                    k1 ^= int(read[0])
                k1 = rotate_left(k1 * C1 % MOD, R2) * C2 % MOD
                h1 ^= k1

    def fmix64(k: int) -> int:
        C1 = 0xFF51_AFD7_ED55_8CCD
        C2 = 0xC4CE_B9FE_1A85_EC53
        R = 33
        tmp = k
        tmp ^= tmp >> R
        tmp = tmp * C1 % MOD
        tmp ^= tmp >> R
        tmp = tmp * C2 % MOD
        tmp ^= tmp >> R
        return tmp

    def get_payload(uuid: str) -> str:
        content = {
            "3064": 1,
            "5062": get_time_milli(),
            "03bf": "https%3A%2F%2Fwww.bilibili.com%2F",
            "39c8": "333.788.fp.risk",
            "34f1": "",
            "d402": "",
            "654a": "",
            "6e7c": "839x959",
            "3c43": {
                "2673": 0,
                "5766": 24,
                "6527": 0,
                "7003": 1,
                "807e": 1,
                "b8ce": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Safari/605.1.15",
                "641c": 0,
                "07a4": "en-US",
                "1c57": "not available",
                "0bd0": 8,
                "748e": [900, 1440],
                "d61f": [875, 1440],
                "fc9d": -480,
                "6aa9": "Asia/Shanghai",
                "75b8": 1,
                "3b21": 1,
                "8a1c": 0,
                "d52f": "not available",
                "adca": "MacIntel",
                "80c9": [
                    [
                        "PDF Viewer",
                        "Portable Document Format",
                        [["application/pdf", "pdf"], ["text/pdf", "pdf"]],
                    ],
                    [
                        "Chrome PDF Viewer",
                        "Portable Document Format",
                        [["application/pdf", "pdf"], ["text/pdf", "pdf"]],
                    ],
                    [
                        "Chromium PDF Viewer",
                        "Portable Document Format",
                        [["application/pdf", "pdf"], ["text/pdf", "pdf"]],
                    ],
                    [
                        "Microsoft Edge PDF Viewer",
                        "Portable Document Format",
                        [["application/pdf", "pdf"], ["text/pdf", "pdf"]],
                    ],
                    [
                        "WebKit built-in PDF",
                        "Portable Document Format",
                        [["application/pdf", "pdf"], ["text/pdf", "pdf"]],
                    ],
                ],
                "13ab": "0dAAAAAASUVORK5CYII=",
                "bfe9": "QgAAEIQAACEIAABCCQN4FXANGq7S8KTZayAAAAAElFTkSuQmCC",
                "a3c1": [
                    "extensions:ANGLE_instanced_arrays;EXT_blend_minmax;EXT_color_buffer_half_float;EXT_float_blend;EXT_frag_depth;EXT_shader_texture_lod;EXT_texture_compression_bptc;EXT_texture_compression_rgtc;EXT_texture_filter_anisotropic;EXT_sRGB;KHR_parallel_shader_compile;OES_element_index_uint;OES_fbo_render_mipmap;OES_standard_derivatives;OES_texture_float;OES_texture_float_linear;OES_texture_half_float;OES_texture_half_float_linear;OES_vertex_array_object;WEBGL_color_buffer_float;WEBGL_compressed_texture_astc;WEBGL_compressed_texture_etc;WEBGL_compressed_texture_etc1;WEBGL_compressed_texture_pvrtc;WEBKIT_WEBGL_compressed_texture_pvrtc;WEBGL_compressed_texture_s3tc;WEBGL_compressed_texture_s3tc_srgb;WEBGL_debug_renderer_info;WEBGL_debug_shaders;WEBGL_depth_texture;WEBGL_draw_buffers;WEBGL_lose_context;WEBGL_multi_draw",
                    "webgl aliased line width range:[1, 1]",
                    "webgl aliased point size range:[1, 511]",
                    "webgl alpha bits:8",
                    "webgl antialiasing:yes",
                    "webgl blue bits:8",
                    "webgl depth bits:24",
                    "webgl green bits:8",
                    "webgl max anisotropy:16",
                    "webgl max combined texture image units:32",
                    "webgl max cube map texture size:16384",
                    "webgl max fragment uniform vectors:1024",
                    "webgl max render buffer size:16384",
                    "webgl max texture image units:16",
                    "webgl max texture size:16384",
                    "webgl max varying vectors:30",
                    "webgl max vertex attribs:16",
                    "webgl max vertex texture image units:16",
                    "webgl max vertex uniform vectors:1024",
                    "webgl max viewport dims:[16384, 16384]",
                    "webgl red bits:8",
                    "webgl renderer:WebKit WebGL",
                    "webgl shading language version:WebGL GLSL ES 1.0 (1.0)",
                    "webgl stencil bits:0",
                    "webgl vendor:WebKit",
                    "webgl version:WebGL 1.0",
                    "webgl unmasked vendor:Apple Inc.",
                    "webgl unmasked renderer:Apple GPU",
                    "webgl vertex shader high float precision:23",
                    "webgl vertex shader high float precision rangeMin:127",
                    "webgl vertex shader high float precision rangeMax:127",
                    "webgl vertex shader medium float precision:23",
                    "webgl vertex shader medium float precision rangeMin:127",
                    "webgl vertex shader medium float precision rangeMax:127",
                    "webgl vertex shader low float precision:23",
                    "webgl vertex shader low float precision rangeMin:127",
                    "webgl vertex shader low float precision rangeMax:127",
                    "webgl fragment shader high float precision:23",
                    "webgl fragment shader high float precision rangeMin:127",
                    "webgl fragment shader high float precision rangeMax:127",
                    "webgl fragment shader medium float precision:23",
                    "webgl fragment shader medium float precision rangeMin:127",
                    "webgl fragment shader medium float precision rangeMax:127",
                    "webgl fragment shader low float precision:23",
                    "webgl fragment shader low float precision rangeMin:127",
                    "webgl fragment shader low float precision rangeMax:127",
                    "webgl vertex shader high int precision:0",
                    "webgl vertex shader high int precision rangeMin:31",
                    "webgl vertex shader high int precision rangeMax:30",
                    "webgl vertex shader medium int precision:0",
                    "webgl vertex shader medium int precision rangeMin:31",
                    "webgl vertex shader medium int precision rangeMax:30",
                    "webgl vertex shader low int precision:0",
                    "webgl vertex shader low int precision rangeMin:31",
                    "webgl vertex shader low int precision rangeMax:30",
                    "webgl fragment shader high int precision:0",
                    "webgl fragment shader high int precision rangeMin:31",
                    "webgl fragment shader high int precision rangeMax:30",
                    "webgl fragment shader medium int precision:0",
                    "webgl fragment shader medium int precision rangeMin:31",
                    "webgl fragment shader medium int precision rangeMax:30",
                    "webgl fragment shader low int precision:0",
                    "webgl fragment shader low int precision rangeMin:31",
                    "webgl fragment shader low int precision rangeMax:30",
                ],
                "6bc5": "Apple Inc.~Apple GPU",
                "ed31": 0,
                "72bd": 0,
                "097b": 0,
                "52cd": [0, 0, 0],
                "a658": [
                    "Andale Mono",
                    "Arial",
                    "Arial Black",
                    "Arial Hebrew",
                    "Arial Narrow",
                    "Arial Rounded MT Bold",
                    "Arial Unicode MS",
                    "Comic Sans MS",
                    "Courier",
                    "Courier New",
                    "Geneva",
                    "Georgia",
                    "Helvetica",
                    "Helvetica Neue",
                    "Impact",
                    "LUCIDA GRANDE",
                    "Microsoft Sans Serif",
                    "Monaco",
                    "Palatino",
                    "Tahoma",
                    "Times",
                    "Times New Roman",
                    "Trebuchet MS",
                    "Verdana",
                    "Wingdings",
                    "Wingdings 2",
                    "Wingdings 3",
                ],
                "d02f": "124.04345259929687",
            },
            "54ef": '{"in_new_ab":true,"ab_version":{"remove_back_version":"REMOVE","login_dialog_version":"V_PLAYER_PLAY_TOAST","open_recommend_blank":"SELF","storage_back_btn":"HIDE","call_pc_app":"FORBID","clean_version_old":"GO_NEW","optimize_fmp_version":"LOADED_METADATA","for_ai_home_version":"V_OTHER","bmg_fallback_version":"DEFAULT","ai_summary_version":"SHOW","weixin_popup_block":"ENABLE","rcmd_tab_version":"DISABLE","in_new_ab":true},"ab_split_num":{"remove_back_version":11,"login_dialog_version":43,"open_recommend_blank":90,"storage_back_btn":87,"call_pc_app":47,"clean_version_old":46,"optimize_fmp_version":28,"for_ai_home_version":38,"bmg_fallback_version":86,"ai_summary_version":466,"weixin_popup_block":45,"rcmd_tab_version":90,"in_new_ab":0},"pageVersion":"new_video","videoGoOldVersion":-1}',
            "8b94": "https%3A%2F%2Fwww.bilibili.com%2F",
            "df35": uuid,
            "07a4": "en-US",
            "5f45": None,
            "db46": 0,
        }
        return json.dumps(
            {"payload": json.dumps(content, separators=(",", ":"))},
            separators=(",", ":"),
        )

    api = API["operate"]["active"]
    client = get_client()
    uuid = gen_uuid_infoc()
    payload = get_payload(uuid)
    buvid_fp = gen_buvid_fp(payload, 31)
    headers = HEADERS.copy()
    headers["Content-Type"] = "application/json"
    resp = await client.request(
        method="POST",
        url=api["url"],
        data=payload,
        headers=headers,
        cookies={
            "buvid3": buvid3,
            "buvid4": buvid4,
            "buvid_fp": buvid_fp,
            "_uuid": uuid,
        },
    )
    data = resp.json()
    if data["code"] != 0:
        raise ExClimbWuzhiException(data["code"], data["msg"])


async def _get_nav(credential: Credential | None = None) -> dict:
    credential = credential if credential else Credential()
    api = API["info"]["valid"]
    client = get_client()
    return (
        await client.request(
            method="GET",
            url=api["url"],
            headers=HEADERS.copy(),
            cookies=credential.get_cookies(),
        )
    ).json()["data"]


async def _get_mixin_key(credential: Credential | None = None) -> str:
    data = await _get_nav(credential=credential)
    wbi_img: dict[str, str] = data["wbi_img"]

    def split(key):
        return wbi_img.get(key).split("/")[-1].split(".")[0]

    ae = split("img_url") + split("sub_url")
    le = reduce(lambda s, i: s + (ae[i] if i < len(ae) else ""), OE, "")
    return le[:32]


def _enc_wbi(params: dict, mixin_key: str) -> dict:
    params.pop("w_rid", None)  # 重试时先把原有 w_rid 去除
    params["wts"] = int(time.time())
    # web_location 因为没被列入参数可能炸一些接口 比如 video.get_ai_conclusion
    # 但 video.get_download_url 的 web_location 不是这东西
    # 因此此处默认提供 1550101，具体哪些一些也不清楚。
    if not params.get("web_location"):
        params["web_location"] = 1550101
    Ae = urllib.parse.urlencode(sorted(params.items()))
    params["w_rid"] = hashlib.md5((Ae + mixin_key).encode(encoding="utf-8")).hexdigest()
    return params


def _enc_dm(params: dict) -> dict:
    dm_rand = "ABCDEFGHIJK"
    params.update(
        {
            "dm_img_list": "[]",  # 鼠标/键盘操作记录
            "dm_img_str": "".join(random.sample(dm_rand, 2)),
            "dm_cover_img_str": "".join(random.sample(dm_rand, 2)),
            "dm_img_inter": '{"ds":[],"wh":[0,0,0],"of":[0,0,0]}',
        }
    )
    return params


def _enc_sign(paramsordata: dict) -> dict:
    paramsordata["appkey"] = APPKEY
    paramsordata = dict(sorted(paramsordata.items()))
    paramsordata["sign"] = hashlib.md5(
        (urllib.parse.urlencode(paramsordata) + APPSEC).encode("utf-8")
    ).hexdigest()
    return paramsordata


"""
算法来源：https://github.com/SocialSisterYi/bilibili-API-collect/issues/903
"""


async def _get_bili_ticket(credential: Credential | None = None) -> str:
    def hmac_sha256(key: str, message: str) -> str:
        key = key.encode("utf-8")
        message = message.encode("utf-8")
        hmac_obj = hmac.new(key, message, hashlib.sha256)
        return hmac_obj.digest().hex()

    credential = credential if credential else Credential()
    o = hmac_sha256("XgwSnGZ1p", f"ts{int(time.time())}")
    api = API["info"]["ticket"]
    params = {
        "key_id": "ec02",
        "hexsign": o,
        "context[ts]": f"{int(time.time())}",
        "csrf": "",
    }
    client = get_client()
    resp = await client.request(
        method="POST",
        url=api["url"],
        params=params,
        headers=HEADERS.copy(),
        cookies=credential.get_cookies(),
    )
    return resp.json()["data"]["ticket"]


################################################## END Anti-Spider ##################################################
