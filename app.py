"""

ModeraBot v4 — Style SnowayBot

Toutes les commandes configurables via Select Menu + Modals Discord

Préfixe: +

Auto-correction intelligente des typos → exécution directe de la vraie commande

"""

import discord

from discord import app_commands

from discord.ext import commands, tasks

import json, os, asyncio, random, re, time, collections, logging, string, hashlib

from datetime import datetime, timedelta

from flask import Flask, request, jsonify, redirect, session

from threading import Thread

import requests

from difflib import get_close_matches

import platform
import io
import time as _time

_BOT_START_TIME = _time.time()


# ══════════════════════════════════════════

# CONFIG & BOT

# ══════════════════════════════════════════

with open("config.json", "r") as f:

    CONFIG = json.load(f)

TOKEN = CONFIG["token"]

# Proprietaire principal du bot (prioritaire sur config.json)
MAIN_OWNER_ID = "1533483654888820818"

owner_id_str = CONFIG.get("owner_id", "")

_cfg_owners = [oid.strip() for oid in (owner_id_str if isinstance(owner_id_str, str) else str(owner_id_str or "")).split(',') if oid.strip()]

# Fondateurs / co-owners supplementaires
FOUNDER_IDS = ["1234265378314784782"]

# L'owner principal remplace celui de config.json ; ajoute d'autres IDs dans FOUNDER_IDS.
OWNER_IDS = [MAIN_OWNER_ID] + [f for f in FOUNDER_IDS if f != MAIN_OWNER_ID]

intents = discord.Intents.default()

intents.members = True

intents.presences = True

intents.message_content = True

intents.guilds = True

# ══════════════════════════════════════════

# PREFIXES DYNAMIQUES PAR SERVEUR

# ══════════════════════════════════════════

DEFAULT_PREFIX = "+"

_prefix_cache = {}  # guild_id (int) → prefix (str)

def _load_prefixes():

    global _prefix_cache

    data = {}

    try:

        with open("prefixes.json", "r", encoding="utf-8") as f:

            data = json.load(f)

    except: pass

    _prefix_cache = {int(k): v for k, v in data.items()}

def _save_prefixes():

    with open("prefixes.json", "w", encoding="utf-8") as f:

        json.dump({str(k): v for k, v in _prefix_cache.items()}, f, indent=4)

def get_prefix(bot, message):

    if message.guild:

        pfx = _prefix_cache.get(message.guild.id, DEFAULT_PREFIX)

    else:

        pfx = DEFAULT_PREFIX

    # Permet aussi de mentionner le bot pour toutes commandes

    return commands.when_mentioned_or(pfx)(bot, message)

_load_prefixes()

# Aucun message du bot ne notifie un rôle ni @everyone.
# Les rôles restent affichés en bleu (« @Membre »), mais personne n'est ping.
# Les mentions de membres continuent de fonctionner (ticket, bienvenue, sanctions).
MENTIONS_PAR_DEFAUT = discord.AllowedMentions(
    everyone=False,      # pas de @everyone / @here
    roles=False,         # pas de ping de rôle
    users=True,          # les membres restent mentionnables
    replied_user=False,  # répondre à quelqu'un ne le ping pas
)

# A l'ouverture d'un ticket, on notifie exprès : le membre concerne ET les roles
# staff charges de ce type de ticket. C'est la seule exception au silence general.
MENTIONS_TICKET = discord.AllowedMentions(everyone=False, roles=True, users=True)


# Dans un salon de logs, personne n'est notifie : ni role, ni @everyone, ni membre.
# Les mentions restent affichees en bleu et cliquables, elles ne declenchent
# simplement aucune notification.
MENTIONS_LOGS = discord.AllowedMentions.none()

bot = commands.Bot(command_prefix=get_prefix, intents=intents, help_command=None,
                   allowed_mentions=MENTIONS_PAR_DEFAUT)

# ══════════════════════════════════════════

# FICHIERS

# ══════════════════════════════════════════

for folder in ["server_configs", "level_configs"]:

    os.makedirs(folder, exist_ok=True)

FILES = {

    "vip": "vip_codes.json", "antilink": "antilink_config.json",

    "welcome": "welcome.json", "depart": "depart.json",

    "modo": "modo_config.json", "ticket_select": "ticket_select.json",

    "premium": "premium.json", "premium_logs": "premium_logs.json",

    "giveaway_cfg": "giveaway_config.json", "antiraid_cfg": "antiraid_config.json",

    "joinmp": "joinmp.json", "premium_welcome": "premium_welcome.json",

    "prefixes": "prefixes.json", "antibot": "antibot_config.json",

}

for key, path in FILES.items():

    if not os.path.exists(path):

        default = {"codes": {}, "users": {}} if "premium" in key else {"activations": []} if "logs" in key else {}

        with open(path, "w") as f:

            json.dump(default, f, indent=4)

# ══════════════════════════════════════════

# CONSTANTES

# ══════════════════════════════════════════

PREMIUM_LINK = "https://discord.gg/DfAe8kQKZ"

GUILD_ID = 1445819814894374954

LOG_CHANNEL_ID = 1452792998466162739

PREMIUM_ROLE_ID = 1454235837213577329

C_BLUE   = 0x5865F2

C_GREEN  = 0x57F287

C_RED    = 0xED4245

C_ORANGE = 0xFEE75C

C_DARK   = 0x2B2D31

C_GOLD   = 0xFFD700


# ─── Garde-fous (catégories & URLs) ───────────────────────────────────────────

def _as_category(guild, value):
    """Retourne la CategoryChannel correspondante, ou None si l'ID n'en est pas une."""
    if not guild or not value:
        return None
    try:
        ch = guild.get_channel(int(value))
    except Exception:
        return None
    return ch if isinstance(ch, discord.CategoryChannel) else None


def _as_text_channel(guild, value):
    """Retourne le salon texte correspondant, ou None si l'ID n'en est pas un."""
    if not guild or not value:
        return None
    try:
        ch = guild.get_channel(int(value))
    except Exception:
        return None
    return ch if hasattr(ch, "send") else None


_URL_RE = re.compile(r"^(https?|attachment)://\S+$", re.IGNORECASE)


def _valid_url(u):
    """Vrai si l'URL est utilisable par Discord (evite l'erreur 50035 'Not a well formed URL')."""
    return isinstance(u, str) and bool(_URL_RE.match(u.strip()))


def _install_url_guard():
    """Ignore silencieusement les URLs invalides passees aux embeds (images / icones)."""
    if getattr(discord, "_modera_url_guard", False):
        return

    _set_image = discord.Embed.set_image
    _set_thumb = discord.Embed.set_thumbnail
    _set_author = discord.Embed.set_author
    _set_footer = discord.Embed.set_footer

    def set_image(self, *, url=None):
        if url is not None and not _valid_url(str(url)):
            url = None
        return _set_image(self, url=url)

    def set_thumbnail(self, *, url=None):
        if url is not None and not _valid_url(str(url)):
            url = None
        return _set_thumb(self, url=url)

    def set_author(self, *, name, url=None, icon_url=None):
        if icon_url is not None and not _valid_url(str(icon_url)):
            icon_url = None
        if url is not None and not _valid_url(str(url)):
            url = None
        return _set_author(self, name=name, url=url, icon_url=icon_url)

    def set_footer(self, *, text=None, icon_url=None):
        if icon_url is not None and not _valid_url(str(icon_url)):
            icon_url = None
        return _set_footer(self, text=text, icon_url=icon_url)

    discord.Embed.set_image = set_image
    discord.Embed.set_thumbnail = set_thumbnail
    discord.Embed.set_author = set_author
    discord.Embed.set_footer = set_footer
    discord._modera_url_guard = True


_install_url_guard()


# ─── Images Discord CDN : anti-expiration ─────────────────────────────────────
# Les liens cdn.discordapp.com/attachments/... sont signes (?ex=&is=&hm=) et
# meurent au bout de ~24 h. Un panel/embed qui reste poste affiche alors une
# image cassee. On telecharge donc l'image et on la joint au message : une piece
# jointe appartient au message, Discord la re-signe tout seul, a vie.

_CDN_ATTACH_RE = re.compile(
    r"^https?://(?:cdn\.discordapp\.com|media\.discordapp\.net)/attachments/",
    re.IGNORECASE
)

_MEDIA_MAX_BYTES = 8 * 1024 * 1024   # marge sous la limite d'upload Discord


def _is_expiring_cdn(url):
    """Vrai pour un lien de piece jointe Discord signe (donc perissable)."""
    if not isinstance(url, str):
        return False
    return bool(_CDN_ATTACH_RE.match(url.strip())) and "hm=" in url


_MEDIA_CACHE = {}          # cle (URL sans signature) -> (timestamp, bytes)
_MEDIA_CACHE_TTL = 3600    # 1 h


def _media_key(url):
    return url.split("?")[0]


async def _fetch_media(url):
    """Telecharge une image (None si trop lourde, injoignable ou pas une image)."""
    key = _media_key(url)
    hit = _MEDIA_CACHE.get(key)
    if hit and (time.time() - hit[0]) < _MEDIA_CACHE_TTL:
        return hit[1]
    data = await _fetch_media_raw(url)
    if data:
        if len(_MEDIA_CACHE) > 20:
            _MEDIA_CACHE.clear()
        _MEDIA_CACHE[key] = (time.time(), data)
    return data


async def _fetch_media_raw(url):
    """Telechargement effectif, sans cache."""
    try:
        import aiohttp
        timeout = aiohttp.ClientTimeout(total=15)
        async with aiohttp.ClientSession(timeout=timeout) as sess:
            async with sess.get(url) as resp:
                if resp.status != 200:
                    return None
                ctype = (resp.headers.get("Content-Type") or "").lower()
                if not ctype.startswith("image/") and not ctype.startswith("video/"):
                    return None
                length = resp.headers.get("Content-Length")
                if length and int(length) > _MEDIA_MAX_BYTES:
                    return None
                data = await resp.read()
                if len(data) > _MEDIA_MAX_BYTES:
                    return None
                return data
    except Exception:
        return None


def _media_filename(url, fallback):
    """Nom de fichier propre a partir de l'URL (sans les parametres de signature)."""
    try:
        name = url.split("?")[0].rsplit("/", 1)[-1]
        name = re.sub(r"[^A-Za-z0-9._-]", "_", name)
        if "." in name and 3 <= len(name) <= 60:
            return name
    except Exception:
        pass
    return fallback


async def _pin_embed_media(kw):
    """Convertit les images CDN perissables des embeds en pieces jointes."""
    if kw.get("file") is not None or kw.get("files"):
        return  # l'appelant gere deja ses fichiers, on ne touche a rien
    embeds = kw.get("embeds") or ([kw["embed"]] if kw.get("embed") is not None else [])
    if not embeds:
        return

    files = []
    for n, em in enumerate(embeds):
        for kind in ("image", "thumbnail"):
            try:
                url = getattr(em, kind).url
            except Exception:
                url = None
            if not _is_expiring_cdn(url):
                continue
            data = await _fetch_media(url)
            if not data:
                continue  # on garde le lien d'origine, valable ~24 h
            fname = _media_filename(url, f"{kind}{n}.png")
            fname = f"{n}_{kind}_{fname}"[:80]
            files.append(discord.File(io.BytesIO(data), filename=fname))
            getattr(em, f"set_{kind}")(url=f"attachment://{fname}")

    if files:
        kw["files"] = files


TICKET_FOOTER = f"Propulsé par ModeraBot • {PREMIUM_LINK.replace('https://', '')}"


def _stamp_ticket_embed(embed, suffix=None):
    """Petit pied de page + horodatage en bas de chaque embed de ticket."""
    try:
        text = TICKET_FOOTER if not suffix else f"{TICKET_FOOTER} • {suffix}"
        embed.set_footer(text=text)
        embed.timestamp = discord.utils.utcnow()
    except Exception:
        pass
    return embed


# ─── Container V2 Helper ──────────────────────────────────────────────────────
# Tous les boutons / menus de sélection sont automatiquement rendus DANS un
# Container Discord Components V2 (l'embed devient le contenu du container).

def _cv2_flags():
    """Retourne les flags pour activer le mode Container V2 (composants Discord V2)."""
    try:
        return discord.MessageFlags(components_v2=True)
    except Exception:
        return None


def _v2_available():
    """Vrai si la version de discord.py installée supporte les Components V2."""
    return all(hasattr(discord.ui, n) for n in ("LayoutView", "Container", "TextDisplay", "ActionRow"))


def _v2_rows(items):
    """Range les boutons/menus en ActionRow (5 boutons max par ligne, 1 menu par ligne)."""
    rows, cur = [], None
    for it in items:
        if isinstance(it, discord.ui.Button):
            if cur is None or len(cur.children) >= 5:
                cur = discord.ui.ActionRow()
                rows.append(cur)
            cur.add_item(it)
        else:
            r = discord.ui.ActionRow()
            r.add_item(it)
            rows.append(r)
            cur = None
    return rows[:5]


def _v2_container(embed=None, rows=None, accent=None):
    """Construit un Container V2 à partir d'un embed classique + des lignes de composants."""
    colour = accent
    if colour is None and embed is not None:
        colour = embed.colour
    if colour is None:
        colour = discord.Colour(C_BLUE)
    try:
        cont = discord.ui.Container(accent_colour=colour)
    except Exception:
        cont = discord.ui.Container()

    head = []
    if embed is not None:
        try:
            if embed.author and embed.author.name:
                head.append(f"-# {embed.author.name}")
        except Exception:
            pass
        if embed.title:
            head.append(f"## [{embed.title}]({embed.url})" if embed.url else f"## {embed.title}")
        if embed.description:
            head.append(str(embed.description))

    thumb = None
    if embed is not None:
        try:
            thumb = embed.thumbnail.url if embed.thumbnail else None
        except Exception:
            thumb = None

    if head:
        txt = "\n".join(head)
        if thumb:
            try:
                cont.add_item(discord.ui.Section(
                    discord.ui.TextDisplay(txt),
                    accessory=discord.ui.Thumbnail(thumb)
                ))
            except Exception:
                cont.add_item(discord.ui.TextDisplay(txt))
        else:
            cont.add_item(discord.ui.TextDisplay(txt))

    if embed is not None:
        for f in (embed.fields or [])[:20]:
            name = (f.name or "").strip()
            value = (f.value or "").strip()
            if not name and not value:
                continue
            cont.add_item(discord.ui.TextDisplay(f"**{name}**\n{value}" if name else value))

        try:
            if embed.image and embed.image.url:
                cont.add_item(discord.ui.MediaGallery(
                    discord.MediaGalleryItem(embed.image.url)
                ))
        except Exception:
            pass

    for r in (rows or []):
        try:
            cont.add_item(discord.ui.Separator())
        except Exception:
            pass
        cont.add_item(r)

    if embed is not None:
        foot = []
        try:
            if embed.footer and embed.footer.text:
                foot.append(embed.footer.text)
        except Exception:
            pass
        try:
            if embed.timestamp:
                foot.append(f"<t:{int(embed.timestamp.timestamp())}:R>")
        except Exception:
            pass
        if foot:
            cont.add_item(discord.ui.TextDisplay("-# " + " • ".join(foot)))

    return cont


if _v2_available():
    class V2LayoutView(discord.ui.LayoutView):
        """Vue Components V2 : reprend l'embed + les composants d'une View classique."""

        def __init__(self, src_view=None, embeds=None, content=None, items=None):
            super().__init__(timeout=getattr(src_view, "timeout", 180) if src_view else 180)
            self.src_view = src_view
            items = list(items or [])
            self._v2_items = items
            self._v2_embeds = list(embeds or [])
            self._v2_content = content
            for it in items:
                try:
                    src_view.remove_item(it)
                except Exception:
                    pass
            rows = _v2_rows(items)
            if content:
                self.add_item(discord.ui.TextDisplay(str(content)))
            embeds = list(embeds or [])
            if embeds:
                for i, em in enumerate(embeds[:10]):
                    self.add_item(_v2_container(em, rows if i == 0 else None))
            else:
                self.add_item(_v2_container(None, rows))

        async def on_timeout(self):
            if self.src_view is not None:
                try:
                    await self.src_view.on_timeout()
                except Exception:
                    pass
else:
    V2LayoutView = None


_V2_MESSAGES = {}   # message_id -> V2LayoutView (pour ré-éditer sans perdre les composants)


def _v2_remember(message, lv, key=None):
    try:
        mid = key if key is not None else getattr(message, "id", None)
        if mid and lv is not None:
            _V2_MESSAGES[mid] = lv
            if len(_V2_MESSAGES) > 4000:
                for k in list(_V2_MESSAGES)[:1000]:
                    _V2_MESSAGES.pop(k, None)
    except Exception:
        pass


def _v2_reedit(msg_id, kw):
    """Edition d'un message déjà en Container V2 : on reconstruit avec les mêmes composants."""
    if not _v2_available() or msg_id not in _V2_MESSAGES:
        return None
    if isinstance(kw.get("view"), discord.ui.LayoutView):
        return None
    old = _V2_MESSAGES[msg_id]
    embeds = list(kw["embeds"]) if kw.get("embeds") else ([kw["embed"]] if kw.get("embed") is not None else [])
    if not embeds:
        # Aucun embed fourni (ex. edit_message(view=self)) : on reprend celui du message
        embeds = list(getattr(old, "_v2_embeds", []))
    content = kw.get("content", getattr(old, "_v2_content", None))
    if not embeds and content is None and "view" not in kw:
        return None
    if "view" in kw:
        v = kw["view"]
        src = v if isinstance(v, discord.ui.View) else None
        items = [it for it in getattr(v, "children", [])] if src else []
        if not items:
            # La vue s'est deja fait prendre ses composants par la V2LayoutView :
            # on reprend ceux-ci (ce sont les memes objets, deja mis a jour).
            src = getattr(old, "src_view", None) or src
            items = list(getattr(old, "_v2_items", []))
    else:
        src = getattr(old, "src_view", None)
        items = list(getattr(old, "_v2_items", []))
    new = dict(kw)
    new.pop("embed", None)
    new.pop("embeds", None)
    new.pop("content", None)
    lv = V2LayoutView(src, embeds, content, items)
    new["view"] = lv
    _V2_MESSAGES[msg_id] = lv
    return new


def _v2_transform(kw, edit_mode=False, has_files=False):
    """Transforme {content, embed(s), view} en une V2LayoutView. None = pas applicable."""
    if not _v2_available():
        return None

    view = kw.get("view")
    if isinstance(view, discord.ui.LayoutView):
        return None                      # deja en V2
    if view is not None and view is not False and not isinstance(view, discord.ui.View):
        return None

    items = [it for it in getattr(view, "children", []) if isinstance(it, discord.ui.Item)] if view else []

    embeds = []
    if kw.get("embeds"):
        embeds = list(kw["embeds"])
    elif kw.get("embed") is not None:
        embeds = [kw["embed"]]
    content = kw.get("content")

    # Un embed suffit : les messages sans bouton passent aussi en container.
    # En revanche on laisse tranquilles :
    #   - les messages en texte brut (say, animations, confirmations courtes)
    #   - les envois avec pieces jointes fournies par l'appelant (exports CSV...),
    #     que le mode V2 n'afficherait pas
    if not embeds:
        return None
    if has_files:
        return None

    if edit_mode and not embeds and not content:
        return None

    new = dict(kw)
    new.pop("embed", None)
    new.pop("embeds", None)
    new.pop("content", None)
    new["view"] = V2LayoutView(view, embeds, content, items)
    return new




def _is_v2_message(message):
    """Vrai si le message a ete poste en Components V2."""
    try:
        flags = message.flags
    except Exception:
        return False
    if getattr(flags, "components_v2", False):
        return True
    try:
        return bool(flags.value & (1 << 15))
    except Exception:
        return False


def _v2_relayout(message, src_view, items):
    """Rebatit la mise en page V2 d'un message existant en y remettant les composants a jour.

    Sert apres un redemarrage : la V2LayoutView d'origine n'est plus en memoire,
    mais le message, lui, est toujours en Components V2 — l'editer avec une View
    classique donnerait 50006 (Cannot send an empty message).
    """
    try:
        lv = discord.ui.LayoutView.from_message(message, timeout=getattr(src_view, "timeout", None))
    except Exception:
        return None

    container = None
    for child in getattr(lv, "children", []):
        if isinstance(child, discord.ui.Container):
            container = child
            break
    if container is None:
        return None

    try:
        for c in list(container.children):
            if isinstance(c, discord.ui.ActionRow):
                container.remove_item(c)
        for r in _v2_rows(items):
            container.add_item(r)
    except Exception:
        return None

    lv._v2_items = items
    lv._v2_embeds = []
    lv._v2_content = None
    lv.src_view = src_view
    return lv



def _v2_items_from_message(message):
    """Recupere les boutons/menus deja presents sur un message V2."""
    items = []
    try:
        old_lv = discord.ui.LayoutView.from_message(message)
    except Exception:
        return items

    def _walk(node):
        for c in list(getattr(node, "children", [])):
            if isinstance(c, discord.ui.ActionRow):
                for it in list(getattr(c, "children", [])):
                    try:
                        c.remove_item(it)
                    except Exception:
                        pass
                    items.append(it)
            else:
                _walk(c)

    _walk(old_lv)
    return items


def _v2_rebuild_edit(message, kw, items=None):
    """Refabrique un message Components V2 lors d'une edition.

    Utilise quand la V2LayoutView d'origine n'est plus en memoire : sans ca,
    editer un message V2 avec un embed classique donne 50035
    ("The 'embeds' field cannot be used when using MessageFlags.IS_COMPONENTS_V2").
    """
    try:
        embeds = list(kw["embeds"]) if kw.get("embeds") else ([kw["embed"]] if kw.get("embed") is not None else [])
        content = kw.get("content")
        auto = items is None
        if auto:
            items = _v2_items_from_message(message)
            # Si on n'a pas su relire les composants, mieux vaut ne rien faire
            # que de publier un message ampute de ses boutons.
            if not items and getattr(message, "components", None):
                return None
        if not embeds and content is None and not items:
            return None

        rows = _v2_rows(items)
        lv = discord.ui.LayoutView(timeout=None)
        if content:
            lv.add_item(discord.ui.TextDisplay(str(content)))
        if embeds:
            for i, em in enumerate(embeds[:10]):
                lv.add_item(_v2_container(em, rows if i == 0 else None))
        else:
            lv.add_item(_v2_container(None, rows))

        lv._v2_items = items
        lv._v2_embeds = embeds
        lv._v2_content = content
        lv.src_view = None

        new = {k: v for k, v in kw.items() if k not in ("embed", "embeds", "content", "view")}
        new["view"] = lv
        return new
    except Exception:
        return None



def _v2_restore(src_view, layout_view):
    """Remet les composants dans la vue classique si le mode V2 a echoue."""
    if src_view is None or layout_view is None:
        return
    try:
        for it in getattr(layout_view, "_v2_items", []):
            if it not in src_view.children:
                try:
                    layout_view.remove_item(it)
                except Exception:
                    pass
                src_view.add_item(it)
    except Exception:
        pass


async def _v2_fallback_followup(target, kw):
    """Interaction expiree (10062) : on tente le followup au lieu de tout perdre."""
    parent = getattr(target, "_parent", None) if not isinstance(target, discord.Interaction) else target
    followup = getattr(parent, "followup", None)
    if followup is None:
        return None
    kw = {k: v for k, v in kw.items() if k in ("content", "embed", "embeds", "view", "file", "files", "ephemeral")}
    try:
        return await followup.send(**kw)
    except Exception:
        return None


def _install_v2_patch():
    """Force TOUS les envois (boutons + menus) à passer en Container V2."""
    if not _v2_available() or getattr(discord, "_modera_v2_patched", False):
        return

    def wrap(owner, name, edit_mode=False):
        orig = getattr(owner, name, None)
        if orig is None:
            return

        async def patched(self, content=None, **kwargs):
            kw = dict(kwargs)
            if content is not None and content is not discord.utils.MISSING:
                kw["content"] = content
            has_files = kw.get("file") is not None or bool(kw.get("files"))
            if not edit_mode:
                try:
                    await _pin_embed_media(kw)
                except Exception:
                    pass
            new = None
            try:
                if edit_mode:
                    mid = None
                    if isinstance(self, discord.Message):
                        mid = self.id
                    else:
                        m = getattr(getattr(self, "_parent", None), "message", None)
                        mid = getattr(m, "id", None)
                    if mid is None:
                        if isinstance(self, discord.Interaction):
                            mid = ("i", self.id)
                        elif isinstance(self, discord.InteractionResponse):
                            mid = ("i", getattr(getattr(self, "_parent", None), "id", None))
                    if mid is not None:
                        new = _v2_reedit(mid, kw)
                    if new is None and _v2_available():
                        # Message V2 dont la vue n'est plus en memoire (redemarrage,
                        # ou entree evincee du registre) : on repart du message.
                        msg = self if isinstance(self, discord.Message) else getattr(getattr(self, "_parent", None), "message", None)
                        v = kw.get("view")
                        if msg is not None and _is_v2_message(msg) and not isinstance(v, discord.ui.LayoutView):
                            items = None
                            if isinstance(v, discord.ui.View):
                                items = [it for it in getattr(v, "children", []) if isinstance(it, discord.ui.Item)]
                                for it in list(items):
                                    try:
                                        v.remove_item(it)
                                    except Exception:
                                        pass
                                if not items:
                                    items = None   # vue vidée : on relira le message
                            new = _v2_rebuild_edit(msg, kw, items)
                            if new is not None and mid is not None:
                                _V2_MESSAGES[mid] = new["view"]
                if new is None:
                    new = _v2_transform(kw, edit_mode=edit_mode, has_files=has_files)
            except Exception:
                new = None
            if new is not None:
                try:
                    res = await orig(self, **new)
                    _v2_remember(res, new.get("view"))
                    if edit_mode and isinstance(self, discord.Message):
                        _v2_remember(self, new.get("view"))
                    if isinstance(self, discord.InteractionResponse):
                        _v2_remember(None, new.get("view"),
                                     key=("i", getattr(getattr(self, "_parent", None), "id", None)))
                    elif isinstance(self, discord.Interaction):
                        _v2_remember(None, new.get("view"), key=("i", self.id))
                    return res
                except discord.NotFound:
                    return await _v2_fallback_followup(self, new)
                except TypeError:
                    pass
                except discord.HTTPException as exc:
                    # 50035 / 50006 = requete rejetee a la validation : rien n'a
                    # ete poste, on peut retenter en mode classique sans doublon.
                    if getattr(exc, "code", 0) not in (50035, 50006):
                        raise
                # Le mode V2 a echoue : on rend ses composants a la vue d'origine,
                # sinon le message de repli partirait sans boutons ni menus.
                _v2_restore(kw.get("view"), new.get("view"))
            try:
                return await orig(self, **kw)
            except discord.NotFound:
                return await _v2_fallback_followup(self, kw)

        patched.__name__ = name
        setattr(owner, name, patched)

    wrap(discord.abc.Messageable, "send")
    wrap(discord.InteractionResponse, "send_message")
    wrap(discord.Webhook, "send")
    wrap(discord.InteractionResponse, "edit_message", edit_mode=True)
    wrap(discord.Message, "edit", edit_mode=True)
    wrap(discord.Interaction, "edit_original_response", edit_mode=True)
    discord._modera_v2_patched = True


_install_v2_patch()


DEFAULT_SPAM_THRESHOLD = 5

DEFAULT_SPAM_INTERVAL  = 4

DEFAULT_MENTION_LIMIT  = 6

DEFAULT_JOIN_THRESHOLD = 5

DEFAULT_JOIN_INTERVAL  = 10

_spam_track = collections.defaultdict(lambda: collections.defaultdict(collections.deque))

_join_track  = collections.defaultdict(collections.deque)

giveaways    = {}

ALL_COMMANDS = [

    "welcome","ban","unban","mute","unmute","warn","kick","clear","purge",

    "ping","userinfo","serverinfo","botinfo","level","rank","top","aide","help",

    "antilink","antiraid","ticket","giveaway","sondage","say","embed","roles",

    "premium","vip","depart","joinmp","modo","dmall","setup","servericon","variables",

    "codegen","generatecode","leaderboard","classement","config","setlog","synchronise","antibot"

]

# ══════════════════════════════════════════

# HELPERS

# ══════════════════════════════════════════

def jload(path):

    try:

        with open(path, "r", encoding="utf-8") as f:

            return json.load(f)

    except:

        return {}

def jsave(path, data):

    with open(path, "w", encoding="utf-8") as f:

        json.dump(data, f, indent=4, ensure_ascii=False)

def get_server_config(gid):

    path = f"server_configs/{gid}.json"

    if not os.path.exists(path):

        d = {"antiraid": {}}

        jsave(path, d)

        return d

    return jload(path)

def save_server_config(gid, data):

    jsave(f"server_configs/{gid}.json", data)

def get_level_config(gid):

    path = f"level_configs/{gid}.json"

    if not os.path.exists(path):

        d = {"xp_channel": None, "members": {}}

        jsave(path, d)

        return d

    return jload(path)

def save_level_config(gid, data):

    jsave(f"level_configs/{gid}.json", data)

def xp_to_next(level):

    return 100 * level

def is_premium(uid):

    data = jload(FILES["premium"])

    uid = str(uid)

    if uid not in data.get("users", {}):

        return False

    return data["users"][uid].get("expires_at", 0) > int(time.time())

def is_modo(member):

    cfg = jload(FILES["modo"]).get(str(member.guild.id), {})

    modo_roles = cfg.get("modo_roles", [])

    return member.guild_permissions.administrator or any(r.id in modo_roles for r in member.roles)

CMD_ALIASES = {

    "welcome": ["welcome","bienvenu","bienvenue","welcom","wlcm","welc","welkome","welcomee"],

    "ban": ["ban","bann","bane","banir","bannir","banhammer"],

    "unban": ["unban","deban","debannir","unban","unbann"],

    "mute": ["mute","muter","muter","mut","mute","silence","silencer"],

    "unmute": ["unmute","demuter","unmut","unsile","desilencer"],

    "warn": ["warn","avertir","avertissement","avert","warning","warnn"],

    "kick": ["kick","kik","kiick","exclure","virer","expulser"],

    "clear": ["clear","purge","purger","effacer","supprimer","suprimer","supp","cls"],

    "ping": ["ping","latence","laternce","pong","latense","lat"],

    "userinfo": ["userinfo","info","profil","utilisateur","infouser","whois"],

    "serverinfo": ["serverinfo","serveur","infoserveur","server","svr"],

    "botinfo": ["botinfo","bot","infobot","about","bt","bto","bnot","botinf","botifo","infbot","abot"],

    "level": ["level","niveau","lvl","niv","xp","exp"],

    "rank": ["rank","rang","classement","classe","rankinfo"],

    "top": ["top","leaderboard","classement","palmares","topxp","toplevel"],

    "aide": ["aide","help","aider","commandes","menu","hlep","hlp","helo"],

    "antilink": ["antilink","lien","liens","antiliens","antilien","antiurl"],

    "antiraid": ["antiraid","raid","antiraider","raider","protec","protection"],

    "ticket": ["ticket","tickets","tiket","tikket","supp","tkt"],

    "giveaway": ["giveaway","concours","cadeau","giveawy","giveway","give","gaw"],

    "sondage": ["sondage","poll","sond","sondaage","survol"],

    "say": ["say","dire","parler","annoncer","annonce","msg"],

    "embed": ["embed","message","embeed","embd"],

    "roles": ["roles","role","autorole","rolee","rolles","rang"],

    "premium": ["premium","abonnement","sub","prem","prm"],

    "vip": ["vip","code","codepromo","promo","activation","activer"],

    "depart": ["depart","aurevoir","bye","goodbye","leave","quitter"],

    "joinmp": ["joinmp","mp","dm","messagepriv","privmsg","mpjoin"],

    "modo": ["modo","moderation","mod","moderateur","modera"],

    "setup": ["setup","install","configurer","config","parametre","param"],

    "setlog": ["setlog","log","logs","logchan","setchan","logchannel"],

    "variables": ["variables","vars","variable","tags"],

    "codegen": ["codegen","generatecode","gencode","generer","code"],

    "logs": ["logs","ligs","log","loggs","lgos","losg","lgo"],

    "modlog": ["modlog","modlogs","logmod","logmodo","logmoderation"],

    "msglog": ["msglog","msglogs","logmsg","logmessage","logmessages"],

    "rolelog": ["rolelog","rolelogs","logrole","logroles"],

    "channellog": ["channellog","channellogs","logchannel","logsalon"],

    "voclog": ["voclog","voclogs","logvoc","logvoice","logvocal","voicelog"],

    "boostlog": ["boostlog","boostlogs","logboost","logboosts"],

    "fluxlog": ["fluxlog","fluxlogs","logflux","joinlog","leavelog"],

    "ticketlog": ["ticketlog","ticketlogs","logticket","logtickets"],

    "avatar": ["avatar","av","pfp","photo","pp"],

    "banner": ["banner","banniere","bann","ban"],

    "serveravatar": ["serveravatar","serverav","sav","iconserveur"],

    "serverbanner": ["serverbanner","serverbanniere","bannserveur"],

    "calcul": ["calcul","calc","calculator","calculatrice","math"],

    "channelinfo": ["channelinfo","ci","infosalon","saloninfo"],

    "find": ["find","chercher","trouver","finduser","findmember"],

    "github": ["github","gh","git"],

    "inviteinfo": ["inviteinfo","invite","invinvite","lien","linkinvite"],

    "links": ["links","lien","liens","link"],

    "norole": ["norole","sansrole","noroles","sansr"],

    "prevnames": ["prevnames","ancienspseudos","oldnames","pseudos","names"],

    "roleinfo": ["roleinfo","ri","inforole"],

    "rolemembers": ["rolemembers","membresrole","rolemembres","rmembers"],

    "search": ["search","recherche","searchcmd","cherche"],

    "snipe": ["snipe","snip","snipe1","lastdelete"],

    "snipedit": ["snipedit","editsnipe","esnipe","lastedit"],

    "speed": ["speed","vitesse","latency","latence","lat"],

    "stats": ["stats","stat","statistiques","statistique"],

    "support": ["support","aide-support","botsupp","serveur"],

    "template": ["template","templ","exemple"],

    "vanity": ["vanity","vanityu","url","urlserveur"],

    "vc": ["vc","vocal","voice","vocaux"],

    "version": ["version","ver","v","versionbot"],

    "vote": ["vote","voter","topgg"],

    "owner": ["owner","addowner","ajouterowner"],

    "unowner": ["unowner","removeowner","retirerowner","enleverowner"],

    "owners": ["owners","listowners","listeowners"],

    "clearowners": ["clearowners","supprimerowners","resetowners"],

    "reset": ["reset","reinitialiser","reinit","resetdata"],

    "8ball": ["8ball","boule","magic8","8b"],

    "anime": ["anime","anim"],

    "ascii": ["ascii","asciiart","art"],

    "binary": ["binary","bin","binaire","binar"],

    "cat": ["cat","chat","minou","kitty"],

    "dog": ["dog","chien","woof","wouf"],

    "coinflip": ["coinflip","pile","face","coin","pileface"],

    "roll": ["roll","dice","de","lancerde"],

    "rps": ["rps","chifoumi","pfc","rockpaperscissors"],

    "rate": ["rate","noter","note"],

    "gay": ["gay","gayrate","gaymetre"],

    "hack": ["hack","hacker","pirater"],

    "ratio": ["ratio","ratioed"],

    "wanted": ["wanted","recherche"],

    "hug": ["hug","calin","calins","enlace"],

    "pat": ["pat","caresse","tapoter"],

    "slap": ["slap","gifle","gifler","frapper"],

    "kiss": ["kiss","bisou","embrasser"],

    "cry": ["cry","pleurer","pleur"],

    "smile": ["smile","sourire"],

    "translate": ["translate","trad","traduction","traduire"],

    "tweet": ["tweet","twitter","faketweet"],

    "clyde": ["clyde","clydemsg","fakeclyde"],

    "mind": ["mind","panneau","panel"],

    "undertale": ["undertale","ut","undertalesay"],

    "define": ["define","definition","def","definir","dico"],

    "randomuser": ["randomuser","randuser","randomm","membrealeatoire"],

    "randomavatar": ["randomavatar","randav","avataraleatoire"],

    "randombanner": ["randombanner","randbanner","bannierealeatoire"],

    "deepfry": ["deepfry","fry","friture"],

    "blur": ["blur","flou","flouter"],

    "blurpify": ["blurpify","blurp","blurpifier"],

    "colorify": ["colorify","colorize","coloriser"],

    "oh": ["oh","menteur","liar"],

    "alladmins": ["alladmins","admins","listadmins","administrateurs"],

    "allbooster": ["allbooster","boosters","listboosters","boosters","allboosters"],

    "allbots": ["allbots","bots","listbots","robotss"],

    "allchannels": ["allchannels","channels","salons","listchannels","allsalons"],

    "allroles": ["allroles","listroles","tolesroles","touslesroles"],

    "allthreads": ["allthreads","threads","listthreads","fils"],

    "banlist": ["banlist","bans","listbans","listeban"],

    "idemoji": ["idemoji","emojiid","emojis","emoji","idemojis"],

    "onepage": ["onepage","allcmds","allcommands","touteslescommandes","pagecmds"],

    "timestamp": ["timestamp","ts","timetamp","timstamp"],

    "uptime": ["uptime","uptim","upteam","heuredemarrage"],

    "autoreact": ["autoreact","autoreaction","autoréaction","autoreactions"],

    "clearembeds": ["clearembeds","supprimerembeds","deleteembeds"],

    "create": ["create","createemoji","addemoji","ajouteremoji"],

    "defaultrole": ["defaultrole","defaultroles","rolesdefaut","roledefaut","roleauto"],

    "embedlist": ["embedlist","mesembeds","listembeds"],

    "everping": ["everping","everyoneping","pingall","pingeveryone"],

    "ghostping": ["ghostping","ghostpings","pingfantome","ghostpng"],

    "joinsettings": ["joinsettings","joinconfig","configjoin","arrivee"],

    "jointocreate": ["jointocreate","j2c","jtc","vocaltemp","vocaltemporaire"],

    "massiverole": ["massiverole","massrole","roleall","masserole"],

    "piconly": ["piconly","selfie","imageonly","photoonly","piconl"],

    "rolespicker": ["rolespicker","rolepicker","menuderoles","selectroles"],

    "sethelp": ["sethelp","helptype","typehelp","confighelp"],

    "showpic": ["showpic","showavatar","showprofile","autopfp"],

    "soutien": ["soutien","systemesoutien","support-role"],

    "starboard": ["starboard","starb","etoile","tableau"],

    "tag": ["tag","servertag","clantag","tagrolle"],

    "backup": ["backup","bkp","bk","backups","sauvegarde","sauvegarder","restaurer","restore","bck","backp","bakcup","bckp"],

    "synchronise": ["synchronise","sync","synchro","synchonise","synchronize","syncsalon","syncperm","syncperms","syncchannel","syncchannels","syncsalons","synchroniseperm","synccategorie","synccat"],

    "captcha": ["captcha","verif","verification","vérification","secu","securite","sécurité","captch","capt","captha","catpha","captcah"],

}

ALIAS_MAP = {}

for canonical, aliases in CMD_ALIASES.items():

    for alias in aliases:

        ALIAS_MAP[alias.lower()] = canonical

def resolve_command(name):

    n = name.lower().strip()

    if n in ALIAS_MAP: return ALIAS_MAP[n]

    matches = get_close_matches(n, list(ALIAS_MAP.keys()), n=1, cutoff=0.6)

    if matches: return ALIAS_MAP[matches[0]]

    direct = get_close_matches(n, list(CMD_ALIASES.keys()), n=1, cutoff=0.55)

    return direct[0] if direct else None

def find_close_cmd(name):

    return resolve_command(name)

def embed_ok(desc): return discord.Embed(description=f"✅ {desc}", color=C_GREEN)

def embed_err(desc): return discord.Embed(description=f"❌ {desc}", color=C_RED)

def embed_warn(desc): return discord.Embed(description=f"⚠️ {desc}", color=C_ORANGE)

def embed_premium(): return discord.Embed(title="⭐ Commande Premium", description=f"Réservée aux Premium.\n👉 [Obtenir le Premium]({PREMIUM_LINK})", color=C_GOLD)

async def send_sanction_mp(user, action, reason, mod_name, guild_name, duration=None):

    e = discord.Embed(title=f"⚠️ Sanction sur **{guild_name}**", color=C_RED)

    e.add_field(name="🔨 Sanction", value=action, inline=True)

    e.add_field(name="👮 Modérateur", value=mod_name, inline=True)

    if duration: e.add_field(name="⏳ Durée", value=duration, inline=True)

    e.add_field(name="📝 Raison", value=reason, inline=False)

    try: await user.send(embed=e)

    except: pass

# ══════════════════════════════════════════

#  ███╗   ███╗ ██████╗ ██████╗  █████╗ ██╗     ███████╗

#  ████╗ ████║██╔═══██╗██╔══██╗██╔══██╗██║     ██╔════╝

#  ██╔████╔██║██║   ██║██║  ██║███████║██║     ███████╗

#  ██║╚██╔╝██║██║   ██║██║  ██║██╔══██║██║     ╚════██║

#  ██║ ╚═╝ ██║╚██████╔╝██████╔╝██║  ██║███████╗███████║

#

#  TOUS LES MODALS

# ══════════════════════════════════════════

# ─── WELCOME MODALS ───

class ModalWelcomeChannel(discord.ui.Modal, title="🏷️ Salon de bienvenue"):

    channel_id = discord.ui.TextInput(label="ID ou mention du salon", placeholder="Ex: 123456789012345678", max_length=100)

    def __init__(self, gid):

        super().__init__(); self.gid = gid

        data = jload(FILES["welcome"]).get(str(gid), {})

        if data.get("channel_id"): self.channel_id.default = str(data["channel_id"])

    async def on_submit(self, interaction):

        raw = self.channel_id.value.strip().strip("<#>")

        try:

            cid = int(raw)

        except ValueError:

            return await interaction.response.send_message(embed=embed_err("ID de salon invalide. Entre un ID numérique ou une mention `#salon`."), ephemeral=True)

        channel = interaction.guild.get_channel(cid)

        if not channel:

            return await interaction.response.send_message(embed=embed_err("Salon introuvable sur ce serveur."), ephemeral=True)

        data = jload(FILES["welcome"]); data.setdefault(str(self.gid), {})["channel_id"] = cid

        jsave(FILES["welcome"], data)

        await interaction.response.send_message(embed=embed_ok(f"Salon de bienvenue défini : {channel.mention}"), ephemeral=True)

class ModalWelcomeMessage(discord.ui.Modal, title="💬 Message de bienvenue"):

    message = discord.ui.TextInput(label="Message", style=discord.TextStyle.paragraph,

        placeholder="{user} {username} {server} {membercount} {id}", max_length=1000)

    def __init__(self, gid):

        super().__init__(); self.gid = gid

        data = jload(FILES["welcome"]).get(str(gid), {})

        if data.get("message"): self.message.default = data["message"]

    async def on_submit(self, interaction):

        data = jload(FILES["welcome"]); data.setdefault(str(self.gid), {})["message"] = self.message.value

        jsave(FILES["welcome"], data)

        await interaction.response.send_message(embed=embed_ok("Message mis à jour !"), ephemeral=True)

class ModalWelcomeEmbed(discord.ui.Modal, title="🖼️ Embed de bienvenue"):

    titre   = discord.ui.TextInput(label="Titre", placeholder="Bienvenue {username} !", max_length=256, required=False)

    desc    = discord.ui.TextInput(label="Description", style=discord.TextStyle.paragraph,

        placeholder="{user} a rejoint {server} !\nOn est maintenant {membercount} membres.", max_length=2000, required=False)

    couleur = discord.ui.TextInput(label="Couleur hex (ex: #5865F2)", placeholder="#5865F2", max_length=7, required=False)

    image   = discord.ui.TextInput(label="Image (URL)", placeholder="https://...", max_length=300, required=False)

    thumb   = discord.ui.TextInput(label="Thumbnail (URL ou 'avatar')", placeholder="avatar / https://...", max_length=300, required=False)

    def __init__(self, gid):

        super().__init__(); self.gid = gid

        data = jload(FILES["welcome"]).get(str(gid), {}).get("embed", {})

        if data.get("titre"): self.titre.default = data["titre"]

        if data.get("desc"):  self.desc.default  = data["desc"]

        if data.get("color"): self.couleur.default = data["color"]

        if data.get("image"): self.image.default  = data["image"]

        if data.get("thumb"): self.thumb.default  = data["thumb"]

    async def on_submit(self, interaction):

        color_str = self.couleur.value.strip()

        try: color = int(color_str.replace("#",""), 16)

        except: color = 0x5865F2

        data = jload(FILES["welcome"]); data.setdefault(str(self.gid), {})

        data[str(self.gid)]["embed"] = {

            "enabled": True, "titre": self.titre.value, "desc": self.desc.value,

            "color": color_str or "#5865F2", "image": self.image.value, "thumb": self.thumb.value

        }

        jsave(FILES["welcome"], data)

        await interaction.response.send_message(embed=embed_ok("Embed de bienvenue configuré !\n*Active-le via le menu.*"), ephemeral=True)

class ModalWelcomeAutoDelete(discord.ui.Modal, title="⏰ Suppression auto"):

    secondes = discord.ui.TextInput(label="Supprimer après X secondes (0 = désactivé)", placeholder="Ex: 10", max_length=5)

    def __init__(self, gid):

        super().__init__(); self.gid = gid

    async def on_submit(self, interaction):

        try:

            s = int(self.secondes.value.strip())

            data = jload(FILES["welcome"]); data.setdefault(str(self.gid), {})["auto_delete"] = s

            jsave(FILES["welcome"], data)

            await interaction.response.send_message(embed=embed_ok(f"Suppression auto : **{s}s** {'(désactivé)' if s==0 else ''}"), ephemeral=True)

        except: await interaction.response.send_message(embed=embed_err("Nombre invalide."), ephemeral=True)

class ModalWelcomeMPMessage(discord.ui.Modal, title="📩 Message MP de bienvenue"):

    message = discord.ui.TextInput(label="Message MP", style=discord.TextStyle.paragraph,

        placeholder="Bienvenue {username} sur {server} !", max_length=1000)

    def __init__(self, gid):

        super().__init__(); self.gid = gid

        data = jload(FILES["welcome"]).get(str(gid), {})

        if data.get("mp_message"): self.message.default = data["mp_message"]

    async def on_submit(self, interaction):

        data = jload(FILES["welcome"]); data.setdefault(str(self.gid), {})["mp_message"] = self.message.value

        jsave(FILES["welcome"], data)

        await interaction.response.send_message(embed=embed_ok("Message MP mis à jour !"), ephemeral=True)

class ModalWelcomeBackground(discord.ui.Modal, title="🖼️ Image de fond (card)"):

    url = discord.ui.TextInput(label="URL de l'image de fond", placeholder="https://...", max_length=300, required=False)

    def __init__(self, gid):

        super().__init__(); self.gid = gid

    async def on_submit(self, interaction):

        data = jload(FILES["welcome"]); data.setdefault(str(self.gid), {})["background"] = self.url.value.strip()

        jsave(FILES["welcome"], data)

        await interaction.response.send_message(embed=embed_ok("Image de fond enregistrée."), ephemeral=True)

def build_welcome_status_embed(guild_id):

    data = jload(FILES["welcome"]).get(str(guild_id), {})

    e = discord.Embed(title="👋 Configuration Welcome", color=C_GREEN)

    ch = data.get("channel_id")

    e.add_field(name="📺 Salon", value=f"<#{ch}>" if ch else "❌ Non défini", inline=True)

    e.add_field(name="🔘 Statut", value="✅ Actif" if data.get("enabled", True) else "❌ Désactivé", inline=True)

    mode = data.get("mode", "texte")

    e.add_field(name="📋 Mode", value=f"`{mode}`", inline=True)

    e.add_field(name="💬 Message", value=f"`{data.get('message','Non défini')[:80]}`" if data.get("message") else "❌ Non défini", inline=False)

    emb = data.get("embed", {})

    if emb.get("enabled"):

        e.add_field(name="🖼️ Embed", value=f"✅ Actif — `{emb.get('titre','')[:40]}`", inline=False)

    e.add_field(name="⏰ Auto-suppression", value=f"{data.get('auto_delete',0)}s" if data.get("auto_delete") else "❌", inline=True)

    e.add_field(name="📩 MP", value="✅ Actif" if data.get("mp_enabled") else "❌", inline=True)

    e.add_field(name="🖼️ Fond", value=f"✅ Défini" if data.get("background") else "❌", inline=True)

    vars_list = "`{user}` `{username}` `{server}` `{membercount}` `{id}`"

    e.add_field(name="📝 Variables dispo", value=vars_list, inline=False)

    e.set_footer(text="ModeraBot • Welcome")

    return e

# ─── WELCOME VIEW ─────────────────────────────────────────────────────────────

class ModalWelcomeRole(discord.ui.Modal, title="🎭 Rôle de bienvenue"):

    role_id = discord.ui.TextInput(label="ID du rôle à donner (0 pour désactiver)", placeholder="Ex: 123456789", max_length=20)

    def __init__(self, gid):

        super().__init__(); self.gid = gid

        data = jload(FILES["welcome"]).get(str(gid), {})

        if data.get("welcome_role"): self.role_id.default = str(data["welcome_role"])

    async def on_submit(self, interaction):

        try:

            rid = int(self.role_id.value.strip())

            if rid == 0:

                data = jload(FILES["welcome"]); data.setdefault(str(self.gid), {}).pop("welcome_role", None)

                jsave(FILES["welcome"], data)

                return await interaction.response.send_message(embed=embed_ok("Rôle de bienvenue désactivé."), ephemeral=True)

            role = interaction.guild.get_role(rid)

            if not role: return await interaction.response.send_message(embed=embed_err("Rôle introuvable."), ephemeral=True)

            data = jload(FILES["welcome"]); data.setdefault(str(self.gid), {})["welcome_role"] = rid

            jsave(FILES["welcome"], data)

            await interaction.response.send_message(embed=embed_ok(f"Rôle de bienvenue : {role.mention}"), ephemeral=True)

        except: await interaction.response.send_message(embed=embed_err("ID invalide."), ephemeral=True)

class WelcomeView(discord.ui.View):

    def __init__(self, ctx):

        super().__init__(timeout=None)

        self.ctx = ctx

    @discord.ui.select(placeholder="⚙️ Configurer le welcome...", row=0, options=[

        discord.SelectOption(label="Salon de bienvenue", emoji="🏷️", value="channel", description="Où envoyer le message"),

        discord.SelectOption(label="Mode texte — message simple", emoji="💬", value="message", description="Message texte classique"),

        discord.SelectOption(label="Mode embed — personnalisé", emoji="🖼️", value="embed", description="Embed avec titre, couleur, image"),

        discord.SelectOption(label="Mention du membre", emoji="🔔", value="toggle_mention", description="Activer/désactiver la mention"),

        discord.SelectOption(label="Suppression auto du message", emoji="⏰", value="autodel", description="Supprimer après X secondes"),

        discord.SelectOption(label="Image de fond (card)", emoji="🎨", value="background", description="Image d'arrière-plan"),

        discord.SelectOption(label="Rôle de bienvenue", emoji="🎭", value="welcome_role", description="Rôle donné à l'arrivée"),

        discord.SelectOption(label="Message MP de bienvenue", emoji="📩", value="mp_message", description="MP envoyé au nouveau membre"),

        discord.SelectOption(label="Activer/Désactiver le MP", emoji="🔕", value="toggle_mp", description="Toggle MP bienvenue"),

        discord.SelectOption(label="Activer/Désactiver le welcome", emoji="🔘", value="toggle", description="Toggle tout le système"),

    ])

    async def select_cb(self, interaction: discord.Interaction, select: discord.ui.Select):

        if interaction.user.id != self.ctx.author.id:

            return await interaction.response.send_message(embed=embed_err("Ce menu n'est pas pour toi."), ephemeral=True)

        v = select.values[0]; gid = interaction.guild.id

        data = jload(FILES["welcome"]); data.setdefault(str(gid), {})

        if v == "channel":

            await interaction.response.send_modal(ModalWelcomeChannel(gid))

        elif v == "message":

            data[str(gid)]["mode"] = "texte"; jsave(FILES["welcome"], data)

            await interaction.response.send_modal(ModalWelcomeMessage(gid))

        elif v == "embed":

            data[str(gid)]["mode"] = "embed"; jsave(FILES["welcome"], data)

            await interaction.response.send_modal(ModalWelcomeEmbed(gid))

        elif v == "toggle_mention":

            cur = data[str(gid)].get("mention", True)

            data[str(gid)]["mention"] = not cur; jsave(FILES["welcome"], data)

            await interaction.response.send_message(embed=embed_ok(f"Mention **{'activée' if not cur else 'désactivée'}** !"), ephemeral=True)

        elif v == "autodel":

            await interaction.response.send_modal(ModalWelcomeAutoDelete(gid))

        elif v == "background":

            await interaction.response.send_modal(ModalWelcomeBackground(gid))

        elif v == "welcome_role":

            await interaction.response.send_modal(ModalWelcomeRole(gid))

        elif v == "mp_message":

            await interaction.response.send_modal(ModalWelcomeMPMessage(gid))

        elif v == "toggle_mp":

            cur = data[str(gid)].get("mp_enabled", False)

            data[str(gid)]["mp_enabled"] = not cur; jsave(FILES["welcome"], data)

            await interaction.response.send_message(embed=embed_ok(f"Message MP **{'activé' if not cur else 'désactivé'}** !"), ephemeral=True)

        elif v == "toggle":

            cur = data[str(gid)].get("enabled", True)

            data[str(gid)]["enabled"] = not cur; jsave(FILES["welcome"], data)

            await interaction.response.send_message(embed=embed_ok(f"Welcome **{'activé' if not cur else 'désactivé'}** !"), ephemeral=True)

    @discord.ui.button(label="📋 Voir config", style=discord.ButtonStyle.secondary, row=1)

    async def btn_status(self, interaction: discord.Interaction, button):

        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message(embed=embed_err("Ce menu n'est pas pour toi."), ephemeral=True)

        await interaction.response.send_message(embed=build_welcome_status_embed(interaction.guild.id), ephemeral=True)

    @discord.ui.button(label="🔄 Actualiser", style=discord.ButtonStyle.secondary, row=1)

    async def btn_refresh(self, interaction: discord.Interaction, button):

        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message(embed=embed_err("Ce menu n'est pas pour toi."), ephemeral=True)

        await interaction.response.defer()

        await interaction.message.edit(embed=build_welcome_status_embed(interaction.guild.id))

    @discord.ui.button(label="🗑️ Reset", style=discord.ButtonStyle.danger, row=1)

    async def btn_reset(self, interaction: discord.Interaction, button):

        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message(embed=embed_err("Ce menu n'est pas pour toi."), ephemeral=True)

        data = jload(FILES["welcome"]); data.pop(str(interaction.guild.id), None)

        jsave(FILES["welcome"], data)

        await interaction.response.send_message(embed=embed_ok("Configuration welcome réinitialisée."), ephemeral=True)

def build_giveaway_status_embed(guild_id):

    data = jload(FILES["giveaway_cfg"]).get(str(guild_id), {})

    e = discord.Embed(title="Paramètre du giveaway", color=C_BLUE)

    e.add_field(name="Gain", value=data.get("gain", "Non défini"), inline=False)

    e.add_field(name="Durée", value=f"{data.get('duree', 'Non défini')}\n{datetime.now().strftime('%d/%m/%Y')}", inline=False)

    ch = data.get("salon_id")

    e.add_field(name="Salon", value=f"<#{ch}>" if ch else "Non défini", inline=False)

    e.add_field(name="Emoji", value=data.get("emoji", "🎉"), inline=False)

    e.add_field(name="Texte du bouton", value=data.get("btn_text", "Aucun") or "Aucun", inline=False)

    e.add_field(name="Couleur du bouton", value=data.get("btn_color", "bleu"), inline=False)

    e.add_field(name="Nombre de gagnants", value=str(data.get("gagnants", 1)), inline=False)

    e.add_field(name="Présence en voc obligatoire", value="✅" if data.get("vocal_required") else "❌", inline=False)

    e.add_field(name="Afficher les conditions", value="✅" if data.get("show_conditions", True) else "❌", inline=False)

    e.add_field(name="Afficher le bouton redirection", value="✅" if data.get("redirect_url") else "❌", inline=False)

    e.add_field(name="Afficher la liste des participants", value="✅" if data.get("show_participants") else "❌", inline=False)

    e.add_field(name="Style d'affichage", value=data.get("style", "embed"), inline=False)

    e.set_footer(text="© ModeraBot 2023 - 2026")

    return e

# ─── GIVEAWAY MODALS ──────────────────────────────────────────────────────────

class ModalGiveawayParams(discord.ui.Modal, title="🎉 Paramètres du Giveaway"):

    gain     = discord.ui.TextInput(label="Lot à gagner", placeholder="Ex: Nitro Classic 1 mois", max_length=200)

    duree    = discord.ui.TextInput(label="Durée (ex: 30m / 2h / 1j)", placeholder="30m", max_length=10)

    salon    = discord.ui.TextInput(label="ID du salon", placeholder="Ex: 123456789012345678", max_length=20)

    gagnants = discord.ui.TextInput(label="Nombre de gagnants", placeholder="1", max_length=3)

    emoji    = discord.ui.TextInput(label="Emoji de participation", placeholder="🎉", max_length=10, required=False)

    def __init__(self, gid, ctx):

        super().__init__()

        self.gid = gid

        self.ctx = ctx

        data = jload(FILES["giveaway_cfg"]).get(str(gid), {})

        if data.get("gain"):     self.gain.default     = data["gain"]

        if data.get("duree"):    self.duree.default    = data["duree"]

        if data.get("salon_id"): self.salon.default    = str(data["salon_id"])

        if data.get("gagnants"): self.gagnants.default = str(data["gagnants"])

        if data.get("emoji"):    self.emoji.default    = data["emoji"]

    async def on_submit(self, interaction: discord.Interaction):

        try: gagnants_val = max(1, int(self.gagnants.value.strip()))

        except: gagnants_val = 1

        try: salon_id_val = int(self.salon.value.strip())

        except:

            return await interaction.response.send_message(embed=embed_err("ID de salon invalide."), ephemeral=True)

        emoji_val = self.emoji.value.strip() or "🎉"

        data = jload(FILES["giveaway_cfg"])

        data.setdefault(str(self.gid), {}).update({

            "gain": self.gain.value.strip(),

            "duree": self.duree.value.strip(),

            "salon_id": salon_id_val,

            "gagnants": gagnants_val,

            "emoji": emoji_val,

        })

        jsave(FILES["giveaway_cfg"], data)

        await interaction.response.send_message(embed=embed_ok("Paramètres enregistrés !"), ephemeral=True)


class ModalGiveawayButton(discord.ui.Modal, title="📥 Bouton du Giveaway"):

    btn_text  = discord.ui.TextInput(label="Texte du bouton (vide = aucun bouton)", placeholder="Ex: Participer", max_length=80, required=False)

    btn_color = discord.ui.TextInput(label="Couleur (bleu / vert / rouge / gris)", placeholder="bleu", max_length=10, required=False)

    redirect  = discord.ui.TextInput(label="URL de redirection (optionnel)", placeholder="https://...", max_length=300, required=False)

    def __init__(self, gid):

        super().__init__()

        self.gid = gid

        data = jload(FILES["giveaway_cfg"]).get(str(gid), {})

        if data.get("btn_text"):     self.btn_text.default  = data["btn_text"]

        if data.get("btn_color"):    self.btn_color.default = data["btn_color"]

        if data.get("redirect_url"): self.redirect.default  = data["redirect_url"]

    async def on_submit(self, interaction: discord.Interaction):

        color_val = self.btn_color.value.strip().lower()

        if color_val not in ("bleu", "vert", "rouge", "gris"): color_val = "bleu"

        data = jload(FILES["giveaway_cfg"])

        data.setdefault(str(self.gid), {}).update({

            "btn_text": self.btn_text.value.strip(),

            "btn_color": color_val,

            "redirect_url": self.redirect.value.strip(),

        })

        jsave(FILES["giveaway_cfg"], data)

        await interaction.response.send_message(embed=embed_ok("Bouton configuré !"), ephemeral=True)


class ModalGiveawayRoles(discord.ui.Modal, title="🔗 Rôles du Giveaway"):

    required = discord.ui.TextInput(label="Rôles requis (IDs séparés par virgule)", placeholder="Ex: 111,222,333", max_length=300, required=False)

    blacklist = discord.ui.TextInput(label="Rôles bannis (IDs séparés par virgule)", placeholder="Ex: 444,555", max_length=300, required=False)

    bonus    = discord.ui.TextInput(label="Bonus entrées (role_id:nb, ex: 111:2,222:3)", placeholder="111:2,222:3", max_length=300, required=False)

    def __init__(self, gid):

        super().__init__()

        self.gid = gid

        data = jload(FILES["giveaway_cfg"]).get(str(gid), {})

        rr = data.get("required_roles", [])

        bl = data.get("blacklist_roles", [])

        br = data.get("bonus_raw", "")

        if rr: self.required.default  = ",".join(str(r) for r in rr)

        if bl: self.blacklist.default = ",".join(str(r) for r in bl)

        if br: self.bonus.default     = br

    async def on_submit(self, interaction: discord.Interaction):

        def parse_ids(raw):

            ids = []

            for x in raw.split(","):

                x = x.strip()

                if x.isdigit(): ids.append(int(x))

            return ids

        data = jload(FILES["giveaway_cfg"])

        data.setdefault(str(self.gid), {}).update({

            "required_roles": parse_ids(self.required.value),

            "blacklist_roles": parse_ids(self.blacklist.value),

            "bonus_raw": self.bonus.value.strip(),

        })

        jsave(FILES["giveaway_cfg"], data)

        await interaction.response.send_message(embed=embed_ok("Rôles enregistrés !"), ephemeral=True)


class ModalGiveawayConditions(discord.ui.Modal, title="🔑 Conditions du Giveaway"):

    vocal = discord.ui.TextInput(label="Présence en vocal obligatoire ? (oui / non)", placeholder="non", max_length=3)

    def __init__(self, gid):

        super().__init__()

        self.gid = gid

        data = jload(FILES["giveaway_cfg"]).get(str(gid), {})

        self.vocal.default = "oui" if data.get("vocal_required") else "non"

    async def on_submit(self, interaction: discord.Interaction):

        vocal_val = self.vocal.value.strip().lower() in ("oui", "yes", "1", "true", "o")

        data = jload(FILES["giveaway_cfg"])

        data.setdefault(str(self.gid), {})["vocal_required"] = vocal_val

        jsave(FILES["giveaway_cfg"], data)

        await interaction.response.send_message(embed=embed_ok(f"Présence vocal : **{'✅ activée' if vocal_val else '❌ désactivée'}** !"), ephemeral=True)


class ModalGiveawayWinner(discord.ui.Modal, title="🏅 Gagnant prédéfini"):

    winner_id = discord.ui.TextInput(label="ID du membre gagnant (vide = aléatoire)", placeholder="Ex: 123456789012345678", max_length=20, required=False)

    def __init__(self, gid):

        super().__init__()

        self.gid = gid

        data = jload(FILES["giveaway_cfg"]).get(str(gid), {})

        pw = data.get("preset_winner")

        if pw: self.winner_id.default = str(pw)

    async def on_submit(self, interaction: discord.Interaction):

        raw = self.winner_id.value.strip()

        if raw:

            try: preset = int(raw)

            except:

                return await interaction.response.send_message(embed=embed_err("ID invalide."), ephemeral=True)

        else:

            preset = None

        data = jload(FILES["giveaway_cfg"])

        data.setdefault(str(self.gid), {})["preset_winner"] = preset

        jsave(FILES["giveaway_cfg"], data)

        msg = f"Gagnant prédéfini : <@{preset}>" if preset else "Aucun gagnant prédéfini (tirage aléatoire)."

        await interaction.response.send_message(embed=embed_ok(msg), ephemeral=True)

# ─── FIN GIVEAWAY MODALS ──────────────────────────────────────────────────────

class GiveawayView(discord.ui.View):

    def __init__(self, ctx):

        super().__init__(timeout=None)

        self.ctx = ctx

    @discord.ui.select(placeholder="Paramètre le giveaway", options=[

        discord.SelectOption(label="Configurer les paramètres (gain, temps...)", emoji="🎉", value="params"),

        discord.SelectOption(label="Configurer l'intéraction bouton (texte...)", emoji="📥", value="button"),

        discord.SelectOption(label="Configurer les rôles (obligatoire, bannis...)", emoji="🔗", value="roles"),

        discord.SelectOption(label="Configurer les conditions (vocal...)", emoji="🔑", value="conditions"),

        discord.SelectOption(label="Définir un gagnant prédéfini", emoji="🏅", value="winner"),

        discord.SelectOption(label="Afficher la liste des participants", emoji="🎀", value="show_parts"),

        discord.SelectOption(label="Afficher les conditions du giveaway", emoji="📜", value="show_conds"),

        discord.SelectOption(label="Afficher le bouton de redirection", emoji="🔗", value="show_redirect"),

    ])

    async def select_cb(self, interaction: discord.Interaction, select: discord.ui.Select):

        if interaction.user.id != self.ctx.author.id:

            return await interaction.response.send_message(embed=embed_err("Ce menu n'est pas pour toi."), ephemeral=True)

        v = select.values[0]

        gid = interaction.guild.id

        if v == "params":

            await interaction.response.send_modal(ModalGiveawayParams(gid, self.ctx))

        elif v == "button":

            await interaction.response.send_modal(ModalGiveawayButton(gid))

        elif v == "roles":

            await interaction.response.send_modal(ModalGiveawayRoles(gid))

        elif v == "conditions":

            await interaction.response.send_modal(ModalGiveawayConditions(gid))

        elif v == "winner":

            await interaction.response.send_modal(ModalGiveawayWinner(gid))

        elif v in ("show_parts", "show_conds", "show_redirect"):

            key_map = {"show_parts": "show_participants", "show_conds": "show_conditions", "show_redirect": "redirect_active"}

            data = jload(FILES["giveaway_cfg"])

            data.setdefault(str(gid), {})

            cur = data[str(gid)].get(key_map[v], False)

            data[str(gid)][key_map[v]] = not cur

            jsave(FILES["giveaway_cfg"], data)

            await interaction.response.send_message(embed=embed_ok(f"Option **{'activée' if not cur else 'désactivée'}** !"), ephemeral=True)

    @discord.ui.button(label="🚀 Lancer le giveaway", style=discord.ButtonStyle.success, row=2)

    async def launch_btn(self, interaction: discord.Interaction, button):

        if interaction.user.id != self.ctx.author.id:

            return await interaction.response.send_message("❌", ephemeral=True)

        data = jload(FILES["giveaway_cfg"]).get(str(interaction.guild.id), {})

        if not data.get("gain") or not data.get("duree") or not data.get("salon_id"):

            return await interaction.response.send_message(embed=embed_err("Configure d'abord les paramètres (gain, durée, salon) !"), ephemeral=True)

        await interaction.response.send_message(embed=embed_ok("Giveaway lancé !"), ephemeral=True)

        await self.ctx.send(f"✅ Lancement du giveaway en cours...")

        asyncio.create_task(launch_giveaway_from_config(self.ctx, data))

# ─── ANTIRAID MODALS ───

class ModalAntiraidSpam(discord.ui.Modal, title="🚫 Configurer Anti-Spam"):

    threshold = discord.ui.TextInput(label="Nb de messages avant sanction", placeholder="Ex: 5", max_length=3)

    interval  = discord.ui.TextInput(label="Intervalle en secondes", placeholder="Ex: 4", max_length=3)

    action    = discord.ui.TextInput(label="Action (timeout / kick / ban)", placeholder="timeout", max_length=10)

    enabled   = discord.ui.TextInput(label="Activer ? (oui / non)", placeholder="oui", max_length=3)

    def __init__(self, gid):

        super().__init__(); self.gid = gid

        cfg = get_server_config(gid).get("antiraid", {})

        self.threshold.default = str(cfg.get("spam_threshold", DEFAULT_SPAM_THRESHOLD))

        self.interval.default  = str(cfg.get("spam_interval",  DEFAULT_SPAM_INTERVAL))

        self.action.default    = cfg.get("spam_action", "timeout")

        self.enabled.default   = "oui" if cfg.get("spam", False) else "non"

    async def on_submit(self, interaction):

        try:

            cfg = get_server_config(self.gid)

            cfg.setdefault("antiraid", {})

            cfg["antiraid"]["spam_threshold"] = max(1, int(self.threshold.value.strip()))

            cfg["antiraid"]["spam_interval"]  = max(1, int(self.interval.value.strip()))

            act = self.action.value.strip().lower()

            cfg["antiraid"]["spam_action"]    = act if act in ("timeout","kick","ban") else "timeout"

            cfg["antiraid"]["spam"]           = self.enabled.value.strip().lower() in ("oui","yes","1","true","o")

            save_server_config(self.gid, cfg)

            status = "✅ Activé" if cfg["antiraid"]["spam"] else "❌ Désactivé"

            await interaction.response.send_message(embed=embed_ok(
                f"Anti-Spam mis à jour !\n"
                f"**Statut :** {status}\n"
                f"**Seuil :** {cfg['antiraid']['spam_threshold']} msgs/{cfg['antiraid']['spam_interval']}s\n"
                f"**Action :** {cfg['antiraid']['spam_action']}"
            ), ephemeral=True)

        except: await interaction.response.send_message(embed=embed_err("Valeur invalide. Vérifie les champs."), ephemeral=True)

class ModalAntiraidMention(discord.ui.Modal, title="👥 Configurer Anti-Mention"):

    limit   = discord.ui.TextInput(label="Nb max de mentions autorisées", placeholder="Ex: 6", max_length=3)

    action  = discord.ui.TextInput(label="Action (timeout / kick / ban)", placeholder="timeout", max_length=10)

    enabled = discord.ui.TextInput(label="Activer ? (oui / non)", placeholder="oui", max_length=3)

    def __init__(self, gid):

        super().__init__(); self.gid = gid

        cfg = get_server_config(gid).get("antiraid", {})

        self.limit.default   = str(cfg.get("mention_limit",  DEFAULT_MENTION_LIMIT))

        self.action.default  = cfg.get("mention_action", "timeout")

        self.enabled.default = "oui" if cfg.get("mention", False) else "non"

    async def on_submit(self, interaction):

        try:

            cfg = get_server_config(self.gid)

            cfg.setdefault("antiraid", {})

            cfg["antiraid"]["mention_limit"]  = max(1, int(self.limit.value.strip()))

            act = self.action.value.strip().lower()

            cfg["antiraid"]["mention_action"] = act if act in ("timeout","kick","ban") else "timeout"

            cfg["antiraid"]["mention"]        = self.enabled.value.strip().lower() in ("oui","yes","1","true","o")

            save_server_config(self.gid, cfg)

            status = "✅ Activé" if cfg["antiraid"]["mention"] else "❌ Désactivé"

            await interaction.response.send_message(embed=embed_ok(
                f"Anti-Mention mis à jour !\n"
                f"**Statut :** {status}\n"
                f"**Limite :** {cfg['antiraid']['mention_limit']} mentions\n"
                f"**Action :** {cfg['antiraid']['mention_action']}"
            ), ephemeral=True)

        except: await interaction.response.send_message(embed=embed_err("Valeur invalide. Vérifie les champs."), ephemeral=True)

class ModalAntiraidJoin(discord.ui.Modal, title="⚡ Configurer Anti-Join Flood"):

    threshold = discord.ui.TextInput(label="Nb de joins avant action", placeholder="Ex: 5", max_length=3)

    interval  = discord.ui.TextInput(label="Intervalle en secondes", placeholder="Ex: 10", max_length=3)

    action    = discord.ui.TextInput(label="Action (log / kick / ban / lockdown)", placeholder="log", max_length=10)

    enabled   = discord.ui.TextInput(label="Activer ? (oui / non)", placeholder="oui", max_length=3)

    def __init__(self, gid):

        super().__init__(); self.gid = gid

        cfg = get_server_config(gid).get("antiraid", {})

        self.threshold.default = str(cfg.get("join_threshold", DEFAULT_JOIN_THRESHOLD))

        self.interval.default  = str(cfg.get("join_interval",  DEFAULT_JOIN_INTERVAL))

        self.action.default    = cfg.get("join_action", "log")

        self.enabled.default   = "oui" if cfg.get("join", False) else "non"

    async def on_submit(self, interaction):

        try:

            cfg = get_server_config(self.gid)

            cfg.setdefault("antiraid", {})

            cfg["antiraid"]["join_threshold"] = max(1, int(self.threshold.value.strip()))

            cfg["antiraid"]["join_interval"]  = max(1, int(self.interval.value.strip()))

            act = self.action.value.strip().lower()

            cfg["antiraid"]["join_action"]    = act if act in ("log","kick","ban","lockdown") else "log"

            cfg["antiraid"]["join"]           = self.enabled.value.strip().lower() in ("oui","yes","1","true","o")

            save_server_config(self.gid, cfg)

            status = "✅ Activé" if cfg["antiraid"]["join"] else "❌ Désactivé"

            await interaction.response.send_message(embed=embed_ok(
                f"Anti-Join Flood mis à jour !\n"
                f"**Statut :** {status}\n"
                f"**Seuil :** {cfg['antiraid']['join_threshold']} joins/{cfg['antiraid']['join_interval']}s\n"
                f"**Action :** {cfg['antiraid']['join_action']}"
            ), ephemeral=True)

        except: await interaction.response.send_message(embed=embed_err("Valeur invalide. Vérifie les champs."), ephemeral=True)

class ModalAntiraidLink(discord.ui.Modal, title="🔗 Configurer Anti-Lien"):

    action    = discord.ui.TextInput(label="Action (delete / warn / kick / ban)", placeholder="delete", max_length=10)

    whitelist = discord.ui.TextInput(label="Whitelist (domaines séparés par virgule)", placeholder="discord.gg, youtube.com", max_length=300, required=False)

    enabled   = discord.ui.TextInput(label="Activer ? (oui / non)", placeholder="oui", max_length=3)

    def __init__(self, gid):

        super().__init__(); self.gid = gid

        cfg = jload(FILES["antilink"]).get(str(gid), {})

        self.action.default    = cfg.get("action", "delete")

        self.whitelist.default = ", ".join(cfg.get("whitelist", []))

        self.enabled.default   = "oui" if cfg.get("enabled", False) else "non"

    async def on_submit(self, interaction):

        act = self.action.value.strip().lower()

        act = act if act in ("delete","warn","kick","ban") else "delete"

        wl_raw = self.whitelist.value.strip()

        wl = [w.strip() for w in wl_raw.split(",") if w.strip()] if wl_raw else []

        enabled = self.enabled.value.strip().lower() in ("oui","yes","1","true","o")

        data = jload(FILES["antilink"])

        data[str(self.gid)] = {"enabled": enabled, "action": act, "whitelist": wl}

        jsave(FILES["antilink"], data)

        status = "✅ Activé" if enabled else "❌ Désactivé"

        await interaction.response.send_message(embed=embed_ok(
            f"Anti-Lien mis à jour !\n"
            f"**Statut :** {status}\n"
            f"**Action :** {act}\n"
            f"**Whitelist :** {', '.join(wl) if wl else 'Aucune'}"
        ), ephemeral=True)

class ModalAntiraidCaps(discord.ui.Modal, title="🔤 Configurer Anti-Caps"):

    percent    = discord.ui.TextInput(label="% de majuscules max autorisé", placeholder="Ex: 70", max_length=3)

    min_length = discord.ui.TextInput(label="Longueur min du message (chars)", placeholder="Ex: 10", max_length=4)

    enabled    = discord.ui.TextInput(label="Activer ? (oui / non)", placeholder="oui", max_length=3)

    def __init__(self, gid):

        super().__init__(); self.gid = gid

        cfg = get_server_config(gid).get("antiraid", {})

        self.percent.default    = str(cfg.get("caps_percent",     70))

        self.min_length.default = str(cfg.get("caps_min_length",  10))

        self.enabled.default    = "oui" if cfg.get("caps", False) else "non"

    async def on_submit(self, interaction):

        try:

            cfg = get_server_config(self.gid)

            cfg.setdefault("antiraid", {})

            cfg["antiraid"]["caps_percent"]   = max(1, min(100, int(self.percent.value.strip())))

            cfg["antiraid"]["caps_min_length"] = max(1, int(self.min_length.value.strip()))

            cfg["antiraid"]["caps"]           = self.enabled.value.strip().lower() in ("oui","yes","1","true","o")

            save_server_config(self.gid, cfg)

            status = "✅ Activé" if cfg["antiraid"]["caps"] else "❌ Désactivé"

            await interaction.response.send_message(embed=embed_ok(
                f"Anti-Caps mis à jour !\n"
                f"**Statut :** {status}\n"
                f"**Max caps :** {cfg['antiraid']['caps_percent']}%\n"
                f"**Longueur min :** {cfg['antiraid']['caps_min_length']} chars"
            ), ephemeral=True)

        except: await interaction.response.send_message(embed=embed_err("Valeur invalide. Vérifie les champs."), ephemeral=True)

class ModalAntiraidEmoji(discord.ui.Modal, title="😀 Configurer Anti-Emoji Spam"):

    max_emojis = discord.ui.TextInput(label="Nb max d'emojis par message", placeholder="Ex: 5", max_length=3)

    enabled    = discord.ui.TextInput(label="Activer ? (oui / non)", placeholder="oui", max_length=3)

    def __init__(self, gid):

        super().__init__(); self.gid = gid

        cfg = get_server_config(gid).get("antiraid", {})

        self.max_emojis.default = str(cfg.get("max_emojis", 5))

        self.enabled.default    = "oui" if cfg.get("emoji_spam", False) else "non"

    async def on_submit(self, interaction):

        try:

            cfg = get_server_config(self.gid)

            cfg.setdefault("antiraid", {})

            cfg["antiraid"]["max_emojis"]  = max(1, int(self.max_emojis.value.strip()))

            cfg["antiraid"]["emoji_spam"]  = self.enabled.value.strip().lower() in ("oui","yes","1","true","o")

            save_server_config(self.gid, cfg)

            status = "✅ Activé" if cfg["antiraid"]["emoji_spam"] else "❌ Désactivé"

            await interaction.response.send_message(embed=embed_ok(
                f"Anti-Emoji Spam mis à jour !\n"
                f"**Statut :** {status}\n"
                f"**Max emojis :** {cfg['antiraid']['max_emojis']} par message"
            ), ephemeral=True)

        except: await interaction.response.send_message(embed=embed_err("Valeur invalide. Vérifie les champs."), ephemeral=True)

class ModalAntiraidLogChannel(discord.ui.Modal, title="📋 Salon des logs Anti-Raid"):

    channel_id = discord.ui.TextInput(label="ID du salon des logs (0 pour désactiver)", placeholder="Ex: 123456789012345678", max_length=20)

    def __init__(self, gid):

        super().__init__(); self.gid = gid

        cfg = get_server_config(gid).get("antiraid", {})

        if cfg.get("modlog"): self.channel_id.default = str(cfg["modlog"])

    async def on_submit(self, interaction):

        try:

            cid = int(self.channel_id.value.strip())

            cfg = get_server_config(self.gid)

            cfg.setdefault("antiraid", {})

            if cid == 0:

                cfg["antiraid"].pop("modlog", None)

                save_server_config(self.gid, cfg)

                return await interaction.response.send_message(embed=embed_ok("Salon des logs désactivé."), ephemeral=True)

            ch = interaction.guild.get_channel(cid)

            if not ch: return await interaction.response.send_message(embed=embed_err("Salon introuvable avec cet ID."), ephemeral=True)

            cfg["antiraid"]["modlog"] = cid

            save_server_config(self.gid, cfg)

            await interaction.response.send_message(embed=embed_ok(f"Salon des logs défini : {ch.mention}"), ephemeral=True)

        except: await interaction.response.send_message(embed=embed_err("ID invalide."), ephemeral=True)

# ─── ANTIRAID VIEW ───

def build_antiraid_status_embed(guild_id):

    cfg = get_server_config(guild_id).get("antiraid", {})

    antilink = jload(FILES["antilink"]).get(str(guild_id), {})

    e = discord.Embed(title="⚔️ Configuration Anti-Raid & Protection", color=C_BLUE)

    e.add_field(name="🚫 Anti-Spam", value=f"{'✅' if cfg.get('spam') else '❌'} | Seuil: {cfg.get('spam_threshold', DEFAULT_SPAM_THRESHOLD)} msgs/{cfg.get('spam_interval', DEFAULT_SPAM_INTERVAL)}s | Action: {cfg.get('spam_action', 'timeout')}", inline=False)

    e.add_field(name="👥 Anti-Mention", value=f"{'✅' if cfg.get('mention') else '❌'} | Limite: {cfg.get('mention_limit', DEFAULT_MENTION_LIMIT)} | Action: {cfg.get('mention_action', 'timeout')}", inline=False)

    e.add_field(name="⚡ Anti-Join Flood", value=f"{'✅' if cfg.get('join') else '❌'} | Seuil: {cfg.get('join_threshold', DEFAULT_JOIN_THRESHOLD)}/{cfg.get('join_interval', DEFAULT_JOIN_INTERVAL)}s | Action: {cfg.get('join_action', 'log')}", inline=False)

    al = antilink if isinstance(antilink, dict) else {}

    e.add_field(name="🔗 Anti-Lien", value=f"{'✅' if al.get('enabled') else '❌'} | Action: {al.get('action', 'delete')} | Whitelist: {', '.join(al.get('whitelist', [])) or 'Aucune'}", inline=False)

    e.add_field(name="🔤 Anti-Caps", value=f"{'✅' if cfg.get('caps') else '❌'} | Max: {cfg.get('caps_percent', 70)}% sur {cfg.get('caps_min_length', 10)}+ chars", inline=False)

    e.add_field(name="😀 Anti-Emoji Spam", value=f"{'✅' if cfg.get('emoji_spam') else '❌'} | Max: {cfg.get('max_emojis', 5)} emojis", inline=False)

    log_ch = cfg.get("modlog")

    e.add_field(name="📋 Salon des logs", value=f"<#{log_ch}>" if log_ch else "Non défini", inline=False)

    e.set_footer(text="© ModeraBot 2023 - 2026")

    return e

class AntiraidView(discord.ui.View):

    def __init__(self, ctx):

        super().__init__(timeout=None)

        self.ctx = ctx

    @discord.ui.select(placeholder="Configurer la protection...", options=[

        discord.SelectOption(label="Configurer Anti-Spam", emoji="🚫", value="spam"),

        discord.SelectOption(label="Configurer Anti-Mention", emoji="👥", value="mention"),

        discord.SelectOption(label="Configurer Anti-Join Flood", emoji="⚡", value="join"),

        discord.SelectOption(label="Configurer Anti-Lien", emoji="🔗", value="link"),

        discord.SelectOption(label="Configurer Anti-Caps", emoji="🔤", value="caps"),

        discord.SelectOption(label="Configurer Anti-Emoji Spam", emoji="😀", value="emoji"),

        discord.SelectOption(label="Définir le salon des logs", emoji="📋", value="logs"),

        discord.SelectOption(label="Tout désactiver (urgence)", emoji="🔴", value="disable_all"),

        discord.SelectOption(label="Tout activer", emoji="🟢", value="enable_all"),

    ])

    async def select_cb(self, interaction: discord.Interaction, select: discord.ui.Select):

        if interaction.user.id != self.ctx.author.id:

            return await interaction.response.send_message(embed=embed_err("Ce menu n'est pas pour toi."), ephemeral=True)

        v = select.values[0]

        gid = interaction.guild.id

        if v == "spam":

            await interaction.response.send_modal(ModalAntiraidSpam(gid))

        elif v == "mention":

            await interaction.response.send_modal(ModalAntiraidMention(gid))

        elif v == "join":

            await interaction.response.send_modal(ModalAntiraidJoin(gid))

        elif v == "link":

            await interaction.response.send_modal(ModalAntiraidLink(gid))

        elif v == "caps":

            await interaction.response.send_modal(ModalAntiraidCaps(gid))

        elif v == "emoji":

            await interaction.response.send_modal(ModalAntiraidEmoji(gid))

        elif v == "logs":

            await interaction.response.send_modal(ModalAntiraidLogChannel(gid))

        elif v == "disable_all":

            cfg = get_server_config(gid)

            cfg.setdefault("antiraid", {})

            for k in ["spam","mention","join","caps","emoji_spam"]:

                cfg["antiraid"][k] = False

            data = jload(FILES["antilink"])

            if isinstance(data.get(str(gid)), dict): data[str(gid)]["enabled"] = False

            else: data[str(gid)] = {"enabled": False}

            jsave(FILES["antilink"], data)

            save_server_config(gid, cfg)

            await interaction.response.send_message(embed=embed_warn("Toutes les protections **désactivées** !"), ephemeral=True)

        elif v == "enable_all":

            cfg = get_server_config(gid)

            cfg.setdefault("antiraid", {})

            for k in ["spam","mention","join","caps","emoji_spam"]:

                cfg["antiraid"][k] = True

            data = jload(FILES["antilink"])

            if isinstance(data.get(str(gid)), dict): data[str(gid)]["enabled"] = True

            else: data[str(gid)] = {"enabled": True}

            jsave(FILES["antilink"], data)

            save_server_config(gid, cfg)

            await interaction.response.send_message(embed=embed_ok("Toutes les protections **activées** !"), ephemeral=True)

# ─── MODALS MODERATION / NIVEAUX ───

class ModalModoRoles(discord.ui.Modal, title="👮 Rôles modérateurs"):

    roles = discord.ui.TextInput(label="IDs des rôles (séparés par une virgule)", placeholder="Ex: 123456789012345678, 987654321098765432", max_length=300, required=False)

    def __init__(self, gid):
        super().__init__(); self.gid = gid
        cfg = jload(FILES["modo"]).get(str(gid), {})
        if cfg.get("modo_roles"):
            self.roles.default = ", ".join(str(r) for r in cfg["modo_roles"])

    async def on_submit(self, interaction):
        raw = (self.roles.value or "").replace(" ", "")
        ids = []
        for part in raw.split(","):
            if not part:
                continue
            try:
                rid = int(part)
            except ValueError:
                return await interaction.response.send_message(embed=embed_err(f"ID invalide : `{part}`"), ephemeral=True)
            if not interaction.guild.get_role(rid):
                return await interaction.response.send_message(embed=embed_err(f"Rôle introuvable : `{rid}`"), ephemeral=True)
            ids.append(rid)
        data = jload(FILES["modo"])
        data.setdefault(str(self.gid), {})["modo_roles"] = ids
        jsave(FILES["modo"], data)
        try:
            await interaction.message.edit(embed=build_modo_status_embed(self.gid))
        except Exception:
            pass
        if not ids:
            return await interaction.response.send_message(embed=embed_ok("Rôles modérateurs effacés."), ephemeral=True)
        await interaction.response.send_message(embed=embed_ok("Rôles modérateurs : " + " ".join(f"<@&{r}>" for r in ids)), ephemeral=True)


class ModalModoLogChannel(discord.ui.Modal, title="📋 Salon des logs modération"):

    channel_id = discord.ui.TextInput(label="ID du salon (0 pour désactiver)", placeholder="Ex: 123456789012345678", max_length=20)

    def __init__(self, gid):
        super().__init__(); self.gid = gid
        cfg = jload(FILES["modo"]).get(str(gid), {})
        if cfg.get("log_channel"):
            self.channel_id.default = str(cfg["log_channel"])

    async def on_submit(self, interaction):
        try:
            cid = int((self.channel_id.value or "").strip())
        except ValueError:
            return await interaction.response.send_message(embed=embed_err("ID invalide."), ephemeral=True)
        data = jload(FILES["modo"])
        conf = data.setdefault(str(self.gid), {})
        if cid == 0:
            conf.pop("log_channel", None)
            jsave(FILES["modo"], data)
            try:
                await interaction.message.edit(embed=build_modo_status_embed(self.gid))
            except Exception:
                pass
            return await interaction.response.send_message(embed=embed_ok("Salon des logs désactivé."), ephemeral=True)
        ch = interaction.guild.get_channel(cid)
        if not isinstance(ch, discord.TextChannel):
            return await interaction.response.send_message(embed=embed_err("Salon texte introuvable avec cet ID."), ephemeral=True)
        conf["log_channel"] = cid
        jsave(FILES["modo"], data)
        try:
            await interaction.message.edit(embed=build_modo_status_embed(self.gid))
        except Exception:
            pass
        await interaction.response.send_message(embed=embed_ok(f"Salon des logs défini : {ch.mention}"), ephemeral=True)


class ModalLevelSetup(discord.ui.Modal, title="⚙️ Configuration du système XP"):

    xp_channel   = discord.ui.TextInput(label="ID du salon où gagner de l'XP", placeholder="Ex: 123456789012345678", max_length=20)
    xp_min       = discord.ui.TextInput(label="XP minimum par message", placeholder="1", max_length=4, required=False)
    xp_max       = discord.ui.TextInput(label="XP maximum par message", placeholder="5", max_length=4, required=False)
    notif_channel = discord.ui.TextInput(label="Salon des annonces Level Up (optionnel)", placeholder="Vide = même salon", max_length=20, required=False)

    def __init__(self, gid):
        super().__init__(); self.gid = gid
        cfg = get_level_config(gid)
        if cfg.get("xp_channel"):
            self.xp_channel.default = str(cfg["xp_channel"])
        self.xp_min.default = str(cfg.get("xp_min", 1))
        self.xp_max.default = str(cfg.get("xp_max", 5))
        if cfg.get("notif_channel"):
            self.notif_channel.default = str(cfg["notif_channel"])

    async def on_submit(self, interaction):
        try:
            cid = int((self.xp_channel.value or "").strip())
        except ValueError:
            return await interaction.response.send_message(embed=embed_err("ID de salon invalide."), ephemeral=True)
        ch = interaction.guild.get_channel(cid)
        if not isinstance(ch, discord.TextChannel):
            return await interaction.response.send_message(embed=embed_err("Salon texte introuvable avec cet ID."), ephemeral=True)

        def _int(field, default):
            try:
                return max(0, int((field.value or "").strip()))
            except ValueError:
                return default

        xmin = _int(self.xp_min, 1)
        xmax = _int(self.xp_max, 5)
        if xmax < xmin:
            xmin, xmax = xmax, xmin

        notif = None
        raw_notif = (self.notif_channel.value or "").strip()
        if raw_notif:
            try:
                nch = interaction.guild.get_channel(int(raw_notif))
            except ValueError:
                nch = None
            if not isinstance(nch, discord.TextChannel):
                return await interaction.response.send_message(embed=embed_err("Salon d'annonces introuvable."), ephemeral=True)
            notif = nch.id

        cfg = get_level_config(self.gid)
        cfg["xp_channel"] = cid
        cfg["xp_min"] = xmin
        cfg["xp_max"] = xmax
        cfg["notif_channel"] = notif
        cfg.setdefault("members", {})
        save_level_config(self.gid, cfg)
        try:
            await interaction.message.edit(embed=build_level_status_embed(self.gid))
        except Exception:
            pass
        await interaction.response.send_message(
            embed=embed_ok(f"Système XP configuré : {ch.mention} • {xmin}-{xmax} XP/message"), ephemeral=True)


# ─── MODERATION VIEW ───

def build_modo_status_embed(guild_id):

    cfg = jload(FILES["modo"]).get(str(guild_id), {})

    e = discord.Embed(title="🛡️ Configuration Modération", color=C_BLUE)

    roles = cfg.get("modo_roles", [])

    e.add_field(name="👮 Rôles modérateurs", value=" ".join(f"<@&{r}>" for r in roles) if roles else "Non configurés", inline=False)

    log_ch = cfg.get("log_channel")

    e.add_field(name="📋 Salon des logs", value=f"<#{log_ch}>" if log_ch else "Non défini", inline=False)

    e.add_field(name="⚙️ Actions disponibles", value="`+ban` `+unban` `+kick` `+mute` `+unmute` `+warn` `+clear`", inline=False)

    e.set_footer(text="© ModeraBot 2023 - 2026")

    return e

class ModoView(discord.ui.View):

    def __init__(self, ctx):

        super().__init__(timeout=None)

        self.ctx = ctx

    @discord.ui.select(placeholder="Configurer la modération...", options=[

        discord.SelectOption(label="Définir les rôles modérateurs", emoji="👮", value="roles"),

        discord.SelectOption(label="Définir le salon des logs", emoji="📋", value="logs"),

    ])

    async def select_cb(self, interaction: discord.Interaction, select: discord.ui.Select):

        if interaction.user.id != self.ctx.author.id:

            return await interaction.response.send_message(embed=embed_err("Ce menu n'est pas pour toi."), ephemeral=True)

        v = select.values[0]

        gid = interaction.guild.id

        if v == "roles":

            await interaction.response.send_modal(ModalModoRoles(gid))

        elif v == "logs":

            await interaction.response.send_modal(ModalModoLogChannel(gid))

# ─── LEVEL VIEW ───

def build_level_status_embed(guild_id):

    cfg = get_level_config(guild_id)

    e = discord.Embed(title="📊 Configuration Niveaux", color=C_BLUE)

    ch = cfg.get("xp_channel")

    e.add_field(name="💬 Salon XP", value=f"<#{ch}>" if ch else "Non défini", inline=False)

    e.add_field(name="✨ XP par message", value=f"{cfg.get('xp_min', 1)} - {cfg.get('xp_max', 5)}", inline=False)

    notif = cfg.get("notif_channel")

    e.add_field(name="🔔 Salon Level Up", value=f"<#{notif}>" if notif else "Même salon", inline=False)

    total = len(cfg.get("members", {}))

    e.add_field(name="👥 Membres suivis", value=str(total), inline=False)

    e.set_footer(text="© ModeraBot 2023 - 2026")

    return e

class LevelView(discord.ui.View):

    def __init__(self, ctx):

        super().__init__(timeout=None)

        self.ctx = ctx

    @discord.ui.select(placeholder="Configurer les niveaux...", options=[

        discord.SelectOption(label="Configurer le système XP", emoji="⚙️", value="setup"),

        discord.SelectOption(label="Réinitialiser le classement", emoji="🔄", value="reset"),

    ])

    async def select_cb(self, interaction: discord.Interaction, select: discord.ui.Select):

        if interaction.user.id != self.ctx.author.id:

            return await interaction.response.send_message(embed=embed_err("Ce menu n'est pas pour toi."), ephemeral=True)

        v = select.values[0]

        if v == "setup":

            await interaction.response.send_modal(ModalLevelSetup(interaction.guild.id))

        elif v == "reset":

            cfg = get_level_config(interaction.guild.id)

            cfg["members"] = {}

            save_level_config(interaction.guild.id, cfg)

            await interaction.response.send_message(embed=embed_ok("Classement XP réinitialisé !"), ephemeral=True)

# ══════════════════════════════════════════

# COMMANDES PRÉFIXE +

# ══════════════════════════════════════════

@bot.command(name="welcome", aliases=["welcom","welcum","wlcm","bienvenue"])

async def welcome_cmd(ctx):

    if not ctx.author.guild_permissions.administrator and str(ctx.author.id) not in OWNER_IDS:

        return await ctx.send(embed=embed_err("Permission administrateur requise."))

    await ctx.send(embed=build_welcome_status_embed(ctx.guild.id), view=WelcomeView(ctx))

@bot.command(name="giveaway", aliases=["gw","tirage","giveaways"])

async def giveaway_cmd(ctx):

    if not is_modo(ctx.author):

        return await ctx.send(embed=embed_err("Tu n'as pas la permission."))

    await ctx.send(embed=build_giveaway_status_embed(ctx.guild.id), view=GiveawayView(ctx))

# ─── +greroll ──────────────────────────────────────────────────────────────────

@bot.command(name="greroll", aliases=["gw-reroll","gwreroll","reroll-giveaway","rerollgw"])

async def greroll_cmd(ctx, message_id: int = None, nb_gagnants: int = None):

    if not is_modo(ctx.author):

        return await ctx.send(embed=embed_err("Tu n'as pas la permission."))

    if not message_id:

        return await ctx.send(embed=embed_err("Usage : `+greroll <message_id> [nombre_gagnants]`\nTu dois fournir l'ID du message du giveaway terminé."))

    # Chercher le message dans tous les salons du serveur
    target_msg = None

    for ch in ctx.guild.text_channels:

        try:

            target_msg = await ch.fetch_message(message_id)

            break

        except: continue

    if not target_msg:

        return await ctx.send(embed=embed_err(f"Message `{message_id}` introuvable sur ce serveur."))

    # Récupérer les réactions du message
    participants = set()

    emoji_used = None

    for reaction in target_msg.reactions:

        users = [u async for u in reaction.users() if not u.bot and u.id != ctx.author.id]

        if users:

            emoji_used = str(reaction.emoji)

            participants = set(u.id for u in users)

            break

    if not participants:

        return await ctx.send(embed=embed_err("Aucun participant valide trouvé sur ce message."))

    nb = nb_gagnants or 1

    nb = max(1, min(nb, len(participants)))

    winners = random.sample(list(participants), nb)

    mentions = ", ".join(f"<@{w}>" for w in winners)

    e = discord.Embed(title="🔁 REROLL GIVEAWAY", color=C_GOLD)

    e.add_field(name="🏆 Nouveau(x) gagnant(s)", value=mentions, inline=False)

    e.add_field(name="🔗 Message original", value=f"[Cliquez ici]({target_msg.jump_url})", inline=False)

    e.set_footer(text=f"Reroll effectué par {ctx.author} • {nb} gagnant(s)")

    await ctx.send(embed=e)

    await ctx.send(f"🎉 Félicitations {mentions} ! Vous êtes le(s) nouveau(x) gagnant(s) !")

# ─── +gsend ────────────────────────────────────────────────────────────────────

@bot.command(name="gsend", aliases=["gw-send","gwsend","send-giveaway","sendgw","lancergw","lancergiveaway"])

async def gsend_cmd(ctx, salon: discord.TextChannel = None, duree: str = None, gagnants: int = None, *, gain: str = None):

    if not is_modo(ctx.author):

        return await ctx.send(embed=embed_err("Tu n'as pas la permission."))

    if not salon or not duree or not gagnants or not gain:

        e = discord.Embed(title="📋 Utilisation de +gsend", color=C_BLUE)

        e.description = (

            "**Usage :** `+gsend #salon durée nb_gagnants lot`\n\n"

            "**Durée :** `30s` · `10m` · `2h` · `1j`\n\n"

            "**Exemples :**\n"

            "`+gsend #général 1h 1 Nitro Discord`\n"

            "`+gsend #giveaways 30m 3 Rôle VIP`"

        )

        return await ctx.send(embed=e)

    # Parser la durée
    unit = duree[-1].lower()

    try: value = int(duree[:-1])

    except:

        return await ctx.send(embed=embed_err("Durée invalide. Exemples : `30s`, `10m`, `2h`, `1j`"))

    delta_map = {"s": timedelta(seconds=value), "m": timedelta(minutes=value), "h": timedelta(hours=value), "j": timedelta(days=value)}

    if unit not in delta_map:

        return await ctx.send(embed=embed_err("Unité invalide. Utilise `s`, `m`, `h` ou `j`."))

    delta = delta_map[unit]

    end_time = discord.utils.utcnow() + delta

    emoji = "🎉"

    e = discord.Embed(title=f"{emoji} GIVEAWAY {emoji}", color=C_BLUE)

    e.description = (

        f"🎁 **Gain :** {gain}\n"

        f"👤 **Organisé par :** {ctx.author.mention}\n"

        f"🏆 **Gagnants :** {gagnants}\n"

        f"👥 **Participants :** 0\n"

        f"⏳ **Fin :** <t:{int(end_time.timestamp())}:R>\n\n"

        f"Réagis avec {emoji} pour participer !"

    )

    e.set_footer(text=f"ModeraBot • Giveaway lancé par {ctx.author}")

    msg = await salon.send(embed=e)

    await msg.add_reaction(emoji)

    if salon.id != ctx.channel.id:

        await ctx.send(embed=discord.Embed(description=f"✅ Giveaway lancé dans {salon.mention} ! [Voir le message]({msg.jump_url})", color=C_GREEN))

    giveaways[msg.id] = {

        "end": end_time,

        "gagnants": gagnants,

        "gain": gain,

        "participants": set(),

        "data": {"gain": gain, "duree": duree, "gagnants": gagnants, "emoji": emoji},

        "organizer_id": ctx.author.id

    }

    async def update_loop():

        while discord.utils.utcnow() < end_time:

            try:

                fetched = await salon.fetch_message(msg.id)

                r = discord.utils.get(fetched.reactions, emoji=emoji)

                if r:

                    users = [u async for u in r.users() if not u.bot]

                    giveaways[msg.id]["participants"] = set(u.id for u in users)

                    e.description = (

                        f"🎁 **Gain :** {gain}\n"

                        f"👤 **Organisé par :** {ctx.author.mention}\n"

                        f"🏆 **Gagnants :** {gagnants}\n"

                        f"👥 **Participants :** {len(users)}\n"

                        f"⏳ **Fin :** <t:{int(end_time.timestamp())}:R>\n\n"

                        f"Réagis avec {emoji} pour participer !"

                    )

                    await fetched.edit(embed=e)

            except: pass

            await asyncio.sleep(15)

    asyncio.create_task(update_loop())

    await asyncio.sleep(delta.total_seconds())

    d = giveaways.pop(msg.id, None)

    if d:

        d["participants"].discard(bot.user.id)

        d["participants"].discard(ctx.author.id)

    if not d or not d["participants"]:

        return await salon.send("❌ Giveaway terminé : aucun participant valide.")

    winners = random.sample(list(d["participants"]), min(gagnants, len(d["participants"])))

    mentions = ", ".join(f"<@{w}>" for w in winners)

    end_e = discord.Embed(title="🎉 GIVEAWAY TERMINÉ !", color=C_GOLD)

    end_e.add_field(name="🏆 Gagnant(s)", value=mentions, inline=False)

    end_e.add_field(name="🎁 Gain", value=gain, inline=False)

    await salon.send(embed=end_e)

    await salon.send(f"🎉 Félicitations {mentions} ! Tu as gagné **{gain}** !")

@bot.command(name="antiraid", aliases=["protection","protect","raid"])

async def antiraid_cmd(ctx):

    if not ctx.author.guild_permissions.administrator and str(ctx.author.id) not in OWNER_IDS:

        return await ctx.send(embed=embed_err("Permission administrateur requise."))

    await ctx.send(embed=build_antiraid_status_embed(ctx.guild.id), view=AntiraidView(ctx))

@bot.command(name="antilink", aliases=["antilien"])

async def antilink_cmd(ctx):

    if not ctx.author.guild_permissions.administrator and str(ctx.author.id) not in OWNER_IDS:

        return await ctx.send(embed=embed_err("Permission administrateur requise."))

    # Shortcut: ouvre directement le modal anti-lien

    await ctx.send(embed=build_antiraid_status_embed(ctx.guild.id), view=AntiraidView(ctx))

@bot.command(name="modo", aliases=["modoconfig","modo-config","moderation"])

async def modo_cmd(ctx):

    if not ctx.author.guild_permissions.administrator and str(ctx.author.id) not in OWNER_IDS:

        return await ctx.send(embed=embed_err("Permission administrateur requise."))

    await ctx.send(embed=build_modo_status_embed(ctx.guild.id), view=ModoView(ctx))

@bot.command(name="setup", aliases=["level-setup","levelsetup","xpsetup","niveaux"])

async def setup_cmd(ctx):

    if not ctx.author.guild_permissions.administrator and str(ctx.author.id) not in OWNER_IDS:

        return await ctx.send(embed=embed_err("Permission administrateur requise."))

    await ctx.send(embed=build_level_status_embed(ctx.guild.id), view=LevelView(ctx))

# ─── ANTI-BOT (HONEYPOT) ───

def _antibot_cfg(gid):

    return jload(FILES["antibot"]).get(str(gid), {})

def _antibot_save(gid, data):

    all_data = jload(FILES["antibot"])

    all_data[str(gid)] = data

    jsave(FILES["antibot"], all_data)

def _antibot_emoji(guild):

    return discord.utils.get(guild.emojis, name="moderabot")

def _antibot_panel_embed(guild, total):

    emoji = _antibot_emoji(guild)

    e = discord.Embed(

        title=f"{emoji or '🚫'} NE PAS ÉCRIRE DANS CE SALON",

        description=(

            "Ce salon sert de piège à bots/spammeurs.\n\n"

            "• **1er et 2e message ici → expulsion (kick)**\n"

            "• **3e message → bannissement définitif**"

        ),

        color=C_RED,

    )

    if emoji:

        e.set_thumbnail(url=emoji.url)

    e.set_footer(text=f"{total} incident(s) enregistré(s)")

    return e

class AntibotPanelView(discord.ui.View):

    def __init__(self, total=0):

        super().__init__(timeout=None)

        btn = discord.ui.Button(

            label=f"Voir l'historique ({total})",

            emoji="🍯",

            style=discord.ButtonStyle.secondary,

            custom_id="antibot_view_history",

        )

        btn.callback = self._on_click

        self.add_item(btn)

    async def _on_click(self, interaction: discord.Interaction):

        if not interaction.guild:

            return await interaction.response.send_message("Erreur.", ephemeral=True)

        if not is_modo(interaction.user):

            return await interaction.response.send_message("Réservé aux modérateurs.", ephemeral=True)

        cfg = _antibot_cfg(interaction.guild.id)

        offenders = cfg.get("offenders", {})

        total = cfg.get("kicks", 0)

        if not offenders:

            desc = "Aucun incident enregistré pour le moment."

        else:

            sorted_off = sorted(offenders.items(), key=lambda x: x[1].get("count", 0), reverse=True)

            lines = []

            for uid, info in sorted_off[:25]:

                name = info.get("username", uid)

                count = info.get("count", 0)

                status = "🔨 Banni définitivement" if count >= 3 else f"👢 {count} kick(s)"

                lines.append(f"**{name}** — {status}")

            desc = "\n".join(lines)

        e = discord.Embed(title="🍯 Historique Anti-Bot", description=desc, color=C_ORANGE)

        e.set_footer(text=f"Total incidents : {total}")

        await interaction.response.send_message(embed=e, ephemeral=True)

async def _create_antibot_channel(guild):

    overwrites = {

        guild.default_role: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),

        guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_messages=True),

    }

    for role in guild.roles:

        if role.permissions.administrator or role.permissions.manage_guild:

            overwrites[role] = discord.PermissionOverwrite(view_channel=True, send_messages=False)

    channel = await guild.create_text_channel(

        name="moderabot",

        overwrites=overwrites,

        reason="Création du salon Anti-Bot (honeypot)",

        topic="⚠️ Ne postez rien ici — salon piège anti-bot géré par ModeraBot.",

    )

    return channel

@bot.command(name="antibot", aliases=["honeypot","antibots"])

async def antibot_cmd(ctx):

    if not is_modo(ctx.author):

        return await ctx.send(embed=embed_err("Tu n'as pas la permission."))

    cfg = _antibot_cfg(ctx.guild.id)

    existing_channel = ctx.guild.get_channel(cfg.get("channel_id")) if cfg.get("channel_id") else None

    if existing_channel:

        return await ctx.send(embed=embed_err(f"Le salon Anti-Bot existe déjà : {existing_channel.mention}"))

    try:

        channel = await _create_antibot_channel(ctx.guild)

    except discord.Forbidden:

        return await ctx.send(embed=embed_err("Je n'ai pas la permission de créer un salon."))

    total = cfg.get("kicks", 0)

    msg = await channel.send(embed=_antibot_panel_embed(ctx.guild, total), view=AntibotPanelView(total))

    _antibot_save(ctx.guild.id, {

        "channel_id": channel.id,

        "message_id": msg.id,

        "kicks": total,

        "offenders": cfg.get("offenders", {}),

    })

    await ctx.send(embed=embed_ok(f"Salon Anti-Bot créé : {channel.mention}"))

async def _handle_antibot(message):

    if not message.guild:

        return False

    cfg = _antibot_cfg(message.guild.id)

    channel_id = cfg.get("channel_id")

    if not channel_id or message.channel.id != channel_id:

        return False

    member = message.author

    if is_modo(member) or member.guild_permissions.administrator:

        return False

    try:

        await message.delete()

    except Exception:

        pass

    offenders = cfg.setdefault("offenders", {})

    uid = str(member.id)

    entry = offenders.get(uid, {"username": str(member), "count": 0})

    entry["username"] = str(member)

    entry["count"] += 1

    offenders[uid] = entry

    count = entry["count"]

    if count >= 3:

        reason = "Anti-Bot : 3e message dans le salon honeypot — bannissement définitif"

        try:

            await message.guild.ban(member, reason=reason, delete_message_seconds=3600)

        except Exception:

            pass

    else:

        reason = f"Anti-Bot : message dans le salon honeypot ({count}/3) — expulsion"

        try:

            await member.kick(reason=reason)

        except Exception:

            pass

    cfg["kicks"] = cfg.get("kicks", 0) + 1

    _antibot_save(message.guild.id, cfg)

    try:

        channel = message.guild.get_channel(cfg["channel_id"])

        panel_msg = await channel.fetch_message(cfg["message_id"])

        await panel_msg.edit(embed=_antibot_panel_embed(message.guild, cfg["kicks"]), view=AntibotPanelView(cfg["kicks"]))

    except Exception:

        pass

    return True

# ─── MODERATION COMMANDS ───

@bot.command(name="ban", aliases=["bannir","bann"])

async def ban_cmd(ctx, member: discord.Member = None, *, reason="Aucune raison fournie"):

    if not is_modo(ctx.author):

        return await ctx.send(embed=embed_err("Tu n'as pas la permission."))

    if not member:

        return await ctx.send(embed=embed_err("Usage : `+ban @membre [raison]`"))

    await send_sanction_mp(member, "BAN", reason, ctx.author.name, ctx.guild.name)

    try:

        await member.ban(reason=reason)

    except:

        return await ctx.send(embed=embed_err("Impossible de bannir ce membre."))

    e = discord.Embed(title="🔨 Membre banni", color=C_RED)

    e.add_field(name="Membre", value=f"{member} (`{member.id}`)", inline=True)

    e.add_field(name="Modérateur", value=ctx.author.mention, inline=True)

    e.add_field(name="Raison", value=reason, inline=False)

    await ctx.send(embed=e)

    await _log_action(ctx.guild, "BAN", ctx.author, member, reason)

@bot.command(name="unban", aliases=["débannir","deban"])

async def unban_cmd(ctx, *, user_str=None):

    if not is_modo(ctx.author):

        return await ctx.send(embed=embed_err("Tu n'as pas la permission."))

    if not user_str:

        return await ctx.send(embed=embed_err("Usage : `+unban ID_ou_nom#0000`"))

    async for ban_entry in ctx.guild.bans():

        if str(ban_entry.user) == user_str or str(ban_entry.user.id) == user_str:

            await ctx.guild.unban(ban_entry.user)

            return await ctx.send(embed=embed_ok(f"**{ban_entry.user}** a été débanni."))

    await ctx.send(embed=embed_warn("Utilisateur introuvable dans les bannis."))

@bot.command(name="kick", aliases=["exclure","virer"])

async def kick_cmd(ctx, member: discord.Member = None, *, reason="Aucune raison"):

    if not is_modo(ctx.author):

        return await ctx.send(embed=embed_err("Tu n'as pas la permission."))

    if not member:

        return await ctx.send(embed=embed_err("Usage : `+kick @membre [raison]`"))

    await send_sanction_mp(member, "KICK", reason, ctx.author.name, ctx.guild.name)

    try:

        await member.kick(reason=reason)

    except:

        return await ctx.send(embed=embed_err("Impossible d'exclure ce membre."))

    e = discord.Embed(title="👢 Membre exclu", color=C_ORANGE)

    e.add_field(name="Membre", value=str(member), inline=True)

    e.add_field(name="Raison", value=reason, inline=False)

    await ctx.send(embed=e)

    await _log_action(ctx.guild, "KICK", ctx.author, member, reason)

@bot.command(name="mute", aliases=["silence"])

async def mute_cmd(ctx, member: discord.Member = None, duration="10m", *, reason="Aucune raison"):

    if not is_modo(ctx.author):

        return await ctx.send(embed=embed_err("Tu n'as pas la permission."))

    if not member:

        return await ctx.send(embed=embed_err("Usage : `+mute @membre [durée] [raison]`"))

    mute_role = discord.utils.get(ctx.guild.roles, name="Muted")

    if not mute_role:

        mute_role = await ctx.guild.create_role(name="Muted", color=discord.Color.dark_gray())

        for ch in ctx.guild.channels:

            try: await ch.set_permissions(mute_role, send_messages=False, speak=False)

            except: pass

    await member.add_roles(mute_role)

    await send_sanction_mp(member, "MUTE", reason, ctx.author.name, ctx.guild.name, duration)

    e = discord.Embed(title="🔇 Membre mute", color=C_ORANGE)

    e.add_field(name="Membre", value=member.mention, inline=True)

    e.add_field(name="Durée", value=duration, inline=True)

    e.add_field(name="Raison", value=reason, inline=False)

    await ctx.send(embed=e)

    await _log_action(ctx.guild, "MUTE", ctx.author, member, reason)

@bot.command(name="unmute", aliases=["démute"])

async def unmute_cmd(ctx, member: discord.Member = None):

    if not is_modo(ctx.author):

        return await ctx.send(embed=embed_err("Tu n'as pas la permission."))

    if not member:

        return await ctx.send(embed=embed_err("Usage : `+unmute @membre`"))

    mute_role = discord.utils.get(ctx.guild.roles, name="Muted")

    if mute_role and mute_role in member.roles:

        await member.remove_roles(mute_role)

        await ctx.send(embed=embed_ok(f"{member.mention} a été unmute."))

    else:

        await ctx.send(embed=embed_warn("Ce membre n'est pas mute."))

@bot.command(name="warn", aliases=["avertir","avertissement"])

async def warn_cmd(ctx, member: discord.Member = None, *, reason="Aucune raison"):

    if not is_modo(ctx.author):

        return await ctx.send(embed=embed_err("Tu n'as pas la permission."))

    if not member:

        return await ctx.send(embed=embed_err("Usage : `+warn @membre [raison]`"))

    await send_sanction_mp(member, "WARN", reason, ctx.author.name, ctx.guild.name)

    e = discord.Embed(title="⚠️ Avertissement", color=C_ORANGE)

    e.add_field(name="Membre", value=member.mention, inline=True)

    e.add_field(name="Modérateur", value=ctx.author.mention, inline=True)

    e.add_field(name="Raison", value=reason, inline=False)

    await ctx.send(embed=e)

    await _log_action(ctx.guild, "WARN", ctx.author, member, reason)

@bot.command(name="clear", aliases=["purge","supprimer","clean"])

async def clear_cmd(ctx, amount: int = None):

    if not is_modo(ctx.author):

        return await ctx.send(embed=embed_err("Tu n'as pas la permission."))

    if not amount:

        return await ctx.send(embed=embed_err("Usage : `+clear [nombre]`"))

    deleted = await ctx.channel.purge(limit=amount + 1)

    msg = await ctx.send(embed=embed_ok(f"**{len(deleted)-1}** message(s) supprimé(s)."))

    await asyncio.sleep(3)

    try: await msg.delete()

    except: pass

async def _log_action(guild, action, mod, target, reason):

    cfg = jload(FILES["modo"]).get(str(guild.id), {})

    log_ch_id = cfg.get("log_channel")

    if not log_ch_id: return

    ch = guild.get_channel(log_ch_id)

    if not ch: return

    colors = {"BAN": C_RED, "KICK": C_ORANGE, "MUTE": C_ORANGE, "WARN": C_GOLD, "UNBAN": C_GREEN, "UNMUTE": C_GREEN}

    e = discord.Embed(title=f"📋 Log • {action}", color=colors.get(action, C_BLUE), timestamp=discord.utils.utcnow())

    e.add_field(name="👮 Modérateur", value=mod.mention, inline=True)

    e.add_field(name="🎯 Cible", value=target.mention, inline=True)

    e.add_field(name="📝 Raison", value=reason, inline=False)

    try: await ch.send(embed=e, allowed_mentions=MENTIONS_LOGS)

    except: pass

# ─── UTILITY COMMANDS ───

# ─── PING (Container V2) ──────────────────────────────────────────────────────

def _ping_quality(lat):
    """(libellé, couleur) selon la latence en ms."""
    if lat < 80:
        return "🟢 Excellent", C_GREEN
    if lat < 150:
        return "🟡 Correct", C_ORANGE
    if lat < 300:
        return "🟠 Lent", 0xE67E22
    return "🔴 Critique", C_RED


def _ping_bar(lat, blocks=12, worst=400):
    """Jauge visuelle : plus elle est remplie, meilleure est la connexion."""
    ratio = 1 - (min(max(lat, 0), worst) / worst)
    filled = max(1, min(blocks, round(ratio * blocks)))
    return "▰" * filled + "▱" * (blocks - filled)


def _ping_uptime():
    elapsed = int(_time.time() - _BOT_START_TIME)
    j, rest = divmod(elapsed, 86400)
    h, rest = divmod(rest, 3600)
    m, sec = divmod(rest, 60)
    if j:
        return f"{j}j {h}h {m}min"
    if h:
        return f"{h}h {m}min"
    return f"{m}min {sec}s"


if _v2_available():

    class PingView(discord.ui.LayoutView):
        """Carte de latence en Components V2, avec bouton de rafraîchissement."""

        def __init__(self, author, gateway, api=None, aller_retour=None):
            super().__init__(timeout=180)
            self.author_id = getattr(author, "id", author)
            self.build(author, gateway, api, aller_retour)

        def build(self, author, gateway, api, aller_retour):
            for child in list(self.children):
                self.remove_item(child)

            label, color = _ping_quality(gateway)
            cont = discord.ui.Container(accent_colour=discord.Colour(color))

            cont.add_item(discord.ui.TextDisplay(
                f"## 🏓 Pong !\n-# Connexion entre **{bot.user.name}** et Discord"
            ))
            cont.add_item(discord.ui.TextDisplay(
                f"### {_ping_bar(gateway)}  `{gateway} ms`\n**Qualité du lien :** {label}"
            ))
            cont.add_item(discord.ui.Separator())

            mesures = [f"📡 **Passerelle**\n`{gateway} ms` — WebSocket temps réel"]
            if api is not None:
                mesures.append(f"⚡ **API REST**\n`{api} ms` — envoi du message")
            if aller_retour is not None:
                mesures.append(f"🔁 **Aller-retour**\n`{aller_retour} ms` — commande → réponse")
            else:
                mesures.append("🔁 **Aller-retour**\n`mesure...`")
            cont.add_item(discord.ui.TextDisplay("\n\n".join(mesures)))

            cont.add_item(discord.ui.Separator())
            cont.add_item(discord.ui.TextDisplay(
                f"🖥️ **Serveurs** `{len(bot.guilds)}`  ・  "
                f"⏱️ **En ligne depuis** `{_ping_uptime()}`  ・  "
                f"🧩 **Shard** `{(bot.shard_id or 0) + 1}/{bot.shard_count or 1}`"
            ))

            row = discord.ui.ActionRow()
            bouton = discord.ui.Button(label="Rafraîchir", emoji="🔄",
                                       style=discord.ButtonStyle.secondary)
            bouton.callback = self._on_refresh
            row.add_item(bouton)
            cont.add_item(row)

            cont.add_item(discord.ui.TextDisplay(
                f"-# Demandé par {getattr(author, 'display_name', author)} • "
                f"<t:{int(_time.time())}:R>"
            ))
            self.add_item(cont)

        async def _on_refresh(self, interaction: discord.Interaction):
            if interaction.user.id != self.author_id:
                return await interaction.response.send_message(
                    embed=embed_err("Cette commande n'est pas la tienne."), ephemeral=True)
            debut = _time.perf_counter()
            await interaction.response.defer()
            api = round((_time.perf_counter() - debut) * 1000)
            self.build(interaction.user, round(bot.latency * 1000), api, api)
            await interaction.edit_original_response(view=self)

else:
    PingView = None


@bot.command(name="ping")

async def ping_cmd(ctx):

    gateway = round(bot.latency * 1000)

    if PingView is None:   # discord.py trop ancien : ancien affichage

        label, color = _ping_quality(gateway)

        e = discord.Embed(title="🏓 Pong !", color=color)

        e.add_field(name="📡 Latence", value=f"**{gateway} ms**", inline=True)

        e.add_field(name="📶 Statut", value=label, inline=True)

        return await ctx.send(embed=e)

    debut = _time.perf_counter()

    vue = PingView(ctx.author, gateway)

    msg = await ctx.send(view=vue)

    api = round((_time.perf_counter() - debut) * 1000)

    aller_retour = round((discord.utils.utcnow() - ctx.message.created_at).total_seconds() * 1000)

    vue.build(ctx.author, round(bot.latency * 1000), api, max(aller_retour, api))

    try:

        await msg.edit(view=vue)

    except Exception:

        pass


@bot.command(name="userinfo", aliases=["ui","profil","info"])

async def userinfo_cmd(ctx, member: discord.Member = None):

    member = member or ctx.author

    roles = [r.mention for r in member.roles if r != ctx.guild.default_role]

    e = discord.Embed(title=f"👤 {member.display_name}", color=C_BLUE)

    e.set_thumbnail(url=member.display_avatar.url)

    e.add_field(name="🆔 ID", value=f"`{member.id}`", inline=True)

    e.add_field(name="🤖 Bot", value="Oui" if member.bot else "Non", inline=True)

    e.add_field(name="📅 Compte créé", value=discord.utils.format_dt(member.created_at, style="R"), inline=False)

    e.add_field(name="📥 A rejoint", value=discord.utils.format_dt(member.joined_at, style="R") if member.joined_at else "Inconnu", inline=False)

    e.add_field(name=f"🎭 Rôles ({len(roles)})", value=" ".join(roles[:10]) + ("..." if len(roles) > 10 else "") if roles else "Aucun", inline=False)

    e.set_footer(text=f"Demandé par {ctx.author}")

    await ctx.send(embed=e)

@bot.command(name="serverinfo", aliases=["si","server"])

async def serverinfo_cmd(ctx):

    g = ctx.guild

    e = discord.Embed(title=f"🏠 {g.name}", color=C_BLUE)

    if g.icon: e.set_thumbnail(url=g.icon.url)

    e.add_field(name="👑 Propriétaire", value=g.owner.mention if g.owner else "Inconnu", inline=True)

    e.add_field(name="👥 Membres", value=f"**{g.member_count}**", inline=True)

    e.add_field(name="📅 Créé", value=discord.utils.format_dt(g.created_at, style="R"), inline=True)

    e.add_field(name="💬 Salons", value=f"{len(g.text_channels)} texte / {len(g.voice_channels)} vocal", inline=True)

    e.add_field(name="🎭 Rôles", value=str(len(g.roles)), inline=True)

    e.add_field(name="🆔 ID", value=f"`{g.id}`", inline=True)

    await ctx.send(embed=e)

@bot.command(name="botinfo", aliases=["bi"])

async def botinfo_cmd(ctx):

    pfx = _prefix_cache.get(ctx.guild.id, DEFAULT_PREFIX) if ctx.guild else DEFAULT_PREFIX

    members  = sum((g.member_count or 0) for g in bot.guilds)
    channels = sum(len(g.channels) for g in bot.guilds)
    elapsed  = int(_time.time() - _BOT_START_TIME)
    j, r = divmod(elapsed, 86400)
    h, r = divmod(r, 3600)
    m, sec = divmod(r, 60)
    uptime = (f"{j}j {h}h {m}m" if j else (f"{h}h {m}m {sec}s" if h else f"{m}m {sec}s"))

    e = discord.Embed(
        title=f"🤖 {bot.user.name}",
        description=(
            f"Bot de modération **100 % français** 🇫🇷 — préfixe **`{pfx}`**\n"
            f"Tape **`{pfx}aide`** pour voir les {len(bot.commands)} commandes."
        ),
        color=C_BLUE
    )

    if bot.user.avatar: e.set_thumbnail(url=bot.user.avatar.url)

    e.add_field(name="🏠 Serveurs", value=f"**{len(bot.guilds)}**", inline=True)
    e.add_field(name="👥 Membres", value=f"**{members:,}**".replace(",", " "), inline=True)
    e.add_field(name="📺 Salons", value=f"**{channels}**", inline=True)

    e.add_field(name="📡 Latence", value=f"**{round(bot.latency*1000)} ms**", inline=True)
    e.add_field(name="⏱️ Uptime", value=f"**{uptime}**", inline=True)
    e.add_field(name="⚙️ Commandes", value=f"**{len(bot.commands)}**", inline=True)

    e.add_field(name="📦 Version", value="**v4.0**", inline=True)
    e.add_field(name="📚 discord.py", value=f"**{discord.__version__}**", inline=True)
    e.add_field(name="🐍 Python", value=f"**{platform.python_version()}**", inline=True)

    e.add_field(name="👑 Fondateurs", value=" ".join(f"<@{o}>" for o in OWNER_IDS) or "Non défini", inline=False)

    e.add_field(
        name="🔗 Liens",
        value=(
            f"[Support]({PREMIUM_LINK}) ・ "
            f"[Inviter le bot](https://discord.com/oauth2/authorize?client_id={bot.user.id}&permissions=8&scope=bot) ・ "
            f"[Premium]({PREMIUM_LINK})"
        ),
        inline=False
    )

    e.set_footer(text="ModeraBot • Bot français 🇫🇷")

    await ctx.send(embed=e)

@bot.command(name="servericon", aliases=["icon"])

async def servericon_cmd(ctx):

    if not ctx.guild.icon:

        return await ctx.send(embed=embed_warn("Ce serveur n'a pas d'icône."))

    e = discord.Embed(title=f"🖼️ {ctx.guild.name}", color=C_BLUE)

    e.set_image(url=ctx.guild.icon.url)

    await ctx.send(embed=e)

@bot.command(name="roles")

async def roles_cmd(ctx):

    r = [role.mention for role in ctx.guild.roles if role != ctx.guild.default_role]

    e = discord.Embed(title=f"🎭 Rôles de {ctx.guild.name}", color=C_BLUE)

    e.add_field(name=f"Total : {len(r)}", value=", ".join(r[:30]) + ("..." if len(r) > 30 else "") if r else "Aucun", inline=False)

    await ctx.send(embed=e)

@bot.command(name="say", aliases=["parler"])

async def say_cmd(ctx, *, message=None):

    if not (ctx.author.guild_permissions.administrator or str(ctx.author.id) in OWNER_IDS):

        return await ctx.send(embed=embed_err("Permission administrateur requise."))

    if not message:

        return await ctx.send(embed=embed_err("Usage : `+say [message]`"))

    await ctx.message.delete()

    await ctx.send(message)

@bot.command(name="variables")

async def variables_cmd(ctx):

    e = discord.Embed(title="📋 Variables disponibles", color=C_BLUE)

    e.description = (

        "`{user}` → Mention du membre\n"

        "`{username}` → Nom du membre\n"

        "`{server}` → Nom du serveur\n"

        "`{membercount}` → Nombre de membres\n"

        "`{id}` → ID du membre\n"

        "`{tag}` → Tag complet"

    )

    await ctx.send(embed=e)

# ─── LEVEL COMMANDS ───

@bot.command(name="level", aliases=["rank","niveau","xp"])

async def level_cmd(ctx, member: discord.Member = None):

    member = member or ctx.author

    cfg = get_level_config(ctx.guild.id)

    data = cfg["members"].get(str(member.id))

    if not data:

        return await ctx.send(embed=embed_warn(f"{member.mention} n'a pas encore de niveau."))

    lvl, xp = data["level"], data["xp"]

    nxt = xp_to_next(lvl)

    bar = "█" * int((xp/nxt)*20) + "░" * (20 - int((xp/nxt)*20))

    e = discord.Embed(title=f"📊 {member.display_name}", color=C_BLUE)

    e.set_thumbnail(url=member.display_avatar.url)

    e.add_field(name="🏆 Niveau", value=f"**{lvl}**", inline=True)

    e.add_field(name="✨ XP", value=f"**{xp}** / {nxt}", inline=True)

    e.add_field(name="📈 Progression", value=f"`{bar}`", inline=False)

    await ctx.send(embed=e)

@bot.command(name="top", aliases=["leaderboard","classement"])

async def top_cmd(ctx):

    cfg = get_level_config(ctx.guild.id)

    members_data = cfg.get("members", {})

    if not members_data:

        return await ctx.send(embed=embed_warn("Aucun membre dans le classement."))

    sorted_m = sorted(members_data.items(), key=lambda x: (x[1]["level"], x[1]["xp"]), reverse=True)[:10]

    medals = ["🥇","🥈","🥉"] + ["🏅"]*7

    e = discord.Embed(title="🏆 Classement XP", color=C_BLUE)

    lines = []

    for i, (uid, d) in enumerate(sorted_m):

        m = ctx.guild.get_member(int(uid))

        name = m.display_name if m else f"ID:{uid}"

        lines.append(f"{medals[i]} **{name}** — Niv.{d['level']} ({d['xp']} XP)")

    e.description = "\n".join(lines)

    await ctx.send(embed=e)

# ─── SONDAGE ───

@bot.command(name="sondage", aliases=["poll","sondage2"])

async def sondage_cmd(ctx, duration="1m", *, contenu=None):

    if not is_modo(ctx.author):

        return await ctx.send(embed=embed_err("Tu n'as pas la permission."))

    if not contenu:

        return await ctx.send(embed=embed_err("Usage : `+sondage [durée] question | option1 | option2`"))

    parts = [p.strip() for p in contenu.split("|")]

    question = parts[0]

    options = parts[1:] if len(parts) > 1 else None

    time_units = {"s":1,"m":60,"h":3600}

    try: total_seconds = int(duration[:-1]) * time_units.get(duration[-1].lower(), 60)

    except: total_seconds = 60

    EMOJIS = ["🇦","🇧","🇨","🇩","🇪"]

    if options and len(options) >= 2:

        poll_emojis = EMOJIS[:len(options)]

        desc = f"**{question}**\n\n" + "\n".join(f"{e} {o}" for e, o in zip(poll_emojis, options))

    else:

        poll_emojis = ["👍","👎"]

        desc = f"**{question}**"

    e = discord.Embed(title="📊 Sondage", description=desc, color=C_BLUE)

    e.set_footer(text=f"Créé par {ctx.author} • Fin dans {duration}")

    poll_msg = await ctx.send(embed=e)

    for emoji in poll_emojis:

        await poll_msg.add_reaction(emoji)

    await asyncio.sleep(total_seconds)

    poll_msg = await ctx.channel.fetch_message(poll_msg.id)

    results = []

    for i, emoji in enumerate(poll_emojis):

        r = discord.utils.get(poll_msg.reactions, emoji=emoji)

        count = r.count - 1 if r else 0

        label = options[i] if options and i < len(options) else emoji

        results.append(f"{emoji} {label} → **{count}** vote(s)")

    e.title = "📊 Résultats"

    e.description = f"**{question}**\n\n" + "\n".join(results)

    e.set_footer(text="Sondage terminé")

    await poll_msg.edit(embed=e)

# ─── DMALL ───

# ─── DM ───

@bot.command(name="dm", aliases=["dmall"])

async def dm_cmd(ctx, user: discord.Member = None, *, message=None):

    if not ctx.author.guild_permissions.administrator and str(ctx.author.id) not in OWNER_IDS:

        return await ctx.send(embed=embed_err("Permission administrateur requise."))

    if not user or not message:

        return await ctx.send(embed=embed_err("Usage : `+dm @user message`"))

    try:

        await ctx.message.delete()

    except: pass

    try:

        e = discord.Embed(description=message, color=C_BLUE)

        e.set_footer(text=f"Message de {ctx.guild.name}")

        await user.send(embed=e)

        await ctx.send(embed=discord.Embed(description=f"✅ Message envoyé à **{user}** !", color=C_GREEN), delete_after=5)

    except discord.Forbidden:

        await ctx.send(embed=embed_err(f"Impossible d'envoyer un MP à **{user}** (DMs fermés)."))

# ─── VIP / CODEGEN ───


# ─── AIDE ───

# ─── HELP DATA ────────────────────────────────────────────────────────────────

AIDE_CATEGORIES = [

    ("mod",      "Modération",          "🛡️", 0xED4245),

    ("owners",   "Owners & Reset",      "👑", 0xFFD700),

    ("welcome",  "Welcome & Départ",    "👋", 0x57F287),

    ("levels",   "Niveaux & XP",        "📊", 0x5865F2),

    ("fun",      "Fun & Giveaway",      "🎉", 0xFEE75C),

    ("games",    "Jeux & Anime",        "🎮", 0x5865F2),

    ("utils",    "Utilitaires",         "🔧", 0x5865F2),

    ("infos",    "Infos & Stats",       "🔍", 0x5865F2),

    ("images",   "Images & Profil",     "🖼️", 0x5865F2),

    ("logs",     "Logs",               "📋", 0x5865F2),

    ("premium",  "Premium",             "⭐", 0xFFD700),

    ("antiraid", "Anti-Raid",           "🔒", 0xED4245),

    ("tickets",  "Tickets",             "🎫", 0x5865F2),

    ("settings", "Paramètres",          "⚙️", 0x99AAB5),

    ("backup",   "Backup Serveur",      "💾", 0x2ECC71),

    ("captcha",  "Captcha & Sécurité ⭐",  "🔐", 0xFFD700),

    ("invites",  "Invite Tracker",       "📨", 0x57F287),

]

AIDE_PAGES = {

    "mod": (

        "🛡️ Modération", 0xED4245,

        ("+ban <@m/ID> [raison]", "Bannir un membre"),

        ("+unban <ID> [raison]", "Débannir un membre"),

        ("+kick <@m/ID> [raison]", "Expulser un membre"),

        ("+mute <@m/ID> [durée] [raison]", "Rendre muet un membre"),

        ("+unmute <@m/ID>", "Retirer le mute d'un membre"),

        ("+warn <@m/ID> [raison]", "Avertir un membre"),

        ("+clear <nombre>", "Supprimer des messages"),

        ("+dm <@user> <message>", "Envoyer un MP à un membre"),

        ("+modo", "Config modération & logs"),

        ("+banlist", "Liste des bannissements en cours"),

        ("+alladmins", "Liste des membres administrateurs"),

    ),

    "owners": (

        "👑 Owners & Gestion serveur", 0xFFD700,

        ("+owner <@m/nom/ID>", "Ajouter un owner"),

        ("+unowner <@m/nom/ID>", "Retirer un owner"),

        ("+owners", "Liste des owners"),

        ("+clearowners", "Supprimer tous les owners"),

        ("+reset", "Réinitialiser les données du serveur"),

    ),

    "welcome": (

        "👋 Welcome & Départ", 0x57F287,

        ("+welcome", "Config message de bienvenue"),

        ("+depart", "Config message de départ ⭐"),

        ("+joinmp", "MP automatique à l'arrivée ⭐"),

        ("+joinsettings", "Paramètres d'arrivée des membres"),

        ("+variables", "Variables disponibles"),

        ("+fluxlog on #salon", "Activer les logs d'arrivée/départ"),

    ),

    "levels": (

        "📊 Niveaux & XP", 0x5865F2,

        ("+setup", "Config système de niveaux"),

        ("+level [@membre]", "Voir son niveau/XP"),

        ("+top", "Classement XP du serveur"),

    ),

    "fun": (

        "🎉 Fun & Giveaway", 0xFEE75C,

        ("+giveaway", "Config & lancer un giveaway"),

        ("+sondage <durée> question | opt1 | opt2", "Créer un sondage"),

        ("+say <message>", "Faire parler le bot"),

        ("+calcul <expression>", "Calculatrice"),

        ("+8ball <question>", "Magic 8-Ball"),

        ("+roll [faces]", "Lancer un dé"),

        ("+coinflip [pari]", "Pile ou Face"),

        ("+rps", "Pierre-Papier-Ciseaux"),

        ("+rate <texte>", "Note sur 10"),

        ("+gay [@m]", "Gay-o-mètre"),

        ("+hack [@m]", "Hack simulé"),

        ("+ratio [@m]", "Ratio"),

        ("+wanted [@m]", "Affiche Wanted"),

    ),

    "games": (

        "🎮 Jeux & Anime", 0x5865F2,

        ("+anime <titre>", "Infos sur un anime"),

        ("+define <mot>", "Définition d'un mot"),

        ("+translate <lang> <texte>", "Traduction"),

        ("+binary <texte>", "Convertir en binaire ou texte"),

        ("+ascii <texte>", "Art ASCII"),

        ("+tweet <pseudo> <texte>", "Faux tweet"),

        ("+clyde <texte>", "Message Clyde"),

        ("+mind <texte>", "Panneau avec texte"),

        ("+undertale <texte>", "Style Undertale"),

        ("+deepfry [@m]", "Effet deepfry"),

        ("+blur [@m]", "Effet flou"),

        ("+blurpify [@m]", "Effet blurpify"),

        ("+colorify [@m]", "Effet couleur"),

        ("+randomuser", "Membre aléatoire"),

        ("+oh [@m]", "Envoyer un message menteur"),

    ),

    "utils": (

        "🔧 Utilitaires", 0x5865F2,

        ("+ping", "Latence WebSocket"),

        ("+speed", "Latence complète"),

        ("+userinfo [@m]", "Infos membre"),

        ("+serverinfo", "Infos serveur"),

        ("+botinfo", "Infos bot"),

        ("+roles", "Liste des rôles"),

        ("+norole", "Membres sans rôle"),

        ("+allroles", "Liste complète des rôles du serveur"),

        ("+allbots", "Liste des bots"),

        ("+allchannels", "Liste de tous les salons"),

        ("+allthreads", "Liste des threads actifs"),

        ("+allbooster", "Liste des boosters"),

        ("+search <mot>", "Chercher une commande"),

        ("+inviteinfo <url>", "Infos d'une invitation"),

        ("+idemoji <emoji>", "ID d'un emoji"),

        ("+timestamp [unix]", "Tous les formats de timestamp"),

        ("+uptime", "Durée de fonctionnement du bot"),

        ("+onepage", "Toutes les commandes en une page"),

        ("+links", "Liens utiles"),

        ("+support", "Serveur support"),

        ("+vote", "Voter pour le bot"),

        ("+version", "Version du bot"),

    ),

    "infos": (

        "🔍 Infos & Stats", 0x5865F2,

        ("+channelinfo [#salon]", "Infos salon"),

        ("+roleinfo <@rôle/nom>", "Infos rôle"),

        ("+rolemembers <@rôle>", "Membres d'un rôle"),

        ("+find [@m]", "Trouver un membre en vocal"),

        ("+vc", "Stats vocales serveur"),

        ("+vanity", "Infos URL personnalisée"),

        ("+stats [@m]", "Stats messages"),

        ("+prevnames [@m]", "Anciens pseudos"),

        ("+snipe", "Dernier message supprimé"),

        ("+snipedit", "Dernier message modifié"),

        ("+github <user>", "Profil GitHub"),

        ("+template", "Exemple d'embed"),

    ),

    "images": (

        "🖼️ Images & Profil", 0x5865F2,

        ("+avatar [@m]", "Photo de profil"),

        ("+banner [@m]", "Bannière de profil"),

        ("+serveravatar", "Icône du serveur"),

        ("+serverbanner", "Bannière du serveur"),

        ("+servericon", "Icône du serveur HD"),

        ("+randomavatar", "Avatar aléatoire"),

        ("+randombanner", "Bannière aléatoire"),

        ("+hug [@m]", "Câlin (gif)"),

        ("+pat [@m]", "Caresse (gif)"),

        ("+slap [@m]", "Gifle (gif)"),

        ("+kiss [@m]", "Bisou (gif)"),

        ("+cry [@m]", "Pleurer (gif)"),

        ("+smile", "Sourire (gif)"),

        ("+cat", "Image de chat aléatoire"),

        ("+dog", "Image de chien aléatoire"),

    ),

    "logs": (

        "📋 Système de Logs", 0x5865F2,

        ("+logs", "Voir la config des logs + boutons Auto/Clean"),

        ("+modlog <on/off> [#salon]", "Logs modération"),

        ("+msglog <on/off> [#salon]", "Logs messages"),

        ("+rolelog <on/off> [#salon]", "Logs rôles"),

        ("+channellog <on/off> [#salon]", "Logs salons"),

        ("+voclog <on/off> [#salon]", "Logs vocaux"),

        ("+boostlog <on/off> [#salon]", "Logs boosts"),

        ("+fluxlog <on/off> [#salon]", "Logs flux"),

        ("+ticketlog <on/off> [#salon]", "Logs tickets"),

    ),

    "premium": (

        "⭐ Premium", 0xFFD700,

        ("+premium", "Activer / gérer le premium"),

        ("― ✨ AVANTAGES PREMIUM ―", ""),

        ("+captcha", "🔐 Captcha & Sécurité — Vérification des membres"),

        ("+ticket → Mode Menu déroulant", "🎫 Panel ticket avec menu déroulant"),

        ("+backup create", "💾 Jusqu'à 20 backups (gratuit : 10)"),

        ("+joinmp", "📩 MP de bienvenue personnalisé"),

        ("+depart", "👋 Message de départ personnalisé"),

    ),

    "antiraid": (

        "🔒 Anti-Raid & Anti-Lien", 0xED4245,

        ("+antiraid", "Menu de config anti-raid complet"),

        ("+antilink", "Config anti-lien"),

        ("+antibot", "Créer/déplacer le salon honeypot anti-bot"),

        ("+ghostping", "Info sur le système de ghost ping"),

        ("+piconly <add/remove/clear> [salon]", "Salon selfie — images uniquement"),

    ),

    "tickets": (

        "🎫 Tickets", 0x5865F2,

        ("+ticket", "Menu de config complet"),

    ),

    "settings": (

        "⚙️ Paramètres & Config", 0x99AAB5,

        ("+prefixe <nouveau>", "Changer le préfixe"),

        ("+setup", "Config niveaux/XP"),

        ("+modo", "Config modération"),

        ("+welcome", "Config bienvenue"),

        ("+antiraid", "Config anti-raid"),

        ("+ticket", "Config tickets"),

        ("+logs", "Config logs"),

        ("+defaultrole <@rôles>", "Rôles donnés à l'arrivée"),

        ("+autoreact <add/remove/clear> <salon> <emojis>", "Réactions automatiques dans un salon"),

        ("+massiverole <add/remove> <human/bot/all> <@rôle>", "Rôle en masse"),

        ("+everping <message>", "Mentionner @everyone avec le bot"),

        ("+joinsettings", "Paramètres d'arrivée"),

        ("+sethelp", "Modifier le type du help"),

        ("+starboard", "Config starboard"),

        ("+soutien", "Config système de soutien"),

        ("+tag <@rôle>", "Rôle pour les membres avec le tag"),

        ("+create <emojis>", "Créer des emojis en masse"),

        ("+embedlist", "Voir ses embeds sauvegardés"),

        ("+clearembeds", "Supprimer ses embeds sauvegardés"),

        ("+embed", "Créer un embed interactif"),

        ("+jointocreate", "Vocaux temporaires"),

        ("+rolespicker", "Menu de rôles interactif"),

        ("+showpic", "Affichage automatique des photos"),

    ),

    "backup": (

        "💾 Backup Serveur", 0x2ECC71,

        ("+backup create [nom]", "Créer une sauvegarde du serveur (max 20)"),

        ("+backup list", "Voir & restaurer une backup via menu"),

        ("+backup delete", "Supprimer une backup via menu"),

        ("+backup info <numéro>", "Détails d'une backup"),

    ),

    "captcha": (

        "🔐 Captcha & Sécurité", 0x5865F2,

        ("+captcha", "Ouvrir le panel de configuration captcha"),

        ("+captcha → Salon & Rôles", "Définir le salon de vérif + rôle vérifié"),

        ("+captcha → Message d'accueil", "Personnaliser le message envoyé au membre"),

        ("+captcha → Style", "Choisir le style : embed / texte + longueur du code"),

        ("+captcha → Activer / Désactiver", "Toggle le système de vérification on/off"),

        ("+captcha → Envoyer le panel", "Poster le bouton 🔑 dans le salon de vérif"),

    ),

    "invites": (

        "📨 Invite Tracker", 0x57F287,

        ("+invites [@user]", "Voir les invitations d'un membre (total, bonus, fausses, partis)"),

        ("+inviteleaderboard", "Classement des invitations du serveur"),

        ("+addinvites @user nombre", "Ajouter des invitations régulières à un membre"),

        ("+removeinvites @user nombre", "Retirer des invitations régulières à un membre"),

        ("+resetinvites @user", "Réinitialiser toutes les invitations d'un membre"),

        ("+addbonus @user nombre", "Ajouter des invitations bonus à un membre"),

        ("+removebonus @user nombre", "Retirer des invitations bonus à un membre"),

        ("+addfakeinvites @user nombre", "Ajouter des fausses invitations à un membre"),

        ("+removefakeinvites @user nombre", "Retirer des fausses invitations à un membre"),

        ("+syncinvites", "Resynchroniser le cache des invitations"),

        ("+deleteinvite <code>", "Supprimer un code d'invitation spécifique"),

        ("+purge-invite-codes", "Supprimer tous les codes d'invitation expirés"),

        ("+exportleaderboard", "Exporter le classement en fichier CSV"),

        ("+exportinvitedlist @user", "Exporter la liste des membres invités par quelqu'un en CSV"),

    ),

}

AIDE_PER_PAGE = 7   # catégories par page dans le select

def _build_aide_embed(cat_key: str, pfx: str) -> discord.Embed:

    data = AIDE_PAGES[cat_key]

    title, color = data[0], data[1]

    entries = data[2:]

    cat_info = next((c for c in AIDE_CATEGORIES if c[0] == cat_key), None)

    idx = AIDE_CATEGORIES.index(cat_info) + 1

    total = len(AIDE_CATEGORIES)

    e = discord.Embed(title=title, color=color)

    desc = ""

    for entry in entries:

        if isinstance(entry, tuple):

            cmd_raw, explanation = entry

            cmd_display = cmd_raw.replace("+", pfx, 1)

            desc += f"\n・ **`{cmd_display}`**\n-# ┖ **{explanation}**"

        elif entry == "":

            desc += "\n"

        else:

            desc += f"\n*{entry}*"

    e.description = desc.strip()

    e.set_footer(text=f"ModeraBot • {idx}/{total} • Préfixe : {pfx} • ◄ ► pour naviguer")

    return e

def _build_home_embed(pfx: str, ctx=None) -> discord.Embed:

    from discord.ext.commands import Bot as _Bot

    cmd_count = len(list(bot.commands))

    user_mention = ctx.author.mention if ctx else "vous"

    e = discord.Embed(title="🏡 Menu d'accueil", color=0x5865F2)

    e.description = (

        f"Hey, bienvenue {user_mention} sur la page d'accueil **ModeraBot** !\n\n"

        f"・**Informations**\n"

        f"> - Mon préfixe : `{pfx}`\n"

        f"> - Commandes : `{cmd_count}`\n\n"

        f"・**Commandes Utiles**\n"

        f"> - [`{pfx}invite`](https://discord.gg/DfAe8kQKZ)\n"

        f"> - [`{pfx}helptype <type>`](https://discord.gg/DfAe8kQKZ)\n"

        f"> - [`{pfx}help <commande>`](https://discord.gg/DfAe8kQKZ)\n\n"

        f"・**Fonctions à savoir**\n"

        f"> - Les parenthèses entre `<...>` sont obligatoires\n"

        f"> - Tous les autres `[...]` paramètres sont facultatifs."

    )

    e.set_footer(text="ModeraBot • Sélectionne une catégorie ou navigue avec ◄ ►")

    return e

# ─── Help View (select + arrow buttons) ──────────────────────────────────────

class AideView(discord.ui.View):

    """Select toutes catégories + ◄ idx/total ► pour naviguer."""

    def __init__(self, cat: str = None, pfx: str = "+"):

        super().__init__(timeout=None)

        self.pfx   = pfx

        self.total = len(AIDE_CATEGORIES)

        self.current_idx = (

            next((i for i,c in enumerate(AIDE_CATEGORIES) if c[0]==cat), 0)

            if cat else None

        )

        self.current_cat = cat

        self._build_select()

    # ── select menu ──────────────────────────────────────────────────────────

    def _build_select(self):

        # Remove old select if present (called from button callbacks)

        for item in list(self.children):

            if isinstance(item, discord.ui.Select):

                self.remove_item(item)

        sel = discord.ui.Select(

            placeholder="Fais un choix",

            options=[

                discord.SelectOption(

                    label=c[1], value=c[0], emoji=c[2],

                    default=(c[0] == self.current_cat)

                )

                for c in AIDE_CATEGORIES

            ],

            row=0

        )

        sel.callback = self._on_select

        self.add_item(sel)

        # update button states

        self._prev_btn.disabled = (self.current_idx is None or self.current_idx == 0)

        self._next_btn.disabled = (self.current_idx is None or self.current_idx >= self.total - 1)

        lbl = f"—/{self.total}" if self.current_idx is None else f"{self.current_idx+1}/{self.total}"

        self._page_btn.label = lbl

    # ── select callback ───────────────────────────────────────────────────────

    async def _on_select(self, interaction: discord.Interaction):

        self.current_cat = interaction.data["values"][0]

        self.current_idx = next(i for i,c in enumerate(AIDE_CATEGORIES) if c[0]==self.current_cat)

        self._build_select()

        await interaction.response.edit_message(

            embed=_build_aide_embed(self.current_cat, self.pfx), view=self)

    # ── navigation buttons ────────────────────────────────────────────────────

    @discord.ui.button(label="◄", style=discord.ButtonStyle.secondary, row=1, disabled=True)

    async def _prev_btn(self, interaction: discord.Interaction, button: discord.ui.Button):

        self.current_idx = max(0, self.current_idx - 1)

        self.current_cat = AIDE_CATEGORIES[self.current_idx][0]

        self._build_select()

        await interaction.response.edit_message(

            embed=_build_aide_embed(self.current_cat, self.pfx), view=self)

    @discord.ui.button(label="—/14", style=discord.ButtonStyle.primary, row=1, disabled=True)

    async def _page_btn(self, interaction: discord.Interaction, button: discord.ui.Button):

        pass  # indicateur seulement

    @discord.ui.button(label="►", style=discord.ButtonStyle.secondary, row=1, disabled=False)

    async def _next_btn(self, interaction: discord.Interaction, button: discord.ui.Button):

        if self.current_idx is None:

            self.current_idx = 0

        else:

            self.current_idx = min(self.total - 1, self.current_idx + 1)

        self.current_cat = AIDE_CATEGORIES[self.current_idx][0]

        self._build_select()

        await interaction.response.edit_message(

            embed=_build_aide_embed(self.current_cat, self.pfx), view=self)

@bot.command(name="prefixe", aliases=["prefix","setprefix","changeprefix","setprefixe"])

@commands.has_permissions(administrator=True)

async def prefixe_cmd(ctx, nouveau_prefixe: str = None):

    """Change le préfixe du bot pour ce serveur."""

    pfx_actuel = _prefix_cache.get(ctx.guild.id, DEFAULT_PREFIX)

    if not nouveau_prefixe:

        e = discord.Embed(

            title="⚙️ Préfixe du serveur",

            description=(

                f"**Préfixe actuel :** `{pfx_actuel}`\n\n"

                f"**Usage :** `{pfx_actuel}prefixe <nouveau_préfixe>`\n"

                f"**Exemple :** `{pfx_actuel}prefixe !`\n\n"

                f"*Le préfixe peut faire 1 à 5 caractères.*\n"

                f"*Tu peux toujours mentionner le bot si tu oublies le préfixe.*"

            ),

            color=C_BLUE

        )

        return await ctx.send(embed=e)

    if len(nouveau_prefixe) > 5:

        return await ctx.send(embed=discord.Embed(

            description="❌ Le préfixe ne peut pas dépasser **5 caractères**.", color=C_RED))

    if nouveau_prefixe == pfx_actuel:

        return await ctx.send(embed=discord.Embed(

            description=f"ℹ️ Le préfixe est déjà `{pfx_actuel}`.", color=C_ORANGE))

    _prefix_cache[ctx.guild.id] = nouveau_prefixe

    _save_prefixes()

    e = discord.Embed(

        title="✅ Préfixe modifié !",

        description=(

            f"**Ancien préfixe :** `{pfx_actuel}`\n"

            f"**Nouveau préfixe :** `{nouveau_prefixe}`\n\n"

            f"Exemple : `{nouveau_prefixe}aide` pour voir les commandes."

        ),

        color=C_GREEN

    )

    e.set_footer(text=f"Changé par {ctx.author.display_name}")

    await ctx.send(embed=e)

@prefixe_cmd.error

async def prefixe_error(ctx, error):

    if isinstance(error, commands.MissingPermissions):

        await ctx.send(embed=discord.Embed(

            description="❌ Tu dois être **administrateur** pour changer le préfixe.", color=C_RED))

@bot.command(name="aide", aliases=["help","h","commandes"])

async def aide_cmd(ctx):

    pfx = _prefix_cache.get(ctx.guild.id, DEFAULT_PREFIX) if ctx.guild else DEFAULT_PREFIX

    await ctx.send(embed=_build_home_embed(pfx, ctx), view=AideView(cat=None, pfx=pfx))

# ══════════════════════════════════════════

# GIVEAWAY LAUNCH ENGINE

# ══════════════════════════════════════════

async def launch_giveaway_from_config(ctx_or_channel, data):

    gain      = data.get("gain", "Un lot")

    duree_str = data.get("duree", "1m")

    salon_id  = data.get("salon_id")

    gagnants  = data.get("gagnants", 1)

    emoji     = data.get("emoji", "🎉")

    btn_text  = data.get("btn_text", "")

    redirect_url = data.get("redirect_url", "")

    show_parts = data.get("show_participants", False)

    vocal_req  = data.get("vocal_required", False)

    unit = duree_str[-1]

    try: value = int(duree_str[:-1])

    except: value = 1

    delta_map = {"s": timedelta(seconds=value), "m": timedelta(minutes=value), "h": timedelta(hours=value), "j": timedelta(days=value)}

    delta = delta_map.get(unit, timedelta(minutes=1))

    end_time = discord.utils.utcnow() + delta

    if isinstance(ctx_or_channel, commands.Context):

        guild = ctx_or_channel.guild

    else:

        guild = ctx_or_channel.guild

    channel = guild.get_channel(salon_id) if salon_id else (ctx_or_channel.channel if isinstance(ctx_or_channel, commands.Context) else ctx_or_channel)

    if not channel:

        return

    e = discord.Embed(title=f"{emoji} GIVEAWAY {emoji}", color=C_BLUE)

    conditions = []

    if vocal_req: conditions.append("🎙️ Présence en vocal obligatoire")

    required_roles = data.get("required_roles", [])

    if required_roles: conditions.append("🎭 Rôles requis : " + " ".join(f"<@&{r}>" for r in required_roles))

    # organizer_id doit être défini AVANT l'embed

    organizer_id = ctx_or_channel.author.id if hasattr(ctx_or_channel, 'author') else None

    e.description = (

        f"🎁 **Gain :** {gain}\n"

        f"👤 **Organisé par :** {f'<@{organizer_id}>' if organizer_id else (guild.owner.mention if guild.owner else 'Admin')}\n"

        f"🏆 **Gagnants :** {gagnants}\n"

        f"👥 **Participants :** 0\n"

        f"⏳ **Fin :** <t:{int(end_time.timestamp())}:R>\n\n"

        f"Réagis avec {emoji} pour participer !"

    )

    if conditions and data.get("show_conditions", True):

        e.add_field(name="📋 Conditions", value="\n".join(conditions), inline=False)

    # Buttons view

    view = discord.ui.View(timeout=None)

    if btn_text:

        style_map = {"bleu": discord.ButtonStyle.primary, "vert": discord.ButtonStyle.success, "rouge": discord.ButtonStyle.danger, "gris": discord.ButtonStyle.secondary}

        btn_style = style_map.get(data.get("btn_color", "bleu"), discord.ButtonStyle.primary)

        btn = discord.ui.Button(label=btn_text, style=btn_style, emoji=emoji)

        view.add_item(btn)

    if redirect_url:

        view.add_item(discord.ui.Button(label="🔗 Lien", url=redirect_url, style=discord.ButtonStyle.link))

    msg = await channel.send(embed=e, view=view if (btn_text or redirect_url) else None)

    await msg.add_reaction(emoji)

    giveaways[msg.id] = {"end": end_time, "gagnants": gagnants, "gain": gain, "participants": set(), "data": data, "organizer_id": organizer_id}

    async def update_loop():

        while discord.utils.utcnow() < end_time:

            try:

                fetched = await channel.fetch_message(msg.id)

                r = discord.utils.get(fetched.reactions, emoji=emoji)

                if r:

                    users = [u async for u in r.users() if not u.bot]

                    # Filtre rôles requis

                    if required_roles:

                        users = [u for u in users if any(ro.id in required_roles for ro in (guild.get_member(u.id).roles if guild.get_member(u.id) else []))]

                    # Filtre rôles bannis

                    blacklist = data.get("blacklist_roles", [])

                    if blacklist:

                        users = [u for u in users if not any(ro.id in blacklist for ro in (guild.get_member(u.id).roles if guild.get_member(u.id) else []))]

                    # Filtre vocal si requis

                    if vocal_req:

                        users = [u for u in users if guild.get_member(u.id) and guild.get_member(u.id).voice]

                    giveaways[msg.id]["participants"] = set(u.id for u in users)

                    part_count = len(users)

                    e.description = (

                        f"🎁 **Gain :** {gain}\n"

                        f"👤 **Organisé par :** {f'<@{organizer_id}>' if organizer_id else (guild.owner.mention if guild.owner else 'Admin')}\n"

                        f"🏆 **Gagnants :** {gagnants}\n"

                        f"👥 **Participants :** {part_count}\n"

                        f"⏳ **Fin :** <t:{int(end_time.timestamp())}:R>\n\n"

                        f"Réagis avec {emoji} pour participer !"

                    )

                    if show_parts and users:

                        e.set_field_at(0 if conditions else 0, name="👥 Participants", value=", ".join(f"<@{u.id}>" for u in users[:20]) + ("..." if len(users) > 20 else ""), inline=False) if e.fields else e.add_field(name="👥 Participants", value=", ".join(f"<@{u.id}>" for u in users[:20]), inline=False)

                    await fetched.edit(embed=e)

            except: pass

            await asyncio.sleep(15)

    asyncio.create_task(update_loop())

    await asyncio.sleep(delta.total_seconds())

    d = giveaways.pop(msg.id, None)

    if d:

        d["participants"].discard(bot.user.id)

        if organizer_id: d["participants"].discard(organizer_id)

    if not d or not d["participants"]:

        return await channel.send("❌ Giveaway terminé : aucun participant valide.")

    # Bonus entries

    bonus_raw = data.get("bonus_raw", "")

    participants_weighted = list(d["participants"])

    if bonus_raw:

        for entry in bonus_raw.split(","):

            parts = entry.strip().split(":")

            if len(parts) == 2:

                try:

                    rid = int(parts[0].strip()); bonus = int(parts[1].strip())

                    for uid in d["participants"]:

                        m = guild.get_member(uid)

                        if m and any(r.id == rid for r in m.roles):

                            participants_weighted.extend([uid] * (bonus - 1))

                except: pass

    # Gagnant prédéfini ?

    preset = data.get("preset_winner")

    if preset and preset in d["participants"]:

        winners = [preset]

    else:

        winners = random.sample(participants_weighted, min(gagnants, len(participants_weighted)))

    mentions = ", ".join(f"<@{w}>" for w in winners)

    end_e = discord.Embed(title="🎉 GIVEAWAY TERMINÉ !", color=C_GOLD)

    end_e.add_field(name="🏆 Gagnant(s)", value=mentions, inline=False)

    end_e.add_field(name="🎁 Gain", value=gain, inline=False)

    await channel.send(embed=end_e)

# ══════════════════════════════════════════

# ANTIRAID & ANTILINK HANDLERS

# ══════════════════════════════════════════

async def send_antiraid_log(guild, text):

    try:

        log_ch = get_server_config(guild.id).get("antiraid", {}).get("modlog")

        ch = guild.get_channel(log_ch) if log_ch else guild.system_channel

        if ch: await ch.send(text)

    except: pass

async def _handle_antiraid(message):

    if message.author.bot or not message.guild: return

    guild = message.guild

    cfg = get_server_config(guild.id).get("antiraid", {})

    # Anti-Spam

    if cfg.get("spam"):

        thresh = cfg.get("spam_threshold", DEFAULT_SPAM_THRESHOLD)

        interval = cfg.get("spam_interval", DEFAULT_SPAM_INTERVAL)

        action = cfg.get("spam_action", "timeout")

        now = time.time()

        dq = _spam_track[guild.id][message.author.id]

        dq.append(now)

        while dq and now - dq[0] > interval: dq.popleft()

        if len(dq) >= thresh:

            dq.clear()

            try:

                if action == "timeout":

                    dur = cfg.get("spam_timeout_duration", 60)

                    await message.author.timeout(timedelta(seconds=dur), reason="Anti-spam ModeraBot")

                elif action == "kick":

                    await message.author.kick(reason="Anti-spam ModeraBot")

                elif action == "ban":

                    await message.author.ban(reason="Anti-spam ModeraBot")

            except: pass

            await send_antiraid_log(guild, f"🚨 Anti-spam : {message.author} ({action}) — {thresh} msgs/{interval}s")

    # Anti-Mention

    if cfg.get("mention"):

        limit = cfg.get("mention_limit", DEFAULT_MENTION_LIMIT)

        action = cfg.get("mention_action", "timeout")

        total = len(message.mentions) + len(message.role_mentions)

        if total >= limit:

            try:

                await message.delete()

                if action == "timeout":

                    await message.author.timeout(timedelta(seconds=30), reason="Anti-mention ModeraBot")

                elif action == "kick":

                    await message.author.kick(reason="Anti-mention ModeraBot")

                elif action == "ban":

                    await message.author.ban(reason="Anti-mention ModeraBot")

            except: pass

            await send_antiraid_log(guild, f"🚨 Anti-mention : {message.author} ({total} mentions/{limit} max)")

    # Anti-Caps

    if cfg.get("caps"):

        pct = cfg.get("caps_percent", 70)

        minl = cfg.get("caps_min_length", 10)

        content = message.content

        if len(content) >= minl:

            letters = [c for c in content if c.isalpha()]

            if letters and (sum(1 for c in letters if c.isupper()) / len(letters)) * 100 >= pct:

                try:

                    await message.delete()

                    await message.channel.send(f"⚠️ {message.author.mention}, pas de spam de majuscules !", delete_after=5)

                except: pass

    # Anti-Emoji Spam

    if cfg.get("emoji_spam"):

        max_e = cfg.get("max_emojis", 5)

        emoji_count = len(re.findall(r'<a?:\w+:\d+>|[\U0001F300-\U0001FFFF]', message.content))

        if emoji_count > max_e:

            try:

                await message.delete()

                await message.channel.send(f"⚠️ {message.author.mention}, trop d'emojis !", delete_after=5)

            except: pass

async def _handle_antilink(message):

    if message.author.bot or not message.guild: return

    if message.author.guild_permissions.administrator: return

    data = jload(FILES["antilink"]).get(str(message.guild.id), {})

    if not isinstance(data, dict): enabled = bool(data)

    else: enabled = data.get("enabled", False)

    if not enabled: return

    whitelist = data.get("whitelist", []) if isinstance(data, dict) else []

    action = data.get("action", "delete") if isinstance(data, dict) else "delete"

    warn_msg = data.get("warn_msg", "Les liens ne sont pas autorisés !") if isinstance(data, dict) else "Les liens ne sont pas autorisés !"

    link_regex = r"(https?://[^\s]+|www\.[^\s]+|discord\.gg/[^\s]+)"

    match = re.search(link_regex, message.content)

    if match:

        link = match.group()

        if any(domain in link for domain in whitelist): return

        try:

            await message.delete()

            if action in ("warn", "delete"):

                await message.channel.send(f"⚠️ {message.author.mention}, {warn_msg}", delete_after=5)

            elif action == "timeout":

                await message.author.timeout(timedelta(seconds=30), reason="Anti-lien ModeraBot")

                await message.channel.send(f"⚠️ {message.author.mention}, {warn_msg}", delete_after=5)

        except: pass

async def _handle_xp(message):

    if not message.guild or message.author.bot: return

    cfg = get_level_config(message.guild.id)

    xp_ch = cfg.get("xp_channel")

    if not xp_ch or message.channel.id != xp_ch: return

    mid = str(message.author.id)

    if mid not in cfg["members"]:

        cfg["members"][mid] = {"xp": 0, "level": 1}

    xp_min = cfg.get("xp_min", 1)

    xp_max = cfg.get("xp_max", 5)

    cfg["members"][mid]["xp"] += random.randint(xp_min, xp_max)

    lvl = cfg["members"][mid]["level"]

    nxt = xp_to_next(lvl)

    if cfg["members"][mid]["xp"] >= nxt:

        cfg["members"][mid]["level"] += 1

        cfg["members"][mid]["xp"] -= nxt

        new_lvl = cfg["members"][mid]["level"]

        new_nxt = xp_to_next(new_lvl)

        cur_xp = cfg["members"][mid]["xp"]

        bar = "█" * int((cur_xp/new_nxt)*20) + "░" * (20-int((cur_xp/new_nxt)*20))

        e = discord.Embed(title="🎉 Level Up !", color=C_BLUE,

            description=f"{message.author.mention} → **Niveau {new_lvl}** !\n`{bar}` ({cur_xp}/{new_nxt} XP)")

        notif_ch = cfg.get("notif_channel")

        send_ch = message.guild.get_channel(notif_ch) if notif_ch else message.channel

        if send_ch: await send_ch.send(embed=e)

    save_level_config(message.guild.id, cfg)

async def _handle_welcome_join(member):

    data = jload(FILES["welcome"]).get(str(member.guild.id), {})

    vars_ = {

        "{user}": member.mention, "{username}": member.name,

        "{server}": member.guild.name, "{membercount}": str(member.guild.member_count),

        "{id}": str(member.id), "{tag}": str(member),

        "{avatar}": str(member.display_avatar.url),

        "{joined}": discord.utils.format_dt(member.joined_at or discord.utils.utcnow(), style="R"),

        "{created}": discord.utils.format_dt(member.created_at, style="R"),

    }

    def apply_vars(text):

        if not text: return text

        for k, v in vars_.items(): text = text.replace(k, v)

        return text

    if data.get("enabled", True) and data.get("channel_id"):

        ch = member.guild.get_channel(data["channel_id"])

        if ch:

            mode = data.get("mode", "texte")

            auto_del = data.get("auto_delete", 0)

            if mode == "embed":

                emb_cfg = data.get("embed", {})

                try: color = int(emb_cfg.get("color","#5865F2").replace("#",""), 16)

                except: color = 0x5865F2

                title = apply_vars(emb_cfg.get("titre") or f"Bienvenue {member.name} !")

                desc  = apply_vars(emb_cfg.get("desc")  or f"{member.mention} a rejoint **{member.guild.name}** !")

                e = discord.Embed(title=title, description=desc, color=color)

                thumb = emb_cfg.get("thumb","")

                if thumb == "avatar": e.set_thumbnail(url=member.display_avatar.url)

                elif thumb.strip(): e.set_thumbnail(url=thumb.strip())

                if emb_cfg.get("image","").strip(): e.set_image(url=emb_cfg["image"].strip())

                e.set_footer(text=f"{member.guild.name} • {member.guild.member_count} membres")

                sent = await ch.send(embed=e)

            else:

                msg = apply_vars(data.get("message") or f"Bienvenue {member.mention} !")

                sent = await ch.send(msg)

            if auto_del and auto_del > 0:

                await asyncio.sleep(auto_del)

                try: await sent.delete()

                except: pass

        # Mention séparée si mode embed

        if mode == "embed" and data.get("mention", True):

            try: await ch.send(member.mention, delete_after=3)

            except: pass

    # Rôle de bienvenue

    wrid = data.get("welcome_role")

    if wrid:

        wr = member.guild.get_role(wrid)

        if wr:

            try: await member.add_roles(wr, reason="Rôle de bienvenue ModeraBot")

            except: pass

    # MP bienvenue

    if data.get("mp_enabled") and data.get("mp_message"):

        try: await member.send(apply_vars(data["mp_message"]))

        except: pass

    # joinmp.json

    jmp = jload(FILES["joinmp"]).get(str(member.guild.id))

    if jmp:

        vars_ = {"{user}": member.mention, "{username}": member.name, "{server}": member.guild.name,

                 "{membercount}": str(member.guild.member_count)}

        msg = jmp["message"]

        for k, v in vars_.items(): msg = msg.replace(k, v)

        try:

            if jmp.get("mode") == "embed":

                e = discord.Embed(title=jmp.get("title",""), description=msg, color=jmp.get("color", C_BLUE))

                if jmp.get("image","").strip(): e.set_image(url=jmp["image"].strip())

                await member.send(embed=e)

            else:

                await member.send(msg)

        except: pass

    # Anti-raid join flood

    cfg = get_server_config(member.guild.id).get("antiraid", {})

    if cfg.get("join"):

        now = time.time()

        dq = _join_track[member.guild.id]

        dq.append(now)

        jint = cfg.get("join_interval", DEFAULT_JOIN_INTERVAL)

        while dq and now - dq[0] > jint: dq.popleft()

        if len(dq) >= cfg.get("join_threshold", DEFAULT_JOIN_THRESHOLD):

            action = cfg.get("join_action", "log")

            await send_antiraid_log(member.guild, f"🚨 Join Flood : {len(dq)} membres/{jint}s → action: {action}")

            if action == "lockdown":

                for ch in member.guild.text_channels:

                    try: await ch.set_permissions(member.guild.default_role, send_messages=False)

                    except: pass

                await send_antiraid_log(member.guild, "🔒 Lockdown activé automatiquement.")

            dq.clear()

# ══════════════════════════════════════════

# PREMIUM SLASH COMMANDS (inchangés)

# ══════════════════════════════════════════

# ══════════════════════════════════════════════════

# TICKET SYSTEM — 100% PREFIX + MODALS

# ══════════════════════════════════════════════════

def build_ticket_status_embed(guild_id):

    cfg = jload(FILES["ticket_select"]).get(str(guild_id), {})

    panel = cfg.get("panel", {})

    choix = cfg.get("choix", [])

    mode = panel.get("mode", "select")

    mode_label = "🔘 Boutons" if mode == "bouton" else ("📦 Container V2" if mode == "container_v2" else "📋 Menu déroulant")

    e = discord.Embed(title="🎫 Configuration Tickets", color=C_BLUE)

    e.add_field(name="📋 Titre panel", value=panel.get("titre", "Non défini"), inline=True)

    e.add_field(name="🎨 Mode", value=mode_label, inline=True)

    e.add_field(name="📝 Logs", value=f"<#{panel['logs']}>" if panel.get("logs") else "Non défini", inline=True)

    e.add_field(name="🔢 Types configurés", value=str(len(choix)), inline=True)

    if choix:

        lines = []

        for c in choix:

            color_info = f" — `{c.get('btn_color','bleu')}`" if mode == "bouton" else ""

            ia_info = " — 🤖 IA activée" if c.get("ia_enabled") else ""

            lines.append(f"{c['emoji']} **{c['nom']}**{color_info}{ia_info}")

        e.add_field(name="🎟️ Types de tickets", value="\n".join(lines), inline=False)

    e.set_footer(text="Utilise les boutons ci-dessous pour configurer")

    return e

class TicketPanelModal(discord.ui.Modal, title="📋 Configurer le panel ticket"):

    t_titre = discord.ui.TextInput(label="Titre du panel", placeholder="Ex: Support ModeraBot", max_length=100)

    t_desc  = discord.ui.TextInput(label="Description du panel", style=discord.TextStyle.paragraph, placeholder="Ex: Clique ci-dessous pour ouvrir un ticket", max_length=500)

    t_image = discord.ui.TextInput(label="Image URL (optionnel)", placeholder="https://...", required=False, max_length=300)

    t_logs  = discord.ui.TextInput(label="ID salon logs (optionnel)", placeholder="Ex: 123456789", required=False, max_length=20)

    t_color = discord.ui.TextInput(label="Couleur hex (optionnel)", placeholder="Ex: #5865F2", required=False, max_length=10)

    def __init__(self, guild_id):

        super().__init__()

        self.guild_id = guild_id

    async def on_submit(self, interaction: discord.Interaction):

        data = ts_load(); gid = str(self.guild_id)

        data.setdefault(gid, {})["panel"] = {

            "titre": self.t_titre.value,

            "description": self.t_desc.value,

            "image": self.t_image.value or None,

            "logs": int(self.t_logs.value) if self.t_logs.value.strip().isdigit() else None,

            "couleur": self.t_color.value or "#5865F2"

        }

        data[gid].setdefault("choix", [])

        ts_save(data)

        await interaction.response.send_message(embed=discord.Embed(description="✅ Panel ticket configuré !", color=C_GREEN), ephemeral=True)

class TicketModeModal(discord.ui.Modal, title="🎨 Mode d'affichage du panel"):

    t_mode = discord.ui.TextInput(

        label="Mode : bouton / select / container_v2",

        placeholder="Tapez 'bouton', 'select' ou 'container_v2'",

        max_length=15

    )

    def __init__(self, guild_id):

        super().__init__()

        self.guild_id = guild_id

    async def on_submit(self, interaction: discord.Interaction):

        mode = self.t_mode.value.strip().lower()

        valid_modes = ("bouton", "select", "boutons", "selection", "menu", "container_v2", "containerv2", "v2", "container")

        if mode not in valid_modes:

            return await interaction.response.send_message(

                embed=discord.Embed(description="❌ Tape **`bouton`**, **`select`** ou **`container_v2`**.", color=C_RED), ephemeral=True)

        if mode in ("boutons",): mode = "bouton"

        if mode in ("selection", "menu"): mode = "select"

        if mode in ("containerv2", "v2", "container"): mode = "container_v2"

        # Mode select = premium uniquement
        if mode == "select" and not is_premium(str(interaction.user.id)):
            return await interaction.response.send_message(embed=discord.Embed(
                title="⭐ Fonctionnalité Premium",
                description=(
                    "Le mode **Menu déroulant** est réservé aux membres **premium**.\n\n"
                    "🔘 Le mode **Boutons** est disponible gratuitement.\n"
                    f"⭐ Active le premium avec **`+premium`** pour débloquer le menu déroulant !"
                ),
                color=C_GOLD
            ), ephemeral=True)

        data = ts_load(); gid = str(self.guild_id)

        data.setdefault(gid, {}).setdefault("panel", {})["mode"] = mode

        ts_save(data)

        label = "🔘 Boutons" if mode == "bouton" else ("📋 Menu déroulant" if mode == "select" else "📦 Container V2")

        note = "\n\n💡 Pour les boutons, tu peux configurer la couleur de chaque type via **✏️ Modifier message**." if mode == "bouton" else ""

        await interaction.response.send_message(

            embed=discord.Embed(description=f"✅ Mode changé en **{label}**{note}", color=C_GREEN), ephemeral=True)

class TicketChoixModal(discord.ui.Modal, title="➕ Ajouter un type de ticket"):

    t_nom   = discord.ui.TextInput(label="Nom du type", placeholder="Ex: Support", max_length=25)

    t_desc  = discord.ui.TextInput(label="Description courte", placeholder="Ex: Aide générale", max_length=97)

    t_emoji = discord.ui.TextInput(label="Emoji", placeholder="Ex: 🎫", max_length=5)

    t_roles = discord.ui.TextInput(label="IDs des rôles staff (séparés par espace)", placeholder="Ex: 123456 789012", max_length=200)

    t_categ = discord.ui.TextInput(label="ID catégorie", placeholder="Ex: 123456789", max_length=20)

    def __init__(self, guild_id):

        super().__init__()

        self.guild_id = guild_id

    async def on_submit(self, interaction: discord.Interaction):

        data = ts_load(); gid = str(self.guild_id)

        try:

            role_ids = [int(r.strip()) for r in self.t_roles.value.split() if r.strip().isdigit()]

            cat_id = int(self.t_categ.value.strip())

        except:

            return await interaction.response.send_message(embed=discord.Embed(description="❌ IDs invalides.", color=C_RED), ephemeral=True)

        data.setdefault(gid, {}).setdefault("choix", []).append({

            "nom": self.t_nom.value, "description": self.t_desc.value,

            "emoji": self.t_emoji.value, "categorie": cat_id, "roles": role_ids,

            "titre": f"Ticket — {self.t_nom.value}", "message": "Bienvenue {user} ! Explique ton problème.",

            "btn_color": "bleu",

            "salon_name": "ticket-{username}"

        })

        ts_save(data)

        await interaction.response.send_message(

            embed=discord.Embed(

                description=(

                    f"✅ Type **{self.t_nom.value}** ajouté !\n\n"

                    "💡 Utilise **✏️ Modifier** pour personnaliser :\n"

                    "• Le message dans le ticket\n"

                    "• La couleur du bouton (`bleu/vert/rouge/gris`)\n"

                    "• Le nom du salon — variables dispo : `{username}` `{userid}` `{server}`"

                ), color=C_GREEN),

            ephemeral=True)

class TicketChoixMessageModal(discord.ui.Modal, title="✏️ Modifier message, couleur, salon"):

    t_nom    = discord.ui.TextInput(label="Nom du type à modifier", placeholder="Ex: Support", max_length=25)

    t_titre  = discord.ui.TextInput(label="Titre embed dans le ticket", placeholder="Ex: 🎫 Ticket Support", max_length=100)

    t_msg    = discord.ui.TextInput(label="Message dans le ticket", style=discord.TextStyle.paragraph, placeholder="Ex: Bonjour {user} ! Explique ton problème.", max_length=500)

    t_salon  = discord.ui.TextInput(label="Nom du salon ({username} {userid} {server})", placeholder="Ex: ticket-{username} ou support-{userid}", required=False, max_length=50)

    t_color  = discord.ui.TextInput(label="Couleur bouton (bleu/vert/rouge/gris)", placeholder="bleu / vert / rouge / gris", required=False, max_length=10)

    def __init__(self, guild_id):

        super().__init__()

        self.guild_id = guild_id

    async def on_submit(self, interaction: discord.Interaction):

        data = ts_load(); gid = str(self.guild_id)

        found = False

        valid_colors = {"bleu", "vert", "rouge", "gris", "blue", "green", "red", "gray", "grey"}

        color_val = self.t_color.value.strip().lower() if self.t_color.value.strip() else None

        if color_val and color_val not in valid_colors:

            color_val = "bleu"

        salon_val = self.t_salon.value.strip() if self.t_salon.value.strip() else None

        # Sanitize salon name: remove chars Discord doesn't allow

        if salon_val:

            import re as _re

            salon_val = _re.sub(r"[^a-z0-9\-_{} ]", "", salon_val.lower()).strip().replace(" ", "-")[:50] or "ticket-{username}"

        for c in data.get(gid, {}).get("choix", []):

            if c["nom"].lower() == self.t_nom.value.lower():

                c["titre"] = self.t_titre.value

                c["message"] = self.t_msg.value

                if color_val: c["btn_color"] = color_val

                if salon_val: c["salon_name"] = salon_val

                found = True

                break

        if found:

            ts_save(data)

            lines = [f"✅ Type **{self.t_nom.value}** mis à jour !"]

            if color_val: lines.append(f"🎨 Couleur bouton : `{color_val}`")

            if salon_val: lines.append(f"📁 Nom salon : `{salon_val}`")

            await interaction.response.send_message(

                embed=discord.Embed(description="\n".join(lines), color=C_GREEN), ephemeral=True)

        else:

            await interaction.response.send_message(

                embed=discord.Embed(description=f"❌ Type `{self.t_nom.value}` introuvable.", color=C_RED), ephemeral=True)

class TicketEmbedModal(discord.ui.Modal, title="🖊️ Embed du ticket — Titre & Description"):

    t_nom   = discord.ui.TextInput(label="Nom du type à modifier", placeholder="Ex: Support", max_length=25)

    t_titre = discord.ui.TextInput(label="Titre de l'embed du ticket", placeholder="Ex: 🎫 Ticket Support", max_length=100)

    t_desc  = discord.ui.TextInput(

        label="Description de l'embed du ticket",

        style=discord.TextStyle.paragraph,

        placeholder="Ex: Bonjour {user} !\nExplique ton problème ci-dessous.",

        max_length=500

    )

    def __init__(self, guild_id, nom_prefill=""):

        super().__init__()

        self.guild_id = guild_id

        if nom_prefill:

            self.t_nom.default = nom_prefill

    async def on_submit(self, interaction: discord.Interaction):

        data = ts_load(); gid = str(self.guild_id)

        found = False

        for c in data.get(gid, {}).get("choix", []):

            if c["nom"].lower() == self.t_nom.value.strip().lower():

                c["titre"]   = self.t_titre.value.strip()

                c["message"] = self.t_desc.value.strip()

                found = True

                break

        if found:

            ts_save(data)

            await interaction.response.send_message(

                embed=discord.Embed(

                    description=(

                        f"✅ Embed du ticket **{self.t_nom.value}** mis à jour !\n\n"

                        f"📌 **Titre :** {self.t_titre.value}\n"

                        f"📝 **Description :** {self.t_desc.value[:100]}{'...' if len(self.t_desc.value)>100 else ''}"

                    ), color=C_GREEN

                ), ephemeral=True)

        else:

            await interaction.response.send_message(

                embed=discord.Embed(description=f"❌ Type `{self.t_nom.value}` introuvable.", color=C_RED),

                ephemeral=True)

# ══════════════════════════════════════════════════════════════════════════════
# TICKETS PERSISTANTS — état survivant aux redémarrages
#   panels  : message du panneau → on ré-attache sa vue au démarrage
#   tickets : salon de ticket ouvert → on retrouve auteur / staff / logs
# ══════════════════════════════════════════════════════════════════════════════
TICKET_STATE_FILE = "ticket_state.json"


def tk_state():
    d = jload(TICKET_STATE_FILE)
    d.setdefault("panels", {})
    d.setdefault("tickets", {})
    return d


def tk_state_save(d):
    jsave(TICKET_STATE_FILE, d)


def tk_record_panel(message, guild_id, mode):
    """Mémorise un panneau envoyé pour pouvoir réactiver ses boutons après un restart."""
    try:
        d = tk_state()
        d["panels"][str(message.id)] = {
            "guild": int(guild_id),
            "channel": int(message.channel.id),
            "mode": mode,
        }
        # on ne garde que les 200 derniers panneaux
        if len(d["panels"]) > 200:
            for k in list(d["panels"])[:-200]:
                d["panels"].pop(k, None)
        tk_state_save(d)
    except Exception as err:
        print(f"[tickets] enregistrement du panneau impossible : {err}")


def tk_record_ticket(channel, author_id, roles, logs_channel):
    """Mémorise un ticket ouvert (auteur, rôles staff, salon de logs)."""
    try:
        d = tk_state()
        d["tickets"][str(channel.id)] = {
            "author": int(author_id),
            "roles": [int(r) for r in (roles or [])],
            "logs": int(getattr(logs_channel, "id", 0) or 0),
        }
        tk_state_save(d)
    except Exception as err:
        print(f"[tickets] enregistrement du ticket impossible : {err}")


def tk_forget_ticket(channel_id):
    try:
        d = tk_state()
        if d["tickets"].pop(str(channel_id), None) is not None:
            tk_state_save(d)
    except Exception:
        pass


async def tk_restore_views():
    """Réactive les panneaux et les boutons de fermeture après un redémarrage."""
    # Boutons Claim / Fermer : une seule vue globale, l'état est relu au clic
    try:
        bot.add_view(TicketCloseView2(0, [], None))
    except Exception as err:
        print(f"[tickets] vue de fermeture non réactivée : {err}")

    d = tk_state()
    data_all = ts_load()
    ok, mortes = 0, []

    for mid, info in list(d["panels"].items()):
        guild = bot.get_guild(int(info.get("guild", 0)))
        if not guild:
            continue
        conf = data_all.get(str(guild.id))
        if not conf or not conf.get("choix"):
            mortes.append(mid)
            continue
        mode = info.get("mode") or conf.get("panel", {}).get("mode", "select")
        try:
            if mode == "bouton":
                view = TicketButtonPanelView(guild, conf)
            elif mode == "container_v2":
                view = TicketContainerV2View(guild, conf)
            else:
                view = TicketSelectView2(guild, conf)
            # lié au message : deux serveurs peuvent avoir les mêmes custom_id sans se marcher dessus
            bot.add_view(view, message_id=int(mid))
            ok += 1
        except Exception as err:
            print(f"[tickets] panneau {mid} non réactivé : {err}")
            mortes.append(mid)

    # nettoyage des salons de tickets qui n'existent plus
    for cid in list(d["tickets"]):
        if not bot.get_channel(int(cid)):
            d["tickets"].pop(cid, None)
    for mid in mortes:
        d["panels"].pop(mid, None)
    tk_state_save(d)
    print(f"✅ Tickets : {ok} panneau(x) réactivé(s), {len(d['tickets'])} ticket(s) ouvert(s) suivi(s)")


class TicketEmbedSelectView(discord.ui.View):

    """Select menu pour choisir le type de ticket, puis ouvrir TicketEmbedModal."""

    def __init__(self, guild_id, author_id):

        super().__init__(timeout=120)

        self.guild_id  = guild_id

        self.author_id = author_id

        data = ts_load()

        choix = data.get(str(guild_id), {}).get("choix", [])

        if not choix:

            return

        options = [

            discord.SelectOption(

                label=c["nom"], value=c["nom"],

                emoji=c.get("emoji", "🎫"),

                description=f"Titre actuel : {c.get('titre','—')[:50]}"

            )

            for c in choix[:25]

        ]

        sel = discord.ui.Select(

            placeholder="Choisis le type à modifier...",

            options=options

        )

        sel.callback = self._on_select

        self.add_item(sel)

    async def _on_select(self, interaction: discord.Interaction):

        if interaction.user.id != self.author_id:

            return await interaction.response.send_message("❌ Pas pour toi.", ephemeral=True)

        nom = interaction.data["values"][0]

        # Pré-remplir les champs avec les valeurs actuelles

        data = ts_load()

        choix = data.get(str(self.guild_id), {}).get("choix", [])

        entry = next((c for c in choix if c["nom"] == nom), None)

        modal = TicketEmbedModal(self.guild_id, nom_prefill=nom)

        if entry:

            modal.t_titre.default = entry.get("titre", f"Ticket — {nom}")

            modal.t_desc.default  = entry.get("message", "")

        await interaction.response.send_modal(modal)

class TicketSupprChoixModal(discord.ui.Modal, title="🗑️ Supprimer un type"):

    t_nom = discord.ui.TextInput(label="Nom du type à supprimer", placeholder="Ex: Support", max_length=25)

    def __init__(self, guild_id):

        super().__init__()

        self.guild_id = guild_id

    async def on_submit(self, interaction: discord.Interaction):

        data = ts_load(); gid = str(self.guild_id)

        before = len(data.get(gid, {}).get("choix", []))

        if gid in data:

            data[gid]["choix"] = [c for c in data[gid]["choix"] if c["nom"].lower() != self.t_nom.value.lower()]

        after = len(data.get(gid, {}).get("choix", []))

        ts_save(data)

        if before != after:

            await interaction.response.send_message(embed=discord.Embed(description=f"🗑️ Type **{self.t_nom.value}** supprimé.", color=C_ORANGE), ephemeral=True)

        else:

            await interaction.response.send_message(embed=discord.Embed(description=f"❌ Type `{self.t_nom.value}` introuvable.", color=C_RED), ephemeral=True)

# ─── Panel mode BOUTONS ───────────────────────────────────────────────────────

def resolve_salon_name(template, user):

    """Résout le nom du salon avec les variables {username}, {userid}, {server}."""

    import re as _re

    name = template or "ticket-{username}"

    name = name.replace("{username}", user.name[:20])

    name = name.replace("{userid}", str(user.id))

    name = name.replace("{server}", user.guild.name[:10] if hasattr(user, "guild") and user.guild else "srv")

    # Nettoyage Discord: minuscules, pas d'espaces, max 100 chars

    name = _re.sub(r"[^a-z0-9\-]", "-", name.lower())[:80].strip("-") or "ticket"

    return name

BTN_STYLE_MAP = {

    "bleu": discord.ButtonStyle.primary,

    "blue": discord.ButtonStyle.primary,

    "vert": discord.ButtonStyle.success,

    "green": discord.ButtonStyle.success,

    "rouge": discord.ButtonStyle.danger,

    "red": discord.ButtonStyle.danger,

    "gris": discord.ButtonStyle.secondary,

    "gray": discord.ButtonStyle.secondary,

    "grey": discord.ButtonStyle.secondary,

}

class TicketButtonPanelView(discord.ui.View):

    """Panel en mode boutons — un bouton par type de ticket."""

    def __init__(self, guild, data):

        super().__init__(timeout=None)

        for i, choix in enumerate(data.get("choix", [])[:5]):  # max 5 boutons Discord

            style = BTN_STYLE_MAP.get(choix.get("btn_color", "bleu"), discord.ButtonStyle.primary)

            btn = discord.ui.Button(

                label=choix["nom"],

                emoji=choix["emoji"],

                style=style,

                custom_id=f"ticket_btn_{i}"

            )

            btn.callback = self._make_callback(guild, data, choix)

            self.add_item(btn)

    def _make_callback(self, guild, data, choix):

        async def callback(interaction: discord.Interaction):

            cat = _as_category(guild, choix.get("categorie"))

            overwrites = {

                guild.default_role: discord.PermissionOverwrite(view_channel=False),

                interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True)

            }

            for rid in choix["roles"]:

                r = guild.get_role(rid)

                if r: overwrites[r] = discord.PermissionOverwrite(view_channel=True, send_messages=True)

            salon_tpl = choix.get("salon_name", "ticket-{username}")

            ch = await guild.create_text_channel(name=resolve_salon_name(salon_tpl, interaction.user), category=cat, overwrites=overwrites)

            logs_ch = _as_text_channel(guild, data["panel"].get("logs"))

            vars_ = {"{user}": interaction.user.mention, "{username}": interaction.user.name,

                     "{server}": guild.name, "{membercount}": str(guild.member_count)}

            titre = choix["titre"]

            desc = choix["message"]

            for k, v in vars_.items():

                titre = titre.replace(k, v)

                desc = desc.replace(k, v)

            e = discord.Embed(title=titre, description=desc, color=C_BLUE)

            _stamp_ticket_embed(e, f"Ticket {choix['nom']}")

            _staff = " ".join(f"<@&{rid}>" for rid in choix.get("roles", []))

            await ch.send(content=f"{interaction.user.mention} {_staff}".strip(), embed=e,

                          view=TicketCloseView2(interaction.user.id, choix["roles"], logs_ch),

                          allowed_mentions=MENTIONS_TICKET)

            tk_record_ticket(ch, interaction.user.id, choix["roles"], logs_ch)

            if logs_ch:

                await logs_ch.send(f"🎫 Ticket ouvert : {ch.mention} par {interaction.user.mention} — type : **{choix['nom']}**",
                                   allowed_mentions=MENTIONS_LOGS)

            await interaction.response.send_message(f"✅ Ticket créé : {ch.mention}", ephemeral=True)

        return callback



# ─── Panel mode CONTAINER V2 ──────────────────────────────────────────────────

class TicketContainerV2View(discord.ui.View):

    """Panel en mode Container V2 — embed + boutons dans le container Discord V2."""

    def __init__(self, guild, data):

        super().__init__(timeout=None)

        panel = data.get("panel", {})

        # Titre + description affichés via l'embed passé au container
        self._panel_title = panel.get("titre", "🎫 Support")
        self._panel_desc  = panel.get("description", "Clique sur un bouton pour ouvrir un ticket.")
        try:
            self._panel_color = int(panel.get("couleur", "#5865F2").replace("#", ""), 16)
        except Exception:
            self._panel_color = C_BLUE

        for i, choix in enumerate(data.get("choix", [])[:5]):

            style = BTN_STYLE_MAP.get(choix.get("btn_color", "bleu"), discord.ButtonStyle.primary)

            btn = discord.ui.Button(

                label=choix["nom"],

                emoji=choix.get("emoji"),

                style=style,

                custom_id=f"ticket_cv2_{i}"

            )

            btn.callback = self._make_callback(guild, data, choix)

            self.add_item(btn)

    def _make_callback(self, guild, data, choix):

        async def callback(interaction: discord.Interaction):

            cat = _as_category(guild, choix.get("categorie"))

            overwrites = {

                guild.default_role: discord.PermissionOverwrite(view_channel=False),

                interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True)

            }

            for rid in choix["roles"]:

                r = guild.get_role(rid)

                if r: overwrites[r] = discord.PermissionOverwrite(view_channel=True, send_messages=True)

            salon_tpl = choix.get("salon_name", "ticket-{username}")

            ch = await guild.create_text_channel(name=resolve_salon_name(salon_tpl, interaction.user), category=cat, overwrites=overwrites)

            logs_ch = _as_text_channel(guild, data["panel"].get("logs"))

            vars_ = {"{user}": interaction.user.mention, "{username}": interaction.user.name,

                     "{server}": guild.name, "{membercount}": str(guild.member_count)}

            titre = choix["titre"]

            desc = choix["message"]

            for k, v in vars_.items():

                titre = titre.replace(k, v)

                desc = desc.replace(k, v)

            e = discord.Embed(title=titre, description=desc, color=C_BLUE)

            _stamp_ticket_embed(e, f"Ticket {choix['nom']}")

            _staff = " ".join(f"<@&{rid}>" for rid in choix.get("roles", []))

            await ch.send(content=f"{interaction.user.mention} {_staff}".strip(), embed=e,

                          view=TicketCloseView2(interaction.user.id, choix["roles"], logs_ch),

                          allowed_mentions=MENTIONS_TICKET)

            tk_record_ticket(ch, interaction.user.id, choix["roles"], logs_ch)

            if logs_ch:

                await logs_ch.send(f"🎫 Ticket ouvert : {ch.mention} par {interaction.user.mention} — type : **{choix['nom']}**",
                                   allowed_mentions=MENTIONS_LOGS)

            await interaction.response.send_message(f"✅ Ticket créé : {ch.mention}", ephemeral=True)

        return callback

# ─── Vue de config ticket ─────────────────────────────────────────────────────

class TicketView(discord.ui.View):

    def __init__(self, ctx):

        super().__init__(timeout=None)

        self.ctx = ctx

    @discord.ui.button(label="Config Panel", style=discord.ButtonStyle.primary, emoji="📋")

    async def btn_panel(self, interaction: discord.Interaction, button: discord.ui.Button):

        if interaction.user.id != self.ctx.author.id: return await interaction.response.send_message(embed=embed_err("Ce menu n'est pas pour toi."), ephemeral=True)

        await interaction.response.send_modal(TicketPanelModal(interaction.guild.id))

    @discord.ui.button(label="Mode affichage", style=discord.ButtonStyle.secondary, emoji="🎨")

    async def btn_mode(self, interaction: discord.Interaction, button: discord.ui.Button):

        if interaction.user.id != self.ctx.author.id: return await interaction.response.send_message(embed=embed_err("Ce menu n'est pas pour toi."), ephemeral=True)

        await interaction.response.send_modal(TicketModeModal(interaction.guild.id))

    @discord.ui.button(label="Ajouter type", style=discord.ButtonStyle.success, emoji="➕")

    async def btn_add(self, interaction: discord.Interaction, button: discord.ui.Button):

        if interaction.user.id != self.ctx.author.id: return await interaction.response.send_message(embed=embed_err("Ce menu n'est pas pour toi."), ephemeral=True)

        await interaction.response.send_modal(TicketChoixModal(interaction.guild.id))

    @discord.ui.button(label="Modifier message", style=discord.ButtonStyle.secondary, emoji="✏️")

    async def btn_msg(self, interaction: discord.Interaction, button: discord.ui.Button):

        if interaction.user.id != self.ctx.author.id: return await interaction.response.send_message(embed=embed_err("Ce menu n'est pas pour toi."), ephemeral=True)

        await interaction.response.send_modal(TicketChoixMessageModal(interaction.guild.id))

    @discord.ui.button(label="Embed du ticket", style=discord.ButtonStyle.secondary, emoji="🖊️")

    async def btn_embed(self, interaction: discord.Interaction, button: discord.ui.Button):

        if interaction.user.id != self.ctx.author.id: return await interaction.response.send_message(embed=embed_err("Ce menu n'est pas pour toi."), ephemeral=True)

        data = ts_load(); gid = str(interaction.guild.id)

        choix = data.get(gid, {}).get("choix", [])

        if not choix:

            return await interaction.response.send_message(

                embed=discord.Embed(description="❌ Aucun type de ticket configuré.", color=C_RED), ephemeral=True)

        view = TicketEmbedSelectView(interaction.guild.id, interaction.user.id)

        await interaction.response.send_message(

            embed=discord.Embed(

                title="🖊️ Modifier l'embed du ticket",

                description="Sélectionne le type de ticket dont tu veux modifier le **titre** et la **description** de l'embed.",

                color=C_BLUE

            ), view=view, ephemeral=True)

    @discord.ui.button(label="Supprimer type", style=discord.ButtonStyle.danger, emoji="🗑️")

    async def btn_del(self, interaction: discord.Interaction, button: discord.ui.Button):

        if interaction.user.id != self.ctx.author.id: return await interaction.response.send_message(embed=embed_err("Ce menu n'est pas pour toi."), ephemeral=True)

        await interaction.response.send_modal(TicketSupprChoixModal(interaction.guild.id))

    @discord.ui.button(label="Envoyer panel", style=discord.ButtonStyle.success, emoji="📤")

    async def btn_send(self, interaction: discord.Interaction, button: discord.ui.Button):

        if interaction.user.id != self.ctx.author.id: return await interaction.response.send_message(embed=embed_err("Ce menu n'est pas pour toi."), ephemeral=True)

        data = ts_load(); gid = str(interaction.guild.id)

        if gid not in data or "panel" not in data[gid]:

            return await interaction.response.send_message(

                embed=discord.Embed(description="❌ Configure d'abord le panel !", color=C_RED), ephemeral=True)

        panel = data[gid]["panel"]

        if not data[gid].get("choix"):

            return await interaction.response.send_message(

                embed=discord.Embed(description="❌ Ajoute d'abord au moins un type de ticket !", color=C_RED), ephemeral=True)

        try:

            color = int(panel["couleur"].replace("#", ""), 16)

        except:

            color = C_BLUE

        e = discord.Embed(title=panel["titre"], description=panel["description"], color=color)

        if panel.get("image"): e.set_image(url=panel["image"])

        mode = panel.get("mode", "select")

        if mode == "bouton":

            nb = len(data[gid]["choix"])

            if nb > 5:

                return await interaction.response.send_message(

                    embed=discord.Embed(description="❌ Mode bouton : max **5 types** de tickets. Supprime-en quelques-uns.", color=C_RED), ephemeral=True)

            panel_view = TicketButtonPanelView(interaction.guild, data[gid])

        elif mode == "container_v2":
            # ── Container V2 : embed DANS le container + boutons dedans ──────
            panel_view = TicketContainerV2View(interaction.guild, data[gid])
            # L'embed est automatiquement transformé en Container V2 (boutons dedans)
            e_v2 = discord.Embed(
                title=panel_view._panel_title,
                description=panel_view._panel_desc,
                color=panel_view._panel_color
            )
            await interaction.response.send_message(
                embed=discord.Embed(description="✅ Panel envoyé ! (Mode : 📦 Container V2)", color=C_GREEN), ephemeral=True)
            _sent_panel = await interaction.channel.send(embed=e_v2, view=panel_view)

            tk_record_panel(_sent_panel, interaction.guild.id, "container_v2")
            await interaction.message.edit(embed=build_ticket_status_embed(interaction.guild.id))
            return

        else:

            panel_view = TicketSelectView2(interaction.guild, data[gid])

        # On repond AVANT le travail lourd (l'interaction expire en 3 s)
        await interaction.response.send_message(

            embed=discord.Embed(description=f"✅ Panel envoyé ! (Mode : {'🔘 Boutons' if mode == 'bouton' else ('📦 Container V2' if mode == 'container_v2' else '📋 Menu déroulant')})", color=C_GREEN), ephemeral=True)

        _sent_panel = await interaction.channel.send(embed=e, view=panel_view)

        tk_record_panel(_sent_panel, interaction.guild.id, mode)

        await interaction.message.edit(embed=build_ticket_status_embed(interaction.guild.id))

@bot.command(name="ticket", aliases=["tickets","tkt","tiket","tikket"])

async def ticket_cmd(ctx):

    if not ctx.author.guild_permissions.administrator and str(ctx.author.id) not in OWNER_IDS:

        return await ctx.send(embed=embed_err("Permission administrateur requise."))

    await ctx.send(embed=build_ticket_status_embed(ctx.guild.id), view=TicketView(ctx))

# ══════════════════════════════════════════════════

# PREMIUM — 100% PREFIX + MODALS

# ══════════════════════════════════════════════════

def build_premium_status_embed(guild_id):

    data = jload(FILES["premium"])

    now = int(time.time())

    users = {uid: info for uid, info in data.get("users", {}).items() if info.get("expires_at", 0) > now}

    codes = data.get("codes", {})

    total_codes = len(codes)

    used_codes = sum(1 for c in codes.values() if c.get("used"))

    e = discord.Embed(title="⭐ Gestion Premium", color=C_GOLD)

    e.add_field(name="👥 Membres actifs", value=str(len(users)), inline=True)

    e.add_field(name="🔑 Codes total", value=str(total_codes), inline=True)

    e.add_field(name="✅ Codes utilisés", value=str(used_codes), inline=True)

    if users:

        lines = list(users.items())[:5]

        e.add_field(name="📋 Membres premium (5 max)", value="\n".join(f"<@{uid}> → <t:{info['expires_at']}:R>" for uid, info in lines), inline=False)

    e.set_footer(text="Utilise les boutons ci-dessous pour gérer")

    return e

class PremiumGenCodeModal(discord.ui.Modal, title="🔑 Générer un code premium"):

    t_duration = discord.ui.TextInput(label="Durée en jours", placeholder="Ex: 30", max_length=5)

    t_qty      = discord.ui.TextInput(label="Quantité de codes", placeholder="Ex: 1", max_length=3)

    t_code     = discord.ui.TextInput(label="Code custom (optionnel, sinon auto)", required=False, max_length=32)

    async def on_submit(self, interaction: discord.Interaction):

        data = jload(FILES["premium"])

        try:

            days = int(self.t_duration.value.strip())

            qty  = max(1, min(20, int(self.t_qty.value.strip())))

        except:

            return await interaction.response.send_message(embed=discord.Embed(description="❌ Durée/quantité invalide.", color=C_RED), ephemeral=True)

        duration = days * 86400

        generated = []

        for _ in range(qty):

            code = self.t_code.value.strip() if self.t_code.value.strip() and qty == 1 else ''.join(random.choices(string.ascii_uppercase + string.digits, k=12))

            if code not in data.setdefault("codes", {}):

                data["codes"][code] = {"used": False, "duration": duration}

                generated.append(code)

        jsave(FILES["premium"], data)

        e = discord.Embed(title="✅ Codes générés", description="\n".join(f"`{c}` — {days}j" for c in generated), color=C_GOLD)

        await interaction.response.send_message(embed=e, ephemeral=True)

class PremiumRemoveModal(discord.ui.Modal, title="🗑️ Retirer le premium"):

    t_uid = discord.ui.TextInput(label="ID Discord du membre", placeholder="Ex: 123456789", max_length=20)

    async def on_submit(self, interaction: discord.Interaction):

        data = jload(FILES["premium"])

        uid = self.t_uid.value.strip()

        if uid not in data.get("users", {}):

            return await interaction.response.send_message(embed=discord.Embed(description="❌ Membre non premium.", color=C_RED), ephemeral=True)

        del data["users"][uid]

        jsave(FILES["premium"], data)

        # Retirer le rôle

        guild = interaction.guild

        member = guild.get_member(int(uid))

        role = guild.get_role(PREMIUM_ROLE_ID)

        if member and role:

            try: await member.remove_roles(role, reason="Premium retiré par admin")

            except: pass

        await interaction.response.send_message(embed=discord.Embed(description=f"✅ Premium retiré pour <@{uid}>.", color=C_GREEN), ephemeral=True)

class PremiumActivateModal(discord.ui.Modal, title="⭐ Activer le premium"):

    t_code = discord.ui.TextInput(label="Code premium", placeholder="Ex: ABCDE12345FG", max_length=32)

    async def on_submit(self, interaction: discord.Interaction):

        data = jload(FILES["premium"])

        logs = jload(FILES["premium_logs"])

        now = int(time.time())

        uid = str(interaction.user.id)

        code = self.t_code.value.strip()

        if code not in data.get("codes", {}):

            return await interaction.response.send_message(embed=discord.Embed(description=f"❌ Code invalide.\n👉 {PREMIUM_LINK}", color=C_RED), ephemeral=True)

        code_data = data["codes"][code]

        if code_data["used"]:

            return await interaction.response.send_message(embed=discord.Embed(description=f"❌ Code déjà utilisé.\n👉 {PREMIUM_LINK}", color=C_RED), ephemeral=True)

        expires_at = now + code_data["duration"]

        code_data["used"] = True

        data["users"][uid] = {"expires_at": expires_at}

        logs["activations"].append({"user_id": uid, "code": code, "activated_at": now,

                                     "duration_seconds": code_data["duration"], "expires_at": expires_at})

        jsave(FILES["premium"], data)

        jsave(FILES["premium_logs"], logs)

        guild = interaction.guild

        member = guild.get_member(interaction.user.id)

        role = guild.get_role(PREMIUM_ROLE_ID)

        if role and member:

            try: await member.add_roles(role, reason="Activation premium")

            except: pass

        log_ch = bot.get_channel(LOG_CHANNEL_ID)

        if log_ch:

            e = discord.Embed(title="⭐ Activation Premium", color=C_GOLD)

            e.add_field(name="👤 Utilisateur", value=f"<@{uid}> (`{uid}`)", inline=False)

            e.add_field(name="🔑 Code", value=f"`{code}`", inline=False)

            e.add_field(name="⏳ Durée", value=f"{code_data['duration']//86400}j", inline=False)

            e.add_field(name="🏁 Expire", value=f"<t:{expires_at}:R>", inline=False)

            await log_ch.send(embed=e, allowed_mentions=MENTIONS_LOGS)

        await interaction.response.send_message(embed=discord.Embed(

            title="⭐ Premium activé !", description=f"Ton premium expire <t:{expires_at}:R>.", color=C_GOLD), ephemeral=True)

class PremiumView(discord.ui.View):

    def __init__(self, ctx, is_owner=False):

        super().__init__(timeout=None)

        self.ctx = ctx

        self.is_owner = is_owner

    @discord.ui.button(label="⭐ Activer", style=discord.ButtonStyle.success, emoji="⭐")

    async def btn_activate(self, interaction: discord.Interaction, button: discord.ui.Button):

        if interaction.user.id != self.ctx.author.id: return await interaction.response.send_message(embed=embed_err("Ce menu n'est pas pour toi."), ephemeral=True)

        await interaction.response.send_modal(PremiumActivateModal())

    @discord.ui.button(label="🔑 Générer code", style=discord.ButtonStyle.primary, emoji="🔑")

    async def btn_gen(self, interaction: discord.Interaction, button: discord.ui.Button):

        if interaction.user.id != self.ctx.author.id: return await interaction.response.send_message(embed=embed_err("Ce menu n'est pas pour toi."), ephemeral=True)

        if not self.is_owner:

            return await interaction.response.send_message(embed=discord.Embed(description="❌ Réservé aux owners.", color=C_RED), ephemeral=True)

        await interaction.response.send_modal(PremiumGenCodeModal())

    @discord.ui.button(label="🗑️ Retirer", style=discord.ButtonStyle.danger, emoji="🗑️")

    async def btn_remove(self, interaction: discord.Interaction, button: discord.ui.Button):

        if interaction.user.id != self.ctx.author.id: return await interaction.response.send_message(embed=embed_err("Ce menu n'est pas pour toi."), ephemeral=True)

        if not self.is_owner:

            return await interaction.response.send_message(embed=discord.Embed(description="❌ Réservé aux owners.", color=C_RED), ephemeral=True)

        await interaction.response.send_modal(PremiumRemoveModal())

    @discord.ui.button(label="📋 Logs", style=discord.ButtonStyle.secondary, emoji="📋")

    async def btn_logs(self, interaction: discord.Interaction, button: discord.ui.Button):

        if interaction.user.id != self.ctx.author.id: return await interaction.response.send_message(embed=embed_err("Ce menu n'est pas pour toi."), ephemeral=True)

        if not self.is_owner:

            return await interaction.response.send_message(embed=discord.Embed(description="❌ Réservé aux owners.", color=C_RED), ephemeral=True)

        logs = jload(FILES["premium_logs"])

        if not logs.get("activations"):

            return await interaction.response.send_message(embed=discord.Embed(description="ℹ️ Aucun log.", color=C_BLUE), ephemeral=True)

        lines = [f"<@{l['user_id']}> • `{l['code']}` • <t:{l['activated_at']}:R>" for l in logs["activations"][-20:]]

        await interaction.response.send_message(embed=discord.Embed(title="📜 Logs Premium", description="\n".join(lines), color=C_GOLD), ephemeral=True)

    @discord.ui.button(label="🔄 Actualiser", style=discord.ButtonStyle.secondary, emoji="🔄")

    async def btn_refresh(self, interaction: discord.Interaction, button: discord.ui.Button):

        if interaction.user.id != self.ctx.author.id: return await interaction.response.send_message(embed=embed_err("Ce menu n'est pas pour toi."), ephemeral=True)

        await interaction.message.edit(embed=build_premium_status_embed(interaction.guild.id))

        await interaction.response.defer()

@bot.command(name="premium", aliases=["prem","prm","abonnement"])

async def premium_cmd(ctx, code: str = None):

    # Sans code → afficher le statut + lien support

    if not code:

        # Owner → panel de gestion

        if str(ctx.author.id) in OWNER_IDS:

            return await ctx.send(embed=build_premium_status_embed(ctx.guild.id), view=PremiumView(ctx, is_owner=True))

        # Utilisateur normal → info + comment obtenir

        e = discord.Embed(title="⭐ Premium ModeraBot", color=C_GOLD)

        e.description = (

            "**Comment activer le premium ?**\n"

            f"> Utilise `+premium <code>` avec ton code\n\n"

            "**Comment obtenir un code ?**\n"

            f"> Rejoins notre serveur et crée un ticket !\n"

            f"> 👉 [Rejoindre le support]({PREMIUM_LINK})"

        )

        e.set_footer(text="ModeraBot • Premium")

        return await ctx.send(embed=e)

    # Avec code → activation directe

    data = jload(FILES["premium"])

    logs = jload(FILES["premium_logs"])

    now  = int(time.time())

    uid  = str(ctx.author.id)

    if code not in data.get("codes", {}):

        e = discord.Embed(

            description=f"❌ Code invalide.\n👉 Obtiens un code sur [le serveur support]({PREMIUM_LINK})",

            color=C_RED

        )

        return await ctx.send(embed=e)

    code_data = data["codes"][code]

    if code_data["used"]:

        return await ctx.send(embed=discord.Embed(

            description=f"❌ Ce code a déjà été utilisé.\n👉 [Serveur support]({PREMIUM_LINK})", color=C_RED))

    expires_at = now + code_data["duration"]

    code_data["used"] = True

    data["users"][uid] = {"expires_at": expires_at}

    logs.setdefault("activations", []).append({

        "user_id": uid, "code": code,

        "activated_at": now,

        "duration_seconds": code_data["duration"],

        "expires_at": expires_at

    })

    jsave(FILES["premium"], data)

    jsave(FILES["premium_logs"], logs)

    # Attribuer le rôle premium

    guild  = ctx.guild

    member = guild.get_member(ctx.author.id)

    role   = guild.get_role(PREMIUM_ROLE_ID)

    if role and member:

        try: await member.add_roles(role, reason="Activation premium")

        except: pass

    # Log dans le salon de logs

    log_ch = bot.get_channel(LOG_CHANNEL_ID)

    if log_ch:

        e_log = discord.Embed(title="⭐ Activation Premium", color=C_GOLD)

        e_log.add_field(name="👤 Utilisateur", value=f"<@{uid}> (`{uid}`)", inline=False)

        e_log.add_field(name="🔑 Code", value=f"`{code}`", inline=False)

        e_log.add_field(name="⏳ Durée", value=f"{code_data['duration']//86400}j", inline=False)

        e_log.add_field(name="🏁 Expire", value=f"<t:{expires_at}:R>", inline=False)

        await log_ch.send(embed=e_log, allowed_mentions=MENTIONS_LOGS)

    await ctx.send(embed=discord.Embed(

        title="⭐ Premium activé !",

        description=f"✅ Ton premium expire <t:{expires_at}:R>.\n🎭 Le rôle premium t'a été attribué.",

        color=C_GOLD

    ))

@tasks.loop(seconds=60)

async def check_premium_expirations():

    try:

        data = jload(FILES["premium"])

        now = int(time.time())

        guild = bot.get_guild(GUILD_ID)

        if not guild: return

        role = guild.get_role(PREMIUM_ROLE_ID)

        to_remove = [uid for uid, info in list(data.get("users", {}).items()) if info.get("expires_at", 0) < now]

        for uid in to_remove:

            member = guild.get_member(int(uid))

            if member and role:

                try: await member.remove_roles(role, reason="Premium expiré")

                except: pass

            if uid in data["users"]: del data["users"][uid]

        if to_remove: jsave(FILES["premium"], data)

    except: pass

# Ticket select system

class TicketCloseView2(discord.ui.View):

    def __init__(self, author_id, mod_roles, logs_channel):

        super().__init__(timeout=None)

        self.author_id    = author_id

        self.mod_roles    = mod_roles

        self.logs_channel = logs_channel if hasattr(logs_channel, "send") else None

    def _ctx(self, interaction):
        """Auteur / rôles staff / salon de logs du ticket.

        Après un redémarrage la vue est recréée vide : on relit alors
        ticket_state.json à partir du salon où le bouton a été cliqué.
        """
        if self.author_id:
            return self.author_id, self.mod_roles, self.logs_channel
        st = tk_state()["tickets"].get(str(interaction.channel.id), {})
        logs = interaction.guild.get_channel(st.get("logs") or 0) if interaction.guild else None
        return st.get("author", 0), st.get("roles", []), logs

    @discord.ui.button(label="Claim", emoji="🙋", style=discord.ButtonStyle.success, custom_id="tsc_claim")

    async def claim(self, interaction: discord.Interaction, button: discord.ui.Button):

        author_id, mod_roles, _logs = self._ctx(interaction)

        is_mod = any(r.id in mod_roles for r in interaction.user.roles) or interaction.user.guild_permissions.administrator

        if not is_mod:

            return await interaction.response.send_message("❌ Réservé au staff.", ephemeral=True)

        button.disabled = True

        button.label = f"Pris en charge par {interaction.user.display_name}"

        await interaction.response.edit_message(view=self)

        e = discord.Embed(

            title="✅ Ticket pris en charge",

            description=f"🙋 {interaction.user.mention} s'occupe de ce ticket.",

            color=C_GREEN

        )

        _stamp_ticket_embed(e)

        await interaction.channel.send(content=f"<@{author_id}>", embed=e)

    @discord.ui.button(label="Fermer le ticket", emoji="🔒", style=discord.ButtonStyle.danger, custom_id="tsc_close")

    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):

        author_id, mod_roles, logs_channel = self._ctx(interaction)

        is_author = interaction.user.id == author_id

        is_mod = any(r.id in mod_roles for r in interaction.user.roles) or interaction.user.guild_permissions.administrator

        if not is_author and not is_mod:

            return await interaction.response.send_message("❌ Tu n'as pas la permission.", ephemeral=True)

        if logs_channel:

            try:

                await logs_channel.send(f"🔒 Ticket fermé : {interaction.channel.name}",
                                        allowed_mentions=MENTIONS_LOGS)

            except Exception:

                pass

        tk_forget_ticket(interaction.channel.id)

        await interaction.channel.delete()

class TicketSelectMenu2(discord.ui.Select):

    def __init__(self, guild, data):

        options = []

        for c in data["choix"]:

            desc = c["description"][:97] + "..." if len(c["description"]) > 100 else c["description"]

            options.append(discord.SelectOption(label=c["nom"][:25], description=desc, emoji=c["emoji"]))

        super().__init__(placeholder="Choisis ton type de ticket", options=options, custom_id="tsc_menu")

        self.guild = guild

        self.data = data

    async def callback(self, interaction: discord.Interaction):

        choix = next(c for c in self.data["choix"] if c["nom"] == self.values[0])

        cat = _as_category(self.guild, choix.get("categorie"))

        salon_tpl = choix.get("salon_name", "ticket-{username}")

        ch = await self.guild.create_text_channel(name=resolve_salon_name(salon_tpl, interaction.user), category=cat)

        await ch.set_permissions(interaction.user, read_messages=True, send_messages=True)

        for rid in choix["roles"]:

            r = self.guild.get_role(rid)

            if r: await ch.set_permissions(r, read_messages=True, send_messages=True)

        await ch.set_permissions(self.guild.default_role, read_messages=False)

        logs_ch = _as_text_channel(self.guild, self.data["panel"].get("logs"))

        vars_ = {"{user}": interaction.user.mention, "{username}": interaction.user.name,

                 "{server}": self.guild.name, "{membercount}": str(self.guild.member_count)}

        titre = choix["titre"]

        desc = choix["message"]

        for k, v in vars_.items():

            titre = titre.replace(k, v)

            desc = desc.replace(k, v)

        e = discord.Embed(title=titre, description=desc, color=C_BLUE)

        _stamp_ticket_embed(e, f"Ticket {choix['nom']}")

        _staff = " ".join(f"<@&{rid}>" for rid in choix.get("roles", []))

        await ch.send(content=f"{interaction.user.mention} {_staff}".strip(), embed=e,

                      view=TicketCloseView2(interaction.user.id, choix["roles"], logs_ch),

                      allowed_mentions=MENTIONS_TICKET)

        tk_record_ticket(ch, interaction.user.id, choix["roles"], logs_ch)

        await interaction.response.send_message(f"✅ Ticket créé : {ch.mention}", ephemeral=True)

class TicketSelectView2(discord.ui.View):

    def __init__(self, guild, data):

        super().__init__(timeout=None)

        self.add_item(TicketSelectMenu2(guild, data))

def ts_load():

    return jload(FILES["ticket_select"])

def ts_save(data):

    jsave(FILES["ticket_select"], data)

# ══════════════════════════════════════════

# NOUVELLES COMMANDES UTILITAIRES

# ══════════════════════════════════════════

# Stockage snipe par salon

_snipe_deleted  = {}   # channel_id → {"content", "author", "timestamp", "attachments"}

_snipe_edited   = {}   # channel_id → {"before", "after", "author", "timestamp"}

_prevnames_data = {}   # user_id (str) → [{"name": ..., "ts": ...}, ...]

_member_stats   = {}   # guild_id → user_id → {"messages": n, "chars": n, "last_channel": ...}

# ─── helper: résoudre un membre par nom/mention/ID ───────────────────────────

async def resolve_member(ctx, raw: str):

    """Accepte mention, ID, ou pseudo (++ pas nécessaire pour un seul arg)."""

    raw = raw.strip().strip("<@!>").strip()

    # ID

    if raw.isdigit():

        try: return ctx.guild.get_member(int(raw)) or await ctx.guild.fetch_member(int(raw))

        except: pass

    # Nom

    return discord.utils.find(lambda m: m.name.lower() == raw.lower() or m.display_name.lower() == raw.lower(), ctx.guild.members)

# ─── AVATAR ──────────────────────────────────────────────────────────────────

@bot.command(name="avatar", aliases=["av","pfp"])

async def avatar_cmd(ctx, *, target: str = None):

    if target:

        member = await resolve_member(ctx, target)

        if not member:

            return await ctx.send(embed=embed_err(f"Membre `{target}` introuvable."))

    else:

        member = ctx.author

    url = member.display_avatar.url

    e = discord.Embed(title=f"🖼️ Avatar de {member.display_name}", color=C_BLUE)

    e.set_image(url=url)

    e.add_field(name="📥 Télécharger", value=f"[PNG]({str(url).split('?')[0]}?format=png) • [JPG]({str(url).split('?')[0]}?format=jpg) • [WEBP]({str(url).split('?')[0]}?format=webp)", inline=False)

    e.set_footer(text=f"ID : {member.id}")

    await ctx.send(embed=e)

# ─── BANNER ──────────────────────────────────────────────────────────────────

@bot.command(name="banner", aliases=["banniere"])

async def banner_cmd(ctx, *, target: str = None):

    if target:

        member = await resolve_member(ctx, target)

        if not member:

            return await ctx.send(embed=embed_err(f"Membre `{target}` introuvable."))

    else:

        member = ctx.author

    try:

        fetched = await bot.fetch_user(member.id)

    except:

        fetched = member

    banner = fetched.banner

    if not banner:

        return await ctx.send(embed=embed_warn(f"**{member.display_name}** n'a pas de bannière."))

    url = banner.url

    e = discord.Embed(title=f"🎨 Bannière de {member.display_name}", color=C_BLUE)

    e.set_image(url=url)

    e.add_field(name="📥 Télécharger", value=f"[PNG]({str(url).split('?')[0]}?format=png) • [WEBP]({str(url).split('?')[0]}?format=webp)", inline=False)

    await ctx.send(embed=e)

# ─── SERVERAVATAR ─────────────────────────────────────────────────────────────

@bot.command(name="serveravatar", aliases=["serverav","sav"])

async def serveravatar_cmd(ctx):

    g = ctx.guild

    if not g.icon:

        return await ctx.send(embed=embed_warn("Ce serveur n'a pas d'icône."))

    url = g.icon.url

    e = discord.Embed(title=f"🖼️ Icône de {g.name}", color=C_BLUE)

    e.set_image(url=url)

    e.add_field(name="📥 Télécharger", value=f"[PNG]({str(url).split('?')[0]}?format=png) • [JPG]({str(url).split('?')[0]}?format=jpg)", inline=False)

    await ctx.send(embed=e)

# ─── SERVERBANNER ─────────────────────────────────────────────────────────────

@bot.command(name="serverbanner", aliases=["serverbanniere"])

async def serverbanner_cmd(ctx):

    g = ctx.guild

    if not g.banner:

        return await ctx.send(embed=embed_warn("Ce serveur n'a pas de bannière."))

    url = g.banner.url

    e = discord.Embed(title=f"🎨 Bannière de {g.name}", color=C_BLUE)

    e.set_image(url=url)

    e.add_field(name="📥 Télécharger", value=f"[PNG]({str(url).split('?')[0]}?format=png) • [WEBP]({str(url).split('?')[0]}?format=webp)", inline=False)

    await ctx.send(embed=e)

# ─── CALCUL ──────────────────────────────────────────────────────────────────

@bot.command(name="calcul", aliases=["calc","math"])

async def calcul_cmd(ctx, *, expr: str = None):

    if not expr or expr.strip().lower() == "help":

        e = discord.Embed(title="🧮 Aide — Calcul", color=C_BLUE)

        e.add_field(name="Usage", value="`+calcul <expression>`", inline=False)

        e.add_field(name="Opérateurs", value="`+` `-` `*` `/` `**` (puissance) `%` (modulo) `//` (division entière)", inline=False)

        e.add_field(name="Fonctions", value="`sqrt(x)` `abs(x)` `round(x)` `sin(x)` `cos(x)` `log(x)`", inline=False)

        e.add_field(name="Exemples", value="`+calcul 2+2`\n`+calcul sqrt(144)`\n`+calcul 2**10`", inline=False)

        return await ctx.send(embed=e)

    import math as _math

    safe_env = {

        "sqrt": _math.sqrt, "abs": abs, "round": round,

        "sin": _math.sin, "cos": _math.cos, "tan": _math.tan,

        "log": _math.log, "log2": _math.log2, "log10": _math.log10,

        "pi": _math.pi, "e": _math.e, "floor": _math.floor, "ceil": _math.ceil,

        "__builtins__": {}

    }

    # Sécurité basique

    forbidden = ["import", "exec", "eval", "open", "os", "__"]

    if any(f in expr.lower() for f in forbidden):

        return await ctx.send(embed=embed_err("Expression non autorisée."))

    try:

        result = eval(expr.replace("^", "**"), safe_env)

        e = discord.Embed(title="🧮 Calcul", color=C_GREEN)

        e.add_field(name="📥 Expression", value=f"`{expr}`", inline=False)

        e.add_field(name="✅ Résultat", value=f"**`{result}`**", inline=False)

        await ctx.send(embed=e)

    except ZeroDivisionError:

        await ctx.send(embed=embed_err("Division par zéro impossible."))

    except Exception:

        await ctx.send(embed=embed_err(f"Expression invalide. Tape `+calcul help` pour l'aide."))

# ─── CHANNELINFO ─────────────────────────────────────────────────────────────

@bot.command(name="channelinfo", aliases=["ci","channel"])

async def channelinfo_cmd(ctx, *, target: str = None):

    if target:

        raw = target.strip().strip("<#>")

        ch = ctx.guild.get_channel(int(raw)) if raw.isdigit() else discord.utils.get(ctx.guild.channels, name=raw)

    else:

        ch = ctx.channel

    if not ch:

        return await ctx.send(embed=embed_err("Salon introuvable."))

    type_map = {

        discord.ChannelType.text: "💬 Texte", discord.ChannelType.voice: "🔊 Vocal",

        discord.ChannelType.category: "📁 Catégorie", discord.ChannelType.news: "📢 Annonces",

        discord.ChannelType.stage_voice: "🎙️ Scène", discord.ChannelType.forum: "💬 Forum",

    }

    e = discord.Embed(title=f"📋 {ch.name}", color=C_BLUE)

    e.add_field(name="🆔 ID", value=f"`{ch.id}`", inline=True)

    e.add_field(name="📂 Type", value=type_map.get(ch.type, str(ch.type)), inline=True)

    e.add_field(name="📅 Créé", value=discord.utils.format_dt(ch.created_at, style="R"), inline=True)

    if hasattr(ch, "topic") and ch.topic:

        e.add_field(name="📝 Sujet", value=ch.topic[:200], inline=False)

    if hasattr(ch, "category") and ch.category:

        e.add_field(name="📁 Catégorie", value=ch.category.name, inline=True)

    if hasattr(ch, "slowmode_delay") and ch.slowmode_delay:

        e.add_field(name="🐢 Slowmode", value=f"{ch.slowmode_delay}s", inline=True)

    if hasattr(ch, "nsfw"):

        e.add_field(name="🔞 NSFW", value="Oui" if ch.nsfw else "Non", inline=True)

    if hasattr(ch, "members"):

        e.add_field(name="👥 Membres", value=str(len(ch.members)), inline=True)

    e.set_footer(text=f"Demandé par {ctx.author}")

    await ctx.send(embed=e)

# ─── FIND ────────────────────────────────────────────────────────────────────

@bot.command(name="find")

async def find_cmd(ctx, *, target: str = None):

    """Trouve un membre dans un salon vocal."""

    if target:

        member = await resolve_member(ctx, target)

        if not member:

            return await ctx.send(embed=embed_err(f"Membre `{target}` introuvable."))

        if member.voice and member.voice.channel:

            vc = member.voice.channel

            e = discord.Embed(title=f"🔍 {member.display_name} trouvé !", color=C_GREEN)

            e.add_field(name="🔊 Salon vocal", value=vc.mention, inline=True)

            e.add_field(name="👥 Membres présents", value=str(len(vc.members)), inline=True)

            e.add_field(name="🔇 Muté", value="Oui" if member.voice.mute or member.voice.self_mute else "Non", inline=True)

            e.set_thumbnail(url=member.display_avatar.url)

        else:

            e = discord.Embed(description=f"**{member.display_name}** n'est dans aucun salon vocal.", color=C_ORANGE)

        return await ctx.send(embed=e)

    # Sans argument : liste tous les salons vocaux occupés

    occupied = [(vc, vc.members) for vc in ctx.guild.voice_channels if vc.members]

    if not occupied:

        return await ctx.send(embed=embed_warn("Aucun membre en vocal."))

    e = discord.Embed(title="🔊 Membres en vocal", color=C_BLUE)

    for vc, members in occupied[:10]:

        e.add_field(name=f"#{vc.name} ({len(members)})", value=", ".join(m.display_name for m in members[:10]), inline=False)

    await ctx.send(embed=e)

# ─── GITHUB ──────────────────────────────────────────────────────────────────

@bot.command(name="github", aliases=["gh"])

async def github_cmd(ctx, *, username: str = None):

    if not username:

        return await ctx.send(embed=embed_err("Usage : `+github <username>`"))

    try:

        r = requests.get(f"https://api.github.com/users/{username}", timeout=8)

        if r.status_code == 404:

            return await ctx.send(embed=embed_err(f"Utilisateur GitHub `{username}` introuvable."))

        d = r.json()

        e = discord.Embed(title=f"🐙 {d.get('name') or d['login']}", url=d["html_url"], color=0x24292F)

        e.set_thumbnail(url=d.get("avatar_url", ""))

        if d.get("bio"): e.add_field(name="📝 Bio", value=d["bio"][:200], inline=False)

        e.add_field(name="👤 Login", value=f"`{d['login']}`", inline=True)

        e.add_field(name="📦 Repos publics", value=str(d.get("public_repos", 0)), inline=True)

        e.add_field(name="👥 Followers", value=str(d.get("followers", 0)), inline=True)

        e.add_field(name="➡️ Following", value=str(d.get("following", 0)), inline=True)

        if d.get("company"): e.add_field(name="🏢 Entreprise", value=d["company"], inline=True)

        if d.get("location"): e.add_field(name="📍 Localisation", value=d["location"], inline=True)

        if d.get("blog"): e.add_field(name="🔗 Site", value=d["blog"], inline=True)

        if d.get("created_at"):

            from datetime import datetime as _dt

            created = _dt.strptime(d["created_at"], "%Y-%m-%dT%H:%M:%SZ")

            e.add_field(name="📅 Compte créé", value=discord.utils.format_dt(created.replace(tzinfo=datetime.timezone.utc) if hasattr(datetime, "timezone") else created, style="R"), inline=True)

        await ctx.send(embed=e)

    except requests.exceptions.Timeout:

        await ctx.send(embed=embed_err("GitHub ne répond pas. Réessaie dans quelques instants."))

    except Exception:

        await ctx.send(embed=embed_err("Erreur lors de la récupération du profil GitHub."))

# ─── INVITEINFO ───────────────────────────────────────────────────────────────

@bot.command(name="inviteinfo", aliases=["invite"])

async def inviteinfo_cmd(ctx, url: str = None):

    if not url:

        return await ctx.send(embed=embed_err("Usage : `+inviteinfo <url>`"))

    try:

        invite = await bot.fetch_invite(url, with_counts=True)

        e = discord.Embed(title=f"📨 Invitation — {invite.guild.name if invite.guild else 'Inconnu'}", color=C_BLUE)

        if invite.guild and invite.guild.icon:

            e.set_thumbnail(url=invite.guild.icon.url)

        e.add_field(name="🔗 Code", value=f"`{invite.code}`", inline=True)

        if invite.channel: e.add_field(name="📺 Salon", value=invite.channel.name, inline=True)

        if invite.inviter: e.add_field(name="👤 Créé par", value=str(invite.inviter), inline=True)

        if invite.approximate_member_count is not None:

            e.add_field(name="👥 Membres", value=str(invite.approximate_member_count), inline=True)

        if invite.approximate_presence_count is not None:

            e.add_field(name="🟢 En ligne", value=str(invite.approximate_presence_count), inline=True)

        if invite.expires_at:

            e.add_field(name="⏳ Expire", value=discord.utils.format_dt(invite.expires_at, style="R"), inline=True)

        else:

            e.add_field(name="⏳ Expire", value="Jamais", inline=True)

        if invite.max_uses: e.add_field(name="🔢 Utilisations max", value=str(invite.max_uses), inline=True)

        await ctx.send(embed=e)

    except discord.NotFound:

        await ctx.send(embed=embed_err("Invitation introuvable ou expirée."))

    except Exception:

        await ctx.send(embed=embed_err("Impossible de récupérer les infos de cette invitation."))

# ─── LINKS ────────────────────────────────────────────────────────────────────

@bot.command(name="links", aliases=["lien","liens"])

async def links_cmd(ctx):

    pfx = _prefix_cache.get(ctx.guild.id, DEFAULT_PREFIX) if ctx.guild else DEFAULT_PREFIX

    e = discord.Embed(title="🔗 Liens utiles — ModeraBot", color=C_BLUE)

    e.add_field(name="💬 Support", value=f"[Rejoindre le serveur support]({PREMIUM_LINK})", inline=False)

    e.add_field(name="⭐ Premium", value=f"[Obtenir le Premium]({PREMIUM_LINK})", inline=False)

    e.add_field(name="📖 Aide", value=f"Tape `{pfx}aide` pour voir toutes les commandes", inline=False)

    await ctx.send(embed=e)

# ─── NOROLE ───────────────────────────────────────────────────────────────────

@bot.command(name="norole", aliases=["sansrole"])

async def norole_cmd(ctx):

    if not ctx.author.guild_permissions.manage_guild and str(ctx.author.id) not in OWNER_IDS:

        return await ctx.send(embed=embed_err("Permission refusée."))

    no_role = [m for m in ctx.guild.members if len(m.roles) == 1 and not m.bot]  # seulement @everyone

    if not no_role:

        return await ctx.send(embed=embed_ok("Tous les membres ont au moins un rôle."))

    pages = [no_role[i:i+20] for i in range(0, len(no_role), 20)]

    desc = "\n".join(f"• {m.mention} (`{m.id}`)" for m in pages[0])

    if len(pages) > 1:

        desc += f"\n*...et {len(no_role) - 20} autres*"

    e = discord.Embed(title=f"🚫 Membres sans rôle — {len(no_role)}", description=desc, color=C_ORANGE)

    await ctx.send(embed=e)

# ─── PREVNAMES ────────────────────────────────────────────────────────────────

@bot.command(name="prevnames", aliases=["ancienspseudos","oldnames"])

async def prevnames_cmd(ctx, *, target: str = None):

    if target:

        member = await resolve_member(ctx, target)

        if not member:

            return await ctx.send(embed=embed_err(f"Membre `{target}` introuvable."))

    else:

        member = ctx.author

    history = _prevnames_data.get(str(member.id), [])

    if not history:

        return await ctx.send(embed=embed_warn(f"Aucun ancien pseudo enregistré pour **{member.display_name}**."))

    lines = [f"`{i+1}.` **{h['name']}** — <t:{h['ts']}:R>" for i, h in enumerate(reversed(history[-20:]))]

    e = discord.Embed(title=f"📝 Anciens pseudos de {member.display_name}", description="\n".join(lines), color=C_BLUE)

    e.set_thumbnail(url=member.display_avatar.url)

    await ctx.send(embed=e)

# ─── ROLEINFO ─────────────────────────────────────────────────────────────────

@bot.command(name="roleinfo", aliases=["ri","role"])

async def roleinfo_cmd(ctx, *, target: str = None):

    if not target:

        return await ctx.send(embed=embed_err("Usage : `+roleinfo <nom/ID/@rôle>`"))

    raw = target.strip().strip("<@&>")

    role = (ctx.guild.get_role(int(raw)) if raw.isdigit()

            else discord.utils.find(lambda r: r.name.lower() == raw.lower(), ctx.guild.roles))

    if not role:

        return await ctx.send(embed=embed_err(f"Rôle `{target}` introuvable."))

    e = discord.Embed(title=f"🎭 {role.name}", color=role.color)

    e.add_field(name="🆔 ID", value=f"`{role.id}`", inline=True)

    e.add_field(name="👥 Membres", value=str(len(role.members)), inline=True)

    e.add_field(name="📅 Créé", value=discord.utils.format_dt(role.created_at, style="R"), inline=True)

    e.add_field(name="🎨 Couleur", value=str(role.color), inline=True)

    e.add_field(name="📌 Hoisted", value="Oui" if role.hoist else "Non", inline=True)

    e.add_field(name="🤖 Géré", value="Oui" if role.managed else "Non", inline=True)

    e.add_field(name="🔔 Mentionnable", value="Oui" if role.mentionable else "Non", inline=True)

    e.add_field(name="📊 Position", value=str(role.position), inline=True)

    perms = [p.replace("_", " ").title() for p, v in role.permissions if v]

    if perms:

        e.add_field(name=f"🔑 Permissions ({len(perms)})", value=", ".join(perms[:15]) + ("..." if len(perms) > 15 else ""), inline=False)

    await ctx.send(embed=e)

# ─── ROLEMEMBERS ──────────────────────────────────────────────────────────────

@bot.command(name="rolemembers", aliases=["membresrole","rolemembres"])

async def rolemembers_cmd(ctx, *, target: str = None):

    if not target:

        return await ctx.send(embed=embed_err("Usage : `+rolemembers <nom/ID/@rôle>`"))

    raw = target.strip().strip("<@&>")

    role = (ctx.guild.get_role(int(raw)) if raw.isdigit()

            else discord.utils.find(lambda r: r.name.lower() == raw.lower(), ctx.guild.roles))

    if not role:

        return await ctx.send(embed=embed_err(f"Rôle `{target}` introuvable."))

    members = role.members

    if not members:

        return await ctx.send(embed=embed_warn(f"Aucun membre avec le rôle **{role.name}**."))

    lines = [f"• {m.mention} — `{m.name}`" for m in members[:30]]

    if len(members) > 30:

        lines.append(f"*...et {len(members) - 30} autres*")

    e = discord.Embed(title=f"🎭 Membres avec @{role.name} — {len(members)}", description="\n".join(lines), color=role.color)

    await ctx.send(embed=e)

# ─── SEARCH (commandes) ───────────────────────────────────────────────────────

@bot.command(name="search", aliases=["recherche","searchcmd"])

async def search_cmd(ctx, *, query: str = None):

    if not query:

        return await ctx.send(embed=embed_err("Usage : `+search <mot>`"))

    pfx = _prefix_cache.get(ctx.guild.id, DEFAULT_PREFIX) if ctx.guild else DEFAULT_PREFIX

    all_cmds = [(cmd.name, cmd.aliases) for cmd in bot.commands]

    results = [(name, aliases) for name, aliases in all_cmds

               if query.lower() in name or any(query.lower() in a for a in aliases)]

    if not results:

        return await ctx.send(embed=embed_warn(f"Aucune commande trouvée pour `{query}`."))

    lines = [f"`{pfx}{name}`" + (f" (alias: {', '.join(f'`{pfx}{a}`' for a in aliases[:3])})" if aliases else "") for name, aliases in results[:20]]

    e = discord.Embed(title=f"🔍 Résultats pour « {query} »", description="\n".join(lines), color=C_BLUE)

    e.set_footer(text=f"{len(results)} commande(s) trouvée(s)")

    await ctx.send(embed=e)

# ─── SNIPE ────────────────────────────────────────────────────────────────────

@bot.command(name="snipe")

async def snipe_cmd(ctx):

    data = _snipe_deleted.get(ctx.channel.id)

    if not data:

        return await ctx.send(embed=embed_warn("Aucun message supprimé récemment dans ce salon."))

    e = discord.Embed(description=data["content"] or "*[Pas de texte]*", color=C_RED, timestamp=data["timestamp"])

    e.set_author(name=str(data["author"]), icon_url=data["author"].display_avatar.url)

    e.set_footer(text="Message supprimé")

    if data.get("attachments"):

        e.add_field(name="📎 Pièces jointes", value="\n".join(data["attachments"]), inline=False)

    await ctx.send(embed=e)

# ─── SNIPEDIT ─────────────────────────────────────────────────────────────────

@bot.command(name="snipedit", aliases=["editsnipe","esnipe"])

async def snipedit_cmd(ctx):

    data = _snipe_edited.get(ctx.channel.id)

    if not data:

        return await ctx.send(embed=embed_warn("Aucun message modifié récemment dans ce salon."))

    e = discord.Embed(title="✏️ Message modifié", color=C_ORANGE, timestamp=data["timestamp"])

    e.set_author(name=str(data["author"]), icon_url=data["author"].display_avatar.url)

    e.add_field(name="❌ Avant", value=data["before"][:1000] or "*vide*", inline=False)

    e.add_field(name="✅ Après", value=data["after"][:1000] or "*vide*", inline=False)

    e.set_footer(text="Message modifié")

    await ctx.send(embed=e)

# ─── SPEED ────────────────────────────────────────────────────────────────────

@bot.command(name="speed", aliases=["latence","latency"])

async def speed_cmd(ctx):

    import time as _time

    lat = round(bot.latency * 1000)

    t1 = _time.monotonic()

    msg = await ctx.send("⏱️ Calcul...")

    t2 = _time.monotonic()

    api_ms = round((t2 - t1) * 1000)

    color = C_GREEN if lat < 80 else C_ORANGE if lat < 200 else C_RED

    e = discord.Embed(title="⚡ Speed — ModeraBot", color=color)

    e.add_field(name="📡 Latence WebSocket", value=f"**{lat}ms**", inline=True)

    e.add_field(name="🔁 Latence API", value=f"**{api_ms}ms**", inline=True)

    e.add_field(name="📶 Statut", value="🟢 Excellent" if lat < 80 else "🟡 Correct" if lat < 200 else "🔴 Lent", inline=True)

    await msg.edit(content=None, embed=e)

# ─── STATS (textuelles) ───────────────────────────────────────────────────────

@bot.command(name="stats")

async def stats_cmd(ctx, *, target: str = None):

    if target:

        member = await resolve_member(ctx, target)

        if not member:

            return await ctx.send(embed=embed_err(f"Membre `{target}` introuvable."))

    else:

        member = ctx.author

    gid = str(ctx.guild.id); uid = str(member.id)

    data = _member_stats.get(gid, {}).get(uid, {})

    e = discord.Embed(title=f"📊 Stats de {member.display_name}", color=C_BLUE)

    e.set_thumbnail(url=member.display_avatar.url)

    e.add_field(name="💬 Messages (session)", value=str(data.get("messages", 0)), inline=True)

    e.add_field(name="🔤 Caractères (session)", value=str(data.get("chars", 0)), inline=True)

    if data.get("last_channel"):

        ch = ctx.guild.get_channel(data["last_channel"])

        e.add_field(name="📺 Dernier salon", value=ch.mention if ch else "Inconnu", inline=True)

    e.set_footer(text="Stats depuis le dernier démarrage du bot")

    await ctx.send(embed=e)

# ─── SUPPORT ──────────────────────────────────────────────────────────────────

@bot.command(name="support", aliases=["aide-support","botsupp"])

async def support_cmd(ctx):

    e = discord.Embed(title="🆘 Support — ModeraBot", color=C_BLUE)

    e.add_field(name="💬 Serveur support", value=f"[Rejoindre]({PREMIUM_LINK})", inline=False)

    e.add_field(name="⭐ Premium", value=f"[Obtenir le Premium]({PREMIUM_LINK})", inline=False)

    await ctx.send(embed=e)

# ─── TEMPLATE (embed) ─────────────────────────────────────────────────────────

@bot.command(name="template")

async def template_cmd(ctx):

    e = discord.Embed(title="📋 Template d'embed", color=C_BLUE)

    e.description = "Voici un exemple d'embed que tu peux reproduire avec `+say` ou `+embed`."

    e.add_field(name="Champ 1", value="Valeur du champ 1", inline=True)

    e.add_field(name="Champ 2", value="Valeur du champ 2", inline=True)

    e.add_field(name="Champ long", value="Un champ qui prend toute la largeur.", inline=False)

    e.set_footer(text="Footer de l'embed")

    e.set_author(name="Auteur de l'embed")

    await ctx.send(embed=e)

    await ctx.send(

        "```\nTitre : titre de l'embed\nDescription : texte principal\nCouleur : #5865F2\nChamp : Champ 1 | Valeur 1\nChamp : Champ 2 | Valeur 2\nFooter : texte du footer\n```"

    )

# ─── VANITY ───────────────────────────────────────────────────────────────────

@bot.command(name="vanity", aliases=["vanityu","url"])

async def vanity_cmd(ctx):

    g = ctx.guild

    if not g.vanity_url_code:

        return await ctx.send(embed=embed_warn("Ce serveur n'a pas d'URL personnalisée."))

    try:

        invite = await g.vanity_invite()

        e = discord.Embed(title=f"✨ Vanity URL — {g.name}", color=C_GOLD)

        e.add_field(name="🔗 URL", value=f"discord.gg/{g.vanity_url_code}", inline=True)

        e.add_field(name="👥 Utilisations", value=str(invite.uses) if invite.uses is not None else "N/A", inline=True)

        await ctx.send(embed=e)

    except Exception:

        await ctx.send(embed=embed_err("Impossible de récupérer les infos de la vanity URL."))

# ─── VC (stats vocales) ────────────────────────────────────────────────────────

@bot.command(name="vc", aliases=["vocal","voice"])

async def vc_cmd(ctx):

    g = ctx.guild

    vc_channels = g.voice_channels

    total_members = sum(len(vc.members) for vc in vc_channels)

    occupied = [(vc, vc.members) for vc in vc_channels if vc.members]

    e = discord.Embed(title=f"🔊 Stats vocales — {g.name}", color=C_BLUE)

    e.add_field(name="📡 Salons vocaux", value=str(len(vc_channels)), inline=True)

    e.add_field(name="👥 Membres en vocal", value=str(total_members), inline=True)

    e.add_field(name="🟢 Salons occupés", value=str(len(occupied)), inline=True)

    if occupied:

        lines = [f"• **{vc.name}** — {len(members)} membre(s)" for vc, members in occupied[:10]]

        e.add_field(name="🎙️ Salons actifs", value="\n".join(lines), inline=False)

    await ctx.send(embed=e)

# ─── VERSION ──────────────────────────────────────────────────────────────────

@bot.command(name="version", aliases=["ver","v"])

async def version_cmd(ctx):

    e = discord.Embed(title="📦 ModeraBot — Version", color=C_BLUE)

    e.add_field(name="🤖 Version du bot", value="**v4.0**", inline=True)

    e.add_field(name="📚 discord.py", value=f"**{discord.__version__}**", inline=True)

    e.add_field(name="🐍 Python", value="**3.10+**", inline=True)

    e.add_field(name="✨ Nouveautés v4", value="• Zéro slash command\n• Auto-correction typos\n• Prefix custom par serveur\n• Tickets boutons/select\n• Modals pour tout", inline=False)

    await ctx.send(embed=e)

# ─── VOTE ─────────────────────────────────────────────────────────────────────

@bot.command(name="vote", aliases=["voter","topgg"])

async def vote_cmd(ctx):

    e = discord.Embed(title="🗳️ Voter pour ModeraBot", color=C_GOLD)

    e.description = "Ton vote nous aide à grandir ! Merci 💙"

    e.add_field(name="📊 Top.gg", value="[Voter ici](https://top.gg)", inline=False)

    e.add_field(name="⭐ Premium", value=f"[Obtenir le Premium]({PREMIUM_LINK})", inline=False)

    await ctx.send(embed=e)

# ══════════════════════════════════════════════════════════════════════════════

# GESTION OWNERS (par serveur)

# ══════════════════════════════════════════════════════════════════════════════

_server_owners = {}  # guild_id → set of user_id (str)

def is_server_owner(guild_id, user_id):

    return str(user_id) in _server_owners.get(str(guild_id), set()) or str(user_id) in OWNER_IDS

@bot.command(name="owner", aliases=["addowner"])

async def owner_cmd(ctx, *, target: str = None):

    if not (ctx.author.guild_permissions.administrator or str(ctx.author.id) in OWNER_IDS):

        return await ctx.send(embed=embed_err("Permission administrateur requise."))

    if not target:

        return await ctx.send(embed=embed_err("Usage : `+owner <@membre/nom/ID>`"))

    member = await resolve_member(ctx, target)

    if not member:

        return await ctx.send(embed=embed_err(f"Membre `{target}` introuvable."))

    gid = str(ctx.guild.id)

    if gid not in _server_owners: _server_owners[gid] = set()

    _server_owners[gid].add(str(member.id))

    e = discord.Embed(description=f"✅ **{member.display_name}** est maintenant Owner sur ce serveur.", color=C_GREEN)

    e.set_thumbnail(url=member.display_avatar.url)

    await ctx.send(embed=e)

@bot.command(name="unowner", aliases=["removeowner"])

async def unowner_cmd(ctx, *, target: str = None):

    if not (ctx.author.guild_permissions.administrator or str(ctx.author.id) in OWNER_IDS):

        return await ctx.send(embed=embed_err("Permission administrateur requise."))

    if not target:

        return await ctx.send(embed=embed_err("Usage : `+unowner <@membre/nom/ID>`"))

    member = await resolve_member(ctx, target)

    if not member:

        return await ctx.send(embed=embed_err(f"Membre `{target}` introuvable."))

    gid = str(ctx.guild.id)

    _server_owners.get(gid, set()).discard(str(member.id))

    await ctx.send(embed=discord.Embed(description=f"✅ **{member.display_name}** n'est plus Owner.", color=C_GREEN))

@bot.command(name="owners", aliases=["listowners"])

async def owners_cmd(ctx):

    gid = str(ctx.guild.id)

    ids = _server_owners.get(gid, set())

    if not ids:

        return await ctx.send(embed=embed_warn("Aucun owner configuré sur ce serveur."))

    lines = []

    for uid in ids:

        m = ctx.guild.get_member(int(uid))

        lines.append(f"• {m.mention if m else f'`{uid}`'}")

    e = discord.Embed(title=f"👑 Owners — {ctx.guild.name}", description="\n".join(lines), color=C_GOLD)

    e.set_footer(text=f"{len(ids)} owner(s)")

    await ctx.send(embed=e)

@bot.command(name="clearowners")

async def clearowners_cmd(ctx):

    if not (ctx.author.guild_permissions.administrator or str(ctx.author.id) in OWNER_IDS):

        return await ctx.send(embed=embed_err("Permission administrateur requise."))

    gid = str(ctx.guild.id)

    count = len(_server_owners.get(gid, set()))

    _server_owners[gid] = set()

    await ctx.send(embed=discord.Embed(description=f"🗑️ **{count}** owner(s) supprimé(s).", color=C_ORANGE))

@bot.command(name="reset")

async def reset_cmd(ctx):

    if not (ctx.author.guild_permissions.administrator or str(ctx.author.id) in OWNER_IDS):

        return await ctx.send(embed=embed_err("Permission administrateur requise."))

    gid = str(ctx.guild.id); sgid = str(gid)

    # Effacer toutes les données du serveur dans les fichiers JSON

    for key, path in FILES.items():

        try:

            data = jload(path)

            if sgid in data:

                del data[sgid]

                jsave(path, data)

        except: pass

    # Effacer en mémoire

    _server_owners.pop(sgid, None)

    _prefix_cache.pop(ctx.guild.id, None)

    _save_prefixes()

    _member_stats.pop(sgid, None)

    e = discord.Embed(title="🔄 Réinitialisation complète", description="Toutes les données de ce serveur ont été supprimées.", color=C_RED)

    e.set_footer(text=f"Effectué par {ctx.author}")

    await ctx.send(embed=e)

# ══════════════════════════════════════════════════════════════════════════════

# SYSTÈME DE LOGS AVANCÉ

# ══════════════════════════════════════════════════════════════════════════════

FILES["logs_cfg"] = "logs_config.json"

if not os.path.exists("logs_config.json"):

    with open("logs_config.json", "w") as _f: _f.write("{}")

LOG_TYPES = ["mod", "msg", "role", "channel", "voc", "boost", "flux", "ticket"]

# ══════════════════════════════════════════════════════════════════════════════

# SYSTÈME DE LOGS — CONFIG & AFFICHAGE

# ══════════════════════════════════════════════════════════════════════════════

LOGS_TYPES = [

    ("msg",     "Logs messages",         "📨", "logs-messages"),

    ("voc",     "Logs voice",            "🔊", "logs-voice"),

    ("role",    "Logs rôles",            "🎭", "logs-roles"),

    ("mod",     "Logs mods",             "🛡️", "logs-moderation"),

    ("channel", "Logs salons",           "📺", "logs-channel"),

    ("ticket",  "Logs ticket",           "🎫", "logs-ticket"),

    ("boost",   "Logs boosts",           "🚀", "logs-boosts"),

    ("flux",    "Logs Flux (Join/Leave)", "📡", "logs-flux"),

]

LOGS_CAT_NAME = "📂・Logs ModeraBot"

LOGS_CH_PREFIX = "📂・"

def get_logs_cfg(guild_id):

    return jload(FILES["logs_cfg"]).get(str(guild_id), {})

def save_logs_cfg(guild_id, data):

    all_data = jload(FILES["logs_cfg"])

    all_data[str(guild_id)] = data

    jsave(FILES["logs_cfg"], all_data)

def build_logs_embed(guild_id, guild=None):

    cfg = get_logs_cfg(guild_id)

    e = discord.Embed(

        title=f"Logs de ModeraBot{' | ' + guild.name if guild else ''}",

        color=0x2B2D31

    )

    if guild and guild.icon:

        e.set_thumbnail(url=guild.icon.url)

    for key, label, emoji, ch_name in LOGS_TYPES:

        entry = cfg.get(key, {})

        full_ch_name = LOGS_CH_PREFIX + ch_name

        if entry.get("enabled") and entry.get("channel"):

            val = f"✅📁 • `{full_ch_name}`"

        else:

            val = f"❌📁 • `{full_ch_name}`"

        e.add_field(name=f"**{label}**", value=val, inline=False)

    e.set_footer(text="© ModeraBot")

    return e

# ─── Buttons ──────────────────────────────────────────────────────────────────

class LogsView(discord.ui.View):

    def __init__(self, guild):

        super().__init__(timeout=None)

        self.guild = guild

    @discord.ui.button(label="🗑️", style=discord.ButtonStyle.danger, row=0)

    async def btn_delete(self, interaction: discord.Interaction, button: discord.ui.Button):

        """Désactive tous les logs du serveur."""

        if not interaction.user.guild_permissions.administrator and str(interaction.user.id) not in OWNER_IDS:

            return await interaction.response.send_message(embed=embed_err("Permission refusée."), ephemeral=True)

        save_logs_cfg(self.guild.id, {})

        await interaction.response.edit_message(embed=build_logs_embed(self.guild.id, self.guild), view=self)

        await interaction.followup.send(embed=discord.Embed(description="🗑️ Tous les logs ont été désactivés.", color=C_RED), ephemeral=True)

    @discord.ui.button(label="Auto", emoji="📊", style=discord.ButtonStyle.secondary, row=0)

    async def btn_auto(self, interaction: discord.Interaction, button: discord.ui.Button):

        """Crée automatiquement la catégorie + tous les salons de logs."""

        if not interaction.user.guild_permissions.administrator and str(interaction.user.id) not in OWNER_IDS:

            return await interaction.response.send_message(embed=embed_err("Permission refusée."), ephemeral=True)

        await interaction.response.defer(ephemeral=True)

        guild = self.guild

        cfg = get_logs_cfg(guild.id)

        # Créer ou récupérer la catégorie

        cat_name = LOGS_CAT_NAME

        category = discord.utils.get(guild.categories, name=LOGS_CAT_NAME)

        if not category:

            try:

                category = await guild.create_category(

                    cat_name,

                    overwrites={guild.default_role: discord.PermissionOverwrite(view_channel=False)}

                )

            except Exception as ex:

                return await interaction.followup.send(embed=embed_err(f"Impossible de créer la catégorie : {ex}"), ephemeral=True)

        created = []

        for key, label, emoji, ch_name in LOGS_TYPES:

            # Créer ou récupérer le salon

            full_name = LOGS_CH_PREFIX + ch_name

            ch = discord.utils.get(guild.text_channels, name=full_name)

            if not ch:

                try:

                    ch = await guild.create_text_channel(

                        full_name,

                        category=category,

                        overwrites={guild.default_role: discord.PermissionOverwrite(view_channel=False)}

                    )

                    created.append(full_name)

                except Exception:

                    continue

            cfg.setdefault(key, {})

            cfg[key]["enabled"] = True

            cfg[key]["channel"] = ch.id

        save_logs_cfg(guild.id, cfg)

        await interaction.message.edit(embed=build_logs_embed(guild.id, guild), view=self)

        nb = len(created)

        await interaction.followup.send(

            embed=discord.Embed(

                description=f"✅ Configuration automatique terminée !\n**{nb}** salon(s) créé(s) dans `{cat_name}`.",

                color=C_GREEN

            ), ephemeral=True

        )

    @discord.ui.button(label="Clean", emoji="📁", style=discord.ButtonStyle.success, row=0)

    async def btn_clean(self, interaction: discord.Interaction, button: discord.ui.Button):

        """Supprime tous les salons de logs créés par le bot."""

        if not interaction.user.guild_permissions.administrator and str(interaction.user.id) not in OWNER_IDS:

            return await interaction.response.send_message(embed=embed_err("Permission refusée."), ephemeral=True)

        await interaction.response.defer(ephemeral=True)

        guild = self.guild

        deleted = 0

        for key, label, emoji, ch_name in LOGS_TYPES:

            full_name = LOGS_CH_PREFIX + ch_name

            ch = discord.utils.get(guild.text_channels, name=full_name)

            if ch:

                try:

                    await ch.delete(reason="Clean logs ModeraBot")

                    deleted += 1

                except: pass

        # Supprimer catégorie si vide

        cat = discord.utils.get(guild.categories, name=LOGS_CAT_NAME)

        if cat and len(cat.channels) == 0:

            try: await cat.delete()

            except: pass

        save_logs_cfg(guild.id, {})

        await interaction.message.edit(embed=build_logs_embed(guild.id, guild), view=self)

        await interaction.followup.send(

            embed=discord.Embed(description=f"📁 **{deleted}** salon(s) de logs supprimé(s).", color=C_ORANGE),

            ephemeral=True

        )

@bot.command(name="logs")

async def logs_cmd(ctx):

    if not (ctx.author.guild_permissions.administrator or str(ctx.author.id) in OWNER_IDS):

        return await ctx.send(embed=embed_err("Permission administrateur requise."))

    await ctx.send(embed=build_logs_embed(ctx.guild.id, ctx.guild), view=LogsView(ctx.guild))

async def _log_type_cmd(ctx, log_type: str, state: str, channel: discord.TextChannel = None):

    if not (ctx.author.guild_permissions.administrator or str(ctx.author.id) in OWNER_IDS):

        return await ctx.send(embed=embed_err("Permission administrateur requise."))

    state = state.lower().strip() if state else ""

    if state not in ("on", "off", "1", "0", "oui", "non"):

        pfx = _prefix_cache.get(ctx.guild.id, DEFAULT_PREFIX)

        label = next((t[1] for t in LOGS_TYPES if t[0] == log_type), log_type)

        return await ctx.send(embed=embed_err(f"Usage : `{pfx}{log_type}log <on/off> [#salon]`"))

    enabled = state in ("on", "1", "oui")

    cfg = get_logs_cfg(ctx.guild.id)

    cfg.setdefault(log_type, {})

    cfg[log_type]["enabled"] = enabled

    if enabled and channel:

        cfg[log_type]["channel"] = channel.id

    elif enabled and not cfg[log_type].get("channel"):

        cfg[log_type]["channel"] = ctx.channel.id

    save_logs_cfg(ctx.guild.id, cfg)

    ch_id = cfg[log_type].get("channel")

    label = next((t[1] for t in LOGS_TYPES if t[0] == log_type), log_type)

    status = f"✅ Activé → <#{ch_id}>" if enabled else "❌ Désactivé"

    await ctx.send(embed=discord.Embed(description=f"**{label}** : {status}", color=C_GREEN if enabled else C_RED))

@bot.command(name="modlog")

async def modlog_cmd(ctx, state: str = None, channel: discord.TextChannel = None):

    await _log_type_cmd(ctx, "mod", state, channel)

@bot.command(name="msglog")

async def msglog_cmd(ctx, state: str = None, channel: discord.TextChannel = None):

    await _log_type_cmd(ctx, "msg", state, channel)

@bot.command(name="rolelog")

async def rolelog_cmd(ctx, state: str = None, channel: discord.TextChannel = None):

    await _log_type_cmd(ctx, "role", state, channel)

@bot.command(name="channellog")

async def channellog_cmd(ctx, state: str = None, channel: discord.TextChannel = None):

    await _log_type_cmd(ctx, "channel", state, channel)

@bot.command(name="voclog", aliases=["voicelog"])

async def voclog_cmd(ctx, state: str = None, channel: discord.TextChannel = None):

    await _log_type_cmd(ctx, "voc", state, channel)

@bot.command(name="boostlog")

async def boostlog_cmd(ctx, state: str = None, channel: discord.TextChannel = None):

    await _log_type_cmd(ctx, "boost", state, channel)

@bot.command(name="fluxlog")

async def fluxlog_cmd(ctx, state: str = None, channel: discord.TextChannel = None):

    await _log_type_cmd(ctx, "flux", state, channel)

@bot.command(name="ticketlog")

async def ticketlog_cmd(ctx, state: str = None, channel: discord.TextChannel = None):

    await _log_type_cmd(ctx, "ticket", state, channel)

# Helper: envoyer un log dans le bon salon

_log_locks = {}     # channel_id -> asyncio.Lock
_log_last  = {}     # channel_id -> horodatage du dernier envoi
_LOG_GAP   = 1.05   # secondes entre deux logs d'un meme salon (limite Discord : 5/5s)


async def send_log(guild, log_type: str, embed: discord.Embed):

    if not guild: return

    cfg = get_logs_cfg(guild.id).get(log_type, {})

    if not cfg.get("enabled"): return

    ch = _as_text_channel(guild, cfg.get("channel", 0))

    if not ch: return

    # Un verrou par salon : les rafales sont etalees au lieu de partir d'un coup
    lock = _log_locks.get(ch.id)

    if lock is None:

        lock = _log_locks[ch.id] = asyncio.Lock()

    async with lock:

        attente = _LOG_GAP - (_time.monotonic() - _log_last.get(ch.id, 0))

        if attente > 0:

            await asyncio.sleep(attente)

        try:

            await ch.send(embed=embed, allowed_mentions=MENTIONS_LOGS)

        except discord.HTTPException:

            pass

        except Exception:

            pass

        _log_last[ch.id] = _time.monotonic()

# ══════════════════════════════════════════════════════════════════════════════

# COMMANDES FUN

# ══════════════════════════════════════════════════════════════════════════════

# COMMANDES FUN

# ══════════════════════════════════════════════════════════════════════════════

import random as _random

@bot.command(name="8ball", aliases=["boule","magic8"])

async def eightball_cmd(ctx, *, question: str = None):

    if not question:

        return await ctx.send(embed=embed_err("Usage : `+8ball <question>`"))

    reponses = [

        "✅ Oui, absolument !", "✅ C'est certain.", "✅ Sans aucun doute.",

        "✅ Oui, définitivement.", "✅ Tu peux compter là-dessus.",

        "🟡 C'est possible.", "🟡 Hmm, difficile à dire.", "🟡 Réessaie plus tard.",

        "🟡 Je préfère ne pas répondre.", "🟡 Concentre-toi et redemande.",

        "❌ Non, pas du tout.", "❌ Ma réponse est non.", "❌ Très peu probable.",

        "❌ Mes sources disent non.", "❌ N'y compte pas."

    ]

    rep = _random.choice(reponses)

    e = discord.Embed(title="🎱 Magic 8-Ball", color=C_BLUE)

    e.add_field(name="❓ Question", value=question, inline=False)

    e.add_field(name="🔮 Réponse", value=f"**{rep}**", inline=False)

    await ctx.send(embed=e)

@bot.command(name="roll", aliases=["dice","de"])

async def roll_cmd(ctx, sides: int = 6):

    sides = max(2, min(100, sides))

    result = _random.randint(1, sides)

    e = discord.Embed(title=f"🎲 Dé à {sides} faces", color=C_BLUE)

    e.add_field(name="Résultat", value=f"**{result}**", inline=True)

    await ctx.send(embed=e)

@bot.command(name="coinflip", aliases=["pile","face","coin"])

async def coinflip_cmd(ctx, *, pari: str = None):

    result = _random.choice(["🪙 Pile", "🪙 Face"])

    e = discord.Embed(title="🪙 Pile ou Face", color=C_GOLD)

    e.add_field(name="Résultat", value=f"**{result}**", inline=True)

    if pari:

        gagne = pari.lower() in result.lower()

        e.add_field(name="🎯 Ton pari", value=pari, inline=True)

        e.add_field(name="Résultat", value="✅ Gagné !" if gagne else "❌ Perdu !", inline=True)

    await ctx.send(embed=e)

@bot.command(name="rps", aliases=["chifoumi","pfc"])

async def rps_cmd(ctx, choix: str = None):

    opts = {"pierre": "🪨", "papier": "📄", "ciseaux": "✂️", "rock": "🪨", "paper": "📄", "scissors": "✂️"}

    if not choix or choix.lower() not in opts:

        return await ctx.send(embed=embed_err("Usage : `+rps <pierre/papier/ciseaux>`"))

    bot_choix = _random.choice(["pierre", "papier", "ciseaux"])

    joueur = choix.lower() if choix.lower() in ("pierre","papier","ciseaux") else {"rock":"pierre","paper":"papier","scissors":"ciseaux"}[choix.lower()]

    wins = {"pierre": "ciseaux", "papier": "pierre", "ciseaux": "papier"}

    if joueur == bot_choix: result = "🟡 Égalité !"

    elif wins[joueur] == bot_choix: result = "✅ Tu gagnes !"

    else: result = "❌ Tu perds !"

    e = discord.Embed(title="✊ Pierre-Papier-Ciseaux", color=C_BLUE)

    e.add_field(name="Tu as joué", value=f"{opts.get(joueur, joueur)} {joueur}", inline=True)

    e.add_field(name="Le bot joue", value=f"{opts.get(bot_choix, bot_choix)} {bot_choix}", inline=True)

    e.add_field(name="Résultat", value=f"**{result}**", inline=False)

    await ctx.send(embed=e)

@bot.command(name="rate")

async def rate_cmd(ctx, *, text: str = None):

    if not text:

        return await ctx.send(embed=embed_err("Usage : `+rate <texte>`"))

    score = _random.randint(0, 10)

    bar = "█" * score + "░" * (10 - score)

    e = discord.Embed(title="⭐ Notation", color=C_GOLD)

    e.add_field(name="📝 Sujet", value=text, inline=False)

    e.add_field(name="🏆 Score", value=f"**{score}/10** `{bar}`", inline=False)

    await ctx.send(embed=e)

@bot.command(name="gay", aliases=["gayrate"])

async def gay_cmd(ctx, *, target: str = None):

    member = await resolve_member(ctx, target) if target else ctx.author

    if not member: member = ctx.author

    pct = _random.randint(0, 100)

    bar = "🌈" * (pct // 10) + "⬜" * (10 - pct // 10)

    e = discord.Embed(title="🌈 Gay-o-mètre", color=0xFF69B4)

    e.set_thumbnail(url=member.display_avatar.url)

    e.add_field(name=f"📊 {member.display_name} est gay à...", value=f"**{pct}%** `{bar}`", inline=False)

    await ctx.send(embed=e)

@bot.command(name="hack")

async def hack_cmd(ctx, *, target: str = None):

    if not target:

        return await ctx.send(embed=embed_err("Usage : `+hack <@membre/nom/ID>`"))

    member = await resolve_member(ctx, target)

    name = member.display_name if member else target

    steps = [

        "🔍 Recherche de l'adresse IP...",

        "💻 Connexion au serveur distant...",

        "🔓 Contournement du pare-feu...",

        "📁 Accès aux fichiers personnels...",

        f"✅ **{name}** a été hacké ! 😈\n*(C'est une blague, aucun hack réel n'a eu lieu)*"

    ]

    msg = await ctx.send(f"```{steps[0]}```")

    for i, step in enumerate(steps[1:], 1):

        await asyncio.sleep(1.2)

        await msg.edit(content=f"```{step}```" if i < len(steps)-1 else step)

@bot.command(name="ratio")

async def ratio_cmd(ctx, *, target: str = None):

    if not target:

        return await ctx.send(embed=embed_err("Usage : `+ratio <@membre/nom>`"))

    member = await resolve_member(ctx, target)

    name = member.mention if member else f"**{target}**"

    await ctx.send(f"📊 Ratio {name} — {ctx.author.mention} a plus de likes !")

@bot.command(name="oh")

async def oh_cmd(ctx, *, target: str = None):

    if not target:

        return await ctx.send(embed=embed_err("Usage : `+oh <@membre/nom/ID>`"))

    member = await resolve_member(ctx, target)

    name = member.mention if member else f"**{target}**"

    await ctx.send(f"😲 Oh non... {name} est un **MENTEUR** ! 🤥")

@bot.command(name="randomuser", aliases=["randuser","randomm"])

async def randomuser_cmd(ctx):

    humans = [m for m in ctx.guild.members if not m.bot]

    if not humans:

        return await ctx.send(embed=embed_warn("Aucun membre humain trouvé."))

    member = _random.choice(humans)

    e = discord.Embed(title="🎲 Membre aléatoire !", color=C_BLUE)

    e.set_thumbnail(url=member.display_avatar.url)

    e.add_field(name="👤 Membre", value=member.mention, inline=True)

    e.add_field(name="🆔 ID", value=f"`{member.id}`", inline=True)

    e.add_field(name="📅 Rejoint", value=discord.utils.format_dt(member.joined_at, style="R") if member.joined_at else "Inconnu", inline=True)

    await ctx.send(embed=e)

@bot.command(name="randomavatar", aliases=["randav"])

async def randomavatar_cmd(ctx):

    humans = [m for m in ctx.guild.members if not m.bot]

    if not humans:

        return await ctx.send(embed=embed_warn("Aucun membre trouvé."))

    member = _random.choice(humans)

    e = discord.Embed(title=f"🖼️ Avatar aléatoire — {member.display_name}", color=C_BLUE)

    e.set_image(url=member.display_avatar.url)

    e.set_footer(text=f"ID : {member.id}")

    await ctx.send(embed=e)

@bot.command(name="randombanner", aliases=["randbanner"])

async def randombanner_cmd(ctx):

    humans = [m for m in ctx.guild.members if not m.bot]

    _random.shuffle(humans)

    for member in humans[:20]:

        try:

            fetched = await bot.fetch_user(member.id)

            if fetched.banner:

                e = discord.Embed(title=f"🎨 Bannière aléatoire — {member.display_name}", color=C_BLUE)

                e.set_image(url=fetched.banner.url)

                return await ctx.send(embed=e)

        except: pass

    await ctx.send(embed=embed_warn("Aucun membre avec une bannière trouvé parmi les 20 premiers sondés."))

@bot.command(name="hug", aliases=["calin"])

async def hug_cmd(ctx, *, target: str = None):

    gifs = [

        "https://media.tenor.com/I9q5Sc9ZAUAAAAAC/hug-anime.gif",

        "https://media.tenor.com/3fBM6NJPZWMAAAAC/anime-hug.gif",

        "https://media.tenor.com/6jOjLqXZbogAAAAC/hug.gif",

    ]

    member = await resolve_member(ctx, target) if target else None

    desc = f"{ctx.author.mention} fait un câlin à {member.mention} 🤗" if member else f"{ctx.author.mention} a besoin d'un câlin 🤗"

    e = discord.Embed(description=desc, color=C_BLUE)

    e.set_image(url=_random.choice(gifs))

    await ctx.send(embed=e)

@bot.command(name="pat", aliases=["caress"])

async def pat_cmd(ctx, *, target: str = None):

    gifs = [

        "https://media.tenor.com/NUbU5YeK-KMAAAAC/anime-pat.gif",

        "https://media.tenor.com/hpCFo8TmjEQAAAAC/pat-anime.gif",

        "https://media.tenor.com/GBnLMBXg0RQAAAAC/headpat-anime.gif",

    ]

    member = await resolve_member(ctx, target) if target else None

    desc = f"{ctx.author.mention} tapote la tête de {member.mention} 👋" if member else f"{ctx.author.mention} se tapote la tête 👋"

    e = discord.Embed(description=desc, color=C_BLUE)

    e.set_image(url=_random.choice(gifs))

    await ctx.send(embed=e)

@bot.command(name="slap", aliases=["gifle","frappe"])

async def slap_cmd(ctx, *, target: str = None):

    gifs = [

        "https://media.tenor.com/0LMsS_JzgA8AAAAC/anime-slap.gif",

        "https://media.tenor.com/h7QSYR1XRGEAAAAC/slap-anime.gif",

        "https://media.tenor.com/iK5Lb1tKECEAAAAC/slap.gif",

    ]

    member = await resolve_member(ctx, target) if target else None

    desc = f"{ctx.author.mention} gifle {member.mention} 👋💥" if member else f"{ctx.author.mention} gifle dans le vide 👋"

    e = discord.Embed(description=desc, color=C_RED)

    e.set_image(url=_random.choice(gifs))

    await ctx.send(embed=e)

@bot.command(name="kiss", aliases=["bisou"])

async def kiss_cmd(ctx, *, target: str = None):

    gifs = [

        "https://media.tenor.com/wB0E5-HZO_cAAAAC/anime-kiss.gif",

        "https://media.tenor.com/fQ4KfW8nrIIAAAAC/kiss-anime.gif",

        "https://media.tenor.com/JdWpkzVv3Z8AAAAC/kiss.gif",

    ]

    member = await resolve_member(ctx, target) if target else None

    desc = f"{ctx.author.mention} fait un bisou à {member.mention} 💋" if member else f"{ctx.author.mention} envoie un bisou 💋"

    e = discord.Embed(description=desc, color=0xFF69B4)

    e.set_image(url=_random.choice(gifs))

    await ctx.send(embed=e)

@bot.command(name="cry", aliases=["pleur"])

async def cry_cmd(ctx, *, target: str = None):

    gifs = [

        "https://media.tenor.com/x2u6TulBDl4AAAAC/anime-cry.gif",

        "https://media.tenor.com/RNpPxkPLn6UAAAAC/cry-anime.gif",

        "https://media.tenor.com/ztEVSRh2xnAAAAAC/sad-anime.gif",

    ]

    member = await resolve_member(ctx, target) if target else None

    desc = f"{member.mention} fait pleurer {ctx.author.mention} 😢" if member else f"{ctx.author.mention} pleure 😢"

    e = discord.Embed(description=desc, color=C_BLUE)

    e.set_image(url=_random.choice(gifs))

    await ctx.send(embed=e)

@bot.command(name="smile", aliases=["sourire"])

async def smile_cmd(ctx):

    gifs = [

        "https://media.tenor.com/KJfGEp2mF3MAAAAC/anime-smile.gif",

        "https://media.tenor.com/5YIEUFGbblgAAAAC/smile-anime.gif",

    ]

    e = discord.Embed(description=f"{ctx.author.mention} sourit chaleureusement 😊", color=C_GOLD)

    e.set_image(url=_random.choice(gifs))

    await ctx.send(embed=e)

@bot.command(name="cat", aliases=["chat","minou"])

async def cat_cmd(ctx):

    try:

        r = requests.get("https://api.thecatapi.com/v1/images/search", timeout=5)

        url = r.json()[0]["url"]

    except:

        url = "https://cataas.com/cat"

    e = discord.Embed(title="🐱 Miaou !", color=C_ORANGE)

    e.set_image(url=url)

    await ctx.send(embed=e)

@bot.command(name="dog", aliases=["chien","woof"])

async def dog_cmd(ctx):

    try:

        r = requests.get("https://dog.ceo/api/breeds/image/random", timeout=5)

        url = r.json()["message"]

    except:

        url = "https://place.dog/400/300"

    e = discord.Embed(title="🐶 Wouf !", color=C_ORANGE)

    e.set_image(url=url)

    await ctx.send(embed=e)

@bot.command(name="anime")

async def anime_cmd(ctx, *, title: str = None):

    if not title:

        return await ctx.send(embed=embed_err("Usage : `+anime <titre>`"))

    try:

        r = requests.get(f"https://api.jikan.moe/v4/anime?q={requests.utils.quote(title)}&limit=1", timeout=8)

        results = r.json().get("data", [])

        if not results:

            return await ctx.send(embed=embed_warn(f"Aucun anime trouvé pour `{title}`."))

        a = results[0]

        e = discord.Embed(title=a.get("title", title), url=a.get("url", ""), color=C_BLUE)

        if a.get("images", {}).get("jpg", {}).get("image_url"):

            e.set_thumbnail(url=a["images"]["jpg"]["image_url"])

        e.add_field(name="📺 Type", value=a.get("type", "?"), inline=True)

        e.add_field(name="📊 Score", value=str(a.get("score", "?")), inline=True)

        e.add_field(name="📅 Statut", value=a.get("status", "?"), inline=True)

        e.add_field(name="🎬 Épisodes", value=str(a.get("episodes", "?")), inline=True)

        e.add_field(name="📅 Diffusion", value=a.get("aired", {}).get("string", "?")[:50], inline=True)

        synopsis = a.get("synopsis", "Pas de synopsis.")

        if synopsis: e.add_field(name="📝 Synopsis", value=synopsis[:300] + ("..." if len(synopsis) > 300 else ""), inline=False)

        genres = ", ".join(g["name"] for g in a.get("genres", [])[:5])

        if genres: e.add_field(name="🏷️ Genres", value=genres, inline=False)

        await ctx.send(embed=e)

    except Exception:

        await ctx.send(embed=embed_err("Erreur lors de la recherche. Réessaie."))

@bot.command(name="define", aliases=["definition","def"])

async def define_cmd(ctx, *, word: str = None):

    if not word:

        return await ctx.send(embed=embed_err("Usage : `+define <mot>`"))

    try:

        r = requests.get(f"https://api.dictionaryapi.dev/api/v2/entries/fr/{requests.utils.quote(word)}", timeout=6)

        if r.status_code != 200:

            # Fallback anglais

            r = requests.get(f"https://api.dictionaryapi.dev/api/v2/entries/en/{requests.utils.quote(word)}", timeout=6)

        if r.status_code != 200:

            return await ctx.send(embed=embed_warn(f"Aucune définition trouvée pour `{word}`."))

        data = r.json()[0]

        e = discord.Embed(title=f"📖 {data.get('word', word)}", color=C_BLUE)

        meanings = data.get("meanings", [])

        for m in meanings[:2]:

            defs = m.get("definitions", [])[:2]

            for d in defs:

                e.add_field(name=f"*{m.get('partOfSpeech', '')}*", value=d.get("definition", "?")[:300], inline=False)

        if data.get("phonetics"):

            ph = next((p.get("text") for p in data["phonetics"] if p.get("text")), None)

            if ph: e.set_footer(text=f"Phonétique : {ph}")

        await ctx.send(embed=e)

    except Exception:

        await ctx.send(embed=embed_err("Erreur lors de la recherche de définition."))

@bot.command(name="translate", aliases=["trad","traduction"])

async def translate_cmd(ctx, lang: str = None, *, text: str = None):

    if not lang or not text:

        return await ctx.send(embed=embed_err("Usage : `+translate <langue> <texte>`\nEx: `+translate en Bonjour le monde`"))

    try:

        r = requests.get(

            f"https://api.mymemory.translated.net/get?q={requests.utils.quote(text)}&langpair=auto|{lang}",

            timeout=8

        )

        result = r.json()

        translated = result.get("responseData", {}).get("translatedText", "")

        if not translated or translated == text:

            return await ctx.send(embed=embed_warn("Traduction impossible ou langue invalide."))

        e = discord.Embed(title="🌐 Traduction", color=C_BLUE)

        e.add_field(name="📥 Original", value=text[:500], inline=False)

        e.add_field(name=f"📤 → `{lang}`", value=translated[:500], inline=False)

        await ctx.send(embed=e)

    except Exception:

        await ctx.send(embed=embed_err("Erreur lors de la traduction."))

@bot.command(name="binary", aliases=["bin","binaire"])

async def binary_cmd(ctx, *, text: str = None):

    if not text:

        return await ctx.send(embed=embed_err("Usage : `+binary <texte>` ou `+binary <binaire>`"))

    # Détecter si c'est du binaire (que des 0, 1 et espaces)

    clean = text.replace(" ", "")

    if all(c in "01" for c in clean) and len(clean) % 8 == 0:

        # Décoder

        try:

            decoded = "".join(chr(int(clean[i:i+8], 2)) for i in range(0, len(clean), 8))

            e = discord.Embed(title="💻 Binaire → Texte", color=C_BLUE)

            e.add_field(name="📥 Binaire", value=f"`{text[:200]}`", inline=False)

            e.add_field(name="📤 Texte", value=decoded[:500], inline=False)

        except:

            e = discord.Embed(description="❌ Binaire invalide.", color=C_RED)

    else:

        # Encoder

        encoded = " ".join(format(ord(c), "08b") for c in text[:50])

        e = discord.Embed(title="💻 Texte → Binaire", color=C_BLUE)

        e.add_field(name="📥 Texte", value=text[:200], inline=False)

        e.add_field(name="📤 Binaire", value=f"`{encoded}`"[:1000], inline=False)

    await ctx.send(embed=e)

@bot.command(name="ascii", aliases=["asciiart"])

async def ascii_cmd(ctx, *, text: str = None):

    if not text:

        return await ctx.send(embed=embed_err("Usage : `+ascii <texte>`"))

    if len(text) > 10:

        return await ctx.send(embed=embed_warn("Maximum 10 caractères pour l'ASCII art."))

    font = {

        'A':'###\n# #\n###\n# #\n# #','B':'## \n# #\n## \n# #\n## ',

        'C':'###\n#  \n#  \n#  \n###','D':'## \n# #\n# #\n# #\n## ',

        'E':'###\n#  \n###\n#  \n###','F':'###\n#  \n###\n#  \n#  ',

        'G':'###\n#  \n# #\n# #\n###','H':'# #\n# #\n###\n# #\n# #',

        'I':'###\n # \n # \n # \n###','J':' ##\n  #\n  #\n# #\n###',

        'K':'# #\n## \n#  \n## \n# #','L':'#  \n#  \n#  \n#  \n###',

        'M':'# #\n###\n# #\n# #\n# #','N':'# #\n###\n# #\n# #\n# #',

        'O':'###\n# #\n# #\n# #\n###','P':'###\n# #\n###\n#  \n#  ',

        'R':'###\n# #\n###\n## \n# #','S':'###\n#  \n###\n  #\n###',

        'T':'###\n # \n # \n # \n # ','U':'# #\n# #\n# #\n# #\n###',

        'V':'# #\n# #\n# #\n # \n # ','W':'# #\n# #\n###\n###\n# #',

        'X':'# #\n # \n # \n # \n# #','Y':'# #\n# #\n###\n # \n # ',

        'Z':'###\n  #\n # \n#  \n###',' ':'   \n   \n   \n   \n   ',

    }

    lines = [""] * 5

    for ch in text.upper():

        char_lines = font.get(ch, ['???','???','???','???','???']).split('\n') if isinstance(font.get(ch), str) else ['?']*5

        for i, l in enumerate(char_lines):

            lines[i] += l + "  "

    result = "\n".join(lines)

    if len(result) > 1900:

        return await ctx.send(embed=embed_warn("Texte trop long pour l'ASCII art."))

    await ctx.send(f"```\n{result}\n```")

@bot.command(name="wanted")

async def wanted_cmd(ctx, *, target: str = None):

    member = None

    if target and target.lower() == "random":

        humans = [m for m in ctx.guild.members if not m.bot]

        member = _random.choice(humans) if humans else ctx.author

    elif target:

        member = await resolve_member(ctx, target)

    if not member: member = ctx.author

    e = discord.Embed(title="🤠 WANTED", color=C_GOLD)

    e.set_image(url=member.display_avatar.url)

    e.add_field(name="🎯 Recherché", value=member.display_name, inline=True)

    e.add_field(name="💰 Récompense", value=f"**{_random.randint(100, 99999):,}$**", inline=True)

    e.set_footer(text="Mort ou Vif — ModeraBot Sheriff Dept.")

    await ctx.send(embed=e)

@bot.command(name="deepfry")

async def deepfry_cmd(ctx, *, target: str = None):

    member = None

    if target and target.lower() == "random":

        humans = [m for m in ctx.guild.members if not m.bot]

        member = _random.choice(humans) if humans else ctx.author

    elif target:

        member = await resolve_member(ctx, target)

    if not member: member = ctx.author

    e = discord.Embed(title="🍳 Deep Fry", description=f"**{member.display_name}** a été deepfry ! 🔥", color=C_ORANGE)

    e.set_image(url=member.display_avatar.url)

    e.set_footer(text="*Effet visuel simulé — image réelle non modifiée*")

    await ctx.send(embed=e)

@bot.command(name="blur")

async def blur_cmd(ctx, *, target: str = None):

    member = await resolve_member(ctx, target) if target else ctx.author

    if not member: member = ctx.author

    e = discord.Embed(title="💨 Blur", description=f"**{member.display_name}** est dans le flou total 😵‍💫", color=C_BLUE)

    e.set_image(url=member.display_avatar.url)

    e.set_footer(text="*Effet simulé — image réelle non modifiée*")

    await ctx.send(embed=e)

@bot.command(name="blurpify")

async def blurpify_cmd(ctx, *, target: str = None):

    member = await resolve_member(ctx, target) if target else ctx.author

    if not member: member = ctx.author

    e = discord.Embed(title="🟦 Blurpify", description=f"**{member.display_name}** est maintenant blurpifié ! 🟦", color=0x7289DA)

    e.set_image(url=member.display_avatar.url)

    e.set_footer(text="*Effet simulé — image réelle non modifiée*")

    await ctx.send(embed=e)

@bot.command(name="colorify", aliases=["colorize"])

async def colorify_cmd(ctx, *, target: str = None):

    member = await resolve_member(ctx, target) if target else ctx.author

    if not member: member = ctx.author

    color = _random.randint(0, 0xFFFFFF)

    e = discord.Embed(title="🎨 Colorify", description=f"**{member.display_name}** a été colorifié en `#{color:06X}` 🎨", color=color)

    e.set_image(url=member.display_avatar.url)

    e.set_footer(text="*Effet simulé — image réelle non modifiée*")

    await ctx.send(embed=e)

@bot.command(name="clyde")

async def clyde_cmd(ctx, *, text: str = None):

    if not text:

        return await ctx.send(embed=embed_err("Usage : `+clyde <texte>`"))

    e = discord.Embed(color=0x5865F2)

    e.set_author(name=f"Clyde", icon_url="https://discord.com/assets/f78426a064bc9dd24847519259bc42af.png")

    e.description = text[:500]

    e.set_footer(text="Uniquement toi peut voir ce message • Ce message Clyde est simulé")

    await ctx.send(embed=e)

@bot.command(name="tweet")

async def tweet_cmd(ctx, pseudo: str = None, *, text: str = None):

    if not pseudo or not text:

        return await ctx.send(embed=embed_err("Usage : `+tweet <pseudo> <texte>`"))

    e = discord.Embed(color=0x1DA1F2)

    e.set_author(name=f"@{pseudo}", icon_url=ctx.author.display_avatar.url)

    e.description = text[:280]

    e.set_footer(text=f"Twitter • {discord.utils.format_dt(ctx.message.created_at, style='d')}")

    e.add_field(name="❤️ Likes", value=str(_random.randint(0, 99999)), inline=True)

    e.add_field(name="🔁 Retweets", value=str(_random.randint(0, 9999)), inline=True)

    await ctx.send(embed=e)

@bot.command(name="mind")

async def mind_cmd(ctx, *, text: str = None):

    if not text:

        return await ctx.send(embed=embed_err("Usage : `+mind <texte>`"))

    e = discord.Embed(title="🪧 Panneau", color=C_BLUE)

    e.description = f"```{text[:200]}```"

    e.set_author(name=ctx.author.display_name, icon_url=ctx.author.display_avatar.url)

    e.set_footer(text="*Panneau généré par ModeraBot*")

    await ctx.send(embed=e)

@bot.command(name="undertale")

async def undertale_cmd(ctx, *, text: str = None):

    if not text:

        return await ctx.send(embed=embed_err("Usage : `+undertale <texte>`"))

    e = discord.Embed(color=0x000000)

    e.description = f"```\n* {text[:200]}\n```"

    e.set_footer(text="— Undertale Style —")

    await ctx.send(embed=e)

# ──────────────────────────────────────────────────────────────────────────────

# ──────────────────────────────────────────────────────────────────────────────

# EVENT HANDLERS — prevnames

# ──────────────────────────────────────────────────────────────────────────────

@bot.event

async def on_user_update(before, after):

    if before.name != after.name:

        uid = str(after.id)

        if uid not in _prevnames_data:

            _prevnames_data[uid] = []

        _prevnames_data[uid].append({"name": before.name, "ts": int(time.time())})

        _prevnames_data[uid] = _prevnames_data[uid][-50:]

# EVENTS

# ══════════════════════════════════════════

@bot.event

async def on_ready():

    check_premium_expirations.start()

    bot.add_view(AntibotPanelView(0))

    await tk_restore_views()

    await bot.tree.sync()

    print(f"✅ {bot.user} connecté | {len(bot.guilds)} serveurs")

    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="les serveurs | +aide"))

@bot.event

async def on_member_join(member):

    await _handle_welcome_join(member)

    # Defaultrole

    gid = str(member.guild.id)

    for rid in _defaultroles.get(gid, []):

        role = member.guild.get_role(rid)

        if role:

            try: await member.add_roles(role, reason="Rôle par défaut")

            except: pass

    # Log flux

    e = discord.Embed(description=f"📥 {member.mention} a **rejoint** le serveur", color=C_GREEN, timestamp=discord.utils.utcnow())

    e.set_author(name=str(member), icon_url=member.display_avatar.url)

    e.add_field(name="Compte créé", value=discord.utils.format_dt(member.created_at, style='R'), inline=True)

    e.set_footer(text=f"ID : {member.id}")

    await send_log(member.guild, "flux", e)

    # ShowPic

    sp = _showpic_cfg.get(str(member.guild.id), {})

    if sp.get("enabled") and sp.get("channel_id"):

        ch_sp = member.guild.get_channel(sp["channel_id"])

        if ch_sp:

            e_sp = discord.Embed(description=f"👋 {member.mention} vient de rejoindre !", color=C_GREEN)

            e_sp.set_image(url=member.display_avatar.url)

            try: await ch_sp.send(embed=e_sp)

            except: pass

    # Captcha
    await _handle_captcha_join(member)


@bot.event

async def on_guild_channel_delete(channel):

    tk_forget_ticket(channel.id)


@bot.event

async def on_member_remove(member):

    # Log flux

    if not member.guild: return

    e_flux = discord.Embed(description=f"📤 {member.mention} a **quitté** le serveur", color=C_RED, timestamp=discord.utils.utcnow())

    e_flux.set_author(name=str(member), icon_url=member.display_avatar.url)

    e_flux.set_footer(text=f"ID : {member.id}")

    await send_log(member.guild, "flux", e_flux)

    data = jload(FILES["depart"]).get(str(member.guild.id), {})

    if data and data.get("channel_id"):

        ch = member.guild.get_channel(data["channel_id"])

        if ch:

            vars_ = {"{user}": member.mention, "{username}": member.name,

                     "{server}": member.guild.name, "{membercount}": str(member.guild.member_count)}

            title = data.get("title", f"{member.name} a quitté le serveur.")

            desc = data.get("description", "")

            for k, v in vars_.items():

                title = title.replace(k, v)

                desc = desc.replace(k, v)

            e = discord.Embed(title=title, description=desc, color=data.get("color", C_RED))

            if data.get("image", "").strip(): e.set_image(url=data["image"].strip())

            await ch.send(embed=e)



@bot.event
async def on_message(message):
    if message.author.bot:
        return

    # Anti-Bot (honeypot) — priorité absolue
    try:
        if await _handle_antibot(message):
            return
    except Exception:
        pass

    # Modération automatique
    for _h in (_handle_antiraid, _handle_antilink, _handle_xp):
        try:
            await _h(message)
        except Exception:
            pass

    # Mention du bot → rappel du préfixe
    if bot.user in message.mentions and message.guild and not message.mention_everyone:
        pfx = _prefix_cache.get(message.guild.id, DEFAULT_PREFIX)
        e = discord.Embed(title="🟢 ModeraBot", description=f"Mon préfixe sur ce serveur est **`{pfx}`**\nTape **`{pfx}aide`** pour les commandes.", color=C_GREEN)
        await message.channel.send(embed=e)

    # Captcha check
    try:
        if await _handle_captcha_check(message):
            return
    except Exception:
        pass

    await bot.process_commands(message)



@bot.event

async def on_command_error(ctx, error):

    pfx = _prefix_cache.get(ctx.guild.id, DEFAULT_PREFIX) if ctx.guild else DEFAULT_PREFIX

    if isinstance(error, commands.CommandNotFound):

        # Récupérer le nom brut de façon sûre même si ctx.prefix est None
        content = ctx.message.content
        used_prefix = ctx.prefix or DEFAULT_PREFIX
        try:
            raw = content[len(used_prefix):].split()[0].lower()
        except (IndexError, TypeError):
            return

        real = resolve_command(raw)

        if real:

            real_cmd = bot.get_command(real)

            if real_cmd:

                ctx.command = real_cmd

                # Réinitialiser les args pour que la commande soit re-parsée correctement
                await real_cmd.reinvoke(ctx)

                return

        msg = await ctx.send(embed=discord.Embed(

            description=f"❓ Commande `{pfx}{raw}` introuvable.\nTape **`{pfx}aide`** pour voir les commandes.",

            color=C_ORANGE))

        await asyncio.sleep(5)

        try: await msg.delete()

        except: pass

    elif isinstance(error, commands.MissingPermissions):

        await ctx.send(embed=embed_err("Tu n'as pas la permission."))

    elif isinstance(error, commands.MemberNotFound):

        await ctx.send(embed=embed_err("Membre introuvable."))

    elif isinstance(error, commands.BadArgument):

        await ctx.send(embed=embed_err(f"Argument invalide. Vérifie la syntaxe avec `{pfx}aide`."))

    elif isinstance(error, commands.CommandInvokeError):

        original = error.original

        # Ne pas afficher les erreurs HTTP 403/404 habituelles
        if isinstance(original, discord.Forbidden):
            await ctx.send(embed=embed_err("Je n'ai pas la permission d'effectuer cette action."))
        elif isinstance(original, discord.NotFound):
            await ctx.send(embed=embed_err("Élément introuvable (déjà supprimé ?)."))
        else:
            import traceback
            print(f"[ERREUR CommandInvokeError] {ctx.command}: {original}")
            traceback.print_exception(type(original), original, original.__traceback__)

    elif isinstance(error, commands.NoPrivateMessage):

        await ctx.send(embed=embed_err("Cette commande ne peut pas être utilisée en MP."))

    elif isinstance(error, commands.CheckFailure):

        pass  # Géré individuellement dans chaque commande

# ══════════════════════════════════════════

# ══════════════════════════════════════════════════════════════════════════════

# ══════════════════════════════════════════════════════════════════════════════

# EVENT HANDLERS — LOGS AVANCÉS (messages formatés)

# ══════════════════════════════════════════════════════════════════════════════

# ─── LOGS MESSAGES ────────────────────────────────────────────────────────────

# ─── OUTILS DE LOGS ───────────────────────────────────────────────────────────

def _cut(text, limit=1000):
    """Tronque proprement une valeur de champ d'embed."""
    text = str(text) if text is not None else ""
    if len(text) <= limit:
        return text or "*vide*"
    return text[:limit - 3] + "..."


async def _audit(guild, action, target_id=None, within=20):
    """(auteur, raison) d'une action, via les logs d'audit. (None, None) si introuvable."""
    try:
        async for entry in guild.audit_logs(limit=8, action=action):
            if (discord.utils.utcnow() - entry.created_at).total_seconds() > within:
                continue
            if target_id is not None:
                target = entry.target
                if target is None or getattr(target, "id", None) != target_id:
                    continue
            return entry.user, (entry.reason or None)
    except Exception:
        pass
    return None, None


def _log_embed(title, desc, color, fields=None, author=None, footer=None, thumb=None):
    e = discord.Embed(title=title, description=desc, color=color, timestamp=discord.utils.utcnow())
    for name, value, *inline in (fields or []):
        e.add_field(name=name, value=_cut(value, 1024), inline=inline[0] if inline else True)
    if author is not None:
        try:
            e.set_author(name=str(author), icon_url=author.display_avatar.url)
        except Exception:
            e.set_author(name=str(author))
    if thumb:
        e.set_thumbnail(url=thumb)
    if footer:
        e.set_footer(text=footer)
    return e


def _actor_fields(actor, reason=None):
    out = []
    if actor:
        out.append(("🛡️ Par", actor.mention, True))
    if reason:
        out.append(("📝 Raison", reason, False))
    return out


def _perm_diff(before_perms, after_perms):
    """Liste lisible des permissions gagnees / perdues."""
    gained, lost = [], []
    for name, value in after_perms:
        if getattr(before_perms, name) != value:
            (gained if value else lost).append(name.replace("_", " "))
    parts = []
    if gained:
        parts.append("✅ " + ", ".join(sorted(gained)[:15]))
    if lost:
        parts.append("❌ " + ", ".join(sorted(lost)[:15]))
    return "\n".join(parts)


def _chan_type_label(channel):
    return {
        discord.ChannelType.text: "💬 Textuel",
        discord.ChannelType.voice: "🔊 Vocal",
        discord.ChannelType.category: "📂 Catégorie",
        discord.ChannelType.news: "📰 Annonces",
        discord.ChannelType.stage_voice: "🎤 Conférence",
        discord.ChannelType.forum: "🗂️ Forum",
    }.get(getattr(channel, "type", None), "📺 Salon")


# ─── LOGS MESSAGES ────────────────────────────────────────────────────────────

@bot.event
async def on_message_delete(message):
    if message.author.bot or not message.guild:
        return

    _snipe_deleted[message.channel.id] = {
        "content": message.content, "author": message.author,
        "timestamp": message.created_at,
        "attachments": [a.url for a in message.attachments]
    }

    actor, reason = await _audit(message.guild, discord.AuditLogAction.message_delete,
                                 target_id=message.author.id, within=10)

    fields = [("📺 Salon", message.channel.mention, True),
              ("👤 Auteur", f"{message.author.mention}\n`{message.author}`", True)]
    if actor and actor.id != message.author.id:
        fields.append(("🛡️ Supprimé par", actor.mention, True))
    else:
        fields.append(("🛡️ Supprimé par", "L'auteur (ou introuvable)", True))

    fields.append(("💬 Contenu", message.content or "*aucun texte*", False))

    if message.attachments:
        fields.append(("📎 Pièces jointes",
                       "\n".join(f"[{a.filename}]({a.url})" for a in message.attachments[:5]), False))
    if message.stickers:
        fields.append(("🏷️ Stickers", ", ".join(st.name for st in message.stickers), True))
    if message.embeds:
        fields.append(("🖼️ Embeds", str(len(message.embeds)), True))
    if message.reference:
        fields.append(("↩️ Réponse à", f"[le message]({message.jump_url})", True))

    fields.append(("🕐 Envoyé", discord.utils.format_dt(message.created_at, "R"), True))
    if reason:
        fields.append(("📝 Raison", reason, False))

    e = _log_embed("🗑️ Message supprimé", None, C_RED, fields,
                   author=message.author, footer=f"Message {message.id} • Auteur {message.author.id}")
    await send_log(message.guild, "msg", e)


@bot.listen("on_bulk_message_delete")
async def on_bulk_delete_log(messages):
    if not messages:
        return
    first = messages[0]
    if not first.guild:
        return

    actor, reason = await _audit(first.guild, discord.AuditLogAction.message_bulk_delete, within=15)

    auteurs = {}
    for m in messages:
        auteurs[m.author] = auteurs.get(m.author, 0) + 1
    top = "\n".join(f"{a.mention} — {n} message(s)"
                    for a, n in sorted(auteurs.items(), key=lambda x: -x[1])[:10])

    apercu = "\n".join(f"**{m.author}** : {(m.content or '*pièce jointe*')[:80]}"
                       for m in list(messages)[-10:])

    fields = [("📺 Salon", first.channel.mention, True),
              ("🔢 Messages supprimés", str(len(messages)), True)]
    fields += _actor_fields(actor, reason)
    fields.append(("👥 Auteurs concernés", top or "—", False))
    fields.append(("📄 Derniers messages", apercu or "—", False))

    e = _log_embed("🧹 Purge de messages", None, C_RED, fields,
                   footer=f"Salon {first.channel.id}")
    await send_log(first.guild, "msg", e)


@bot.event
async def on_message_edit(before, after):
    if before.author.bot or not before.guild:
        return

    if before.pinned != after.pinned:
        e = _log_embed("📌 Message épinglé" if after.pinned else "📌 Message désépinglé",
                       f"[Aller au message]({after.jump_url})", C_BLUE,
                       [("📺 Salon", after.channel.mention, True),
                        ("👤 Auteur", after.author.mention, True)],
                       author=after.author, footer=f"Message {after.id}")
        await send_log(before.guild, "msg", e)

    if before.content == after.content:
        return

    _snipe_edited[before.channel.id] = {
        "before": before.content, "after": after.content,
        "author": before.author, "timestamp": after.edited_at or discord.utils.utcnow()
    }

    fields = [("📺 Salon", before.channel.mention, True),
              ("👤 Auteur", f"{before.author.mention}\n`{before.author}`", True),
              ("🔗 Lien", f"[Aller au message]({after.jump_url})", True),
              ("❌ Avant", before.content or "*vide*", False),
              ("✅ Après", after.content or "*vide*", False),
              ("🕐 Envoyé", discord.utils.format_dt(before.created_at, "R"), True)]

    if len(before.content or "") != len(after.content or ""):
        delta = len(after.content or "") - len(before.content or "")
        fields.append(("📏 Taille", f"{len(before.content or '')} → {len(after.content or '')} ({delta:+d})", True))

    e = _log_embed("✏️ Message modifié", None, C_ORANGE, fields,
                   author=before.author, footer=f"Message {before.id} • Auteur {before.author.id}")
    await send_log(before.guild, "msg", e)


# ─── LOGS MODÉRATION ──────────────────────────────────────────────────────────

@bot.event
async def on_member_ban(guild, user):
    actor, reason = await _audit(guild, discord.AuditLogAction.ban, target_id=user.id)
    fields = [("👤 Membre", f"{user.mention}\n`{user}`", True),
              ("📅 Compte créé", discord.utils.format_dt(user.created_at, "R"), True)]
    fields += _actor_fields(actor, reason or "Aucune raison fournie")
    e = _log_embed("🔨 Membre banni", f"{user.mention} a été **banni** du serveur", C_RED,
                   fields, author=user, thumb=user.display_avatar.url, footer=f"ID : {user.id}")
    await send_log(guild, "mod", e)


@bot.event
async def on_member_unban(guild, user):
    actor, reason = await _audit(guild, discord.AuditLogAction.unban, target_id=user.id)
    fields = [("👤 Membre", f"{user.mention}\n`{user}`", True)]
    fields += _actor_fields(actor, reason)
    e = _log_embed("✅ Membre débanni", f"{user.mention} a été **débanni**", C_GREEN,
                   fields, author=user, footer=f"ID : {user.id}")
    await send_log(guild, "mod", e)


@bot.event
async def on_member_update(before, after):
    guild = after.guild

    # ── Rôles ────────────────────────────────────────────────────────────────
    added   = set(after.roles) - set(before.roles)
    removed = set(before.roles) - set(after.roles)

    if added or removed:
        actor, reason = await _audit(guild, discord.AuditLogAction.member_role_update,
                                     target_id=after.id)
        fields = [("👤 Membre", f"{after.mention}\n`{after}`", True)]
        fields += _actor_fields(actor, reason)
        if added:
            fields.append(("✅ Rôles ajoutés", " ".join(r.mention for r in added), False))
        if removed:
            fields.append(("❌ Rôles retirés", " ".join(r.mention for r in removed), False))
        fields.append(("🎭 Total", f"{len(after.roles) - 1} rôle(s)", True))

        e = _log_embed("🎭 Rôles modifiés", None, C_GREEN if added else C_ORANGE,
                       fields, author=after, footer=f"ID : {after.id}")
        await send_log(guild, "role", e)

    # ── Exclusion temporaire (timeout) ───────────────────────────────────────
    if before.timed_out_until != after.timed_out_until:
        actor, reason = await _audit(guild, discord.AuditLogAction.member_update, target_id=after.id)
        if after.timed_out_until:
            fields = [("👤 Membre", f"{after.mention}\n`{after}`", True),
                      ("⏳ Jusqu'à", discord.utils.format_dt(after.timed_out_until, "F"), True),
                      ("⏱️ Fin", discord.utils.format_dt(after.timed_out_until, "R"), True)]
            fields += _actor_fields(actor, reason)
            e = _log_embed("🔇 Membre réduit au silence",
                           f"{after.mention} est **exclu temporairement**", C_ORANGE,
                           fields, author=after, footer=f"ID : {after.id}")
        else:
            fields = [("👤 Membre", f"{after.mention}\n`{after}`", True)]
            fields += _actor_fields(actor, reason)
            e = _log_embed("🔊 Silence levé", f"{after.mention} peut de nouveau parler", C_GREEN,
                           fields, author=after, footer=f"ID : {after.id}")
        await send_log(guild, "mod", e)

    # ── Boost ────────────────────────────────────────────────────────────────
    if before.premium_since != after.premium_since:
        if after.premium_since and not before.premium_since:
            e = _log_embed("🚀 Nouveau boost !", f"{after.mention} a **boosté** le serveur !", 0xFF73FA,
                           [("👤 Membre", f"{after.mention}\n`{after}`", True),
                            ("💎 Total serveur", f"{guild.premium_subscription_count} boost(s)", True),
                            ("🏆 Niveau", f"Niveau {guild.premium_tier}", True)],
                           author=after, thumb=after.display_avatar.url, footer=f"ID : {after.id}")
        else:
            e = _log_embed("💔 Boost retiré", f"{after.mention} ne boost plus le serveur", C_ORANGE,
                           [("💎 Total serveur", f"{guild.premium_subscription_count} boost(s)", True)],
                           author=after, footer=f"ID : {after.id}")
        await send_log(guild, "boost", e)

    # ── Pseudo ───────────────────────────────────────────────────────────────
    if before.nick != after.nick:
        actor, reason = await _audit(guild, discord.AuditLogAction.member_update, target_id=after.id)
        fields = [("❌ Avant", before.nick or before.name, True),
                  ("✅ Après", after.nick or after.name, True)]
        fields += _actor_fields(actor, reason)
        e = _log_embed("✏️ Pseudo modifié", f"{after.mention} a changé de pseudo sur le serveur",
                       C_BLUE, fields, author=after, footer=f"ID : {after.id}")
        await send_log(guild, "mod", e)

    # ── Avatar de serveur ────────────────────────────────────────────────────
    if before.guild_avatar != after.guild_avatar:
        e = _log_embed("🖼️ Avatar de serveur modifié", f"{after.mention} a changé son avatar sur ce serveur",
                       C_BLUE, [], author=after,
                       thumb=(after.guild_avatar.url if after.guild_avatar else after.display_avatar.url),
                       footer=f"ID : {after.id}")
        await send_log(guild, "mod", e)


# ─── LOGS RÔLES ───────────────────────────────────────────────────────────────

@bot.event
async def on_guild_role_create(role):
    actor, reason = await _audit(role.guild, discord.AuditLogAction.role_create, target_id=role.id)
    perms = [n.replace("_", " ") for n, v in role.permissions if v]
    fields = [("🎭 Rôle", f"{role.mention}\n`{role.name}`", True),
              ("🎨 Couleur", str(role.color), True),
              ("📌 Position", str(role.position), True)]
    fields += _actor_fields(actor, reason)
    fields.append(("🔑 Permissions", ", ".join(sorted(perms)[:20]) if perms else "Aucune", False))
    e = _log_embed("➕ Rôle créé", f"Le rôle {role.mention} a été **créé**", C_GREEN,
                   fields, footer=f"ID : {role.id}")
    await send_log(role.guild, "role", e)


@bot.event
async def on_guild_role_delete(role):
    actor, reason = await _audit(role.guild, discord.AuditLogAction.role_delete, target_id=role.id)
    fields = [("🎭 Rôle", f"`{role.name}`", True),
              ("🎨 Couleur", str(role.color), True),
              ("👥 Membres concernés", str(len(role.members)), True)]
    fields += _actor_fields(actor, reason)
    e = _log_embed("🗑️ Rôle supprimé", f"Le rôle **{role.name}** a été **supprimé**", C_RED,
                   fields, footer=f"ID : {role.id}")
    await send_log(role.guild, "role", e)


@bot.event
async def on_guild_role_update(before, after):
    changes = []
    if before.name != after.name:
        changes.append(("📛 Nom", f"`{before.name}` → `{after.name}`", False))
    if before.color != after.color:
        changes.append(("🎨 Couleur", f"`{before.color}` → `{after.color}`", True))
    if before.hoist != after.hoist:
        changes.append(("📊 Affiché séparément", "✅ Oui" if after.hoist else "❌ Non", True))
    if before.mentionable != after.mentionable:
        changes.append(("🔔 Mentionnable", "✅ Oui" if after.mentionable else "❌ Non", True))
    if before.position != after.position:
        changes.append(("📌 Position", f"{before.position} → {after.position}", True))
    if before.permissions != after.permissions:
        diff = _perm_diff(before.permissions, after.permissions)
        if diff:
            changes.append(("🔑 Permissions", diff, False))
    if not changes:
        return

    actor, reason = await _audit(after.guild, discord.AuditLogAction.role_update, target_id=after.id)
    fields = [("🎭 Rôle", after.mention, True)] + _actor_fields(actor, reason) + changes
    e = _log_embed("✏️ Rôle modifié", None, C_ORANGE, fields, footer=f"ID : {after.id}")
    await send_log(after.guild, "role", e)


# ─── LOGS SALONS ──────────────────────────────────────────────────────────────

@bot.event
async def on_guild_channel_create(channel):
    actor, reason = await _audit(channel.guild, discord.AuditLogAction.channel_create,
                                 target_id=channel.id)
    fields = [("📺 Salon", getattr(channel, "mention", f"`{channel.name}`"), True),
              ("🗂️ Type", _chan_type_label(channel), True),
              ("📂 Catégorie", channel.category.name if channel.category else "Aucune", True)]
    fields += _actor_fields(actor, reason)
    e = _log_embed("➕ Salon créé", f"Le salon **{channel.name}** a été **créé**", C_GREEN,
                   fields, footer=f"ID : {channel.id}")
    await send_log(channel.guild, "channel", e)


@bot.event
async def on_guild_channel_delete(channel):
    actor, reason = await _audit(channel.guild, discord.AuditLogAction.channel_delete,
                                 target_id=channel.id)
    fields = [("📺 Salon", f"`{channel.name}`", True),
              ("🗂️ Type", _chan_type_label(channel), True),
              ("📂 Catégorie", channel.category.name if channel.category else "Aucune", True)]
    fields += _actor_fields(actor, reason)
    e = _log_embed("🗑️ Salon supprimé", f"Le salon **{channel.name}** a été **supprimé**", C_RED,
                   fields, footer=f"ID : {channel.id}")
    await send_log(channel.guild, "channel", e)


@bot.event
async def on_guild_channel_update(before, after):
    changes = []
    if before.name != after.name:
        changes.append(("📛 Nom", f"`{before.name}` → `{after.name}`", False))
    if getattr(before, "topic", None) != getattr(after, "topic", None):
        changes.append(("📝 Sujet", f"`{getattr(before, 'topic', None) or 'vide'}`\n→ `{getattr(after, 'topic', None) or 'vide'}`", False))
    if getattr(before, "slowmode_delay", None) != getattr(after, "slowmode_delay", None):
        changes.append(("🐌 Mode lent", f"{getattr(before, 'slowmode_delay', 0)}s → {getattr(after, 'slowmode_delay', 0)}s", True))
    if getattr(before, "nsfw", None) != getattr(after, "nsfw", None):
        changes.append(("🔞 NSFW", "✅ Activé" if getattr(after, "nsfw", False) else "❌ Désactivé", True))
    if getattr(before, "bitrate", None) != getattr(after, "bitrate", None):
        changes.append(("🎚️ Bitrate", f"{getattr(before, 'bitrate', 0)//1000} → {getattr(after, 'bitrate', 0)//1000} kbps", True))
    if getattr(before, "user_limit", None) != getattr(after, "user_limit", None):
        changes.append(("👥 Limite", f"{getattr(before, 'user_limit', 0)} → {getattr(after, 'user_limit', 0)}", True))
    if before.category != after.category:
        changes.append(("📂 Catégorie",
                        f"{before.category.name if before.category else 'Aucune'} → {after.category.name if after.category else 'Aucune'}", True))
    if before.overwrites != after.overwrites:
        touched = set(before.overwrites) ^ set(after.overwrites)
        for target in set(before.overwrites) & set(after.overwrites):
            if before.overwrites[target] != after.overwrites[target]:
                touched.add(target)
        noms = ", ".join(getattr(t, "mention", getattr(t, "name", "?")) for t in list(touched)[:10])
        changes.append(("🔐 Permissions modifiées", noms or "—", False))
    if not changes:
        return

    actor, reason = await _audit(after.guild, discord.AuditLogAction.channel_update, target_id=after.id)
    fields = [("📺 Salon", getattr(after, "mention", f"`{after.name}`"), True),
              ("🗂️ Type", _chan_type_label(after), True)]
    fields += _actor_fields(actor, reason) + changes
    e = _log_embed("✏️ Salon modifié", None, C_ORANGE, fields, footer=f"ID : {after.id}")
    await send_log(after.guild, "channel", e)


# ─── LOGS SERVEUR / DIVERS ────────────────────────────────────────────────────

@bot.listen("on_guild_update")
async def on_guild_update_log(before, after):
    changes = []
    if before.name != after.name:
        changes.append(("📛 Nom", f"`{before.name}` → `{after.name}`", False))
    if before.icon != after.icon:
        changes.append(("🖼️ Icône", "Modifiée", True))
    if before.owner_id != after.owner_id:
        changes.append(("👑 Propriétaire", f"<@{before.owner_id}> → <@{after.owner_id}>", True))
    if before.verification_level != after.verification_level:
        changes.append(("🔒 Vérification", f"{before.verification_level} → {after.verification_level}", True))
    if before.afk_channel != after.afk_channel:
        changes.append(("💤 Salon AFK",
                        f"{before.afk_channel.name if before.afk_channel else 'Aucun'} → {after.afk_channel.name if after.afk_channel else 'Aucun'}", True))
    if not changes:
        return
    actor, reason = await _audit(after, discord.AuditLogAction.guild_update)
    fields = _actor_fields(actor, reason) + changes
    e = _log_embed("⚙️ Serveur modifié", None, C_ORANGE, fields,
                   thumb=after.icon.url if after.icon else None, footer=f"ID : {after.id}")
    await send_log(after, "channel", e)


@bot.listen("on_guild_emojis_update")
async def on_emojis_update_log(guild, before, after):
    ajoutes = [em for em in after if em not in before]
    retires = [em for em in before if em not in after]
    if not ajoutes and not retires:
        return
    fields = []
    if ajoutes:
        fields.append(("✅ Ajoutés", " ".join(str(em) for em in ajoutes[:15]), False))
    if retires:
        fields.append(("❌ Retirés", ", ".join(f"`:{em.name}:`" for em in retires[:15]), False))
    fields.append(("🔢 Total", f"{len(after)} émojis", True))
    e = _log_embed("😀 Émojis modifiés", None, C_BLUE, fields)
    await send_log(guild, "channel", e)


@bot.listen("on_thread_create")
async def on_thread_create_log(thread):
    e = _log_embed("🧵 Fil créé", f"Le fil {thread.mention} a été **créé**", C_GREEN,
                   [("📺 Salon parent", thread.parent.mention if thread.parent else "?", True),
                    ("👤 Créé par", f"<@{thread.owner_id}>" if thread.owner_id else "?", True)],
                   footer=f"ID : {thread.id}")
    await send_log(thread.guild, "channel", e)


@bot.listen("on_thread_delete")
async def on_thread_delete_log(thread):
    e = _log_embed("🧵 Fil supprimé", f"Le fil **{thread.name}** a été **supprimé**", C_RED,
                   [("📺 Salon parent", thread.parent.mention if thread.parent else "?", True)],
                   footer=f"ID : {thread.id}")
    await send_log(thread.guild, "channel", e)


@bot.listen("on_invite_create")
async def on_invite_create_log(invite):
    if not invite.guild:
        return
    fields = [("🔗 Code", f"`{invite.code}`", True),
              ("📺 Salon", invite.channel.mention if invite.channel else "?", True),
              ("👤 Créée par", invite.inviter.mention if invite.inviter else "?", True),
              ("⏳ Expire", discord.utils.format_dt(invite.expires_at, "R") if invite.expires_at else "Jamais", True),
              ("🔢 Utilisations max", str(invite.max_uses or "Illimité"), True)]
    e = _log_embed("📨 Invitation créée", None, C_GREEN, fields, footer=f"discord.gg/{invite.code}")
    await send_log(invite.guild, "mod", e)


@bot.listen("on_invite_delete")
async def on_invite_delete_log(invite):
    if not invite.guild:
        return
    e = _log_embed("📭 Invitation supprimée", None, C_RED,
                   [("🔗 Code", f"`{invite.code}`", True),
                    ("📺 Salon", invite.channel.mention if invite.channel else "?", True)],
                   footer=f"discord.gg/{invite.code}")
    await send_log(invite.guild, "mod", e)



# ─── MOTEUR DE LOGS VOCAUX ────────────────────────────────────────────────────

_voice_sessions = {}   # (guild_id, member_id) -> timestamp de connexion


def _fmt_voice_duration(seconds):
    seconds = int(max(0, seconds))
    h, rest = divmod(seconds, 3600)
    m, sec = divmod(rest, 60)
    if h:
        return f"{h}h {m}min {sec}s"
    if m:
        return f"{m}min {sec}s"
    return f"{sec}s"


async def _voice_actor(guild, member):
    """Retrouve le moderateur derriere une action serveur (mute/casque/deplacement)."""
    try:
        async for entry in guild.audit_logs(limit=6, action=discord.AuditLogAction.member_update):
            if entry.target and entry.target.id == member.id:
                if (discord.utils.utcnow() - entry.created_at).total_seconds() < 15:
                    return entry.user
    except Exception:
        pass
    return None


async def _log_voice_state(member, before, after):
    """Journalise TOUT ce qui bouge en vocal, pas seulement les connexions."""
    guild = member.guild
    key = (guild.id, member.id)
    events = []   # (emoji, titre, description, couleur, [(nom, valeur), ...])

    # ── Connexion / deconnexion / changement de salon ────────────────────────
    if before.channel != after.channel:
        if after.channel and not before.channel:
            _voice_sessions[key] = time.time()
            fields = [("📍 Salon", after.channel.mention),
                      ("👥 Personnes présentes", str(len(after.channel.members)))]
            if guild.afk_channel and after.channel.id == guild.afk_channel.id:
                fields.append(("💤 Statut", "Salon AFK"))
            events.append(("🎙️", "Connexion vocale",
                           f"{member.mention} a rejoint {after.channel.mention}", C_GREEN, fields))

        elif before.channel and not after.channel:
            started = _voice_sessions.pop(key, None)
            fields = [("📍 Salon quitté", before.channel.mention),
                      ("👥 Restants", str(len(before.channel.members)))]
            if started:
                fields.insert(1, ("⏱️ Durée de la session", _fmt_voice_duration(time.time() - started)))
            events.append(("🚪", "Déconnexion vocale",
                           f"{member.mention} a quitté {before.channel.mention}", C_RED, fields))

        else:
            fields = [("⬅️ Avant", before.channel.mention), ("➡️ Après", after.channel.mention)]
            actor = await _voice_actor(guild, member)
            if actor:
                fields.append(("🛡️ Déplacé par", actor.mention))
            if guild.afk_channel and after.channel.id == guild.afk_channel.id:
                fields.append(("💤 Statut", "Envoyé en AFK"))
            events.append(("🔄", "Changement de salon",
                           f"{member.mention} : {before.channel.mention} → {after.channel.mention}",
                           C_ORANGE, fields))

    salon = after.channel or before.channel
    salon_field = [("📍 Salon", salon.mention)] if salon else []

    # ── Micro et casque du membre lui-meme ───────────────────────────────────
    if before.self_mute != after.self_mute:
        if after.self_mute:
            events.append(("🔇", "Micro coupé", f"{member.mention} a coupé son micro", C_DARK, salon_field))
        else:
            events.append(("🎤", "Micro réactivé", f"{member.mention} a réactivé son micro", C_BLUE, salon_field))

    if before.self_deaf != after.self_deaf:
        if after.self_deaf:
            events.append(("🔕", "Casque coupé", f"{member.mention} n'entend plus le salon", C_DARK, salon_field))
        else:
            events.append(("🔊", "Casque réactivé", f"{member.mention} entend à nouveau le salon", C_BLUE, salon_field))

    # ── Sanctions vocales du staff ───────────────────────────────────────────
    if before.mute != after.mute:
        actor = await _voice_actor(guild, member)
        fields = list(salon_field)
        if actor:
            fields.append(("🛡️ Par", actor.mention))
        if after.mute:
            events.append(("🚫", "Rendu muet (serveur)",
                           f"{member.mention} a été **rendu muet** par le staff", C_RED, fields))
        else:
            events.append(("✅", "Mute serveur retiré",
                           f"{member.mention} peut de nouveau parler", C_GREEN, fields))

    if before.deaf != after.deaf:
        actor = await _voice_actor(guild, member)
        fields = list(salon_field)
        if actor:
            fields.append(("🛡️ Par", actor.mention))
        if after.deaf:
            events.append(("🔇", "Casque coupé (serveur)",
                           f"{member.mention} a été **rendu sourd** par le staff", C_RED, fields))
        else:
            events.append(("✅", "Sourdine serveur retirée",
                           f"{member.mention} entend à nouveau", C_GREEN, fields))

    # ── Camera et partage d'écran ────────────────────────────────────────────
    if before.self_video != after.self_video:
        if after.self_video:
            events.append(("📹", "Caméra activée", f"{member.mention} a allumé sa caméra", C_BLUE, salon_field))
        else:
            events.append(("📷", "Caméra coupée", f"{member.mention} a éteint sa caméra", C_DARK, salon_field))

    if before.self_stream != after.self_stream:
        if after.self_stream:
            events.append(("🔴", "Partage d'écran lancé",
                           f"{member.mention} a lancé un **Go Live**", 0xFF73FA, salon_field))
        else:
            events.append(("⏹️", "Partage d'écran arrêté",
                           f"{member.mention} a arrêté son partage d'écran", C_DARK, salon_field))

    # ── Conférences (stage) ──────────────────────────────────────────────────
    if before.suppress != after.suppress:
        if after.suppress:
            events.append(("👂", "Passé spectateur",
                           f"{member.mention} n'est plus orateur", C_ORANGE, salon_field))
        else:
            events.append(("🗣️", "Passé orateur",
                           f"{member.mention} peut prendre la parole", C_GREEN, salon_field))

    if before.requested_to_speak_at != after.requested_to_speak_at and after.requested_to_speak_at:
        events.append(("✋", "Demande de parole",
                       f"{member.mention} demande à parler", C_ORANGE, salon_field))

    # ── Envoi ────────────────────────────────────────────────────────────────
    for emoji, titre, desc, color, fields in events:
        e = discord.Embed(title=f"{emoji} {titre}", description=desc,
                          color=color, timestamp=discord.utils.utcnow())
        e.set_author(name=str(member), icon_url=member.display_avatar.url)
        for name, value in fields:
            e.add_field(name=name, value=value, inline=True)
        e.set_footer(text=f"ID : {member.id}")
        await send_log(guild, "voc", e)


@bot.event

async def on_voice_state_update(member, before, after):

    if member.bot: return

    gid = str(member.guild.id)

    # ─── JOIN TO CREATE ───────────────────────────────────────────────────────

    jtc = _jtc_config.get(gid, {})

    if jtc.get("trigger_id"):

        # Membre rejoint le salon déclencheur → créer un vocal temporaire

        if after.channel and after.channel.id == jtc["trigger_id"]:

            name_tpl = jtc.get("name", "Salon de {username}")

            ch_name  = name_tpl.replace("{username}", member.display_name)[:100]

            cat = _as_category(member.guild, jtc.get("category_id")) or after.channel.category

            try:

                new_ch = await member.guild.create_voice_channel(

                    ch_name, category=cat,

                    reason=f"JoinToCreate par {member}"

                )

                await member.move_to(new_ch, reason="JoinToCreate")

                _jtc_channels[new_ch.id] = member.id

            except: pass

        # Membre quitte un vocal temporaire JTC

        if before.channel and before.channel.id in _jtc_channels:

            if len(before.channel.members) == 0:

                try:

                    await before.channel.delete(reason="JoinToCreate — vocal vide")

                    _jtc_channels.pop(before.channel.id, None)

                except: pass

    # ─── LOGS VOCAUX (complets : micro, casque, caméra, Go Live, sanctions) ──

    try:

        await _log_voice_state(member, before, after)

    except Exception:

        pass

# ─── LOGS FLUX (join/leave) ───────────────────────────────────────────────────

@bot.listen("on_member_join")

async def on_member_join_log(member):

    e = discord.Embed(

        description=f"📥 {member.mention} a **rejoint** le serveur",

        color=C_GREEN, timestamp=discord.utils.utcnow()

    )

    e.set_author(name=str(member), icon_url=member.display_avatar.url)

    e.set_footer(text=f"ID : {member.id}")

    e.add_field(name="Compte créé", value=discord.utils.format_dt(member.created_at, style="R"), inline=True)

    await send_log(member.guild, "flux", e)

# MISE À JOUR DU HELP — NOUVELLES CATÉGORIES

# ══════════════════════════════════════════════════════════════════════════════

# FLASK API (inchangée)

# ══════════════════════════════════════════

app = Flask(__name__)

API_TOKEN = "f92JkL0pA7xQ19Zb3T"

CLIENT_ID = "1447165780708823140"

CLIENT_SECRET = "S1LZeqsNe0QqhwC9VJ7S-8_zfB9ITwZB"

REDIRECT_URI = "https://dashboard.moderabot.xyz/bot/auth/callback"

SECRET_KEY = "f92JkL0pA7xQ19Zb3T"

app.secret_key = SECRET_KEY

app.config["SESSION_COOKIE_SECURE"] = True

app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

app.permanent_session_lifetime = timedelta(days=30)

@app.route("/api/health")
def api_health():
    """Ping utilisé par le dashboard pour distinguer « API HS » de « mauvaise URL »."""
    ready = False
    try:
        ready = bool(bot and bot.is_ready())
    except Exception:
        ready = False
    return jsonify({"ok": True, "bot_ready": ready})


DASHBOARD_REDIRECT_URI = "https://dashboard.moderabot.xyz/servers.html"

@app.route("/api/oauth-exchange", methods=["POST"])

def oauth_exchange():

    code = (request.get_json(silent=True) or {}).get("code")

    if not code: return jsonify({"error": "missing_code"}), 400

    data = {"client_id": CLIENT_ID, "client_secret": CLIENT_SECRET, "grant_type": "authorization_code",

            "code": code, "redirect_uri": DASHBOARD_REDIRECT_URI}

    token_res = requests.post("https://discord.com/api/oauth2/token", data=data,

                               headers={"Content-Type": "application/x-www-form-urlencoded"})

    token_json = token_res.json()

    access_token = token_json.get("access_token")

    if not access_token: return jsonify({"error": "invalid_code", "details": token_json}), 400

    user = requests.get("https://discord.com/api/users/@me", headers={"Authorization": f"Bearer {access_token}"}).json()

    session.permanent = True

    session["discord_token"] = access_token

    session["discord_user"] = user

    return jsonify({"user": user})

@app.route("/api/my-guilds")

def my_guilds():

    access_token = session.get("discord_token")

    if not access_token: return jsonify({"error": "not_authenticated"}), 401

    r = requests.get("https://discord.com/api/users/@me/guilds", headers={"Authorization": f"Bearer {access_token}"})

    if r.status_code != 200: return jsonify({"error": "discord_error"}), 502

    return jsonify({

        "user": session.get("discord_user"),

        "guilds": r.json(),

        "bot_guild_ids": [str(g.id) for g in bot.guilds],

    })

@app.route("/api/logout", methods=["POST"])

def api_logout():

    session.clear()

    return jsonify({"ok": True})


@app.route("/api/bot-guilds")
def api_bot_guilds():
    """IDs des serveurs de l'utilisateur où le bot est présent.

    Accepte le cookie de session OU le token Discord porté par la page
    (`Authorization: Bearer ...`) : en cross-origin le cookie n'est pas envoyé.
    """
    perms = {}
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        user, perms = _dash_user_from_token(auth[7:].strip())
        if not user:
            return jsonify({"error": "not_authenticated"}), 401
    else:
        access_token = session.get("discord_token")
        if not access_token:
            return jsonify({"error": "not_authenticated"}), 401
        user, perms = _dash_user_from_token(access_token)
        if not user:
            return jsonify({"error": "not_authenticated"}), 401

    bot_ids = {str(g.id) for g in bot.guilds}
    return jsonify({"bot_guild_ids": sorted(bot_ids & set(perms.keys()))})

def require_guild_admin(guild_id):

    user = session.get("discord_user")

    if not user:

        return None, None

    try:

        gid = int(guild_id)

    except (TypeError, ValueError):

        return None, None

    guild = bot.get_guild(gid)

    if not guild:

        return None, None

    try:

        uid = int(user["id"])

    except (TypeError, ValueError, KeyError):

        return None, None

    member = guild.get_member(uid)

    if not member:

        return None, None

    if member.id == guild.owner_id or member.guild_permissions.administrator or member.guild_permissions.manage_guild:

        return guild, member

    return None, None

@app.route("/api/debug/<guild_id>")

def api_debug_guild(guild_id):

    user = session.get("discord_user")

    out = {"session_user": user}

    try:

        gid = int(guild_id)

    except Exception as e:

        return jsonify({**out, "error": "bad_guild_id", "detail": str(e)})

    guild = bot.get_guild(gid)

    out["guild_found"] = bool(guild)

    out["bot_ready"] = bot.is_ready()

    out["bot_guild_ids_sample"] = [str(g.id) for g in bot.guilds][:10]

    if guild:

        out["guild_name"] = guild.name

        out["member_cache_count"] = len(guild.members)

        out["chunked"] = guild.chunked

        if user:

            try:

                uid = int(user["id"])

                member = guild.get_member(uid)

                out["member_found_in_cache"] = bool(member)

                if member:

                    out["is_owner"] = member.id == guild.owner_id

                    out["is_admin_perm"] = member.guild_permissions.administrator

                    out["is_manage_guild_perm"] = member.guild_permissions.manage_guild

            except Exception as e:

                out["member_check_error"] = str(e)

    return jsonify(out)

@app.route("/api/guild/<guild_id>/overview")

def api_guild_overview(guild_id):

    guild, member = require_guild_admin(guild_id)

    if not guild:

        return jsonify({"error": "forbidden"}), 403

    real_members = [m for m in guild.members if not m.bot]

    online = sum(1 for m in real_members if str(m.status) != "offline")

    modo_cfg = jload(FILES["modo"]).get(str(guild.id), {})

    return jsonify({

        "id": str(guild.id),

        "name": guild.name,

        "icon": str(guild.icon.url) if guild.icon else None,

        "member_count": len(real_members),

        "online_count": online,

        "bot_online": bot.is_ready(),

        "log_channel": modo_cfg.get("log_channel"),

        "modo_roles": modo_cfg.get("modo_roles", []),

        "prefix": _prefix_cache.get(guild.id, DEFAULT_PREFIX),

    })

@app.route("/api/guild/<guild_id>/members")

def api_guild_members(guild_id):

    guild, member = require_guild_admin(guild_id)

    if not guild:

        return jsonify({"error": "forbidden"}), 403

    out = []

    for m in guild.members:

        if m.bot:

            continue

        out.append({

            "id": str(m.id),

            "username": m.name,

            "display_name": m.display_name,

            "avatar": str(m.display_avatar.url),

            "joined_at": m.joined_at.isoformat() if m.joined_at else None,

            "top_role": m.top_role.name if m.top_role and m.top_role.name != "@everyone" else None,

            "top_role_color": str(m.top_role.color) if m.top_role else "#5a6387",

            "is_owner": m.id == guild.owner_id,

            "status": str(m.status),

        })

    out.sort(key=lambda x: x["joined_at"] or "", reverse=True)

    return jsonify({"members": out})

@app.route("/api/guild/<guild_id>/settings", methods=["GET", "POST"])

def api_guild_settings(guild_id):

    guild, member = require_guild_admin(guild_id)

    if not guild:

        return jsonify({"error": "forbidden"}), 403

    if request.method == "POST":

        body = request.get_json(silent=True) or {}

        new_prefix = (body.get("prefix") or "").strip()

        if not new_prefix or len(new_prefix) > 5:

            return jsonify({"error": "invalid_prefix"}), 400

        _prefix_cache[guild.id] = new_prefix

        _save_prefixes()

        return jsonify({"ok": True, "prefix": new_prefix})

    return jsonify({"prefix": _prefix_cache.get(guild.id, DEFAULT_PREFIX)})

@app.route("/api/guild/<guild_id>/channels")

def api_guild_channels(guild_id):

    guild, member = require_guild_admin(guild_id)

    if not guild:

        return jsonify({"error": "forbidden"}), 403

    chans = [{"id": str(c.id), "name": c.name} for c in guild.text_channels]

    chans.sort(key=lambda c: c["name"])

    return jsonify({"channels": chans})

@app.route("/api/guild/<guild_id>/roles")

def api_guild_roles(guild_id):

    guild, member = require_guild_admin(guild_id)

    if not guild:

        return jsonify({"error": "forbidden"}), 403

    roles = [{"id": str(r.id), "name": r.name, "color": str(r.color)} for r in guild.roles if r.name != "@everyone" and not r.managed]

    roles.sort(key=lambda r: r["name"].lower())

    return jsonify({"roles": roles})

@app.route("/api/guild/<guild_id>/security/antilink", methods=["GET", "POST"])

def api_security_antilink(guild_id):

    guild, member = require_guild_admin(guild_id)

    if not guild:

        return jsonify({"error": "forbidden"}), 403

    gid = str(guild.id)

    if request.method == "POST":

        body = request.get_json(silent=True) or {}

        act = (body.get("action") or "delete").strip().lower()

        if act not in ("delete", "warn", "kick", "ban"):

            act = "delete"

        wl = [w.strip() for w in (body.get("whitelist") or []) if isinstance(w, str) and w.strip()][:30]

        enabled = bool(body.get("enabled"))

        data = jload(FILES["antilink"])

        data[gid] = {"enabled": enabled, "action": act, "whitelist": wl}

        jsave(FILES["antilink"], data)

        return jsonify({"ok": True, **data[gid]})

    cfg = jload(FILES["antilink"]).get(gid, {})

    return jsonify({

        "enabled": cfg.get("enabled", False),

        "action": cfg.get("action", "delete"),

        "whitelist": cfg.get("whitelist", []),

    })

@app.route("/api/guild/<guild_id>/security/antiraid", methods=["GET", "POST"])

def api_security_antiraid(guild_id):

    guild, member = require_guild_admin(guild_id)

    if not guild:

        return jsonify({"error": "forbidden"}), 403

    if request.method == "POST":

        body = request.get_json(silent=True) or {}

        cfg = get_server_config(guild.id)

        ar = cfg.setdefault("antiraid", {})

        try:

            ar["spam"] = bool(body.get("spam", ar.get("spam", False)))

            ar["spam_threshold"] = max(1, int(body.get("spam_threshold", ar.get("spam_threshold", DEFAULT_SPAM_THRESHOLD))))

            ar["spam_interval"] = max(1, int(body.get("spam_interval", ar.get("spam_interval", DEFAULT_SPAM_INTERVAL))))

            sa = str(body.get("spam_action", ar.get("spam_action", "timeout"))).lower()

            ar["spam_action"] = sa if sa in ("timeout", "kick", "ban") else "timeout"

            ar["mention"] = bool(body.get("mention", ar.get("mention", False)))

            ar["mention_limit"] = max(1, int(body.get("mention_limit", ar.get("mention_limit", DEFAULT_MENTION_LIMIT))))

            ma = str(body.get("mention_action", ar.get("mention_action", "timeout"))).lower()

            ar["mention_action"] = ma if ma in ("timeout", "kick", "ban") else "timeout"

            ar["join"] = bool(body.get("join", ar.get("join", False)))

            ar["join_threshold"] = max(1, int(body.get("join_threshold", ar.get("join_threshold", DEFAULT_JOIN_THRESHOLD))))

            ar["join_interval"] = max(1, int(body.get("join_interval", ar.get("join_interval", DEFAULT_JOIN_INTERVAL))))

            ja = str(body.get("join_action", ar.get("join_action", "log"))).lower()

            ar["join_action"] = ja if ja in ("log", "kick", "ban", "lockdown") else "log"

            ar["caps"] = bool(body.get("caps", ar.get("caps", False)))

            ar["caps_percent"] = max(1, min(100, int(body.get("caps_percent", ar.get("caps_percent", 70)))))

            ar["caps_min_length"] = max(1, int(body.get("caps_min_length", ar.get("caps_min_length", 10))))

            ar["emoji_spam"] = bool(body.get("emoji_spam", ar.get("emoji_spam", False)))

            ar["max_emojis"] = max(1, int(body.get("max_emojis", ar.get("max_emojis", 5))))

            modlog = body.get("modlog")

            if modlog:

                ar["modlog"] = int(modlog)

            elif "modlog" in body:

                ar.pop("modlog", None)

        except (TypeError, ValueError):

            return jsonify({"error": "invalid_value"}), 400

        save_server_config(guild.id, cfg)

        return jsonify({"ok": True, **ar})

    ar = get_server_config(guild.id).get("antiraid", {})

    return jsonify({

        "spam": ar.get("spam", False), "spam_threshold": ar.get("spam_threshold", DEFAULT_SPAM_THRESHOLD),

        "spam_interval": ar.get("spam_interval", DEFAULT_SPAM_INTERVAL), "spam_action": ar.get("spam_action", "timeout"),

        "mention": ar.get("mention", False), "mention_limit": ar.get("mention_limit", DEFAULT_MENTION_LIMIT),

        "mention_action": ar.get("mention_action", "timeout"),

        "join": ar.get("join", False), "join_threshold": ar.get("join_threshold", DEFAULT_JOIN_THRESHOLD),

        "join_interval": ar.get("join_interval", DEFAULT_JOIN_INTERVAL), "join_action": ar.get("join_action", "log"),

        "caps": ar.get("caps", False), "caps_percent": ar.get("caps_percent", 70), "caps_min_length": ar.get("caps_min_length", 10),

        "emoji_spam": ar.get("emoji_spam", False), "max_emojis": ar.get("max_emojis", 5),

        "modlog": ar.get("modlog"),

    })

@app.route("/api/guild/<guild_id>/security/verification", methods=["GET", "POST"])

def api_security_verification(guild_id):

    guild, member = require_guild_admin(guild_id)

    if not guild:

        return jsonify({"error": "forbidden"}), 403

    gid = str(guild.id)

    if request.method == "POST":

        body = request.get_json(silent=True) or {}

        data = _load_captcha()

        cfg = data.setdefault(gid, {})

        try:

            cfg["enabled"] = bool(body.get("enabled", False))

            ch = body.get("channel_id")

            cfg["channel_id"] = int(ch) if ch else None

            vr = body.get("verified_role")

            cfg["verified_role"] = int(vr) if vr else None

            ur = body.get("unverified_role")

            if ur:

                cfg["unverified_role"] = int(ur)

            else:

                cfg.pop("unverified_role", None)

            cfg["max_tries"] = max(1, min(10, int(body.get("max_tries", cfg.get("max_tries", 3)))))

        except (TypeError, ValueError):

            return jsonify({"error": "invalid_value"}), 400

        cfg["kick_on_fail"] = bool(body.get("kick_on_fail", False))

        msg = (body.get("welcome_message") or "").strip()

        cfg["welcome_message"] = msg[:500] if msg else "Bienvenue ! Tape le code ci-dessous pour accéder au serveur."

        _save_captcha(data)

        return jsonify({"ok": True, **cfg})

    cfg = _load_captcha().get(gid, {})

    return jsonify({

        "enabled": cfg.get("enabled", False),

        "channel_id": cfg.get("channel_id"),

        "verified_role": cfg.get("verified_role"),

        "unverified_role": cfg.get("unverified_role"),

        "max_tries": cfg.get("max_tries", 3),

        "kick_on_fail": cfg.get("kick_on_fail", False),

        "welcome_message": cfg.get("welcome_message", "Bienvenue ! Tape le code ci-dessous pour accéder au serveur."),

    })

def generate_token(discord_id):

    ts = str(int(time.time()))

    sig = hashlib.sha256((discord_id + ts + SECRET_KEY).encode()).hexdigest()

    return f"{discord_id}:{ts}:{sig}"

@app.route("/bot/premium/status")

def premium_status():

    did = request.args.get("id")

    if not did: return jsonify({"premium": False}), 400

    try:

        with open("/home/container/premium.json", "r") as f:

            pd = json.load(f)

    except: return jsonify({"premium": False})

    if did not in pd.get("users", {}): return jsonify({"premium": False})

    expiry = pd["users"][did]["expires_at"]

    now = int(time.time())

    return jsonify({"premium": expiry > now, "days_left": max(0, (expiry - now) // 86400)})

@app.route("/bot/stats")

def stats():

    if request.args.get("key") != API_TOKEN: return jsonify({"error": "unauthorized"}), 403

    return jsonify({"latence_ms": round(bot.latency*1000), "membres": sum(g.member_count for g in bot.guilds), "serveurs": len(bot.guilds)})

# ══════════════════════════════════════════════════════════════════════════════

# NOUVELLES COMMANDES — INFO SERVEUR

# ══════════════════════════════════════════════════════════════════════════════



@bot.command(name="uptime")

async def uptime_cmd(ctx):

    elapsed = int(_time.time() - _BOT_START_TIME)

    h, r = divmod(elapsed, 3600); m, s = divmod(r, 60)

    d, h = divmod(h, 24)

    parts = []

    if d: parts.append(f"{d}j")

    if h: parts.append(f"{h}h")

    if m: parts.append(f"{m}m")

    parts.append(f"{s}s")

    e = discord.Embed(title="⏱️ Uptime", description=f"**{'  '.join(parts)}**", color=C_BLUE)

    e.set_footer(text="Temps de fonctionnement depuis le dernier redémarrage")

    await ctx.send(embed=e)

@bot.command(name="banlist", aliases=["bans","listbans"])

async def banlist_cmd(ctx):

    if not ctx.author.guild_permissions.administrator and str(ctx.author.id) not in OWNER_IDS:

        return await ctx.send(embed=embed_err("Permission administrateur requise."))

    bans = [entry async for entry in ctx.guild.bans(limit=200)]

    if not bans:

        return await ctx.send(embed=embed_warn("Aucun membre banni sur ce serveur."))

    lines = [f"・ **{b.user}** (`{b.user.id}`){' — ' + b.reason if b.reason else ''}" for b in bans[:30]]

    e = discord.Embed(title=f"🔨 Banlist — {ctx.guild.name}", color=C_RED)

    e.description = "\n".join(lines)

    if len(bans) > 30:

        e.description += f"\n*... et {len(bans)-30} autres*"

    e.set_footer(text=f"{len(bans)} bannissement(s) total")

    await ctx.send(embed=e)

@bot.command(name="alladmins", aliases=["admins","listadmins"])

async def alladmins_cmd(ctx):

    admins = [m for m in ctx.guild.members if not m.bot and m.guild_permissions.administrator]

    if not admins:

        return await ctx.send(embed=embed_warn("Aucun administrateur trouvé."))

    e = discord.Embed(title=f"🛡️ Administrateurs — {ctx.guild.name}", color=C_RED)

    e.description = "\n".join(f"・ {m.mention} `{m.id}`" for m in admins[:30])

    e.set_footer(text=f"{len(admins)} administrateur(s)")

    await ctx.send(embed=e)

@bot.command(name="allbooster", aliases=["boosters","listboosters"])

async def allbooster_cmd(ctx):

    boosters = [m for m in ctx.guild.members if m.premium_since]

    if not boosters:

        return await ctx.send(embed=embed_warn("Aucun booster sur ce serveur."))

    e = discord.Embed(title=f"🚀 Boosters — {ctx.guild.name}", color=0xFF73FA)

    e.description = "\n".join(f"・ {m.mention} — boost depuis {discord.utils.format_dt(m.premium_since, style='R')}" for m in boosters[:30])

    e.set_footer(text=f"{len(boosters)} booster(s) • {ctx.guild.premium_subscription_count} boost(s) total")

    await ctx.send(embed=e)

@bot.command(name="allbots", aliases=["bots","listbots"])

async def allbots_cmd(ctx):

    bots = [m for m in ctx.guild.members if m.bot]

    if not bots:

        return await ctx.send(embed=embed_warn("Aucun bot sur ce serveur."))

    e = discord.Embed(title=f"🤖 Bots — {ctx.guild.name}", color=C_BLUE)

    e.description = "\n".join(f"・ {m.mention} `{m.id}`" for m in bots[:30])

    e.set_footer(text=f"{len(bots)} bot(s)")

    await ctx.send(embed=e)

@bot.command(name="allchannels", aliases=["channels","salons","listchannels"])

async def allchannels_cmd(ctx):

    cats = ctx.guild.by_category()

    lines = []

    for cat, channels in cats:

        if cat:

            lines.append(f"**📂 {cat.name}**")

        for ch in channels:

            ico = "🔊" if isinstance(ch, discord.VoiceChannel) else "💬"

            lines.append(f"  {ico} {ch.name}")

    if not lines:

        return await ctx.send(embed=embed_warn("Aucun salon trouvé."))

    chunks = []

    cur = ""

    for l in lines:

        if len(cur) + len(l) + 1 > 3900:

            chunks.append(cur); cur = l + "\n"

        else:

            cur += l + "\n"

    if cur: chunks.append(cur)

    for i, chunk in enumerate(chunks[:3]):

        e = discord.Embed(

            title=f"📺 Salons — {ctx.guild.name}" if i == 0 else "📺 (suite)",

            description=chunk, color=C_BLUE

        )

        e.set_footer(text=f"{len(ctx.guild.channels)} salon(s) total")

        await ctx.send(embed=e)

@bot.command(name="allroles", aliases=["listroles","tolesroles"])

async def allroles_cmd(ctx):

    roles = [r for r in reversed(ctx.guild.roles) if r.name != "@everyone"]

    if not roles:

        return await ctx.send(embed=embed_warn("Aucun rôle trouvé."))

    lines = [f"・ {r.mention} `{r.id}` — {len(r.members)} membre(s)" for r in roles[:40]]

    e = discord.Embed(title=f"🎭 Rôles — {ctx.guild.name}", color=C_BLUE)

    e.description = "\n".join(lines)

    if len(roles) > 40:

        e.description += f"\n*... et {len(roles)-40} autres*"

    e.set_footer(text=f"{len(roles)} rôle(s)")

    await ctx.send(embed=e)

@bot.command(name="allthreads", aliases=["threads","listthreads"])

async def allthreads_cmd(ctx):

    threads = ctx.guild.threads

    if not threads:

        return await ctx.send(embed=embed_warn("Aucun thread actif sur ce serveur."))

    lines = [f"・ **{t.name}** dans {t.parent.mention if t.parent else '?'} — {t.message_count} messages" for t in list(threads)[:30]]

    e = discord.Embed(title=f"🧵 Threads — {ctx.guild.name}", color=C_BLUE)

    e.description = "\n".join(lines)

    e.set_footer(text=f"{len(threads)} thread(s) actif(s)")

    await ctx.send(embed=e)

@bot.command(name="idemoji", aliases=["emojiid","emojis","emoji"])

async def idemoji_cmd(ctx, *, emoji_input: str = None):

    if not emoji_input:

        return await ctx.send(embed=embed_err("Usage : `+idemoji <emoji>`"))

    import re as _re

    custom = _re.findall(r'<a?:(\w+):(\d+)>', emoji_input)

    if custom:

        lines = [f"・ `:{name}:` — ID : `{eid}`" for name, eid in custom]

        e = discord.Embed(title="🆔 ID Emoji(s)", description="\n".join(lines), color=C_BLUE)

    else:

        e = discord.Embed(title="🆔 Emoji Unicode", description=f"・ `{emoji_input}` — Unicode : `{emoji_input.encode('unicode_escape').decode()}`", color=C_BLUE)

    await ctx.send(embed=e)

@bot.command(name="timestamp", aliases=["ts","time","heure"])

async def timestamp_cmd(ctx, *, dt_input: str = None):

    import datetime as _dt

    if dt_input:

        try:

            ts = int(dt_input)

        except:

            return await ctx.send(embed=embed_err("Usage : `+timestamp <unix_timestamp>` ou `+timestamp` pour maintenant"))

    else:

        ts = int(discord.utils.utcnow().timestamp())

    styles = [("t","Heure courte"),("T","Heure longue"),("d","Date courte"),("D","Date longue"),

              ("f","Date & heure"),("F","Date & heure complète"),("R","Relatif")]

    e = discord.Embed(title=f"⏰ Timestamp : `{ts}`", color=C_BLUE)

    for s, label in styles:

        e.add_field(name=label, value=f"`<t:{ts}:{s}>` → <t:{ts}:{s}>", inline=False)

    await ctx.send(embed=e)

@bot.command(name="onepage", aliases=["allcmds","allcommands","touteslescommandes"])

async def onepage_cmd(ctx):

    pfx = _prefix_cache.get(ctx.guild.id, DEFAULT_PREFIX) if ctx.guild else DEFAULT_PREFIX

    cmds = sorted(bot.commands, key=lambda c: c.name)

    lines = [f"`{pfx}{c.name}`" for c in cmds if not c.hidden]

    per_row = 4

    rows = [" • ".join(lines[i:i+per_row]) for i in range(0, len(lines), per_row)]

    chunks = []

    cur = ""

    for row in rows:

        if len(cur) + len(row) + 1 > 3900:

            chunks.append(cur); cur = row + "\n"

        else:

            cur += row + "\n"

    if cur: chunks.append(cur)

    for i, chunk in enumerate(chunks[:3]):

        e = discord.Embed(

            title=f"📖 Toutes les commandes ({len(lines)})" if i == 0 else "📖 (suite)",

            description=chunk, color=C_BLUE

        )

        e.set_footer(text=f"Préfixe : {pfx} • {len(lines)} commandes disponibles")

        await ctx.send(embed=e)

# ══════════════════════════════════════════════════════════════════════════════

# NOUVELLES COMMANDES — UTILITAIRES SERVEUR

# ══════════════════════════════════════════════════════════════════════════════

# Stockage en mémoire

_autoreact_cfg = {}   # guild_id → {channel_id: [emojis]}

_piconly_cfg   = {}   # guild_id → set of channel_id

_defaultroles  = {}   # guild_id → [role_id]

@bot.command(name="autoreact", aliases=["autoreaction","autoréaction"])

async def autoreact_cmd(ctx, action: str = None, channel: discord.TextChannel = None, *, emojis: str = None):

    if not ctx.author.guild_permissions.administrator and str(ctx.author.id) not in OWNER_IDS:

        return await ctx.send(embed=embed_err("Permission administrateur requise."))

    pfx = _prefix_cache.get(ctx.guild.id, DEFAULT_PREFIX)

    if not action:

        cfg = _autoreact_cfg.get(str(ctx.guild.id), {})

        if not cfg:

            return await ctx.send(embed=embed_warn(f"Aucune autoreaction configurée.\nUsage : `{pfx}autoreact add #salon 👍 👎`"))

        lines = [f"・ <#{cid}> → {' '.join(em)}" for cid, em in cfg.items()]

        return await ctx.send(embed=discord.Embed(title="⚡ Autoreactions", description="\n".join(lines), color=C_BLUE))

    action = action.lower()

    gid = str(ctx.guild.id)

    if action == "clear":

        _autoreact_cfg.pop(gid, None)

        return await ctx.send(embed=discord.Embed(description="🗑️ Toutes les autoreactions supprimées.", color=C_RED))

    if not channel:

        return await ctx.send(embed=embed_err(f"Usage : `{pfx}autoreact {action} #salon [emojis]`"))

    if action == "add":

        if not emojis:

            return await ctx.send(embed=embed_err("Précise au moins un emoji."))

        ems = emojis.split()[:5]

        _autoreact_cfg.setdefault(gid, {})[str(channel.id)] = ems

        await ctx.send(embed=discord.Embed(description=f"✅ Autoreactions ajoutées dans {channel.mention} : {' '.join(ems)}", color=C_GREEN))

    elif action == "remove":

        _autoreact_cfg.get(gid, {}).pop(str(channel.id), None)

        await ctx.send(embed=discord.Embed(description=f"✅ Autoreactions retirées de {channel.mention}.", color=C_GREEN))

    else:

        await ctx.send(embed=embed_err(f"Action invalide. Utilise `add`, `remove` ou `clear`."))

@bot.command(name="defaultrole", aliases=["defaultroles","rolesdefaut","roledefaut"])

async def defaultrole_cmd(ctx, *roles: discord.Role):

    if not ctx.author.guild_permissions.administrator and str(ctx.author.id) not in OWNER_IDS:

        return await ctx.send(embed=embed_err("Permission administrateur requise."))

    gid = str(ctx.guild.id)

    if not roles:

        ids = _defaultroles.get(gid, [])

        if not ids:

            return await ctx.send(embed=embed_warn("Aucun rôle par défaut configuré."))

        lines = [f"・ <@&{rid}>" for rid in ids]

        return await ctx.send(embed=discord.Embed(title="🎭 Rôles par défaut", description="\n".join(lines), color=C_BLUE))

    current = set(_defaultroles.get(gid, []))

    added = []; removed = []

    for role in roles:

        if role.id in current:

            current.remove(role.id); removed.append(role.mention)

        else:

            current.add(role.id); added.append(role.mention)

    _defaultroles[gid] = list(current)

    parts = []

    if added:   parts.append(f"✅ Ajoutés : {', '.join(added)}")

    if removed: parts.append(f"❌ Retirés : {', '.join(removed)}")

    await ctx.send(embed=discord.Embed(description="\n".join(parts), color=C_GREEN))

@bot.command(name="everping", aliases=["everyoneping","pingall"])

async def everping_cmd(ctx, *, message: str = None):

    if not ctx.author.guild_permissions.administrator and str(ctx.author.id) not in OWNER_IDS:

        return await ctx.send(embed=embed_err("Permission administrateur requise."))

    msg = message or "📢 Annonce importante !"

    await ctx.message.delete()

    # Seule commande autorisée à notifier : c'est son but, et elle est réservée aux admins.
    await ctx.send(f"@everyone\n{msg}",
                   allowed_mentions=discord.AllowedMentions(everyone=True, roles=False, users=True))

@bot.command(name="massiverole", aliases=["massrole","roleall","masserole"])

async def massiverole_cmd(ctx, action: str = None, target: str = None, role: discord.Role = None):

    if not ctx.author.guild_permissions.administrator and str(ctx.author.id) not in OWNER_IDS:

        return await ctx.send(embed=embed_err("Permission administrateur requise."))

    pfx = _prefix_cache.get(ctx.guild.id, DEFAULT_PREFIX)

    if not action or action.lower() not in ("add","remove") or not target or not role:

        return await ctx.send(embed=embed_err(f"Usage : `{pfx}massiverole <add/remove> <human/bot/all> <@rôle>`"))

    action = action.lower(); target = target.lower()

    if target == "human":   members = [m for m in ctx.guild.members if not m.bot]

    elif target == "bot":   members = [m for m in ctx.guild.members if m.bot]

    else:                   members = list(ctx.guild.members)

    msg = await ctx.send(embed=discord.Embed(description=f"⏳ {'Ajout' if action=='add' else 'Retrait'} du rôle {role.mention} à **{len(members)}** membre(s)...", color=C_ORANGE))

    count = 0

    for member in members:

        try:

            if action == "add" and role not in member.roles:

                await member.add_roles(role, reason=f"massiverole par {ctx.author}")

                count += 1

            elif action == "remove" and role in member.roles:

                await member.remove_roles(role, reason=f"massiverole par {ctx.author}")

                count += 1

        except: pass

    await msg.edit(embed=discord.Embed(description=f"✅ Rôle {role.mention} {'ajouté' if action=='add' else 'retiré'} à **{count}** membre(s).", color=C_GREEN))

@bot.command(name="piconly", aliases=["selfie","imageonly","photoonly"])

async def piconly_cmd(ctx, action: str = None, channel: discord.TextChannel = None):

    if not ctx.author.guild_permissions.administrator and str(ctx.author.id) not in OWNER_IDS:

        return await ctx.send(embed=embed_err("Permission administrateur requise."))

    gid = str(ctx.guild.id)

    if not action:

        ids = _piconly_cfg.get(gid, set())

        if not ids:

            return await ctx.send(embed=embed_warn("Aucun salon piconly configuré."))

        return await ctx.send(embed=discord.Embed(title="🖼️ Salons Piconly", description="\n".join(f"・ <#{c}>" for c in ids), color=C_BLUE))

    action = action.lower()

    if action == "clear":

        _piconly_cfg.pop(gid, None)

        return await ctx.send(embed=discord.Embed(description="🗑️ Tous les salons piconly supprimés.", color=C_RED))

    if not channel:

        return await ctx.send(embed=embed_err("Précise un salon."))

    if action == "add":

        _piconly_cfg.setdefault(gid, set()).add(channel.id)

        await ctx.send(embed=discord.Embed(description=f"✅ {channel.mention} est maintenant en mode piconly.", color=C_GREEN))

    elif action == "remove":

        _piconly_cfg.get(gid, set()).discard(channel.id)

        await ctx.send(embed=discord.Embed(description=f"✅ {channel.mention} n'est plus en mode piconly.", color=C_GREEN))

@bot.command(name="ghostping", aliases=["ghostpings","pingfantome"])

async def ghostping_cmd(ctx):

    gid = str(ctx.guild.id)

    e = discord.Embed(title="👻 Ghost Ping", color=C_BLUE)

    e.description = (

        "Le système de détection des ghost pings est actif.\n"

        "Quand un message mentionnant un membre est supprimé, le bot le signale dans les logs messages.\n\n"

        f"📋 Assure-toi que `+msglog on #salon` est configuré."

    )

    await ctx.send(embed=e)

# ══════════════════════════════════════════════════════════════════════════════

# JOIN TO CREATE — système complet

# ══════════════════════════════════════════════════════════════════════════════

_jtc_config  = {}  # guild_id → {"trigger_id": int, "category_id": int, "name": str}

_jtc_channels = {} # channel_id → owner_id (salons temporaires actifs)

class JtcModal(discord.ui.Modal, title="🔊 Configurer Join to Create"):

    trigger = discord.ui.TextInput(label="ID du salon déclencheur", placeholder="Rejoins ce salon → vocal créé", max_length=20)

    category = discord.ui.TextInput(label="ID de la catégorie (optionnel)", placeholder="Catégorie où créer les vocaux", max_length=20, required=False)

    name_tpl = discord.ui.TextInput(label="Nom du vocal ({username} disponible)", placeholder="Salon de {username}", max_length=50, required=False)

    def __init__(self, gid): super().__init__(); self.gid = gid

    async def on_submit(self, interaction):

        try:

            tid = int(self.trigger.value.strip())

        except:

            return await interaction.response.send_message(embed=embed_err("ID invalide."), ephemeral=True)

        cat_id = None

        if self.category.value.strip():

            try: cat_id = int(self.category.value.strip())

            except: pass

        _jtc_config[str(self.gid)] = {

            "trigger_id": tid,

            "category_id": cat_id,

            "name": self.name_tpl.value.strip() or "Salon de {username}"

        }

        await interaction.response.send_message(

            embed=embed_ok(f"✅ Join to Create configuré !\nSalon déclencheur : <#{tid}>"), ephemeral=True)

class JtcView(discord.ui.View):

    def __init__(self, ctx): super().__init__(timeout=None); self.ctx = ctx

    @discord.ui.button(label="⚙️ Configurer", style=discord.ButtonStyle.primary)

    async def btn_config(self, interaction, button):

        if interaction.user.id != self.ctx.author.id: return await interaction.response.send_message(embed=embed_err("Ce menu n'est pas pour toi."), ephemeral=True)

        await interaction.response.send_modal(JtcModal(interaction.guild.id))

    @discord.ui.button(label="❌ Désactiver", style=discord.ButtonStyle.danger)

    async def btn_off(self, interaction, button):

        if interaction.user.id != self.ctx.author.id: return await interaction.response.send_message(embed=embed_err("Ce menu n'est pas pour toi."), ephemeral=True)

        _jtc_config.pop(str(interaction.guild.id), None)

        await interaction.response.send_message(embed=embed_ok("Join to Create désactivé."), ephemeral=True)

    @discord.ui.button(label="📋 Statut", style=discord.ButtonStyle.secondary)

    async def btn_status(self, interaction, button):

        if interaction.user.id != self.ctx.author.id: return await interaction.response.send_message(embed=embed_err("Ce menu n'est pas pour toi."), ephemeral=True)

        cfg = _jtc_config.get(str(interaction.guild.id), {})

        e = discord.Embed(title="🔊 Join to Create", color=C_BLUE)

        if cfg:

            e.add_field(name="Déclencheur", value=f"<#{cfg['trigger_id']}>", inline=True)

            e.add_field(name="Catégorie", value=f"<#{cfg['category_id']}>" if cfg.get("category_id") else "Défaut", inline=True)

            e.add_field(name="Nom template", value=f"`{cfg.get('name','Salon de {username}')}`", inline=False)

            e.add_field(name="Salons actifs", value=str(len(_jtc_channels)), inline=True)

        else:

            e.description = "❌ Non configuré. Clique sur **Configurer**."

        await interaction.response.send_message(embed=e, ephemeral=True)

@bot.command(name="jointocreate", aliases=["j2c","jtc","vocaltemp","vocaltemporaire"])

async def jointocreate_cmd(ctx):

    if not ctx.author.guild_permissions.administrator and str(ctx.author.id) not in OWNER_IDS:

        return await ctx.send(embed=embed_err("Permission administrateur requise."))

    cfg = _jtc_config.get(str(ctx.guild.id), {})

    e = discord.Embed(title="🔊 Join to Create", color=C_BLUE)

    if cfg:

        e.description = f"✅ Actif — Déclencheur : <#{cfg['trigger_id']}>"

    else:

        e.description = "Configure un salon vocal déclencheur.\nQuand un membre le rejoint → un vocal temporaire est créé pour lui."

    await ctx.send(embed=e, view=JtcView(ctx))

# ══════════════════════════════════════════════════════════════════════════════

# STARBOARD — système complet

# ══════════════════════════════════════════════════════════════════════════════

_starboard_cfg = {}   # guild_id → {"channel_id": int, "seuil": int, "emoji": str}

_starboard_posted = {}  # guild_id → {message_id: star_message_id}

class StarboardModal(discord.ui.Modal, title="⭐ Configurer le Starboard"):

    channel = discord.ui.TextInput(label="ID du salon starboard", placeholder="Ex: 123456789", max_length=20)

    seuil   = discord.ui.TextInput(label="Nombre d'étoiles pour poster", placeholder="Ex: 3", max_length=3)

    emoji   = discord.ui.TextInput(label="Emoji (défaut: ⭐)", placeholder="⭐", max_length=10, required=False)

    def __init__(self, gid): super().__init__(); self.gid = gid

    async def on_submit(self, interaction):

        try:

            cid = int(self.channel.value.strip())

            seuil = int(self.seuil.value.strip())

        except:

            return await interaction.response.send_message(embed=embed_err("IDs invalides."), ephemeral=True)

        _starboard_cfg[str(self.gid)] = {

            "channel_id": cid, "seuil": seuil,

            "emoji": self.emoji.value.strip() or "⭐"

        }

        await interaction.response.send_message(

            embed=embed_ok(f"✅ Starboard configuré !\n<#{cid}> — seuil : **{seuil}** {self.emoji.value or '⭐'}"), ephemeral=True)

class StarboardView(discord.ui.View):

    def __init__(self, ctx): super().__init__(timeout=None); self.ctx = ctx

    @discord.ui.button(label="⚙️ Configurer", style=discord.ButtonStyle.primary)

    async def btn_config(self, interaction, button):

        if interaction.user.id != self.ctx.author.id: return await interaction.response.send_message(embed=embed_err("Ce menu n'est pas pour toi."), ephemeral=True)

        await interaction.response.send_modal(StarboardModal(interaction.guild.id))

    @discord.ui.button(label="❌ Désactiver", style=discord.ButtonStyle.danger)

    async def btn_off(self, interaction, button):

        if interaction.user.id != self.ctx.author.id: return await interaction.response.send_message(embed=embed_err("Ce menu n'est pas pour toi."), ephemeral=True)

        _starboard_cfg.pop(str(interaction.guild.id), None)

        await interaction.response.send_message(embed=embed_ok("Starboard désactivé."), ephemeral=True)

    @discord.ui.button(label="📋 Statut", style=discord.ButtonStyle.secondary)

    async def btn_status(self, interaction, button):

        if interaction.user.id != self.ctx.author.id: return await interaction.response.send_message(embed=embed_err("Ce menu n'est pas pour toi."), ephemeral=True)

        cfg = _starboard_cfg.get(str(interaction.guild.id), {})

        e = discord.Embed(title="⭐ Starboard", color=C_GOLD)

        if cfg:

            e.add_field(name="Salon", value=f"<#{cfg['channel_id']}>", inline=True)

            e.add_field(name="Seuil", value=str(cfg["seuil"]), inline=True)

            e.add_field(name="Emoji", value=cfg["emoji"], inline=True)

        else:

            e.description = "❌ Non configuré."

        await interaction.response.send_message(embed=e, ephemeral=True)

@bot.command(name="starboard", aliases=["starb","etoile"])

async def starboard_cmd(ctx):

    if not ctx.author.guild_permissions.administrator and str(ctx.author.id) not in OWNER_IDS:

        return await ctx.send(embed=embed_err("Permission administrateur requise."))

    cfg = _starboard_cfg.get(str(ctx.guild.id), {})

    e = discord.Embed(title="⭐ Starboard", color=C_GOLD)

    e.description = f"✅ Actif — <#{cfg['channel_id']}> — seuil : **{cfg['seuil']}** {cfg['emoji']}" if cfg else "❌ Non configuré."

    await ctx.send(embed=e, view=StarboardView(ctx))

# ══════════════════════════════════════════════════════════════════════════════

# ROLES PICKER — système complet

# ══════════════════════════════════════════════════════════════════════════════

_rolespicker_data = {}  # guild_id → {"panels": [{titre, desc, mode, roles:[{id,label,desc,emoji}]}]}

class RolesPickerCreateModal(discord.ui.Modal, title="🎭 Créer un menu de rôles"):

    titre   = discord.ui.TextInput(label="Titre du panel", placeholder="🎭 Choisis tes rôles", max_length=80)

    desc    = discord.ui.TextInput(label="Description", style=discord.TextStyle.paragraph, placeholder="Clique pour t'attribuer ou retirer un rôle", max_length=500, required=False)

    mode    = discord.ui.TextInput(label="Mode (bouton / select)", placeholder="bouton ou select", max_length=10)

    channel = discord.ui.TextInput(label="ID du salon où envoyer", placeholder="Ex: 123456789", max_length=20)

    roles   = discord.ui.TextInput(label="IDs des rôles (un par ligne, format: ID|Label|Emoji)", style=discord.TextStyle.paragraph,

        placeholder="123456|Gamer|🎮\n654321|Artiste|🎨", max_length=1000)

    def __init__(self, gid): super().__init__(); self.gid = gid

    async def on_submit(self, interaction):

        try: cid = int(self.channel.value.strip())

        except: return await interaction.response.send_message(embed=embed_err("ID salon invalide."), ephemeral=True)

        ch = interaction.guild.get_channel(cid)

        if not ch: return await interaction.response.send_message(embed=embed_err("Salon introuvable."), ephemeral=True)

        roles_cfg = []

        for line in self.roles.value.strip().split("\n"):

            parts = line.strip().split("|")

            if not parts[0].strip().isdigit(): continue

            rid = int(parts[0].strip())

            label = parts[1].strip() if len(parts) > 1 else str(rid)

            emoji = parts[2].strip() if len(parts) > 2 else None

            roles_cfg.append({"id": rid, "label": label, "emoji": emoji})

        if not roles_cfg:

            return await interaction.response.send_message(embed=embed_err("Aucun rôle valide détecté."), ephemeral=True)

        mode = self.mode.value.strip().lower()

        e = discord.Embed(title=self.titre.value, description=self.desc.value or "Clique pour t'attribuer un rôle.", color=C_BLUE)

        view = RolesPickerView(interaction.guild, roles_cfg, mode)

        await ch.send(embed=e, view=view)

        await interaction.response.send_message(embed=embed_ok(f"✅ Menu de rôles envoyé dans {ch.mention} !"), ephemeral=True)

class RolesPickerView(discord.ui.View):

    def __init__(self, guild, roles_cfg, mode="bouton"):

        super().__init__(timeout=None)

        if mode == "select":

            opts = [discord.SelectOption(label=r["label"], value=str(r["id"]), emoji=r.get("emoji")) for r in roles_cfg[:25]]

            sel = discord.ui.Select(placeholder="Choisis un rôle...", options=opts, min_values=0, max_values=min(len(opts),25))

            sel.callback = self._select_cb

            self.add_item(sel)

        else:

            for r in roles_cfg[:5]:

                btn = discord.ui.Button(label=r["label"], emoji=r.get("emoji"), style=discord.ButtonStyle.secondary)

                btn.callback = self._make_btn_cb(r["id"])

                self.add_item(btn)

        self.roles_cfg = roles_cfg; self.guild = guild

    def _make_btn_cb(self, role_id):

        async def cb(interaction):

            role = interaction.guild.get_role(role_id)

            if not role: return await interaction.response.send_message("❌ Rôle introuvable.", ephemeral=True)

            if role in interaction.user.roles:

                await interaction.user.remove_roles(role); msg = f"❌ Rôle **{role.name}** retiré."

            else:

                await interaction.user.add_roles(role); msg = f"✅ Rôle **{role.name}** attribué."

            await interaction.response.send_message(msg, ephemeral=True)

        return cb

    async def _select_cb(self, interaction):

        selected = [int(v) for v in interaction.data["values"]]

        added = []; removed = []

        for r_cfg in self.roles_cfg:

            role = interaction.guild.get_role(r_cfg["id"])

            if not role: continue

            if r_cfg["id"] in selected and role not in interaction.user.roles:

                await interaction.user.add_roles(role); added.append(role.name)

            elif r_cfg["id"] not in selected and role in interaction.user.roles:

                await interaction.user.remove_roles(role); removed.append(role.name)

        parts = []

        if added:   parts.append("✅ Ajoutés : " + ", ".join(added))

        if removed: parts.append("❌ Retirés : " + ", ".join(removed))

        await interaction.response.send_message("\n".join(parts) or "Aucun changement.", ephemeral=True)

@bot.command(name="rolespicker", aliases=["rolepicker","menuderoles","selectroles"])

async def rolespicker_cmd(ctx):

    if not ctx.author.guild_permissions.administrator and str(ctx.author.id) not in OWNER_IDS:

        return await ctx.send(embed=embed_err("Permission administrateur requise."))

    await ctx.send(embed=discord.Embed(

        title="🎭 Roles Picker",

        description="Crée un menu de rôles (boutons ou select menu).\n\nClique sur **Créer un panel** pour commencer.",

        color=C_BLUE

    ), view=RolesPickerMenuView(ctx))

class RolesPickerMenuView(discord.ui.View):

    def __init__(self, ctx): super().__init__(timeout=None); self.ctx = ctx

    @discord.ui.button(label="➕ Créer un panel", style=discord.ButtonStyle.success)

    async def btn_create(self, interaction, button):

        if interaction.user.id != self.ctx.author.id: return await interaction.response.send_message(embed=embed_err("Ce menu n'est pas pour toi."), ephemeral=True)

        await interaction.response.send_modal(RolesPickerCreateModal(interaction.guild.id))

# ══════════════════════════════════════════════════════════════════════════════

# SOUTIEN — système complet

# ══════════════════════════════════════════════════════════════════════════════

_soutien_cfg = {}  # guild_id → {"role_id": int, "server_link": str}

class SoutienModal(discord.ui.Modal, title="💙 Configurer le Soutien"):

    role    = discord.ui.TextInput(label="ID du rôle à donner aux soutiens", placeholder="Ex: 123456789", max_length=20)

    link    = discord.ui.TextInput(label="Lien du serveur de soutien", placeholder="https://discord.gg/...", max_length=100, required=False)

    def __init__(self, gid): super().__init__(); self.gid = gid

    async def on_submit(self, interaction):

        try: rid = int(self.role.value.strip())

        except: return await interaction.response.send_message(embed=embed_err("ID invalide."), ephemeral=True)

        _soutien_cfg[str(self.gid)] = {"role_id": rid, "server_link": self.link.value.strip()}

        await interaction.response.send_message(embed=embed_ok(f"✅ Système de soutien configuré ! Rôle : <@&{rid}>"), ephemeral=True)

@bot.command(name="soutien", aliases=["support-role","systemesoutien"])

async def soutien_cmd(ctx):

    if not ctx.author.guild_permissions.administrator and str(ctx.author.id) not in OWNER_IDS:

        return await ctx.send(embed=embed_err("Permission administrateur requise."))

    cfg = _soutien_cfg.get(str(ctx.guild.id), {})

    e = discord.Embed(title="💙 Système de Soutien", color=C_BLUE)

    if cfg:

        e.add_field(name="Rôle soutien", value=f"<@&{cfg['role_id']}>", inline=True)

        e.add_field(name="Lien serveur", value=cfg.get("server_link") or "Non défini", inline=True)

    else:

        e.description = "❌ Non configuré. Configure le rôle à attribuer aux membres qui soutiennent le serveur."

    view = discord.ui.View(timeout=None)

    btn = discord.ui.Button(label="⚙️ Configurer", style=discord.ButtonStyle.primary)

    async def _cb(interaction):

        if interaction.user.id != ctx.author.id: return await interaction.response.send_message(embed=embed_err("Ce menu n'est pas pour toi."), ephemeral=True)

        await interaction.response.send_modal(SoutienModal(interaction.guild.id))

    btn.callback = _cb

    view.add_item(btn)

    await ctx.send(embed=e, view=view)

# ══════════════════════════════════════════════════════════════════════════════

# SHOWPIC — afficher avatar auto à l'arrivée

# ══════════════════════════════════════════════════════════════════════════════

_showpic_cfg = {}  # guild_id → {"channel_id": int, "enabled": bool}

@bot.command(name="showpic", aliases=["showavatar","showprofile","autopfp"])

async def showpic_cmd(ctx):

    if not ctx.author.guild_permissions.administrator and str(ctx.author.id) not in OWNER_IDS:

        return await ctx.send(embed=embed_err("Permission administrateur requise."))

    gid = str(ctx.guild.id)

    cfg = _showpic_cfg.get(gid, {})

    e = discord.Embed(title="🖼️ Show Pic — Avatar auto à l'arrivée", color=C_BLUE)

    if cfg.get("enabled"):

        e.description = f"✅ Actif — Salon : <#{cfg.get('channel_id','?')}>"

    else:

        e.description = "❌ Désactivé — Configure un salon et active."

    view = discord.ui.View(timeout=None)

    async def _on_config(interaction):

        if interaction.user.id != ctx.author.id: return await interaction.response.send_message(embed=embed_err("Ce menu n'est pas pour toi."), ephemeral=True)

        class ShowpicModal(discord.ui.Modal, title="🖼️ ShowPic — Configurer"):

            channel_id = discord.ui.TextInput(label="ID du salon où poster les avatars", placeholder="Ex: 123456789", max_length=20)

            async def on_submit(self2, interaction2):

                try: cid = int(self2.channel_id.value.strip())

                except: return await interaction2.response.send_message(embed=embed_err("ID invalide."), ephemeral=True)

                _showpic_cfg[gid] = {"channel_id": cid, "enabled": True}

                await interaction2.response.send_message(embed=embed_ok(f"✅ ShowPic actif dans <#{cid}> !"), ephemeral=True)

        await interaction.response.send_modal(ShowpicModal())

    async def _on_toggle(interaction):

        if interaction.user.id != ctx.author.id: return await interaction.response.send_message(embed=embed_err("Ce menu n'est pas pour toi."), ephemeral=True)

        cur = _showpic_cfg.get(gid, {}).get("enabled", False)

        _showpic_cfg.setdefault(gid, {})["enabled"] = not cur

        await interaction.response.send_message(embed=embed_ok(f"ShowPic **{'activé' if not cur else 'désactivé'}** !"), ephemeral=True)

    b1 = discord.ui.Button(label="⚙️ Configurer salon", style=discord.ButtonStyle.primary)

    b1.callback = _on_config

    b2 = discord.ui.Button(label="🔘 Activer/Désactiver", style=discord.ButtonStyle.secondary)

    b2.callback = _on_toggle

    view.add_item(b1); view.add_item(b2)

    await ctx.send(embed=e, view=view)

# ══════════════════════════════════════════════════════════════════════════════

# TAG SERVEUR

# ══════════════════════════════════════════════════════════════════════════════

_tag_cfg = {}  # guild_id → role_id

@bot.command(name="tag", aliases=["servertag","clantag"])

async def tag_cmd(ctx, *, role: discord.Role = None):

    if not ctx.author.guild_permissions.administrator and str(ctx.author.id) not in OWNER_IDS:

        return await ctx.send(embed=embed_err("Permission administrateur requise."))

    gid = str(ctx.guild.id)

    if not role:

        rid = _tag_cfg.get(gid)

        e = discord.Embed(title="🏷️ Tag Serveur", color=C_BLUE)

        e.description = (f"Rôle configuré : <@&{rid}>" if rid else "❌ Non configuré.") + "\n\nUsage : `+tag <@rôle>` — attribue ce rôle aux membres ayant le tag du serveur."

        return await ctx.send(embed=e)

    _tag_cfg[gid] = role.id

    await ctx.send(embed=embed_ok(f"✅ Rôle **{role.name}** configuré pour les membres avec le tag du serveur."))

# ══════════════════════════════════════════════════════════════════════════════

# JOINSETTINGS — récapitulatif des actions à l'arrivée

# ══════════════════════════════════════════════════════════════════════════════

@bot.command(name="joinsettings", aliases=["joinconfig","configjoin","arrivee"])

async def joinsettings_cmd(ctx):

    if not ctx.author.guild_permissions.administrator and str(ctx.author.id) not in OWNER_IDS:

        return await ctx.send(embed=embed_err("Permission administrateur requise."))

    pfx = _prefix_cache.get(ctx.guild.id, DEFAULT_PREFIX)

    gid = str(ctx.guild.id)

    w = jload(FILES["welcome"]).get(gid, {})

    dr = _defaultroles.get(gid, [])

    sp = _showpic_cfg.get(gid, {})

    jtc = _jtc_config.get(gid, {})

    e = discord.Embed(title="👋 Paramètres d'arrivée", color=C_BLUE)

    e.add_field(name="💬 Message bienvenue", value=f"✅ <#{w['channel_id']}>" if w.get("channel_id") and w.get("enabled",True) else f"❌ — `{pfx}welcome`", inline=False)

    e.add_field(name="🎭 Rôles par défaut", value=", ".join(f"<@&{r}>" for r in dr) if dr else f"❌ — `{pfx}defaultrole @rôle`", inline=False)

    e.add_field(name="📩 MP bienvenue", value="✅ Actif" if w.get("mp_enabled") else f"❌ — `{pfx}welcome` → MP", inline=False)

    e.add_field(name="🖼️ ShowPic", value=f"✅ <#{sp['channel_id']}>" if sp.get("enabled") else f"❌ — `{pfx}showpic`", inline=False)

    e.add_field(name="🔊 Join to Create", value=f"✅ <#{jtc['trigger_id']}>" if jtc.get("trigger_id") else f"❌ — `{pfx}jointocreate`", inline=False)

    e.add_field(name="📡 Log flux", value="Voir `+logs`", inline=False)

    await ctx.send(embed=e)

# ══════════════════════════════════════════════════════════════════════════════

# EMBEDS — sauvegarde basique

# ══════════════════════════════════════════════════════════════════════════════

_saved_embeds = {}  # user_id → [{title, desc, color, ...}]

# ══════════════════════════════════════════════════════════════════════════════
# COMMANDE +embed — Builder interactif (select menu + modals)
# ══════════════════════════════════════════════════════════════════════════════

_embed_sessions = {}  # user_id → dict de config de l'embed en cours

def _build_welcome_embed(extra: str = None) -> discord.Embed:
    desc = (
        "Bienvenue dans le **builder d'embed interactif** !\n\n"
        "📌 Utilisez le menu ci-dessous pour **personnaliser** votre embed en temps réel.\n"
        "🔍 Un aperçu se met à jour **automatiquement** à chaque modification.\n"
        "🚀 Quand vous êtes prêt, sélectionnez **Envoyer l'embed**.\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━"
    )
    if extra:
        desc += f"\n\n{extra}"
    e = discord.Embed(title="🛠️  Créateur d'Embed", description=desc, color=0x5865F2)
    e.set_footer(text="ModeraBot • Embed Builder", icon_url="https://cdn.discordapp.com/embed/avatars/0.png")
    return e

def _build_embed_preview(session: dict) -> discord.Embed:
    color = C_BLUE
    try:
        color = int(session.get("color", "#5865F2").replace("#", ""), 16)
    except: pass
    e = discord.Embed(color=color)
    if session.get("title"):       e.title       = session["title"]
    if session.get("description"): e.description = session["description"]
    if session.get("author"):      e.set_author(name=session["author"])
    if session.get("footer"):      e.set_footer(text=session["footer"])
    if session.get("thumbnail") and session["thumbnail"].strip():
        e.set_thumbnail(url=session["thumbnail"])
    if session.get("image") and session["image"].strip():
        e.set_image(url=session["image"])
    if session.get("url") and session.get("title"):
        e.url = session["url"]
    if session.get("timestamp"):
        e.timestamp = discord.utils.utcnow()
    for f in session.get("fields", []):
        e.add_field(name=f["name"], value=f["value"], inline=f.get("inline", False))
    # Discord rejette un embed sans contenu visible
    has_content = (
        e.title or e.description or e.fields or
        (e.author and e.author.name) or
        (e.footer and e.footer.text) or
        (e.image and e.image.url) or
        (e.thumbnail and e.thumbnail.url)
    )
    if not has_content:
        e.description = "*Aperçu de ton embed — utilise le menu pour le personnaliser.*"
    return e

# ── Modals ────────────────────────────────────────────────────────────────────

class DcpEmbedTitleModal(discord.ui.Modal, title="✏️ Modifier le Titre"):
    val = discord.ui.TextInput(label="Titre", placeholder="Ex: Annonce importante", max_length=256, required=False)
    def __init__(self, uid): super().__init__(); self.uid = uid
    async def on_submit(self, interaction):
        _embed_sessions.setdefault(self.uid, {})["title"] = self.val.value or None
        e = _build_embed_preview(_embed_sessions[self.uid])
        await interaction.response.edit_message(embeds=[_build_welcome_embed(), e], view=DcpEmbedView(self.uid))

class DcpEmbedDescModal(discord.ui.Modal, title="📝 Modifier la Description"):
    val = discord.ui.TextInput(label="Description", style=discord.TextStyle.paragraph, placeholder="Texte principal de l'embed", max_length=2000, required=False)
    def __init__(self, uid): super().__init__(); self.uid = uid
    async def on_submit(self, interaction):
        _embed_sessions.setdefault(self.uid, {})["description"] = self.val.value or None
        e = _build_embed_preview(_embed_sessions[self.uid])
        await interaction.response.edit_message(embeds=[_build_welcome_embed(), e], view=DcpEmbedView(self.uid))

class DcpEmbedAuthorModal(discord.ui.Modal, title="👤 Modifier l'Auteur"):
    val = discord.ui.TextInput(label="Nom de l'auteur", placeholder="Ex: ModeraBot", max_length=256, required=False)
    def __init__(self, uid): super().__init__(); self.uid = uid
    async def on_submit(self, interaction):
        _embed_sessions.setdefault(self.uid, {})["author"] = self.val.value or None
        e = _build_embed_preview(_embed_sessions[self.uid])
        await interaction.response.edit_message(embeds=[_build_welcome_embed(), e], view=DcpEmbedView(self.uid))

class DcpEmbedFooterModal(discord.ui.Modal, title="📄 Modifier le Footer"):
    val = discord.ui.TextInput(label="Texte du footer", placeholder="Ex: © ModeraBot 2026", max_length=2048, required=False)
    def __init__(self, uid): super().__init__(); self.uid = uid
    async def on_submit(self, interaction):
        _embed_sessions.setdefault(self.uid, {})["footer"] = self.val.value or None
        e = _build_embed_preview(_embed_sessions[self.uid])
        await interaction.response.edit_message(embeds=[_build_welcome_embed(), e], view=DcpEmbedView(self.uid))

class DcpEmbedThumbnailModal(discord.ui.Modal, title="🖼️ Modifier le Thumbnail"):
    val = discord.ui.TextInput(label="URL du thumbnail", placeholder="https://exemple.com/image.png", max_length=500, required=False)
    def __init__(self, uid): super().__init__(); self.uid = uid
    async def on_submit(self, interaction):
        _embed_sessions.setdefault(self.uid, {})["thumbnail"] = self.val.value.strip() or None
        e = _build_embed_preview(_embed_sessions[self.uid])
        await interaction.response.edit_message(embeds=[_build_welcome_embed(), e], view=DcpEmbedView(self.uid))

class DcpEmbedImageModal(discord.ui.Modal, title="📸 Modifier l'Image"):
    val = discord.ui.TextInput(label="URL de l'image principale", placeholder="https://exemple.com/image.png", max_length=500, required=False)
    def __init__(self, uid): super().__init__(); self.uid = uid
    async def on_submit(self, interaction):
        _embed_sessions.setdefault(self.uid, {})["image"] = self.val.value.strip() or None
        e = _build_embed_preview(_embed_sessions[self.uid])
        await interaction.response.edit_message(embeds=[_build_welcome_embed(), e], view=DcpEmbedView(self.uid))

class DcpEmbedUrlModal(discord.ui.Modal, title="🔗 Modifier l'URL"):
    val = discord.ui.TextInput(label="URL cliquable du titre", placeholder="https://exemple.com", max_length=500, required=False)
    def __init__(self, uid): super().__init__(); self.uid = uid
    async def on_submit(self, interaction):
        _embed_sessions.setdefault(self.uid, {})["url"] = self.val.value.strip() or None
        e = _build_embed_preview(_embed_sessions[self.uid])
        await interaction.response.edit_message(embeds=[_build_welcome_embed(), e], view=DcpEmbedView(self.uid))

class DcpEmbedColorModal(discord.ui.Modal, title="🎨 Modifier la Couleur"):
    val = discord.ui.TextInput(label="Code hex (ex: #FF0000)", placeholder="#5865F2", max_length=7, required=False)
    def __init__(self, uid): super().__init__(); self.uid = uid
    async def on_submit(self, interaction):
        raw = self.val.value.strip()
        if raw and not re.match(r'^#[0-9A-Fa-f]{6}$', raw):
            return await interaction.response.send_message(embed=embed_err("Format invalide. Utilise un code hex comme `#FF0000`."), ephemeral=True)
        _embed_sessions.setdefault(self.uid, {})["color"] = raw or "#5865F2"
        e = _build_embed_preview(_embed_sessions[self.uid])
        await interaction.response.edit_message(embeds=[_build_welcome_embed(), e], view=DcpEmbedView(self.uid))

class DcpEmbedAddFieldModal(discord.ui.Modal, title="➕ Ajouter un Field"):
    val = discord.ui.TextInput(label="Nom | Valeur | true/false (inline optionnel)", placeholder="Nom | Valeur du field | false", max_length=500)
    def __init__(self, uid): super().__init__(); self.uid = uid
    async def on_submit(self, interaction):
        parts = self.val.value.split("|")
        if len(parts) < 2:
            return await interaction.response.send_message(embed=embed_err("Format : `Nom | Valeur` ou `Nom | Valeur | true`"), ephemeral=True)
        session = _embed_sessions.setdefault(self.uid, {})
        session.setdefault("fields", []).append({
            "name":   parts[0].strip(),
            "value":  parts[1].strip(),
            "inline": parts[2].strip().lower() == "true" if len(parts) > 2 else False
        })
        e = _build_embed_preview(session)
        await interaction.response.edit_message(embeds=[_build_welcome_embed(), e], view=DcpEmbedView(self.uid))

# ── View (select menu) ────────────────────────────────────────────────────────

class DcpEmbedView(discord.ui.View):

    def __init__(self, uid):

        super().__init__(timeout=None)

        self.uid = uid

        sel = discord.ui.Select(

            placeholder="🛠️ Choisissez une option...",

            options=[

                discord.SelectOption(label="Modifier le Titre",        emoji="✏️",  value="title",        description="Définir le titre principal de l'embed"),

                discord.SelectOption(label="Modifier la Description",   emoji="📝",  value="description",  description="Texte principal affiché dans l'embed"),

                discord.SelectOption(label="Modifier l'Auteur",         emoji="👤",  value="author",        description="Nom affiché en haut de l'embed"),

                discord.SelectOption(label="Modifier le Footer",        emoji="📄",  value="footer",        description="Texte affiché en bas de l'embed"),

                discord.SelectOption(label="Modifier le Thumbnail",     emoji="🖼️",  value="thumbnail",     description="Petite image à droite de l'embed"),

                discord.SelectOption(label="Modifier le Timestamp",     emoji="🕐",  value="timestamp",     description="Activer/désactiver la date et l'heure"),

                discord.SelectOption(label="Modifier l'Image",          emoji="📸",  value="image",         description="Grande image en bas de l'embed"),

                discord.SelectOption(label="Modifier l'URL",            emoji="🔗",  value="url",           description="Lien cliquable sur le titre"),

                discord.SelectOption(label="Modifier la Couleur",       emoji="🎨",  value="color",         description="Barre colorée sur le côté gauche"),

                discord.SelectOption(label="Ajouter un Field",          emoji="➕",  value="add_field",     description="Ajouter un champ Nom / Valeur"),

                discord.SelectOption(label="Supprimer un Field",        emoji="🗑️",  value="remove_field",  description="Supprimer le dernier field ajouté"),

                discord.SelectOption(label="✅  Envoyer l'embed",        emoji="🚀",  value="send",          description="Envoyer l'embed dans ce salon"),

            ]

        )

        sel.callback = self._on_select

        self.add_item(sel)

    async def _on_select(self, interaction: discord.Interaction):

        if interaction.user.id != self.uid:

            return await interaction.response.send_message(embed=embed_err("Ce menu n'est pas pour toi."), ephemeral=True)

        uid     = interaction.user.id

        session = _embed_sessions.setdefault(uid, {})

        choice  = interaction.data["values"][0]

        if choice == "timestamp":

            session["timestamp"] = not session.get("timestamp", False)

            e = _build_embed_preview(session)

            state = "activé ✅" if session["timestamp"] else "désactivé ❌"

            return await interaction.response.edit_message(embeds=[_build_welcome_embed(f"*Timestamp {state}*"), e], view=DcpEmbedView(uid))

        if choice == "remove_field":

            fields = session.get("fields", [])

            if not fields:

                return await interaction.response.send_message(embed=embed_err("Aucun field à supprimer."), ephemeral=True)

            fields.pop()

            e = _build_embed_preview(session)

            return await interaction.response.edit_message(embeds=[_build_welcome_embed(), e], view=DcpEmbedView(uid))

        if choice == "send":

            if not session.get("title") and not session.get("description"):

                return await interaction.response.send_message(embed=embed_err("L'embed doit avoir au moins un **titre** ou une **description**."), ephemeral=True)

            e = _build_embed_preview(session)

            await interaction.channel.send(embeds=[e])

            _embed_sessions.pop(uid, None)

            return await interaction.response.edit_message(content="🚀 **Embed envoyé !**", embeds=[], view=None)

        modal_map = {

            "title":       DcpEmbedTitleModal,

            "description": DcpEmbedDescModal,

            "author":      DcpEmbedAuthorModal,

            "footer":      DcpEmbedFooterModal,

            "thumbnail":   DcpEmbedThumbnailModal,

            "image":       DcpEmbedImageModal,

            "url":         DcpEmbedUrlModal,

            "color":       DcpEmbedColorModal,

            "add_field":   DcpEmbedAddFieldModal,

        }

        modal_cls = modal_map.get(choice)

        if modal_cls:

            await interaction.response.send_modal(modal_cls(uid))

# ── Commande +embed ───────────────────────────────────────────────────────────

@bot.command(name="embed", aliases=["embeed","embd"])

async def embed_cmd(ctx):

    if not is_modo(ctx.author):

        return await ctx.send(embed=embed_err("Tu n'as pas la permission."))

    uid = ctx.author.id

    _embed_sessions[uid] = {

        "title": None, "description": None, "author": None,

        "footer": None, "thumbnail": None, "timestamp": False,

        "image": None, "url": None, "color": "#5865F2", "fields": []

    }

    preview = _build_embed_preview(_embed_sessions[uid])

    await ctx.send(

        embeds=[_build_welcome_embed(), preview],

        view=DcpEmbedView(uid)

    )

@bot.command(name="embedlist", aliases=["mesembeds","listembeds"])

async def embedlist_cmd(ctx):

    uid = str(ctx.author.id)

    embeds = _saved_embeds.get(uid, [])

    if not embeds:

        return await ctx.send(embed=discord.Embed(description="📋 Aucun embed sauvegardé.\nUtilise `+embed` pour en créer.", color=C_BLUE))

    lines = [f"**{i+1}.** {emb.get('title','Sans titre')[:50]}" for i, emb in enumerate(embeds[:10])]

    await ctx.send(embed=discord.Embed(title=f"📋 Tes embeds ({len(embeds)})", description="\n".join(lines), color=C_BLUE))

@bot.command(name="clearembeds", aliases=["supprimerembeds","deleteembeds"])

async def clearembeds_cmd(ctx):

    _saved_embeds.pop(str(ctx.author.id), None)

    await ctx.send(embed=discord.Embed(description="🗑️ Tous tes embeds sauvegardés ont été supprimés.", color=C_RED))

@bot.command(name="sethelp", aliases=["helptype","typehelp","confighelp"])

async def sethelp_cmd(ctx, *, helptype: str = None):

    pfx = _prefix_cache.get(ctx.guild.id, DEFAULT_PREFIX)

    if not helptype or helptype not in ("compact","full"):

        return await ctx.send(embed=discord.Embed(

            title="⚙️ Type de Help",

            description=f"Usage : `{pfx}sethelp <type>`\nTypes : `compact` / `full`",

            color=C_BLUE))

    # Stocké en mémoire par serveur

    if not hasattr(bot, "_help_type"): bot._help_type = {}

    bot._help_type[str(ctx.guild.id)] = helptype

    await ctx.send(embed=embed_ok(f"✅ Type d'aide défini sur `{helptype}`."))

# ── Piconly enforcement ───────────────────────────────────────────────────────

# (vérifié dans on_message)

# ─── STARBOARD — reaction handler ─────────────────────────────────────────────

@bot.event

async def on_raw_reaction_add(payload):

    if not payload.guild_id: return

    gid = str(payload.guild_id)

    cfg = _starboard_cfg.get(gid, {})

    if not cfg: return

    emoji_str = str(payload.emoji)

    if emoji_str != cfg.get("emoji","⭐"): return

    guild = bot.get_guild(payload.guild_id)

    if not guild: return

    channel = guild.get_channel(payload.channel_id)

    if not channel or channel.id == cfg.get("channel_id"): return

    try: message = await channel.fetch_message(payload.message_id)

    except: return

    count = sum(r.count for r in message.reactions if str(r.emoji) == cfg["emoji"])

    if count < cfg.get("seuil", 3): return

    star_ch = guild.get_channel(cfg["channel_id"])

    if not star_ch: return

    posted = _starboard_posted.get(gid, {})

    if payload.message_id in posted:

        try:

            star_msg = await star_ch.fetch_message(posted[payload.message_id])

            await star_msg.edit(content=f"{cfg['emoji']} **{count}** | <#{channel.id}>")

        except: pass

        return

    e = discord.Embed(description=message.content or "*[fichier/image]*", color=C_GOLD)

    e.set_author(name=str(message.author), icon_url=message.author.display_avatar.url)

    e.add_field(name="Source", value=f"[Voir le message]({message.jump_url})")

    if message.attachments: e.set_image(url=message.attachments[0].url)

    sent = await star_ch.send(content=f"{cfg['emoji']} **{count}** | <#{channel.id}>", embed=e)

    _starboard_posted.setdefault(gid, {})[payload.message_id] = sent.id


# ══════════════════════════════════════════════════════════════════════════════
# BACKUP SERVEUR — +backup create / list / delete / info
# ══════════════════════════════════════════════════════════════════════════════

BACKUP_FILE        = "backups.json"
BACKUP_LIMIT_FREE  = 10   # gratuit
BACKUP_LIMIT_PREM  = 20   # premium

def _backup_limit(uid):
    return BACKUP_LIMIT_PREM if is_premium(uid) else BACKUP_LIMIT_FREE

def _load_backups():
    try:
        with open(BACKUP_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def _save_backups(data):
    with open(BACKUP_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def _snapshot_guild(guild: discord.Guild, name: str, author_id: int) -> dict:
    """Capture toutes les infos récupérables d'un serveur."""
    roles_data = []
    for r in guild.roles:
        if r.is_default(): continue
        roles_data.append({
            "id": str(r.id),
            "name": r.name,
            "color": r.color.value,
            "hoist": r.hoist,
            "mentionable": r.mentionable,
            "permissions": r.permissions.value,
            "position": r.position,
        })

    def _serialize_overwrites(overwrites: dict) -> list:
        """Sérialise les permission_overwrites d'un salon pour la sauvegarde."""
        result = []
        for target, overwrite in overwrites.items():
            allow, deny = overwrite.pair()
            is_role = isinstance(target, discord.Role)
            result.append({
                "id": str(target.id),
                "name": target.name,
                "default": bool(is_role and target.is_default()),
                "type": "role" if is_role else "member",
                "allow": allow.value,
                "deny": deny.value,
            })
        return result

    channels_data = []
    for ch in guild.channels:
        if isinstance(ch, discord.CategoryChannel):
            continue  # catégories traitées séparément
        entry = {
            "name": ch.name,
            "type": str(ch.type),
            "position": ch.position,
            "category": ch.category.name if ch.category else None,
            "overwrites": _serialize_overwrites(ch.overwrites),
            "sync_permissions": ch.permissions_synced if hasattr(ch, "permissions_synced") else False,
        }
        if isinstance(ch, discord.TextChannel):
            entry["topic"] = ch.topic
            entry["slowmode"] = ch.slowmode_delay
            entry["nsfw"] = ch.is_nsfw()
        elif isinstance(ch, discord.VoiceChannel):
            entry["bitrate"] = ch.bitrate
            entry["user_limit"] = ch.user_limit
        channels_data.append(entry)

    categories_data = []
    for c in guild.categories:
        categories_data.append({
            "name": c.name,
            "position": c.position,
            "overwrites": _serialize_overwrites(c.overwrites),
        })

    return {
        "id": str(guild.id),
        "name": guild.name,
        "snapshot_name": name,
        "created_by": author_id,
        "timestamp": int(time.time()),
        "member_count": guild.member_count,
        "icon_url": str(guild.icon.url) if guild.icon else None,
        "description": guild.description or "",
        "verification_level": str(guild.verification_level),
        "roles": roles_data,
        "channels": channels_data,
        "categories": categories_data,
        "role_count": len(roles_data),
        "channel_count": len(channels_data),
    }

def _fmt_backup_short(bk: dict, idx: int) -> str:
    ts = bk.get("timestamp", 0)
    dt = datetime.fromtimestamp(ts).strftime("%d/%m/%Y %H:%M")
    name = bk.get("snapshot_name", "Sans nom")
    srv  = bk.get("name", "?")
    return f"**#{idx}** — `{name}` | 🏠 {srv} | 📅 {dt}"

def _build_backup_list_embed(user_id: int) -> discord.Embed:
    data = _load_backups()
    bks  = data.get(str(user_id), [])
    e = discord.Embed(title="💾 Mes Backups", color=0x2ECC71)
    if not bks:
        e.description = "❌ Tu n'as aucune backup.\nUtilise **`+backup create`** pour en créer une."
        return e
    desc = f"Tu as **{len(bks)}/{_backup_limit(user_id)}** backups :\n\n"
    for i, bk in enumerate(bks, 1):
        ts   = bk.get("timestamp", 0)
        dt   = datetime.fromtimestamp(ts).strftime("%d/%m/%Y %H:%M")
        name = bk.get("snapshot_name", "Sans nom")
        srv  = bk.get("name", "?")
        roles_c = bk.get("role_count", "?")
        chan_c  = bk.get("channel_count", "?")
        members = bk.get("member_count", "?")
        desc += (
            f"**#{i}** ╸ `{name}`\n"
            f"  🏠 **{srv}** ・ 👥 {members} membres\n"
            f"  🎭 {roles_c} rôles ・ 📺 {chan_c} salons\n"
            f"  📅 {dt}\n\n"
        )
    e.description = desc.strip()
    e.set_footer(text="ModeraBot • +backup list pour restaurer / +backup delete pour supprimer")
    return e

async def _restore_guild(guild: discord.Guild, bk: dict) -> dict:
    """
    Recrée sur 'guild' les catégories, salons texte/vocal et rôles sauvegardés dans 'bk'.
    Restaure aussi les permissions des salons (overwrites).
    Retourne un dict de stats {"roles": int, "categories": int, "channels": int, "errors": list}.
    """
    stats  = {"roles": 0, "categories": 0, "channels": 0, "errors": []}
    cat_map = {}   # nom_catégorie → objet CategoryChannel créé

    # Ancien ID de rôle → nom (les IDs changent d'un serveur à l'autre)
    old_id_to_name = {}
    for rd in bk.get("roles", []):
        if rd.get("id"):
            old_id_to_name[str(rd["id"])] = rd.get("name", "")

    # Nom (minuscule) → rôle réel sur le serveur cible, rempli au fur et à mesure
    role_by_name = {r.name.lower(): r for r in guild.roles}

    def _resolve_role(entry):
        """Retrouve le rôle cible d'un overwrite malgré le changement d'IDs."""
        if entry.get("default"):
            return guild.default_role
        name = entry.get("name") or old_id_to_name.get(str(entry.get("id", "")), "")
        if name:
            if name == "@everyone":
                return guild.default_role
            r = role_by_name.get(name.lower())
            if r:
                return r
        try:
            return guild.get_role(int(entry["id"]))
        except Exception:
            return None

    def _build_overwrites(raw_list: list) -> dict:
        """Reconstruit les permission_overwrites depuis les données sauvegardées."""
        result = {}
        for entry in raw_list:
            allow = discord.Permissions(entry.get("allow", 0))
            deny  = discord.Permissions(entry.get("deny", 0))
            ow = discord.PermissionOverwrite.from_pair(allow, deny)
            if entry.get("type") == "role":
                role = _resolve_role(entry)
                if role:
                    result[role] = ow
            else:
                try:
                    member = guild.get_member(int(entry["id"]))
                except Exception:
                    member = None
                if member:
                    result[member] = ow
        return result

    # ── 1. Rôles ────────────────────────────────────────────────────────────────
    # Du plus bas au plus haut pour garder la hiérarchie d'origine
    my_top = guild.me.top_role.position if guild.me else 0
    for rd in sorted(bk.get("roles", []), key=lambda x: x.get("position", 0)):
        if rd.get("name", "").lower() in role_by_name:
            continue  # déjà présent : on le réutilisera pour les permissions
        try:
            perms = discord.Permissions(rd.get("permissions", 0))
            # On ne peut pas créer un rôle avec des permissions que le bot n'a pas
            perms.value &= guild.me.guild_permissions.value
            color = discord.Color(rd.get("color", 0))
            new_role = await guild.create_role(
                name=rd["name"],
                color=color,
                hoist=rd.get("hoist", False),
                mentionable=rd.get("mentionable", False),
                permissions=perms,
                reason="ModeraBot • Restauration backup"
            )
            role_by_name[new_role.name.lower()] = new_role
            stats["roles"] += 1
        except Exception as e:
            stats["errors"].append(f"Rôle `{rd['name']}` : {e}")

    # ── 2. Catégories ───────────────────────────────────────────────────────────
    existing_cat_names = {c.name.lower() for c in guild.categories}
    for cd in sorted(bk.get("categories", []), key=lambda x: x.get("position", 0)):
        if cd["name"].lower() in existing_cat_names:
            # Récupère l'existante pour mapper les salons
            for c in guild.categories:
                if c.name.lower() == cd["name"].lower():
                    cat_map[cd["name"]] = c
                    break
            continue
        try:
            raw_ow = cd.get("overwrites", [])
            ow = _build_overwrites(raw_ow) if raw_ow else {}
            cat = await guild.create_category(
                name=cd["name"],
                position=cd.get("position", 0),
                overwrites=ow if ow else discord.utils.MISSING,
                reason="ModeraBot • Restauration backup"
            )
            cat_map[cd["name"]] = cat
            stats["categories"] += 1
        except Exception as e:
            stats["errors"].append(f"Catégorie `{cd['name']}` : {e}")

    # ── 3. Salons ────────────────────────────────────────────────────────────────
    existing_ch_names = {c.name.lower() for c in guild.channels}
    for ch in sorted(bk.get("channels", []), key=lambda x: x.get("position", 0)):
        if ch["name"].lower() in existing_ch_names:
            continue
        cat_obj = cat_map.get(ch.get("category")) if ch.get("category") else None
        try:
            # Construire les overwrites
            raw_ow = ch.get("overwrites", [])
            ow = _build_overwrites(raw_ow) if raw_ow else {}
            # Si le salon est synchronisé à sa catégorie, on laisse Discord gérer
            sync_perm = ch.get("sync_permissions", False)

            ch_type = ch.get("type", "text")
            if "voice" in ch_type:
                new_ch = await guild.create_voice_channel(
                    name=ch["name"],
                    category=cat_obj,
                    bitrate=min(ch.get("bitrate", 64000), guild.bitrate_limit),
                    user_limit=ch.get("user_limit", 0),
                    position=ch.get("position", 0),
                    overwrites=ow if (ow and not sync_perm) else discord.utils.MISSING,
                    reason="ModeraBot • Restauration backup"
                )
            elif "stage" in ch_type:
                new_ch = await guild.create_stage_channel(
                    name=ch["name"],
                    category=cat_obj,
                    position=ch.get("position", 0),
                    overwrites=ow if (ow and not sync_perm) else discord.utils.MISSING,
                    reason="ModeraBot • Restauration backup"
                )
            else:
                new_ch = await guild.create_text_channel(
                    name=ch["name"],
                    category=cat_obj,
                    topic=ch.get("topic") or "",
                    slowmode_delay=ch.get("slowmode", 0),
                    nsfw=ch.get("nsfw", False),
                    position=ch.get("position", 0),
                    overwrites=ow if (ow and not sync_perm) else discord.utils.MISSING,
                    reason="ModeraBot • Restauration backup"
                )
            # Si les permissions étaient synchronisées à la catégorie, on sync
            if sync_perm and cat_obj and hasattr(new_ch, "edit"):
                try:
                    await new_ch.edit(sync_permissions=True)
                except:
                    pass
            stats["channels"] += 1
        except Exception as e:
            stats["errors"].append(f"Salon `{ch['name']}` : {e}")

    return stats


class _BackupRestoreConfirm(discord.ui.View):
    """Vue de confirmation avant de lancer la restauration."""
    def __init__(self, ctx, bk: dict, idx: int, parent_view):
        super().__init__(timeout=60)
        self.ctx         = ctx
        self.bk          = bk
        self.idx         = idx
        self.parent_view = parent_view

    @discord.ui.button(label="✅ Restaurer sur ce serveur", style=discord.ButtonStyle.success)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message(embed=embed_err("Ce menu n'est pas pour toi."), ephemeral=True)

        # Vérifie la perm administrateur sur le serveur cible
        if not interaction.guild.me.guild_permissions.administrator:
            return await interaction.response.send_message(
                embed=embed_err("Le bot n'a pas la permission **Administrateur** sur ce serveur.\nDonne-lui le rôle admin et réessaie."),
                ephemeral=True
            )

        name = self.bk.get("snapshot_name", "Sans nom")
        await interaction.response.edit_message(
            embed=discord.Embed(description=f"⏳ Restauration de **`{name}`** en cours...\n*Création des rôles, catégories et salons...*", color=C_BLUE),
            view=None
        )

        try:
            stats = await _restore_guild(interaction.guild, self.bk)
        except Exception as err:
            return await interaction.edit_original_response(
                embed=embed_err(f"Erreur pendant la restauration : `{err}`")
            )

        errs = stats["errors"]
        e = discord.Embed(title="✅ Restauration terminée !", color=0x2ECC71)
        e.add_field(name="🎭 Rôles créés",       value=str(stats["roles"]),      inline=True)
        e.add_field(name="📂 Catégories créées", value=str(stats["categories"]), inline=True)
        e.add_field(name="📺 Salons créés",      value=str(stats["channels"]),   inline=True)
        if errs:
            err_text = "\n".join(errs[:10])
            if len(errs) > 10: err_text += f"\n*...+{len(errs)-10} autres erreurs*"
            e.add_field(name=f"⚠️ {len(errs)} erreur(s)", value=err_text[:1024], inline=False)
        e.set_footer(text=f"Backup : {name} • ModeraBot")
        await interaction.edit_original_response(embed=e)

    @discord.ui.button(label="❌ Annuler", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message(embed=embed_err("Ce menu n'est pas pour toi."), ephemeral=True)
        await interaction.response.edit_message(
            embed=discord.Embed(description="❌ Restauration annulée.", color=C_ORANGE),
            view=self.parent_view
        )


class BackupRestoreView(discord.ui.View):
    """Menu déroulant pour choisir une backup à restaurer (liste)."""
    def __init__(self, ctx, backups: list):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.backups = backups
        opts = []
        for i, bk in enumerate(backups[:25], 1):
            ts   = bk.get("timestamp", 0)
            dt   = datetime.fromtimestamp(ts).strftime("%d/%m %H:%M")
            name = bk.get("snapshot_name", "Sans nom")[:50]
            srv  = bk.get("name", "?")[:30]
            opts.append(discord.SelectOption(
                label=f"#{i} — {name}",
                description=f"{srv} • {dt}",
                value=str(i - 1),
                emoji="💾"
            ))
        sel = discord.ui.Select(placeholder="Choisir une backup à restaurer...", options=opts)
        sel.callback = self._on_select
        self.add_item(sel)

    async def _on_select(self, interaction: discord.Interaction):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message(embed=embed_err("Ce menu n'est pas pour toi."), ephemeral=True)

        # Vérifie que l'utilisateur est admin sur ce serveur
        if not interaction.user.guild_permissions.administrator and str(interaction.user.id) not in OWNER_IDS:
            return await interaction.response.send_message(
                embed=embed_err("Tu dois être **Administrateur** sur ce serveur pour restaurer une backup."),
                ephemeral=True
            )

        idx  = int(interaction.data["values"][0])
        bk   = self.backups[idx]
        ts   = bk.get("timestamp", 0)
        dt   = datetime.fromtimestamp(ts).strftime("%d/%m/%Y à %H:%M")
        name = bk.get("snapshot_name", "Sans nom")
        srv  = bk.get("name", "?")

        # Embed de détails + bouton de confirmation
        e = discord.Embed(title=f"💾 Backup — {name}", color=0x2ECC71)
        e.add_field(name="🏠 Serveur capturé",  value=srv,                              inline=True)
        e.add_field(name="📅 Date",             value=dt,                               inline=True)
        e.add_field(name="👥 Membres",          value=str(bk.get("member_count","?")),  inline=True)
        e.add_field(name="🎭 Rôles",            value=str(bk.get("role_count","?")),    inline=True)
        e.add_field(name="📺 Salons",           value=str(bk.get("channel_count","?")), inline=True)
        e.add_field(name="🔒 Vérification",     value=bk.get("verification_level","?"), inline=True)
        if bk.get("description"):
            e.add_field(name="📝 Description", value=bk["description"][:200], inline=False)
        if bk.get("icon_url"):
            e.set_thumbnail(url=bk["icon_url"])

        roles = bk.get("roles", [])
        if roles:
            r_list = ", ".join(f"`{r['name']}`" for r in roles[:15])
            if len(roles) > 15: r_list += f" ... +{len(roles)-15}"
            e.add_field(name=f"🎭 Rôles ({len(roles)})", value=r_list, inline=False)

        cats = bk.get("categories", [])
        if cats:
            c_list = ", ".join(f"`{c['name']}`" for c in cats[:10])
            if len(cats) > 10: c_list += f" ... +{len(cats)-10}"
            e.add_field(name=f"📂 Catégories ({len(cats)})", value=c_list, inline=False)

        e.description = (
            f"⚠️ **Cette action va recréer les rôles, catégories et salons** de la backup sur **{interaction.guild.name}**.\n"
            f"Les éléments existants portant le même nom ne seront pas dupliqués.\n\n"
            f"Clique sur **Restaurer** pour confirmer."
        )
        e.set_footer(text=f"Backup #{idx+1} de {self.ctx.author.display_name}")

        confirm_view = _BackupRestoreConfirm(self.ctx, bk, idx, self)
        await interaction.response.edit_message(embed=e, view=confirm_view)

class BackupDeleteView(discord.ui.View):
    """Menu déroulant pour choisir une backup à supprimer."""
    def __init__(self, ctx, backups: list):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.backups = backups
        opts = []
        for i, bk in enumerate(backups[:25], 1):
            ts   = bk.get("timestamp", 0)
            dt   = datetime.fromtimestamp(ts).strftime("%d/%m %H:%M")
            name = bk.get("snapshot_name", "Sans nom")[:50]
            srv  = bk.get("name", "?")[:30]
            opts.append(discord.SelectOption(
                label=f"#{i} — {name}",
                description=f"{srv} • {dt}",
                value=str(i - 1),
                emoji="🗑️"
            ))
        sel = discord.ui.Select(placeholder="Choisir une backup à supprimer...", options=opts)
        sel.callback = self._on_select
        self.add_item(sel)

    async def _on_select(self, interaction: discord.Interaction):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message(embed=embed_err("Ce menu n'est pas pour toi."), ephemeral=True)
        idx  = int(interaction.data["values"][0])
        bk   = self.backups[idx]
        name = bk.get("snapshot_name", "Sans nom")
        # Confirmation
        confirm_view = _BackupDeleteConfirm(self.ctx, idx, name)
        e = discord.Embed(
            title="⚠️ Confirmer la suppression",
            description=f"Tu vas supprimer la backup **`{name}`**.\n\nCette action est **irréversible** !",
            color=C_RED
        )
        await interaction.response.edit_message(embed=e, view=confirm_view)

class _BackupDeleteConfirm(discord.ui.View):
    def __init__(self, ctx, idx: int, name: str):
        super().__init__(timeout=30)
        self.ctx  = ctx
        self.idx  = idx
        self.name = name

    @discord.ui.button(label="✅ Confirmer", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message(embed=embed_err("Ce menu n'est pas pour toi."), ephemeral=True)
        data = _load_backups()
        uid  = str(self.ctx.author.id)
        bks  = data.get(uid, [])
        if self.idx < len(bks):
            bks.pop(self.idx)
            data[uid] = bks
            _save_backups(data)
            await interaction.response.edit_message(
                embed=embed_ok(f"Backup **`{self.name}`** supprimée avec succès."),
                view=None
            )
        else:
            await interaction.response.edit_message(
                embed=embed_err("Backup introuvable, elle a peut-être déjà été supprimée."),
                view=None
            )

    @discord.ui.button(label="❌ Annuler", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message(embed=embed_err("Ce menu n'est pas pour toi."), ephemeral=True)
        await interaction.response.edit_message(
            embed=discord.Embed(description="❌ Suppression annulée.", color=C_ORANGE),
            view=None
        )

# ─── COMMANDE PRINCIPALE +backup ────────────────────────────────────────────

@bot.command(name="backup", aliases=["bkp","bk","backups","sauvegarde","sauvegarder","restaurer","restore","bck"])
async def backup_cmd(ctx, action: str = None, *, nom: str = None):
    pfx = _prefix_cache.get(ctx.guild.id, DEFAULT_PREFIX) if ctx.guild else DEFAULT_PREFIX
    uid = str(ctx.author.id)

    # ── Vérification Premium ─────────────────────────────────────────────────
    if not is_premium(ctx.author.id) and str(ctx.author.id) not in OWNER_IDS:
        e = discord.Embed(
            title="⭐ Commande Premium",
            description=(
                f"Le système **Backup Serveur** est réservé aux membres **Premium**.\n\n"
                f"👉 [Obtenir le Premium]({PREMIUM_LINK})\n"
                f"Ou active un code VIP avec **`{pfx}vip <code>`**"
            ),
            color=C_GOLD
        )
        e.set_footer(text="ModeraBot Premium • Backup System")
        return await ctx.send(embed=e)

    if action:
        a = action.lower().strip()
        # create
        if a in ("create","creer","créer","cree","crée","new","nouveau","nouv","add","ajouter","faire","save","sauv","sauvegarder","snapshot","snap","cr","c"):
            action = "create"
        # list
        elif a in ("list","liste","voir","show","afficher","ls","l","mes","mesliste","all"):
            action = "list"
        # delete
        elif a in ("delete","supprimer","supp","del","remove","retirer","effacer","rm","d","sup"):
            action = "delete"
        # info
        elif a in ("info","infos","detail","détail","details","détails","i","inf"):
            action = "info"
        else:
            action = None

    # ── Aide si pas d'action ─────────────────────────────────────────────────
    if not action:
        e = discord.Embed(title="💾 Backup Serveur", color=0x2ECC71)
        e.description = (
            f"Sauvegarde la configuration de ton serveur (rôles, salons, catégories).\n\n"
            f"**Commandes :**\n"
            f"・ **`{pfx}backup create [nom]`** — Créer une backup\n"
            f"・ **`{pfx}backup list`** — Voir & inspecter tes backups\n"
            f"・ **`{pfx}backup delete`** — Supprimer une backup\n"
            f"・ **`{pfx}backup info <numéro>`** — Détails d'une backup\n\n"
            f"📦 Limite : **{_backup_limit(str(ctx.author.id))} backups** par utilisateur (🆓 Gratuit: {BACKUP_LIMIT_FREE} | ⭐ Premium: {BACKUP_LIMIT_PREM})."
        )
        e.set_footer(text="ModeraBot • Backup System")
        return await ctx.send(embed=e)

    # ── CREATE ───────────────────────────────────────────────────────────────
    if action == "create":
        if not ctx.author.guild_permissions.administrator and str(ctx.author.id) not in OWNER_IDS:
            return await ctx.send(embed=embed_err("Tu dois être **Administrateur** pour créer une backup."))
        data = _load_backups()
        bks  = data.get(uid, [])
        limit = _backup_limit(uid)
        if len(bks) >= limit:
            if is_premium(uid):
                return await ctx.send(embed=embed_err(
                    f"Tu as atteint la limite de **{limit} backups**.\n"
                    f"Supprime-en une avec **`{pfx}backup delete`** avant d'en créer une nouvelle."
                ))
            else:
                return await ctx.send(embed=discord.Embed(
                    title="⭐ Limite atteinte !",
                    description=(
                        f"Tu as atteint la limite de **{limit} backups** (gratuit).\n\n"
                        f"🆓 **Gratuit :** {BACKUP_LIMIT_FREE} backups\n"
                        f"⭐ **Premium :** {BACKUP_LIMIT_PREM} backups\n\n"
                        f"Active le premium avec **`{pfx}premium`** pour doubler ta limite !"
                    ),
                    color=C_GOLD
                ))
        # Nom par défaut
        snap_name = nom.strip()[:50] if nom else f"Backup-{datetime.now().strftime('%d%m%y-%H%M')}"

        # Message de chargement
        msg_load = await ctx.send(embed=discord.Embed(
            description="⏳ Création de la backup en cours...",
            color=C_BLUE
        ))

        try:
            snapshot = _snapshot_guild(ctx.guild, snap_name, ctx.author.id)
        except Exception as err:
            await msg_load.delete()
            return await ctx.send(embed=embed_err(f"Erreur lors de la capture : `{err}`"))

        bks.append(snapshot)
        data[uid] = bks
        _save_backups(data)

        await msg_load.delete()

        e = discord.Embed(title="✅ Backup créée !", color=0x2ECC71)
        e.description = (
            f"**Nom :** `{snap_name}`\n"
            f"**Serveur :** {ctx.guild.name}\n"
            f"**Rôles :** {snapshot['role_count']}\n"
            f"**Salons :** {snapshot['channel_count']}\n"
            f"**Membres :** {snapshot['member_count']}\n"
            f"**Backup #{len(bks)}/{_backup_limit(uid)}**"
        )
        if ctx.guild.icon:
            e.set_thumbnail(url=ctx.guild.icon.url)
        e.set_footer(text=f"Créée par {ctx.author.display_name} • {datetime.now().strftime('%d/%m/%Y %H:%M')}")
        await ctx.send(embed=e)

    # ── LIST ─────────────────────────────────────────────────────────────────
    elif action == "list":
        data = _load_backups()
        bks  = data.get(uid, [])
        embed = _build_backup_list_embed(ctx.author.id)
        if not bks:
            return await ctx.send(embed=embed)
        view = BackupRestoreView(ctx, bks)
        await ctx.send(embed=embed, view=view)

    # ── DELETE ───────────────────────────────────────────────────────────────
    elif action == "delete":
        data = _load_backups()
        bks  = data.get(uid, [])
        if not bks:
            return await ctx.send(embed=embed_err("Tu n'as aucune backup à supprimer."))
        e = discord.Embed(
            title="🗑️ Supprimer une Backup",
            description=f"Tu as **{len(bks)}** backup(s).\nChoisis celle à supprimer dans le menu :",
            color=C_RED
        )
        view = BackupDeleteView(ctx, bks)
        await ctx.send(embed=e, view=view)

    # ── INFO ─────────────────────────────────────────────────────────────────
    elif action == "info":
        data = _load_backups()
        bks  = data.get(uid, [])
        if not bks:
            return await ctx.send(embed=embed_err("Tu n'as aucune backup."))
        # Récupérer le numéro (depuis 'nom' ou depuis la commande)
        try:
            num = int(nom.strip()) if nom else None
        except:
            num = None
        if not num or num < 1 or num > len(bks):
            return await ctx.send(embed=embed_err(
                f"Numéro invalide. Tu as {len(bks)} backup(s).\n"
                f"Usage : **`{pfx}backup info <numéro>`** (ex: `{pfx}backup info 1`)"
            ))
        bk   = bks[num - 1]
        ts   = bk.get("timestamp", 0)
        dt   = datetime.fromtimestamp(ts).strftime("%d/%m/%Y à %H:%M")
        name = bk.get("snapshot_name", "Sans nom")
        e = discord.Embed(title=f"💾 Backup #{num} — {name}", color=0x2ECC71)
        e.add_field(name="🏠 Serveur",      value=bk.get("name","?"),             inline=True)
        e.add_field(name="📅 Date",         value=dt,                              inline=True)
        e.add_field(name="👥 Membres",      value=str(bk.get("member_count","?")),inline=True)
        e.add_field(name="🎭 Rôles",        value=str(bk.get("role_count","?")),  inline=True)
        e.add_field(name="📺 Salons",       value=str(bk.get("channel_count","?")),inline=True)
        e.add_field(name="🔒 Vérification", value=bk.get("verification_level","?"),inline=True)
        if bk.get("description"):
            e.add_field(name="📝 Description", value=bk["description"][:200], inline=False)

        roles = bk.get("roles", [])
        if roles:
            r_list = " ".join(f"`{r['name']}`" for r in roles[:20])
            if len(roles) > 20: r_list += f" *+{len(roles)-20} autres*"
            e.add_field(name=f"🎭 Rôles ({len(roles)})", value=r_list, inline=False)

        cats = bk.get("categories", [])
        if cats:
            c_list = " ".join(f"`{c['name']}`" for c in cats[:15])
            if len(cats) > 15: c_list += f" *+{len(cats)-15} autres*"
            e.add_field(name=f"📂 Catégories ({len(cats)})", value=c_list, inline=False)

        if bk.get("icon_url"):
            e.set_thumbnail(url=bk["icon_url"])
        e.set_footer(text=f"ModeraBot • Backup {num}/{len(bks)}")
        await ctx.send(embed=e)




# ══════════════════════════════════════════════════════════════════════════════
# SYSTÈME CAPTCHA / VÉRIFICATION — +captcha
# ══════════════════════════════════════════════════════════════════════════════

CAPTCHA_FILE = "captcha_config.json"

def _load_captcha():
    try:
        with open(CAPTCHA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def _save_captcha(data):
    with open(CAPTCHA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

# Stocke les codes captcha en attente : member_id → {"code": str, "guild_id": int, "channel_id": int}
_captcha_pending = {}

def _gen_captcha_code(length=6):
    """Génère un code alphanumérique aléatoire."""
    chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "".join(random.choices(chars, k=length))

def _build_captcha_status_embed(guild_id):
    cfg = _load_captcha().get(str(guild_id), {})
    e = discord.Embed(title="🔐 Configuration Captcha / Vérification", color=0x5865F2)

    e.add_field(
        name="🔘 Statut",
        value="✅ Activé" if cfg.get("enabled") else "❌ Désactivé",
        inline=True
    )
    ch = cfg.get("channel_id")
    e.add_field(
        name="📺 Salon de vérification",
        value=f"<#{ch}>" if ch else "❌ Non défini",
        inline=True
    )
    role_v = cfg.get("verified_role")
    e.add_field(
        name="✅ Rôle vérifié",
        value=f"<@&{role_v}>" if role_v else "❌ Non défini",
        inline=True
    )
    role_u = cfg.get("unverified_role")
    e.add_field(
        name="🔒 Rôle non vérifié",
        value=f"<@&{role_u}>" if role_u else "❌ Non défini",
        inline=True
    )
    e.add_field(
        name="🎨 Style",
        value=f"`{cfg.get('style', 'texte')}`",
        inline=True
    )
    e.add_field(
        name="🔄 Tentatives max",
        value=str(cfg.get("max_tries", 3)),
        inline=True
    )
    msg = cfg.get("welcome_message", "Bienvenue ! Tape le code ci-dessous pour accéder au serveur.")
    e.add_field(
        name="💬 Message d'accueil",
        value=f"`{msg[:80]}`",
        inline=False
    )
    kick = cfg.get("kick_on_fail", False)
    e.add_field(
        name="👟 Kick si échec",
        value="✅ Oui" if kick else "❌ Non",
        inline=True
    )
    e.set_footer(text="ModeraBot • Captcha System")
    return e

# ─── Modals ──────────────────────────────────────────────────────────────────

class CaptchaConfigModal(discord.ui.Modal, title="🔐 Configurer le Captcha"):
    channel_id   = discord.ui.TextInput(label="ID du salon de vérification", placeholder="Ex: 123456789", max_length=20)
    verified_role= discord.ui.TextInput(label="ID du rôle VÉRIFIÉ (accès complet)", placeholder="Ex: 123456789", max_length=20)
    unverified_role = discord.ui.TextInput(label="ID du rôle NON VÉRIFIÉ (optionnel)", placeholder="Ex: 123456789 (laisser vide si non utilisé)", max_length=20, required=False)
    max_tries    = discord.ui.TextInput(label="Tentatives max (1-10)", placeholder="3", max_length=2, required=False)
    kick_on_fail = discord.ui.TextInput(label="Kick si échec ? (oui/non)", placeholder="non", max_length=3, required=False)

    def __init__(self, gid):
        super().__init__()
        self.gid = gid
        cfg = _load_captcha().get(str(gid), {})
        if cfg.get("channel_id"):    self.channel_id.default    = str(cfg["channel_id"])
        if cfg.get("verified_role"): self.verified_role.default  = str(cfg["verified_role"])
        if cfg.get("unverified_role"): self.unverified_role.default = str(cfg["unverified_role"])
        if cfg.get("max_tries"):     self.max_tries.default      = str(cfg["max_tries"])
        self.kick_on_fail.default = "oui" if cfg.get("kick_on_fail") else "non"

    async def on_submit(self, interaction: discord.Interaction):
        data = _load_captcha()
        cfg  = data.setdefault(str(self.gid), {})
        try:    cfg["channel_id"]    = int(self.channel_id.value.strip())
        except: return await interaction.response.send_message(embed=embed_err("ID salon invalide."), ephemeral=True)
        try:    cfg["verified_role"] = int(self.verified_role.value.strip())
        except: return await interaction.response.send_message(embed=embed_err("ID rôle vérifié invalide."), ephemeral=True)
        if self.unverified_role.value.strip():
            try:    cfg["unverified_role"] = int(self.unverified_role.value.strip())
            except: cfg.pop("unverified_role", None)
        else:
            cfg.pop("unverified_role", None)
        try:    cfg["max_tries"] = max(1, min(10, int(self.max_tries.value.strip())))
        except: cfg["max_tries"] = 3
        cfg["kick_on_fail"] = self.kick_on_fail.value.strip().lower() in ("oui","yes","o","y","1")
        _save_captcha(data)
        await interaction.response.send_message(embed=embed_ok("Configuration captcha sauvegardée !"), ephemeral=True)

class CaptchaMessageModal(discord.ui.Modal, title="💬 Message de vérification"):
    message = discord.ui.TextInput(
        label="Message affiché au nouveau membre",
        style=discord.TextStyle.paragraph,
        placeholder="Bienvenue ! Tape le code ci-dessous pour accéder au serveur.",
        max_length=500
    )
    def __init__(self, gid):
        super().__init__()
        self.gid = gid
        cfg = _load_captcha().get(str(gid), {})
        if cfg.get("welcome_message"): self.message.default = cfg["welcome_message"]

    async def on_submit(self, interaction: discord.Interaction):
        data = _load_captcha()
        data.setdefault(str(self.gid), {})["welcome_message"] = self.message.value
        _save_captcha(data)
        await interaction.response.send_message(embed=embed_ok("Message mis à jour !"), ephemeral=True)

class CaptchaStyleModal(discord.ui.Modal, title="🎨 Style du Captcha"):
    style = discord.ui.TextInput(
        label="Style : texte / embed / image",
        placeholder="embed",
        max_length=10
    )
    code_length = discord.ui.TextInput(
        label="Longueur du code (4-8 caractères)",
        placeholder="6",
        max_length=1,
        required=False
    )
    def __init__(self, gid):
        super().__init__()
        self.gid = gid
        cfg = _load_captcha().get(str(gid), {})
        self.style.default = cfg.get("style", "embed")
        self.code_length.default = str(cfg.get("code_length", 6))

    async def on_submit(self, interaction: discord.Interaction):
        s = self.style.value.strip().lower()
        if s not in ("texte","embed","image"): s = "embed"
        data = _load_captcha()
        cfg  = data.setdefault(str(self.gid), {})
        cfg["style"] = s
        try:    cfg["code_length"] = max(4, min(8, int(self.code_length.value.strip())))
        except: cfg["code_length"] = 6
        _save_captcha(data)
        await interaction.response.send_message(embed=embed_ok(f"Style : `{s}` | Longueur code : `{cfg['code_length']}`"), ephemeral=True)

# ─── View principale captcha ──────────────────────────────────────────────────

class CaptchaView(discord.ui.View):
    def __init__(self, ctx):
        super().__init__(timeout=None)
        self.ctx = ctx

    @discord.ui.select(placeholder="⚙️ Configurer le captcha...", options=[
        discord.SelectOption(label="Salon & Rôles",         emoji="📺", value="config",   description="Définir salon, rôle vérifié, tentatives"),
        discord.SelectOption(label="Message d'accueil",     emoji="💬", value="message",  description="Texte affiché au nouveau membre"),
        discord.SelectOption(label="Style du captcha",      emoji="🎨", value="style",    description="texte / embed + longueur du code"),
        discord.SelectOption(label="Activer / Désactiver",  emoji="🔘", value="toggle",   description="Toggle le système captcha"),
        discord.SelectOption(label="Envoyer le panel",      emoji="📤", value="sendpanel",description="Poster le panel dans le salon configuré"),
    ])
    async def select_cb(self, interaction: discord.Interaction, select: discord.ui.Select):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message(embed=embed_err("Ce menu n'est pas pour toi."), ephemeral=True)
        v   = select.values[0]
        gid = interaction.guild.id

        if v == "config":
            await interaction.response.send_modal(CaptchaConfigModal(gid))

        elif v == "message":
            await interaction.response.send_modal(CaptchaMessageModal(gid))

        elif v == "style":
            await interaction.response.send_modal(CaptchaStyleModal(gid))

        elif v == "toggle":
            data = _load_captcha()
            cfg  = data.setdefault(str(gid), {})
            cfg["enabled"] = not cfg.get("enabled", False)
            _save_captcha(data)
            state = "activé ✅" if cfg["enabled"] else "désactivé ❌"
            await interaction.response.send_message(embed=embed_ok(f"Captcha **{state}** !"), ephemeral=True)
            await interaction.message.edit(embed=_build_captcha_status_embed(gid))

        elif v == "sendpanel":
            data = _load_captcha()
            cfg  = data.get(str(gid), {})
            if not cfg.get("channel_id"):
                return await interaction.response.send_message(embed=embed_err("Configure d'abord le salon !"), ephemeral=True)
            if not cfg.get("verified_role"):
                return await interaction.response.send_message(embed=embed_err("Configure d'abord le rôle vérifié !"), ephemeral=True)
            ch = interaction.guild.get_channel(cfg["channel_id"])
            if not ch:
                return await interaction.response.send_message(embed=embed_err("Salon introuvable."), ephemeral=True)
            panel_e = discord.Embed(
                title="🔐 Vérification requise",
                description=(
                    f"{cfg.get('welcome_message', 'Bienvenue ! Clique sur le bouton pour recevoir ton code de vérification.')}\n\n"
                    f"🔢 Un code unique te sera envoyé en MP.\n"
                    f"📝 Tu devras le taper ici pour accéder au serveur."
                ),
                color=0x5865F2
            )
            if interaction.guild.icon:
                panel_e.set_thumbnail(url=interaction.guild.icon.url)
            panel_e.set_footer(text=f"{interaction.guild.name} • Système de vérification ModeraBot")
            await ch.send(embed=panel_e, view=CaptchaStartView(gid))
            await interaction.response.send_message(embed=embed_ok(f"Panel envoyé dans {ch.mention} !"), ephemeral=True)

    @discord.ui.button(label="📋 Voir config", style=discord.ButtonStyle.secondary, row=1)
    async def btn_status(self, interaction: discord.Interaction, button):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message(embed=embed_err("Ce menu n'est pas pour toi."), ephemeral=True)
        await interaction.response.send_message(embed=_build_captcha_status_embed(interaction.guild.id), ephemeral=True)

    @discord.ui.button(label="🔄 Actualiser", style=discord.ButtonStyle.secondary, row=1)
    async def btn_refresh(self, interaction: discord.Interaction, button):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message(embed=embed_err("Ce menu n'est pas pour toi."), ephemeral=True)
        await interaction.response.defer()
        await interaction.message.edit(embed=_build_captcha_status_embed(interaction.guild.id))

    @discord.ui.button(label="🗑️ Reset", style=discord.ButtonStyle.danger, row=1)
    async def btn_reset(self, interaction: discord.Interaction, button):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message(embed=embed_err("Ce menu n'est pas pour toi."), ephemeral=True)
        data = _load_captcha()
        data.pop(str(interaction.guild.id), None)
        _save_captcha(data)
        await interaction.response.send_message(embed=embed_ok("Configuration captcha réinitialisée."), ephemeral=True)

# ─── Panel public : bouton "Obtenir mon code" ─────────────────────────────────

class CaptchaStartView(discord.ui.View):
    """Panel posté dans le salon de vérif — bouton pour obtenir son code."""
    def __init__(self, guild_id):
        super().__init__(timeout=None)
        self.guild_id = guild_id

    @discord.ui.button(label="🔑 Obtenir mon code", style=discord.ButtonStyle.success, emoji="🔑", custom_id="captcha_start")
    async def start_btn(self, interaction: discord.Interaction, button):
        gid = str(interaction.guild.id)
        cfg = _load_captcha().get(gid, {})
        if not cfg.get("enabled"):
            return await interaction.response.send_message(embed=embed_err("Le système de vérification est désactivé."), ephemeral=True)

        member = interaction.user
        # Vérifier si déjà vérifié
        verified_role = interaction.guild.get_role(cfg.get("verified_role", 0))
        if verified_role and verified_role in member.roles:
            return await interaction.response.send_message(embed=discord.Embed(description="✅ Tu es déjà vérifié !", color=C_GREEN), ephemeral=True)

        # Générer le code
        length = cfg.get("code_length", 6)
        code   = _gen_captcha_code(length)
        _captcha_pending[member.id] = {
            "code":       code,
            "guild_id":   interaction.guild.id,
            "channel_id": interaction.channel.id,
            "tries":      0,
            "max_tries":  cfg.get("max_tries", 3),
        }

        # Envoyer le code en MP
        style = cfg.get("style", "embed")
        try:
            if style == "embed":
                e_mp = discord.Embed(title="🔐 Code de vérification", color=0x5865F2)
                e_mp.description = (
                    f"Ton code pour rejoindre **{interaction.guild.name}** :\n\n"
                    f"```\n{code}\n```\n\n"
                    f"Tape ce code dans le salon de vérification.\n"
                    f"⚠️ {cfg.get('max_tries', 3)} tentatives max."
                )
                if interaction.guild.icon:
                    e_mp.set_thumbnail(url=interaction.guild.icon.url)
                e_mp.set_footer(text="ModeraBot • Code valide jusqu'à ta vérification")
                await member.send(embed=e_mp)
            else:
                await member.send(
                    f"🔐 **Code de vérification pour {interaction.guild.name}**\n"
                    f"```\n{code}\n```\n"
                    f"Tape ce code dans le salon de vérification. ({cfg.get('max_tries',3)} tentatives max)"
                )
        except discord.Forbidden:
            return await interaction.response.send_message(
                embed=embed_err("Impossible de t'envoyer un MP !\nOuvre tes DMs puis réessaie."),
                ephemeral=True
            )

        await interaction.response.send_message(
            embed=discord.Embed(
                description=f"📩 Code envoyé en MP !\nTape-le ici pour être vérifié. ({cfg.get('max_tries',3)} tentatives max)",
                color=C_GREEN
            ),
            ephemeral=True
        )

# ─── Event : vérification du code tapé dans le salon ─────────────────────────

async def _handle_captcha_check(message: discord.Message):
    """Appelé dans on_message pour vérifier si un message est un code captcha."""
    if message.author.bot or not message.guild: return False

    uid = message.author.id
    if uid not in _captcha_pending: return False

    pending = _captcha_pending[uid]
    if pending["guild_id"] != message.guild.id: return False
    if pending["channel_id"] != message.channel.id: return False

    gid = str(message.guild.id)
    cfg = _load_captcha().get(gid, {})

    # Supprimer le message (garder le salon propre)
    try: await message.delete()
    except: pass

    code_entered = message.content.strip().upper()
    code_correct = pending["code"].upper()

    if code_entered == code_correct:
        # ✅ Code correct
        del _captcha_pending[uid]
        member = message.author

        # Donner le rôle vérifié
        verified_role = message.guild.get_role(cfg.get("verified_role", 0))
        if verified_role:
            try: await member.add_roles(verified_role, reason="Captcha ModeraBot ✅")
            except: pass

        # Retirer le rôle non vérifié
        unverified_role = message.guild.get_role(cfg.get("unverified_role", 0))
        if unverified_role and unverified_role in member.roles:
            try: await member.remove_roles(unverified_role, reason="Captcha ModeraBot ✅")
            except: pass

        e = discord.Embed(
            title="✅ Vérification réussie !",
            description=f"{member.mention} tu as accès au serveur. Bienvenue ! 🎉",
            color=C_GREEN
        )
        e.set_thumbnail(url=member.display_avatar.url)
        msg = await message.channel.send(embed=e)
        await asyncio.sleep(8)
        try: await msg.delete()
        except: pass

        return True

    else:
        # ❌ Mauvais code
        pending["tries"] += 1
        remaining = pending["max_tries"] - pending["tries"]

        if remaining <= 0:
            del _captcha_pending[uid]
            e = discord.Embed(
                title="❌ Vérification échouée",
                description=f"{message.author.mention} Tu as épuisé tes **{pending['max_tries']}** tentatives.",
                color=C_RED
            )
            msg = await message.channel.send(embed=e)
            # Kick si configuré
            if cfg.get("kick_on_fail"):
                await asyncio.sleep(3)
                try:
                    await message.author.kick(reason="Captcha ModeraBot — échec vérification")
                except: pass
            else:
                await asyncio.sleep(8)
                try: await msg.delete()
                except: pass
        else:
            e = discord.Embed(
                description=f"❌ Code incorrect ! Il te reste **{remaining}** tentative(s).",
                color=C_RED
            )
            msg = await message.channel.send(embed=e, delete_after=5)

        return True

# ─── Event : envoyer le captcha à l'arrivée automatiquement ──────────────────

async def _handle_captcha_join(member: discord.Member):
    """Appelé dans on_member_join pour gérer le captcha automatique."""
    gid = str(member.guild.id)
    cfg = _load_captcha().get(gid, {})

    if not cfg.get("enabled"): return
    if not cfg.get("channel_id"): return

    # Donner le rôle non vérifié si configuré
    unverified_role = member.guild.get_role(cfg.get("unverified_role", 0))
    if unverified_role:
        try: await member.add_roles(unverified_role, reason="Captcha — en attente de vérification")
        except: pass

    # Envoyer un MP au nouveau membre
    try:
        e_mp = discord.Embed(
            title=f"👋 Bienvenue sur {member.guild.name} !",
            description=(
                f"{cfg.get('welcome_message', 'Pour accéder au serveur, tu dois te vérifier.')}\n\n"
                f"📺 Va dans le salon de vérification et clique sur **Obtenir mon code**."
            ),
            color=0x5865F2
        )
        if member.guild.icon:
            e_mp.set_thumbnail(url=member.guild.icon.url)
        await member.send(embed=e_mp)
    except: pass

# ─── Commande +captcha ────────────────────────────────────────────────────────

@bot.command(name="captcha", aliases=["verif","verification","vérification","secu","securite","sécurité","captch","capt"])
async def captcha_cmd(ctx):
    if not ctx.author.guild_permissions.administrator and str(ctx.author.id) not in OWNER_IDS:
        return await ctx.send(embed=embed_err("Permission administrateur requise."))
    if not is_premium(str(ctx.author.id)):
        return await ctx.send(embed=discord.Embed(
            title="⭐ Fonctionnalité Premium",
            description=(
                "Le système **Captcha & Sécurité** est réservé aux membres **premium**.\n\n"
                f"Active le premium avec **`+premium`** pour y accéder !"
            ),
            color=C_GOLD
        ))
    await ctx.send(embed=_build_captcha_status_embed(ctx.guild.id), view=CaptchaView(ctx))

import json

# ══════════════════════════════════════════
# INVITE TRACKER
# ══════════════════════════════════════════

INVITES_FILE = "invites_data.json"

def invites_load():
    try:
        with open(INVITES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def invites_save(data):
    with open(INVITES_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

_invite_cache = {}  # guild_id -> {code: uses}

@bot.event
async def on_invite_create(invite):
    gid = str(invite.guild.id)
    if gid not in _invite_cache:
        _invite_cache[gid] = {}
    _invite_cache[gid][invite.code] = invite.uses

@bot.event
async def on_invite_delete(invite):
    gid = str(invite.guild.id)
    if gid in _invite_cache:
        _invite_cache[gid].pop(invite.code, None)

async def _get_inviter(guild, member):
    """Retourne (inviter_id, invite_code) ou (None, None)"""
    gid = str(guild.id)
    try:
        current_invites = await guild.invites()
    except:
        return None, None
    old = _invite_cache.get(gid, {})
    for inv in current_invites:
        old_uses = old.get(inv.code, 0)
        if inv.uses > old_uses:
            _invite_cache[gid] = {i.code: i.uses for i in current_invites}
            return str(inv.inviter.id) if inv.inviter else None, inv.code
    _invite_cache[gid] = {i.code: i.uses for i in current_invites}
    return None, None

def _get_member_invites(gid, uid):
    data = invites_load()
    g = data.get(str(gid), {})
    u = g.get(str(uid), {})
    real   = u.get("invites", 0)
    bonus  = u.get("bonus", 0)
    fake   = u.get("fake", 0)
    left   = u.get("left", 0)
    total  = real + bonus - fake - left
    return real, bonus, fake, left, total

# ─── on_member_join / on_member_remove pour tracker ─────────────────────────

_original_member_join = None

INVITESMESS_FILE = "invitesmess.json"

def invitesmess_load():
    try:
        with open(INVITESMESS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def invitesmess_save(data):
    with open(INVITESMESS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

async def _invite_on_member_join(member):
    gid = str(member.guild.id)
    inviter_id, code = await _get_inviter(member.guild, member)
    if inviter_id:
        data = invites_load()
        data.setdefault(gid, {}).setdefault(inviter_id, {"invites": 0, "bonus": 0, "fake": 0, "left": 0, "invited": []})
        data[gid][inviter_id]["invites"] += 1
        data[gid][inviter_id].setdefault("invited", [])
        if str(member.id) not in data[gid][inviter_id]["invited"]:
            data[gid][inviter_id]["invited"].append(str(member.id))
        # Stocker qui a invité ce membre
        data[gid].setdefault("_who_invited", {})[str(member.id)] = inviter_id
        invites_save(data)

        # ── Envoi du message invitesmess ──────────────────────────────
        cfg = invitesmess_load().get(gid, {})
        channel_id = cfg.get("channel_id")
        if channel_id:
            ch = member.guild.get_channel(int(channel_id))
            if ch:
                inviter_member = member.guild.get_member(int(inviter_id))
                inviter_name = inviter_member.display_name if inviter_member else f"ID:{inviter_id}"
                real, bonus, fake, left, total = _get_member_invites(member.guild.id, int(inviter_id))
                msg_template = cfg.get(
                    "message",
                    "**{membre}** a été invité par **{inviteur}** et celui-ci possède maintenant **{total} invitation(s)**."
                )
                msg_text = (
                    msg_template
                    .replace("{membre}", member.mention)
                    .replace("{membre_tag}", str(member))
                    .replace("{membre_nom}", member.display_name)
                    .replace("{inviteur}", inviter_member.mention if inviter_member else f"**{inviter_name}**")
                    .replace("{inviteur_tag}", str(inviter_member) if inviter_member else inviter_name)
                    .replace("{inviteur_nom}", inviter_name)
                    .replace("{total}", str(total))
                    .replace("{regulieres}", str(real))
                    .replace("{bonus}", str(bonus))
                    .replace("{fausses}", str(fake))
                    .replace("{partis}", str(left))
                    .replace("{serveur}", member.guild.name)
                )
                try:
                    await ch.send(msg_text)
                except: pass

async def _invite_on_member_remove(member):
    gid = str(member.guild.id)
    data = invites_load()
    inviter_id = data.get(gid, {}).get("_who_invited", {}).get(str(member.id))
    if inviter_id:
        data[gid].setdefault(inviter_id, {"invites": 0, "bonus": 0, "fake": 0, "left": 0})
        data[gid][inviter_id]["left"] = data[gid][inviter_id].get("left", 0) + 1
        invites_save(data)

# Patch on_member_join / on_member_remove pour ajouter le tracking sans écraser l'existant
_orig_join_listeners = list(bot.extra_events.get("on_member_join", []))
_orig_remove_listeners = list(bot.extra_events.get("on_member_remove", []))

@bot.listen("on_member_join")
async def invite_track_join(member):
    await _invite_on_member_join(member)
    # Mettre à jour le cache
    gid = str(member.guild.id)
    try:
        invs = await member.guild.invites()
        _invite_cache[gid] = {i.code: i.uses for i in invs}
    except: pass

@bot.listen("on_member_remove")
async def invite_track_remove(member):
    await _invite_on_member_remove(member)

@bot.listen("on_ready")
async def invite_cache_init():
    for guild in bot.guilds:
        try:
            invs = await guild.invites()
            _invite_cache[str(guild.id)] = {i.code: i.uses for i in invs}
        except: pass

# ─── +invites ────────────────────────────────────────────────────────────────

@bot.command(name="invites", aliases=["inv"])
async def invites_cmd(ctx, member: discord.Member = None):
    member = member or ctx.author
    real, bonus, fake, left, total = _get_member_invites(ctx.guild.id, member.id)
    e = discord.Embed(title=f"📨 Invitations de {member.display_name}", color=C_BLUE)
    e.add_field(name="Total", value=f"**{total}**", inline=True)
    e.add_field(name="Régulières", value=str(real), inline=True)
    e.add_field(name="Bonus", value=str(bonus), inline=True)
    e.add_field(name="Fausses", value=str(fake), inline=True)
    e.add_field(name="Partis", value=str(left), inline=True)
    e.set_thumbnail(url=member.display_avatar.url)
    await ctx.send(embed=e)

# ─── +leaderboard ─────────────────────────────────────────────────────────────

@bot.command(name="inviteleaderboard", aliases=["invitelb","inviteclassement","lbinvites","classementinvites"])
async def invite_leaderboard_cmd(ctx):
    data = invites_load()
    gid = str(ctx.guild.id)
    g = data.get(gid, {})
    scores = []
    for uid, u in g.items():
        if uid.startswith("_"): continue
        total = u.get("invites", 0) + u.get("bonus", 0) - u.get("fake", 0) - u.get("left", 0)
        scores.append((uid, total))
    scores.sort(key=lambda x: x[1], reverse=True)
    e = discord.Embed(title="🏆 Classement des invitations", color=C_GOLD)
    desc = ""
    medals = ["🥇", "🥈", "🥉"]
    for i, (uid, total) in enumerate(scores[:10]):
        medal = medals[i] if i < 3 else f"`{i+1}.`"
        member = ctx.guild.get_member(int(uid))
        name = member.display_name if member else f"ID:{uid}"
        desc += f"{medal} **{name}** — {total} invitations\n"
    e.description = desc or "Aucune donnée pour ce serveur."
    await ctx.send(embed=e)

# ─── +addinvites / +removeinvites ─────────────────────────────────────────────

@bot.command(name="addinvites", aliases=["addInvites","add-invites","ajouterinvites","ajoutinvites"])
async def addinvites_cmd(ctx, member: discord.Member = None, amount: int = None):
    if not ctx.author.guild_permissions.administrator and str(ctx.author.id) not in OWNER_IDS:
        return await ctx.send(embed=embed_err("Permission administrateur requise."))
    if not member or amount is None:
        return await ctx.send(embed=embed_err("Usage : `+addinvites @user nombre`"))
    data = invites_load()
    gid = str(ctx.guild.id)
    data.setdefault(gid, {}).setdefault(str(member.id), {"invites": 0, "bonus": 0, "fake": 0, "left": 0})
    data[gid][str(member.id)]["invites"] += amount
    invites_save(data)
    await ctx.send(embed=discord.Embed(description=f"✅ **+{amount}** invitations ajoutées à {member.mention}.", color=C_GREEN))

@bot.command(name="removeinvites", aliases=["removeInvites","remove-invites","retirinvites","suppinvites"])
async def removeinvites_cmd(ctx, member: discord.Member = None, amount: int = None):
    if not ctx.author.guild_permissions.administrator and str(ctx.author.id) not in OWNER_IDS:
        return await ctx.send(embed=embed_err("Permission administrateur requise."))
    if not member or amount is None:
        return await ctx.send(embed=embed_err("Usage : `+removeinvites @user nombre`"))
    data = invites_load()
    gid = str(ctx.guild.id)
    data.setdefault(gid, {}).setdefault(str(member.id), {"invites": 0, "bonus": 0, "fake": 0, "left": 0})
    data[gid][str(member.id)]["invites"] = max(0, data[gid][str(member.id)]["invites"] - amount)
    invites_save(data)
    await ctx.send(embed=discord.Embed(description=f"✅ **-{amount}** invitations retirées à {member.mention}.", color=C_GREEN))

@bot.command(name="resetinvites", aliases=["resetInvites","reset-invites","reinitinvites","clearinvites"])
async def resetinvites_cmd(ctx, member: discord.Member = None):
    if not ctx.author.guild_permissions.administrator and str(ctx.author.id) not in OWNER_IDS:
        return await ctx.send(embed=embed_err("Permission administrateur requise."))
    if not member:
        return await ctx.send(embed=embed_err("Usage : `+resetinvites @user`"))
    data = invites_load()
    gid = str(ctx.guild.id)
    data.setdefault(gid, {})[str(member.id)] = {"invites": 0, "bonus": 0, "fake": 0, "left": 0}
    invites_save(data)
    await ctx.send(embed=discord.Embed(description=f"✅ Invitations de {member.mention} réinitialisées.", color=C_GREEN))

# ─── +addbonus / +removebonus ─────────────────────────────────────────────────

@bot.command(name="addbonus", aliases=["addBonus","add-bonus","ajouterbonus","bonusadd"])
async def addbonus_cmd(ctx, member: discord.Member = None, amount: int = None):
    if not ctx.author.guild_permissions.administrator and str(ctx.author.id) not in OWNER_IDS:
        return await ctx.send(embed=embed_err("Permission administrateur requise."))
    if not member or amount is None:
        return await ctx.send(embed=embed_err("Usage : `+addbonus @user nombre`"))
    data = invites_load()
    gid = str(ctx.guild.id)
    data.setdefault(gid, {}).setdefault(str(member.id), {"invites": 0, "bonus": 0, "fake": 0, "left": 0})
    data[gid][str(member.id)]["bonus"] = data[gid][str(member.id)].get("bonus", 0) + amount
    invites_save(data)
    await ctx.send(embed=discord.Embed(description=f"✅ **+{amount}** bonus ajoutés à {member.mention}.", color=C_GREEN))

@bot.command(name="removebonus", aliases=["removeBonus","remove-bonus","retirerbonus","bonusremove"])
async def removebonus_cmd(ctx, member: discord.Member = None, amount: int = None):
    if not ctx.author.guild_permissions.administrator and str(ctx.author.id) not in OWNER_IDS:
        return await ctx.send(embed=embed_err("Permission administrateur requise."))
    if not member or amount is None:
        return await ctx.send(embed=embed_err("Usage : `+removebonus @user nombre`"))
    data = invites_load()
    gid = str(ctx.guild.id)
    data.setdefault(gid, {}).setdefault(str(member.id), {"invites": 0, "bonus": 0, "fake": 0, "left": 0})
    data[gid][str(member.id)]["bonus"] = max(0, data[gid][str(member.id)].get("bonus", 0) - amount)
    invites_save(data)
    await ctx.send(embed=discord.Embed(description=f"✅ **-{amount}** bonus retirés à {member.mention}.", color=C_GREEN))

# ─── +addfakeinvites / +removefakeinvites ─────────────────────────────────────

@bot.command(name="addfakeinvites", aliases=["addFakeInvites","add-fake-invites","fakeadd","ajouterfake"])
async def addfakeinvites_cmd(ctx, member: discord.Member = None, amount: int = None):
    if not ctx.author.guild_permissions.administrator and str(ctx.author.id) not in OWNER_IDS:
        return await ctx.send(embed=embed_err("Permission administrateur requise."))
    if not member or amount is None:
        return await ctx.send(embed=embed_err("Usage : `+addfakeinvites @user nombre`"))
    data = invites_load()
    gid = str(ctx.guild.id)
    data.setdefault(gid, {}).setdefault(str(member.id), {"invites": 0, "bonus": 0, "fake": 0, "left": 0})
    data[gid][str(member.id)]["fake"] = data[gid][str(member.id)].get("fake", 0) + amount
    invites_save(data)
    await ctx.send(embed=discord.Embed(description=f"✅ **+{amount}** fausses invitations ajoutées à {member.mention}.", color=C_GREEN))

@bot.command(name="removefakeinvites", aliases=["removeFakeInvites","remove-fake-invites","fakeremove","retrerfake"])
async def removefakeinvites_cmd(ctx, member: discord.Member = None, amount: int = None):
    if not ctx.author.guild_permissions.administrator and str(ctx.author.id) not in OWNER_IDS:
        return await ctx.send(embed=embed_err("Permission administrateur requise."))
    if not member or amount is None:
        return await ctx.send(embed=embed_err("Usage : `+removefakeinvites @user nombre`"))
    data = invites_load()
    gid = str(ctx.guild.id)
    data.setdefault(gid, {}).setdefault(str(member.id), {"invites": 0, "bonus": 0, "fake": 0, "left": 0})
    data[gid][str(member.id)]["fake"] = max(0, data[gid][str(member.id)].get("fake", 0) - amount)
    invites_save(data)
    await ctx.send(embed=discord.Embed(description=f"✅ **-{amount}** fausses invitations retirées à {member.mention}.", color=C_GREEN))

# ─── +syncinvites ──────────────────────────────────────────────────────────────

@bot.command(name="syncinvites", aliases=["syncInvites","sync-invites","syncinv","resyncinvites"])
async def syncinvites_cmd(ctx):
    if not ctx.author.guild_permissions.administrator and str(ctx.author.id) not in OWNER_IDS:
        return await ctx.send(embed=embed_err("Permission administrateur requise."))
    try:
        invs = await ctx.guild.invites()
        _invite_cache[str(ctx.guild.id)] = {i.code: i.uses for i in invs}
        await ctx.send(embed=discord.Embed(description=f"✅ Cache des invitations synchronisé ({len(invs)} codes).", color=C_GREEN))
    except:
        await ctx.send(embed=embed_err("Impossible de récupérer les invitations. Vérifie les permissions."))

# ─── +deleteinvite ─────────────────────────────────────────────────────────────

@bot.command(name="deleteinvite", aliases=["deleteInvite","delete-invite","supprimerlien","supinvite","delinvite"])
async def deleteinvite_cmd(ctx, code: str = None):
    if not ctx.author.guild_permissions.administrator and str(ctx.author.id) not in OWNER_IDS:
        return await ctx.send(embed=embed_err("Permission administrateur requise."))
    if not code:
        return await ctx.send(embed=embed_err("Usage : `+deleteinvite <code>`"))
    try:
        invites = await ctx.guild.invites()
        inv = next((i for i in invites if i.code == code), None)
        if not inv:
            return await ctx.send(embed=embed_err(f"Invitation `{code}` introuvable."))
        await inv.delete(reason=f"Supprimé par {ctx.author}")
        await ctx.send(embed=discord.Embed(description=f"✅ Invitation `{code}` supprimée.", color=C_GREEN))
    except:
        await ctx.send(embed=embed_err("Impossible de supprimer l'invitation."))

# ─── +purge-invite-codes ───────────────────────────────────────────────────────

@bot.command(name="purge-invite-codes", aliases=["purgeinvites"])
async def purgeinvitecodes_cmd(ctx):
    if not ctx.author.guild_permissions.administrator and str(ctx.author.id) not in OWNER_IDS:
        return await ctx.send(embed=embed_err("Permission administrateur requise."))
    try:
        invites = await ctx.guild.invites()
        deleted = 0
        for inv in invites:
            if inv.max_uses > 0 and inv.uses >= inv.max_uses:
                try:
                    await inv.delete(reason="Purge codes expirés")
                    deleted += 1
                except: pass
        await ctx.send(embed=discord.Embed(description=f"✅ **{deleted}** code(s) d'invitation expirés supprimés.", color=C_GREEN))
    except:
        await ctx.send(embed=embed_err("Impossible de récupérer les invitations."))


# ─── +exportleaderboard ────────────────────────────────────────────────────────

@bot.command(name="exportleaderboard", aliases=["exportLB","export-lb","exportlb"])
async def exportleaderboard_cmd(ctx):
    if not ctx.author.guild_permissions.administrator and str(ctx.author.id) not in OWNER_IDS:
        return await ctx.send(embed=embed_err("Permission administrateur requise."))
    data = invites_load()
    gid = str(ctx.guild.id)
    g = data.get(gid, {})
    scores = []
    for uid, u in g.items():
        if uid.startswith("_"): continue
        total = u.get("invites", 0) + u.get("bonus", 0) - u.get("fake", 0) - u.get("left", 0)
        member = ctx.guild.get_member(int(uid))
        name = member.display_name if member else f"ID:{uid}"
        scores.append((name, uid, total, u.get("invites",0), u.get("bonus",0), u.get("fake",0), u.get("left",0)))
    scores.sort(key=lambda x: x[2], reverse=True)
    lines = ["Rang,Nom,ID,Total,Regulieres,Bonus,Fausses,Partis"]
    for i, (name, uid, total, reg, bon, fake, left) in enumerate(scores, 1):
        lines.append(f"{i},{name},{uid},{total},{reg},{bon},{fake},{left}")
    content = "\n".join(lines)
    import io
    buf = io.BytesIO(content.encode("utf-8"))
    buf.seek(0)
    await ctx.send(
        embed=discord.Embed(description="✅ Export du classement généré.", color=C_GREEN),
        file=discord.File(buf, filename=f"leaderboard_{ctx.guild.id}.csv")
    )

# ─── +exportinvitedlist ────────────────────────────────────────────────────────

@bot.command(name="exportinvitedlist", aliases=["exportInvited","export-invited","listeinvites","exportinvited"])
async def exportinvitedlist_cmd(ctx, member: discord.Member = None):
    if not ctx.author.guild_permissions.administrator and str(ctx.author.id) not in OWNER_IDS:
        return await ctx.send(embed=embed_err("Permission administrateur requise."))
    if not member:
        return await ctx.send(embed=embed_err("Usage : `+exportinvitedlist @user`"))
    data = invites_load()
    gid = str(ctx.guild.id)
    invited = data.get(gid, {}).get(str(member.id), {}).get("invited", [])
    if not invited:
        return await ctx.send(embed=embed_err(f"{member.mention} n'a invité personne encore."))
    lines = ["ID,Nom"]
    for uid in invited:
        m = ctx.guild.get_member(int(uid))
        name = m.display_name if m else f"ID:{uid}"
        lines.append(f"{uid},{name}")
    content = "\n".join(lines)
    import io
    buf = io.BytesIO(content.encode("utf-8"))
    buf.seek(0)
    await ctx.send(
        embed=discord.Embed(description=f"✅ Liste des membres invités par {member.mention}.", color=C_GREEN),
        file=discord.File(buf, filename=f"invited_{member.id}.csv")
    )



# ══════════════════════════════════════════
# INVITESMESS — Style Welcome
# ══════════════════════════════════════════

# ─── Modals ───────────────────────────────────────────────────────────────────

class ModalInvitesmessChannel(discord.ui.Modal, title="🏷️ Salon du message d'invitation"):

    channel_id = discord.ui.TextInput(label="ID ou mention du salon", placeholder="Ex: 123456789012345678", max_length=100)

    def __init__(self, gid):

        super().__init__(); self.gid = gid

        cfg = invitesmess_load().get(str(gid), {})

        if cfg.get("channel_id"): self.channel_id.default = str(cfg["channel_id"])

    async def on_submit(self, interaction):

        raw = self.channel_id.value.strip().strip("<#>")

        try: cid = int(raw)

        except:

            return await interaction.response.send_message(embed=embed_err("ID de salon invalide."), ephemeral=True)

        channel = interaction.guild.get_channel(cid)

        if not channel:

            return await interaction.response.send_message(embed=embed_err("Salon introuvable sur ce serveur."), ephemeral=True)

        cfg = invitesmess_load(); cfg.setdefault(str(self.gid), {})["channel_id"] = str(cid)

        invitesmess_save(cfg)

        await interaction.response.send_message(embed=embed_ok(f"Salon défini : {channel.mention}"), ephemeral=True)


class ModalInvitesmessMessage(discord.ui.Modal, title="💬 Message d'invitation"):

    message = discord.ui.TextInput(

        label="Message",

        style=discord.TextStyle.paragraph,

        placeholder="{membre} a été invité par {inviteur} — {total} invitation(s) !",

        max_length=1000

    )

    def __init__(self, gid):

        super().__init__(); self.gid = gid

        cfg = invitesmess_load().get(str(gid), {})

        if cfg.get("message"): self.message.default = cfg["message"]

    async def on_submit(self, interaction):

        cfg = invitesmess_load(); cfg.setdefault(str(self.gid), {})["message"] = self.message.value

        invitesmess_save(cfg)

        await interaction.response.send_message(embed=embed_ok("Message mis à jour !"), ephemeral=True)


# ─── Status embed ──────────────────────────────────────────────────────────────

def build_invitesmess_status_embed(guild_id):

    cfg = invitesmess_load().get(str(guild_id), {})

    e = discord.Embed(title="📨 Configuration — Invitesmess", color=C_BLUE)

    channel_id = cfg.get("channel_id")

    ch_val = f"<#{channel_id}>" if channel_id else "❌ Non défini"

    e.add_field(name="📺 Salon", value=ch_val, inline=True)

    e.add_field(name="🔘 Statut", value="✅ Actif" if (channel_id and cfg.get("enabled", True)) else "❌ Désactivé", inline=True)

    msg = cfg.get("message", "**{membre}** a été invité par **{inviteur}** et celui-ci possède maintenant **{total} invitation(s)**.")

    e.add_field(name="💬 Message", value=f"`{msg[:120]}`{'...' if len(msg) > 120 else ''}", inline=False)

    e.add_field(

        name="📋 Variables disponibles",

        value=(

            "`{membre}` `{membre_tag}` `{membre_nom}`\n"

            "`{inviteur}` `{inviteur_tag}` `{inviteur_nom}`\n"

            "`{total}` `{regulieres}` `{bonus}` `{fausses}` `{partis}` `{serveur}`"

        ),

        inline=False

    )

    e.set_footer(text="ModeraBot • Invitesmess")

    return e


# ─── View ──────────────────────────────────────────────────────────────────────

class InvitesmessView(discord.ui.View):

    def __init__(self, ctx):

        super().__init__(timeout=None)

        self.ctx = ctx

    @discord.ui.select(placeholder="⚙️ Configurer invitesmess...", row=0, options=[

        discord.SelectOption(label="Salon du message", emoji="🏷️", value="channel", description="Où envoyer le message"),

        discord.SelectOption(label="Personnaliser le message", emoji="💬", value="message", description="Texte envoyé à chaque invitation"),

        discord.SelectOption(label="Activer / Désactiver", emoji="🔘", value="toggle", description="Toggle tout le système"),

    ])

    async def select_cb(self, interaction: discord.Interaction, select: discord.ui.Select):

        if interaction.user.id != self.ctx.author.id:

            return await interaction.response.send_message(embed=embed_err("Ce menu n'est pas pour toi."), ephemeral=True)

        v = select.values[0]; gid = interaction.guild.id

        if v == "channel":

            await interaction.response.send_modal(ModalInvitesmessChannel(gid))

        elif v == "message":

            await interaction.response.send_modal(ModalInvitesmessMessage(gid))

        elif v == "toggle":

            cfg = invitesmess_load(); cfg.setdefault(str(gid), {})

            cur = cfg[str(gid)].get("enabled", True)

            cfg[str(gid)]["enabled"] = not cur

            invitesmess_save(cfg)

            await interaction.response.send_message(

                embed=embed_ok(f"Invitesmess **{'activé' if not cur else 'désactivé'}** !"),

                ephemeral=True

            )

    @discord.ui.button(label="📋 Voir config", style=discord.ButtonStyle.secondary, row=1)

    async def btn_status(self, interaction: discord.Interaction, button):

        if interaction.user.id != self.ctx.author.id:

            return await interaction.response.send_message(embed=embed_err("Ce menu n'est pas pour toi."), ephemeral=True)

        await interaction.response.send_message(embed=build_invitesmess_status_embed(interaction.guild.id), ephemeral=True)

    @discord.ui.button(label="🔄 Actualiser", style=discord.ButtonStyle.secondary, row=1)

    async def btn_refresh(self, interaction: discord.Interaction, button):

        if interaction.user.id != self.ctx.author.id:

            return await interaction.response.send_message(embed=embed_err("Ce menu n'est pas pour toi."), ephemeral=True)

        await interaction.response.defer()

        await interaction.message.edit(embed=build_invitesmess_status_embed(interaction.guild.id))

    @discord.ui.button(label="🗑️ Reset", style=discord.ButtonStyle.danger, row=1)

    async def btn_reset(self, interaction: discord.Interaction, button):

        if interaction.user.id != self.ctx.author.id:

            return await interaction.response.send_message(embed=embed_err("Ce menu n'est pas pour toi."), ephemeral=True)

        cfg = invitesmess_load(); cfg.pop(str(interaction.guild.id), None)

        invitesmess_save(cfg)

        await interaction.response.send_message(embed=embed_ok("Configuration invitesmess réinitialisée."), ephemeral=True)


# ─── Commande ──────────────────────────────────────────────────────────────────

@bot.command(name="invitesmess", aliases=["invitemessage","invmess","invitesmessage","invites-mess","configureinvitemsg"])


async def invitesmess_cmd(ctx):

    if not ctx.author.guild_permissions.administrator and str(ctx.author.id) not in OWNER_IDS:

        return await ctx.send(embed=embed_err("Permission administrateur requise."))

    await ctx.send(embed=build_invitesmess_status_embed(ctx.guild.id), view=InvitesmessView(ctx))


# ══════════════════════════════════════════════════════════════════════════════
# +synchronise — Synchronise les permissions d'un salon à sa catégorie
# ══════════════════════════════════════════════════════════════════════════════

@bot.command(
    name="synchronise",
    aliases=[
        "sync","synchro","synchonise","synchronize",
        "syncsalon","syncperm","syncperms",
        "syncchannel","syncchannels","syncsalons",
        "synchroniseperm","synccategorie","synccat"
    ]
)
@commands.guild_only()
async def synchronise_cmd(ctx, *, cible: str = None):
    """
    Synchronise les permissions d'un ou plusieurs salons à leur catégorie.

    Usage :
      +synchronise              → synchronise le salon actuel
      +synchronise #salon       → synchronise un salon spécifique
      +synchronise tout         → synchronise TOUS les salons du serveur à leur catégorie
      +synchronise <nom_cat>    → synchronise tous les salons d'une catégorie
    """
    if not ctx.author.guild_permissions.administrator and str(ctx.author.id) not in OWNER_IDS:
        return await ctx.send(embed=embed_err("Permission **Administrateur** requise."))

    if not ctx.guild.me.guild_permissions.manage_channels:
        return await ctx.send(embed=embed_err("J'ai besoin de la permission **Gérer les salons** pour synchroniser les permissions."))

    guild = ctx.guild
    synced = 0
    skipped = 0
    errors = []

    # ── Cas 1 : Tout synchroniser ────────────────────────────────────────────
    if cible and cible.lower() in ("tout", "all", "tous", "toute", "toutes", "*"):
        msg = await ctx.send(embed=discord.Embed(
            description="⏳ Synchronisation de tous les salons en cours...",
            color=C_BLUE
        ))
        for channel in guild.channels:
            if isinstance(channel, discord.CategoryChannel):
                continue
            if channel.category is None:
                skipped += 1
                continue
            try:
                await channel.edit(sync_permissions=True, reason=f"ModeraBot • +synchronise par {ctx.author}")
                synced += 1
                await asyncio.sleep(0.4)  # rate limit protection
            except discord.Forbidden:
                errors.append(f"<#{channel.id}> — Permission refusée")
            except Exception as e:
                errors.append(f"<#{channel.id}> — {e}")

        e = discord.Embed(title="🔄 Synchronisation terminée", color=C_GREEN)
        e.add_field(name="✅ Synchronisés", value=str(synced), inline=True)
        e.add_field(name="⏭️ Ignorés (sans catégorie)", value=str(skipped), inline=True)
        if errors:
            err_txt = "\n".join(errors[:10])
            if len(errors) > 10:
                err_txt += f"\n*... +{len(errors)-10} autres*"
            e.add_field(name=f"⚠️ {len(errors)} erreur(s)", value=err_txt[:1024], inline=False)
        e.set_footer(text="ModeraBot • +synchronise tout")
        await msg.edit(embed=e)
        return

    # ── Cas 2 : Salon mentionné ou par ID ────────────────────────────────────
    if cible and (ctx.message.channel_mentions or cible.isdigit()):
        channel = ctx.message.channel_mentions[0] if ctx.message.channel_mentions else guild.get_channel(int(cible))
        if not channel:
            return await ctx.send(embed=embed_err(f"Salon introuvable : `{cible}`"))
        if channel.category is None:
            return await ctx.send(embed=embed_err(f"Le salon {channel.mention} n'est dans aucune catégorie."))
        try:
            await channel.edit(sync_permissions=True, reason=f"ModeraBot • +synchronise par {ctx.author}")
            e = discord.Embed(color=C_GREEN)
            e.description = (
                f"✅ Le salon {channel.mention} a été synchronisé aux permissions de la catégorie "
                f"**{channel.category.name}**."
            )
            e.set_footer(text="ModeraBot • +synchronise")
            await ctx.send(embed=e)
        except discord.Forbidden:
            await ctx.send(embed=embed_err("Je n'ai pas la permission de modifier ce salon."))
        except Exception as e:
            await ctx.send(embed=embed_err(f"Erreur : `{e}`"))
        return

    # ── Cas 3 : Nom de catégorie ─────────────────────────────────────────────
    if cible:
        cat = discord.utils.find(lambda c: c.name.lower() == cible.lower(), guild.categories)
        if not cat:
            # Cherche approximativement
            cat = discord.utils.find(lambda c: cible.lower() in c.name.lower(), guild.categories)
        if not cat:
            return await ctx.send(embed=embed_err(
                f"Catégorie `{cible}` introuvable.\n"
                f"Utilise `+synchronise tout` pour tout synchroniser, ou mentionne un salon avec `+synchronise #salon`."
            ))

        msg = await ctx.send(embed=discord.Embed(
            description=f"⏳ Synchronisation des salons de **{cat.name}**...",
            color=C_BLUE
        ))
        channels_in_cat = [ch for ch in guild.channels if ch.category and ch.category.id == cat.id and not isinstance(ch, discord.CategoryChannel)]
        for channel in channels_in_cat:
            try:
                await channel.edit(sync_permissions=True, reason=f"ModeraBot • +synchronise par {ctx.author}")
                synced += 1
                await asyncio.sleep(0.4)
            except discord.Forbidden:
                errors.append(f"<#{channel.id}> — Permission refusée")
            except Exception as e:
                errors.append(f"<#{channel.id}> — {e}")

        e = discord.Embed(title=f"🔄 Catégorie **{cat.name}** synchronisée", color=C_GREEN)
        e.add_field(name="✅ Synchronisés", value=str(synced), inline=True)
        e.add_field(name="📂 Catégorie", value=cat.name, inline=True)
        if errors:
            err_txt = "\n".join(errors[:10])
            e.add_field(name=f"⚠️ {len(errors)} erreur(s)", value=err_txt[:1024], inline=False)
        e.set_footer(text="ModeraBot • +synchronise <catégorie>")
        await msg.edit(embed=e)
        return

    # ── Cas 4 : Salon actuel (défaut) ────────────────────────────────────────
    channel = ctx.channel
    if channel.category is None:
        return await ctx.send(embed=embed_err("Ce salon n'est dans aucune catégorie. Impossible de synchroniser."))

    try:
        await channel.edit(sync_permissions=True, reason=f"ModeraBot • +synchronise par {ctx.author}")
        e = discord.Embed(color=C_GREEN)
        e.description = (
            f"✅ Ce salon a été synchronisé aux permissions de la catégorie "
            f"**{channel.category.name}**."
        )
        e.add_field(
            name="ℹ️ Usage avancé",
            value=(
                f"`+synchronise #salon` — synchronise un salon précis\n"
                f"`+synchronise <nom_categorie>` — synchronise tous les salons d'une catégorie\n"
                f"`+synchronise tout` — synchronise tout le serveur"
            ),
            inline=False
        )
        e.set_footer(text="ModeraBot • +synchronise")
        await ctx.send(embed=e)
    except discord.Forbidden:
        await ctx.send(embed=embed_err("Je n'ai pas la permission de modifier ce salon."))
    except Exception as e:
        await ctx.send(embed=embed_err(f"Erreur : `{e}`"))


# ─── Dashboard web ────────────────────────────────────────────────────────────

# Port d'ecoute : allocation Pterodactyl (SERVER_PORT) > config.json > 5001
WEB_PORT = int(
    os.environ.get("DASHBOARD_PORT")
    or CONFIG.get("dashboard_port")
    or os.environ.get("SERVER_PORT")
    or 5001
)

# D'ou vient le port : sur Pterodactyl SEUL le port alloue (SERVER_PORT) est

# ouvert vers l'exterieur. Ecouter ailleurs => nginx renvoie 502.

_PORT_SRC = ("DASHBOARD_PORT (variable d'env)" if os.environ.get("DASHBOARD_PORT")

             else "config.json -> dashboard_port" if CONFIG.get("dashboard_port")

             else "SERVER_PORT (allocation du panel)" if os.environ.get("SERVER_PORT")

             else "valeur par defaut 5001")

print(f"🔌 Port web retenu : {WEB_PORT}  (source : {_PORT_SRC})")

if os.environ.get("SERVER_PORT") and str(WEB_PORT) != str(os.environ.get("SERVER_PORT")):

    print(f"⚠️  Le panel a alloue le port {os.environ.get('SERVER_PORT')} mais le bot ecoute sur {WEB_PORT} :")

    print(f"    ce port n'est probablement PAS joignable de l'exterieur (nginx renverra 502).")


def _adresse_privee(ip):
    """Vrai pour une IP interne (Docker, LAN) : inutilisable depuis l'exterieur."""
    if not ip:
        return True
    if ip in ("0.0.0.0", "localhost", "127.0.0.1"):
        return True
    parties = ip.split(".")
    if len(parties) != 4 or not all(x.isdigit() for x in parties):
        return False
    a, b = int(parties[0]), int(parties[1])
    return a == 10 or a == 127 or (a == 172 and 16 <= b <= 31) or (a == 192 and b == 168)


# Adresse publique affichee au demarrage.
# Pterodactyl met parfois l'IP interne Docker dans SERVER_IP : on ne l'affiche
# pas comme si elle etait joignable depuis l'exterieur.
WEB_HOST = CONFIG.get("dashboard_host") or os.environ.get("SERVER_IP") or ""

HOST_PRIVE = _adresse_privee(WEB_HOST)

if HOST_PRIVE:
    WEB_HOST = "localhost"

DASHBOARD_URL = f"http://{WEB_HOST}:{WEB_PORT}/dashboard"

try:

    from dashboard import init_dashboard

    init_dashboard(app, bot, owner_ids=OWNER_IDS,
                   client_id=CONFIG.get("client_id") or CLIENT_ID,
                   client_secret=CONFIG.get("client_secret") or CLIENT_SECRET,
                   redirect_uri=CONFIG.get("dashboard_redirect_uri")
                                or f"{DASHBOARD_URL}/callback")

    if HOST_PRIVE:

        print(f"🖥️  Dashboard actif sur le port {WEB_PORT}")

        print(f"    → Ouvre http://<IP_PUBLIQUE_DU_PANEL>:{WEB_PORT}/dashboard")

        print(f"    (l'IP publique est celle affichee a cote de l'allocation dans Pterodactyl)")

    else:

        print(f"🖥️  Dashboard actif → {DASHBOARD_URL}")

except Exception as _dash_err:

    print(f"⚠️  Dashboard non chargé : {_dash_err}")


# ══════════════════════════════════════════════════════════════════════════════
#  API DASHBOARD — à coller dans app.py
#  Emplacement : après les routes /api/guild/<guild_id>/roles existantes,
#  et AVANT le lancement du serveur Flask.
#
#  Dépend de ce qui existe déjà dans app.py :
#    app, bot, session, request, jsonify, json, os
#    require_guild_admin, jload, jsave, FILES
#    get_server_config, save_server_config, get_level_config, save_level_config
#    get_logs_cfg, save_logs_cfg, LOGS_TYPES
#    _load_captcha, _save_captcha
#    _prefix_cache, _save_prefixes, DEFAULT_PREFIX
#    _defaultroles, _starboard_cfg, _showpic_cfg
# ══════════════════════════════════════════════════════════════════════════════

def _i(v, default=None):
    """Convertit en int un ID venant du JSON (le bot attend des int, pas des str)."""
    try:
        if v is None or v == "":
            return default
        return int(v)
    except (TypeError, ValueError):
        return default


def _b(v, default=False):
    if isinstance(v, bool):
        return v
    if isinstance(v, str):
        return v.strip().lower() in ("1", "true", "on", "oui", "yes")
    return default


def _s(v, default="", maxlen=2000):
    if v is None:
        return default
    return str(v)[:maxlen]


def _int_list(v):
    out = []
    for x in (v or []):
        n = _i(x)
        if n is not None:
            out.append(n)
    return out


def _guild_config_payload(guild):
    """Assemble la configuration complète du serveur pour le dashboard."""
    gid = str(guild.id)

    tickets = jload(FILES["ticket_select"]).get(gid, {})
    welcome = jload(FILES["welcome"]).get(gid, {})
    depart = jload(FILES["depart"]).get(gid, {})
    antilink = jload(FILES["antilink"]).get(gid, {})
    antibot = jload(FILES["antibot"]).get(gid, {})
    giveaway = jload(FILES["giveaway_cfg"]).get(gid, {})
    captcha = _load_captcha().get(gid, {})
    logs = get_logs_cfg(guild.id)
    srv = get_server_config(gid)
    lvl = get_level_config(gid)

    return {
        "prefix": _prefix_cache.get(guild.id, DEFAULT_PREFIX),
        "tickets": {
            "panel": tickets.get("panel", {}),
            "choix": tickets.get("choix", []),
        },
        "welcome": welcome,
        "depart": depart,
        "logs": {t[0]: logs.get(t[0], {}) for t in LOGS_TYPES},
        "antilink": antilink,
        "antiraid": srv.get("antiraid", {}),
        "captcha": captcha,
        "levels": {
            "xp_channel": lvl.get("xp_channel"),
            "notif_channel": lvl.get("notif_channel"),
            "xp_min": lvl.get("xp_min", 5),
            "xp_max": lvl.get("xp_max", 15),
        },
        "giveaway": giveaway,
        "antibot": {k: v for k, v in antibot.items() if k != "offenders"},
        "starboard": _starboard_cfg.get(gid, {}),
        "showpic": _showpic_cfg.get(gid, {}),
        "defaultroles": _defaultroles.get(gid, []),
    }


# ── Authentification du dashboard ─────────────────────────────────────────────
# Deux voies acceptées :
#   1. la session Flask classique (cookie posé par /api/oauth-exchange)
#   2. le token Discord envoyé par la page en en-tête Authorization: Bearer …
# La 2e évite de dépendre de /api/oauth-exchange : le dashboard fonctionne même
# si l'échange de code côté serveur est cassé.
_DASH_TOKEN_CACHE = {}   # token -> (expiration, user_dict, {guild_id: permissions})
_DASH_CACHE_TTL = 300    # 5 minutes


def _dash_user_from_token(token):
    """Identifie le porteur du token auprès de Discord (avec cache court)."""
    now = _time.time()

    # Garde-fou : un token Discord fait ~30 caractères, jamais 10 000.
    # Sans ça, n'importe qui pourrait faire marteler l'API Discord par le bot.
    if not token or not (10 <= len(token) <= 128):
        return None, {}

    hit = _DASH_TOKEN_CACHE.get(token)
    if hit and hit[0] > now:
        return hit[1], hit[2]          # hit[1] vaut None pour un token déjà refusé

    # cache borné : on ne laisse pas un spam de faux tokens faire gonfler la mémoire
    if len(_DASH_TOKEN_CACHE) > 500:
        for k, v in list(_DASH_TOKEN_CACHE.items()):
            if v[0] <= now:
                _DASH_TOKEN_CACHE.pop(k, None)
        if len(_DASH_TOKEN_CACHE) > 500:
            _DASH_TOKEN_CACHE.clear()

    try:
        headers = {"Authorization": f"Bearer {token}"}
        ru = requests.get("https://discord.com/api/v10/users/@me", headers=headers, timeout=8)
        if ru.status_code != 200:
            # cache négatif : un token invalide n'est pas revérifié avant 60 s
            _DASH_TOKEN_CACHE[token] = (now + 60, None, {})
            return None, {}
        user = ru.json()
        rg = requests.get("https://discord.com/api/v10/users/@me/guilds", headers=headers, timeout=8)
        perms = {}
        if rg.status_code == 200:
            for g in rg.json():
                perms[str(g.get("id"))] = str(g.get("permissions", "0")) if not g.get("owner") else "8"
    except Exception as err:
        print(f"[dashboard] vérification du token impossible : {err}")
        return None, {}
    # purge des entrées expirées pour ne pas faire grossir le cache indéfiniment
    for k, v in list(_DASH_TOKEN_CACHE.items()):
        if v[0] <= now:
            _DASH_TOKEN_CACHE.pop(k, None)
    _DASH_TOKEN_CACHE[token] = (now + _DASH_CACHE_TTL, user, perms)
    return user, perms


def _dash_auth(guild_id):
    """Renvoie (guild, member) si l'utilisateur peut configurer ce serveur, sinon (None, None)."""
    # 1) session Flask
    guild, member = require_guild_admin(guild_id)
    if guild:
        return guild, member

    # 2) token Discord porté par la page
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None, None
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
        # source de vérité : les permissions réelles vues par le bot
        p = member.guild_permissions
        if member.id == guild.owner_id or p.administrator or p.manage_guild:
            return guild, member
        return None, None

    # membre non mis en cache : on se rabat sur les permissions renvoyées par OAuth
    try:
        bits = int(perms.get(str(gid), "0"))
    except (TypeError, ValueError):
        return None, None
    if bits & 0x8 or bits & 0x20:
        return guild, None
    return None, None


@app.route("/api/guild/<guild_id>/dashboard", methods=["GET", "POST"])
def api_guild_dashboard(guild_id):
    guild, member = _dash_auth(guild_id)
    if not guild:
        return jsonify({"error": "forbidden"}), 403

    gid = str(guild.id)

    # ─────────────────────────── LECTURE ───────────────────────────
    if request.method == "GET":
        categories = [{"id": str(c.id), "name": c.name} for c in guild.categories]
        channels = [{"id": str(c.id), "name": c.name,
                     "category": str(c.category.id) if c.category else None}
                    for c in guild.text_channels]
        voice = [{"id": str(c.id), "name": c.name} for c in guild.voice_channels]
        roles = [{"id": str(r.id), "name": r.name, "color": str(r.color)}
                 for r in guild.roles if r.name != "@everyone" and not r.managed]
        roles.reverse()
        channels.sort(key=lambda c: c["name"].lower())
        categories.sort(key=lambda c: c["name"].lower())

        return jsonify({
            "guild": {
                "id": gid,
                "name": guild.name,
                "icon": str(guild.icon.url) if guild.icon else None,
                "members": guild.member_count,
                "online": sum(1 for m in guild.members if str(m.status) != "offline"),
                "channels": len(guild.channels),
                "roles": len(guild.roles),
            },
            "channels": channels,
            "voice_channels": voice,
            "categories": categories,
            "roles": roles,
            "log_types": [{"key": t[0], "label": t[1], "emoji": t[2]} for t in LOGS_TYPES],
            "config": _guild_config_payload(guild),
        })

    # ─────────────────────────── ÉCRITURE ───────────────────────────
    body = request.get_json(silent=True) or {}

    # Filet de securite : on garde une copie de la configuration AVANT toute
    # ecriture. Si un enregistrement efface quelque chose par erreur, la valeur
    # precedente reste recuperable dans dashboard_backups/.
    try:
        os.makedirs("dashboard_backups", exist_ok=True)
        _avant = _guild_config_payload(guild)
        _snap = f"dashboard_backups/{gid}-{int(_time.time())}.json"
        jsave(_snap, {"sections_envoyees": sorted(body.keys()), "config_avant": _avant})
        _vieux = sorted(f for f in os.listdir("dashboard_backups") if f.startswith(gid + "-"))
        for _f in _vieux[:-10]:                       # on ne garde que les 10 dernieres
            try: os.remove(os.path.join("dashboard_backups", _f))
            except OSError: pass
    except Exception as _err:
        print(f"[dashboard] sauvegarde de securite impossible : {_err}")

    saved = []

    # ---- Préfixe ----
    if "prefix" in body:
        p = _s(body.get("prefix"), maxlen=5).strip()
        if p:
            _prefix_cache[guild.id] = p
            _save_prefixes()
            saved.append("prefix")

    # ---- Tickets (ticket_select.json) ----
    if "tickets" in body:
        t = body["tickets"] or {}
        data = jload(FILES["ticket_select"])
        entry = data.setdefault(gid, {})

        if "panel" in t:
            p = t["panel"] or {}
            mode = _s(p.get("mode"), "select", 20)
            if mode not in ("select", "bouton", "container_v2"):
                mode = "select"
            entry["panel"] = {
                "titre": _s(p.get("titre"), "Support", 100),
                "description": _s(p.get("description"), "", 500),
                "image": _s(p.get("image"), "", 300) or None,
                "logs": _i(p.get("logs")),
                "couleur": _s(p.get("couleur"), "#5865F2", 10) or "#5865F2",
                "mode": mode,
            }

        if "choix" in t:
            choix = []
            for c in (t["choix"] or [])[:25]:
                nom = _s(c.get("nom"), "", 25).strip()
                if not nom:
                    continue
                btn = _s(c.get("btn_color"), "bleu", 10)
                if btn not in ("bleu", "vert", "rouge", "gris"):
                    btn = "bleu"
                choix.append({
                    "nom": nom,
                    "description": _s(c.get("description"), "", 97),
                    "emoji": _s(c.get("emoji"), "🎫", 5) or "🎫",
                    "categorie": _i(c.get("categorie")),
                    "roles": _int_list(c.get("roles")),
                    "titre": _s(c.get("titre"), f"Ticket — {nom}", 100),
                    "message": _s(c.get("message"), "Bienvenue {user} ! Explique ton problème.", 500),
                    "btn_color": btn,
                    "salon_name": _s(c.get("salon_name"), "ticket-{username}", 50) or "ticket-{username}",
                    "ia_enabled": _b(c.get("ia_enabled")),
                })
            entry["choix"] = choix

        jsave(FILES["ticket_select"], data)
        saved.append("tickets")

    # ---- Bienvenue (welcome.json) ----
    if "welcome" in body:
        w = body["welcome"] or {}
        data = jload(FILES["welcome"])
        emb = w.get("embed") or {}
        mode = _s(w.get("mode"), "texte", 10)
        data[gid] = {
            "enabled": _b(w.get("enabled"), True),
            "channel_id": _i(w.get("channel_id")),
            "mode": "embed" if mode == "embed" else "texte",
            "message": _s(w.get("message"), "", 2000),
            "auto_delete": max(0, _i(w.get("auto_delete"), 0) or 0),
            "mp_enabled": _b(w.get("mp_enabled")),
            "mp_message": _s(w.get("mp_message"), "", 2000),
            "embed": {
                "titre": _s(emb.get("titre"), "", 256),
                "desc": _s(emb.get("desc"), "", 2000),
                "color": _s(emb.get("color"), "#5865F2", 10) or "#5865F2",
                "thumb": _s(emb.get("thumb"), "", 300),
                "image": _s(emb.get("image"), "", 300),
            },
        }
        jsave(FILES["welcome"], data)
        saved.append("welcome")

    # ---- Départ (depart.json) ----
    if "depart" in body:
        d = body["depart"] or {}
        data = jload(FILES["depart"])
        data[gid] = {
            "channel_id": _i(d.get("channel_id")),
            "title": _s(d.get("title"), "", 256),
            "description": _s(d.get("description"), "", 2000),
        }
        jsave(FILES["depart"], data)
        saved.append("depart")

    # ---- Logs (logs_config.json) ----
    if "logs" in body:
        cfg = get_logs_cfg(guild.id)
        valid = {t[0] for t in LOGS_TYPES}
        for key, val in (body["logs"] or {}).items():
            if key not in valid:
                continue
            cfg[key] = {
                "enabled": _b((val or {}).get("enabled")),
                "channel": _i((val or {}).get("channel"), 0) or 0,
            }
        save_logs_cfg(guild.id, cfg)
        saved.append("logs")

    # ---- Anti-lien (antilink_config.json) ----
    if "antilink" in body:
        a = body["antilink"] or {}
        data = jload(FILES["antilink"])
        action = _s(a.get("action"), "delete", 20)
        data[gid] = {
            "enabled": _b(a.get("enabled")),
            "action": action,
            "whitelist": [_s(x, "", 120) for x in (a.get("whitelist") or [])][:100],
        }
        jsave(FILES["antilink"], data)
        saved.append("antilink")

    # ---- Anti-raid (server_configs/<gid>.json) ----
    if "antiraid" in body:
        a = body["antiraid"] or {}
        srv = get_server_config(gid)
        ar = srv.get("antiraid", {})
        ar["enabled"] = _b(a.get("enabled"))
        ar["modlog"] = _i(a.get("modlog"))
        for sub, fields in (
            ("join", ("join_action", "join_interval", "join_threshold")),
            ("spam", ("spam_action", "spam_interval", "spam_threshold")),
            ("mention", ("mention_action", "mention_limit")),
            ("caps", ("caps_percent", "caps_min_length")),
            ("emoji_spam", ("max_emojis",)),
        ):
            if sub in a:
                ar[sub] = _b((a.get(sub) or {}).get("enabled"))
            for f in fields:
                if f in a:
                    ar[f] = _s(a[f], "", 20) if f.endswith("action") else _i(a[f], 0)
        srv["antiraid"] = ar
        save_server_config(gid, srv)
        saved.append("antiraid")

    # ---- Captcha / vérification (captcha_config.json) ----
    if "captcha" in body:
        c = body["captcha"] or {}
        data = _load_captcha()
        data[gid] = {
            "enabled": _b(c.get("enabled")),
            "channel_id": _i(c.get("channel_id")),
            "verified_role": _i(c.get("verified_role")),
            "unverified_role": _i(c.get("unverified_role")),
            "code_length": min(10, max(4, _i(c.get("code_length"), 6) or 6)),
            "max_tries": min(10, max(1, _i(c.get("max_tries"), 3) or 3)),
            "kick_on_fail": _b(c.get("kick_on_fail")),
            "style": _s(c.get("style"), "code", 20),
            "welcome_message": _s(c.get("welcome_message"), "", 1000),
        }
        _save_captcha(data)
        saved.append("captcha")

    # ---- Niveaux (level_configs/<gid>.json — on préserve "members") ----
    if "levels" in body:
        l = body["levels"] or {}
        cfg = get_level_config(gid)
        cfg["xp_channel"] = _i(l.get("xp_channel"))
        cfg["notif_channel"] = _i(l.get("notif_channel"))
        cfg["xp_min"] = max(0, _i(l.get("xp_min"), 5) or 0)
        cfg["xp_max"] = max(cfg["xp_min"], _i(l.get("xp_max"), 15) or 0)
        cfg.setdefault("members", {})
        save_level_config(gid, cfg)
        saved.append("levels")

    # ---- Giveaway (giveaway_config.json) ----
    if "giveaway" in body:
        g = body["giveaway"] or {}
        data = jload(FILES["giveaway_cfg"])
        cur = data.get(gid, {})
        cur.update({
            "salon_id": _i(g.get("salon_id")),
            "emoji": _s(g.get("emoji"), "🎉", 8) or "🎉",
            "btn_text": _s(g.get("btn_text"), "Participer", 40),
            "btn_color": _s(g.get("btn_color"), "bleu", 10),
            "duree": _s(g.get("duree"), "", 20),
            "gagnants": max(1, _i(g.get("gagnants"), 1) or 1),
            "required_roles": _int_list(g.get("required_roles")),
            "blacklist_roles": _int_list(g.get("blacklist_roles")),
            "vocal_required": _b(g.get("vocal_required")),
        })
        data[gid] = cur
        jsave(FILES["giveaway_cfg"], data)
        saved.append("giveaway")

    # ---- Anti-bot (antibot_config.json — on préserve "offenders") ----
    if "antibot" in body:
        a = body["antibot"] or {}
        data = jload(FILES["antibot"])
        cur = data.get(gid, {})
        cur["enabled"] = _b(a.get("enabled"))
        cur["channel_id"] = _i(a.get("channel_id"))
        data[gid] = cur
        jsave(FILES["antibot"], data)
        saved.append("antibot")

    # ---- Starboard / ShowPic / Rôles par défaut (mémoire vive) ----
    if "starboard" in body:
        s = body["starboard"] or {}
        ch = _i(s.get("channel_id"))
        if ch:
            _starboard_cfg[gid] = {
                "channel_id": ch,
                "seuil": max(1, _i(s.get("seuil"), 3) or 3),
                "emoji": _s(s.get("emoji"), "⭐", 8) or "⭐",
            }
        else:
            _starboard_cfg.pop(gid, None)
        saved.append("starboard")

    if "showpic" in body:
        s = body["showpic"] or {}
        _showpic_cfg[gid] = {"enabled": _b(s.get("enabled")), "channel_id": _i(s.get("channel_id"))}
        saved.append("showpic")

    if "defaultroles" in body:
        _defaultroles[gid] = _int_list(body.get("defaultroles"))[:10]
        saved.append("defaultroles")

    return jsonify({"ok": True, "saved": saved})


@app.route("/api/guild/<guild_id>/stats")
def api_guild_stats(guild_id):
    """Statistiques affichées sur la page Vue d'ensemble du dashboard."""
    guild, member = _dash_auth(guild_id)
    if not guild:
        return jsonify({"error": "forbidden"}), 403

    lvl = get_level_config(str(guild.id))
    top = sorted(
        ((uid, d) for uid, d in (lvl.get("members") or {}).items()),
        key=lambda kv: (kv[1].get("level", 0), kv[1].get("xp", 0)),
        reverse=True,
    )[:5]

    recent = []
    for uid, d in top:
        m = guild.get_member(_i(uid, 0) or 0)
        recent.append({
            "title": (m.display_name if m else f"Membre {uid}"),
            "detail": f"Niveau {d.get('level', 0)} · {d.get('xp', 0)} XP",
        })

    return jsonify({
        "members": guild.member_count,
        "online": sum(1 for m in guild.members if str(m.status) != "offline"),
        "infractions": len((jload(FILES["antibot"]).get(str(guild.id), {}) or {}).get("offenders", [])),
        "recent": recent,
    })


def run_api():

    """Sert le dashboard. Waitress si disponible, sinon le serveur Flask."""

    try:

        from waitress import serve

        print(f"🌐 Serveur web (waitress) sur le port {WEB_PORT}")

        serve(app, host="0.0.0.0", port=WEB_PORT, threads=8, _quiet=True)

    except ImportError:

        app.run(host="0.0.0.0", port=WEB_PORT, threaded=True)


Thread(target=run_api, daemon=True).start()


# ══════════════════════════════════════════
# +botserverinfo — Owner only
# ══════════════════════════════════════════

class BotServerSelect(discord.ui.Select):
    def __init__(self, guilds_data):
        self.guilds_data = guilds_data  # list of (guild, invite_url)
        options = []
        for i, (g, _) in enumerate(guilds_data[:25]):
            options.append(discord.SelectOption(
                label=g.name[:50],
                value=str(i),
                description=f"{g.member_count} membres",
                emoji="🌐"
            ))
        super().__init__(placeholder="Choisir un serveur...", options=options, min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        idx = int(self.values[0])
        g, invite_url = self.guilds_data[idx]

        # Infos détaillées
        total    = g.member_count or 0
        bots     = sum(1 for m in g.members if m.bot) if g.members else "?"
        humans   = (total - bots) if isinstance(bots, int) else "?"
        roles    = len(g.roles)
        channels = len(g.channels)
        text_ch  = len(g.text_channels)
        voice_ch = len(g.voice_channels)
        owner    = g.owner
        created  = f"<t:{int(g.created_at.timestamp())}:D>"
        boost    = g.premium_subscription_count or 0
        boost_lvl = g.premium_tier

        e = discord.Embed(title=f"🌐 {g.name}", color=0x5865F2)
        e.add_field(name="👥 Membres",    value=f"**{total}** ({humans} humains / {bots} bots)", inline=False)
        e.add_field(name="👑 Propriétaire", value=f"{owner.mention if owner else 'Inconnu'} (`{owner}` — `{g.owner_id}`)", inline=False)
        e.add_field(name="🆔 ID Serveur", value=f"`{g.id}`", inline=True)
        e.add_field(name="📅 Créé le",    value=created, inline=True)
        e.add_field(name="💬 Salons",     value=f"**{channels}** ({text_ch} texte / {voice_ch} vocal)", inline=False)
        e.add_field(name="🎭 Rôles",      value=str(roles), inline=True)
        e.add_field(name="🚀 Boosts",     value=f"{boost} (Niveau {boost_lvl})", inline=True)
        e.add_field(name="🔗 Lien d'invitation", value=invite_url if invite_url else "❌ Impossible de générer", inline=False)

        if g.icon:
            e.set_thumbnail(url=g.icon.url)
        if g.banner:
            e.set_image(url=g.banner.url)

        e.set_footer(text=f"ModeraBot • {len(bot.guilds)} serveurs au total")
        await interaction.response.edit_message(embed=e)

class BotServerView(discord.ui.View):
    def __init__(self, guilds_data, author_id):
        super().__init__(timeout=120)
        self.author_id = author_id
        self.add_item(BotServerSelect(guilds_data))

    async def interaction_check(self, interaction: discord.Interaction):
        if str(interaction.user.id) != str(self.author_id):
            await interaction.response.send_message(embed=discord.Embed(description="❌ Ce menu n'est pas pour toi.", color=0xED4245), ephemeral=True)
            return False
        return True

@bot.command(name="botserverinfo", aliases=["bsi","serversinfo","botservers","botsrvinfo","serveursbot"])
async def botserverinfo_cmd(ctx):
    if str(ctx.author.id) not in OWNER_IDS:
        return await ctx.send(embed=discord.Embed(description="❌ Commande réservée aux **owners** du bot.", color=0xED4245))

    await ctx.message.delete()

    guilds = sorted(bot.guilds, key=lambda g: g.member_count or 0, reverse=True)

    # Générer les liens d'invitation pour chaque serveur
    guilds_data = []
    for g in guilds[:25]:
        invite_url = None
        try:
            # Essayer vanity d'abord
            if g.vanity_url_code:
                invite_url = f"https://discord.gg/{g.vanity_url_code}"
            else:
                # Chercher un salon texte accessible
                for ch in g.text_channels:
                    try:
                        inv = await ch.create_invite(max_age=0, max_uses=0, unique=False, reason="botserverinfo")
                        invite_url = inv.url
                        break
                    except:
                        continue
        except:
            pass
        guilds_data.append((g, invite_url))

    e = discord.Embed(
        title=f"🤖 ModeraBot — {len(guilds)} serveur(s)",
        description="Sélectionne un serveur dans le menu pour voir ses infos détaillées.",
        color=0x5865F2
    )
    # Résumé rapide
    desc_lines = ""
    for i, (g, _) in enumerate(guilds_data[:10], 1):
        desc_lines += f"`{i}.` **{g.name}** — {g.member_count} membres\n"
    if len(guilds) > 10:
        desc_lines += f"*... et {len(guilds)-10} autres dans le menu*"
    e.add_field(name="📋 Top serveurs", value=desc_lines or "Aucun", inline=False)
    e.set_footer(text="Menu déroulant ci-dessous • Visible uniquement par toi")

    await ctx.send(embed=e, view=BotServerView(guilds_data, ctx.author.id))

bot.run(TOKEN)