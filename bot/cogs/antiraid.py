"""Module Anti-Raid.

TASKS :
  - decay      : purge les compteurs d'arrivees hors fenetre
  - unlock     : leve automatiquement le lockdown a la fin du delai
  - watchdog   : reevalue l'etat de raid toutes les 30 s
"""
from __future__ import annotations

import logging
import time
from collections import defaultdict, deque

import discord
from discord import app_commands
from discord.ext import commands, tasks

from bot.cogs import bridge
from core import database as db

log = logging.getLogger("modera.antiraid")


class AntiRaid(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        # guild_id -> deque des timestamps d'arrivee
        self.joins: dict[int, deque[float]] = defaultdict(lambda: deque(maxlen=200))
        # guild_id -> timestamp de fin de lockdown
        self.lockdown_until: dict[int, float] = {}
        self.raid_mode: set[int] = set()

    async def cog_load(self) -> None:
        self.decay.start()
        self.unlock.start()

    async def cog_unload(self) -> None:
        self.decay.cancel()
        self.unlock.cancel()

    # ── Detection ──────────────────────────────────────────────────────
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        guild = member.guild
        now = time.time()
        await db.run(db.bump_stat, guild.id, "joins")
        await db.run(db.execute,
                     """INSERT INTO join_log (guild_id, user_id, created_at, joined_at)
                        VALUES (?, ?, ?, ?)""",
                     (guild.id, member.id, member.created_at.timestamp(), now))

        conf = await db.run(db.get_config, guild.id, "antiraid")
        if not conf["enabled"]:
            return

        # 1) Compte trop recent
        min_age = int(conf["min_account_age"] or 0)
        if min_age > 0:
            age_days = (now - member.created_at.timestamp()) / 86400
            if age_days < min_age:
                await self.handle_young(member, conf, age_days)

        # 2) Vague d'arrivees
        window = int(conf["join_window"])
        bucket = self.joins[guild.id]
        bucket.append(now)
        recent = [t for t in bucket if now - t <= window]
        if len(recent) >= int(conf["join_threshold"]) and guild.id not in self.raid_mode:
            await self.trigger_raid(guild, conf, len(recent), window)

        if guild.id in self.raid_mode:
            await self.punish_raider(member, conf)

    async def handle_young(self, member: discord.Member, conf: dict, age_days: float) -> None:
        action = conf["young_account_action"]
        reason = f"Anti-raid : compte cree il y a {age_days:.1f} jour(s)"
        try:
            if action == "kick":
                await member.kick(reason=reason)
            elif action == "ban":
                await member.ban(reason=reason, delete_message_days=1)
            elif conf["quarantine_role_id"]:
                role = member.guild.get_role(int(conf["quarantine_role_id"]))
                if role:
                    await member.add_roles(role, reason=reason)
        except discord.HTTPException:
            log.warning("action compte recent impossible sur %s", member)
        await self.alert(member.guild, conf,
                         f"Compte recent : {member.mention} (`{member.id}`) — {age_days:.1f} j "
                         f"— action : **{action}**")

    async def punish_raider(self, member: discord.Member, conf: dict) -> None:
        action = conf["action"]
        try:
            if action == "kick":
                await member.kick(reason="Anti-raid : vague d'arrivees")
            elif action == "ban":
                await member.ban(reason="Anti-raid : vague d'arrivees",
                                 delete_message_days=1)
        except discord.HTTPException:
            pass

    async def trigger_raid(self, guild: discord.Guild, conf: dict,
                           count: int, window: int) -> None:
        self.raid_mode.add(guild.id)
        log.warning("RAID detecte sur %s : %s arrivees en %ss", guild.name, count, window)
        await self.alert(guild, conf,
                         f"@here **RAID DETECTE** : {count} arrivees en {window} s. "
                         f"Action : **{conf['action']}**.", ping=True)

        if conf["action"] == "lockdown":
            await self.set_lockdown(guild, True)
            minutes = int(conf["lockdown_minutes"])
            self.lockdown_until[guild.id] = time.time() + minutes * 60
            await db.run(db.set_state, f"lockdown:{guild.id}", True)

    async def set_lockdown(self, guild: discord.Guild, enable: bool) -> None:
        everyone = guild.default_role
        for channel in guild.text_channels:
            overwrite = channel.overwrites_for(everyone)
            if overwrite.send_messages is (False if enable else None):
                continue
            overwrite.send_messages = False if enable else None
            try:
                await channel.set_permissions(everyone, overwrite=overwrite,
                                              reason="Anti-raid")
            except discord.HTTPException:
                continue

    async def alert(self, guild: discord.Guild, conf: dict, text: str,
                    ping: bool = False) -> None:
        channel = guild.get_channel(int(conf["alert_channel_id"] or 0))
        if not isinstance(channel, discord.TextChannel):
            return
        embed = discord.Embed(title="Anti-Raid", description=text, colour=0xED4245,
                              timestamp=discord.utils.utcnow())
        await channel.send(
            embed=embed,
            allowed_mentions=discord.AllowedMentions(everyone=ping, users=False, roles=False),
        )

    # ── TASK : nettoyage des compteurs ─────────────────────────────────
    @tasks.loop(seconds=30)
    async def decay(self) -> None:
        now = time.time()
        for guild_id, bucket in list(self.joins.items()):
            while bucket and now - bucket[0] > 300:
                bucket.popleft()
            if not bucket:
                self.joins.pop(guild_id, None)
                self.raid_mode.discard(guild_id)

    # ── TASK : fin automatique du lockdown ─────────────────────────────
    @tasks.loop(seconds=30)
    async def unlock(self) -> None:
        now = time.time()
        for guild_id, deadline in list(self.lockdown_until.items()):
            if now < deadline:
                continue
            self.lockdown_until.pop(guild_id, None)
            self.raid_mode.discard(guild_id)
            guild = self.bot.get_guild(guild_id)
            if guild is None:
                continue
            await self.set_lockdown(guild, False)
            await db.run(db.set_state, f"lockdown:{guild_id}", False)
            conf = await db.run(db.get_config, guild_id, "antiraid")
            await self.alert(guild, conf, "Lockdown termine, le serveur est rouvert.")

    @decay.before_loop
    @unlock.before_loop
    async def _before(self) -> None:
        await self.bot.wait_until_ready()

    # ── Commandes ──────────────────────────────────────────────────────
    @app_commands.command(name="lockdown", description="Verrouiller/deverrouiller le serveur")
    @app_commands.default_permissions(manage_guild=True)
    async def lockdown_cmd(self, interaction: discord.Interaction, actif: bool) -> None:
        await interaction.response.defer(ephemeral=True)
        await self.set_lockdown(interaction.guild, actif)
        await db.run(db.set_state, f"lockdown:{interaction.guild.id}", actif)
        await interaction.followup.send(
            "Serveur verrouille." if actif else "Serveur deverrouille.", ephemeral=True)

    @app_commands.command(name="raidmode", description="Forcer la sortie du mode raid")
    @app_commands.default_permissions(manage_guild=True)
    async def raidmode(self, interaction: discord.Interaction) -> None:
        self.raid_mode.discard(interaction.guild.id)
        self.joins.pop(interaction.guild.id, None)
        await interaction.response.send_message("Mode raid reinitialise.", ephemeral=True)


# ── Actions dashboard ──────────────────────────────────────────────────
@bridge.action("raid_reset")
async def _raid_reset(self, guild, payload, author) -> str:
    cog = self.bot.get_cog("AntiRaid")
    if cog:
        cog.raid_mode.discard(guild.id)
        cog.joins.pop(guild.id, None)
        cog.lockdown_until.pop(guild.id, None)
    return "Mode raid reinitialise"


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(AntiRaid(bot))
