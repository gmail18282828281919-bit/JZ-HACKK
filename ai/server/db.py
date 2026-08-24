"""Stockage des cles d'API (SQLite). Seul le hash de la cle est enregistre."""
import hashlib
import os
import secrets
import sqlite3
import time
from typing import Optional

from .config import DB_PATH

KEY_PREFIX = "jz"

SCHEMA = """
CREATE TABLE IF NOT EXISTS api_keys (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    label       TEXT    NOT NULL,
    key_hash    TEXT    NOT NULL UNIQUE,
    key_hint    TEXT    NOT NULL,
    created_at  INTEGER NOT NULL,
    last_used   INTEGER,
    calls       INTEGER NOT NULL DEFAULT 0,
    revoked     INTEGER NOT NULL DEFAULT 0
);
"""


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(SCHEMA)
    return conn


_conn = connect()


def hash_key(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def generate_key(label: str = "default") -> str:
    """Cree une nouvelle cle et renvoie sa valeur en clair (affichee une seule fois)."""
    raw = f"{KEY_PREFIX}-{secrets.token_hex(24)}"
    _conn.execute(
        "INSERT INTO api_keys (label, key_hash, key_hint, created_at) VALUES (?,?,?,?)",
        (label, hash_key(raw), raw[-6:], int(time.time())),
    )
    _conn.commit()
    return raw


def verify_key(raw: str) -> Optional[sqlite3.Row]:
    row = _conn.execute(
        "SELECT * FROM api_keys WHERE key_hash = ? AND revoked = 0", (hash_key(raw),)
    ).fetchone()
    return row


def touch_key(key_id: int) -> None:
    _conn.execute(
        "UPDATE api_keys SET last_used = ?, calls = calls + 1 WHERE id = ?",
        (int(time.time()), key_id),
    )
    _conn.commit()


def list_keys():
    return _conn.execute(
        "SELECT id, label, key_hint, created_at, last_used, calls, revoked "
        "FROM api_keys ORDER BY id"
    ).fetchall()


def revoke_key(key_id: int) -> bool:
    cur = _conn.execute("UPDATE api_keys SET revoked = 1 WHERE id = ?", (key_id,))
    _conn.commit()
    return cur.rowcount > 0


def count_active() -> int:
    return _conn.execute(
        "SELECT COUNT(*) AS n FROM api_keys WHERE revoked = 0"
    ).fetchone()["n"]


def admin_token() -> str:
    """Token d'administration (creation/revocation de cles a distance)."""
    return os.getenv("JZAI_ADMIN_TOKEN", "")
