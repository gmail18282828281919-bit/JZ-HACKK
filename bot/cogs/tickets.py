"""Module Tickets : panneau persistant, ouverture/fermeture, transcripts.

TASKS :
  - auto_close : ferme les tickets inactifs depuis N heures (configurable dashboard)
"""
from __future__ import annotations

import asyncio
import io
import logging
import time

import discord
from discord import app_commands
from discord.ext import commands, tasks

from bot.cogs import bridge
from core import database as db

log = logging.getLogger("modera.tickets")


async def open_ticket(bot: commands.Bot, guild: discord.Guild,
                      member: discord.Member) -> tuple[bool, str]:
    """Cree le salon du ticket. Renvoie (succes, message)."""
    conf = await db.run(db.get_config, guild.id, "tickets")
    if not conf["enabled"]:
        return False, "Le systeme de tickets est desactive."

    rows = await db.run(
        db.query,
        "SELECT COUNT(*) AS n FROM tickets WHERE guild_id = ? AND user_id = ? AND status = 'open'",
        (guild.id, member.id),
    )
    if rows[0]["n"] >= int(conf["max_per_user"]):
        return False, f"Tu as deja {rows[0]['n']} ticket(s) ouvert(s)."

    category = guild.get_channel(int(conf["category_id"] or 0))
    if not isinstance(category, discord.CategoryChannel):
        category = None

    staff_roles = [guild.get_role(int(rid)) for rid in conf["staff_role_ids"]]
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        member: discord.PermissionOverwrite(view_channel=True, send_messages=True,
                                            attach_files=True, read_message_history=True),
        guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True,
                                              manage_channels=True),
    }
    for role in staff_roles:
        if role is not None:
            overwrites[role] = discord.PermissionOverwrite(
                view_channel=True, send_messages=True, read_message_history=True)

    channel = await guild.create_text_channel(
        name=f"ticket-{member.name}"[:100],
        category=category,
        overwrites=overwrites,
        reason=f"Ticket ouvert par {member}",
    )

    now = time.time()
    ticket_id = await db.run(
        db.execute,
        """INSERT INTO tickets (guild_id, channel_id, user_id, opened_at, last_activity)
           VALUES (?, ?, ?, ?, ?)""",
        (guild.id, channel.id, member.id, now, now),
    )

    mentions = " ".join(role.mention for role in staff_roles if role)
    embed = discord.Embed(
        title=f"Ticket #{ticket_id}",
        description=str(conf["open_message"]),
        colour=0x6AB3E8,
        timestamp=discord.utils.utcnow(),
    )
    embed.set_footer(text=f"Ouvert par {member}", icon_url=member.display_avatar.url)
    await channel.send(
        content=f"{member.mention} {mentions}".strip(),
        embed=embed,
        view=TicketControls(),
        allowed_mentions=discord.AllowedMentions(users=True, roles=True),
    )
    return True, channel.mention


async def close_ticket(bot: commands.Bot, guild: discord.Guild, ticket: dict,
                       closed_by: int, reason: str = "") -> str:
    conf = await db.run(db.get_config, guild.id, "tickets")
    channel = guild.get_channel(int(ticket["channel_id"]))
    transcript = ""

    if channel is not None and conf["transcript"]:
        lines = []
        async for message in channel.history(limit=500, oldest_first=True):
            stamp = message.created_at.strftime("%d/%m %H:%M")
            lines.append(f"[{stamp}] {message.author}: {message.clean_content}")
        transcript = "\n".join(lines)

        log_channel = guild.get_channel(int(conf["log_channel_id"] or 0))
        if isinstance(log_channel, discord.TextChannel) and transcript:
            await log_channel.send(
                content=f"Transcript du ticket #{ticket['id']} (ferme par <@{closed_by}>)",
                file=discord.File(io.BytesIO(transcript.encode("utf-8")),
                                  filename=f"ticket-{ticket['id']}.txt"),
                allowed_mentions=discord.AllowedMentions.none(),
            )

    await db.run(
        db.execute,
        """UPDATE tickets SET status = 'closed', closed_at = ?, closed_by = ?, transcript = ?
           WHERE id = ?""",
        (time.time(), closed_by, transcript[:100000], ticket["id"]),
    )

    if channel is not None:
        await channel.delete(reason=f"Ticket ferme : {reason or 'aucune raison'}")
    return f"Ticket #{ticket['id']} ferme"


class TicketPanel(discord.ui.View):
    """Vue persistante du panneau (custom_id fixe : survit aux redemarrages)."""

    def __init__(self) -> None:
        super().__init__(timeout=None)

    @discord.ui.button(label="Ouvrir un ticket", emoji="\N{ADMISSION TICKETS}",
                       style=discord.ButtonStyle.primary, custom_id="modera:ticket:open")
    async def open(self, interaction: discord.Interaction, _button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True, thinking=True)
        ok, message = await open_ticket(interaction.client, interaction.guild,
                                        interaction.user)
        await interaction.followup.send(
            f"Ton ticket : {message}" if ok else message, ephemeral=True)


class TicketControls(discord.ui.View):
    def __init__(self) -> None:
        super().__init__(timeout=None)

    @discord.ui.button(label="Fermer", emoji="\N{LOCK}", style=discord.ButtonStyle.danger,
                       custom_id="modera:ticket:close")
    async def close(self, interaction: discord.Interaction, _button: discord.ui.Button):
        rows = await db.run(db.query,
                            "SELECT * FROM tickets WHERE channel_id = ? AND status = 'open'",
                            (interaction.channel.id,))
        if not rows:
            return await interaction.response.send_message("Ticket introuvable.",
                                                           ephemeral=True)
        ticket = dict(rows[0])
        conf = await db.run(db.get_config, interaction.guild.id, "tickets")
        is_staff = (interaction.user.guild_permissions.manage_guild
                    or any(role.id in [int(r) for r in conf["staff_role_ids"]]
                           for role in interaction.user.roles)
                    or interaction.user.id == ticket["user_id"])
        if not is_staff:
            return await interaction.response.send_message(
                "Seuls le staff et l'auteur peuvent fermer ce ticket.", ephemeral=True)

        await interaction.response.send_message("Fermeture dans 3 secondes...")
        await asyncio.sleep(3)
        await close_ticket(interaction.client, interaction.guild, ticket,
                           interaction.user.id, "bouton")

    @discord.ui.button(label="Prendre en charge", emoji="\N{RAISED HAND}",
                       style=discord.ButtonStyle.secondary, custom_id="modera:ticket:claim")
    async def claim(self, interaction: discord.Interaction, _button: discord.ui.Button):
        conf = await db.run(db.get_config, interaction.guild.id, "tickets")
        staff_ids = [int(r) for r in conf["staff_role_ids"]]
        if not (interaction.user.guild_permissions.manage_guild
                or any(role.id in staff_ids for role in interaction.user.roles)):
            return await interaction.response.send_message("Reserve au staff.", ephemeral=True)
        await db.run(db.execute,
                     "UPDATE tickets SET claimed_by = ? WHERE channel_id = ? AND status = 'open'",
                     (interaction.user.id, interaction.channel.id))
        await interaction.response.send_message(
            f"{interaction.user.mention} prend ce ticket en charge.")


class Tickets(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def cog_load(self) -> None:
        self.bot.add_view(TicketPanel())
        self.bot.add_view(TicketControls())
        self.auto_close.start()

    async def cog_unload(self) -> None:
        self.auto_close.cancel()

    # ── TASK : fermeture automatique des tickets inactifs ──────────────
    @tasks.loop(minutes=10)
    async def auto_close(self) -> None:
        for guild in self.bot.guilds:
            conf = await db.run(db.get_config, guild.id, "tickets")
            hours = int(conf["auto_close_hours"] or 0)
            if not conf["enabled"] or hours <= 0:
                continue
            cutoff = time.time() - hours * 3600
            rows = await db.run(
                db.query,
                "SELECT * FROM tickets WHERE guild_id = ? AND status = 'open' AND last_activity < ?",
                (guild.id, cutoff),
            )
            for row in rows:
                try:
                    await close_ticket(self.bot, guild, dict(row), self.bot.user.id,
                                       "inactivite")
                except discord.HTTPException:
                    log.warning("fermeture auto impossible pour le ticket %s", row["id"])

    @auto_close.before_loop
    async def _before_auto_close(self) -> None:
        await self.bot.wait_until_ready()

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot or not message.guild:
            return
        await db.run(db.execute,
                     "UPDATE tickets SET last_activity = ? WHERE channel_id = ? AND status = 'open'",
                     (time.time(), message.channel.id))

    # ── Commandes ──────────────────────────────────────────────────────
    @app_commands.command(name="panel", description="Publier le panneau de tickets")
    @app_commands.default_permissions(manage_guild=True)
    async def panel(self, interaction: discord.Interaction,
                    salon: discord.TextChannel | None = None) -> None:
        conf = await db.run(db.get_config, interaction.guild.id, "tickets")
        channel = salon or interaction.guild.get_channel(int(conf["panel_channel_id"] or 0))
        if not isinstance(channel, discord.TextChannel):
            return await interaction.response.send_message(
                "Configure d'abord le salon du panneau sur le dashboard.", ephemeral=True)
        embed = discord.Embed(title=str(conf["panel_title"]),
                              description=str(conf["panel_message"]), colour=0x6AB3E8)
        await channel.send(embed=embed, view=TicketPanel())
        await interaction.response.send_message(f"Panneau publie dans {channel.mention}",
                                                ephemeral=True)

    @app_commands.command(name="close", description="Fermer le ticket courant")
    async def close(self, interaction: discord.Interaction, raison: str = "") -> None:
        rows = await db.run(db.query,
                            "SELECT * FROM tickets WHERE channel_id = ? AND status = 'open'",
                            (interaction.channel.id,))
        if not rows:
            return await interaction.response.send_message("Ce salon n'est pas un ticket.",
                                                           ephemeral=True)
        await interaction.response.send_message("Fermeture du ticket...")
        await close_ticket(self.bot, interaction.guild, dict(rows[0]),
                           interaction.user.id, raison)


# ── Actions exposees au dashboard ──────────────────────────────────────
@bridge.action("post_ticket_panel")
async def _post_panel(self, guild, payload, author) -> str:
    conf = await db.run(db.get_config, guild.id, "tickets")
    channel = self.text_channel(guild, payload.get("channel_id") or conf["panel_channel_id"])
    embed = discord.Embed(title=str(conf["panel_title"]),
                          description=str(conf["panel_message"]), colour=0x6AB3E8)
    await channel.send(embed=embed, view=TicketPanel())
    return f"Panneau de tickets publie dans #{channel.name}"


@bridge.action("close_ticket")
async def _close_ticket(self, guild, payload, author) -> str:
    rows = await db.run(db.query,
                        "SELECT * FROM tickets WHERE id = ? AND guild_id = ? AND status = 'open'",
                        (int(payload.get("ticket_id") or 0), guild.id))
    if not rows:
        raise bridge.PermissionDenied("Ticket introuvable ou deja ferme.")
    return await close_ticket(self.bot, guild, dict(rows[0]), author.id, "dashboard")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Tickets(bot))
