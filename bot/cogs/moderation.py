"""Commandes de moderation classiques (miroir des actions du dashboard)."""
from __future__ import annotations

import time
from datetime import timedelta

import discord
from discord import app_commands
from discord.ext import commands

from core import database as db


class Moderation(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def log_sanction(self, guild_id: int, user_id: int, kind: str,
                           reason: str, moderator_id: int,
                           expires_at: float | None = None) -> None:
        await db.run(db.execute,
                     """INSERT INTO sanctions (guild_id, user_id, kind, reason, moderator_id,
                                               created_at, expires_at, active)
                        VALUES (?, ?, ?, ?, ?, ?, ?, 1)""",
                     (guild_id, user_id, kind, reason, moderator_id, time.time(), expires_at))
        await db.run(db.bump_stat, guild_id, "sanctions")

    @app_commands.command(name="ban", description="Bannir un membre")
    @app_commands.default_permissions(ban_members=True)
    async def ban(self, interaction: discord.Interaction, membre: discord.Member,
                  raison: str = "Aucune raison", jours: int = 0) -> None:
        await membre.ban(reason=f"{interaction.user} : {raison}",
                         delete_message_days=max(0, min(7, jours)))
        await self.log_sanction(interaction.guild.id, membre.id, "ban", raison,
                                interaction.user.id)
        await interaction.response.send_message(f"{membre} banni. Raison : {raison}")

    @app_commands.command(name="kick", description="Expulser un membre")
    @app_commands.default_permissions(kick_members=True)
    async def kick(self, interaction: discord.Interaction, membre: discord.Member,
                   raison: str = "Aucune raison") -> None:
        await membre.kick(reason=f"{interaction.user} : {raison}")
        await self.log_sanction(interaction.guild.id, membre.id, "kick", raison,
                                interaction.user.id)
        await interaction.response.send_message(f"{membre} expulse. Raison : {raison}")

    @app_commands.command(name="mute", description="Exclure temporairement un membre")
    @app_commands.default_permissions(moderate_members=True)
    async def mute(self, interaction: discord.Interaction, membre: discord.Member,
                   minutes: int = 10, raison: str = "Aucune raison") -> None:
        minutes = max(1, min(40320, minutes))
        await membre.timeout(timedelta(minutes=minutes), reason=f"{interaction.user} : {raison}")
        await self.log_sanction(interaction.guild.id, membre.id, "timeout", raison,
                                interaction.user.id, time.time() + minutes * 60)
        await interaction.response.send_message(f"{membre} exclu {minutes} min. Raison : {raison}")

    @app_commands.command(name="warn", description="Avertir un membre")
    @app_commands.default_permissions(moderate_members=True)
    async def warn(self, interaction: discord.Interaction, membre: discord.Member,
                   raison: str = "Aucune raison") -> None:
        await db.run(db.execute,
                     """INSERT INTO warnings (guild_id, user_id, moderator_id, reason, created_at)
                        VALUES (?, ?, ?, ?, ?)""",
                     (interaction.guild.id, membre.id, interaction.user.id, raison, time.time()))
        await db.run(db.bump_stat, interaction.guild.id, "sanctions")
        await interaction.response.send_message(f"{membre} averti. Raison : {raison}")

    @app_commands.command(name="warnings", description="Voir les avertissements d'un membre")
    async def warnings(self, interaction: discord.Interaction,
                       membre: discord.Member) -> None:
        rows = await db.run(
            db.query,
            """SELECT * FROM warnings WHERE guild_id = ? AND user_id = ? AND active = 1
               ORDER BY id DESC LIMIT 10""",
            (interaction.guild.id, membre.id),
        )
        if not rows:
            return await interaction.response.send_message("Aucun avertissement.",
                                                           ephemeral=True)
        embed = discord.Embed(title=f"Avertissements de {membre}", colour=0x6AB3E8)
        for row in rows:
            stamp = time.strftime("%d/%m/%Y", time.localtime(row["created_at"]))
            embed.add_field(name=f"#{row['id']} — {stamp}",
                            value=f"{row['reason']} (par <@{row['moderator_id']}>)",
                            inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="clear", description="Supprimer des messages")
    @app_commands.default_permissions(manage_messages=True)
    async def clear(self, interaction: discord.Interaction, nombre: int = 10) -> None:
        nombre = max(1, min(200, nombre))
        await interaction.response.defer(ephemeral=True)
        deleted = await interaction.channel.purge(limit=nombre)
        await interaction.followup.send(f"{len(deleted)} messages supprimes.", ephemeral=True)

    @commands.Cog.listener()
    async def on_app_command_completion(self, interaction: discord.Interaction,
                                        _command) -> None:
        if interaction.guild:
            await db.run(db.bump_stat, interaction.guild.id, "commands")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Moderation(bot))
