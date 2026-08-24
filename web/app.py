"""Serveur Flask du dashboard.

Tourne dans un thread separe du bot (Flask est synchrone, discord.py est async).
Communication avec le bot uniquement via la base SQLite partagee :
  - lecture  : cache des serveurs, stats, tickets, config
  - ecriture : config des modules + file d'actions (``action_queue``)

Flask n'ecoute QUE sur 127.0.0.1 : c'est nginx qui expose le site en HTTPS.
Le bot, lui, n'est jamais expose sur le reseau.
"""
from __future__ import annotations

import functools
import logging
import secrets
import time
from datetime import timedelta

from flask import (Flask, abort, jsonify, redirect, render_template, request,
                   session, url_for)

from core import config, database as db
from core.defaults import MODULES, sanitize
from web import oauth

log = logging.getLogger("modera.web")

GUILD_CACHE_TTL = 60          # secondes avant de redemander la liste a Discord
ACTION_RATE_LIMIT = (20, 60)  # 20 actions par 60 s et par utilisateur
_rate: dict[int, list[float]] = {}

# Actions autorisees depuis le dashboard (liste blanche stricte).
ALLOWED_ACTIONS = {
    "send_message", "announce", "kick", "ban", "unban", "timeout", "untimeout",
    "warn", "clear_warnings", "purge", "role_add", "role_remove", "lockdown",
    "refresh", "post_ticket_panel", "close_ticket", "raid_reset",
}


def create_app() -> Flask:
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.secret_key = config.FLASK_SECRET
    app.config.update(
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=config.SECURE_COOKIES,
        PERMANENT_SESSION_LIFETIME=timedelta(seconds=config.SESSION_MAX_AGE),
        MAX_CONTENT_LENGTH=256 * 1024,
        JSON_SORT_KEYS=False,
    )

    register_routes(app)
    register_api(app)

    @app.after_request
    def security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        return response

    return app


# ── Helpers de session ─────────────────────────────────────────────────
def current_user() -> dict | None:
    """Utilisateur connecte, avec rafraichissement transparent du token."""
    data = session.get("discord")
    if not data:
        return None
    if oauth.token_expired(data):
        try:
            fresh = oauth.refresh(data["refresh_token"])
        except oauth.OAuthError:
            session.clear()
            return None
        data.update({
            "access_token": fresh["access_token"],
            "refresh_token": fresh.get("refresh_token", data["refresh_token"]),
            "expires_at": time.time() + fresh.get("expires_in", 604800),
        })
        session["discord"] = data
    return data


def user_guilds(force: bool = False) -> list[dict]:
    """Liste des serveurs de l'utilisateur, mise en cache pour menager l'API."""
    data = current_user()
    if not data:
        return []
    cache = session.get("guilds_cache")
    if cache and not force and time.time() - cache["at"] < GUILD_CACHE_TTL:
        return cache["items"]
    guilds = oauth.fetch_guilds(data["access_token"])
    session["guilds_cache"] = {"at": time.time(), "items": guilds}
    return guilds


def require_login(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        if not current_user():
            return jsonify({"error": "non_authentifie"}), 401
        return func(*args, **kwargs)
    return wrapper


def require_manager(func):
    """Verifie que l'utilisateur gere ce serveur ET que le bot y est present."""
    @functools.wraps(func)
    def wrapper(guild_id: int, *args, **kwargs):
        if not current_user():
            return jsonify({"error": "non_authentifie"}), 401
        target = next((g for g in user_guilds() if str(g["id"]) == str(guild_id)), None)
        if target is None or not oauth.has_manage_guild(target):
            return jsonify({"error": "acces_refuse"}), 403
        if db.get_guild(guild_id) is None:
            return jsonify({"error": "bot_absent"}), 404
        return func(guild_id, *args, **kwargs)
    return wrapper


def check_csrf() -> None:
    """Protege les POST : le cookie seul ne suffit pas."""
    token = session.get("csrf")
    sent = request.headers.get("X-CSRF-Token")
    if not sent and request.is_json:
        sent = (request.get_json(silent=True) or {}).get("csrf")
    if not token or not sent or not secrets.compare_digest(str(token), str(sent)):
        abort(403, "csrf")


def csrf_token() -> str:
    if "csrf" not in session:
        session["csrf"] = secrets.token_urlsafe(32)
    return session["csrf"]


def rate_limited(user_id: int) -> bool:
    limit, window = ACTION_RATE_LIMIT
    now = time.time()
    hits = [t for t in _rate.get(user_id, []) if now - t < window]
    hits.append(now)
    _rate[user_id] = hits
    return len(hits) > limit


# ── Pages ──────────────────────────────────────────────────────────────
def register_routes(app: Flask) -> None:

    @app.route("/")
    @app.route("/index.html")
    def index():
        if current_user():
            return redirect("/servers.html")
        return render_template("index.html", client_id=config.CLIENT_ID,
                               login_url=url_for("login"))

    @app.route("/login")
    def login():
        state = secrets.token_urlsafe(24)
        session["oauth_state"] = state
        return redirect(oauth.authorize_url(state))

    @app.route("/servers.html")
    def servers():
        return render_template("servers.html", client_id=config.CLIENT_ID,
                               csrf=csrf_token())

    @app.route("/dash.html")
    def dash():
        guild_id = request.args.get("guild", "")
        if not guild_id.isdigit():
            return redirect("/servers.html")
        if not current_user():
            return redirect("/index.html")
        return render_template("dash.html", guild_id=guild_id, modules=MODULES,
                               csrf=csrf_token(), client_id=config.CLIENT_ID)

    @app.errorhandler(403)
    def forbidden(error):
        return jsonify({"error": "interdit", "detail": str(error)}), 403


# ── API ────────────────────────────────────────────────────────────────
def register_api(app: Flask) -> None:

    @app.post("/api/oauth-exchange")
    def oauth_exchange():
        payload = request.get_json(silent=True) or {}
        code = str(payload.get("code", ""))[:512]
        if not code:
            return jsonify({"error": "code_manquant"}), 400

        state = payload.get("state")
        expected = session.pop("oauth_state", None)
        if expected and state and not secrets.compare_digest(str(expected), str(state)):
            return jsonify({"error": "state_invalide"}), 400

        try:
            token = oauth.exchange_code(code)
            profile = oauth.fetch_user(token["access_token"])
        except oauth.OAuthError as exc:
            return jsonify({"error": str(exc)}), 400

        session.permanent = True
        session["discord"] = {
            "id": profile["id"],
            "username": profile["username"],
            "avatar": profile["avatar"],
            "access_token": token["access_token"],
            "refresh_token": token.get("refresh_token", ""),
            "expires_at": time.time() + token.get("expires_in", 604800),
        }
        session.pop("guilds_cache", None)
        csrf_token()
        return jsonify({"ok": True, "user": profile})

    @app.post("/api/logout")
    def logout():
        data = session.get("discord")
        if data and data.get("access_token"):
            oauth.revoke(data["access_token"])
        session.clear()
        return jsonify({"ok": True})

    @app.get("/api/my-guilds")
    @require_login
    def my_guilds():
        data = current_user()
        try:
            guilds = user_guilds(force=request.args.get("refresh") == "1")
        except oauth.OAuthError as exc:
            return jsonify({"error": str(exc)}), 502
        return jsonify({
            "user": {"id": data["id"], "username": data["username"],
                     "avatar": data["avatar"]},
            "guilds": guilds,
            "bot_guild_ids": [str(gid) for gid in db.bot_guild_ids()],
            "csrf": csrf_token(),
        })

    @app.get("/api/status")
    def status():
        heartbeat = db.get_state("heartbeat", {"online": False}) or {"online": False}
        # Sans battement depuis 90 s, on considere le bot hors ligne.
        if time.time() - heartbeat.get("at", 0) > 90:
            heartbeat["online"] = False
        return jsonify(heartbeat)

    @app.get("/api/guild/<int:guild_id>")
    @require_manager
    def guild_state(guild_id: int):
        guild = db.get_guild(guild_id)
        tickets = db.query(
            "SELECT * FROM tickets WHERE guild_id = ? ORDER BY id DESC LIMIT 20",
            (guild_id,))
        open_tickets = db.query_one(
            "SELECT COUNT(*) AS n FROM tickets WHERE guild_id = ? AND status = 'open'",
            (guild_id,))
        warnings = db.query_one(
            "SELECT COUNT(*) AS n FROM warnings WHERE guild_id = ? AND active = 1",
            (guild_id,))
        return jsonify({
            "guild": {
                "id": str(guild_id), "name": guild["name"], "icon": guild["icon"],
                "member_count": guild["member_count"],
                "channels": guild["channels"], "roles": guild["roles"],
                "updated_at": guild["updated_at"],
            },
            "config": db.get_all_configs(guild_id),
            "stats": db.get_stats(guild_id, 14),
            "tickets": [dict(row) | {"transcript": None} for row in tickets],
            "counters": {
                "open_tickets": open_tickets["n"],
                "warnings": warnings["n"],
                "lockdown": bool(db.get_state(f"lockdown:{guild_id}", False)),
            },
            "audit": db.get_audit(guild_id, 30),
            "actions": db.recent_actions(guild_id, 15),
            "csrf": csrf_token(),
        })

    @app.post("/api/guild/<int:guild_id>/config/<module>")
    @require_manager
    def save_config(guild_id: int, module: str):
        check_csrf()
        if module not in MODULES:
            return jsonify({"error": "module_inconnu"}), 404
        payload = request.get_json(silent=True) or {}
        clean = sanitize(module, payload.get("config", {}))
        db.set_config(guild_id, module, clean)

        user = current_user()
        db.add_audit(guild_id, int(user["id"]), user["username"],
                     "config_update", f"module {module}")
        return jsonify({"ok": True, "config": clean})

    @app.post("/api/guild/<int:guild_id>/action")
    @require_manager
    def queue_action(guild_id: int):
        check_csrf()
        user = current_user()
        if rate_limited(int(user["id"])):
            return jsonify({"error": "trop_de_requetes"}), 429

        payload = request.get_json(silent=True) or {}
        name = str(payload.get("action", ""))
        if name not in ALLOWED_ACTIONS:
            return jsonify({"error": "action_non_autorisee"}), 400

        args = payload.get("payload") or {}
        if not isinstance(args, dict) or len(args) > 20:
            return jsonify({"error": "payload_invalide"}), 400

        action_id = db.enqueue_action(guild_id, name, args, int(user["id"]))
        return jsonify({"ok": True, "id": action_id})

    @app.get("/api/guild/<int:guild_id>/action/<int:action_id>")
    @require_manager
    def action_status(guild_id: int, action_id: int):
        row = db.query_one(
            "SELECT * FROM action_queue WHERE id = ? AND guild_id = ?",
            (action_id, guild_id))
        if row is None:
            return jsonify({"error": "introuvable"}), 404
        return jsonify(dict(row))

    @app.get("/api/guild/<int:guild_id>/ticket/<int:ticket_id>")
    @require_manager
    def ticket_transcript(guild_id: int, ticket_id: int):
        row = db.query_one(
            "SELECT * FROM tickets WHERE id = ? AND guild_id = ?", (ticket_id, guild_id))
        if row is None:
            return jsonify({"error": "introuvable"}), 404
        return jsonify(dict(row))

    @app.get("/api/guild/<int:guild_id>/members/search")
    @require_manager
    def search_member(guild_id: int):
        """Recherche dans les membres connus (avertissements, niveaux, tickets)."""
        term = request.args.get("q", "").strip()
        if term.isdigit():
            return jsonify({"members": [{"id": term}]})
        return jsonify({"members": []})


app = create_app()


def run_web() -> None:
    """Point d'entree du thread Flask (serveur de dev)."""
    app.run(host=config.WEB_HOST, port=config.WEB_PORT, debug=False,
            use_reloader=False, threaded=True)
