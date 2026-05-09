from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star, register
from astrbot.core.message.components import Image, Plain
from astrbot.core.message.message_event_result import MessageChain

from .core.compat import to_thread
from .core.config import TextWorldConfig
from .core.database import TextWorldDB
from .core.defaults import CHARACTER_CARD_TEMPLATE
from .core.narrator_v2 import BatchNarrator
from .core.service_v2 import TextWorldService
from .core.webapp import WebPanel

PLUGIN_NAME = "astrbot_plugin_text_world"
PLUGIN_VERSION = "0.3.3"
PLUGIN_REPO = "https://github.com/taolicx/astrbot_plugin_text_world"

MAP_IMAGE_FILES: tuple[str, ...] = (
    "academy_city_overview_annotated.png",
    "academy_city_district7_annotated.png",
    "academy_city_route_map.png",
)
MAP_IMAGE_INTRO = (
    "\u3010\u5b66\u56ed\u90fd\u5e02\u5730\u56fe\u3011\n"
    "\u5df2\u53d1\u9001\u56fe\u7247\u7248\u5730\u56fe\uff1a"
    "\u603b\u89c8\u3001\u7b2c\u4e03\u5b66\u533a\u7ec6\u8282\u3001\u8def\u7ebf\u56fe\u3002"
)
MAP_PRIVATE_AMBIGUOUS_TEXT = (
    "\u68c0\u6d4b\u5230\u4f60\u5728\u591a\u4e2a\u7fa4\u4e16\u754c\u90fd\u6709"
    "\u89d2\u8272\uff0c\u79c1\u804a\u91cc\u65e0\u6cd5\u5224\u65ad\u8981\u67e5\u770b"
    "\u54ea\u4e00\u4e2a\u3002"
)
MAP_PRIVATE_NO_WORLD_TEXT = "\u6ca1\u6709\u627e\u5230\u5df2\u7ed1\u5b9a\u7684\u7fa4\u4e16\u754c\u3002"

COMMAND_ALIASES: dict[str, tuple[str, ...]] = {
    "help": ("世界帮助", "文游帮助", "世界菜单"),
    "template": ("角色卡模板", "角色模板", "创建格式"),
    "open": ("世界开启", "开启世界", "文游开启"),
    "create": ("创建角色", "角色创建", "创建人物"),
    "action": ("行动", "文游行动", "提交行动"),
    "status": ("状态", "我的状态", "状态栏"),
    "map": ("地图", "世界地图"),
    "pending": ("待结算", "本轮行动", "行动列表"),
    "checkin": ("签到", "每日签到"),
    "manual_settle": ("世界结算", "文游结算", "立即结算"),
    "manual_event": ("世界事件", "文游事件", "触发事件"),
    "web": ("世界后台", "文游后台"),
}

GROUP_TEXT_COMMANDS = {
    "help",
    "template",
    "open",
    "create",
    "action",
    "status",
    "map",
    "pending",
    "checkin",
    "manual_settle",
    "manual_event",
    "web",
}

PAYLOAD_COMMANDS = {"create", "action", "manual_event"}


def help_text() -> str:
    return "\n".join(
        [
            "【学园都市文游】",
            "世界开启：在当前群登记世界",
            "角色卡模板：查看完整创建格式",
            "创建角色 游戏名 | 身份 | 阵营 | 能力 | 能力等级：提交角色卡，需管理员审核",
            "创建角色 我叫星野遥，是第七学区某高中学生，能力是微弱电磁感应：也支持自然语言提交",
            "行动 内容：提交本小时行动",
            "状态：查看自己的状态栏",
            "地图：查看当前位置和可前往地点",
            "待结算：查看本轮提交数量",
            "签到：每日获得学都币",
            "绑定文游私聊：私聊 bot 后绑定个人结果和早八状态栏",
            "世界开启后：群内普通聊天会被静默拦截，只回复文游指令",
            "管理员：世界结算 / 世界事件 / 世界后台",
        ]
    )


@register(
    PLUGIN_NAME,
    "codex",
    "学园都市小时制群文游系统：群行动、统一结算、私聊结果、前端后台、角色审核、事件预设、背包商店。",
    PLUGIN_VERSION,
    PLUGIN_REPO,
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
        await to_thread(self.db.init, self.cfg.admin_username, self.cfg.admin_password)
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

    @filter.command("角色卡模板", alias={"角色模板", "创建格式"})
    async def character_template(self, event: AstrMessageEvent):
        yield event.plain_result(CHARACTER_CARD_TEMPLATE).stop_event()

    @filter.command("世界开启", alias={"开启世界", "文游开启"})
    async def open_world(self, event: AstrMessageEvent):
        yield event.plain_result(await self._handle_open_world(event)).stop_event()

    @filter.command("创建角色", alias={"角色创建", "创建人物"})
    async def create_character(self, event: AstrMessageEvent):
        yield event.plain_result(await self._handle_create_character(event)).stop_event()

    @filter.command("行动", alias={"文游行动", "提交行动"})
    async def submit_action(self, event: AstrMessageEvent):
        yield event.plain_result(await self._handle_submit_action(event)).stop_event()

    @filter.command("状态", alias={"我的状态", "状态栏"})
    async def status(self, event: AstrMessageEvent):
        yield event.plain_result(await self._handle_status(event)).stop_event()

    @filter.command("地图", alias={"世界地图"})
    async def map_cmd(self, event: AstrMessageEvent):
        result = await self._handle_map_images(event)
        if result:
            yield result.stop_event()
        else:
            yield event.plain_result(await self._handle_map(event)).stop_event()

    @filter.command("待结算", alias={"本轮行动", "行动列表"})
    async def pending(self, event: AstrMessageEvent):
        yield event.plain_result(await self._handle_pending(event)).stop_event()

    @filter.command("签到", alias={"每日签到"})
    async def checkin(self, event: AstrMessageEvent):
        yield event.plain_result(await self._handle_checkin(event)).stop_event()

    @filter.event_message_type(filter.EventMessageType.PRIVATE_MESSAGE)
    @filter.command("绑定文游私聊", alias={"绑定世界私聊", "文游私聊绑定"})
    async def bind_private(self, event: AstrMessageEvent):
        count = await to_thread(self.service.bind_private, self._sender_id(event), self._origin(event))
        if count <= 0:
            yield event.plain_result("还没有找到你的角色卡，请先在群里提交或让管理员绑定 QQ 号。").stop_event()
            return
        yield event.plain_result(f"已绑定文游私聊，关联角色数：{count}。").stop_event()

    @filter.permission_type(filter.PermissionType.ADMIN)
    @filter.command("世界结算", alias={"文游结算", "立即结算"})
    async def manual_settle(self, event: AstrMessageEvent):
        yield event.plain_result(await self._handle_manual_settle(event)).stop_event()

    @filter.permission_type(filter.PermissionType.ADMIN)
    @filter.command("世界事件", alias={"文游事件", "触发事件"})
    async def manual_event(self, event: AstrMessageEvent):
        yield event.plain_result(await self._handle_manual_event(event)).stop_event()

    @filter.permission_type(filter.PermissionType.ADMIN)
    @filter.command("世界后台", alias={"文游后台"})
    async def web_url(self, event: AstrMessageEvent):
        yield event.plain_result(
            f"文游后台：http://{self.cfg.web_host}:{self.cfg.web_port}\n默认管理员账号请看插件配置。"
        ).stop_event()

    @filter.event_message_type(filter.EventMessageType.GROUP_MESSAGE, priority=50)
    async def world_group_listener(self, event: AstrMessageEvent):
        if not self.cfg.enable_world_chat_silence:
            return
        group_id = self._group_id(event)
        if not group_id:
            return
        command = self._parse_text_world_command(event)
        world_enabled = await to_thread(self.service.world_is_enabled, group_id)
        if not world_enabled and not command:
            return

        event.should_call_llm(False)
        if not command:
            event.stop_event()
            return

        if command["key"] == "map":
            result = await self._handle_map_images(event)
            if result:
                yield result.stop_event()
            else:
                yield event.plain_result(await self._handle_map(event)).stop_event()
            return

        msg = await self._handle_group_text_command(event, command["key"])
        if msg:
            yield event.plain_result(msg).stop_event()
        else:
            event.stop_event()

    async def _handle_group_text_command(self, event: AstrMessageEvent, key: str) -> str:
        if key == "help":
            return help_text()
        if key == "template":
            return CHARACTER_CARD_TEMPLATE
        if key == "open":
            return await self._handle_open_world(event)
        if key == "create":
            return await self._handle_create_character(event)
        if key == "action":
            return await self._handle_submit_action(event)
        if key == "status":
            return await self._handle_status(event)
        if key == "map":
            return await self._handle_map(event)
        if key == "pending":
            return await self._handle_pending(event)
        if key == "checkin":
            return await self._handle_checkin(event)
        if key == "manual_settle":
            if not self._is_admin(event):
                return "权限不足，只有管理员可以手动结算。"
            return await self._handle_manual_settle(event)
        if key == "manual_event":
            if not self._is_admin(event):
                return "权限不足，只有管理员可以手动触发事件。"
            return await self._handle_manual_event(event)
        if key == "web":
            if not self._is_admin(event):
                return "权限不足，只有管理员可以查看后台入口。"
            return f"文游后台：http://{self.cfg.web_host}:{self.cfg.web_port}\n默认管理员账号请看插件配置。"
        return ""

    async def _bound_group_id_for_private(self, event: AstrMessageEvent) -> str:
        if not self._is_private_chat(event):
            return ""
        binding = await to_thread(
            self.service.private_world_for_qq,
            self._sender_id(event),
            self._origin(event),
        )
        if not binding:
            return ""
        if binding.get("ambiguous"):
            return "__ambiguous__"
        return str(binding.get("group_id") or "")

    async def _command_group_id(
        self,
        event: AstrMessageEvent,
        *,
        allow_private_binding: bool = False,
    ) -> str:
        group_id = self._group_id(event)
        if group_id:
            return group_id
        if allow_private_binding:
            return await self._bound_group_id_for_private(event)
        return ""

    def _private_binding_hint(self) -> str:
        return "请先在私聊发送：绑定文游私聊。若你在多个群都有角色，请到对应群内使用该指令。"

    async def _handle_open_world(self, event: AstrMessageEvent) -> str:
        group_id = self._group_id(event)
        if not group_id:
            return "请在群聊中使用。"
        self._last_event_by_group[group_id] = event
        world = await to_thread(self.service.ensure_world, group_id, self._origin(event))
        return f"学园都市文字世界已开启。当前第 {world['current_round']} 轮。\n后台：http://{self.cfg.web_host}:{self.cfg.web_port}"

    async def _handle_create_character(self, event: AstrMessageEvent) -> str:
        group_id = self._group_id(event)
        if not group_id:
            return "请在群里提交角色卡。"
        payload = self._command_payload(event, COMMAND_ALIASES["create"])
        if not payload:
            return CHARACTER_CARD_TEMPLATE
        card_cheat = await to_thread(self.service.character_card_cheat_reason, payload)
        if card_cheat:
            return card_cheat

        provider_id = await self._provider_id(event)
        normalized = await self._parse_character_payload(payload, self._sender_id(event), provider_id)
        ok, msg = await to_thread(
            self.service.create_character_request,
            group_id,
            self._origin(event),
            self._sender_id(event),
            normalized["game_name"],
            normalized["identity"],
            faction=normalized["faction"],
            ability=normalized["ability"],
            power_level=normalized["power_level"],
        )
        if normalized.get("_source") == "natural":
            card_text = "\n".join(
                [
                    "已按自然语言整理角色卡：",
                    f"游戏名：{normalized['game_name']}",
                    f"身份：{normalized['identity']}",
                    f"阵营：{normalized['faction']}",
                    f"能力：{normalized['ability']}",
                    f"能力等级：{normalized['power_level']}",
                    msg,
                ]
            )
            return card_text
        return msg

    async def _parse_character_payload(self, payload: str, sender_id: str, provider_id: str) -> dict[str, str]:
        parts = [part.strip() for part in payload.replace("｜", "|").split("|", 4)]
        parts = [part for part in parts if part]
        if len(parts) >= 2:
            return {
                "game_name": parts[0],
                "identity": parts[1],
                "faction": parts[2] if len(parts) >= 3 else "",
                "ability": parts[3] if len(parts) >= 4 else "",
                "power_level": parts[4] if len(parts) >= 5 else "Level 0",
                "_source": "structured",
            }
        if not self.cfg.enable_natural_character_card:
            return {
                "game_name": "",
                "identity": "",
                "faction": "",
                "ability": "",
                "power_level": "Level 0",
                "_source": "structured",
            }
        normalized = await self.narrator.normalize_character_card(payload, sender_id, provider_id)
        normalized["_source"] = "natural"
        return normalized

    async def _handle_submit_action(self, event: AstrMessageEvent) -> str:
        group_id = self._group_id(event)
        if not group_id:
            return "行动需要在群里提交。"
        self._last_event_by_group[group_id] = event
        text = self._command_payload(event, COMMAND_ALIASES["action"])
        ok, msg = await to_thread(
            self.service.submit_action,
            group_id,
            self._origin(event),
            self._sender_id(event),
            text,
        )
        return msg

    async def _handle_status(self, event: AstrMessageEvent) -> str:
        group_id = await self._command_group_id(event, allow_private_binding=True)
        if group_id == "__ambiguous__":
            return "检测到你在多个群世界都有角色，私聊里无法判断要查看哪一个。" + self._private_binding_hint()
        if not group_id:
            return "没有找到已绑定的群世界。" + self._private_binding_hint()
        return await to_thread(self.service.get_status_by_qq, group_id, self._sender_id(event))

    async def _handle_map(self, event: AstrMessageEvent) -> str:
        group_id = await self._command_group_id(event, allow_private_binding=True)
        if group_id == "__ambiguous__":
            return "检测到你在多个群世界都有角色，私聊里无法判断要查看哪一个。" + self._private_binding_hint()
        if not group_id:
            return "没有找到已绑定的群世界。" + self._private_binding_hint()
        return await to_thread(self.service.map_text, group_id, self._sender_id(event))

    async def _handle_map_images(self, event: AstrMessageEvent):
        group_id = await self._command_group_id(event, allow_private_binding=True)
        if group_id == "__ambiguous__":
            return event.plain_result(MAP_PRIVATE_AMBIGUOUS_TEXT + self._private_binding_hint())
        if not group_id:
            return event.plain_result(MAP_PRIVATE_NO_WORLD_TEXT + self._private_binding_hint())

        map_dir = Path(__file__).resolve().parent / "assets" / "maps"
        image_paths = [map_dir / name for name in MAP_IMAGE_FILES]
        missing = [path for path in image_paths if not path.is_file()]
        if missing:
            logger.warning(
                "[TextWorld] map image assets missing: "
                + ", ".join(str(path) for path in missing)
            )
            return None

        chain = [Plain(MAP_IMAGE_INTRO + "\n")]
        chain.extend(Image.fromFileSystem(str(path)) for path in image_paths)
        return event.chain_result(chain)

    async def _handle_pending(self, event: AstrMessageEvent) -> str:
        group_id = await self._command_group_id(event, allow_private_binding=True)
        if group_id == "__ambiguous__":
            return "检测到你在多个群世界都有角色，私聊里无法判断要查看哪一个。" + self._private_binding_hint()
        if not group_id:
            return "没有找到已绑定的群世界。" + self._private_binding_hint()
        return await to_thread(self.service.pending_text, group_id)

    async def _handle_checkin(self, event: AstrMessageEvent) -> str:
        group_id = await self._command_group_id(event, allow_private_binding=True)
        if group_id == "__ambiguous__":
            return "检测到你在多个群世界都有角色，私聊里无法判断要签到哪一个。" + self._private_binding_hint()
        if not group_id:
            return "没有找到已绑定的群世界。" + self._private_binding_hint()
        ok, msg = await to_thread(self.service.checkin, group_id, self._sender_id(event))
        return msg

    async def _handle_manual_settle(self, event: AstrMessageEvent) -> str:
        group_id = self._group_id(event)
        if not group_id:
            return "请在要结算的群里使用。"
        self._last_event_by_group[group_id] = event
        return await self._settle_group(group_id, event, force_event=False)

    async def _handle_manual_event(self, event: AstrMessageEvent) -> str:
        group_id = self._group_id(event)
        if not group_id:
            return "请在要触发事件的群里使用。"
        self._last_event_by_group[group_id] = event
        return await self._settle_group(group_id, event, force_event=True)

    async def _scheduler_loop(self):
        while True:
            try:
                due = await to_thread(self.service.due_worlds)
                for world in due:
                    await self._settle_group(world["group_id"], self._last_event_by_group.get(world["group_id"]))
                daily_due = await to_thread(self.service.due_daily_worlds)
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
            result = await to_thread(self.service.settle_round, group_id, force_event)
            provider_id = await self._provider_id(event) if event else ""
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
        statuses = await to_thread(self.service.daily_statuses, world["group_id"])
        sent_count = 0
        for qq_id, text in statuses.items():
            if await self._send_private_by_qq(world["group_id"], qq_id, "【早安状态栏】\n" + text, None):
                sent_count += 1
        if sent_count or not statuses:
            await to_thread(self.service.mark_daily_sent, world["group_id"])
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
        row = await to_thread(self.db.fetch_one, "SELECT group_origin FROM worlds WHERE group_id=?", (group_id,))
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
        row = await to_thread(
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
            return self.cfg.provider_for("main")
        try:
            value = await self.context.get_current_chat_provider_id(umo=event.unified_msg_origin)
            if isinstance(value, str) and value:
                return value
        except Exception:
            pass
        return self.cfg.provider_for("main")

    def _group_id(self, event: AstrMessageEvent) -> str:
        if self._is_private_chat(event):
            return ""
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

    def _is_private_chat(self, event: AstrMessageEvent) -> bool:
        try:
            if event.is_private_chat():
                return True
        except Exception:
            pass
        message_obj = getattr(event, "message_obj", None)
        message_type = getattr(message_obj, "type", None)
        value = getattr(message_type, "value", message_type)
        return str(value or "").lower() in {"friendmessage", "private", "private_message", "friend_message"}

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

    def _command_payload(self, event: AstrMessageEvent, names: list[str] | tuple[str, ...]) -> str:
        text = (getattr(event, "message_str", "") or "").strip()
        for name in names:
            if text == name:
                return ""
            if text.startswith(name):
                return text[len(name):].strip()
        return text

    def _parse_text_world_command(self, event: AstrMessageEvent) -> dict[str, str]:
        text = (getattr(event, "message_str", "") or "").strip()
        if not text:
            return {}
        text = self._strip_wake_prefixes(text)
        candidates = [
            (key, name)
            for key in GROUP_TEXT_COMMANDS
            for name in COMMAND_ALIASES[key]
        ]
        candidates.sort(key=lambda item: len(item[1]), reverse=True)
        for key, name in candidates:
            if text == name:
                return {"key": key, "name": name, "payload": text[len(name):].strip()}
            if key in PAYLOAD_COMMANDS and text.startswith(name):
                return {"key": key, "name": name, "payload": text[len(name):].strip()}
        return {}

    def _strip_wake_prefixes(self, text: str) -> str:
        text = str(text or "").strip()
        try:
            cfg = self.context.get_config()
            prefixes = cfg.get("wake_prefix", []) if isinstance(cfg, dict) else []
        except Exception:
            prefixes = []
        for prefix in prefixes or []:
            prefix = str(prefix or "").strip()
            if prefix and text.startswith(prefix):
                return text[len(prefix):].strip()
        return text

    def _is_admin(self, event: AstrMessageEvent) -> bool:
        try:
            if event.is_admin():
                return True
        except Exception:
            pass
        try:
            cfg = self.context.get_config(umo=event.unified_msg_origin)
            admins = cfg.get("admins_id", []) if isinstance(cfg, dict) else []
        except Exception:
            admins = []
        sender_id = self._sender_id(event)
        return any(str(item) == sender_id for item in admins)
