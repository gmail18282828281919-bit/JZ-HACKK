#!/usr/bin/env python3
"""
Applique au fichier principal du bot (app.py / app_122.py) les corrections
necessaires pour que le dashboard fonctionne reellement.

Deux facons de s'en servir :

1. PATCH SEUL — on precise le fichier a corriger :

       python3 patch_app.py app.py

2. MODE DEMARRAGE — sans argument : corrige app.py, puis LANCE le bot.
   Concu pour Pterodactyl, ou la commande de demarrage est verrouillee mais
   ou la variable APP PY FILE est modifiable : il suffit d'y mettre
   patch_app.py au lieu de app.py. Le patch se rejoue a chaque demarrage
   (il ne refait rien s'il est deja applique) puis passe la main au bot.

       python3 patch_app.py

   Le fichier a lancer peut etre change avec la variable d'environnement
   BOT_FILE (defaut : app.py).

Ce que le script corrige :
  1. WEB_PORT       : le port alloue par Pterodactyl (SERVER_PORT) devient
                      prioritaire sur config.json, et le defaut passe a 30121.
  2. le print menteur "port 30121" en dur -> affiche le vrai port.
  3. cookie de session : SECURE=True casse la session en http:// simple,
                         il devient conditionnel a une URL publique https.
  4. require_guild_admin : accepte aussi le token Bearer envoye par le
                           dashboard, plus seulement le cookie de session.
                           (sans ca, /overview, /members, /settings,
                            /security/* repondent toujours 403)
  5. secrets           : client_id / client_secret / secret_key lus depuis
                         config.json ou les variables d'environnement,
                         avec la valeur actuelle en repli.
  6. branchement       : appel de register_dashboard(...) avant le demarrage
                         du serveur web, pour servir les pages du dashboard.
  7. /api/debug/<id>   : route publique qui divulguait le nom d'une guilde,
                         son nombre de membres et la liste des serveurs du
                         bot a n'importe quel visiteur. Reservee aux admins.
  8. init_dashboard    : ancien import mort qui affichait un avertissement
                         alarmant a chaque demarrage.

Le script est idempotent : le relancer ne casse rien.
Une sauvegarde <fichier>.bak est creee au premier passage.
"""

import os
import re
import runpy
import shutil
import sys

CHANGES = []


def _note(done, label):
    CHANGES.append(("✅" if done else "⏭️ ", label))
    return done


# ----------------------------------------------------------------- 1. port
PORT_OLD = """WEB_PORT = int(
    os.environ.get("DASHBOARD_PORT")
    or CONFIG.get("dashboard_port")
    or os.environ.get("SERVER_PORT")
    or 5001
)"""

PORT_NEW = '''# Le port doit correspondre a l'allocation du panel : SERVER_PORT est fourni
# par Pterodactyl et c'est le SEUL port joignable de l'exterieur. Il passe donc
# avant config.json, qui contient souvent une valeur oubliee.
WEB_PORT = int(
    os.environ.get("DASHBOARD_PORT")
    or os.environ.get("SERVER_PORT")
    or CONFIG.get("dashboard_port")
    or 30121
)'''

PORT_SRC_OLD = '''             else "SERVER_PORT (allocation du panel)" if os.environ.get("SERVER_PORT")

             else "valeur par defaut 5001")'''

PORT_SRC_NEW = '''             else "SERVER_PORT (allocation du panel)" if os.environ.get("SERVER_PORT")

             else "valeur par defaut 30121")'''


def patch_port(src):
    done = False
    if PORT_OLD in src:
        src = src.replace(PORT_OLD, PORT_NEW)
        done = True
    if PORT_SRC_OLD in src:
        src = src.replace(PORT_SRC_OLD, PORT_SRC_NEW)
        done = True
    # l'ordre de priorite affiche doit suivre le nouvel ordre reel
    src = src.replace(
        '_PORT_SRC = ("DASHBOARD_PORT (variable d\'env)" if os.environ.get("DASHBOARD_PORT")\n\n'
        '             else "config.json -> dashboard_port" if CONFIG.get("dashboard_port")\n\n'
        '             else "SERVER_PORT (allocation du panel)" if os.environ.get("SERVER_PORT")',
        '_PORT_SRC = ("DASHBOARD_PORT (variable d\'env)" if os.environ.get("DASHBOARD_PORT")\n\n'
        '             else "SERVER_PORT (allocation du panel)" if os.environ.get("SERVER_PORT")\n\n'
        '             else "config.json -> dashboard_port" if CONFIG.get("dashboard_port")',
    )
    _note(done, "WEB_PORT : SERVER_PORT prioritaire, defaut 30121")
    return src


# --------------------------------------------------- 2. print du vrai port
def patch_print(src):
    old = 'print(f"🌐 Serveur web (waitress) sur le port 30121")'
    new = 'print(f"🌐 Serveur web (waitress) sur 0.0.0.0:{WEB_PORT}")'
    done = old in src
    if done:
        src = src.replace(old, new)
    _note(done, "affichage du vrai port d'ecoute")
    return src


# ------------------------------------------------------ 3. cookie session
COOKIE_OLD = 'app.config["SESSION_COOKIE_SECURE"] = True'
COOKIE_NEW = '''# Un cookie "Secure" n'est jamais stocke sur une page en http:// simple :
# on ne l'active que si le dashboard est reellement servi en https.
app.config["SESSION_COOKIE_SECURE"] = str(
    os.environ.get("DASHBOARD_PUBLIC_URL") or CONFIG.get("dashboard_public_url") or ""
).startswith("https://")'''


def patch_cookie(src):
    done = COOKIE_OLD in src and COOKIE_NEW not in src
    if done:
        src = src.replace(COOKIE_OLD, COOKIE_NEW, 1)
    _note(done, "SESSION_COOKIE_SECURE conditionnel a https")
    return src


# ------------------------------------------------ 4. auth par token Bearer
ADMIN_NEW = '''def require_guild_admin(guild_id):
    """Autorise l'appelant s'il administre la guilde.

    Deux sources acceptees : le cookie de session Flask (OAuth cote serveur)
    et l'en-tete Authorization: Bearer <token> envoye par le dashboard
    (OAuth implicite cote navigateur). Sans le second, toutes les routes
    /api/guild/... repondent 403 des que la page est servie sans cookie.
    """
    user = session.get("discord_user")
    perms = {}

    if not user:
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            user, perms = _dash_user_from_token(auth[7:].strip())
    if not user:
        return None, None

    try:
        gid = int(guild_id)
        uid = int(user["id"])
    except (TypeError, ValueError, KeyError):
        return None, None

    guild = bot.get_guild(gid)
    if not guild:
        return None, None

    member = guild.get_member(uid)
    if member is not None:
        p = member.guild_permissions
        if member.id == guild.owner_id or p.administrator or p.manage_guild:
            return guild, member
        return None, None

    # membre absent du cache : on retombe sur les permissions donnees par Discord
    try:
        bits = int(perms.get(str(gid), "0"))
    except (TypeError, ValueError):
        return None, None
    if bits & 0x8 or bits & 0x20:
        return guild, None
    return None, None


'''


def patch_admin(src):
    if "Deux sources acceptees" in src:
        _note(False, "require_guild_admin (deja fait)")
        return src
    pattern = re.compile(
        r"def require_guild_admin\(guild_id\):.*?(?=@app\.route\(\"/api/debug/)",
        re.DOTALL,
    )
    src, n = pattern.subn(lambda m: ADMIN_NEW, src, count=1)
    _note(bool(n), "require_guild_admin accepte le token Bearer")
    return src


# ------------------------------------------------------------ 5. secrets
SECRET_LINES = (
    ("API_TOKEN", "api_token", "DASHBOARD_API_TOKEN"),
    ("CLIENT_ID", "client_id", "DISCORD_CLIENT_ID"),
    ("CLIENT_SECRET", "client_secret", "DISCORD_CLIENT_SECRET"),
    ("SECRET_KEY", "secret_key", "DASHBOARD_SECRET_KEY"),
)


def patch_secrets(src):
    done = False
    for name, cfg_key, env_key in SECRET_LINES:
        m = re.search(rf'^{name} = "([^"]*)"$', src, re.MULTILINE)
        if not m:
            continue
        current = m.group(1)
        repl = (f'{name} = (os.environ.get("{env_key}")\n'
                f'              or CONFIG.get("{cfg_key}")\n'
                f'              or "{current}")')
        src = src[:m.start()] + repl + src[m.end():]
        done = True
    _note(done, "secrets lus depuis config.json / variables d'env")
    return src


# --------------------------------------------------------- 6. branchement
HOOK_ANCHOR = "Thread(target=run_api, daemon=True).start()"

HOOK_NEW = '''# ---------------------------------------------------------------
# Dashboard web : pages + API servies par CE serveur, sur CE port.
# Meme origine que l'API => aucun CORS, aucun blocage "mixed content",
# un seul port a ouvrir dans le firewall / les allocations du panel.
# ---------------------------------------------------------------
try:
    from dashboard import register_dashboard

    register_dashboard(
        app, bot,
        client_id=CLIENT_ID,
        port=WEB_PORT,
        public_url=os.environ.get("DASHBOARD_PUBLIC_URL")
                   or CONFIG.get("dashboard_public_url", ""),
        allowed_origins=CONFIG.get("dashboard_allowed_origins", ""),
        start_time=globals().get("_BOT_START_TIME"),
        tunnel=CONFIG.get("tunnel"),
    )
except Exception as _web_err:
    print(f"⚠️  Dashboard web non charge : {_web_err}")


Thread(target=run_api, daemon=True).start()'''


def patch_hook(src):
    if "from dashboard import register_dashboard" in src:
        _note(False, "register_dashboard (deja branche)")
        return src
    if HOOK_ANCHOR not in src:
        _note(False, "register_dashboard (ancre 'Thread(target=run_api...)' introuvable)")
        return src
    src = src.replace(HOOK_ANCHOR, HOOK_NEW, 1)
    _note(True, "register_dashboard branche avant le demarrage du serveur")
    return src


def run_bot(path):
    """Lance le fichier du bot dans CE processus.

    On evite un sous-processus : Pterodactyl suit le PID qu'il a demarre, et
    la console du panel ecrit sur son entree standard. Rester dans le meme
    processus garde donc l'arret propre et la console fonctionnels.
    """
    print(f"\n🚀 Demarrage du bot : {path}\n", flush=True)
    sys.argv = [path]
    runpy.run_path(path, run_name="__main__")


DEBUG_ROUTE_NEW = '''@app.route("/api/debug/<guild_id>")
def api_debug_guild(guild_id):
    """Diagnostic reserve aux administrateurs de la guilde concernee.

    Cette route etait publique : elle renvoyait le nom du serveur, son nombre
    de membres et un echantillon des guildes du bot a n'importe quel visiteur.
    """
    guild, member = require_guild_admin(guild_id)
    if not guild:
        return jsonify({"error": "forbidden"}), 403

    user = session.get("discord_user")
    out = {
        "session_user": (user or {}).get("id"),
        "guild_found": True,
        "guild_name": guild.name,
        "bot_ready": bot.is_ready(),
        "member_cache_count": len(guild.members),
        "chunked": guild.chunked,
    }
    if member is not None:
        out["is_owner"] = member.id == guild.owner_id
        out["is_admin_perm"] = member.guild_permissions.administrator
        out["is_manage_guild_perm"] = member.guild_permissions.manage_guild
    return jsonify(out)


'''


def patch_debug(src):
    if "Diagnostic reserve aux administrateurs" in src:
        _note(False, "/api/debug (deja fait)")
        return src
    pat = re.compile(
        r'@app\.route\("/api/debug/<guild_id>"\).*?'
        r'(?=@app\.route\("/api/guild/<guild_id>/overview")',
        re.DOTALL)
    src, n = pat.subn(lambda m: DEBUG_ROUTE_NEW, src, count=1)
    _note(bool(n), "/api/debug reserve aux administrateurs")
    return src


def patch_legacy_import(src):
    """Retire l'ancien bloc `from dashboard import init_dashboard`.

    Ce module n'a jamais existe : le bloc echouait deja silencieusement.
    Maintenant que dashboard.py existe, il affiche a chaque demarrage un
    avertissement alarmant alors que tout fonctionne.
    """
    if "from dashboard import init_dashboard" not in src:
        _note(False, "ancien import init_dashboard (deja retire)")
        return src
    pat = re.compile(
        r"try:\s*\n+\s*from dashboard import init_dashboard.*?"
        r"(?=\n@app\.route|\ndef |\nclass |\nThread\()",
        re.DOTALL)
    m = pat.search(src)
    if not m:
        _note(False, "ancien import init_dashboard (bloc introuvable)")
        return src
    src = src[:m.start()] + src[m.end():]
    _note(True, "ancien import init_dashboard supprime")
    return src


def main():
    # Sans argument : mode demarrage (patch + lancement du bot).
    startup_mode = len(sys.argv) < 2
    path = os.environ.get("BOT_FILE", "app.py") if startup_mode else sys.argv[1]

    if not os.path.isfile(path):
        print(f"❌ Fichier introuvable : {path}")
        if startup_mode:
            print("   Precise le nom du fichier du bot dans la variable BOT_FILE.")
        return 1

    with open(path, "r", encoding="utf-8") as f:
        original = f.read()

    src = original
    for step in (patch_port, patch_print, patch_cookie,
                 patch_admin, patch_secrets, patch_debug,
                 patch_legacy_import, patch_hook):
        src = step(src)

    print(f"\n📄 {path}")
    for mark, label in CHANGES:
        print(f"  {mark} {label}")

    if src == original:
        print("\n✅ Rien a changer, le fichier est deja a jour.")
        if startup_mode:
            run_bot(path)
        return 0

    try:
        compile(src, path, "exec")
    except SyntaxError as err:
        print(f"\n❌ Le resultat ne compile pas ({err}) — aucun changement ecrit.")
        if startup_mode:
            # on ne bloque pas le bot pour autant : il demarre sans le dashboard
            run_bot(path)
        return 1

    backup = path + ".bak"
    if not os.path.exists(backup):
        shutil.copy2(path, backup)
        print(f"\n💾 Sauvegarde : {backup}")
    with open(path, "w", encoding="utf-8") as f:
        f.write(src)
    print("✅ Fichier mis a jour.")
    if startup_mode:
        run_bot(path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
