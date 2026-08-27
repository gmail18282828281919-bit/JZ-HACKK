# ============================================================================
#  dashboard.py — pages du dashboard + API servies par le serveur du bot
#
#  Branche depuis app.py :
#
#      from dashboard import register_dashboard
#      register_dashboard(app, bot, client_id=..., port=..., public_url=...,
#                         allowed_origins=..., start_time=..., tunnel=...)
#
#  Tout passe par le meme port que l'API du bot : meme origine, donc aucun
#  CORS a regler et aucun blocage "mixed content" cote navigateur.
#
#  Fichiers web attendus a cote de ce fichier (ou dans ./dashboard, ./web,
#  ./public, ./static) : index.html, servers.html, dash.html.
# ============================================================================

import os
import time

import requests
from flask import (jsonify, make_response, redirect, request,
                   send_from_directory, session)

# Extensions servies telles quelles. Tout le reste est refuse : ce dossier
# contient aussi les fichiers du bot, qui n'ont rien a faire sur le web.
EXTENSIONS = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".svg": "image/svg+xml",
    ".webp": "image/webp",
    ".ico": "image/x-icon",
    ".woff": "font/woff",
    ".woff2": "font/woff2",
    ".txt": "text/plain; charset=utf-8",
}

# Ces fichiers vivent a cote des pages mais ne doivent jamais etre servis.
INTERDITS = {
    "config.json", "prefixes.json", "premium.json", "ticket_state.json",
    "dashboard_extras.json", "app.py", "dashboard.py", "modules_extra.py",
}

DOSSIERS_WEB = ("dashboard", "web", "public", "static", "site", "www")
PAGES = ("index.html", "servers.html", "dash.html")


def _dossier_web():
    """Trouve le dossier qui contient les pages du dashboard."""
    base = os.path.dirname(os.path.abspath(__file__)) or os.getcwd()
    candidats = [os.path.join(base, d) for d in DOSSIERS_WEB] + [base]
    for dossier in candidats:
        if not os.path.isdir(dossier):
            continue
        if any(os.path.isfile(os.path.join(dossier, p)) for p in PAGES):
            return dossier
    return base


def _origines(valeur):
    if not valeur:
        return []
    if isinstance(valeur, (list, tuple, set)):
        return [str(o).strip().rstrip("/") for o in valeur if str(o).strip()]
    return [o.strip().rstrip("/") for o in str(valeur).split(",") if o.strip()]


def _secret():
    """client_secret : variable d'environnement, puis config.json."""
    valeur = os.environ.get("DISCORD_CLIENT_SECRET")
    if valeur:
        return valeur
    chemin = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
    try:
        import json
        with open(chemin, "r", encoding="utf-8") as fichier:
            return (json.load(fichier) or {}).get("client_secret", "")
    except Exception:
        return ""


def register_dashboard(app, bot, client_id="", port=None, public_url="",
                       allowed_origins="", start_time=None, tunnel=None,
                       **_ignore):
    """Ajoute au serveur Flask les pages du dashboard et l'API qu'elles utilisent."""

    dossier = _dossier_web()
    origines = _origines(allowed_origins)
    depart = start_time or time.time()

    base_url = str(public_url or "").strip().rstrip("/")
    if not base_url:
        base_url = f"http://127.0.0.1:{port}" if port else ""
    redirect_uri = f"{base_url}/servers.html" if base_url else "/servers.html"

    # ------------------------------------------------------------------ CORS
    if origines:
        @app.after_request
        def _cors(reponse):
            origine = (request.headers.get("Origin") or "").rstrip("/")
            if origine in origines:
                reponse.headers["Access-Control-Allow-Origin"] = origine
                reponse.headers["Access-Control-Allow-Credentials"] = "true"
                reponse.headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type, Accept"
                reponse.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
                reponse.headers["Vary"] = "Origin"
            return reponse

        @app.route("/api/<path:_reste>", methods=["OPTIONS"], endpoint="dash_preflight")
        def _preflight(_reste):
            return ("", 204)

    # ------------------------------------------------------------------ API
    @app.route("/api/config", endpoint="dash_config")
    def api_config():
        """Lu au demarrage par servers.html et dash.html."""
        return jsonify({
            "client_id": str(client_id or ""),
            "redirect_uri": redirect_uri,
            "public_url": base_url,
            "port": port,
            "invite_url": (
                f"https://discord.com/oauth2/authorize?client_id={client_id}"
                f"&permissions=8&scope=bot+applications.commands"
                if client_id else ""
            ),
        })

    @app.route("/api/status", endpoint="dash_status")
    def api_status():
        """Etat du bot : pied de page du dashboard et detection des serveurs."""
        pret = False
        nom = None
        guildes = 0
        membres = 0
        try:
            pret = bool(bot and bot.is_ready())
            if bot and bot.user:
                nom = str(bot.user)
            guildes = len(bot.guilds) if bot else 0
            membres = sum((g.member_count or 0) for g in bot.guilds) if bot else 0
        except Exception:
            pass

        return jsonify({
            "ok": True,
            "bot_ready": pret,
            "bot_name": nom,
            "bot_id": str(getattr(getattr(bot, "user", None), "id", "") or ""),
            "guild_count": guildes,
            "member_count": membres,
            "uptime": int(time.time() - depart),
            "latency_ms": int((getattr(bot, "latency", 0) or 0) * 1000),
        })

    # -------------------------------------------------- connexion cote serveur
    @app.route("/bot/auth/callback", endpoint="dash_auth_callback")
    def auth_callback():
        """Retour OAuth quand la connexion se fait avec un code (et non un token)."""
        code = request.args.get("code")
        if not code:
            erreur = request.args.get("error_description") or request.args.get("error")
            if erreur:
                return (f"Connexion Discord refusee : {erreur}", 400)
            return redirect("/servers.html")

        secret = _secret()
        if not secret:
            return ("client_secret introuvable : renseigne DISCORD_CLIENT_SECRET "
                    "ou client_secret dans config.json.", 500)

        try:
            reponse = requests.post(
                "https://discord.com/api/oauth2/token",
                data={
                    "client_id": str(client_id or ""),
                    "client_secret": secret,
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": f"{base_url}/bot/auth/callback" if base_url else request.base_url,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=10,
            )
            jeton = reponse.json().get("access_token")
            if not jeton:
                return ("Discord a refuse le code de connexion. Reessaie depuis la page d'accueil.", 400)

            utilisateur = requests.get(
                "https://discord.com/api/users/@me",
                headers={"Authorization": f"Bearer {jeton}"}, timeout=10,
            ).json()
        except Exception as err:
            return (f"Connexion impossible : {err}", 502)

        session.permanent = True
        session["discord_token"] = jeton
        session["discord_user"] = utilisateur
        return redirect("/servers.html")

    # ---------------------------------------------------------------- pages
    def _servir(nom_fichier):
        chemin = os.path.join(dossier, nom_fichier)
        if not os.path.isfile(chemin):
            return (f"Page introuvable : {nom_fichier}", 404)

        reponse = make_response(send_from_directory(dossier, nom_fichier))
        extension = os.path.splitext(nom_fichier)[1].lower()
        reponse.headers["Content-Type"] = EXTENSIONS.get(extension, "application/octet-stream")
        # Les pages evoluent souvent : jamais de cache sur le HTML.
        if extension == ".html":
            reponse.headers["Cache-Control"] = "no-store, must-revalidate"
        else:
            reponse.headers["Cache-Control"] = "public, max-age=3600"
        reponse.headers["X-Content-Type-Options"] = "nosniff"
        return reponse

    @app.route("/", endpoint="dash_accueil")
    def accueil():
        return _servir("index.html")

    @app.route("/<path:fichier>", endpoint="dash_fichier")
    def fichier_statique(fichier):
        """Sert les pages et leurs images. Refuse tout le reste."""
        if fichier.startswith(("api/", "bot/")):
            return jsonify({"error": "not_found"}), 404

        nom = os.path.normpath(fichier).replace("\\", "/")
        if nom.startswith("..") or nom.startswith("/"):
            return ("Chemin refuse", 403)
        if os.path.basename(nom) in INTERDITS:
            return ("Fichier non servi", 403)
        if os.path.splitext(nom)[1].lower() not in EXTENSIONS:
            return ("Type de fichier non servi", 403)

        return _servir(nom)

    # -------------------------------------------------------------- demarrage
    manquantes = [p for p in PAGES if not os.path.isfile(os.path.join(dossier, p))]
    print("🖥️  Dashboard web branche sur l'API du bot")
    print(f"    → Pages servies depuis : {dossier}")
    print(f"    → Page de connexion : {base_url or f'http://127.0.0.1:{port}'}/")
    print(f"    → Redirect URI a declarer sur le portail Discord : {redirect_uri}")
    if origines:
        print(f"    → Origines autorisees : {', '.join(origines)}")
    if tunnel:
        print(f"    → Tunnel configure : {tunnel}")
    if manquantes:
        print(f"    ⚠️  Pages absentes de ce dossier : {', '.join(manquantes)}")
    if not client_id:
        print("    ⚠️  client_id vide : la connexion Discord ne pourra pas demarrer.")

    return app
