import discord
from discord.ext import commands, tasks

class AdManager(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        
        # A frissítendő üzenetek ID-jai listaként megadva
        self.target_message_ids = [1535587563559985153, 1535599067600789536]
        
        # A képek listája, amelyeket sorban váltogatni fog 1 percenként
        self.images_list = [
            "https://cdn.discordapp.com/attachments/1528783198677504051/1535356724981010432/csecs.png?ex=6a7eb820&is=6a7d66a0&hm=35b99a9aeffb90b054fcd189edb35459f2354c7ec95cd0d528a69357449bffd3&",
            "https://cdn.discordapp.com/attachments/1528783198677504051/1536793099710242946/bbb.png?ex=6a7eabdb&is=6a7d5a5b&hm=bdb50e68ea915a91061d9cd1b6c21fb257c9ed309d27d3f631985317874ed124&"
        ]
        
        # Nyomon követi, hogy éppen melyik képnél tartunk
        self.current_image_index = 0
        
        # Időzítő elindítása (1 perc)
        self.auto_update_ad.start()

    def cog_unload(self):
        self.auto_update_ad.cancel()

    @commands.command(name="kep_valt", help="Manuálisan lépteti a hirdetés képét a következőre.")
    @commands.has_permissions(administrator=True)
    async def manual_update(self, ctx):
        await ctx.message.delete()
        await self.rotate_image()
        await ctx.send("A képek sikeresen átváltva a következőre!", delete_after=3)

    async def rotate_image(self):
        """Megkeresi az üzeneteket a bot összes elérhető csatornájában, majd cseréli a képeket."""
        
        # Végigmegyünk mindkét megadott üzenet ID-n
        for msg_id in self.target_message_ids:
            message = None
            
            # Végigmegyünk a bot összes szerverén és azok szöveges csatornáin
            for guild in self.bot.guilds:
                for channel in guild.text_channels:
                    try:
                        message = await channel.fetch_message(msg_id)
                        if message:
                            break
                    except discord.NotFound:
                        continue
                    except discord.Forbidden:
                        continue
                if message:
                    break

            try:
                if message and message.embeds:
                    embed = message.embeds[0]
                    
                    # Kiválasztja az aktuális képet a listából
                    next_image_url = self.images_list[self.current_image_index]
                    
                    # Beállítja az új képet az embedben
                    embed.set_image(url=next_image_url)
                    
                    # Frissíti az üzenetet
                    await message.edit(embed=embed)
                    print(f"Kép sikeresen frissítve ennél: {msg_id} -> {next_image_url}")
                else:
                    print(f"Az üzenet ({msg_id}) nem található egyik csatornában sem, vagy nem tartalmaz embedet!")

            except Exception as e:
                print(f"Hiba történt a kép cseréje közben ({msg_id}): {e}")

        # Lép egyet a következő képre a listában az összes üzenet frissítése után
        self.current_image_index = (self.current_image_index + 1) % len(self.images_list)

    @tasks.loop(minutes=1.0)
    async def auto_update_ad(self):
        await self.rotate_image()

    @auto_update_ad.before_loop
    async def before_auto_update(self):
        await self.bot.wait_until_ready()

async def setup(bot):
    await bot.add_cog(AdManager(bot))