from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star, register
from astrbot.core.message.components import Plain
from astrbot.core.message.message_event_result import MessageChain

from .core.config import TextWorldConfig
from .core.database import TextWorldDB
from .core.narrator_v2 import BatchNarrator
from .core.service_v2 import TextWorldService
from .core.webapp import WebPanel

PLUGIN_NAME = "astrbot_plugin_text_world"
PLUGIN_VERSION = "0.2.0"


def help_text() -> str:
    return "\n".join(
        [
            "【学院都市文游】",
            "世界开启：在当前群登记世界",
            "创建角色 游戏名 | 身份设定：提交角色卡，需管理员审核",
            "行动 内容：提交本小时行动",
            "状态：查看自己的状态栏",
            "地图：查看当前位置和可前往地点",
            "待结算：查看本轮提交数量",
            "签到：每日获得学都币",
            "绑定文游私聊：私聊 bot 后绑定个人结果和早八状态栏",
            "管理员：世界结算 / 世界事件 / 世界后台",
        ]
    )


@register(
    PLUGIN_NAME,
    "codex",
    "学院都市小时制群文游系统：群行动、统一结算、私聊结果、前端后台、角色审核、事件预设、背包商店。",
    PLUGIN_VERSION,
)
class TextWorldPlugin(Star):
    def __init__(self, context: Context, config: Any):
        super().__init__(context)
        self.context = context
        self.cfg = TextWorldConfig(config, Path(__file__).resolve().parent)
        self.db = TextWorldDB(self.cfg.db_path)
        self.service = TextWorldService(self.db, self.cfg)
        self.narrator = BatchNarrator(context, self.cfg)
        self.web = WebPanel(self.service, self.cfg.web_host, self.cfg.web_port)
        self._scheduler_task: asyncio.Task | None = None
        self._last_event_by_group: dict[str, AstrMessageEvent] = {}
        self._settle_locks: dict[str, asyncio.Lock] = {}

    async def initialize(self):
        await asyncio.to_thread(self.db.init, self.cfg.admin_username, self.cfg.admin_password)
        if self.cfg.web_enabled:
            await self.web.start()
        self._scheduler_task = asyncio.create_task(self._scheduler_loop())
        logger.info("[TextWorld] initialized")

    async def terminate(self):
        if self._scheduler_task:
            self._scheduler_task.cancel()
            try:
                await self._scheduler_task
            except asyncio.CancelledError:
                pass
        await self.web.stop()
        logger.info("[TextWorld] terminated")

    @filter.command("世界帮助", alias={"文游帮助", "世界菜单"})
    async def world_help(self, event: AstrMessageEvent):
        yield event.plain_result(help_text()).stop_event()

    @filter.command("世界开启", alias={"开启世界", "文游开启"})
    async def open_world(self, event: AstrMessageEvent):
        group_id = self._group_id(event)
        if not group_id:
            yield event.plain_result("请在群聊中使用。").stop_event()
            return
        self._last_event_by_group[group_id] = event
        world = await asyncio.to_thread(self.service.ensure_world, group_id, self._origin(event))
        yield event.plain_result(
            f"学院都市文字世界已开启。当前第 {world['current_round']} 轮。\n后台：http://{self.cfg.web_host}:{self.cfg.web_port}"
        ).stop_event()

    @filter.command("创建角色", alias={"角色创建", "创建人物"})
    async def create_character(self, event: AstrMessageEvent):
        group_id = self._group_id(event)
        if not group_id:
            yield event.plain_result("请在群里提交角色卡。").stop_event()
            return
        payload = self._command_payload(event, ["创建角色", "角色创建", "创建人物"])
        name, sep, identity = payload.partition("|")
        if not sep:
            name, sep, identity = payload.partition("｜")
        ok, msg = await asyncio.to_thread(
            self.service.create_character_request,
            group_id,
            self._origin(event),
            self._sender_id(event),
            name.strip(),
            identity.strip(),
        )
        yield event.plain_result(msg).stop_event()

    @filter.command("行动", alias={"文游行动", "提交行动"})
    async def submit_action(self, event: AstrMessageEvent):
        group_id = self._group_id(event)
        if not group_id:
            yield event.plain_result("行动需要在群里提交。").stop_event()
            return
        self._last_event_by_group[group_id] = event
        text = self._command_payload(event, ["行动", "文游行动", "提交行动"])
        ok, msg = await asyncio.to_thread(
            self.service.submit_action,
            group_id,
            self._origin(event),
            self._sender_id(event),
            text,
        )
        yield event.plain_result(msg).stop_event()

    @filter.command("状态", alias={"我的状态", "状态栏"})
    async def status(self, event: AstrMessageEvent):
        group_id = self._group_id(event)
        if not group_id:
            yield event.plain_result("请在对应群聊里查看状态。").stop_event()
            return
        text = await asyncio.to_thread(self.service.get_status_by_qq, group_id, self._sender_id(event))
        yield event.plain_result(text).stop_event()

    @filter.command("地图", alias={"世界地图"})
    async def map_cmd(self, event: AstrMessageEvent):
        group_id = self._group_id(event)
        if not group_id:
            yield event.plain_result("请在群里查看地图。").stop_event()
            return
        text = await asyncio.to_thread(self.service.map_text, group_id, self._sender_id(event))
        yield event.plain_result(text).stop_event()

    @filter.command("待结算", alias={"本轮行动", "行动列表"})
    async def pending(self, event: AstrMessageEvent):
        group_id = self._group_id(event)
        if not group_id:
            yield event.plain_result("请在群里查看待结算信息。").stop_event()
            return
        text = await asyncio.to_thread(self.service.pending_text, group_id)
        yield event.plain_result(text).stop_event()

    @filter.command("签到", alias={"每日签到"})
    async def checkin(self, event: AstrMessageEvent):
        group_id = self._group_id(event)
        if not group_id:
            yield event.plain_result("请在群里签到。").stop_event()
            return
        ok, msg = await asyncio.to_thread(self.service.checkin, group_id, self._sender_id(event))
        yield event.plain_result(msg).stop_event()

    @filter.event_message_type(filter.EventMessageType.PRIVATE_MESSAGE)
    @filter.command("绑定文游私聊", alias={"绑定世界私聊", "文游私聊绑定"})
    async def bind_private(self, event: AstrMessageEvent):
        count = await asyncio.to_thread(self.service.bind_private, self._sender_id(event), self._origin(event))
        if count <= 0:
            yield event.plain_result("还没有找到你的角色卡，请先在群里提交或让管理员绑定 QQ 号。").stop_event()
            return
        yield event.plain_result(f"已绑定文游私聊，关联角色数：{count}。").stop_event()

    @filter.permission_type(filter.PermissionType.ADMIN)
    @filter.command("世界结算", alias={"文游结算", "立即结算"})
    async def manual_settle(self, event: AstrMessageEvent):
        group_id = self._group_id(event)
        if not group_id:
            yield event.plain_result("请在要结算的群里使用。").stop_event()
            return
        self._last_event_by_group[group_id] = event
        msg = await self._settle_group(group_id, event, force_event=False)
        yield event.plain_result(msg).stop_event()

    @filter.permission_type(filter.PermissionType.ADMIN)
    @filter.command("世界事件", alias={"文游事件", "触发事件"})
    async def manual_event(self, event: AstrMessageEvent):
        group_id = self._group_id(event)
        if not group_id:
            yield event.plain_result("请在要触发事件的群里使用。").stop_event()
            return
        self._last_event_by_group[group_id] = event
        msg = await self._settle_group(group_id, event, force_event=True)
        yield event.plain_result(msg).stop_event()

    @filter.permission_type(filter.PermissionType.ADMIN)
    @filter.command("世界后台", alias={"文游后台"})
    async def web_url(self, event: AstrMessageEvent):
        yield event.plain_result(
            f"文游后台：http://{self.cfg.web_host}:{self.cfg.web_port}\n默认管理员账号请看插件配置。"
        ).stop_event()

    async def _scheduler_loop(self):
        while True:
            try:
                due = await asyncio.to_thread(self.service.due_worlds)
                for world in due:
                    await self._settle_group(world["group_id"], self._last_event_by_group.get(world["group_id"]))
                daily_due = await asyncio.to_thread(self.service.due_daily_worlds)
                for world in daily_due:
                    await self._send_daily_status(world)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.exception(f"[TextWorld] scheduler failed: {exc}")
            await asyncio.sleep(self.cfg.scheduler_poll_seconds)

    async def _settle_group(
        self,
        group_id: str,
        event: AstrMessageEvent | None = None,
        force_event: bool = False,
    ) -> str:
        lock = self._settle_locks.setdefault(group_id, asyncio.Lock())
        if lock.locked():
            return "这个世界正在结算中，请稍后再试。"
        async with lock:
            return await self._settle_group_locked(group_id, event, force_event)

    async def _settle_group_locked(
        self,
        group_id: str,
        event: AstrMessageEvent | None = None,
        force_event: bool = False,
    ) -> str:
        try:
            result = await asyncio.to_thread(self.service.settle_round, group_id, force_event)
            provider_id = await self._provider_id(event) if event else self.cfg.default_provider_id
            result = await self.narrator.narrate_round(result, provider_id)
            group_sent = await self._send_group(group_id, result["public_summary"], event)
            private_sent, private_total = await self._send_private_results(group_id, result["private_results"], event)
            if not group_sent:
                logger.warning(f"[TextWorld] round {result['round_no']} public summary for group {group_id} was not sent.")
            if private_sent < private_total:
                logger.warning(f"[TextWorld] round {result['round_no']} private results for group {group_id}: {private_sent}/{private_total} sent.")
            suffix = "" if group_sent else "（群公告发送失败，请检查 bot 权限或群 origin）"
            if private_total:
                suffix += f" 私聊发送 {private_sent}/{private_total}。"
            return f"第 {result['round_no']} 轮结算完成。{suffix}"
        except Exception as exc:
            logger.exception(f"[TextWorld] settle failed: {exc}")
            return f"结算失败：{exc}"

    async def _send_daily_status(self, world: dict[str, Any]) -> None:
        statuses = await asyncio.to_thread(self.service.daily_statuses, world["group_id"])
        sent_count = 0
        for qq_id, text in statuses.items():
            if await self._send_private_by_qq(world["group_id"], qq_id, "【早安状态栏】\n" + text, None):
                sent_count += 1
        if sent_count or not statuses:
            await asyncio.to_thread(self.service.mark_daily_sent, world["group_id"])
        else:
            logger.warning(f"[TextWorld] daily status for group {world['group_id']} was not marked sent because all private sends failed.")

    async def _send_group(
        self,
        group_id: str,
        text: str,
        event: AstrMessageEvent | None,
    ) -> bool:
        if event:
            try:
                await event.send(event.plain_result(text))
                return True
            except Exception as exc:
                logger.warning(f"[TextWorld] group send via event failed: {exc}")
        row = await asyncio.to_thread(self.db.fetch_one, "SELECT group_origin FROM worlds WHERE group_id=?", (group_id,))
        origin = str((row or {}).get("group_origin") or "")
        if origin:
            return await self._send_origin(origin, text)
        return False

    async def _send_private_results(
        self,
        group_id: str,
        results: dict[str, str],
        event: AstrMessageEvent | None,
    ) -> tuple[int, int]:
        sent = 0
        for qq_id, text in results.items():
            if await self._send_private_by_qq(group_id, qq_id, text, event):
                sent += 1
        return sent, len(results)

    async def _send_private_by_qq(
        self,
        group_id: str,
        qq_id: str,
        text: str,
        event: AstrMessageEvent | None,
    ) -> bool:
        row = await asyncio.to_thread(
            self.db.fetch_one,
            "SELECT private_origin FROM characters WHERE group_id=? AND qq_id=?",
            (group_id, qq_id),
        )
        origin = str((row or {}).get("private_origin") or "")
        if origin and await self._send_origin(origin, text):
            return True
        if event and self.cfg.enable_onebot_private_fallback:
            return await self._send_onebot_private(event, qq_id, text)
        logger.warning(f"[TextWorld] private result not sent to {qq_id}; ask user to bind private chat.")
        return False

    async def _send_origin(self, origin: str, text: str) -> bool:
        try:
            await self.context.send_message(origin, MessageChain([Plain(text)]))
            return True
        except Exception as exc:
            logger.warning(f"[TextWorld] send origin failed: {exc}")
            return False

    async def _send_onebot_private(self, event: AstrMessageEvent, qq_id: str, text: str) -> bool:
        bot = getattr(event, "bot", None)
        if not bot or not hasattr(bot, "send_private_msg"):
            return False
        try:
            await bot.send_private_msg(user_id=int(qq_id), message=[{"type": "text", "data": {"text": text}}])
            return True
        except Exception as exc:
            logger.warning(f"[TextWorld] onebot private send failed: {exc}")
            return False

    async def _provider_id(self, event: AstrMessageEvent | None) -> str:
        if not event:
            return self.cfg.default_provider_id
        try:
            value = await self.context.get_current_chat_provider_id(umo=event.unified_msg_origin)
            if isinstance(value, str) and value:
                return value
        except Exception:
            pass
        return self.cfg.default_provider_id

    def _group_id(self, event: AstrMessageEvent) -> str:
        try:
            value = event.get_group_id()
            if value:
                return str(value)
        except Exception:
            pass
        message_obj = getattr(event, "message_obj", None)
        for name in ("group_id", "session_id"):
            value = getattr(message_obj, name, None)
            if value:
                return str(value)
        return ""

    def _sender_id(self, event: AstrMessageEvent) -> str:
        try:
            value = event.get_sender_id()
            if value:
                return str(value)
        except Exception:
            pass
        message_obj = getattr(event, "message_obj", None)
        sender = getattr(message_obj, "sender", None)
        for obj in (sender, message_obj, event):
            value = getattr(obj, "user_id", None) if obj else None
            if value:
                return str(value)
        return ""

    def _origin(self, event: AstrMessageEvent) -> str:
        return str(getattr(event, "unified_msg_origin", "") or "")

    def _command_payload(self, event: AstrMessageEvent, names: list[str]) -> str:
        text = (getattr(event, "message_str", "") or "").strip()
        for name in names:
            if text == name:
                return ""
            if text.startswith(name):
                return text[len(name):].strip()
        return text
