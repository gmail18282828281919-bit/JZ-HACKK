"""Module AutoMod : anti-spam, anti-lien, anti-mention, mots interdits.

TASKS :
  - expire_sanctions : leve les timeouts/bans temporaires arrives a echeance
"""
from __future__ import annotations

import logging
import re
import time
from collections import defaultdict, deque
from datetime import timedelta

import discord
from discord.ext import commands, tasks

from core import database as db

log = logging.getLogger("modera.automod")

INVITE_RE = re.compile(r"(discord\.(gg|io|me|li)|discordapp\.com/invite)/\S+", re.I)
LINK_RE = re.compile(r"https?://\S+", re.I)


class AutoMod(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        # (guild_id, user_id) -> timestamps des derniers messages
        self.history: dict[tuple[int, int], deque[float]] = defaultdict(
            lambda: deque(maxlen=40))

    async def cog_load(self) -> None:
        self.expire_sanctions.start()

    async def cog_unload(self) -> None:
        self.expire_sanctions.cancel()

    def is_exempt(self, message: discord.Message, conf: dict) -> bool:
        member = message.author
        if member.guild_permissions.manage_messages:
            return True
        if str(message.channel.id) in map(str, conf["ignored_channel_ids"]):
            return True
        ignored = {int(r) for r in conf["ignored_role_ids"]}
        return any(role.id in ignored for role in member.roles)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot or not message.guild:
            return
        await db.run(db.bump_stat, message.guild.id, "messages")

        conf = await db.run(db.get_config, message.guild.id, "automod")
        if not conf["enabled"] or self.is_exempt(message, conf):
            return

        reason = self.detect(message, conf)
        if reason is None:
            return

        try:
            await message.delete()
        except discord.HTTPException:
            pass
        await self.sanction(message, conf, reason)

    def detect(self, message: discord.Message, conf: dict) -> str | None:
        content = message.content or ""

        if conf["anti_invite"] and INVITE_RE.search(content):
            return "invitation Discord"
        if conf["anti_link"] and LINK_RE.search(content):
            return "lien interdit"

        max_mentions = int(conf["max_mentions"] or 0)
        if max_mentions and len(message.mentions) + len(message.role_mentions) > max_mentions:
            return f"trop de mentions (>{max_mentions})"

        words = [w.strip().lower() for w in str(conf["banned_words"]).splitlines()
                 if w.strip()]
        lowered = content.lower()
        for word in words:
            if word in lowered:
                return f"mot interdit ({word})"

        if conf["anti_spam"]:
            key = (message.guild.id, message.author.id)
            now = time.time()
            bucket = self.history[key]
            bucket.append(now)
            window = int(conf["spam_window"])
            recent = [t for t in bucket if now - t <= window]
            if len(recent) >= int(conf["spam_messages"]):
                bucket.clear()
                return f"spam ({len(recent)} messages en {window}s)"

        return None

    async def sanction(self, message: discord.Message, conf: dict, reason: str) -> None:
        member = message.author
        guild = message.guild
        kind = conf["sanction"]
        full_reason = f"AutoMod : {reason}"

        try:
            if kind == "timeout":
                minutes = int(conf["timeout_minutes"])
                await member.timeout(timedelta(minutes=minutes), reason=full_reason)
                await db.run(db.execute,
                             """INSERT INTO sanctions (guild_id, user_id, kind, reason,
                                                       created_at, expires_at, active)
                                VALUES (?, ?, 'timeout', ?, ?, ?, 1)""",
                             (guild.id, member.id, full_reason, time.time(),
                              time.time() + minutes * 60))
            elif kind == "kick":
                await member.kick(reason=full_reason)
            elif kind == "ban":
                await member.ban(reason=full_reason, delete_message_days=1)
            elif kind == "warn":
                await self.add_warning(guild, member, full_reason, conf)
        except discord.HTTPException:
            log.warning("sanction automod impossible sur %s", member)
            return

        if kind != "delete":
            await db.run(db.bump_stat, guild.id, "sanctions")

        try:
            await message.channel.send(
                f"{member.mention} — message supprime ({reason}).",
                delete_after=8,
                allowed_mentions=discord.AllowedMentions(users=True),
            )
        except discord.HTTPException:
            pass

    async def add_warning(self, guild: discord.Guild, member: discord.Member,
                          reason: str, conf: dict) -> None:
        await db.run(db.execute,
                     """INSERT INTO warnings (guild_id, user_id, moderator_id, reason, created_at)
                        VALUES (?, ?, ?, ?, ?)""",
                     (guild.id, member.id, self.bot.user.id, reason, time.time()))
        limit = int(conf["warn_limit"] or 0)
        if limit <= 0:
            return
        rows = await db.run(
            db.query,
            "SELECT COUNT(*) AS n FROM warnings WHERE guild_id = ? AND user_id = ? AND active = 1",
            (guild.id, member.id),
        )
        if rows[0]["n"] >= limit:
            try:
                await member.ban(reason=f"AutoMod : {limit} avertissements atteints")
            except discord.HTTPException:
                pass

    # ── TASK : expiration des sanctions temporaires ────────────────────
    @tasks.loop(minutes=1)
    async def expire_sanctions(self) -> None:
        now = time.time()
        rows = await db.run(
            db.query,
            "SELECT * FROM sanctions WHERE active = 1 AND expires_at IS NOT NULL AND expires_at <= ?",
            (now,),
        )
        for row in rows:
            guild = self.bot.get_guild(row["guild_id"])
            if guild is not None and row["kind"] == "ban":
                try:
                    await guild.unban(discord.Object(id=row["user_id"]),
                                      reason="Fin du bannissement temporaire")
                except discord.HTTPException:
                    pass
            await db.run(db.execute, "UPDATE sanctions SET active = 0 WHERE id = ?",
                         (row["id"],))

    @expire_sanctions.before_loop
    async def _before_expire(self) -> None:
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(AutoMod(bot))
