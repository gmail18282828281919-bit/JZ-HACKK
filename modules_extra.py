# -*- coding: utf-8 -*-
# ============================================================================
#  ModeraBot — PACK DE MODULES SUPPLEMENTAIRES
#  ---------------------------------------------------------------------------
#  Ce fichier N'EDITE RIEN dans app.py : il s'y branche.
#  Dans app.py, juste AVANT la derniere ligne "bot.run(TOKEN)", ajoute :
#
#      import modules_extra
#      modules_extra.setup(bot, app)
#
#  Nouvelles categories ajoutees (chacune a son panneau + ses commandes) :
#     💰 Economie          +economy
#     🛡️ AutoMod Pro       +automod
#     💡 Suggestions       +suggestions
#     📊 Sondages          +pollconfig
#     🔒 Protection        +guard
#     📋 Candidatures      +apply
#
#  Toute la config est stockee dans extras_configs/<guild_id>.json et est
#  editable depuis le dashboard via /api/guild/<gid>/extras (GET / POST).
# ============================================================================

import os
import json
import time
import random
import asyncio
import re
from datetime import datetime, timedelta, timezone

import discord
from discord.ext import commands, tasks

# ---------------------------------------------------------------------------
#  Couleurs / constantes
# ---------------------------------------------------------------------------
X_BLUE   = 0x5865F2
X_GREEN  = 0x57F287
X_RED    = 0xED4245
X_ORANGE = 0xFEE75C
X_GOLD   = 0xF1C40F
X_PURPLE = 0x9B59B6
X_CYAN   = 0x22D3EE

EXTRAS_DIR = "extras_configs"
os.makedirs(EXTRAS_DIR, exist_ok=True)

bot = None      # rempli par setup()
app = None      # rempli par setup()

# ---------------------------------------------------------------------------
#  Stockage
# ---------------------------------------------------------------------------
DEFAULT_CFG = {
    "economy": {
        "enabled": False,
        "symbole": "🪙",
        "monnaie": "coins",
        "start_balance": 100,
        "daily_amount": 250,
        "work_min": 50,
        "work_max": 300,
        "work_cooldown": 3600,
        "rob_enabled": True,
        "rob_cooldown": 7200,
        "rob_success": 40,
        "rob_max_percent": 20,
        "log_channel": None,
        "shop": [],
    },
    "automod": {
        "enabled": False,
        "log_channel": None,
        "badwords": [],
        "badword_action": "delete",
        "anti_invite": False,
        "invite_action": "delete",
        "anti_zalgo": False,
        "anti_spoiler": False,
        "max_lines": 0,
        "max_attachments": 0,
        "ignored_channels": [],
        "ignored_roles": [],
        "warn_message": "{user} ce message n'est pas autorise ici.",
    },
    "suggestions": {
        "enabled": False,
        "channel_id": None,
        "review_channel": None,
        "log_channel": None,
        "up_emoji": "👍",
        "down_emoji": "👎",
        "anonymous": False,
        "threads": True,
        "auto_delete_cmd": True,
        "min_length": 10,
        "counter": 0,
    },
    "polls": {
        "enabled": False,
        "channel_id": None,
        "default_duration": "1h",
        "color": "#5865F2",
        "allow_multi": False,
        "show_voters": False,
        "ping_role": None,
    },
    "guard": {
        "raidmode": False,
        "panic": False,
        "lock_message": "🔒 Ce salon a ete verrouille par le staff.",
        "unlock_message": "🔓 Ce salon est de nouveau ouvert.",
        "log_channel": None,
        "agegate": False,
        "agegate_days": 7,
        "agegate_action": "kick",
        "auto_slowmode": 0,
        "locked_channels": [],
        "immune_roles": [],
    },
    "antinuke": {
        "enabled": False,
        "log_channel": None,
        "punish": "strip",
        "window": 60,
        "max_channel_delete": 3,
        "max_role_delete": 3,
        "max_ban": 3,
        "max_kick": 5,
        "protect_channels": True,
        "protect_roles": True,
        "protect_bans": True,
        "protect_kicks": True,
        "anti_bot_add": False,
        "whitelist_roles": [],
        "whitelist_users": [],
    },
    "infractions": {
        "enabled": False,
        "log_channel": None,
        "dm_user": True,
        "expire_days": 0,
        "auto_mute_at": 3,
        "auto_kick_at": 0,
        "auto_ban_at": 5,
    },
    "automsg": {
        "enabled": False,
        "messages": [],
    },
    "birthdays": {
        "enabled": False,
        "channel_id": None,
        "role_id": None,
        "hour": 10,
        "message": "Joyeux anniversaire {user} !",
    },
    "customcmds": {
        "enabled": False,
        "delete_trigger": False,
        "commands": [],
    },
    "apply": {
        "enabled": False,
        "panel_channel": None,
        "review_channel": None,
        "accepted_role": None,
        "log_channel": None,
        "titre": "📋 Candidatures",
        "description": "Choisis un poste ci-dessous pour postuler.",
        "couleur": "#5865F2",
        "cooldown_hours": 24,
        "postes": [],
    },
}


def _deep_default(cur, ref):
    if not isinstance(cur, dict):
        return json.loads(json.dumps(ref))
    for k, v in ref.items():
        if k not in cur or cur[k] is None:
            cur[k] = json.loads(json.dumps(v))
        elif isinstance(v, dict):
            cur[k] = _deep_default(cur[k], v)
    return cur


def xpath(gid):
    return os.path.join(EXTRAS_DIR, f"{gid}.json")


def xload(gid):
    try:
        with open(xpath(gid), "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        data = {}
    return _deep_default(data, DEFAULT_CFG)


def xsave(gid, data):
    try:
        with open(xpath(gid), "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except Exception:
        pass


def xget(gid, section):
    return xload(gid).get(section, {})


def xset(gid, section, data):
    cfg = xload(gid)
    cfg[section] = data
    xsave(gid, cfg)


# --- banque / inventaires (fichier separe, plus gros) ----------------------
BANK_DIR = "extras_bank"
os.makedirs(BANK_DIR, exist_ok=True)


def bank_load(gid):
    try:
        with open(os.path.join(BANK_DIR, f"{gid}.json"), "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def bank_save(gid, data):
    try:
        with open(os.path.join(BANK_DIR, f"{gid}.json"), "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except Exception:
        pass


def acc(gid, uid):
    data = bank_load(gid)
    u = data.get(str(uid))
    if not u:
        eco = xget(gid, "economy")
        u = {"cash": int(eco.get("start_balance", 100)), "bank": 0,
             "items": [], "daily": 0, "work": 0, "rob": 0}
        data[str(uid)] = u
        bank_save(gid, data)
    for k, v in (("cash", 0), ("bank", 0), ("items", []), ("daily", 0), ("work", 0), ("rob", 0)):
        u.setdefault(k, v)
    return u


def acc_save(gid, uid, u):
    data = bank_load(gid)
    data[str(uid)] = u
    bank_save(gid, data)


# ---------------------------------------------------------------------------
#  Petits helpers
# ---------------------------------------------------------------------------
def ok(desc):
    return discord.Embed(description=f"✅ {desc}", color=X_GREEN)


def err(desc):
    return discord.Embed(description=f"❌ {desc}", color=X_RED)


def warn(desc):
    return discord.Embed(description=f"⚠️ {desc}", color=X_ORANGE)


def is_admin(member):
    try:
        return member.guild_permissions.administrator or member.id == member.guild.owner_id
    except Exception:
        return False


def is_staff(member):
    try:
        p = member.guild_permissions
        return p.administrator or p.manage_guild or p.manage_messages or p.moderate_members
    except Exception:
        return False


def color_of(value, fallback=X_BLUE):
    try:
        return int(str(value).lstrip("#"), 16)
    except Exception:
        return fallback


def money(gid, amount):
    eco = xget(gid, "economy")
    return f"{eco.get('symbole','🪙')} **{int(amount):,}**".replace(",", " ")


def parse_duration(txt, default=3600):
    if not txt:
        return default
    m = re.fullmatch(r"\s*(\d+)\s*([smhdj]?)\s*", str(txt).lower())
    if not m:
        return default
    n = int(m.group(1))
    unit = m.group(2) or "m"
    return n * {"s": 1, "m": 60, "h": 3600, "d": 86400, "j": 86400}.get(unit, 60)


def fmt_left(seconds):
    seconds = max(0, int(seconds))
    h, r = divmod(seconds, 3600)
    m, s = divmod(r, 60)
    if h:
        return f"{h}h {m}min"
    if m:
        return f"{m}min {s}s"
    return f"{s}s"


async def send_log(guild, section_key, embed):
    """Envoie un embed dans le salon de logs configure pour la section."""
    try:
        cid = xget(guild.id, section_key).get("log_channel")
        if not cid:
            return
        ch = guild.get_channel(int(cid))
        if ch:
            await ch.send(embed=embed)
    except Exception:
        pass


def chan_field(guild, cid):
    return f"<#{cid}>" if cid else "❌ Non defini"


def role_field(cid):
    return f"<@&{cid}>" if cid else "❌ Non defini"


# ===========================================================================
# ===========================================================================
#   💰  CATEGORIE 1 — ECONOMIE
# ===========================================================================
# ===========================================================================

def eco_embed(guild):
    c = xget(guild.id, "economy")
    e = discord.Embed(
        title="💰 Systeme d'economie",
        description="Configure la monnaie du serveur, les gains et la boutique.\n"
                    "Utilise le menu ci-dessous pour tout regler.",
        color=X_GOLD)
    e.add_field(name="🔘 Statut", value="✅ Actif" if c.get("enabled") else "❌ Desactive", inline=True)
    e.add_field(name="🪙 Monnaie", value=f"{c.get('symbole','🪙')} {c.get('monnaie','coins')}", inline=True)
    e.add_field(name="🎁 Solde de depart", value=str(c.get("start_balance", 100)), inline=True)
    e.add_field(name="📅 Daily", value=f"{c.get('daily_amount',250)} / 24h", inline=True)
    e.add_field(name="💼 Travail",
                value=f"{c.get('work_min',50)} - {c.get('work_max',300)} · cd {fmt_left(c.get('work_cooldown',3600))}",
                inline=True)
    e.add_field(name="🔫 Vol",
                value=("✅ %d%% de reussite" % c.get("rob_success", 40)) if c.get("rob_enabled") else "❌ Desactive",
                inline=True)
    e.add_field(name="🛒 Boutique", value=f"{len(c.get('shop', []))} article(s)", inline=True)
    e.add_field(name="📋 Salon de logs", value=chan_field(guild, c.get("log_channel")), inline=True)
    e.add_field(name="⌨️ Commandes",
                value="`+balance` `+daily` `+work` `+pay` `+deposit` `+withdraw` `+rob`\n"
                      "`+shop` `+buy` `+inventory` `+ecolb` `+addmoney` `+removemoney`",
                inline=False)
    e.set_footer(text="ModeraBot • Economie")
    return e


class ModalEcoMonnaie(discord.ui.Modal, title="🪙 Monnaie du serveur"):
    symbole = discord.ui.TextInput(label="Symbole / emoji", max_length=8, placeholder="🪙")
    nom = discord.ui.TextInput(label="Nom de la monnaie", max_length=20, placeholder="coins")
    start = discord.ui.TextInput(label="Solde de depart", max_length=9, placeholder="100")

    def __init__(self, gid):
        super().__init__()
        self.gid = gid
        c = xget(gid, "economy")
        self.symbole.default = c.get("symbole", "🪙")
        self.nom.default = c.get("monnaie", "coins")
        self.start.default = str(c.get("start_balance", 100))

    async def on_submit(self, interaction: discord.Interaction):
        c = xget(self.gid, "economy")
        c["symbole"] = str(self.symbole.value).strip() or "🪙"
        c["monnaie"] = str(self.nom.value).strip() or "coins"
        try:
            c["start_balance"] = max(0, int(str(self.start.value).strip()))
        except Exception:
            pass
        xset(self.gid, "economy", c)
        await interaction.response.edit_message(embed=eco_embed(interaction.guild))


class ModalEcoGains(discord.ui.Modal, title="💼 Gains (daily & travail)"):
    daily = discord.ui.TextInput(label="Montant du daily", max_length=9, placeholder="250")
    wmin = discord.ui.TextInput(label="Gain minimum de +work", max_length=9, placeholder="50")
    wmax = discord.ui.TextInput(label="Gain maximum de +work", max_length=9, placeholder="300")
    cd = discord.ui.TextInput(label="Cooldown de +work (ex: 30m, 1h)", max_length=10, placeholder="1h")

    def __init__(self, gid):
        super().__init__()
        self.gid = gid
        c = xget(gid, "economy")
        self.daily.default = str(c.get("daily_amount", 250))
        self.wmin.default = str(c.get("work_min", 50))
        self.wmax.default = str(c.get("work_max", 300))
        self.cd.default = f"{int(c.get('work_cooldown', 3600) // 60)}m"

    async def on_submit(self, interaction: discord.Interaction):
        c = xget(self.gid, "economy")
        try:
            c["daily_amount"] = max(0, int(str(self.daily.value).strip()))
            c["work_min"] = max(0, int(str(self.wmin.value).strip()))
            c["work_max"] = max(c["work_min"], int(str(self.wmax.value).strip()))
        except Exception:
            return await interaction.response.send_message(
                embed=err("Les montants doivent etre des nombres."), ephemeral=True)
        c["work_cooldown"] = parse_duration(self.cd.value, 3600)
        xset(self.gid, "economy", c)
        await interaction.response.edit_message(embed=eco_embed(interaction.guild))


class ModalEcoRob(discord.ui.Modal, title="🔫 Reglages du vol"):
    success = discord.ui.TextInput(label="Chance de reussite (%)", max_length=3, placeholder="40")
    maxp = discord.ui.TextInput(label="Part volee maximum (%)", max_length=3, placeholder="20")
    cd = discord.ui.TextInput(label="Cooldown (ex: 2h)", max_length=10, placeholder="2h")

    def __init__(self, gid):
        super().__init__()
        self.gid = gid
        c = xget(gid, "economy")
        self.success.default = str(c.get("rob_success", 40))
        self.maxp.default = str(c.get("rob_max_percent", 20))
        self.cd.default = f"{int(c.get('rob_cooldown', 7200) // 60)}m"

    async def on_submit(self, interaction: discord.Interaction):
        c = xget(self.gid, "economy")
        try:
            c["rob_success"] = min(100, max(0, int(str(self.success.value).strip())))
            c["rob_max_percent"] = min(100, max(1, int(str(self.maxp.value).strip())))
        except Exception:
            return await interaction.response.send_message(
                embed=err("Entre des pourcentages valides."), ephemeral=True)
        c["rob_cooldown"] = parse_duration(self.cd.value, 7200)
        xset(self.gid, "economy", c)
        await interaction.response.edit_message(embed=eco_embed(interaction.guild))


class ModalEcoItem(discord.ui.Modal, title="🛒 Nouvel article"):
    nom = discord.ui.TextInput(label="Nom de l'article", max_length=40)
    prix = discord.ui.TextInput(label="Prix", max_length=9, placeholder="500")
    desc = discord.ui.TextInput(label="Description", max_length=100, required=False)
    role = discord.ui.TextInput(label="ID du role donne (optionnel)", max_length=25, required=False)
    stock = discord.ui.TextInput(label="Stock (-1 = illimite)", max_length=6, required=False, placeholder="-1")

    def __init__(self, gid):
        super().__init__()
        self.gid = gid

    async def on_submit(self, interaction: discord.Interaction):
        c = xget(self.gid, "economy")
        shop = c.get("shop", [])
        if len(shop) >= 25:
            return await interaction.response.send_message(embed=err("25 articles maximum."), ephemeral=True)
        try:
            prix = max(0, int(str(self.prix.value).strip()))
        except Exception:
            return await interaction.response.send_message(embed=err("Prix invalide."), ephemeral=True)
        try:
            stock = int(str(self.stock.value).strip() or "-1")
        except Exception:
            stock = -1
        shop.append({
            "nom": str(self.nom.value).strip(),
            "prix": prix,
            "description": str(self.desc.value or "").strip(),
            "role": str(self.role.value or "").strip() or None,
            "stock": stock,
        })
        c["shop"] = shop
        xset(self.gid, "economy", c)
        await interaction.response.edit_message(embed=eco_embed(interaction.guild))


class ModalEcoLog(discord.ui.Modal, title="📋 Salon de logs economie"):
    salon = discord.ui.TextInput(label="ID du salon (vide = aucun)", max_length=25, required=False)

    def __init__(self, gid):
        super().__init__()
        self.gid = gid
        self.salon.default = str(xget(gid, "economy").get("log_channel") or "")

    async def on_submit(self, interaction: discord.Interaction):
        c = xget(self.gid, "economy")
        v = str(self.salon.value or "").strip()
        c["log_channel"] = int(v) if v.isdigit() else None
        xset(self.gid, "economy", c)
        await interaction.response.edit_message(embed=eco_embed(interaction.guild))


class EcoShopRemove(discord.ui.View):
    def __init__(self, gid, author_id):
        super().__init__(timeout=120)
        self.gid = gid
        self.author_id = author_id
        shop = xget(gid, "economy").get("shop", [])
        opts = [discord.SelectOption(label=i["nom"][:100], value=str(n),
                                     description=f"{i.get('prix',0)} • {i.get('description','')[:50]}")
                for n, i in enumerate(shop[:25])]
        if opts:
            self.add_item(EcoShopRemoveSelect(opts))

    async def interaction_check(self, interaction):
        return str(interaction.user.id) == str(self.author_id)


class EcoShopRemoveSelect(discord.ui.Select):
    def __init__(self, options):
        super().__init__(placeholder="Article a supprimer...", options=options)

    async def callback(self, interaction: discord.Interaction):
        c = xget(interaction.guild.id, "economy")
        shop = c.get("shop", [])
        i = int(self.values[0])
        if 0 <= i < len(shop):
            nom = shop.pop(i)["nom"]
            c["shop"] = shop
            xset(interaction.guild.id, "economy", c)
            return await interaction.response.edit_message(
                embed=ok(f"Article **{nom}** supprime."), view=None)
        await interaction.response.edit_message(embed=err("Article introuvable."), view=None)


class EconomyView(discord.ui.View):
    def __init__(self, ctx):
        super().__init__(timeout=300)
        self.ctx = ctx

    async def interaction_check(self, interaction: discord.Interaction):
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message(embed=err("Ce panneau n'est pas pour toi."), ephemeral=True)
            return False
        return True

    @discord.ui.select(placeholder="⚙️ Configurer l'economie...", options=[
        discord.SelectOption(label="Monnaie & solde de depart", emoji="🪙", value="monnaie"),
        discord.SelectOption(label="Gains (daily / travail)", emoji="💼", value="gains"),
        discord.SelectOption(label="Reglages du vol", emoji="🔫", value="rob"),
        discord.SelectOption(label="Ajouter un article a la boutique", emoji="🛒", value="additem"),
        discord.SelectOption(label="Supprimer un article", emoji="🗑️", value="delitem"),
        discord.SelectOption(label="Salon de logs", emoji="📋", value="logs"),
    ])
    async def menu(self, interaction: discord.Interaction, select: discord.ui.Select):
        gid = interaction.guild.id
        v = select.values[0]
        if v == "monnaie":
            return await interaction.response.send_modal(ModalEcoMonnaie(gid))
        if v == "gains":
            return await interaction.response.send_modal(ModalEcoGains(gid))
        if v == "rob":
            return await interaction.response.send_modal(ModalEcoRob(gid))
        if v == "additem":
            return await interaction.response.send_modal(ModalEcoItem(gid))
        if v == "logs":
            return await interaction.response.send_modal(ModalEcoLog(gid))
        if v == "delitem":
            if not xget(gid, "economy").get("shop"):
                return await interaction.response.send_message(embed=err("La boutique est vide."), ephemeral=True)
            return await interaction.response.send_message(
                embed=warn("Choisis l'article a supprimer."),
                view=EcoShopRemove(gid, interaction.user.id), ephemeral=True)

    @discord.ui.button(label="Activer / Desactiver", emoji="🔘", style=discord.ButtonStyle.success, row=1)
    async def toggle(self, interaction: discord.Interaction, button: discord.ui.Button):
        c = xget(interaction.guild.id, "economy")
        c["enabled"] = not c.get("enabled")
        xset(interaction.guild.id, "economy", c)
        await interaction.response.edit_message(embed=eco_embed(interaction.guild), view=self)

    @discord.ui.button(label="Vol on/off", emoji="🔫", style=discord.ButtonStyle.secondary, row=1)
    async def togglerob(self, interaction: discord.Interaction, button: discord.ui.Button):
        c = xget(interaction.guild.id, "economy")
        c["rob_enabled"] = not c.get("rob_enabled")
        xset(interaction.guild.id, "economy", c)
        await interaction.response.edit_message(embed=eco_embed(interaction.guild), view=self)

    @discord.ui.button(label="Reset de la banque", emoji="🗑️", style=discord.ButtonStyle.danger, row=1)
    async def reset(self, interaction: discord.Interaction, button: discord.ui.Button):
        bank_save(interaction.guild.id, {})
        await interaction.response.send_message(embed=ok("Tous les soldes ont ete remis a zero."), ephemeral=True)

    @discord.ui.button(label="Fermer", emoji="✖️", style=discord.ButtonStyle.secondary, row=1)
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(view=None)
        self.stop()


def register_economy(bot):

    def eco_on(ctx):
        return xget(ctx.guild.id, "economy").get("enabled")

    @bot.command(name="economy", aliases=["eco", "economie", "ecoconfig", "ecosetup"])
    async def economy_cmd(ctx):
        """Panneau de configuration de l'economie."""
        if not is_admin(ctx.author):
            return await ctx.send(embed=err("Permission administrateur requise."))
        await ctx.send(embed=eco_embed(ctx.guild), view=EconomyView(ctx))

    @bot.command(name="balance", aliases=["bal", "argent", "solde", "money"])
    async def balance_cmd(ctx, membre: discord.Member = None):
        if not eco_on(ctx):
            return await ctx.send(embed=err("L'economie est desactivee (`+economy`)."))
        membre = membre or ctx.author
        u = acc(ctx.guild.id, membre.id)
        total = u["cash"] + u["bank"]
        e = discord.Embed(title=f"💰 Portefeuille de {membre.display_name}", color=X_GOLD)
        e.add_field(name="👛 En poche", value=money(ctx.guild.id, u["cash"]), inline=True)
        e.add_field(name="🏦 En banque", value=money(ctx.guild.id, u["bank"]), inline=True)
        e.add_field(name="📊 Total", value=money(ctx.guild.id, total), inline=True)
        if u["items"]:
            e.add_field(name="🎒 Inventaire", value=", ".join(u["items"][:10]), inline=False)
        e.set_thumbnail(url=membre.display_avatar.url)
        await ctx.send(embed=e)

    @bot.command(name="daily", aliases=["quotidien", "journalier"])
    async def daily_cmd(ctx):
        if not eco_on(ctx):
            return await ctx.send(embed=err("L'economie est desactivee (`+economy`)."))
        c = xget(ctx.guild.id, "economy")
        u = acc(ctx.guild.id, ctx.author.id)
        left = u["daily"] + 86400 - time.time()
        if left > 0:
            return await ctx.send(embed=warn(f"Deja recupere. Reviens dans **{fmt_left(left)}**."))
        gain = int(c.get("daily_amount", 250))
        u["cash"] += gain
        u["daily"] = int(time.time())
        acc_save(ctx.guild.id, ctx.author.id, u)
        await ctx.send(embed=discord.Embed(
            description=f"📅 Tu recuperes ton daily : {money(ctx.guild.id, gain)}\n"
                        f"Nouveau solde : {money(ctx.guild.id, u['cash'])}",
            color=X_GREEN))

    @bot.command(name="work", aliases=["travail", "travailler", "bosser"])
    async def work_cmd(ctx):
        if not eco_on(ctx):
            return await ctx.send(embed=err("L'economie est desactivee (`+economy`)."))
        c = xget(ctx.guild.id, "economy")
        u = acc(ctx.guild.id, ctx.author.id)
        cd = int(c.get("work_cooldown", 3600))
        left = u["work"] + cd - time.time()
        if left > 0:
            return await ctx.send(embed=warn(f"Tu es fatigue. Repos encore **{fmt_left(left)}**."))
        gain = random.randint(int(c.get("work_min", 50)), int(c.get("work_max", 300)))
        jobs = ["livreur de pizzas", "developpeur", "streamer", "moderateur freelance",
                "chauffeur de taxi", "vendeur de kebabs", "graphiste", "youtubeur"]
        u["cash"] += gain
        u["work"] = int(time.time())
        acc_save(ctx.guild.id, ctx.author.id, u)
        await ctx.send(embed=discord.Embed(
            description=f"💼 Tu as bosse comme **{random.choice(jobs)}** et gagne {money(ctx.guild.id, gain)}.",
            color=X_GREEN))

    @bot.command(name="pay", aliases=["payer", "donner", "give"])
    async def pay_cmd(ctx, membre: discord.Member = None, montant: int = None):
        if not eco_on(ctx):
            return await ctx.send(embed=err("L'economie est desactivee (`+economy`)."))
        if not membre or montant is None:
            return await ctx.send(embed=err("Usage : `+pay @membre montant`"))
        if montant <= 0:
            return await ctx.send(embed=err("Le montant doit etre positif."))
        if membre.id == ctx.author.id:
            return await ctx.send(embed=err("Tu ne peux pas te payer toi-meme."))
        u = acc(ctx.guild.id, ctx.author.id)
        if u["cash"] < montant:
            return await ctx.send(embed=err("Tu n'as pas assez en poche."))
        t = acc(ctx.guild.id, membre.id)
        u["cash"] -= montant
        t["cash"] += montant
        acc_save(ctx.guild.id, ctx.author.id, u)
        acc_save(ctx.guild.id, membre.id, t)
        await ctx.send(embed=ok(f"{ctx.author.mention} a envoye {money(ctx.guild.id, montant)} a {membre.mention}."))
        await send_log(ctx.guild, "economy", discord.Embed(
            title="💸 Transfert", color=X_GOLD,
            description=f"{ctx.author} ➜ {membre} : {montant}"))

    @bot.command(name="deposit", aliases=["dep", "deposer"])
    async def deposit_cmd(ctx, montant: str = None):
        if not eco_on(ctx):
            return await ctx.send(embed=err("L'economie est desactivee (`+economy`)."))
        u = acc(ctx.guild.id, ctx.author.id)
        if montant in ("all", "tout"):
            montant = u["cash"]
        else:
            try:
                montant = int(montant)
            except Exception:
                return await ctx.send(embed=err("Usage : `+deposit montant` ou `+deposit all`"))
        if montant <= 0 or montant > u["cash"]:
            return await ctx.send(embed=err("Montant invalide."))
        u["cash"] -= montant
        u["bank"] += montant
        acc_save(ctx.guild.id, ctx.author.id, u)
        await ctx.send(embed=ok(f"{money(ctx.guild.id, montant)} deposes en banque."))

    @bot.command(name="withdraw", aliases=["with", "retirer", "retrait"])
    async def withdraw_cmd(ctx, montant: str = None):
        if not eco_on(ctx):
            return await ctx.send(embed=err("L'economie est desactivee (`+economy`)."))
        u = acc(ctx.guild.id, ctx.author.id)
        if montant in ("all", "tout"):
            montant = u["bank"]
        else:
            try:
                montant = int(montant)
            except Exception:
                return await ctx.send(embed=err("Usage : `+withdraw montant` ou `+withdraw all`"))
        if montant <= 0 or montant > u["bank"]:
            return await ctx.send(embed=err("Montant invalide."))
        u["bank"] -= montant
        u["cash"] += montant
        acc_save(ctx.guild.id, ctx.author.id, u)
        await ctx.send(embed=ok(f"{money(ctx.guild.id, montant)} retires de la banque."))

    @bot.command(name="rob", aliases=["voler", "braquer"])
    async def rob_cmd(ctx, membre: discord.Member = None):
        if not eco_on(ctx):
            return await ctx.send(embed=err("L'economie est desactivee (`+economy`)."))
        c = xget(ctx.guild.id, "economy")
        if not c.get("rob_enabled"):
            return await ctx.send(embed=err("Le vol est desactive sur ce serveur."))
        if not membre or membre.id == ctx.author.id or membre.bot:
            return await ctx.send(embed=err("Usage : `+rob @membre`"))
        u = acc(ctx.guild.id, ctx.author.id)
        left = u["rob"] + int(c.get("rob_cooldown", 7200)) - time.time()
        if left > 0:
            return await ctx.send(embed=warn(f"Trop risque pour l'instant. Attends **{fmt_left(left)}**."))
        t = acc(ctx.guild.id, membre.id)
        u["rob"] = int(time.time())
        if t["cash"] < 50:
            acc_save(ctx.guild.id, ctx.author.id, u)
            return await ctx.send(embed=warn(f"{membre.display_name} n'a rien en poche."))
        if random.randint(1, 100) <= int(c.get("rob_success", 40)):
            vol = int(t["cash"] * int(c.get("rob_max_percent", 20)) / 100)
            vol = max(1, random.randint(1, max(1, vol)))
            t["cash"] -= vol
            u["cash"] += vol
            msg = f"🔫 Braquage reussi ! Tu voles {money(ctx.guild.id, vol)} a {membre.mention}."
            col = X_GREEN
        else:
            amende = min(u["cash"], random.randint(50, 200))
            u["cash"] -= amende
            msg = f"🚨 Tu t'es fait attraper ! Amende de {money(ctx.guild.id, amende)}."
            col = X_RED
        acc_save(ctx.guild.id, ctx.author.id, u)
        acc_save(ctx.guild.id, membre.id, t)
        await ctx.send(embed=discord.Embed(description=msg, color=col))

    @bot.command(name="shop", aliases=["boutique", "magasin", "store"])
    async def shop_cmd(ctx):
        if not eco_on(ctx):
            return await ctx.send(embed=err("L'economie est desactivee (`+economy`)."))
        c = xget(ctx.guild.id, "economy")
        shop = c.get("shop", [])
        if not shop:
            return await ctx.send(embed=warn("La boutique est vide. Un admin peut ajouter des articles avec `+economy`."))
        e = discord.Embed(title="🛒 Boutique du serveur",
                          description="Achete avec `+buy <numero>`.", color=X_GOLD)
        for i, it in enumerate(shop, 1):
            stock = it.get("stock", -1)
            stxt = "∞" if stock is None or stock < 0 else str(stock)
            e.add_field(
                name=f"`{i}.` {it['nom']} — {c.get('symbole','🪙')} {it.get('prix',0)}",
                value=f"{it.get('description') or 'Aucune description'}\n"
                      f"Stock : **{stxt}**" + (f" · Role : <@&{it['role']}>" if it.get("role") else ""),
                inline=False)
        e.set_footer(text=f"{len(shop)} article(s)")
        await ctx.send(embed=e)

    @bot.command(name="buy", aliases=["acheter", "achat"])
    async def buy_cmd(ctx, numero: int = None):
        if not eco_on(ctx):
            return await ctx.send(embed=err("L'economie est desactivee (`+economy`)."))
        c = xget(ctx.guild.id, "economy")
        shop = c.get("shop", [])
        if numero is None or numero < 1 or numero > len(shop):
            return await ctx.send(embed=err("Usage : `+buy <numero>` — voir `+shop`."))
        it = shop[numero - 1]
        stock = it.get("stock", -1)
        if stock is not None and stock == 0:
            return await ctx.send(embed=err("Article en rupture de stock."))
        u = acc(ctx.guild.id, ctx.author.id)
        prix = int(it.get("prix", 0))
        if u["cash"] < prix:
            return await ctx.send(embed=err(f"Il te manque {money(ctx.guild.id, prix - u['cash'])}."))
        u["cash"] -= prix
        u["items"].append(it["nom"])
        acc_save(ctx.guild.id, ctx.author.id, u)
        if stock is not None and stock > 0:
            it["stock"] = stock - 1
            c["shop"] = shop
            xset(ctx.guild.id, "economy", c)
        if it.get("role"):
            try:
                role = ctx.guild.get_role(int(it["role"]))
                if role:
                    await ctx.author.add_roles(role, reason="Achat boutique")
            except Exception:
                pass
        await ctx.send(embed=ok(f"Tu as achete **{it['nom']}** pour {money(ctx.guild.id, prix)}."))
        await send_log(ctx.guild, "economy", discord.Embed(
            title="🛒 Achat", color=X_GOLD, description=f"{ctx.author} a achete **{it['nom']}** ({prix})"))

    @bot.command(name="inventory", aliases=["inventaire", "sac", "items"])
    async def inventory_cmd(ctx, membre: discord.Member = None):
        if not eco_on(ctx):
            return await ctx.send(embed=err("L'economie est desactivee (`+economy`)."))
        membre = membre or ctx.author
        u = acc(ctx.guild.id, membre.id)
        if not u["items"]:
            return await ctx.send(embed=warn(f"{membre.display_name} n'a aucun article."))
        compte = {}
        for i in u["items"]:
            compte[i] = compte.get(i, 0) + 1
        e = discord.Embed(title=f"🎒 Inventaire de {membre.display_name}",
                          description="\n".join(f"• **{k}** ×{v}" for k, v in compte.items()),
                          color=X_PURPLE)
        await ctx.send(embed=e)

    @bot.command(name="ecolb", aliases=["ecoleaderboard", "richest", "topargent", "classementargent"])
    async def ecolb_cmd(ctx):
        if not eco_on(ctx):
            return await ctx.send(embed=err("L'economie est desactivee (`+economy`)."))
        data = bank_load(ctx.guild.id)
        rows = sorted(data.items(), key=lambda kv: kv[1].get("cash", 0) + kv[1].get("bank", 0), reverse=True)[:10]
        if not rows:
            return await ctx.send(embed=warn("Aucun compte pour l'instant."))
        medals = ["🥇", "🥈", "🥉"] + ["🔹"] * 7
        lines = []
        for i, (uid, u) in enumerate(rows):
            m = ctx.guild.get_member(int(uid))
            nom = m.display_name if m else f"Utilisateur {uid}"
            lines.append(f"{medals[i]} **{nom}** — {money(ctx.guild.id, u.get('cash', 0) + u.get('bank', 0))}")
        await ctx.send(embed=discord.Embed(title="🏆 Les plus riches du serveur",
                                           description="\n".join(lines), color=X_GOLD))

    @bot.command(name="addmoney", aliases=["ajoutargent", "givemoney"])
    async def addmoney_cmd(ctx, membre: discord.Member = None, montant: int = None):
        if not is_admin(ctx.author):
            return await ctx.send(embed=err("Permission administrateur requise."))
        if not membre or montant is None:
            return await ctx.send(embed=err("Usage : `+addmoney @membre montant`"))
        u = acc(ctx.guild.id, membre.id)
        u["cash"] += montant
        acc_save(ctx.guild.id, membre.id, u)
        await ctx.send(embed=ok(f"{money(ctx.guild.id, montant)} ajoutes a {membre.mention}."))

    @bot.command(name="removemoney", aliases=["retirerargent", "takemoney"])
    async def removemoney_cmd(ctx, membre: discord.Member = None, montant: int = None):
        if not is_admin(ctx.author):
            return await ctx.send(embed=err("Permission administrateur requise."))
        if not membre or montant is None:
            return await ctx.send(embed=err("Usage : `+removemoney @membre montant`"))
        u = acc(ctx.guild.id, membre.id)
        u["cash"] = max(0, u["cash"] - montant)
        acc_save(ctx.guild.id, membre.id, u)
        await ctx.send(embed=ok(f"{money(ctx.guild.id, montant)} retires a {membre.mention}."))

    @bot.command(name="resetmoney", aliases=["resetargent", "resetbank"])
    async def resetmoney_cmd(ctx, membre: discord.Member = None):
        if not is_admin(ctx.author):
            return await ctx.send(embed=err("Permission administrateur requise."))
        if membre:
            data = bank_load(ctx.guild.id)
            data.pop(str(membre.id), None)
            bank_save(ctx.guild.id, data)
            return await ctx.send(embed=ok(f"Compte de {membre.mention} reinitialise."))
        bank_save(ctx.guild.id, {})
        await ctx.send(embed=ok("Tous les comptes ont ete reinitialises."))


# ===========================================================================
# ===========================================================================
#   🛡️  CATEGORIE 2 — AUTOMOD PRO
# ===========================================================================
# ===========================================================================

INVITE_RE = re.compile(r"(discord\.(gg|io|me|li)|discordapp\.com/invite|discord\.com/invite)/\S+", re.I)
ZALGO_RE = re.compile(r"[̀-ͯ҃-҉᪰-᫿᷀-᷿⃐-⃰]{4,}")

ACTIONS = {
    "delete": "Supprimer le message",
    "warn": "Supprimer + avertir",
    "mute": "Supprimer + mute 10 min",
    "kick": "Supprimer + expulser",
    "ban": "Supprimer + bannir",
    "log": "Journaliser seulement",
}


def am_embed(guild):
    c = xget(guild.id, "automod")
    e = discord.Embed(
        title="🛡️ AutoMod Pro",
        description="Filtres automatiques de messages : mots interdits, pubs, spam de lignes, zalgo…\n"
                    "Complementaire de `+antiraid` (qui gere le flood et les raids).",
        color=X_BLUE)
    e.add_field(name="🔘 Statut", value="✅ Actif" if c.get("enabled") else "❌ Desactive", inline=True)
    e.add_field(name="📋 Logs", value=chan_field(guild, c.get("log_channel")), inline=True)
    e.add_field(name="🤬 Mots interdits",
                value=f"{len(c.get('badwords', []))} mot(s) · action : `{c.get('badword_action','delete')}`",
                inline=False)
    e.add_field(name="🔗 Anti-pub (invitations)",
                value=("✅ Actif · action : `%s`" % c.get("invite_action", "delete")) if c.get("anti_invite") else "❌ Desactive",
                inline=True)
    e.add_field(name="🌀 Anti-zalgo", value="✅" if c.get("anti_zalgo") else "❌", inline=True)
    e.add_field(name="🙈 Anti-spoiler", value="✅" if c.get("anti_spoiler") else "❌", inline=True)
    e.add_field(name="📏 Lignes max",
                value=str(c.get("max_lines") or "∞"), inline=True)
    e.add_field(name="📎 Fichiers max par message",
                value=str(c.get("max_attachments") or "∞"), inline=True)
    ign = c.get("ignored_channels", [])
    e.add_field(name="🚫 Salons ignores",
                value=(" ".join(f"<#{i}>" for i in ign[:8]) if ign else "Aucun"), inline=False)
    igr = c.get("ignored_roles", [])
    e.add_field(name="🎭 Roles ignores",
                value=(" ".join(f"<@&{i}>" for i in igr[:8]) if igr else "Aucun"), inline=False)
    e.add_field(name="⌨️ Commandes",
                value="`+badword add/del/list` `+antiinvite` `+automodignore` `+automodlogs` `+automodtest`",
                inline=False)
    e.set_footer(text="ModeraBot • AutoMod Pro")
    return e


class ModalAmBadwords(discord.ui.Modal, title="🤬 Mots interdits"):
    mots = discord.ui.TextInput(label="Liste (separee par des virgules)",
                                style=discord.TextStyle.paragraph, required=False, max_length=1500)
    action = discord.ui.TextInput(label="Action : delete / warn / mute / kick / ban", max_length=10)

    def __init__(self, gid):
        super().__init__()
        self.gid = gid
        c = xget(gid, "automod")
        self.mots.default = ", ".join(c.get("badwords", []))
        self.action.default = c.get("badword_action", "delete")

    async def on_submit(self, interaction: discord.Interaction):
        c = xget(self.gid, "automod")
        mots = [m.strip().lower() for m in str(self.mots.value or "").split(",") if m.strip()]
        c["badwords"] = mots[:200]
        a = str(self.action.value).strip().lower()
        c["badword_action"] = a if a in ACTIONS else "delete"
        xset(self.gid, "automod", c)
        await interaction.response.edit_message(embed=am_embed(interaction.guild))


class ModalAmLimites(discord.ui.Modal, title="📏 Limites de message"):
    lignes = discord.ui.TextInput(label="Lignes max (0 = illimite)", max_length=4, placeholder="0")
    fichiers = discord.ui.TextInput(label="Fichiers max (0 = illimite)", max_length=3, placeholder="0")
    msg = discord.ui.TextInput(label="Message d'avertissement",
                               style=discord.TextStyle.paragraph, required=False, max_length=300)

    def __init__(self, gid):
        super().__init__()
        self.gid = gid
        c = xget(gid, "automod")
        self.lignes.default = str(c.get("max_lines", 0))
        self.fichiers.default = str(c.get("max_attachments", 0))
        self.msg.default = c.get("warn_message", "")

    async def on_submit(self, interaction: discord.Interaction):
        c = xget(self.gid, "automod")
        try:
            c["max_lines"] = max(0, int(str(self.lignes.value).strip() or 0))
            c["max_attachments"] = max(0, int(str(self.fichiers.value).strip() or 0))
        except Exception:
            return await interaction.response.send_message(embed=err("Entre des nombres valides."), ephemeral=True)
        c["warn_message"] = str(self.msg.value or "").strip()
        xset(self.gid, "automod", c)
        await interaction.response.edit_message(embed=am_embed(interaction.guild))


class ModalAmInvite(discord.ui.Modal, title="🔗 Anti-pub"):
    action = discord.ui.TextInput(label="Action : delete / warn / mute / kick / ban", max_length=10)

    def __init__(self, gid):
        super().__init__()
        self.gid = gid
        self.action.default = xget(gid, "automod").get("invite_action", "delete")

    async def on_submit(self, interaction: discord.Interaction):
        c = xget(self.gid, "automod")
        a = str(self.action.value).strip().lower()
        c["invite_action"] = a if a in ACTIONS else "delete"
        c["anti_invite"] = True
        xset(self.gid, "automod", c)
        await interaction.response.edit_message(embed=am_embed(interaction.guild))


class ModalAmIgnore(discord.ui.Modal, title="🚫 Exceptions"):
    salons = discord.ui.TextInput(label="IDs de salons ignores (virgules)", required=False, max_length=500)
    roles = discord.ui.TextInput(label="IDs de roles ignores (virgules)", required=False, max_length=500)
    logs = discord.ui.TextInput(label="ID du salon de logs AutoMod", required=False, max_length=25)

    def __init__(self, gid):
        super().__init__()
        self.gid = gid
        c = xget(gid, "automod")
        self.salons.default = ", ".join(str(i) for i in c.get("ignored_channels", []))
        self.roles.default = ", ".join(str(i) for i in c.get("ignored_roles", []))
        self.logs.default = str(c.get("log_channel") or "")

    async def on_submit(self, interaction: discord.Interaction):
        c = xget(self.gid, "automod")
        c["ignored_channels"] = [int(x) for x in re.findall(r"\d{5,25}", str(self.salons.value or ""))][:50]
        c["ignored_roles"] = [int(x) for x in re.findall(r"\d{5,25}", str(self.roles.value or ""))][:50]
        v = str(self.logs.value or "").strip()
        c["log_channel"] = int(v) if v.isdigit() else None
        xset(self.gid, "automod", c)
        await interaction.response.edit_message(embed=am_embed(interaction.guild))


class AutomodView(discord.ui.View):
    def __init__(self, ctx):
        super().__init__(timeout=300)
        self.ctx = ctx

    async def interaction_check(self, interaction: discord.Interaction):
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message(embed=err("Ce panneau n'est pas pour toi."), ephemeral=True)
            return False
        return True

    @discord.ui.select(placeholder="⚙️ Configurer l'AutoMod...", options=[
        discord.SelectOption(label="Mots interdits", emoji="🤬", value="badwords"),
        discord.SelectOption(label="Anti-pub (invitations Discord)", emoji="🔗", value="invite"),
        discord.SelectOption(label="Limites (lignes / fichiers)", emoji="📏", value="limites"),
        discord.SelectOption(label="Exceptions & salon de logs", emoji="🚫", value="ignore"),
    ])
    async def menu(self, interaction: discord.Interaction, select: discord.ui.Select):
        v = select.values[0]
        gid = interaction.guild.id
        if v == "badwords":
            return await interaction.response.send_modal(ModalAmBadwords(gid))
        if v == "invite":
            return await interaction.response.send_modal(ModalAmInvite(gid))
        if v == "limites":
            return await interaction.response.send_modal(ModalAmLimites(gid))
        if v == "ignore":
            return await interaction.response.send_modal(ModalAmIgnore(gid))

    @discord.ui.button(label="Activer / Desactiver", emoji="🔘", style=discord.ButtonStyle.success, row=1)
    async def toggle(self, interaction: discord.Interaction, button: discord.ui.Button):
        c = xget(interaction.guild.id, "automod")
        c["enabled"] = not c.get("enabled")
        xset(interaction.guild.id, "automod", c)
        await interaction.response.edit_message(embed=am_embed(interaction.guild), view=self)

    @discord.ui.button(label="Anti-pub on/off", emoji="🔗", style=discord.ButtonStyle.secondary, row=1)
    async def tinv(self, interaction: discord.Interaction, button: discord.ui.Button):
        c = xget(interaction.guild.id, "automod")
        c["anti_invite"] = not c.get("anti_invite")
        xset(interaction.guild.id, "automod", c)
        await interaction.response.edit_message(embed=am_embed(interaction.guild), view=self)

    @discord.ui.button(label="Zalgo on/off", emoji="🌀", style=discord.ButtonStyle.secondary, row=1)
    async def tzal(self, interaction: discord.Interaction, button: discord.ui.Button):
        c = xget(interaction.guild.id, "automod")
        c["anti_zalgo"] = not c.get("anti_zalgo")
        xset(interaction.guild.id, "automod", c)
        await interaction.response.edit_message(embed=am_embed(interaction.guild), view=self)

    @discord.ui.button(label="Spoiler on/off", emoji="🙈", style=discord.ButtonStyle.secondary, row=2)
    async def tspo(self, interaction: discord.Interaction, button: discord.ui.Button):
        c = xget(interaction.guild.id, "automod")
        c["anti_spoiler"] = not c.get("anti_spoiler")
        xset(interaction.guild.id, "automod", c)
        await interaction.response.edit_message(embed=am_embed(interaction.guild), view=self)

    @discord.ui.button(label="Tout desactiver", emoji="🔴", style=discord.ButtonStyle.danger, row=2)
    async def offall(self, interaction: discord.Interaction, button: discord.ui.Button):
        c = xget(interaction.guild.id, "automod")
        for k in ("enabled", "anti_invite", "anti_zalgo", "anti_spoiler"):
            c[k] = False
        xset(interaction.guild.id, "automod", c)
        await interaction.response.edit_message(embed=am_embed(interaction.guild), view=self)

    @discord.ui.button(label="Fermer", emoji="✖️", style=discord.ButtonStyle.secondary, row=2)
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(view=None)
        self.stop()


async def automod_punish(message, action, motif):
    """Applique l'action AutoMod et journalise."""
    guild = message.guild
    c = xget(guild.id, "automod")
    if action != "log":
        try:
            await message.delete()
        except Exception:
            pass
    if action in ("warn", "mute", "kick", "ban"):
        txt = (c.get("warn_message") or "{user} ce message n'est pas autorise ici.").replace(
            "{user}", message.author.mention).replace("{motif}", motif)
        try:
            await message.channel.send(txt, delete_after=8)
        except Exception:
            pass
    try:
        if action == "mute":
            await message.author.timeout(timedelta(minutes=10), reason=f"AutoMod : {motif}")
        elif action == "kick":
            await message.author.kick(reason=f"AutoMod : {motif}")
        elif action == "ban":
            await message.author.ban(reason=f"AutoMod : {motif}", delete_message_days=0)
    except Exception:
        pass

    try:
        if xget(guild.id, "infractions").get("enabled"):
            await inf_record(guild, message.author, "automod", motif, guild.me)
    except Exception:
        pass

    e = discord.Embed(title="🛡️ AutoMod", color=X_RED,
                      timestamp=datetime.now(timezone.utc))
    e.add_field(name="👤 Membre", value=f"{message.author.mention} (`{message.author.id}`)", inline=True)
    e.add_field(name="📺 Salon", value=message.channel.mention, inline=True)
    e.add_field(name="⚙️ Action", value=f"`{action}`", inline=True)
    e.add_field(name="📝 Motif", value=motif, inline=False)
    if message.content:
        e.add_field(name="💬 Message", value=f"```{message.content[:900]}```", inline=False)
    await send_log(guild, "automod", e)


async def automod_check(message):
    if not message.guild or message.author.bot:
        return False
    c = xget(message.guild.id, "automod")
    if not c.get("enabled"):
        return False
    if is_staff(message.author):
        return False
    if message.channel.id in [int(x) for x in c.get("ignored_channels", [])]:
        return False
    ign_roles = {int(x) for x in c.get("ignored_roles", [])}
    if ign_roles and any(r.id in ign_roles for r in getattr(message.author, "roles", [])):
        return False

    content = message.content or ""
    low = content.lower()

    for w in c.get("badwords", []):
        if w and w in low:
            await automod_punish(message, c.get("badword_action", "delete"), f"Mot interdit : ||{w}||")
            return True

    if c.get("anti_invite") and INVITE_RE.search(content):
        await automod_punish(message, c.get("invite_action", "delete"), "Invitation Discord (pub)")
        return True

    if c.get("anti_zalgo") and ZALGO_RE.search(content):
        await automod_punish(message, "delete", "Texte zalgo / caracteres deformes")
        return True

    if c.get("anti_spoiler") and content.count("||") >= 8:
        await automod_punish(message, "delete", "Spam de spoilers")
        return True

    ml = int(c.get("max_lines") or 0)
    if ml and content.count("\n") + 1 > ml:
        await automod_punish(message, "delete", f"Plus de {ml} lignes")
        return True

    ma = int(c.get("max_attachments") or 0)
    if ma and len(message.attachments) > ma:
        await automod_punish(message, "delete", f"Plus de {ma} fichier(s)")
        return True

    return False


def register_automod(bot):

    @bot.command(name="automod", aliases=["automodpro", "filtre", "filtres", "automodpanel"])
    async def automod_cmd(ctx):
        if not is_admin(ctx.author):
            return await ctx.send(embed=err("Permission administrateur requise."))
        await ctx.send(embed=am_embed(ctx.guild), view=AutomodView(ctx))

    @bot.command(name="badword", aliases=["badwords", "motinterdit", "motsinterdits", "blacklistword"])
    async def badword_cmd(ctx, action: str = None, *, mot: str = None):
        if not is_staff(ctx.author):
            return await ctx.send(embed=err("Tu n'as pas la permission."))
        c = xget(ctx.guild.id, "automod")
        mots = c.get("badwords", [])
        action = (action or "list").lower()
        if action in ("add", "ajouter", "+"):
            if not mot:
                return await ctx.send(embed=err("Usage : `+badword add <mot>`"))
            for m in [x.strip().lower() for x in mot.split(",") if x.strip()]:
                if m not in mots:
                    mots.append(m)
            c["badwords"] = mots[:200]
            xset(ctx.guild.id, "automod", c)
            return await ctx.send(embed=ok(f"Ajoute. **{len(c['badwords'])}** mot(s) filtre(s)."))
        if action in ("del", "remove", "supprimer", "-"):
            if not mot:
                return await ctx.send(embed=err("Usage : `+badword del <mot>`"))
            m = mot.strip().lower()
            if m not in mots:
                return await ctx.send(embed=err("Ce mot n'est pas dans la liste."))
            mots.remove(m)
            c["badwords"] = mots
            xset(ctx.guild.id, "automod", c)
            return await ctx.send(embed=ok(f"**{m}** retire de la liste."))
        if action in ("clear", "reset", "vider"):
            c["badwords"] = []
            xset(ctx.guild.id, "automod", c)
            return await ctx.send(embed=ok("Liste videe."))
        if not mots:
            return await ctx.send(embed=warn("Aucun mot interdit. `+badword add <mot>`"))
        await ctx.send(embed=discord.Embed(
            title=f"🤬 Mots interdits ({len(mots)})",
            description=" ".join(f"`{m}`" for m in mots[:100]),
            color=X_BLUE))

    @bot.command(name="antiinvite", aliases=["antipub", "antiinvitation", "antiads"])
    async def antiinvite_cmd(ctx, etat: str = None):
        if not is_admin(ctx.author):
            return await ctx.send(embed=err("Permission administrateur requise."))
        c = xget(ctx.guild.id, "automod")
        if etat in ("on", "activer", "true"):
            c["anti_invite"] = True
        elif etat in ("off", "desactiver", "false"):
            c["anti_invite"] = False
        else:
            c["anti_invite"] = not c.get("anti_invite")
        xset(ctx.guild.id, "automod", c)
        await ctx.send(embed=ok(f"Anti-pub **{'active' if c['anti_invite'] else 'desactive'}**."))

    @bot.command(name="automodignore", aliases=["automodexception", "amignore"])
    async def automodignore_cmd(ctx, salon: discord.TextChannel = None):
        if not is_admin(ctx.author):
            return await ctx.send(embed=err("Permission administrateur requise."))
        salon = salon or ctx.channel
        c = xget(ctx.guild.id, "automod")
        ign = [int(x) for x in c.get("ignored_channels", [])]
        if salon.id in ign:
            ign.remove(salon.id)
            txt = f"{salon.mention} n'est plus ignore."
        else:
            ign.append(salon.id)
            txt = f"{salon.mention} est desormais ignore par l'AutoMod."
        c["ignored_channels"] = ign
        xset(ctx.guild.id, "automod", c)
        await ctx.send(embed=ok(txt))

    @bot.command(name="automodlogs", aliases=["amlogs", "logsautomod"])
    async def automodlogs_cmd(ctx, salon: discord.TextChannel = None):
        if not is_admin(ctx.author):
            return await ctx.send(embed=err("Permission administrateur requise."))
        c = xget(ctx.guild.id, "automod")
        c["log_channel"] = salon.id if salon else None
        xset(ctx.guild.id, "automod", c)
        await ctx.send(embed=ok(f"Logs AutoMod : {salon.mention if salon else 'desactives'}."))

    @bot.command(name="automodtest", aliases=["amtest", "testautomod"])
    async def automodtest_cmd(ctx, *, texte: str = None):
        if not is_staff(ctx.author):
            return await ctx.send(embed=err("Tu n'as pas la permission."))
        if not texte:
            return await ctx.send(embed=err("Usage : `+automodtest <texte>`"))
        c = xget(ctx.guild.id, "automod")
        low = texte.lower()
        hits = []
        for w in c.get("badwords", []):
            if w and w in low:
                hits.append(f"Mot interdit : ||{w}||")
        if c.get("anti_invite") and INVITE_RE.search(texte):
            hits.append("Invitation Discord")
        if c.get("anti_zalgo") and ZALGO_RE.search(texte):
            hits.append("Zalgo")
        ml = int(c.get("max_lines") or 0)
        if ml and texte.count("\n") + 1 > ml:
            hits.append(f"Plus de {ml} lignes")
        if hits:
            return await ctx.send(embed=warn("Ce message serait **bloque** :\n• " + "\n• ".join(hits)))
        await ctx.send(embed=ok("Ce message passerait les filtres."))


# ===========================================================================
# ===========================================================================
#   💡  CATEGORIE 3 — SUGGESTIONS
# ===========================================================================
# ===========================================================================

def sg_embed(guild):
    c = xget(guild.id, "suggestions")
    e = discord.Embed(
        title="💡 Systeme de suggestions",
        description="Les membres proposent leurs idees avec `+suggest`, le staff valide ou refuse "
                    "directement depuis les boutons de la suggestion.",
        color=X_CYAN)
    e.add_field(name="🔘 Statut", value="✅ Actif" if c.get("enabled") else "❌ Desactive", inline=True)
    e.add_field(name="📺 Salon des suggestions", value=chan_field(guild, c.get("channel_id")), inline=True)
    e.add_field(name="🗳️ Votes", value=f"{c.get('up_emoji','👍')} / {c.get('down_emoji','👎')}", inline=True)
    e.add_field(name="📋 Salon de logs", value=chan_field(guild, c.get("log_channel")), inline=True)
    e.add_field(name="🧵 Fil de discussion", value="✅" if c.get("threads") else "❌", inline=True)
    e.add_field(name="🕵️ Mode anonyme", value="✅" if c.get("anonymous") else "❌", inline=True)
    e.add_field(name="✂️ Longueur minimum", value=f"{c.get('min_length',10)} caracteres", inline=True)
    e.add_field(name="🧹 Supprimer la commande", value="✅" if c.get("auto_delete_cmd") else "❌", inline=True)
    e.add_field(name="🔢 Suggestions envoyees", value=str(c.get("counter", 0)), inline=True)
    e.add_field(name="⌨️ Commandes",
                value="`+suggest` `+approve` `+deny` `+suggestinfo` `+suggestreset`", inline=False)
    e.set_footer(text="ModeraBot • Suggestions")
    return e


class ModalSgSalons(discord.ui.Modal, title="📺 Salons des suggestions"):
    salon = discord.ui.TextInput(label="ID du salon des suggestions", max_length=25)
    logs = discord.ui.TextInput(label="ID du salon de logs (optionnel)", max_length=25, required=False)

    def __init__(self, gid):
        super().__init__()
        self.gid = gid
        c = xget(gid, "suggestions")
        self.salon.default = str(c.get("channel_id") or "")
        self.logs.default = str(c.get("log_channel") or "")

    async def on_submit(self, interaction: discord.Interaction):
        c = xget(self.gid, "suggestions")
        v = str(self.salon.value or "").strip()
        c["channel_id"] = int(v) if v.isdigit() else None
        v2 = str(self.logs.value or "").strip()
        c["log_channel"] = int(v2) if v2.isdigit() else None
        xset(self.gid, "suggestions", c)
        await interaction.response.edit_message(embed=sg_embed(interaction.guild))


class ModalSgVotes(discord.ui.Modal, title="🗳️ Emojis de vote"):
    up = discord.ui.TextInput(label="Emoji pour", max_length=32, placeholder="👍")
    down = discord.ui.TextInput(label="Emoji contre", max_length=32, placeholder="👎")
    mini = discord.ui.TextInput(label="Longueur minimum d'une suggestion", max_length=4, placeholder="10")

    def __init__(self, gid):
        super().__init__()
        self.gid = gid
        c = xget(gid, "suggestions")
        self.up.default = c.get("up_emoji", "👍")
        self.down.default = c.get("down_emoji", "👎")
        self.mini.default = str(c.get("min_length", 10))

    async def on_submit(self, interaction: discord.Interaction):
        c = xget(self.gid, "suggestions")
        c["up_emoji"] = str(self.up.value).strip() or "👍"
        c["down_emoji"] = str(self.down.value).strip() or "👎"
        try:
            c["min_length"] = max(1, int(str(self.mini.value).strip()))
        except Exception:
            pass
        xset(self.gid, "suggestions", c)
        await interaction.response.edit_message(embed=sg_embed(interaction.guild))


class SuggestionsView(discord.ui.View):
    def __init__(self, ctx):
        super().__init__(timeout=300)
        self.ctx = ctx

    async def interaction_check(self, interaction: discord.Interaction):
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message(embed=err("Ce panneau n'est pas pour toi."), ephemeral=True)
            return False
        return True

    @discord.ui.select(placeholder="⚙️ Configurer les suggestions...", options=[
        discord.SelectOption(label="Salon des suggestions & logs", emoji="📺", value="salons"),
        discord.SelectOption(label="Emojis de vote & longueur mini", emoji="🗳️", value="votes"),
    ])
    async def menu(self, interaction: discord.Interaction, select: discord.ui.Select):
        if select.values[0] == "salons":
            return await interaction.response.send_modal(ModalSgSalons(interaction.guild.id))
        return await interaction.response.send_modal(ModalSgVotes(interaction.guild.id))

    @discord.ui.button(label="Activer / Desactiver", emoji="🔘", style=discord.ButtonStyle.success, row=1)
    async def toggle(self, interaction: discord.Interaction, button: discord.ui.Button):
        c = xget(interaction.guild.id, "suggestions")
        c["enabled"] = not c.get("enabled")
        xset(interaction.guild.id, "suggestions", c)
        await interaction.response.edit_message(embed=sg_embed(interaction.guild), view=self)

    @discord.ui.button(label="Fils on/off", emoji="🧵", style=discord.ButtonStyle.secondary, row=1)
    async def th(self, interaction: discord.Interaction, button: discord.ui.Button):
        c = xget(interaction.guild.id, "suggestions")
        c["threads"] = not c.get("threads")
        xset(interaction.guild.id, "suggestions", c)
        await interaction.response.edit_message(embed=sg_embed(interaction.guild), view=self)

    @discord.ui.button(label="Anonyme on/off", emoji="🕵️", style=discord.ButtonStyle.secondary, row=1)
    async def anon(self, interaction: discord.Interaction, button: discord.ui.Button):
        c = xget(interaction.guild.id, "suggestions")
        c["anonymous"] = not c.get("anonymous")
        xset(interaction.guild.id, "suggestions", c)
        await interaction.response.edit_message(embed=sg_embed(interaction.guild), view=self)

    @discord.ui.button(label="Fermer", emoji="✖️", style=discord.ButtonStyle.secondary, row=1)
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(view=None)
        self.stop()


class SuggestionVoteView(discord.ui.View):
    """Vue persistante attachee a chaque suggestion publiee."""

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Approuver", emoji="✅", style=discord.ButtonStyle.success,
                       custom_id="mb_sg_approve")
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._decide(interaction, True)

    @discord.ui.button(label="Refuser", emoji="❌", style=discord.ButtonStyle.danger,
                       custom_id="mb_sg_deny")
    async def deny(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._decide(interaction, False)

    async def _decide(self, interaction: discord.Interaction, approved: bool):
        if not is_staff(interaction.user):
            return await interaction.response.send_message(
                embed=err("Reserve au staff."), ephemeral=True)
        msg = interaction.message
        e = msg.embeds[0] if msg.embeds else discord.Embed()
        e.color = X_GREEN if approved else X_RED
        statut = "✅ Approuvee" if approved else "❌ Refusee"
        champs = [f for f in e.fields if f.name != "📌 Statut"]
        e.clear_fields()
        for f in champs:
            e.add_field(name=f.name, value=f.value, inline=f.inline)
        e.add_field(name="📌 Statut", value=f"{statut} par {interaction.user.mention}", inline=False)
        await interaction.response.edit_message(embed=e, view=None)
        await send_log(interaction.guild, "suggestions", discord.Embed(
            title="💡 Suggestion traitee", color=e.color,
            description=f"{statut} par {interaction.user.mention}\n[Voir]({msg.jump_url})"))


def register_suggestions(bot):

    @bot.command(name="suggestions", aliases=["suggestionconfig", "suggestsetup", "configsuggestion"])
    async def suggestions_cmd(ctx):
        if not is_admin(ctx.author):
            return await ctx.send(embed=err("Permission administrateur requise."))
        await ctx.send(embed=sg_embed(ctx.guild), view=SuggestionsView(ctx))

    @bot.command(name="suggest", aliases=["suggestion", "idee", "proposer"])
    async def suggest_cmd(ctx, *, texte: str = None):
        c = xget(ctx.guild.id, "suggestions")
        if not c.get("enabled"):
            return await ctx.send(embed=err("Les suggestions sont desactivees (`+suggestions`)."))
        if not texte or len(texte) < int(c.get("min_length", 10)):
            return await ctx.send(embed=err(
                f"Ta suggestion doit faire au moins **{c.get('min_length',10)}** caracteres."))
        ch = ctx.guild.get_channel(int(c["channel_id"])) if c.get("channel_id") else None
        if not ch:
            return await ctx.send(embed=err("Aucun salon de suggestions configure."))

        c["counter"] = int(c.get("counter", 0)) + 1
        num = c["counter"]
        xset(ctx.guild.id, "suggestions", c)

        e = discord.Embed(title=f"💡 Suggestion #{num}", description=texte, color=X_CYAN,
                          timestamp=datetime.now(timezone.utc))
        if not c.get("anonymous"):
            e.set_author(name=str(ctx.author), icon_url=ctx.author.display_avatar.url)
            e.add_field(name="👤 Auteur", value=ctx.author.mention, inline=True)
        else:
            e.add_field(name="👤 Auteur", value="Anonyme", inline=True)
        e.add_field(name="📌 Statut", value="🕓 En attente", inline=True)
        e.set_footer(text=f"{ctx.guild.name} • Vote ci-dessous")

        msg = await ch.send(embed=e, view=SuggestionVoteView())
        for emo in (c.get("up_emoji", "👍"), c.get("down_emoji", "👎")):
            try:
                await msg.add_reaction(emo)
            except Exception:
                pass
        if c.get("threads"):
            try:
                await msg.create_thread(name=f"Suggestion #{num}", auto_archive_duration=1440)
            except Exception:
                pass
        if c.get("auto_delete_cmd"):
            try:
                await ctx.message.delete()
            except Exception:
                pass
        await ctx.send(embed=ok(f"Suggestion **#{num}** envoyee dans {ch.mention}."), delete_after=8)

    @bot.command(name="approve", aliases=["approuver", "accepter", "valider"])
    async def approve_cmd(ctx, message_id: int = None, *, raison: str = "Aucune raison"):
        await _decide_cmd(ctx, message_id, raison, True)

    @bot.command(name="deny", aliases=["refuser", "rejeter", "decline"])
    async def deny_cmd(ctx, message_id: int = None, *, raison: str = "Aucune raison"):
        await _decide_cmd(ctx, message_id, raison, False)

    async def _decide_cmd(ctx, message_id, raison, approved):
        if not is_staff(ctx.author):
            return await ctx.send(embed=err("Reserve au staff."))
        c = xget(ctx.guild.id, "suggestions")
        ch = ctx.guild.get_channel(int(c["channel_id"])) if c.get("channel_id") else None
        if not ch or not message_id:
            return await ctx.send(embed=err("Usage : `+approve <id du message> [raison]`"))
        try:
            msg = await ch.fetch_message(message_id)
        except Exception:
            return await ctx.send(embed=err("Suggestion introuvable dans le salon configure."))
        e = msg.embeds[0] if msg.embeds else discord.Embed(description="—")
        e.color = X_GREEN if approved else X_RED
        champs = [f for f in e.fields if f.name != "📌 Statut"]
        e.clear_fields()
        for f in champs:
            e.add_field(name=f.name, value=f.value, inline=f.inline)
        e.add_field(name="📌 Statut",
                    value=f"{'✅ Approuvee' if approved else '❌ Refusee'} par {ctx.author.mention}\n"
                          f"📝 {raison}", inline=False)
        await msg.edit(embed=e, view=None)
        await ctx.send(embed=ok("Suggestion mise a jour."))

    @bot.command(name="suggestinfo", aliases=["infosuggestion", "suggestionstats"])
    async def suggestinfo_cmd(ctx):
        c = xget(ctx.guild.id, "suggestions")
        e = discord.Embed(title="💡 Suggestions — infos", color=X_CYAN)
        e.add_field(name="Statut", value="✅ Actif" if c.get("enabled") else "❌ Desactive", inline=True)
        e.add_field(name="Salon", value=chan_field(ctx.guild, c.get("channel_id")), inline=True)
        e.add_field(name="Total envoye", value=str(c.get("counter", 0)), inline=True)
        await ctx.send(embed=e)

    @bot.command(name="suggestreset", aliases=["resetsuggestions", "resetsuggest"])
    async def suggestreset_cmd(ctx):
        if not is_admin(ctx.author):
            return await ctx.send(embed=err("Permission administrateur requise."))
        c = xget(ctx.guild.id, "suggestions")
        c["counter"] = 0
        xset(ctx.guild.id, "suggestions", c)
        await ctx.send(embed=ok("Compteur de suggestions remis a zero."))


# ===========================================================================
# ===========================================================================
#   📊  CATEGORIE 4 — SONDAGES
# ===========================================================================
# ===========================================================================

POLLS = {}   # message_id -> {"options": [...], "votes": {uid: idx}, "end": ts, ...}


def poll_embed(guild, rec):
    c = xget(guild.id, "polls")
    total = len(rec["votes"])
    lines = []
    for i, opt in enumerate(rec["options"]):
        n = sum(1 for v in rec["votes"].values() if v == i)
        pct = int(n / total * 100) if total else 0
        barre = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
        lines.append(f"**{i+1}. {opt}**\n`{barre}` {pct}% · {n} vote(s)")
    e = discord.Embed(title=f"📊 {rec['question']}", description="\n\n".join(lines),
                      color=color_of(c.get("color", "#5865F2")))
    e.add_field(name="👥 Participants", value=str(total), inline=True)
    if rec.get("end"):
        e.add_field(name="⏳ Fin", value=f"<t:{int(rec['end'])}:R>", inline=True)
    e.set_footer(text=f"Lance par {rec.get('author_name','?')}")
    return e


class PollVoteView(discord.ui.View):
    def __init__(self, mid, options):
        super().__init__(timeout=None)
        self.mid = mid
        opts = [discord.SelectOption(label=o[:100], value=str(i)) for i, o in enumerate(options[:25])]
        self.add_item(PollSelect(opts))

    @discord.ui.button(label="Retirer mon vote", emoji="🗑️", style=discord.ButtonStyle.secondary, row=1)
    async def unvote(self, interaction: discord.Interaction, button: discord.ui.Button):
        rec = POLLS.get(interaction.message.id)
        if not rec:
            return await interaction.response.send_message(embed=err("Sondage termine."), ephemeral=True)
        rec["votes"].pop(str(interaction.user.id), None)
        await interaction.response.edit_message(embed=poll_embed(interaction.guild, rec), view=self)

    @discord.ui.button(label="Terminer", emoji="🛑", style=discord.ButtonStyle.danger, row=1)
    async def stopit(self, interaction: discord.Interaction, button: discord.ui.Button):
        rec = POLLS.get(interaction.message.id)
        if not rec:
            return await interaction.response.send_message(embed=err("Sondage deja termine."), ephemeral=True)
        if not is_staff(interaction.user) and interaction.user.id != rec.get("author_id"):
            return await interaction.response.send_message(embed=err("Reserve au staff ou a l'auteur."), ephemeral=True)
        e = poll_embed(interaction.guild, rec)
        e.title = "🛑 " + e.title[2:]
        e.set_footer(text="Sondage termine")
        POLLS.pop(interaction.message.id, None)
        await interaction.response.edit_message(embed=e, view=None)


class PollSelect(discord.ui.Select):
    def __init__(self, options):
        super().__init__(placeholder="🗳️ Vote ici...", options=options)

    async def callback(self, interaction: discord.Interaction):
        rec = POLLS.get(interaction.message.id)
        if not rec:
            return await interaction.response.send_message(embed=err("Sondage termine."), ephemeral=True)
        rec["votes"][str(interaction.user.id)] = int(self.values[0])
        await interaction.response.edit_message(embed=poll_embed(interaction.guild, rec),
                                                view=self.view)


def poll_cfg_embed(guild):
    c = xget(guild.id, "polls")
    e = discord.Embed(title="📊 Sondages",
                      description="Cree des sondages avec barres de progression en direct : `+pollpro`.",
                      color=color_of(c.get("color", "#5865F2")))
    e.add_field(name="🔘 Statut", value="✅ Actif" if c.get("enabled") else "❌ Desactive", inline=True)
    e.add_field(name="📺 Salon par defaut", value=chan_field(guild, c.get("channel_id")), inline=True)
    e.add_field(name="⏳ Duree par defaut", value=c.get("default_duration", "1h"), inline=True)
    e.add_field(name="🎨 Couleur", value=c.get("color", "#5865F2"), inline=True)
    e.add_field(name="🔔 Role ping", value=role_field(c.get("ping_role")), inline=True)
    e.add_field(name="👁️ Afficher les votants", value="✅" if c.get("show_voters") else "❌", inline=True)
    e.add_field(name="⌨️ Commandes",
                value="`+pollpro` `+quickpoll` `+endpoll` `+pollresults`", inline=False)
    e.set_footer(text="ModeraBot • Sondages")
    return e


class ModalPollCfg(discord.ui.Modal, title="📊 Reglages des sondages"):
    salon = discord.ui.TextInput(label="ID du salon par defaut", required=False, max_length=25)
    duree = discord.ui.TextInput(label="Duree par defaut (ex: 1h, 30m)", max_length=10, placeholder="1h")
    couleur = discord.ui.TextInput(label="Couleur (hex)", max_length=7, placeholder="#5865F2")
    ping = discord.ui.TextInput(label="ID du role a ping (optionnel)", required=False, max_length=25)

    def __init__(self, gid):
        super().__init__()
        self.gid = gid
        c = xget(gid, "polls")
        self.salon.default = str(c.get("channel_id") or "")
        self.duree.default = c.get("default_duration", "1h")
        self.couleur.default = c.get("color", "#5865F2")
        self.ping.default = str(c.get("ping_role") or "")

    async def on_submit(self, interaction: discord.Interaction):
        c = xget(self.gid, "polls")
        v = str(self.salon.value or "").strip()
        c["channel_id"] = int(v) if v.isdigit() else None
        c["default_duration"] = str(self.duree.value).strip() or "1h"
        c["color"] = str(self.couleur.value).strip() or "#5865F2"
        p = str(self.ping.value or "").strip()
        c["ping_role"] = int(p) if p.isdigit() else None
        xset(self.gid, "polls", c)
        await interaction.response.edit_message(embed=poll_cfg_embed(interaction.guild))


class PollConfigView(discord.ui.View):
    def __init__(self, ctx):
        super().__init__(timeout=300)
        self.ctx = ctx

    async def interaction_check(self, interaction: discord.Interaction):
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message(embed=err("Ce panneau n'est pas pour toi."), ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Reglages", emoji="⚙️", style=discord.ButtonStyle.primary)
    async def cfg(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ModalPollCfg(interaction.guild.id))

    @discord.ui.button(label="Activer / Desactiver", emoji="🔘", style=discord.ButtonStyle.success)
    async def toggle(self, interaction: discord.Interaction, button: discord.ui.Button):
        c = xget(interaction.guild.id, "polls")
        c["enabled"] = not c.get("enabled")
        xset(interaction.guild.id, "polls", c)
        await interaction.response.edit_message(embed=poll_cfg_embed(interaction.guild), view=self)

    @discord.ui.button(label="Votants visibles", emoji="👁️", style=discord.ButtonStyle.secondary)
    async def voters(self, interaction: discord.Interaction, button: discord.ui.Button):
        c = xget(interaction.guild.id, "polls")
        c["show_voters"] = not c.get("show_voters")
        xset(interaction.guild.id, "polls", c)
        await interaction.response.edit_message(embed=poll_cfg_embed(interaction.guild), view=self)

    @discord.ui.button(label="Fermer", emoji="✖️", style=discord.ButtonStyle.secondary)
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(view=None)
        self.stop()


def register_polls(bot):

    @bot.command(name="pollconfig", aliases=["sondageconfig", "pollsetup", "sondages"])
    async def pollconfig_cmd(ctx):
        if not is_admin(ctx.author):
            return await ctx.send(embed=err("Permission administrateur requise."))
        await ctx.send(embed=poll_cfg_embed(ctx.guild), view=PollConfigView(ctx))

    @bot.command(name="pollpro", aliases=["sondagepro", "pollavance", "spoll"])
    async def poll_cmd(ctx, *, texte: str = None):
        c = xget(ctx.guild.id, "polls")
        if not c.get("enabled"):
            return await ctx.send(embed=err("Les sondages sont desactives (`+pollconfig`)."))
        if not is_staff(ctx.author):
            return await ctx.send(embed=err("Reserve au staff."))
        if not texte or "|" not in texte:
            return await ctx.send(embed=err(
                "Usage : `+pollpro Question | Option 1 | Option 2 | ...`"))
        parts = [p.strip() for p in texte.split("|") if p.strip()]
        question, options = parts[0], parts[1:]
        if len(options) < 2:
            return await ctx.send(embed=err("Il faut au moins 2 options."))
        ch = ctx.guild.get_channel(int(c["channel_id"])) if c.get("channel_id") else ctx.channel
        rec = {"question": question, "options": options[:25], "votes": {},
               "author_id": ctx.author.id, "author_name": str(ctx.author),
               "end": time.time() + parse_duration(c.get("default_duration", "1h"), 3600)}
        content = f"<@&{c['ping_role']}>" if c.get("ping_role") else None
        msg = await ch.send(content=content, embed=poll_embed(ctx.guild, rec),
                            view=PollVoteView(0, rec["options"]))
        POLLS[msg.id] = rec
        if ch.id != ctx.channel.id:
            await ctx.send(embed=ok(f"Sondage publie dans {ch.mention}."))

    @bot.command(name="quickpoll", aliases=["qpoll", "sondagerapide"])
    async def quickpoll_cmd(ctx, *, question: str = None):
        if not question:
            return await ctx.send(embed=err("Usage : `+quickpoll <question>`"))
        e = discord.Embed(title="📊 Sondage rapide", description=question, color=X_BLUE)
        e.set_footer(text=f"Demande par {ctx.author}")
        msg = await ctx.send(embed=e)
        for emo in ("👍", "👎", "🤷"):
            try:
                await msg.add_reaction(emo)
            except Exception:
                pass

    @bot.command(name="endpoll", aliases=["finsondage", "stoppoll"])
    async def endpoll_cmd(ctx, message_id: int = None):
        if not is_staff(ctx.author):
            return await ctx.send(embed=err("Reserve au staff."))
        if not message_id or message_id not in POLLS:
            return await ctx.send(embed=err("Usage : `+endpoll <id du message>` (sondage actif requis)."))
        rec = POLLS.pop(message_id)
        try:
            msg = await ctx.channel.fetch_message(message_id)
            e = poll_embed(ctx.guild, rec)
            e.set_footer(text="Sondage termine")
            await msg.edit(embed=e, view=None)
        except Exception:
            pass
        await ctx.send(embed=ok("Sondage termine."))

    @bot.command(name="pollresults", aliases=["resultats", "resultatsondage"])
    async def pollresults_cmd(ctx, message_id: int = None):
        rec = POLLS.get(message_id) if message_id else None
        if not rec:
            return await ctx.send(embed=err("Aucun sondage actif avec cet ID."))
        await ctx.send(embed=poll_embed(ctx.guild, rec))


# ===========================================================================
# ===========================================================================
#   🔒  CATEGORIE 5 — PROTECTION & LOCKDOWN
# ===========================================================================
# ===========================================================================

def gd_embed(guild):
    c = xget(guild.id, "guard")
    e = discord.Embed(
        title="🔒 Protection & Lockdown",
        description="Verrouillage express du serveur, mode raid et filtre de comptes trop recents.\n"
                    "A utiliser en complement de `+antiraid` pendant une attaque.",
        color=X_RED if (c.get("panic") or c.get("raidmode")) else X_BLUE)
    e.add_field(name="🚨 Mode raid", value="🔴 ACTIF" if c.get("raidmode") else "🟢 Inactif", inline=True)
    e.add_field(name="🆘 Mode panique", value="🔴 ACTIF" if c.get("panic") else "🟢 Inactif", inline=True)
    e.add_field(name="🔒 Salons verrouilles", value=str(len(c.get("locked_channels", []))), inline=True)
    e.add_field(name="👶 Filtre comptes recents",
                value=(f"✅ < {c.get('agegate_days',7)} j → `{c.get('agegate_action','kick')}`"
                       if c.get("agegate") else "❌ Desactive"), inline=False)
    e.add_field(name="🐌 Slowmode automatique (mode raid)",
                value=f"{c.get('auto_slowmode',0)}s" if c.get("auto_slowmode") else "❌", inline=True)
    e.add_field(name="📋 Salon de logs", value=chan_field(guild, c.get("log_channel")), inline=True)
    imm = c.get("immune_roles", [])
    e.add_field(name="🛡️ Roles immunises",
                value=(" ".join(f"<@&{i}>" for i in imm[:8]) if imm else "Aucun"), inline=False)
    e.add_field(name="⌨️ Commandes",
                value="`+lock` `+unlock` `+lockall` `+unlockall` `+slowmode` `+panic` `+raidmode` `+agegate`",
                inline=False)
    e.set_footer(text="ModeraBot • Protection")
    return e


class ModalGdMessages(discord.ui.Modal, title="💬 Messages de verrouillage"):
    lock = discord.ui.TextInput(label="Message de verrouillage",
                               style=discord.TextStyle.paragraph, max_length=300, required=False)
    unlock = discord.ui.TextInput(label="Message de deverrouillage",
                                  style=discord.TextStyle.paragraph, max_length=300, required=False)
    logs = discord.ui.TextInput(label="ID du salon de logs", required=False, max_length=25)

    def __init__(self, gid):
        super().__init__()
        self.gid = gid
        c = xget(gid, "guard")
        self.lock.default = c.get("lock_message", "")
        self.unlock.default = c.get("unlock_message", "")
        self.logs.default = str(c.get("log_channel") or "")

    async def on_submit(self, interaction: discord.Interaction):
        c = xget(self.gid, "guard")
        c["lock_message"] = str(self.lock.value or "").strip()
        c["unlock_message"] = str(self.unlock.value or "").strip()
        v = str(self.logs.value or "").strip()
        c["log_channel"] = int(v) if v.isdigit() else None
        xset(self.gid, "guard", c)
        await interaction.response.edit_message(embed=gd_embed(interaction.guild))


class ModalGdAgegate(discord.ui.Modal, title="👶 Filtre de comptes recents"):
    jours = discord.ui.TextInput(label="Age minimum du compte (jours)", max_length=4, placeholder="7")
    action = discord.ui.TextInput(label="Action : kick / ban / log", max_length=6, placeholder="kick")
    slow = discord.ui.TextInput(label="Slowmode auto en mode raid (secondes)",
                                max_length=5, required=False, placeholder="10")

    def __init__(self, gid):
        super().__init__()
        self.gid = gid
        c = xget(gid, "guard")
        self.jours.default = str(c.get("agegate_days", 7))
        self.action.default = c.get("agegate_action", "kick")
        self.slow.default = str(c.get("auto_slowmode", 0))

    async def on_submit(self, interaction: discord.Interaction):
        c = xget(self.gid, "guard")
        try:
            c["agegate_days"] = max(0, int(str(self.jours.value).strip()))
            c["auto_slowmode"] = max(0, min(21600, int(str(self.slow.value).strip() or 0)))
        except Exception:
            return await interaction.response.send_message(embed=err("Valeurs invalides."), ephemeral=True)
        a = str(self.action.value).strip().lower()
        c["agegate_action"] = a if a in ("kick", "ban", "log") else "kick"
        c["agegate"] = True
        xset(self.gid, "guard", c)
        await interaction.response.edit_message(embed=gd_embed(interaction.guild))


class ModalGdImmune(discord.ui.Modal, title="🛡️ Roles immunises"):
    roles = discord.ui.TextInput(label="IDs de roles (virgules)", required=False, max_length=500)

    def __init__(self, gid):
        super().__init__()
        self.gid = gid
        self.roles.default = ", ".join(str(i) for i in xget(gid, "guard").get("immune_roles", []))

    async def on_submit(self, interaction: discord.Interaction):
        c = xget(self.gid, "guard")
        c["immune_roles"] = [int(x) for x in re.findall(r"\d{5,25}", str(self.roles.value or ""))][:50]
        xset(self.gid, "guard", c)
        await interaction.response.edit_message(embed=gd_embed(interaction.guild))


async def do_lock(guild, channel, lock=True, reason="Lockdown"):
    role = guild.default_role
    ow = channel.overwrites_for(role)
    ow.send_messages = False if lock else None
    try:
        await channel.set_permissions(role, overwrite=ow, reason=reason)
        return True
    except Exception:
        return False


class GuardView(discord.ui.View):
    def __init__(self, ctx):
        super().__init__(timeout=300)
        self.ctx = ctx

    async def interaction_check(self, interaction: discord.Interaction):
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message(embed=err("Ce panneau n'est pas pour toi."), ephemeral=True)
            return False
        return True

    @discord.ui.select(placeholder="⚙️ Configurer la protection...", options=[
        discord.SelectOption(label="Messages de verrouillage & logs", emoji="💬", value="msg"),
        discord.SelectOption(label="Filtre de comptes recents", emoji="👶", value="age"),
        discord.SelectOption(label="Roles immunises", emoji="🛡️", value="immune"),
    ])
    async def menu(self, interaction: discord.Interaction, select: discord.ui.Select):
        v = select.values[0]
        gid = interaction.guild.id
        if v == "msg":
            return await interaction.response.send_modal(ModalGdMessages(gid))
        if v == "age":
            return await interaction.response.send_modal(ModalGdAgegate(gid))
        return await interaction.response.send_modal(ModalGdImmune(gid))

    @discord.ui.button(label="Mode raid", emoji="🚨", style=discord.ButtonStyle.danger, row=1)
    async def raid(self, interaction: discord.Interaction, button: discord.ui.Button):
        c = xget(interaction.guild.id, "guard")
        c["raidmode"] = not c.get("raidmode")
        xset(interaction.guild.id, "guard", c)
        if c["raidmode"] and c.get("auto_slowmode"):
            for ch in interaction.guild.text_channels:
                try:
                    await ch.edit(slowmode_delay=int(c["auto_slowmode"]))
                except Exception:
                    pass
        await interaction.response.edit_message(embed=gd_embed(interaction.guild), view=self)

    @discord.ui.button(label="Verrouiller tout", emoji="🔒", style=discord.ButtonStyle.danger, row=1)
    async def lockall(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        c = xget(interaction.guild.id, "guard")
        locked = []
        for ch in interaction.guild.text_channels:
            if await do_lock(interaction.guild, ch, True, "Lockdown panneau"):
                locked.append(ch.id)
        c["locked_channels"] = locked
        c["panic"] = True
        xset(interaction.guild.id, "guard", c)
        await interaction.edit_original_response(embed=gd_embed(interaction.guild), view=self)

    @discord.ui.button(label="Deverrouiller tout", emoji="🔓", style=discord.ButtonStyle.success, row=1)
    async def unlockall(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        c = xget(interaction.guild.id, "guard")
        for ch in interaction.guild.text_channels:
            await do_lock(interaction.guild, ch, False, "Deverrouillage panneau")
        c["locked_channels"] = []
        c["panic"] = False
        xset(interaction.guild.id, "guard", c)
        await interaction.edit_original_response(embed=gd_embed(interaction.guild), view=self)

    @discord.ui.button(label="Filtre comptes on/off", emoji="👶", style=discord.ButtonStyle.secondary, row=2)
    async def age(self, interaction: discord.Interaction, button: discord.ui.Button):
        c = xget(interaction.guild.id, "guard")
        c["agegate"] = not c.get("agegate")
        xset(interaction.guild.id, "guard", c)
        await interaction.response.edit_message(embed=gd_embed(interaction.guild), view=self)

    @discord.ui.button(label="Fermer", emoji="✖️", style=discord.ButtonStyle.secondary, row=2)
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(view=None)
        self.stop()


def register_guard(bot):

    @bot.command(name="guard", aliases=["lockdown", "panelguard", "securiteplus"])
    async def guard_cmd(ctx):
        if not is_admin(ctx.author):
            return await ctx.send(embed=err("Permission administrateur requise."))
        await ctx.send(embed=gd_embed(ctx.guild), view=GuardView(ctx))

    @bot.command(name="lock", aliases=["verrouiller", "fermer"])
    async def lock_cmd(ctx, salon: discord.TextChannel = None, *, raison: str = "Aucune raison"):
        if not is_staff(ctx.author):
            return await ctx.send(embed=err("Tu n'as pas la permission."))
        salon = salon or ctx.channel
        c = xget(ctx.guild.id, "guard")
        if not await do_lock(ctx.guild, salon, True, raison):
            return await ctx.send(embed=err("Impossible de verrouiller ce salon."))
        locked = [int(x) for x in c.get("locked_channels", [])]
        if salon.id not in locked:
            locked.append(salon.id)
        c["locked_channels"] = locked
        xset(ctx.guild.id, "guard", c)
        await salon.send(embed=discord.Embed(
            description=c.get("lock_message") or "🔒 Ce salon a ete verrouille.", color=X_RED))
        if salon.id != ctx.channel.id:
            await ctx.send(embed=ok(f"{salon.mention} verrouille."))
        await send_log(ctx.guild, "guard", discord.Embed(
            title="🔒 Salon verrouille", color=X_RED,
            description=f"{salon.mention} par {ctx.author.mention}\n📝 {raison}"))

    @bot.command(name="unlock", aliases=["deverrouiller", "ouvrir"])
    async def unlock_cmd(ctx, salon: discord.TextChannel = None):
        if not is_staff(ctx.author):
            return await ctx.send(embed=err("Tu n'as pas la permission."))
        salon = salon or ctx.channel
        c = xget(ctx.guild.id, "guard")
        if not await do_lock(ctx.guild, salon, False, "Deverrouillage"):
            return await ctx.send(embed=err("Impossible de deverrouiller ce salon."))
        c["locked_channels"] = [int(x) for x in c.get("locked_channels", []) if int(x) != salon.id]
        xset(ctx.guild.id, "guard", c)
        await salon.send(embed=discord.Embed(
            description=c.get("unlock_message") or "🔓 Ce salon est de nouveau ouvert.", color=X_GREEN))
        if salon.id != ctx.channel.id:
            await ctx.send(embed=ok(f"{salon.mention} deverrouille."))

    @bot.command(name="lockall", aliases=["verrouillertout", "lockserver"])
    async def lockall_cmd(ctx):
        if not is_admin(ctx.author):
            return await ctx.send(embed=err("Permission administrateur requise."))
        msg = await ctx.send(embed=warn("Verrouillage du serveur en cours…"))
        c = xget(ctx.guild.id, "guard")
        locked = []
        for ch in ctx.guild.text_channels:
            if await do_lock(ctx.guild, ch, True, f"Lockdown par {ctx.author}"):
                locked.append(ch.id)
        c["locked_channels"] = locked
        c["panic"] = True
        xset(ctx.guild.id, "guard", c)
        await msg.edit(embed=ok(f"**{len(locked)}** salon(s) verrouille(s)."))
        await send_log(ctx.guild, "guard", discord.Embed(
            title="🆘 LOCKDOWN TOTAL", color=X_RED,
            description=f"Declenche par {ctx.author.mention} — {len(locked)} salons"))

    @bot.command(name="unlockall", aliases=["deverrouillertout", "unlockserver"])
    async def unlockall_cmd(ctx):
        if not is_admin(ctx.author):
            return await ctx.send(embed=err("Permission administrateur requise."))
        msg = await ctx.send(embed=warn("Deverrouillage en cours…"))
        c = xget(ctx.guild.id, "guard")
        n = 0
        for ch in ctx.guild.text_channels:
            if await do_lock(ctx.guild, ch, False, f"Fin du lockdown par {ctx.author}"):
                n += 1
        c["locked_channels"] = []
        c["panic"] = False
        xset(ctx.guild.id, "guard", c)
        await msg.edit(embed=ok(f"**{n}** salon(s) deverrouille(s)."))

    @bot.command(name="slowmode", aliases=["slow", "lenteur", "ralentir"])
    async def slowmode_cmd(ctx, duree: str = None, salon: discord.TextChannel = None):
        if not is_staff(ctx.author):
            return await ctx.send(embed=err("Tu n'as pas la permission."))
        salon = salon or ctx.channel
        if duree is None:
            return await ctx.send(embed=err("Usage : `+slowmode 10s` · `+slowmode off`"))
        sec = 0 if duree in ("off", "0", "stop") else parse_duration(duree, 0)
        sec = max(0, min(21600, sec))
        try:
            await salon.edit(slowmode_delay=sec)
        except Exception:
            return await ctx.send(embed=err("Impossible de modifier ce salon."))
        await ctx.send(embed=ok(f"Slowmode de {salon.mention} : **{sec}s**" if sec
                                else f"Slowmode desactive dans {salon.mention}."))

    @bot.command(name="panic", aliases=["panique", "urgence", "sos"])
    async def panic_cmd(ctx):
        if not is_admin(ctx.author):
            return await ctx.send(embed=err("Permission administrateur requise."))
        c = xget(ctx.guild.id, "guard")
        c["panic"] = not c.get("panic")
        c["raidmode"] = c["panic"]
        xset(ctx.guild.id, "guard", c)
        if c["panic"]:
            n = 0
            for ch in ctx.guild.text_channels:
                if await do_lock(ctx.guild, ch, True, "Mode panique"):
                    n += 1
                try:
                    await ch.edit(slowmode_delay=max(10, int(c.get("auto_slowmode") or 10)))
                except Exception:
                    pass
            c["locked_channels"] = [ch.id for ch in ctx.guild.text_channels]
            xset(ctx.guild.id, "guard", c)
            return await ctx.send(embed=discord.Embed(
                title="🆘 MODE PANIQUE ACTIVE",
                description=f"**{n}** salons verrouilles, slowmode applique, mode raid actif.\n"
                            "Refais `+panic` pour tout remettre en place.",
                color=X_RED))
        for ch in ctx.guild.text_channels:
            await do_lock(ctx.guild, ch, False, "Fin du mode panique")
            try:
                await ch.edit(slowmode_delay=0)
            except Exception:
                pass
        c["locked_channels"] = []
        xset(ctx.guild.id, "guard", c)
        await ctx.send(embed=ok("Mode panique desactive, serveur rouvert."))

    @bot.command(name="raidmode", aliases=["moderaid", "antiraidmode"])
    async def raidmode_cmd(ctx, etat: str = None):
        if not is_admin(ctx.author):
            return await ctx.send(embed=err("Permission administrateur requise."))
        c = xget(ctx.guild.id, "guard")
        if etat in ("on", "activer"):
            c["raidmode"] = True
        elif etat in ("off", "desactiver"):
            c["raidmode"] = False
        else:
            c["raidmode"] = not c.get("raidmode")
        xset(ctx.guild.id, "guard", c)
        await ctx.send(embed=ok(f"Mode raid **{'active' if c['raidmode'] else 'desactive'}**."
                                + (" Les nouveaux comptes recents seront bloques." if c["raidmode"] else "")))

    @bot.command(name="agegate", aliases=["comptesrecents", "minage", "ageminimum"])
    async def agegate_cmd(ctx, jours: int = None, action: str = None):
        if not is_admin(ctx.author):
            return await ctx.send(embed=err("Permission administrateur requise."))
        c = xget(ctx.guild.id, "guard")
        if jours is None:
            c["agegate"] = not c.get("agegate")
            xset(ctx.guild.id, "guard", c)
            return await ctx.send(embed=ok(f"Filtre de comptes recents **{'active' if c['agegate'] else 'desactive'}**."))
        c["agegate"] = True
        c["agegate_days"] = max(0, jours)
        if action in ("kick", "ban", "log"):
            c["agegate_action"] = action
        xset(ctx.guild.id, "guard", c)
        await ctx.send(embed=ok(f"Comptes de moins de **{jours} jour(s)** → `{c['agegate_action']}`."))


# ===========================================================================
# ===========================================================================
#   📋  CATEGORIE 6 — CANDIDATURES (recrutement staff)
# ===========================================================================
# ===========================================================================

def ap_embed(guild):
    c = xget(guild.id, "apply")
    postes = c.get("postes", [])
    e = discord.Embed(
        title="📋 Candidatures / Recrutement",
        description="Un panneau public ou les membres postulent, un formulaire par poste, "
                    "et une validation staff en un clic — exactement comme les tickets.",
        color=color_of(c.get("couleur", "#5865F2")))
    e.add_field(name="🔘 Statut", value="✅ Actif" if c.get("enabled") else "❌ Desactive", inline=True)
    e.add_field(name="📺 Salon du panneau", value=chan_field(guild, c.get("panel_channel")), inline=True)
    e.add_field(name="📥 Salon de reception", value=chan_field(guild, c.get("review_channel")), inline=True)
    e.add_field(name="🎭 Role donne si accepte", value=role_field(c.get("accepted_role")), inline=True)
    e.add_field(name="⏳ Cooldown", value=f"{c.get('cooldown_hours',24)} h", inline=True)
    e.add_field(name="📋 Logs", value=chan_field(guild, c.get("log_channel")), inline=True)
    if postes:
        e.add_field(name=f"💼 Postes ({len(postes)})",
                    value="\n".join(f"{p.get('emoji','📄')} **{p['nom']}** — {len(p.get('questions',[]))} question(s)"
                                    for p in postes[:10]), inline=False)
    else:
        e.add_field(name="💼 Postes", value="❌ Aucun poste. Ajoute-en un via le menu.", inline=False)
    e.add_field(name="⌨️ Commandes",
                value="`+apply` `+applysend` `+applyadd` `+applydel` `+applylist`", inline=False)
    e.set_footer(text="ModeraBot • Candidatures")
    return e


class ModalApPanel(discord.ui.Modal, title="🖼️ Apparence du panneau"):
    titre = discord.ui.TextInput(label="Titre", max_length=100)
    desc = discord.ui.TextInput(label="Description", style=discord.TextStyle.paragraph, max_length=1000)
    couleur = discord.ui.TextInput(label="Couleur (hex)", max_length=7, placeholder="#5865F2")
    salon = discord.ui.TextInput(label="ID du salon du panneau", required=False, max_length=25)

    def __init__(self, gid):
        super().__init__()
        self.gid = gid
        c = xget(gid, "apply")
        self.titre.default = c.get("titre", "📋 Candidatures")
        self.desc.default = c.get("description", "")
        self.couleur.default = c.get("couleur", "#5865F2")
        self.salon.default = str(c.get("panel_channel") or "")

    async def on_submit(self, interaction: discord.Interaction):
        c = xget(self.gid, "apply")
        c["titre"] = str(self.titre.value).strip()
        c["description"] = str(self.desc.value).strip()
        c["couleur"] = str(self.couleur.value).strip() or "#5865F2"
        v = str(self.salon.value or "").strip()
        c["panel_channel"] = int(v) if v.isdigit() else None
        xset(self.gid, "apply", c)
        await interaction.response.edit_message(embed=ap_embed(interaction.guild))


class ModalApSalons(discord.ui.Modal, title="📥 Reception & role"):
    review = discord.ui.TextInput(label="ID du salon de reception", max_length=25)
    role = discord.ui.TextInput(label="ID du role donne si accepte", required=False, max_length=25)
    logs = discord.ui.TextInput(label="ID du salon de logs", required=False, max_length=25)
    cd = discord.ui.TextInput(label="Cooldown entre 2 candidatures (heures)", max_length=4, placeholder="24")

    def __init__(self, gid):
        super().__init__()
        self.gid = gid
        c = xget(gid, "apply")
        self.review.default = str(c.get("review_channel") or "")
        self.role.default = str(c.get("accepted_role") or "")
        self.logs.default = str(c.get("log_channel") or "")
        self.cd.default = str(c.get("cooldown_hours", 24))

    async def on_submit(self, interaction: discord.Interaction):
        c = xget(self.gid, "apply")
        for field, key in ((self.review, "review_channel"), (self.role, "accepted_role"), (self.logs, "log_channel")):
            v = str(field.value or "").strip()
            c[key] = int(v) if v.isdigit() else None
        try:
            c["cooldown_hours"] = max(0, int(str(self.cd.value).strip()))
        except Exception:
            pass
        xset(self.gid, "apply", c)
        await interaction.response.edit_message(embed=ap_embed(interaction.guild))


class ModalApPoste(discord.ui.Modal, title="💼 Nouveau poste"):
    nom = discord.ui.TextInput(label="Nom du poste", max_length=40, placeholder="Moderateur")
    emoji = discord.ui.TextInput(label="Emoji", max_length=8, required=False, placeholder="🛡️")
    desc = discord.ui.TextInput(label="Description courte", max_length=90, required=False)
    questions = discord.ui.TextInput(
        label="Questions (une par ligne, 5 max)",
        style=discord.TextStyle.paragraph, max_length=900,
        placeholder="Ton age ?\nTon experience en moderation ?\nCombien d'heures par jour ?")

    def __init__(self, gid):
        super().__init__()
        self.gid = gid

    async def on_submit(self, interaction: discord.Interaction):
        c = xget(self.gid, "apply")
        postes = c.get("postes", [])
        if len(postes) >= 25:
            return await interaction.response.send_message(embed=err("25 postes maximum."), ephemeral=True)
        qs = [q.strip() for q in str(self.questions.value).split("\n") if q.strip()][:5]
        if not qs:
            return await interaction.response.send_message(embed=err("Ajoute au moins une question."), ephemeral=True)
        postes.append({
            "nom": str(self.nom.value).strip(),
            "emoji": str(self.emoji.value or "📄").strip() or "📄",
            "description": str(self.desc.value or "").strip(),
            "questions": qs,
        })
        c["postes"] = postes
        xset(self.gid, "apply", c)
        await interaction.response.edit_message(embed=ap_embed(interaction.guild))


class ApPosteRemove(discord.ui.Select):
    def __init__(self, postes):
        super().__init__(placeholder="Poste a supprimer...",
                         options=[discord.SelectOption(label=p["nom"][:100], value=str(i),
                                                       emoji=p.get("emoji") or None)
                                  for i, p in enumerate(postes[:25])])

    async def callback(self, interaction: discord.Interaction):
        c = xget(interaction.guild.id, "apply")
        postes = c.get("postes", [])
        i = int(self.values[0])
        if 0 <= i < len(postes):
            nom = postes.pop(i)["nom"]
            c["postes"] = postes
            xset(interaction.guild.id, "apply", c)
            return await interaction.response.edit_message(embed=ok(f"Poste **{nom}** supprime."), view=None)
        await interaction.response.edit_message(embed=err("Poste introuvable."), view=None)


class ApplyConfigView(discord.ui.View):
    def __init__(self, ctx):
        super().__init__(timeout=300)
        self.ctx = ctx

    async def interaction_check(self, interaction: discord.Interaction):
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message(embed=err("Ce panneau n'est pas pour toi."), ephemeral=True)
            return False
        return True

    @discord.ui.select(placeholder="⚙️ Configurer les candidatures...", options=[
        discord.SelectOption(label="Apparence du panneau", emoji="🖼️", value="panel"),
        discord.SelectOption(label="Salon de reception, role & cooldown", emoji="📥", value="salons"),
        discord.SelectOption(label="Ajouter un poste", emoji="➕", value="add"),
        discord.SelectOption(label="Supprimer un poste", emoji="🗑️", value="del"),
    ])
    async def menu(self, interaction: discord.Interaction, select: discord.ui.Select):
        v = select.values[0]
        gid = interaction.guild.id
        if v == "panel":
            return await interaction.response.send_modal(ModalApPanel(gid))
        if v == "salons":
            return await interaction.response.send_modal(ModalApSalons(gid))
        if v == "add":
            return await interaction.response.send_modal(ModalApPoste(gid))
        postes = xget(gid, "apply").get("postes", [])
        if not postes:
            return await interaction.response.send_message(embed=err("Aucun poste a supprimer."), ephemeral=True)
        view = discord.ui.View(timeout=120)
        view.add_item(ApPosteRemove(postes))
        await interaction.response.send_message(embed=warn("Choisis le poste a supprimer."),
                                                view=view, ephemeral=True)

    @discord.ui.button(label="Activer / Desactiver", emoji="🔘", style=discord.ButtonStyle.success, row=1)
    async def toggle(self, interaction: discord.Interaction, button: discord.ui.Button):
        c = xget(interaction.guild.id, "apply")
        c["enabled"] = not c.get("enabled")
        xset(interaction.guild.id, "apply", c)
        await interaction.response.edit_message(embed=ap_embed(interaction.guild), view=self)

    @discord.ui.button(label="Envoyer le panneau", emoji="📤", style=discord.ButtonStyle.primary, row=1)
    async def send(self, interaction: discord.Interaction, button: discord.ui.Button):
        c = xget(interaction.guild.id, "apply")
        ch = interaction.guild.get_channel(int(c["panel_channel"])) if c.get("panel_channel") else interaction.channel
        if not c.get("postes"):
            return await interaction.response.send_message(embed=err("Ajoute au moins un poste."), ephemeral=True)
        await ch.send(embed=apply_public_embed(interaction.guild), view=ApplyPanelView())
        await interaction.response.send_message(embed=ok(f"Panneau envoye dans {ch.mention}."), ephemeral=True)

    @discord.ui.button(label="Fermer", emoji="✖️", style=discord.ButtonStyle.secondary, row=1)
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(view=None)
        self.stop()


def apply_public_embed(guild):
    c = xget(guild.id, "apply")
    e = discord.Embed(title=c.get("titre", "📋 Candidatures"),
                      description=c.get("description", "Clique sur le bouton pour postuler."),
                      color=color_of(c.get("couleur", "#5865F2")))
    postes = c.get("postes", [])
    if postes:
        e.add_field(name="💼 Postes ouverts",
                    value="\n".join(f"{p.get('emoji','📄')} **{p['nom']}** — {p.get('description','')}"
                                    for p in postes[:15]), inline=False)
    if guild.icon:
        e.set_thumbnail(url=guild.icon.url)
    e.set_footer(text=f"{guild.name} • Candidature confidentielle")
    return e


class ApplyFormModal(discord.ui.Modal):
    def __init__(self, poste):
        super().__init__(title=f"📝 {poste['nom']}"[:45])
        self.poste = poste
        self.champs = []
        for q in poste.get("questions", [])[:5]:
            item = discord.ui.TextInput(label=q[:45], style=discord.TextStyle.paragraph,
                                        max_length=500, required=True)
            self.champs.append((q, item))
            self.add_item(item)

    async def on_submit(self, interaction: discord.Interaction):
        guild = interaction.guild
        c = xget(guild.id, "apply")
        ch = guild.get_channel(int(c["review_channel"])) if c.get("review_channel") else None
        if not ch:
            return await interaction.response.send_message(
                embed=err("Le salon de reception n'est pas configure. Previens un admin."), ephemeral=True)

        e = discord.Embed(title=f"📋 Candidature — {self.poste['nom']}",
                          color=color_of(c.get("couleur", "#5865F2")),
                          timestamp=datetime.now(timezone.utc))
        e.set_author(name=str(interaction.user), icon_url=interaction.user.display_avatar.url)
        e.add_field(name="👤 Candidat", value=f"{interaction.user.mention} (`{interaction.user.id}`)", inline=False)
        for q, item in self.champs:
            e.add_field(name=f"❓ {q[:100]}", value=(item.value or "—")[:1024], inline=False)
        e.add_field(name="📌 Statut", value="🕓 En attente", inline=False)
        e.set_footer(text=f"Compte cree le {interaction.user.created_at.strftime('%d/%m/%Y')}")

        await ch.send(embed=e, view=ApplyReviewView())

        cds = c.get("cooldowns", {})
        cds[str(interaction.user.id)] = int(time.time())
        c["cooldowns"] = cds
        xset(guild.id, "apply", c)

        await interaction.response.send_message(
            embed=ok(f"Ta candidature pour **{self.poste['nom']}** a bien ete envoyee au staff."), ephemeral=True)


class ApplyPosteSelect(discord.ui.Select):
    def __init__(self, postes):
        super().__init__(placeholder="💼 Choisis un poste...",
                         options=[discord.SelectOption(label=p["nom"][:100], value=str(i),
                                                       description=(p.get("description") or "")[:90] or None,
                                                       emoji=p.get("emoji") or None)
                                  for i, p in enumerate(postes[:25])])
        self.postes = postes

    async def callback(self, interaction: discord.Interaction):
        poste = self.postes[int(self.values[0])]
        await interaction.response.send_modal(ApplyFormModal(poste))


class ApplyPanelView(discord.ui.View):
    """Vue publique persistante : bouton Postuler."""

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Postuler", emoji="📝", style=discord.ButtonStyle.primary,
                       custom_id="mb_apply_open")
    async def open(self, interaction: discord.Interaction, button: discord.ui.Button):
        c = xget(interaction.guild.id, "apply")
        if not c.get("enabled"):
            return await interaction.response.send_message(
                embed=err("Les candidatures sont fermees pour le moment."), ephemeral=True)
        postes = c.get("postes", [])
        if not postes:
            return await interaction.response.send_message(
                embed=err("Aucun poste ouvert actuellement."), ephemeral=True)
        cd = int(c.get("cooldown_hours", 24)) * 3600
        last = int((c.get("cooldowns") or {}).get(str(interaction.user.id), 0))
        if cd and last and time.time() - last < cd:
            return await interaction.response.send_message(
                embed=warn(f"Tu as deja postule recemment. Reessaie dans **{fmt_left(last + cd - time.time())}**."),
                ephemeral=True)
        if len(postes) == 1:
            return await interaction.response.send_modal(ApplyFormModal(postes[0]))
        view = discord.ui.View(timeout=180)
        view.add_item(ApplyPosteSelect(postes))
        await interaction.response.send_message(
            embed=discord.Embed(description="💼 Selectionne le poste qui t'interesse :", color=X_BLUE),
            view=view, ephemeral=True)


class ApplyReviewView(discord.ui.View):
    """Vue persistante staff : accepter / refuser une candidature."""

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Accepter", emoji="✅", style=discord.ButtonStyle.success,
                       custom_id="mb_apply_accept")
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._decide(interaction, True)

    @discord.ui.button(label="Refuser", emoji="❌", style=discord.ButtonStyle.danger,
                       custom_id="mb_apply_deny")
    async def deny(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._decide(interaction, False)

    async def _decide(self, interaction: discord.Interaction, accepted: bool):
        if not is_staff(interaction.user):
            return await interaction.response.send_message(embed=err("Reserve au staff."), ephemeral=True)
        guild = interaction.guild
        c = xget(guild.id, "apply")
        msg = interaction.message
        e = msg.embeds[0] if msg.embeds else discord.Embed()

        uid = None
        for f in e.fields:
            m = re.search(r"\((\d{5,25})\)", f.value or "")
            if m:
                uid = int(m.group(1))
                break

        e.color = X_GREEN if accepted else X_RED
        champs = [f for f in e.fields if f.name != "📌 Statut"]
        e.clear_fields()
        for f in champs:
            e.add_field(name=f.name, value=f.value, inline=f.inline)
        e.add_field(name="📌 Statut",
                    value=f"{'✅ Acceptee' if accepted else '❌ Refusee'} par {interaction.user.mention}",
                    inline=False)
        await interaction.response.edit_message(embed=e, view=None)

        membre = guild.get_member(uid) if uid else None
        if membre:
            if accepted and c.get("accepted_role"):
                try:
                    role = guild.get_role(int(c["accepted_role"]))
                    if role:
                        await membre.add_roles(role, reason="Candidature acceptee")
                except Exception:
                    pass
            try:
                await membre.send(embed=discord.Embed(
                    title=f"📋 Candidature sur {guild.name}",
                    description=("✅ **Felicitations, ta candidature a ete acceptee !**"
                                 if accepted else
                                 "❌ Ta candidature a ete refusee. Tu pourras retenter plus tard."),
                    color=X_GREEN if accepted else X_RED))
            except Exception:
                pass

        await send_log(guild, "apply", discord.Embed(
            title="📋 Candidature traitee", color=e.color,
            description=f"{'Acceptee' if accepted else 'Refusee'} par {interaction.user.mention}\n"
                        f"Candidat : {membre.mention if membre else 'inconnu'}"))


def register_apply(bot):

    @bot.command(name="apply", aliases=["candidature", "candidatures", "recrutement", "postuler"])
    async def apply_cmd(ctx):
        if not is_admin(ctx.author):
            return await ctx.send(embed=err("Permission administrateur requise."))
        await ctx.send(embed=ap_embed(ctx.guild), view=ApplyConfigView(ctx))

    @bot.command(name="applysend", aliases=["applypanel", "panelcandidature", "sendapply"])
    async def applysend_cmd(ctx, salon: discord.TextChannel = None):
        if not is_admin(ctx.author):
            return await ctx.send(embed=err("Permission administrateur requise."))
        c = xget(ctx.guild.id, "apply")
        if not c.get("postes"):
            return await ctx.send(embed=err("Ajoute au moins un poste avec `+apply`."))
        salon = salon or (ctx.guild.get_channel(int(c["panel_channel"])) if c.get("panel_channel") else ctx.channel)
        await salon.send(embed=apply_public_embed(ctx.guild), view=ApplyPanelView())
        await ctx.send(embed=ok(f"Panneau de candidature envoye dans {salon.mention}."))

    @bot.command(name="applyadd", aliases=["addposte", "ajouterposte"])
    async def applyadd_cmd(ctx, *, texte: str = None):
        if not is_admin(ctx.author):
            return await ctx.send(embed=err("Permission administrateur requise."))
        if not texte or "|" not in texte:
            return await ctx.send(embed=err(
                "Usage : `+applyadd Nom du poste | Question 1 | Question 2 | ...`"))
        parts = [p.strip() for p in texte.split("|") if p.strip()]
        c = xget(ctx.guild.id, "apply")
        postes = c.get("postes", [])
        if len(postes) >= 25:
            return await ctx.send(embed=err("25 postes maximum."))
        postes.append({"nom": parts[0][:40], "emoji": "📄", "description": "",
                       "questions": parts[1:6] or ["Pourquoi toi ?"]})
        c["postes"] = postes
        xset(ctx.guild.id, "apply", c)
        await ctx.send(embed=ok(f"Poste **{parts[0]}** ajoute ({len(parts[1:6])} question(s))."))

    @bot.command(name="applydel", aliases=["delposte", "supprimerposte"])
    async def applydel_cmd(ctx, *, nom: str = None):
        if not is_admin(ctx.author):
            return await ctx.send(embed=err("Permission administrateur requise."))
        c = xget(ctx.guild.id, "apply")
        postes = c.get("postes", [])
        if not nom:
            return await ctx.send(embed=err("Usage : `+applydel <nom du poste>`"))
        restants = [p for p in postes if p["nom"].lower() != nom.strip().lower()]
        if len(restants) == len(postes):
            return await ctx.send(embed=err("Poste introuvable."))
        c["postes"] = restants
        xset(ctx.guild.id, "apply", c)
        await ctx.send(embed=ok(f"Poste **{nom}** supprime."))

    @bot.command(name="applylist", aliases=["listpostes", "postes"])
    async def applylist_cmd(ctx):
        c = xget(ctx.guild.id, "apply")
        postes = c.get("postes", [])
        if not postes:
            return await ctx.send(embed=warn("Aucun poste configure."))
        e = discord.Embed(title="💼 Postes ouverts", color=X_BLUE)
        for p in postes:
            e.add_field(name=f"{p.get('emoji','📄')} {p['nom']}",
                        value=(p.get("description") or "Aucune description")
                              + "\n" + "\n".join(f"• {q}" for q in p.get("questions", [])[:5]),
                        inline=False)
        await ctx.send(embed=e)


# ===========================================================================
# ===========================================================================
#   CATEGORIE 7 — ANTI-NUKE
# ===========================================================================
# ===========================================================================

NUKE_TRACK = {}


def an_embed(guild):
    c = xget(guild.id, "antinuke")
    e = discord.Embed(
        title="🧨 Anti-nuke",
        description="Surveille les actions destructrices d'un administrateur ou d'un bot compromis : "
                    "suppressions en masse de salons, de roles, bans ou kicks en rafale.",
        color=X_RED if c.get("enabled") else X_BLUE)
    e.add_field(name="🔘 Statut", value="✅ Actif" if c.get("enabled") else "❌ Desactive", inline=True)
    e.add_field(name="⚖️ Sanction", value=f"`{c.get('punish','strip')}`", inline=True)
    e.add_field(name="⏱️ Fenetre", value=f"{c.get('window',60)} s", inline=True)
    e.add_field(name="📺 Salons supprimes",
                value=(f"Max {c.get('max_channel_delete',3)}" if c.get("protect_channels") else "❌"), inline=True)
    e.add_field(name="🎭 Roles supprimes",
                value=(f"Max {c.get('max_role_delete',3)}" if c.get("protect_roles") else "❌"), inline=True)
    e.add_field(name="🔨 Bans", value=(f"Max {c.get('max_ban',3)}" if c.get("protect_bans") else "❌"), inline=True)
    e.add_field(name="👢 Kicks", value=(f"Max {c.get('max_kick',5)}" if c.get("protect_kicks") else "❌"), inline=True)
    e.add_field(name="🤖 Ajout de bots", value="🚫 Bloque" if c.get("anti_bot_add") else "Autorise", inline=True)
    e.add_field(name="📋 Logs", value=chan_field(guild, c.get("log_channel")), inline=True)
    wl = c.get("whitelist_roles", []) + c.get("whitelist_users", [])
    e.add_field(name="✅ Liste blanche", value=f"{len(wl)} entree(s)", inline=False)
    e.add_field(name="⌨️ Commandes", value="`+antinuke` `+antinukewl` `+antinukelogs`", inline=False)
    e.set_footer(text="ModeraBot • Anti-nuke")
    return e


class ModalAnLimites(discord.ui.Modal, title="🧨 Limites de l'anti-nuke"):
    fenetre = discord.ui.TextInput(label="Fenetre de detection (secondes)", max_length=5, placeholder="60")
    salons = discord.ui.TextInput(label="Salons supprimes maximum", max_length=3, placeholder="3")
    roles = discord.ui.TextInput(label="Roles supprimes maximum", max_length=3, placeholder="3")
    bans = discord.ui.TextInput(label="Bans maximum", max_length=3, placeholder="3")
    kicks = discord.ui.TextInput(label="Kicks maximum", max_length=3, placeholder="5")

    def __init__(self, gid):
        super().__init__()
        self.gid = gid
        c = xget(gid, "antinuke")
        self.fenetre.default = str(c.get("window", 60))
        self.salons.default = str(c.get("max_channel_delete", 3))
        self.roles.default = str(c.get("max_role_delete", 3))
        self.bans.default = str(c.get("max_ban", 3))
        self.kicks.default = str(c.get("max_kick", 5))

    async def on_submit(self, interaction: discord.Interaction):
        c = xget(self.gid, "antinuke")
        try:
            c["window"] = max(5, int(str(self.fenetre.value).strip()))
            c["max_channel_delete"] = max(1, int(str(self.salons.value).strip()))
            c["max_role_delete"] = max(1, int(str(self.roles.value).strip()))
            c["max_ban"] = max(1, int(str(self.bans.value).strip()))
            c["max_kick"] = max(1, int(str(self.kicks.value).strip()))
        except Exception:
            return await interaction.response.send_message(embed=err("Entre des nombres valides."), ephemeral=True)
        xset(self.gid, "antinuke", c)
        await interaction.response.edit_message(embed=an_embed(interaction.guild))


class ModalAnSanction(discord.ui.Modal, title="⚖️ Sanction et logs"):
    punish = discord.ui.TextInput(label="Sanction : strip / kick / ban", max_length=6, placeholder="strip")
    logs = discord.ui.TextInput(label="ID du salon de logs", required=False, max_length=25)

    def __init__(self, gid):
        super().__init__()
        self.gid = gid
        c = xget(gid, "antinuke")
        self.punish.default = c.get("punish", "strip")
        self.logs.default = str(c.get("log_channel") or "")

    async def on_submit(self, interaction: discord.Interaction):
        c = xget(self.gid, "antinuke")
        a = str(self.punish.value).strip().lower()
        c["punish"] = a if a in ("strip", "kick", "ban") else "strip"
        v = str(self.logs.value or "").strip()
        c["log_channel"] = int(v) if v.isdigit() else None
        xset(self.gid, "antinuke", c)
        await interaction.response.edit_message(embed=an_embed(interaction.guild))


class ModalAnWhitelist(discord.ui.Modal, title="✅ Liste blanche"):
    roles = discord.ui.TextInput(label="IDs de roles autorises (virgules)", required=False, max_length=500)
    users = discord.ui.TextInput(label="IDs de membres autorises (virgules)", required=False, max_length=500)

    def __init__(self, gid):
        super().__init__()
        self.gid = gid
        c = xget(gid, "antinuke")
        self.roles.default = ", ".join(str(i) for i in c.get("whitelist_roles", []))
        self.users.default = ", ".join(str(i) for i in c.get("whitelist_users", []))

    async def on_submit(self, interaction: discord.Interaction):
        c = xget(self.gid, "antinuke")
        c["whitelist_roles"] = [int(x) for x in re.findall(r"\d{5,25}", str(self.roles.value or ""))][:50]
        c["whitelist_users"] = [int(x) for x in re.findall(r"\d{5,25}", str(self.users.value or ""))][:50]
        xset(self.gid, "antinuke", c)
        await interaction.response.edit_message(embed=an_embed(interaction.guild))


class AntinukeView(discord.ui.View):
    def __init__(self, ctx):
        super().__init__(timeout=300)
        self.ctx = ctx

    async def interaction_check(self, interaction: discord.Interaction):
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message(embed=err("Ce panneau n'est pas pour toi."), ephemeral=True)
            return False
        return True

    @discord.ui.select(placeholder="⚙️ Configurer l'anti-nuke...", options=[
        discord.SelectOption(label="Limites de detection", emoji="🧨", value="limites"),
        discord.SelectOption(label="Sanction et salon de logs", emoji="⚖️", value="sanction"),
        discord.SelectOption(label="Liste blanche", emoji="✅", value="wl"),
    ])
    async def menu(self, interaction: discord.Interaction, select: discord.ui.Select):
        v = select.values[0]
        gid = interaction.guild.id
        if v == "limites":
            return await interaction.response.send_modal(ModalAnLimites(gid))
        if v == "sanction":
            return await interaction.response.send_modal(ModalAnSanction(gid))
        return await interaction.response.send_modal(ModalAnWhitelist(gid))

    @discord.ui.button(label="Activer / Desactiver", emoji="🔘", style=discord.ButtonStyle.success, row=1)
    async def toggle(self, interaction: discord.Interaction, button: discord.ui.Button):
        c = xget(interaction.guild.id, "antinuke")
        c["enabled"] = not c.get("enabled")
        xset(interaction.guild.id, "antinuke", c)
        await interaction.response.edit_message(embed=an_embed(interaction.guild), view=self)

    @discord.ui.button(label="Ajout de bots", emoji="🤖", style=discord.ButtonStyle.secondary, row=1)
    async def bots(self, interaction: discord.Interaction, button: discord.ui.Button):
        c = xget(interaction.guild.id, "antinuke")
        c["anti_bot_add"] = not c.get("anti_bot_add")
        xset(interaction.guild.id, "antinuke", c)
        await interaction.response.edit_message(embed=an_embed(interaction.guild), view=self)

    @discord.ui.button(label="Fermer", emoji="✖️", style=discord.ButtonStyle.secondary, row=1)
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(view=None)
        self.stop()


def an_whitelisted(guild, user):
    c = xget(guild.id, "antinuke")
    if user is None:
        return True
    if user.id == guild.owner_id or str(user.id) in OWNER_IDS_EXTRA:
        return True
    if int(user.id) in [int(x) for x in c.get("whitelist_users", [])]:
        return True
    member = guild.get_member(user.id)
    if member:
        wl = {int(x) for x in c.get("whitelist_roles", [])}
        if wl and any(r.id in wl for r in member.roles):
            return True
    return False


OWNER_IDS_EXTRA = set()


async def an_audit_author(guild, action, target_id=None):
    try:
        async for entry in guild.audit_logs(limit=5, action=action):
            if (datetime.now(timezone.utc) - entry.created_at).total_seconds() > 20:
                continue
            if target_id and getattr(entry.target, "id", None) != target_id:
                continue
            return entry.user
    except Exception:
        return None
    return None


async def an_trigger(guild, user, kind, limit):
    c = xget(guild.id, "antinuke")
    key = (guild.id, user.id, kind)
    now = time.time()
    window = int(c.get("window", 60))
    hits = [t for t in NUKE_TRACK.get(key, []) if now - t < window]
    hits.append(now)
    NUKE_TRACK[key] = hits
    if len(hits) < limit:
        return
    NUKE_TRACK[key] = []

    punish = c.get("punish", "strip")
    member = guild.get_member(user.id)
    done = "aucune"
    if member:
        try:
            if punish == "ban":
                await member.ban(reason=f"Anti-nuke : {kind}")
                done = "banni"
            elif punish == "kick":
                await member.kick(reason=f"Anti-nuke : {kind}")
                done = "expulse"
            else:
                roles = [r for r in member.roles if r.is_assignable()]
                if roles:
                    await member.remove_roles(*roles, reason=f"Anti-nuke : {kind}")
                done = "roles retires"
        except Exception:
            done = "echec (permissions)"

    e = discord.Embed(title="🧨 Anti-nuke declenche", color=X_RED,
                      timestamp=datetime.now(timezone.utc))
    e.add_field(name="👤 Auteur", value=f"{user} (`{user.id}`)", inline=True)
    e.add_field(name="⚠️ Action", value=kind, inline=True)
    e.add_field(name="📊 Seuil", value=f"{limit} en {window}s", inline=True)
    e.add_field(name="⚖️ Sanction", value=done, inline=False)
    await send_log(guild, "antinuke", e)


def register_antinuke(bot):

    @bot.command(name="antinuke", aliases=["antinuk", "nukeprotection", "antidestruction"])
    async def antinuke_cmd(ctx):
        if not is_admin(ctx.author):
            return await ctx.send(embed=err("Permission administrateur requise."))
        await ctx.send(embed=an_embed(ctx.guild), view=AntinukeView(ctx))

    @bot.command(name="antinukewl", aliases=["antinukewhitelist", "nukewl"])
    async def antinukewl_cmd(ctx, cible: str = None):
        if not is_admin(ctx.author):
            return await ctx.send(embed=err("Permission administrateur requise."))
        if not cible:
            c = xget(ctx.guild.id, "antinuke")
            r = " ".join(f"<@&{i}>" for i in c.get("whitelist_roles", [])) or "Aucun"
            u = " ".join(f"<@{i}>" for i in c.get("whitelist_users", [])) or "Aucun"
            return await ctx.send(embed=discord.Embed(
                title="✅ Liste blanche anti-nuke", color=X_BLUE,
                description=f"**Roles :** {r}\n**Membres :** {u}"))
        ids = re.findall(r"\d{5,25}", cible)
        if not ids:
            return await ctx.send(embed=err("Mentionne un role ou un membre, ou donne son ID."))
        oid = int(ids[0])
        c = xget(ctx.guild.id, "antinuke")
        key = "whitelist_roles" if ctx.guild.get_role(oid) else "whitelist_users"
        lst = [int(x) for x in c.get(key, [])]
        if oid in lst:
            lst.remove(oid)
            txt = "retire de la liste blanche."
        else:
            lst.append(oid)
            txt = "ajoute a la liste blanche."
        c[key] = lst
        xset(ctx.guild.id, "antinuke", c)
        await ctx.send(embed=ok(f"<@{'&' if key=='whitelist_roles' else ''}{oid}> {txt}"))

    @bot.command(name="antinukelogs", aliases=["nukelogs"])
    async def antinukelogs_cmd(ctx, salon: discord.TextChannel = None):
        if not is_admin(ctx.author):
            return await ctx.send(embed=err("Permission administrateur requise."))
        c = xget(ctx.guild.id, "antinuke")
        c["log_channel"] = salon.id if salon else None
        xset(ctx.guild.id, "antinuke", c)
        await ctx.send(embed=ok(f"Logs anti-nuke : {salon.mention if salon else 'desactives'}."))


# ===========================================================================
# ===========================================================================
#   CATEGORIE 8 — INFRACTIONS
# ===========================================================================
# ===========================================================================

INF_DIR = "extras_infractions"
os.makedirs(INF_DIR, exist_ok=True)


def inf_load(gid):
    try:
        with open(os.path.join(INF_DIR, f"{gid}.json"), "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def inf_save(gid, data):
    try:
        with open(os.path.join(INF_DIR, f"{gid}.json"), "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except Exception:
        pass


def inf_list(gid, uid):
    c = xget(gid, "infractions")
    items = inf_load(gid).get(str(uid), [])
    days = int(c.get("expire_days", 0))
    if days:
        limite = time.time() - days * 86400
        items = [i for i in items if i.get("date", 0) >= limite]
    return items


def inf_add(guild, member, kind, reason, moderator):
    gid = guild.id
    data = inf_load(gid)
    items = data.setdefault(str(member.id), [])
    items.append({
        "id": int(time.time() * 1000) % 100000000,
        "type": kind,
        "raison": reason,
        "mod": str(moderator),
        "mod_id": getattr(moderator, "id", 0),
        "date": int(time.time()),
    })
    inf_save(gid, data)
    return len(inf_list(gid, member.id))


def inf_embed(guild):
    c = xget(guild.id, "infractions")
    data = inf_load(guild.id)
    total = sum(len(v) for v in data.values())
    e = discord.Embed(
        title="📒 Casier des membres",
        description="Historique des sanctions, avec sanctions automatiques quand un membre "
                    "accumule trop d'infractions.",
        color=X_ORANGE)
    e.add_field(name="🔘 Statut", value="✅ Actif" if c.get("enabled") else "❌ Desactive", inline=True)
    e.add_field(name="📋 Logs", value=chan_field(guild, c.get("log_channel")), inline=True)
    e.add_field(name="📩 Prevenir le membre", value="✅" if c.get("dm_user") else "❌", inline=True)
    e.add_field(name="🔇 Mute automatique",
                value=f"a {c.get('auto_mute_at')} infractions" if c.get("auto_mute_at") else "❌", inline=True)
    e.add_field(name="👢 Kick automatique",
                value=f"a {c.get('auto_kick_at')} infractions" if c.get("auto_kick_at") else "❌", inline=True)
    e.add_field(name="🔨 Ban automatique",
                value=f"a {c.get('auto_ban_at')} infractions" if c.get("auto_ban_at") else "❌", inline=True)
    e.add_field(name="⏳ Expiration",
                value=f"{c.get('expire_days')} jours" if c.get("expire_days") else "Jamais", inline=True)
    e.add_field(name="📊 Total enregistre", value=f"{total} infraction(s) · {len(data)} membre(s)", inline=True)
    e.add_field(name="⌨️ Commandes",
                value="`+infractions` `+addinfraction` `+delinfraction` `+clearinfractions` `+casier`",
                inline=False)
    e.set_footer(text="ModeraBot • Infractions")
    return e


class ModalInfSeuils(discord.ui.Modal, title="📒 Sanctions automatiques"):
    mute = discord.ui.TextInput(label="Mute a X infractions (0 = jamais)", max_length=3, placeholder="3")
    kick = discord.ui.TextInput(label="Kick a X infractions (0 = jamais)", max_length=3, placeholder="0")
    ban = discord.ui.TextInput(label="Ban a X infractions (0 = jamais)", max_length=3, placeholder="5")
    expire = discord.ui.TextInput(label="Expiration en jours (0 = jamais)", max_length=4, placeholder="0")
    logs = discord.ui.TextInput(label="ID du salon de logs", required=False, max_length=25)

    def __init__(self, gid):
        super().__init__()
        self.gid = gid
        c = xget(gid, "infractions")
        self.mute.default = str(c.get("auto_mute_at", 3))
        self.kick.default = str(c.get("auto_kick_at", 0))
        self.ban.default = str(c.get("auto_ban_at", 5))
        self.expire.default = str(c.get("expire_days", 0))
        self.logs.default = str(c.get("log_channel") or "")

    async def on_submit(self, interaction: discord.Interaction):
        c = xget(self.gid, "infractions")
        try:
            c["auto_mute_at"] = max(0, int(str(self.mute.value).strip() or 0))
            c["auto_kick_at"] = max(0, int(str(self.kick.value).strip() or 0))
            c["auto_ban_at"] = max(0, int(str(self.ban.value).strip() or 0))
            c["expire_days"] = max(0, int(str(self.expire.value).strip() or 0))
        except Exception:
            return await interaction.response.send_message(embed=err("Entre des nombres valides."), ephemeral=True)
        v = str(self.logs.value or "").strip()
        c["log_channel"] = int(v) if v.isdigit() else None
        xset(self.gid, "infractions", c)
        await interaction.response.edit_message(embed=inf_embed(interaction.guild))


class InfractionsView(discord.ui.View):
    def __init__(self, ctx):
        super().__init__(timeout=300)
        self.ctx = ctx

    async def interaction_check(self, interaction: discord.Interaction):
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message(embed=err("Ce panneau n'est pas pour toi."), ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Sanctions automatiques", emoji="⚙️", style=discord.ButtonStyle.primary)
    async def seuils(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ModalInfSeuils(interaction.guild.id))

    @discord.ui.button(label="Activer / Desactiver", emoji="🔘", style=discord.ButtonStyle.success)
    async def toggle(self, interaction: discord.Interaction, button: discord.ui.Button):
        c = xget(interaction.guild.id, "infractions")
        c["enabled"] = not c.get("enabled")
        xset(interaction.guild.id, "infractions", c)
        await interaction.response.edit_message(embed=inf_embed(interaction.guild), view=self)

    @discord.ui.button(label="Prevenir en MP", emoji="📩", style=discord.ButtonStyle.secondary)
    async def dm(self, interaction: discord.Interaction, button: discord.ui.Button):
        c = xget(interaction.guild.id, "infractions")
        c["dm_user"] = not c.get("dm_user")
        xset(interaction.guild.id, "infractions", c)
        await interaction.response.edit_message(embed=inf_embed(interaction.guild), view=self)

    @discord.ui.button(label="Tout effacer", emoji="🗑️", style=discord.ButtonStyle.danger)
    async def reset(self, interaction: discord.Interaction, button: discord.ui.Button):
        inf_save(interaction.guild.id, {})
        await interaction.response.send_message(embed=ok("Tous les casiers ont ete effaces."), ephemeral=True)

    @discord.ui.button(label="Fermer", emoji="✖️", style=discord.ButtonStyle.secondary)
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(view=None)
        self.stop()


async def inf_apply_auto(guild, member, total):
    c = xget(guild.id, "infractions")
    try:
        if c.get("auto_ban_at") and total >= int(c["auto_ban_at"]):
            await member.ban(reason=f"{total} infractions")
            return "ban"
        if c.get("auto_kick_at") and total >= int(c["auto_kick_at"]):
            await member.kick(reason=f"{total} infractions")
            return "kick"
        if c.get("auto_mute_at") and total >= int(c["auto_mute_at"]):
            await member.timeout(timedelta(hours=1), reason=f"{total} infractions")
            return "mute"
    except Exception:
        return None
    return None


async def inf_record(guild, member, kind, reason, moderator):
    c = xget(guild.id, "infractions")
    if not c.get("enabled"):
        return
    total = inf_add(guild, member, kind, reason, moderator)
    auto = await inf_apply_auto(guild, member, total)
    if c.get("dm_user"):
        try:
            await member.send(embed=discord.Embed(
                title=f"📒 Infraction sur {guild.name}",
                description=f"**Type :** {kind}\n**Raison :** {reason}\n**Total :** {total} infraction(s)"
                            + (f"\n**Sanction automatique :** {auto}" if auto else ""),
                color=X_ORANGE))
        except Exception:
            pass
    e = discord.Embed(title="📒 Infraction enregistree", color=X_ORANGE,
                      timestamp=datetime.now(timezone.utc))
    e.add_field(name="👤 Membre", value=f"{member.mention} (`{member.id}`)", inline=True)
    e.add_field(name="⚠️ Type", value=kind, inline=True)
    e.add_field(name="📊 Total", value=str(total), inline=True)
    e.add_field(name="📝 Raison", value=reason, inline=False)
    if auto:
        e.add_field(name="⚖️ Sanction automatique", value=f"`{auto}`", inline=False)
    await send_log(guild, "infractions", e)


def register_infractions(bot):

    @bot.command(name="infractions", aliases=["casier", "sanctions", "historique"])
    async def infractions_cmd(ctx, membre: discord.Member = None):
        if membre is None:
            if not is_admin(ctx.author):
                return await ctx.send(embed=err("Permission administrateur requise."))
            return await ctx.send(embed=inf_embed(ctx.guild), view=InfractionsView(ctx))
        if not is_staff(ctx.author) and membre.id != ctx.author.id:
            return await ctx.send(embed=err("Tu ne peux consulter que ton propre casier."))
        items = inf_list(ctx.guild.id, membre.id)
        if not items:
            return await ctx.send(embed=ok(f"{membre.mention} n'a aucune infraction."))
        e = discord.Embed(title=f"📒 Casier de {membre.display_name}",
                          description=f"**{len(items)}** infraction(s)", color=X_ORANGE)
        for i in items[-10:]:
            e.add_field(
                name=f"#{i['id']} · {i['type']}",
                value=f"📝 {i.get('raison','Aucune raison')}\n"
                      f"👮 {i.get('mod','?')} · <t:{int(i.get('date',0))}:R>",
                inline=False)
        e.set_thumbnail(url=membre.display_avatar.url)
        await ctx.send(embed=e)

    @bot.command(name="addinfraction", aliases=["ajoutinfraction", "addcasier"])
    async def addinfraction_cmd(ctx, membre: discord.Member = None, *, raison: str = "Aucune raison"):
        if not is_staff(ctx.author):
            return await ctx.send(embed=err("Reserve au staff."))
        if not membre:
            return await ctx.send(embed=err("Usage : `+addinfraction @membre raison`"))
        c = xget(ctx.guild.id, "infractions")
        if not c.get("enabled"):
            return await ctx.send(embed=err("Le module infractions est desactive (`+infractions`)."))
        await inf_record(ctx.guild, membre, "manuelle", raison, ctx.author)
        await ctx.send(embed=ok(f"Infraction ajoutee a {membre.mention} "
                                f"({len(inf_list(ctx.guild.id, membre.id))} au total)."))

    @bot.command(name="delinfraction", aliases=["supprinfraction", "delcasier"])
    async def delinfraction_cmd(ctx, membre: discord.Member = None, infraction_id: int = None):
        if not is_staff(ctx.author):
            return await ctx.send(embed=err("Reserve au staff."))
        if not membre or infraction_id is None:
            return await ctx.send(embed=err("Usage : `+delinfraction @membre <id>`"))
        data = inf_load(ctx.guild.id)
        items = data.get(str(membre.id), [])
        restants = [i for i in items if int(i.get("id")) != infraction_id]
        if len(restants) == len(items):
            return await ctx.send(embed=err("Infraction introuvable."))
        data[str(membre.id)] = restants
        inf_save(ctx.guild.id, data)
        await ctx.send(embed=ok(f"Infraction `#{infraction_id}` supprimee."))

    @bot.command(name="clearinfractions", aliases=["clearcasier", "resetinfractions"])
    async def clearinfractions_cmd(ctx, membre: discord.Member = None):
        if not is_admin(ctx.author):
            return await ctx.send(embed=err("Permission administrateur requise."))
        data = inf_load(ctx.guild.id)
        if membre:
            data.pop(str(membre.id), None)
            inf_save(ctx.guild.id, data)
            return await ctx.send(embed=ok(f"Casier de {membre.mention} efface."))
        inf_save(ctx.guild.id, {})
        await ctx.send(embed=ok("Tous les casiers ont ete effaces."))

    @bot.command(name="topinfractions", aliases=["worstmembers", "topcasier"])
    async def topinfractions_cmd(ctx):
        if not is_staff(ctx.author):
            return await ctx.send(embed=err("Reserve au staff."))
        data = inf_load(ctx.guild.id)
        rows = sorted(data.items(), key=lambda kv: len(kv[1]), reverse=True)[:10]
        if not rows:
            return await ctx.send(embed=ok("Aucune infraction enregistree."))
        lignes = []
        for uid, items in rows:
            m = ctx.guild.get_member(int(uid))
            lignes.append(f"**{m.display_name if m else uid}** — {len(items)} infraction(s)")
        await ctx.send(embed=discord.Embed(title="📒 Membres les plus sanctionnes",
                                           description="\n".join(lignes), color=X_ORANGE))


# ===========================================================================
# ===========================================================================
#   CATEGORIE 9 — MESSAGES AUTOMATIQUES
# ===========================================================================
# ===========================================================================

def am2_embed(guild):
    c = xget(guild.id, "automsg")
    msgs = c.get("messages", [])
    e = discord.Embed(
        title="🔁 Messages automatiques",
        description="Publie des messages a intervalle regulier : regles, promotion, rappels.",
        color=X_CYAN)
    e.add_field(name="🔘 Statut", value="✅ Actif" if c.get("enabled") else "❌ Desactive", inline=True)
    e.add_field(name="📨 Messages configures", value=str(len(msgs)), inline=True)
    for i, m in enumerate(msgs[:8], 1):
        e.add_field(
            name=f"#{i} · toutes les {m.get('interval_minutes',60)} min "
                 f"{'✅' if m.get('enabled', True) else '❌'}",
            value=f"<#{m.get('channel')}> — {(m.get('content') or '')[:70]}",
            inline=False)
    e.add_field(name="⌨️ Commandes",
                value="`+automessage` `+automessageadd` `+automessagelist` `+automessagedel`", inline=False)
    e.set_footer(text="ModeraBot • Messages automatiques")
    return e


class ModalAm2Add(discord.ui.Modal, title="🔁 Nouveau message automatique"):
    salon = discord.ui.TextInput(label="ID du salon", max_length=25)
    interval = discord.ui.TextInput(label="Intervalle en minutes", max_length=6, placeholder="60")
    contenu = discord.ui.TextInput(label="Message", style=discord.TextStyle.paragraph, max_length=1800)
    titre = discord.ui.TextInput(label="Titre de l'embed (vide = message simple)", required=False, max_length=100)
    couleur = discord.ui.TextInput(label="Couleur de l'embed", required=False, max_length=7, placeholder="#5865F2")

    def __init__(self, gid):
        super().__init__()
        self.gid = gid

    async def on_submit(self, interaction: discord.Interaction):
        c = xget(self.gid, "automsg")
        msgs = c.get("messages", [])
        if len(msgs) >= 15:
            return await interaction.response.send_message(embed=err("15 messages maximum."), ephemeral=True)
        salon = str(self.salon.value).strip()
        if not salon.isdigit():
            return await interaction.response.send_message(embed=err("ID de salon invalide."), ephemeral=True)
        try:
            interval = max(5, int(str(self.interval.value).strip()))
        except Exception:
            return await interaction.response.send_message(embed=err("Intervalle invalide."), ephemeral=True)
        msgs.append({
            "channel": int(salon),
            "interval_minutes": interval,
            "content": str(self.contenu.value),
            "titre": str(self.titre.value or "").strip(),
            "couleur": str(self.couleur.value or "#5865F2").strip() or "#5865F2",
            "enabled": True,
            "last": 0,
        })
        c["messages"] = msgs
        xset(self.gid, "automsg", c)
        await interaction.response.edit_message(embed=am2_embed(interaction.guild))


class Am2Remove(discord.ui.Select):
    def __init__(self, msgs):
        super().__init__(placeholder="Message a supprimer...",
                         options=[discord.SelectOption(
                             label=f"#{i+1} · {(m.get('content') or '')[:40]}"[:100], value=str(i))
                             for i, m in enumerate(msgs[:25])])

    async def callback(self, interaction: discord.Interaction):
        c = xget(interaction.guild.id, "automsg")
        msgs = c.get("messages", [])
        i = int(self.values[0])
        if 0 <= i < len(msgs):
            msgs.pop(i)
            c["messages"] = msgs
            xset(interaction.guild.id, "automsg", c)
            return await interaction.response.edit_message(embed=ok("Message supprime."), view=None)
        await interaction.response.edit_message(embed=err("Introuvable."), view=None)


class AutoMsgView(discord.ui.View):
    def __init__(self, ctx):
        super().__init__(timeout=300)
        self.ctx = ctx

    async def interaction_check(self, interaction: discord.Interaction):
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message(embed=err("Ce panneau n'est pas pour toi."), ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Ajouter un message", emoji="➕", style=discord.ButtonStyle.primary)
    async def add(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ModalAm2Add(interaction.guild.id))

    @discord.ui.button(label="Supprimer", emoji="🗑️", style=discord.ButtonStyle.danger)
    async def rm(self, interaction: discord.Interaction, button: discord.ui.Button):
        msgs = xget(interaction.guild.id, "automsg").get("messages", [])
        if not msgs:
            return await interaction.response.send_message(embed=err("Aucun message."), ephemeral=True)
        view = discord.ui.View(timeout=120)
        view.add_item(Am2Remove(msgs))
        await interaction.response.send_message(embed=warn("Choisis le message a supprimer."),
                                                view=view, ephemeral=True)

    @discord.ui.button(label="Activer / Desactiver", emoji="🔘", style=discord.ButtonStyle.success)
    async def toggle(self, interaction: discord.Interaction, button: discord.ui.Button):
        c = xget(interaction.guild.id, "automsg")
        c["enabled"] = not c.get("enabled")
        xset(interaction.guild.id, "automsg", c)
        await interaction.response.edit_message(embed=am2_embed(interaction.guild), view=self)

    @discord.ui.button(label="Fermer", emoji="✖️", style=discord.ButtonStyle.secondary)
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(view=None)
        self.stop()


def register_automsg(bot):

    @bot.command(name="automessage", aliases=["automessages", "messageauto", "autopost"])
    async def automessage_cmd(ctx):
        if not is_admin(ctx.author):
            return await ctx.send(embed=err("Permission administrateur requise."))
        await ctx.send(embed=am2_embed(ctx.guild), view=AutoMsgView(ctx))

    @bot.command(name="automessageadd", aliases=["addautomessage", "autopostadd"])
    async def automessageadd_cmd(ctx, salon: discord.TextChannel = None, minutes: int = None, *, texte: str = None):
        if not is_admin(ctx.author):
            return await ctx.send(embed=err("Permission administrateur requise."))
        if not salon or not minutes or not texte:
            return await ctx.send(embed=err("Usage : `+automessageadd #salon 60 Ton message`"))
        c = xget(ctx.guild.id, "automsg")
        msgs = c.get("messages", [])
        if len(msgs) >= 15:
            return await ctx.send(embed=err("15 messages maximum."))
        msgs.append({"channel": salon.id, "interval_minutes": max(5, minutes), "content": texte,
                     "titre": "", "couleur": "#5865F2", "enabled": True, "last": 0})
        c["messages"] = msgs
        xset(ctx.guild.id, "automsg", c)
        await ctx.send(embed=ok(f"Message automatique ajoute dans {salon.mention} toutes les {max(5, minutes)} min."))

    @bot.command(name="automessagelist", aliases=["listautomessages", "autopostlist"])
    async def automessagelist_cmd(ctx):
        await ctx.send(embed=am2_embed(ctx.guild))

    @bot.command(name="automessagedel", aliases=["delautomessage", "autopostdel"])
    async def automessagedel_cmd(ctx, numero: int = None):
        if not is_admin(ctx.author):
            return await ctx.send(embed=err("Permission administrateur requise."))
        c = xget(ctx.guild.id, "automsg")
        msgs = c.get("messages", [])
        if numero is None or numero < 1 or numero > len(msgs):
            return await ctx.send(embed=err("Usage : `+automessagedel <numero>` — voir `+automessagelist`."))
        msgs.pop(numero - 1)
        c["messages"] = msgs
        xset(ctx.guild.id, "automsg", c)
        await ctx.send(embed=ok(f"Message automatique `#{numero}` supprime."))


# ===========================================================================
# ===========================================================================
#   CATEGORIE 10 — ANNIVERSAIRES
# ===========================================================================
# ===========================================================================

BDAY_DIR = "extras_birthdays"
os.makedirs(BDAY_DIR, exist_ok=True)


def bday_load(gid):
    try:
        with open(os.path.join(BDAY_DIR, f"{gid}.json"), "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def bday_save(gid, data):
    try:
        with open(os.path.join(BDAY_DIR, f"{gid}.json"), "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except Exception:
        pass


def bd_embed(guild):
    c = xget(guild.id, "birthdays")
    data = bday_load(guild.id)
    e = discord.Embed(
        title="🎂 Anniversaires",
        description="Les membres enregistrent leur date avec `+birthday 24/08`, "
                    "le bot les souhaite automatiquement.",
        color=X_PURPLE)
    e.add_field(name="🔘 Statut", value="✅ Actif" if c.get("enabled") else "❌ Desactive", inline=True)
    e.add_field(name="📺 Salon d'annonce", value=chan_field(guild, c.get("channel_id")), inline=True)
    e.add_field(name="🎭 Role du jour", value=role_field(c.get("role_id")), inline=True)
    e.add_field(name="🕙 Heure d'annonce", value=f"{c.get('hour',10)} h", inline=True)
    e.add_field(name="👥 Dates enregistrees", value=str(len(data)), inline=True)
    e.add_field(name="💬 Message", value=f"`{c.get('message','')[:80]}`", inline=False)
    e.add_field(name="⌨️ Commandes",
                value="`+birthdays` `+birthday` `+birthdaylist` `+birthdayremove` `+nextbirthdays`",
                inline=False)
    e.set_footer(text="ModeraBot • Anniversaires")
    return e


class ModalBdCfg(discord.ui.Modal, title="🎂 Reglages des anniversaires"):
    salon = discord.ui.TextInput(label="ID du salon d'annonce", max_length=25)
    role = discord.ui.TextInput(label="ID du role donne le jour J", required=False, max_length=25)
    heure = discord.ui.TextInput(label="Heure d'annonce (0-23)", max_length=2, placeholder="10")
    message = discord.ui.TextInput(label="Message", style=discord.TextStyle.paragraph, max_length=500,
                                   placeholder="Joyeux anniversaire {user} !")

    def __init__(self, gid):
        super().__init__()
        self.gid = gid
        c = xget(gid, "birthdays")
        self.salon.default = str(c.get("channel_id") or "")
        self.role.default = str(c.get("role_id") or "")
        self.heure.default = str(c.get("hour", 10))
        self.message.default = c.get("message", "")

    async def on_submit(self, interaction: discord.Interaction):
        c = xget(self.gid, "birthdays")
        v = str(self.salon.value or "").strip()
        c["channel_id"] = int(v) if v.isdigit() else None
        r = str(self.role.value or "").strip()
        c["role_id"] = int(r) if r.isdigit() else None
        try:
            c["hour"] = min(23, max(0, int(str(self.heure.value).strip())))
        except Exception:
            pass
        c["message"] = str(self.message.value).strip() or "Joyeux anniversaire {user} !"
        xset(self.gid, "birthdays", c)
        await interaction.response.edit_message(embed=bd_embed(interaction.guild))


class BirthdayView(discord.ui.View):
    def __init__(self, ctx):
        super().__init__(timeout=300)
        self.ctx = ctx

    async def interaction_check(self, interaction: discord.Interaction):
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message(embed=err("Ce panneau n'est pas pour toi."), ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Reglages", emoji="⚙️", style=discord.ButtonStyle.primary)
    async def cfg(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ModalBdCfg(interaction.guild.id))

    @discord.ui.button(label="Activer / Desactiver", emoji="🔘", style=discord.ButtonStyle.success)
    async def toggle(self, interaction: discord.Interaction, button: discord.ui.Button):
        c = xget(interaction.guild.id, "birthdays")
        c["enabled"] = not c.get("enabled")
        xset(interaction.guild.id, "birthdays", c)
        await interaction.response.edit_message(embed=bd_embed(interaction.guild), view=self)

    @discord.ui.button(label="Fermer", emoji="✖️", style=discord.ButtonStyle.secondary)
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(view=None)
        self.stop()


def register_birthdays(bot):

    @bot.command(name="birthdays", aliases=["anniversaires", "birthdayconfig", "bdayconfig"])
    async def birthdays_cmd(ctx):
        if not is_admin(ctx.author):
            return await ctx.send(embed=err("Permission administrateur requise."))
        await ctx.send(embed=bd_embed(ctx.guild), view=BirthdayView(ctx))

    @bot.command(name="birthday", aliases=["anniversaire", "bday", "mondate"])
    async def birthday_cmd(ctx, date: str = None):
        c = xget(ctx.guild.id, "birthdays")
        if not c.get("enabled"):
            return await ctx.send(embed=err("Les anniversaires sont desactives (`+birthdays`)."))
        data = bday_load(ctx.guild.id)
        if not date:
            mien = data.get(str(ctx.author.id))
            if not mien:
                return await ctx.send(embed=warn("Tu n'as pas enregistre ta date. Exemple : `+birthday 24/08`"))
            return await ctx.send(embed=ok(f"Ta date enregistree : **{mien}**"))
        m = re.fullmatch(r"(\d{1,2})[/\-.](\d{1,2})", date.strip())
        if not m:
            return await ctx.send(embed=err("Format attendu : `JJ/MM`, par exemple `+birthday 24/08`"))
        jour, mois = int(m.group(1)), int(m.group(2))
        if not (1 <= jour <= 31 and 1 <= mois <= 12):
            return await ctx.send(embed=err("Date invalide."))
        data[str(ctx.author.id)] = f"{jour:02d}/{mois:02d}"
        bday_save(ctx.guild.id, data)
        await ctx.send(embed=ok(f"Anniversaire enregistre : **{jour:02d}/{mois:02d}**"))

    @bot.command(name="birthdaylist", aliases=["listanniversaires", "bdaylist"])
    async def birthdaylist_cmd(ctx):
        data = bday_load(ctx.guild.id)
        if not data:
            return await ctx.send(embed=warn("Aucune date enregistree."))
        lignes = []
        for uid, d in sorted(data.items(), key=lambda kv: (kv[1][3:], kv[1][:2])):
            m = ctx.guild.get_member(int(uid))
            if m:
                lignes.append(f"**{d}** — {m.display_name}")
        await ctx.send(embed=discord.Embed(title="🎂 Anniversaires du serveur",
                                           description="\n".join(lignes[:40]) or "Aucun membre",
                                           color=X_PURPLE))

    @bot.command(name="nextbirthdays", aliases=["prochainsanniversaires", "nextbday"])
    async def nextbirthdays_cmd(ctx):
        data = bday_load(ctx.guild.id)
        if not data:
            return await ctx.send(embed=warn("Aucune date enregistree."))
        today = datetime.now()
        rows = []
        for uid, d in data.items():
            m = ctx.guild.get_member(int(uid))
            if not m:
                continue
            try:
                jour, mois = int(d[:2]), int(d[3:5])
                prochain = datetime(today.year, mois, jour)
                if prochain < today:
                    prochain = datetime(today.year + 1, mois, jour)
                rows.append((prochain, m, d))
            except Exception:
                continue
        rows.sort(key=lambda r: r[0])
        lignes = [f"**{d}** — {m.display_name} · dans {(p - today).days} jour(s)" for p, m, d in rows[:10]]
        await ctx.send(embed=discord.Embed(title="🎂 Prochains anniversaires",
                                           description="\n".join(lignes) or "Aucun", color=X_PURPLE))

    @bot.command(name="birthdayremove", aliases=["supprimeranniversaire", "bdayremove"])
    async def birthdayremove_cmd(ctx, membre: discord.Member = None):
        cible = membre or ctx.author
        if membre and not is_admin(ctx.author):
            return await ctx.send(embed=err("Permission administrateur requise."))
        data = bday_load(ctx.guild.id)
        if data.pop(str(cible.id), None) is None:
            return await ctx.send(embed=err("Aucune date enregistree."))
        bday_save(ctx.guild.id, data)
        await ctx.send(embed=ok(f"Date supprimee pour {cible.mention}."))


# ===========================================================================
# ===========================================================================
#   CATEGORIE 11 — COMMANDES PERSONNALISEES
# ===========================================================================
# ===========================================================================

def cc_embed(guild):
    c = xget(guild.id, "customcmds")
    cmds = c.get("commands", [])
    e = discord.Embed(
        title="⌨️ Commandes personnalisees",
        description="Cree tes propres commandes : le bot repond un texte ou un embed.",
        color=X_BLUE)
    e.add_field(name="🔘 Statut", value="✅ Actif" if c.get("enabled") else "❌ Desactive", inline=True)
    e.add_field(name="🧹 Supprimer la commande", value="✅" if c.get("delete_trigger") else "❌", inline=True)
    e.add_field(name="📋 Commandes creees", value=str(len(cmds)), inline=True)
    if cmds:
        e.add_field(name="📝 Liste",
                    value=" ".join(f"`+{x['nom']}`" for x in cmds[:30]), inline=False)
    e.add_field(name="⌨️ Commandes",
                value="`+customcmd` `+ccadd` `+ccdel` `+cclist`", inline=False)
    e.set_footer(text="ModeraBot • Commandes personnalisees")
    return e


class ModalCcAdd(discord.ui.Modal, title="⌨️ Nouvelle commande"):
    nom = discord.ui.TextInput(label="Nom (sans le prefixe)", max_length=25, placeholder="regles")
    reponse = discord.ui.TextInput(label="Reponse", style=discord.TextStyle.paragraph, max_length=1800)
    titre = discord.ui.TextInput(label="Titre de l'embed (vide = texte simple)", required=False, max_length=100)
    couleur = discord.ui.TextInput(label="Couleur", required=False, max_length=7, placeholder="#5865F2")
    roles = discord.ui.TextInput(label="IDs de roles autorises (vide = tous)", required=False, max_length=300)

    def __init__(self, gid):
        super().__init__()
        self.gid = gid

    async def on_submit(self, interaction: discord.Interaction):
        c = xget(self.gid, "customcmds")
        cmds = c.get("commands", [])
        nom = re.sub(r"[^a-z0-9_-]", "", str(self.nom.value).strip().lower())
        if not nom:
            return await interaction.response.send_message(embed=err("Nom invalide."), ephemeral=True)
        if any(x["nom"] == nom for x in cmds):
            return await interaction.response.send_message(embed=err("Cette commande existe deja."), ephemeral=True)
        if len(cmds) >= 50:
            return await interaction.response.send_message(embed=err("50 commandes maximum."), ephemeral=True)
        cmds.append({
            "nom": nom,
            "reponse": str(self.reponse.value),
            "titre": str(self.titre.value or "").strip(),
            "couleur": str(self.couleur.value or "#5865F2").strip() or "#5865F2",
            "roles": [int(x) for x in re.findall(r"\d{5,25}", str(self.roles.value or ""))][:10],
        })
        c["commands"] = cmds
        xset(self.gid, "customcmds", c)
        await interaction.response.edit_message(embed=cc_embed(interaction.guild))


class CcRemove(discord.ui.Select):
    def __init__(self, cmds):
        super().__init__(placeholder="Commande a supprimer...",
                         options=[discord.SelectOption(label="+" + x["nom"][:99], value=str(i))
                                  for i, x in enumerate(cmds[:25])])

    async def callback(self, interaction: discord.Interaction):
        c = xget(interaction.guild.id, "customcmds")
        cmds = c.get("commands", [])
        i = int(self.values[0])
        if 0 <= i < len(cmds):
            nom = cmds.pop(i)["nom"]
            c["commands"] = cmds
            xset(interaction.guild.id, "customcmds", c)
            return await interaction.response.edit_message(embed=ok(f"`+{nom}` supprimee."), view=None)
        await interaction.response.edit_message(embed=err("Introuvable."), view=None)


class CustomCmdView(discord.ui.View):
    def __init__(self, ctx):
        super().__init__(timeout=300)
        self.ctx = ctx

    async def interaction_check(self, interaction: discord.Interaction):
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message(embed=err("Ce panneau n'est pas pour toi."), ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Creer une commande", emoji="➕", style=discord.ButtonStyle.primary)
    async def add(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ModalCcAdd(interaction.guild.id))

    @discord.ui.button(label="Supprimer", emoji="🗑️", style=discord.ButtonStyle.danger)
    async def rm(self, interaction: discord.Interaction, button: discord.ui.Button):
        cmds = xget(interaction.guild.id, "customcmds").get("commands", [])
        if not cmds:
            return await interaction.response.send_message(embed=err("Aucune commande."), ephemeral=True)
        view = discord.ui.View(timeout=120)
        view.add_item(CcRemove(cmds))
        await interaction.response.send_message(embed=warn("Choisis la commande a supprimer."),
                                                view=view, ephemeral=True)

    @discord.ui.button(label="Activer / Desactiver", emoji="🔘", style=discord.ButtonStyle.success)
    async def toggle(self, interaction: discord.Interaction, button: discord.ui.Button):
        c = xget(interaction.guild.id, "customcmds")
        c["enabled"] = not c.get("enabled")
        xset(interaction.guild.id, "customcmds", c)
        await interaction.response.edit_message(embed=cc_embed(interaction.guild), view=self)

    @discord.ui.button(label="Fermer", emoji="✖️", style=discord.ButtonStyle.secondary)
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(view=None)
        self.stop()


def register_customcmds(bot):

    @bot.command(name="customcmd", aliases=["customcommands", "cc", "commandesperso"])
    async def customcmd_cmd(ctx):
        if not is_admin(ctx.author):
            return await ctx.send(embed=err("Permission administrateur requise."))
        await ctx.send(embed=cc_embed(ctx.guild), view=CustomCmdView(ctx))

    @bot.command(name="ccadd", aliases=["addcc", "addcustomcmd"])
    async def ccadd_cmd(ctx, nom: str = None, *, reponse: str = None):
        if not is_admin(ctx.author):
            return await ctx.send(embed=err("Permission administrateur requise."))
        if not nom or not reponse:
            return await ctx.send(embed=err("Usage : `+ccadd nom Ta reponse`"))
        c = xget(ctx.guild.id, "customcmds")
        cmds = c.get("commands", [])
        nom = re.sub(r"[^a-z0-9_-]", "", nom.lower())
        if not nom:
            return await ctx.send(embed=err("Nom invalide."))
        if any(x["nom"] == nom for x in cmds):
            return await ctx.send(embed=err("Cette commande existe deja."))
        if len(cmds) >= 50:
            return await ctx.send(embed=err("50 commandes maximum."))
        cmds.append({"nom": nom, "reponse": reponse, "titre": "", "couleur": "#5865F2", "roles": []})
        c["commands"] = cmds
        xset(ctx.guild.id, "customcmds", c)
        await ctx.send(embed=ok(f"Commande `+{nom}` creee."))

    @bot.command(name="ccdel", aliases=["delcc", "delcustomcmd"])
    async def ccdel_cmd(ctx, nom: str = None):
        if not is_admin(ctx.author):
            return await ctx.send(embed=err("Permission administrateur requise."))
        if not nom:
            return await ctx.send(embed=err("Usage : `+ccdel nom`"))
        c = xget(ctx.guild.id, "customcmds")
        cmds = c.get("commands", [])
        nom = nom.lower().lstrip("+")
        restants = [x for x in cmds if x["nom"] != nom]
        if len(restants) == len(cmds):
            return await ctx.send(embed=err("Commande introuvable."))
        c["commands"] = restants
        xset(ctx.guild.id, "customcmds", c)
        await ctx.send(embed=ok(f"Commande `+{nom}` supprimee."))

    @bot.command(name="cclist", aliases=["listcc", "listcustomcmds"])
    async def cclist_cmd(ctx):
        await ctx.send(embed=cc_embed(ctx.guild))


async def cc_handle(message):
    if not message.guild or message.author.bot:
        return
    c = xget(message.guild.id, "customcmds")
    if not c.get("enabled") or not c.get("commands"):
        return
    try:
        prefixes = await bot.get_prefix(message)
    except Exception:
        prefixes = "+"
    if isinstance(prefixes, str):
        prefixes = [prefixes]
    used = next((p for p in prefixes if p and message.content.startswith(p)), None)
    if not used:
        return
    nom = message.content[len(used):].split(" ")[0].lower()
    entry = next((x for x in c["commands"] if x["nom"] == nom), None)
    if not entry:
        return
    roles = [int(r) for r in entry.get("roles", [])]
    if roles and not any(r.id in roles for r in message.author.roles) and not is_admin(message.author):
        return
    reponse = (entry.get("reponse") or "").replace("{user}", message.author.mention) \
        .replace("{username}", message.author.display_name) \
        .replace("{server}", message.guild.name) \
        .replace("{membercount}", str(message.guild.member_count))
    if entry.get("titre"):
        await message.channel.send(embed=discord.Embed(
            title=entry["titre"], description=reponse, color=color_of(entry.get("couleur", "#5865F2"))))
    else:
        await message.channel.send(reponse)
    if c.get("delete_trigger"):
        try:
            await message.delete()
        except Exception:
            pass


# ===========================================================================
#   TACHES DE FOND
# ===========================================================================

async def extras_loop():
    await bot.wait_until_ready()
    while not bot.is_closed():
        try:
            now = time.time()
            for guild in list(bot.guilds):
                c = xget(guild.id, "automsg")
                if c.get("enabled"):
                    changed = False
                    for m in c.get("messages", []):
                        if not m.get("enabled", True):
                            continue
                        if now - float(m.get("last", 0)) < int(m.get("interval_minutes", 60)) * 60:
                            continue
                        ch = guild.get_channel(int(m.get("channel", 0) or 0))
                        if not ch:
                            continue
                        try:
                            if m.get("titre"):
                                await ch.send(embed=discord.Embed(
                                    title=m["titre"], description=m.get("content", ""),
                                    color=color_of(m.get("couleur", "#5865F2"))))
                            else:
                                await ch.send(m.get("content", ""))
                            m["last"] = now
                            changed = True
                        except Exception:
                            continue
                    if changed:
                        xset(guild.id, "automsg", c)

                b = xget(guild.id, "birthdays")
                if b.get("enabled") and b.get("channel_id"):
                    maintenant = datetime.now()
                    if maintenant.hour == int(b.get("hour", 10)):
                        marque = xload(guild.id).get("_bday_done")
                        jour_cle = maintenant.strftime("%Y-%m-%d")
                        if marque != jour_cle:
                            data = bday_load(guild.id)
                            today = maintenant.strftime("%d/%m")
                            fetes = [guild.get_member(int(u)) for u, d in data.items() if d == today]
                            fetes = [m for m in fetes if m]
                            ch = guild.get_channel(int(b["channel_id"]))
                            if ch and fetes:
                                for m in fetes:
                                    try:
                                        await ch.send(embed=discord.Embed(
                                            title="🎂 Joyeux anniversaire !",
                                            description=(b.get("message") or "Joyeux anniversaire {user} !")
                                            .replace("{user}", m.mention)
                                            .replace("{username}", m.display_name)
                                            .replace("{server}", guild.name),
                                            color=X_PURPLE))
                                        if b.get("role_id"):
                                            role = guild.get_role(int(b["role_id"]))
                                            if role:
                                                await m.add_roles(role, reason="Anniversaire")
                                    except Exception:
                                        continue
                            full = xload(guild.id)
                            full["_bday_done"] = jour_cle
                            xsave(guild.id, full)
        except Exception:
            pass
        await asyncio.sleep(60)


# ===========================================================================
#   AIDE — liste des nouvelles categories
# ===========================================================================

EXTRA_HELP = [
    ("💰 Economie", "+economy",
     "`+balance` `+daily` `+work` `+pay` `+deposit` `+withdraw` `+rob` `+shop` "
     "`+buy` `+inventory` `+ecolb` `+addmoney` `+removemoney` `+resetmoney`"),
    ("🛡️ AutoMod Pro", "+automod",
     "`+badword` `+antiinvite` `+automodignore` `+automodlogs` `+automodtest`"),
    ("💡 Suggestions", "+suggestions",
     "`+suggest` `+approve` `+deny` `+suggestinfo` `+suggestreset`"),
    ("📊 Sondages", "+pollconfig",
     "`+pollpro` `+quickpoll` `+endpoll` `+pollresults`"),
    ("🔒 Protection", "+guard",
     "`+lock` `+unlock` `+lockall` `+unlockall` `+slowmode` `+panic` `+raidmode` `+agegate`"),
    ("📋 Candidatures", "+apply",
     "`+applysend` `+applyadd` `+applydel` `+applylist`"),
    ("🧨 Anti-nuke", "+antinuke",
     "`+antinukewl` `+antinukelogs`"),
    ("📒 Infractions", "+infractions",
     "`+addinfraction` `+delinfraction` `+clearinfractions` `+topinfractions`"),
    ("🔁 Messages automatiques", "+automessage",
     "`+automessageadd` `+automessagelist` `+automessagedel`"),
    ("🎂 Anniversaires", "+birthdays",
     "`+birthday` `+birthdaylist` `+nextbirthdays` `+birthdayremove`"),
    ("⌨️ Commandes personnalisees", "+customcmd",
     "`+ccadd` `+ccdel` `+cclist`"),
]


class ExtraHelpView(discord.ui.View):
    def __init__(self, ctx):
        super().__init__(timeout=180)
        self.ctx = ctx

    @discord.ui.select(placeholder="📚 Ouvrir un panneau...", options=[
        discord.SelectOption(label=t.split(" ", 1)[1], emoji=t.split(" ", 1)[0], value=p)
        for t, p, _ in EXTRA_HELP
    ])
    async def menu(self, interaction: discord.Interaction, select: discord.ui.Select):
        await interaction.response.send_message(
            embed=ok(f"Tape **{select.values[0]}** pour ouvrir ce panneau."), ephemeral=True)


def register_help(bot):

    @bot.command(name="modules", aliases=["extrahelp", "newcmds", "pluscommandes", "categories"])
    async def modules_cmd(ctx):
        e = discord.Embed(
            title="🧩 Modules supplementaires",
            description="Chaque categorie a son panneau de configuration interactif.",
            color=X_PURPLE)
        for titre, panel, cmds in EXTRA_HELP:
            e.add_field(name=f"{titre} — `{panel}`", value=cmds, inline=False)
        e.set_footer(text=f"ModeraBot • {sum(c.count('`') // 2 for _, _, c in EXTRA_HELP)} commandes ajoutees")
        await ctx.send(embed=e, view=ExtraHelpView(ctx))


# ===========================================================================
#   ECOUTEURS D'EVENEMENTS (n'ecrasent pas ceux d'app.py)
# ===========================================================================

def register_listeners(bot):

    @bot.listen("on_message")
    async def _extra_on_message(message):
        try:
            if await automod_check(message):
                return
        except Exception:
            pass
        try:
            await cc_handle(message)
        except Exception:
            pass

    @bot.listen("on_guild_channel_delete")
    async def _extra_channel_delete(channel):
        guild = channel.guild
        c = xget(guild.id, "antinuke")
        if not c.get("enabled") or not c.get("protect_channels"):
            return
        author = await an_audit_author(guild, discord.AuditLogAction.channel_delete)
        if author and not an_whitelisted(guild, author):
            await an_trigger(guild, author, "suppression de salons", int(c.get("max_channel_delete", 3)))

    @bot.listen("on_guild_role_delete")
    async def _extra_role_delete(role):
        guild = role.guild
        c = xget(guild.id, "antinuke")
        if not c.get("enabled") or not c.get("protect_roles"):
            return
        author = await an_audit_author(guild, discord.AuditLogAction.role_delete)
        if author and not an_whitelisted(guild, author):
            await an_trigger(guild, author, "suppression de roles", int(c.get("max_role_delete", 3)))

    @bot.listen("on_member_ban")
    async def _extra_member_ban(guild, user):
        c = xget(guild.id, "antinuke")
        if not c.get("enabled") or not c.get("protect_bans"):
            return
        author = await an_audit_author(guild, discord.AuditLogAction.ban, user.id)
        if author and author.id != user.id and not an_whitelisted(guild, author):
            await an_trigger(guild, author, "bans en rafale", int(c.get("max_ban", 3)))

    @bot.listen("on_member_join")
    async def _extra_antinuke_bot(member):
        try:
            if not member.bot:
                return
            c = xget(member.guild.id, "antinuke")
            if not c.get("enabled") or not c.get("anti_bot_add"):
                return
            author = await an_audit_author(member.guild, discord.AuditLogAction.bot_add, member.id)
            if author and an_whitelisted(member.guild, author):
                return
            await member.kick(reason="Anti-nuke : ajout de bot non autorise")
            await send_log(member.guild, "antinuke", discord.Embed(
                title="🤖 Bot bloque", color=X_RED,
                description=f"{member} a ete expulse (ajout par {author if author else 'inconnu'})."))
        except Exception:
            pass

    @bot.listen("on_member_join")
    async def _extra_on_join(member):
        try:
            c = xget(member.guild.id, "guard")
            if not c.get("agegate") and not c.get("raidmode"):
                return
            immune = {int(x) for x in c.get("immune_roles", [])}
            if immune and any(r.id in immune for r in member.roles):
                return
            jours = int(c.get("agegate_days", 7))
            age = (datetime.now(timezone.utc) - member.created_at).days
            if c.get("raidmode") and age < max(jours, 1):
                action = c.get("agegate_action", "kick")
            elif c.get("agegate") and age < jours:
                action = c.get("agegate_action", "kick")
            else:
                return
            motif = f"Compte trop recent ({age} j < {jours} j)"
            if action == "kick":
                try:
                    await member.kick(reason=motif)
                except Exception:
                    pass
            elif action == "ban":
                try:
                    await member.ban(reason=motif, delete_message_days=0)
                except Exception:
                    pass
            await send_log(member.guild, "guard", discord.Embed(
                title="👶 Compte recent bloque", color=X_ORANGE,
                description=f"{member} (`{member.id}`)\n{motif} → `{action}`"))
        except Exception:
            pass

    @bot.listen("on_ready")
    async def _extra_on_ready():
        try:
            bot.add_view(ApplyPanelView())
            bot.add_view(ApplyReviewView())
            bot.add_view(SuggestionVoteView())
        except Exception:
            pass


# ===========================================================================
#   PONT VERS LES REGLAGES DEJA GERES PAR APP.PY
#   (modo, join to create, autoreact, piconly, soutien, tag)
#   Ces reglages vivent dans app.py : on lit et on ecrit ses propres
#   structures, sans rien modifier dans son code.
# ===========================================================================

def _main():
    import sys
    return sys.modules.get("__main__")


def _mfile(key):
    m = _main()
    files = getattr(m, "FILES", {}) if m else {}
    return files.get(key)


def _mload(key):
    m = _main()
    path = _mfile(key)
    if not m or not path:
        return {}
    try:
        return m.jload(path)
    except Exception:
        return {}


def _msave(key, data):
    m = _main()
    path = _mfile(key)
    if not m or not path:
        return
    try:
        m.jsave(path, data)
    except Exception:
        pass


def _mdict(name):
    m = _main()
    d = getattr(m, name, None) if m else None
    return d if isinstance(d, dict) else None


def bridge_read(gid):
    gid = str(gid)
    out = {}

    modo = _mload("modo").get(gid, {})
    out["modo"] = {
        "roles": [str(r) for r in modo.get("modo_roles", [])],
        "log_channel": str(modo["log_channel"]) if modo.get("log_channel") else None,
    }

    jtc = (_mdict("_jtc_config") or {}).get(gid, {})
    out["jtc"] = {
        "trigger_id": str(jtc["trigger_id"]) if jtc.get("trigger_id") else None,
        "category_id": str(jtc["category_id"]) if jtc.get("category_id") else None,
        "name": jtc.get("name", "Salon de {username}"),
    }

    ar = (_mdict("_autoreact_cfg") or {}).get(gid, {})
    out["autoreact"] = {"salons": [{"channel": str(cid), "emojis": " ".join(ems)}
                                   for cid, ems in ar.items()]}

    po = (_mdict("_piconly_cfg") or {}).get(gid, set())
    out["piconly"] = {"channels": [str(c) for c in po]}

    so = (_mdict("_soutien_cfg") or {}).get(gid, {})
    out["soutien"] = {
        "role_id": str(so["role_id"]) if so.get("role_id") else None,
        "server_link": so.get("server_link", ""),
    }

    tag = (_mdict("_tag_cfg") or {}).get(gid)
    out["tag"] = {"role_id": str(tag) if tag else None}
    return out


def bridge_write(gid, body):
    gid = str(gid)
    saved = []

    if "modo" in body:
        b = body["modo"] or {}
        data = _mload("modo")
        conf = data.setdefault(gid, {})
        conf["modo_roles"] = _ids(b.get("roles"), 25)
        ch = _i(b.get("log_channel"))
        if ch:
            conf["log_channel"] = ch
        else:
            conf.pop("log_channel", None)
        _msave("modo", data)
        saved.append("modo")

    if "jtc" in body:
        b = body["jtc"] or {}
        d = _mdict("_jtc_config")
        if d is not None:
            trigger = _i(b.get("trigger_id"))
            if trigger:
                d[gid] = {
                    "trigger_id": trigger,
                    "category_id": _i(b.get("category_id")),
                    "name": _s(b.get("name"), "Salon de {username}", 60) or "Salon de {username}",
                }
            else:
                d.pop(gid, None)
            saved.append("jtc")

    if "autoreact" in body:
        b = body["autoreact"] or {}
        d = _mdict("_autoreact_cfg")
        if d is not None:
            entry = {}
            for row in (b.get("salons") or [])[:25]:
                ch = _i((row or {}).get("channel"))
                ems = [e for e in _s(row.get("emojis"), "", 120).split() if e][:5]
                if ch and ems:
                    entry[str(ch)] = ems
            if entry:
                d[gid] = entry
            else:
                d.pop(gid, None)
            saved.append("autoreact")

    if "piconly" in body:
        b = body["piconly"] or {}
        d = _mdict("_piconly_cfg")
        if d is not None:
            ids = set(_ids(b.get("channels"), 50))
            if ids:
                d[gid] = ids
            else:
                d.pop(gid, None)
            saved.append("piconly")

    if "soutien" in body:
        b = body["soutien"] or {}
        d = _mdict("_soutien_cfg")
        if d is not None:
            rid = _i(b.get("role_id"))
            if rid:
                d[gid] = {"role_id": rid, "server_link": _s(b.get("server_link"), "", 100)}
            else:
                d.pop(gid, None)
            saved.append("soutien")

    if "tag" in body:
        b = body["tag"] or {}
        d = _mdict("_tag_cfg")
        if d is not None:
            rid = _i(b.get("role_id"))
            if rid:
                d[gid] = rid
            else:
                d.pop(gid, None)
            saved.append("tag")

    return saved


# ===========================================================================
#   API DASHBOARD — /api/guild/<gid>/extras
# ===========================================================================

def _s(v, default="", maxlen=200):
    if v is None:
        return default
    return str(v)[:maxlen]


def _i(v, default=None):
    try:
        n = int(str(v).strip())
        return n if n else (default if str(v).strip() not in ("0",) else 0)
    except Exception:
        return default


def _b(v, default=False):
    if v is None:
        return default
    if isinstance(v, bool):
        return v
    return str(v).lower() in ("1", "true", "on", "yes", "oui")


def _n(v, default=0, lo=0, hi=10 ** 9):
    try:
        return max(lo, min(hi, int(float(v))))
    except Exception:
        return default


def _ids(v, limit=50):
    out = []
    for x in (v or []):
        try:
            out.append(int(x))
        except Exception:
            continue
    return out[:limit]


def _auth(guild_id):
    """Reutilise le controle d'acces du dashboard d'app.py si disponible."""
    import sys
    main = sys.modules.get("__main__")
    fn = getattr(main, "_dash_auth", None)
    if fn:
        try:
            return fn(guild_id)
        except Exception:
            return (None, None)
    guild = bot.get_guild(int(guild_id)) if bot and str(guild_id).isdigit() else None
    return (guild, None)


def register_api(app):
    from flask import request, jsonify

    @app.route("/api/guild/<guild_id>/extras", methods=["GET", "POST"])
    def api_guild_extras(guild_id):
        guild, member = _auth(guild_id)
        if not guild:
            return jsonify({"error": "forbidden"}), 403
        gid = str(guild.id)

        if request.method == "GET":
            cfg = xload(gid)
            try:
                cfg.update(bridge_read(gid))
            except Exception:
                pass
            bank = bank_load(gid)
            inf = inf_load(gid)
            cfg["_stats"] = {
                "infractions": sum(len(v) for v in inf.values()),
                "membres_sanctionnes": len(inf),
                "anniversaires": len(bday_load(gid)),
                "automessages": len(cfg.get("automsg", {}).get("messages", [])),
                "customcmds": len(cfg.get("customcmds", {}).get("commands", [])),
                "comptes": len(bank),
                "argent_total": sum((u.get("cash", 0) + u.get("bank", 0)) for u in bank.values()),
                "articles": len(cfg.get("economy", {}).get("shop", [])),
                "postes": len(cfg.get("apply", {}).get("postes", [])),
                "badwords": len(cfg.get("automod", {}).get("badwords", [])),
                "suggestions": cfg.get("suggestions", {}).get("counter", 0),
                "salons_verrouilles": len(cfg.get("guard", {}).get("locked_channels", [])),
            }
            cfg["_meta"] = {
                "voice": [{"id": str(c.id), "name": c.name} for c in guild.voice_channels],
            }
            return jsonify({"ok": True, "config": cfg})

        body = request.get_json(silent=True) or {}
        cfg = xload(gid)
        saved = []

        if "economy" in body:
            b = body["economy"] or {}
            c = cfg["economy"]
            c["enabled"] = _b(b.get("enabled"))
            c["symbole"] = _s(b.get("symbole"), "🪙", 8) or "🪙"
            c["monnaie"] = _s(b.get("monnaie"), "coins", 20) or "coins"
            c["start_balance"] = _n(b.get("start_balance"), 100)
            c["daily_amount"] = _n(b.get("daily_amount"), 250)
            c["work_min"] = _n(b.get("work_min"), 50)
            c["work_max"] = max(c["work_min"], _n(b.get("work_max"), 300))
            c["work_cooldown"] = _n(b.get("work_cooldown"), 3600, 0, 604800)
            c["rob_enabled"] = _b(b.get("rob_enabled"))
            c["rob_cooldown"] = _n(b.get("rob_cooldown"), 7200, 0, 604800)
            c["rob_success"] = _n(b.get("rob_success"), 40, 0, 100)
            c["rob_max_percent"] = _n(b.get("rob_max_percent"), 20, 1, 100)
            c["log_channel"] = _i(b.get("log_channel"))
            shop = []
            for it in (b.get("shop") or [])[:25]:
                nom = _s((it or {}).get("nom"), "", 40).strip()
                if not nom:
                    continue
                shop.append({
                    "nom": nom,
                    "prix": _n(it.get("prix"), 0),
                    "description": _s(it.get("description"), "", 100),
                    "role": _s(it.get("role"), "", 25) or None,
                    "stock": _n(it.get("stock"), -1, -1, 10 ** 6),
                })
            c["shop"] = shop
            saved.append("economy")

        if "automod" in body:
            b = body["automod"] or {}
            c = cfg["automod"]
            c["enabled"] = _b(b.get("enabled"))
            c["log_channel"] = _i(b.get("log_channel"))
            c["badwords"] = [_s(w, "", 60).strip().lower() for w in (b.get("badwords") or []) if _s(w).strip()][:200]
            for key, default in (("badword_action", "delete"), ("invite_action", "delete")):
                a = _s(b.get(key), default, 10).lower()
                c[key] = a if a in ACTIONS else default
            c["anti_invite"] = _b(b.get("anti_invite"))
            c["anti_zalgo"] = _b(b.get("anti_zalgo"))
            c["anti_spoiler"] = _b(b.get("anti_spoiler"))
            c["max_lines"] = _n(b.get("max_lines"), 0, 0, 500)
            c["max_attachments"] = _n(b.get("max_attachments"), 0, 0, 10)
            c["ignored_channels"] = _ids(b.get("ignored_channels"))
            c["ignored_roles"] = _ids(b.get("ignored_roles"))
            c["warn_message"] = _s(b.get("warn_message"), "", 300)
            saved.append("automod")

        if "suggestions" in body:
            b = body["suggestions"] or {}
            c = cfg["suggestions"]
            c["enabled"] = _b(b.get("enabled"))
            c["channel_id"] = _i(b.get("channel_id"))
            c["log_channel"] = _i(b.get("log_channel"))
            c["up_emoji"] = _s(b.get("up_emoji"), "👍", 32) or "👍"
            c["down_emoji"] = _s(b.get("down_emoji"), "👎", 32) or "👎"
            c["anonymous"] = _b(b.get("anonymous"))
            c["threads"] = _b(b.get("threads"), True)
            c["auto_delete_cmd"] = _b(b.get("auto_delete_cmd"), True)
            c["min_length"] = _n(b.get("min_length"), 10, 1, 2000)
            saved.append("suggestions")

        if "polls" in body:
            b = body["polls"] or {}
            c = cfg["polls"]
            c["enabled"] = _b(b.get("enabled"))
            c["channel_id"] = _i(b.get("channel_id"))
            c["default_duration"] = _s(b.get("default_duration"), "1h", 10) or "1h"
            c["color"] = _s(b.get("color"), "#5865F2", 7) or "#5865F2"
            c["allow_multi"] = _b(b.get("allow_multi"))
            c["show_voters"] = _b(b.get("show_voters"))
            c["ping_role"] = _i(b.get("ping_role"))
            saved.append("polls")

        if "guard" in body:
            b = body["guard"] or {}
            c = cfg["guard"]
            c["raidmode"] = _b(b.get("raidmode"))
            c["lock_message"] = _s(b.get("lock_message"), "", 300)
            c["unlock_message"] = _s(b.get("unlock_message"), "", 300)
            c["log_channel"] = _i(b.get("log_channel"))
            c["agegate"] = _b(b.get("agegate"))
            c["agegate_days"] = _n(b.get("agegate_days"), 7, 0, 3650)
            a = _s(b.get("agegate_action"), "kick", 6).lower()
            c["agegate_action"] = a if a in ("kick", "ban", "log") else "kick"
            c["auto_slowmode"] = _n(b.get("auto_slowmode"), 0, 0, 21600)
            c["immune_roles"] = _ids(b.get("immune_roles"))
            saved.append("guard")

        if "apply" in body:
            b = body["apply"] or {}
            c = cfg["apply"]
            c["enabled"] = _b(b.get("enabled"))
            c["panel_channel"] = _i(b.get("panel_channel"))
            c["review_channel"] = _i(b.get("review_channel"))
            c["accepted_role"] = _i(b.get("accepted_role"))
            c["log_channel"] = _i(b.get("log_channel"))
            c["titre"] = _s(b.get("titre"), "📋 Candidatures", 100)
            c["description"] = _s(b.get("description"), "", 1000)
            c["couleur"] = _s(b.get("couleur"), "#5865F2", 7) or "#5865F2"
            c["cooldown_hours"] = _n(b.get("cooldown_hours"), 24, 0, 8760)
            postes = []
            for p in (b.get("postes") or [])[:25]:
                nom = _s((p or {}).get("nom"), "", 40).strip()
                if not nom:
                    continue
                postes.append({
                    "nom": nom,
                    "emoji": _s(p.get("emoji"), "📄", 8) or "📄",
                    "description": _s(p.get("description"), "", 90),
                    "questions": [_s(q, "", 45) for q in (p.get("questions") or []) if _s(q).strip()][:5]
                                 or ["Pourquoi toi ?"],
                })
            c["postes"] = postes
            saved.append("apply")

        if "antinuke" in body:
            b = body["antinuke"] or {}
            c = cfg["antinuke"]
            c["enabled"] = _b(b.get("enabled"))
            c["log_channel"] = _i(b.get("log_channel"))
            a = _s(b.get("punish"), "strip", 6).lower()
            c["punish"] = a if a in ("strip", "kick", "ban") else "strip"
            c["window"] = _n(b.get("window"), 60, 5, 3600)
            c["max_channel_delete"] = _n(b.get("max_channel_delete"), 3, 1, 100)
            c["max_role_delete"] = _n(b.get("max_role_delete"), 3, 1, 100)
            c["max_ban"] = _n(b.get("max_ban"), 3, 1, 100)
            c["max_kick"] = _n(b.get("max_kick"), 5, 1, 100)
            for k in ("protect_channels", "protect_roles", "protect_bans", "protect_kicks", "anti_bot_add"):
                c[k] = _b(b.get(k))
            c["whitelist_roles"] = _ids(b.get("whitelist_roles"))
            c["whitelist_users"] = _ids(b.get("whitelist_users"))
            saved.append("antinuke")

        if "infractions" in body:
            b = body["infractions"] or {}
            c = cfg["infractions"]
            c["enabled"] = _b(b.get("enabled"))
            c["log_channel"] = _i(b.get("log_channel"))
            c["dm_user"] = _b(b.get("dm_user"), True)
            c["expire_days"] = _n(b.get("expire_days"), 0, 0, 3650)
            c["auto_mute_at"] = _n(b.get("auto_mute_at"), 3, 0, 100)
            c["auto_kick_at"] = _n(b.get("auto_kick_at"), 0, 0, 100)
            c["auto_ban_at"] = _n(b.get("auto_ban_at"), 5, 0, 100)
            saved.append("infractions")

        if "automsg" in body:
            b = body["automsg"] or {}
            c = cfg["automsg"]
            c["enabled"] = _b(b.get("enabled"))
            anciens = {int(m.get("channel", 0) or 0): m.get("last", 0) for m in c.get("messages", [])}
            msgs = []
            for m in (b.get("messages") or [])[:15]:
                ch = _i((m or {}).get("channel"))
                contenu = _s(m.get("content"), "", 1800)
                if not ch or not contenu.strip():
                    continue
                msgs.append({
                    "channel": ch,
                    "interval_minutes": _n(m.get("interval_minutes"), 60, 5, 43200),
                    "content": contenu,
                    "titre": _s(m.get("titre"), "", 100),
                    "couleur": _s(m.get("couleur"), "#5865F2", 7) or "#5865F2",
                    "enabled": _b(m.get("enabled"), True),
                    "last": anciens.get(ch, 0),
                })
            c["messages"] = msgs
            saved.append("automsg")

        if "birthdays" in body:
            b = body["birthdays"] or {}
            c = cfg["birthdays"]
            c["enabled"] = _b(b.get("enabled"))
            c["channel_id"] = _i(b.get("channel_id"))
            c["role_id"] = _i(b.get("role_id"))
            c["hour"] = _n(b.get("hour"), 10, 0, 23)
            c["message"] = _s(b.get("message"), "Joyeux anniversaire {user} !", 500)
            saved.append("birthdays")

        if "customcmds" in body:
            b = body["customcmds"] or {}
            c = cfg["customcmds"]
            c["enabled"] = _b(b.get("enabled"))
            c["delete_trigger"] = _b(b.get("delete_trigger"))
            cmds, vus = [], set()
            for x in (b.get("commands") or [])[:50]:
                nom = re.sub(r"[^a-z0-9_-]", "", _s((x or {}).get("nom"), "", 25).lower())
                rep = _s(x.get("reponse"), "", 1800)
                if not nom or nom in vus or not rep.strip():
                    continue
                vus.add(nom)
                cmds.append({
                    "nom": nom,
                    "reponse": rep,
                    "titre": _s(x.get("titre"), "", 100),
                    "couleur": _s(x.get("couleur"), "#5865F2", 7) or "#5865F2",
                    "roles": _ids(x.get("roles"), 10),
                })
            c["commands"] = cmds
            saved.append("customcmds")

        try:
            saved += bridge_write(gid, body)
        except Exception:
            pass

        xsave(gid, cfg)
        return jsonify({"ok": True, "saved": saved})


# ===========================================================================
#   POINT D'ENTREE
# ===========================================================================

class _SafeBot:
    """Proxy autour du bot : ignore proprement les noms/alias deja pris par app.py
    au lieu de faire planter le demarrage."""

    def __init__(self, real):
        self._real = real

    def __getattr__(self, name):
        return getattr(self._real, name)

    def command(self, *args, **kwargs):
        used = set(self._real.all_commands.keys())
        name = kwargs.get("name")
        aliases = [a for a in (kwargs.get("aliases") or []) if a not in used]
        if aliases != (kwargs.get("aliases") or []):
            kwargs["aliases"] = aliases
        if name in used:
            kwargs["name"] = "x" + name
            print(f"[modules_extra] '+{name}' existe deja dans app.py "
                  f"-> la nouvelle commande devient '+x{name}'")
        return self._real.command(*args, **kwargs)


def setup(bot_instance, app_instance=None):
    """A appeler depuis app.py juste avant bot.run(TOKEN)."""
    global bot, app
    bot = bot_instance
    app = app_instance
    safe = _SafeBot(bot_instance)

    register_economy(safe)
    register_automod(safe)
    register_suggestions(safe)
    register_polls(safe)
    register_guard(safe)
    register_apply(safe)
    register_antinuke(safe)
    register_infractions(safe)
    register_automsg(safe)
    register_birthdays(safe)
    register_customcmds(safe)
    register_help(safe)
    register_listeners(bot)

    try:
        main_mod = __import__("sys").modules.get("__main__")
        for oid in (getattr(main_mod, "OWNER_IDS", None) or []):
            OWNER_IDS_EXTRA.add(str(oid))
    except Exception:
        pass

    try:
        bot.loop.create_task(extras_loop())
    except Exception:
        @bot.listen("on_ready")
        async def _extra_start_loop():
            if not getattr(bot, "_extras_loop_started", False):
                bot._extras_loop_started = True
                bot.loop.create_task(extras_loop())

    if app is not None:
        try:
            register_api(app)
        except Exception as e:
            print(f"[modules_extra] API non enregistree : {e}")

    print("[modules_extra] 11 categories et 75+ commandes ajoutees.")
    return bot
