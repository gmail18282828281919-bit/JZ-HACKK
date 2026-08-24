"""Couche de donnees partagee entre le bot (async) et Flask (thread).

SQLite en mode WAL : plusieurs lecteurs + un ecrivain en parallele, ce qui
suffit largement ici. Chaque thread possede sa propre connexion (sqlite3 n'est
pas partageable entre threads). Le bot appelle les helpers via ``asyncio.to_thread``
pour ne jamais bloquer sa boucle d'evenements.
"""
from __future__ import annotations

import asyncio
import json
import sqlite3
import threading
import time
from typing import Any, Iterable

from core import config
from core.defaults import MODULES, default_config

_local = threading.local()

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS guilds (
    guild_id      INTEGER PRIMARY KEY,
    name          TEXT    NOT NULL DEFAULT '',
    icon          TEXT,
    owner_id      INTEGER NOT NULL DEFAULT 0,
    member_count  INTEGER NOT NULL DEFAULT 0,
    channel_cache TEXT    NOT NULL DEFAULT '[]',
    role_cache    TEXT    NOT NULL DEFAULT '[]',
    updated_at    REAL    NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS guild_config (
    guild_id   INTEGER NOT NULL,
    module     TEXT    NOT NULL,
    data       TEXT    NOT NULL,
    updated_at REAL    NOT NULL DEFAULT 0,
    PRIMARY KEY (guild_id, module)
);

CREATE TABLE IF NOT EXISTS tickets (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id      INTEGER NOT NULL,
    channel_id    INTEGER NOT NULL,
    user_id       INTEGER NOT NULL,
    subject       TEXT    NOT NULL DEFAULT '',
    status        TEXT    NOT NULL DEFAULT 'open',
    claimed_by    INTEGER NOT NULL DEFAULT 0,
    opened_at     REAL    NOT NULL,
    last_activity REAL    NOT NULL,
    closed_at     REAL,
    closed_by     INTEGER,
    transcript    TEXT
);
CREATE INDEX IF NOT EXISTS idx_tickets_guild ON tickets(guild_id, status);

CREATE TABLE IF NOT EXISTS warnings (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id      INTEGER NOT NULL,
    user_id       INTEGER NOT NULL,
    moderator_id  INTEGER NOT NULL,
    reason        TEXT    NOT NULL DEFAULT '',
    created_at    REAL    NOT NULL,
    active        INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS idx_warn_guild ON warnings(guild_id, user_id);

CREATE TABLE IF NOT EXISTS sanctions (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id     INTEGER NOT NULL,
    user_id      INTEGER NOT NULL,
    kind         TEXT    NOT NULL,
    reason       TEXT    NOT NULL DEFAULT '',
    moderator_id INTEGER NOT NULL DEFAULT 0,
    created_at   REAL    NOT NULL,
    expires_at   REAL,
    active       INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS idx_sanctions_exp ON sanctions(active, expires_at);

CREATE TABLE IF NOT EXISTS levels (
    guild_id INTEGER NOT NULL,
    user_id  INTEGER NOT NULL,
    xp       INTEGER NOT NULL DEFAULT 0,
    level    INTEGER NOT NULL DEFAULT 0,
    last_xp  REAL    NOT NULL DEFAULT 0,
    PRIMARY KEY (guild_id, user_id)
);

CREATE TABLE IF NOT EXISTS join_log (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id   INTEGER NOT NULL,
    user_id    INTEGER NOT NULL,
    created_at REAL    NOT NULL,
    joined_at  REAL    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_join_guild ON join_log(guild_id, joined_at);

CREATE TABLE IF NOT EXISTS stats (
    guild_id INTEGER NOT NULL,
    day      TEXT    NOT NULL,
    messages INTEGER NOT NULL DEFAULT 0,
    joins    INTEGER NOT NULL DEFAULT 0,
    leaves   INTEGER NOT NULL DEFAULT 0,
    commands INTEGER NOT NULL DEFAULT 0,
    sanctions INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (guild_id, day)
);

-- File d'actions : le dashboard ecrit ici, le bot consomme (cog bridge).
CREATE TABLE IF NOT EXISTS action_queue (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id     INTEGER NOT NULL,
    action       TEXT    NOT NULL,
    payload      TEXT    NOT NULL DEFAULT '{}',
    requested_by INTEGER NOT NULL,
    status       TEXT    NOT NULL DEFAULT 'pending',
    result       TEXT,
    created_at   REAL    NOT NULL,
    executed_at  REAL
);
CREATE INDEX IF NOT EXISTS idx_queue_pending ON action_queue(status, id);

CREATE TABLE IF NOT EXISTS audit_log (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id   INTEGER NOT NULL,
    user_id    INTEGER NOT NULL,
    username   TEXT    NOT NULL DEFAULT '',
    action     TEXT    NOT NULL,
    details    TEXT    NOT NULL DEFAULT '',
    created_at REAL    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_audit_guild ON audit_log(guild_id, id);

CREATE TABLE IF NOT EXISTS bot_state (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


# ── Connexion ──────────────────────────────────────────────────────────
def connect() -> sqlite3.Connection:
    """Connexion propre au thread courant."""
    conn = getattr(_local, "conn", None)
    if conn is None:
        config.DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(config.DATABASE_PATH, timeout=15, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=15000")
        conn.execute("PRAGMA foreign_keys=ON")
        _local.conn = conn
    return conn


def setup() -> None:
    """Cree le schema. A appeler une fois au demarrage."""
    connect().executescript(SCHEMA)


def query(sql: str, params: Iterable[Any] = ()) -> list[sqlite3.Row]:
    return connect().execute(sql, tuple(params)).fetchall()


def query_one(sql: str, params: Iterable[Any] = ()) -> sqlite3.Row | None:
    return connect().execute(sql, tuple(params)).fetchone()


def execute(sql: str, params: Iterable[Any] = ()) -> int:
    cur = connect().execute(sql, tuple(params))
    return cur.lastrowid or cur.rowcount


# ── Config des modules ─────────────────────────────────────────────────
def get_config(guild_id: int, module: str) -> dict[str, Any]:
    """Config d'un module, completee par les valeurs par defaut."""
    base = default_config(module)
    row = query_one(
        "SELECT data FROM guild_config WHERE guild_id = ? AND module = ?",
        (guild_id, module),
    )
    if row:
        try:
            stored = json.loads(row["data"])
            if isinstance(stored, dict):
                base.update({k: v for k, v in stored.items() if k in base})
        except json.JSONDecodeError:
            pass
    return base


def get_all_configs(guild_id: int) -> dict[str, dict[str, Any]]:
    return {module: get_config(guild_id, module) for module in MODULES}


def set_config(guild_id: int, module: str, data: dict[str, Any]) -> None:
    execute(
        """INSERT INTO guild_config (guild_id, module, data, updated_at)
           VALUES (?, ?, ?, ?)
           ON CONFLICT(guild_id, module)
           DO UPDATE SET data = excluded.data, updated_at = excluded.updated_at""",
        (guild_id, module, json.dumps(data), time.time()),
    )


# ── Cache des serveurs (ecrit par le bot, lu par le web) ───────────────
def upsert_guild(guild_id: int, name: str, icon: str | None, owner_id: int,
                 member_count: int, channels: list[dict], roles: list[dict]) -> None:
    execute(
        """INSERT INTO guilds (guild_id, name, icon, owner_id, member_count,
                               channel_cache, role_cache, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(guild_id) DO UPDATE SET
               name = excluded.name, icon = excluded.icon,
               owner_id = excluded.owner_id, member_count = excluded.member_count,
               channel_cache = excluded.channel_cache, role_cache = excluded.role_cache,
               updated_at = excluded.updated_at""",
        (guild_id, name, icon, owner_id, member_count,
         json.dumps(channels), json.dumps(roles), time.time()),
    )


def get_guild(guild_id: int) -> dict[str, Any] | None:
    row = query_one("SELECT * FROM guilds WHERE guild_id = ?", (guild_id,))
    if not row:
        return None
    data = dict(row)
    data["channels"] = json.loads(data.pop("channel_cache") or "[]")
    data["roles"] = json.loads(data.pop("role_cache") or "[]")
    return data


def bot_guild_ids() -> list[int]:
    return [row["guild_id"] for row in query("SELECT guild_id FROM guilds")]


# ── File d'actions ─────────────────────────────────────────────────────
def enqueue_action(guild_id: int, action: str, payload: dict[str, Any],
                   requested_by: int) -> int:
    return execute(
        """INSERT INTO action_queue (guild_id, action, payload, requested_by,
                                     status, created_at)
           VALUES (?, ?, ?, ?, 'pending', ?)""",
        (guild_id, action, json.dumps(payload), requested_by, time.time()),
    )


def take_pending_actions(limit: int = 10) -> list[dict[str, Any]]:
    """Reserve un lot d'actions (statut -> running) de facon atomique."""
    conn = connect()
    conn.execute("BEGIN IMMEDIATE")
    try:
        rows = conn.execute(
            "SELECT * FROM action_queue WHERE status = 'pending' ORDER BY id LIMIT ?",
            (limit,),
        ).fetchall()
        if rows:
            conn.executemany(
                "UPDATE action_queue SET status = 'running' WHERE id = ?",
                [(row["id"],) for row in rows],
            )
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise

    actions = []
    for row in rows:
        item = dict(row)
        item["status"] = "running"
        try:
            item["payload"] = json.loads(item["payload"])
        except json.JSONDecodeError:
            item["payload"] = {}
        actions.append(item)
    return actions


def finish_action(action_id: int, status: str, result: str = "") -> None:
    execute(
        "UPDATE action_queue SET status = ?, result = ?, executed_at = ? WHERE id = ?",
        (status, result[:1000], time.time(), action_id),
    )


def recent_actions(guild_id: int, limit: int = 25) -> list[dict[str, Any]]:
    return [dict(row) for row in query(
        "SELECT * FROM action_queue WHERE guild_id = ? ORDER BY id DESC LIMIT ?",
        (guild_id, limit),
    )]


# ── Audit ──────────────────────────────────────────────────────────────
def add_audit(guild_id: int, user_id: int, username: str, action: str,
              details: str = "") -> None:
    execute(
        """INSERT INTO audit_log (guild_id, user_id, username, action, details, created_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (guild_id, user_id, username, action, details[:500], time.time()),
    )


def get_audit(guild_id: int, limit: int = 50) -> list[dict[str, Any]]:
    return [dict(row) for row in query(
        "SELECT * FROM audit_log WHERE guild_id = ? ORDER BY id DESC LIMIT ?",
        (guild_id, limit),
    )]


# ── Stats ──────────────────────────────────────────────────────────────
def bump_stat(guild_id: int, field: str, amount: int = 1) -> None:
    if field not in ("messages", "joins", "leaves", "commands", "sanctions"):
        raise ValueError(f"champ de stat inconnu : {field}")
    day = time.strftime("%Y-%m-%d")
    execute(
        f"""INSERT INTO stats (guild_id, day, {field}) VALUES (?, ?, ?)
            ON CONFLICT(guild_id, day) DO UPDATE SET {field} = {field} + ?""",
        (guild_id, day, amount, amount),
    )


def get_stats(guild_id: int, days: int = 14) -> list[dict[str, Any]]:
    return [dict(row) for row in query(
        "SELECT * FROM stats WHERE guild_id = ? ORDER BY day DESC LIMIT ?",
        (guild_id, days),
    )][::-1]


# ── Etat global du bot (heartbeat, latence...) ─────────────────────────
def set_state(key: str, value: Any) -> None:
    execute(
        """INSERT INTO bot_state (key, value) VALUES (?, ?)
           ON CONFLICT(key) DO UPDATE SET value = excluded.value""",
        (key, json.dumps(value)),
    )


def get_state(key: str, fallback: Any = None) -> Any:
    row = query_one("SELECT value FROM bot_state WHERE key = ?", (key,))
    if not row:
        return fallback
    try:
        return json.loads(row["value"])
    except json.JSONDecodeError:
        return fallback


# ── Wrapper async pour le bot ──────────────────────────────────────────
async def run(func, *args, **kwargs):
    """Execute un helper synchrone dans un thread, sans bloquer la boucle du bot."""
    return await asyncio.to_thread(func, *args, **kwargs)
