
import discord
from discord.ext import commands
import asyncio

class MessageLimitCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Célcsatorna ID-ja
        self.target_channel_id = 1541789169397927957
        
        # Felhasználók üzenetszámlálója
        self.user_message_counts = {}

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # Ne reagáljon a bot a saját üzeneteire, vagy ha nem guildben (szerveren) van
        if message.author.bot or not message.guild:
            return

        # Csak a megadott csatornát vizsgáljuk
        if message.channel.id == self.target_channel_id:
            user_id = message.author.id
            
            # Adminokat kihagyjuk
            if message.author.guild_permissions.administrator:
                return

            # Lekérdezzük, hány üzenetnél tart eddig
            current_count = self.user_message_counts.get(user_id, 0) + 1
            self.user_message_counts[user_id] = current_count

            # Ha ez volt a 2. üzenete
            if current_count == 2:
                try:
                    # Lekérjük a meglévő engedélyeket a csatornára, vagy csinálunk egy újat
                    overwrite = message.channel.overwrites_for(message.author)
                    
                    # Csak az írást tiltjuk le, a láthatóságot explicit engedélyezzük, hogy ne tűnjön el a szoba
                    overwrite.send_messages = False
                    overwrite.read_messages = True  # Biztosítjuk, hogy látni fogja
                    
                    # Alkalmazzuk a beállítást
                    await message.channel.set_permissions(message.author, overwrite=overwrite)
                except discord.Forbidden:
                    return # Ha a botnak nincs joga kezelni az engedélyeket

                # Privát üzenet küldése a felhasználónak
                try:
                    await message.author.send(
                        f"Szia! Elérted a 2 üzenetes limitet ebben a csatornában (<#{self.target_channel_id}>). "
                        f"A szobát továbbra is **látni fogod**, de az írási jogod **24 órára** le lett tiltva."
                    )
                except discord.Forbidden:
                    # Vészmegoldás, ha le vannak tiltva a DM-ei
                    temp_msg = await message.channel.send(
                        f"{message.author.mention}, elérted a 2 üzenetes limitet. A szobát látod, de 24 óráig nem írhatsz bele!",
                        delete_after=5
                    )

                # Háttérfolyamat indítása (24 óra = 86400 másodperc)
                self.bot.loop.create_task(self.unlock_user_after_delay(message.channel, message.author, 86400))

    async def unlock_user_after_delay(self, channel, member, delay):
        await asyncio.sleep(delay)
        try:
            # Lekérjük a jelenlegi felülírásokat
            overwrite = channel.overwrites_for(member)
            
            # Visszaállítjuk az írási jogot True-ra (vagy töröljük az egészet, ha nem volt más egyedi jog)
            overwrite.send_messages = None
            
            # Ha nincsen más egyedi beállítása ebben a szobában, akár törölhetjük is a felülírást, 
            # de a biztonság kedvéért frissítjük az overwrite-ot:
            if overwrite.is_empty():
                await channel.set_permissions(member, overwrite=None)
            else:
                await channel.set_permissions(member, overwrite=overwrite)
            
            # Nullázzuk a számlálót
            if member.id in self.user_message_counts:
                del self.user_message_counts[member.id]
                
            # Értesítés privát üzenetben
            await member.send(f"Letelt a 24 óra! Újra írhatsz ebben a csatornában: <#{channel.id}>.")
        except Exception:
            pass

async def setup(bot):
    await bot.add_cog(MessageLimitCog(bot))

           