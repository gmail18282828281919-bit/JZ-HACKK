"""Configuration globale, chargee depuis l'environnement (.env)."""
from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def _load_dotenv() -> None:
    """Charge .env sans dependance externe (python-dotenv reste optionnel)."""
    path = BASE_DIR / ".env"
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip("'\""))


_load_dotenv()


def _int_set(raw: str) -> set[int]:
    return {int(x) for x in raw.replace(",", " ").split() if x.strip().isdigit()}


# ── Bot ────────────────────────────────────────────────────────────────
TOKEN: str = os.getenv("DISCORD_TOKEN", "")
OWNER_IDS: set[int] = _int_set(os.getenv("OWNER_IDS", ""))

# ── OAuth2 ─────────────────────────────────────────────────────────────
CLIENT_ID: str = os.getenv("CLIENT_ID", "")
CLIENT_SECRET: str = os.getenv("CLIENT_SECRET", "")
OAUTH_REDIRECT_URI: str = os.getenv(
    "OAUTH_REDIRECT_URI", "http://127.0.0.1:5000/servers.html"
)
OAUTH_SCOPES: str = "identify guilds"

API_BASE = "https://discord.com/api/v10"
CDN_BASE = "https://cdn.discordapp.com"

# ── Web ────────────────────────────────────────────────────────────────
FLASK_SECRET: str = os.getenv("FLASK_SECRET", "")
WEB_HOST: str = os.getenv("WEB_HOST", "127.0.0.1")
WEB_PORT: int = int(os.getenv("WEB_PORT", "5000"))
SECURE_COOKIES: bool = os.getenv("SECURE_COOKIES", "1") == "1"
SESSION_MAX_AGE = 7 * 24 * 3600

# ── Base de donnees partagee bot <-> web ───────────────────────────────
DATABASE_PATH: Path = BASE_DIR / os.getenv("DATABASE_PATH", "data/jz.db")

# Permissions Discord
PERM_ADMINISTRATOR = 0x8
PERM_MANAGE_GUILD = 0x20


def missing_config() -> list[str]:
    """Renvoie la liste des variables obligatoires non renseignees."""
    required = {
        "DISCORD_TOKEN": TOKEN,
        "CLIENT_ID": CLIENT_ID,
        "CLIENT_SECRET": CLIENT_SECRET,
        "FLASK_SECRET": FLASK_SECRET,
    }
    return [name for name, value in required.items() if not value]
