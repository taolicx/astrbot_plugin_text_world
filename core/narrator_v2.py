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
                "不得让玩家随意成为原作主角、Level 5、暗部核心或统括理事会高层。",
                "科学侧事件优先；魔法侧只能作为少量传闻、访客或异常线索，不能突然改写主线。",
                "原作人物出现时保持克制，不能替玩家完成行动目标。",
                "暗部、妹妹们、幻想御手、滞空回线、树状图设计者、魔法侧等核心线索只能写成公开传闻、异常痕迹或调查碎片，不能直接给出终局真相。",
                "学舍之园、常盘台中学、研究所、没有窗户的大楼等地点有权限边界；程序没有允许时只能写外围、公开区或被拦下。",
                "public_summary 只写群内公开信息，不泄露个人私密行动。",
                "player_results 的 key 必须保持 QQ 号不变。",
                "文字风格是《某魔法的禁书目录》学园都市同人群文游旁白，克制、有画面感，不自称 AI。",
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
                    "faction 是阵营归类，优先使用普通学生、风纪委员 Judgment、警备员 Anti-Skill、研究机构、Skill-Out、暗部边缘、留学生、魔法侧访客、无阵营。",
                    "ability 是能力描述，尽量保留自然语言里的核心能力，并写出限制或代价。",
                    "power_level 只能是 Level 0 到 Level 5；普通玩家没有明确写等级时默认整理为 Level 3。",
                    "outfit 是穿衣着装，提取玩家写到的服装、制服、外套、随身显眼穿搭；没有就空字符串。",
                    "body_profile 是简易身材数据，提取身高、体型、发型等低敏外观；没有就空字符串，不要补编。",
                    "如果原文暗示高阶能力，最多整理到 Level 4；只有明确写 Level 5 才可保留 Level 5，不能输出更高等级。",
                    "不得把玩家整理成上条当麻、御坂美琴、一方通行等原作角色本人。",
                    "如果玩家声称拥有幻想杀手、心理掌握、矢量操作、超电磁炮本人级能力，保留为相似但弱化的原创能力并写明限制。",
                ],
                "output_schema": {
                    "game_name": "游戏名",
                    "identity": "身份",
                    "faction": "阵营",
                    "ability": "能力",
                    "power_level": "Level 3",
                    "outfit": "穿衣着装",
                    "body_profile": "简易身材数据",
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
                "世界观来自《某魔法的禁书目录》学园都市，默认是科学侧日常与事件。",
                "字段要求：",
                "- game_name：游戏名或昵称；如果没有明确名字，使用 玩家+QQ后4位。",
                "- identity：身份简介，尽量一句话。",
                "- faction：阵营，优先使用普通学生、风纪委员 Judgment、警备员 Anti-Skill、研究机构、Skill-Out、暗部边缘、留学生、魔法侧访客、无阵营。",
                "- ability：能力描述，保留核心设定，不要乱加新能力，尽量补一句限制或代价。",
                "- power_level：只能输出 Level 0 / Level 1 / Level 2 / Level 3 / Level 4 / Level 5；普通玩家未写等级时默认 Level 3。",
                "- outfit：穿衣着装，只提取玩家明确写过的服装信息，缺失时输出空字符串。",
                "- body_profile：简易身材数据，只提取身高、体型、发型等低敏外观，缺失时输出空字符串。",
                "如果原文表达模糊，优先保守整理，保持可审核。",
                "不得把玩家整理成原作角色本人、绝对能力者、魔神、统括理事长或暗部核心首领。",
                "如果玩家使用原作角色招牌能力名，整理为原创弱化变体，例如低强度电磁感知、局部矢量感知、短距念动辅助等，并保留审核余地。",
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
            "outfit": self._clip(self._text_value(data.get("outfit") or data.get("clothing") or data.get("wearing") or ""), 120),
            "body_profile": self._clip(self._text_value(data.get("body_profile") or data.get("body") or data.get("appearance") or ""), 120),
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
            "outfit": self._guess_outfit(raw_text),
            "body_profile": self._guess_body_profile(raw_text),
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
            (("风纪委员", "风纪", "judgment"), "风纪委员 Judgment"),
            (("警备员", "警备", "anti-skill", "antiskill"), "警备员 Anti-Skill"),
            (("item",), "暗部 ITEM"),
            (("group",), "暗部 GROUP"),
            (("school",), "暗部 SCHOOL"),
            (("暗部",), "暗部边缘"),
            (("研究所", "研究员", "实验室", "学园都市研究"), "研究机构"),
            (("魔法侧", "魔法师", "必要之恶教会", "英国清教", "罗马正教"), "魔法侧访客"),
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

    def _guess_outfit(self, raw_text: str) -> str:
        text = self._text_value(raw_text)
        patterns = [
            r"(?:穿着|穿|服装|着装|衣服|制服|外套)\s*(?:是|为|:|：)?\s*([^。；;\n]{2,80})",
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return self._clip(match.group(1), 120)
        return ""

    def _guess_body_profile(self, raw_text: str) -> str:
        text = self._text_value(raw_text)
        parts: list[str] = []
        height = re.search(r"([12]?[0-9]{2})\s*(?:cm|厘米|公分)", text, re.I)
        if height:
            parts.append(height.group(0))
        for keyword in ("偏瘦", "纤细", "普通体型", "结实", "高挑", "娇小", "短发", "长发", "黑发", "白发", "茶发"):
            if keyword in text and keyword not in parts:
                parts.append(keyword)
        return self._clip("，".join(parts), 120)

    def _normalize_power_level(self, raw_value: Any) -> str:
        text = self._text_value(raw_value).lower()
        if not text:
            return "Level 3"
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
        return "Level 3"

    def _sender_tail(self, sender_id: str) -> str:
        sender_id = re.sub(r"\s+", "", str(sender_id or ""))
        if not sender_id:
            return "0000"
        digits = re.sub(r"\D+", "", sender_id)
        if digits:
            return digits[-4:].rjust(4, "0")
        return sender_id[-4:].rjust(4, "0")
