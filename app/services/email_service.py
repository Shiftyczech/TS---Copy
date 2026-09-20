"""
Email service – SMTP sending using config from tsd00 + smtp_config.ini
Replaces MEJLOVANI.DLL from original VFP app.
"""
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders, policy
from email.header import Header
from email.utils import formataddr
import os
import datetime
import configparser
import base64

def _deobfuscate(text: str) -> str:
    if not text: return ""
    try:
        return bytes([b ^ 0x5A for b in base64.b64decode(text)]).decode("utf-8")
    except Exception:
        return text


class EmailService:
    def __init__(self, ctx):
        self.ctx = ctx
        self._load_config()

    def _load_config(self):
        cfg = self.ctx.db.get_first_record("tsd00")
        self.smtp_server = str(cfg.get("POSTSERVER", "")) if cfg else ""
        self.smtp_port = 25
        self.sender_name = str(cfg.get("ODESILATEL", "")) if cfg else ""
        self.sender_email = str(cfg.get("MAIL", "")) if cfg else ""
        self.smtp_user = ""
        self.smtp_password = ""
        self.use_tls = False

        print(f"DB config: server={self.smtp_server}, port={self.smtp_port}, sender={self.sender_email}")

        # Override from smtp_config.ini if it exists
        ini_paths = [
            os.path.join(self.ctx.app_dir, "smtp_config.ini"),
            os.path.join(self.ctx.app_dir, "dist", "smtp_config.ini")
        ]
        
        for ini_path in ini_paths:
            if os.path.isfile(ini_path):
                print(f"Loading SMTP config from: {ini_path}")
                cp = configparser.ConfigParser()
                cp.read(ini_path, encoding="utf-8")
                if cp.has_section("smtp"):
                    self.smtp_server = cp.get("smtp", "server", fallback=self.smtp_server)
                    self.smtp_port = cp.getint("smtp", "port", fallback=self.smtp_port)
                    self.smtp_user = cp.get("smtp", "user", fallback="")
                    raw_pwd = cp.get("smtp", "password", fallback="")
                    self.smtp_password = _deobfuscate(raw_pwd) if raw_pwd else ""
                    self.use_tls = cp.getboolean("smtp", "tls", fallback=False)
                    self.sender_email = cp.get("smtp", "sender_email", fallback=self.sender_email)
                    # Stop after the first valid config file is found
                    break

        print(f"Final config: server={self.smtp_server}, port={self.smtp_port}, user={self.smtp_user}, sender={self.sender_email}, tls={self.use_tls}")

    def send(self, to_email, subject, body, attachments=None, html_attachment=None, pdf_attachment=None):
        """Send an email via SMTP."""
        print(f"Sending email to: {to_email}, subject: {subject}")
        msg = MIMEMultipart()
        msg["From"] = formataddr((Header(self.sender_name, 'utf-8').encode(), self.sender_email))
        msg["To"] = to_email
        msg["Subject"] = Header(subject, 'utf-8')

        msg.attach(MIMEText(body, "plain", "utf-8"))

        if html_attachment:
            filename, content = html_attachment
            part = MIMEBase("text", "html", charset="utf-8")
            part.set_payload(content.encode("utf-8"))
            encoders.encode_base64(part)
            part.add_header(
                "Content-Disposition",
                f"attachment; filename={filename}"
            )
            msg.attach(part)
            
        if pdf_attachment:
            filename, content_bytes = pdf_attachment
            part = MIMEBase("application", "pdf")
            part.set_payload(content_bytes)
            encoders.encode_base64(part)
            part.add_header(
                "Content-Disposition",
                f"attachment; filename={filename}"
            )
            msg.attach(part)

        if attachments:
            for filepath in attachments:
                if os.path.isfile(filepath):
                    with open(filepath, "rb") as f:
                        part = MIMEBase("application", "octet-stream")
                        part.set_payload(f.read())
                    encoders.encode_base64(part)
                    part.add_header(
                        "Content-Disposition",
                        f"attachment; filename={os.path.basename(filepath)}"
                    )
                    msg.attach(part)

        print(f"Connecting to {self.smtp_server}:{self.smtp_port}")
        if self.smtp_port == 465:
            with smtplib.SMTP_SSL(self.smtp_server, self.smtp_port, timeout=30) as server:
                server.set_debuglevel(1)
                if self.smtp_user and self.smtp_password:
                    server.login(self.smtp_user, self.smtp_password)
                result = server.sendmail(self.sender_email, [to_email], msg.as_string())
                print(f"Sendmail result: {result}")
        else:
            with smtplib.SMTP(self.smtp_server, self.smtp_port, timeout=30) as server:
                server.set_debuglevel(1)
                if self.use_tls:
                    server.starttls()
                if self.smtp_user and self.smtp_password:
                    server.login(self.smtp_user, self.smtp_password)
                result = server.sendmail(self.sender_email, [to_email], msg.as_string())
                print(f"Sendmail result: {result}")
        print("Email sent successfully")

    def send_direct(self, to, subject, body, cc="", attachments=None, html_attachment=None, pdf_attachment=None):
        """Send an email directly with CC support."""
        msg = MIMEMultipart()
        msg["From"] = formataddr((Header(self.sender_name, 'utf-8').encode(), self.sender_email))
        msg["To"] = to
        if cc:
            msg["Cc"] = cc
        msg["Subject"] = Header(subject, 'utf-8')

        msg.attach(MIMEText(body, "plain", "utf-8"))

        if html_attachment:
            filename, content = html_attachment
            part = MIMEBase("text", "html", charset="utf-8")
            part.set_payload(content.encode("utf-8"))
            encoders.encode_base64(part)
            part.add_header(
                "Content-Disposition",
                f"attachment; filename={filename}"
            )
            msg.attach(part)
            
        if pdf_attachment:
            filename, content_bytes = pdf_attachment
            part = MIMEBase("application", "pdf")
            part.set_payload(content_bytes)
            encoders.encode_base64(part)
            part.add_header(
                "Content-Disposition",
                f"attachment; filename={filename}"
            )
            msg.attach(part)

        if attachments:
            for filepath in attachments:
                if os.path.isfile(filepath):
                    with open(filepath, "rb") as f:
                        part = MIMEBase("application", "octet-stream")
                        part.set_payload(f.read())
                    encoders.encode_base64(part)
                    part.add_header(
                        "Content-Disposition",
                        f"attachment; filename={os.path.basename(filepath)}"
                    )
                    msg.attach(part)

        recipients = [to]
        if cc:
            recipients.extend(cc.split(","))

        try:
            if self.smtp_port == 465:
                with smtplib.SMTP_SSL(self.smtp_server, self.smtp_port, timeout=30) as server:
                    if self.smtp_user and self.smtp_password:
                        server.login(self.smtp_user, self.smtp_password)
                    server.sendmail(self.sender_email, recipients, msg.as_string())
            else:
                with smtplib.SMTP(self.smtp_server, self.smtp_port, timeout=30) as server:
                    if self.use_tls:
                        server.starttls()
                    if self.smtp_user and self.smtp_password:
                        server.login(self.smtp_user, self.smtp_password)
                    server.sendmail(self.sender_email, recipients, msg.as_string())
            return True
        except Exception as e:
            import socket
            import smtplib
            error_msg = str(e)
            if isinstance(e, socket.gaierror):
                error_msg = "Nelze najít server (zkontrolujte adresu serveru nebo připojení k internetu)."
            elif isinstance(e, socket.timeout):
                error_msg = "Spojení vypršelo (server neodpovídá)."
            elif isinstance(e, ConnectionRefusedError):
                error_msg = "Spojení bylo odmítnuto (zkontrolujte port nebo zabezpečení)."
            elif isinstance(e, smtplib.SMTPAuthenticationError):
                error_msg = "Chyba ověření (nesprávné jméno nebo heslo)."
            elif isinstance(e, smtplib.SMTPException):
                error_msg = f"Chyba poštovního serveru: {e}"
            else:
                error_msg = f"Neznámá chyba sítě/serveru: {e}"
            print(f"Email send error: {e}")
            raise RuntimeError(f"Chyba při odesílání e-mailu: {error_msg}") from e

    def send_from_queue(self, record):
        """Send a single message from tsd08 queue."""
        to_email = str(record.get("KOMU_MAIL", ""))
        subject = str(record.get("PREDMET", ""))
        body = str(record.get("ZPRAVA", ""))
        priloha_raw = str(record.get("PRILOHA", "")).strip()
        plany_raw = str(record.get("PLANY", "")).strip()
        
        attachments = []
        pdf_attachment = None
        
        if priloha_raw:
            if priloha_raw.startswith("<") or "<html" in priloha_raw.lower() or "<table" in priloha_raw.lower():
                cislo_obj = record.get("CISLO_OBJ", "objednavka")
                
                # Convert HTML to PDF
                import tempfile
                import os
                from PySide6.QtGui import QTextDocument
                from PySide6.QtPrintSupport import QPrinter
                
                doc = QTextDocument()
                doc.setHtml(priloha_raw)
                
                fd, temp_path = tempfile.mkstemp(suffix=".pdf")
                os.close(fd)
                
                try:
                    printer = QPrinter()
                    printer.setOutputFormat(QPrinter.PdfFormat)
                    printer.setOutputFileName(temp_path)
                    doc.print_(printer)
                    
                    with open(temp_path, "rb") as f:
                        pdf_bytes = f.read()
                    pdf_attachment = (f"objednavka_{cislo_obj}.pdf", pdf_bytes)
                except Exception as e:
                    print(f"Error generating PDF: {e}")
                finally:
                    if os.path.exists(temp_path):
                        os.remove(temp_path)
            else:
                attachments.extend([p.strip() for p in priloha_raw.split(",") if p.strip()])
                
        if plany_raw:
            for p in plany_raw.split(","):
                p_code = p.strip()
                if p_code:
                    plan_path = self._get_plan_path(p_code)
                    if plan_path:
                        attachments.append(plan_path)
            
        if not attachments:
            attachments = None

        self.send(to_email, subject, body, attachments=attachments, pdf_attachment=pdf_attachment)

        # Mark as sent using record number for precision
        if "_RECNO" in record:
            self.ctx.db.update_record("tsd08", record["_RECNO"], {
                "ODESLANO": datetime.datetime.now(),
            })
        else:
            self.ctx.db.update("tsd08", "CISLO_OBJ", record.get("CISLO_OBJ", ""), {
                "ODESLANO": datetime.datetime.now(),
            })

    def send_all_pending(self):
        """Send all unsent messages from tsd08."""
        rows = self.ctx.db.read_all("tsd08")
        sent = 0
        errors = []
        for r in rows:
            if r.get("ODESLANO"):
                continue
            try:
                self.send_from_queue(r)
                sent += 1
            except Exception as e:
                errors.append(f"Obj. {r.get('CISLO_OBJ', '?')}: {e}")
        return sent, errors

    def _get_plan_path(self, plan_code):
        if not plan_code:
            return ""
        mapping = {
            "A": "central_nakres.jpg",
            "B": "optimal_nakres.jpg",
            "C": "maximal_nakres.jpg",
            "D": "satelit_20_nakres.jpg",
            "E": "satelit_25_nakres.jpg"
        }
        filename = mapping.get(str(plan_code).strip().upper())
        if not filename:
            return ""
        path = os.path.join(self.ctx.app_dir, "VZORKY", filename)
        if os.path.isfile(path):
            return path
        return ""

    # Mapping of TYP_ZAKLAD numeric codes (from tsd02) to plan letter codes (A-E)
    # 1 = skleník 2m šíře    → CENTRAL  (A)
    # 2 = skleník 2.5m šíře  → OPTIMAL  (B)
    # 3 = skleník 3m šíře    → MAXIMAL  (C)
    # 4 = skleník ST 2m      → SATELIT 2m  (D)
    # 5 = skleník ST 2.5m    → SATELIT 2.5m (E)
    _TYP_ZAKLAD_TO_PLAN = {
        "1": "A",
        "2": "B",
        "3": "C",
        "4": "D",
        "5": "E",
    }

    def _collect_plans_for_order(self, cislo_obj, items_table, fallback_plan=""):
        """Automatically determine greenhouse plan codes from order assemblies.

        Reads all assemblies (sestavy) in the order's items_table, looks up each
        assembly's TYP_ZAKLAD from tsd02, maps it to a plan letter code (A-E),
        and returns a deduplicated comma-separated string (e.g. "A,C").
        If no plan codes are found via assemblies, falls back to the
        manually-set fallback_plan value on the order.
        """
        try:
            items = self.ctx.db.read_where(items_table, {"CISLO_OBJ": cislo_obj})
        except Exception:
            items = []

        # Build a cache: tsd02 KOD (int) -> plan letter code (A-E)
        try:
            all_sestavy = self.ctx.db.read_all("tsd02")
            sestavy_map = {}
            for r in all_sestavy:
                if not r.get("KOD"):
                    continue
                typ_zaklad = str(r.get("TYP_ZAKLAD", "")).strip()
                plan_code = self._TYP_ZAKLAD_TO_PLAN.get(typ_zaklad, "")
                if plan_code:
                    sestavy_map[int(r["KOD"])] = plan_code
        except Exception:
            sestavy_map = {}

        seen = []
        for item in items:
            try:
                kod = int(item.get("KOD", 0))
            except (ValueError, TypeError):
                continue
            plan_code = sestavy_map.get(kod, "")
            if plan_code and plan_code not in seen:
                seen.append(plan_code)

        if seen:
            return ",".join(seen)
        # Fall back to the manually-set plan on the order
        return str(fallback_plan).strip() if fallback_plan else ""

    def queue_message(self, cislo_obj, komu_jmeno, komu_mail, predmet, zprava, typ="M", priloha="", plany=""):
        """Add a message to the send queue (tsd08)."""
        self.ctx.db.insert("tsd08", {
            "CISLO_OBJ": cislo_obj,
            "KOMU_JMENO": komu_jmeno,
            "KOMU_MAIL": komu_mail,
            "PREDMET": predmet,
            "ZPRAVA": zprava,
            "VYTVORENO": datetime.datetime.now(),
            "ODESLANO": None,
            "TYP": typ,
            "PRILOHA": priloha,
            "PLANY": plany,
        })

    def queue_confirmation(self, cislo_obj, table=None):
        """Queue order confirmation email for the given order number."""
        if not table:
            order = self.ctx.db.read_by_key("tsd04", "CISLO_OBJ", cislo_obj)
            table = "tsd04"
            if not order:
                order = self.ctx.db.read_by_key("tsd06", "CISLO_OBJ", cislo_obj)
                table = "tsd06"
        else:
            order = self.ctx.db.read_by_key(table, "CISLO_OBJ", cislo_obj)
        if not order:
            return
        komu_jmeno = str(order.get("Z_JMENO", "")).strip()
        komu_mail = str(order.get("E_MAIL", "")).strip()
        if not komu_mail:
            return
            
        vl_odvoz = order.get("VL_ODVOZ", False)
        typ = "OV" if vl_odvoz else "OR"
        
        t_recs = self.ctx.db.read_where("tsd07", {"TYP": typ})
        t = t_recs[0] if isinstance(t_recs, list) and t_recs else (t_recs if t_recs else {})
        
        from app.services.document_generator import DocumentGenerator
        gen = DocumentGenerator(self.ctx)
        
        predmet = str(t.get("PREDMET_E", "")).strip()
        if not predmet:
            predmet = f"Potvrzení objednávky č. {cislo_obj}"
        predmet = gen.replace_text_placeholders(predmet, cislo_obj, table)
            
        zprava = str(t.get("TEXT_MAIL", "")).strip()
        if not zprava:
            cena = order.get("CENA_CELK", 0) or 0
            zprava = (
                f"Vážený zákazníku,\n\n"
                f"potvrzujeme přijetí Vaší objednávky č. {cislo_obj}.\n"
                f"Celková cena: {cena} Kč\n\n"
                f"Děkujeme za Vaši objednávku.\n"
                f"{self.sender_name}"
            )
        zprava = gen.replace_text_placeholders(zprava, cislo_obj, table)
            
        # Generate order HTML as attachment
        priloha = ""
        items_table = f"{table}a"
        try:
            priloha = gen.generate_order(cislo_obj, table=table, items_table=items_table)
        except Exception:
            pass

        # Auto-collect plans from order assemblies; fall back to manually-set PLAN
        plany = self._collect_plans_for_order(
            cislo_obj, items_table, fallback_plan=order.get("PLAN", "")
        )

        self.ctx.db.insert("tsd08", {
            "CISLO_OBJ": cislo_obj,
            "KOMU_JMENO": komu_jmeno,
            "KOMU_MAIL": komu_mail,
            "PREDMET": predmet,
            "ZPRAVA": zprava,
            "VYTVORENO": datetime.datetime.now(),
            "ODESLANO": None,
            "TYP": "P",
            "PRILOHA": priloha,
            "PLANY": plany,
        })
    def queue_change_notification(self, cislo_obj, table=None):
        """Queue notification email about order modification."""
        if not table:
            order = self.ctx.db.read_by_key("tsd04", "CISLO_OBJ", cislo_obj)
            table = "tsd04"
            if not order:
                order = self.ctx.db.read_by_key("tsd06", "CISLO_OBJ", cislo_obj)
                table = "tsd06"
        else:
            order = self.ctx.db.read_by_key(table, "CISLO_OBJ", cislo_obj)
        if not order:
            return
            
        komu_jmeno = str(order.get("Z_JMENO", "")).strip()
        komu_mail = str(order.get("E_MAIL", "")).strip()
        if not komu_mail:
            return
            
        vl_odvoz = order.get("VL_ODVOZ", False)
        typ = "ZV" if vl_odvoz else "ZR"
        
        t_recs = self.ctx.db.read_where("tsd07", {"TYP": typ})
        t = t_recs[0] if isinstance(t_recs, list) and t_recs else (t_recs if t_recs else {})
        
        from app.services.document_generator import DocumentGenerator
        gen = DocumentGenerator(self.ctx)
            
        predmet = str(t.get("PREDMET_E", "")).strip()
        if not predmet:
            predmet = f"Změna v objednávce č. {cislo_obj}"
        predmet = gen.replace_text_placeholders(predmet, cislo_obj, table)
            
        zprava = str(t.get("TEXT_MAIL", "")).strip()
        if not zprava:
            zprava = (
                f"Vážený zákazníku,\n\n"
                f"v systému byla zaznamenána změna v údajích Vaší objednávky č. {cislo_obj}.\n"
                f"Aktuální stav naleznete v přiloženém dokumentu.\n\n"
                f"Děkujeme,\n"
                f"{self.sender_name}"
            )
        zprava = gen.replace_text_placeholders(zprava, cislo_obj, table)
        
        priloha = ""
        items_table = f"{table}a"
        try:
            priloha = gen.generate_order(cislo_obj, table=table, items_table=items_table)
        except Exception:
            pass

        # Auto-collect plans from order assemblies; fall back to manually-set PLAN
        plany = self._collect_plans_for_order(
            cislo_obj, items_table, fallback_plan=order.get("PLAN", "")
        )

        self.ctx.db.insert("tsd08", {
            "CISLO_OBJ": cislo_obj,
            "KOMU_JMENO": komu_jmeno,
            "KOMU_MAIL": komu_mail,
            "PREDMET": predmet,
            "ZPRAVA": zprava,
            "VYTVORENO": datetime.datetime.now(),
            "ODESLANO": None,
            "TYP": "Z",
            "PRILOHA": priloha,
            "PLANY": plany,
        })
