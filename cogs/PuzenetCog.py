import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import re

# ------------------- STAFF RANGOK ID-JEI -------------------
STAFF_ROLE_IDS = [
    1529858809106006136, # Bot parancsok-hoz (ENGEDÉLY)
    1530634556414365826, # Alapító
    1529131477756018779, # Tulajdonos
    840270209913847869
]

# ------------------- PRIVÁT ÜZENET MODAL -------------------
class PuzenetModal(discord.ui.Modal, title="✉️ ParentLand Privát Üzenet"):
    cim_input = discord.ui.TextInput(
        label="📌 Üzenet Címe",
        style=discord.TextStyle.short,
        placeholder="Pl.: Fontos Hirdetmény / Szerver Info",
        required=True,
        max_length=100
    )
    leiras_input = discord.ui.TextInput(
        label="📝 Fő tartalom / Leírás",
        style=discord.TextStyle.paragraph,
        placeholder="Írd ide a privát üzenet tartalmát...",
        required=True,
        max_length=2000
    )
    idozites_input = discord.ui.TextInput(
        label="⏱️ Időzítés másodpercben (Kihagyható)",
        placeholder="Pl.: 10 (vagy hagyd üresen az azonnali küldéshez)",
        required=False,
        max_length=10
    )

    def __init__(self, target_str: str):
        super().__init__()
        self.target_str = target_str

    async def on_submit(self, interaction: discord.Interaction):
        delay = 0
        raw_delay = self.idozites_input.value.strip()
        if raw_delay:
            if raw_delay.isdigit():
                delay = int(raw_delay)
            else:
                await interaction.response.send_message("❌ Az időzítésnek érvényes számnak kell lennie (másodpercben)!", ephemeral=True)
                return

        await interaction.response.send_message(
            f"✅ **A feladat rögzítve!** A privát üzenetek ki lesznek küldve" + (f" {delay} másodperc múlva." if delay > 0 else " azonnal."),
            ephemeral=True
        )

        asyncio.create_task(
            send_puzenet_background_task(
                guild=interaction.guild,
                sender=interaction.user,
                target_str=self.target_str,
                title=self.cim_input.value,
                description=self.leiras_input.value,
                delay=delay
            )
        )

# ------------------- HÁTTÉRFELADAT A KÜLDÉSHEZ -------------------
async def send_puzenet_background_task(guild: discord.Guild, sender: discord.Member, target_str: str, title: str, description: str, delay: int):
    if delay > 0:
        await asyncio.sleep(delay)

    target_str_clean = target_str.strip().lower()
    recipients = set()

    if target_str_clean in ["everyone", "@everyone", "mindenki", "@mindenki"]:
        recipients = set(guild.members)
    elif target_str_clean in ["here", "@here"]:
        recipients = {m for m in guild.members if m.status != discord.Status.offline}
    else:
        role_match = re.search(r"<@&(\d+)>", target_str)
        user_match = re.search(r"<@!?(\d+)>", target_str)

        if role_match:
            role_id = int(role_match.group(1))
            role = guild.get_role(role_id)
            if role:
                recipients = set(role.members)
        elif user_match:
            user_id = int(user_match.group(1))
            member = guild.get_member(user_id)
            if member:
                recipients = {member}
        elif target_str_clean.isdigit():
            member = guild.get_member(int(target_str_clean))
            if member:
                recipients = {member}
            else:
                role = guild.get_role(int(target_str_clean))
                if role:
                    recipients = set(role.members)

    if not recipients:
        return

    formatted_description = f"# **{title}**\n\n{description}"

    embed = discord.Embed(
        description=formatted_description,
        color=discord.Color.from_rgb(255, 140, 0)
    )
    
    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)

    embed.add_field(
        name="━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        value="🌐 **Web:** HAMAROSAN... | 🖥️ **IP:**parentland.ggwp.cc",
        inline=False
    )

    embed.set_footer(
        text="A ParentLand csapata Jóváhagyásával",
        icon_url=guild.icon.url if guild.icon else None
    )
    embed.timestamp = discord.utils.utcnow()

    for member in recipients:
        if member.bot:
            continue
        try:
            await member.send(embed=embed)
            await asyncio.sleep(0.5)
        except Exception:
            pass

# ------------------- PUZENET COG -------------------
class PuzenetCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="püzenet", description="Privát üzenet küldése rangnak, felhasználónak vagy mindenki számára.")
    @app_commands.describe(célpont="Írd be a rangot, embert, vagy @everyone / @here / mindenki szót")
    @app_commands.checks.has_any_role(*STAFF_ROLE_IDS)
    async def puzenet_parancs(self, interaction: discord.Interaction, célpont: str):
        await interaction.response.send_modal(PuzenetModal(target_str=célpont))

    @puzenet_parancs.error
    async def puzenet_parancs_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, (app_commands.MissingRole, app_commands.MissingAnyRole)):
            roles_mentions = ", ".join([f"<@&{r_id}>" for r_id in STAFF_ROLE_IDS])
            await interaction.response.send_message(
                f"🚫 **Nincs jogosultságod!** Ezt a parancsot csak a következő rangok valamelyikével használhatod: {roles_mentions}", 
                ephemeral=True
            )
        else:
            await interaction.response.send_message("❌ Váratlan hiba történt a parancs futtatása közben.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(PuzenetCog(bot))