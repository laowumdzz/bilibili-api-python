"""网页端二维码登录真机验收脚本。

流程：终端渲染二维码 → 手机 B 站 App 扫码并确认 → 轮询至完成 →
输出凭据各字段非空性校验（只打印字段名与长度，严禁输出凭据值）→
调用 check_valid 验证登录身份被识别。

用法：uv run python scripts/qrcode_login.py
"""

import asyncio
import logging

from bilibili_api.login_v2 import QrCodeLogin, QrCodeLoginEvents

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("qrcode_login")


async def main() -> None:
    login = QrCodeLogin()
    await login.generate_qrcode()
    logger.info("%s", login.get_qrcode_terminal())
    logger.info("请使用手机 B 站 App 扫码并确认登录...")

    while True:
        state = await login.check_state()
        if state == QrCodeLoginEvents.DONE:
            break
        if state == QrCodeLoginEvents.SCAN:
            logger.info("等待扫码...")
        elif state == QrCodeLoginEvents.CONF:
            logger.info("已扫码，等待手机上确认...")
        else:
            logger.info("二维码已过期，请重新运行脚本。")
            return
        await asyncio.sleep(2)

    credential = login.get_credential()
    # 只输出非空性与长度，严禁打印凭据值
    for field in ("sessdata", "bili_jct", "dedeuserid", "ac_time_value"):
        value = getattr(credential, field) or ""
        status = f"已取得 (长度 {len(value)})" if value else "为空 ✗"
        logger.info("%s: %s", field, status)

    valid = await credential.check_valid()
    logger.info("登录身份校验 (check_valid): %s", "已识别" if valid else "未识别 ✗")


if __name__ == "__main__":
    asyncio.run(main())
