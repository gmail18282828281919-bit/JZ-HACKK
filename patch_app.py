#!/usr/bin/env python3
# ============================================================================
#  patch_app.py — verifie et repare app.py, puis demarre le bot
#
#      python3 patch_app.py            verifie, corrige, puis lance app.py
#      python3 patch_app.py --check    verifie seulement, ne modifie rien
#      python3 patch_app.py --no-run   corrige mais ne lance pas le bot
#
#  Chaque correctif est idempotent : relancer le script ne fait rien de plus.
#  Une sauvegarde app.py.bak est ecrite avant toute modification.
# ============================================================================

import os
import re
import shutil
import subprocess
import sys

DOSSIER = os.path.dirname(os.path.abspath(__file__)) or os.getcwd()
APP = os.path.join(DOSSIER, "app.py")
SAUVEGARDE = APP + ".bak"

FICHIERS_ATTENDUS = [
    ("dashboard.py", "pages du dashboard et /api/config, /api/status"),
    ("modules_extra.py", "commandes supplementaires et /api/guild/<id>/extras"),
    ("index.html", "page de connexion"),
    ("servers.html", "choix du serveur"),
    ("dash.html", "configuration du serveur"),
    ("config.json", "token du bot, client_id, client_secret"),
]

DONNEES = ("extras_configs", "extras_bank", "extras_birthdays", "extras_infractions")


# ---------------------------------------------------------------- correctifs

def c_web_port(source):
    """WEB_PORT doit suivre l'allocation du panel (SERVER_PORT)."""
    if "SERVER_PORT" in source:
        return source, False
    motif = re.search(r"^WEB_PORT\s*=.*$", source, re.M)
    if not motif:
        return source, False
    remplacement = (
        'WEB_PORT = int(\n'
        '    os.environ.get("SERVER_PORT")\n'
        '    or os.environ.get("PORT")\n'
        '    or CONFIG.get("web_port")\n'
        '    or 30121\n'
        ')'
    )
    return source[:motif.start()] + remplacement + source[motif.end():], True


def c_cookie_https(source):
    """Un cookie Secure n'est pas stocke en http:// : on le conditionne."""
    if "SESSION_COOKIE_SECURE" not in source:
        return source, False
    if 'startswith("https://")' in source:
        return source, False
    motif = re.search(r'^app\.config\["SESSION_COOKIE_SECURE"\]\s*=.*$', source, re.M)
    if not motif:
        return source, False
    remplacement = (
        'app.config["SESSION_COOKIE_SECURE"] = str(\n'
        '    os.environ.get("DASHBOARD_PUBLIC_URL") or CONFIG.get("dashboard_public_url") or ""\n'
        ').startswith("https://")'
    )
    return source[:motif.start()] + remplacement + source[motif.end():], True


def c_debug_protege(source):
    """/api/debug ne doit jamais repondre a un visiteur anonyme."""
    motif = re.search(r'@app\.route\("/api/debug/<guild_id>"\)\s*\ndef (\w+)\(guild_id\):\n', source)
    if not motif:
        return source, False
    suite = source[motif.end():motif.end() + 400]
    if "require_guild_admin" in suite or "_dash_auth" in suite:
        return source, False
    garde = ('    guild, member = require_guild_admin(guild_id)\n'
             '    if not guild:\n'
             '        return jsonify({"error": "forbidden"}), 403\n')
    return source[:motif.end()] + garde + source[motif.end():], True


def c_import_obsolete(source):
    """L'ancien init_dashboard n'existe plus : register_dashboard le remplace."""
    if "init_dashboard" not in source:
        return source, False
    lignes = [l for l in source.splitlines(keepends=True) if "init_dashboard" not in l]
    return "".join(lignes), True


CORRECTIFS = [
    ("WEB_PORT : SERVER_PORT prioritaire, defaut 30121", c_web_port),
    ("SESSION_COOKIE_SECURE conditionnel a https", c_cookie_https),
    ("/api/debug reserve aux administrateurs", c_debug_protege),
    ("ancien import init_dashboard retire", c_import_obsolete),
]

# Presences a verifier sans rien modifier : le code est trop specifique pour
# etre genere ici, mais son absence doit etre signalee.
CONTROLES = [
    ("require_guild_admin", "def require_guild_admin", "verification des droits sur un serveur"),
    ("register_dashboard", "register_dashboard(", "pages du dashboard branchees"),
    ("modules_extra", "_charger_modules_extra", "chargement du pack de modules"),
    ("panels", "/api/guild/<guild_id>/panel", "envoi des panneaux depuis le dashboard"),
    ("secrets", "os.environ.get(\"DISCORD_CLIENT_SECRET\")", "secrets lus depuis l'environnement"),
]


def main():
    verifier_seulement = "--check" in sys.argv
    lancer = "--no-run" not in sys.argv and not verifier_seulement

    print("📄 app.py")
    if not os.path.isfile(APP):
        print(f"   ❌ introuvable dans {DOSSIER}")
        return 1

    with open(APP, "r", encoding="utf-8") as fichier:
        source = origine = fichier.read()

    modifies = []
    for libelle, correctif in CORRECTIFS:
        try:
            source, change = correctif(source)
        except Exception as erreur:
            print(f"  ⚠️  {libelle} : {erreur}")
            continue
        print(f"  {'🔧' if change else '⏭️ '} {libelle}{'' if change else ' (deja fait)'}")
        if change:
            modifies.append(libelle)

    for _cle, marqueur, libelle in CONTROLES:
        print(f"  {'⏭️ ' if marqueur in source else '❌'} {libelle}"
              f"{' (deja fait)' if marqueur in source else ' — MANQUANT'}")

    if modifies and not verifier_seulement:
        try:
            compile(source, APP, "exec")
        except SyntaxError as erreur:
            print(f"❌ Correctif abandonne : le resultat ne compile pas ({erreur}).")
            return 1
        shutil.copyfile(APP, SAUVEGARDE)
        with open(APP, "w", encoding="utf-8") as fichier:
            fichier.write(source)
        print(f"✅ {len(modifies)} correctif(s) applique(s). Sauvegarde : {os.path.basename(SAUVEGARDE)}")
    elif modifies:
        print(f"ℹ️  {len(modifies)} correctif(s) a appliquer (mode --check : rien n'a ete ecrit).")
    else:
        print("✅ Rien a changer, le fichier est deja a jour.")

    print("\n📁 Fichiers du dashboard")
    for nom, role in FICHIERS_ATTENDUS:
        present = os.path.isfile(os.path.join(DOSSIER, nom))
        print(f"  {'✅' if present else '❌'} {nom:<18} {role}")

    print("\n💾 Donnees des modules")
    for nom in DONNEES:
        chemin = os.path.join(DOSSIER, nom)
        if not os.path.isfile(chemin):
            if not verifier_seulement:
                with open(chemin, "w", encoding="utf-8") as fichier:
                    fichier.write("{}\n")
                print(f"  🔧 {nom} recree vide")
            else:
                print(f"  ❌ {nom} absent")
        else:
            print(f"  ✅ {nom}")

    if lancer:
        print("\n🚀 Demarrage du bot : app.py")
        return subprocess.call([sys.executable, APP], cwd=DOSSIER)
    return 0


if __name__ == "__main__":
    sys.exit(main())
