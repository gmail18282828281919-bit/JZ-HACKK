"""Client OAuth2 Discord (cote serveur uniquement).

Le navigateur ne voit jamais le CLIENT_SECRET ni les tokens : l'echange du code
se fait ici, les tokens restent dans la session serveur signee.
"""
from __future__ import annotations

import time

import requests

from core import config

SESSION = requests.Session()
SESSION.headers["User-Agent"] = "ModeraBot-Dashboard/1.0"
TIMEOUT = 10


class OAuthError(Exception):
    pass


def authorize_url(state: str) -> str:
    from urllib.parse import urlencode
    params = {
        "client_id": config.CLIENT_ID,
        "redirect_uri": config.OAUTH_REDIRECT_URI,
        "response_type": "code",
        "scope": config.OAUTH_SCOPES,
        "state": state,
        "prompt": "none",
    }
    return f"https://discord.com/oauth2/authorize?{urlencode(params)}"


def exchange_code(code: str) -> dict:
    response = SESSION.post(
        f"{config.API_BASE}/oauth2/token",
        data={
            "client_id": config.CLIENT_ID,
            "client_secret": config.CLIENT_SECRET,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": config.OAUTH_REDIRECT_URI,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=TIMEOUT,
    )
    if response.status_code != 200:
        raise OAuthError(f"echange du code refuse ({response.status_code})")
    return response.json()


def refresh(refresh_token: str) -> dict:
    response = SESSION.post(
        f"{config.API_BASE}/oauth2/token",
        data={
            "client_id": config.CLIENT_ID,
            "client_secret": config.CLIENT_SECRET,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=TIMEOUT,
    )
    if response.status_code != 200:
        raise OAuthError("refresh token invalide")
    return response.json()


def revoke(token: str) -> None:
    try:
        SESSION.post(
            f"{config.API_BASE}/oauth2/token/revoke",
            data={"client_id": config.CLIENT_ID, "client_secret": config.CLIENT_SECRET,
                  "token": token},
            timeout=TIMEOUT,
        )
    except requests.RequestException:
        pass


def _get(path: str, access_token: str) -> dict | list:
    response = SESSION.get(
        f"{config.API_BASE}{path}",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=TIMEOUT,
    )
    if response.status_code == 401:
        raise OAuthError("token expire")
    if response.status_code == 429:
        raise OAuthError("rate limit Discord, reessaie dans quelques secondes")
    if response.status_code != 200:
        raise OAuthError(f"Discord a repondu {response.status_code}")
    return response.json()


def fetch_user(access_token: str) -> dict:
    data = _get("/users/@me", access_token)
    return {"id": data["id"], "username": data.get("global_name") or data["username"],
            "avatar": data.get("avatar")}


def fetch_guilds(access_token: str) -> list[dict]:
    data = _get("/users/@me/guilds", access_token)
    return [{"id": g["id"], "name": g["name"], "icon": g.get("icon"),
             "owner": g.get("owner", False), "permissions": str(g.get("permissions", "0"))}
            for g in data]


def has_manage_guild(guild: dict) -> bool:
    """Le membre peut-il configurer ce serveur ?"""
    if guild.get("owner"):
        return True
    try:
        permissions = int(guild.get("permissions", "0"))
    except (TypeError, ValueError):
        return False
    return bool(permissions & (config.PERM_ADMINISTRATOR | config.PERM_MANAGE_GUILD))


def token_expired(session_data: dict) -> bool:
    return time.time() >= session_data.get("expires_at", 0) - 60
