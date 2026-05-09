from __future__ import annotations

import json
import random
import re
import sqlite3
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

from .config import TextWorldConfig
from .database import TextWorldDB, cn_today, iso_after_minutes, parse_iso, utc_now, utc_now_iso
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
        power_level: str = "Level 0",
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
        power_level = self.clean_text(power_level, 20) or "Level 0"
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
                    UPDATE characters SET user_id=?,game_name=?,display_name=?,identity=?,faction=?,ability=?,power_level=?,audit_status=?,updated_at=?
                    WHERE id=?
                    """,
                    (user_id, game_name, game_name, identity, faction, ability, power_level, status, now, row["id"]),
                )
                return True, "角色卡已更新，等待管理员审核。" if not approve else "角色卡已更新并通过。"
            con.execute(
                """
                INSERT INTO characters(group_id,user_id,qq_id,game_name,display_name,identity,faction,ability,power_level,audit_status,location_key,hp,energy,water,satiety,mood,money,created_at,updated_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
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
            cur = con.execute(
                "UPDATE characters SET private_origin=?, updated_at=? WHERE qq_id=?",
                (private_origin, utc_now_iso(), qq_id),
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
            if int(character["hp"]) <= 0 and not (self._looks_like_heal(text) or self._looks_like_rest(text)):
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
                       characters.ability, characters.power_level
                FROM actions
                JOIN characters ON characters.id=actions.character_id
                WHERE actions.group_id=? AND actions.round_no=? AND actions.status='pending'
                ORDER BY actions.submitted_at ASC
                """,
                (group_id, round_no),
            ).fetchall()

            outcomes = []
            for row in actions:
                outcomes.append(self._resolve_action(con, group_id, row))

            self._apply_hourly_decay(con, group_id)
            roster = self._location_roster(con, group_id)
            public_summary = self._build_public_summary(round_no, outcomes, npc_updates, roster, active_event)
            private_results = {}
            for outcome in outcomes:
                private_text = self._build_private_result(con, group_id, round_no, outcome)
                private_results[str(outcome["qq_id"])] = private_text
                con.execute(
                    """
                    INSERT INTO history(group_id,round_no,visibility,character_id,kind,text,created_at)
                    VALUES(?,?,?,?,?,?,?)
                    """,
                    (group_id, round_no, "private", outcome["character_id"], "round_result", private_text, utc_now_iso()),
                )
                con.execute(
                    "UPDATE actions SET status='resolved', result_text=?, warnings=?, resolved_at=? WHERE id=?",
                    (private_text, dumps(outcome.get("warnings", [])), utc_now_iso(), outcome["action_id"]),
                )
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
                "public_summary": public_summary,
                "private_results": private_results,
                "npc_updates": npc_updates,
                "active_event": active_event,
                "outcomes": outcomes,
            }

        return self.db.run(work)

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
                    npcs = [dict(row) for row in con.execute(f"SELECT npc_key,group_id,name,role,faction,location_key,disposition FROM npcs WHERE group_id IN ({placeholders}) ORDER BY group_id,name LIMIT 200", tuple(world_ids)).fetchall()]
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
                "power_level": self.clean_text(str(payload.get("power_level") if payload.get("power_level") is not None else (row["power_level"] if row else "Level 0")), 20) or "Level 0",
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
                    UPDATE characters SET user_id=?,game_name=?,display_name=?,identity=?,faction=?,ability=?,power_level=?,audit_status=?,location_key=?,hp=?,energy=?,water=?,satiety=?,mood=?,money=?,updated_at=?
                    WHERE id=?
                    """,
                    (user_id, *fields.values(), now, row["id"]),
                )
            else:
                con.execute(
                    """
                    INSERT INTO characters(group_id,user_id,qq_id,game_name,display_name,identity,faction,ability,power_level,audit_status,location_key,hp,energy,water,satiety,mood,money,created_at,updated_at)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (group_id, user_id, qq_id, *fields.values(), now, now),
                )
            return dict(con.execute("SELECT * FROM characters WHERE group_id=? AND qq_id=?", (group_id, qq_id)).fetchone())

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
                f"阵营：{char['faction'] or '无'}",
                f"能力：{char['ability'] or '未设定'}",
                f"战斗力：{char['power_level']}",
                f"审核：{self.audit_label(char['audit_status'])}",
                f"位置：{location_name}",
                f"生命：{char['hp']}/100",
                f"精力：{char['energy']}/100",
                f"水分：{char['water']}/100",
                f"饱食度：{char['satiety']}/100",
                f"心情：{char['mood']}/100",
                f"学都币：{char['money']}",
                f"背包：{bag}",
                f"本轮行动：{'已提交' if pending else '未提交'}",
                f"当前轮次：第 {world['current_round'] if world else '-'} 轮",
                f"下次结算：{self.format_time(world['next_tick_at']) if world else '-'}",
            ]
        )

    def _resolve_action(self, con: sqlite3.Connection, group_id: str, row: sqlite3.Row) -> dict[str, Any]:
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
        location_key = row["location_key"]
        summary = "你的行动被记录并执行，具体细节会在本轮剧情里展开。"
        accepted = True
        if target:
            if self._can_move(con, group_id, row["location_key"], target["location_key"]):
                location_key = target["location_key"]
                summary = f"你从{old_location['name'] if old_location else '原地'}去了{target['name']}。"
                energy_delta = -10
            else:
                accepted = False
                target_name = target["name"]
                summary = f"你尝试前往{target_name}，但地图路线不成立，本轮留在原地。"
                warnings.append(f"地图规则拦截：当前位置不能直接前往{target_name}。")
                energy_delta = -2
            restricted_warning = self._restricted_location_warning(target, text) if accepted else ""
            if restricted_warning:
                warnings.append(restricted_warning)
                energy_delta -= 3
                mood_delta -= 1
        elif self._looks_like_rest(text):
            summary = "你把这一轮用于休整，精力和心情略有恢复。"
            energy_delta = 12
            mood_delta = 3
        elif self._looks_like_buy(con, group_id, text):
            (
                summary,
                money_delta,
                hp_delta,
                energy_delta,
                water_delta,
                satiety_delta,
                mood_delta,
            ) = self._resolve_purchase(con, group_id, row)
        elif self._looks_like_heal(text):
            cost = min(int(row["money"]), 30)
            if cost >= 10:
                money_delta = -cost
                hp_delta = min(25, cost)
                summary = f"你接受了基础治疗，花费 {cost} 学都币，生命有所恢复。"
            else:
                summary = "你想治疗伤势，但学都币不太够。"
                warnings.append("治疗失败：余额不足。")
        elif self._looks_like_work(text):
            gain = random.randint(8, 20)
            money_delta = gain
            energy_delta = -14
            summary = f"你做了些力所能及的事，获得 {gain} 学都币。"
        if self._looks_like_ability_use(text):
            power_cost = self._power_use_cost(row["power_level"], text)
            energy_delta -= power_cost
            if int(row["energy"]) < 25:
                mood_delta -= 2
                warnings.append("精力不足会影响个人现实演算，能力表现被压低。")
            warnings.append(f"能力使用消耗：精力 -{power_cost}。")
        risk_score = self._action_risk_score(text)
        if risk_score:
            energy_delta -= min(8, risk_score * 2)
            if random.random() < min(0.18 + risk_score * 0.09, 0.72):
                injury = random.randint(2 + risk_score, 6 + risk_score * 3)
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
        if new_water <= 15:
            new_energy = clamp(new_energy - 5)
            warnings.append("水分偏低，精力受到影响。")
        if new_satiety <= 15:
            new_mood = clamp(new_mood - 3)
            warnings.append("饱食度偏低，心情受到影响。")
        con.execute(
            """
            UPDATE characters SET location_key=?,hp=?,energy=?,water=?,satiety=?,mood=?,money=?,updated_at=? WHERE id=?
            """,
            (location_key, new_hp, new_energy, new_water, new_satiety, new_mood, new_money, utc_now_iso(), row["character_id"]),
        )
        encounters = self._encounters(con, group_id, location_key, row["character_id"])
        self._small_relationship_changes(con, group_id, row["character_id"], encounters)
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
            },
        }

    def _build_public_summary(
        self,
        round_no: int,
        outcomes: list[dict[str, Any]],
        npc_updates: list[str],
        roster: dict[str, list[str]],
        event: dict[str, Any] | None,
    ) -> str:
        lines = [f"【第 {round_no} 轮学园都市更新】"]
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
    ) -> str:
        char = con.execute("SELECT * FROM characters WHERE id=?", (outcome["character_id"],)).fetchone()
        loc = self._location(con, group_id, outcome["location_key"])
        lines = [f"【第 {round_no} 轮个人结果】", outcome["summary"]]
        if loc:
            lines.append(f"当前位置：{loc['name']}")
        if outcome["encounters"]:
            lines.append("你遇到了：" + "、".join(item["name"] for item in outcome["encounters"][:6]))
        if outcome["warnings"]:
            lines.append("提醒：" + "；".join(outcome["warnings"]))
        deltas = outcome["deltas"]
        delta_text = "，".join(f"{key} {value:+d}" for key, value in deltas.items() if value)
        if delta_text:
            lines.append("本轮变化：" + delta_text)
        if char:
            lines.append(
                f"状态：生命 {char['hp']}/100，精力 {char['energy']}/100，水分 {char['water']}/100，饱食度 {char['satiety']}/100，心情 {char['mood']}/100，学都币 {char['money']}"
            )
        return "\n".join(lines)

    def _move_npcs(self, con: sqlite3.Connection, group_id: str) -> list[str]:
        rows = con.execute("SELECT * FROM npcs WHERE group_id=?", (group_id,)).fetchall()
        updates = []
        for npc in rows:
            neighbors = con.execute(
                "SELECT to_location_key FROM location_edges WHERE group_id=? AND from_location_key=?",
                (group_id, npc["location_key"]),
            ).fetchall()
            if not neighbors or random.random() > 0.55:
                continue
            next_key = random.choice(neighbors)["to_location_key"]
            old = self._location(con, group_id, npc["location_key"])
            new = self._location(con, group_id, next_key)
            con.execute("UPDATE npcs SET location_key=?, updated_at=? WHERE id=?", (next_key, utc_now_iso(), npc["id"]))
            if old and new:
                updates.append(f"{npc['name']}从{old['name']}去了{new['name']}")
        return updates

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

    def _resolve_purchase(self, con: sqlite3.Connection, group_id: str, row: sqlite3.Row) -> tuple[str, int, int, int, int, int, int]:
        items = con.execute(
            "SELECT * FROM shop_items WHERE group_id=? AND is_active=1 ORDER BY length(name) DESC, price ASC",
            (group_id,),
        ).fetchall()
        text = str(row["text"])
        selected = self._select_purchase_item(items, text, int(row["money"]))
        if not selected:
            selected = next((item for item in items if item["price"] <= row["money"] and int(item["stock"]) != 0), None)
        if not selected:
            return "你想买东西，但学都币不太够或商品已经售罄。", 0, 0, 0, -3, -2, 0
        if selected["price"] > row["money"]:
            return f"你想购买{selected['name']}，但学都币不足。", 0, 0, 0, -3, -2, 0
        if int(selected["stock"]) == 0:
            return f"你想购买{selected['name']}，但已经售罄。", 0, 0, 0, -3, -2, 0
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
        water_delta = int_value(effect.get("water"), 0) - 3
        satiety_delta = int_value(effect.get("satiety"), 0) - 2
        hp_delta = int_value(effect.get("hp"), 0)
        energy_delta = int_value(effect.get("energy"), 0)
        mood_delta = int_value(effect.get("mood"), 0)
        return (
            f"你购买了{selected['name']}，花费 {selected['price']} 学都币，物品已放入背包。",
            -int(selected["price"]),
            hp_delta,
            energy_delta,
            water_delta,
            satiety_delta,
            mood_delta,
        )

    def _select_purchase_item(self, items: list[sqlite3.Row], text: str, money: int) -> sqlite3.Row | None:
        lower_text = text.lower()
        explicit_intents = ("买", "购买", "付款", "结账", "buy")
        if any(word in text or word in lower_text for word in explicit_intents):
            for item in items:
                if item["name"] in text:
                    return item

        keyword_groups = (
            (self._purchase_intent_words("food"), ("便当", "套餐", "午餐", "折扣券")),
            (self._purchase_intent_words("water"), ("水", "饮料", "果冻")),
            (self._purchase_intent_words("heal"), ("绷带", "凝胶", "医疗")),
            (self._purchase_intent_words("travel"), ("通勤", "地下铁", "一日券")),
            (self._purchase_intent_words("info"), ("书库", "检索", "资料卡", "点数")),
        )
        for triggers, name_hints in keyword_groups:
            if not any(word in text for word in triggers):
                continue
            candidates = [
                item
                for item in items
                if int(item["stock"]) != 0
                and int(item["price"]) <= money
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
        return (matched_hint, -recovery, int(item["price"]))

    def _purchase_intent_words(self, category: str = "") -> tuple[str, ...]:
        groups = {
            "food": ("吃饭", "点餐", "用餐", "午餐", "晚餐", "早餐", "热餐", "便当", "套餐", "饿"),
            "water": ("喝水", "饮水", "补水", "口渴", "喝饮料", "补充饮料"),
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

    def _extract_location(self, con: sqlite3.Connection, group_id: str, current_key: str, text: str) -> sqlite3.Row | None:
        rows = con.execute("SELECT * FROM locations WHERE group_id=?", (group_id,)).fetchall()
        matches = [row for row in rows if row["name"] in text or row["location_key"] in text]
        if not matches:
            return None
        target_order = self._rank_location_mentions(matches, text)
        for row in target_order:
            if row["location_key"] != current_key and self._can_move(con, group_id, current_key, row["location_key"]):
                return row
        for row in target_order:
            if row["location_key"] != current_key:
                return row
        for row in target_order:
            if row["location_key"] == current_key:
                return row
        return target_order[0]

    def _rank_location_mentions(self, rows: list[sqlite3.Row], text: str) -> list[sqlite3.Row]:
        intent_words = ("前往", "去", "到", "进入", "调查", "潜入", "硬闯", "搜索", "查看", "拜访", "抵达")

        def score(row: sqlite3.Row) -> tuple[int, int, int]:
            name = str(row["name"] or "")
            key = str(row["location_key"] or "")
            indexes = [idx for idx in (text.find(name), text.find(key)) if idx >= 0]
            first_index = min(indexes) if indexes else len(text)
            before = text[max(0, first_index - 12):first_index]
            intent = 0 if any(word in before for word in intent_words) else 1
            # Longer names are usually more specific, so prefer them when intent is tied.
            return (intent, first_index, -len(name))

        return sorted(rows, key=score)

    def _encounters(self, con: sqlite3.Connection, group_id: str, location_key: str, character_id: int) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for row in con.execute(
            "SELECT id,game_name FROM characters WHERE group_id=? AND location_key=? AND id<>? AND audit_status='approved'",
            (group_id, location_key, character_id),
        ).fetchall():
            results.append({"type": "player", "id": str(row["id"]), "name": row["game_name"]})
        for row in con.execute(
            "SELECT npc_key,name FROM npcs WHERE group_id=? AND location_key=?",
            (group_id, location_key),
        ).fetchall():
            results.append({"type": "npc", "id": row["npc_key"], "name": row["name"]})
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
            SELECT locations.name AS location_name, npcs.name AS name
            FROM npcs JOIN locations ON locations.group_id=npcs.group_id AND locations.location_key=npcs.location_key
            WHERE npcs.group_id=?
            """,
            (group_id,),
        ).fetchall():
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

    def cheat_reason(self, text: str) -> str:
        compact = re.sub(r"\s+", "", text.lower())
        for pattern in CHEAT_PATTERNS:
            normalized_pattern = re.sub(r"\s+", "", pattern.lower())
            if normalized_pattern in compact:
                return f"行动被反作弊拦截：包含高风险词“{pattern}”。"
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
        return re.sub(r"\s+", " ", text or "").strip()

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
        return any(word in text.lower() for word in ("休息", "睡觉", "放松", "恢复", "躺", "自习", "rest", "sleep"))

    def _looks_like_buy(self, con: sqlite3.Connection, group_id: str, text: str) -> bool:
        if any(word in text or word in text.lower() for word in ("买", "购买", "吃饭", "点餐", "用餐", "购物", "消费", "付款", "结账", "buy")):
            return True
        broad_purchase_words = (
            *self._purchase_intent_words("food"),
            *self._purchase_intent_words("water"),
            *self._purchase_intent_words("travel"),
        )
        if any(word in text for word in broad_purchase_words):
            return True
        if self._purchase_item_mentioned_with_intent(con, group_id, text):
            return True
        return False

    def _purchase_item_mentioned_with_intent(self, con: sqlite3.Connection, group_id: str, text: str) -> bool:
        if not any(word in text for word in ("要", "拿", "买", "购买", "兑换", "付款", "结账", "补充")):
            return False
        return bool(con.execute(
            "SELECT 1 FROM shop_items WHERE group_id=? AND is_active=1 AND instr(?, name)>0 LIMIT 1",
            (group_id, text),
        ).fetchone())

    def _looks_like_work(self, text: str) -> bool:
        return any(word in text for word in ("兼职", "打工", "帮忙", "跑腿", "工作", "摆摊"))

    def _looks_like_heal(self, text: str) -> bool:
        return any(word in text.lower() for word in ("医院", "治疗", "看病", "疗伤", "包扎", "hospital", "heal", "clinic", "doctor"))

    def _restricted_location_warning(self, target: sqlite3.Row, text: str) -> str:
        tags = set(loads(target["tags"], []))
        name = str(target["name"] or "")
        if "禁区" in tags or "高风险" in tags:
            if any(word in text for word in ("硬闯", "潜入", "破解", "翻墙", "强行", "偷", "黑入", "突破")):
                return f"{name}属于高权限/高风险区域，本轮只能触及外围痕迹，强行深入会被警备或权限边界拦下。"
            return f"{name}有权限边界，本轮按公开区域或外围行动处理。"
        if "权限" in tags and not any(word in text for word in ("通行证", "许可", "邀请", "登记", "申请")):
            return f"{name}需要通行许可；没有许可时只能在外围活动。"
        return ""

    def _looks_like_ability_use(self, text: str) -> bool:
        return any(
            word in text
            for word in (
                "使用能力",
                "发动能力",
                "能力",
                "AIM",
                "个人现实",
                "电磁",
                "念动",
                "空间",
                "心理",
                "矢量",
                "演算",
                "超能力",
                "异能",
            )
        )

    def _power_use_cost(self, power_level: str, text: str) -> int:
        level_match = re.search(r"(?:level|lv)\.?\s*([0-5])", str(power_level or ""), re.I)
        level = int(level_match.group(1)) if level_match else 0
        base = 4 + level * 2
        if any(word in text for word in ("全力", "连续", "长时间", "大范围", "精密", "战斗")):
            base += 5
        if level <= 0:
            base = max(3, base - 2)
        return min(base, 22)

    def _action_risk_score(self, text: str) -> int:
        risk_keywords = (
            ("战斗", "袭击", "硬闯", "追逐", "危险"),
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
