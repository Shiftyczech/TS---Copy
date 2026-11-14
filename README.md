# TS Skleníky – Evidence objednávek a rozvozů

Moderní podnikový informační a expediční systém vyvinutý v **Pythonu (PySide6 / Qt)** pro kompletní správu zakázek, kalkulaci a konfiguraci skleníků, plánování logistiky, tisk průvodek a automatizaci zákaznické komunikace.

Systém byl původně provozován na platformě FoxPro (DBF/FPT) a byl kompletně zmodernizován do vysokorychlostní architektury s podporou lokální **SQLite** databáze a síťového víceuživatelského serveru **MariaDB** (Synology NAS).

---

## 🚀 Klíčové funkce a moduly

### 1. 📦 Příjem a správa objednávek
* **Rychlé zadávání zakázek:** Evidence odběratele, fakturačních a doručovacích údajů, telefonů, e-mailů a způsobu úhrady.
* **Inteligentní našeptávač PSČ a obcí:** Automatické doplňování měst podle PSČ a naopak z vestavěné databáze PSČ ČR.
* **Validace telefonních čísel:** Automatické formátování telefonních a mobilních čísel do standardizovaného tvaru `+420 XXX XXX XXX`.
* **Automatické číslování s recyklací čísel:** Systém automaticky generuje nová čísla objednávek a nabízí možnost obsadit uvolněná čísla po stornovaných zakázkách.
* **Fulltextové vyhledávání a filtrace:** Okamžité vyhledávání podle jména, adresy, PSČ, telefonního čísla, data přijetí nebo čísla objednávky.

### 2. 🏗️ Skleníkové sestavy a kalkulátor dílů
* **Evidence modelových řad:** Podpora všech typů skleníků (Variant, Satelit, Optimal, Central, Maximal atd.).
* **Automatický rozpis na díly:** Každá sestava se automaticky rozpadá na přesné počty profilů, skel, spojovacího materiálu a doplňků.
* **Pravidla záměny dílů:** Inteligentní logika záměn dílů (např. prodloužení, střešní větrací okna, regály, dveře).
* **Přiřazení montážních plánků:** Výběr a zobrazení nákresů a plánků z vestavěné knihovny vzorů.

### 3. 🚚 Plánování rozvozů a logistika
* **Tvorba rozvozních tras:** Plánování rozvozů podle regionů, směrů a termínů závozů.
* **Přiřazování objednávek do tras:** Pohodlný výběr zakázek s hlídáním kapacity vozidla a pořadí vykládky.
* **Správa vlastních odvozů:** Přehledná evidence zákazníků, kteří si odebírají zboží osobně na skladě.
* **Tisk plánů pro řidiče:** Generování expedičních seznamů a plánů jízd pro řidiče rozvozových vozidel.

### 4. 📄 Tisk a generování dokumentů
* **Objednávkové a dodací listy:** Profesionální formátované dokumenty připravené k tisku nebo exportu.
* **Export do PDF s náhledem:** Integrovaný náhledový dialog s možností přímého tisku na výchozí tiskárnu nebo uložení do PDF.
* **Hromadný tisk:** Možnost vytisknout celou dávku dokladů pro vybranou rozvozní trasu jedním klikem.

### 5. ✉️ Elektronická pošta a zákaznická komunikace
* **Automatické notifikace:** Odesílání potvrzení objednávek, avíz o termínu expedice a výzev k odběru zboží.
* **Integrovaný e-mailový klient:** Vlastní SMTP podpora (SSL/TLS, port 465/587) nezávislá na poštovním klientovi Windows.
* **Šablony zpráv:** Nastavitelné předlohy e-mailů a SMS zpráv s proměnnými pro zákazníka.
* **Přehled odeslané pošty:** Historie a stav všech odeslaných zpráv s možností opětovného odeslání.

### 6. 🗄️ Dlouhodobý archiv a úklid dat
* **Dvoutřídní správa dat:** Oddělení aktivních zakázek (`tsd04`) od vyřízených (`tsd06`) pro maximální rychlost programu.
* **Úklid do archivu:** Průvodce přesunem vyřízených a závezených objednávek k vybranému datu do archivu.
* **Zpětný převod z archivu:** Možnost kdykoliv vrátit archivovanou objednávku zpět mezi aktivní zakázky k dořešení či reklamaci.

### 7. 👥 Uživatelé a bezpečnost
* Přihlašování uživatelů heslem.
* Nastavení uživatelských práv a oprávnění k jednotlivým funkcím.

---

## 🌐 Síťový víceuživatelský provoz (Synology NAS)

Program podporuje současnou práci více uživatelů v kanceláři v zapojení **Klient–Server**:

```
┌─────────────────────────┐               ┌─────────────────────────┐
│     Počítač 1 (Win 11)  │               │    Počítač 2 (Win 11)   │
│ Lokální běh z disku C:  │               │ Lokální běh z disku C:  │
│  (start za < 1 sekundu) │               │  (start za < 1 sekundu) │
└────────────┬────────────┘               └────────────┬────────────┘
             │                                         │
             │   TCP/IP (port 3306) – pouze SQL data   │
             └───────────────────┬─────────────────────┘
                                 │
                     ┌───────────▼───────────┐
                     │     Synology NAS      │
                     │  Balíček MariaDB 10   │
                     │ (běží 24/7, bezpečný  │
                     │    souběžný přístup)  │
                     └───────────┬───────────┘
                                 │
                     ┌───────────▼───────────┐
                     │ Synology Hyper Backup │
                     │  (automatická noční   │
                     │   záloha bez záseků)  │
                     └───────────────────────┘
```

* **Okamžitý start:** Program je na obou PC nainstalován lokálně na disku `C:`. Nezatěžuje síť a startuje bleskově bez načítání binárních souborů přes SMB.
* **Centrální data v MariaDB:** Všechna data jsou uložena v MariaDB 10 na Synology NASu (`10.0.0.20:3306`).
* **ACID transakce:** Obě stanice mohou současně vytvářet a upravovat objednávky bez rizika poškození souborů či kolizí zámků.
* **Automatický fallback:** V případě výpadku sítě nebo nedostupnosti Synology aplikace automaticky naběhne v nouzovém režimu s lokální databází.

---

## 💾 Zálohování a ochrana dat

1. **Automatické zálohy na Synology:** Úloha v *Hyper Backup* každou noc automaticky verzovaně zálohuje databázi MariaDB 10 bez nutnosti zásahu uživatele a bez přerušení provozu.
2. **Ruční zálohy v aplikaci:** Přímo v menu *Servisní akce -> Záloha a obnovení* lze vytvořit kompletní ZIP zálohu na disk nebo odeslat na **Google Drive**.
3. **Před-migrační zálohy:** Při jakémkoliv převodu či úklidu dat program automaticky vytvoří bezpečnostní archiv.

---

## 🔄 Vzdálené automatické aktualizace (GitHub Releases)

Aplikace obsahuje vestavěný auto-updater propojený s tímto GitHub repozitářem:

1. **Vydání nové verze z domova:**
   - V souboru `app/version.py` se zvýší číslo verze (např. na `1.0.1`).
   - Přes `build.bat` se vygeneruje nový `EvidenceSkleniků.exe`.
   - Na GitHubu se v sekci *Releases* vytvoří nové vydání s příslušným tagem a přiloženým `.exe`.
2. **Automatická detekce v kanceláři:**
   - Po spuštění programu na klientském PC proběhne tichá kontrola nejnovější verze.
   - Při nalezení nové verze se zobrazí dotaz:
     > *K dispozici je nová verze aplikace (vX.X.X). Přejete si aplikaci nyní aktualizovat a restartovat?*
   - Po potvrzení se nový soubor stáhne a běžící aplikace se atomicky nahradí a restartuje.

---

## 🛠️ Instalace a spuštění pro vývojáře

### Požadavky
* Python 3.10 – 3.13
* Virtuální prostředí (venv)

### Instalace závislostí
```bash
pip install -r app/requirements.txt
```

### Spuštění aplikace ze zdrojových kódů
```bash
python app/main.py
```

### Sestavení spustitelného souboru (.exe) pro Windows
V kořenové složce nebo ve složce `app/` spusťte:
```cmd
app\build.bat
```
Výsledný soubor `EvidenceSkleniků.exe` se vytvoří ve složce `app/dist/`.

---

## 📁 Struktura projektu

```text
├── app/
│   ├── main.py                  # Hlavní vstupní bod aplikace a AppContext
│   ├── version.py               # Číslo verze aplikace a konfigurace pro updater
│   ├── build.bat                # Skript pro sestavení PyInstaller .exe
│   ├── requirements.txt         # Seznam Python knihoven
│   ├── EvidenceSkleniku.spec    # PyInstaller specifikace pro sestavení
│   ├── models/                  # Datové modely (objednávka, rozvoz, produkty...)
│   ├── services/
│   │   ├── mariadb_service.py   # Síťová databázová služba MariaDB (Synology)
│   │   ├── sqlite_service.py    # Lokální vysokorychlostní SQLite služba
│   │   ├── dbf_service.py       # Původní FoxPro DBF kompatibilní služba
│   │   ├── migration_mariadb_service.py # Hromadný migrační převodník SQLite -> MariaDB
│   │   ├── github_updater.py    # Automatické stahování a instalace aktualizací
│   │   ├── backup_service.py    # Zálohování do ZIP a SQL dump
│   │   ├── email_service.py     # Odesílání e-mailů přes SMTP
│   │   └── document_generator.py# Generování tiskových podkladů a dokladů
│   ├── views/                   # Uživatelské rozhraní Qt (dialogy a okna)
│   │   ├── main_window.py       # Hlavní panel aplikace
│   │   ├── objednavka_dialog.py # Dialog tvorby a editace objednávky
│   │   ├── migrace_mariadb_dialog.py # Konfigurace a převod do MariaDB
│   │   ├── update_dialog.py     # Dialog průběhu aktualizace z GitHubu
│   │   └── ...                  # Ostatní specializované dialogy
│   ├── styles/                  # Témata vzhledu (tmavé, světlé, modré QSS)
│   ├── VZORKY/                  # Vzory nákresů a plánků skleníků
│   └── DATA/                    # Lokální datové úložiště (ts_data.db, DBF)
└── README.md                    # Dokumentace projektu
```

---

*Vyvinuto pro společnost TS Skleníky.*
