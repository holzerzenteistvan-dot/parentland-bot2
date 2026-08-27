import discord
from discord.ext import commands
from discord import app_commands
import asyncio
from datetime import datetime
import zoneinfo

# ------------------- STAFF RANGOK ID-JEI -------------------
STAFF_ROLE_IDS = [
    1529858809106006136, # Bot parancsok-hoz (ENGEDÉLY)
    1530634556414365826, # Alapító
    1529131477756018779, # Tulajdonos
    1529131248075669634  # Admin
]

class UzenetModal(discord.ui.Modal, title="✉️ ParentLand Üzenet Készítő"):
    def __init__(self, target_channel: discord.TextChannel, image_file: discord.Attachment = None):
        super().__init__()
        self.target_channel = target_channel
        self.image_file = image_file

    cim = discord.ui.TextInput(
        label="📌 Üzenet Címe",
        style=discord.TextStyle.short,
        placeholder="Pl.: HATALMAS HÍR",
        default="HATALMAS HÍR",
        required=True,
        max_length=100
    )

    leiras = discord.ui.TextInput(
        label="📝 Fő tartalom / Leírás",
        style=discord.TextStyle.paragraph,
        placeholder="Írd ide a részletes szöveget (használhatsz @everyone, @role pingeket is)...",
        default="Írd ide a részletes szöveget...!\n\n",
        required=True,
        max_length=4000
    )

    datum_idozites = discord.ui.TextInput(
        label="📅 Időzítés DÁTUMMAL (Magyar idő szerint)",
        style=discord.TextStyle.short,
        placeholder="Pl: 2026.05.22 18:34 (opcionális)",
        required=False,
        max_length=20
    )

    perc_idozites = discord.ui.TextInput(
        label="⏱️ Időzítés PERCBEN (Alternatíva)",
        style=discord.TextStyle.short,
        placeholder="Pl: 10 (opcionális)",
        required=False,
        max_length=5
    )

    async def on_submit(self, interaction: discord.Interaction):
        delay_seconds = 0
        target_timestamp = None
        tz = zoneinfo.ZoneInfo("Europe/Budapest")
        now = datetime.now(tz)

        if self.datum_idozites.value.strip():
            raw_date = self.datum_idozites.value.strip().replace(".", "-").replace("/", "-")
            
            parsed_dt = None
            for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S"):
                try:
                    parsed_dt = datetime.strptime(raw_date, fmt)
                    break
                except ValueError:
                    pass

            if not parsed_dt:
                await interaction.response.send_message(
                    "❌ **Hibás dátum formátum!** Használd a következőt: `ÉÉÉÉ.HH.NN ÓÓ:PP`",
                    ephemeral=True
                )
                return

            target_dt = parsed_dt.replace(tzinfo=tz)
            if target_dt < now:
                await interaction.response.send_message("❌ Nem adhatsz meg múltbéli dátumot!", ephemeral=True)
                return

            delay_seconds = (target_dt - now).total_seconds()
            target_timestamp = int(target_dt.timestamp())

        elif self.perc_idozites.value.strip():
            try:
                minutes = float(self.perc_idozites.value.strip())
                if minutes < 0:
                    raise ValueError
                delay_seconds = minutes * 60
                target_timestamp = int(now.timestamp() + delay_seconds)
            except ValueError:
                await interaction.response.send_message("❌ A percnek pozitív számnak kell lennie!", ephemeral=True)
                return

        if delay_seconds > 0:
            await interaction.response.send_message(
                f"⏳ **Üzenet sikeresen időzítve!**\n"
                f"• **Célcsatorna:** {self.target_channel.mention}\n"
                f"• **Kiküldés:** <t:{target_timestamp}:F>",
                ephemeral=True
            )
            await asyncio.sleep(delay_seconds)
        else:
            await interaction.response.send_message(
                f"✅ **Üzenet azonnal kiküldve ide:** {self.target_channel.mention}",
                ephemeral=True
            )

        formatted_description = f"# **{self.cim.value}**\n\n{self.leiras.value}"

        embed = discord.Embed(
            description=formatted_description,
            color=discord.Color.from_rgb(255, 140, 0)
        )

        if interaction.guild.icon:
            embed.set_thumbnail(url=interaction.guild.icon.url)

        if self.image_file:
            embed.set_image(url=self.image_file.url)

        embed.add_field(
            name="━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            value="🌐 **Web:** HAMAROSAN... | 🖥️ **IP:**parentland.ggwp.cc",
            inline=False
        )

        embed.set_footer(
            text="A ParentLand csapata Jóváhagyásával",
            icon_url=interaction.guild.icon.url if interaction.guild.icon else None
        )
        embed.timestamp = discord.utils.utcnow()

        # ENGEDÉLYEZÜK A PINGELÉST (@everyone, rangok, felhasználók)
        allowed_mentions = discord.AllowedMentions(everyone=True, roles=True, users=True)
        
        await self.target_channel.send(embed=embed, allowed_mentions=allowed_mentions)


class UzenetCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="üzenet", 
        description="Létrehoz egy formázott ParentLand beágyazott (embed) üzenetet a kiválasztott csatornára."
    )
    @app_commands.describe(
        csatorna="Melyik szobába küldje a bot az üzenetet?", 
        kep="Tölts fel egy képet az üzenethez (Opcionális)"
    )
    @app_commands.checks.has_any_role(*STAFF_ROLE_IDS)
    async def uzenet_parancs(
        self, 
        interaction: discord.Interaction, 
        csatorna: discord.TextChannel, 
        kep: discord.Attachment = None
    ):
        await interaction.response.send_modal(UzenetModal(target_channel=csatorna, image_file=kep))

    @uzenet_parancs.error
    async def uzenet_parancs_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, (app_commands.MissingRole, app_commands.MissingAnyRole)):
            roles_mentions = ", ".join([f"<@&{r_id}>" for r_id in STAFF_ROLE_IDS])
            await interaction.response.send_message(
                f"🚫 **Nincs jogosultságod!** Ezt a parancsot csak a következő rangok valamelyikével használhatod: {roles_mentions}", 
                ephemeral=True
            )
        else:
            await interaction.response.send_message("❌ Váratlan hiba történt a parancs futtatása közben.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(UzenetCog(bot))