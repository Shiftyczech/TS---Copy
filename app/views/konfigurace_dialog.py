"""
Konfigurace – 3 tabs: Údaje o firmě / Ostatní parametry / E-mail (SMTP)
"""
import os
import configparser
import smtplib
import base64

def _obfuscate(text: str) -> str:
    if not text: return ""
    try:
        return base64.b64encode(bytes([b ^ 0x5A for b in text.encode("utf-8")])).decode("utf-8")
    except Exception:
        return text

def _deobfuscate(text: str) -> str:
    if not text: return ""
    try:
        return bytes([b ^ 0x5A for b in base64.b64decode(text)]).decode("utf-8")
    except Exception:
        return text

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget,
    QLabel, QLineEdit, QPushButton, QRadioButton, QButtonGroup,
    QCheckBox, QGroupBox, QFormLayout, QMessageBox, QFileDialog,
    QSpinBox
)
from PySide6.QtGui import QAction
from PySide6.QtCore import Qt, QThread, Signal
from app.utils import format_phone_number


class SmtpTestWorker(QThread):
    result = Signal(bool, str)

    def __init__(self, server, port, user, password, use_tls, parent=None):
        super().__init__(parent)
        self.server = server
        self.port = port
        self.user = user
        self.password = password
        self.use_tls = use_tls

    def run(self):
        try:
            if self.port == 465:
                with smtplib.SMTP_SSL(self.server, self.port, timeout=15) as srv:
                    if self.user and self.password:
                        srv.login(self.user, self.password)
                    srv.noop()
            else:
                with smtplib.SMTP(self.server, self.port, timeout=15) as srv:
                    if self.use_tls:
                        srv.starttls()
                    if self.user and self.password:
                        srv.login(self.user, self.password)
                    srv.noop()
            self.result.emit(True, "Připojení úspěšné – SMTP server je dostupný.")
        except smtplib.SMTPAuthenticationError:
            self.result.emit(False, "Chyba přihlášení – zkontrolujte uživatele a heslo.")
        except Exception as e:
            self.result.emit(False, f"Chyba: {e}")


class KonfiguraceDialog(QDialog):
    def __init__(self, ctx, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self.setWindowTitle("Konfigurace")
        self.setMinimumSize(750, 550)
        self.resize(750, 550)
        self._build_ui()
        self._load_data()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_firma_tab(), "Údaje o firmě")
        self.tabs.addTab(self._build_parametry_tab(), "Ostatní parametry")
        self.tabs.addTab(self._build_smtp_tab(), "E-mail (SMTP)")
        layout.addWidget(self.tabs)

        btn_row = QHBoxLayout()
        self.btn_ulozit = QPushButton("Uložit")
        self.btn_ulozit.setObjectName("accentButton")
        self.btn_zpet = QPushButton("Zpět")
        self.btn_zpet.setObjectName("dangerButton")
        btn_row.addWidget(self.btn_ulozit)
        btn_row.addStretch()
        btn_row.addWidget(self.btn_zpet)
        layout.addLayout(btn_row)

        self.btn_ulozit.clicked.connect(self._save)
        self.btn_zpet.clicked.connect(self.reject)

    def _build_firma_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(20, 20, 20, 20)

        # IČ + DIČ
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("IČ:"))
        self.edit_ico = QLineEdit()
        self.edit_ico.setMaximumWidth(150)
        row1.addWidget(self.edit_ico)
        row1.addSpacing(40)
        row1.addWidget(QLabel("DIČ:"))
        self.edit_dic = QLineEdit()
        self.edit_dic.setMaximumWidth(200)
        row1.addWidget(self.edit_dic)
        row1.addStretch()
        layout.addLayout(row1)

        # Název firmy (2 lines)
        row2 = QHBoxLayout()
        lbl_naz = QLabel("Název firmy:")
        lbl_naz.setStyleSheet("font-weight: bold;")
        row2.addWidget(lbl_naz)
        self.edit_nazev1 = QLineEdit()
        row2.addWidget(self.edit_nazev1)
        layout.addLayout(row2)

        row2b = QHBoxLayout()
        row2b.addSpacing(90)
        self.edit_nazev2 = QLineEdit()
        row2b.addWidget(self.edit_nazev2)
        layout.addLayout(row2b)

        # Ulice
        row3 = QHBoxLayout()
        lbl_ul = QLabel("Ulice:")
        lbl_ul.setStyleSheet("font-weight: bold;")
        row3.addWidget(lbl_ul)
        self.edit_ulice = QLineEdit()
        row3.addWidget(self.edit_ulice)
        layout.addLayout(row3)

        # PSČ + Místo
        row4 = QHBoxLayout()
        lbl_psn = QLabel("PSČ:")
        lbl_psn.setStyleSheet("font-weight: bold;")
        row4.addWidget(lbl_psn)
        self.edit_psc = QLineEdit()
        self.edit_psc.setMaximumWidth(80)
        row4.addWidget(self.edit_psc)
        row4.addWidget(QLabel("Místo:"))
        self.edit_obec = QLineEdit()
        row4.addWidget(self.edit_obec)
        layout.addLayout(row4)

        # Telefon + Fax
        row5 = QHBoxLayout()
        row5.addWidget(QLabel("Telefon:"))
        self.edit_telefon = QLineEdit()
        self.edit_telefon.setMaximumWidth(180)
        row5.addWidget(self.edit_telefon)
        row5.addSpacing(30)
        row5.addWidget(QLabel("Fax:"))
        self.edit_fax = QLineEdit()
        self.edit_fax.setMaximumWidth(180)
        row5.addWidget(self.edit_fax)
        row5.addStretch()
        layout.addLayout(row5)

        # E-mail
        row6 = QHBoxLayout()
        row6.addWidget(QLabel("E-mail:"))
        self.edit_mail = QLineEdit()
        row6.addWidget(self.edit_mail)
        layout.addLayout(row6)

        # Logo
        row7 = QHBoxLayout()
        row7.addWidget(QLabel("Logo:"))
        self.edit_logo = QLineEdit()
        row7.addWidget(self.edit_logo)
        btn_browse = QPushButton("...")
        btn_browse.setMaximumWidth(30)
        btn_browse.clicked.connect(self._browse_logo)
        row7.addWidget(btn_browse)
        layout.addLayout(row7)

        layout.addStretch()
        return tab

    def _build_parametry_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(20, 20, 20, 20)

        # Částka za dopravu
        row1 = QHBoxLayout()
        lbl_dopr = QLabel("Částka za dopravu")
        lbl_dopr.setStyleSheet("font-weight: bold;")
        row1.addWidget(lbl_dopr)
        self.edit_dopravne = QLineEdit()
        self.edit_dopravne.setMaximumWidth(80)
        row1.addWidget(self.edit_dopravne)
        row1.addWidget(QLabel("Kč"))
        row1.addStretch()
        layout.addLayout(row1)

        # Dokumenty tisknout na tiskárnu
        row2 = QHBoxLayout()
        lbl_tisk = QLabel("Dokumenty tisknout na tiskárnu")
        lbl_tisk.setStyleSheet("font-weight: bold;")
        row2.addWidget(lbl_tisk)
        self.grp_tisk = QButtonGroup(self)
        self.rb_vychozi = QRadioButton("výchozí")
        self.rb_zvolit = QRadioButton("zvolit před tiskem")
        self.rb_netisknout = QRadioButton("netisknout")
        self.rb_vychozi.setChecked(True)
        self.grp_tisk.addButton(self.rb_vychozi, 1)
        self.grp_tisk.addButton(self.rb_zvolit, 2)
        self.grp_tisk.addButton(self.rb_netisknout, 3)
        for rb in [self.rb_vychozi, self.rb_zvolit, self.rb_netisknout]:
            row2.addWidget(rb)
        layout.addLayout(row2)

        layout.addSpacing(10)

        # Odesílatel
        row4 = QHBoxLayout()
        row4.addWidget(QLabel("Název odesílatele:"))
        self.edit_odesilatel = QLineEdit()
        row4.addWidget(self.edit_odesilatel)
        layout.addLayout(row4)

        layout.addSpacing(10)

        # Dodat po + Automatická záměna
        row7 = QHBoxLayout()
        row7.addWidget(QLabel('Zkrátit položku "Dodat po" o'))
        self.spin_dodat = QSpinBox()
        self.spin_dodat.setMinimum(0)
        self.spin_dodat.setMaximum(365)
        self.spin_dodat.setValue(5)
        row7.addWidget(self.spin_dodat)
        row7.addWidget(QLabel("dnů"))
        row7.addSpacing(40)
        self.chk_zamena = QCheckBox("povolit automatickou záměnu dílů")
        row7.addWidget(self.chk_zamena)
        row7.addStretch()
        layout.addSpacing(15)
        grp_db = QGroupBox("Databázové úložiště")
        db_layout = QHBoxLayout(grp_db)
        backend = getattr(self.ctx, "backend_name", "dbf").upper()
        self.lbl_db_info = QLabel(f"Aktivní databáze: <b>{'SQLite (vysokorychlostní)' if backend == 'SQLITE' else 'FoxPro DBF (původní)'}</b>")
        db_layout.addWidget(self.lbl_db_info)
        db_layout.addStretch()
        btn_migrace = QPushButton("Správa a převod databáze...")
        btn_migrace.clicked.connect(self._open_migrace)
        db_layout.addWidget(btn_migrace)
        layout.addWidget(grp_db)

        layout.addStretch()
        return tab

    def _open_migrace(self):
        from app.views.migrace_db_dialog import MigraceDbDialog
        dlg = MigraceDbDialog(self.ctx, parent=self)
        dlg.exec()
        backend = getattr(self.ctx, "backend_name", "dbf").upper()
        if hasattr(self, "lbl_db_info"):
            self.lbl_db_info.setText(f"Aktivní databáze: <b>{'SQLite (vysokorychlostní)' if backend == 'SQLITE' else 'FoxPro DBF (původní)'}</b>")

    # ── SMTP tab ─────────────────────────────────────────────────
    def _build_smtp_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        lbl_info = QLabel("Nastavení SMTP serveru pro odesílání e-mailů")
        lbl_info.setStyleSheet("font-weight: bold; font-size: 14px; margin-bottom: 4px;")
        layout.addWidget(lbl_info)

        form = QFormLayout()
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(12)
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        self.edit_smtp_server = QLineEdit()
        self.edit_smtp_server.setMinimumHeight(32)
        self.edit_smtp_server.setPlaceholderText("např. smtp.example.com nebo 88.86.113.75")
        form.addRow("SMTP server:", self.edit_smtp_server)

        port_row = QHBoxLayout()
        self.edit_smtp_port = QSpinBox()
        self.edit_smtp_port.setMinimum(1)
        self.edit_smtp_port.setMaximum(65535)
        self.edit_smtp_port.setValue(587)
        self.edit_smtp_port.setMinimumHeight(32)
        self.edit_smtp_port.setMinimumWidth(100)
        port_row.addWidget(self.edit_smtp_port)
        port_row.addStretch()
        form.addRow("Port:", port_row)

        self.chk_smtp_tls = QCheckBox("Použít TLS (doporučeno pro port 587)")
        self.chk_smtp_tls.setChecked(True)
        self.chk_smtp_tls.setMinimumHeight(28)
        form.addRow("Šifrování:", self.chk_smtp_tls)

        self.edit_smtp_user = QLineEdit()
        self.edit_smtp_user.setMinimumHeight(32)
        self.edit_smtp_user.setPlaceholderText("přihlašovací jméno / e-mail")
        form.addRow("Uživatel:", self.edit_smtp_user)

        self.edit_smtp_password = QLineEdit()
        self.edit_smtp_password.setMinimumHeight(32)
        self.edit_smtp_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.edit_smtp_password.setPlaceholderText("heslo k poštovnímu účtu")
        form.addRow("Heslo:", self.edit_smtp_password)

        self.chk_show_password = QCheckBox("Zobrazit heslo")
        self.chk_show_password.toggled.connect(self._toggle_password_visibility)
        form.addRow("", self.chk_show_password)

        self.edit_smtp_sender = QLineEdit()
        self.edit_smtp_sender.setMinimumHeight(32)
        self.edit_smtp_sender.setPlaceholderText("e-mail odesílatele")
        form.addRow("E-mail odesílatele:", self.edit_smtp_sender)

        layout.addLayout(form)
        layout.addSpacing(16)

        # Test button
        btn_row = QHBoxLayout()
        self.btn_test_smtp = QPushButton("  Otestovat připojení  ")
        self.btn_test_smtp.setObjectName("accentButton")
        self.btn_test_smtp.clicked.connect(self._test_smtp)
        btn_row.addWidget(self.btn_test_smtp)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self.lbl_smtp_status = QLabel("")
        self.lbl_smtp_status.setMinimumHeight(24)
        self.lbl_smtp_status.setWordWrap(True)
        layout.addWidget(self.lbl_smtp_status)

        layout.addStretch()
        return tab

    def _toggle_password_visibility(self, visible):
        if visible:
            self.edit_smtp_password.setEchoMode(QLineEdit.EchoMode.Normal)
        else:
            self.edit_smtp_password.setEchoMode(QLineEdit.EchoMode.Password)

    def _test_smtp(self):
        """Test SMTP connection with current settings asynchronously."""
        server = self.edit_smtp_server.text().strip()
        port = self.edit_smtp_port.value()
        user = self.edit_smtp_user.text().strip()
        password = self.edit_smtp_password.text().strip()
        use_tls = self.chk_smtp_tls.isChecked()

        if not server:
            self.lbl_smtp_status.setStyleSheet("color: #FF5252;")
            self.lbl_smtp_status.setText("Vyplňte adresu SMTP serveru.")
            return

        self.lbl_smtp_status.setStyleSheet("color: #FFD54F;")
        self.lbl_smtp_status.setText("Testuji připojení...")
        self.btn_test_smtp.setEnabled(False)

        self._smtp_worker = SmtpTestWorker(server, port, user, password, use_tls)
        self._smtp_worker.result.connect(self._on_smtp_test_result)
        self._smtp_worker.start()

    def _on_smtp_test_result(self, success, message):
        self.btn_test_smtp.setEnabled(True)
        if success:
            self.lbl_smtp_status.setStyleSheet("color: #4CAF50; font-weight: bold;")
        else:
            self.lbl_smtp_status.setStyleSheet("color: #FF5252;")
        self.lbl_smtp_status.setText(message)

    def _get_ini_path(self):
        return os.path.join(self.ctx.app_dir, "smtp_config.ini")

    def _load_smtp_config(self):
        """Load SMTP settings from smtp_config.ini."""
        ini_path = self._get_ini_path()
        if not os.path.isfile(ini_path):
            return
        cp = configparser.ConfigParser()
        cp.read(ini_path, encoding="utf-8")
        if not cp.has_section("smtp"):
            return
        self.edit_smtp_server.setText(cp.get("smtp", "server", fallback=""))
        self.edit_smtp_port.setValue(cp.getint("smtp", "port", fallback=587))
        self.chk_smtp_tls.setChecked(cp.getboolean("smtp", "tls", fallback=True))
        self.edit_smtp_user.setText(cp.get("smtp", "user", fallback=""))
        raw_pwd = cp.get("smtp", "password", fallback="")
        self.edit_smtp_password.setText(_deobfuscate(raw_pwd) if raw_pwd else "")
        self.edit_smtp_sender.setText(cp.get("smtp", "sender_email", fallback=""))

    def _save_smtp_config(self):
        """Save SMTP settings to smtp_config.ini."""
        cp = configparser.ConfigParser()
        cp.add_section("smtp")
        cp.set("smtp", "server", self.edit_smtp_server.text().strip())
        cp.set("smtp", "port", str(self.edit_smtp_port.value()))
        cp.set("smtp", "tls", "yes" if self.chk_smtp_tls.isChecked() else "no")
        cp.set("smtp", "user", self.edit_smtp_user.text().strip())
        pwd = self.edit_smtp_password.text().strip()
        cp.set("smtp", "password", _obfuscate(pwd) if pwd else "")
        cp.set("smtp", "sender_email", self.edit_smtp_sender.text().strip())
        ini_path = self._get_ini_path()
        with open(ini_path, "w", encoding="utf-8") as f:
            cp.write(f)

    def _browse_logo(self):
        path, _ = QFileDialog.getOpenFileName(self, "Vybrat logo", "", "Obrázky (*.png *.jpg *.bmp)")
        if path:
            self.edit_logo.setText(path)

    def _load_data(self):
        cfg = self.ctx.db.get_first_record("tsd00")
        if not cfg:
            return
        self.edit_ico.setText(str(cfg.get("ICO", "")))
        self.edit_dic.setText(str(cfg.get("DIC", "")))
        self.edit_nazev1.setText(str(cfg.get("NAZEV1", "")))
        self.edit_nazev2.setText(str(cfg.get("NAZEV2", "")))
        self.edit_ulice.setText(str(cfg.get("ULICE", "")))
        self.edit_psc.setText(str(cfg.get("PSC", "")))
        self.edit_obec.setText(str(cfg.get("OBEC", "")))
        self.edit_telefon.setText(format_phone_number(str(cfg.get("TELEFON", ""))))
        self.edit_fax.setText(str(cfg.get("FAX", "")))
        self.edit_mail.setText(str(cfg.get("MAIL", "")))
        self.edit_logo.setText(str(cfg.get("LOGO", "")))
        self.edit_dopravne.setText(str(cfg.get("DOPRAVNE", 0)))
        self.edit_odesilatel.setText(str(cfg.get("ODESILATEL", "")))

        # Load SMTP tab from ini
        self._load_smtp_config()

        tisk = int(cfg.get("TISK", 1) or 1)
        btn = self.grp_tisk.button(tisk)
        if btn:
            btn.setChecked(True)

        self.spin_dodat.setValue(int(cfg.get("DODAT_PO", 5) or 5))
        self.chk_zamena.setChecked(bool(cfg.get("ZAMENA", True)))

    def _save(self):
        ico = self.edit_ico.text().strip()
        if not ico:
            QMessageBox.warning(self, "Chyba", "IČ firmy nesmí být prázdné.")
            return
            
        nazev1 = self.edit_nazev1.text().strip()
        if not nazev1:
            QMessageBox.warning(self, "Chyba", "Název firmy nesmí být prázdný.")
            return
            
        try:
            dopravne_text = self.edit_dopravne.text().strip().replace(',', '.')
            dopravne_val = float(dopravne_text) if dopravne_text else 0.0
        except ValueError:
            QMessageBox.warning(self, "Chyba", "Částka za dopravu musí být platné číslo.")
            return

        data = {
            "ICO": ico,
            "DIC": self.edit_dic.text().strip(),
            "NAZEV1": nazev1,
            "NAZEV2": self.edit_nazev2.text().strip(),
            "ULICE": self.edit_ulice.text().strip(),
            "PSC": self.edit_psc.text().strip(),
            "OBEC": self.edit_obec.text().strip(),
            "TELEFON": format_phone_number(self.edit_telefon.text().strip()),
            "FAX": self.edit_fax.text().strip(),
            "MAIL": self.edit_mail.text().strip(),
            "LOGO": self.edit_logo.text().strip(),
            "DOPRAVNE": dopravne_val,
            "TISK": self.grp_tisk.checkedId(),
            "ODESILATEL": self.edit_odesilatel.text().strip(),
            "DODAT_PO": self.spin_dodat.value(),
            "ZAMENA": self.chk_zamena.isChecked(),
        }
        # Update first (and only) record in tsd00
        cfg = self.ctx.db.get_first_record("tsd00")
        if cfg:
            self.ctx.db.update_record("tsd00", cfg["_RECNO"], data)
        else:
            self.ctx.db.insert("tsd00", data)

        # Save SMTP settings to ini
        self._save_smtp_config()

        QMessageBox.information(self, "Uloženo", "Konfigurace byla uložena.")
        self.accept()
