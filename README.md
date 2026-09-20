# 🌿 TS Skleníky – Evidence a správa zakázek

Komplexní desktopový informační a evidenční systém vyvinutý pro správu zakázek, výrobu, skladové díly, expedici a logistiku skleníků. Aplikace nabízí moderní grafické rozhraní v **PySide6 (Qt for Python)**, duální podporu databází (FoxPro DBF i moderní SQLite), automatické zálohování na Google Drive a integrovanou e-mailovou komunikaci se zákazníky.

---

## ✨ Klíčové funkce

### 📦 1. Správa objednávek a zákazníků
- **Evidence zakázek**: Kompletní životní cyklus objednávky od přijetí, přes výrobu a kompletaci dílů, až po expedici a fakturaci.
- **Parametrické vyhledávání a filtry**: Rychlé vyhledávání podle čísla objednávky, jména zákazníka, adresy, PSČ, typu skleníku nebo termínu dodání.
- **Historie a zpětný archiv**: Snadný přístup k historickým objednávkám s možností nahlížení a dohledání parametrů.
- **Automatické našeptávání adres**: Integrovaný číselník PSČ a měst pro rychlé a bezchybné zadávání doručovacích adres.

### 🏗️ 2. Katalog skleníků, sestav a dílů
- **Sestavy skleníků**: Evidence modelových řad, standardních i atypických rozměrů, výplní a volitelného příslušenství.
- **Skladové a základní díly**: Přehled profilů, spojovacího materiálu, polic, oken a automatických otvíračů s vazbou na konkrétní sestavy.
- **Fulltextové vyhledávání dílů v zakázkách**: Okamžité zjištění, ve kterých rozpracovaných zakázkách je daný komponent použit.

### 🚚 3. Expedice a rozvozní plány
- **Plánování rozvozových tras**: Sdružování zakázek do rozvozních plánů podle regionů, PSČ a termínů.
- **Vlastní odvozy**: Samostatná evidence pro zákazníky, kteří si skleník vyzvedávají osobně ve výrobě.
- **Přehledy nakládky**: Generování soupisů a podkladů pro řidiče a expediční skladníky.

### 📄 4. Tiskové výstupy a dokumenty
- **Automatické generování dokumentů**: Dodací listy, předávací protokoly, štítky na balíky a montážní soupisy.
- **Náhled před tiskem**: Integrovaný dialog s náhledem dokumentů a přímým odesláním na tiskárnu.

### ✉️ 5. Elektronická pošta a šablony zpráv
- **Vestavěný e-mailový klient**: Odesílání potvrzení objednávek, informací o expedici a montážních pokynů přímo z aplikace.
- **Dynamické šablony**: Předdefinované texty zpráv s automatickým doplňováním proměnných (jméno, číslo zakázky, termín rozvozu, částka).
- **Propojení přes SMTP**: Možnost odesílání přes standardní zabezpečený SMTP protokol (včetně SSL/TLS).

### ☁️ 6. Bezpečnost a zálohování dat
- **Lokální zálohování**: Automatické vytváření komprimovaných ZIP archivů při ukončení aplikace s volitelnou rotací (např. uchování posledních 7 dní).
- **Synchronizace na Google Drive**: Bezpečné ukládání záloh do cloudového úložiště prostřednictvím oficiálního Google Drive API (OAuth 2.0).
- **Duální databázová vrstva & migrace**: Plynulý přechod z historických FoxPro databází (`.DBF`, `.CDX`, `.FPT`) do moderního formátu **SQLite3** s vestavěným migračním průvodcem.

### 🎨 7. Moderní uživatelské rozhraní
- **Přepínání motivů vzhledu**: Tmavý režim (Dark), světlý režim (Light) a modrý manažerský styl (Blue theme).
- **Intuitivní klávesové zkratky**: Rychlá obsluha formulářů pomocí kláves `Enter` a akcentovaných tlačítek pro maximální rychlost práce.

---

## 🛠️ Architektura a technologie

- **Jazyk**: [Python](https://www.python.org/) 3.12+
- **GUI Framework**: [PySide6](https://pypi.org/project/PySide6/) (oficiální Qt 6 binding pro Python)
- **Databáze**: 
  - [SQLite3](https://docs.python.org/3/library/sqlite3.html) (moderní datové úložiště)
  - [dbf](https://pypi.org/project/dbf/) (zpětná kompatibilita s formátem dBase / Visual FoxPro)
- **Cloudové API**: [Google API Client](https://github.com/googleapis/google-api-python-client) & [google-auth-oauthlib](https://github.com/googleapis/google-auth-library-python-oauthlib)
- **Distribuce**: [PyInstaller](https://pyinstaller.org/) pro sestavení do samostatného spustitelného `.exe` souboru pro Windows

---

## 📁 Struktura projektu

```text
TS - Copy/
├── app/
│   ├── main.py                     # Vstupní bod aplikace, inicializace UI a témat
│   ├── build.bat                   # Skript pro sestavení samostatného .exe souboru
│   ├── requirements.txt            # Seznam Python závislostí
│   │
│   ├── models/                     # Datové modely (Objednavka, Produkt, Rozvoz, Uzivatel...)
│   ├── services/                   # Aplikační služby (DBF, SQLite, E-mail, Google Drive, Zálohy)
│   │   ├── sqlite_service.py       # Správa SQLite databáze
│   │   ├── dbf_service.py          # Práce s FoxPro DBF tabulkami
│   │   ├── migration_service.py    # Nástroj pro převod DBF -> SQLite
│   │   ├── backup_service.py       # Lokální i cloudové zálohování
│   │   ├── email_service.py        # Odesílání pošty přes SMTP
│   │   └── gdrive_helper.py        # Integrace s Google Drive API
│   │
│   ├── views/                      # Grafické dialogy a komponenty uživatelského rozhraní
│   │   ├── main_window.py          # Hlavní okno aplikace
│   │   ├── seznam_objednavek_dialog.py
│   │   ├── objednavka_dialog.py
│   │   ├── rozvozni_plany_dialog.py
│   │   ├── sklenikove_sestavy_dialog.py
│   │   ├── backup_dialog.py
│   │   └── ...
│   │
│   ├── styles/                     # QSS styly (dark_theme.qss, light_theme.qss, blue_theme.qss)
│   ├── DATA/                       # Složka pro databáze (DBF / ts_data.db - ignorováno gitem)
│   ├── Zaloha/                     # Cílová složka lokálních záloh (ignorováno gitem)
│   │
│   ├── credentials.example.json    # Vzor konfigurace pro Google Drive OAuth
│   ├── smtp_config.example.ini     # Vzor konfigurace pro SMTP odesílání
│   └── backup_config.example.ini   # Vzor nastavení frekvence záloh
│
├── .gitignore                      # Kompletní pravidla ochrany citlivých dat a binárek
└── README.md                       # Dokumentace projektu
```

---

## 🚀 Rychlý start (Instalace a spuštění)

### 1. Prerekvizity
- Nainstalovaný **Python 3.12** nebo novější (doporučeno [python.org](https://www.python.org/downloads/)).
- Git pro správu verzí.

### 2. Klonování repozitáře
```bash
git clone https://github.com/Shiftyczech/TS---Copy.git
cd TS---Copy
```

### 3. Vytvoření virtuálního prostředí
```bash
# Vytvoření virtuálního prostředí
python -m venv .venv

# Aktivace na Windows (PowerShell)
.venv\Scripts\Activate.ps1

# Nebo v klasickém příkazovém řádku (cmd)
.venv\Scripts\activate.bat
```

### 4. Instalace závislostí
```bash
pip install --upgrade pip
pip install -r app/requirements.txt
```

---

## ⚙️ Konfigurace

Před prvním spuštěním si připravte konfigurační soubory podle vzorů ve složce `app/`:

### 1. Nastavení e-mailu (SMTP)
Zkopírujte `app/smtp_config.example.ini` do `app/smtp_config.ini`:
```ini
[smtp]
server = smtp.vasedomena.cz
port = 465
tls = no
user = info@vasedomena.cz
password = vase_bezpecne_heslo
sender_email = info@vasedomena.cz
```

### 2. Nastavení Google Drive API (volitelné pro cloudové zálohy)
1. V [Google Cloud Console](https://console.cloud.google.com/) vytvořte projekt a povolte **Google Drive API**.
2. Vytvořte přihlašovací údaje typu **OAuth 2.0 Client ID (Desktop Application)**.
3. Stáhněte JSON klíč a uložte jej do `app/credentials.json` (podle vzoru `app/credentials.example.json`).
4. Při prvním spuštění zálohy na Disk vás aplikace vyzve k jednorázovému přihlášení v prohlížeči. Vytvořený autorizační token se uloží do `app/token.json`.

### 3. Nastavení zálohování
Zkopírujte `app/backup_config.example.ini` do `app/backup_config.ini`:
```ini
[backup]
auto_backup = yes
keep_count = 7
backup_dir = Zaloha
```

### 4. Příprava databázových souborů
Do složky `app/DATA/` nahrajte buď stávající soubory FoxPro (`.DBF`), nebo nechte aplikaci inicializovat novou SQLite databázi `ts_data.db`.

---

## ▶️ Spuštění aplikace

Spusťte hlavní skript:
```bash
python app/main.py
```

---

## 🔨 Sestavení spustitelného souboru (.exe)

Pokud chcete aplikaci distribuovat koncovým uživatelům bez nutnosti instalace Pythonu:

1. Ujistěte se, že máte ve virtuálním prostředí nainstalovaný PyInstaller:
   ```bash
   pip install pyinstaller
   ```
2. Spusťte přiložený sestavovací skript:
   ```bash
   cd app
   build.bat
   ```
3. Výsledný spustitelný soubor `EvidenceSkleniků.exe` naleznete ve složce `app/dist/`. K němu stačí do stejné složky umístit složku `DATA/` s daty a konfigurační `.ini` soubory.

---

## 🔒 Bezpečnost a ochrana dat

- Repozitář obsahuje striktní `.gitignore`, který brání nechtěnému verzování reálných databázových souborů se zákaznickými údaji (`*.db`, `*.DBF`, `*.FPT`), šifrovacích klíčů, hesel (`smtp_config.ini`), OAuth tokenů (`credentials.json`, `token.json`) a velkých ZIP záloh.
- Pro sdílení repozitáře s dalšími vývojáři vždy používejte výhradně šablonové soubory `*.example`. Nikdy do repozitáře necommitujte produkční hesla!

---

## 📄 Licence

Tento projekt je proprietární software určený pro interní evidenci a správu zakázek. Všechna práva vyhrazena.
