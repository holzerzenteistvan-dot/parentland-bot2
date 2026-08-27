import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timezone

class Invites(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.invites = {}          # {guild_id: [invite objektumok]}
        self.inviter_map = {}      # {(guild_id, member_id): inviter_id}
        self.user_stats = {}       # {guild_id: {user_id: {"regular": 0, "left": 0, "fake": 0, "bonus": 0}}}
        bot.loop.create_task(self.load_invites())

    async def load_invites(self):
        await self.bot.wait_until_ready()
        for guild in self.bot.guilds:
            try:
                self.invites[guild.id] = await guild.invites()
            except discord.Forbidden:
                pass
            if guild.id not in self.user_stats:
                self.user_stats[guild.id] = {}

    def get_user_stat(self, guild_id, user_id):
        if guild_id not in self.user_stats:
            self.user_stats[guild_id] = {}
        if user_id not in self.user_stats[guild_id]:
            self.user_stats[guild_id][user_id] = {"regular": 0, "left": 0, "fake": 0, "bonus": 0}
        return self.user_stats[guild_id][user_id]

    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        try:
            self.invites[guild.id] = await guild.invites()
        except discord.Forbidden:
            pass
        self.user_stats[guild.id] = {}

    @commands.Cog.listener()
    async def on_invite_create(self, invite):
        if invite.guild.id in self.invites:
            self.invites[invite.guild.id] = await invite.guild.invites()

    @commands.Cog.listener()
    async def on_invite_delete(self, invite):
        if invite.guild.id in self.invites:
            self.invites[invite.guild.id] = await invite.guild.invites()

    @commands.Cog.listener()
    async def on_member_join(self, member):
        guild = member.guild
        if guild.id not in self.invites:
            return

        old_invites = self.invites[guild.id]
        
        try:
            new_invites = await guild.invites()
        except discord.Forbidden:
            return

        self.invites[guild.id] = new_invites

        inviter = None
        used_invite = None

        # Megkeressük, melyik meghívó használati száma nőtt meg
        for new_inv in new_invites:
            for old_inv in old_invites:
                if new_inv.code == old_inv.code and new_inv.uses > old_inv.uses:
                    inviter = new_inv.inviter
                    used_invite = new_inv
                    break
            if inviter:
                break

        channel_id = 1533125471686889705
        channel = guild.get_channel(channel_id)
        if not channel:
            return

        embed = discord.Embed(
            color=discord.Color.green(),
            timestamp=discord.utils.utcnow()
        )

        # Hamis fiók szűrés (pl. ha a fiók 7 napnál fiatalabb)
        account_age_days = (datetime.now(timezone.utc) - member.created_at).days
        is_fake = account_age_days < 7

        if inviter and inviter.id != member.id:
            # Elmentjük, hogy ki hívta ki
            self.inviter_map[(guild.id, member.id)] = inviter.id
            stats = self.get_user_stat(guild.id, inviter.id)

            if is_fake:
                stats["fake"] += 1
                status_note = "⚠️ (Hamis/Alt fiók)"
            else:
                stats["regular"] += 1
                status_note = ""

            total_effective = stats["regular"] - stats["left"] + stats["bonus"]

            embed.description = (
                f"📥 **{member.mention}** csatlakozott a szerverhez!\n"
                f"👤 **Aki hívta:** {inviter.mention} (`{inviter}`)\n"
                f"🔗 **Használt kód:** `{used_invite.code}` {status_note}\n"
                f"📊 **Meghívók:** {total_effective} valós "
                f"(`{stats['regular']}` valós, `{stats['left']}` kilépett, `{stats['fake']}` hamis)"
            )
        else:
            embed.description = (
                f"📥 **{member.mention}** csatlakozott a szerverhez!\n"
                f"👤 **Aki hívta:** Nem beazonosítható (Vanity URL / Direkt link / Fedezet)"
            )

        await channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        guild = member.guild
        channel_id = 1533125471686889705
        channel = guild.get_channel(channel_id)

        embed = discord.Embed(
            color=discord.Color.red(),
            timestamp=discord.utils.utcnow()
        )

        # Ellenőrizzük, hogy el van-e mentve, ki hívta meg ezt a tagot
        inviter_id = self.inviter_map.pop((guild.id, member.id), None)

        if inviter_id:
            inviter = guild.get_member(inviter_id)
            stats = self.get_user_stat(guild.id, inviter_id)
            stats["left"] += 1
            total_effective = stats["regular"] - stats["left"] + stats["bonus"]

            inviter_text = inviter.mention if inviter else f"Ismeretlen felhasználó (ID: {inviter_id})"

            embed.description = (
                f"📤 **{member.name}** kilépett a szerverről.\n"
                f"👤 **Aki hívta:** {inviter_text}\n"
                f"📉 **Meghívók:** {total_effective} valós "
                f"(`{stats['regular']}` valós, `{stats['left']}` kilépett)"
            )
        else:
            embed.description = (
                f"📤 **{member.name}** kilépett a szerverről.\n"
                f"👤 **Aki hívta:** Nem beazonosítható"
            )

        if channel:
            await channel.send(embed=embed)

    # Opcionális: /meghívók parancs, hogy a felhasználók le tudják kérdezni az adataikat
    @app_commands.command(name="meghívók", description="Lekérdezi a saját vagy egy másik tag meghívási statisztikáit.")
    @app_commands.describe(tag="Melyik tag adataira vagy kíváncsi? (Hagyd üresen a sajátodhoz)")
    async def meghivok_command(self, interaction: discord.Interaction, tag: discord.Member = None):
        target = tag or interaction.user
        stats = self.get_user_stat(interaction.guild.id, target.id)
        
        total_effective = stats["regular"] - stats["left"] + stats["bonus"]

        embed = discord.Embed(
            title=f"📊 {target.display_name} meghívási statisztikái",
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(name="Összes valós", value=str(total_effective), inline=True)
        embed.add_field(name="Sikeres", value=str(stats["regular"]), inline=True)
        embed.add_field(name="Kilépett", value=str(stats["left"]), inline=True)
        embed.add_field(name="Hamis/Alt", value=str(stats["fake"]), inline=True)
        embed.add_field(name="Bónusz", value=str(stats["bonus"]), inline=True)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(Invites(bot))