from datetime import timedelta
import re
import discord
from discord import app_commands
from discord.ext import commands

# -----------------------------------------------------
STAFF_ROLE_IDS = [
    1529858809106006136, #Bot parancsok-hoz (ENGEDÉLY)
    1530634556414365826, #Alapító
    1529131477756018779, #Tulajdonos
    1529131248075669634, #Admin
    1529130472247136496  #Moderátor
]

# Naplózó csatorna ID (ahova a logok mennek)
LOG_CHANNEL_ID = 1533141000011120914
# ----------------------------------------------------

# Kivételként megadott kategória azonosítók (ID-k), ahol szabad linket küldeni
EXCLUDED_CATEGORY_IDS = {
    1528773883791020252,
    1528774050279854192,
    1528773221296640181,
    1528774116805447922
}

# Memóriabeli tároló warnokhoz: {user_id: warn_count}
WARN_STORAGE = {}

# Szigorú, mindenféle linket és meghívót felismerő regex minta
URL_REGEX = re.compile(
    r"("
    r"https?://"  # http:// vagy https://
    r"|www\."  # www. kezdet
    r"|[a-zA-Z0-9-]+\.(com|hu|net|org|edu|gov|mil|biz|info|mobi|name|aero|jobs|museum|me|co|uk|de|fr|ru|it|es|nl|pl|eu|cc|tk|ml|ga|cf|gq)\b"  # Ismertebb domain végződések
    r"|discord\.gg/[a-zA-Z0-9]+"  # Discord meghívók
    r"|discord(app)?\.com/invite/[a-zA-Z0-9]+"  # Discord invite linkek
    r")",
    re.IGNORECASE,
)


# ------------------- STAFF JOGOSULTSÁG ELLENŐRZŐ -------------------
def has_staff_role():
    async def predicate(interaction: discord.Interaction) -> bool:
        if interaction.user.guild_permissions.administrator:
            return True

        user_role_ids = [role.id for role in interaction.user.roles]
        is_staff = any(role_id in STAFF_ROLE_IDS for role_id in user_role_ids)

        if not is_staff:
            await interaction.response.send_message(
                "❌ **Hiba:** Nincs jogosultságod használni ezt a parancsot! (Csak"
                " Staff tagok használhatják)",
                ephemeral=True,
            )
        return is_staff

    return app_commands.check(predicate)


# ------------------- IDŐPARSOLÓ SEGÉDFÜGGVÉNY -------------------
def parse_time(time_str: str) -> int:
    """Átalakítja az s/m/h/d/w/y formátumú időt másodpercekre."""
    time_str = time_str.strip().lower()
    if not time_str:
        return 0

    unit = time_str[-1]
    try:
        val = int(time_str[:-1])
    except ValueError:
        return 0

    multipliers = {
        "s": 1,
        "m": 60,
        "h": 3600,
        "d": 86400,
        "w": 604800,
        "y": 31536000,
    }

    return val * multipliers.get(unit, 0)


# ------------------- NAPLÓZÓ SEGÉDFÜGGVÉNY -------------------
async def send_mod_log(
    guild: discord.Guild,
    action_type: str,
    staff_user: discord.User,
    staff_name_input: str,
    target_user: discord.abc.User | None,
    target_id_str: str,
    reason: str,
    duration: str = "N/A",
    extra_info: str = "",
    color: discord.Color = discord.Color.blue(),
):
    log_channel = guild.get_channel(LOG_CHANNEL_ID)
    if not log_channel:
        return

    embed = discord.Embed(
        title=f"🛡️ Moderációs Napló: {action_type}",
        color=color,
        timestamp=discord.utils.utcnow(),
    )

    # Végrehajtó Staff adatai
    staff_mention = (
        staff_user.mention if hasattr(staff_user, "mention") else "Ismeretlen"
    )
    embed.add_field(
        name="👤 Végrehajtó Staff (Discord)",
        value=f"{staff_mention}\nNév: `{staff_user}`\nID: `{staff_user.id}`",
        inline=True,
    )
    embed.add_field(
        name="✍️ Megadott Staff Név",
        value=f"`{staff_name_input}`",
        inline=True,
    )

    # Célpont adatai
    if target_user:
        target_mention = (
            target_user.mention
            if hasattr(target_user, "mention")
            else "Ismeretlen"
        )
        embed.add_field(
            name="🎯 Érintett Tag",
            value=f"{target_mention}\nNév: `{target_user}`\nID: `{target_user.id}`",
            inline=True,
        )
    else:
        embed.add_field(
            name="🎯 Érintett Tag", value=f"ID: `{target_id_str}`", inline=True
        )

    embed.add_field(name="⏱️ Időtartam / Idő", value=f"`{duration}`", inline=True)
    embed.add_field(name="📌 Ok", value=f"{reason}", inline=False)

    if extra_info:
        embed.add_field(name="🚨 További infó", value=extra_info, inline=False)

    await log_channel.send(embed=embed)


# ------------------- WARN FÜGGVÉNY (Automatikus) -------------------
async def process_automatic_warn(
    user: discord.Member,
    guild: discord.Guild,
    reason_text: str,
    staff_display_name: str,
    channel: discord.TextChannel,
    interaction_user: discord.User = None,
):
    user_id = user.id

    if user_id not in WARN_STORAGE:
        WARN_STORAGE[user_id] = 0

    WARN_STORAGE[user_id] += 1
    current_warns = WARN_STORAGE[user_id]
    warns_left = max(0, 4 - current_warns)

    auto_punish_msg = ""
    mute_seconds = 0
    total_mute_minutes = 0

    if current_warns >= 4:
        cycle = (current_warns - 1) // 4
        base_minutes = 60
        extra_minutes = cycle * 30
        total_mute_minutes = base_minutes + extra_minutes
        mute_seconds = total_mute_minutes * 60

        hours = total_mute_minutes // 60
        minutes = total_mute_minutes % 60
        time_text = f"{hours} óra" if hours > 0 else ""
        if minutes > 0:
            time_text += f" {minutes} perc"

        try:
            await user.timeout(
                timedelta(seconds=mute_seconds),
                reason=f"Automatikus büntetés 4 warn elérése miatt (Kör: {cycle + 1})",
            )
            auto_punish_msg = (
                f"\n\n🚨 **Elérte a 4. warnt, ezért automatikus némítást kapott"
                f" {time_text} időtartamra! (Warnjai reszelve lettek.)**"
            )
        except Exception as e:
            auto_punish_msg = f"\n\n❌ Hiba az automatikus némításkor: {e}"

        WARN_STORAGE[user_id] = 0
        current_warns_for_dm = 4
        warns_left_for_dm = 0
    else:
        current_warns_for_dm = current_warns
        warns_left_for_dm = warns_left

    # DM küldése a felhasználónak
    try:
        dm_embed = discord.Embed(
            title="⚠️ Figyelmeztetést kaptál!",
            description=f"Figyelmeztettek a(z) **{guild.name}** szerveren.",
            color=(
                discord.Color.red()
                if current_warns_for_dm == 4
                else discord.Color.orange()
            ),
        )
        dm_embed.add_field(name="📌 Ok", value=reason_text, inline=False)
        dm_embed.add_field(
            name="🛡️ Végrehajtó Staff", value=staff_display_name, inline=False
        )
        dm_embed.add_field(
            name="📊 Jelenlegi warnok",
            value=f"{current_warns_for_dm} / 4",
            inline=True,
        )
        dm_embed.add_field(
            name="⏳ Hátralévő warn", value=f"{warns_left_for_dm} db", inline=True
        )
        await user.send(embed=dm_embed)
    except discord.Forbidden:
        pass

    # Üzenet a csatornára
    response_text = (
        f"✅ **{user.mention}** figyelmeztetve lett a tiltott linkküldés"
        f" miatt!\n📊 Aktuális warnok: **{current_warns if current_warns != 0 else 4}/4**"
        f" (Még {warns_left} van hátra a büntetésig)\n📌 Ok: {reason_text}"
        f"{auto_punish_msg}"
    )
    await channel.send(response_text, delete_after=15)

    # Naplózás a log csatornába
    bot_user = (
        interaction_user
        if interaction_user
        else guild.me._user
        if hasattr(guild.me, "_user")
        else guild.me
    )
    await send_mod_log(
        guild=guild,
        action_type="Automatikus Link Warn",
        staff_user=bot_user,
        staff_name_input=staff_display_name,
        target_user=user,
        target_id_str=str(user.id),
        reason=reason_text,
        duration="Azonnali",
        extra_info=(
            f"Jelenlegi warnok száma: {current_warns_for_dm}/4"
            f"{auto_punish_msg}"
        ),
        color=discord.Color.orange(),
    )


# ------------------- 1. MUTE MODAL & PARANCS -------------------
class MuteModal(discord.ui.Modal, title="Tag Némítása (Mute)"):
    staff_name = discord.ui.TextInput(
        label="Staff neve", placeholder="A te neved...", required=True
    )
    reason = discord.ui.TextInput(
        label="Büntetés oka",
        style=discord.TextStyle.paragraph,
        placeholder="Írd le az okot...",
        required=True,
    )
    duration = discord.ui.TextInput(
        label="Büntetés ideje (s/m/h/d/w/y)",
        placeholder="Pl.: 30m, 1h, 2d...",
        required=True,
    )

    def __init__(self, target: discord.Member):
        super().__init__()
        self.target = target

    async def on_submit(self, interaction: discord.Interaction):
        seconds = parse_time(self.duration.value)
        if seconds <= 0:
            await interaction.response.send_message(
                "❌ **Hiba:** Érvénytelen időformátum! Használd pl.: `30m`, `1h`, `1d`.",
                ephemeral=True,
            )
            return

        try:
            duration_delta = timedelta(seconds=seconds)
            await self.target.timeout(
                duration_delta,
                reason=(
                    f"Staff: {self.staff_name.value} | Ok: {self.reason.value}"
                ),
            )

            dm_success = True
            try:
                dm_embed = discord.Embed(
                    title="🔇 Némítva lettél (Mute)",
                    description=(
                        "Felfüggesztést kaptál a(z)"
                        f" **{interaction.guild.name}** szerveren."
                    ),
                    color=discord.Color.orange(),
                )
                dm_embed.add_field(
                    name="📌 Ok", value=self.reason.value, inline=False
                )
                dm_embed.add_field(
                    name="🛡️ Végrehajtó Staff",
                    value=self.staff_name.value,
                    inline=True,
                )
                dm_embed.add_field(
                    name="⏱️ Időtartam", value=self.duration.value, inline=True
                )

                await self.target.send(embed=dm_embed)
            except discord.Forbidden:
                dm_success = False

            response_msg = (
                f"✅ **{self.target.mention}** sikeresen némítva lett"
                f" **{self.duration.value}** időtartamra!\n📌 **Ok:**"
                f" {self.reason.value}"
            )
            if not dm_success:
                response_msg += (
                    "\n*(Megjegyzés: A tagnak nem sikerült privát embedet küldeni, mert"
                    " le vannak tiltva a DM-jei.)*"
                )

            await interaction.response.send_message(response_msg, ephemeral=True)

            # Naplózás
            await send_mod_log(
                guild=interaction.guild,
                action_type="Mute (Némítás)",
                staff_user=interaction.user,
                staff_name_input=self.staff_name.value,
                target_user=self.target,
                target_id_str=str(self.target.id),
                reason=self.reason.value,
                duration=self.duration.value,
                color=discord.Color.orange(),
            )

        except Exception as e:
            await interaction.response.send_message(
                f"❌ Hiba történt a némítás során: {e}", ephemeral=True
            )


# ------------------- 2. UNMUTE MODAL & PARANCS -------------------
class UnmuteModal(discord.ui.Modal, title="Tag Némításának Feloldása (Unmute)"):
    staff_name = discord.ui.TextInput(
        label="Staff neve", placeholder="A te neved...", required=True
    )
    reason = discord.ui.TextInput(
        label="Feloldás oka",
        style=discord.TextStyle.paragraph,
        placeholder="Írd le az okot...",
        required=True,
    )

    def __init__(self, target: discord.Member):
        super().__init__()
        self.target = target

    async def on_submit(self, interaction: discord.Interaction):
        try:
            await self.target.timeout(
                None, reason=f"Staff: {self.staff_name.value} | Ok: {self.reason.value}"
            )

            dm_success = True
            try:
                dm_embed = discord.Embed(
                    title="🔊 Némítás feloldva (Unmute)",
                    description=(
                        "A némításod feloldásra került a(z)"
                        f" **{interaction.guild.name}** szerveren."
                    ),
                    color=discord.Color.green(),
                )
                dm_embed.add_field(
                    name="📌 Ok", value=self.reason.value, inline=False
                )
                dm_embed.add_field(
                    name="🛡️ Végrehajtó Staff",
                    value=self.staff_name.value,
                    inline=False,
                )

                await self.target.send(embed=dm_embed)
            except discord.Forbidden:
                dm_success = False

            response_msg = (
                f"✅ **{self.target.mention}** némítása sikeresen feloldva!\n📌 **Ok:**"
                f" {self.reason.value}"
            )
            if not dm_success:
                response_msg += (
                    "\n*(Megjegyzés: A tagnak nem sikerült privát embedet küldeni, mert"
                    " le vannak tiltva a DM-jei.)*"
                )

            await interaction.response.send_message(response_msg, ephemeral=True)

            # Naplózás
            await send_mod_log(
                guild=interaction.guild,
                action_type="Unmute (Némítás Feloldás)",
                staff_user=interaction.user,
                staff_name_input=self.staff_name.value,
                target_user=self.target,
                target_id_str=str(self.target.id),
                reason=self.reason.value,
                duration="Azonnali",
                color=discord.Color.green(),
            )

        except Exception as e:
            await interaction.response.send_message(
                f"❌ Hiba történt a némítás feloldása során: {e}", ephemeral=True
            )


# ------------------- 3. BAN MODAL & PARANCS -------------------
class BanModal(discord.ui.Modal, title="Tag Kitiltása (Ban)"):
    staff_name = discord.ui.TextInput(
        label="Staff neve", placeholder="A te neved...", required=True
    )
    reason = discord.ui.TextInput(
        label="Büntetés oka",
        style=discord.TextStyle.paragraph,
        placeholder="Írd le az okot...",
        required=True,
    )
    duration = discord.ui.TextInput(
        label="Büntetés ideje (s/m/h/d/w/y vagy perm)",
        placeholder="Pl.: 7d, 1y...",
        required=True,
    )

    def __init__(self, target: discord.Member):
        super().__init__()
        self.target = target

    async def on_submit(self, interaction: discord.Interaction):
        dm_success = True
        try:
            dm_embed = discord.Embed(
                title="🔨 Kitiltva lettél (Ban)",
                description=(
                    f"Ki lettél tiltva a(z) **{interaction.guild.name}** szerverről."
                ),
                color=discord.Color.red(),
            )
            dm_embed.add_field(name="📌 Ok", value=self.reason.value, inline=False)
            dm_embed.add_field(
                name="🛡️ Végrehajtó Staff", value=self.staff_name.value, inline=True
            )
            dm_embed.add_field(
                name="⏱️ Időtartam / Jelleg",
                value=self.duration.value,
                inline=True,
            )

            await self.target.send(embed=dm_embed)
        except discord.Forbidden:
            dm_success = False

        try:
            await self.target.ban(
                reason=(
                    f"Staff: {self.staff_name.value} | Idő:"
                    f" {self.duration.value} | Ok: {self.reason.value}"
                )
            )

            response_msg = (
                f"✅ **{self.target.mention}** sikeresen ki lett tiltva!\n📌 **Ok:**"
                f" {self.reason.value}"
            )
            if not dm_success:
                response_msg += (
                    "\n*(Megjegyzés: A tagnak nem sikerült privát embedet küldeni, mert"
                    " le vannak tiltva a DM-jei.)*"
                )

            await interaction.response.send_message(response_msg, ephemeral=True)

            # Naplózás
            await send_mod_log(
                guild=interaction.guild,
                action_type="Ban (Kitiltás)",
                staff_user=interaction.user,
                staff_name_input=self.staff_name.value,
                target_user=self.target,
                target_id_str=str(self.target.id),
                reason=self.reason.value,
                duration=self.duration.value,
                color=discord.Color.red(),
            )

        except Exception as e:
            await interaction.response.send_message(
                f"❌ Hiba történt a kitiltás során: {e}", ephemeral=True
            )


# ------------------- 4. UNBAN MODAL & PARANCS -------------------
class UnbanModal(discord.ui.Modal, title="Kitiltás Feloldása (Unban)"):
    staff_name = discord.ui.TextInput(
        label="Staff neve", placeholder="A te neved...", required=True
    )
    user_id_input = discord.ui.TextInput(
        label="Felhasználó ID-je",
        placeholder="Pl.: 123456789012345678",
        required=True,
    )
    reason = discord.ui.TextInput(
        label="Feloldás oka",
        style=discord.TextStyle.paragraph,
        placeholder="Írd le az okot...",
        required=True,
    )

    def __init__(self, guild: discord.Guild):
        super().__init__()
        self.guild = guild

    async def on_submit(self, interaction: discord.Interaction):
        try:
            user_id = int(self.user_id_input.value.strip())
        except ValueError:
            await interaction.response.send_message(
                "❌ **Hiba:** Érvénytelen felhasználói ID! Csak számokat adj meg.",
                ephemeral=True,
            )
            return

        user = self.guild.get_member(user_id)
        if not user:
            try:
                user = await interaction.client.fetch_user(user_id)
            except discord.NotFound:
                user = None

        try:
            await self.guild.fetch_ban(discord.Object(id=user_id))
        except discord.NotFound:
            await interaction.response.send_message(
                "❌ **Hiba:** Ez a felhasználó nincs kitiltva a szerverről!",
                ephemeral=True,
            )
            return

        try:
            await self.guild.unban(
                discord.Object(id=user_id),
                reason=f"Staff: {self.staff_name.value} | Ok: {self.reason.value}",
            )

            dm_success = True
            if user:
                try:
                    dm_embed = discord.Embed(
                        title="🔓 Kitiltás feloldva (Unban)",
                        description=(
                            "A kitiltásod feloldásra került a(z)"
                            f" **{interaction.guild.name}** szerveren."
                        ),
                        color=discord.Color.green(),
                    )
                    dm_embed.add_field(
                        name="📌 Ok", value=self.reason.value, inline=False
                    )
                    dm_embed.add_field(
                        name="🛡️ Végrehajtó Staff",
                        value=self.staff_name.value,
                        inline=False,
                    )
                    await user.send(embed=dm_embed)
                except discord.Forbidden:
                    dm_success = False
            else:
                dm_success = False

            response_msg = (
                f"✅ A kitiltás sikeresen feloldva a(z) `{user_id}` ID-jű"
                f" felhasználó számára!\n📌 **Ok:** {self.reason.value}"
            )
            if not dm_success:
                response_msg += (
                    "\n*(Megjegyzés: A tagnak nem sikerült privát embedet küldeni.)*"
                )

            await interaction.response.send_message(response_msg, ephemeral=True)

            # Naplózás
            await send_mod_log(
                guild=interaction.guild,
                action_type="Unban (Kitiltás Feloldás)",
                staff_user=interaction.user,
                staff_name_input=self.staff_name.value,
                target_user=user,
                target_id_str=str(user_id),
                reason=self.reason.value,
                duration="Azonnali",
                color=discord.Color.green(),
            )

        except Exception as e:
            await interaction.response.send_message(
                f"❌ Hiba történt a kitiltás feloldása során: {e}", ephemeral=True
            )


# ------------------- 5. WARN MODAL & PARANCS -------------------
class WarnModal(discord.ui.Modal, title="Figyelmeztetés (Warn)"):
    staff_name = discord.ui.TextInput(
        label="Staff neve", placeholder="A te neved...", required=True
    )
    reason = discord.ui.TextInput(
        label="Büntetés oka",
        style=discord.TextStyle.paragraph,
        placeholder="Írd le az okot...",
        required=True,
    )

    def __init__(self, target: discord.Member):
        super().__init__()
        self.target = target

    async def on_submit(self, interaction: discord.Interaction):
        user_id = self.target.id

        if user_id not in WARN_STORAGE:
            WARN_STORAGE[user_id] = 0

        WARN_STORAGE[user_id] += 1
        current_warns = WARN_STORAGE[user_id]

        warns_left = max(0, 4 - current_warns)

        auto_punish_msg = ""
        mute_seconds = 0
        total_mute_minutes = 0

        if current_warns >= 4:
            cycle = (current_warns - 1) // 4
            base_minutes = 60
            extra_minutes = cycle * 30
            total_mute_minutes = base_minutes + extra_minutes
            mute_seconds = total_mute_minutes * 60

            hours = total_mute_minutes // 60
            minutes = total_mute_minutes % 60
            time_text = f"{hours} óra" if hours > 0 else ""
            if minutes > 0:
                time_text += f" {minutes} perc"

            try:
                await self.target.timeout(
                    timedelta(seconds=mute_seconds),
                    reason=f"Automatikus büntetés 4 warn elérése miatt (Kör: {cycle + 1})",
                )
                auto_punish_msg = (
                    f"\n\n🚨 **Elérted a 4. warnt, ezért automatikus némítást kaptál"
                    f" {time_text} időtartamra! (Warnjaid reszelve lettek.)**"
                )
            except Exception as e:
                auto_punish_msg = f"\n\n❌ Hiba az automatikus némításkor: {e}"

            WARN_STORAGE[user_id] = 0
            current_warns_for_dm = 4
            warns_left_for_dm = 0
        else:
            current_warns_for_dm = current_warns
            warns_left_for_dm = warns_left

        dm_success = True
        try:
            dm_embed = discord.Embed(
                title="⚠️ Figyelmeztetést kaptál!",
                description=(
                    f"Figyelmeztettek a(z) **{interaction.guild.name}** szerveren."
                ),
                color=(
                    discord.Color.red()
                    if current_warns_for_dm == 4
                    else discord.Color.orange()
                ),
            )
            dm_embed.add_field(name="📌 Ok", value=self.reason.value, inline=False)
            dm_embed.add_field(
                name="🛡️ Végrehajtó Staff", value=self.staff_name.value, inline=False
            )
            dm_embed.add_field(
                name="📊 Jelenlegi warnok",
                value=f"{current_warns_for_dm} / 4",
                inline=True,
            )
            dm_embed.add_field(
                name="⏳ Hátralévő warn", value=f"{warns_left_for_dm} db", inline=True
            )

            if current_warns_for_dm == 4 and total_mute_minutes > 0:
                hours = total_mute_minutes // 60
                minutes = total_mute_minutes % 60
                t_str = f"{hours} óra" if hours > 0 else ""
                if minutes > 0:
                    t_str += f" {minutes} perc"
                dm_embed.add_field(
                    name="🚨 Automatikus Büntetés",
                    value=(
                        "Elérted a 4 warnt! Némítva lettél"
                        f" {t_str} időtartamra, a warnjaid nullázódtak."
                    ),
                    inline=False,
                )

            await self.target.send(embed=dm_embed)
        except discord.Forbidden:
            dm_success = False

        response_text = (
            f"✅ **{self.target.mention}** figyelmeztetve lett!\n"
            f"📊 Aktuális warnok: **{current_warns if current_warns != 0 else 4}/4**"
            f" (Még {warns_left} van hátra a büntetésig)\n📌 Ok:"
            f" {self.reason.value}"
            f"{auto_punish_msg}"
        )
        if not dm_success:
            response_text += (
                "\n*(Megjegyzés: A tagnak nem sikerült beágyazott privát üzenetet"
                " küldeni, mert le vannak tiltva a DM-jei.)*"
            )

        await interaction.response.send_message(response_text, ephemeral=True)

        # Naplózás
        await send_mod_log(
            guild=interaction.guild,
            action_type="Warn (Figyelmeztetés)",
            staff_user=interaction.user,
            staff_name_input=self.staff_name.value,
            target_user=self.target,
            target_id_str=str(self.target.id),
            reason=self.reason.value,
            duration=f"Jelenlegi warnok: {current_warns_for_dm}/4",
            extra_info=auto_punish_msg.strip(),
            color=discord.Color.orange(),
        )


# ------------------- MODERÁCIÓS & SZŰRŐ COG -------------------
class ModerationCog(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    # --- AUTOMATIKUS LINK SZŰRÉS ÉS WARN ---
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        if message.guild is None:
            return

        channel = message.channel
        if hasattr(channel, "category") and channel.category is not None:
            if channel.category.id in EXCLUDED_CATEGORY_IDS:
                return

        # Üzenet felbontása szavakra (így kezeljük a sortöréseket és szóközöket is)
        words = message.content.split()
        has_bad_link = False

        for word in words:
            if URL_REGEX.search(word):
                word_lower = word.lower()
                
                # Bővített domain lista (hozzáadva: klipy.com, pinterest.com)
                allowed_domains = ["tenor.com", "giphy.com", "imgur.com", "gifer.com", "klipy.com", "pinterest.com", "cdn.discordapp.com", "media.discordapp.net", "discord.com/channels"]
                allowed_extensions = [".gif", ".png", ".jpg", ".jpeg", ".webp", ".mp4"]
                
                is_allowed_gif = any(domain in word_lower for domain in allowed_domains) or any(ext in word_lower for ext in allowed_extensions)
                
                # Ha a link GIF, Kép, vagy Videó, átengedjük
                if is_allowed_gif:
                    continue
                else:
                    # Ha találunk akár csak egy tiltott linket, megjelöljük és megállítjuk a keresést
                    has_bad_link = True
                    break

        # A törlés és a WARN CSAK AKKOR fut le, ha a has_bad_link értéke True!
        if has_bad_link:
            try:
                await message.delete()
            except discord.Forbidden:
                pass
            except discord.HTTPException:
                pass

            # Automatikus figyelmeztetés kiosztása
            await process_automatic_warn(
                user=message.author,
                guild=message.guild,
                reason_text="Tiltott link küldése ebben a csatornában.",
                staff_display_name="LinkSzűrő Bot",
                channel=channel,
                interaction_user=self.bot.user,
            )

    # --- SLASH PARANCSOK ---
    @app_commands.command(
        name="mute", description="Felfüggeszti/némítja a kiválasztott felhasználót."
    )
    @has_staff_role()
    async def mute_command(
        self, interaction: discord.Interaction, target: discord.Member
    ):
        await interaction.response.send_modal(MuteModal(target))

    @app_commands.command(
        name="unmute", description="Feloldja a kiválasztott felhasználó némítását."
    )
    @has_staff_role()
    async def unmute_command(
        self, interaction: discord.Interaction, target: discord.Member
    ):
        await interaction.response.send_modal(UnmuteModal(target))

    @app_commands.command(
        name="ban", description="Kitiltja a kiválasztott felhasználót a szerverről."
    )
    @has_staff_role()
    async def ban_command(
        self, interaction: discord.Interaction, target: discord.Member
    ):
        await interaction.response.send_modal(BanModal(target))

    @app_commands.command(
        name="unban", description="Feloldja egy felhasználó kitiltását ID alapján."
    )
    @has_staff_role()
    async def unban_command(self, interaction: discord.Interaction):
        await interaction.response.send_modal(UnbanModal(interaction.guild))

    @app_commands.command(
        name="warn", description="Figyelmeztetésben részesít egy felhasználót."
    )
    @has_staff_role()
    async def warn_command(
        self, interaction: discord.Interaction, target: discord.Member
    ):
        await interaction.response.send_modal(WarnModal(target))


async def setup(bot):
    await bot.add_cog(ModerationCog(bot))