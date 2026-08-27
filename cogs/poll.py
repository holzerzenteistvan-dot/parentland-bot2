import discord
from discord.ext import commands
from discord import app_commands
import asyncio
from datetime import datetime, timedelta, timezone

# ------------------- STAFF RANGOK ID-JEI -------------------
STAFF_ROLE_IDS = [
    1529858809106006136, #Bot parancsok-hoz (ENGEDÉLY)
    1530634556414365826, #Alapító
    1529131477756018779 #Tulajdonos
]

# ------------------- STAFF JOGOSULTSÁG ELLENŐRZŐ -------------------
def has_staff_role():
    async def predicate(interaction: discord.Interaction) -> bool:
        # Ha az illető Adminisztrátor, automatikusan átengedjük
        if interaction.user.guild_permissions.administrator:
            return True
            
        # Ellenőrizzük, hogy a felhasználónak megvan-e valamelyik staff rangja a listából
        user_role_ids = [role.id for role in interaction.user.roles]
        is_staff = any(role_id in STAFF_ROLE_IDS for role_id in user_role_ids)
        
        if not is_staff:
            await interaction.response.send_message(
                "❌ **Hiba:** Nincs jogosultságod használni ezt a parancsot! (Ehhez Staff rang szükséges)", 
                ephemeral=True
            )
        return is_staff
    return app_commands.check(predicate)

# ------------------- IDŐPARSOLÓ SEGÉDFÜGGVÉNY -------------------
def parse_time(time_str: str) -> int:
    """Átalakítja az s/m/h/d/w formátumú időt másodpercekre."""
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


# ------------------- SZAVAZÁS GOMBOK ÉS LOGIKA -------------------
class PollView(discord.ui.View):
    def __init__(self, options: list[str], max_votes: int, duration_seconds: int, author: discord.Member, title: str, description: str, end_timestamp: int):
        super().__init__(timeout=duration_seconds if duration_seconds > 0 else None)
        self.options = options
        self.max_votes = max_votes
        self.author = author
        self.title_text = title
        self.desc_text = description
        self.end_timestamp = end_timestamp
        self.votes: dict[int, set[int]] = {}  # {user_id: {opció_indexek}}
        self.message: discord.Message = None
        self.is_closed = False

        for index, option in enumerate(options):
            button = discord.ui.Button(
                label=option[:80],
                style=discord.ButtonStyle.secondary, 
                custom_id=f"poll_opt_{index}"
            )
            button.callback = self.create_callback(index)
            self.add_item(button)

    def create_callback(self, index: int):
        async def button_callback(interaction: discord.Interaction):
            if self.is_closed or datetime.now(timezone.utc).timestamp() >= self.end_timestamp:
                self.is_closed = True
                await interaction.response.send_message("❌ **Ez a szavazás már lejárt!**", ephemeral=True)
                await self.update_poll_embed(closed=True)
                return

            user_id = interaction.user.id
            if user_id not in self.votes:
                self.votes[user_id] = set()

            user_choices = self.votes[user_id]

            if index in user_choices:
                user_choices.remove(index)
                await interaction.response.send_message("❌ Sikeresen visszavonta a szavazatodat erről az opcióról!", ephemeral=True)
            else:
                if len(user_choices) >= self.max_votes:
                    if self.max_votes == 1:
                        await interaction.response.send_message("⚠️ Ebben a szavazásban csak **1** opciót választhatsz ki!", ephemeral=True)
                    else:
                        await interaction.response.send_message(f"⚠️ Elérted a maximum **{self.max_votes}** választási lehetőséget!", ephemeral=True)
                    return
                
                user_choices.add(index)
                await interaction.response.send_message(f"✅ Sikeresen leadtad a szavazatod erre: **{self.options[index]}**", ephemeral=True)

            if self.message:
                await self.update_poll_embed(closed=False)

        return button_callback

    def calculate_stats(self):
        counts = [0] * len(self.options)
        unique_voters = len(self.votes)

        for user_choices in self.votes.values():
            for choice in user_choices:
                counts[choice] += 1

        return counts, unique_voters

    async def update_poll_embed(self, closed: bool = False):
        if closed:
            self.is_closed = True

        counts, unique_voters = self.calculate_stats()
        total_selections = sum(counts)
        now_str = datetime.now().strftime("%Y. %m. %d. %H:%M")

        status_text = "🔒 LEZÁRULT" if closed else "🟢 AKTÍV"
        color = discord.Color.red() if closed else discord.Color.green()

        embed = discord.Embed(
            title=f"📊 {self.title_text}",
            description=f"{self.desc_text}\n\n",
            color=color
        )

        embed.add_field(
            name="ℹ️ Információk",
            value=(
                f"• Indította: {self.author.mention} (ID: `{self.author.id}`)\n"
                f"• Állapot: {status_text}\n"
                f"• Lejárat: <t:{self.end_timestamp}:R> (<t:{self.end_timestamp}:F>)\n"
                f"• Választható opciók száma: **{self.max_votes}** db"
            ),
            inline=False
        )

        options_text = ""
        for i, opt in enumerate(self.options):
            votes_count = counts[i]
            if total_selections > 0:
                percentage = (votes_count / total_selections) * 100
            else:
                percentage = 0.0

            bar_length = 10
            filled_blocks = int(round((percentage / 100) * bar_length))
            bar = "█" * filled_blocks + "░" * (bar_length - filled_blocks)

            options_text += f"**{i + 1}. {opt}**\n`{bar}` {votes_count} db ({percentage:.1f}%)\n\n"

        embed.add_field(name="Választható opciók és eredmények:", value=options_text.strip(), inline=False)
        embed.set_footer(text=f"ParentLand csapata Jóváhagyásával • {unique_voters} szavazó • {now_str}")

        if closed:
            for child in self.children:
                child.disabled = True

        if self.message:
            try:
                await self.message.edit(embed=embed, view=self)
            except discord.HTTPException:
                pass

    async def on_timeout(self):
        self.is_closed = True
        if self.message:
            try:
                await self.update_poll_embed(closed=True)
            except Exception:
                pass


# ------------------- MODAL (GUI) -------------------
class PollModal(discord.ui.Modal, title="Új Szavazás Létrehozása"):
    def __init__(self, target_channel: discord.TextChannel = None):
        super().__init__()
        self.target_channel = target_channel

    poll_title_input = discord.ui.TextInput(
        label="Szavazás címe (pl. csatorna neve)",
        placeholder="Pl.: számolószoba",
        required=True,
        max_length=4000
    )
    poll_desc_input = discord.ui.TextInput(
        label="Szavazás kérdése / leírása",
        style=discord.TextStyle.paragraph,
        placeholder="Legyen-e számolószoba, új koncepcióval?",
        required=True
    )
    max_votes_input = discord.ui.TextInput(
        label="Hány opciót választhat egy tag?",
        placeholder="Pl.: 1",
        required=True,
        max_length=2
    )
    duration_input = discord.ui.TextInput(
        label="Meddig tartson? (Pl.: 30m, 2h, 1d)",
        placeholder="Pl.: 2h, 1d...",
        required=True,
        max_length=10
    )
    options_input = discord.ui.TextInput(
        label="Válaszopciók vesszővel elválasztva (2-10 db)",
        placeholder="Igen, Nem",
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        raw_options = self.options_input.value.split(",")
        options = [opt.strip() for opt in raw_options if opt.strip()]

        if not (2 <= len(options) <= 10):
            await interaction.response.send_message("❌ **Hiba:** Kérlek **2 és 10** közötti számú opciót adj meg vesszővel elválasztva!", ephemeral=True)
            return

        try:
            max_votes = int(self.max_votes_input.value.strip())
        except ValueError:
            await interaction.response.send_message("❌ **Hiba:** A választható szavazatok száma csak szám lehet!", ephemeral=True)
            return

        if max_votes < 1 or max_votes > len(options):
            await interaction.response.send_message(f"❌ **Hiba:** A választható opciók száma 1 és {len(options)} között kell legyen!", ephemeral=True)
            return

        duration_seconds = parse_time(self.duration_input.value)
        if duration_seconds <= 0:
            await interaction.response.send_message("❌ **Hiba:** Érvénytelen időtartam formátum! Használd pl.: `30m`, `2h`, `1d`.", ephemeral=True)
            return

        end_timestamp = int(datetime.now(timezone.utc).timestamp()) + duration_seconds

        # Meghatározzuk, hová küldje (ha megadtak csatornát, oda, különben az aktuálisba)
        channel_to_send = self.target_channel if self.target_channel else interaction.channel

        await interaction.response.send_message(f"✅ A szavazás sikeresen létrehozva ide: {channel_to_send.mention}!", ephemeral=True)

        view = PollView(
            options=options,
            max_votes=max_votes,
            duration_seconds=duration_seconds,
            author=interaction.user,
            title=self.poll_title_input.value,
            description=self.poll_desc_input.value,
            end_timestamp=end_timestamp
        )

        now_str = datetime.now().strftime("%Y. %m. %d. %H:%M")
        embed = discord.Embed(
            title=f"📊 {self.poll_title_input.value}",
            description=f"{self.poll_desc_input.value}\n\n",
            color=discord.Color.green() 
        )

        embed.add_field(
            name="ℹ️ Információk",
            value=(
                f"• Indította: {interaction.user.mention} (ID: `{interaction.user.id}`)\n"
                f"• Állapot: 🟢 AKTÍV\n"
                f"• Lejárat: <t:{end_timestamp}:R> (<t:{end_timestamp}:F>)\n"
                f"• Választható opciók száma: **{max_votes}** db"
            ),
            inline=False
        )

        options_text = ""
        for i, opt in enumerate(options):
            options_text += f"**{i + 1}. {opt}**\n`░░░░░░░░░░` 0 db (0.0%)\n\n"

        embed.add_field(name="Választható opciók és eredmények:", value=options_text.strip(), inline=False)
        embed.set_footer(text=f"ParentLand csapata Jóváhagyásával • 0 szavazó • {now_str}")

        message = await channel_to_send.send(embed=embed, view=view)
        view.message = message


# ------------------- COG DEFINÍCIÓ -------------------
class PollCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="szavazás", description="Interaktív beágyazott szavazás indítása visszaszámlálással.")
    @app_commands.describe(csatorna="Melyik csatornára küldje a szavazást? (Ha kihagyod, ide küldi)")
    @has_staff_role()
    async def szavazas_command(self, interaction: discord.Interaction, csatorna: discord.TextChannel = None):
        await interaction.response.send_modal(PollModal(target_channel=csatorna))


async def setup(bot):
    await bot.add_cog(PollCog(bot))