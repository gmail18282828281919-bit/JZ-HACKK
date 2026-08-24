"""Module Bienvenue : messages d'arrivee/depart, MP et roles automatiques."""
from __future__ import annotations

import logging

import discord
from discord.ext import commands

from core import database as db

log = logging.getLogger("modera.welcome")


def render(template: str, member: discord.Member) -> str:
    guild = member.guild
    return (str(template)
            .replace("{mention}", member.mention)
            .replace("{user}", member.name)
            .replace("{tag}", str(member))
            .replace("{id}", str(member.id))
            .replace("{server}", guild.name)
            .replace("{count}", str(guild.member_count or 0)))[:2000]


class Welcome(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        conf = await db.run(db.get_config, member.guild.id, "welcome")
        if not conf["enabled"]:
            return

        channel = member.guild.get_channel(int(conf["channel_id"] or 0))
        if isinstance(channel, discord.TextChannel):
            embed = discord.Embed(description=render(conf["message"], member),
                                  colour=0x6AB3E8)
            embed.set_thumbnail(url=member.display_avatar.url)
            await channel.send(content=member.mention, embed=embed,
                               allowed_mentions=discord.AllowedMentions(users=True))

        if conf["dm_enabled"]:
            try:
                await member.send(render(conf["dm_message"], member))
            except discord.HTTPException:
                pass

        roles = []
        for role_id in conf["autorole_ids"]:
            role = member.guild.get_role(int(role_id))
            if role and role < member.guild.me.top_role and not role.managed:
                roles.append(role)
        if roles:
            try:
                await member.add_roles(*roles, reason="Role automatique")
            except discord.HTTPException:
                log.warning("autorole impossible sur %s", member)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member) -> None:
        await db.run(db.bump_stat, member.guild.id, "leaves")
        conf = await db.run(db.get_config, member.guild.id, "welcome")
        if not (conf["enabled"] and conf["leave_enabled"]):
            return
        channel = member.guild.get_channel(int(conf["leave_channel_id"] or 0))
        if isinstance(channel, discord.TextChannel):
            await channel.send(
                embed=discord.Embed(description=render(conf["leave_message"], member),
                                    colour=0x5A6387),
                allowed_mentions=discord.AllowedMentions.none(),
            )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Welcome(bot))
