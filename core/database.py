from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, TypeVar

from .defaults import DEFAULT_LOCATIONS, DEFAULT_NPCS

T = TypeVar("T")
CN_TZ = timezone(timedelta(hours=8), "Asia/Shanghai")


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def utc_now_iso() -> str:
    return utc_now().isoformat()


def cn_today() -> str:
    return datetime.now(CN_TZ).strftime("%Y-%m-%d")


def iso_after_minutes(minutes: int) -> str:
    return (utc_now() + timedelta(minutes=minutes)).isoformat()


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def password_hash(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("ascii"), 120000)
    return f"pbkdf2_sha256${salt}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, salt, digest_hex = stored.split("$", 2)
    except ValueError:
        return False
    if scheme != "pbkdf2_sha256":
        return False
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("ascii"), 120000)
    return hmac.compare_digest(digest.hex(), digest_hex)


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    return dict(row) if row is not None else None


def rows_to_dicts(rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
    return [dict(row) for row in rows]


class TextWorldDB:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._lock = threading.RLock()

    def connect(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(self.db_path, timeout=30)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys = ON")
        try:
            con.execute("PRAGMA journal_mode = WAL")
        except sqlite3.OperationalError:
            pass
        return con

    def run(self, fn: Callable[[sqlite3.Connection], T]) -> T:
        with self._lock:
            with self.connect() as con:
                result = fn(con)
                con.commit()
                return result

    def init(self, admin_username: str, admin_password: str) -> None:
        def work(con: sqlite3.Connection) -> None:
            self._migrate(con)
            self._ensure_admin(con, admin_username, admin_password)
            self._backfill_character_users(con)

        self.run(work)

    def _migrate(self, con: sqlite3.Connection) -> None:
        con.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              username TEXT NOT NULL UNIQUE,
              password_hash TEXT NOT NULL,
              role TEXT NOT NULL DEFAULT 'player',
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS sessions (
              token TEXT PRIMARY KEY,
              user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
              expires_at TEXT NOT NULL,
              created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS worlds (
              group_id TEXT PRIMARY KEY,
              group_origin TEXT NOT NULL DEFAULT '',
              name TEXT NOT NULL DEFAULT '学院都市',
              enabled INTEGER NOT NULL DEFAULT 1,
              current_round INTEGER NOT NULL DEFAULT 1,
              cycle_minutes INTEGER NOT NULL DEFAULT 60,
              event_cycle_minutes INTEGER NOT NULL DEFAULT 120,
              next_tick_at TEXT NOT NULL,
              next_event_at TEXT NOT NULL,
              last_daily_status_date TEXT NOT NULL DEFAULT '',
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS locations (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              group_id TEXT NOT NULL REFERENCES worlds(group_id) ON DELETE CASCADE,
              location_key TEXT NOT NULL,
              name TEXT NOT NULL,
              description TEXT NOT NULL DEFAULT '',
              tags TEXT NOT NULL DEFAULT '[]',
              sort_order INTEGER NOT NULL DEFAULT 0,
              UNIQUE(group_id, location_key)
            );

            CREATE TABLE IF NOT EXISTS location_edges (
              group_id TEXT NOT NULL REFERENCES worlds(group_id) ON DELETE CASCADE,
              from_location_key TEXT NOT NULL,
              to_location_key TEXT NOT NULL,
              PRIMARY KEY(group_id, from_location_key, to_location_key)
            );

            CREATE TABLE IF NOT EXISTS characters (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              group_id TEXT NOT NULL REFERENCES worlds(group_id) ON DELETE CASCADE,
              user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
              qq_id TEXT NOT NULL,
              game_name TEXT NOT NULL,
              display_name TEXT NOT NULL,
              identity TEXT NOT NULL DEFAULT '',
              faction TEXT NOT NULL DEFAULT '',
              ability TEXT NOT NULL DEFAULT '',
              power_level TEXT NOT NULL DEFAULT 'D',
              audit_status TEXT NOT NULL DEFAULT 'pending',
              location_key TEXT NOT NULL DEFAULT 'school_gate',
              hp INTEGER NOT NULL DEFAULT 100,
              energy INTEGER NOT NULL DEFAULT 100,
              water INTEGER NOT NULL DEFAULT 80,
              satiety INTEGER NOT NULL DEFAULT 80,
              mood INTEGER NOT NULL DEFAULT 70,
              money INTEGER NOT NULL DEFAULT 100,
              private_origin TEXT NOT NULL DEFAULT '',
              last_checkin_date TEXT NOT NULL DEFAULT '',
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              UNIQUE(group_id, qq_id),
              UNIQUE(group_id, game_name)
            );

            CREATE TABLE IF NOT EXISTS npcs (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              group_id TEXT NOT NULL REFERENCES worlds(group_id) ON DELETE CASCADE,
              npc_key TEXT NOT NULL,
              name TEXT NOT NULL,
              role TEXT NOT NULL DEFAULT '',
              faction TEXT NOT NULL DEFAULT '',
              location_key TEXT NOT NULL DEFAULT 'school_gate',
              disposition TEXT NOT NULL DEFAULT '中立',
              memory TEXT NOT NULL DEFAULT '',
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              UNIQUE(group_id, npc_key)
            );

            CREATE TABLE IF NOT EXISTS actions (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              group_id TEXT NOT NULL REFERENCES worlds(group_id) ON DELETE CASCADE,
              character_id INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
              round_no INTEGER NOT NULL,
              text TEXT NOT NULL,
              status TEXT NOT NULL DEFAULT 'pending',
              result_text TEXT NOT NULL DEFAULT '',
              warnings TEXT NOT NULL DEFAULT '[]',
              submitted_at TEXT NOT NULL,
              resolved_at TEXT NOT NULL DEFAULT '',
              UNIQUE(group_id, character_id, round_no)
            );

            CREATE TABLE IF NOT EXISTS event_presets (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              group_id TEXT NOT NULL REFERENCES worlds(group_id) ON DELETE CASCADE,
              title TEXT NOT NULL,
              description TEXT NOT NULL DEFAULT '',
              effect_json TEXT NOT NULL DEFAULT '{}',
              is_public INTEGER NOT NULL DEFAULT 1,
              trigger_next INTEGER NOT NULL DEFAULT 0,
              used_at TEXT NOT NULL DEFAULT '',
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS inventory (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              character_id INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
              item_name TEXT NOT NULL,
              quantity INTEGER NOT NULL DEFAULT 0,
              meta_json TEXT NOT NULL DEFAULT '{}',
              UNIQUE(character_id, item_name)
            );

            CREATE TABLE IF NOT EXISTS shop_items (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              group_id TEXT NOT NULL REFERENCES worlds(group_id) ON DELETE CASCADE,
              name TEXT NOT NULL,
              description TEXT NOT NULL DEFAULT '',
              price INTEGER NOT NULL DEFAULT 0,
              stock INTEGER NOT NULL DEFAULT -1,
              effect_json TEXT NOT NULL DEFAULT '{}',
              is_active INTEGER NOT NULL DEFAULT 1,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              UNIQUE(group_id, name)
            );

            CREATE TABLE IF NOT EXISTS relationships (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              group_id TEXT NOT NULL REFERENCES worlds(group_id) ON DELETE CASCADE,
              source_type TEXT NOT NULL,
              source_id TEXT NOT NULL,
              target_type TEXT NOT NULL,
              target_id TEXT NOT NULL,
              score INTEGER NOT NULL DEFAULT 0,
              updated_at TEXT NOT NULL,
              UNIQUE(group_id, source_type, source_id, target_type, target_id)
            );

            CREATE TABLE IF NOT EXISTS history (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              group_id TEXT NOT NULL REFERENCES worlds(group_id) ON DELETE CASCADE,
              round_no INTEGER NOT NULL DEFAULT 0,
              visibility TEXT NOT NULL DEFAULT 'public',
              character_id INTEGER REFERENCES characters(id) ON DELETE SET NULL,
              kind TEXT NOT NULL DEFAULT 'event',
              text TEXT NOT NULL,
              created_at TEXT NOT NULL
            );
            """
        )
        self._add_missing_columns(con)
        con.executescript(
            """
            CREATE INDEX IF NOT EXISTS idx_actions_due ON actions(group_id, round_no, status);
            CREATE INDEX IF NOT EXISTS idx_characters_user ON characters(user_id);
            CREATE INDEX IF NOT EXISTS idx_characters_private ON characters(qq_id);
            CREATE INDEX IF NOT EXISTS idx_history_scope ON history(group_id, visibility, id);
            CREATE INDEX IF NOT EXISTS idx_inventory_character ON inventory(character_id);
            CREATE INDEX IF NOT EXISTS idx_relationships_source ON relationships(group_id, source_type, source_id);
            """
        )

    def _add_missing_columns(self, con: sqlite3.Connection) -> None:
        column_specs: dict[str, dict[str, str]] = {
            "users": {
                "role": "TEXT NOT NULL DEFAULT 'player'",
                "updated_at": "TEXT NOT NULL DEFAULT ''",
            },
            "worlds": {
                "group_origin": "TEXT NOT NULL DEFAULT ''",
                "enabled": "INTEGER NOT NULL DEFAULT 1",
                "current_round": "INTEGER NOT NULL DEFAULT 1",
                "cycle_minutes": "INTEGER NOT NULL DEFAULT 60",
                "event_cycle_minutes": "INTEGER NOT NULL DEFAULT 120",
                "last_daily_status_date": "TEXT NOT NULL DEFAULT ''",
            },
            "characters": {
                "user_id": "INTEGER REFERENCES users(id) ON DELETE SET NULL",
                "display_name": "TEXT NOT NULL DEFAULT ''",
                "faction": "TEXT NOT NULL DEFAULT ''",
                "ability": "TEXT NOT NULL DEFAULT ''",
                "power_level": "TEXT NOT NULL DEFAULT 'D'",
                "audit_status": "TEXT NOT NULL DEFAULT 'pending'",
                "location_key": "TEXT NOT NULL DEFAULT 'school_gate'",
                "hp": "INTEGER NOT NULL DEFAULT 100",
                "energy": "INTEGER NOT NULL DEFAULT 100",
                "water": "INTEGER NOT NULL DEFAULT 80",
                "satiety": "INTEGER NOT NULL DEFAULT 80",
                "mood": "INTEGER NOT NULL DEFAULT 70",
                "money": "INTEGER NOT NULL DEFAULT 100",
                "private_origin": "TEXT NOT NULL DEFAULT ''",
                "last_checkin_date": "TEXT NOT NULL DEFAULT ''",
            },
            "npcs": {
                "faction": "TEXT NOT NULL DEFAULT ''",
                "memory": "TEXT NOT NULL DEFAULT ''",
            },
            "actions": {
                "result_text": "TEXT NOT NULL DEFAULT ''",
                "warnings": "TEXT NOT NULL DEFAULT '[]'",
                "resolved_at": "TEXT NOT NULL DEFAULT ''",
            },
            "event_presets": {
                "effect_json": "TEXT NOT NULL DEFAULT '{}'",
                "is_public": "INTEGER NOT NULL DEFAULT 1",
                "trigger_next": "INTEGER NOT NULL DEFAULT 0",
                "used_at": "TEXT NOT NULL DEFAULT ''",
            },
            "shop_items": {
                "stock": "INTEGER NOT NULL DEFAULT -1",
                "effect_json": "TEXT NOT NULL DEFAULT '{}'",
                "is_active": "INTEGER NOT NULL DEFAULT 1",
            },
            "history": {
                "round_no": "INTEGER NOT NULL DEFAULT 0",
                "visibility": "TEXT NOT NULL DEFAULT 'public'",
                "character_id": "INTEGER REFERENCES characters(id) ON DELETE SET NULL",
                "kind": "TEXT NOT NULL DEFAULT 'event'",
            },
        }
        for table, specs in column_specs.items():
            existing = {row["name"] for row in con.execute(f"PRAGMA table_info({table})").fetchall()}
            for column, spec in specs.items():
                if column not in existing:
                    con.execute(f"ALTER TABLE {table} ADD COLUMN {column} {spec}")
        con.execute("UPDATE characters SET display_name=game_name WHERE display_name=''")

    def _backfill_character_users(self, con: sqlite3.Connection) -> None:
        rows = con.execute(
            "SELECT id,qq_id,game_name,user_id FROM characters WHERE user_id IS NULL OR user_id=''"
        ).fetchall()
        for row in rows:
            username = str(row["game_name"] or row["qq_id"]).strip()
            if not username:
                continue
            existing_user = con.execute("SELECT id,role FROM users WHERE username=?", (username,)).fetchone()
            if existing_user and existing_user["role"] == "player" and not self._user_belongs_to_other_qq(con, int(existing_user["id"]), str(row["qq_id"])):
                user_id = int(existing_user["id"])
            elif existing_user:
                username = self._available_player_username(con, f"{username}_{row['qq_id']}")
                existing_player = con.execute("SELECT id FROM users WHERE username=?", (username,)).fetchone()
                if existing_player:
                    user_id = int(existing_player["id"])
                else:
                    now = utc_now_iso()
                    cur = con.execute(
                        "INSERT INTO users(username,password_hash,role,created_at,updated_at) VALUES(?,?,?,?,?)",
                        (username, password_hash(str(row["qq_id"])[-6:] or "123456"), "player", now, now),
                    )
                    user_id = int(cur.lastrowid)
            else:
                now = utc_now_iso()
                cur = con.execute(
                    "INSERT INTO users(username,password_hash,role,created_at,updated_at) VALUES(?,?,?,?,?)",
                    (username, password_hash(str(row["qq_id"])[-6:] or "123456"), "player", now, now),
                )
                user_id = int(cur.lastrowid)
            con.execute("UPDATE characters SET user_id=? WHERE id=?", (user_id, row["id"]))

    def _user_belongs_to_other_qq(self, con: sqlite3.Connection, user_id: int, qq_id: str) -> bool:
        return bool(con.execute(
            "SELECT 1 FROM characters WHERE user_id=? AND qq_id<>? LIMIT 1",
            (user_id, qq_id),
        ).fetchone())

    def _available_player_username(self, con: sqlite3.Connection, base: str) -> str:
        username = base[:32] or "player"
        if not con.execute("SELECT 1 FROM users WHERE username=?", (username,)).fetchone():
            return username
        for index in range(2, 1000):
            suffix = f"_{index}"
            candidate = (username[: 32 - len(suffix)] + suffix) if len(username) + len(suffix) > 32 else username + suffix
            if not con.execute("SELECT 1 FROM users WHERE username=?", (candidate,)).fetchone():
                return candidate
        raise ValueError("无法为旧角色生成可用玩家账号。")

    def _ensure_admin(self, con: sqlite3.Connection, username: str, password: str) -> None:
        now = utc_now_iso()
        row = con.execute("SELECT id FROM users WHERE username=?", (username,)).fetchone()
        if row:
            return
        con.execute(
            "INSERT INTO users(username,password_hash,role,created_at,updated_at) VALUES(?,?,?,?,?)",
            (username, password_hash(password), "admin", now, now),
        )

    def create_session(self, username: str, password: str) -> str | None:
        def work(con: sqlite3.Connection) -> str | None:
            con.execute("DELETE FROM sessions WHERE expires_at<=?", (utc_now_iso(),))
            row = con.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
            if not row or not verify_password(password, row["password_hash"]):
                return None
            token = secrets.token_urlsafe(32)
            con.execute(
                "INSERT INTO sessions(token,user_id,expires_at,created_at) VALUES(?,?,?,?)",
                (token, row["id"], (utc_now() + timedelta(days=14)).isoformat(), utc_now_iso()),
            )
            return token

        return self.run(work)

    def ensure_player_user(
        self,
        con: sqlite3.Connection,
        username: str,
        initial_password: str,
        user_id: int | None = None,
        *,
        reset_password: bool = False,
    ) -> int:
        now = utc_now_iso()
        if reset_password and len(initial_password) < 6:
            raise ValueError("玩家密码至少 6 位。")
        if user_id:
            existing = con.execute("SELECT id FROM users WHERE username=? AND id<>?", (username, user_id)).fetchone()
            if existing:
                raise ValueError("这个游戏名对应的账号已存在。")
            row = con.execute("SELECT id,role FROM users WHERE id=?", (user_id,)).fetchone()
            if row:
                if row["role"] != "player":
                    raise ValueError("这个账号名不可用于玩家角色。")
                con.execute("UPDATE users SET username=?, updated_at=? WHERE id=?", (username, now, user_id))
                if reset_password:
                    con.execute(
                        "UPDATE users SET password_hash=?, updated_at=? WHERE id=?",
                        (password_hash(initial_password), now, user_id),
                    )
                    con.execute("DELETE FROM sessions WHERE user_id=?", (user_id,))
                return int(user_id)
        row = con.execute("SELECT id,role FROM users WHERE username=?", (username,)).fetchone()
        if row:
            if row["role"] != "player":
                raise ValueError("这个账号名不可用于玩家角色。")
            if reset_password:
                con.execute(
                    "UPDATE users SET password_hash=?, updated_at=? WHERE id=?",
                    (password_hash(initial_password), now, row["id"]),
                )
                con.execute("DELETE FROM sessions WHERE user_id=?", (row["id"],))
            return int(row["id"])
        cur = con.execute(
            "INSERT INTO users(username,password_hash,role,created_at,updated_at) VALUES(?,?,?,?,?)",
            (username, password_hash(initial_password), "player", now, now),
        )
        return int(cur.lastrowid)

    def change_password(self, user_id: int, old_password: str, new_password: str) -> tuple[bool, str]:
        if len(new_password) < 6:
            return False, "新密码至少 6 位。"

        def work(con: sqlite3.Connection) -> tuple[bool, str]:
            row = con.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
            if not row or not verify_password(old_password, row["password_hash"]):
                return False, "旧密码错误。"
            con.execute(
                "UPDATE users SET password_hash=?, updated_at=? WHERE id=?",
                (password_hash(new_password), utc_now_iso(), user_id),
            )
            con.execute("DELETE FROM sessions WHERE user_id=?", (user_id,))
            return True, "密码已修改，请重新登录。"

        return self.run(work)

    def user_by_session(self, token: str) -> dict[str, Any] | None:
        def work(con: sqlite3.Connection) -> dict[str, Any] | None:
            row = con.execute(
                """
                SELECT users.* FROM sessions
                JOIN users ON users.id=sessions.user_id
                WHERE sessions.token=? AND sessions.expires_at>?
                """,
                (token, utc_now_iso()),
            ).fetchone()
            return row_to_dict(row)

        return self.run(work)

    def delete_session(self, token: str) -> None:
        self.run(lambda con: con.execute("DELETE FROM sessions WHERE token=?", (token,)))

    def ensure_world(
        self,
        group_id: str,
        group_origin: str,
        cycle_minutes: int,
        event_cycle_minutes: int,
    ) -> dict[str, Any]:
        def work(con: sqlite3.Connection) -> dict[str, Any]:
            now = utc_now_iso()
            row = con.execute("SELECT * FROM worlds WHERE group_id=?", (group_id,)).fetchone()
            if not row:
                con.execute(
                    """
                    INSERT INTO worlds(group_id,group_origin,name,enabled,current_round,cycle_minutes,event_cycle_minutes,next_tick_at,next_event_at,created_at,updated_at)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        group_id,
                        group_origin,
                        "学院都市",
                        1,
                        1,
                        cycle_minutes,
                        event_cycle_minutes,
                        iso_after_minutes(cycle_minutes),
                        iso_after_minutes(event_cycle_minutes),
                        now,
                        now,
                    ),
                )
                self._seed_defaults(con, group_id)
            elif group_origin and not row["group_origin"]:
                con.execute(
                    "UPDATE worlds SET group_origin=?, updated_at=? WHERE group_id=?",
                    (group_origin, now, group_id),
                )
            return row_to_dict(con.execute("SELECT * FROM worlds WHERE group_id=?", (group_id,)).fetchone()) or {}

        return self.run(work)

    def _seed_defaults(self, con: sqlite3.Connection, group_id: str) -> None:
        for index, (key, location) in enumerate(DEFAULT_LOCATIONS.items()):
            con.execute(
                """
                INSERT OR IGNORE INTO locations(group_id,location_key,name,description,tags,sort_order)
                VALUES(?,?,?,?,?,?)
                """,
                (
                    group_id,
                    key,
                    location.name,
                    location.description,
                    json.dumps(location.tags, ensure_ascii=False),
                    index,
                ),
            )
            for neighbor in location.neighbors:
                con.execute(
                    "INSERT OR IGNORE INTO location_edges(group_id,from_location_key,to_location_key) VALUES(?,?,?)",
                    (group_id, key, neighbor),
                )
        for key, npc in DEFAULT_NPCS.items():
            con.execute(
                """
                INSERT OR IGNORE INTO npcs(group_id,npc_key,name,role,location_key,disposition,created_at,updated_at)
                VALUES(?,?,?,?,?,?,?,?)
                """,
                (group_id, key, npc.name, npc.role, npc.location_id, npc.disposition, utc_now_iso(), utc_now_iso()),
            )
        defaults = [
            ("矿泉水", "补充水分的普通瓶装水。", 5, {"water": 20}),
            ("面包", "简单管饱的面包。", 8, {"satiety": 20}),
            ("便携绷带", "处理轻伤的基础医疗用品。", 20, {"hp": 10}),
            ("能量饮料", "短时间补充精力，略微影响心情。", 18, {"energy": 15, "mood": -1}),
        ]
        for name, desc, price, effect in defaults:
            con.execute(
                """
                INSERT OR IGNORE INTO shop_items(group_id,name,description,price,stock,effect_json,is_active,created_at,updated_at)
                VALUES(?,?,?,?,?,?,?,?,?)
                """,
                (group_id, name, desc, price, -1, json.dumps(effect, ensure_ascii=False), 1, utc_now_iso(), utc_now_iso()),
            )

    def scalar(self, sql: str, params: tuple[Any, ...] = ()) -> Any:
        return self.run(lambda con: con.execute(sql, params).fetchone()[0])

    def fetch_one(self, sql: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
        return self.run(lambda con: row_to_dict(con.execute(sql, params).fetchone()))

    def fetch_all(self, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        return self.run(lambda con: rows_to_dicts(con.execute(sql, params).fetchall()))
