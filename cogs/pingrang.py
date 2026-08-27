import discord
from discord.ext import commands
from discord import app_commands
import asyncio
from datetime import datetime
import zoneinfo

# ------------------- BEÁLLÍTÁSOK -------------------
# Ide írd be azoknak a rangoknak az ID-ját (számként), akik MŰKÖDTETHETIK a parancsot:
STAFF_ROLE_IDS = [
    1529858809106006136
]

# ------------------- GOMB DIZÁJN -------------------
class RangGombView(discord.ui.View):
    def __init__(self, target_role: discord.Role):
        super().__init__(timeout=None)  # timeout=None -> Soha nem jár le a gomb!
        button = discord.ui.Button(
            label="Elfogadom",
            style=discord.ButtonStyle.success,  # Zöld gomb
            emoji="✅",
            custom_id=f"role_button_{target_role.id}"  # Egyedi azonosító a rang ID-jával
        )
        self.add_item(button)


# ------------------- MODAL (GUI ABLAK) -------------------
class PingRangModal(discord.ui.Modal, title="✅ Rangos Üzenet Készítő"):
    def __init__(self, target_channel: discord.TextChannel, target_role: discord.Role, image_file: discord.Attachment = None):
        super().__init__()
        self.target_channel = target_channel
        self.target_role = target_role
        self.image_file = image_file

    cim = discord.ui.TextInput(
        label="📌 Üzenet Címe",
        style=discord.TextStyle.short,
        placeholder="Pl.: Kattints a gombra a Rangért!",
        required=True,
        max_length=100
    )

    leiras = discord.ui.TextInput(
        label="📝 Fő tartalom / Leírás",
        style=discord.TextStyle.paragraph,
        placeholder="Írd ide a tájékoztató szöveget...",
        required=True,
        max_length=2000
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

        # 1. DÁTUM ALAPÚ IDŐZÍTÉS
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

        # 2. PERC ALAPÚ IDŐZÍTÉS
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

        # Visszajelzés
        if delay_seconds > 0:
            await interaction.response.send_message(
                f"⏳ **Rangos üzenet időzítve!**\n"
                f"• **Adható rang:** {self.target_role.mention}\n"
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

        # ------------------- EMBED DIZÁJN -------------------
        formatted_description = f"# ***{self.cim.value}***\n\n\n{self.leiras.value}"

        embed = discord.Embed(
            description=formatted_description,
            color=self.target_role.color if self.target_role.color != discord.Color.default() else discord.Color.from_rgb(88, 101, 242)
        )

        if interaction.guild.icon:
            embed.set_thumbnail(url=interaction.guild.icon.url)

        if self.image_file:
            embed.set_image(url=self.image_file.url)

        embed.add_field(
            name="- - - - - - - - - - - - - - - - - - - - -",
            value=f"👇 **Kattints az alábbi gombra az elfogadáshoz!**\n👤 **Kiadta:** {interaction.user.mention}",
            inline=False
        )

        embed.set_footer(
            text="A ParentLand Vezetőség jóváhagyásával",
            icon_url=interaction.guild.icon.url if interaction.guild.icon else None
        )
        embed.timestamp = discord.utils.utcnow()

        # ÜZENET ELKÜLDÉSE AZ "ELFOGADOM" GOMBBAL (VIEW)
        await self.target_channel.send(
            embed=embed, 
            view=RangGombView(target_role=self.target_role)
        )


# ------------------- COG OSZTÁLY -------------------
class PingRangCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ------------------- ÖRÖKÖS GOMBKATTINTÁS KEZELŐ -------------------
    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        if interaction.type == discord.InteractionType.component:
            custom_id = interaction.data.get("custom_id", "")
            
            if custom_id.startswith("role_button_"):
                try:
                    role_id = int(custom_id.replace("role_button_", ""))
                    role = interaction.guild.get_role(role_id)
                    
                    if not role:
                        await interaction.response.send_message("❌ Ez a rang már nem létezik a szerveren!", ephemeral=True)
                        return

                    user = interaction.user

                    if role in user.roles:
                        await user.remove_roles(role)
                        await interaction.response.send_message(
                            f"➖ **Sikeresen levetted a(z) {role.mention} rangot!**", 
                            ephemeral=True
                        )
                    else:
                        await user.add_roles(role)
                        await interaction.response.send_message(
                            f"➕ **Sikeresen megkaptad a(z) {role.mention} rangot!** ✅", 
                            ephemeral=True
                        )
                except Exception as e:
                    await interaction.response.send_message(f"❌ Hiba történt a rang módosításakor: {e}", ephemeral=True)

    @app_commands.command(
        name="pingrang", 
        description="Létrehoz egy üzenetet egy 'Elfogadom' gombbal, amire kattintva a tagok megkapják a rangot."
    )
    @app_commands.describe(
        rang="Melyik rangot kapják meg a tagok a gombra kattintva?",
        csatorna="Melyik szobába küldje a bot az üzenetet?", 
        kep="Tölts fel egy képet az üzenethez (Opcionális)"
    )
    @app_commands.checks.has_any_role(*STAFF_ROLE_IDS)
    async def pingrang_parancs(
        self, 
        interaction: discord.Interaction, 
        rang: discord.Role,
        csatorna: discord.TextChannel, 
        kep: discord.Attachment = None
    ):
        await interaction.response.send_modal(PingRangModal(target_channel=csatorna, target_role=rang, image_file=kep))

    # Jogosultsági hibák kezelése
    @pingrang_parancs.error
    async def pingrang_parancs_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, (app_commands.MissingRole, app_commands.MissingAnyRole)):
            roles_mentions = ", ".join([f"<@&{r_id}>" for r_id in STAFF_ROLE_IDS])
            await interaction.response.send_message(
                f"🚫 **Nincs jogosultságod!** Ezt a parancsot csak a következő rangok valamelyikével használhatod: {roles_mentions}", 
                ephemeral=True
            )
        else:
            await interaction.response.send_message("❌ Váratlan hiba történt a parancs futtatása közben.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(PingRangCog(bot))