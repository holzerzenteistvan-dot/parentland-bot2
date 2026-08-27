import discord
from discord.ext import commands
from discord import app_commands

# ------------------- STAFF RANGOK ID-JEI -------------------
STAFF_ROLE_IDS = [
    1529858809106006136
]

def has_staff_role():
    async def predicate(interaction: discord.Interaction) -> bool:
        if interaction.user.guild_permissions.administrator:
            return True
            
        user_role_ids = [role.id for role in interaction.user.roles]
        is_staff = any(role_id in STAFF_ROLE_IDS for role_id in user_role_ids)
        
        if not is_staff:
            await interaction.response.send_message(
                "❌ **Hiba:** Nincs jogosultságod használni ezt a parancsot! (Ehhez Staff rang szükséges)", 
                ephemeral=True
            )
        return is_staff
    return app_commands.check(predicate)


# ------------------- CLEAR COG DEFINÍCIÓ -------------------
class ClearCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="clear", description="Törli a megadott számú üzenetet a csatornából (max. 100).")
    @app_commands.describe(amount="Hány darab üzenetet szeretnél törölni?")
    @has_staff_role()
    async def clear_command(self, interaction: discord.Interaction, amount: int):
        # Ellenőrizzük, hogy érvényes számot adott-e meg (1 és 100 között)
        if amount < 1 or amount > 100:
            await interaction.response.send_message(
                "❌ **Hiba:** Kérlek 1 és 100 közötti darabszámot adj meg!", 
                ephemeral=True
            )
            return

        # Először válaszolunk egy ephemeral (csak számára látható) üzenettel, hogy a bot ne akadjon el
        await interaction.response.send_message(f"🧹 Törlés folyamatban...", ephemeral=True)

        try:
            # Töröljük a megadott számú üzenetet (+1-et nem kell, mert a slash parancs válasza ephemeral volt)
            deleted = await interaction.channel.purge(limit=amount)
            
            # Utólag szerkesztjük a választ, hogy hány üzenet lett törölve
            await interaction.edit_original_response(
                content=f"✅ Sikeresen törölve **{len(deleted)}** darab üzenet!"
            )
        except discord.Forbidden:
            await interaction.edit_original_response(
                content="❌ **Hiba:** A botnak nincs joga a tömeges üzenettörléshez (`Manage Messages`)!"
            )
        except discord.HTTPException as e:
            await interaction.edit_original_response(
                content=f"❌ Hiba történt a törlés során: {e}"
            )


async def setup(bot):
    await bot.add_cog(ClearCog(bot))