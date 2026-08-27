# Discord bot – Koyeb hosztolási útmutató

## ⚠️ FONTOS – ELSŐ LÉPÉS, MIELŐTT BÁRMI MÁST CSINÁLSZ

A feltöltött `bot.py` fájlban egy **valódi, élő Discord bot token** volt
beégetve a kódba. Mivel ez a fájl most már át lett adva (és könnyen tovább
kerülhetett/kerülhet máshova, pl. GitHubra), **tekintsd ezt a tokent
kiszivárgottnak**. Bárki, aki hozzáfér, teljesen átveheti az irányítást a
botod felett.

Ezt tedd **most azonnal**:
1. Menj a [Discord Developer Portalba](https://discord.com/developers/applications).
2. Válaszd ki a botod alkalmazását → **Bot** fül.
3. Kattints a **Reset Token** (token újragenerálása) gombra. Ez azonnal
   érvényteleníti a régi, kiszivárgott tokent.
4. Az új tokent **ne írd bele sehova a kódba** – ezt fogod majd Koyeb-en
   környezeti változóként megadni (lásd lentebb).

A kódot már átalakítottam úgy, hogy a tokent egy `DISCORD_TOKEN` nevű
környezeti változóból olvassa be, nincs többé a fájlban.

## Mit változtattam a projekten

- `bot.py`: a token és a `GUILD_ID` most a `DISCORD_TOKEN` és `GUILD_ID`
  környezeti változókból jön, nincs többé hardcode-olva.
- `cogs/MessageLimitCog.py`: a fájlnévben volt egy láthatatlan Unicode
  karakter, ezt eltávolítottam, hogy biztosan mindenhol probléma nélkül
  betöltődjön.
- Töröltem a `__pycache__` mappákat (nem kellenek a repóba).
- Hozzáadtam egy `requirements.txt`-et (`discord.py`) és egy `.gitignore`-t.

## 1. Töltsd fel GitHub-ra

Koyeb legegyszerűbben egy GitHub repóból deployol:

```bash
cd bot-projekt-mappa
git init
git add .
git commit -m "Discord bot Koyeb-hez"
git branch -M main
git remote add origin https://github.com/FELHASZNALONEV/REPO-NEV.git
git push -u origin main
```

(Ha nem akarod nyilvánossá tenni, csinálj **private** repót – ez ingyenes
GitHubon, és Koyeb ingyen tud privát repóból is deployolni, ha
összekötöd a GitHub fiókodat.)

## 2. Szolgáltatás létrehozása Koyeb-en

1. Jelentkezz be a [Koyeb Control Panelbe](https://app.koyeb.com).
2. Kattints **Create Service** (vagy **Create Web Service**), majd válaszd
   a **GitHub**-ot forrásként, és válaszd ki a repódat.
3. **Service type**: válaszd a **Worker** típust. Ez azért fontos, mert a
   Discord bot nem szolgál ki HTTP kéréseket, nincs szüksége publikus
   portra – a "Web Service" típusnál a health check emiatt hibázna.
4. **Builder**: hagyd Buildpack-en (automatikusan felismeri, hogy Python
   projekt a `requirements.txt` alapján).
5. **Run command** (Override): add meg explicit módon:
   ```
   python bot.py
   ```
6. **Environment variables** (nagyon fontos, itt add meg a titkos
   adatokat):
   - `DISCORD_TOKEN` = az újragenerált bot tokened (lásd fentebb) –
     állítsd **Secret**-nek, ha van ilyen opció
   - `GUILD_ID` = a szervered ID-ja (ha nem adod meg, a kódban lévő
     alapértelmezett ID-t fogja használni)
7. Adj nevet az App/Service-nek, majd kattints **Deploy**.

## 3. Ellenőrzés

A Koyeb "Logs" (Runtime logs) fülén látnod kell:

```
✅ Sikeres bejelentkezés! Bot neve: ...
🔌 Betöltve: cogs/...
✅ Sikeresen szinkronizálva N slash parancs a szerverre!
```

Ha `❌` hibát látsz a token miatt, ellenőrizd, hogy a `DISCORD_TOKEN`
környezeti változó pontosan az új, érvényes tokent tartalmazza-e.

## Fontos figyelmeztetés az adattárolásról

A `LevelingSystem.py` és a `HirdetesCog.py` helyi JSON fájlokba írja az
adatokat (pl. szintek, hirdetések). Koyeb-en az alapértelmezett
fájlrendszer **nem tartós** (ephemeral) — ha újradeployolod a szolgáltatást
vagy az instance újraindul, ezek az adatok elveszhetnek. Ha ez fontos
adat, érdemes külső adatbázisra (pl. Koyeb-en elérhető managed Postgres,
vagy bármilyen külső DB) átállítani hosszabb távon.
