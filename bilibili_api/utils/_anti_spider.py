"""
bilibili_api.utils._anti_spider — 反爬虫相关逻辑。
"""

################################################## BEGIN Anti-Spider ##################################################
import asyncio
import hashlib
import hmac
import io
import json
import random
import struct
import time
from typing import cast
import urllib.parse

from ..exceptions import (
    ExClimbWuzhiException,
)
from ._credential import Credential
from ._log import request_log
from ._session import get_client
from ._types import API, APPKEY, APPSEC, HEADERS


class AntiSpiderCache:
    """线程/协程安全的反爬虫参数缓存"""

    def __init__(self):
        """初始化各项反爬虫参数缓存为空，锁惰性创建。"""
        self._buvid3: str = ""
        self._buvid4: str = ""
        self._bili_ticket: str = ""
        self._bili_ticket_expires: int = 0
        # 惰性创建，避免 sync() 包装器跨事件循环复用时 RuntimeError
        self._lock: asyncio.Lock | None = None

    def _get_lock(self) -> asyncio.Lock:
        """获取（必要时惰性创建）协程锁"""
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    async def get_buvid(self):
        """获取 buvid3/buvid4，过期时自动刷新"""
        if self._buvid3 == "" or self._buvid4 == "":
            async with self._get_lock():
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
        """获取 bili_ticket，过期时自动刷新（双重检查锁避免并发重复获取）"""
        if time.time() > int(self._bili_ticket_expires):
            self.invalidate_bili_ticket()
        if self._bili_ticket == "":
            async with self._get_lock():
                if time.time() > int(self._bili_ticket_expires):
                    self.invalidate_bili_ticket()
                if self._bili_ticket == "":
                    self._bili_ticket = await _get_bili_ticket(credential)
                    self._bili_ticket_expires = int(time.time()) + 3 * 86400
                    request_log.dispatch(
                        "ANTI_SPIDER",
                        "反爬虫",
                        {"msg": f"获取 bili_ticket 成功: [{self._bili_ticket}]"},
                    )
        return self._bili_ticket, self._bili_ticket_expires

    def invalidate_buvid(self) -> None:
        """作废缓存的 buvid3/buvid4，下次 get_buvid() 时重新获取。"""
        self._buvid3 = ""
        self._buvid4 = ""

    def invalidate_bili_ticket(self) -> None:
        """作废缓存的 bili_ticket，下次 get_bili_ticket() 时重新获取。"""
        self._bili_ticket = ""
        self._bili_ticket_expires = 0


anti_spider_cache = AntiSpiderCache()


async def _get_spi_buvid() -> dict:
    """
    调用 spi 接口获取新的 buvid3/buvid4

    Returns:
        dict: 含 b_3（buvid3）与 b_4（buvid4）字段
    """
    api = API["info"]["spi"]
    client = get_client()
    resp = await client.request(method="GET", url=api["url"], headers=HEADERS.copy())
    # spi 端点响应恒为 JSON 对象，client 层 json() 诚实地返回 object，此处为唯一收窄点
    return cast(dict, resp.json())["data"]


"""
思路来源：https://github.com/SocialSisterYi/bilibili-API-collect/issues/933
"""


async def _active_buvid(buvid3: str, buvid4: str) -> None:
    """
    激活 buvid3/buvid4，模拟浏览器环境构造指纹 payload 并提交风控激活接口。

    Args:
        buvid3 (str): 待激活的 buvid3
        buvid4 (str): 待激活的 buvid4

    Raises:
        ExClimbWuzhiException: 激活接口返回非 0 错误码（风控拦截）时抛出
    """
    MOD = 1 << 64

    def get_time_milli() -> int:
        """获取当前毫秒级时间戳。"""
        return int(time.time() * 1000)

    def rotate_left(x: int, k: int) -> int:
        """将 64 位整数 x 循环左移 k 位。"""
        bin_str = bin(x)[2:].rjust(64, "0")
        return int(bin_str[k:] + bin_str[:k], base=2)

    def gen_uuid_infoc() -> str:
        """生成浏览器 _uuid cookie 格式的字符串（8-4-4-4-12 段 + 时间戳尾缀 + infoc）。"""
        t = get_time_milli() % 100000
        mp = [*list("123456789ABCDEF"), "10"]
        pck = [8, 4, 4, 4, 12]

        def gen_part(x):
            """从字符表中随机取 x 个字符组成一段。"""
            return "".join([random.choice(mp) for _ in range(x)])  # mimosa-ignore

        return "-".join([gen_part(size) for size in pck]) + str(t).ljust(5, "0") + "infoc"

    def gen_b_lsid() -> str:
        """生成 b_lsid cookie：8 位大写十六进制随机数 + 下划线 + 毫秒时间戳十六进制。"""
        ret = ""
        for _ in range(8):
            ret += hex(random.randint(0, 15))[2:].upper()  # mimosa-ignore
        ret = f"{ret}_{hex(get_time_milli())[2:].upper()}"
        return ret

    def gen_buvid_fp(key: str, seed: int):
        """对 payload 字符串做 murmur3 哈希生成 buvid_fp 指纹。"""
        source = io.BytesIO(bytes(key, "ascii"))
        m = murmur3_x64_128(source, seed)
        return f"{hex(m & (MOD - 1))[2:]}{hex(m >> 64)[2:]}"

    def murmur3_x64_128(source: io.BufferedIOBase, seed: int) -> int:
        """murmur3 x64 128 位哈希算法实现（纯 Python 移植，按 16 字节块处理）。"""
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
        """murmur3 的最终混合（finalization mix）步骤，增强哈希扩散性。"""
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
        """构造风控激活接口的 payload：模拟浏览器采集的环境指纹信息（UA、WebGL、字体等）。"""
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
    # 依次生成模拟浏览器环境的 uuid、payload 与 buvid_fp 指纹，随 cookies 一并提交激活
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
    # 激活接口响应恒为 JSON 对象，client 层 json() 诚实地返回 object，此处为唯一收窄点
    data = cast(dict, resp.json())
    if data["code"] != 0:
        raise ExClimbWuzhiException(data["code"], data["msg"])


def _enc_dm(params: dict) -> dict:
    """
    为请求参数补充 dm_img 系列风控字段（模拟浏览器行为指纹，当前为空记录 + 随机占位串）。

    Args:
        params (dict): 待补充参数，原地修改并返回

    Returns:
        dict: 补充了 dm_img_list / dm_img_str / dm_cover_img_str / dm_img_inter 的参数
    """
    dm_rand = "ABCDEFGHIJK"
    params.update(
        {
            "dm_img_list": "[]",  # 鼠标/键盘操作记录
            "dm_img_str": "".join(random.sample(dm_rand, 2)),  # mimosa-ignore
            "dm_cover_img_str": "".join(random.sample(dm_rand, 2)),  # mimosa-ignore
            "dm_img_inter": '{"ds":[],"wh":[0,0,0],"of":[0,0,0]}',
        }
    )
    return params


def _enc_sign(paramsordata: dict) -> dict:
    """
    为 APP 端请求计算 sign 签名：追加 appkey，按 key 排序拼接后与 appsec 一起做 MD5。

    Args:
        paramsordata (dict): 待签名参数，原地修改并返回

    Returns:
        dict: 排序后追加了 appkey / sign 的参数
    """
    paramsordata["appkey"] = APPKEY
    paramsordata = dict(sorted(paramsordata.items()))
    paramsordata["sign"] = hashlib.md5((urllib.parse.urlencode(paramsordata) + APPSEC).encode("utf-8")).hexdigest()
    return paramsordata


"""
算法来源：https://github.com/SocialSisterYi/bilibili-API-collect/issues/903
"""


async def _get_bili_ticket(credential: Credential | None = None) -> str:
    """
    获取 bili_ticket：用固定密钥对当前时间戳做 HMAC-SHA256 签名后请求 ticket 接口。

    Args:
        credential (Credential | None, optional): 凭据类. Defaults to None.

    Returns:
        str: bili_ticket
    """

    def hmac_sha256(key: str, message: str) -> str:
        """计算 HMAC-SHA256 签名并返回十六进制字符串。"""
        key_bytes = key.encode("utf-8")
        message_bytes = message.encode("utf-8")
        hmac_obj = hmac.new(key_bytes, message_bytes, hashlib.sha256)
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
    # bili_ticket 端点响应恒为 JSON 对象，client 层 json() 诚实地返回 object，此处为唯一收窄点
    return cast(dict, resp.json())["data"]["ticket"]


################################################## END Anti-Spider ##################################################
