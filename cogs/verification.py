import discord
from discord.ext import commands
from discord import app_commands
import random
import string

# ------------------- BEÁLLÍTÁSOK / ID-K -------------------
ELLENORZES_RANG_1_ID = 1529128339934154812  # Szabályzat elfogadása után kapja meg (Ezt levesszük)
TAG_RANG_2_ID = 1529128863098077247        # A jó kód beírása után kapja meg (Ezt odaadjuk)
ELLENORZES_SZOBA_ID = 1528774338512420886   # A szoba ID-ja


def generate_numeric_code(length=22) -> str:
    """Kizárólag 22 számjegyből álló kód generálása."""
    return ''.join(random.choices(string.digits, k=length))


# ------------------- 1. SZABÁLYZAT ELFOGADÓ GOMB -------------------
class RuleAcceptView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Szabályzat elfogadása & Rang felvétele", 
        style=discord.ButtonStyle.success, 
        emoji="📜", 
        custom_id="accept_rules_button"
    )
    async def accept_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        if not guild:
            await interaction.response.send_message("❌ Ez a gomb csak a szerveren működik!", ephemeral=True)
            return

        role_1 = guild.get_role(ELLENORZES_RANG_1_ID)
        if not role_1:
            await interaction.response.send_message("❌ Nem található a megadott ellenőrző rang!", ephemeral=True)
            return

        member = interaction.user
        if role_1 in member.roles:
            await interaction.response.send_message("⚠️ Már elfogadtad a szabályzatot!", ephemeral=True)
            return

        try:
            await member.add_roles(role_1)
            channel = guild.get_channel(ELLENORZES_SZOBA_ID)
            channel_mention = channel.mention if channel else f"<#{ELLENORZES_SZOBA_ID}>"
            
            await interaction.response.send_message(
                f"✅ **Sikeresen elfogadtad a szabályzatot!**\n"
                f"Megkaptad a(z) {role_1.mention} rangot. "
                f"Nyisd meg a {channel_mention} szobát a folytatáshoz!",
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(f"❌ Hiba történt a rang adása közben: {e}", ephemeral=True)


# ------------------- 2. FELUGRÓ ABLAK (MODAL) A KÓD BEÍRÁSÁHOZ -------------------
class CodeInputModal(discord.ui.Modal, title="Kód ellenőrzése"):
    code_input = discord.ui.TextInput(
        label="Illeszd be a generált 22 jegyű kódot:",
        style=discord.TextStyle.short,
        placeholder="Pl.: 0543269051188219418652",
        required=True,
        min_length=1,
        max_length=40
    )

    async def on_submit(self, interaction: discord.Interaction):
        bot = interaction.client
        user_id = interaction.user.id

        expected_code = getattr(bot, "active_codes", {}).get(user_id)

        if not expected_code:
            await interaction.response.send_message(
                "❌ **Nincs aktív kódod!** Kattints előbb az **1. Kód igénylése** gombra!",
                ephemeral=True
            )
            return

        # Csak a számjegyeket tartjuk meg
        cleaned_input = "".join(char for char in self.code_input.value if char.isdigit())

        if cleaned_input == expected_code:
            del bot.active_codes[user_id]
            guild = interaction.guild
            
            role_1 = guild.get_role(ELLENORZES_RANG_1_ID)
            final_role = guild.get_role(TAG_RANG_2_ID)

            if final_role:
                try:
                    # RANGOK FRISSÍTÉSE: 1-es rang levétele, 2-es rang megadása
                    if role_1 and role_1 in interaction.user.roles:
                        await interaction.user.remove_roles(role_1)
                        
                    await interaction.user.add_roles(final_role)
                    
                    await interaction.response.send_message(
                        f"🎉 **Sikeres hitelesítés!** Megkaptad a(z) {final_role.mention} rangot! Üdv a szerveren!",
                        ephemeral=True
                    )
                except Exception as e:
                    await interaction.response.send_message(f"❌ Hiba a rangok frissítésekor: {e}", ephemeral=True)
            else:
                await interaction.response.send_message("❌ A végső rang nem található a szerveren!", ephemeral=True)
        else:
            await interaction.response.send_message(
                f"❌ **A kód nem egyezik!**\n"
                f"• Beírtál: `{cleaned_input}` ({len(cleaned_input)} szám)\n"
                f"• Elvárt: `{expected_code}` (22 szám)\n\n"
                f"(Igényelj új kódot az **1. Kód igénylése** gombbal!)",
                ephemeral=True
            )


# ------------------- 3. HITELESÍTŐ GOMBOK -------------------
class VerificationButtonView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="1. Kód igénylése", 
        style=discord.ButtonStyle.primary, 
        emoji="🔑", 
        custom_id="get_code_button"
    )
    async def get_code_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        user = interaction.user
        bot = interaction.client

        if not hasattr(bot, "active_codes"):
            bot.active_codes = {}

        code = generate_numeric_code(22)
        bot.active_codes[user.id] = code

        await interaction.response.send_message(
            f"🔐 **Az ellenőrző kódod:**\n\n"
            f"`{code}`\n\n"
            f"💡 *Másold ki/jelöld ki a fenti kódot, majd kattints a **2. Kód beírása** gombra!*",
            ephemeral=True
        )

    @discord.ui.button(
        label="2. Kód beírása", 
        style=discord.ButtonStyle.success, 
        emoji="📝", 
        custom_id="enter_code_button"
    )
    async def enter_code_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(CodeInputModal())


# ------------------- MAIN COG -------------------
class VerificationCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        if not hasattr(bot, "active_codes"):
            self.bot.active_codes = {}

    @app_commands.command(name="ellenorzes", description="Kihelyezi a Hitelesítés gombokat.")
    @app_commands.checks.has_permissions(administrator=True)
    async def ellenorzes_parancs(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🔐 Szerver Hitelesítés",
            description=(
                "**Hogyan hitelesítsd magad?**\n\n"
                "1️⃣ Kattints az **1. Kód igénylése** gombra (megjelenik a kódod rejtett üzenetben).\n"
                "2️⃣ Másold ki a megjelent kódot.\n"
                "3️⃣ Kattints a **2. Kód beírása** gombra, és illeszd be a felugró ablakba!"
            ),
            color=discord.Color.blue()
        )
        await interaction.channel.send(embed=embed, view=VerificationButtonView())
        await interaction.response.send_message("✅ Hitelesítő gombok kihelyezve!", ephemeral=True)

    @app_commands.command(name="szabalyzat_gomb_kihelyezes", description="Kihelyezi a szabályzat gombot.")
    @app_commands.checks.has_permissions(administrator=True)
    async def setup_rules_button(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="📜 Szerver Szabályzat",
            description="Kattints az alábbi gombra a szabályzat elfogadásához!",
            color=discord.Color.green()
        )
        await interaction.channel.send(embed=embed, view=RuleAcceptView())
        await interaction.response.send_message("✅ Szabályzat gomb kihelyezve!", ephemeral=True)


async def setup(bot):
    bot.add_view(RuleAcceptView())
    bot.add_view(VerificationButtonView())
    await bot.add_cog(VerificationCog(bot))