import discord
from discord.ext import tasks, commands

class ServerStats(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # --- BEÁLLÍTÁSOK ---
        self.MEMBER_ROLE_ID = 1528502838995718275  # A tagok rang ID-ja
        self.BOT_ROLE_ID = 153131730512904407      # A botok rang ID-ja
        
        self.MEMBER_CHANNEL_ID = 1530627106826879237
        self.BOT_CHANNEL_ID = 1530627191728111817
        # --------------------
        
        self.update_stats.start()

    def cog_unload(self):
        self.update_stats.cancel()

    @tasks.loop(seconds=5)
    async def update_stats(self):
        for guild in self.bot.guilds:
            # Tagok számlálása a rang alapján
            member_role = guild.get_role(self.MEMBER_ROLE_ID)
            member_count = len(member_role.members) if member_role else 0

            # Botok számlálása a rang vagy a Discord saját bot-szűrője alapján
            bot_role = guild.get_role(self.BOT_ROLE_ID)
            bot_count = len(bot_role.members) if bot_role else sum(1 for m in guild.members if m.bot)

            # Tag csatorna frissítése
            member_channel = guild.get_channel(self.MEMBER_CHANNEL_ID)
            if member_channel:
                try:
                    await member_channel.edit(name=f"👤 Tagok: {member_count}")
                except Exception as e:
                    print(f"Hiba a tag csatorna frissítésekor: {e}")

            # Bot csatorna frissítése
            bot_channel = guild.get_channel(self.BOT_CHANNEL_ID)
            if bot_channel:
                try:
                    await bot_channel.edit(name=f"🤖 Botok: {bot_count}")
                except Exception as e:
                    print(f"Hiba a bot csatorna frissítésekor: {e}")

    @update_stats.before_loop
    async def before_update_stats(self):
        await self.bot.wait_until_ready()

async def setup(bot):
    await bot.add_cog(ServerStats(bot))