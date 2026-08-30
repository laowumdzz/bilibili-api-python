import json

from bilibili_api import sync
from bilibili_api.utils.initial_state import get_initial_state


async def main() -> dict:
    content = {}
    content["anime"] = (await get_initial_state("https://www.bilibili.com/anime/index/"))[0]
    content["movie"] = (await get_initial_state("https://www.bilibili.com/movie/index/"))[0]
    content["tv"] = (await get_initial_state("https://www.bilibili.com/tv/index/"))[0]
    content["documentary"] = (await get_initial_state("https://www.bilibili.com/documentary/index/"))[0]
    content["variety"] = (await get_initial_state("https://www.bilibili.com/variety/index/"))[0]
    content["guochuang"] = (await get_initial_state("https://www.bilibili.com/guochuang/index/"))[0]
    return content


if __name__ == "__main__":
    # 异步函数内不使用阻塞式 open，改为同步侧写入（ASYNC230）
    # 硬编码脚本输出文件名，无外部输入
    # mimosa-ignore
    with open("bangumi_index_params.json", "w", encoding="UTF-8") as f:
        json.dump(sync(main()), f, ensure_ascii=False, indent=4)
