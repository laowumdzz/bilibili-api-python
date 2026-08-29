import json
import sys

from bilibili_api import Api, sync


async def main() -> None:
    res = await Api(url="https://s1.hdslb.com/bfs/subtitle/subtitle_lan.json", method="GET").request(raw=True)
    sys.stdout.write(json.dumps(res, ensure_ascii=False, indent=4) + "\n")


sync(main())
