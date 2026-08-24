"""Module Niveaux : XP par message, annonces et classement."""
from __future__ import annotations

import random
import time

import discord
from discord import app_commands
from discord.ext import commands

from core import database as db


def xp_for_level(level: int) -> int:
    """XP total requis pour atteindre un niveau."""
    return 5 * level * level + 50 * level + 100


class Levels(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot or not message.guild:
            return
        conf = await db.run(db.get_config, message.guild.id, "levels")
        if not conf["enabled"]:
            return
        if str(message.channel.id) in map(str, conf["ignored_channel_ids"]):
            return

        now = time.time()
        row = await db.run(db.query_one,
                           "SELECT * FROM levels WHERE guild_id = ? AND user_id = ?",
                           (message.guild.id, message.author.id))
        if row and now - row["last_xp"] < int(conf["cooldown"]):
            return

        gained = random.randint(int(conf["xp_min"]), max(int(conf["xp_min"]),
                                                         int(conf["xp_max"])))
        total = (row["xp"] if row else 0) + gained
        level = row["level"] if row else 0

        new_level = level
        while total >= xp_for_level(new_level):
            new_level += 1

        await db.run(db.execute,
                     """INSERT INTO levels (guild_id, user_id, xp, level, last_xp)
                        VALUES (?, ?, ?, ?, ?)
                        ON CONFLICT(guild_id, user_id) DO UPDATE SET
                            xp = excluded.xp, level = excluded.level, last_xp = excluded.last_xp""",
                     (message.guild.id, message.author.id, total, new_level, now))

        if new_level > level and conf["announce"]:
            text = (str(conf["announce_message"])
                    .replace("{mention}", message.author.mention)
                    .replace("{user}", message.author.name)
                    .replace("{level}", str(new_level)))
            target = message.guild.get_channel(int(conf["announce_channel_id"] or 0))
            channel = target if isinstance(target, discord.TextChannel) else message.channel
            await channel.send(text, allowed_mentions=discord.AllowedMentions(users=True))

    @app_commands.command(name="rank", description="Voir ton niveau")
    async def rank(self, interaction: discord.Interaction,
                   membre: discord.Member | None = None) -> None:
        target = membre or interaction.user
        row = await db.run(db.query_one,
                           "SELECT * FROM levels WHERE guild_id = ? AND user_id = ?",
                           (interaction.guild.id, target.id))
        if not row:
            return await interaction.response.send_message("Aucune donnee.", ephemeral=True)
        needed = xp_for_level(row["level"])
        embed = discord.Embed(title=f"Niveau de {target.display_name}", colour=0x6AB3E8)
        embed.add_field(name="Niveau", value=str(row["level"]))
        embed.add_field(name="XP", value=f"{row['xp']} / {needed}")
        embed.set_thumbnail(url=target.display_avatar.url)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="leaderboard", description="Classement du serveur")
    async def leaderboard(self, interaction: discord.Interaction) -> None:
        rows = await db.run(
            db.query,
            "SELECT * FROM levels WHERE guild_id = ? ORDER BY xp DESC LIMIT 10",
            (interaction.guild.id,),
        )
        if not rows:
            return await interaction.response.send_message("Classement vide.", ephemeral=True)
        lines = [f"**{i}.** <@{row['user_id']}> — niveau {row['level']} ({row['xp']} XP)"
                 for i, row in enumerate(rows, 1)]
        embed = discord.Embed(title="Classement", description="\n".join(lines),
                              colour=0x6AB3E8)
        await interaction.response.send_message(
            embed=embed, allowed_mentions=discord.AllowedMentions.none())


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Levels(bot))
