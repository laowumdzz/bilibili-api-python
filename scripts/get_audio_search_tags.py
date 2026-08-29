import json
import sys

import httpx

from bilibili_api.utils.network import HEADERS

sys.stdout.write(
    json.dumps(
        httpx.get("https://api.bilibili.com/x/mv/tag", headers=HEADERS).json(),
        indent=4,
        ensure_ascii=False,
    )
    + "\n"
)
