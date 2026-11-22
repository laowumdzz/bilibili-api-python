"""
scripts/record_nonebot_frames.py

人工执行的只读弹幕帧录制脚本（不入 CI、不发送任何内容）。

用途：为适配器事件回归补充真实帧来源。脚本以匿名凭据只读连接一个直播间，
把收到的帧按 `cmd` 分文件写入 `tests/fixtures/nonebot_frames/raw/`（该目录
默认不入库，见其 `.gitignore`），并对用户名 / 头像 / uid 做脱敏。

用法：

```bash
uv run python scripts/record_nonebot_frames.py --room 544853 --duration 120
```

注意：脚本只读（订阅弹幕），不得用于发送弹幕或改变任何账号状态。
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import datetime
import json
import logging
import pathlib
from typing import Any

from bilibili_api._live_danmaku import LiveDanmaku
from bilibili_api.utils.network import Credential

logger = logging.getLogger("record_nonebot_frames")

RAW_DIR = pathlib.Path("tests/fixtures/nonebot_frames/raw")

_NAME_KEYS = frozenset({"uname", "uface", "face", "name", "open_id", "union_id", "anchor_uname", "uname_color"})
_UID_KEYS = frozenset({"uid", "ruid", "target_id", "tuid"})


class _Sanitizer:
    """把用户标识替换为稳定占位值，避免把真实用户信息写进样本。"""

    def __init__(self) -> None:
        self._uids: dict[int, int] = {}

    def sanitize(self, value: Any) -> Any:
        """
        递归脱敏。

        Args:
            value (Any): 待脱敏数据。

        Returns:
            Any: 脱敏后的副本。
        """
        if isinstance(value, dict):
            result: dict[str, Any] = {}
            for key, item in value.items():
                lowered = str(key).lower()
                if lowered in _NAME_KEYS:
                    result[str(key)] = "user"
                elif lowered in _UID_KEYS and isinstance(item, int):
                    result[str(key)] = self._uids.setdefault(item, len(self._uids) + 1)
                else:
                    result[str(key)] = self.sanitize(item)
            return result
        if isinstance(value, list):
            return [self.sanitize(item) for item in value]
        return value


async def _wait_connected(danmaku: LiveDanmaku, timeout: float = 20.0) -> None:
    """
    等待弹幕连接建立。

    Args:
        danmaku (LiveDanmaku): 弹幕实例。
        timeout (float, optional): 最长等待秒数. Defaults to 20.0.

    Raises:
        TimeoutError: 超时仍未建立连接。
    """
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while danmaku.get_status() != LiveDanmaku.STATUS_ESTABLISHED:
        if loop.time() > deadline:
            raise TimeoutError("等待弹幕连接建立超时")
        await asyncio.sleep(0.2)


async def record(room: int, duration: float) -> dict[str, list[dict]]:
    """
    录制一个直播间的弹幕帧。

    Args:
        room (int): 房间号（长短号均可）。
        duration (float): 录制时长（秒）。

    Returns:
        dict[str, list[dict]]: cmd 到帧列表的映射（已脱敏）。
    """
    sanitizer = _Sanitizer()
    frames: dict[str, list[dict]] = {}
    danmaku = LiveDanmaku(room_display_id=room, credential=Credential())

    @danmaku.on("ALL")
    async def on_event(event: dict[str, Any]) -> None:
        data = event.get("data")
        if not isinstance(data, dict):
            return
        raw_cmd = data.get("cmd")
        if not isinstance(raw_cmd, str):
            return
        cmd = raw_cmd.split(":", 1)[0]
        frames.setdefault(cmd, []).append(sanitizer.sanitize(data))

    task = asyncio.create_task(danmaku.connect())
    try:
        await _wait_connected(danmaku)
        logger.info("已连接房间 %s，开始录制 %.0f 秒", room, duration)
        await asyncio.sleep(duration)
    finally:
        if danmaku.get_status() == LiveDanmaku.STATUS_ESTABLISHED:
            await danmaku.disconnect()
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    return frames


def write_frames(out_dir: pathlib.Path, frames: dict[str, list[dict]], room: int, duration: float) -> dict[str, int]:
    """
    把脱敏后的帧写入按 cmd 分文件。

    Args:
        out_dir (pathlib.Path): 输出目录。
        frames (dict[str, list[dict]]): cmd 到帧列表的映射。
        room (int): 房间号。
        duration (float): 录制时长（秒）。

    Returns:
        dict[str, int]: 每个 cmd 写入的帧数。
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    for cmd, items in frames.items():
        path = out_dir / f"{cmd}.jsonl"
        with path.open("w", encoding="utf-8", newline="\n") as handle:
            for item in items:
                handle.write(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n")
    meta = out_dir / "meta.txt"
    meta.write_text(
        f"room={room}\nrecorded_at={datetime.now().isoformat(timespec='seconds')}\nruntime={duration}\n",
        encoding="utf-8",
    )
    return {cmd: len(items) for cmd, items in frames.items()}


def main() -> None:
    """命令行入口。"""
    parser = argparse.ArgumentParser(description="只读录制 bilibili 直播弹幕帧（人工执行，不入 CI）")
    parser.add_argument("--room", type=int, default=544853, help="房间号（长短号均可）")
    parser.add_argument("--duration", type=float, default=120.0, help="录制时长（秒）")
    parser.add_argument("--out", type=pathlib.Path, default=RAW_DIR, help="输出目录")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
    frames = asyncio.run(record(room=args.room, duration=args.duration))
    counts = write_frames(args.out, frames, room=args.room, duration=args.duration)
    logger.info("录制完成：%s 个 cmd，共 %s 帧", len(counts), sum(counts.values()))


if __name__ == "__main__":
    main()
