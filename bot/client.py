"""Le client Discord. Tourne dans la boucle asyncio principale."""
from __future__ import annotations

import logging
import time

import discord
from discord.ext import commands, tasks

from core import config, database as db

log = logging.getLogger("modera.bot")

COGS = (
    "bot.cogs.bridge",
    "bot.cogs.tickets",
    "bot.cogs.antiraid",
    "bot.cogs.automod",
    "bot.cogs.moderation",
    "bot.cogs.welcome",
    "bot.cogs.logs",
    "bot.cogs.levels",
)


def build_intents() -> discord.Intents:
    intents = discord.Intents.default()
    intents.members = True          # arrivees/departs, anti-raid, autorole
    intents.message_content = True  # automod, XP
    intents.guilds = True
    return intents


class ModeraBot(commands.Bot):
    def __init__(self) -> None:
        super().__init__(
            command_prefix=commands.when_mentioned,
            intents=build_intents(),
            help_command=None,
            allowed_mentions=discord.AllowedMentions(everyone=False, roles=False),
        )
        self.started_at = time.time()

    async def setup_hook(self) -> None:
        for cog in COGS:
            try:
                await self.load_extension(cog)
                log.info("cog charge : %s", cog)
            except Exception:
                log.exception("echec du chargement de %s", cog)

        await self.tree.sync()
        self.heartbeat.start()

    async def on_ready(self) -> None:
        log.info("connecte en tant que %s (%s serveurs)", self.user, len(self.guilds))
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name=f"{len(self.guilds)} serveurs · /help",
            )
        )
        await self.sync_all_guilds()

    # ── Cache serveur pour le dashboard ────────────────────────────────
    async def sync_guild(self, guild: discord.Guild) -> None:
        """Ecrit salons/roles/stats du serveur en base pour que Flask les lise."""
        channels = [
            {
                "id": str(channel.id),
                "name": channel.name,
                "type": ("category" if isinstance(channel, discord.CategoryChannel)
                         else "voice" if isinstance(channel, discord.VoiceChannel)
                         else "forum" if isinstance(channel, discord.ForumChannel)
                         else "text"),
                "position": channel.position,
            }
            for channel in guild.channels
            if isinstance(channel, (discord.TextChannel, discord.VoiceChannel,
                                    discord.CategoryChannel, discord.ForumChannel))
        ]
        me = guild.me
        roles = [
            {
                "id": str(role.id),
                "name": role.name,
                "color": f"#{role.color.value:06x}" if role.color.value else "#99aab5",
                "position": role.position,
                "managed": role.managed,
                # le bot ne peut pas manipuler un role au-dessus du sien
                "assignable": bool(me and role < me.top_role and not role.managed
                                   and not role.is_default()),
            }
            for role in sorted(guild.roles, key=lambda r: r.position, reverse=True)
        ]
        await db.run(
            db.upsert_guild, guild.id, guild.name,
            guild.icon.key if guild.icon else None,
            guild.owner_id or 0, guild.member_count or 0, channels, roles,
        )

    async def sync_all_guilds(self) -> None:
        for guild in self.guilds:
            await self.sync_guild(guild)

    async def on_guild_join(self, guild: discord.Guild) -> None:
        await self.sync_guild(guild)

    async def on_guild_remove(self, guild: discord.Guild) -> None:
        await db.run(db.execute, "DELETE FROM guilds WHERE guild_id = ?", (guild.id,))

    async def on_guild_update(self, _before, after: discord.Guild) -> None:
        await self.sync_guild(after)

    # ── TASK : heartbeat + rafraichissement du cache ───────────────────
    @tasks.loop(seconds=30)
    async def heartbeat(self) -> None:
        """Le dashboard lit cet etat pour afficher "Bot en ligne" et la latence."""
        await db.run(db.set_state, "heartbeat", {
            "online": True,
            "latency_ms": round(self.latency * 1000, 1) if self.latency else 0,
            "guilds": len(self.guilds),
            "users": sum(g.member_count or 0 for g in self.guilds),
            "uptime": round(time.time() - self.started_at),
            "at": time.time(),
        })

    @heartbeat.before_loop
    async def _before_heartbeat(self) -> None:
        await self.wait_until_ready()

    async def close(self) -> None:
        await db.run(db.set_state, "heartbeat", {"online": False, "at": time.time()})
        await super().close()


def guild_config(guild_id: int, module: str) -> dict:
    """Raccourci synchrone (utilise dans les threads DB)."""
    return db.get_config(guild_id, module)
