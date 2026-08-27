import discord
from discord.ext import commands
from discord import app_commands
import asyncio
from datetime import datetime, timedelta, timezone
import random

STAFF_ROLE_IDS = [
    1529858809106006136, #Bot parancsok-hoz (ENGEDÉLY)
    1530634556414365826, #Alapító
    1529131477756018779 #Tulajdonos
]

TICKET_CHANNEL_ID = 1528818862932627576

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

def parse_time(time_str: str) -> int:
    time_str = time_str.strip().lower()
    if not time_str:
        return 0
    
    unit = time_str[-1]
    try:
        val = int(time_str[:-1])
    except ValueError:
        return 0
    
    multipliers = {
        's': 1,
        'm': 60,
        'h': 3600,
        'd': 86400,
        'w': 604800
    }
    
    return val * multipliers.get(unit, 0)


# ------------------- PERZISZTENS NYEREMÉNYJÁTÉK VIEW -------------------
class GiveawayView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.active_giveaways = {}

    @discord.ui.button(label="Jelentkezek", style=discord.ButtonStyle.secondary, custom_id="persistent_giveaway:join_btn")
    async def join_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        message_id = interaction.message.id

        if message_id not in self.active_giveaways:
            embed = interaction.message.embeds[0]
            if "LEZÁRULT" in embed.description or any("LEZÁRULT" in field.value for field in embed.fields):
                await interaction.response.send_message("❌ Ez a nyereményjáték már véget ért!", ephemeral=True)
                return
            else:
                # Kinyerjük a címet a leírás első sorából
                first_line = embed.description.split("\n")[0].replace("# 🎁 ", "").replace("🎁 ", "").strip()
                self.active_giveaways[message_id] = {
                    "participants": set(),
                    "winners_count": 1,
                    "title": first_line,
                    "author_id": interaction.user.id
                }

        data = self.active_giveaways[message_id]
        participants = data["participants"]
        user_id = interaction.user.id

        if user_id in participants:
            participants.remove(user_id)
            await interaction.response.send_message("❌ Sikeresen lemondtad a jelentkezésedet a nyereményjátékról!", ephemeral=True)
        else:
            participants.add(user_id)
            await interaction.response.send_message("✅ Sikeresen jelentkeztél a nyereményjátékra!", ephemeral=True)

        await self.update_embed_count(interaction.message, len(participants))

    async def update_embed_count(self, message: discord.Message, count: int):
        try:
            embed = message.embeds[0]
            new_fields = []
            for field in embed.fields:
                if "jelentkezők" in field.value.lower() or "jelentkező" in field.name.lower():
                    lines = field.value.split("\n")
                    updated_lines = []
                    for line in lines:
                        if "jelentkezők" in line.lower():
                            updated_lines.append(f"• Eddigi jelentkezők: **{count}** fő")
                        else:
                            updated_lines.append(line)
                    new_fields.append((field.name, "\n".join(updated_lines), field.inline))
                else:
                    new_fields.append((field.name, field.value, field.inline))
            
            embed.clear_fields()
            for name, value, inline in new_fields:
                embed.add_field(name=name, value=value, inline=inline)

            await message.edit(embed=embed)
        except Exception:
            pass

    async def end_giveaway(self, message: discord.Message, message_id: int):
        if message_id not in self.active_giveaways:
            return
        
        data = self.active_giveaways[message_id]
        participants = list(data["participants"])
        winners_count = data["winners_count"]

        try:
            embed = message.embeds[0]
            embed.color = discord.Color.red()  # Lejárt állapotban piros sáv
            
            new_fields = []
            for field in embed.fields:
                val = field.value.replace("🟢 AKTÍV", "🔒 LEZÁRULT")
                new_fields.append((field.name, val, field.inline))
            
            embed.clear_fields()
            for name, value, inline in new_fields:
                embed.add_field(name=name, value=value, inline=inline)

            if not participants:
                winners_text = "Senki sem jelentkezett a nyereményjátékra! 😢"
                chosen_uids = []
            else:
                actual_winners = min(winners_count, len(participants))
                chosen_uids = random.sample(participants, actual_winners)
                winners_text = ", ".join([f"<@{uid}>" for uid in chosen_uids])

            winner_label = "🏆 Nyertes:" if len(chosen_uids) == 1 else "🏆 Nyertesek:"
            embed.add_field(name=winner_label, value=winners_text, inline=False)

            for child in self.children:
                child.disabled = True

            await message.edit(embed=embed, view=self)

            # Privát üzenet küldése a nyerteseknek
            ticket_channel = message.guild.get_channel(TICKET_CHANNEL_ID)
            ticket_mention = ticket_channel.mention if ticket_channel else f"<#{TICKET_CHANNEL_ID}>"

            for uid in chosen_uids:
                try:
                    user = await message.guild.fetch_member(uid)
                    if user:
                        dm_embed = discord.Embed(
                            title="🎉 Gratulálunk, nyertél!",
                            description=f"Örömmel értesítünk, hogy te vagy a(z) **{message.guild.name}** szerveren futott nyereményjáték egyik nyertese!",
                            color=discord.Color.gold()
                        )
                        dm_embed.add_field(
                            name="🎫 Nyeremény átvétele", 
                            value=f"Kérlek, nyiss egy nyereményjáték hibajegyet itt: {ticket_mention}", 
                            inline=False
                        )
                        dm_embed.set_footer(text="ParentLand Nyereményjáték")
                        
                        await user.send(embed=dm_embed)
                except Exception:
                    pass

        except Exception:
            pass
        finally:
            del self.active_giveaways[message_id]


persistent_giveaway_view = GiveawayView()


# ------------------- MODAL (GUI) -------------------
class GiveawayModal(discord.ui.Modal, title="Új Nyereményjáték Indítása"):
    def __init__(self, target_channel: discord.TextChannel):
        super().__init__()
        self.target_channel = target_channel

    title_input = discord.ui.TextInput(
        label="Nyeremény címe",
        placeholder="Pl.: VIP Rang / 10 millió $, stb.",
        required=True,
        max_length=4000
    )
    desc_input = discord.ui.TextInput(
        label="Leírás / Feltételek",
        style=discord.TextStyle.paragraph,
        placeholder="Írd le a részleteket...",
        required=True
    )
    winners_input = discord.ui.TextInput(
        label="Nyertesek száma",
        placeholder="Pl.: 1",
        required=True,
        max_length=2
    )
    duration_input = discord.ui.TextInput(
        label="Meddig tartson? (Pl.: 30m, 2h, 1d)",
        placeholder="Pl.: 1d, 2h...",
        required=True,
        max_length=10
    )

    async def on_submit(self, interaction: discord.Interaction):
        try:
            winners_count = int(self.winners_input.value.strip())
        except ValueError:
            await interaction.response.send_message("❌ **Hiba:** A nyertesek száma csak szám lehet!", ephemeral=True)
            return

        if winners_count < 1:
            await interaction.response.send_message("❌ **Hiba:** Legalább 1 nyertesnek lennie kell!", ephemeral=True)
            return

        duration_seconds = parse_time(self.duration_input.value)
        if duration_seconds <= 0:
            await interaction.response.send_message("❌ **Hiba:** Érvénytelen időtartam formátum! Használd pl.: `30m`, `2h`, `1d`.", ephemeral=True)
            return

        end_timestamp = int(datetime.now(timezone.utc).timestamp()) + duration_seconds

        await interaction.response.send_message(f"✅ A nyereményjáték sikeresen elindítva itt: {self.target_channel.mention}!", ephemeral=True)

        now_str = datetime.now().strftime("%Y. %m. %d. %H:%M")
        
        # Nagyobb cím a leírás elején (Markdown #), több üres sor, majd szaggatott vonal
        embed_description = f"# 🎁 {self.title_input.value}\n\n\n{self.desc_input.value}\n\n\n---"

        embed = discord.Embed(
            title="",  # Üresen hagyjuk a normál címet, hogy ne duplázódjon
            description=embed_description,
            color=discord.Color.green()  # Aktív állapotban zöld sáv
        )

        embed.add_field(
            name="ℹ️ Információk",
            value=(
                f"• Indította: {interaction.user.mention} (ID: `{interaction.user.id}`)\n"
                f"• Állapot: 🟢 AKTÍV\n"
                f"• Lejárat: <t:{end_timestamp}:R> (<t:{end_timestamp}:F>)\n"
                f"• Nyertesek száma: **{winners_count}** db\n"
                f"• Eddigi jelentkezők: **0** fő"
            ),
            inline=False
        )
        embed.set_footer(text=f"ParentLand Nyereményjáték • {now_str}")

        message = await self.target_channel.send(embed=embed, view=persistent_giveaway_view)
        
        persistent_giveaway_view.active_giveaways[message.id] = {
            "participants": set(),
            "winners_count": winners_count,
            "title": self.title_input.value,
            "end_timestamp": end_timestamp,
            "author_id": interaction.user.id
        }

        async def timer_task():
            await asyncio.sleep(duration_seconds)
            await persistent_giveaway_view.end_giveaway(message, message.id)

        asyncio.create_task(timer_task())


# ------------------- COG DEFINÍCIÓ -------------------
class GiveawayCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot.add_view(persistent_giveaway_view)

    @app_commands.command(name="nyereményjáték", description="Interaktív nyereményjáték indítása GUI ablak segítségével.")
    @app_commands.describe(csatorna="Hová küldje a bot a nyereményjáték üzenetet?")
    @has_staff_role()
    async def nyeremenyjatek_command(self, interaction: discord.Interaction, csatorna: discord.TextChannel):
        await interaction.response.send_modal(GiveawayModal(target_channel=csatorna))


async def setup(bot):
    await bot.add_cog(GiveawayCog(bot))