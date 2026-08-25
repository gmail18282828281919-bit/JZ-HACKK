"""Commande !reglement : le bot poste le règlement en embed.

    pip install -U discord.py
    python3 discord/reglement_bot.py        (mets ton token dans DISCORD_TOKEN)

Le contenu de l'embed est lu depuis reglement-embed.json, à côté de ce
fichier : tu modifies le règlement sans toucher au code.
"""
import json
import os
import pathlib

import discord
from discord.ext import commands

EMBED_FILE = pathlib.Path(__file__).with_name("reglement-embed.json")

bot = commands.Bot(command_prefix="!", intents=discord.Intents.default())


def build_embed():
    data = json.loads(EMBED_FILE.read_text(encoding="utf-8"))
    return discord.Embed.from_dict(data["embeds"][0])


@bot.command(name="reglement")
@commands.has_permissions(manage_guild=True)
async def reglement(ctx, salon: discord.TextChannel = None):
    """Poste le règlement dans le salon indiqué (ou dans le salon courant)."""
    await (salon or ctx.channel).send(embed=build_embed())
    if salon:
        await ctx.reply(f"Règlement posté dans {salon.mention}.")


@reglement.error
async def reglement_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.reply("Il faut la permission « Gérer le serveur » pour ça.")
    else:
        raise error


if __name__ == "__main__":
    token = os.environ.get("DISCORD_TOKEN")
    if not token:
        raise SystemExit("Mets ton token dans la variable DISCORD_TOKEN.")
    bot.run(token)
