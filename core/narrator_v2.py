from __future__ import annotations

import json
import re
from typing import Any

from .config import TextWorldConfig

try:
    from astrbot.api import logger
except Exception:
    import logging

    logger = logging.getLogger("astrbot_plugin_text_world.narrator")


class BatchNarrator:
    def __init__(self, context: Any, config: TextWorldConfig):
        self.context = context
        self.config = config

    async def narrate_round(self, result: dict[str, Any], provider_id: str = "") -> dict[str, Any]:
        if not self.config.enable_llm:
            return result
        provider_id = self.config.provider_for("story", provider_id)
        if not provider_id:
            return result
        payload = {
            "task": "把程序已经结算好的群文游结果润色成可发送文本。必须一次性输出 JSON，程序会拆开发群公告和私聊。",
            "rules": [
                "不得更改程序给出的地点、状态、货币、背包、相遇名单。",
                "不得让角色瞬移，不得新增未结算的奖励或伤害。",
                "public_summary 只写群内公开信息，不泄露个人私密行动。",
                "player_results 的 key 必须保持 QQ 号不变。",
                "文字风格是学院都市群文游旁白，克制、有画面感，不自称 AI。",
            ],
            "input": result,
            "output_schema": {
                "public_summary": "群公告文本",
                "player_results": {"QQ号": "该玩家私聊文本"},
            },
        }
        try:
            resp = await self.context.llm_generate(
                chat_provider_id=provider_id,
                prompt=json.dumps(payload, ensure_ascii=False),
                system_prompt=self.config.system_prompt(),
            )
            text = (getattr(resp, "completion_text", None) or str(resp)).strip()
            parsed = self._parse_json(text)
            public_summary = self._clip(str(parsed.get("public_summary") or result.get("public_summary") or "").strip(), 1800)
            player_results = parsed.get("player_results") or {}
            if not isinstance(player_results, dict):
                player_results = {}
            merged = dict(result)
            merged["public_summary"] = public_summary or result.get("public_summary", "")
            fallback_private = result.get("private_results") or {}
            if self.config.enable_ai_private_result:
                merged["private_results"] = {
                    str(qq): self._clip(str(player_results.get(str(qq)) or fallback).strip(), 1400)
                    for qq, fallback in fallback_private.items()
                }
            else:
                merged["private_results"] = fallback_private
            return merged
        except Exception as exc:
            logger.warning(f"[TextWorld] batch narration fallback: {exc}")
            return result

    async def normalize_character_card(
        self,
        raw_text: str,
        sender_id: str = "",
        provider_id: str = "",
    ) -> dict[str, str]:
        raw_text = self._clip(str(raw_text or "").strip(), 2000)
        sender_id = str(sender_id or "").strip()
        if not raw_text:
            return self._fallback_character_card("", sender_id)

        provider_id = self.config.provider_for("fast", provider_id)
        if self.config.enable_natural_character_card and provider_id:
            payload = {
                "task": "把玩家的自然语言角色设定整理成标准角色卡，只输出 JSON。",
                "rules": [
                    "只输出 JSON，不要输出解释、markdown 或多余文本。",
                    "保留玩家原意，不要擅自添加不存在的身份、阵营或能力。",
                    "game_name 是游戏名或昵称，缺失时用 玩家+QQ后4位 兜底。",
                    "identity 是身份简介，尽量压缩成一句话。",
                    "faction 是阵营归类，优先使用世界内常见阵营名。",
                    "ability 是能力描述，尽量保留自然语言里的核心能力。",
                    "power_level 只能是 Level 0 到 Level 5。",
                    "如果原文暗示高阶能力，最多整理到 Level 5，不要输出更高等级。",
                ],
                "output_schema": {
                    "game_name": "游戏名",
                    "identity": "身份",
                    "faction": "阵营",
                    "ability": "能力",
                    "power_level": "Level 0",
                },
                "input": {
                    "sender_id": sender_id,
                    "raw_text": raw_text,
                },
            }
            try:
                resp = await self.context.llm_generate(
                    chat_provider_id=provider_id,
                    prompt=json.dumps(payload, ensure_ascii=False),
                    system_prompt=self._character_card_prompt(),
                )
                text = (getattr(resp, "completion_text", None) or str(resp)).strip()
                parsed = self._parse_json(text)
                normalized = self._normalize_character_card_dict(parsed, raw_text, sender_id)
                if normalized:
                    return normalized
            except Exception as exc:
                logger.warning(f"[TextWorld] character card normalize fallback: {exc}")
        return self._fallback_character_card(raw_text, sender_id)

    def _parse_json(self, text: str) -> dict[str, Any]:
        text = text.strip()
        fence = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", text, re.S | re.I)
        if fence:
            text = fence.group(1).strip()
        try:
            data = json.loads(text)
            return data if isinstance(data, dict) else {}
        except json.JSONDecodeError:
            pass
        match = re.search(r"\{.*\}", text, re.S)
        if not match:
            return {}
        data = json.loads(match.group(0))
        return data if isinstance(data, dict) else {}

    def _clip(self, text: str, limit: int) -> str:
        if len(text) <= limit:
            return text
        return text[:limit].rstrip() + "\n……"

    def _character_card_prompt(self) -> str:
        return "\n".join(
            [
                "你是学院都市文字世界的角色卡整理器。",
                "你只负责把自然语言整理成标准角色卡，不负责审核。",
                "必须只输出 JSON，不要输出解释、前缀、后缀或 markdown。",
                "字段要求：",
                "- game_name：游戏名或昵称；如果没有明确名字，使用 玩家+QQ后4位。",
                "- identity：身份简介，尽量一句话。",
                "- faction：阵营，使用世界内常见阵营名。",
                "- ability：能力描述，保留核心设定，不要乱加新能力。",
                "- power_level：只能输出 Level 0 / Level 1 / Level 2 / Level 3 / Level 4 / Level 5。",
                "如果原文表达模糊，优先保守整理，保持可审核。",
            ]
        )

    def _normalize_character_card_dict(self, data: dict[str, Any], raw_text: str, sender_id: str) -> dict[str, str]:
        if not isinstance(data, dict):
            return {}
        normalized = {
            "game_name": self._clip(self._text_value(data.get("game_name") or data.get("name") or data.get("game") or ""), 32),
            "identity": self._clip(self._text_value(data.get("identity") or data.get("role") or data.get("description") or ""), 240),
            "faction": self._clip(self._text_value(data.get("faction") or data.get("camp") or data.get("group") or ""), 80),
            "ability": self._clip(self._text_value(data.get("ability") or data.get("power") or data.get("skill") or ""), 240),
            "power_level": self._normalize_power_level(data.get("power_level") or data.get("level") or ""),
        }
        if not normalized["game_name"]:
            normalized["game_name"] = self._guess_game_name(raw_text, sender_id)
        if not normalized["identity"]:
            normalized["identity"] = self._guess_identity(raw_text)
        if not normalized["faction"]:
            normalized["faction"] = self._guess_faction(raw_text)
        if not normalized["ability"]:
            normalized["ability"] = self._guess_ability(raw_text)
        normalized["power_level"] = self._normalize_power_level(normalized["power_level"] or raw_text)
        return normalized

    def _fallback_character_card(self, raw_text: str, sender_id: str) -> dict[str, str]:
        return {
            "game_name": self._guess_game_name(raw_text, sender_id),
            "identity": self._guess_identity(raw_text),
            "faction": self._guess_faction(raw_text),
            "ability": self._guess_ability(raw_text),
            "power_level": self._normalize_power_level(raw_text),
        }

    def _text_value(self, value: Any) -> str:
        return re.sub(r"\s+", " ", str(value or "")).strip()

    def _guess_game_name(self, raw_text: str, sender_id: str) -> str:
        text = self._text_value(raw_text)
        patterns = [
            r"(?:我叫|名字叫|名叫|昵称是|游戏名是|游戏名叫|角色名是|代号是|ID是|id是)\s*([^\s，。；;|｜/]{2,16})",
            r"^(?:我是|我)\s*([^\s，。；;|｜/]{2,16})",
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                name = self._clip(match.group(1), 32)
                if name:
                    return name
        tail = self._sender_tail(sender_id)
        return f"玩家{tail}"

    def _guess_identity(self, raw_text: str) -> str:
        text = self._text_value(raw_text)
        patterns = [
            r"我叫[^\s，。；;|｜/]{2,16}\s*[，,]\s*是([^。；;\n]{2,120}?)(?:，能力|,能力|，擅长|,擅长|。|；|;|$)",
            r"(?:身份|职业|背景|设定|简介|我是|身为|来自)\s*[:：]?\s*([^。；;\n]{2,120})",
            r"(?:一名|一位|一个)\s*([^。；;\n]{2,120})",
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                identity = self._clip(match.group(1), 240)
                if identity:
                    return identity
        if text:
            return self._clip(text.split("\n", 1)[0], 120)
        return "身份未说明"

    def _guess_faction(self, raw_text: str) -> str:
        text = self._text_value(raw_text).lower()
        mappings = [
            (("风纪委员", "风纪"), "风纪委员"),
            (("警备员", "警备"), "警备员"),
            (("暗部",), "暗部"),
            (("研究所", "研究员", "实验室", "学园都市研究"), "研究机构"),
            (("留学生",), "留学生"),
            (("skill-out", "skill out", "无能力者", "skillout"), "Skill-Out"),
            (("学生", "高中生", "中学生", "初中生", "大学生"), "普通学生"),
            (("无阵营", "中立", "独行", "单独行动"), "无阵营"),
        ]
        for keywords, faction in mappings:
            if any(keyword in text for keyword in keywords):
                return faction
        return "普通学生"

    def _guess_ability(self, raw_text: str) -> str:
        text = self._text_value(raw_text)
        patterns = [
            r"(?:能力是|技能是)\s*([^。；;\n]{2,120})",
            r"(?:能力|异能|特长|擅长|可以|能|会|拥有)\s*(?:是|为|:|：)?\s*([^。；;\n]{2,120})",
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                ability = self._clip(self._clean_ability(match.group(1)), 240)
                if ability:
                    return ability
        if text:
            return self._clip(self._clean_ability(text.split("，", 1)[0].split(",", 1)[0]), 120)
        return "未明确能力"

    def _clean_ability(self, text: str) -> str:
        text = self._text_value(text)
        text = re.sub(r"[\s，,；;。]*(?:level|lv\.?)\s*[0-9]+[\s。；;，,]*$", "", text, flags=re.I)
        text = re.sub(r"[\s，,；;。]*[0-9]+\s*级[\s。；;，,]*$", "", text)
        return text.strip()

    def _normalize_power_level(self, raw_value: Any) -> str:
        text = self._text_value(raw_value).lower()
        if not text:
            return "Level 0"
        match = re.search(r"(?:level|lv\.?)\s*([0-9]+)", text, re.I)
        if not match:
            match = re.search(r"([0-9]+)\s*级", text)
        if match:
            level = max(0, min(5, int(match.group(1))))
            return f"Level {level}"
        if any(keyword in text for keyword in ("绝对能力者", "level 5", "lv5", "lv 5", "5级", "五级")):
            return "Level 5"
        if any(keyword in text for keyword in ("level 4", "lv4", "lv 4", "4级", "四级")):
            return "Level 4"
        if any(keyword in text for keyword in ("无能力", "普通人", "level 0", "lv0", "lv 0", "0级", "零级")):
            return "Level 0"
        return "Level 0"

    def _sender_tail(self, sender_id: str) -> str:
        sender_id = re.sub(r"\s+", "", str(sender_id or ""))
        if not sender_id:
            return "0000"
        digits = re.sub(r"\D+", "", sender_id)
        if digits:
            return digits[-4:].rjust(4, "0")
        return sender_id[-4:].rjust(4, "0")
