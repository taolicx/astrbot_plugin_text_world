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
        provider_id = provider_id or self.config.default_provider_id
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
