import discord
from discord.ext import commands
import asyncio
import os

# ------------------- JOGOSULTSÁGOK BEÁLLÍTÁSA -------------------
intents = discord.Intents.default()
intents.members = True   # 👈 KÖTELEZŐ az üdvözlő kódhoz (belépés/kilépés)!
intents.invites = True   # 👈 KÖTELEZŐ a meghívók nyomon követéséhez!
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ------------------- BEÁLLÍTÁSOK -------------------
# A szervered ID-ját és a bot tokent KÖRNYEZETI VÁLTOZÓKBÓL olvassuk be
# (Koyeb-en az "Environment variables" alatt kell beállítani őket).
# Soha ne írd be a tokent közvetlenül a kódba!
GUILD_ID = int(os.environ.get("GUILD_ID", "1528502838995718275"))
TOKEN = os.environ.get("DISCORD_TOKEN")

if not TOKEN:
    raise RuntimeError(
        "Hiányzik a DISCORD_TOKEN környezeti változó! Állítsd be Koyeb-en "
        "az Environment variables alatt, mielőtt elindítod a botot."
    )


# ------------------- BOT INDULÁSA -------------------
@bot.event
async def on_ready():
    print(f"✅ Sikeres bejelentkezés! Bot neve: {bot.user}")
    
    # Slash parancsok azonnali szinkronizálása a szerveredre
    try:
        guild = discord.Object(id=GUILD_ID)
        bot.tree.copy_global_to(guild=guild)
        synced = await bot.tree.sync(guild=guild)
        print(f"✅ Sikeresen szinkronizálva {len(synced)} slash parancs a szerverre!")
    except Exception as e:
        print(f"❌ Hiba a parancsok szinkronizálásakor: {e}")

        
#-----------------------------------------------------------------

# ------------------- FŐ BETÖLTŐ FÜGGVÉNY -------------------

async def main():
    async with bot:
        # Betölti az összes .py fájlt a 'cogs' mappából (kivéve az __init__.py-t)
        if os.path.exists("./cogs"):
            for filename in os.listdir("./cogs"):
                if filename.endswith(".py") and not filename.startswith("__"):
                    await bot.load_extension(f"cogs.{filename[:-3]}")
                    print(f"🔌 Betöltve: cogs/{filename}")
        else:
            print("⚠️ A 'cogs' mappa nem található! Hozz létre egy 'cogs' mappát a bot.py mellett.")
        
        # Bot elindítása
        await bot.start(TOKEN)

# Indítás
if __name__ == "__main__":
    asyncio.run(main())