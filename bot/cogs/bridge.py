"""Pont dashboard -> bot.

Le site web n'a AUCUN acces au token du bot : il depose seulement des ordres
dans la table ``action_queue``. Cette task les consomme, revalide les droits du
demandeur cote bot, execute, puis ecrit le resultat que le dashboard relit.
"""
from __future__ import annotations

import logging
import time
from datetime import timedelta
from typing import Any, Callable, Awaitable

import discord
from discord.ext import commands, tasks

from core import database as db

log = logging.getLogger("modera.bridge")

Handler = Callable[["Bridge", discord.Guild, dict, discord.Member], Awaitable[str]]
HANDLERS: dict[str, Handler] = {}


def action(name: str):
    def wrapper(func: Handler) -> Handler:
        HANDLERS[name] = func
        return func
    return wrapper


class PermissionDenied(Exception):
    """Le demandeur n'a pas (ou plus) le droit de lancer cette action."""


class Bridge(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def cog_load(self) -> None:
        self.consume_queue.start()
        self.refresh_cache.start()

    async def cog_unload(self) -> None:
        self.consume_queue.cancel()
        self.refresh_cache.cancel()

    # ── TASK : consommation de la file d'actions ───────────────────────
    @tasks.loop(seconds=2)
    async def consume_queue(self) -> None:
        try:
            pending = await db.run(db.take_pending_actions, 10)
        except Exception:
            log.exception("lecture de la file impossible")
            return

        for item in pending:
            try:
                result = await self.execute(item)
                await db.run(db.finish_action, item["id"], "done", result)
            except PermissionDenied as exc:
                await db.run(db.finish_action, item["id"], "denied", str(exc))
            except discord.Forbidden:
                await db.run(db.finish_action, item["id"], "error",
                             "Permissions Discord insuffisantes pour le bot.")
            except discord.HTTPException as exc:
                await db.run(db.finish_action, item["id"], "error", f"Discord: {exc}")
            except Exception as exc:
                log.exception("action %s en echec", item["action"])
                await db.run(db.finish_action, item["id"], "error", str(exc))

    @consume_queue.before_loop
    async def _before_queue(self) -> None:
        await self.bot.wait_until_ready()

    async def execute(self, item: dict[str, Any]) -> str:
        guild = self.bot.get_guild(item["guild_id"])
        if guild is None:
            raise PermissionDenied("Le bot n'est pas (ou plus) sur ce serveur.")

        handler = HANDLERS.get(item["action"])
        if handler is None:
            raise PermissionDenied(f"Action inconnue : {item['action']}")

        # Revalidation cote bot : le site a deja verifie, on ne lui fait pas confiance.
        author = guild.get_member(item["requested_by"])
        if author is None:
            try:
                author = await guild.fetch_member(item["requested_by"])
            except discord.NotFound:
                raise PermissionDenied("Tu n'es plus membre de ce serveur.")
        if not (author.guild_permissions.manage_guild or author.id == guild.owner_id):
            raise PermissionDenied("Il faut la permission 'Gerer le serveur'.")

        result = await handler(self, guild, item["payload"], author)

        await db.run(db.add_audit, guild.id, author.id, str(author),
                     item["action"], result)
        await self.notify_logs(guild, author, item["action"], result)
        return result

    async def notify_logs(self, guild: discord.Guild, author: discord.Member,
                          name: str, result: str) -> None:
        conf = await db.run(db.get_config, guild.id, "logs")
        if not (conf["enabled"] and conf["dashboard"] and conf["channel_id"]):
            return
        channel = guild.get_channel(int(conf["channel_id"]))
        if not isinstance(channel, discord.TextChannel):
            return
        embed = discord.Embed(
            title="Action dashboard",
            description=f"**{name}** — {result}",
            colour=0x6AB3E8,
            timestamp=discord.utils.utcnow(),
        )
        embed.set_footer(text=f"Par {author} ({author.id})")
        await channel.send(embed=embed)

    # ── TASK : rafraichissement du cache salons/roles ──────────────────
    @tasks.loop(minutes=5)
    async def refresh_cache(self) -> None:
        await self.bot.sync_all_guilds()

    @refresh_cache.before_loop
    async def _before_refresh(self) -> None:
        await self.bot.wait_until_ready()

    # ── Utilitaires ────────────────────────────────────────────────────
    def text_channel(self, guild: discord.Guild, raw: Any) -> discord.TextChannel:
        channel = guild.get_channel(int(raw or 0))
        if not isinstance(channel, discord.TextChannel):
            raise PermissionDenied("Salon texte introuvable.")
        return channel

    async def fetch_member(self, guild: discord.Guild, raw: Any) -> discord.Member:
        user_id = int(raw or 0)
        member = guild.get_member(user_id)
        if member is None:
            try:
                member = await guild.fetch_member(user_id)
            except discord.NotFound:
                raise PermissionDenied("Membre introuvable sur ce serveur.")
        return member

    def check_hierarchy(self, guild: discord.Guild, author: discord.Member,
                        target: discord.Member) -> None:
        """Empeche un admin du dashboard de frapper plus haut que lui, et le bot aussi."""
        if target.id == guild.owner_id:
            raise PermissionDenied("Impossible de sanctionner le proprietaire.")
        if target.id == self.bot.user.id:
            raise PermissionDenied("Le bot ne peut pas se sanctionner lui-meme.")
        if author.id != guild.owner_id and target.top_role >= author.top_role:
            raise PermissionDenied("Cette personne a un role superieur ou egal au tien.")
        if guild.me.top_role <= target.top_role:
            raise PermissionDenied("Le role du bot est trop bas pour agir sur ce membre.")


# ── Handlers ───────────────────────────────────────────────────────────
@action("send_message")
async def _send_message(self: Bridge, guild, payload, author) -> str:
    channel = self.text_channel(guild, payload.get("channel_id"))
    content = str(payload.get("content", "")).strip()[:2000]
    if not content:
        raise PermissionDenied("Message vide.")
    await channel.send(content, allowed_mentions=discord.AllowedMentions(
        everyone=bool(payload.get("allow_everyone")) and author.guild_permissions.mention_everyone,
        roles=bool(payload.get("allow_everyone")),
        users=True,
    ))
    return f"Message envoye dans #{channel.name}"


@action("announce")
async def _announce(self: Bridge, guild, payload, author) -> str:
    channel = self.text_channel(guild, payload.get("channel_id"))
    embed = discord.Embed(
        title=str(payload.get("title", ""))[:256] or None,
        description=str(payload.get("content", ""))[:4000],
        colour=int(str(payload.get("color", "#6ab3e8")).lstrip("#"), 16),
        timestamp=discord.utils.utcnow(),
    )
    embed.set_footer(text=f"{guild.name}", icon_url=guild.icon.url if guild.icon else None)
    await channel.send(embed=embed)
    return f"Annonce publiee dans #{channel.name}"


@action("kick")
async def _kick(self: Bridge, guild, payload, author) -> str:
    member = await self.fetch_member(guild, payload.get("user_id"))
    self.check_hierarchy(guild, author, member)
    reason = str(payload.get("reason", ""))[:400] or "Dashboard"
    await member.kick(reason=f"{author} (dashboard) : {reason}")
    await db.run(db.bump_stat, guild.id, "sanctions")
    return f"{member} expulse"


@action("ban")
async def _ban(self: Bridge, guild, payload, author) -> str:
    user_id = int(payload.get("user_id") or 0)
    reason = str(payload.get("reason", ""))[:400] or "Dashboard"
    delete_days = max(0, min(7, int(payload.get("delete_days", 0) or 0)))
    member = guild.get_member(user_id)
    if member is not None:
        self.check_hierarchy(guild, author, member)
    await guild.ban(discord.Object(id=user_id), reason=f"{author} (dashboard) : {reason}",
                    delete_message_days=delete_days)
    await db.run(db.bump_stat, guild.id, "sanctions")
    return f"Utilisateur {user_id} banni"


@action("unban")
async def _unban(self: Bridge, guild, payload, author) -> str:
    user_id = int(payload.get("user_id") or 0)
    await guild.unban(discord.Object(id=user_id), reason=f"{author} (dashboard)")
    await db.run(db.execute,
                 "UPDATE sanctions SET active = 0 WHERE guild_id = ? AND user_id = ? AND kind = 'ban'",
                 (guild.id, user_id))
    return f"Utilisateur {user_id} debanni"


@action("timeout")
async def _timeout(self: Bridge, guild, payload, author) -> str:
    member = await self.fetch_member(guild, payload.get("user_id"))
    self.check_hierarchy(guild, author, member)
    minutes = max(1, min(40320, int(payload.get("minutes", 10) or 10)))
    reason = str(payload.get("reason", ""))[:400] or "Dashboard"
    await member.timeout(timedelta(minutes=minutes), reason=f"{author} : {reason}")
    await db.run(db.execute,
                 """INSERT INTO sanctions (guild_id, user_id, kind, reason, moderator_id,
                                           created_at, expires_at, active)
                    VALUES (?, ?, 'timeout', ?, ?, ?, ?, 1)""",
                 (guild.id, member.id, reason, author.id, time.time(),
                  time.time() + minutes * 60))
    await db.run(db.bump_stat, guild.id, "sanctions")
    return f"{member} exclu pour {minutes} min"


@action("untimeout")
async def _untimeout(self: Bridge, guild, payload, author) -> str:
    member = await self.fetch_member(guild, payload.get("user_id"))
    await member.timeout(None, reason=f"{author} (dashboard)")
    return f"Exclusion levee pour {member}"


@action("warn")
async def _warn(self: Bridge, guild, payload, author) -> str:
    member = await self.fetch_member(guild, payload.get("user_id"))
    self.check_hierarchy(guild, author, member)
    reason = str(payload.get("reason", ""))[:400] or "Dashboard"
    await db.run(db.execute,
                 """INSERT INTO warnings (guild_id, user_id, moderator_id, reason, created_at)
                    VALUES (?, ?, ?, ?, ?)""",
                 (guild.id, member.id, author.id, reason, time.time()))
    await db.run(db.bump_stat, guild.id, "sanctions")
    try:
        await member.send(f"Tu as recu un avertissement sur **{guild.name}** : {reason}")
    except discord.HTTPException:
        pass
    return f"{member} averti"


@action("clear_warnings")
async def _clear_warnings(self: Bridge, guild, payload, author) -> str:
    user_id = int(payload.get("user_id") or 0)
    await db.run(db.execute,
                 "UPDATE warnings SET active = 0 WHERE guild_id = ? AND user_id = ?",
                 (guild.id, user_id))
    return f"Avertissements effaces pour {user_id}"


@action("purge")
async def _purge(self: Bridge, guild, payload, author) -> str:
    channel = self.text_channel(guild, payload.get("channel_id"))
    amount = max(1, min(200, int(payload.get("amount", 10) or 10)))
    deleted = await channel.purge(limit=amount)
    return f"{len(deleted)} messages supprimes dans #{channel.name}"


@action("role_add")
async def _role_add(self: Bridge, guild, payload, author) -> str:
    member = await self.fetch_member(guild, payload.get("user_id"))
    role = guild.get_role(int(payload.get("role_id") or 0))
    if role is None:
        raise PermissionDenied("Role introuvable.")
    if role >= guild.me.top_role or role.managed:
        raise PermissionDenied("Le bot ne peut pas attribuer ce role.")
    if author.id != guild.owner_id and role >= author.top_role:
        raise PermissionDenied("Ce role est au-dessus du tien.")
    await member.add_roles(role, reason=f"{author} (dashboard)")
    return f"Role {role.name} ajoute a {member}"


@action("role_remove")
async def _role_remove(self: Bridge, guild, payload, author) -> str:
    member = await self.fetch_member(guild, payload.get("user_id"))
    role = guild.get_role(int(payload.get("role_id") or 0))
    if role is None:
        raise PermissionDenied("Role introuvable.")
    if role >= guild.me.top_role or role.managed:
        raise PermissionDenied("Le bot ne peut pas retirer ce role.")
    await member.remove_roles(role, reason=f"{author} (dashboard)")
    return f"Role {role.name} retire a {member}"


@action("lockdown")
async def _lockdown(self: Bridge, guild, payload, author) -> str:
    enable = bool(payload.get("enable", True))
    everyone = guild.default_role
    touched = 0
    for channel in guild.text_channels:
        overwrite = channel.overwrites_for(everyone)
        if overwrite.send_messages is (False if enable else None):
            continue
        overwrite.send_messages = False if enable else None
        await channel.set_permissions(everyone, overwrite=overwrite,
                                      reason=f"Lockdown par {author} (dashboard)")
        touched += 1
    await db.run(db.set_state, f"lockdown:{guild.id}", enable)
    verb = "verrouille" if enable else "deverrouille"
    return f"Serveur {verb} ({touched} salons)"


@action("refresh")
async def _refresh(self: Bridge, guild, payload, author) -> str:
    await self.bot.sync_guild(guild)
    return "Cache du serveur rafraichi"


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Bridge(bot))
