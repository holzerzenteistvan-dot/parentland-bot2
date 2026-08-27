import discord
from discord.ext import commands

# ------------------- BEÁLLÍTÁSOK -------------------
LOG_CHANNEL_ID = 1528774422767472691  # Ide küldi a belépő/kilépő üzeneteket

class UdvozloCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Szótár a meghívók tárolására {guild_id: {invite_code: uses}}
        self.invites_cache = {}

    async def update_invites_cache(self, guild):
        """Frissíti az adott szerver meghívóinak állapotát a memóriában."""
        try:
            guild_invites = await guild.invites()
            self.invites_cache[guild.id] = {invite.code: invite.uses for invite in guild_invites}
        except discord.Forbidden:
            self.invites_cache[guild.id] = {}

    # --- KORÁBBI MEGHÍVÓK BETÖLTÉSE A BOT INDULÁSAKOR ---
    @commands.Cog.listener()
    async def on_ready(self):
        for guild in self.bot.guilds:
            await self.update_invites_cache(guild)
        print("✅ [Udvozlo] Meghívók sikeresen betöltve a memóriába!")

    # --- BELÉPÉS (JOIN) ESEMÉNY ---
    @commands.Cog.listener()
    async def on_member_join(self, member):
        guild = member.guild
        channel = guild.get_channel(LOG_CHANNEL_ID)
        
        if not channel:
            print(f"❌ [Udvozlo Hiba] A {LOG_CHANNEL_ID} ID-jű csatorna nem található!")
            return

        inviter_text = "Ismeretlen (vagy egyéni URL)"
        old_invites = self.invites_cache.get(guild.id, {})
        
        # Kikeresük, hogy melyik meghívó használatszáma nőtt
        try:
            new_invites = await guild.invites()
            for invite in new_invites:
                if invite.code in old_invites and invite.uses > old_invites[invite.code]:
                    inviter_text = f"{invite.inviter.mention} (`{invite.inviter.name}`)"
                    break
            self.invites_cache[guild.id] = {invite.code: invite.uses for invite in new_invites}
        except discord.Forbidden:
            inviter_text = "Nincs jogosultság a meghívók olvasásához"

        avatar_url = member.avatar.url if member.avatar else member.default_avatar.url
        created_timestamp = int(member.created_at.timestamp())

        # Embed üzenet elkészítése
        embed = discord.Embed(
            title="👋 Egy új tag csatlakozott a szerverhez",
            description=f"Örömmel köszöntjük **{member.name}**-t közöttünk! Érezd jól magad! ✨",
            color=discord.Color.green()
        )
        
        embed.set_thumbnail(url=avatar_url)
        embed.add_field(name="👤 Felhasználó", value=member.mention, inline=False)
        embed.add_field(name="🆔 ID", value=f"`{member.id}`", inline=False)
        embed.add_field(name="📩 Meghívta", value=inviter_text, inline=False)
        embed.add_field(name="🎂 Fiók létrehozva", value=f"<t:{created_timestamp}:R>", inline=False)
        embed.add_field(name="📊 Tagok száma", value=f"**{guild.member_count}**", inline=False)

        embed.set_footer(
            text="A ParentLand csapata Jóváhagyásával",
            icon_url=guild.icon.url if guild.icon else None
        )
        embed.timestamp = discord.utils.utcnow()

        await channel.send(embed=embed)

    # --- KILÉPÉS (LEAVE) ESEMÉNY ---
    @commands.Cog.listener()
    async def on_member_remove(self, member):
        guild = member.guild
        channel = guild.get_channel(LOG_CHANNEL_ID)
        
        if not channel:
            return

        avatar_url = member.avatar.url if member.avatar else member.default_avatar.url
        joined_text = f"<t:{int(member.joined_at.timestamp())}:R>" if member.joined_at else "Ismeretlen"

        # Embed üzenet elkészítése
        embed = discord.Embed(
            title="🚪 Egy tag elhagyta a szervert",
            description=f"Sajnáljuk, hogy **{member.name}** távozott közülünk.",
            color=discord.Color.red()
        )
        
        embed.set_thumbnail(url=avatar_url)
        embed.add_field(name="👤 Felhasználó", value=member.name, inline=False)
        embed.add_field(name="🆔 ID", value=f"`{member.id}`", inline=False)
        embed.add_field(name="📅 Csatlakozott", value=joined_text, inline=False)
        embed.add_field(name="📊 Tagok száma", value=f"**{guild.member_count}**", inline=False)

        embed.set_footer(
            text="A ParentLand csapata Jóváhagyásával",
            icon_url=guild.icon.url if guild.icon else None
        )
        embed.timestamp = discord.utils.utcnow()

        await channel.send(embed=embed)


# Modul regisztrálása a fő botban
async def setup(bot):
    await bot.add_cog(UdvozloCog(bot))