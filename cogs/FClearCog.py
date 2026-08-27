import discord
from discord.ext import commands
from discord import app_commands

# ------------------- BEÁLLÍTÁSOK -------------------
STAFF_ROLE_IDS = [
    1529858809106006136, # Bot parancsok-hoz (ENGEDÉLY)
    1530634556414365826, # Alapító
    1529131477756018779 # Tulajdonos
]

def has_staff_role():
    async def predicate(interaction: discord.Interaction) -> bool:
        if interaction.user.guild_permissions.administrator:
            return True
            
        user_role_ids = [role.id for role in interaction.user.roles]
        is_staff = any(role_id in STAFF_ROLE_IDS for role_id in user_role_ids)
        
        if not is_staff:
            await interaction.response.send_message(
                "❌ **Hiba:** Nincs jogosultságod használni ezt a parancsot! (Csak Staff tagok használhatják)", 
                ephemeral=True
            )
        return is_staff
    return app_commands.check(predicate)


# ------------------- FCLEAR COG -------------------
class FClearCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="fclear", description="Törli egy adott felhasználó összes üzenetét a szerver összes csatornájából.")
    @app_commands.describe(felhasznalo="Kitől szeretnéd törölni az üzeneteket?")
    @has_staff_role()
    async def fclear_command(self, interaction: discord.Interaction, felhasznalo: discord.Member):
        await interaction.response.send_message(
            f"🧹 **{felhasznalo.mention}** üzeneteinek törlése folyamatban a szerveren... Ez eltarthat néhány pillanatig.", 
            ephemeral=True
        )

        deleted_total = 0
        guild = interaction.guild

        try:
            for channel in guild.text_channels:
                try:
                    deleted_messages = await channel.purge(
                        limit=None, 
                        check=lambda m: m.author.id == felhasznalo.id
                    )
                    deleted_total += len(deleted_messages)
                except discord.Forbidden:
                    continue
                except discord.HTTPException:
                    continue

            await interaction.edit_original_response(
                content=f"✅ Sikeresen törölve összesen **{deleted_total}** darab üzenet **{felhasznalo.mention}** felhasználótól!"
            )

        except Exception as e:
            await interaction.edit_original_response(
                content=f"❌ Hiba történt a törlés során: {e}"
            )

    @fclear_command.error
    async def fclear_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, (app_commands.MissingRole, app_commands.MissingAnyRole, app_commands.CheckFailure)):
            await interaction.response.send_message(
                "❌ **Hiba:** Nincs jogosultságod használni ezt a parancsot!", 
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "❌ Ismeretlen hiba történt a parancs futtatása közben.", 
                ephemeral=True
            )


async def setup(bot):
    await bot.add_cog(FClearCog(bot))