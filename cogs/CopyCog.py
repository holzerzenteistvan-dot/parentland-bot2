import discord
from discord import app_commands
from discord.ext import commands


# Felugró ablak (Modal) kizárólag a Cím és Leírás másolásához
class CopyModal(discord.ui.Modal, title="Embed Másolása"):
    embed_title = discord.ui.TextInput(
        label="Embed Cím",
        style=discord.TextStyle.short,
        required=False,
        max_length=256,
    )
    embed_desc = discord.ui.TextInput(
        label="Embed Leírás",
        style=discord.TextStyle.paragraph,
        required=False,
        max_length=4000,
    )

    def __init__(self, e_title: str, e_desc: str):
        super().__init__()
        # Alapértelmezett értékek beállítása
        self.embed_title.default = e_title[:256] if e_title else ""
        self.embed_desc.default = e_desc[:4000] if e_desc else ""

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            "✅ A cím és a leírás sikeresen kimásolható volt!", ephemeral=True
        )


class CopyCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # Perzisztens eseménykezelő a gombokhoz
    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        if interaction.type == discord.InteractionType.component:
            custom_id = interaction.data.get("custom_id", "")
            if custom_id.startswith("copy_msg_"):
                try:
                    message_id = int(custom_id.split("_")[2])
                    target_message = await interaction.channel.fetch_message(message_id)

                    # Változók előkészítése
                    title_text = ""
                    desc_text = ""

                    # Ha van Embed az üzenetben, kinyerjük csak a címet és leírást
                    if target_message.embeds:
                        embed = target_message.embeds[0] # Csak az első embedet nézzük
                        title_text = embed.title or ""
                        desc_text = embed.description or ""

                    # Ha nincs sem cím, sem leírás
                    if not title_text and not desc_text:
                        await interaction.response.send_message(
                            "❌ Ebben az üzenetben nincs másolható Embed cím vagy leírás!",
                            ephemeral=True
                        )
                        return

                    # Megnyitjuk a Modalt a címmel és leírással
                    modal = CopyModal(title_text, desc_text)
                    await interaction.response.send_modal(modal)

                except discord.NotFoundError:
                    await interaction.response.send_message(
                        "❌ Az eredeti üzenet nem található (lehet, hogy törölték).",
                        ephemeral=True,
                    )
                except Exception as e:
                    await interaction.response.send_message(
                        f"❌ Hiba történt: {e}", ephemeral=True
                    )

    # A /másolás slash parancs a megadott rang ID-kkel
    @app_commands.command(
        name="másolás", description="Létrehoz egy másoló gombot a megadott üzenethez."
    )
    @app_commands.describe(üzenet_id="A másolandó üzenet azonosítója (ID-je)")
    @app_commands.checks.has_any_role(
        1529858809106006136,  # Bot parancsok-hoz (ENGEDÉLY)
        1530634556414365826,  # Alapító
        1529131477756018779,  # Tulajdonos
    )
    async def masolas(self, interaction: discord.Interaction, üzenet_id: str):
        try:
            msg_id = int(üzenet_id)
        except ValueError:
            await interaction.response.send_message(
                "❌ Az üzenet ID-je csak szám lehet!", ephemeral=True
            )
            return

        try:
            target_msg = await interaction.channel.fetch_message(msg_id)
        except discord.NotFoundError:
            await interaction.response.send_message(
                "❌ Nem található üzenet ezzel az ID-vel ebben a csatornában!",
                ephemeral=True,
            )
            return

        view = discord.ui.View(timeout=None)
        button = discord.ui.Button(
            label="Embed másolása",
            style=discord.ButtonStyle.secondary,
            emoji="📋",
            custom_id=f"copy_msg_{msg_id}",
        )
        view.add_item(button)

        await interaction.response.send_message(
            f"📋 **Másolási segédlet** a(z) <@{target_msg.author.id}> által írt üzenethez:",
            view=view,
        )

    # Hiba kezelése a parancshoz
    @masolas.error
    async def masolas_error(self, interaction: discord.Interaction, error):
        if isinstance(error, (app_commands.MissingRole, app_commands.MissingAnyRole)):
            await interaction.response.send_message(
                "❌ Ehhez a parancshoz nincs jogosultságod (szükséges hozzá a megadott rangok egyike)!",
                ephemeral=True,
            )
        else:
            await interaction.response.send_message(
                f"❌ Hiba történt: {error}", ephemeral=True
            )


async def setup(bot):
    await bot.add_cog(CopyCog(bot))