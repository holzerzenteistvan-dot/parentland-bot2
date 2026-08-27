import asyncio
import json
import os
from discord.ext import tasks, commands
import discord

FJL_NEV = "hirdetesek.json"

ENGEDEDEZETT_RANG_IDK = [
    1529858809106006136,  # Bot parancsok-hoz (ENGEDÉLY)
    1530634556414365826,  # Alapító
    1529131477756018779,  # Tulajdonos
]


def adatok_betoltese():
  if os.path.exists(FJL_NEV):
    try:
      with open(FJL_NEV, "r", encoding="utf-8") as f:
        data = json.load(f)
        # Ha a régi formátumú lista (egyszerű tömb), konvertáljuk az új szerkezetre
        if isinstance(data, list):
          return {
              "hirdetesek": data,
              "aktualis_index": 0,
              "uzenet_id": None,
          }
        return data
    except Exception:
      return {"hirdetesek": [], "aktualis_index": 0, "uzenet_id": None}
  return {"hirdetesek": [], "aktualis_index": 0, "uzenet_id": None}


def adatok_mentese(cog_adat):
  try:
    with open(FJL_NEV, "w", encoding="utf-8") as f:
      json.dump(cog_adat, f, ensure_ascii=False, indent=4)
  except Exception as e:
    print(f"[HIRDETÉS MENTÉSI HIBA]: {e}")


def has_allowed_role():
  async def predicate(interaction: discord.Interaction):
    if interaction.user.guild_permissions.administrator:
      return True

    user_role_ids = [role.id for role in interaction.user.roles]
    if any(rang_id in user_role_ids for rang_id in ENGEDEDEZETT_RANG_IDK):
      return True

    await interaction.response.send_message(
        "❌ Nincs jogod használni ezt a parancsot (szükséges rang hiányzik).",
        ephemeral=True,
    )
    return False

  return discord.app_commands.check(predicate)


class HirdetesModal(discord.ui.Modal, title="Új Hirdetés Létrehozása"):
  szoveg_input = discord.ui.TextInput(
      label="Hirdetés főszövege (Markdown támogatott)",
      style=discord.TextStyle.paragraph,
      placeholder="Írd ide a szöveget...",
      max_length=2000,
      required=True,
  )

  kep_input = discord.ui.TextInput(
      label="Alsó kép linkje (Opcionális)",
      style=discord.TextStyle.short,
      placeholder="https://pelda.hu/kep.png",
      required=False,
  )

  def __init__(self, cog):
    super().__init__()
    self.cog = cog

  async def on_submit(self, interaction: discord.Interaction):
    szoveg = self.szoveg_input.value
    kep_link = self.kep_input.value.strip()

    uj_hirdetes = {"szoveg": szoveg, "kep": kep_link}
    self.cog.adatok["hirdetesek"].append(uj_hirdetes)
    adatok_mentese(self.cog.adatok)

    embed = discord.Embed(
        description=szoveg, color=discord.Color.from_rgb(230, 126, 34)
    )
    if kep_link:
      embed.set_image(url=kep_link)
    self.cog.hirdetesek_embed_lista.append(embed)

    await interaction.response.send_message(
        f"✅ Hirdetés elmentve! Összesen:"
        f" {len(self.cog.adatok['hirdetesek'])} db",
        ephemeral=True,
    )

    if (
        len(self.cog.adatok["hirdetesek"]) == 1
        and not self.cog.hirdetes_forgatas.is_running()
    ):
      self.cog.hirdetes_forgatas.start()
    elif len(self.cog.adatok["hirdetesek"]) == 1:
      await self.cog.azonnali_kikuldes()


class HirdetesTorlesSelect(discord.ui.Select):

  def __init__(self, hirdetesek_lista):
    options = []
    for index, item in enumerate(hirdetesek_lista[:25]):
      szoveg_rovid = (
          item["szoveg"][:47] + "..."
          if len(item["szoveg"]) > 50
          else item["szoveg"]
      )
      options.append(
          discord.SelectOption(
              label=f"#{index + 1}. Hirdetés",
              description=szoveg_rovid,
              value=str(index),
          )
      )

    super().__init__(
        placeholder="Válaszd ki a törölni kívánt hirdetés(eke)t...",
        min_values=1,
        max_values=min(len(options), 25),
        options=options,
    )

  async def callback(self, interaction: discord.Interaction):
    cog = interaction.client.get_cog("HirdetesCog")
    if not cog:
      await interaction.response.send_message(
          "❌ Hiba történt a Cog lekérésekor.", ephemeral=True
      )
      return

    torlendo_indexek = sorted(
        [int(val) for val in self.values], reverse=True
    )

    torolt_db = 0
    for idx in torlendo_indexek:
      if 0 <= idx < len(cog.adatok["hirdetesek"]):
        cog.adatok["hirdetesek"].pop(idx)
        cog.hirdetesek_embed_lista.pop(idx)
        torolt_db += 1

    adatok_mentese(cog.adatok)

    if not cog.adatok["hirdetesek"]:
      cog.hirdetes_forgatas.cancel()
      if cog.cel_uzenet:
        try:
          await cog.cel_uzenet.delete()
        except:
          pass
        cog.cel_uzenet = None
      cog.adatok["aktualis_index"] = 0
      cog.adatok["uzenet_id"] = None
      adatok_mentese(cog.adatok)
      valasz_szoveg = (
          f"🗑️ Sikeresen törölve **{torolt_db}** hirdetés. A lista üres, a"
          " forgatás leállt."
      )
    else:
      if cog.adatok["aktualis_index"] >= len(cog.adatok["hirdetesek"]):
        cog.adatok["aktualis_index"] = 0
      adatok_mentese(cog.adatok)
      valasz_szoveg = f"🗑️ Sikeresen törölve **{torolt_db}** hirdetés."

    await interaction.response.edit_message(
        content=valasz_szoveg, view=None, embed=None
    )


class HirdetesTorlesView(discord.ui.View):

  def __init__(self, hirdetesek_lista):
    super().__init__(timeout=60)
    self.add_item(HirdetesTorlesSelect(hirdetesek_lista))


class HirdetesCog(commands.Cog):

  def __init__(self, bot):
    self.bot = bot
    self.CSATORNA_ID = 1528827113724182658  # A te csatorna ID-d

    self.adatok = adatok_betoltese()
    self.hirdetesek_embed_lista = []

    for item in self.adatok["hirdetesek"]:
      embed = discord.Embed(
          description=item["szoveg"], color=discord.Color.from_rgb(230, 126, 34)
      )
      if item.get("kep"):
        embed.set_image(url=item["kep"])
      self.hirdetesek_embed_lista.append(embed)

    self.cel_uzenet = None

  def cog_unload(self):
    self.hirdetes_forgatas.cancel()

  async def azonnali_kikuldes(self):
    if not self.hirdetesek_embed_lista:
      return
    csatorna = self.bot.get_channel(self.CSATORNA_ID)
    if not csatorna:
      return

    idx = self.adatok.get("aktualis_index", 0)
    if idx >= len(self.hirdetesek_embed_lista):
      idx = 0

    embed = self.hirdetesek_embed_lista[idx]
    try:
      self.cel_uzenet = await csatorna.send(embed=embed)
      self.adatok["uzenet_id"] = self.cel_uzenet.id
      adatok_mentese(self.adatok)
    except Exception as e:
      print(f"[HIRDETÉS HIBA küldéskor]: {e}")

  @discord.app_commands.command(
      name="hirdetes", description="Új hirdetés hozzáadása."
  )
  @has_allowed_role()
  async def hirdetes(self, interaction: discord.Interaction):
    modal = HirdetesModal(self)
    await interaction.response.send_modal(modal)

  @discord.app_commands.command(
      name="hirdetes_torlese", description="Hirdetések törlése menüből."
  )
  @has_allowed_role()
  async def hirdetes_torlese(self, interaction: discord.Interaction):
    if not self.adatok["hirdetesek"]:
      await interaction.response.send_message(
          "❌ Jelenleg nincsenek aktív hirdetések a rendszerben.", ephemeral=True
      )
      return

    view = HirdetesTorlesView(self.adatok["hirdetesek"])
    await interaction.response.send_message(
        "Válaszd ki alább a törölni kívánt hirdetéseket (akár többet is"
        " kijelölhetsz):",
        view=view,
        ephemeral=True,
    )

  @tasks.loop(minutes=1.0)
  async def hirdetes_forgatas(self):
    if not self.hirdetesek_embed_lista:
      return

    csatorna = self.bot.get_channel(self.CSATORNA_ID)
    if not csatorna:
      return

    # Index növelése a következő hirdetésre
    if len(self.hirdetesek_embed_lista) > 1:
      self.adatok["aktualis_index"] = (
          self.adatok["aktualis_index"] + 1
      ) % len(self.hirdetesek_embed_lista)
      adatok_mentese(self.adatok)

    idx = self.adatok["aktualis_index"]
    embed = self.hirdetesek_embed_lista[idx]

    try:
      if self.cel_uzenet is None:
        # Megpróbáljuk lekérni a mentett üzenet ID alapján, ha létezik
        uzenet_id = self.adatok.get("uzenet_id")
        if uzenet_id:
          try:
            self.cel_uzenet = await csatorna.fetch_message(uzenet_id)
          except discord.NotFound:
            self.cel_uzenet = None

      if self.cel_uzenet is None:
        self.cel_uzenet = await csatorna.send(embed=embed)
      else:
        self.cel_uzenet = await self.cel_uzenet.edit(embed=embed)

      self.adatok["uzenet_id"] = self.cel_uzenet.id
      adatok_mentese(self.adatok)
    except Exception as e:
      try:
        self.cel_uzenet = await csatorna.send(embed=embed)
        self.adatok["uzenet_id"] = self.cel_uzenet.id
        adatok_mentese(self.adatok)
      except:
        pass

  @hirdetes_forgatas.before_loop
  async def before_hirdetes_forgatas(self):
    await self.bot.wait_until_ready()
    if self.hirdetesek_embed_lista:
      # Megpróbáljuk megkeresni a korábbi üzenetet induláskor
      uzenet_id = self.adatok.get("uzenet_id")
      if uzenet_id:
        csatorna = self.bot.get_channel(self.CSATORNA_ID)
        if csatorna:
          try:
            self.cel_uzenet = await csatorna.fetch_message(uzenet_id)
          except discord.NotFound:
            self.cel_uzenet = None

      if not self.cel_uzenet:
        await self.azonnali_kikuldes()

      if not self.hirdetes_forgatas.is_running():
        self.hirdetes_forgatas.start()


async def setup(bot):
  await bot.add_cog(HirdetesCog(bot))