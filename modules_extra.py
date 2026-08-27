# ============================================================================
#  modules_extra.py — pack de modules supplementaires pour ModeraBot
#
#  Charge par app.py via _charger_modules_extra() : la fonction setup(bot, app)
#  branche les commandes sur le bot et l'API des pages "extras" du dashboard.
#
#  Donnees (fichiers JSON, recreees vides si absentes) :
#     extras_configs      reglages par serveur
#     extras_bank         economie : portefeuille et banque
#     extras_birthdays    dates d'anniversaire
#     extras_infractions  casier des membres
# ============================================================================

import json
import os
import random
import re
import time
from datetime import datetime, timedelta

import discord
from discord.ext import commands, tasks
from flask import jsonify, request

import requests

DOSSIER = os.path.dirname(os.path.abspath(__file__)) or os.getcwd()
F_CONFIGS = os.path.join(DOSSIER, "extras_configs")
F_BANK = os.path.join(DOSSIER, "extras_bank")
F_BIRTHDAYS = os.path.join(DOSSIER, "extras_birthdays")
F_INFRACTIONS = os.path.join(DOSSIER, "extras_infractions")

BLEU, VERT, ROUGE, OR = 0x5865F2, 0x3BA55D, 0xED4245, 0xFAA61A

# ---------------------------------------------------------------------------
#  Stockage
# ---------------------------------------------------------------------------

def _load(chemin):
    try:
        with open(chemin, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except FileNotFoundError:
        return {}
    except Exception as err:
        print(f"[modules_extra] lecture de {os.path.basename(chemin)} impossible : {err}")
        return {}


def _save(chemin, data):
    provisoire = chemin + ".tmp"
    try:
        with open(provisoire, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(provisoire, chemin)
    except Exception as err:
        print(f"[modules_extra] ecriture de {os.path.basename(chemin)} impossible : {err}")


# Modele exact attendu par les pages "extras" du dashboard.
DEFAUTS = {
    "economy": {"enabled": False, "symbole": "", "monnaie": "coins", "start_balance": 100,
                "daily_amount": 250, "work_min": 50, "work_max": 300, "work_cooldown": 3600,
                "rob_enabled": True, "rob_cooldown": 7200, "rob_success": 40,
                "rob_max_percent": 20, "log_channel": None, "shop": []},
    "automod": {"enabled": False, "log_channel": None, "badwords": [], "badword_action": "delete",
                "anti_invite": False, "invite_action": "delete", "anti_zalgo": False,
                "anti_spoiler": False, "max_lines": 0, "max_attachments": 0,
                "ignored_channels": [], "ignored_roles": [],
                "warn_message": "{user} ce message n'est pas autorisé ici."},
    "suggestions": {"enabled": False, "channel_id": None, "log_channel": None, "up_emoji": "",
                    "down_emoji": "", "anonymous": False, "threads": True,
                    "auto_delete_cmd": True, "min_length": 10, "counter": 0},
    "polls": {"enabled": False, "channel_id": None, "default_duration": "1h", "color": "#5865F2",
              "allow_multi": False, "show_voters": False, "ping_role": None},
    "guard": {"raidmode": False, "panic": False,
              "lock_message": "Ce salon a été verrouillé par le staff.",
              "unlock_message": "Ce salon est de nouveau ouvert.", "log_channel": None,
              "agegate": False, "agegate_days": 7, "agegate_action": "kick",
              "auto_slowmode": 0, "locked_channels": [], "immune_roles": []},
    "apply": {"enabled": False, "panel_channel": None, "review_channel": None,
              "accepted_role": None, "log_channel": None, "titre": "Candidatures",
              "description": "Choisis un poste ci-dessous pour postuler.", "couleur": "#5865F2",
              "cooldown_hours": 24, "postes": []},
    "antinuke": {"enabled": False, "log_channel": None, "punish": "strip", "window": 60,
                 "max_channel_delete": 3, "max_role_delete": 3, "max_ban": 3, "max_kick": 5,
                 "protect_channels": True, "protect_roles": True, "protect_bans": True,
                 "protect_kicks": True, "anti_bot_add": False,
                 "whitelist_roles": [], "whitelist_users": []},
    "infractions": {"enabled": False, "log_channel": None, "dm_user": True, "expire_days": 0,
                    "auto_mute_at": 3, "auto_kick_at": 0, "auto_ban_at": 5},
    "automsg": {"enabled": False, "messages": []},
    "birthdays": {"enabled": False, "channel_id": None, "role_id": None, "hour": 10,
                  "message": "Joyeux anniversaire {user} !"},
    "customcmds": {"enabled": False, "delete_trigger": False, "commands": []},
    "modo": {"roles": [], "log_channel": None},
    "jtc": {"trigger_id": None, "category_id": None, "name": "Salon de {username}"},
    "autoreact": {"salons": []},
    "piconly": {"channels": []},
    "soutien": {"role_id": None, "server_link": ""},
    "tag": {"role_id": None},
}


def _fusion(base, ajout):
    """Complete `ajout` avec les valeurs par defaut manquantes."""
    sortie = json.loads(json.dumps(base))
    for cle, valeur in (ajout or {}).items():
        if isinstance(valeur, dict) and isinstance(sortie.get(cle), dict):
            sortie[cle] = _fusion(sortie[cle], valeur)
        else:
            sortie[cle] = valeur
    return sortie


def conf(gid):
    """Configuration complete d'un serveur, valeurs par defaut comprises."""
    return _fusion(DEFAUTS, _load(F_CONFIGS).get(str(gid), {}))


def conf_save(gid, data):
    tout = _load(F_CONFIGS)
    tout[str(gid)] = data
    _save(F_CONFIGS, tout)


def mod(gid, nom):
    return conf(gid).get(nom, {})


def mod_save(gid, nom, data):
    tout = conf(gid)
    tout[nom] = data
    conf_save(gid, tout)


# ---------------------------------------------------------------------------
#  Economie
# ---------------------------------------------------------------------------

def compte(gid, uid):
    banque = _load(F_BANK).setdefault(str(gid), {})
    depart = mod(gid, "economy").get("start_balance", 100)
    c = banque.get(str(uid))
    if not isinstance(c, dict):
        return {"cash": depart, "bank": 0, "inventory": [], "cooldowns": {}}
    c.setdefault("cash", depart)
    c.setdefault("bank", 0)
    c.setdefault("inventory", [])
    c.setdefault("cooldowns", {})
    return c


def compte_save(gid, uid, data):
    banque = _load(F_BANK)
    banque.setdefault(str(gid), {})[str(uid)] = data
    _save(F_BANK, banque)


def crediter(gid, uid, montant):
    c = compte(gid, uid)
    c["cash"] = max(0, int(c["cash"]) + int(montant))
    compte_save(gid, uid, c)
    return c


def cooldown_restant(c, cle, duree):
    fin = float(c.get("cooldowns", {}).get(cle, 0)) + float(duree)
    return max(0, int(fin - time.time()))


def cooldown_pose(gid, uid, c, cle):
    c.setdefault("cooldowns", {})[cle] = time.time()
    compte_save(gid, uid, c)


def duree_lisible(secondes):
    secondes = int(secondes)
    heures, reste = divmod(secondes, 3600)
    minutes, sec = divmod(reste, 60)
    if heures:
        return f"{heures} h {minutes} min"
    if minutes:
        return f"{minutes} min {sec} s"
    return f"{sec} s"


def somme(gid, montant):
    e = mod(gid, "economy")
    symbole = e.get("symbole") or ""
    return f"{symbole}{int(montant):,}".replace(",", " ") + f" {e.get('monnaie', 'coins')}"


# ---------------------------------------------------------------------------
#  Outils communs
# ---------------------------------------------------------------------------

def ok(texte):
    return discord.Embed(description=f"✅ {texte}", color=VERT)


def err(texte):
    return discord.Embed(description=f"❌ {texte}", color=ROUGE)


def info(texte):
    return discord.Embed(description=texte, color=BLEU)


def est_staff(membre, gid):
    if membre.guild_permissions.administrator or membre.id == membre.guild.owner_id:
        return True
    roles_modo = [int(r) for r in mod(gid, "modo").get("roles", []) if str(r).isdigit()]
    return any(r.id in roles_modo for r in membre.roles)


def variables(texte, membre, guild):
    remplacements = {
        "{user}": membre.mention,
        "{username}": membre.display_name,
        "{server}": guild.name,
        "{membercount}": str(guild.member_count or 0),
        "{id}": str(membre.id),
    }
    for cle, valeur in remplacements.items():
        texte = str(texte or "").replace(cle, valeur)
    return texte


def salon(guild, valeur):
    try:
        return guild.get_channel(int(valeur)) if valeur else None
    except (TypeError, ValueError):
        return None


async def journaliser(guild, module_nom, contenu):
    ch = salon(guild, mod(guild.id, module_nom).get("log_channel"))
    if ch:
        try:
            await ch.send(embed=info(contenu))
        except discord.HTTPException:
            pass


def couleur(valeur, defaut=BLEU):
    try:
        return int(str(valeur).replace("#", ""), 16)
    except (TypeError, ValueError):
        return defaut


# ---------------------------------------------------------------------------
#  Infractions
# ---------------------------------------------------------------------------

def casier(gid, uid):
    return _load(F_INFRACTIONS).get(str(gid), {}).get(str(uid), [])


def casier_ajout(gid, uid, raison, auteur_id):
    tout = _load(F_INFRACTIONS)
    membres = tout.setdefault(str(gid), {})
    liste = membres.setdefault(str(uid), [])
    liste.append({
        "id": (max([i.get("id", 0) for i in liste]) + 1) if liste else 1,
        "raison": str(raison)[:400],
        "auteur": int(auteur_id),
        "date": int(time.time()),
    })
    _save(F_INFRACTIONS, tout)
    return liste


def casier_actives(gid, uid):
    """Infractions encore valables, selon l'expiration configuree."""
    jours = int(mod(gid, "infractions").get("expire_days", 0) or 0)
    liste = casier(gid, uid)
    if jours <= 0:
        return liste
    limite = time.time() - jours * 86400
    return [i for i in liste if i.get("date", 0) >= limite]


# ---------------------------------------------------------------------------
#  Enregistrement des commandes
# ---------------------------------------------------------------------------

_AJOUTEES = []

def _commande(bot, nom, **kwargs):
    """Decorateur qui n'ecrase jamais une commande deja definie dans app.py."""
    def enrobe(fonction):
        if bot.get_command(nom):
            print(f"[modules_extra] +{nom} existe deja dans app.py : conservee telle quelle.")
            return fonction
        bot.command(name=nom, **kwargs)(fonction)
        _AJOUTEES.append([nom] + list(kwargs.get("aliases", [])))
        return fonction
    return enrobe


def setup(bot, app):
    """Point d'entree appele par app.py."""

    # ---------------------------------------------------------------- economie
    @_commande(bot, "balance", aliases=["bal", "money", "argent"])
    async def balance_cmd(ctx, membre: discord.Member = None):
        cible = membre or ctx.author
        e = mod(ctx.guild.id, "economy")
        if not e.get("enabled"):
            return await ctx.send(embed=err("L'économie est désactivée sur ce serveur."))
        c = compte(ctx.guild.id, cible.id)
        emb = discord.Embed(title=f"💰 Portefeuille de {cible.display_name}", color=OR)
        emb.add_field(name="En poche", value=somme(ctx.guild.id, c["cash"]))
        emb.add_field(name="En banque", value=somme(ctx.guild.id, c["bank"]))
        emb.add_field(name="Total", value=somme(ctx.guild.id, c["cash"] + c["bank"]), inline=False)
        await ctx.send(embed=emb)

    @_commande(bot, "daily")
    async def daily_cmd(ctx):
        e = mod(ctx.guild.id, "economy")
        if not e.get("enabled"):
            return await ctx.send(embed=err("L'économie est désactivée sur ce serveur."))
        c = compte(ctx.guild.id, ctx.author.id)
        reste = cooldown_restant(c, "daily", 86400)
        if reste:
            return await ctx.send(embed=err(f"Reviens dans {duree_lisible(reste)}."))
        gain = int(e.get("daily_amount", 250))
        c["cash"] += gain
        cooldown_pose(ctx.guild.id, ctx.author.id, c, "daily")
        await ctx.send(embed=ok(f"Récompense quotidienne : **{somme(ctx.guild.id, gain)}**"))

    @_commande(bot, "work", aliases=["travail"])
    async def work_cmd(ctx):
        e = mod(ctx.guild.id, "economy")
        if not e.get("enabled"):
            return await ctx.send(embed=err("L'économie est désactivée sur ce serveur."))
        c = compte(ctx.guild.id, ctx.author.id)
        reste = cooldown_restant(c, "work", e.get("work_cooldown", 3600))
        if reste:
            return await ctx.send(embed=err(f"Tu es fatigué. Reviens dans {duree_lisible(reste)}."))
        gain = random.randint(int(e.get("work_min", 50)), max(int(e.get("work_min", 50)), int(e.get("work_max", 300))))
        c["cash"] += gain
        cooldown_pose(ctx.guild.id, ctx.author.id, c, "work")
        await ctx.send(embed=ok(f"Tu as travaillé et gagné **{somme(ctx.guild.id, gain)}**"))

    @_commande(bot, "pay", aliases=["donner"])
    async def pay_cmd(ctx, membre: discord.Member = None, montant: int = 0):
        if not membre or montant <= 0:
            return await ctx.send(embed=err(f"Usage : `{ctx.prefix}pay @membre 100`"))
        if membre.id == ctx.author.id:
            return await ctx.send(embed=err("Tu ne peux pas te payer toi-même."))
        c = compte(ctx.guild.id, ctx.author.id)
        if c["cash"] < montant:
            return await ctx.send(embed=err("Tu n'as pas assez en poche."))
        c["cash"] -= montant
        compte_save(ctx.guild.id, ctx.author.id, c)
        crediter(ctx.guild.id, membre.id, montant)
        await ctx.send(embed=ok(f"{somme(ctx.guild.id, montant)} envoyés à {membre.mention}"))

    @_commande(bot, "deposit", aliases=["dep", "deposer"])
    async def deposit_cmd(ctx, montant: str = "all"):
        c = compte(ctx.guild.id, ctx.author.id)
        valeur = c["cash"] if str(montant).lower() in ("all", "tout") else max(0, int(montant) if str(montant).isdigit() else 0)
        if valeur <= 0 or valeur > c["cash"]:
            return await ctx.send(embed=err("Montant invalide."))
        c["cash"] -= valeur
        c["bank"] += valeur
        compte_save(ctx.guild.id, ctx.author.id, c)
        await ctx.send(embed=ok(f"{somme(ctx.guild.id, valeur)} déposés en banque."))

    @_commande(bot, "withdraw", aliases=["wd", "retirer"])
    async def withdraw_cmd(ctx, montant: str = "all"):
        c = compte(ctx.guild.id, ctx.author.id)
        valeur = c["bank"] if str(montant).lower() in ("all", "tout") else max(0, int(montant) if str(montant).isdigit() else 0)
        if valeur <= 0 or valeur > c["bank"]:
            return await ctx.send(embed=err("Montant invalide."))
        c["bank"] -= valeur
        c["cash"] += valeur
        compte_save(ctx.guild.id, ctx.author.id, c)
        await ctx.send(embed=ok(f"{somme(ctx.guild.id, valeur)} retirés de la banque."))

    @_commande(bot, "rob", aliases=["braquer"])
    async def rob_cmd(ctx, membre: discord.Member = None):
        e = mod(ctx.guild.id, "economy")
        if not e.get("enabled") or not e.get("rob_enabled", True):
            return await ctx.send(embed=err("Les braquages sont désactivés."))
        if not membre or membre.id == ctx.author.id:
            return await ctx.send(embed=err(f"Usage : `{ctx.prefix}rob @membre`"))
        voleur = compte(ctx.guild.id, ctx.author.id)
        reste = cooldown_restant(voleur, "rob", e.get("rob_cooldown", 7200))
        if reste:
            return await ctx.send(embed=err(f"Trop risqué pour l'instant. Attends {duree_lisible(reste)}."))
        cible = compte(ctx.guild.id, membre.id)
        if cible["cash"] < 50:
            return await ctx.send(embed=err("Cette personne n'a rien en poche."))

        cooldown_pose(ctx.guild.id, ctx.author.id, voleur, "rob")
        if random.randint(1, 100) <= int(e.get("rob_success", 40)):
            maxi = int(cible["cash"] * int(e.get("rob_max_percent", 20)) / 100) or 1
            butin = random.randint(1, maxi)
            cible["cash"] -= butin
            voleur["cash"] += butin
            compte_save(ctx.guild.id, membre.id, cible)
            compte_save(ctx.guild.id, ctx.author.id, voleur)
            return await ctx.send(embed=ok(f"Braquage réussi : **{somme(ctx.guild.id, butin)}** volés à {membre.mention}"))

        amende = min(voleur["cash"], 100)
        voleur["cash"] -= amende
        compte_save(ctx.guild.id, ctx.author.id, voleur)
        await ctx.send(embed=err(f"Braquage raté ! Amende de {somme(ctx.guild.id, amende)}."))

    @_commande(bot, "shop", aliases=["boutique"])
    async def shop_cmd(ctx):
        articles = mod(ctx.guild.id, "economy").get("shop", [])
        if not articles:
            return await ctx.send(embed=err("La boutique est vide."))
        emb = discord.Embed(title="🛒 Boutique", color=BLEU)
        for i, a in enumerate(articles[:25], start=1):
            stock = a.get("stock", -1)
            details = [somme(ctx.guild.id, a.get("prix", 0))]
            if a.get("role"):
                details.append(f"donne <@&{a['role']}>")
            if stock is not None and int(stock) >= 0:
                details.append(f"stock : {stock}")
            emb.add_field(name=f"{i}. {a.get('nom', 'Article')}",
                          value=(a.get("description") or "") + "\n" + " · ".join(details),
                          inline=False)
        emb.set_footer(text=f"Acheter : {ctx.prefix}buy <numéro>")
        await ctx.send(embed=emb)

    @_commande(bot, "buy", aliases=["acheter"])
    async def buy_cmd(ctx, numero: int = 0):
        articles = mod(ctx.guild.id, "economy").get("shop", [])
        if numero < 1 or numero > len(articles):
            return await ctx.send(embed=err(f"Usage : `{ctx.prefix}buy 1`"))
        article = articles[numero - 1]
        prix = int(article.get("prix", 0))
        c = compte(ctx.guild.id, ctx.author.id)
        if c["cash"] < prix:
            return await ctx.send(embed=err("Tu n'as pas assez en poche."))
        stock = article.get("stock", -1)
        if stock is not None and int(stock) == 0:
            return await ctx.send(embed=err("Article en rupture de stock."))

        c["cash"] -= prix
        c.setdefault("inventory", []).append(article.get("nom", "Article"))
        compte_save(ctx.guild.id, ctx.author.id, c)

        if stock is not None and int(stock) > 0:
            e = mod(ctx.guild.id, "economy")
            e["shop"][numero - 1]["stock"] = int(stock) - 1
            mod_save(ctx.guild.id, "economy", e)

        if article.get("role"):
            role = ctx.guild.get_role(int(article["role"]))
            if role:
                try:
                    await ctx.author.add_roles(role, reason="Achat en boutique")
                except discord.Forbidden:
                    pass
        await ctx.send(embed=ok(f"Tu as acheté **{article.get('nom', 'Article')}**."))

    @_commande(bot, "inventory", aliases=["inv", "inventaire"])
    async def inventory_cmd(ctx, membre: discord.Member = None):
        cible = membre or ctx.author
        objets = compte(ctx.guild.id, cible.id).get("inventory", [])
        if not objets:
            return await ctx.send(embed=err("Inventaire vide."))
        await ctx.send(embed=discord.Embed(title=f"🎒 Inventaire de {cible.display_name}",
                                           description="\n".join(f"• {o}" for o in objets[:40]),
                                           color=BLEU))

    @_commande(bot, "ecolb", aliases=["baltop", "richest"])
    async def ecolb_cmd(ctx):
        comptes = _load(F_BANK).get(str(ctx.guild.id), {})
        if not comptes:
            return await ctx.send(embed=err("Aucun compte sur ce serveur."))
        classement = sorted(comptes.items(),
                            key=lambda kv: (kv[1].get("cash", 0) + kv[1].get("bank", 0)),
                            reverse=True)[:10]
        lignes = []
        for rang, (uid, c) in enumerate(classement, start=1):
            membre = ctx.guild.get_member(int(uid))
            nom = membre.display_name if membre else f"Membre {uid}"
            lignes.append(f"**{rang}.** {nom} — {somme(ctx.guild.id, c.get('cash', 0) + c.get('bank', 0))}")
        await ctx.send(embed=discord.Embed(title="🏆 Les plus riches",
                                           description="\n".join(lignes), color=OR))

    @_commande(bot, "addmoney")
    async def addmoney_cmd(ctx, membre: discord.Member = None, montant: int = 0):
        if not est_staff(ctx.author, ctx.guild.id):
            return await ctx.send(embed=err("Réservé au staff."))
        if not membre or montant == 0:
            return await ctx.send(embed=err(f"Usage : `{ctx.prefix}addmoney @membre 500`"))
        crediter(ctx.guild.id, membre.id, montant)
        await ctx.send(embed=ok(f"{somme(ctx.guild.id, montant)} crédités à {membre.mention}"))

    @_commande(bot, "removemoney")
    async def removemoney_cmd(ctx, membre: discord.Member = None, montant: int = 0):
        if not est_staff(ctx.author, ctx.guild.id):
            return await ctx.send(embed=err("Réservé au staff."))
        if not membre or montant <= 0:
            return await ctx.send(embed=err(f"Usage : `{ctx.prefix}removemoney @membre 500`"))
        crediter(ctx.guild.id, membre.id, -montant)
        await ctx.send(embed=ok(f"{somme(ctx.guild.id, montant)} retirés à {membre.mention}"))

    @_commande(bot, "resetmoney")
    async def resetmoney_cmd(ctx):
        if not ctx.author.guild_permissions.administrator:
            return await ctx.send(embed=err("Permission administrateur requise."))
        banque = _load(F_BANK)
        banque.pop(str(ctx.guild.id), None)
        _save(F_BANK, banque)
        await ctx.send(embed=ok("Tous les comptes de ce serveur ont été remis à zéro."))

    # ------------------------------------------------------------ anniversaires
    @_commande(bot, "birthday", aliases=["anniv", "anniversaire"])
    async def birthday_cmd(ctx, date: str = None):
        if not date:
            return await ctx.send(embed=err(f"Usage : `{ctx.prefix}birthday 24/08`"))
        correspondance = re.fullmatch(r"(\d{1,2})[/\-.](\d{1,2})", date.strip())
        if not correspondance:
            return await ctx.send(embed=err("Format attendu : `JJ/MM`."))
        jour, mois = int(correspondance.group(1)), int(correspondance.group(2))
        if not (1 <= jour <= 31 and 1 <= mois <= 12):
            return await ctx.send(embed=err("Cette date n'existe pas."))
        tout = _load(F_BIRTHDAYS)
        tout.setdefault(str(ctx.guild.id), {})[str(ctx.author.id)] = f"{jour:02d}/{mois:02d}"
        _save(F_BIRTHDAYS, tout)
        await ctx.send(embed=ok(f"Anniversaire enregistré : **{jour:02d}/{mois:02d}**"))

    @_commande(bot, "birthdayremove", aliases=["annivremove"])
    async def birthdayremove_cmd(ctx):
        tout = _load(F_BIRTHDAYS)
        if tout.get(str(ctx.guild.id), {}).pop(str(ctx.author.id), None) is None:
            return await ctx.send(embed=err("Tu n'avais pas de date enregistrée."))
        _save(F_BIRTHDAYS, tout)
        await ctx.send(embed=ok("Date supprimée."))

    @_commande(bot, "birthdaylist", aliases=["annivlist"])
    async def birthdaylist_cmd(ctx):
        dates = _load(F_BIRTHDAYS).get(str(ctx.guild.id), {})
        if not dates:
            return await ctx.send(embed=err("Aucune date enregistrée."))
        lignes = []
        for uid, date in sorted(dates.items(), key=lambda kv: (kv[1][3:], kv[1][:2])):
            membre = ctx.guild.get_member(int(uid))
            if membre:
                lignes.append(f"🎂 **{date}** — {membre.display_name}")
        await ctx.send(embed=discord.Embed(title="🎂 Anniversaires du serveur",
                                           description="\n".join(lignes[:40]) or "Aucun membre trouvé.",
                                           color=0x9B59B6))

    @_commande(bot, "nextbirthdays", aliases=["prochainsanniv"])
    async def nextbirthdays_cmd(ctx):
        dates = _load(F_BIRTHDAYS).get(str(ctx.guild.id), {})
        if not dates:
            return await ctx.send(embed=err("Aucune date enregistrée."))
        aujourdhui = datetime.now()

        def jours_restants(valeur):
            jour, mois = int(valeur[:2]), int(valeur[3:])
            annee = aujourdhui.year
            try:
                prochain = datetime(annee, mois, jour)
            except ValueError:
                return 999
            if prochain < aujourdhui:
                prochain = datetime(annee + 1, mois, jour)
            return (prochain - aujourdhui).days

        classement = sorted(dates.items(), key=lambda kv: jours_restants(kv[1]))[:10]
        lignes = []
        for uid, date in classement:
            membre = ctx.guild.get_member(int(uid))
            if membre:
                lignes.append(f"**{date}** — {membre.display_name} (dans {jours_restants(date)} j)")
        await ctx.send(embed=discord.Embed(title="🎈 Prochains anniversaires",
                                           description="\n".join(lignes) or "Aucun membre trouvé.",
                                           color=0x9B59B6))

    # --------------------------------------------------------------- infractions
    @_commande(bot, "infractions", aliases=["casier", "warns"])
    async def infractions_cmd(ctx, membre: discord.Member = None):
        cible = membre or ctx.author
        if cible.id != ctx.author.id and not est_staff(ctx.author, ctx.guild.id):
            return await ctx.send(embed=err("Réservé au staff."))
        liste = casier_actives(ctx.guild.id, cible.id)
        if not liste:
            return await ctx.send(embed=ok(f"{cible.display_name} n'a aucune infraction."))
        lignes = [f"**#{i['id']}** — {i['raison']} · <t:{i['date']}:R>" for i in liste[-15:]]
        await ctx.send(embed=discord.Embed(title=f"📁 Casier de {cible.display_name}",
                                           description="\n".join(lignes), color=ROUGE))

    @_commande(bot, "addinfraction", aliases=["addwarn"])
    async def addinfraction_cmd(ctx, membre: discord.Member = None, *, raison: str = "Aucune raison"):
        if not est_staff(ctx.author, ctx.guild.id):
            return await ctx.send(embed=err("Réservé au staff."))
        if not membre:
            return await ctx.send(embed=err(f"Usage : `{ctx.prefix}addinfraction @membre raison`"))

        liste = casier_ajout(ctx.guild.id, membre.id, raison, ctx.author.id)
        reglages = mod(ctx.guild.id, "infractions")
        total = len(casier_actives(ctx.guild.id, membre.id))
        await ctx.send(embed=ok(f"Infraction ajoutée à {membre.mention} — total : **{total}**"))

        if reglages.get("dm_user", True):
            try:
                await membre.send(embed=discord.Embed(
                    title=f"⚠️ Infraction sur {ctx.guild.name}",
                    description=f"**Raison :** {raison}\n**Total :** {total}", color=ROUGE))
            except discord.HTTPException:
                pass

        await journaliser(ctx.guild, "infractions",
                          f"⚠️ {membre.mention} — infraction n°{liste[-1]['id']} par {ctx.author.mention}\n> {raison}")

        try:
            if reglages.get("auto_ban_at") and total >= int(reglages["auto_ban_at"]):
                await membre.ban(reason=f"{total} infractions")
            elif reglages.get("auto_kick_at") and total >= int(reglages["auto_kick_at"]):
                await membre.kick(reason=f"{total} infractions")
            elif reglages.get("auto_mute_at") and total >= int(reglages["auto_mute_at"]):
                await membre.timeout(timedelta(minutes=10), reason=f"{total} infractions")
        except (discord.Forbidden, discord.HTTPException):
            await ctx.send(embed=err("Sanction automatique impossible : permissions insuffisantes."))

    @_commande(bot, "delinfraction", aliases=["delwarn"])
    async def delinfraction_cmd(ctx, membre: discord.Member = None, identifiant: int = 0):
        if not est_staff(ctx.author, ctx.guild.id):
            return await ctx.send(embed=err("Réservé au staff."))
        if not membre or not identifiant:
            return await ctx.send(embed=err(f"Usage : `{ctx.prefix}delinfraction @membre 2`"))
        tout = _load(F_INFRACTIONS)
        liste = tout.get(str(ctx.guild.id), {}).get(str(membre.id), [])
        restantes = [i for i in liste if i.get("id") != identifiant]
        if len(restantes) == len(liste):
            return await ctx.send(embed=err("Infraction introuvable."))
        tout[str(ctx.guild.id)][str(membre.id)] = restantes
        _save(F_INFRACTIONS, tout)
        await ctx.send(embed=ok(f"Infraction #{identifiant} retirée."))

    @_commande(bot, "clearinfractions", aliases=["clearwarns"])
    async def clearinfractions_cmd(ctx, membre: discord.Member = None):
        if not est_staff(ctx.author, ctx.guild.id):
            return await ctx.send(embed=err("Réservé au staff."))
        if not membre:
            return await ctx.send(embed=err(f"Usage : `{ctx.prefix}clearinfractions @membre`"))
        tout = _load(F_INFRACTIONS)
        tout.get(str(ctx.guild.id), {}).pop(str(membre.id), None)
        _save(F_INFRACTIONS, tout)
        await ctx.send(embed=ok(f"Casier de {membre.mention} vidé."))

    @_commande(bot, "topinfractions")
    async def topinfractions_cmd(ctx):
        if not est_staff(ctx.author, ctx.guild.id):
            return await ctx.send(embed=err("Réservé au staff."))
        membres = _load(F_INFRACTIONS).get(str(ctx.guild.id), {})
        classement = sorted(membres.items(), key=lambda kv: len(kv[1]), reverse=True)[:10]
        lignes = []
        for uid, liste in classement:
            membre = ctx.guild.get_member(int(uid))
            lignes.append(f"**{len(liste)}** — {membre.display_name if membre else 'Membre ' + uid}")
        await ctx.send(embed=discord.Embed(title="📊 Membres les plus sanctionnés",
                                           description="\n".join(lignes) or "Aucun casier.",
                                           color=ROUGE))

    # -------------------------------------------------------------- suggestions
    @_commande(bot, "suggest", aliases=["suggestion", "idee"])
    async def suggest_cmd(ctx, *, texte: str = None):
        s = mod(ctx.guild.id, "suggestions")
        if not s.get("enabled"):
            return await ctx.send(embed=err("Les suggestions sont désactivées."))
        if not texte or len(texte) < int(s.get("min_length", 10)):
            return await ctx.send(embed=err(f"Ta suggestion doit faire au moins {s.get('min_length', 10)} caractères."))

        ch = salon(ctx.guild, s.get("channel_id")) or ctx.channel
        numero = int(s.get("counter", 0)) + 1
        s["counter"] = numero
        mod_save(ctx.guild.id, "suggestions", s)

        emb = discord.Embed(title=f"💡 Suggestion #{numero}", description=texte, color=0x22D3EE)
        emb.add_field(name="Auteur", value="Anonyme" if s.get("anonymous") else ctx.author.mention)
        emb.add_field(name="Statut", value="En attente")
        message = await ch.send(embed=emb)

        for emoji in (s.get("up_emoji") or "👍", s.get("down_emoji") or "👎"):
            try:
                await message.add_reaction(emoji)
            except discord.HTTPException:
                pass
        if s.get("threads"):
            try:
                await message.create_thread(name=f"Suggestion #{numero}")
            except discord.HTTPException:
                pass
        if s.get("auto_delete_cmd", True) and ctx.channel.permissions_for(ctx.guild.me).manage_messages:
            try:
                await ctx.message.delete()
            except discord.HTTPException:
                pass
        if ch.id != ctx.channel.id:
            await ctx.send(embed=ok(f"Suggestion publiée dans {ch.mention}."), delete_after=8)

    async def _statuer(ctx, identifiant, raison, accepte):
        if not est_staff(ctx.author, ctx.guild.id):
            return await ctx.send(embed=err("Réservé au staff."))
        ch = salon(ctx.guild, mod(ctx.guild.id, "suggestions").get("channel_id")) or ctx.channel
        async for message in ch.history(limit=200):
            if message.embeds and message.embeds[0].title == f"💡 Suggestion #{identifiant}":
                emb = message.embeds[0]
                emb.color = VERT if accepte else ROUGE
                emb.clear_fields()
                emb.add_field(name="Statut", value=("✅ Approuvée" if accepte else "❌ Refusée"))
                emb.add_field(name="Par", value=ctx.author.mention)
                if raison:
                    emb.add_field(name="Raison", value=raison, inline=False)
                await message.edit(embed=emb)
                return await ctx.send(embed=ok("Suggestion mise à jour."))
        await ctx.send(embed=err("Suggestion introuvable."))

    @_commande(bot, "approve", aliases=["approuver"])
    async def approve_cmd(ctx, identifiant: int = 0, *, raison: str = ""):
        await _statuer(ctx, identifiant, raison, True)

    @_commande(bot, "deny", aliases=["refuser"])
    async def deny_cmd(ctx, identifiant: int = 0, *, raison: str = ""):
        await _statuer(ctx, identifiant, raison, False)

    @_commande(bot, "suggestinfo")
    async def suggestinfo_cmd(ctx):
        s = mod(ctx.guild.id, "suggestions")
        ch = salon(ctx.guild, s.get("channel_id"))
        await ctx.send(embed=discord.Embed(
            title="💡 Suggestions",
            description=(f"**Total :** {s.get('counter', 0)}\n"
                         f"**Salon :** {ch.mention if ch else 'non défini'}\n"
                         f"**Anonymes :** {'oui' if s.get('anonymous') else 'non'}"),
            color=BLEU))

    @_commande(bot, "suggestreset")
    async def suggestreset_cmd(ctx):
        if not ctx.author.guild_permissions.administrator:
            return await ctx.send(embed=err("Permission administrateur requise."))
        s = mod(ctx.guild.id, "suggestions")
        s["counter"] = 0
        mod_save(ctx.guild.id, "suggestions", s)
        await ctx.send(embed=ok("Compteur des suggestions remis à zéro."))

    # ------------------------------------------------------------------ sondages
    @_commande(bot, "quickpoll", aliases=["sondage"])
    async def quickpoll_cmd(ctx, *, question: str = None):
        if not question:
            return await ctx.send(embed=err(f"Usage : `{ctx.prefix}quickpoll ta question`"))
        p = mod(ctx.guild.id, "polls")
        emb = discord.Embed(title="📊 Sondage", description=question, color=couleur(p.get("color")))
        emb.set_footer(text=f"Proposé par {ctx.author.display_name}")
        message = await ctx.send(embed=emb)
        for emoji in ("👍", "👎"):
            await message.add_reaction(emoji)

    @_commande(bot, "pollpro")
    async def pollpro_cmd(ctx, *, contenu: str = None):
        if not contenu or "|" not in contenu:
            return await ctx.send(embed=err(f"Usage : `{ctx.prefix}pollpro Question | Choix A | Choix B`"))
        morceaux = [m.strip() for m in contenu.split("|") if m.strip()]
        question, choix = morceaux[0], morceaux[1:10]
        if len(choix) < 2:
            return await ctx.send(embed=err("Il faut au moins deux choix."))
        chiffres = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣"]
        p = mod(ctx.guild.id, "polls")
        emb = discord.Embed(title=f"📊 {question}", color=couleur(p.get("color")),
                            description="\n".join(f"{chiffres[i]} {c}" for i, c in enumerate(choix)))
        emb.set_footer(text=f"Sondage de {ctx.author.display_name}")
        message = await ctx.send(embed=emb)
        for i in range(len(choix)):
            await message.add_reaction(chiffres[i])

    # ----------------------------------------------------------------- protection
    @_commande(bot, "lock", aliases=["verrouiller"])
    async def lock_cmd(ctx):
        if not est_staff(ctx.author, ctx.guild.id):
            return await ctx.send(embed=err("Réservé au staff."))
        g = mod(ctx.guild.id, "guard")
        await ctx.channel.set_permissions(ctx.guild.default_role, send_messages=False)
        await ctx.send(embed=info(f"🔒 {g.get('lock_message')}"))
        await journaliser(ctx.guild, "guard", f"🔒 {ctx.channel.mention} verrouillé par {ctx.author.mention}")

    @_commande(bot, "unlock", aliases=["deverrouiller"])
    async def unlock_cmd(ctx):
        if not est_staff(ctx.author, ctx.guild.id):
            return await ctx.send(embed=err("Réservé au staff."))
        g = mod(ctx.guild.id, "guard")
        await ctx.channel.set_permissions(ctx.guild.default_role, send_messages=None)
        await ctx.send(embed=info(f"🔓 {g.get('unlock_message')}"))
        await journaliser(ctx.guild, "guard", f"🔓 {ctx.channel.mention} déverrouillé par {ctx.author.mention}")

    @_commande(bot, "lockall")
    async def lockall_cmd(ctx):
        if not ctx.author.guild_permissions.administrator:
            return await ctx.send(embed=err("Permission administrateur requise."))
        verrouilles = 0
        for ch in ctx.guild.text_channels:
            try:
                await ch.set_permissions(ctx.guild.default_role, send_messages=False)
                verrouilles += 1
            except discord.HTTPException:
                continue
        await ctx.send(embed=ok(f"{verrouilles} salon(s) verrouillé(s)."))

    @_commande(bot, "unlockall")
    async def unlockall_cmd(ctx):
        if not ctx.author.guild_permissions.administrator:
            return await ctx.send(embed=err("Permission administrateur requise."))
        ouverts = 0
        for ch in ctx.guild.text_channels:
            try:
                await ch.set_permissions(ctx.guild.default_role, send_messages=None)
                ouverts += 1
            except discord.HTTPException:
                continue
        await ctx.send(embed=ok(f"{ouverts} salon(s) déverrouillé(s)."))

    @_commande(bot, "slowmode", aliases=["lent"])
    async def slowmode_cmd(ctx, secondes: int = 0):
        if not est_staff(ctx.author, ctx.guild.id):
            return await ctx.send(embed=err("Réservé au staff."))
        await ctx.channel.edit(slowmode_delay=max(0, min(21600, secondes)))
        await ctx.send(embed=ok(f"Slowmode réglé sur {secondes} s." if secondes else "Slowmode désactivé."))

    @_commande(bot, "raidmode")
    async def raidmode_cmd(ctx, etat: str = None):
        if not ctx.author.guild_permissions.administrator:
            return await ctx.send(embed=err("Permission administrateur requise."))
        g = mod(ctx.guild.id, "guard")
        g["raidmode"] = (str(etat).lower() in ("on", "oui", "true")) if etat else not g.get("raidmode")
        mod_save(ctx.guild.id, "guard", g)
        await ctx.send(embed=ok(f"Mode raid **{'activé' if g['raidmode'] else 'désactivé'}**."))

    # ------------------------------------------------------------------- automod
    @_commande(bot, "badword", aliases=["motinterdit"])
    async def badword_cmd(ctx, action: str = None, *, mot: str = None):
        if not est_staff(ctx.author, ctx.guild.id):
            return await ctx.send(embed=err("Réservé au staff."))
        a = mod(ctx.guild.id, "automod")
        action = (action or "list").lower()

        if action in ("add", "ajouter") and mot:
            for m in [x.strip().lower() for x in mot.split(",") if x.strip()]:
                if m not in a["badwords"]:
                    a["badwords"].append(m)
            mod_save(ctx.guild.id, "automod", a)
            return await ctx.send(embed=ok(f"{len(a['badwords'])} mot(s) filtré(s) au total."))

        if action in ("del", "remove", "retirer") and mot:
            a["badwords"] = [m for m in a["badwords"] if m != mot.strip().lower()]
            mod_save(ctx.guild.id, "automod", a)
            return await ctx.send(embed=ok("Mot retiré de la liste."))

        if not a["badwords"]:
            return await ctx.send(embed=err("Aucun mot filtré."))
        await ctx.send(embed=discord.Embed(title="🚫 Mots filtrés",
                                           description=", ".join(f"`{m}`" for m in a["badwords"][:80]),
                                           color=ROUGE))

    @_commande(bot, "automodtest")
    async def automodtest_cmd(ctx, *, texte: str = ""):
        a = mod(ctx.guild.id, "automod")
        trouve = [m for m in a.get("badwords", []) if m in texte.lower()]
        if trouve:
            return await ctx.send(embed=err(f"Ce message serait filtré : {', '.join(trouve)}"))
        await ctx.send(embed=ok("Ce message passerait les filtres."))

    # -------------------------------------------------------- commandes perso
    @_commande(bot, "ccadd")
    async def ccadd_cmd(ctx, nom: str = None, *, reponse: str = None):
        if not est_staff(ctx.author, ctx.guild.id):
            return await ctx.send(embed=err("Réservé au staff."))
        if not nom or not reponse:
            return await ctx.send(embed=err(f"Usage : `{ctx.prefix}ccadd regles Voici les règles…`"))
        nom = re.sub(r"[^a-z0-9_-]", "", nom.lower())[:25]
        if not nom:
            return await ctx.send(embed=err("Nom invalide : lettres, chiffres, tiret et tiret bas."))
        c = mod(ctx.guild.id, "customcmds")
        c["commands"] = [x for x in c.get("commands", []) if x.get("nom") != nom]
        c["commands"].append({"nom": nom, "reponse": reponse, "titre": "", "couleur": "#5865F2", "roles": []})
        c["enabled"] = True
        mod_save(ctx.guild.id, "customcmds", c)
        await ctx.send(embed=ok(f"Commande `{ctx.prefix}{nom}` créée."))

    @_commande(bot, "ccdel")
    async def ccdel_cmd(ctx, nom: str = None):
        if not est_staff(ctx.author, ctx.guild.id):
            return await ctx.send(embed=err("Réservé au staff."))
        c = mod(ctx.guild.id, "customcmds")
        avant = len(c.get("commands", []))
        c["commands"] = [x for x in c.get("commands", []) if x.get("nom") != (nom or "").lower()]
        mod_save(ctx.guild.id, "customcmds", c)
        if len(c["commands"]) == avant:
            return await ctx.send(embed=err("Commande introuvable."))
        await ctx.send(embed=ok("Commande supprimée."))

    @_commande(bot, "cclist")
    async def cclist_cmd(ctx):
        liste = mod(ctx.guild.id, "customcmds").get("commands", [])
        if not liste:
            return await ctx.send(embed=err("Aucune commande personnalisée."))
        await ctx.send(embed=discord.Embed(
            title="⌨️ Commandes personnalisées",
            description=" ".join(f"`{ctx.prefix}{c['nom']}`" for c in liste[:50]), color=BLEU))

    # ----------------------------------------------------------- messages auto
    @_commande(bot, "automessagelist")
    async def automessagelist_cmd(ctx):
        messages = mod(ctx.guild.id, "automsg").get("messages", [])
        if not messages:
            return await ctx.send(embed=err("Aucun message automatique."))
        lignes = []
        for i, m in enumerate(messages, start=1):
            ch = salon(ctx.guild, m.get("channel"))
            lignes.append(f"**{i}.** {ch.mention if ch else 'salon inconnu'} — toutes les {m.get('interval_minutes', 60)} min")
        await ctx.send(embed=discord.Embed(title="🔁 Messages automatiques",
                                           description="\n".join(lignes), color=BLEU))

    @_commande(bot, "automessageadd")
    async def automessageadd_cmd(ctx, channel: discord.TextChannel = None, minutes: int = 60, *, texte: str = None):
        if not est_staff(ctx.author, ctx.guild.id):
            return await ctx.send(embed=err("Réservé au staff."))
        if not channel or not texte:
            return await ctx.send(embed=err(f"Usage : `{ctx.prefix}automessageadd #salon 60 ton texte`"))
        a = mod(ctx.guild.id, "automsg")
        if len(a.get("messages", [])) >= 15:
            return await ctx.send(embed=err("15 messages automatiques maximum."))
        a.setdefault("messages", []).append({
            "channel": str(channel.id), "interval_minutes": max(5, minutes),
            "content": texte, "titre": "", "couleur": "#5865F2", "enabled": True, "last": 0})
        a["enabled"] = True
        mod_save(ctx.guild.id, "automsg", a)
        await ctx.send(embed=ok(f"Message ajouté dans {channel.mention} toutes les {max(5, minutes)} min."))

    @_commande(bot, "automessagedel")
    async def automessagedel_cmd(ctx, numero: int = 0):
        if not est_staff(ctx.author, ctx.guild.id):
            return await ctx.send(embed=err("Réservé au staff."))
        a = mod(ctx.guild.id, "automsg")
        if numero < 1 or numero > len(a.get("messages", [])):
            return await ctx.send(embed=err(f"Usage : `{ctx.prefix}automessagedel 1`"))
        a["messages"].pop(numero - 1)
        mod_save(ctx.guild.id, "automsg", a)
        await ctx.send(embed=ok("Message automatique supprimé."))

    # ------------------------------------------------------------ auto-reactions
    @_commande(bot, "autoreact")
    async def autoreact_cmd(ctx, action: str = None, channel: discord.TextChannel = None, *, emojis: str = ""):
        a = mod(ctx.guild.id, "autoreact")
        action = (action or "list").lower()

        if action in ("add", "ajouter"):
            if not est_staff(ctx.author, ctx.guild.id):
                return await ctx.send(embed=err("Réservé au staff."))
            if not channel or not emojis.strip():
                return await ctx.send(embed=err(f"Usage : `{ctx.prefix}autoreact add #salon 👍 👎`"))
            a["salons"] = [s for s in a.get("salons", []) if str(s.get("channel")) != str(channel.id)]
            a["salons"].append({"channel": str(channel.id), "emojis": " ".join(emojis.split()[:5])})
            mod_save(ctx.guild.id, "autoreact", a)
            return await ctx.send(embed=ok(f"Réactions automatiques activées dans {channel.mention}."))

        if action in ("remove", "retirer") and channel:
            if not est_staff(ctx.author, ctx.guild.id):
                return await ctx.send(embed=err("Réservé au staff."))
            a["salons"] = [s for s in a.get("salons", []) if str(s.get("channel")) != str(channel.id)]
            mod_save(ctx.guild.id, "autoreact", a)
            return await ctx.send(embed=ok("Réactions automatiques retirées."))

        if action == "clear":
            if not est_staff(ctx.author, ctx.guild.id):
                return await ctx.send(embed=err("Réservé au staff."))
            mod_save(ctx.guild.id, "autoreact", {"salons": []})
            return await ctx.send(embed=ok("Toutes les auto-réactions ont été supprimées."))

        if not a.get("salons"):
            return await ctx.send(embed=err("Aucune auto-réaction configurée."))
        lignes = []
        for s in a["salons"]:
            ch = salon(ctx.guild, s.get("channel"))
            lignes.append(f"{ch.mention if ch else 'salon inconnu'} — {s.get('emojis', '')}")
        await ctx.send(embed=discord.Embed(title="⚡ Auto-réactions",
                                           description="\n".join(lignes), color=BLEU))

    # --------------------------------------------------------- photos seulement
    @_commande(bot, "piconly")
    async def piconly_cmd(ctx, action: str = None, channel: discord.TextChannel = None):
        p = mod(ctx.guild.id, "piconly")
        action = (action or "list").lower()

        if action in ("add", "remove") and channel:
            if not est_staff(ctx.author, ctx.guild.id):
                return await ctx.send(embed=err("Réservé au staff."))
            liste = [str(c) for c in p.get("channels", [])]
            if action == "add" and str(channel.id) not in liste:
                liste.append(str(channel.id))
            if action == "remove":
                liste = [c for c in liste if c != str(channel.id)]
            mod_save(ctx.guild.id, "piconly", {"channels": liste})
            return await ctx.send(embed=ok(f"{channel.mention} : mode photo seulement **{'activé' if action == 'add' else 'désactivé'}**."))

        salons = [salon(ctx.guild, c) for c in p.get("channels", [])]
        salons = [s for s in salons if s]
        if not salons:
            return await ctx.send(embed=err("Aucun salon en photos seulement."))
        await ctx.send(embed=discord.Embed(title="🖼️ Photos seulement",
                                           description=" ".join(s.mention for s in salons), color=BLEU))

    # ------------------------------------------------------------- soutien / tag
    @_commande(bot, "soutien")
    async def soutien_cmd(ctx):
        s = mod(ctx.guild.id, "soutien")
        role = ctx.guild.get_role(int(s["role_id"])) if s.get("role_id") else None
        await ctx.send(embed=discord.Embed(
            title="💙 Soutenir le serveur",
            description=(f"Mets **{s.get('server_link') or 'le lien du serveur'}** dans ton statut "
                         f"pour recevoir {role.mention if role else 'le rôle de soutien'}."),
            color=BLEU))

    # ----------------------------------------------------------------- ecoutes
    async def _sur_message(message):
        if not message.guild or message.author.bot:
            return

        gid = message.guild.id
        contenu = message.content or ""

        # photos seulement
        salons_photo = [str(c) for c in mod(gid, "piconly").get("channels", [])]
        if str(message.channel.id) in salons_photo and not message.attachments:
            if message.channel.permissions_for(message.guild.me).manage_messages:
                try:
                    await message.delete()
                    await message.channel.send(
                        embed=err(f"{message.author.mention} ce salon n'accepte que les images."),
                        delete_after=6)
                except discord.HTTPException:
                    pass
            return

        # auto-reactions
        for s in mod(gid, "autoreact").get("salons", []):
            if str(s.get("channel")) == str(message.channel.id):
                for emoji in str(s.get("emojis", "")).split()[:5]:
                    try:
                        await message.add_reaction(emoji)
                    except discord.HTTPException:
                        pass

        # automod : mots interdits et invitations
        a = mod(gid, "automod")
        if a.get("enabled") and not message.author.guild_permissions.manage_messages:
            ignores = [str(c) for c in a.get("ignored_channels", [])]
            roles_ignores = [str(r) for r in a.get("ignored_roles", [])]
            if (str(message.channel.id) not in ignores
                    and not any(str(r.id) in roles_ignores for r in message.author.roles)):
                minuscule = contenu.lower()
                fautif = any(m in minuscule for m in a.get("badwords", []))
                invitation = a.get("anti_invite") and re.search(r"discord(?:\.gg|app\.com/invite)/", minuscule)
                lignes_max = int(a.get("max_lines", 0) or 0)
                trop_long = lignes_max and contenu.count("\n") + 1 > lignes_max
                pieces_max = int(a.get("max_attachments", 0) or 0)
                trop_fichiers = pieces_max and len(message.attachments) > pieces_max

                if fautif or invitation or trop_long or trop_fichiers:
                    try:
                        await message.delete()
                    except discord.HTTPException:
                        pass
                    avertissement = variables(a.get("warn_message", ""), message.author, message.guild)
                    if avertissement:
                        await message.channel.send(embed=err(avertissement), delete_after=6)
                    await journaliser(message.guild, "automod",
                                      f"🛡️ Message de {message.author.mention} supprimé dans {message.channel.mention}")
                    if a.get("badword_action") == "warn" and fautif:
                        casier_ajout(gid, message.author.id, "AutoMod : message filtré", bot.user.id)
                    return

        # commandes personnalisees
        c = mod(gid, "customcmds")
        if c.get("enabled") and c.get("commands"):
            prefixe = str(await bot.get_prefix(message))
            if isinstance(prefixe, list):
                prefixe = prefixe[0]
            if contenu.startswith(prefixe):
                nom = contenu[len(prefixe):].split()[0].lower() if contenu[len(prefixe):].split() else ""
                for perso in c["commands"]:
                    if perso.get("nom") != nom:
                        continue
                    roles_requis = [str(r) for r in perso.get("roles", [])]
                    if roles_requis and not any(str(r.id) in roles_requis for r in message.author.roles):
                        return
                    reponse = variables(perso.get("reponse", ""), message.author, message.guild)
                    if perso.get("titre"):
                        await message.channel.send(embed=discord.Embed(
                            title=perso["titre"], description=reponse,
                            color=couleur(perso.get("couleur"))))
                    else:
                        await message.channel.send(reponse)
                    if c.get("delete_trigger"):
                        try:
                            await message.delete()
                        except discord.HTTPException:
                            pass
                    return

    async def _sur_arrivee(membre):
        """Filtre des comptes trop recents (module Protection)."""
        g = mod(membre.guild.id, "guard")
        if not g.get("agegate") or membre.bot:
            return
        jours = int(g.get("agegate_days", 7) or 0)
        if jours <= 0:
            return
        age = (discord.utils.utcnow() - membre.created_at).days
        if age >= jours:
            return
        action = g.get("agegate_action", "kick")
        await journaliser(membre.guild, "guard",
                          f"🚧 {membre.mention} : compte de {age} j (minimum {jours} j) → {action}")
        try:
            if action == "kick":
                await membre.kick(reason=f"Compte trop récent ({age} j)")
            elif action == "ban":
                await membre.ban(reason=f"Compte trop récent ({age} j)")
        except (discord.Forbidden, discord.HTTPException):
            pass

    async def _sur_vocal(membre, avant, apres):
        """Salons vocaux temporaires (join to create)."""
        j = mod(membre.guild.id, "jtc")
        declencheur = j.get("trigger_id")
        if not declencheur:
            return

        if apres.channel and str(apres.channel.id) == str(declencheur):
            categorie = membre.guild.get_channel(int(j["category_id"])) if j.get("category_id") else apres.channel.category
            nom = str(j.get("name", "Salon de {username}")) \
                .replace("{username}", membre.display_name).replace("{userid}", str(membre.id))
            try:
                salon_cree = await membre.guild.create_voice_channel(
                    name=nom[:100], category=categorie,
                    reason="Salon vocal temporaire")
                await membre.move_to(salon_cree)
                _VOCAUX_TEMPORAIRES.add(salon_cree.id)
            except (discord.Forbidden, discord.HTTPException):
                pass

        if avant.channel and avant.channel.id in _VOCAUX_TEMPORAIRES and not avant.channel.members:
            try:
                await avant.channel.delete(reason="Salon vocal temporaire vide")
                _VOCAUX_TEMPORAIRES.discard(avant.channel.id)
            except (discord.Forbidden, discord.HTTPException):
                pass

    bot.add_listener(_sur_message, "on_message")
    bot.add_listener(_sur_arrivee, "on_member_join")
    bot.add_listener(_sur_vocal, "on_voice_state_update")

    # -------------------------------------------------------------- taches de fond
    @tasks.loop(minutes=1)
    async def boucle_messages_auto():
        maintenant = time.time()
        configs = _load(F_CONFIGS)
        for gid, donnees in list(configs.items()):
            a = _fusion(DEFAUTS, donnees).get("automsg", {})
            if not a.get("enabled"):
                continue
            guild = bot.get_guild(int(gid)) if str(gid).isdigit() else None
            if not guild:
                continue
            modifie = False
            for message in a.get("messages", []):
                if not message.get("enabled", True) or not message.get("content"):
                    continue
                intervalle = max(5, int(message.get("interval_minutes", 60))) * 60
                if maintenant - float(message.get("last", 0)) < intervalle:
                    continue
                ch = salon(guild, message.get("channel"))
                if not ch:
                    continue
                try:
                    if message.get("titre"):
                        await ch.send(embed=discord.Embed(title=message["titre"],
                                                          description=message["content"],
                                                          color=couleur(message.get("couleur"))))
                    else:
                        await ch.send(message["content"])
                    message["last"] = maintenant
                    modifie = True
                except discord.HTTPException:
                    continue
            if modifie:
                tout = conf(gid)
                tout["automsg"] = a
                conf_save(gid, tout)

    @tasks.loop(minutes=30)
    async def boucle_anniversaires():
        maintenant = datetime.now()
        aujourdhui = f"{maintenant.day:02d}/{maintenant.month:02d}"
        toutes = _load(F_BIRTHDAYS)
        for gid, dates in list(toutes.items()):
            b = mod(gid, "birthdays")
            if not b.get("enabled") or maintenant.hour != int(b.get("hour", 10)):
                continue
            guild = bot.get_guild(int(gid)) if str(gid).isdigit() else None
            ch = salon(guild, b.get("channel_id")) if guild else None
            if not guild or not ch:
                continue
            marque = _load(F_CONFIGS).get(str(gid), {}).get("_dernier_anniv")
            if marque == f"{maintenant.date()}":
                continue
            for uid, date in dates.items():
                if date != aujourdhui:
                    continue
                membre = guild.get_member(int(uid))
                if not membre:
                    continue
                try:
                    await ch.send(embed=discord.Embed(
                        title="🎂 Joyeux anniversaire !",
                        description=variables(b.get("message", ""), membre, guild),
                        color=0x9B59B6))
                    if b.get("role_id"):
                        role = guild.get_role(int(b["role_id"]))
                        if role:
                            await membre.add_roles(role, reason="Anniversaire")
                except (discord.Forbidden, discord.HTTPException):
                    continue
            tout = conf(gid)
            tout["_dernier_anniv"] = f"{maintenant.date()}"
            conf_save(gid, tout)

    async def _demarrer_boucles():
        if not boucle_messages_auto.is_running():
            boucle_messages_auto.start()
        if not boucle_anniversaires.is_running():
            boucle_anniversaires.start()

    bot.add_listener(_demarrer_boucles, "on_ready")

    # ------------------------------------------------------------------- API
    _enregistrer_api(app, bot)

    noms = sum(len(n) for n in _AJOUTEES)
    print(f"[modules_extra] {len(_AJOUTEES)} commandes ajoutees "
          f"({noms} en comptant les alias) sur 11 categories.")


_VOCAUX_TEMPORAIRES = set()


# ---------------------------------------------------------------------------
#  API du dashboard : GET/POST /api/guild/<id>/extras
# ---------------------------------------------------------------------------

def _authentifieur(app):
    """Reutilise _dash_auth d'app.py plutot que de refaire la verification."""
    vue = app.view_functions.get("api_guild_dashboard")
    if vue:
        fonction = vue.__globals__.get("_dash_auth")
        if callable(fonction):
            return fonction
    return None


def _auth_secours(bot, guild_id):
    """Verification directe du token Discord si app.py n'expose pas la sienne."""
    entete = request.headers.get("Authorization", "")
    if not entete.startswith("Bearer "):
        return None, None
    try:
        reponse = requests.get(
            "https://discord.com/api/v10/users/@me/guilds",
            headers={"Authorization": entete}, timeout=8)
        if reponse.status_code != 200:
            return None, None
        for g in reponse.json():
            if str(g.get("id")) != str(guild_id):
                continue
            bits = 8 if g.get("owner") else int(g.get("permissions", 0))
            if bits & 0x8 or bits & 0x20:
                return bot.get_guild(int(guild_id)), None
    except Exception:
        return None, None
    return None, None


def _enregistrer_api(app, bot):
    auth = _authentifieur(app)

    def _verifier(guild_id):
        if auth:
            return auth(guild_id)
        return _auth_secours(bot, guild_id)

    def extras(guild_id):
        guild, _membre = _verifier(guild_id)
        if not guild:
            return jsonify({"error": "forbidden"}), 403

        gid = str(guild.id)

        if request.method == "POST":
            corps = request.get_json(silent=True)
            if not isinstance(corps, dict):
                return jsonify({"error": "JSON invalide"}), 400
            corps.pop("_stats", None)
            corps.pop("_meta", None)
            conf_save(gid, _fusion(DEFAUTS, corps))
            return jsonify({"ok": True})

        donnees = conf(gid)
        comptes = _load(F_BANK).get(gid, {})
        donnees["_stats"] = {
            "comptes": len(comptes),
            "argent_total": sum(int(c.get("cash", 0)) + int(c.get("bank", 0)) for c in comptes.values()),
            "bd": len(_load(F_BIRTHDAYS).get(gid, {})),
            "inf": sum(len(v) for v in _load(F_INFRACTIONS).get(gid, {}).values()),
            "infm": len(_load(F_INFRACTIONS).get(gid, {})),
        }
        donnees["_meta"] = {
            "voice": [{"id": str(c.id), "name": c.name} for c in guild.voice_channels],
        }
        return jsonify({"config": donnees})

    try:
        app.add_url_rule("/api/guild/<guild_id>/extras", "extras_api",
                         extras, methods=["GET", "POST"])
    except Exception as err:
        print(f"[modules_extra] API non enregistree : {err}")
