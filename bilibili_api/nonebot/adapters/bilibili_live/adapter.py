"""
bilibili_api.nonebot.adapters.bilibili_live.adapter

适配器主体：生命周期、房间监听、帧分发与 API 分发。

网络与登录态全部下沉到库：HTTP / WebSocket 经 `BiliAPIClient`（由 NoneBot 驱动
承载），账号经凭据存储，反爬要素由库集中实现；本模块只负责协议与编排。
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from contextlib import suppress
import time
from typing import Any

from typing_extensions import override

from nonebot import get_plugin_config
from nonebot.adapters import Adapter as BaseAdapter
from nonebot.adapters import Bot as BaseBot

from ....clients.NoneBotClient import NoneBotClient, driver_name, ensure_websocket_support
from ....exceptions import ArgsException, NetworkException, ResponseCodeException
from ....live import LiveRoom
from ....utils._api import Api, get_buvid
from ....utils._credential import Credential
from ....utils._session import BiliAPIClient, get_client, register_client
from ....utils._types import BiliWsMsgType
from ....utils.credential_store_sqlite import SQLiteCredentialStoreManager
from .accounts import AccountPool, build_pool_from_store
from .bot import WebBot
from .config import Config, NoneBotLiveConfig, parse_config
from .const import (
    API_DANMU_INFO,
    HEARTBEAT_INTERVAL,
    HEARTBEAT_TIMEOUT,
    USER_AGENT,
    get_endpoint,
)
from .event import Event, packet_to_event
from .exception import ApiNotAvailable
from .log import log
from .packet import OpCode, Packet, new_auth_packet
from .scheduler import ConnectionScheduler, RoomState, RoomSubscription

CLIENT_NAME = "nonebot"
"""驱动承载客户端在库内的注册名。"""

AUTH_TIMEOUT = 15.0
"""等待鉴权回复的超时（秒）。"""


class Adapter(BaseAdapter):
    """NoneBot 直播适配器。"""

    def __init__(self, driver: Any, **kwargs: Any) -> None:
        """
        Args:
            driver (Any): NoneBot 驱动。
            **kwargs (Any): 传递给 NoneBot `Adapter` 的其余参数。
        """
        super().__init__(driver, **kwargs)
        self._config: NoneBotLiveConfig | None = None
        self._store: SQLiteCredentialStoreManager | None = None
        self._pool: AccountPool | None = None
        self._scheduler: ConnectionScheduler | None = None
        self._client: BiliAPIClient | None = None
        self._ws_ids: dict[int, int] = {}
        self._closed = False
        self._clock: Callable[[], float] = time.monotonic
        self._sleep: Callable[[float], Awaitable[None]] = asyncio.sleep
        self.setup()

    @classmethod
    @override
    def get_name(cls) -> str:
        """
        返回适配器名称（与上游一致）。

        Returns:
            str: 适配器名称。
        """
        return "bilibili Live"

    def setup(self) -> None:
        """挂接启动与关闭钩子。"""
        self.on_ready(self.startup)
        self.driver.on_shutdown(self.shutdown)

    async def startup(self) -> None:
        """
        启动适配器。

        顺序固定为：能力检测 → 配置校验 → 客户端注册 → 凭据存储加载 → uid 校验 →
        账号池 → 房间归一 → 按策略建立订阅。

        Raises:
            ArgsException: 配置非法、uid 缺失、驱动不支持 WebSocket、规模超限。
            CredentialStoreCorruptException: 凭据存储损坏（原样透传，不静默重建）。
            CredentialStoreVersionMismatchException: 凭据存储版本不匹配（原样透传）。
        """
        if self._closed:
            return
        ensure_websocket_support(self.driver)
        config = parse_config(get_plugin_config(Config).bilibili_live_bots)
        self._config = config
        self._register_client()
        store = await self._load_store(config)
        self._store = store
        pool = await build_pool_from_store(store, config)
        self._pool = pool
        for uid in pool.all_uids():
            slot = pool.get(uid)
            if slot is None:
                continue
            bot = WebBot(self, self_id=str(uid), credential=slot.credential.model_copy(deep=True))
            self.bot_connect(bot)
        self._scheduler = ConnectionScheduler(
            config=config,
            pool=pool,
            ops=self,
            persist_credential=self._persist_credential,
        )
        self._scheduler.subscribe_from_config()
        declared_rooms = sum(len(bot.room_ids) for bot in config.bots)
        if declared_rooms > len(self._scheduler.subscriptions):
            log(
                "WARNING",
                f"配置声明了 {declared_rooms} 个房间，去重后为 "
                f"{len(self._scheduler.subscriptions)} 个（同一房间被多次声明，已合并）",
            )
        await self._normalize_rooms(config)
        await self._scheduler.startup()
        log(
            "INFO",
            f"bilibili Live 适配器已启动：{len(pool.all_uids())} 个账号，{len(self._scheduler.subscriptions)} 个房间",
        )

    def _register_client(self) -> None:
        """注册并选中由 NoneBot 驱动承载的客户端（接管选择并记录 INFO）。"""
        register_client(CLIENT_NAME, NoneBotClient, {"chunk_size": 262144})
        client = get_client()
        self._client = client
        log(
            "INFO",
            f"bilibili Live 适配器已接管请求客户端：{CLIENT_NAME}（驱动 {driver_name(self.driver)}）",
        )

    async def _load_store(self, config: NoneBotLiveConfig) -> SQLiteCredentialStoreManager:
        """
        取凭据存储单例并加载数据。

        必须先 `load()` 再读写：存储为「整表删除后重写」，单例初始内存为空，
        顺序颠倒会清空其它账号（research D9）。

        Args:
            config (NoneBotLiveConfig): 适配器配置。

        Returns:
            SQLiteCredentialStoreManager: 已加载的存储管理器。
        """
        store = SQLiteCredentialStoreManager(db_path=config.db_path, key_path=config.key_path)
        return await type(store).load()

    async def _persist_credential(self, uid: int, credential: Credential) -> None:
        """
        把刷新后的凭据写回存储。

        Args:
            uid (int): 账号 uid。
            credential (Credential): 刷新后的凭据。
        """
        if self._store is None:
            raise ArgsException("凭据存储尚未初始化，无法写回刷新后的凭据")
        await self._store.add_credential(uid, credential)

    async def _normalize_rooms(self, config: NoneBotLiveConfig) -> None:
        """
        归一房间长短号、按真实房间号去重并校验规模上限（V-05 / V-07）。

        Args:
            config (NoneBotLiveConfig): 适配器配置。
        """
        if self._scheduler is None:
            return
        seen: dict[int, RoomSubscription] = {}
        for subscription in list(self._scheduler.subscriptions.values()):
            try:
                info = await LiveRoom(
                    room_display_id=subscription.room_display_id,
                    credential=Credential(),
                ).get_room_play_info()
            except Exception as e:
                log(
                    "WARNING",
                    f"房间 {subscription.room_display_id} 归一失败（V-07），已跳过：{type(e).__name__}",
                )
                subscription.state = RoomState.CLOSED
                self._scheduler.subscriptions.pop(subscription.room_display_id, None)
                continue
            real_id = int(info["room_id"])
            subscription.room_real_id = real_id
            anchor_uid = info.get("uid")
            for bot in self.bots.values():
                if isinstance(bot, WebBot) and isinstance(anchor_uid, int):
                    bot.room_anchors[real_id] = anchor_uid
            existing = seen.get(real_id)
            if existing is not None:
                log(
                    "WARNING",
                    f"房间 {subscription.room_display_id} 与 {existing.room_display_id} "
                    f"归一后同为 {real_id}，已去重（保留先声明者）",
                )
                subscription.state = RoomState.CLOSED
                self._scheduler.subscriptions.pop(subscription.room_display_id, None)
                continue
            seen[real_id] = subscription
        config.check_room_scale(len(seen))

    def _bot_for(self, subscription: RoomSubscription) -> WebBot | None:
        """
        取订阅当前承载账号对应的 WebBot。

        Args:
            subscription (RoomSubscription): 房间订阅。

        Returns:
            WebBot | None: Bot 实例；账号未分配或不存在时为 `None`。
        """
        uid = subscription.uid
        if uid is None and self._pool is not None:
            slot = self._pool.current()
            uid = None if slot is None else slot.uid
        if uid is None:
            return None
        bot = self.bots.get(str(uid))
        return bot if isinstance(bot, WebBot) else None

    async def connect(self, subscription: RoomSubscription) -> None:
        """
        建立并鉴权一条房间连接，随后启动心跳与读取任务。

        Args:
            subscription (RoomSubscription): 房间订阅。

        Raises:
            ArgsException: 账号池无可用账号（V-08）或 Bot 缺失。
            CredentialNoSessdataException: 凭据缺少登录态。
            CookiesRefreshException: 凭据刷新失败（账号已标记死亡）。
            NetworkException: 打开 WebSocket 失败。
            ResponseCodeException: 鉴权返回非 0 代码。
        """
        if self._client is None:
            raise ArgsException("请求客户端尚未初始化")
        bot = self._bot_for(subscription)
        if bot is None:
            raise ArgsException("没有可用账号可供房间建立连接（V-08）")
        uid = int(bot.self_id)
        subscription.uid = uid
        if self._pool is not None:
            slot = await self._pool.ensure_usable(uid, self._persist_credential)
            bot.credential = slot.credential.model_copy(deep=True)
        if subscription.room_real_id is None:
            await self._resolve_room(subscription)
        real_id = subscription.room_real_id
        if real_id is None:
            raise ArgsException(f"房间 {subscription.room_display_id} 缺少真实房间号")
        api = get_endpoint(API_DANMU_INFO)
        info = (
            await Api(**api, credential=bot.credential)
            .update_params(
                id=real_id,
                type=0,
                web_location="444.8",
            )
            .result_dict()
        )
        hosts = info.get("host_list") or []
        if not hosts:
            raise NetworkException(200, "弹幕服务器列表为空")
        host = hosts[0]
        buvid3 = bot.credential.buvid3 or (await get_buvid())[0]
        headers = {
            "User-Agent": USER_AGENT,
            "Cookie": self._cookie_header(bot.credential),
        }
        ws_id = await self._client.ws_create(
            f"wss://{host['host']}:{host['wss_port']}/sub",
            headers=headers,
        )
        try:
            await self._client.ws_send(ws_id, new_auth_packet(real_id, uid, str(info["token"]), buvid3).to_bytes())
            await self._await_auth(ws_id)
        except BaseException:
            await self._client.ws_close(ws_id)
            raise
        self._ws_ids[real_id] = ws_id
        subscription.state = RoomState.CONNECTED
        if self._scheduler is not None:
            self._scheduler.note_frame(subscription)
        for coroutine in (self._heartbeat_loop(subscription, ws_id), self._read_loop(subscription, ws_id)):
            task: asyncio.Task[Any] = asyncio.create_task(coroutine)
            subscription.tasks.add(task)
            task.add_done_callback(subscription.tasks.discard)
        log(
            "SUCCESS",
            f"房间 {real_id} 已连接（账号 uid={uid}）",
        )

    @staticmethod
    def _cookie_header(credential: Credential) -> str:
        """
        构造 WebSocket 握手用的 Cookie 头。

        Args:
            credential (Credential): 账号凭据。

        Returns:
            str: `k=v; k=v` 形式的 Cookie 头；无有效字段时为空串。
        """
        parts = [f"{key}={value}" for key, value in credential.get_cookies().items() if value]
        return "; ".join(parts)

    async def _resolve_room(self, subscription: RoomSubscription) -> None:
        """
        归一房间号并记录主播 uid。

        Args:
            subscription (RoomSubscription): 房间订阅。
        """
        info = await LiveRoom(
            room_display_id=subscription.room_display_id, credential=Credential()
        ).get_room_play_info()
        subscription.room_real_id = int(info["room_id"])
        anchor_uid = info.get("uid")
        if isinstance(anchor_uid, int):
            for bot in self.bots.values():
                if isinstance(bot, WebBot):
                    bot.room_anchors[subscription.room_real_id] = anchor_uid

    async def _await_auth(self, ws_id: int) -> None:
        """
        等待鉴权回复并校验返回码。

        Args:
            ws_id (int): WebSocket 连接编号。

        Raises:
            NetworkException: 连接在鉴权完成前关闭。
            ResponseCodeException: 鉴权返回非 0 代码。
        """
        if self._client is None:
            raise ArgsException("请求客户端尚未初始化")
        loop = asyncio.get_running_loop()
        deadline = loop.time() + AUTH_TIMEOUT
        while True:
            remaining = deadline - loop.time()
            if remaining <= 0:
                raise NetworkException(0, "等待鉴权回复超时")
            data, flag = await asyncio.wait_for(self._client.ws_recv(ws_id), timeout=remaining)
            if flag is BiliWsMsgType.CLOSED:
                raise NetworkException(0, "连接在鉴权完成前关闭")
            if flag is not BiliWsMsgType.BINARY:
                continue
            try:
                packet = Packet.from_bytes(data)
            except ValueError:
                continue
            if packet.opcode != OpCode.AuthReply:
                continue
            decoded = packet.decode_dict()
            code = int(decoded.get("code", 0))
            if code != 0:
                raise ResponseCodeException(code, str(decoded.get("message", "鉴权失败")), decoded)
            return

    async def _read_loop(self, subscription: RoomSubscription, ws_id: int) -> None:
        """
        读取循环：按帧到达顺序分发事件；结束或出错后进入失败分类流程。

        Args:
            subscription (RoomSubscription): 房间订阅。
            ws_id (int): WebSocket 连接编号。
        """
        assert self._client is not None
        intentional = False
        error: BaseException | None = None
        try:
            while True:
                data, flag = await self._client.ws_recv(ws_id)
                if flag is BiliWsMsgType.CLOSED:
                    intentional = subscription.state in (RoomState.CLOSING, RoomState.CLOSED) or self._closed
                    if not intentional:
                        error = NetworkException(1000, "弹幕连接已关闭")
                    break
                if flag is not BiliWsMsgType.BINARY:
                    continue
                if self._scheduler is not None:
                    self._scheduler.note_frame(subscription)
                await self._handle_ws_message(subscription, data)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            error = e
        finally:
            await self._release_ws(subscription)
            if error is not None and not self._closed and self._scheduler is not None:
                await self._scheduler.handle_failure(subscription, error)

    async def _release_ws(self, subscription: RoomSubscription) -> None:
        """
        关闭订阅对应的 WebSocket（幂等）。

        Args:
            subscription (RoomSubscription): 房间订阅。
        """
        real_id = subscription.room_real_id
        if real_id is None or self._client is None:
            return
        ws_id = self._ws_ids.pop(real_id, None)
        if ws_id is not None:
            with suppress(Exception):
                await self._client.ws_close(ws_id)

    async def _handle_ws_message(self, subscription: RoomSubscription, data: bytes) -> None:
        """
        解析一段 WebSocket 数据并把其中每个帧转为事件。

        Args:
            subscription (RoomSubscription): 房间订阅。
            data (bytes): 原始数据。
        """
        real_id = subscription.room_real_id
        if real_id is None:
            return
        offset = 0
        while offset < len(data):
            try:
                packet = Packet.from_bytes(data[offset:])
            except ValueError:
                log("ERROR", f"房间 {real_id} 解析帧头失败：offset={offset}, 长度={len(data)}")
                return
            offset += packet.length
            try:
                decoded = packet.decode_data()
            except Exception as e:
                log("ERROR", f"房间 {real_id} 解包失败，已跳过：{type(e).__name__}")
                continue
            if isinstance(decoded, list):
                for sub_packet in decoded:
                    await self._dispatch_packet(subscription, sub_packet)
            else:
                await self._dispatch_packet(subscription, packet)

    async def _dispatch_packet(self, subscription: RoomSubscription, packet: Packet) -> None:
        """
        把单个帧转为事件并交给 NoneBot；单帧失败不影响后续帧。

        Args:
            subscription (RoomSubscription): 房间订阅。
            packet (Packet): 协议帧。
        """
        real_id = subscription.room_real_id
        if real_id is None:
            return
        if packet.opcode == OpCode.AuthReply:
            return
        try:
            event: Event = packet_to_event(packet, real_id)
        except Exception as e:
            log("WARNING", f"房间 {real_id} 事件解析失败，已跳过：{type(e).__name__}")
            return
        bot = self._bot_for(subscription)
        if bot is None:
            return
        try:
            await bot._handle_event(event)
        except Exception as e:
            # FR-014：单个处理器异常不得中断该房间后续分发
            log("ERROR", f"房间 {real_id} 事件处理器异常：{type(e).__name__}")

    async def _heartbeat_loop(self, subscription: RoomSubscription, ws_id: int) -> None:
        """
        心跳循环：定时发送心跳；超过 `HEARTBEAT_TIMEOUT` 未收帧则断开以触发重连。

        关闭连接后由读取循环把 `CLOSED` 交回调度器，进入退避重连（FR-021）。

        Args:
            subscription (RoomSubscription): 房间订阅。
            ws_id (int): WebSocket 连接编号。
        """
        assert self._client is not None
        while not self._closed:
            await self._sleep(HEARTBEAT_INTERVAL)
            if subscription.state is not RoomState.CONNECTED:
                return
            last_frame = subscription.last_frame_at
            if last_frame is not None and self._clock() - last_frame > HEARTBEAT_TIMEOUT:
                log("WARNING", f"房间 {subscription.room_real_id} 心跳超时，准备重连")
                with suppress(Exception):
                    await self._client.ws_close(ws_id)
                return
            with suppress(Exception):
                await self._client.ws_send(ws_id, Packet.new_binary(OpCode.Heartbeat, 0, b"").to_bytes())

    async def disconnect(self, subscription: RoomSubscription) -> None:
        """
        断开订阅（幂等）：先关连接，再取消心跳与读取任务。

        Args:
            subscription (RoomSubscription): 房间订阅。
        """
        await self._release_ws(subscription)
        current = asyncio.current_task()
        tasks = [task for task in subscription.tasks if task is not current]
        for task in tasks:
            task.cancel()
        for task in tasks:
            with suppress(asyncio.CancelledError, Exception):
                await task
        subscription.tasks.clear()

    async def live_status(self, room_display_id: int) -> int:
        """
        查询开播状态（以空凭据轮询，research D11）。

        Args:
            room_display_id (int): 房间号。

        Returns:
            int: `0` 未开播、`1` 直播中、`2` 轮播。
        """
        info = await LiveRoom(room_display_id=room_display_id, credential=Credential()).get_room_play_info()
        return int(info.get("live_status", 0))

    async def shutdown(self) -> None:
        """
        关闭适配器：取消全部任务、关闭连接与客户端，可重复安全调用。
        """
        if self._closed:
            return
        self._closed = True
        if self._scheduler is not None:
            await self._scheduler.shutdown()
        for bot in list(self.bots.values()):
            self.bot_disconnect(bot)
        self.bots.clear()
        if self._client is not None:
            with suppress(Exception):
                await self._client.close()
        self._ws_ids.clear()

    @override
    async def _call_api(self, bot: BaseBot, api: str, **data: Any) -> Any:
        """
        分发 Bot 公共 API 方法。

        Args:
            bot (Bot): 目标 Bot。
            api (str): 方法名。
            **data (Any): 方法参数。

        Returns:
            Any: 方法返回值。

        Raises:
            ApiNotAvailable: 私有名、未知名或非 WebBot。
        """
        if not isinstance(bot, WebBot):
            raise ApiNotAvailable
        handler = getattr(bot.__class__, api, None)
        if api.startswith("_") or handler is None:
            raise ApiNotAvailable
        log("DEBUG", f"WebBot {bot.self_id} calling API <y>{api}</y>")
        return await handler(bot, **data)


__all__ = ["Adapter"]
