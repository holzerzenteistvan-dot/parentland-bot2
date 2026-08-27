import asyncio
import json
import os
import random
import discord
from discord import app_commands
from discord.ext import commands

SZINT_FAJL = "szint_rendszer.json"
SZINT_BEALLITAS_FAJL = "szint_beallitasok.json"
SZINT_TOP_FAJL = "szint_top_uzenet.json"


def szint_betoltes():
    if os.path.exists(SZINT_FAJL):
        try:
            with open(SZINT_FAJL, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}
    return {}


def szint_mentes(adatok):
    with open(SZINT_FAJL, "w", encoding="utf-8") as f:
        json.dump(adatok, f, ensure_ascii=False, indent=4)


def beallitas_betoltes():
    if os.path.exists(SZINT_BEALLITAS_FAJL):
        try:
            with open(SZINT_BEALLITAS_FAJL, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}
    return {}


def beallitas_mentes(adatok):
    with open(SZINT_BEALLITAS_FAJL, "w", encoding="utf-8") as f:
        json.dump(adatok, f, ensure_ascii=False, indent=4)


def top_uzenet_betoltes():
    if os.path.exists(SZINT_TOP_FAJL):
        try:
            with open(SZINT_TOP_FAJL, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return None
    return None


def top_uzenet_mentes(adat):
    with open(SZINT_TOP_FAJL, "w", encoding="utf-8") as f:
        json.dump(adat, f, ensure_ascii=False, indent=4)


def keszit_szint_top_embed(guild):
    data = szint_betoltes()
    embed = discord.Embed(
        title="📈 ÉLŐ XP TOPLISTA",
        color=discord.Color.orange(),
    )

    if not data:
        embed.description = "Még nincsenek rögzített adatok a szintrendszerben!"
        return embed

    rendezett = sorted(
        data.items(),
        key=lambda x: (x[1].get("level", 1), x[1].get("xp", 0)),
        reverse=True,
    )[:15]

    szoveg = ""
    for i, (u_id_str, info) in enumerate(rendezett, 1):
        u_id = int(u_id_str)
        member = guild.get_member(u_id) if guild else None
        m_mention = member.mention if member else f"<@id:{u_id}>"
        
        lvl = info.get("level", 1)
        xp = info.get("xp", 0)
        req_xp = lvl * 100

        szoveg += (
            f"**{i}.** {m_mention}\n"
            f" └ Szint: `{lvl}` | XP: `{xp} / {req_xp}`\n"
        )

    embed.description = szoveg
    return embed


async def frissit_szint_toplista(bot):
    adat = top_uzenet_betoltes()
    if not adat:
        return

    channel_id = adat.get("channel_id")
    message_id = adat.get("message_id")

    channel = bot.get_channel(channel_id)
    if not channel:
        try:
            channel = await bot.fetch_channel(channel_id)
        except:
            return

    try:
        message = await channel.fetch_message(message_id)
        embed = keszit_szint_top_embed(channel.guild)
        await message.edit(embed=embed)
    except:
        pass


class LevelingSystem(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        u_id_str = str(message.author.id)
        data = szint_betoltes()

        if u_id_str not in data:
            data[u_id_str] = {"xp": 0, "level": 1}

        old_level = data[u_id_str]["level"]
        data[u_id_str]["xp"] += random.randint(15, 25)

        # Ciklus, ami kezeli az összes szintlépést (akár több szintet is ugorhat egyszerre)
        while True:
            current_lvl = data[u_id_str]["level"]
            req_xp = current_lvl * 100
            if data[u_id_str]["xp"] >= req_xp:
                data[u_id_str]["xp"] -= req_xp
                data[u_id_str]["level"] += 1
            else:
                break

        new_level = data[u_id_str]["level"]
        szint_mentes(data)

        # Ha történt szintlépés (akár több is)
        if new_level > old_level:
            beallitasok = beallitas_betoltes()
            ch_id = beallitasok.get("channel_id")
            if ch_id:
                ch = self.bot.get_channel(ch_id)
                if not ch:
                    try:
                        ch = await self.bot.fetch_channel(ch_id)
                    except:
                        ch = None

                if ch:
                    ugras_szoveg = f" *(Szintugrás: {old_level} ➔ {new_level})*" if new_level - old_level > 1 else ""
                    
                    embed = discord.Embed(
                        title="🎉 Új Szint Elérve!",
                        description=(
                            f"Fantasztikus teljesítmény, {message.author.mention}!\n"
                            f"Sikeresen elérted a(z) **{new_level}. szintet**!{ugras_szoveg}\n\n"
                            "🚀 *Csak így tovább, folytasd a beszélgetést a további fejlődésért!*"
                        ),
                        color=discord.Color.orange(),
                    )
                    await ch.send(embed=embed)

        await frissit_szint_toplista(self.bot)

    @app_commands.command(
        name="szintlépés_üzenet",
        description="Állítsd be a csatornát, ahova a szintlépési üzenetek érkeznek!",
    )
    @app_commands.describe(csatorna="Válaszd ki azt a csatornát, ahova a bot küldje a szintlépéseket")
    @app_commands.checks.has_permissions(administrator=True)
    async def szintlepes_uzenet(
        self, interaction: discord.Interaction, csatorna: discord.TextChannel
    ):
        beallitasok = beallitas_betoltes()
        beallitasok["channel_id"] = csatorna.id
        beallitas_mentes(beallitasok)

        await interaction.response.send_message(
            f"✅ A szintlépési üzenetek csatornája sikeresen beállítva ide: {csatorna.mention}!",
            ephemeral=True,
        )

    @app_commands.command(
        name="szintlépés_top",
        description="Létrehozza az élő XP toplistát a megadott csatornában!",
    )
    @app_commands.describe(
        csatorna="Válaszd ki a csatornát, ahova a toplistát írja (alapértelmezett a jelenlegi)"
    )
    async def szintlepes_top(
        self, interaction: discord.Interaction, csatorna: discord.TextChannel = None
    ):
        cel_csatorna = csatorna if csatorna else interaction.channel
        embed = keszit_szint_top_embed(interaction.guild)

        uzenet = await cel_csatorna.send(embed=embed)

        top_uzenet_mentes({
            "channel_id": cel_csatorna.id,
            "message_id": uzenet.id,
        })

        await interaction.response.send_message(
            "✅ Az élő XP toplista üzenet sikeresen létrehozva ebben a csatornában!",
            ephemeral=True,
        )


async def setup(bot):
    await bot.add_cog(LevelingSystem(bot))