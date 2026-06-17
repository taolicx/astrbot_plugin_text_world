from __future__ import annotations

import json
import random
import re
import sqlite3
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

from .config import TextWorldConfig
from .database import CN_TZ, TextWorldDB, cn_today, iso_after_minutes, parse_iso, utc_now, utc_now_iso
from .defaults import CHEAT_PATTERNS, EVENT_SEEDS


def clamp(value: int, low: int = 0, high: int = 100) -> int:
    return max(low, min(high, int(value)))


def dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def loads(raw: str, default: Any) -> Any:
    try:
        return json.loads(raw or "")
    except Exception:
        return default


def int_value(value: Any, default: int) -> int:
    if value is None or value == "":
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


WEEKDAY_CN = ("星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日")


class TextWorldService:
    def __init__(self, db: TextWorldDB, config: TextWorldConfig):
        self.db = db
        self.config = config

    def ensure_world(self, group_id: str, group_origin: str = "") -> dict[str, Any]:
        return self.db.ensure_world(
            group_id,
            group_origin,
            self.config.cycle_minutes,
            self.config.event_cycle_minutes,
        )

    def world_is_enabled(self, group_id: str) -> bool:
        group_id = str(group_id or "").strip()
        if not group_id:
            return False
        row = self.db.fetch_one("SELECT enabled FROM worlds WHERE group_id=?", (group_id,))
        return bool(row and int(row.get("enabled") or 0) == 1)

    def current_time_context(self) -> dict[str, str | int]:
        now = datetime.now(CN_TZ).replace(microsecond=0)
        hour = now.hour
        if 5 <= hour < 8:
            phase = "清晨"
        elif 8 <= hour < 12:
            phase = "上午"
        elif 12 <= hour < 14:
            phase = "午间"
        elif 14 <= hour < 18:
            phase = "下午"
        elif 18 <= hour < 22:
            phase = "夜间"
        else:
            phase = "深夜"
        weekday = WEEKDAY_CN[now.weekday()]
        return {
            "timezone": "Asia/Shanghai",
            "date": now.strftime("%Y-%m-%d"),
            "time": now.strftime("%H:%M:%S"),
            "weekday": weekday,
            "phase": phase,
            "hour": hour,
            "iso": now.isoformat(),
            "display": f"{now.strftime('%Y-%m-%d %H:%M:%S')} 北京时间（{weekday}，{phase}）",
            "rule": "世界时间与现实北京时间同步；剧情里的昼夜、营业、上课、宵禁和路上人流必须按该时间处理。",
        }

    def current_time_line(self) -> str:
        return str(self.current_time_context()["display"])

    def create_character_request(
        self,
        group_id: str,
        group_origin: str,
        qq_id: str,
        game_name: str,
        identity: str,
        *,
        faction: str = "",
        ability: str = "",
        power_level: str = "Level 3",
        gender: str = "",
        outfit: str = "",
        body_profile: str = "",
        approve: bool = False,
    ) -> tuple[bool, str]:
        qq_id = str(qq_id or "").strip()
        if not qq_id:
            return False, "无法识别你的 QQ 号，暂时不能创建角色。"
        self.ensure_world(group_id, group_origin)
        game_name = self.clean_name(game_name)
        identity = self.clean_text(identity, 240)
        faction = self.clean_text(faction, 80)
        ability = self.clean_text(ability, 240)
        power_level = self.clean_text(power_level, 20) or "Level 3"
        gender = self.clean_text(gender, 20)
        outfit = self.clean_text(outfit, 120)
        body_profile = self.clean_text(body_profile, 120)
        if not game_name or not identity:
            return False, "格式：创建角色 游戏名 | 身份 | 阵营 | 能力 | 能力等级"
        card_cheat = self.character_card_cheat_reason(
            " ".join([game_name, identity, faction, ability, power_level])
        )
        if card_cheat:
            return False, card_cheat
        now = utc_now_iso()
        status = "approved" if approve else "pending"

        def work(con: sqlite3.Connection) -> tuple[bool, str]:
            name_owner = con.execute(
                "SELECT qq_id FROM characters WHERE group_id=? AND game_name=?",
                (group_id, game_name),
            ).fetchone()
            if name_owner and str(name_owner["qq_id"]) != str(qq_id):
                return False, "这个游戏名已经被使用了，请换一个。"
            row = con.execute(
                "SELECT * FROM characters WHERE group_id=? AND qq_id=?",
                (group_id, qq_id),
            ).fetchone()
            try:
                self._validate_player_account_owner(con, game_name, qq_id, int(row["id"]) if row else None)
                user_id = self.db.ensure_player_user(
                    con,
                    game_name,
                    qq_id[-6:] or "123456",
                    int(row["user_id"]) if row and row["user_id"] else None,
                )
            except ValueError as exc:
                return False, str(exc)
            if row:
                con.execute(
                    """
                    UPDATE characters SET user_id=?,game_name=?,display_name=?,identity=?,faction=?,ability=?,power_level=?,gender=?,outfit=?,body_profile=?,audit_status=?,updated_at=?
                    WHERE id=?
                    """,
                    (user_id, game_name, game_name, identity, faction, ability, power_level, gender, outfit, body_profile, status, now, row["id"]),
                )
                return True, "角色卡已更新，等待管理员审核。" if not approve else "角色卡已更新并通过。"
            con.execute(
                """
                INSERT INTO characters(group_id,user_id,qq_id,game_name,display_name,identity,faction,ability,power_level,gender,outfit,body_profile,audit_status,location_key,hp,energy,water,satiety,mood,money,created_at,updated_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    group_id,
                    user_id,
                    qq_id,
                    game_name,
                    game_name,
                    identity,
                    faction,
                    ability,
                    power_level,
                    gender,
                    outfit,
                    body_profile,
                    status,
                    "school_gate",
                    100,
                    100,
                    80,
                    80,
                    70,
                    self.config.start_money,
                    now,
                    now,
                ),
            )
            return True, "角色卡已提交，等待管理员审核。" if not approve else "角色卡已创建并通过。"

        return self.db.run(work)

    def bind_private(self, qq_id: str, private_origin: str) -> int:
        qq_id = str(qq_id or "").strip()
        private_origin = str(private_origin or "").strip()
        if not qq_id or not private_origin:
            return 0

        def work(con: sqlite3.Connection) -> int:
            rows = con.execute(
                "SELECT id,audit_status FROM characters WHERE qq_id=? ORDER BY updated_at DESC, id DESC",
                (qq_id,),
            ).fetchall()
            if not rows:
                return 0
            approved_rows = [row for row in rows if str(row["audit_status"]) == "approved"]
            if len(approved_rows) == 1:
                target_id = int(approved_rows[0]["id"])
            elif len(approved_rows) > 1:
                return -1
            elif len(rows) == 1:
                target_id = int(rows[0]["id"])
            else:
                return -1
            con.execute(
                "UPDATE characters SET private_origin='', updated_at=? WHERE qq_id=?",
                (utc_now_iso(), qq_id),
            )
            cur = con.execute(
                "UPDATE characters SET private_origin=?, updated_at=? WHERE id=?",
                (private_origin, utc_now_iso(), target_id),
            )
            return int(cur.rowcount)

        return self.db.run(work)

    def submit_action(
        self, group_id: str, group_origin: str, qq_id: str, text: str
    ) -> tuple[bool, str]:
        qq_id = str(qq_id or "").strip()
        if not qq_id:
            return False, "无法识别你的 QQ 号，暂时不能提交行动。"
        world = self.ensure_world(group_id, group_origin)
        text = self.normalize_action(text)
        if not text:
            return False, "行动不能为空。"
        if len(text) > self.config.max_action_length:
            return False, f"行动太长了，每次行动最多 {self.config.max_action_length} 字。"
        cheat = self.cheat_reason(text)
        if cheat:
            return False, cheat

        def work(con: sqlite3.Connection) -> tuple[bool, str]:
            character = con.execute(
                "SELECT * FROM characters WHERE group_id=? AND qq_id=?",
                (group_id, qq_id),
            ).fetchone()
            if not character:
                return False, "你还没有角色卡。请先发送：角色卡模板，然后按格式提交。"
            if character["audit_status"] != "approved":
                return False, "你的角色卡还没有通过审核，暂时不能行动。"
            if int(character["hp"]) <= 0 and not (self._looks_like_self_heal(text) or self._looks_like_rest(text)):
                return False, "你的生命值过低，本轮只能休息或去医院治疗。"
            exists = con.execute(
                "SELECT id FROM actions WHERE group_id=? AND character_id=? AND round_no=?",
                (group_id, character["id"], world["current_round"]),
            ).fetchone()
            if exists:
                return False, "你本轮已经提交过行动了。每小时只能提交一次。"
            con.execute(
                """
                INSERT INTO actions(group_id,character_id,round_no,text,status,submitted_at)
                VALUES(?,?,?,?,?,?)
                """,
                (group_id, character["id"], world["current_round"], text, "pending", utc_now_iso()),
            )
            count = con.execute(
                "SELECT COUNT(*) FROM actions WHERE group_id=? AND round_no=? AND status='pending'",
                (group_id, world["current_round"]),
            ).fetchone()[0]
            return True, f"行动已记录，等待本轮统一结算。当前已有 {count} 人提交。"

        return self.db.run(work)

    def due_worlds(self) -> list[dict[str, Any]]:
        rows = self.db.fetch_all("SELECT * FROM worlds WHERE enabled=1")
        now = utc_now()
        return [row for row in rows if (parse_iso(row.get("next_tick_at")) or now + timedelta(days=1)) <= now]

    def due_daily_worlds(self) -> list[dict[str, Any]]:
        rows = self.db.fetch_all("SELECT * FROM worlds WHERE enabled=1")
        now_cn = datetime.now(timezone(timedelta(hours=8)))
        today = now_cn.strftime("%Y-%m-%d")
        if now_cn.hour < self.config.daily_status_hour:
            return []
        return [row for row in rows if row.get("last_daily_status_date") != today]

    def settle_round(self, group_id: str, force_event: bool = False) -> dict[str, Any]:
        def work(con: sqlite3.Connection) -> dict[str, Any]:
            world = con.execute("SELECT * FROM worlds WHERE group_id=?", (group_id,)).fetchone()
            if not world:
                raise RuntimeError("世界不存在")
            round_no = int(world["current_round"])
            time_context = self.current_time_context()
            npc_updates = self._move_npcs(con, group_id)
            active_event = self._consume_next_event(con, group_id)
            if not active_event and self._event_due(world):
                active_event = self._random_event(con, group_id)
            if force_event and not active_event:
                active_event = self._random_event(con, group_id)
            if active_event:
                self._apply_event_effect(con, group_id, active_event)
            actions = con.execute(
                """
                SELECT actions.*, characters.qq_id, characters.game_name, characters.location_key, characters.hp, characters.energy,
                       characters.water, characters.satiety, characters.mood, characters.money, characters.identity, characters.faction,
                       characters.ability, characters.power_level, characters.outfit, characters.body_profile,
                       characters.reputation, characters.physical_exp, characters.social_exp, characters.study_exp, characters.art_exp,
                       characters.task_state_json,
                       characters.ability_exp, characters.daily_development_date, characters.death_protection,
                       characters.traits_json
                FROM actions
                JOIN characters ON characters.id=actions.character_id
                WHERE actions.group_id=? AND actions.round_no=? AND actions.status='pending'
                ORDER BY actions.submitted_at ASC
                """,
                (group_id, round_no),
            ).fetchall()

            outcomes = []
            action_rows = [dict(row) for row in actions]
            pvp_index, passive_pvp_index = self._build_pvp_index(con, group_id, action_rows)
            for row in actions:
                outcomes.append(self._resolve_action(con, group_id, row, pvp_index.get(int(row["id"]), [])))
            active_actions_by_character = {int(row["character_id"]): row for row in action_rows}
            passive_pvp_index = {
                int(character_id): [
                    attack
                    for attack in attacks
                    if not self._passive_pvp_already_answered(active_actions_by_character.get(int(character_id)), attack)
                ]
                for character_id, attacks in passive_pvp_index.items()
            }
            passive_pvp_index = {character_id: attacks for character_id, attacks in passive_pvp_index.items() if attacks}
            passive_outcomes = self._resolve_passive_pvp_impacts(con, group_id, passive_pvp_index)
            passive_outcomes.extend(self._resolve_active_social_impacts(con, group_id, action_rows))

            self._apply_hourly_decay(con, group_id)
            roster = self._location_roster(con, group_id)
            private_results = {}
            outcome_by_character = {int(outcome["character_id"]): outcome for outcome in outcomes}
            for passive in passive_outcomes:
                existing = outcome_by_character.get(int(passive["character_id"]))
                if existing:
                    for key, value in passive.get("deltas", {}).items():
                        existing.setdefault("deltas", {})[key] = int(existing["deltas"].get(key, 0)) + int(value or 0)
                    existing.setdefault("warnings", []).extend(passive.get("warnings", []))
                    impacts = passive.get("passive_impacts") or [{"summary": passive.get("summary", "")}]
                    existing.setdefault("passive_impacts", []).extend(impact for impact in impacts if impact.get("summary"))
                else:
                    outcomes.append(passive)
                    outcome_by_character[int(passive["character_id"])] = passive
            public_summary = self._ensure_sendable_text(
                self._build_public_summary(round_no, outcomes, npc_updates, roster, active_event, time_context),
                f"【第 {round_no} 轮学园都市更新】\n世界时间：{time_context['display']}\n本轮结算已完成，但公共摘要文本为空，详情请查看个人结果。",
            )
            for outcome in outcomes:
                private_text = self._ensure_sendable_text(
                    self._build_private_result(con, group_id, round_no, outcome, time_context),
                    f"【第 {round_no} 轮个人结果】\n世界时间：{time_context['display']}\n本轮个人结果已记录，但文本生成异常，请联系管理员查看历史。",
                )
                private_results[str(outcome["qq_id"])] = private_text
                con.execute(
                    """
                    INSERT INTO history(group_id,round_no,visibility,character_id,kind,text,created_at)
                    VALUES(?,?,?,?,?,?,?)
                    """,
                    (group_id, round_no, "private", outcome["character_id"], "round_result", private_text, utc_now_iso()),
                )
                if outcome.get("action_id"):
                    con.execute(
                        "UPDATE actions SET status='resolved', result_text=?, warnings=?, resolved_at=? WHERE id=?",
                        (private_text, dumps(outcome.get("warnings", [])), utc_now_iso(), outcome["action_id"]),
                    )
            participant_qq_ids = self._approved_player_qq_ids(con, group_id)
            for qq_id in participant_qq_ids:
                private_results.setdefault(str(qq_id), "")
            con.execute(
                """
                INSERT INTO history(group_id,round_no,visibility,kind,text,created_at)
                VALUES(?,?,?,?,?,?)
                """,
                (group_id, round_no, "public", "round_public", public_summary, utc_now_iso()),
            )
            con.execute(
                """
                UPDATE worlds SET current_round=current_round+1,next_tick_at=?,next_event_at=CASE WHEN ? THEN ? ELSE next_event_at END,updated_at=?
                WHERE group_id=?
                """,
                (
                    iso_after_minutes(int(world["cycle_minutes"])),
                    1 if active_event else 0,
                    iso_after_minutes(int(world["event_cycle_minutes"])),
                    utc_now_iso(),
                    group_id,
                ),
            )
            return {
                "group_id": group_id,
                "round_no": round_no,
                "time_context": time_context,
                "public_summary": public_summary,
                "private_results": private_results,
                "npc_updates": npc_updates,
                "active_event": active_event,
                "outcomes": outcomes,
            }

        return self.db.run(work)

    def _with_private_delivery_note(self, public_summary: str) -> str:
        text = str(public_summary or "").strip()
        if not text:
            return ""
        if "本摘要仅私聊发送" in text:
            return text
        return text + "\n提示：本摘要仅私聊发送给已参与游戏的玩家，群聊不再发布剧情公告。"

    def _approved_player_qq_ids(self, con: sqlite3.Connection, group_id: str) -> list[str]:
        rows = con.execute(
            "SELECT qq_id FROM characters WHERE group_id=? AND audit_status='approved' ORDER BY id",
            (group_id,),
        ).fetchall()
        return [str(row["qq_id"]) for row in rows if str(row["qq_id"] or "").strip()]

    def merge_public_summary_into_private_results(
        self,
        round_no: int,
        public_summary: str,
        private_results: dict[str, str],
    ) -> dict[str, str]:
        public_summary = self._ensure_sendable_text(
            public_summary,
            f"【第 {round_no} 轮学园都市更新】\n本轮公共摘要生成异常，请联系管理员查看历史。",
        )
        public_summary = self._with_private_delivery_note(public_summary)
        merged_results: dict[str, str] = {}
        for qq_id, personal in (private_results or {}).items():
            qq_text = str(qq_id)
            personal = str(personal or "").strip()
            if personal:
                merged = f"{public_summary}\n\n{personal}"
                merged_results[qq_text] = self._clip_text(merged, self.config.public_summary_max_chars + self.config.private_result_max_chars + 200)
                continue
            event_only = "\n".join(
                [
                    public_summary,
                    "",
                    f"【第 {round_no} 轮个人结果】",
                    "你本轮没有提交行动，也没有被其他玩家行动直接影响；仅接收本轮世界事件和新闻摘要。",
                ]
            )
            merged_results[qq_text] = self._clip_text(event_only, self.config.public_summary_max_chars + 500)
        return merged_results

    def _clip_text(self, text: str, limit: int) -> str:
        limit = max(100, int(limit or 0))
        text = str(text or "")
        if len(text) <= limit:
            return text
        return text[: max(0, limit - 24)].rstrip() + "\n……（内容已截断）"

    def mark_daily_sent(self, group_id: str) -> None:
        self.db.run(
            lambda con: con.execute(
                "UPDATE worlds SET last_daily_status_date=?, updated_at=? WHERE group_id=?",
                (cn_today(), utc_now_iso(), group_id),
            )
        )

    def daily_statuses(self, group_id: str) -> dict[str, str]:
        def work(con: sqlite3.Connection) -> dict[str, str]:
            rows = con.execute(
                "SELECT * FROM characters WHERE group_id=? AND audit_status='approved' ORDER BY id",
                (group_id,),
            ).fetchall()
            return {str(row["qq_id"]): self.format_status(con, row) for row in rows}

        return self.db.run(work)

    def checkin(self, group_id: str, qq_id: str) -> tuple[bool, str]:
        today = cn_today()

        def work(con: sqlite3.Connection) -> tuple[bool, str]:
            char = con.execute(
                "SELECT * FROM characters WHERE group_id=? AND qq_id=?",
                (group_id, qq_id),
            ).fetchone()
            if not char:
                return False, "你还没有角色卡。"
            if char["audit_status"] != "approved":
                return False, "角色卡通过审核后才能签到。"
            if char["last_checkin_date"] == today:
                return False, "今天已经签到过了。"
            reward = self.config.checkin_reward
            con.execute(
                "UPDATE characters SET money=money+?, mood=min(100,mood+1), last_checkin_date=?, updated_at=? WHERE id=?",
                (reward, today, utc_now_iso(), char["id"]),
            )
            con.execute(
                "INSERT INTO history(group_id,visibility,character_id,kind,text,created_at) VALUES(?,?,?,?,?,?)",
                (group_id, "private", char["id"], "checkin", f"每日签到获得 {reward} 学都币。", utc_now_iso()),
            )
            return True, f"签到成功，获得 {reward} 学都币。"

        return self.db.run(work)

    def private_world_for_qq(self, qq_id: str, private_origin: str = "") -> dict[str, Any] | None:
        qq_id = str(qq_id or "").strip()
        private_origin = str(private_origin or "").strip()
        if not qq_id:
            return None

        def work(con: sqlite3.Connection) -> dict[str, Any] | None:
            base_sql = """
                SELECT
                  characters.group_id,
                  characters.game_name,
                  characters.audit_status,
                  characters.private_origin,
                  worlds.enabled,
                  worlds.updated_at
                FROM characters
                JOIN worlds ON worlds.group_id=characters.group_id
                WHERE characters.qq_id=?
                  AND worlds.enabled=1
                  {extra_where}
                ORDER BY
                  CASE WHEN characters.private_origin<>'' THEN 0 ELSE 1 END,
                  CASE WHEN characters.audit_status='approved' THEN 0 ELSE 1 END,
                  worlds.updated_at DESC,
                  characters.updated_at DESC,
                  characters.id DESC
                LIMIT 2
            """
            rows: list[sqlite3.Row] = []
            if private_origin:
                rows = con.execute(
                    base_sql.format(extra_where="AND characters.private_origin=?"),
                    (qq_id, private_origin),
                ).fetchall()
                if len(rows) == 1:
                    return dict(rows[0])
                if len(rows) > 1:
                    return {"ambiguous": True}

            approved_rows = con.execute(
                base_sql.format(extra_where="AND characters.private_origin='' AND characters.audit_status='approved'"),
                (qq_id,),
            ).fetchall()
            if len(approved_rows) == 1:
                return dict(approved_rows[0])
            if len(approved_rows) > 1:
                return {"ambiguous": True}

            rows = con.execute(
                base_sql.format(extra_where="AND characters.private_origin=''"),
                (qq_id,),
            ).fetchall()
            if not rows:
                return None
            if len(rows) > 1:
                return {"ambiguous": True}
            return dict(rows[0])

        return self.db.run(work)

    def get_status_by_qq(self, group_id: str, qq_id: str) -> str:
        def work(con: sqlite3.Connection) -> str:
            char = con.execute(
                "SELECT * FROM characters WHERE group_id=? AND qq_id=?",
                (group_id, qq_id),
            ).fetchone()
            if not char:
                return "你还没有角色卡。"
            return self.format_status(con, char)

        return self.db.run(work)

    def task_text(self, group_id: str, qq_id: str) -> str:
        def work(con: sqlite3.Connection) -> str:
            char = con.execute(
                "SELECT * FROM characters WHERE group_id=? AND qq_id=?",
                (group_id, qq_id),
            ).fetchone()
            if not char:
                return "你还没有角色卡。"
            if char["audit_status"] != "approved":
                return "角色卡通过审核后才能查看今日任务。"
            return self._task_text_for_char(con, char)

        return self.db.run(work)

    def _task_text_for_char(self, con: sqlite3.Connection, char: sqlite3.Row) -> str:
        loc = self._location(con, char["group_id"], char["location_key"])
        task = self._daily_task_hint(char)
        identity_tasks = self._identity_task_suggestions(str(char["identity"] or ""), str(char["faction"] or ""))
        growth_tasks = self._growth_task_suggestions(char)
        time_context = self.current_time_context()
        lines = [
            f"【{char['game_name']} 的今日引导】",
            f"现实时间：{time_context['display']}",
            f"当前位置：{loc['name'] if loc else char['location_key']}",
            f"当前引导：{task}",
            f"声望等级：{self._reputation_label(int_value(char['reputation'], 0))}",
            "可选任务：",
        ]
        for item in identity_tasks[:5]:
            lines.append("- " + item)
        lines.append("成长方向：")
        for item in growth_tasks[:5]:
            lines.append("- " + item)
        lines.append("提示：任务不是强制指令，只要在“行动”里自然写出对应行为，结算时会按身份、地点、现实时间和角色状态判定。")
        return "\n".join(lines)

    def map_text(self, group_id: str, qq_id: str | None = None) -> str:
        def work(con: sqlite3.Connection) -> str:
            char = None
            if qq_id:
                char = con.execute(
                    "SELECT * FROM characters WHERE group_id=? AND qq_id=?",
                    (group_id, qq_id),
                ).fetchone()
            locations = con.execute(
                "SELECT * FROM locations WHERE group_id=? ORDER BY sort_order,id",
                (group_id,),
            ).fetchall()
            lines = ["【学园都市地图】"]
            if char:
                loc = self._location(con, group_id, char["location_key"])
                if loc:
                    lines.append(f"当前位置：{loc['name']} - {loc['description']}")
                    neighbors = self._neighbor_names(con, group_id, char["location_key"])
                    lines.append("可前往：" + ("、".join(neighbors) if neighbors else "无"))
                    lines.append("")
            lines.append("地点连接：")
            for loc in locations:
                neighbors = self._neighbor_names(con, group_id, loc["location_key"])
                lines.append(f"- {loc['name']} -> {'、'.join(neighbors) if neighbors else '无'}")
            return "\n".join(lines)

        return self.db.run(work)

    def pending_text(self, group_id: str) -> str:
        def work(con: sqlite3.Connection) -> str:
            world = con.execute("SELECT * FROM worlds WHERE group_id=?", (group_id,)).fetchone()
            if not world:
                return "这个群还没有开启文字世界。"
            count = con.execute(
                "SELECT COUNT(*) FROM actions WHERE group_id=? AND round_no=? AND status='pending'",
                (group_id, world["current_round"]),
            ).fetchone()[0]
            total = con.execute(
                "SELECT COUNT(*) FROM characters WHERE group_id=? AND audit_status='approved'",
                (group_id,),
            ).fetchone()[0]
            return "\n".join(
                [
                    "【待结算】",
                    f"现实联动时间：{self.current_time_line()}",
                    f"当前轮次：第 {world['current_round']} 轮",
                    f"已提交行动：{count} 人",
                    f"已审核角色：{total} 人",
                    f"下次结算：{self.format_time(world['next_tick_at'])}",
                ]
            )

        return self.db.run(work)

    def dashboard_snapshot(self, user: dict[str, Any]) -> dict[str, Any]:
        role = user.get("role")
        username = user.get("username")

        def work(con: sqlite3.Connection) -> dict[str, Any]:
            worlds = [dict(row) for row in con.execute("SELECT * FROM worlds ORDER BY created_at DESC").fetchall()]
            if role == "admin":
                characters = [dict(row) for row in con.execute("SELECT * FROM characters ORDER BY updated_at DESC LIMIT 200").fetchall()]
                world_ids = [row["group_id"] for row in worlds]
                events = [dict(row) for row in con.execute("SELECT * FROM event_presets ORDER BY updated_at DESC LIMIT 100").fetchall()]
                history = [dict(row) for row in con.execute("SELECT * FROM history ORDER BY id DESC LIMIT 100").fetchall()]
                shop = [dict(row) for row in con.execute("SELECT * FROM shop_items ORDER BY group_id,name LIMIT 200").fetchall()]
                npcs = [dict(row) for row in con.execute("SELECT * FROM npcs ORDER BY group_id,name LIMIT 200").fetchall()]
                locations = [dict(row) for row in con.execute("SELECT * FROM locations ORDER BY group_id,sort_order,id LIMIT 500").fetchall()]
                edges = [dict(row) for row in con.execute("SELECT * FROM location_edges ORDER BY group_id,from_location_key,to_location_key LIMIT 2000").fetchall()]
            else:
                characters = [dict(row) for row in con.execute(
                    "SELECT characters.* FROM characters JOIN users ON users.id=characters.user_id WHERE users.username=?",
                    (username,),
                ).fetchall()]
                world_ids = sorted({row["group_id"] for row in characters})
                worlds = [row for row in worlds if row["group_id"] in world_ids]
                if world_ids:
                    placeholders = ",".join("?" for _ in world_ids)
                    events = []
                    history = [
                        dict(row)
                        for row in con.execute(
                            f"""
                            SELECT history.* FROM history
                            LEFT JOIN characters ON characters.id=history.character_id
                            WHERE history.group_id IN ({placeholders})
                              AND (
                                history.visibility='public'
                                OR characters.user_id=?
                              )
                            ORDER BY history.id DESC LIMIT 100
                            """,
                            (*world_ids, user.get("id")),
                        ).fetchall()
                    ]
                    shop = [dict(row) for row in con.execute(
                        f"""
                        SELECT id,group_id,name,description,price,stock,is_active,created_at,updated_at
                        FROM shop_items
                        WHERE group_id IN ({placeholders}) AND is_active=1
                        ORDER BY group_id,name LIMIT 200
                        """,
                        tuple(world_ids),
                    ).fetchall()]
                    npcs = [
                        dict(row)
                        for row in con.execute(
                            f"SELECT npc_key,group_id,name,role,faction,location_key,disposition,memory FROM npcs WHERE group_id IN ({placeholders}) ORDER BY group_id,name LIMIT 200",
                            tuple(world_ids),
                        ).fetchall()
                    ]
                    locations = [
                        dict(row)
                        for row in con.execute(
                            f"SELECT * FROM locations WHERE group_id IN ({placeholders}) ORDER BY group_id,sort_order,id LIMIT 500",
                            tuple(world_ids),
                        ).fetchall()
                    ]
                    edges = [
                        dict(row)
                        for row in con.execute(
                            f"SELECT * FROM location_edges WHERE group_id IN ({placeholders}) ORDER BY group_id,from_location_key,to_location_key LIMIT 2000",
                            tuple(world_ids),
                        ).fetchall()
                    ]
                else:
                    events = []
                    history = []
                    shop = []
                    npcs = []
                    locations = []
                    edges = []
            return {
                "user": {"username": username, "role": role},
                "worlds": worlds,
                "characters": characters,
                "events": events,
                "history": history,
                "shop": shop,
                "npcs": npcs,
                "locations": locations,
                "edges": edges,
                "worldbook": self.config.worldbook_info(preview_chars=2400 if role == "admin" else 800),
                "providers": self.config.provider_info(),
                "time_context": self.current_time_context(),
            }

        return self.db.run(work)

    def admin_update_character(self, payload: dict[str, Any]) -> dict[str, Any]:
        group_id = str(payload.get("group_id") or "").strip()
        qq_id = str(payload.get("qq_id") or "").strip()
        if not group_id or not qq_id:
            raise ValueError("缺少 group_id 或 qq_id")
        self.ensure_world(group_id, "")
        now = utc_now_iso()

        def work(con: sqlite3.Connection) -> dict[str, Any]:
            row = con.execute(
                "SELECT * FROM characters WHERE group_id=? AND qq_id=?",
                (group_id, qq_id),
            ).fetchone()
            game_name = self.clean_name(str(payload.get("game_name") or (row["game_name"] if row else qq_id)))
            existing_name = con.execute(
                "SELECT qq_id FROM characters WHERE group_id=? AND game_name=?",
                (group_id, game_name),
            ).fetchone()
            if existing_name and str(existing_name["qq_id"]) != qq_id:
                raise ValueError("这个游戏名已经被使用了。")
            self._validate_player_account_owner(con, game_name, qq_id, int(row["id"]) if row else None)
            audit_status = str(payload.get("audit_status") or (row["audit_status"] if row else "approved")).strip()
            if audit_status not in {"approved", "pending", "rejected"}:
                raise ValueError("审核状态只能是 approved、pending 或 rejected。")
            location_key = str(payload.get("location_key") or (row["location_key"] if row else "school_gate")).strip()
            if not self._location(con, group_id, location_key):
                raise ValueError("位置 key 不存在，请先使用已有地图地点。")
            fields = {
                "game_name": game_name,
                "display_name": self.clean_name(str(payload.get("display_name") or payload.get("game_name") or (row["display_name"] if row else qq_id))),
                "identity": self.clean_text(str(payload.get("identity") if payload.get("identity") is not None else (row["identity"] if row else "")), 240),
                "faction": self.clean_text(str(payload.get("faction") if payload.get("faction") is not None else (row["faction"] if row else "")), 80),
                "ability": self.clean_text(str(payload.get("ability") if payload.get("ability") is not None else (row["ability"] if row else "")), 240),
                "power_level": self.clean_text(str(payload.get("power_level") if payload.get("power_level") is not None else (row["power_level"] if row else "Level 3")), 20) or "Level 3",
                "gender": self.clean_text(str(payload.get("gender") if payload.get("gender") is not None else (row["gender"] if row and "gender" in row.keys() else "")), 20),
                "outfit": self.clean_text(str(payload.get("outfit") if payload.get("outfit") is not None else (row["outfit"] if row else "")), 120),
                "body_profile": self.clean_text(str(payload.get("body_profile") if payload.get("body_profile") is not None else (row["body_profile"] if row else "")), 120),
                "ability_exp": max(0, int_value(payload.get("ability_exp"), int(row["ability_exp"]) if row else 0)),
                "death_protection": max(0, int_value(payload.get("death_protection"), int(row["death_protection"]) if row else 0)),
                "traits_json": self._clean_traits_json(payload.get("traits_json") if payload.get("traits_json") is not None else (row["traits_json"] if row else "[]")),
                "audit_status": audit_status,
                "location_key": location_key,
                "hp": clamp(int_value(payload.get("hp"), int(row["hp"]) if row else 100)),
                "energy": clamp(int_value(payload.get("energy"), int(row["energy"]) if row else 100)),
                "water": clamp(int_value(payload.get("water"), int(row["water"]) if row else 80)),
                "satiety": clamp(int_value(payload.get("satiety"), int(row["satiety"]) if row else 80)),
                "mood": clamp(int_value(payload.get("mood"), int(row["mood"]) if row else 70)),
                "money": max(0, int_value(payload.get("money"), int(row["money"]) if row else self.config.start_money)),
            }
            user_id = self.db.ensure_player_user(
                con,
                game_name,
                str(payload.get("password") or qq_id[-6:] or "123456"),
                int(row["user_id"]) if row and row["user_id"] else None,
                reset_password=bool(payload.get("password")),
            )
            if row:
                con.execute(
                    """
                    UPDATE characters SET user_id=?,game_name=?,display_name=?,identity=?,faction=?,ability=?,power_level=?,gender=?,outfit=?,body_profile=?,ability_exp=?,death_protection=?,traits_json=?,audit_status=?,location_key=?,hp=?,energy=?,water=?,satiety=?,mood=?,money=?,updated_at=?
                    WHERE id=?
                    """,
                    (user_id, *fields.values(), now, row["id"]),
                )
            else:
                con.execute(
                    """
                    INSERT INTO characters(group_id,user_id,qq_id,game_name,display_name,identity,faction,ability,power_level,gender,outfit,body_profile,ability_exp,death_protection,traits_json,audit_status,location_key,hp,energy,water,satiety,mood,money,created_at,updated_at)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (group_id, user_id, qq_id, *fields.values(), now, now),
                )
            return dict(con.execute("SELECT * FROM characters WHERE group_id=? AND qq_id=?", (group_id, qq_id)).fetchone())

        return self.db.run(work)

    def pending_character_cards(self, group_id: str, limit: int = 12) -> list[dict[str, Any]]:
        group_id = str(group_id or "").strip()
        if not group_id:
            return []
        limit = max(1, min(30, int_value(limit, 12)))

        def work(con: sqlite3.Connection) -> list[dict[str, Any]]:
            rows = con.execute(
                """
                SELECT id,qq_id,game_name,display_name,identity,faction,ability,power_level,gender,created_at,updated_at
                FROM characters
                WHERE group_id=? AND audit_status='pending'
                ORDER BY updated_at ASC, id ASC
                LIMIT ?
                """,
                (group_id, limit),
            ).fetchall()
            return [dict(row) for row in rows]

        return self.db.run(work)

    def admin_audit_character(
        self,
        group_id: str,
        query: str,
        audit_status: str = "approved",
    ) -> dict[str, Any]:
        group_id = str(group_id or "").strip()
        query = self.clean_text(str(query or ""), 80)
        audit_status = str(audit_status or "approved").strip()
        aliases = {
            "approve": "approved",
            "approved": "approved",
            "pass": "approved",
            "通过": "approved",
            "批准": "approved",
            "同意": "approved",
            "拒绝": "rejected",
            "驳回": "rejected",
            "不通过": "rejected",
            "rejected": "rejected",
            "reject": "rejected",
            "待审核": "pending",
            "退回": "pending",
            "pending": "pending",
        }
        audit_status = aliases.get(audit_status, audit_status)
        if audit_status not in {"approved", "pending", "rejected"}:
            raise ValueError("审核状态只能是 approved、pending、rejected，或中文：通过/拒绝/退回。")
        if not group_id or not query:
            raise ValueError("缺少群号或角色查询词。")
        self.ensure_world(group_id, "")
        now = utc_now_iso()

        def work(con: sqlite3.Connection) -> dict[str, Any]:
            exact = con.execute(
                """
                SELECT * FROM characters
                WHERE group_id=?
                  AND (qq_id=? OR game_name=? OR display_name=?)
                ORDER BY CASE WHEN audit_status='pending' THEN 0 ELSE 1 END, updated_at DESC, id DESC
                """,
                (group_id, query, query, query),
            ).fetchall()
            if not exact:
                fuzzy = con.execute(
                    """
                    SELECT * FROM characters
                    WHERE group_id=?
                      AND (instr(game_name, ?) > 0 OR instr(display_name, ?) > 0)
                    ORDER BY CASE WHEN audit_status='pending' THEN 0 ELSE 1 END, length(game_name), updated_at DESC, id DESC
                    LIMIT 6
                    """,
                    (group_id, query, query),
                ).fetchall()
                exact = fuzzy
            if not exact:
                raise ValueError(f"没有找到角色：{query}")
            if len(exact) > 1:
                pending = [row for row in exact if str(row["audit_status"]) == "pending"]
                candidates = pending or exact
                names = "、".join(f"{row['game_name']}({row['qq_id']})" for row in candidates[:5])
                raise ValueError(f"匹配到多个角色，请用 QQ 号或完整游戏名：{names}")
            row = exact[0]
            con.execute(
                "UPDATE characters SET audit_status=?, updated_at=? WHERE id=?",
                (audit_status, now, row["id"]),
            )
            return dict(con.execute("SELECT * FROM characters WHERE id=?", (row["id"],)).fetchone())

        return self.db.run(work)

    def admin_event_preset(self, payload: dict[str, Any]) -> dict[str, Any]:
        group_id = str(payload.get("group_id") or "").strip()
        title = self.clean_text(str(payload.get("title") or ""), 120)
        description = self.clean_text(str(payload.get("description") or ""), 1000)
        if not group_id or not title:
            raise ValueError("缺少 group_id 或事件名称")
        self.ensure_world(group_id, "")
        now = utc_now_iso()
        effect = payload.get("effect") or {}
        if not isinstance(effect, dict):
            raise ValueError("事件效果必须是 JSON 对象。")

        def work(con: sqlite3.Connection) -> dict[str, Any]:
            con.execute(
                """
                INSERT INTO event_presets(group_id,title,description,effect_json,is_public,trigger_next,created_at,updated_at)
                VALUES(?,?,?,?,?,?,?,?)
                """,
                (
                    group_id,
                    title,
                    description,
                    dumps(effect),
                    1 if payload.get("is_public", True) else 0,
                    1 if payload.get("trigger_next", False) else 0,
                    now,
                    now,
                ),
            )
            return dict(con.execute("SELECT * FROM event_presets WHERE id=last_insert_rowid()").fetchone())

        return self.db.run(work)

    def admin_trigger_event(self, event_id: int) -> bool:
        def work(con: sqlite3.Connection) -> bool:
            cur = con.execute(
                "UPDATE event_presets SET trigger_next=1, updated_at=? WHERE id=?",
                (utc_now_iso(), event_id),
            )
            return int(cur.rowcount) > 0

        return self.db.run(work)

    def admin_shop_item(self, payload: dict[str, Any]) -> dict[str, Any]:
        group_id = str(payload.get("group_id") or "").strip()
        name = self.clean_text(str(payload.get("name") or ""), 80)
        if not group_id or not name:
            raise ValueError("缺少 group_id 或商品名")
        self.ensure_world(group_id, "")
        now = utc_now_iso()
        effect = payload.get("effect") or {}
        if not isinstance(effect, dict):
            raise ValueError("商品效果必须是 JSON 对象。")
        price = max(0, int_value(payload.get("price"), 0))
        stock_raw = int_value(payload.get("stock"), -1)
        stock = -1 if stock_raw < 0 else stock_raw

        def work(con: sqlite3.Connection) -> dict[str, Any]:
            con.execute(
                """
                INSERT INTO shop_items(group_id,name,description,price,stock,effect_json,is_active,created_at,updated_at)
                VALUES(?,?,?,?,?,?,?,?,?)
                ON CONFLICT(group_id,name) DO UPDATE SET
                  description=excluded.description, price=excluded.price, stock=excluded.stock,
                  effect_json=excluded.effect_json, is_active=excluded.is_active, updated_at=excluded.updated_at
                """,
                (
                    group_id,
                    name,
                    self.clean_text(str(payload.get("description") or ""), 500),
                    price,
                    stock,
                    dumps(effect),
                    1 if payload.get("is_active", True) else 0,
                    now,
                    now,
                ),
            )
            return dict(con.execute("SELECT * FROM shop_items WHERE group_id=? AND name=?", (group_id, name)).fetchone())

        return self.db.run(work)

    def format_status(self, con: sqlite3.Connection, char: sqlite3.Row | dict[str, Any]) -> str:
        location = self._location(con, char["group_id"], char["location_key"])
        location_name = location["name"] if location else char["location_key"]
        inv = con.execute(
            "SELECT item_name,quantity FROM inventory WHERE character_id=? AND quantity>0 ORDER BY item_name",
            (char["id"],),
        ).fetchall()
        bag = "、".join(f"{row['item_name']} x{row['quantity']}" for row in inv) if inv else "无"
        pending = con.execute(
            """
            SELECT actions.id FROM actions
            JOIN worlds ON worlds.group_id=actions.group_id
            WHERE actions.group_id=? AND actions.character_id=? AND actions.round_no=worlds.current_round AND actions.status='pending'
            """,
            (char["group_id"], char["id"]),
        ).fetchone()
        world = con.execute("SELECT * FROM worlds WHERE group_id=?", (char["group_id"],)).fetchone()
        return "\n".join(
            [
                f"【{char['game_name']} 的状态栏】",
                f"身份：{char['identity'] or '未设定'}",
                f"性别：{char['gender'] if 'gender' in char.keys() and char['gender'] else '未设定'}",
                f"阵营：{char['faction'] or '无'}",
                f"能力名称-等级：{char['ability'] or '未设定'} - {char['power_level']}",
                f"能力经验：{int(char['ability_exp'])}/{self._next_level_exp(char['power_level'])}",
                f"声望等级：{self._reputation_label(int_value(char['reputation'] if 'reputation' in char.keys() else 0, 0))}",
                f"扩展经验：体力 {int_value(char['physical_exp'] if 'physical_exp' in char.keys() else 0, 0)}，社交 {int_value(char['social_exp'] if 'social_exp' in char.keys() else 0, 0)}，学业 {int_value(char['study_exp'] if 'study_exp' in char.keys() else 0, 0)}，艺术 {int_value(char['art_exp'] if 'art_exp' in char.keys() else 0, 0)}",
                f"当前引导：{self._daily_task_hint(char)}",
                f"穿衣着装：{char['outfit'] or '日常学生装/未详细设定'}",
                f"简易身材：{char['body_profile'] or '未详细设定'}",
                f"审核：{self.audit_label(char['audit_status'])}",
                f"位置：{location_name}",
                f"世界时间：{self.current_time_line()}",
                f"生命：{char['hp']}/100",
                f"精力：{char['energy']}/100",
                f"水分：{char['water']}/100",
                f"饱食度：{char['satiety']}/100",
                f"心情：{char['mood']}/100",
                f"学都币：{char['money']}",
                f"死亡保护：{char['death_protection']} 次",
                f"词条：{self._traits_text(char['traits_json'])}",
                f"背包：{bag}",
                f"本轮行动：{'已提交' if pending else '未提交'}",
                f"当前轮次：第 {world['current_round'] if world else '-'} 轮",
                f"下次结算：{self.format_time(world['next_tick_at']) if world else '-'}",
            ]
        )

    def _ensure_sendable_text(self, text: Any, fallback: str) -> str:
        cleaned = str(text or "").strip()
        if not cleaned or self._is_placeholder_summary(cleaned):
            return str(fallback or "").strip()
        return cleaned

    def _is_placeholder_summary(self, text: str) -> bool:
        markers = (
            "你的行动被记录并执行",
            "具体细节会在本轮剧情里展开",
            "稍后展开",
            "等待后续剧情",
        )
        return any(marker in str(text or "") for marker in markers)

    def _generic_action_summary(
        self,
        con: sqlite3.Connection,
        group_id: str,
        location_key: str,
        text: str,
        game_name: str = "",
    ) -> str:
        loc = self._location(con, group_id, location_key)
        loc_name = str(loc["name"] if loc else location_key or "当前位置")
        phase = str(self.current_time_context().get("phase") or "当前时段")
        action_text = self.clean_text(text, 90)
        if any(word in text for word in ("观察", "查看", "看看", "盯", "巡查", "巡视")):
            return f"{game_name or '你'}留在{loc_name}观察周围动向。{phase}的人流、广播和警备机器人巡逻被记录下来，你获得了一些公开层面的环境线索。"
        if any(word in text for word in ("调查", "打听", "询问", "寻找线索", "查", "问")):
            return f"{game_name or '你'}在{loc_name}围绕“{action_text}”展开调查。本轮只得到公开传闻和可接触线索，未突破权限边界。"
        if any(word in text for word in ("等待", "蹲守", "守着", "等人")):
            return f"{game_name or '你'}在{loc_name}等待目标或机会。{phase}的环境让行动节奏放慢，你没有获得直接奖励，但保留了后续接触的可能。"
        if any(word in text for word in ("上课", "学习", "自习", "补习", "写作业", "读书")):
            return f"{game_name or '你'}在{loc_name}完成了一段学习安排。课程、终端资料和周围学生的讨论让你对当下局势有了更清晰的判断。"
        if any(word in text for word in ("散步", "闲逛", "逛", "巡逻", "巡街")):
            return f"{game_name or '你'}沿着{loc_name}附近活动了一圈。{phase}的街区没有立刻爆发事件，但你注意到几处适合下轮继续追查的细节。"
        return f"{game_name or '你'}在{loc_name}完成了本轮行动：“{action_text}”。程序已按当前位置、现实时间和角色状态结算，未识别到特殊奖励、交易或伤害。"

    def _resolve_rest(
        self,
        con: sqlite3.Connection,
        group_id: str,
        row: sqlite3.Row,
        text: str,
        location_key: str,
    ) -> tuple[str, int, int, int, int, int, int]:
        loc = self._location(con, group_id, location_key)
        loc_name = str(loc["name"] if loc else location_key or "当前位置")
        tags = set(loads(str(loc["tags"] or "[]"), []) if loc else [])
        lower = text.lower()
        facility_words = ("宿舍", "床", "休息室", "酒店", "医院", "诊疗", "按摩", "温泉", "家庭餐厅", "付费", "花钱", "胶囊旅馆")
        facility = bool(tags & {"休息", "恢复", "医疗", "餐饮", "生活"}) or any(word in text or word in lower for word in facility_words)
        paid = any(word in text for word in ("付费", "花钱", "开房", "酒店", "按摩", "诊疗", "买票", "套餐", "休息室"))
        cost = 0
        if paid:
            cost = min(int(row["money"]), 30 if "医院" in text or location_key == "hospital" else 20)
        recovery = 55
        hp_delta = 0
        water_delta = 0
        satiety_delta = 0
        mood_delta = 5
        if facility:
            recovery += 15
            mood_delta += 2
        if paid and cost >= 10:
            recovery += 15
            hp_delta += 6 if ("医院" in text or location_key == "hospital") else 2
            water_delta += 8
            satiety_delta += 8
        elif paid and cost < 10:
            paid = False
            cost = 0
        if location_key == "hospital":
            hp_delta += 8
            recovery += 5
        elif location_key in {"dorm", "family_restaurant", "canteen"}:
            water_delta += 6
            satiety_delta += 6
        recovery = max(50, min(100, recovery))
        summary = f"你在{loc_name}认真休整了一轮，精力恢复 {recovery} 点。"
        if facility:
            summary += " 场所条件较适合恢复，效果比原地硬撑更好。"
        if paid and cost:
            summary += f" 你额外花费 {cost} 学都币使用设施或服务，恢复效果进一步提高。"
        return summary, -cost, hp_delta, recovery, water_delta, satiety_delta, mood_delta

    def _resolve_self_heal(self, row: sqlite3.Row) -> tuple[str, int, int, list[str]]:
        cost = min(int(row["money"]), 30)
        if cost >= 10:
            return f"你接受了基础治疗，花费 {cost} 学都币，生命有所恢复。", -cost, min(25, cost), []
        return "你想治疗伤势，但学都币不太够。", 0, 0, ["治疗失败：余额不足。"]

    def _resolve_action(
        self,
        con: sqlite3.Connection,
        group_id: str,
        row: sqlite3.Row,
        pvp_targets: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        warnings: list[str] = []
        text = str(row["text"])
        old_location = self._location(con, group_id, row["location_key"])
        target = self._extract_location(con, group_id, row["location_key"], text)
        if target and target["location_key"] == row["location_key"]:
            target = None
        energy_delta = -8
        water_delta = -random.randint(3, 6)
        satiety_delta = -random.randint(2, 5)
        mood_delta = random.choice([-1, 0, 1])
        money_delta = 0
        hp_delta = 0
        exp_delta = 0
        death_protection_delta = 0
        development_mark = ""
        location_key = row["location_key"]
        summary = self._generic_action_summary(con, group_id, row["location_key"], text, row["game_name"])
        accepted = True
        pvp_targets = pvp_targets or []
        pvp_intent = self._looks_like_pvp(text) or bool(pvp_targets)
        development_intent = self._looks_like_development(text)
        battle_intent = self._looks_like_battle(text) or pvp_intent
        inventory_use_intent = self._looks_like_inventory_use(con, row["character_id"], text)
        purchase_intent = self._looks_like_buy(con, group_id, text) and not self._looks_like_transfer(text)
        if purchase_intent and inventory_use_intent and not self._has_purchase_intent_alongside_inventory(text):
            purchase_intent = False
        self_heal_intent = self._looks_like_self_heal(text)
        movement_path: list[str] = []
        if target:
            movement_path = self._movement_path(con, group_id, row["location_key"], target["location_key"])
            if movement_path:
                location_key = target["location_key"]
                summary = self._movement_summary(con, group_id, old_location, movement_path)
                energy_delta = -6 - max(1, len(movement_path) - 1) * 4
                if len(movement_path) > 2:
                    warnings.append("本轮跨越了多段路线，路上可能出现传闻、偶遇或轻微消耗。")
                route_scene = self._route_scene(con, group_id, movement_path, row, text)
                if route_scene:
                    summary += " " + route_scene
            else:
                accepted = False
                target_name = target["name"]
                summary = f"你尝试前往{target_name}，但超过本轮可移动范围或地图路线不成立，本轮留在原地。"
                warnings.append(f"地图规则拦截：当前位置不能在 {self.config.max_move_steps} 格内前往{target_name}。")
                energy_delta = -2
            restricted_warning = self._restricted_location_warning(target, text, row) if accepted else ""
            if restricted_warning:
                warnings.append(restricted_warning)
                energy_delta -= 3
                mood_delta -= 1
            if accepted and inventory_use_intent:
                (
                    use_summary,
                    use_money_delta,
                    use_hp_delta,
                    use_energy_delta,
                    use_water_delta,
                    use_satiety_delta,
                    use_mood_delta,
                    use_death_protection_delta,
                    use_warnings,
                ) = self._resolve_inventory_use(con, group_id, row)
                summary += " " + use_summary
                money_delta += use_money_delta
                hp_delta += use_hp_delta
                energy_delta += use_energy_delta
                water_delta += use_water_delta
                satiety_delta += use_satiety_delta
                mood_delta += use_mood_delta
                death_protection_delta += use_death_protection_delta
                warnings.extend(use_warnings)
                if purchase_intent:
                    (
                        purchase_summary,
                        purchase_money_delta,
                        purchase_hp_delta,
                        purchase_energy_delta,
                        purchase_water_delta,
                        purchase_satiety_delta,
                        purchase_mood_delta,
                        purchase_death_protection_delta,
                    ) = self._resolve_purchase(con, group_id, row)
                    summary += " " + purchase_summary
                    money_delta += purchase_money_delta
                    hp_delta += purchase_hp_delta
                    energy_delta += purchase_energy_delta
                    water_delta += purchase_water_delta
                    satiety_delta += purchase_satiety_delta
                    mood_delta += purchase_mood_delta
                    death_protection_delta += purchase_death_protection_delta
            elif accepted and self_heal_intent:
                heal_summary, heal_money_delta, heal_hp_delta, heal_warnings = self._resolve_self_heal(row)
                summary += " " + heal_summary
                money_delta += heal_money_delta
                hp_delta += heal_hp_delta
                warnings.extend(heal_warnings)
            elif accepted and self._looks_like_rest(text):
                (
                    rest_summary,
                    rest_money_delta,
                    rest_hp_delta,
                    rest_energy_delta,
                    rest_water_delta,
                    rest_satiety_delta,
                    rest_mood_delta,
                ) = self._resolve_rest(con, group_id, row, text, location_key)
                summary += " " + rest_summary
                money_delta += rest_money_delta
                hp_delta += rest_hp_delta
                energy_delta += rest_energy_delta
                water_delta += rest_water_delta
                satiety_delta += rest_satiety_delta
                mood_delta += rest_mood_delta
            elif accepted and purchase_intent:
                (
                    purchase_summary,
                    purchase_money_delta,
                    purchase_hp_delta,
                    purchase_energy_delta,
                    purchase_water_delta,
                    purchase_satiety_delta,
                    purchase_mood_delta,
                    purchase_death_protection_delta,
                ) = self._resolve_purchase(con, group_id, row)
                summary += " " + purchase_summary
                money_delta += purchase_money_delta
                hp_delta += purchase_hp_delta
                energy_delta += purchase_energy_delta
                water_delta += purchase_water_delta
                satiety_delta += purchase_satiety_delta
                mood_delta += purchase_mood_delta
                death_protection_delta += purchase_death_protection_delta
            elif accepted and development_intent:
                today = cn_today()
                if str(row["daily_development_date"] or "") == today:
                    summary += " 但今天已经完成过一次正式能力开发。"
                    energy_delta -= 2
                else:
                    exp_delta = self._exp_with_trait_bonus(row, self._amount_with_secondary_bonus(row, 50, "study"), "development")
                    money_delta += self._income_with_level_bonus(15, row["power_level"])
                    energy_delta -= 10
                    mood_delta += 1
                    development_mark = today
                    summary += f" 并参加能力开发课程，获得 {exp_delta} 点能力经验。"
            elif accepted and battle_intent:
                exp_delta = self._exp_with_trait_bonus(row, self._amount_with_secondary_bonus(row, 20, "physical"), "battle")
                energy_delta -= 14
                if pvp_intent:
                    damage = self._pvp_self_damage(row, pvp_targets, text)
                    hp_delta -= damage
                    mood_delta -= 3
                    summary += f" 随后爆发了真实冲突，承受 {damage} 点伤害，获得 {exp_delta} 点战斗经验。{self._conflict_consequence_line(damage)}"
                    warnings.extend(self._conflict_warning_lines(damage))
                else:
                    training_damage = self._training_damage(text)
                    hp_delta -= training_damage
                    summary += f" 随后进行了有接触的实战训练，承受 {training_damage} 点伤害，获得 {exp_delta} 点战斗经验。"
        elif inventory_use_intent:
            (
                summary,
                money_delta,
                hp_delta,
                energy_delta,
                water_delta,
                satiety_delta,
                mood_delta,
                death_protection_delta,
                use_warnings,
            ) = self._resolve_inventory_use(con, group_id, row)
            warnings.extend(use_warnings)
            if purchase_intent:
                (
                    purchase_summary,
                    purchase_money_delta,
                    purchase_hp_delta,
                    purchase_energy_delta,
                    purchase_water_delta,
                    purchase_satiety_delta,
                    purchase_mood_delta,
                    purchase_death_protection_delta,
                ) = self._resolve_purchase(con, group_id, row)
                summary += " " + purchase_summary
                money_delta += purchase_money_delta
                hp_delta += purchase_hp_delta
                energy_delta += purchase_energy_delta
                water_delta += purchase_water_delta
                satiety_delta += purchase_satiety_delta
                mood_delta += purchase_mood_delta
                death_protection_delta += purchase_death_protection_delta
        elif purchase_intent:
            (
                summary,
                money_delta,
                hp_delta,
                energy_delta,
                water_delta,
                satiety_delta,
                mood_delta,
                death_protection_delta,
            ) = self._resolve_purchase(con, group_id, row)
        elif self_heal_intent:
            summary, money_delta, hp_delta, heal_warnings = self._resolve_self_heal(row)
            warnings.extend(heal_warnings)
        elif self._looks_like_rest(text):
            (
                summary,
                money_delta,
                hp_delta,
                energy_delta,
                water_delta,
                satiety_delta,
                mood_delta,
            ) = self._resolve_rest(con, group_id, row, text, location_key)
        elif self._looks_like_work(text):
            gain = random.randint(8, 20)
            money_delta = self._income_with_secondary_bonus(row, gain, text)
            energy_delta = -14
            summary = f"你做了些力所能及的事，获得 {money_delta} 学都币。"
        elif development_intent:
            today = cn_today()
            if str(row["daily_development_date"] or "") == today:
                summary = "你想参加能力开发课程，但今天已经完成过一次正式训练。"
                energy_delta = -4
                mood_delta = -1
            else:
                exp_delta = self._exp_with_trait_bonus(row, self._amount_with_secondary_bonus(row, 50, "study"), "development")
                money_delta = self._income_with_level_bonus(15, row["power_level"])
                energy_delta = -18
                mood_delta = 1
                development_mark = today
                summary = f"你参加了能力开发课程，获得 {exp_delta} 点能力经验和 {money_delta} 学都币。"
        elif battle_intent:
            exp_delta = self._exp_with_trait_bonus(row, self._amount_with_secondary_bonus(row, 20, "physical"), "battle")
            energy_delta = -22
            if pvp_intent:
                damage = self._pvp_self_damage(row, pvp_targets, text)
                hp_delta -= damage
                mood_delta -= 4
                if pvp_targets:
                    target_names = "、".join(str(item.get("game_name") or "") for item in pvp_targets[:3])
                    summary = f"你和{target_names}爆发了正面冲突。能力、体力和临场判断都被拉到危险区间，本轮承受 {damage} 点伤害，获得 {exp_delta} 点战斗经验。{self._conflict_consequence_line(damage)}"
                else:
                    summary = f"你主动卷入真实冲突，本轮承受 {damage} 点伤害，获得 {exp_delta} 点战斗经验。{self._conflict_consequence_line(damage)}"
                warnings.append("真实冲突会造成生命损失；如果继续互殴，可能进入濒死保护或复苏惩罚。")
                warnings.extend(self._conflict_warning_lines(damage))
            else:
                training_damage = self._training_damage(text)
                hp_delta -= training_damage
                summary = f"你进行了一次有接触的实战训练，承受 {training_damage} 点伤害，获得 {exp_delta} 点战斗经验。"
        if self._ability_use_applies(text, battle_intent):
            power_cost = self._power_use_cost(row["power_level"], text)
            energy_delta -= power_cost
            if int(row["energy"]) < 25:
                mood_delta -= 2
                warnings.append("精力不足会影响个人现实演算，能力表现被压低。")
            warnings.append(f"能力使用消耗：精力 -{power_cost}。")
            if battle_intent:
                summary += " " + self._ability_battle_detail(row, text)
        risk_score = self._action_risk_score(text)
        if risk_score:
            energy_delta -= min(8, risk_score * 2)
            if random.random() < min(0.18 + risk_score * 0.09, 0.72):
                injury = random.randint(2 + risk_score, 6 + risk_score * 3) * self.config.risk_damage_multiplier
                hp_delta -= injury
                warnings.append(f"高风险行动造成受伤：生命 -{injury}。")
            if self._mentions_canon_core_secret(text):
                warnings.append("核心机密线索只得到外围痕迹；本轮不会直接揭开暗部或统括理事会真相。")

        new_hp = clamp(int(row["hp"]) + hp_delta)
        new_energy = clamp(int(row["energy"]) + energy_delta)
        new_water = clamp(int(row["water"]) + water_delta)
        new_satiety = clamp(int(row["satiety"]) + satiety_delta)
        new_mood = clamp(int(row["mood"]) + mood_delta)
        new_money = max(0, int(row["money"]) + money_delta)
        new_exp = max(0, int(row["ability_exp"]) + exp_delta)
        new_death_protection = max(0, int(row["death_protection"] or 0) + death_protection_delta)
        task_result = self._resolve_task_and_secondary_growth(row, text, location_key, battle_intent, development_intent)
        reputation_delta = int(task_result.get("reputation", 0))
        physical_exp_delta = int(task_result.get("physical_exp", 0))
        social_exp_delta = int(task_result.get("social_exp", 0))
        study_exp_delta = int(task_result.get("study_exp", 0))
        art_exp_delta = int(task_result.get("art_exp", 0))
        if task_result.get("summary"):
            summary += " " + str(task_result["summary"])
        warnings.extend(str(item) for item in task_result.get("warnings", []) if item)
        if new_water <= 15:
            new_energy = clamp(new_energy - 5)
            warnings.append("水分偏低，精力受到影响。")
        if new_satiety <= 15:
            new_mood = clamp(new_mood - 3)
            warnings.append("饱食度偏低，心情受到影响。")
        if new_hp <= 0:
            if new_death_protection > 0:
                new_death_protection -= 1
                new_hp = 1
                warnings.append("死亡保护卡生效：角色保留 1 点生命，本次不扣除能力经验。")
            else:
                new_hp = 1
                warnings.append("濒死保护：角色保留 1 点生命，本次不扣除能力经验；请尽快休息或治疗。")
        con.execute(
            """
            UPDATE characters SET location_key=?,hp=?,energy=?,water=?,satiety=?,mood=?,money=?,ability_exp=?,reputation=?,physical_exp=?,social_exp=?,study_exp=?,art_exp=?,death_protection=?,daily_development_date=CASE WHEN ?<>'' THEN ? ELSE daily_development_date END,updated_at=? WHERE id=?
            """,
            (
                location_key,
                new_hp,
                new_energy,
                new_water,
                new_satiety,
                new_mood,
                new_money,
                new_exp,
                max(0, int(row["reputation"] or 0) + reputation_delta),
                max(0, int(row["physical_exp"] or 0) + physical_exp_delta),
                max(0, int(row["social_exp"] or 0) + social_exp_delta),
                max(0, int(row["study_exp"] or 0) + study_exp_delta),
                max(0, int(row["art_exp"] or 0) + art_exp_delta),
                new_death_protection,
                development_mark,
                development_mark,
                utc_now_iso(),
                row["character_id"],
            ),
        )
        encounters = self._encounters(con, group_id, location_key, row["character_id"])
        self._small_relationship_changes(con, group_id, row["character_id"], encounters)
        npc_interactions = self._resolve_npc_interactions(con, group_id, row["character_id"], location_key, text, encounters)
        if npc_interactions:
            summary += " " + " ".join(npc_interactions[:2])
        npc_scene = self._npc_scene_reactions(con, group_id, row, location_key, text, encounters, battle_intent)
        if npc_scene:
            summary += " " + " ".join(npc_scene[:2])
        return {
            "action_id": row["id"],
            "character_id": row["character_id"],
            "qq_id": row["qq_id"],
            "game_name": row["game_name"],
            "text": text,
            "accepted": accepted,
            "summary": summary,
            "location_key": location_key,
            "encounters": encounters,
            "warnings": warnings,
            "deltas": {
                "hp": hp_delta,
                "energy": energy_delta,
                "water": water_delta,
                "satiety": satiety_delta,
                "mood": mood_delta,
                "money": money_delta,
                "exp": exp_delta,
                "reputation": reputation_delta,
                "physical_exp": physical_exp_delta,
                "social_exp": social_exp_delta,
                "study_exp": study_exp_delta,
                "art_exp": art_exp_delta,
                "death_protection": death_protection_delta,
            },
            "passive_impacts": [],
        }

    def _resolve_passive_pvp_impacts(
        self,
        con: sqlite3.Connection,
        group_id: str,
        passive_pvp_index: dict[int, list[dict[str, Any]]],
    ) -> list[dict[str, Any]]:
        outcomes: list[dict[str, Any]] = []
        for target_id, attacks in passive_pvp_index.items():
            if not attacks:
                continue
            target = con.execute("SELECT * FROM characters WHERE id=? AND group_id=?", (target_id, group_id)).fetchone()
            if not target:
                continue
            total_hp = 0
            total_energy = 0
            total_mood = 0
            attacker_names: list[str] = []
            for attack in attacks[:4]:
                attacker = attack.get("attacker") or {}
                attacker_names.append(str(attacker.get("game_name") or "某个玩家"))
                damage = self._passive_pvp_damage(target, attacker, str(attack.get("text") or ""))
                total_hp -= damage
                total_energy -= max(4, int(damage * 0.35))
                total_mood -= max(2, int(damage * 0.2))
            if len(attacks) > 4:
                extra = len(attacks) - 4
                total_hp -= extra * 4
                total_energy -= extra * 2
                total_mood -= extra
            new_hp = clamp(int(target["hp"]) + total_hp)
            new_energy = clamp(int(target["energy"]) + total_energy)
            new_mood = clamp(int(target["mood"]) + total_mood)
            warnings = ["你本轮没有主动处理这次冲突，但其他玩家的行动影响到了你。"]
            warnings.extend(self._conflict_warning_lines(abs(total_hp)))
            if new_hp <= 0:
                death_protection = int(target["death_protection"] or 0)
                if death_protection > 0:
                    death_protection -= 1
                    new_hp = 1
                    warnings.append("死亡保护卡生效：本次被动冲突后保留 1 点生命。")
                else:
                    death_protection = 0
                    new_hp = 1
                    warnings.append("你被打到濒死边缘，之后最好尽快治疗或休息。")
                con.execute(
                    "UPDATE characters SET hp=?,energy=?,mood=?,death_protection=?,updated_at=? WHERE id=?",
                    (new_hp, new_energy, new_mood, death_protection, utc_now_iso(), target_id),
                )
            else:
                con.execute(
                    "UPDATE characters SET hp=?,energy=?,mood=?,updated_at=? WHERE id=?",
                    (new_hp, new_energy, new_mood, utc_now_iso(), target_id),
                )
            attacker_text = "、".join(attacker_names[:4])
            if len(attacker_names) > 4:
                attacker_text += f"等 {len(attacker_names)} 人"
            outcomes.append(
                {
                    "action_id": None,
                    "character_id": target_id,
                    "qq_id": target["qq_id"],
                    "game_name": target["game_name"],
                    "text": "",
                    "accepted": True,
                    "summary": f"{attacker_text}的行动波及了你，你被迫卷入冲突并承受了 {abs(total_hp)} 点伤害。{self._conflict_consequence_line(abs(total_hp))}",
                    "location_key": target["location_key"],
                    "encounters": [],
                    "warnings": warnings,
                    "deltas": {
                        "hp": total_hp,
                        "energy": total_energy,
                        "water": 0,
                        "satiety": 0,
                        "mood": total_mood,
                        "money": 0,
                        "exp": 0,
                        "death_protection": 0,
                    },
                    "passive_impacts": [],
                }
            )
        return outcomes

    def _passive_pvp_damage(
        self,
        target: sqlite3.Row,
        attacker: dict[str, Any],
        text: str,
    ) -> int:
        low = max(1, int(self.config.pvp_damage_min * 0.7))
        high = max(low, int(self.config.pvp_damage_max * 0.9))
        attacker_level = self._power_level_value(str(attacker.get("power_level") or ""))
        target_level = self._power_level_value(str(target["power_level"] or ""))
        level_gap = attacker_level - target_level
        low += max(0, level_gap) * 3
        high += max(0, level_gap) * 5
        if int(target["energy"]) < 30:
            low += 2
            high += 5
        if any(word in text for word in ("全力", "下重手", "不留手", "拼命", "生死", "致命")):
            low += 4
            high += 10
        low, high = self._scale_conflict_damage_range(low, high)
        low = max(1, min(95, low))
        high = max(low, min(98, high))
        return random.randint(low, high)

    def _scale_conflict_damage_range(self, low: int, high: int) -> tuple[int, int]:
        percent = int(getattr(self.config, "conflict_damage_multiplier_percent", 100) or 100)
        if percent == 100:
            return low, high
        scaled_low = max(1, round(int(low) * percent / 100))
        scaled_high = max(scaled_low, round(int(high) * percent / 100))
        return scaled_low, scaled_high

    def _conflict_consequence_line(self, damage: int) -> str:
        intensity = int(getattr(self.config, "conflict_narrative_intensity", 2) or 2)
        damage = max(0, int(damage or 0))
        if intensity <= 1:
            if damage >= 35:
                return " 这已经不是普通争执，行动后需要立刻处理伤势。"
            if damage >= 18:
                return " 这次冲突留下了明显伤痛和行动迟滞。"
            return " 这次冲突留下了疼痛和擦伤。"
        if damage >= 50:
            return " 冲击让意识一度发黑，衣物和随身物品被扯乱，必须尽快离开现场并接受治疗。"
        if damage >= 35:
            return " 疼痛、出血和短暂眩晕同时袭来，周围的警备机器人与路人视线已经被吸引过来。"
        if damage >= 18:
            return " 你身上留下明显淤青和破口，呼吸变得急促，继续硬撑会让伤势扩大。"
        return " 疼痛很快从接触点扩散开来，至少留下了擦伤、淤青和狼狈的姿态。"

    def _conflict_warning_lines(self, damage: int) -> list[str]:
        intensity = int(getattr(self.config, "conflict_narrative_intensity", 2) or 2)
        if intensity <= 1:
            return []
        damage = max(0, int(damage or 0))
        if damage >= 50:
            return ["重伤级冲突：建议下一轮优先治疗或撤离；继续战斗很可能触发濒死保护。"]
        if damage >= 35:
            return ["严重受伤：本轮结果会被按真实伤害处理，警备员或风纪委员可能介入后续剧情。"]
        if damage >= 18:
            return ["中度受伤：伤口和疼痛会影响后续行动，建议补给、治疗或休息。"]
        return []

    def _build_public_summary(
        self,
        round_no: int,
        outcomes: list[dict[str, Any]],
        npc_updates: list[str],
        roster: dict[str, list[str]],
        event: dict[str, Any] | None,
        time_context: dict[str, Any] | None = None,
    ) -> str:
        time_context = time_context or self.current_time_context()
        lines = [f"【第 {round_no} 轮学园都市更新】", f"世界时间：{time_context['display']}"]
        if outcomes:
            lines.append(f"{len(outcomes)} 名角色完成了本轮行动。")
        else:
            lines.append("本轮没有收到玩家行动，学园都市按自己的节奏继续运转。")
        crowded = [f"{place}：{', '.join(names[:5])}" for place, names in roster.items() if len(names) >= 2]
        if crowded:
            lines.append("公开可见的聚集点：" + "；".join(crowded[:4]))
        if event:
            lines.append(f"公共事件：{event['title']} - {event['description']}")
        elif npc_updates:
            lines.append("街头传闻：" + random.choice(npc_updates))
        return "\n".join(lines)

    def _build_private_result(
        self,
        con: sqlite3.Connection,
        group_id: str,
        round_no: int,
        outcome: dict[str, Any],
        time_context: dict[str, Any] | None = None,
    ) -> str:
        char = con.execute("SELECT * FROM characters WHERE id=?", (outcome["character_id"],)).fetchone()
        loc = self._location(con, group_id, outcome["location_key"])
        time_context = time_context or self.current_time_context()
        lines = [f"【第 {round_no} 轮个人结果】", f"世界时间：{time_context['display']}", outcome["summary"]]
        if loc:
            lines.append(f"当前位置：{loc['name']}")
        if outcome["encounters"]:
            lines.append("你遇到了：" + "、".join(item["name"] for item in outcome["encounters"][:6]))
        if outcome["warnings"]:
            lines.append("提醒：" + "；".join(outcome["warnings"]))
        if outcome.get("passive_impacts"):
            lines.append("交互影响：")
            for impact in outcome["passive_impacts"][:4]:
                lines.append("- " + str(impact.get("summary") or "你受到了其他玩家行动的影响。"))
        deltas = outcome["deltas"]
        delta_text = "，".join(
            f"{self._delta_label(key)} {value:+d}" for key, value in deltas.items() if value
        )
        if delta_text:
            lines.append("本轮变化：" + delta_text)
        if char:
            lines.append(
                f"状态：生命 {char['hp']}/100，精力 {char['energy']}/100，水分 {char['water']}/100，饱食度 {char['satiety']}/100，心情 {char['mood']}/100，学都币 {char['money']}"
            )
        return "\n".join(lines)

    def _delta_label(self, key: str) -> str:
        return {
            "hp": "生命",
            "energy": "精力",
            "water": "水分",
            "satiety": "饱食度",
            "mood": "心情",
            "money": "学都币",
            "exp": "能力经验",
            "reputation": "声望",
            "physical_exp": "体力经验",
            "social_exp": "社交经验",
            "study_exp": "学业经验",
            "art_exp": "艺术经验",
            "death_protection": "死亡保护",
            "relation": "关系",
        }.get(str(key), str(key))

    def _move_npcs(self, con: sqlite3.Connection, group_id: str) -> list[str]:
        rows = con.execute("SELECT * FROM npcs WHERE group_id=?", (group_id,)).fetchall()
        updates = []
        for npc in rows:
            if self._is_static_or_restricted_npc(npc):
                continue
            expected_key = self._npc_expected_location(con, group_id, npc)
            if expected_key:
                if expected_key == str(npc["location_key"] or ""):
                    continue
                old = self._location(con, group_id, npc["location_key"])
                new = self._location(con, group_id, expected_key)
                old_was_reasonable = self._npc_can_visit(npc, str(npc["location_key"] or ""))
                if new:
                    con.execute("UPDATE npcs SET location_key=?, updated_at=? WHERE id=?", (expected_key, utc_now_iso(), npc["id"]))
                    if old and old_was_reasonable:
                        updates.append(f"{npc['name']}按现实时间从{old['name']}沿正常路线回到{new['name']}")
                continue
            neighbors = con.execute(
                "SELECT to_location_key FROM location_edges WHERE group_id=? AND from_location_key=?",
                (group_id, npc["location_key"]),
            ).fetchall()
            if not neighbors or random.random() > 0.55:
                continue
            candidates = [str(item["to_location_key"]) for item in neighbors if self._npc_can_visit(npc, str(item["to_location_key"]))]
            if not candidates:
                continue
            next_key = random.choice(candidates)
            old = self._location(con, group_id, npc["location_key"])
            new = self._location(con, group_id, next_key)
            con.execute("UPDATE npcs SET location_key=?, updated_at=? WHERE id=?", (next_key, utc_now_iso(), npc["id"]))
            if old and new:
                updates.append(f"{npc['name']}从{old['name']}沿正常路线去了{new['name']}")
        return updates

    def _npc_expected_location(self, con: sqlite3.Connection, group_id: str, npc: sqlite3.Row) -> str:
        hour = int(self.current_time_context()["hour"])
        name = str(npc["name"] or "")
        faction = str(npc["faction"] or "")
        role = str(npc["role"] or "")
        current = str(npc["location_key"] or "")
        if name == "佐天泪子":
            if hour >= 22 or hour < 6:
                return self._npc_routed_target(con, group_id, current, "sakugawa")
            if 8 <= hour < 16:
                return self._npc_routed_target(con, group_id, current, "sakugawa")
        if "常盘台" in faction:
            if hour >= 22 or hour < 6:
                return self._npc_routed_target(con, group_id, current, "gakusha_no_sono")
            if 8 <= hour < 16:
                return self._npc_routed_target(con, group_id, current, "tokiwa_dai")
        if "风纪委员" in faction and 8 <= hour < 20:
            return self._npc_routed_target(con, group_id, current, "judgment_177")
        if "警备员" in faction or "教师" in role:
            if hour >= 20 or hour < 7:
                return self._npc_routed_target(con, group_id, current, "anti_skill_07_hq") if "警备员" in faction else ""
        return ""

    def _npc_routed_target(self, con: sqlite3.Connection, group_id: str, current_key: str, target_key: str) -> str:
        if not target_key or current_key == target_key:
            return target_key
        return target_key if self._movement_path(con, group_id, current_key, target_key) else ""

    def _is_static_or_restricted_npc(self, npc: sqlite3.Row) -> bool:
        return self._npc_should_stay_put(npc)

    def _npc_should_stay_put(self, npc: sqlite3.Row) -> bool:
        npc_key = str(npc["npc_key"] or "") if "npc_key" in npc.keys() else ""
        name = str(npc["name"] or "")
        disposition = str(npc["disposition"] or "")
        faction = str(npc["faction"] or "")
        role = str(npc["role"] or "")
        if npc_key in {
            "heaven_canceller",
            "board_clerk",
            "komoe_tsukuyomi",
            "aiho_yomikawa",
            "tsuzuri_tessou",
        }:
            return True
        if "冥土追魂" in name or "医生" in role or "医疗机构" in faction:
            return True
        if "教师" in role or "警备员" in faction:
            return True
        restricted_words = ("禁区", "高危", "传闻", "危险")
        if any(word in disposition for word in restricted_words):
            return True
        if "统括理事会" in faction or "木原一族" in faction:
            return True
        if "暗部" in faction:
            return True
        if "Level 5" in role and "御坂美琴" not in str(npc["name"] or "") and "食蜂操祈" not in str(npc["name"] or ""):
            return True
        return False

    def _npc_hidden_from_normal_encounter(self, npc: sqlite3.Row) -> bool:
        disposition = str(npc["disposition"] or "")
        faction = str(npc["faction"] or "")
        role = str(npc["role"] or "")
        if any(word in disposition for word in ("禁区", "高危", "传闻", "危险")):
            return True
        if "统括理事会" in faction or "木原一族" in faction:
            return True
        if "暗部" in faction and "边缘" not in faction:
            return True
        if "Level 5" in role and "御坂美琴" not in str(npc["name"] or "") and "食蜂操祈" not in str(npc["name"] or ""):
            return True
        return False

    def _npc_can_visit(self, npc: sqlite3.Row, location_key: str) -> bool:
        name = str(npc["name"] or "")
        faction = str(npc["faction"] or "")
        role = str(npc["role"] or "")
        current = str(npc["location_key"] or "")
        hour = int(self.current_time_context()["hour"])
        if name == "佐天泪子" and location_key in {"tokiwa_dai", "gakusha_no_sono"}:
            return False
        if (hour >= 22 or hour < 6) and "普通学生" in faction and location_key not in {"dorm", "school_gate", "classroom", "sakugawa"}:
            return False
        if (hour >= 22 or hour < 6) and "常盘台" in faction and location_key not in {"gakusha_no_sono", "tokiwa_dai"}:
            return False
        if location_key == current:
            return True
        if "常盘台" in faction and location_key in {"sakugawa", "judgment_177", "seventh_mist", "plaza", "gakusha_no_sono", "tokiwa_dai"}:
            return True
        if "风纪委员" in faction and location_key in {"judgment_177", "plaza", "main_road", "school_gate", "sakugawa", "seventh_mist"}:
            return True
        if "普通学生" in faction and location_key in {"school_gate", "classroom", "dorm", "family_restaurant", "plaza", "main_road", "sakugawa", "seventh_mist"}:
            return not (hour >= 22 or hour < 6) or location_key in {"dorm", "school_gate", "classroom"}
        if "警备员" in faction or "教师" in role:
            return location_key in {"anti_skill_07_hq", "school_gate", "classroom", "main_road", "plaza"}
        return False

    def _consume_next_event(self, con: sqlite3.Connection, group_id: str) -> dict[str, Any] | None:
        row = con.execute(
            "SELECT * FROM event_presets WHERE group_id=? AND trigger_next=1 ORDER BY id LIMIT 1",
            (group_id,),
        ).fetchone()
        if not row:
            return None
        con.execute("UPDATE event_presets SET trigger_next=0, used_at=?, updated_at=? WHERE id=?", (utc_now_iso(), utc_now_iso(), row["id"]))
        return dict(row)

    def _random_event(self, con: sqlite3.Connection, group_id: str) -> dict[str, Any]:
        locations = con.execute("SELECT * FROM locations WHERE group_id=? ORDER BY RANDOM() LIMIT 1", (group_id,)).fetchone()
        loc_name = locations["name"] if locations else "学园都市"
        return {
            "title": "随机公共事件",
            "description": f"{loc_name}附近出现新动向：{random.choice(EVENT_SEEDS)}",
            "effect_json": dumps({"mood": random.choice([-1, 0, 1])}),
        }

    def _apply_event_effect(self, con: sqlite3.Connection, group_id: str, event: dict[str, Any] | sqlite3.Row) -> None:
        effect = loads(str(event.get("effect_json") or "{}") if isinstance(event, dict) else str(event["effect_json"] or "{}"), {})
        if not isinstance(effect, dict):
            return
        allowed = {"hp", "energy", "water", "satiety", "mood", "money"}
        deltas = {key: int_value(effect.get(key), 0) for key in allowed}
        if not any(deltas.values()):
            return
        rows = con.execute("SELECT * FROM characters WHERE group_id=? AND audit_status='approved'", (group_id,)).fetchall()
        for char in rows:
            con.execute(
                """
                UPDATE characters
                SET hp=?, energy=?, water=?, satiety=?, mood=?, money=?, updated_at=?
                WHERE id=?
                """,
                (
                    clamp(char["hp"] + deltas["hp"]),
                    clamp(char["energy"] + deltas["energy"]),
                    clamp(char["water"] + deltas["water"]),
                    clamp(char["satiety"] + deltas["satiety"]),
                    clamp(char["mood"] + deltas["mood"]),
                    max(0, int(char["money"]) + deltas["money"]),
                    utc_now_iso(),
                    char["id"],
                ),
            )
        summary_parts = [f"{key} {value:+d}" for key, value in deltas.items() if value]
        con.execute(
            "INSERT INTO history(group_id,visibility,kind,text,created_at) VALUES(?,?,?,?,?)",
            (group_id, "public", "event_effect", "公共事件影响：" + "，".join(summary_parts), utc_now_iso()),
        )

    def _event_due(self, world: sqlite3.Row) -> bool:
        due = parse_iso(world["next_event_at"])
        return bool(due and due <= utc_now())

    def _apply_hourly_decay(self, con: sqlite3.Connection, group_id: str) -> None:
        rows = con.execute("SELECT * FROM characters WHERE group_id=? AND audit_status='approved'", (group_id,)).fetchall()
        for char in rows:
            water = clamp(char["water"] - random.randint(3, 6))
            satiety = clamp(char["satiety"] - random.randint(2, 5))
            hp = char["hp"]
            energy = char["energy"]
            mood = char["mood"]
            if water <= 10:
                hp = clamp(hp - 2)
            if satiety <= 10:
                energy = clamp(energy - 3)
                mood = clamp(mood - 2)
            con.execute(
                "UPDATE characters SET hp=?,energy=?,water=?,satiety=?,mood=?,updated_at=? WHERE id=?",
                (hp, energy, water, satiety, mood, utc_now_iso(), char["id"]),
            )

    def _scaled_price(self, base_price: Any) -> int:
        base = max(0, int_value(base_price, 0))
        if base <= 0:
            return 0
        percent = max(20, min(500, int(getattr(self.config, "shop_price_multiplier_percent", 100) or 100)))
        return max(1, int(round(base * percent / 100)))

    def _scaled_item_price(self, item: sqlite3.Row | dict[str, Any]) -> int:
        return self._scaled_price(item["price"])

    def _price_multiplier_note(self) -> str:
        percent = int(getattr(self.config, "shop_price_multiplier_percent", 100) or 100)
        return f"（当前物价倍率 {percent}%）" if percent != 100 else ""

    def _resolve_inventory_use(
        self,
        con: sqlite3.Connection,
        group_id: str,
        row: sqlite3.Row,
    ) -> tuple[str, int, int, int, int, int, int, int, list[str]]:
        text = str(row["text"])
        item = self._select_inventory_use_item(con, int(row["character_id"]), group_id, text)
        if not item:
            if self._explicitly_from_inventory(text):
                return "你想使用背包里的物品，但背包中没有识别到对应可用物品。", 0, 0, 0, 0, 0, -1, 0, ["背包物品不存在或数量不足，未自动购买。"]
            return "你想使用随身物品，但没有找到可用的背包物品。", 0, 0, 0, 0, 0, 0, 0, []

        effect = loads(str(item.get("effect_json") or "{}"), {})
        if not isinstance(effect, dict):
            effect = {}
        quantity = int_value(item.get("quantity"), 0)
        if quantity <= 0:
            return f"你想使用{item['name']}，但背包里已经没有可用数量。", 0, 0, 0, 0, 0, -1, 0, ["背包物品数量不足，未自动购买。"]

        con.execute(
            "UPDATE inventory SET quantity=quantity-1 WHERE character_id=? AND item_name=?",
            (row["character_id"], item["name"]),
        )
        name = str(item["name"])
        hp_delta = int_value(effect.get("hp"), 0)
        energy_delta = int_value(effect.get("energy"), 0)
        water_delta = int_value(effect.get("water"), 0)
        satiety_delta = int_value(effect.get("satiety"), 0)
        mood_delta = int_value(effect.get("mood"), 0)
        death_protection_delta = max(0, int_value(effect.get("death_protection"), 0))
        action_word = self._inventory_use_action_word(name, effect, text)
        summary = f"你从背包中{action_word}{name}，没有花费学都币。"
        if hp_delta or energy_delta or water_delta or satiety_delta or mood_delta or death_protection_delta:
            summary += " 背包物品效果已结算。"
        else:
            summary += " 该物品没有直接数值恢复效果，但本轮使用记录已写入。"
        return summary, 0, hp_delta, energy_delta, water_delta, satiety_delta, mood_delta, death_protection_delta, []

    def _select_inventory_use_item(
        self,
        con: sqlite3.Connection,
        character_id: int,
        group_id: str,
        text: str,
    ) -> dict[str, Any] | None:
        rows = con.execute(
            """
            SELECT inventory.item_name AS name, inventory.quantity AS quantity, COALESCE(shop_items.effect_json, '{}') AS effect_json
            FROM inventory
            LEFT JOIN characters ON characters.id=inventory.character_id
            LEFT JOIN shop_items ON shop_items.group_id=characters.group_id AND shop_items.name=inventory.item_name
            WHERE inventory.character_id=? AND inventory.quantity>0
            ORDER BY length(inventory.item_name) DESC
            """,
            (character_id,),
        ).fetchall()
        if not rows:
            return None
        normalized_text = self._normalize_purchase_text(text)
        matches = [dict(row) for row in rows if self._item_purchase_matches(str(row["name"]), normalized_text)]
        if matches:
            return matches[0]
        if self._explicitly_from_inventory(text):
            categories = self._inventory_use_categories_from_text(text)
            for row in rows:
                row_dict = dict(row)
                if self._inventory_item_matches_categories(row_dict, categories):
                    return row_dict
        return None

    def _looks_like_inventory_use(self, con: sqlite3.Connection, character_id: int, text: str) -> bool:
        if self._looks_like_transfer(text) or self._looks_like_theft_transfer(text):
            return False
        if self._explicit_purchase_text(text) and not self._explicitly_from_inventory(text):
            return False
        use_words = ("吃", "喝", "食用", "饮用", "使用", "用掉", "消耗", "打开", "服用", "拿出", "从背包", "背包里", "已有", "随身")
        if not any(word in text for word in use_words):
            return False
        if self._explicitly_from_inventory(text):
            return True
        return self._select_inventory_use_item(con, character_id, "", text) is not None

    def _explicit_purchase_text(self, text: str) -> bool:
        return any(word in text or word in text.lower() for word in ("买", "购买", "领取", "换取", "兑换", "补给", "点餐", "购物", "消费", "付款", "结账", "buy", "来一份"))

    def _explicitly_from_inventory(self, text: str) -> bool:
        return self._explicit_inventory_source(text)

    def _explicit_inventory_source(self, text: str) -> bool:
        source_words = ("背包里", "包里", "已有", "现有", "随身", "库存", "带着的", "拿出", "掏出", "用掉", "消耗", "从背包")
        if not any(word in text for word in source_words):
            return False
        check_text = text
        if self._explicit_inventory_destination(text):
            check_text = re.sub(r"(放|塞|装|存|收入|收进|放进|放到|装进|装到|存进|存到).{0,8}(背包里|背包|包里|包中|随身)", "", text)
        return any(word in check_text for word in source_words)

    def _explicit_inventory_destination(self, text: str) -> bool:
        return bool(re.search(r"(放|塞|装|存|收入|收进|放进|放到|装进|装到|存进|存到).{0,8}(背包|包里|包中|随身)", text))

    def _has_purchase_intent_alongside_inventory(self, text: str) -> bool:
        if not self._explicit_purchase_text(text):
            return False
        return self._explicit_inventory_source(text) or self._explicit_inventory_destination(text)

    def _inventory_use_categories_from_text(self, text: str) -> set[str]:
        categories: set[str] = set()
        if any(word in text for word in ("吃", "食用", "饭", "餐", "饱", "饿")):
            categories.add("food")
        if any(word in text for word in ("喝", "饮用", "水", "渴", "饮料", "补水")):
            categories.add("water")
        if any(word in text for word in ("包扎", "治疗", "疗伤", "绷带", "药", "凝胶", "创可贴")):
            categories.add("heal")
        if any(word in text for word in ("车票", "通勤", "地铁", "一日券")):
            categories.add("travel")
        if any(word in text for word in ("定位", "查询", "检索", "资料")):
            categories.add("info")
        return categories

    def _inventory_item_matches_categories(self, item: dict[str, Any], categories: set[str]) -> bool:
        if not categories:
            return False
        effect = loads(str(item.get("effect_json") or "{}"), {})
        if not isinstance(effect, dict):
            effect = {}
        name = str(item.get("name") or "")
        item_categories: set[str] = set()
        if int_value(effect.get("satiety"), 0) > 0:
            item_categories.add("food")
        if int_value(effect.get("water"), 0) > 0:
            item_categories.add("water")
        if int_value(effect.get("hp"), 0) > 0 or any(word in name for word in ("绷带", "凝胶", "医疗", "创可贴")):
            item_categories.add("heal")
        if any(word in name for word in ("地下铁", "通勤", "一日券", "车票", "交通券")):
            item_categories.add("travel")
        if any(word in name for word in ("资料", "检索", "定位")):
            item_categories.add("info")
        return bool(item_categories & categories)

    def _inventory_use_action_word(self, item_name: str, effect: dict[str, Any], text: str) -> str:
        if any(word in text for word in ("喝", "饮用")) or int_value(effect.get("water"), 0) > int_value(effect.get("satiety"), 0):
            return "喝下"
        if any(word in text for word in ("吃", "食用")) or int_value(effect.get("satiety"), 0) > 0:
            return "吃掉"
        if any(word in text for word in ("包扎", "治疗", "疗伤")) or int_value(effect.get("hp"), 0) > 0:
            return "使用"
        return "使用"

    def _resolve_purchase(self, con: sqlite3.Connection, group_id: str, row: sqlite3.Row) -> tuple[str, int, int, int, int, int, int, int]:
        items = con.execute(
            "SELECT * FROM shop_items WHERE group_id=? AND is_active=1 ORDER BY length(name) DESC, price ASC",
            (group_id,),
        ).fetchall()
        text = str(row["text"])
        purchase_text = self._purchase_context_text(text)
        store_only = self._explicit_inventory_destination(text) and not self._purchase_text_implies_immediate_use(purchase_text)
        selections = self._select_purchase_items(items, purchase_text, int(row["money"]))
        if not selections:
            daily_purchase = self._resolve_daily_purchase(purchase_text, int(row["money"]))
            if daily_purchase:
                return daily_purchase
            return "你想购买东西，但没说清楚要买什么。", 0, 0, 0, 0, 0, 0, 0
        current_money = int(row["money"])
        purchased: list[sqlite3.Row] = []
        skipped: list[str] = []
        hp_delta = 0
        energy_delta = 0
        water_delta = 0
        satiety_delta = 0
        mood_delta = 0
        death_protection_delta = 0
        money_delta = 0
        for selected in selections[:4]:
            price = self._scaled_item_price(selected)
            if int(selected["stock"]) == 0:
                skipped.append(f"{selected['name']}售罄")
                continue
            if price > current_money:
                skipped.append(f"{selected['name']}余额不足（需要 {price}）")
                continue
            effect = loads(selected["effect_json"], {})
            if not isinstance(effect, dict):
                effect = {}
            if int(selected["stock"]) > 0:
                con.execute("UPDATE shop_items SET stock=stock-1, updated_at=? WHERE id=?", (utc_now_iso(), selected["id"]))
            con.execute(
                """
                INSERT INTO inventory(character_id,item_name,quantity,meta_json) VALUES(?,?,?,?)
                ON CONFLICT(character_id,item_name) DO UPDATE SET quantity=quantity+excluded.quantity
                """,
                (row["character_id"], selected["name"], 1, "{}"),
            )
            current_money -= price
            money_delta -= price
            purchased.append(selected)
            if not store_only:
                water_delta += int_value(effect.get("water"), 0)
                satiety_delta += int_value(effect.get("satiety"), 0)
                hp_delta += int_value(effect.get("hp"), 0)
                energy_delta += int_value(effect.get("energy"), 0)
                mood_delta += int_value(effect.get("mood"), 0)
                death_protection_delta += max(0, int_value(effect.get("death_protection"), 0))
        if not purchased:
            return "你想购买东西，但" + "、".join(skipped or ["没有可购买的商品"]) + "。", 0, 0, 0, -3, -2, 0, 0
        names = "、".join(str(item["name"]) for item in purchased)
        skipped_text = f"；未完成：{'、'.join(skipped)}" if skipped else ""
        note = self._price_multiplier_note()
        storage_note = "，本轮按备用物资处理，未立即食用或饮用" if store_only else ""
        return (
            f"你购买了{names}，共花费 {-money_delta} 学都币{note}，物品已放入背包{storage_note}{skipped_text}。",
            money_delta,
            hp_delta,
            energy_delta,
            water_delta,
            satiety_delta,
            mood_delta,
            death_protection_delta,
        )

    def _resolve_daily_purchase(self, text: str, money: int) -> tuple[str, int, int, int, int, int, int, int] | None:
        daily = self._daily_purchase_profile(text)
        if not daily:
            return None
        name, base_price, water, satiety, energy, mood = daily
        price = self._scaled_price(base_price)
        if money < price:
            return f"你想购买{name}，但余额不足（需要 {price} 学都币）。", 0, 0, 0, 0, 0, 0, 0
        note = self._price_multiplier_note()
        return (
            f"你购买了{name}，花费 {price} 学都币{note}。该类日用品按普通生活消费处理，没有额外放入背包。",
            -price,
            0,
            energy,
            water,
            satiety,
            mood,
            0,
        )

    def _daily_purchase_profile(self, text: str) -> tuple[str, int, int, int, int, int] | None:
        if not self._purchase_item_mentioned_with_intent_text(text) and not any(word in text for word in ("吃", "喝", "点", "来一份")):
            return None
        profiles = (
            (("拉面", "面条", "热汤面"), "拉面", 28, 35, 100, 0, 2),
            (("套餐", "定食", "午餐", "晚餐", "早餐", "吃饭", "饭"), "普通餐食", 25, 20, 100, 0, 1),
            (("面包", "饭团", "三明治", "轻食"), "轻食", 12, 5, 55, 0, 1),
            (("咖啡", "奶茶", "饮料", "果汁", "茶"), "饮料", 12, 65, 0, 5, 1),
            (("水", "矿泉水", "瓶装水", "饮用水"), "饮用水", 6, 100, 0, 0, 0),
        )
        for triggers, name, price, water, satiety, energy, mood in profiles:
            if any(word in text for word in triggers):
                return name, price, water, satiety, energy, mood
        return None

    def _purchase_context_text(self, text: str) -> str:
        text = str(text or "")
        if not self._explicit_inventory_source(text):
            return text
        protected_spans = self._inventory_use_spans(text)
        if not protected_spans:
            return text
        chunks: list[str] = []
        cursor = 0
        for start, end in protected_spans:
            chunks.append(text[cursor:start])
            cursor = end
        chunks.append(text[cursor:])
        cleaned = re.sub(r"(并|然后|再|顺便)$", "", "".join(chunks).strip()).strip()
        return cleaned or text

    def _inventory_use_spans(self, text: str) -> list[tuple[int, int]]:
        protected_spans: list[tuple[int, int]] = []
        source_pattern = r"(背包里|包里|已有|现有|随身|库存|带着的|从背包|拿出|掏出|用掉|消耗)"
        use_pattern = r"(吃|喝|食用|饮用|使用|服用|包扎|治疗|用掉|消耗|拿出|掏出)"
        for match in re.finditer(source_pattern, text):
            source_start, source_end = match.span()
            left_candidates: list[int] = []
            for sep in ("，", ",", "。", "；", ";", "然后", "再", "顺便", "并"):
                index = text.rfind(sep, 0, source_start)
                if index >= 0:
                    left_candidates.append(index + len(sep))
            left_bound = max(left_candidates, default=0)
            right_candidates = [
                index
                for sep in ("，", ",", "。", "；", ";", "然后", "再", "顺便", "并")
                for index in [text.find(sep, source_end)]
                if index >= 0
            ]
            right_bound = min(right_candidates) if right_candidates else len(text)
            segment = text[left_bound:right_bound]
            if re.search(use_pattern, segment):
                protected_spans.append((left_bound, right_bound))
        if not protected_spans:
            return []
        protected_spans.sort()
        merged: list[tuple[int, int]] = []
        for start, end in protected_spans:
            if merged and start <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(merged[-1][1], end))
            else:
                merged.append((start, end))
        return merged

    def _purchase_text_implies_immediate_use(self, text: str) -> bool:
        return any(word in str(text or "") for word in ("吃", "喝", "食用", "饮用", "用餐", "点餐", "来一份", "直接用", "马上用", "当场"))

    def _select_purchase_items(self, items: list[sqlite3.Row], text: str, money: int) -> list[sqlite3.Row]:
        explicit = self._explicit_purchase_items(items, text)
        if explicit:
            selected: list[sqlite3.Row] = []
            seen: set[int] = set()
            satisfied_categories: set[str] = set()
            remaining_money = int(money)
            for item in explicit[:4]:
                selected.append(item)
                seen.add(int(item["id"]))
                satisfied_categories.update(self._purchase_item_categories(item))
                remaining_money -= self._scaled_item_price(item)
            category_items = self._select_purchase_categories(items, text, remaining_money, seen, satisfied_categories)
            return [*selected, *category_items][:4]
        category_items = self._select_purchase_categories(items, text, money)
        if category_items:
            return category_items[:4]
        selected = self._select_purchase_item(items, text, money)
        return [selected] if selected else []

    def _select_purchase_categories(
        self,
        items: list[sqlite3.Row],
        text: str,
        money: int,
        excluded_ids: set[int] | None = None,
        satisfied_categories: set[str] | None = None,
    ) -> list[sqlite3.Row]:
        normalized_text = self._normalize_purchase_text(text)
        satisfied = set(satisfied_categories or set())
        category_rules = (
            (
                ("food", "食物", "吃的", "饭", "餐", "便当", "午餐", "晚餐", "早餐", "热餐", "拉面", "面"),
                "food",
                ("拉面", "便当", "套餐", "午餐", "折扣券", "果冻"),
            ),
            (
                ("water", "水", "饮用水", "矿泉水", "瓶装水", "饮料", "喝的", "补水"),
                "water",
                ("矿泉水", "瓶装水", "饮用水", "饮料", "果冻"),
            ),
            (
                ("heal", "药", "绷带", "创可贴", "医疗用品", "治疗用品"),
                "heal",
                ("绷带", "凝胶", "医疗"),
            ),
            (
                ("travel", "车票", "通勤", "地铁票", "一日券", "交通券"),
                "travel",
                ("地下铁", "通勤", "一日券", "车票"),
            ),
        )
        selected: list[sqlite3.Row] = []
        remaining_money = int(money)
        seen: set[int] = set(excluded_ids or set())
        for triggers, category, hints in category_rules:
            if category in satisfied:
                continue
            if not any(word in normalized_text for word in triggers):
                continue
            candidates = [
                item
                for item in items
                if int(item["stock"]) != 0
                and self._scaled_item_price(item) <= remaining_money
                and int(item["id"]) not in seen
                and category in self._purchase_item_categories(item)
                and any(hint in item["name"] for hint in hints)
            ]
            if not candidates:
                continue
            item = sorted(candidates, key=lambda candidate: self._purchase_item_score(candidate, hints))[0]
            selected.append(item)
            seen.add(int(item["id"]))
            satisfied.add(category)
            remaining_money -= self._scaled_item_price(item)
        return selected

    def _purchase_item_categories(self, item: sqlite3.Row) -> set[str]:
        effect = loads(str(item["effect_json"] or "{}"), {})
        if not isinstance(effect, dict):
            effect = {}
        name = str(item["name"] or "")
        categories: set[str] = set()
        if int_value(effect.get("satiety"), 0) > 0:
            categories.add("food")
        if int_value(effect.get("water"), 0) > 0:
            categories.add("water")
        if int_value(effect.get("hp"), 0) > 0 or "医疗" in name or "绷带" in name:
            categories.add("heal")
        if any(word in name for word in ("地下铁", "通勤", "一日券", "车票", "交通券")):
            categories.add("travel")
        return categories

    def _explicit_purchase_items(self, items: list[sqlite3.Row], text: str) -> list[sqlite3.Row]:
        normalized_text = self._normalize_purchase_text(text)
        matches: list[sqlite3.Row] = []
        seen: set[int] = set()
        for item in items:
            if int(item["stock"]) == 0:
                continue
            if self._item_purchase_matches(item["name"], normalized_text):
                item_id = int(item["id"])
                if item_id not in seen:
                    matches.append(item)
                    seen.add(item_id)
        if len(matches) >= 2:
            return sorted(matches, key=lambda item: normalized_text.find(self._normalize_purchase_text(str(item["name"] or ""))))
        return matches

    def _select_purchase_item(self, items: list[sqlite3.Row], text: str, money: int) -> sqlite3.Row | None:
        lower_text = self._normalize_purchase_text(text).lower()
        explicit_intents = ("买", "购买", "拿取", "领取", "换取", "兑换", "补给", "付款", "结账", "buy")
        if any(word in text or word in lower_text for word in explicit_intents):
            for item in items:
                if self._item_purchase_matches(item["name"], text):
                    return item
        travel_ticket_words = (
            "地铁票",
            "地下铁票",
            "通勤票",
            "通勤券",
            "通勤一日券",
            "地铁券",
            "地下铁券",
            "地铁一日券",
            "地下铁一日券",
            "一日券",
            "车票",
            "乘车券",
        )
        if any(word in text for word in travel_ticket_words):
            hints = ("地下铁", "通勤", "一日券", "通行证", "车票")
            candidates = [
                item
                for item in items
                if int(item["stock"]) != 0
                and self._scaled_item_price(item) <= money
                and any(hint in item["name"] for hint in hints)
            ]
            if candidates:
                return sorted(candidates, key=lambda item: self._purchase_item_score(item, hints))[0]
        if self._purchase_item_mentioned_with_intent_text(text):
            for item in items:
                if int(item["stock"]) != 0 and self._scaled_item_price(item) <= money and self._item_purchase_matches(item["name"], text):
                    return item

        keyword_groups = (
            (self._purchase_intent_words("food"), ("拉面", "便当", "套餐", "午餐", "折扣券", "果冻")),
            (self._purchase_intent_words("water"), ("矿泉水", "瓶装水", "饮用水", "水", "饮料", "果冻")),
            (self._purchase_intent_words("heal"), ("绷带", "凝胶", "医疗")),
            (self._purchase_intent_words("info"), ("书库", "检索", "资料卡", "点数")),
        )
        for triggers, name_hints in keyword_groups:
            if not any(word in text for word in triggers):
                continue
            candidates = [
                item
                for item in items
                if int(item["stock"]) != 0
                and self._scaled_item_price(item) <= money
                and any(hint in item["name"] for hint in name_hints)
            ]
            if candidates:
                return sorted(candidates, key=lambda item: self._purchase_item_score(item, name_hints))[0]
        return None

    def _purchase_item_score(self, item: sqlite3.Row, name_hints: tuple[str, ...]) -> tuple[int, int, int]:
        name = str(item["name"] or "")
        effect = loads(str(item["effect_json"] or "{}"), {})
        if not isinstance(effect, dict):
            effect = {}
        matched_hint = next((index for index, hint in enumerate(name_hints) if hint in name), len(name_hints))
        recovery = sum(int_value(effect.get(key), 0) for key in ("satiety", "water", "hp", "energy"))
        return (matched_hint, -recovery, self._scaled_item_price(item))

    def _normalize_purchase_text(self, text: str) -> str:
        text = str(text or "")
        aliases = (
            ("饮用水", "矿泉水"),
            ("瓶装水", "矿泉水"),
            ("一瓶水", "矿泉水"),
            ("瓶水", "矿泉水"),
            ("学生便当", "学生便当"),
            ("便当", "学生便当"),
            ("吃的", "食物"),
            ("饭", "食物"),
            ("热餐", "拉面"),
            ("面条", "拉面"),
            ("备用电池", "便携终端电池"),
            ("终端电池", "便携终端电池"),
            ("电池包", "便携终端电池"),
            ("创可贴", "便携绷带"),
            ("绷带", "便携绷带"),
            ("地铁一日券", "地下铁一日券"),
            ("地铁票", "地下铁一日券"),
            ("地铁券", "地下铁一日券"),
            ("通勤一日券", "通勤一日券"),
            ("通勤票", "通勤一日券"),
        )
        for source, target in aliases:
            text = text.replace(source, target)
        return text

    def _item_purchase_matches(self, item_name: str, text: str) -> bool:
        normalized_text = self._normalize_purchase_text(text)
        normalized_name = self._normalize_purchase_text(item_name)
        return normalized_name in normalized_text or item_name in normalized_text

    def _purchase_intent_words(self, category: str = "") -> tuple[str, ...]:
        groups = {
            "food": ("吃饭", "点餐", "用餐", "午餐", "晚餐", "早餐", "热餐", "买饭", "买便当", "要便当", "要套餐", "拉面", "食物", "饿"),
            "water": ("喝水", "饮水", "补水", "口渴", "喝饮料", "补充饮料", "买水", "要水", "要饮料"),
            "heal": ("绷带", "凝胶", "药", "医疗用品"),
            "travel": ("通勤", "地铁", "公交", "单轨", "车票"),
            "info": ("书库", "检索", "资料卡", "查询点数"),
        }
        if category:
            return groups.get(category, ())
        merged: list[str] = []
        for words in groups.values():
            merged.extend(words)
        return tuple(merged)

    def _clean_traits_json(self, value: Any) -> str:
        if isinstance(value, str):
            parsed = loads(value, [])
        else:
            parsed = value
        if not isinstance(parsed, list):
            parsed = []
        cleaned: list[dict[str, Any]] = []
        for item in parsed[:12]:
            if isinstance(item, str):
                name = self.clean_text(item, 40)
                if name:
                    cleaned.append({"name": name})
                continue
            if not isinstance(item, dict):
                continue
            name = self.clean_text(str(item.get("name") or item.get("title") or ""), 40)
            if not name:
                continue
            cleaned.append({
                "name": name,
                "type": self.clean_text(str(item.get("type") or ""), 30),
                "bonus": max(0, min(100, int_value(item.get("bonus"), 0))),
            })
        return dumps(cleaned)

    def _traits_text(self, raw: str) -> str:
        traits = loads(str(raw or "[]"), [])
        if not isinstance(traits, list) or not traits:
            return "无"
        names = []
        for item in traits[:6]:
            if isinstance(item, str):
                names.append(item)
            elif isinstance(item, dict):
                bonus = int_value(item.get("bonus"), 0)
                suffix = f"+{bonus}%" if bonus else ""
                names.append(f"{item.get('name') or '未命名词条'}{suffix}")
        return "、".join(names) if names else "无"

    def _level_number(self, power_level: str) -> int:
        match = re.search(r"(?:level|lv)\.?\s*([0-5])", str(power_level or ""), re.I)
        return int(match.group(1)) if match else 3

    def _next_level_exp(self, power_level: str) -> int:
        thresholds = {0: 50, 1: 100, 2: 500, 3: 1500, 4: 5000, 5: 20000}
        return thresholds.get(self._level_number(power_level), 1500)

    def _income_with_level_bonus(self, amount: int, power_level: str) -> int:
        level = self._level_number(power_level)
        return int(round(max(0, amount) * (1 + level * 0.1)))

    def _secondary_exp_bonus_percent(self, row: sqlite3.Row | dict[str, Any], key: str) -> int:
        value = int_value(row[key] if isinstance(row, sqlite3.Row) and key in row.keys() else (row.get(key) if isinstance(row, dict) else 0), 0)
        return max(0, min(35, value // 40))

    def _amount_with_secondary_bonus(self, row: sqlite3.Row | dict[str, Any], amount: int, category: str) -> int:
        key_map = {
            "physical": "physical_exp",
            "social": "social_exp",
            "study": "study_exp",
            "art": "art_exp",
        }
        key = key_map.get(category, "")
        if not key:
            return max(0, int(amount))
        bonus = self._secondary_exp_bonus_percent(row, key)
        return int(round(max(0, int(amount)) * (1 + bonus / 100)))

    def _income_with_secondary_bonus(self, row: sqlite3.Row, amount: int, text: str) -> int:
        base = self._income_with_level_bonus(amount, row["power_level"])
        bonus = self._secondary_exp_bonus_percent(row, "physical_exp") // 2
        if any(word in text for word in ("服务", "接待", "销售", "谈判", "跑腿", "委托")):
            bonus += self._secondary_exp_bonus_percent(row, "social_exp")
        if any(word in text for word in ("音乐", "演奏", "唱歌", "绘画", "摄影", "表演", "手工", "美术")):
            bonus += self._secondary_exp_bonus_percent(row, "art_exp")
        return int(round(base * (1 + min(50, bonus) / 100)))

    def _daily_income_estimate(self, power_level: str) -> int:
        return self._income_with_level_bonus(70, power_level)

    def _reputation_label(self, reputation: int) -> str:
        if reputation >= 180:
            return "Lv5 可靠人物"
        if reputation >= 100:
            return "Lv4 值得信任"
        if reputation >= 45:
            return "Lv3 有名学生"
        if reputation >= 15:
            return "Lv2 略有口碑"
        return "Lv1 普通"

    def _daily_task_hint(self, char: sqlite3.Row | dict[str, Any]) -> str:
        identity = str(char["identity"] if isinstance(char, sqlite3.Row) else char.get("identity", ""))
        faction = str(char["faction"] if isinstance(char, sqlite3.Row) and "faction" in char.keys() else (char.get("faction", "") if isinstance(char, dict) else ""))
        identity_text = f"{identity} {faction}"
        location_key = str(char["location_key"] if isinstance(char, sqlite3.Row) else char.get("location_key", ""))
        hour = int(self.current_time_context()["hour"])
        if 8 <= hour < 16 and self._identity_matches_school(identity_text, "any") and location_key not in {"classroom", "tokiwa_dai", "sakugawa", "gakusha_no_sono"}:
            return "上课时段，建议前往所属学校或课程地点。"
        if 22 <= hour or hour < 6:
            if self._identity_matches_school(identity_text, "tokiwadai") and location_key not in {"gakusha_no_sono", "tokiwa_dai"}:
                return "夜间应回到学舍之园或常盘台相关宿舍，晚归会影响声望。"
            if self._identity_matches_school(identity_text, "any") and location_key not in {"dorm", "school_gate", "classroom", "gakusha_no_sono", "tokiwa_dai", "sakugawa"}:
                return "夜间建议回宿舍或学校附近，长期滞留街区会影响声望。"
        if "风纪委员" in identity_text or "Judgment" in identity_text:
            return "可接取巡逻、失物、寻人或学生纠纷任务。"
        if "研究" in identity_text or "实习" in identity_text:
            return "可接取公开研究记录、设备维护或资料整理任务。"
        return "按身份行动可获得声望或对应扩展经验。"

    def _identity_task_suggestions(self, identity: str, faction: str = "") -> list[str]:
        text = f"{identity} {faction}"
        tasks: list[str] = []
        if self._identity_matches_school(text, "tokiwadai"):
            tasks.extend([
                "按时参加常盘台/学舍之园课程或能力测定，可获得学业经验和少量声望。",
                "夜间回到学舍之园或常盘台相关宿舍，避免晚归带来的声望损失。",
                "参与派阀、茶会、学生纠纷调停等社交行动，可获得社交经验。",
            ])
        elif self._identity_matches_school(text, "sakugawa"):
            tasks.extend([
                "前往栅川中学上课、社团或打听学生传闻，可获得学业/社交经验。",
                "与佐天泪子、初春饰利等日常线 NPC 正常交流，可能获得公开线索。",
            ])
        elif self._identity_matches_school(text, "kamijou"):
            tasks.extend([
                "前往上条的高中上课、补习或完成能力开发课程，可获得学业经验。",
                "放学后在家庭餐厅、学生寮、公共广场等地点接触日常事件。",
            ])
        elif self._identity_matches_school(text, "any"):
            tasks.extend([
                "上课时段前往所属学校或课程地点，完成学习、补习或能力开发。",
                "夜间回宿舍或学校附近，长期滞留街区会影响声望。",
            ])
        if any(word in text for word in ("风纪委员", "Judgment")):
            tasks.extend([
                "在风纪委员支部接取巡逻、失物、寻人或学生纠纷任务，可提升声望。",
                "遇到冲突时可选择介入维持秩序，但高风险事件会消耗更多精力。",
            ])
        if any(word in text for word in ("警备员", "Anti-Skill")):
            tasks.extend([
                "前往警备员第七学区本部登记巡逻、训练或处理报案。",
                "大型冲突或公共事件中可按权限协助封锁、疏散和记录。",
            ])
        if any(word in text for word in ("研究", "实习", "实验室", "研究所")):
            tasks.extend([
                "在研究所外围登记处整理公开记录、设备维护或能力数据，可获得学业经验。",
                "高权限研究线索只能从外围调查，不会直接绕过封锁。",
            ])
        if any(word in text for word in ("Skill-Out", "武装无能力", "暗部边缘")):
            tasks.extend([
                "可接触街区传闻、跑腿委托或低层交易，但抢夺和越权会触发反作弊或冲突判定。",
            ])
        if not tasks:
            tasks.extend([
                "按身份选择上课、打工、巡逻、调查、社交、训练或休息，都能触发对应成长。",
                "和玩家或 NPC 互动时写清对象、地点、态度和目的，结算反馈会更稳定。",
            ])
        return tasks

    def _growth_task_suggestions(self, char: sqlite3.Row | dict[str, Any]) -> list[str]:
        get = char.__getitem__ if isinstance(char, sqlite3.Row) else char.get
        physical = int_value(get("physical_exp"), 0)
        social = int_value(get("social_exp"), 0)
        study = int_value(get("study_exp"), 0)
        art = int_value(get("art_exp"), 0)
        lowest = sorted(
            [
                ("体力", physical, "训练、跑步、巡逻、实战或运动类行动会增加体力经验；战斗时可提供轻微抗压加成。"),
                ("社交", social, "聊天、合作、支援、委托、谈判和 NPC 互动会增加社交经验；互动反馈会更顺。"),
                ("学业", study, "上课、自习、补习、能力开发、公开资料整理会增加学业经验；研究和课程收益更好。"),
                ("艺术", art, "音乐、绘画、摄影、表演、手工等行动会增加艺术经验；可影响兼职收入和部分 NPC 互动。"),
            ],
            key=lambda item: item[1],
        )
        suggestions = [item[2] for item in lowest[:3]]
        suggestions.append(f"日常收入参考：普通学生每天约 {self._daily_income_estimate(str(get('power_level') or 'Level 3'))} 学都币；能力等级、体力、社交和艺术经验会略微影响打工收益。")
        return suggestions

    def _resolve_task_and_secondary_growth(
        self,
        row: sqlite3.Row,
        text: str,
        location_key: str,
        battle_intent: bool,
        development_intent: bool,
    ) -> dict[str, Any]:
        result: dict[str, Any] = {
            "summary": "",
            "warnings": [],
            "reputation": 0,
            "physical_exp": 0,
            "social_exp": 0,
            "study_exp": 0,
            "art_exp": 0,
        }
        identity = f"{row['identity'] or ''} {row['faction'] or ''}"
        hour = int(self.current_time_context()["hour"])
        if self._looks_like_study_task(text) or development_intent:
            result["study_exp"] += 10
            if self._identity_matches_school(identity, "any"):
                result["reputation"] += 1
                result["summary"] = "你完成了符合学生身份的学习/课程安排，声望小幅提升。"
        if battle_intent or any(word in text for word in ("训练", "跑步", "锻炼", "体能", "运动", "巡逻")):
            result["physical_exp"] += 8 if battle_intent else 5
        if self._looks_like_social_interaction(text) or self._looks_like_npc_interaction(text):
            result["social_exp"] += 6
        if any(word in text for word in ("音乐", "演奏", "唱歌", "绘画", "画画", "摄影", "手工", "美术", "舞台", "表演")):
            result["art_exp"] += 8
        if any(word in text for word in ("巡逻", "失物", "寻人", "报案", "维持秩序", "帮助路人")):
            result["reputation"] += 2
            if not result["summary"]:
                result["summary"] = "你完成了有公开价值的协助行动，周围对你的评价略有提高。"
        if (22 <= hour or hour < 6) and self._identity_matches_school(identity, "any"):
            if location_key not in {"dorm", "school_gate", "classroom", "gakusha_no_sono", "tokiwa_dai", "sakugawa"}:
                result["reputation"] -= 1
                result["warnings"].append("夜间未回宿舍或学校附近，校方/宿舍管理对你的评价略受影响。")
        return result

    def _looks_like_study_task(self, text: str) -> bool:
        return any(word in text for word in ("上课", "听课", "补习", "学习", "自习", "作业", "课程", "考试", "能力开发课", "实验课"))

    def _exp_with_trait_bonus(self, row: sqlite3.Row, amount: int, kind: str) -> int:
        bonus = 0
        traits = loads(str(row["traits_json"] or "[]"), [])
        if isinstance(traits, list):
            for item in traits:
                if not isinstance(item, dict):
                    continue
                trait_type = str(item.get("type") or "")
                if trait_type in {kind, "exp", "all"}:
                    bonus += int_value(item.get("bonus"), 0)
        return int(round(max(0, amount) * (1 + min(bonus, 200) / 100)))

    def _location(self, con: sqlite3.Connection, group_id: str, key: str) -> sqlite3.Row | None:
        return con.execute("SELECT * FROM locations WHERE group_id=? AND location_key=?", (group_id, key)).fetchone()

    def _validate_player_account_owner(
        self,
        con: sqlite3.Connection,
        game_name: str,
        qq_id: str,
        character_id: int | None = None,
    ) -> None:
        existing = con.execute(
            """
            SELECT characters.id, characters.qq_id
            FROM characters
            JOIN users ON users.id=characters.user_id
            WHERE users.username=?
            """,
            (game_name,),
        ).fetchone()
        if existing and str(existing["qq_id"]) != str(qq_id) and int(existing["id"]) != int(character_id or 0):
            raise ValueError("这个游戏名对应的前端账号已被其他 QQ 使用。")

    def _neighbor_names(self, con: sqlite3.Connection, group_id: str, key: str) -> list[str]:
        return [
            row["name"]
            for row in con.execute(
                """
                SELECT locations.name FROM location_edges
                JOIN locations ON locations.group_id=location_edges.group_id AND locations.location_key=location_edges.to_location_key
                WHERE location_edges.group_id=? AND location_edges.from_location_key=?
                ORDER BY locations.sort_order
                """,
                (group_id, key),
            ).fetchall()
        ]

    def _can_move(self, con: sqlite3.Connection, group_id: str, from_key: str, to_key: str) -> bool:
        if from_key == to_key:
            return True
        return bool(con.execute(
            "SELECT 1 FROM location_edges WHERE group_id=? AND from_location_key=? AND to_location_key=?",
            (group_id, from_key, to_key),
        ).fetchone())

    def _movement_path(self, con: sqlite3.Connection, group_id: str, from_key: str, to_key: str) -> list[str]:
        max_steps = int(getattr(self.config, "max_move_steps", 1) or 0)
        if max_steps <= 0:
            return [from_key] if from_key == to_key else []
        if from_key == to_key:
            return [from_key]
        edges = con.execute(
            "SELECT from_location_key,to_location_key FROM location_edges WHERE group_id=?",
            (group_id,),
        ).fetchall()
        graph: dict[str, list[str]] = defaultdict(list)
        for edge in edges:
            graph[str(edge["from_location_key"])].append(str(edge["to_location_key"]))
        queue: list[list[str]] = [[from_key]]
        seen = {from_key}
        while queue:
            path = queue.pop(0)
            if len(path) - 1 >= max_steps:
                continue
            for next_key in graph.get(path[-1], []):
                if next_key in seen:
                    continue
                next_path = [*path, next_key]
                if next_key == to_key:
                    return next_path
                seen.add(next_key)
                queue.append(next_path)
        return []

    def _movement_summary(
        self,
        con: sqlite3.Connection,
        group_id: str,
        old_location: sqlite3.Row | None,
        path: list[str],
    ) -> str:
        if len(path) <= 1:
            return f"你留在{old_location['name'] if old_location else '原地'}附近行动。"
        names = []
        for key in path:
            loc = self._location(con, group_id, key)
            names.append(str(loc["name"] if loc else key))
        if len(names) <= 2:
            return f"你从{names[0]}去了{names[-1]}。"
        return f"你从{names[0]}出发，途经{'、'.join(names[1:-1])}，抵达{names[-1]}。"

    def _route_scene(
        self,
        con: sqlite3.Connection,
        group_id: str,
        path: list[str],
        row: sqlite3.Row,
        text: str,
    ) -> str:
        if len(path) <= 2 or random.random() > 0.55:
            return ""
        mid_keys = path[1:-1]
        random.shuffle(mid_keys)
        for key in mid_keys:
            loc = self._location(con, group_id, key)
            if not loc:
                continue
            npc_rows = con.execute(
                "SELECT npc_key,name,role,faction,disposition,memory,location_key FROM npcs WHERE group_id=? AND location_key=? ORDER BY RANDOM() LIMIT 3",
                (group_id, key),
            ).fetchall()
            for npc in npc_rows:
                if self._npc_hidden_from_normal_encounter(npc):
                    continue
                if not self._npc_can_visit(npc, key):
                    continue
                npc_dict = {
                    "type": "npc",
                    "id": npc["npc_key"],
                    "name": npc["name"],
                    "role": npc["role"],
                    "faction": npc["faction"],
                    "disposition": npc["disposition"],
                    "memory": self.clean_text(npc["memory"], 160),
                }
                reaction = self._npc_scene_reaction(npc_dict, self._looks_like_battle(text), text)
                if reaction:
                    self._adjust_npc_relationship(con, group_id, int(row["character_id"]), str(npc["npc_key"]), 1)
                    return f"途经{loc['name']}时，{reaction}"
                return f"途经{loc['name']}时，你和{npc['name']}擦肩而过，对方的反应被记录为后续可能的交集。"
            if random.random() < 0.5:
                seed = random.choice(EVENT_SEEDS)
                return f"途经{loc['name']}时，路边新闻屏和学生议论提到“{seed}”，这条传闻可能在后续回合发酵。"
        return ""

    def _projected_action_location(self, con: sqlite3.Connection, group_id: str, action: dict[str, Any]) -> str:
        current_key = str(action.get("location_key") or "")
        text = str(action.get("text") or "")
        if not current_key:
            return ""
        target = self._extract_location(con, group_id, current_key, text)
        if target and target["location_key"] != current_key and self._movement_path(con, group_id, current_key, target["location_key"]):
            return str(target["location_key"])
        return current_key

    def _same_round_reachable(
        self,
        actor: dict[str, Any],
        target: sqlite3.Row,
        projected_locations: dict[int, str],
    ) -> bool:
        actor_id = int(actor.get("id") or 0)
        target_id = int(target["id"])
        actor_location = projected_locations.get(actor_id) or str(actor.get("location_key") or "")
        target_location = projected_locations.get(target_id) or str(target["location_key"] or "")
        return bool(actor_location and target_location and actor_location == target_location)

    def _extract_location(self, con: sqlite3.Connection, group_id: str, current_key: str, text: str) -> sqlite3.Row | None:
        if self._explicitly_from_inventory(text):
            return None
        rows = con.execute("SELECT * FROM locations WHERE group_id=?", (group_id,)).fetchall()
        matches = [
            row
            for row in rows
            if row["name"] in text
            or row["location_key"] in text
            or self._location_alias_matches(row, text)
        ]
        if not matches:
            fuzzy = self._fuzzy_location_matches(rows, text)
            if not fuzzy:
                return None
            for row in fuzzy:
                if row["location_key"] != current_key:
                    return row
            return fuzzy[0]
        target_order = self._rank_location_mentions(matches, text)
        for row in target_order:
            if row["location_key"] != current_key:
                return row
        for row in target_order:
            if row["location_key"] == current_key:
                return row
        return target_order[0]

    def _rank_location_mentions(self, rows: list[sqlite3.Row], text: str) -> list[sqlite3.Row]:
        intent_words = ("前往", "去", "到", "进入", "调查", "潜入", "硬闯", "搜索", "查看", "拜访", "抵达")

        def score(row: sqlite3.Row) -> tuple[int, int, int, int]:
            name = str(row["name"] or "")
            key = str(row["location_key"] or "")
            matches: list[tuple[int, int]] = []
            for value in (name, key):
                index = text.find(value) if value else -1
                if index >= 0:
                    matches.append((index, len(value)))
            matches.extend(self._location_alias_matches(row, text))
            first_index = min((index for index, _ in matches), default=len(text))
            best_match_length = max((length for index, length in matches if index == first_index), default=0)
            before = text[max(0, first_index - 12):first_index]
            intent = 0 if any(word in before for word in intent_words) else 1
            # Longer matched phrases are usually more specific, so they beat broad aliases like “第七学区”.
            return (intent, first_index, -best_match_length, -len(name))

        return sorted(rows, key=score)

    def _fuzzy_location_matches(self, rows: list[sqlite3.Row], text: str) -> list[sqlite3.Row]:
        query = self._location_query_text(text)
        if not query:
            return []
        scored: list[tuple[int, sqlite3.Row]] = []
        for row in rows:
            name = str(row["name"] or "")
            key = str(row["location_key"] or "")
            tags = "".join(loads(str(row["tags"] or "[]"), []))
            haystack = self._normalize_location_text(name + key + tags)
            score = self._fuzzy_text_score(query, haystack)
            if score >= max(2, min(5, len(query) // 2)):
                scored.append((score, row))
        scored.sort(key=lambda item: (-item[0], int(item[1]["sort_order"] or 0)))
        return [row for _, row in scored[:3]]

    def _location_query_text(self, text: str) -> str:
        compact = self._normalize_location_text(text)
        compact = re.sub(
            r"(行动|我|我们|想|要|打算|准备|前往|去|到|进入|调查|搜索|查看|拜访|抵达|看看|附近|门口|入口|那边|那里|这边|路过|然后|并且|购买|买|吃|喝|找|询问|交流|聊天|等待|观察)",
            "",
            compact,
        )
        return compact[:24]

    def _normalize_location_text(self, text: str) -> str:
        text = re.sub(r"\s+", "", str(text or "")).lower()
        district_numbers = {
            1: "一",
            2: "二",
            3: "三",
            4: "四",
            5: "五",
            6: "六",
            7: "七",
            8: "八",
            9: "九",
            10: "十",
            11: "十一",
            12: "十二",
            13: "十三",
            14: "十四",
            15: "十五",
            16: "十六",
            17: "十七",
            18: "十八",
            19: "十九",
            20: "二十",
            21: "二十一",
            22: "二十二",
            23: "二十三",
        }
        text = text.replace("第７学区", "第七学区").replace("第〇七学区", "第七学区")
        for number, cn_number in sorted(district_numbers.items(), key=lambda item: -item[0]):
            text = text.replace(f"第{number:02d}学区", f"第{cn_number}学区")
            text = text.replace(f"第{number}学区", f"第{cn_number}学区")
            text = re.sub(rf"(?<![0-9第]){number}学区", f"第{cn_number}学区", text)
        return text

    def _fuzzy_text_score(self, query: str, haystack: str) -> int:
        if query in haystack:
            return len(query) * 2
        score = 0
        last_index = -1
        for char in query:
            index = haystack.find(char, last_index + 1)
            if index >= 0:
                score += 1
                if index == last_index + 1:
                    score += 1
                last_index = index
        return score

    def _location_alias_matches(self, row: sqlite3.Row, text: str) -> list[tuple[int, int]]:
        key = str(row["location_key"] or "")
        compact = re.sub(r"\s+", "", str(text or ""))
        compact = re.sub(r"(?<![0-9第])7学区", "第七学区", compact)
        compact = (
            compact.replace("第７学区", "第七学区")
            .replace("第7学区", "第七学区")
            .replace("第〇七学区", "第七学区")
            .replace("第07学区", "第七学区")
        )
        if key == "district_07":
            aliases = (
                "第七学区门口",
                "第七学区入口",
                "第七学区大门",
                "第七学区外面",
                "第七学区外",
                "第七学区外围",
                "第七学区附近",
                "第七学区路口",
                "第七学区",
                "中心学区门口",
                "中心学区入口",
                "中心学区",
            )
        elif key == "school_gate":
            aliases = (
                "第七学区某高中校门",
                "第七学区某高中门口",
                "第七学区高中校门",
                "第七学区高中门口",
                "第七学区学校门口",
                "第七学区校门口",
                "第七学区校门",
                "某高中校门",
                "某高中门口",
                "高中校门",
                "高中门口",
                "学校校门",
                "学校门口",
                "校门口",
                "校门",
            )
        elif key == "hospital":
            aliases = (
                "冥土追魂所在医院",
                "冥土追魂医院",
                "第七学区医院",
                "医院",
            )
        elif key == "main_road":
            aliases = (
                "第七学区生活圈主干道",
                "生活圈主干道",
                "主干道",
                "大路",
                "路边",
            )
        elif key == "canteen":
            aliases = (
                "学生寮食堂",
                "食堂",
                "餐厅窗口",
            )
        elif key == "seventh_mist":
            aliases = (
                "Seventh Mist",
                "seventh mist",
                "第七迷雾",
                "大型商场",
                "商场",
            )
        elif key == "shichifukujin_street":
            aliases = (
                "七福神商店街",
                "商店街",
                "旧式商店街",
            )
        elif key == "market":
            aliases = (
                "第七学区商业入口",
                "商业入口",
                "商业区入口",
            )
        elif key == "plaza":
            aliases = (
                "第七学区公共广场",
                "公共广场",
                "广场",
            )
        else:
            aliases = ()
        return [(compact.find(alias), len(alias)) for alias in aliases if compact.find(alias) >= 0]

    def _encounters(self, con: sqlite3.Connection, group_id: str, location_key: str, character_id: int) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for row in con.execute(
            "SELECT id,game_name FROM characters WHERE group_id=? AND location_key=? AND id<>? AND audit_status='approved'",
            (group_id, location_key, character_id),
        ).fetchall():
            results.append({"type": "player", "id": str(row["id"]), "name": row["game_name"]})
        for row in con.execute(
            "SELECT npc_key,name,role,faction,disposition,memory FROM npcs WHERE group_id=? AND location_key=?",
            (group_id, location_key),
        ).fetchall():
            if self._npc_hidden_from_normal_encounter(row):
                continue
            results.append(
                {
                    "type": "npc",
                    "id": row["npc_key"],
                    "name": row["name"],
                    "role": row["role"],
                    "faction": row["faction"],
                    "disposition": row["disposition"],
                    "memory": self.clean_text(row["memory"], 160),
                }
            )
        return results

    def _location_roster(self, con: sqlite3.Connection, group_id: str) -> dict[str, list[str]]:
        roster: dict[str, list[str]] = defaultdict(list)
        for row in con.execute(
            """
            SELECT locations.name AS location_name, characters.game_name AS name
            FROM characters JOIN locations ON locations.group_id=characters.group_id AND locations.location_key=characters.location_key
            WHERE characters.group_id=? AND characters.audit_status='approved'
            """,
            (group_id,),
        ).fetchall():
            roster[row["location_name"]].append(row["name"])
        for row in con.execute(
            """
            SELECT locations.name AS location_name, npcs.name AS name, npcs.role AS role, npcs.faction AS faction, npcs.disposition AS disposition
            FROM npcs JOIN locations ON locations.group_id=npcs.group_id AND locations.location_key=npcs.location_key
            WHERE npcs.group_id=?
            """,
            (group_id,),
        ).fetchall():
            if self._npc_hidden_from_normal_encounter(row):
                continue
            roster[row["location_name"]].append(row["name"])
        return dict(roster)

    def _small_relationship_changes(self, con: sqlite3.Connection, group_id: str, character_id: int, encounters: list[dict[str, Any]]) -> None:
        for item in encounters:
            if random.random() > 0.35:
                continue
            delta = random.choice([-1, 1])
            con.execute(
                """
                INSERT INTO relationships(group_id,source_type,source_id,target_type,target_id,score,updated_at)
                VALUES(?,?,?,?,?,?,?)
                ON CONFLICT(group_id,source_type,source_id,target_type,target_id)
                DO UPDATE SET score=max(-100,min(100,score+excluded.score)), updated_at=excluded.updated_at
                """,
                (group_id, "player", str(character_id), item["type"], item["id"], delta, utc_now_iso()),
            )

    def _resolve_npc_interactions(
        self,
        con: sqlite3.Connection,
        group_id: str,
        character_id: int,
        location_key: str,
        text: str,
        encounters: list[dict[str, Any]],
    ) -> list[str]:
        if not self._looks_like_npc_interaction(text):
            return []
        npcs = [item for item in encounters if item.get("type") == "npc"]
        if not npcs:
            mentioned = self._mentioned_npcs(con, group_id, text)
            if mentioned:
                results: list[str] = []
                for npc in mentioned[:2]:
                    if self._npc_can_visit(npc, location_key):
                        interaction = self._classify_npc_interaction(text)
                        delta = self._npc_relation_delta(interaction)
                        if delta:
                            self._adjust_npc_relationship(con, group_id, character_id, str(npc["npc_key"]), delta)
                        loc = self._location(con, group_id, str(npc["location_key"]))
                        place = str(loc["name"] if loc else npc["location_key"])
                        summary = self._npc_interaction_summary(dict(npc), interaction, delta)
                        results.append(f"你通过消息、支部记录或熟人转述联系上了{npc['name']}。对方当前主要活动在{place}；{summary}")
                    else:
                        loc = self._location(con, group_id, str(npc["location_key"]))
                        place = str(loc["name"] if loc else npc["location_key"])
                        results.append(f"你尝试寻找{npc['name']}，但对方当前不在这里，而是在{place}附近活动；本轮得到的线索只够确认行踪，想深入互动需要前往合理地点或等待对方按日程出现。")
                return results
            return []
        mentioned = [item for item in npcs if self._npc_name_in_text(item, text)]
        targets = mentioned or npcs[:1]
        results: list[str] = []
        for npc in targets[:2]:
            interaction = self._classify_npc_interaction(text)
            delta = self._npc_relation_delta(interaction)
            if delta:
                self._adjust_npc_relationship(con, group_id, character_id, str(npc["id"]), delta)
            results.append(self._npc_interaction_summary(npc, interaction, delta))
        return results

    def _looks_like_npc_interaction(self, text: str) -> bool:
        return any(
            word in text
            for word in (
                "找",
                "拜访",
                "询问",
                "请教",
                "交流",
                "聊天",
                "委托",
                "帮忙",
                "请求",
                "道谢",
                "送",
                "交给",
                "报告",
                "对话",
            )
        )

    def _mentioned_npcs(self, con: sqlite3.Connection, group_id: str, text: str) -> list[sqlite3.Row]:
        rows = con.execute(
            "SELECT npc_key,name,role,faction,location_key,disposition,memory FROM npcs WHERE group_id=?",
            (group_id,),
        ).fetchall()
        return [row for row in rows if self._npc_name_in_text(row, text)]

    def _npc_name_in_text(self, npc: sqlite3.Row | dict[str, Any], text: str) -> bool:
        name = str(npc["name"] if isinstance(npc, sqlite3.Row) else npc.get("name", "")).strip()
        npc_id = str(npc["npc_key"] if isinstance(npc, sqlite3.Row) and "npc_key" in npc.keys() else (npc.get("id", "") if isinstance(npc, dict) else "")).strip()
        aliases = {name, npc_id}
        if "御坂" in name:
            aliases.add("御坂")
        if "白井" in name:
            aliases.add("白井")
        if "初春" in name:
            aliases.add("初春")
        if "佐天" in name:
            aliases.add("佐天")
        if "冥土追魂" in name:
            aliases.update({"医生", "呱太医生", "冥土追魂"})
        return any(alias and alias in text for alias in aliases)

    def _classify_npc_interaction(self, text: str) -> str:
        if any(word in text for word in ("威胁", "逼问", "挑衅", "攻击", "抢", "偷")):
            return "pressure"
        if any(word in text for word in ("帮忙", "协助", "支援", "保护", "道谢", "送", "交给", "报告")):
            return "support"
        if any(word in text for word in ("询问", "请教", "打听", "调查", "线索")):
            return "ask"
        return "talk"

    def _npc_relation_delta(self, interaction: str) -> int:
        return {"support": 2, "ask": 1, "talk": 1, "pressure": -3}.get(interaction, 0)

    def _adjust_npc_relationship(
        self,
        con: sqlite3.Connection,
        group_id: str,
        character_id: int,
        npc_key: str,
        delta: int,
    ) -> None:
        con.execute(
            """
            INSERT INTO relationships(group_id,source_type,source_id,target_type,target_id,score,updated_at)
            VALUES(?,?,?,?,?,?,?)
            ON CONFLICT(group_id,source_type,source_id,target_type,target_id)
            DO UPDATE SET score=max(-100,min(100,score+excluded.score)), updated_at=excluded.updated_at
            """,
            (group_id, "player", str(character_id), "npc", npc_key, delta, utc_now_iso()),
        )

    def _npc_interaction_summary(self, npc: sqlite3.Row | dict[str, Any], interaction: str, delta: int) -> str:
        if isinstance(npc, sqlite3.Row):
            name = str(npc["name"] or "对方")
            memory = str(npc["memory"] or "").strip() if "memory" in npc.keys() else ""
            disposition = str(npc["disposition"] or "").strip() if "disposition" in npc.keys() else ""
        else:
            name = str(npc.get("name") or "对方")
            memory = str(npc.get("memory") or "").strip()
            disposition = str(npc.get("disposition") or "").strip()
        memory_hint = f" 对方的反应带着一点既有印象：{memory[:60]}。" if memory else ""
        style_hint = f"态度偏{disposition}。" if disposition else ""
        if interaction == "support":
            return f"你和{name}进行了支援或委托相关的互动，{style_hint}对方明显更愿意配合。{memory_hint}".strip()
        if interaction == "ask":
            return f"你向{name}打听情报，{style_hint}对方给出了符合当前位置和权限的有限线索。{memory_hint}".strip()
        if interaction == "pressure":
            return f"你对{name}施加了压力，{style_hint}对方明显警惕，之后未必愿意继续帮忙。{memory_hint}".strip()
        return f"你和{name}进行了简短交流，{style_hint}对方对你的印象有了轻微变化。{memory_hint}".strip()

    def _npc_scene_reactions(
        self,
        con: sqlite3.Connection,
        group_id: str,
        row: sqlite3.Row,
        location_key: str,
        text: str,
        encounters: list[dict[str, Any]],
        battle_intent: bool,
    ) -> list[str]:
        if not battle_intent and not self._looks_like_social_interaction(text):
            return []
        npcs = [item for item in encounters if item.get("type") == "npc"]
        if not npcs and random.random() < 0.25:
            npcs = self._passing_npcs(con, group_id, location_key, limit=2)
        results: list[str] = []
        for npc in npcs[:2]:
            reaction = self._npc_scene_reaction(npc, battle_intent, text)
            if not reaction:
                continue
            delta = 1 if "介入" in reaction or "帮" in reaction or "劝" in reaction else 0
            if delta:
                self._adjust_npc_relationship(con, group_id, int(row["character_id"]), str(npc["id"]), delta)
            results.append(reaction)
        return results

    def _passing_npcs(self, con: sqlite3.Connection, group_id: str, location_key: str, limit: int = 2) -> list[dict[str, Any]]:
        rows = con.execute(
            "SELECT npc_key,name,role,faction,disposition,memory,location_key FROM npcs WHERE group_id=? ORDER BY RANDOM() LIMIT 12",
            (group_id,),
        ).fetchall()
        results: list[dict[str, Any]] = []
        for npc in rows:
            if self._npc_hidden_from_normal_encounter(npc):
                continue
            if not self._npc_can_visit(npc, location_key):
                continue
            results.append(
                {
                    "type": "npc",
                    "id": npc["npc_key"],
                    "name": npc["name"],
                    "role": npc["role"],
                    "faction": npc["faction"],
                    "disposition": npc["disposition"],
                    "memory": self.clean_text(npc["memory"], 160),
                }
            )
            if len(results) >= limit:
                break
        return results

    def _npc_scene_reaction(self, npc: dict[str, Any], battle_intent: bool, text: str) -> str:
        name = str(npc.get("name") or "某个 NPC")
        faction = str(npc.get("faction") or "")
        disposition = str(npc.get("disposition") or "")
        role = str(npc.get("role") or "")
        if battle_intent:
            if "风纪委员" in faction or "警备员" in faction:
                return f"{name}注意到冲突升级，立刻试图介入维持秩序，并警告继续动手会被记录。"
            if any(word in disposition for word in ("友好", "热心", "可靠", "爽快")):
                return f"{name}路过时被动静吸引，没有替你解决战斗，但会提醒你控制伤害并尽快撤离。"
            if "高傲" in disposition or "严格" in disposition:
                return f"{name}旁观了片刻，对你处理冲突的方式保持审视态度。"
            return f"{name}被现场动静吸引，短暂停留后选择保持距离。"
        if self._looks_like_social_pressure(text):
            if "风纪委员" in faction or "警备员" in faction:
                return f"{name}注意到你给他人施压，出面提醒双方不要把纠纷升级。"
            return f"{name}看见这次互动后明显变得谨慎，之后对相关传闻会更留心。"
        if any(word in text for word in ("帮助", "协助", "保护", "道谢", "支援")):
            if any(word in disposition for word in ("友好", "热心", "可靠", "温柔")) or "教师" in role:
                return f"{name}看见你的协助行为后态度缓和，愿意在公开范围内多给一点提示。"
        return ""

    def cheat_reason(self, text: str) -> str:
        compact = re.sub(r"\s+", "", text.lower())
        for pattern in CHEAT_PATTERNS:
            normalized_pattern = re.sub(r"\s+", "", pattern.lower())
            if normalized_pattern in compact:
                return f"行动被反作弊拦截：包含高风险词“{pattern}”。"
        if self._looks_like_claimed_incoming_transfer(text):
            return "行动被反作弊拦截：不能单方面声明别人给你钱或物品。请让对方用自己的行动写明赠与/转账。"
        if re.search(r"(给我|获得|增加).{0,8}([0-9]{4,}|无限).{0,8}(学都币|金币|钱)", text):
            return "行动被反作弊拦截：不能直接刷取大量货币。"
        return ""

    def character_card_cheat_reason(self, text: str) -> str:
        raw = str(text or "")
        lowered = raw.lower()
        compact = re.sub(r"\s+", "", lowered)
        hard_blocks = (
            "绝对能力者",
            "level6",
            "lv6",
            "魔神",
            "统括理事长",
            "亚雷斯塔",
            "爱华斯",
            "上条当麻本人",
            "御坂美琴本人",
            "一方通行本人",
            "幻想杀手",
            "十万三千本魔道书",
            "全知全能",
            "无敌",
            "秒杀",
            "一击必杀",
            "时间停止",
            "操控现实",
            "瞬移全图",
            "全图瞬移",
            "无限学都币",
            "无限金币",
            "无限钱",
        )
        for pattern in hard_blocks:
            normalized = re.sub(r"\s+", "", pattern.lower())
            if normalized in compact:
                return f"角色卡被反作弊拦截：包含高风险设定“{pattern}”。请降低强度后重新提交。"
        if re.search(r"(level|lv)\.?\s*[6-9][0-9]*", lowered, re.I):
            return "角色卡被反作弊拦截：能力等级不能高于 Level 5。"
        if re.search(r"([6-9][0-9]*)级", compact):
            return "角色卡被反作弊拦截：能力等级不能高于 Level 5。"
        return ""

    def normalize_action(self, text: str) -> str:
        text = re.sub(r"\s+", " ", text or "").strip()
        for prefix in ("行动", "文游行动", "提交行动"):
            if text == prefix:
                return ""
            if text.startswith(prefix):
                return text[len(prefix):].strip()
        return text

    def clean_name(self, text: str) -> str:
        return re.sub(r"\s+", "", text or "")[:32]

    def clean_text(self, text: str, limit: int) -> str:
        return re.sub(r"\s+", " ", text or "").strip()[:limit]

    def audit_label(self, status: str) -> str:
        return {"approved": "已通过", "pending": "待审核", "rejected": "已拒绝"}.get(status, status)

    def format_time(self, value: str) -> str:
        dt = parse_iso(value)
        if not dt:
            return "-"
        return dt.astimezone(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M 北京时间")

    def _looks_like_rest(self, text: str) -> bool:
        return any(word in text.lower() for word in ("休息", "睡觉", "放松", "恢复体力", "恢复精力", "躺", "rest", "sleep"))

    def _looks_like_buy(self, con: sqlite3.Connection, group_id: str, text: str) -> bool:
        if self._looks_like_theft_transfer(text) or self._looks_like_claimed_incoming_transfer(text):
            return False
        if any(word in text or word in text.lower() for word in ("买", "购买", "拿取", "领取", "换取", "兑换", "补给", "吃饭", "点餐", "用餐", "购物", "消费", "付款", "结账", "buy")):
            return True
        if self._purchase_item_mentioned_with_intent(con, group_id, text):
            return True
        broad_purchase_words = (
            *self._purchase_intent_words("food"),
            *self._purchase_intent_words("water"),
        )
        if any(word in text for word in broad_purchase_words):
            return True
        travel_ticket_words = (
            "地铁票",
            "地下铁票",
            "通勤票",
            "通勤券",
            "通勤一日券",
            "地铁券",
            "地下铁券",
            "地铁一日券",
            "地下铁一日券",
            "车票",
            "乘车券",
        )
        if any(word in text for word in travel_ticket_words):
            return True
        return False

    def _purchase_item_mentioned_with_intent(self, con: sqlite3.Connection, group_id: str, text: str) -> bool:
        if not self._purchase_item_mentioned_with_intent_text(text):
            return False
        return bool(con.execute(
            "SELECT 1 FROM shop_items WHERE group_id=? AND is_active=1 AND instr(?, name)>0 LIMIT 1",
            (group_id, self._normalize_purchase_text(text)),
        ).fetchone())

    def _purchase_item_mentioned_with_intent_text(self, text: str) -> bool:
        return bool(
            any(word in text for word in ("要", "买", "购买", "兑换", "补给", "付款", "结账", "补充"))
            or re.search(r"(拿|取)(一|个|张|瓶|份|件|些|点)", text)
            or "拿取" in text
            or "领取" in text
            or "换取" in text
        )

    def _looks_like_work(self, text: str) -> bool:
        return any(word in text for word in ("兼职", "打工", "帮忙", "跑腿", "工作", "摆摊"))

    def _looks_like_development(self, text: str) -> bool:
        return any(
            word in text
            for word in (
                "能力开发",
                "能力训练",
                "开发课程",
                "能力测定",
                "AIM测定",
                "参加训练",
                "训练能力",
                "能力课程",
            )
        )

    def _looks_like_battle(self, text: str) -> bool:
        return any(
            word in text
            for word in (
                "战斗训练",
                "模拟战",
                "切磋",
                "对练",
                "实战",
                "冲突",
                "互殴",
                "打架",
                "攻击",
                "袭击",
                "殴打",
                "迎战",
                "战斗",
            )
        )

    def _looks_like_pvp(self, text: str) -> bool:
        return self._looks_like_theft_transfer(text) or any(
            word in text
            for word in (
                "互殴",
                "打架",
                "殴打",
                "攻击",
                "袭击",
                "揍",
                "打他",
                "打她",
                "打倒",
                "击倒",
                "制服",
                "干架",
                "决斗",
                "正面冲突",
                "下重手",
                "全力打",
            )
        )

    def _training_damage(self, text: str) -> int:
        low = max(3, int(self.config.pvp_damage_min * 0.35))
        high = max(low, int(self.config.pvp_damage_max * 0.5))
        if self._looks_like_pvp(text):
            low = max(low, int(self.config.pvp_damage_min * 0.6))
            high = max(high, int(self.config.pvp_damage_max * 0.75))
        return random.randint(low, high)

    def _pvp_self_damage(
        self,
        actor: sqlite3.Row,
        pvp_targets: list[dict[str, Any]],
        text: str,
    ) -> int:
        low = self.config.pvp_damage_min
        high = self.config.pvp_damage_max
        actor_level = self._power_level_value(actor["power_level"])
        if pvp_targets:
            target_levels = [self._power_level_value(str(item.get("power_level") or "")) for item in pvp_targets]
            strongest_target = max(target_levels) if target_levels else actor_level
            level_gap = strongest_target - actor_level
            low += max(0, level_gap) * 3
            high += max(0, level_gap) * 5
            if len(pvp_targets) >= 2:
                low += 4
                high += 8
        if int(actor["energy"]) < 30:
            low += 3
            high += 6
        if int(actor["hp"]) < 35:
            low += 2
            high += 5
        physical_mitigation = self._secondary_exp_bonus_percent(actor, "physical_exp")
        if physical_mitigation:
            low -= max(0, physical_mitigation // 3)
            high -= max(0, physical_mitigation // 2)
        if any(word in text for word in ("全力", "下重手", "不留手", "拼命", "生死", "致命")):
            low += 5
            high += 12
        low, high = self._scale_conflict_damage_range(low, high)
        low = max(1, min(95, low))
        high = max(low, min(98, high))
        return random.randint(low, high)

    def _passive_pvp_already_answered(
        self,
        target_action: dict[str, Any] | None,
        attack: dict[str, Any],
    ) -> bool:
        if not target_action:
            return False
        text = str(target_action.get("text") or "")
        attacker = attack.get("attacker") or {}
        if self._looks_like_pvp(text) and self._mentions_character_dict(text, attacker):
            return True
        return False

    def _build_passive_social_index(
        self,
        con: sqlite3.Connection,
        group_id: str,
        actions: list[dict[str, Any]],
    ) -> dict[int, list[dict[str, Any]]]:
        if not actions:
            return {}
        characters = con.execute(
            "SELECT id, game_name, display_name, qq_id, location_key, power_level FROM characters WHERE group_id=? AND audit_status='approved'",
            (group_id,),
        ).fetchall()
        index: dict[int, list[dict[str, Any]]] = defaultdict(list)
        for action in actions:
            text = str(action.get("text") or "")
            if self._looks_like_pvp(text) or not self._looks_like_social_interaction(text):
                continue
            actor_id = int(action["character_id"])
            actor = next((dict(row) for row in characters if int(row["id"]) == actor_id), None)
            if not actor:
                continue
            targets = [
                dict(target)
                for target in characters
                if int(target["id"]) != actor_id and self._mentions_character(text, target)
            ]
            for target in targets[:4]:
                index[int(target["id"])].append(
                    {
                        "actor": actor,
                        "action_id": int(action["id"]),
                        "text": text,
                    }
                )
        return index

    def _resolve_passive_social_impacts(
        self,
        con: sqlite3.Connection,
        group_id: str,
        passive_social_index: dict[int, list[dict[str, Any]]],
    ) -> list[dict[str, Any]]:
        outcomes: list[dict[str, Any]] = []
        for target_id, interactions in passive_social_index.items():
            if not interactions:
                continue
            target = con.execute("SELECT * FROM characters WHERE id=? AND group_id=?", (target_id, group_id)).fetchone()
            if not target:
                continue
            mood_delta = 0
            energy_delta = 0
            summaries: list[str] = []
            for interaction in interactions[:4]:
                actor = interaction.get("actor") or {}
                actor_name = str(actor.get("game_name") or "某个玩家")
                text = str(interaction.get("text") or "")
                if self._looks_like_helpful_interaction(text):
                    mood_delta += 2
                    energy_delta -= 1
                    summaries.append(f"{actor_name}的行动尝试与你协作或提供帮助。")
                elif self._looks_like_social_pressure(text):
                    mood_delta -= 2
                    energy_delta -= 2
                    summaries.append(f"{actor_name}的行动给你带来了一些压力。")
                else:
                    mood_delta += 1
                    energy_delta -= 1
                    summaries.append(f"{actor_name}的行动与你产生了交集。")
            mood_delta = max(-8, min(8, mood_delta))
            energy_delta = max(-8, min(2, energy_delta))
            new_mood = clamp(int(target["mood"]) + mood_delta)
            new_energy = clamp(int(target["energy"]) + energy_delta)
            con.execute(
                "UPDATE characters SET energy=?,mood=?,updated_at=? WHERE id=?",
                (new_energy, new_mood, utc_now_iso(), target_id),
            )
            outcomes.append(
                {
                    "action_id": None,
                    "character_id": target_id,
                    "qq_id": target["qq_id"],
                    "game_name": target["game_name"],
                    "text": "",
                    "accepted": True,
                    "summary": "其他玩家的行动与你产生了交互。",
                    "location_key": target["location_key"],
                    "encounters": [],
                    "warnings": ["你本轮即使没有主动行动，也收到了其他玩家行动带来的影响。"],
                    "deltas": {
                        "hp": 0,
                        "energy": energy_delta,
                        "water": 0,
                        "satiety": 0,
                        "mood": mood_delta,
                        "money": 0,
                        "exp": 0,
                        "death_protection": 0,
                    },
                    "passive_impacts": [{"summary": summary} for summary in summaries],
                }
            )
        return outcomes

    def _resolve_active_social_impacts(
        self,
        con: sqlite3.Connection,
        group_id: str,
        actions: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        if not actions:
            return []
        characters = con.execute(
            "SELECT * FROM characters WHERE group_id=? AND audit_status='approved'",
            (group_id,),
        ).fetchall()
        char_by_id = {int(row["id"]): row for row in characters}
        outcomes: list[dict[str, Any]] = []
        for action in actions:
            text = str(action.get("text") or "")
            if self._looks_like_pvp(text) or not self._looks_like_social_interaction(text):
                continue
            actor = char_by_id.get(int(action["character_id"]))
            if not actor:
                continue
            targets = [
                target
                for target in characters
                if int(target["id"]) != int(actor["id"]) and self._mentions_character(text, target)
            ]
            for target in targets[:4]:
                interaction = self._classify_social_interaction(text)
                relation_delta = self._social_relation_delta(interaction)
                self._adjust_player_relationship(con, group_id, int(actor["id"]), int(target["id"]), relation_delta)
                self._adjust_player_relationship(con, group_id, int(target["id"]), int(actor["id"]), max(-2, min(3, relation_delta)))
                transfer_text, actor_money_delta, target_money_delta = self._try_social_transfer(con, actor, target, text, interaction)
                actor_deltas = self._social_state_deltas(actor, interaction, "actor")
                target_deltas = self._social_state_deltas(target, interaction, "target")
                actor_deltas["money"] = actor_deltas.get("money", 0) + actor_money_delta
                target_deltas["money"] = target_deltas.get("money", 0) + target_money_delta
                self._apply_social_state_deltas(con, int(actor["id"]), actor_deltas)
                self._apply_social_state_deltas(con, int(target["id"]), target_deltas)
                outcomes.append(
                    self._social_outcome(
                        actor,
                        target,
                        interaction,
                        relation_delta,
                        transfer_text,
                        actor_deltas,
                        perspective="actor",
                    )
                )
                outcomes.append(
                    self._social_outcome(
                        target,
                        actor,
                        interaction,
                        max(-2, min(3, relation_delta)),
                        transfer_text,
                        target_deltas,
                        perspective="target",
                    )
                )
        return outcomes

    def _social_outcome(
        self,
        receiver: sqlite3.Row,
        other: sqlite3.Row,
        interaction: str,
        relation_delta: int,
        transfer_text: str,
        state_deltas: dict[str, int],
        *,
        perspective: str,
    ) -> dict[str, Any]:
        if perspective == "actor":
            summary = self._actor_social_summary(other["game_name"], interaction)
        else:
            summary = self._target_social_summary(other["game_name"], interaction)
        passive_impacts = [{"summary": summary}]
        if transfer_text:
            passive_impacts.append({"summary": transfer_text})
        return {
            "action_id": None,
            "character_id": receiver["id"],
            "qq_id": receiver["qq_id"],
            "game_name": receiver["game_name"],
            "text": "",
            "accepted": True,
            "summary": summary,
            "location_key": receiver["location_key"],
            "encounters": [],
            "warnings": [],
            "deltas": {
                "hp": 0,
                "energy": state_deltas.get("energy", 0),
                "water": 0,
                "satiety": 0,
                "mood": state_deltas.get("mood", 0),
                "money": state_deltas.get("money", 0),
                "exp": 0,
                "death_protection": 0,
            },
            "passive_impacts": passive_impacts,
        }

    def _classify_social_interaction(self, text: str) -> str:
        if self._looks_like_theft_transfer(text):
            return "pressure"
        if self._looks_like_transfer(text):
            return "transfer"
        if any(word in text for word in ("保护", "护送", "掩护", "支援", "救", "治疗", "送医", "医院", "包扎")):
            return "support"
        if any(word in text for word in ("一起", "同行", "会合", "组队", "带上", "陪")):
            return "together"
        if any(word in text for word in ("交流", "聊天", "谈", "询问", "分享", "提醒")):
            return "talk"
        if self._looks_like_social_pressure(text):
            return "pressure"
        return "contact"

    def _social_relation_delta(self, interaction: str) -> int:
        return {
            "support": 2,
            "transfer": 1,
            "together": 1,
            "talk": 1,
            "contact": 0,
            "pressure": -2,
        }.get(interaction, 0)

    def _social_state_deltas(self, row: sqlite3.Row, interaction: str, perspective: str) -> dict[str, int]:
        social_bonus = self._secondary_exp_bonus_percent(row, "social_exp")
        energy_relief = 1 if social_bonus >= 4 else 0
        mood_bonus = 1 if social_bonus >= 8 else 0

        def tuned(energy: int, mood: int) -> dict[str, int]:
            if energy < 0:
                energy = min(0, energy + energy_relief)
            if mood > 0:
                mood += mood_bonus
            return {"energy": energy, "mood": mood}

        if interaction == "support":
            return tuned(-2, 1 if perspective == "actor" else 3)
        if interaction == "transfer":
            return tuned(-1, 1)
        if interaction == "together":
            return tuned(-2, 1)
        if interaction == "talk":
            return tuned(-1, 1)
        if interaction == "pressure":
            return tuned(-2, -2 if perspective == "actor" else -4)
        return tuned(0, 0)

    def _apply_social_state_deltas(self, con: sqlite3.Connection, character_id: int, deltas: dict[str, int]) -> None:
        energy_delta = int(deltas.get("energy", 0))
        mood_delta = int(deltas.get("mood", 0))
        if not energy_delta and not mood_delta:
            return
        row = con.execute("SELECT energy,mood FROM characters WHERE id=?", (character_id,)).fetchone()
        if not row:
            return
        con.execute(
            "UPDATE characters SET energy=?, mood=?, updated_at=? WHERE id=?",
            (clamp(int(row["energy"]) + energy_delta), clamp(int(row["mood"]) + mood_delta), utc_now_iso(), character_id),
        )

    def _actor_social_summary(self, target_name: str, interaction: str) -> str:
        mapping = {
            "support": f"你对{target_name}提供了支援或保护，这会让对方更容易感受到你的立场。",
            "transfer": f"你和{target_name}产生了物品或金钱往来，系统已尝试按行动内容处理转移。",
            "together": f"你尝试和{target_name}共同行动，本轮会把你们的交集记录下来。",
            "talk": f"你和{target_name}进行了交流，对方对你的印象出现轻微变化。",
            "pressure": f"你对{target_name}施加了压力，这可能降低对方对你的观感。",
            "contact": f"你和{target_name}产生了交集。",
        }
        return mapping.get(interaction, mapping["contact"])

    def _target_social_summary(self, actor_name: str, interaction: str) -> str:
        mapping = {
            "support": f"{actor_name}对你提供了支援或保护。",
            "transfer": f"{actor_name}和你产生了物品或金钱往来。",
            "together": f"{actor_name}尝试与你共同行动。",
            "talk": f"{actor_name}与你进行了交流。",
            "pressure": f"{actor_name}对你施加了压力，你对这次接触的感受并不轻松。",
            "contact": f"{actor_name}的行动与你产生了交集。",
        }
        return mapping.get(interaction, mapping["contact"])

    def _adjust_player_relationship(
        self,
        con: sqlite3.Connection,
        group_id: str,
        source_id: int,
        target_id: int,
        delta: int,
    ) -> None:
        if not delta or source_id == target_id:
            return
        con.execute(
            """
            INSERT INTO relationships(group_id,source_type,source_id,target_type,target_id,score,updated_at)
            VALUES(?,?,?,?,?,?,?)
            ON CONFLICT(group_id,source_type,source_id,target_type,target_id)
            DO UPDATE SET score=max(-100,min(100,score+excluded.score)), updated_at=excluded.updated_at
            """,
            (group_id, "player", str(source_id), "player", str(target_id), delta, utc_now_iso()),
        )

    def _try_social_transfer(
        self,
        con: sqlite3.Connection,
        actor: sqlite3.Row,
        target: sqlite3.Row,
        text: str,
        interaction: str,
    ) -> tuple[str, int, int]:
        if interaction != "transfer":
            return "", 0, 0
        if not self._is_outgoing_transfer(text):
            if self._looks_like_theft_transfer(text):
                return "检测到抢夺/偷取意图：本轮按压力或冲突处理，不会直接转移对方资源。", 0, 0
            if self._looks_like_claimed_incoming_transfer(text):
                return "检测到单方声明对方给你资源：未获得对方行动确认，不会过账。", 0, 0
            return "检测到资源往来意图，但方向不明确；只有主动给出自己资源才会过账。", 0, 0
        money_match = re.search(r"([0-9]{1,5})\s*(?:学都币|币|元)", text)
        if money_match:
            amount = max(1, min(10000, int(money_match.group(1))))
            balance_row = con.execute("SELECT money FROM characters WHERE id=?", (actor["id"],)).fetchone()
            current_money = int(balance_row["money"]) if balance_row else int(actor["money"])
            if current_money >= amount:
                con.execute("UPDATE characters SET money=money-?, updated_at=? WHERE id=?", (amount, utc_now_iso(), actor["id"]))
                con.execute("UPDATE characters SET money=money+?, updated_at=? WHERE id=?", (amount, utc_now_iso(), target["id"]))
                return f"转移学都币 {amount}：{actor['game_name']} -> {target['game_name']}。", -amount, amount
            return f"{actor['game_name']}想转移 {amount} 学都币，但余额不足（当前 {max(0, current_money)}），转移未完成。", 0, 0
        item_name = self._extract_inventory_item_name(con, actor["id"], text)
        if item_name:
            row = con.execute(
                "SELECT quantity FROM inventory WHERE character_id=? AND item_name=?",
                (actor["id"], item_name),
            ).fetchone()
            if row and int(row["quantity"]) > 0:
                con.execute(
                    "UPDATE inventory SET quantity=quantity-1 WHERE character_id=? AND item_name=?",
                    (actor["id"], item_name),
                )
                con.execute(
                    """
                    INSERT INTO inventory(character_id,item_name,quantity,meta_json) VALUES(?,?,?,?)
                    ON CONFLICT(character_id,item_name) DO UPDATE SET quantity=quantity+excluded.quantity
                    """,
                    (target["id"], item_name, 1, "{}"),
                )
                return f"转移物品：{actor['game_name']} 将 {item_name} x1 交给 {target['game_name']}。", 0, 0
            return f"{actor['game_name']}想转移 {item_name}，但背包里没有可用数量。", 0, 0
        return "检测到转移意图，但没有识别到明确金额或背包物品名称。", 0, 0

    def _extract_inventory_item_name(self, con: sqlite3.Connection, character_id: int, text: str) -> str:
        rows = con.execute(
            "SELECT item_name FROM inventory WHERE character_id=? AND quantity>0 ORDER BY length(item_name) DESC",
            (character_id,),
        ).fetchall()
        for row in rows:
            name = str(row["item_name"] or "")
            if name and name in text:
                return name
        return ""

    def _looks_like_social_interaction(self, text: str) -> bool:
        return any(
            word in text
            for word in (
                "一起",
                "同行",
                "邀请",
                "约",
                "找",
                "等待",
                "会合",
                "碰面",
                "交流",
                "聊天",
                "帮助",
                "协助",
                "保护",
                "跟随",
                "组队",
                "带上",
                "陪",
                "给",
                "送",
                "赠送",
                "交换",
                "交易",
                "转账",
                "支付",
                "逼问",
                "威胁",
                "拦住",
                "质问",
                "跟踪",
                "盯梢",
                "纠缠",
            )
        )

    def _looks_like_transfer(self, text: str) -> bool:
        if any(word in text for word in ("交换", "交易", "转账", "支付", "付款", "过账")):
            return True
        resource_words = (
            "学都币",
            "金币",
            "元",
            "钱",
            "物品",
            "道具",
            "背包",
            "矿泉水",
            "饮用水",
            "瓶装水",
            "学生便当",
            "便当",
            "创可贴",
            "绷带",
            "便携绷带",
            "医疗凝胶贴",
            "电池",
            "终端电池",
            "便携终端电池",
            "电池包",
            "资料卡",
            "检索点数",
            "通行证",
            "通勤券",
            "一日券",
            "购物券",
            "折扣券",
            "定位卡",
            "死亡保护卡",
            "凭证",
            "词条卡",
            "装备",
            "材料",
        )
        transfer_words = ("送", "赠送", "给", "交给", "递给", "拿给", "转交")
        return any(word in text for word in transfer_words) and any(
            word in text for word in resource_words
        )

    def _is_outgoing_transfer(self, text: str) -> bool:
        if not self._looks_like_transfer(text):
            return False
        return bool(
            re.search(r"(我|本人|自己).{0,8}(给|送|赠送|转账|支付|交给|拿给|递给)", text)
            or re.search(r"(给|送|赠送|转账|支付|交给|拿给|递给).{0,24}(学都币|币|元|金币|钱|WaterBottle|饮用水|便当|创可贴|电池)", text)
        ) and not self._looks_like_claimed_incoming_transfer(text) and not self._looks_like_theft_transfer(text)

    def _looks_like_claimed_incoming_transfer(self, text: str) -> bool:
        other_subject = r"(?!我|本人|自己)[A-Za-z0-9_\-\u4e00-\u9fff]{1,32}"
        resource = r"(学都币|币|元|金币|钱|物品|道具|背包|矿泉水|饮用水|瓶装水|学生便当|便当|创可贴|绷带|便携绷带|医疗凝胶贴|电池|终端电池|便携终端电池|电池包|资料卡|检索点数|通行证|通勤券|一日券|购物券|折扣券|定位卡|死亡保护卡|凭证|词条卡|装备|材料)"
        return bool(
            re.search(rf"{other_subject}.{{0,12}}(给了?我|送了?我|转给我|转账给我|支付给我|交给我|赠送给我).{{0,24}}{resource}", text)
            or re.search(rf"{other_subject}.{{0,12}}把.{{0,24}}{resource}.{{0,8}}(给|送|转|交给)我", text)
            or re.search(rf"(我|本人).{{0,8}}(收到|拿到|获得|得到).{{0,16}}(他|她|对方|别人|玩家|{other_subject}).{{0,16}}{resource}", text)
            or re.search(rf"(玩家|对方|{other_subject}).{{0,8}}(同意|答应|允许|承诺).{{0,8}}(给我|送我|转给我).{{0,24}}{resource}", text)
        )

    def _looks_like_theft_transfer(self, text: str) -> bool:
        theft_word = any(
            word in text
            for word in (
                "抢",
                "抢夺",
                "抢走",
                "夺走",
                "偷",
                "偷走",
                "扒窃",
                "掏包",
                "勒索",
                "敲诈",
                "搜身拿走",
            )
        ) or bool(re.search(r"从.{0,16}(身上|背包|口袋|钱包|那里|那边).{0,12}(拿|取|夺|偷|抢)", text))
        return theft_word and any(word in text for word in ("学都币", "币", "元", "金币", "钱", "物品", "道具", "背包"))

    def _looks_like_helpful_interaction(self, text: str) -> bool:
        return any(word in text for word in ("帮助", "协助", "保护", "治疗", "分享", "送", "提醒", "陪", "支援"))

    def _looks_like_social_pressure(self, text: str) -> bool:
        return any(word in text for word in ("逼问", "威胁", "拦住", "质问", "跟踪", "盯梢", "纠缠"))

    def _mentions_character_dict(self, text: str, character: dict[str, Any]) -> bool:
        names = {
            str(character.get("game_name") or "").strip(),
            str(character.get("display_name") or "").strip(),
            str(character.get("qq_id") or "").strip(),
        }
        return any(name and name in text for name in names)

    def _power_level_value(self, power_level: str) -> int:
        match = re.search(r"(?:level|lv)\.?\s*([0-5])", str(power_level or ""), re.I)
        return int(match.group(1)) if match else 0

    def _build_pvp_index(
        self,
        con: sqlite3.Connection,
        group_id: str,
        actions: list[dict[str, Any]],
    ) -> tuple[dict[int, list[dict[str, Any]]], dict[int, list[dict[str, Any]]]]:
        if not actions:
            return {}, {}
        characters = con.execute(
            "SELECT id, game_name, display_name, qq_id, location_key, power_level FROM characters WHERE group_id=? AND audit_status='approved'",
            (group_id,),
        ).fetchall()
        char_by_id = {int(row["id"]): dict(row) for row in characters}
        action_by_character = {int(row["character_id"]): row for row in actions}
        projected_locations = {
            int(action["character_id"]): self._projected_action_location(con, group_id, action)
            for action in actions
        }
        index: dict[int, list[dict[str, Any]]] = defaultdict(list)
        passive_index: dict[int, list[dict[str, Any]]] = defaultdict(list)
        for action in actions:
            text = str(action.get("text") or "")
            if not self._looks_like_pvp(text):
                continue
            actor_id = int(action["character_id"])
            actor = char_by_id.get(actor_id)
            if not actor:
                continue
            named_targets = [
                target
                for target in characters
                if int(target["id"]) != actor_id and self._mentions_character(text, target)
            ]
            named_targets = [
                target for target in named_targets if self._same_round_reachable(actor, target, projected_locations)
            ]
            if not named_targets:
                named_targets = [
                    target
                    for target in characters
                    if int(target["id"]) != actor_id
                    and self._same_round_reachable(actor, target, projected_locations)
                    and self._looks_like_pvp(str(action_by_character.get(int(target["id"]), {}).get("text") or ""))
                ]
            for target in named_targets[:3]:
                target_dict = dict(target)
                index[int(action["id"])].append(target_dict)
                passive_index[int(target["id"])].append(
                    {
                        "attacker": dict(actor),
                        "action_id": int(action["id"]),
                        "text": text,
                    }
                )
                target_action = action_by_character.get(int(target["id"]))
                if target_action and self._looks_like_pvp(str(target_action.get("text") or "")):
                    index[int(target_action["id"])].append(dict(actor))
        for action_id, targets in list(index.items()):
            dedup: dict[int, dict[str, Any]] = {}
            for target in targets:
                dedup[int(target["id"])] = target
            index[action_id] = list(dedup.values())
        for target_id, attacks in list(passive_index.items()):
            dedup_attacks: dict[tuple[int, int], dict[str, Any]] = {}
            for attack in attacks:
                attacker = attack.get("attacker") or {}
                key = (int(attacker.get("id") or 0), int(attack.get("action_id") or 0))
                dedup_attacks[key] = attack
            passive_index[target_id] = list(dedup_attacks.values())
        return index, passive_index

    def _mentions_character(self, text: str, character: sqlite3.Row) -> bool:
        names = {
            str(character["game_name"] or "").strip(),
            str(character["display_name"] or "").strip(),
            str(character["qq_id"] or "").strip(),
        }
        return any(name and name in text for name in names)

    def _looks_like_heal(self, text: str) -> bool:
        return any(word in text.lower() for word in ("医院", "治疗", "看病", "疗伤", "包扎", "hospital", "heal", "clinic", "doctor"))

    def _looks_like_self_heal(self, text: str) -> bool:
        if not self._looks_like_heal(text):
            return False
        if any(word in text for word in ("护送", "送医", "带他", "带她", "带对方", "帮他", "帮她", "给他", "给她", "替他", "替她")):
            return False
        if re.search(r"(护送|帮助|协助|救助|支援).{0,16}(他|她|对方|玩家|[A-Za-z0-9_\-\u4e00-\u9fff]{1,32}).{0,16}(医院|治疗|包扎|看病|疗伤)", text):
            return False
        return True

    def _restricted_location_warning(self, target: sqlite3.Row, text: str, actor: sqlite3.Row | dict[str, Any] | None = None) -> str:
        tags = set(loads(target["tags"], []))
        name = str(target["name"] or "")
        if actor and self._identity_allows_location(actor, str(target["location_key"] or "")):
            return ""
        if "禁区" in tags or "高风险" in tags:
            if any(word in text for word in ("硬闯", "潜入", "破解", "翻墙", "强行", "偷", "黑入", "突破")):
                return f"{name}属于高权限/高风险区域，本轮只能触及外围痕迹，强行深入会被警备或权限边界拦下。"
            return f"{name}有权限边界，本轮按公开区域或外围行动处理。"
        if "权限" in tags and not any(word in text for word in ("通行证", "许可", "邀请", "登记", "申请")):
            return f"{name}需要通行许可；没有许可时只能在外围活动。"
        return ""

    def _identity_allows_location(self, actor: sqlite3.Row | dict[str, Any], location_key: str) -> bool:
        identity = str(actor["identity"] if isinstance(actor, sqlite3.Row) else actor.get("identity", ""))
        faction = str(actor["faction"] if isinstance(actor, sqlite3.Row) else actor.get("faction", ""))
        text = f"{identity} {faction}"
        if location_key in {"tokiwa_dai", "gakusha_no_sono"} and self._identity_matches_school(text, "tokiwadai"):
            return True
        if location_key == "classroom" and self._identity_matches_school(text, "kamijou"):
            return True
        if location_key == "sakugawa" and self._identity_matches_school(text, "sakugawa"):
            return True
        if location_key in {"judgment_177", "anti_skill_07_hq"} and any(word in text for word in ("风纪委员", "Judgment", "警备员", "Anti-Skill", "教师")):
            return True
        if location_key in {"lab", "mizuho_pathology", "s_processor"} and any(word in text for word in ("研究所", "研究机构", "研究员", "实习", "实验室")):
            return True
        return False

    def _identity_matches_school(self, identity: str, school: str) -> bool:
        text = str(identity or "")
        if school == "tokiwadai":
            return any(word in text for word in ("常盘台", "学舍之园", "Tokiwadai", "tokiwadai"))
        if school == "sakugawa":
            return any(word in text for word in ("栅川", "佐天同校", "初春同校"))
        if school == "kamijou":
            return any(word in text for word in ("某高中", "上条的高中", "第七学区高中", "普通高中", "高中生"))
        if school == "any":
            return any(word in text for word in ("学生", "高中", "中学", "初中", "大学", "常盘台", "栅川", "学舍之园", "Tokiwadai", "tokiwadai"))
        return False

    def _ability_use_applies(self, text: str, battle_intent: bool = False) -> bool:
        cleaned = self._strip_negated_ability_mentions(text)
        if not cleaned.strip():
            return False
        if battle_intent and not self._explicitly_no_ability(text):
            return True
        return self._looks_like_ability_use(text)

    def _explicitly_no_ability(self, text: str) -> bool:
        text = str(text or "")
        negated_patterns = (
            r"(?:不|不要|不再|不用|不靠|不动用|不发动|不使用|不施展|不释放|未|没|没有|禁止|避免|拒绝|不能|不会|不准|尽量不|暂时不|先不).{0,10}(?:能力|超能力|异能|AIM|个人现实|电磁|念动|空间|心理|矢量)",
            r"(?:能力|超能力|异能|AIM|个人现实|电磁|念动|空间|心理|矢量).{0,10}(?:不用|不靠|不动用|不发动|不使用|不施展|不释放|未使用|没使用|没有使用|禁止使用|避免使用)",
            r"(?:只|仅|单纯).{0,6}(?:体术|拳脚|肉搏|徒手|普通攻击|普通战斗|物理攻击)",
        )
        return any(re.search(pattern, text, re.I) for pattern in negated_patterns)

    def _looks_like_ability_use(self, text: str) -> bool:
        text = str(text or "")
        cleaned = self._strip_negated_ability_mentions(text)
        if not cleaned.strip():
            return False
        explicit_patterns = (
            r"(?:使用|发动|动用|施展|释放|开启|维持|运转|演算|全力|连续|大范围).{0,10}(?:能力|超能力|异能|AIM|个人现实|电磁|念动|空间|心理|矢量)",
            r"(?:能力|超能力|异能|AIM|个人现实|电磁|念动|空间|心理|矢量).{0,16}(?:使用|发动|动用|施展|释放|开启|维持|运转|演算|攻击|防御|干扰|移动|战斗|打架|互殴|殴打|袭击|制服|压制|反击|迎战|对打)",
            r"(?:用|靠|借助|配合|结合).{0,8}(?:能力|超能力|异能|AIM|个人现实|电磁|念动|空间|心理|矢量).{0,16}(?:战斗|打架|互殴|殴打|攻击|袭击|制服|压制|反击|迎战|对打)",
            r"(?:战斗|打架|互殴|殴打|攻击|袭击|制服|压制|反击|迎战|对打).{0,16}(?:使用|发动|动用|施展|释放|用|靠).{0,8}(?:能力|超能力|异能|AIM|个人现实|电磁|念动|空间|心理|矢量)",
        )
        if any(re.search(pattern, cleaned, re.I) for pattern in explicit_patterns):
            return True
        specific_terms = (
            "电磁炮",
            "念动力",
            "空间移动",
            "心理掌握",
            "矢量操作",
            "AIM扩散",
            "个人现实演算",
        )
        return any(term in cleaned for term in specific_terms)

    def _strip_negated_ability_mentions(self, text: str) -> str:
        cleaned = str(text or "")
        negated_patterns = (
            r"(?:不|不要|不再|不用|不靠|不动用|不发动|不使用|不施展|不释放|未|没|没有|禁止|避免|拒绝|不能|不会|不准|尽量不|暂时不|先不).{0,10}(?:能力|超能力|异能|AIM|个人现实|电磁|念动|空间|心理|矢量)",
            r"(?:能力|超能力|异能|AIM|个人现实|电磁|念动|空间|心理|矢量).{0,10}(?:不用|不靠|不动用|不发动|不使用|不施展|不释放|未使用|没使用|没有使用|禁止使用|避免使用)",
        )
        for pattern in negated_patterns:
            cleaned = re.sub(pattern, " ", cleaned, flags=re.I)
        return cleaned

    def _power_use_cost(self, power_level: str, text: str) -> int:
        level_match = re.search(r"(?:level|lv)\.?\s*([0-5])", str(power_level or ""), re.I)
        level = int(level_match.group(1)) if level_match else 0
        base = 4 + level * 2
        if any(word in text for word in ("全力", "连续", "长时间", "大范围", "精密", "战斗")):
            base += 5
        if level <= 0:
            base = max(3, base - 2)
        return min(base, 22)

    def _ability_battle_detail(self, row: sqlite3.Row, text: str) -> str:
        ability = str(row["ability"] or "")
        level = str(row["power_level"] or "Level 0")
        source = ability + " " + text
        if any(word in source for word in ("电磁", "电流", "电击", "超电磁炮")):
            return f"你的{level}电磁系演算被压进战斗节奏，电流干扰、金属牵引和短促放电成为攻防核心。"
        if any(word in source for word in ("空间", "瞬移", "传送")):
            return f"你的{level}空间系能力主要用于调整站位、避开正面冲击和制造突袭角度，但不会突破地图距离限制。"
        if any(word in source for word in ("念动", "念力", "动力")):
            return f"你的{level}念动系输出压在推拉、偏转和短距离控制上，每次强行改变轨迹都会增加演算负担。"
        if any(word in source for word in ("心理", "精神", "认知", "记忆")):
            return f"你的{level}心理系能力更偏向干扰判断、制造迟疑和读取表层反应，公开场合使用会带来额外警惕。"
        if any(word in source for word in ("矢量", "反射")):
            return f"你的{level}矢量相关演算集中在卸力、偏转和反击窗口上，强行承受连续冲击会迅速消耗精力。"
        if ability:
            return f"你的能力“{ability[:60]}”被纳入战斗判定，程序按{level}强度处理输出、代价和失误风险。"
        return f"你默认动用了{level}能力参与战斗，个人现实演算带来额外消耗，也让冲突结果更接近真实能力战。"

    def _action_risk_score(self, text: str) -> int:
        risk_keywords = (
            ("战斗", "攻击", "袭击", "互殴", "殴打", "打架", "硬闯", "追逐", "危险"),
            ("潜入", "破解", "偷", "黑入", "绕过权限", "突破封锁"),
            ("暗部", "ITEM", "GROUP", "SCHOOL", "猎犬部队", "妹妹们"),
            ("没有窗户的大楼", "统括理事会", "树状图设计者", "滞空回线"),
            ("魔法侧", "魔法师", "魔导书", "必要之恶教会", "罗马正教"),
            ("幻想御手", "Level Upper", "绝对能力者进化", "量产型能力者"),
        )
        score = 0
        for group in risk_keywords:
            if any(word.lower() in text.lower() for word in group):
                score += 1
        return min(score, 5)

    def _mentions_canon_core_secret(self, text: str) -> bool:
        return any(
            word.lower() in text.lower()
            for word in (
                "暗部",
                "ITEM",
                "GROUP",
                "SCHOOL",
                "妹妹们",
                "绝对能力者进化",
                "量产型能力者",
                "树状图设计者",
                "滞空回线",
                "没有窗户的大楼",
                "统括理事会",
                "幻想御手",
                "Level Upper",
                "魔神",
                "爱华斯",
            )
        )
