"""Module Logs : journalisation des evenements du serveur."""
from __future__ import annotations

import discord
from discord.ext import commands

from core import database as db

COLOURS = {
    "delete": 0xED4245,
    "edit": 0xFAA61A,
    "join": 0x3BA55D,
    "leave": 0x5A6387,
    "update": 0x6AB3E8,
}


class Logs(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def send(self, guild: discord.Guild, key: str, embed: discord.Embed) -> None:
        conf = await db.run(db.get_config, guild.id, "logs")
        if not (conf["enabled"] and conf.get(key) and conf["channel_id"]):
            return
        channel = guild.get_channel(int(conf["channel_id"]))
        if isinstance(channel, discord.TextChannel):
            try:
                await channel.send(embed=embed)
            except discord.HTTPException:
                pass

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message) -> None:
        if not message.guild or message.author.bot:
            return
        embed = discord.Embed(title="Message supprime", colour=COLOURS["delete"],
                              description=message.content[:2000] or "*(sans texte)*",
                              timestamp=discord.utils.utcnow())
        embed.add_field(name="Auteur", value=f"{message.author} (`{message.author.id}`)")
        embed.add_field(name="Salon", value=message.channel.mention)
        await self.send(message.guild, "message_delete", embed)

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message,
                              after: discord.Message) -> None:
        if not before.guild or before.author.bot or before.content == after.content:
            return
        embed = discord.Embed(title="Message modifie", colour=COLOURS["edit"],
                              timestamp=discord.utils.utcnow())
        embed.add_field(name="Avant", value=before.content[:1000] or "*(vide)*", inline=False)
        embed.add_field(name="Apres", value=after.content[:1000] or "*(vide)*", inline=False)
        embed.add_field(name="Auteur", value=f"{before.author} (`{before.author.id}`)")
        embed.add_field(name="Salon", value=before.channel.mention)
        await self.send(before.guild, "message_edit", embed)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        embed = discord.Embed(title="Arrivee", colour=COLOURS["join"],
                              description=f"{member.mention} — `{member.id}`",
                              timestamp=discord.utils.utcnow())
        embed.add_field(name="Compte cree",
                        value=discord.utils.format_dt(member.created_at, "R"))
        embed.set_thumbnail(url=member.display_avatar.url)
        await self.send(member.guild, "member_join", embed)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member) -> None:
        roles = ", ".join(r.name for r in member.roles if not r.is_default()) or "aucun"
        embed = discord.Embed(title="Depart", colour=COLOURS["leave"],
                              description=f"{member} — `{member.id}`",
                              timestamp=discord.utils.utcnow())
        embed.add_field(name="Roles", value=roles[:1000], inline=False)
        await self.send(member.guild, "member_leave", embed)

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member,
                               after: discord.Member) -> None:
        changes = []
        if before.nick != after.nick:
            changes.append(f"Pseudo : `{before.nick}` -> `{after.nick}`")
        added = set(after.roles) - set(before.roles)
        removed = set(before.roles) - set(after.roles)
        if added:
            changes.append("Roles ajoutes : " + ", ".join(r.name for r in added))
        if removed:
            changes.append("Roles retires : " + ", ".join(r.name for r in removed))
        if not changes:
            return
        embed = discord.Embed(title="Membre modifie", colour=COLOURS["update"],
                              description=f"{after} — `{after.id}`\n" + "\n".join(changes),
                              timestamp=discord.utils.utcnow())
        await self.send(after.guild, "member_update", embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Logs(bot))
