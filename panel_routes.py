# ============================================================================
#  panel_routes.py — envoi des panneaux depuis le dashboard
#
#  Le bouton « Envoyer le panneau » du dashboard appelle :
#      POST /api/guild/<guild_id>/panel/<cle>
#      POST /api/guild/<guild_id>/panel
#      POST /api/guild/<guild_id>/send-panel
#
#  Ces routes existent deja dans app.py. Ce fichier les fournit en module
#  separe, pour un app.py qui ne les aurait pas : il DETECTE la presence des
#  routes et ne s'enregistre que si elles manquent — jamais de doublon,
#  jamais d'erreur "overwriting an existing endpoint function".
#
#  Branchement (facultatif), apres la creation de l'app Flask :
#
#      from panel_routes import register_panel_routes
#      register_panel_routes(app, bot)
# ============================================================================

import asyncio

import discord
from flask import jsonify, request

ENDPOINT = "panel_routes_envoi"
REGLES = (
    "/api/guild/<guild_id>/panel",
    "/api/guild/<guild_id>/panel/<panel_key>",
    "/api/guild/<guild_id>/send-panel",
)

# Modules qui n'ont pas de panneau public cote bot : on renvoie la commande
# Discord a utiliser plutot qu'une erreur muette.
COMMANDES = {
    "giveaway": "+giveaway",
    "apply": "+apply",
    "suggestions": "+suggestions",
    "polls": "+pollconfig",
    "birthdays": "+birthdays",
}


class PanelError(Exception):
    """Message renvoye tel quel au dashboard."""


def _deja_enregistre(app):
    """Vrai si app.py fournit deja l'envoi des panneaux."""
    existantes = {str(r.rule) for r in app.url_map.iter_rules()}
    return any(regle in existantes for regle in REGLES)


def _globals_app(app):
    """Recupere les fonctions et vues du bot definies dans app.py."""
    for nom in ("api_guild_dashboard", "api_guild_stats", "api_health"):
        vue = app.view_functions.get(nom)
        if vue:
            return vue.__globals__
    return {}


def _couleur(valeur, defaut=0x5865F2):
    try:
        return int(str(valeur).replace("#", ""), 16)
    except (TypeError, ValueError):
        return defaut


def register_panel_routes(app, bot):
    """Ajoute l'envoi des panneaux si app.py ne le fournit pas deja."""

    if _deja_enregistre(app):
        print("[panel_routes] envoi des panneaux deja present dans app.py : rien a ajouter.")
        return app

    espace = _globals_app(app)
    dash_auth = espace.get("_dash_auth") or espace.get("require_guild_admin")
    ts_load = espace.get("ts_load")
    tk_record_panel = espace.get("tk_record_panel")
    charger_captcha = espace.get("_load_captcha")

    def _attendre(coro, timeout=25):
        """Flask tourne dans un thread : on execute la coroutine dans la boucle du bot."""
        return asyncio.run_coroutine_threadsafe(coro, bot.loop).result(timeout=timeout)

    def _embed_ticket(panel):
        e = discord.Embed(
            title=panel.get("titre") or "Support",
            description=panel.get("description") or "",
            color=_couleur(panel.get("couleur")),
        )
        if panel.get("image"):
            e.set_image(url=panel["image"])
        return e

    async def _envoyer_tickets(guild, channel, payload):
        conf = ((ts_load() if ts_load else {}) or {}).get(str(guild.id)) or {}
        choix = conf.get("choix") or []
        if not choix:
            raise PanelError("Ajoute au moins un type de ticket avant d'envoyer le panneau.")

        panel = conf.get("panel") or {}
        mode = panel.get("mode", "select")

        vue_boutons = espace.get("TicketButtonPanelView")
        vue_menu = espace.get("TicketSelectView2")
        vue_v2 = espace.get("TicketContainerV2View")

        if mode == "bouton" and vue_boutons:
            if len(choix) > 5:
                raise PanelError("Mode boutons : 5 types de tickets maximum.")
            view, embed = vue_boutons(guild, conf), _embed_ticket(panel)
        elif mode == "container_v2" and vue_v2:
            view = vue_v2(guild, conf)
            embed = discord.Embed(title=view._panel_title, description=view._panel_desc,
                                  color=view._panel_color)
        elif vue_menu:
            view, embed = vue_menu(guild, conf), _embed_ticket(panel)
        else:
            raise PanelError("Les vues des tickets sont introuvables dans app.py.")

        message = await channel.send(embed=embed, view=view)
        if tk_record_panel:
            tk_record_panel(message, guild.id, mode)
        return f"Panneau des tickets publie dans #{channel.name}"

    async def _envoyer_captcha(guild, channel, payload):
        cfg = ((charger_captcha() if charger_captcha else {}) or {}).get(str(guild.id), {})
        if not cfg.get("enabled"):
            raise PanelError("Active la verification avant d'envoyer le panneau.")
        if not cfg.get("verified_role"):
            raise PanelError("Choisis d'abord le role donne apres verification.")

        vue = espace.get("CaptchaStartView")
        if not vue:
            raise PanelError("La vue de verification est introuvable dans app.py.")

        e = discord.Embed(
            title="🔐 Vérification requise",
            description=(
                f"{cfg.get('welcome_message', 'Bienvenue ! Clique sur le bouton pour recevoir ton code de vérification.')}\n\n"
                f"🔢 Un code unique te sera envoyé en MP.\n"
                f"📝 Tu devras le taper ici pour accéder au serveur."
            ),
            color=0x5865F2,
        )
        if guild.icon:
            e.set_thumbnail(url=guild.icon.url)
        e.set_footer(text=f"{guild.name} • Système de vérification ModeraBot")

        await channel.send(embed=e, view=vue(guild.id))
        return f"Panneau de verification publie dans #{channel.name}"

    envois = {"tickets": _envoyer_tickets, "captcha": _envoyer_captcha}

    def envoyer(guild_id, panel_key=None):
        if dash_auth:
            guild, _membre = dash_auth(guild_id)
        else:
            guild = bot.get_guild(int(guild_id)) if str(guild_id).isdigit() else None
        if not guild:
            return jsonify({"error": "forbidden"}), 403

        corps = request.get_json(silent=True) or {}
        cle = str(panel_key or corps.get("panel") or "").strip().lower()

        try:
            channel = guild.get_channel(int(corps.get("channel_id") or 0))
        except (TypeError, ValueError):
            channel = None
        if not isinstance(channel, discord.TextChannel):
            return jsonify({"error": "Salon introuvable — choisis-en un autre."}), 404

        perms = channel.permissions_for(guild.me)
        if not (perms.send_messages and perms.embed_links):
            return jsonify({"error": f"Le bot ne peut pas ecrire dans #{channel.name}."}), 403

        envoi = envois.get(cle)
        if envoi is None:
            commande = COMMANDES.get(cle)
            return jsonify({"error": (f"Ce panneau se publie sur Discord avec {commande}."
                                      if commande else "Panneau inconnu.")}), 501

        try:
            detail = _attendre(envoi(guild, channel, corps))
        except PanelError as erreur:
            return jsonify({"error": str(erreur)}), 400
        except discord.Forbidden:
            return jsonify({"error": f"Discord refuse l'envoi dans #{channel.name}."}), 403
        except Exception as erreur:
            return jsonify({"error": f"Envoi impossible : {erreur}"}), 500

        return jsonify({"ok": True, "detail": detail, "channel_id": str(channel.id)})

    for index, regle in enumerate(REGLES):
        app.add_url_rule(regle, f"{ENDPOINT}_{index}", envoyer, methods=["POST"])

    print("[panel_routes] envoi des panneaux enregistre (tickets, verification).")
    return app
