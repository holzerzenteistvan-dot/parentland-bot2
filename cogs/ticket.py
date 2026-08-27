import discord
from discord.ext import commands
from discord import app_commands
import io
import asyncio
from datetime import datetime

# ------------------- BEÁLLÍTÁSOK / ID-K -------------------
TICKET_CATEGORY_ID = 1528774116805447922  # A kategória ID-ja
TRANSCRIPT_CHANNEL_ID = 1530579409990586378  # A log/transcript csatorna ID-ja
PARTNER_CHANNEL_ID = 1528819656335294565  # A hivatalos partner szoba ID-ja

# Kategóriánként külön megadható Staff rangok ID-i listákban:
TICKET_STAFF_ROLES = {
    "hibajegy": [
        1530634556414365826, # Alapító
        1529131477756018779, # Tulajdonos
        1529131248075669634, # Admin
        1529130472247136496  # Moderátor
    ],
    "partner": [
        1530634556414365826, # Alapító
        1529131477756018779, # Tulajdonos
        1529131248075669634, # Admin
        1529129761870319656  # Partner Manager
    ],
    "tgf": [
        1530634556414365826, # Alapító
        1529131477756018779, # Tulajdonos
        1529129916849852697  # Média Manager
    ],
    "nyeremeny": [
        1530634556414365826, # Alapító
        1529131477756018779, # Tulajdonos
        1529131248075669634, # Admin
        1529130472247136496  # Moderátor
    ],
    "fellebbezes": [
        1530634556414365826, # Alapító
        1529131477756018779, # Tulajdonos
        1529131248075669634  # Admin
    ]
}

# Segédfüggvény a ticket típusának meghatározására a csatorna nevéből
def get_ticket_type_from_channel(channel: discord.TextChannel) -> str:
    parts = channel.name.split("-")
    if parts:
        t_type = parts[0]
        if t_type in TICKET_STAFF_ROLES:
            return t_type
    return None

# Segédfüggvény annak ellenőrzésére, hogy a user az adott kategóriában Staff-e
def is_staff(member: discord.Member, ticket_type: str = None) -> bool:
    if member.guild_permissions.administrator:
        return True
    
    if ticket_type and ticket_type in TICKET_STAFF_ROLES:
        allowed_roles = TICKET_STAFF_ROLES[ticket_type]
    else:
        allowed_roles = [r_id for roles in TICKET_STAFF_ROLES.values() for r_id in roles]
        
    return any(role.id in allowed_roles for role in member.roles)


# ------------------- KÖZÖS TRANSCRIPT & TÖRLÉS FÜGGVÉNY -------------------
async def close_and_transcript_ticket(channel: discord.TextChannel, closed_by: discord.Member, extra_info: str = ""):
    guild = channel.guild

    messages = []
    async for message in channel.history(limit=None, oldest_first=True):
        timestamp = message.created_at.strftime("%Y-%m-%d %H:%M:%S")
        author = f"{message.author.name} ({message.author.id})"
        content = message.content
        
        attachments = [att.url for att in message.attachments]
        if attachments:
            content += f" [Csatolmányok: {', '.join(attachments)}]"
            
        messages.append(f"[{timestamp}] {author}: {content}")

    transcript_content = f"--- HIBAJEGY TRANSCRIPT: {channel.name} ---\n"
    transcript_content += f"Lezárta: {closed_by.name} ({closed_by.id})\n"
    if extra_info:
        transcript_content += f"Megjegyzés: {extra_info}\n"
    transcript_content += f"Dátum: {discord.utils.utcnow().strftime('%Y-%m-%d %H:%M:%S')}\n"
    transcript_content += "=" * 50 + "\n\n"
    transcript_content += "\n".join(messages)

    file = discord.File(
        fp=io.BytesIO(transcript_content.encode("utf-8")),
        filename=f"transcript-{channel.name}.txt"
    )

    log_channel = guild.get_channel(TRANSCRIPT_CHANNEL_ID)
    if log_channel:
        embed = discord.Embed(
            title="🔒 Hibajegy Lezárva",
            description=f"A(z) `{channel.name}` nevű hibajegy lezárásra került.",
            color=discord.Color.red()
        )
        embed.add_field(name="Lezárta:", value=closed_by.mention, inline=True)
        if extra_info:
            embed.add_field(name="Státusz / Infó:", value=extra_info, inline=False)
        embed.timestamp = discord.utils.utcnow()
        
        await log_channel.send(embed=embed, file=file)

    await asyncio.sleep(3)
    try:
        await channel.delete(reason=f"Hibajegy lezárva - {closed_by.name} által")
    except Exception:
        pass


# ------------------- ELUTASÍTÁSI INDOKLÓ MODAL -------------------
class RejectReasonModal(discord.ui.Modal, title="Partnerség Elutasítása"):
    reason_input = discord.ui.TextInput(
        label="Mi az elutasítás oka?",
        style=discord.TextStyle.paragraph,
        placeholder="Írd le részletesen az indokot...",
        required=True,
        max_length=1000
    )

    def __init__(self, channel: discord.TextChannel, closer: discord.Member, owner: discord.Member):
        super().__init__()
        self.channel = channel
        self.closer = closer
        self.owner = owner

    async def on_submit(self, interaction: discord.Interaction):
        reason = self.reason_input.value

        if self.owner:
            try:
                embed = discord.Embed(
                    title="❌ Partnerségi Kérelem Elutasítva",
                    description=f"Sajnálattal értesítünk, hogy a(z) **{interaction.guild.name}** szerverre beadott partnerségi kérelmedet elutasítottuk.",
                    color=discord.Color.red()
                )
                embed.add_field(name="📝 Elutasítás oka", value=reason, inline=False)
                embed.add_field(name="👤 Elutasította (Staff)", value=self.closer.mention, inline=False)
                embed.set_footer(
                    text="A ParentLand csapata Jóváhagyásával",
                    icon_url=interaction.guild.icon.url if interaction.guild.icon else None
                )
                embed.timestamp = discord.utils.utcnow()

                await self.owner.send(embed=embed)
            except Exception as e:
                print(f"Hiba az elutasító privát üzenet küldésekor: {e}")

        await interaction.response.send_message("❌ Partnerség elutasítva, indok elküldve a felhasználónak.", ephemeral=True)
        await close_and_transcript_ticket(self.channel, self.closer, f"Partnerség elutasítva. Indok: {reason}")


# ------------------- PARTNER DÖNTÉSI VIEW -------------------
class PartnerDecisionView(discord.ui.View):
    def __init__(self, channel: discord.TextChannel, closer: discord.Member, ticket_data: dict, owner: discord.Member):
        super().__init__(timeout=None)
        self.channel = channel
        self.closer = closer
        self.ticket_data = ticket_data
        self.owner = owner

    @discord.ui.button(label="Igen, elfogadom", style=discord.ButtonStyle.success, emoji="✅")
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        partner_channel = interaction.guild.get_channel(PARTNER_CHANNEL_ID)
        
        if partner_channel:
            server_name = self.ticket_data.get('Szerver Neve', 'Partner Szerver')
            partner_text = self.ticket_data.get('Partner Szöveg', 'Nincs megadva')

            embed = discord.Embed(
                title=f"🤝 {server_name}",
                color=discord.Color.from_rgb(255, 140, 0)
            )
            
            if interaction.guild.icon:
                embed.set_thumbnail(url=interaction.guild.icon.url)
            
            # Hosszú partner szöveg biztonságos darabolása mezőkre, hogy ne vágja le a Discord
            if len(partner_text) > 1024:
                chunks = [partner_text[i:i+1024] for i in range(0, len(partner_text), 1024)]
                for chunk in chunks:
                    embed.add_field(name="\u200b", value=chunk, inline=False)
            else:
                embed.add_field(name="\u200b", value=partner_text, inline=False)
            
            # Elválasztó vonal és a Partner tag különálló mezőben
            embed.add_field(
                name="━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
                value=f"👤 **Partner:** {self.owner.mention if self.owner else 'Ismeretlen'}\n🌐 **Web:** HAMAROSAN... | 🖥️ **IP:** HAMAROSAN...",
                inline=False
            )

            embed.set_footer(
                text="A ParentLand csapata Jóváhagyásával",
                icon_url=interaction.guild.icon.url if interaction.guild.icon else None
            )
            embed.timestamp = discord.utils.utcnow()
            
            await partner_channel.send(embed=embed)
            await interaction.response.send_message("✅ A partnerség elfogadva, posztolva a partner szobába.", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Hiba: Nem találom a partner szobát!", ephemeral=True)
            
        await close_and_transcript_ticket(self.channel, self.closer, "Partnerség elfogadva")

    @discord.ui.button(label="Nem, elutasítom", style=discord.ButtonStyle.danger, emoji="❌")
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(RejectReasonModal(self.channel, self.closer, self.owner))


# ------------------- LEZÁRÁS GOMB & LOGIKA -------------------
class CloseTicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Hibajegy lezárása", 
        style=discord.ButtonStyle.danger, 
        emoji="🔒", 
        custom_id="close_ticket_button"
    )
    async def close_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        channel = interaction.channel
        ticket_type = get_ticket_type_from_channel(channel)

        if not is_staff(interaction.user, ticket_type):
            await interaction.response.send_message("❌ **Ezt a hibajegyet csak az erre jogosult Staff tagok zárhatják le!**", ephemeral=True)
            return

        if ticket_type == "partner":
            owner = None
            for member, overwrite in channel.overwrites.items():
                if isinstance(member, discord.Member) and overwrite.read_messages:
                    owner = member
                    break

            last_msg = [m async for m in channel.history(limit=1, oldest_first=False)][0]
            fields = {}
            if last_msg.embeds:
                for field in last_msg.embeds[0].fields:
                    clean_name = field.name.replace("📌 ", "").replace(":", "").strip()
                    fields[clean_name] = field.value
            
            await interaction.response.send_message(
                "❓ **Partner ticketet zársz le! Elfogadod a partnerséget?**", 
                view=PartnerDecisionView(channel, interaction.user, fields, owner), 
                ephemeral=True
            )
        else:
            await interaction.response.send_message("🔒 **A hibajegy lezárásra kerül, transcript készül...**", ephemeral=True)
            await close_and_transcript_ticket(channel, interaction.user, "Ticket lezárva")


# ------------------- HELPER FÜGGVÉNY -------------------
async def create_ticket_channel(interaction: discord.Interaction, ticket_type: str, type_title: str, fields: dict):
    guild = interaction.guild
    user = interaction.user

    clean_username = "".join(c for c in user.name.lower() if c.isalnum() or c in ("-", "_"))
    channel_name = f"{ticket_type}-{clean_username}"

    existing_channel = discord.utils.get(guild.text_channels, name=channel_name)
    if existing_channel:
        await interaction.response.send_message(
            f"⚠️ Már van egy nyitott hibajegyed ebben a kategóriában: {existing_channel.mention}", 
            ephemeral=True
        )
        return

    category = guild.get_channel(TICKET_CATEGORY_ID)
    
    if category is None or not isinstance(category, discord.CategoryChannel):
        await interaction.response.send_message(
            "❌ **Hiba:** A beállított `TICKET_CATEGORY_ID` nem létezik vagy nem kategória!",
            ephemeral=True
        )
        return

    overwrites = {
        guild.default_role: discord.PermissionOverwrite(read_messages=False),
        user: discord.PermissionOverwrite(read_messages=True, send_messages=True, attach_files=True),
        guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
    }

    staff_mentions = []
    role_ids = TICKET_STAFF_ROLES.get(ticket_type, [])
    for role_id in role_ids:
        staff_role = guild.get_role(role_id)
        if staff_role:
            overwrites[staff_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
            staff_mentions.append(staff_role.mention)

    try:
        ticket_channel = await guild.create_text_channel(
            name=channel_name,
            category=category,
            overwrites=overwrites,
            reason=f"Hibajegy nyitva: {user.name} ({type_title})"
        )

        embed = discord.Embed(
            title=f"📩 {type_title} - {user.display_name}",
            description=f"Üdvözlünk {user.mention}!\n\nA megadott adataid alább láthatóak. A Support csapat hamarosan válaszol!",
            color=discord.Color.blue()
        )

        for label, val in fields.items():
            if not val:
                val = "Nincs megadva"
            
            if len(val) > 1024:
                chunks = [val[i:i+1024] for i in range(0, len(val), 1024)]
                for index, chunk in enumerate(chunks):
                    if index == 0:
                        embed.add_field(name=f"📌 {label}:", value=chunk, inline=False)
                    else:
                        embed.add_field(name="", value=chunk, inline=False)
            else:
                embed.add_field(name=f"📌 {label}:", value=val, inline=False)

        await ticket_channel.send(
            content=f"{user.mention} " + " ".join(staff_mentions),
            embed=embed,
            view=CloseTicketView()
        )

        await interaction.response.send_message(
            f"✅ **Sikeresen létrejött a hibajegyed!** Kattints ide: {ticket_channel.mention}", 
            ephemeral=True
        )
    except Exception as e:
        print(f"Hiba csatorna létrehozásakor: {e}")
        await interaction.response.send_message(f"❌ Hiba történt a csatorna létrehozásakor: {e}", ephemeral=True)


# ------------------- MODAL-OK -------------------
class SimaTicketModal(discord.ui.Modal, title="hibajegy"):
    title_input = discord.ui.TextInput(label="Cím", placeholder="Rövid összefoglaló...", required=True, max_length=100)
    desc_input = discord.ui.TextInput(label="Leírás", style=discord.TextStyle.paragraph, placeholder="Írd le részletesen...", required=True, max_length=4000)

    async def on_submit(self, interaction: discord.Interaction):
        fields = {"Cím": self.title_input.value, "Leírás": self.desc_input.value}
        await create_ticket_channel(interaction, "hibajegy", "hibajegy", fields)


class PartnerTicketModal(discord.ui.Modal, title="Partner"):
    server_name = discord.ui.TextInput(label="Szerver Neve", placeholder="Pl.: Saját Discord Szerver", required=True, max_length=100)
    member_count = discord.ui.TextInput(label="Mennyi tag van a szerveren?", placeholder="Pl.: 250", required=True, max_length=50)
    partner_text = discord.ui.TextInput(label="Partner szöveg", style=discord.TextStyle.paragraph, placeholder="Illeszd be...", required=True, max_length=4000)

    async def on_submit(self, interaction: discord.Interaction):
        fields = {"Szerver Neve": self.server_name.value, "Tagok Száma": self.member_count.value, "Partner Szöveg": self.partner_text.value}
        await create_ticket_channel(interaction, "partner", "Partner", fields)


class TGFTicketModal(discord.ui.Modal, title="TGF"):
    apply_for = discord.ui.TextInput(label="Mire jelentkeznél?", placeholder="Pl.: Moderátor, Builder...", required=True, max_length=100)
    birth_date = discord.ui.TextInput(label="Születési idő", placeholder="Pl.: 2008.05.12", required=True, max_length=100)

    async def on_submit(self, interaction: discord.Interaction):
        fields = {"Jelentkezési Pozíció": self.apply_for.value, "Születési Idő": self.birth_date.value}
        await create_ticket_channel(interaction, "tgf", "TGF", fields)


class GiveawayTicketModal(discord.ui.Modal, title="Nyereményjáték"):
    mc_name = discord.ui.TextInput(label="Minecraft Felhasználóneved", placeholder="Pl.: Steve123", required=True, max_length=100)
    prize = discord.ui.TextInput(label="Mit nyertél?", placeholder="Pl.: VIP Rang", required=True, max_length=200)

    async def on_submit(self, interaction: discord.Interaction):
        fields = {"Minecraft Felhasználónév": self.mc_name.value, "Nyert Tárgy/Rang": self.prize.value}
        await create_ticket_channel(interaction, "nyeremeny", "Nyereményjáték", fields)


class FellebbezésTicketModal(discord.ui.Modal, title="Fellebbezés"):
    mc_name = discord.ui.TextInput(
        label="Minecraft Felhasználónév", 
        placeholder="Pl.: Steve123", 
        required=True,
        max_length=100
    )
    punishment_reason = discord.ui.TextInput(
        label="Büntetés Oka", 
        placeholder="Miért kaptad a büntetést?", 
        required=True,
        max_length=500
    )
    appeal_reason = discord.ui.TextInput(
        label="Miért érzed jogtalannak?", 
        style=discord.TextStyle.paragraph, 
        placeholder="Írd le részletesen az indoklást...", 
        required=True,
        max_length=4000
    )

    async def on_submit(self, interaction: discord.Interaction):
        fields = {
            "Minecraft Felhasználónév": self.mc_name.value,
            "Büntetés Oka": self.punishment_reason.value,
            "Indoklás": self.appeal_reason.value
        }
        await create_ticket_channel(interaction, "fellebbezes", "Fellebbezés", fields)


# ------------------- LENYÍLÓ MENÜ -------------------
class TicketSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="hibajegy", description="Cím és leírás megadásával", emoji="🎫", value="hibajegy"),
            discord.SelectOption(label="Partner", description="Szerver név, tagok száma, partner szöveg", emoji="🤝", value="partner"),
            discord.SelectOption(label="TGF", description="Mire jelentkeznél és születési idő", emoji="📝", value="tgf"),
            discord.SelectOption(label="Nyereményjáték", description="Minecraft név és nyert tárgy átvétele", emoji="🎁", value="nyeremeny"),
            discord.SelectOption(label="Fellebbezés", description="Büntetés felülvizsgálata és indoklása", emoji="⚖️", value="fellebbezes"),
        ]
        super().__init__(placeholder="Válassz kategóriát...", min_values=1, max_values=1, options=options, custom_id="ticket_type_select")

    async def callback(self, interaction: discord.Interaction):
        selected = self.values[0]
        if selected == "hibajegy":
            modal = SimaTicketModal()
        elif selected == "partner":
            modal = PartnerTicketModal()
        elif selected == "tgf":
            modal = TGFTicketModal()
        elif selected == "nyeremeny":
            modal = GiveawayTicketModal()
        elif selected == "fellebbezes":
            modal = FellebbezésTicketModal()
        else:
            return

        await interaction.response.send_modal(modal)

        try:
            if interaction.message:
                await interaction.message.edit(view=TicketSelectView())
        except Exception as e:
            print(f"Hiba a panel resetelésekor: {e}")


class TicketSelectView(discord.ui.View):
    def __init__(self, timeout=None):
        super().__init__(timeout=timeout)
        self.add_item(TicketSelect())


# ------------------- MAIN COG -------------------
class TicketCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        try:
            await self.bot.tree.sync()
            print("Parancsok sikeresen szinkronizálva!")
        except Exception as e:
            print(f"Hiba a parancsok szinkronizálásakor: {e}")

    @app_commands.command(name="hibajegy", description="Kihelyezi a Hibajegy nyitó menüt a szobába.")
    @app_commands.checks.has_permissions(administrator=True)
    async def hibajegy_parancs(self, interaction: discord.Interaction):
        await interaction.response.send_message("✅ Hibajegy panel sikeresen kihelyezve!", ephemeral=True)
        
        embed = discord.Embed(
            title="🎫 Hibajegy Nyitás (Ticket System)",
            description=(
                "Miben segíthetünk? Válassz az alábbi lehetőségek közül a megfelelő űrlap megnyitásához:\n\n"
                "• **🎫 hibajegy:** Cím és leírás megadásával\n"
                "• **🤝 Partner:** Szerver adatok és partner szöveg\n"
                "• **📝 TGF:** Tagfelvételi jelentkezés\n"
                "• **🎁 Nyereményjáték:** Minecraft név és nyeremény átvétele\n"
                "• **⚖️ Fellebbezés:** Büntetés felülvizsgálata és indoklása"
            ),
            color=discord.Color.gold()
        )
        await interaction.channel.send(embed=embed, view=TicketSelectView())


async def setup(bot):
    bot.add_view(TicketSelectView())
    bot.add_view(CloseTicketView())
    await bot.add_cog(TicketCog(bot))