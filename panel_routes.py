# ============================================================================
#  panel_routes.py — envoi des panneaux depuis le dashboard
#
#  Le dashboard envoie déjà tout ce qu'il faut (embed, mode d'affichage,
#  options, salon). Ce fichier ajoute les routes qui manquent au bot :
#
#      POST /api/guild/<guild_id>/panel/<clé>
#      POST /api/guild/<guild_id>/panel
#
#  BRANCHEMENT — deux lignes dans le fichier qui crée déjà ton serveur web,
#  juste après avoir créé l'application aiohttp :
#
#      from panel_routes import setup_panel_routes
#      setup_panel_routes(app, bot)
#
#  (`app` = ton aiohttp.web.Application, `bot` = ton commands.Bot)
# ============================================================================

import inspect

import discord
from aiohttp import web

# Couleurs des boutons telles que le dashboard les nomme
STYLES = {
    "bleu":  discord.ButtonStyle.primary,
    "vert":  discord.ButtonStyle.success,
    "rouge": discord.ButtonStyle.danger,
    "gris":  discord.ButtonStyle.secondary,
}

# Méthodes de cog qui savent déjà publier un panneau : si l'une existe, on
# l'utilise, comme ça les boutons restent ceux que ton bot sait traiter.
DELEGUES = ("send_panel", "envoyer_panneau", "post_panel", "publish_panel")


def _couleur(valeur):
    """'#5865F2' -> discord.Colour. Retombe sur le bleu Discord si illisible."""
    try:
        return discord.Colour(int(str(valeur).lstrip("#"), 16))
    except (TypeError, ValueError):
        return discord.Colour(0x5865F2)


def _embed(data):
    e = discord.Embed(
        title=(data.get("title") or None),
        description=(data.get("description") or None),
        colour=_couleur(data.get("color")),
    )
    if data.get("image"):
        e.set_image(url=data["image"])
    if data.get("footer"):
        e.set_footer(text=data["footer"])
    return e


def _vue(payload):
    """Construit le menu ou les boutons décrits par le dashboard.

    Les custom_id suivent le format `mb:<panneau>:<index>` : c'est ce que ton
    cog doit écouter pour réagir au clic. Si ton bot utilise déjà ses propres
    identifiants, préfère la délégation à un cog (voir DELEGUES ci-dessus).
    """
    options = payload.get("options") or []
    panneau = payload.get("panel", "panel")
    if not options:
        return None

    vue = discord.ui.View(timeout=None)

    if payload.get("mode") == "select" or (payload.get("mode") is None and len(options) > 5):
        choix = [
            discord.SelectOption(
                label=(o.get("label") or "Sans nom")[:100],
                description=(o.get("description") or None),
                emoji=(o.get("emoji") or None),
                value=f"mb:{panneau}:{i}",
            )
            for i, o in enumerate(options[:25])
        ]
        vue.add_item(discord.ui.Select(
            custom_id=f"mb:{panneau}:select",
            placeholder=payload.get("placeholder") or "Fais ton choix…",
            options=choix,
        ))
    else:
        for i, o in enumerate(options[:5]):
            vue.add_item(discord.ui.Button(
                label=(o.get("label") or "Ouvrir")[:80],
                emoji=(o.get("emoji") or None),
                style=STYLES.get(o.get("style"), discord.ButtonStyle.primary),
                custom_id=f"mb:{panneau}:{i}",
            ))
    return vue


async def _deleguer(bot, salon, payload):
    """Laisse un cog publier le panneau s'il sait déjà le faire."""
    for cog in bot.cogs.values():
        for nom in DELEGUES:
            fonction = getattr(cog, nom, None)
            if not callable(fonction):
                continue
            try:
                resultat = fonction(salon, payload)
                if inspect.isawaitable(resultat):
                    await resultat
                return True
            except TypeError:
                continue        # signature différente : on essaie la suivante
    return False


def setup_panel_routes(app, bot, check_auth=None):
    """Ajoute les routes d'envoi des panneaux à l'application aiohttp.

    check_auth : fonction optionnelle (request, guild_id) -> bool, pour
    réutiliser la vérification d'accès de tes autres routes.
    """

    async def envoyer(request):
        guild_id = request.match_info.get("guild_id")

        try:
            payload = await request.json()
        except Exception:
            return web.json_response({"error": "JSON invalide"}, status=400)

        if check_auth is not None:
            autorise = check_auth(request, guild_id)
            if inspect.isawaitable(autorise):
                autorise = await autorise
            if not autorise:
                return web.json_response({"error": "Accès refusé"}, status=403)

        guild = bot.get_guild(int(guild_id)) if str(guild_id).isdigit() else None
        if guild is None:
            return web.json_response({"error": "Le bot n'est pas dans ce serveur"}, status=404)

        salon = guild.get_channel(int(payload.get("channel_id") or 0))
        if salon is None:
            return web.json_response({"error": "Salon introuvable"}, status=404)

        permissions = salon.permissions_for(guild.me)
        if not (permissions.send_messages and permissions.embed_links):
            return web.json_response(
                {"error": f"Il manque au bot la permission d'écrire dans #{salon.name}"},
                status=403,
            )

        payload.setdefault("panel", request.match_info.get("key", "panel"))

        try:
            if not await _deleguer(bot, salon, payload):
                message = await salon.send(
                    embed=_embed(payload.get("embed") or {}),
                    view=_vue(payload),
                )
                # Les boutons restent actifs après un redémarrage du bot
                vue = _vue(payload)
                if vue is not None:
                    bot.add_view(vue, message_id=message.id)
        except discord.Forbidden:
            return web.json_response({"error": "Discord a refusé l'envoi (permissions)"}, status=403)
        except discord.HTTPException as erreur:
            return web.json_response({"error": f"Discord : {erreur.text or erreur}"}, status=502)

        return web.json_response({"ok": True, "channel_id": str(salon.id)})

    app.router.add_post("/api/guild/{guild_id}/panel/{key}", envoyer)
    app.router.add_post("/api/guild/{guild_id}/panel", envoyer)
    return app
