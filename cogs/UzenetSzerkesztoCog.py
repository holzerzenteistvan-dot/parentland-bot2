import discord
from discord.ext import commands
from discord import app_commands
import asyncio

# ------------------- STAFF RANGOK ID-JEI -------------------
STAFF_ROLE_IDS = [
    1529858809106006136, # Bot parancsok-hoz (ENGEDÉLY)
    1530634556414365826, # Alapító
    1529131477756018779, # Tulajdonos
    1529131248075669634  # Admin
]

# ------------------- SZERKESZTŐ MODAL -------------------
class UzenetSzerkesztoModal(discord.ui.Modal, title="✏️ ParentLand Üzenet Szerkesztő"):
    def __init__(self, target_message: discord.Message):
        super().__init__(title="✏️ ParentLand Üzenet Szerkesztő")
        self.target_message = target_message

        old_title = ""
        old_text = ""
        old_image_url = ""
        
        # Megpróbáljuk kinyerni az eredeti formázásból a címet, leírást és a képet
        if target_message.embeds:
            embed = target_message.embeds[0]
            
            if embed.image and embed.image.url:
                old_image_url = embed.image.url
                
            if embed.description:
                desc = embed.description
                if desc.startswith("# **") and "**\n\n" in desc:
                    parts = desc.split("**\n\n", 1)
                    old_title = parts[0].replace("# **", "").strip()
                    old_text = parts[1] if len(parts) > 1 else ""
                else:
                    old_text = desc
            if embed.title and not old_title:
                old_title = embed.title

        self.cim = discord.ui.TextInput(
            label="📌 Üzenet Címe",
            style=discord.TextStyle.short,
            placeholder="Pl.: HATALMAS HÍR",
            default=old_title,
            required=True,
            max_length=100
        )
        self.leiras = discord.ui.TextInput(
            label="📝 Fő tartalom / Leírás",
            style=discord.TextStyle.paragraph,
            placeholder="Írd ide a részletes szöveget...",
            default=old_text,
            required=True,
            max_length=4000
        )
        self.kep_url = discord.ui.TextInput(
            label="🖼️ Kép URL (Hagyd üresen, ha nincs)",
            style=discord.TextStyle.short,
            placeholder="https://pelda.hu/kep.png",
            default=old_image_url,
            required=False,
            max_length=500
        )

        self.add_item(self.cim)
        self.add_item(self.leiras)
        self.add_item(self.kep_url)

    async def on_submit(self, interaction: discord.Interaction):
        guild = interaction.guild
        
        # Hivatalos ParentLand formátum felépítése
        formatted_description = f"# **{self.cim.value}**\n\n{self.leiras.value}"

        embed = discord.Embed(
            description=formatted_description,
            color=discord.Color.from_rgb(255, 140, 0)
        )

        if guild and guild.icon:
            embed.set_thumbnail(url=guild.icon.url)

        # Ha megadtak/megtartottak kép URL-t, beállítjuk a képet
        if self.kep_url.value and self.kep_url.value.strip():
            embed.set_image(url=self.kep_url.value.strip())

        embed.add_field(
            name="━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            value="🌐 **Web:** HAMAROSAN... | 🖥️ **IP:**HAMAROSAN...",
            inline=False
        )

        embed.set_footer(
            text="A ParentLand csapata Jóváhagyásával",
            icon_url=guild.icon.url if guild and guild.icon else None
        )
        embed.timestamp = discord.utils.utcnow()

        allowed_mentions = discord.AllowedMentions(everyone=True, roles=True, users=True)

        try:
            await self.target_message.edit(content=None, embed=embed, allowed_mentions=allowed_mentions)
            await interaction.response.send_message(
                "✅ **Az üzenet és a kép sikeresen frissítve lett!**",
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(
                f"❌ Hiba történt a szerkesztés során: {e}",
                ephemeral=True
            )

# ------------------- SZERKESZTŐ COG -------------------
class UzenetSzerkesztoCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="üzenet_szerkesztés", 
        description="Meglévő ParentLand üzenet szerkesztése az azonosítója (ID-ja) alapján."
    )
    @app_commands.describe(üzenet_azonosító="Az üzenet egyedi ID-ja (Copy ID)")
    @app_commands.checks.has_any_role(*STAFF_ROLE_IDS)
    async def uzenet_szerkesztes(self, interaction: discord.Interaction, üzenet_azonosító: str):
        try:
            msg_id = int(üzenet_azonosító.strip())
        except ValueError:
            await interaction.response.send_message("❌ Az üzenet azonosítónak érvényes számnak kell lennie!", ephemeral=True)
            return

        await interaction.response.send_message("🔍 **Üzenet keresése a csatornákban...**", ephemeral=True)

        target_message = None
        # Végigkeressük a szöveges csatornákat az üzenet ID alapján
        for channel in interaction.guild.text_channels:
            try:
                target_message = await channel.fetch_message(msg_id)
                if target_message:
                    break
            except Exception:
                continue

        if not target_message:
            await interaction.edit_original_response(content="❌ **Nem található üzenet** ezzel az azonosítóval a szerveren!")
            return

        class SzerkesztoGombView(discord.ui.View):
            def __init__(self, message: discord.Message):
                super().__init__(timeout=60)
                self.message = message

            @discord.ui.button(label="Szerkesztő ablak megnyitása", style=discord.ButtonStyle.green, emoji="✏️")
            async def open_modal(self, btn_interaction: discord.Interaction, button: discord.ui.Button):
                await btn_interaction.response.send_modal(UzenetSzerkesztoModal(target_message=self.message))

        await interaction.edit_original_response(
            content=f"✅ **Megvan az üzenet!** Kattints az alábbi gombra a szerkesztő ablak (GUI) megnyitásához:",
            view=SzerkesztoGombView(target_message)
        )

    @uzenet_szerkesztes.error
    async def uzenet_szerkesztes_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, (app_commands.MissingRole, app_commands.MissingAnyRole)):
            roles_mentions = ", ".join([f"<@&{r_id}>" for r_id in STAFF_ROLE_IDS])
            await interaction.response.send_message(
                f"🚫 **Nincs jogosultságod!** Ezt a parancsot csak a következő rangok valamelyikével használhatod: {roles_mentions}", 
                ephemeral=True
            )
        else:
            await interaction.response.send_message("❌ Váratlan hiba történt a parancs futtatása közben.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(UzenetSzerkesztoCog(bot))