"""
Document generator – merges VZR HTML templates with order data.
TSH00.VZR is the main template (header, supplier, customer, items table).
TSH01.VZR / TSH02.VZR are appended for order text + closing tags.
TSH03A.VZR / TSH03B.VZR are appended for delivery notice text.
Placeholders use «Name» format (cp1250 encoded).
"""
import os
import datetime
import html as html_lib
import re
from app.utils import format_phone_number, get_effective_address

ZP_UHR_MAP = {1: "hotově", 2: "převodem", 3: "QR kódem"}


class DocumentGenerator:
    def __init__(self, ctx):
        self.ctx = ctx
        v_dir = os.path.join(ctx.app_dir, "VZORKY")
        if not os.path.isdir(v_dir):
            app_v_dir = os.path.join(ctx.app_dir, "app", "VZORKY")
            if os.path.isdir(app_v_dir):
                v_dir = app_v_dir
        self.vzorky_dir = v_dir

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate_order(self, cislo_obj, table="tsd04", items_table=None, short_format=False, force_creation_text=False):
        """Generate order confirmation HTML."""
        print(f"[DEBUG_GEN] generate_order called. cislo_obj={cislo_obj}, table={table}, items_table={items_table}")
        if not items_table:
            items_table = f"{table}a"
        order = self._get_order(cislo_obj, table)
        print(f"[DEBUG_GEN] Order loaded: {bool(order)}, CENA_CELK={order.get('CENA_CELK')}, PLAN={repr(order.get('PLAN'))}")
        cfg = self.ctx.db.get_first_record("tsd00") or {}

        zmena = order.get("ZMENA") and order.get("DATUM_ZM") is not None
        if force_creation_text:
            zmena = False
            
        vl_odvoz = order.get("VL_ODVOZ", False)

        # Assemble: TSH00 (main) + TSH01/TSH02 (text + closing)
        header = self._load_template("TSH00.VZR")
        
        if short_format:
            body = "</TABLE>\n</TD></TR>\n«Nakresy»\n</TABLE>\n</FONT>\n</BODY>\n</HTML>\n"
        else:
            body_file = "TSH02.VZR" if zmena else "TSH01.VZR"
            try:
                body = self._load_template(body_file)
            except FileNotFoundError:
                body = self._load_template("TSH01.VZR")
        
        html = header + body

        # Determine text template type
        if zmena:
            typ = "ZV" if vl_odvoz else "ZR"
        else:
            typ = "OV" if vl_odvoz else "OR"

        text_rec = self._get_text_template(typ)

        # Build dynamic blocks
        items = self.ctx.db.read_where(items_table, {"CISLO_OBJ": cislo_obj})
        detail_table = items_table[:-1] + "b"
        vyrobky_html = self._build_vyrobky(items, order, detail_table)
        pozn_zak_html = self._build_pozn_zak(order)
        misto_urc_html = self._build_misto_urc(order)
        text_pole1 = str(text_rec.get("TEXT_POLE1", "")) if text_rec else ""
        text_mail = str(text_rec.get("TEXT_MAIL", "")) if text_rec else ""
        
        if not text_mail:
            sender_name = self._s(cfg, "ODESILATEL")
            if zmena:
                text_mail = (
                    f"Vážený zákazníku,\n\n"
                    f"v systému byla zaznamenána změna v údajích Vaší objednávky č. {cislo_obj}.\n"
                    f"Aktuální stav naleznete v přiloženém dokumentu.\n\n"
                    f"Děkujeme,\n"
                    f"{sender_name}"
                )
            else:
                cena = order.get("CENA_CELK", 0) or 0
                text_mail = (
                    f"Vážený zákazníku,\n\n"
                    f"potvrzujeme přijetí Vaší objednávky č. {cislo_obj}.\n"
                    f"Celková cena: {cena} Kč\n\n"
                    f"Děkujeme za Vaši objednávku.\n"
                    f"{sender_name}"
                )
                
        text_mail = self.replace_text_placeholders(text_mail, cislo_obj, table)
        text_pole1 = self.replace_text_placeholders(text_pole1, cislo_obj, table)

        # Normalize newlines: remove excessive empty lines to save space
        text_pole1 = re.sub(r'(\r?\n){3,}', '\n\n', text_pole1)
        # Escape HTML before replacing newlines
        text_pole1 = html_lib.escape(text_pole1).replace("\r\n", "\n").replace("\n", "<BR>\n")

        try:
            cislo_fmt = str(int(cislo_obj)).zfill(6)
        except (ValueError, TypeError):
            cislo_fmt = str(cislo_obj).strip().zfill(6)

        eff_addr = get_effective_address(order)
        replacements = {
            "«Cislo_Obj»": cislo_fmt,
            "«Číslo objednávky»": cislo_fmt,
            "«Datum výzvy»": self._fmt_date(order.get("DATUM_NA")),
            # Supplier (Dodavatel)
            "«D_Nazev1»": self._s(cfg, "NAZEV1"),
            "«D_Nazev2»": self._s(cfg, "NAZEV2"),
            "«D_Ulice»": self._s(cfg, "ULICE"),
            "«D_PSC»": self._s(cfg, "PSC"),
            "«D_Obec»": self._s(cfg, "OBEC"),
            "«D_Telefon»": self._s(cfg, "TELEFON"),
            "«Dodat_po»": self._fmt_date(order.get("DATUM_PO")),
            "«D_ICO»": self._s(cfg, "ICO"),
            # Customer (Objednatel - preferred delivery address with fallback to billing)
            "«O_Jmeno»": html_lib.escape(eff_addr["jmeno"]),
            "«O_Ulice»": html_lib.escape(eff_addr["ulice"]),
            "«O_PSC»": html_lib.escape(eff_addr["psc"]),
            "«O_Posta»": html_lib.escape(eff_addr["posta"]),
            "«O_Telefon»": format_phone_number(str(order.get("MOBIL", "") or order.get("TELEFON", ""))),
            # Dates & terms
            "«Dat_Prij»": self._fmt_date(order.get("DATUM_PR")),
            "«Dod_Lhuta»": self._s(order, "DOD_LHUTA"),
            "«Zp_Uhr»": ZP_UHR_MAP.get(int(order.get("ZP_UHR", 1) or 1), ""),
            # Dynamic blocks
            "«Misto_Urc»": misto_urc_html,
            "«Vyrobky»": vyrobky_html,
            "«Pozn_Zak»": pozn_zak_html,
            "«Text_Pole1»": text_pole1,
            "«Nakresy»": "",
        }

        for placeholder, value in replacements.items():
            k = placeholder.strip("«»")
            pattern = re.compile(rf"(«|<<)\s*{k}\s*(»|>>)", re.IGNORECASE)
            html = pattern.sub(str(value), html)

        # Fix missing semicolons in non-breaking spaces from old templates
        html = html.replace("&nbsp;", "&nbsp").replace("&nbsp", "&nbsp;")
        
        # Globally replace Jiří with Daniel as requested
        html = html.replace("Jiří Tobiáš", "Daniel Tobiáš")
        html = html.replace("Jiří", "Daniel")
        html = html.replace("JIŘÍ TOBIÁŠ", "DANIEL TOBIÁŠ")
        html = html.replace("JIŘÍ", "DANIEL")
        
        return html

    def generate_delivery_notice(self, cislo_obj, table="tsd04", items_table=None):
        """Generate delivery expedition notice (výzva k expedici)."""
        if not items_table:
            items_table = f"{table}a"
        order = self._get_order(cislo_obj, table)
        cfg = self.ctx.db.get_first_record("tsd00") or {}

        vl_odvoz = order.get("VL_ODVOZ", False)
        typ = "VV" if vl_odvoz else "VR"
        text_rec = self._get_text_template(typ)

        header = self._load_template("TSH00.VZR")
        body_file = "TSH03B.VZR" if vl_odvoz else "TSH03A.VZR"
        try:
            body = self._load_template(body_file)
        except FileNotFoundError:
            body = self._load_template("TSH03A.VZR")
        html = header + body

        items = self.ctx.db.read_where(items_table, {"CISLO_OBJ": cislo_obj})
        detail_table = items_table[:-1] + "b"
        vyrobky_html = self._build_vyrobky(items, order, detail_table)
        pozn_zak_html = self._build_pozn_zak(order)
        misto_urc_html = self._build_misto_urc(order)

        text_pole1 = str(text_rec.get("TEXT_POLE1", "")) if text_rec else ""
        text_pole2 = str(text_rec.get("TEXT_POLE2", "")) if text_rec else ""
        text_pole1 = re.sub(r'(\r?\n){3,}', '\n\n', text_pole1)
        text_pole2 = re.sub(r'(\r?\n){3,}', '\n\n', text_pole2)
        text_pole1 = html_lib.escape(text_pole1).replace("\r\n", "\n").replace("\n", "<BR>\n")
        text_pole2 = html_lib.escape(text_pole2).replace("\r\n", "\n").replace("\n", "<BR>\n")

        # Get route info
        trasa_cislo = str(order.get("TRASA", "")).strip()
        route = None
        if trasa_cislo:
            route = self.ctx.db.read_by_key("tsd05", "CISLO", trasa_cislo)

        # Build delivery date text
        dat_na = self._fmt_date(route.get("DATUM")) if route else self._fmt_date(order.get("DATUM_NA"))
        if dat_na:
            vyzva_text = f"Termín vyzvednutí: {dat_na}" if vl_odvoz else f"Termín dovozu: {dat_na}"
        else:
            vyzva_text = ""

        try:
            cislo_fmt = str(int(cislo_obj)).zfill(6)
        except (ValueError, TypeError):
            cislo_fmt = str(cislo_obj).strip().zfill(6)

        eff_addr = get_effective_address(order)
        replacements = {
            "«Cislo_Obj»": cislo_fmt,
            "«Číslo objednávky»": cislo_fmt,
            "«Datum výzvy»": self._fmt_date(route.get("DATUM")) if route else self._fmt_date(order.get("DATUM_NA")),
            "«D_Nazev1»": self._s(cfg, "NAZEV1"),
            "«D_Nazev2»": self._s(cfg, "NAZEV2"),
            "«D_Ulice»": self._s(cfg, "ULICE"),
            "«D_PSC»": self._s(cfg, "PSC"),
            "«D_Obec»": self._s(cfg, "OBEC"),
            "«D_Telefon»": self._s(cfg, "TELEFON"),
            "«Dodat_po»": self._fmt_date(order.get("DATUM_PO")),
            "«D_ICO»": self._s(cfg, "ICO"),
            "«O_Jmeno»": html_lib.escape(eff_addr["jmeno"]),
            "«O_Ulice»": html_lib.escape(eff_addr["ulice"]),
            "«O_PSC»": html_lib.escape(eff_addr["psc"]),
            "«O_Posta»": html_lib.escape(eff_addr["posta"]),
            "«Dat_Prij»": self._fmt_date(order.get("DATUM_PR")),
            "«Dod_Lhuta»": self._s(order, "DOD_LHUTA"),
            "«Zp_Uhr»": ZP_UHR_MAP.get(int(order.get("ZP_UHR", 1) or 1), ""),
            "«Misto_Urc»": misto_urc_html,
            "«Vyrobky»": vyrobky_html,
            "«Pozn_Zak»": pozn_zak_html,
            "«Text_Pole1»": text_pole1,
            "«Text_Pole2»": text_pole2,
            "«Vyzva_NaT»": vyzva_text,
            "«Datum_Trasy»": self._fmt_date(route.get("DATUM")) if route else "",
            "«Smer_Trasy»": self._s(route, "SMER") if route else "",
            "«Nakresy»": "",
        }

        for placeholder, value in replacements.items():
            k = placeholder.strip("«»")
            pattern = re.compile(rf"(«|<<)\s*{k}\s*(»|>>)", re.IGNORECASE)
            html = pattern.sub(str(value), html)

        # Fix missing semicolons in non-breaking spaces from old templates
        html = html.replace("&nbsp;", "&nbsp").replace("&nbsp", "&nbsp;")
        
        # Globally replace Jiří with Daniel as requested
        html = html.replace("Jiří Tobiáš", "Daniel Tobiáš")
        html = html.replace("Jiří", "Daniel")
        html = html.replace("JIŘÍ TOBIÁŠ", "DANIEL TOBIÁŠ")
        html = html.replace("JIŘÍ", "DANIEL")
        
        return html
    def replace_text_placeholders(self, text, cislo_obj, table="tsd04"):
        """Replace placeholders like «Cislo_Obj» or <<Cislo_Obj>> in text."""
        if not text:
            return text
        order = self._get_order(cislo_obj, table)
        cfg = self.ctx.db.get_first_record("tsd00") or {}
        
        try:
            cislo_fmt = str(int(cislo_obj)).zfill(6)
        except (ValueError, TypeError):
            cislo_fmt = str(cislo_obj).strip().zfill(6)
            
        cena = self._fmt_num(int(float(order.get("CENA_CELK", 0) or 0)))
        
        trasa_cislo = str(order.get("TRASA", "")).strip()
        route = None
        if trasa_cislo:
            route = self.ctx.db.read_by_key("tsd05", "CISLO", trasa_cislo)
        
        eff_addr = get_effective_address(order)
        reps = {
            "Cislo_Obj": cislo_fmt,
            "Číslo objednávky": cislo_fmt,
            "Datum výzvy": self._fmt_date(route.get("DATUM")) if route else self._fmt_date(order.get("DATUM_NA")),
            "Cena": f"{cena} Kč",
            "D_Nazev1": self._s(cfg, "NAZEV1"),
            "D_Telefon": self._s(cfg, "TELEFON"),
            "O_Jmeno": eff_addr["jmeno"],
            "O_Ulice": eff_addr["ulice"],
            "O_PSC": eff_addr["psc"],
            "O_Posta": eff_addr["posta"],
            "Dat_Prij": self._fmt_date(order.get("DATUM_PR")),
            "Dod_Lhuta": self._s(order, "DOD_LHUTA"),
            "Zp_Uhr": ZP_UHR_MAP.get(int(order.get("ZP_UHR", 1) or 1), ""),
            "Datum_Trasy": self._fmt_date(route.get("DATUM")) if route else "",
            "Smer_Trasy": self._s(route, "SMER") if route else "",
        }
        
        for k, v in reps.items():
            pattern = re.compile(rf"(«|<<)\s*{k}\s*(»|>>)", re.IGNORECASE)
            text = pattern.sub(str(v), text)
            
        # Globally replace Jiří with Daniel as requested
        text = text.replace("Jiří Tobiáš", "Daniel Tobiáš")
        text = text.replace("Jiří", "Daniel")
        text = text.replace("JIŘÍ TOBIÁŠ", "DANIEL TOBIÁŠ")
        text = text.replace("JIŘÍ", "DANIEL")
            
        return text

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _get_order(self, cislo_obj, table="tsd04"):
        order = self.ctx.db.read_by_key(table, "CISLO_OBJ", cislo_obj)
        if not order:
            raise ValueError(f"Objednávka {cislo_obj} nenalezena.")
        if isinstance(order, list):
            order = order[0]
        return order

    def _get_text_template(self, typ):
        """Get text template record from tsd07 by TYP code (OR/OV/ZR/ZV/VR/VV)."""
        recs = self.ctx.db.read_where("tsd07", {"TYP": typ})
        if recs:
            return recs[0] if isinstance(recs, list) else recs
        return None

    def _load_template(self, filename):
        safe_filename = os.path.basename(filename)
        path = os.path.join(self.vzorky_dir, safe_filename)
        if not os.path.isfile(path):
            raise FileNotFoundError(f"Šablona {safe_filename} nebyla nalezena ve složce {self.vzorky_dir}.")
        with open(path, "r", encoding="cp1250", errors="replace") as f:
            content = f.read()
            
        # Dynamické nahrazení řádku FAX na Dodat po (pro staré šablony)
        content = content.replace("Fax:&nbsp;«D_Fax»", "Dodat po:&nbsp;«Dodat_po»")
        content = content.replace("Fax:&nbsp«D_Fax»", "Dodat po:&nbsp«Dodat_po»")
        content = content.replace("Fax: «D_Fax»", "Dodat po: «Dodat_po»")
        content = content.replace("Fax:&nbsp;D_Fax", "Dodat po:&nbsp;Dodat_po")
        content = content.replace("Fax:&nbspD_Fax", "Dodat po:&nbspDodat_po")
        
        return content

    def _build_vyrobky(self, items, order, detail_table="tsd04b"):
        """Build product rows HTML for «Vyrobky» placeholder."""
        rows = []
        printed_details = set()
        
        cislo_obj = order.get("CISLO_OBJ", 0)
        try:
            all_details = self.ctx.db.read_where(detail_table, {"CISLO_OBJ": cislo_obj})
            if isinstance(all_details, dict):
                all_details = [all_details]
        except Exception:
            all_details = []
            
        print(f"[DEBUG_GEN] all_details loaded for {cislo_obj}: {len(all_details)}")
        for i, d in enumerate(all_details):
            print(f"  DB detail {i}: KOD={d.get('KOD')}, NAZEV={repr(d.get('NAZEV'))}, CENA={d.get('CENA')}, FINAL={d.get('FINAL')}")

        def safe_int(val, default=0):
            try:
                if val is None:
                    return default
                v = str(val).strip()
                return int(float(v)) if v else default
            except (ValueError, TypeError):
                return default

        for it in items:
            nazev = self._s(it, "NAZEV")
            cena = int(float(it.get("CENA", 0) or 0))
            mnoz = int(float(it.get("MNOZSTVI", 1) or 1))
            celk = cena * mnoz
            dopravne = int(float(it.get("DOPRAVNE", 0) or 0))

            # Main product row (underlined)
            rows.append(
                f'<TR><TD HEIGHT=20><FONT SIZE=2><U>{nazev}</FONT></U></TD>'
                f'<TD ALIGN="RIGHT"><FONT SIZE=2>{self._fmt_num(cena)}</FONT></TD>'
                f'<TD ALIGN="RIGHT"><FONT SIZE=2>{mnoz}</FONT></TD>'
                f'<TD ALIGN="RIGHT"><FONT SIZE=2>{self._fmt_num(celk)}</FONT></TD></TR>'
            )

            # Shipping row for this product
            if dopravne > 0:
                rows.append(
                    f'<TR><TD ALIGN="LEFT" HEIGHT=20><FONT SIZE=2>'
                    f'&nbsp;&nbsp;&nbsp;&nbsp;dopravné</FONT></TD>'
                    f'<TD ALIGN="RIGHT"><FONT SIZE=2>{self._fmt_num(dopravne)}</FONT></TD>'
                    f'<TD ALIGN="RIGHT"><FONT SIZE=2>{mnoz}</FONT></TD>'
                    f'<TD ALIGN="RIGHT"><FONT SIZE=2>{self._fmt_num(dopravne * mnoz)}</FONT></TD></TR>'
                )

            # Linked accessories from detail table (tsd06b/tsd04b)
            kod = int(it.get("KOD", 0) or 0)
            
            try:
                assembly_parts = self.ctx.db.read_where("tsd02a", {"FINAL": kod})
                glass_kods = {int(float(p.get("KOD", 0) or 0)) for p in assembly_parts}
            except Exception:
                glass_kods = set()
            
            def get_final_int(d):
                try:
                    val = d.get("FINAL")
                    if val is None:
                        return 0
                    v = str(val).strip()
                    if not v:
                        return 0
                    return int(float(v))
                except (ValueError, TypeError):
                    return 0
                    
            details = [d for d in all_details if get_final_int(d) == kod]
            for d in details:
                printed_details.add(id(d))
                d_kod = int(float(d.get("KOD", 0) or 0))
                is_glass = d_kod in glass_kods
                
                d_nazev = self._s(d, "NAZEV")
                d_cena = safe_int(d.get("CENA", 0), 0)
                d_mnoz = safe_int(d.get("MNOZSTVI", 1), 1)
                d_celk = d_cena * d_mnoz
                if is_glass or d_celk == 0:
                    continue
                rows.append(
                    f'<TR><TD ALIGN="LEFT" HEIGHT=20><FONT SIZE=2>'
                    f'&nbsp;&nbsp;&nbsp;&nbsp;{d_nazev}</FONT></TD>'
                    f'<TD ALIGN="RIGHT"><FONT SIZE=2>{self._fmt_num(d_cena)}</FONT></TD>'
                    f'<TD ALIGN="RIGHT"><FONT SIZE=2>{d_mnoz}</FONT></TD>'
                    f'<TD ALIGN="RIGHT"><FONT SIZE=2>{self._fmt_num(d_celk)}</FONT></TD></TR>'
                )

        print(f"[DEBUG_GEN] Printing unlinked accessories...")
        # Unlinked accessories from detail table
        for d in all_details:
            if id(d) not in printed_details:
                d_nazev = self._s(d, "NAZEV")
                d_cena = safe_int(d.get("CENA", 0), 0)
                d_mnoz = safe_int(d.get("MNOZSTVI", 1), 1)
                d_celk = d_cena * d_mnoz
                print(f"  Unlinked: {d_nazev}, cena={d_cena}, mnoz={d_mnoz}, celk={d_celk}")
                if d_celk == 0:
                    continue
                rows.append(
                    f'<TR><TD ALIGN="LEFT" HEIGHT=20><FONT SIZE=2>'
                    f'&nbsp;&nbsp;{d_nazev}</FONT></TD>'
                    f'<TD ALIGN="RIGHT"><FONT SIZE=2>{self._fmt_num(d_cena)}</FONT></TD>'
                    f'<TD ALIGN="RIGHT"><FONT SIZE=2>{d_mnoz}</FONT></TD>'
                    f'<TD ALIGN="RIGHT"><FONT SIZE=2>{self._fmt_num(d_celk)}</FONT></TD></TR>'
                )

        # Totals row
        celkem = safe_int(order.get("CENA_CELK", 0), 0)
        rows.append(
            f'<TR><TD ALIGN="RIGHT" HEIGHT=20 COLSPAN=3><FONT SIZE=2><B>Celkem</B>'
            f'<TD ALIGN="RIGHT"><FONT SIZE=2><B>{self._fmt_num(celkem)}</B></FONT></TD></TR>'
        )
        return "\n".join(rows)

    def _build_misto_urc(self, order):
        """Build delivery address HTML for «Misto_Urc» placeholder.
        Superseded by placing delivery address directly in the main header.
        """
        return ""

    def _build_pozn_zak(self, order):
        """Build customer notes HTML for «Pozn_Zak» placeholder."""
        pozn = self._s(order, "POZN_ZAK")
        if not pozn:
            return ""
        return (
            f'<TR><TD COLSPAN=4 HEIGHT=20><FONT SIZE=2>'
            f'Poznámka: {pozn}</FONT></TD></TR>'
        )

    @staticmethod
    def _s(record, field):
        """Get string field value, stripped and HTML escaped."""
        val = record.get(field, "")
        return html_lib.escape(str(val).strip()) if val else ""

    @staticmethod
    def _fmt_date(d):
        if isinstance(d, (datetime.date, datetime.datetime)):
            return d.strftime("%d.%m.%Y")
        return str(d).strip() if d else ""

    @staticmethod
    def _fmt_num(n):
        """Format number with space as thousands separator (Czech style)."""
        s = f"{int(n):,}".replace(",", " ")
        return s
