# Piply

Osobní trader hub – deník obchodů, statistiky, a sociální síť pro tebe a tvoje
kamarády tradery. Běží lokálně na tvém počítači (Python + Flask + SQLite).

## Co to umí

- **Účet** – registrace, přihlášení, editace profilu (fotka, bio, počáteční kapitál)
- **Obchodní deník** – ruční zápis obchodů (pár, směr, ceny, SL/TP, P/L, RRR,
  emoce, hodnocení, poznámky, screenshot grafu) + **import z MT4/CSV**
- **Týdenní shrnutí** – přehled obchodů po týdnech + vlastní reflexe a hodnocení
- **Statistiky a grafy** – winrate, profit factor, průměrné RRR, max drawdown,
  kapitálová křivka, rozpad podle páru a podle emoce (Chart.js)
- **Sociální síť** – feed s příspěvky (text/foto, veřejné/přátelé/jen já),
  lajky a komentáře, systém přátel (žádosti, přijetí, odebrání, blokování),
  soukromé zprávy 1:1 (chat), notifikace, nastavení soukromí zpráv

**Vynecháno zatím záměrně** (podle zadání): AI novinky z Forexu/politiky a
ekonomický kalendář z ForexFactory. Dá se doplnit později jako další modul,
struktura appky je na to připravená.

## Spuštění (poprvé)

Potřebuješ jen **Python 3.10+** (Flask se ti nainstaluje přes pip).

```bash
cd piply
python3 -m venv venv
source venv/bin/activate        # na Windows: venv\Scripts\activate
pip install -r requirements.txt
python3 app.py
```

Otevři v prohlížeči **http://127.0.0.1:5000** – databáze `trader_hub.db` se
vytvoří automaticky při prvním spuštění (jsou v ní všechny tabulky, žádný
další krok navíc netřeba).

Příště už stačí `source venv/bin/activate && python3 app.py`.

## Jak se připojí kamarádi

Appka běží na tvém počítači, takže kamarádi se k ní musí umět připojit po síti:

**Stejná Wi-Fi / lokální síť** (nejjednodušší): spusť appku s

```bash
HOST=0.0.0.0 python3 app.py
```

a zjisti svoji lokální IP adresu (`ipconfig` na Windows / `ifconfig` nebo
`ip a` na Mac/Linux, něco jako `192.168.1.23`). Kamarádi pak v prohlížeči
otevřou `http://192.168.1.23:5000` a founou vlastní účet. Tvůj počítač musí
zůstat zapnutý a appka spuštěná, dokud ji chtějí používat.

**Mimo tvoji síť** (kamarádi odjinud): appka by musela běžet na serveru
dostupném z internetu (VPS, Raspberry Pi s port forwardingem apod.) – kód se
vůbec nemění, jen bys ji nespouštěl na svém počítači, ale tam. Až budete chtít
tenhle krok udělat, dej vědět, pomůžu to nasadit.

## Import obchodů z MT4

V MetaTraderu 4: záložka **Historie účtu** → pravé tlačítko → **Uložit jako
sestavu** → otevři v Excelu/Google Sheets → ulož jako **CSV** → nahraj v appce
přes *Deník → Import z MT4/CSV*. Detaily a vzorový formát jsou přímo na té
stránce v appce.

## Bezpečnost / nastavení

- Hesla jsou hashovaná (nikdy se neukládají v čitelné podobě).
- Pro produkční/sdílené nasazení si nastav vlastní `SECRET_KEY`:
  `TRADER_HUB_SECRET=neco-nahodneho-dlouheho python3 app.py`
- Flaskí dev server (co se spustí přes `python3 app.py`) je určený pro
  lokální/domácí použití mezi kamarády – ne pro veřejný internet bez dalšího
  zabezpečení (HTTPS, produkční WSGI server apod.).

## Struktura projektu

```
piply/
  app.py              hlavní Flask aplikace
  db.py                databázová vrstva (SQLite)
  helpers.py            sdílené pomocné funkce (auth, notifikace, uploady…)
  schema.sql             definice tabulek
  routes/               jednotlivé moduly (auth, profile, journal, stats, social, messages, notifications)
  templates/             HTML šablony (Jinja2)
  static/css/style.css   vzhled
  static/js/app.js       lajky/komentáře/chat bez reloadu stránky
  static/img/            loga a favicon
  static/uploads/        nahrané fotky a screenshoty (vytváří se za běhu)
```

## Co by šlo doplnit později

- AI novinky + ekonomický kalendář (ForexFactory/Reuters) – potřebuje
  internetové připojení appky a případně API klíč na AI shrnutí
- E-mailové / mobilní notifikace (teď jsou jen v appce)
- Nasazení na veřejný server, aby appka běžela 24/7 i bez zapnutého tvého počítače
