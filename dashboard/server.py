"""
Branchement du dashboard web sur l'application Flask deja presente dans le bot.

Objectif : UN SEUL PORT (celui de l'allocation Pterodactyl, 30121 par defaut).
Les pages HTML et l'API sont servies par la meme origine, donc :
  - pas de CORS a configurer,
  - pas de blocage "mixed content" (page https qui appelle du http),
  - une seule regle de firewall.

Utilisation dans app.py, juste avant `Thread(target=run_api, ...)` :

    from dashboard import register_dashboard
    register_dashboard(app, bot, client_id=CLIENT_ID, port=WEB_PORT)

Les routes /api/guild/... existantes du bot ne sont pas touchees : ce module
ajoute seulement ce qui manquait (pages, /api/config, /api/me, CORS de secours).
"""

import os
import time

import requests
from flask import jsonify, request, send_from_directory

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")

# pages servies telles quelles depuis dashboard/static/
PAGES = ("index.html", "servers.html", "dashboard.html")

# cache des tokens Discord verifies : token -> (expiration, user, guilds)
_TOKEN_CACHE = {}
_TOKEN_TTL = 120


def _split_origins(value):
    if not value:
        return []
    if isinstance(value, (list, tuple, set)):
        items = list(value)
    else:
        items = str(value).split(",")
    return [o.strip().rstrip("/") for o in items if o and o.strip()]


def _verify_token(token):
    """Retourne (user, guilds) pour un token OAuth2 Discord, ou (None, [])."""
    now = time.time()
    if not token or not (10 <= len(token) <= 128):
        return None, []

    hit = _TOKEN_CACHE.get(token)
    if hit and hit[0] > now:
        return hit[1], hit[2]

    for key, val in list(_TOKEN_CACHE.items()):
        if val[0] <= now:
            _TOKEN_CACHE.pop(key, None)
    if len(_TOKEN_CACHE) > 500:
        _TOKEN_CACHE.clear()

    headers = {"Authorization": f"Bearer {token}"}
    try:
        ru = requests.get("https://discord.com/api/v10/users/@me", headers=headers, timeout=8)
        if ru.status_code != 200:
            _TOKEN_CACHE[token] = (now + 60, None, [])
            return None, []
        user = ru.json()
        rg = requests.get(
            "https://discord.com/api/v10/users/@me/guilds?with_counts=true",
            headers=headers, timeout=8,
        )
        guilds = rg.json() if rg.status_code == 200 else []
        if not isinstance(guilds, list):
            guilds = []
    except Exception as err:
        print(f"[dashboard] verification du token impossible : {err}")
        return None, []

    _TOKEN_CACHE[token] = (now + _TOKEN_TTL, user, guilds)
    return user, guilds


def _bearer():
    auth = request.headers.get("Authorization", "")
    return auth[7:].strip() if auth.startswith("Bearer ") else None


def _is_admin(guild):
    """Le membre a-t-il Administrateur (0x8) ou Gerer le serveur (0x20) ?"""
    if guild.get("owner") is True:
        return True
    try:
        perms = int(guild.get("permissions_new") or guild.get("permissions") or 0)
    except (TypeError, ValueError):
        return False
    return bool(perms & 0x8) or bool(perms & 0x20)


def register_dashboard(app, bot, client_id="", port=None, public_url="",
                       allowed_origins=None, invite_permissions=8):
    """Ajoute les pages du dashboard et les routes d'appoint a l'app Flask du bot.

    app                : l'instance Flask deja creee dans le bot
    bot                : l'instance commands.Bot
    client_id          : application ID Discord (pour le lien OAuth du front)
    port               : port d'ecoute, seulement pour l'affichage des URLs
    public_url         : URL publique complete si le bot est derriere un reverse proxy
                         (ex: https://dashboard.moderabot.xyz) ; sinon deduite du navigateur
    allowed_origins    : origines autorisees en CORS si le dashboard est heberge ailleurs.
                         Liste ou chaine separee par des virgules, "*" pour tout autoriser.
    invite_permissions : permissions du lien d'invitation du bot
    """
    client_id = str(client_id or os.environ.get("DISCORD_CLIENT_ID") or "")
    public_url = (public_url or os.environ.get("DASHBOARD_PUBLIC_URL") or "").rstrip("/")
    origins = _split_origins(
        allowed_origins if allowed_origins is not None
        else os.environ.get("DASHBOARD_ALLOWED_ORIGINS", "")
    )
    allow_all = "*" in origins

    # ------------------------------------------------------------------
    # CORS — inutile quand la page est servie par le bot (meme origine),
    # utile seulement si tu heberges le HTML sur un autre domaine.
    # L'auth se fait par header Bearer, jamais par cookie : pas de
    # Access-Control-Allow-Credentials, donc "*" reste sans danger ici.
    # ------------------------------------------------------------------
    @app.after_request
    def _cors(response):
        origin = (request.headers.get("Origin") or "").rstrip("/")
        if origin and (allow_all or origin in origins):
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Vary"] = "Origin"
            response.headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type, Accept"
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
            response.headers["Access-Control-Max-Age"] = "600"
        return response

    @app.route("/")
    def _dash_root():
        return send_from_directory(STATIC_DIR, "index.html")

    @app.route("/<any(" + ", ".join(f"'{p}'" for p in PAGES) + "):page>")
    def _dash_page(page):
        return send_from_directory(STATIC_DIR, page)

    # alias pratiques
    @app.route("/dashboard")
    def _dash_alias():
        return send_from_directory(STATIC_DIR, "dashboard.html")

    @app.route("/servers")
    def _servers_alias():
        return send_from_directory(STATIC_DIR, "servers.html")

    @app.route("/favicon.ico")
    def _favicon():
        return ("", 204)

    @app.route("/api/config")
    def _api_config():
        """Config publique consommee par le front : aucun secret ici."""
        base = public_url or request.host_url.rstrip("/")
        return jsonify({
            "client_id": client_id,
            "redirect_uri": f"{base}/servers.html",
            "invite_url": (
                f"https://discord.com/oauth2/authorize?client_id={client_id}"
                f"&permissions={invite_permissions}&scope=bot%20applications.commands"
            ) if client_id else "",
            "bot_name": str(bot.user) if getattr(bot, "user", None) else None,
            "bot_avatar": (str(bot.user.display_avatar.url)
                           if getattr(bot, "user", None) else None),
            "bot_ready": bool(getattr(bot, "is_ready", lambda: False)()),
            "guild_count": len(getattr(bot, "guilds", []) or []),
        })

    @app.route("/api/me")
    def _api_me():
        """Utilisateur connecte + ses serveurs administrables, bot present ou non."""
        token = _bearer()
        if not token:
            return jsonify({"error": "not_authenticated"}), 401

        user, guilds = _verify_token(token)
        if not user:
            return jsonify({"error": "not_authenticated"}), 401

        bot_ids = {str(g.id) for g in (getattr(bot, "guilds", []) or [])}
        out = []
        for g in guilds:
            if not _is_admin(g):
                continue
            gid = str(g.get("id"))
            out.append({
                "id": gid,
                "name": g.get("name"),
                "icon": g.get("icon"),
                "owner": bool(g.get("owner")),
                "members": g.get("approximate_member_count"),
                "bot_present": gid in bot_ids,
            })
        out.sort(key=lambda g: (not g["bot_present"], (g["name"] or "").lower()))

        return jsonify({
            "user": {
                "id": user.get("id"),
                "username": user.get("username"),
                "global_name": user.get("global_name"),
                "avatar": user.get("avatar"),
                "discriminator": user.get("discriminator"),
            },
            "guilds": out,
            "bot_ready": bool(getattr(bot, "is_ready", lambda: False)()),
        })

    shown = public_url or (f"http://<IP_PUBLIQUE_DU_PANEL>:{port}" if port else "")
    print("🖥️  Dashboard web branche sur l'API du bot")
    if shown:
        print(f"    → Page de connexion : {shown}/")
        print(f"    → Redirect URI a declarer sur le portail Discord : {shown}/servers.html")
    if origins:
        print(f"    → CORS autorise pour : {', '.join(origins)}")
    return app
