"""
Dashboard web du bot Discord — module unique.

A placer a cote de app.py, avec le dossier web/ contenant les pages :

    /home/container/
    ├── app.py
    ├── config.json
    ├── dashboard.py      <- ce fichier
    └── web/
        ├── index.html
        ├── servers.html
        └── dash.html

Objectif : UN SEUL PORT (celui de l'allocation Pterodactyl, 30121 par defaut).
Les pages HTML et l'API sont servies par la meme origine, donc :
  - pas de CORS a configurer,
  - pas de blocage "mixed content" (page https qui appelle du http),
  - une seule regle de firewall.

Branchement dans app.py (fait automatiquement par patch_app.py) :

    from dashboard import register_dashboard
    register_dashboard(app, bot, client_id=CLIENT_ID, port=WEB_PORT)

Les routes /api/guild/... existantes du bot ne sont pas touchees : ce module
ajoute seulement ce qui manquait (pages, /api/config, /api/status, /api/me).
"""

import os
import time

import requests
from flask import jsonify, request, send_from_directory

_HERE = os.path.dirname(os.path.abspath(__file__))


def _find_static():
    """Trouve le dossier des pages, quel que soit le nom choisi a l'upload."""
    for name in ("web", "static", "dashboard/static", "public", "html"):
        path = os.path.join(_HERE, *name.split("/"))
        if os.path.isfile(os.path.join(path, "index.html")):
            return path
    return _HERE          # pages deposees a cote de ce fichier


STATIC_DIR = _find_static()

# pages servies telles quelles depuis le dossier detecte ci-dessus
PAGES = ("index.html", "servers.html", "dash.html", "dashboard.html")

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


# =====================================================================
#  Tunnel inverse (optionnel)
#
#  Quand le pare-feu de l'hebergeur du bot bloque les connexions
#  ENTRANTES, le bot ne peut pas etre joint directement. Mais rien
#  n'empeche le bot de SORTIR : c'est ainsi qu'il parle a Discord.
#
#  On inverse donc le sens : le bot ouvre une connexion SSH vers ton VPS
#  et demande un "remote port forward". Le VPS se met alors a ecouter sur
#  127.0.0.1:<remote_port>, et tout ce qui arrive la ressort chez le bot.
#  nginx n'a plus qu'a transmettre /api/ vers ce port local.
#
#  Aucun port a ouvrir chez l'hebergeur du bot, et le port distant est
#  lie a 127.0.0.1 : seul nginx, sur le VPS, peut l'atteindre. Le trafic
#  est chiffre par SSH sur tout le trajet.
# =====================================================================

TUNNEL_STATE = {"connected": False, "last_error": None, "since": None, "attempts": 0}


def _tunnel_pipe(a, b):
    """Recopie les octets de a vers b jusqu'a la fermeture."""
    try:
        while True:
            data = a.recv(32768)
            if not data:
                break
            b.sendall(data)
    except Exception:
        pass
    finally:
        for sock in (a, b):
            try:
                sock.close()
            except Exception:
                pass


def _tunnel_handler(chan, origin, server, local_port):
    """Une connexion est arrivee sur le VPS : on la relie au serveur web local."""
    import socket as _socket
    import threading

    try:
        sock = _socket.create_connection(("127.0.0.1", local_port), timeout=10)
    except Exception as err:
        print(f"[tunnel] serveur web local injoignable : {err}")
        try:
            chan.close()
        except Exception:
            pass
        return

    threading.Thread(target=_tunnel_pipe, args=(chan, sock), daemon=True).start()
    threading.Thread(target=_tunnel_pipe, args=(sock, chan), daemon=True).start()


def _tunnel_key(path):
    """Charge la cle privee, ou en cree une et affiche la cle publique."""
    import paramiko

    if os.path.exists(path):
        for cls in (paramiko.Ed25519Key, paramiko.RSAKey, paramiko.ECDSAKey):
            try:
                return cls.from_private_key_file(path)
            except Exception:
                continue
        raise RuntimeError(f"cle illisible : {path}")

    key = paramiko.Ed25519Key.generate()
    key.write_private_key_file(path)
    try:
        os.chmod(path, 0o600)
    except Exception:
        pass
    pub = f"{key.get_name()} {key.get_base64()} bot-dashboard"
    with open(path + ".pub", "w") as f:
        f.write(pub + "\n")

    print("\n" + "=" * 68)
    print("🔑 CLE DU TUNNEL CREEE — a installer sur ton VPS")
    print("=" * 68)
    print("Copie la ligne ci-dessous, puis sur ton VPS lance :")
    print("   mkdir -p ~/.ssh && nano ~/.ssh/authorized_keys")
    print("et colle-la dedans.\n")
    print(pub)
    print("=" * 68 + "\n")
    return key


def _tunnel_loop(cfg, local_port):
    """Maintient le tunnel ouvert, avec reconnexion automatique."""
    import time as _t

    try:
        import paramiko
    except ImportError:
        print("[tunnel] paramiko n'est pas installe — tunnel desactive.")
        print("[tunnel] Sur Pterodactyl : onglet Startup -> ADDITIONAL PYTHON PACKAGES -> paramiko")
        TUNNEL_STATE["last_error"] = "paramiko manquant"
        return

    host = cfg.get("host")
    port = int(cfg.get("port") or 22)
    user = cfg.get("user") or "bottunnel"
    remote_port = int(cfg.get("remote_port") or 8099)
    key_path = cfg.get("key_file") or os.path.join(_HERE, "tunnel_key")

    if not host:
        print("[tunnel] aucun 'host' dans la config du tunnel — desactive.")
        return

    delay = 5
    while True:
        client = None
        TUNNEL_STATE["attempts"] += 1
        try:
            key = _tunnel_key(key_path)
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            client.connect(hostname=host, port=port, username=user, pkey=key,
                           look_for_keys=False, allow_agent=False, timeout=20)

            transport = client.get_transport()
            transport.set_keepalive(15)
            transport.request_port_forward(
                "127.0.0.1", remote_port,
                handler=lambda c, o, s: _tunnel_handler(c, o, s, local_port))

            TUNNEL_STATE.update({"connected": True, "last_error": None, "since": _t.time()})
            print(f"🔒 Tunnel ouvert : {user}@{host}:{port} → 127.0.0.1:{remote_port} → bot:{local_port}")
            delay = 5

            # La boucle dort tant que le transport tient ; le trafic est
            # traite par les threads lances dans le handler.
            while transport.is_active():
                _t.sleep(2)
            raise ConnectionError("transport SSH ferme")

        except Exception as err:
            TUNNEL_STATE.update({"connected": False, "last_error": str(err), "since": None})
            print(f"[tunnel] deconnecte ({err}) — nouvelle tentative dans {delay} s")
        finally:
            if client is not None:
                try:
                    client.close()
                except Exception:
                    pass

        _t.sleep(delay)
        delay = min(delay * 2, 120)      # 5, 10, 20... plafonne a 2 min


def start_tunnel(cfg, local_port):
    """Demarre le tunnel dans un thread de fond. Sans effet si non configure."""
    import threading

    if not cfg or not cfg.get("enabled", True) or not cfg.get("host"):
        return False
    threading.Thread(target=_tunnel_loop, args=(cfg, local_port), daemon=True).start()
    return True


def register_dashboard(app, bot, client_id="", port=None, public_url="",
                       allowed_origins=None, invite_permissions=8, start_time=None,
                       tunnel=None):
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
    start_time         : timestamp de demarrage du bot, pour l'uptime affiche
    tunnel             : config du tunnel inverse (voir start_tunnel), ou None
    """
    started = float(start_time or time.time())
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
        name = "dash.html" if os.path.exists(os.path.join(STATIC_DIR, "dash.html")) else "dashboard.html"
        return send_from_directory(STATIC_DIR, name)

    @app.route("/servers")
    def _servers_alias():
        return send_from_directory(STATIC_DIR, "servers.html")

    @app.route("/favicon.ico")
    def _favicon():
        return ("", 204)

    def _base_url():
        """URL publique du dashboard, vue depuis le navigateur.

        Derriere un reverse proxy, request.host_url voit toujours du http :
        c'est nginx qui parle a Flask en clair. On suit donc l'en-tete
        X-Forwarded-Proto quand elle est presente, sinon le schema observe.
        Une URL explicite dans la config a toujours le dernier mot.
        """
        if public_url:
            return public_url
        proto = (request.headers.get("X-Forwarded-Proto") or "").split(",")[0].strip()
        host = request.headers.get("X-Forwarded-Host") or request.host
        if proto in ("http", "https"):
            return f"{proto}://{host}"
        return request.host_url.rstrip("/")

    @app.route("/api/config")
    def _api_config():
        """Config publique consommee par le front : aucun secret ici."""
        base = _base_url()
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

    @app.route("/api/status")
    def _api_status():
        """Etat temps reel du bot, consomme par l'indicateur du dashboard.

        Repondre a cette route prouve deja que le serveur web du bot recoit
        bien les requetes ; bot_ready dit en plus si la connexion Discord
        (gateway) est etablie, et ws_latency_ms si elle est en bonne sante.
        """
        ready = False
        try:
            ready = bool(bot.is_ready())
        except Exception:
            ready = False

        latency = None
        try:
            raw = getattr(bot, "latency", None)
            if raw is not None and raw == raw and raw != float("inf"):
                latency = round(raw * 1000)
        except Exception:
            latency = None

        guilds = list(getattr(bot, "guilds", []) or [])
        members = 0
        for g in guilds:
            try:
                members += int(getattr(g, "member_count", 0) or 0)
            except Exception:
                pass

        return jsonify({
            "ok": True,
            "api": True,
            "bot_ready": ready,
            "bot_name": str(bot.user) if getattr(bot, "user", None) else None,
            "bot_avatar": (str(bot.user.display_avatar.url)
                           if getattr(bot, "user", None) else None),
            "guild_count": len(guilds),
            "member_count": members,
            "ws_latency_ms": latency,
            "uptime_seconds": int(time.time() - started),
            "server_time": int(time.time()),
            "tunnel": (None if not TUNNEL_STATE["attempts"] else {
                "connected": TUNNEL_STATE["connected"],
                "last_error": TUNNEL_STATE["last_error"],
            }),
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

    if start_tunnel(tunnel, port or 30121):
        print("🔒 Tunnel inverse active (connexion sortante vers ton VPS)")

    shown = public_url or (f"http://<IP_PUBLIQUE_DU_PANEL>:{port}" if port else "")
    print("🖥️  Dashboard web branche sur l'API du bot")
    if shown:
        print(f"    → Page de connexion : {shown}/")
        print(f"    → Redirect URI a declarer sur le portail Discord : {shown}/servers.html")
    if origins:
        print(f"    → CORS autorise pour : {', '.join(origins)}")
    return app
