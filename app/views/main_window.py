"""
Main Window - Úvodní panel
1:1 replica of the original VFP application's main screen.
"""
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QMenu, QMessageBox, QFrame,
    QProgressDialog, QDialog, QDateEdit, QApplication, QComboBox
)
from PySide6.QtCore import Qt, QDate, QSettings
from PySide6.QtGui import QAction


class UklidArchivuDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Úklid dat do archivu")
        self.setModal(True)
        self.setMinimumWidth(300)

        layout = QVBoxLayout(self)

        info_label = QLabel("Vyberte datum, do kterého se mají vyřízené objednávky uklidit do archivu.\n\nDatum nesmí být mladší než poslední dva dny.")
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        self.date_edit = QDateEdit(self)
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat("dd.MM.yyyy")
        max_date = QDate.currentDate().addDays(-2)
        self.date_edit.setMaximumDate(max_date)
        self.date_edit.setDate(max_date)
        layout.addWidget(self.date_edit)

        btn_layout = QHBoxLayout()
        btn_ok = QPushButton("OK")
        btn_ok.clicked.connect(self.accept)
        btn_storno = QPushButton("Zrušit")
        btn_storno.clicked.connect(self.reject)

        btn_layout.addStretch()
        btn_layout.addWidget(btn_ok)
        btn_layout.addWidget(btn_storno)
        layout.addLayout(btn_layout)

    def selected_date(self) -> QDate:
        return self.date_edit.date()


class MainWindow(QMainWindow):
    def __init__(self, app_context):
        super().__init__()
        self.ctx = app_context
        self.authenticated = False
        self.setWindowTitle("Evidence skleníků")
        self.setMinimumSize(800, 600)
        self.resize(1000, 700)
        self._build_ui()
        # Give password field focus so Enter works immediately
        self.password_edit.setFocus()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(40, 20, 40, 20)

        # Theme selector at the top right
        top_bar = QHBoxLayout()
        top_bar.addStretch()
        self.combo_theme = QComboBox()
        self.combo_theme.setObjectName("comboTheme")
        self.combo_theme.setFixedWidth(130)
        self.combo_theme.addItem("Tmavý režim", "dark")
        self.combo_theme.addItem("Světlý režim", "light")
        self.combo_theme.addItem("Modrý režim", "blue")
        self._init_theme_combo()
        self.combo_theme.currentIndexChanged.connect(self._on_theme_changed)
        top_bar.addWidget(self.combo_theme)
        main_layout.addLayout(top_bar)

        # --- Title area ---
        title_area = QVBoxLayout()
        title_area.setAlignment(Qt.AlignCenter)

        self.title_label = QLabel("Tobiášovy  šroubované")
        self.title_label.setObjectName("titleLabel")
        self.title_label.setAlignment(Qt.AlignCenter)
        title_area.addWidget(self.title_label)

        self.subtitle_label = QLabel("S K L E N Í K Y")
        self.subtitle_label.setObjectName("subtitleLabel")
        self.subtitle_label.setAlignment(Qt.AlignCenter)
        title_area.addWidget(self.subtitle_label)

        main_layout.addLayout(title_area)
        main_layout.addSpacing(30)

        # --- Content area: buttons (left) + info (right) ---
        content_layout = QHBoxLayout()
        content_layout.setSpacing(60)

        # Left side - Menu buttons
        btn_layout = QVBoxLayout()
        btn_layout.setSpacing(6)

        self.btn_objednavky = QPushButton("Objednávky")
        self.btn_objednavky.setObjectName("mainMenuButton")
        self.btn_rozvozni = QPushButton("Rozvozní plány")
        self.btn_rozvozni.setObjectName("mainMenuButton")
        self.btn_archiv = QPushButton("Archiv")
        self.btn_archiv.setObjectName("mainMenuButton")
        self.btn_dily = QPushButton("Základní díly a sestavy")
        self.btn_dily.setObjectName("mainMenuButton")
        self.btn_texty = QPushButton("Texty zpráv a dokumentů")
        self.btn_texty.setObjectName("mainMenuButton")
        self.btn_servis = QPushButton("Servisní akce")
        self.btn_servis.setObjectName("mainMenuButton")
        self.btn_konec = QPushButton("Konec")
        self.btn_konec.setObjectName("mainMenuButton")

        for btn in [self.btn_objednavky, self.btn_rozvozni, self.btn_archiv,
                     self.btn_dily, self.btn_texty, self.btn_servis, self.btn_konec]:
            btn_layout.addWidget(btn)

        btn_layout.addStretch()
        content_layout.addLayout(btn_layout)

        # Right side - Password
        right_layout = QVBoxLayout()
        right_layout.addStretch()

        # Password row – centered together
        pw_layout = QHBoxLayout()
        pw_layout.addStretch()
        pw_label = QLabel("Heslo:")
        pw_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.Password)
        self.password_edit.setFixedWidth(160)
        self.password_edit.returnPressed.connect(self._check_password)
        pw_layout.addWidget(pw_label)
        pw_layout.addSpacing(8)
        pw_layout.addWidget(self.password_edit)
        pw_layout.addStretch()
        right_layout.addLayout(pw_layout)

        right_layout.addStretch()
        content_layout.addLayout(right_layout)

        main_layout.addLayout(content_layout)
        main_layout.addStretch()

        # --- Setup menus ---
        self._setup_menus()
        self._setup_connections()
        self._set_buttons_enabled(False)

    def _setup_menus(self):
        # Objednávky popup menu
        self.menu_objednavky = QMenu(self)
        self.act_prijem = self.menu_objednavky.addAction("Příjem objednávky")
        self.act_oprava = self.menu_objednavky.addAction("Oprava objednávky")
        self.act_seznam = self.menu_objednavky.addAction("Seznam objednávek")
        self.act_vyhledani_sestavy_obj = self.menu_objednavky.addAction("Vyhledávání sestavy v objednávkách")
        self.act_vlastni_odvozy = self.menu_objednavky.addAction("Vlastní odvozy")
        self.act_eposta = self.menu_objednavky.addAction("Elektronická pošta")

        # Archiv popup menu
        self.menu_archiv = QMenu(self)
        self.act_prohl_archiv = self.menu_archiv.addAction("Prohlížení archivu")
        self.act_uklid = self.menu_archiv.addAction("Úklid dat do archivu")
        self.act_zpetny = self.menu_archiv.addAction("Zpětný převod z archivu")

        # Základní díly a sestavy popup menu
        self.menu_dily = QMenu(self)
        self.act_zakl_dily = self.menu_dily.addAction("Základní díly a doplňky")
        self.act_skl_sestavy = self.menu_dily.addAction("Skleníkové sestavy")

        # Texty zpráv a dokumentů popup menu
        self.menu_texty = QMenu(self)
        self.act_info_texty = self.menu_texty.addAction("Informační texty")
        self.act_email_texty = self.menu_texty.addAction("E-Mail zprávy")
        self.act_sms_texty = self.menu_texty.addAction("SMS zprávy")

        # Servisní akce popup menu
        self.menu_servis = QMenu(self)
        self.act_konfigurace = self.menu_servis.addAction("Konfigurace")
        self.act_uzivatele = self.menu_servis.addAction("Uživatelé a práva")
        self.act_psc = self.menu_servis.addAction("Poštovní směrovací čísla")
        self.menu_servis.addSeparator()
        self.act_zaloha = self.menu_servis.addAction("Záloha a obnovení")
        self.act_migrace = self.menu_servis.addAction("Převod databáze (DBF ↔ SQLite)")

    def _setup_connections(self):
        self.btn_objednavky.clicked.connect(lambda: self._show_menu(self.btn_objednavky, self.menu_objednavky))
        self.btn_rozvozni.clicked.connect(self._open_rozvozni_plany)
        self.btn_archiv.clicked.connect(lambda: self._show_menu(self.btn_archiv, self.menu_archiv))
        self.btn_dily.clicked.connect(lambda: self._show_menu(self.btn_dily, self.menu_dily))
        self.btn_texty.clicked.connect(lambda: self._show_menu(self.btn_texty, self.menu_texty))
        self.btn_servis.clicked.connect(lambda: self._show_menu(self.btn_servis, self.menu_servis))
        self.btn_konec.clicked.connect(self.close)

        # Objednávky actions
        self.act_prijem.triggered.connect(self._open_nova_objednavka)
        self.act_oprava.triggered.connect(self._open_oprava_objednavky)
        self.act_seznam.triggered.connect(self._open_seznam_objednavek)
        self.act_vyhledani_sestavy_obj.triggered.connect(self._open_vyhledani_sestavy_obj)
        self.act_vlastni_odvozy.triggered.connect(self._open_vlastni_odvozy)
        self.act_eposta.triggered.connect(self._open_eposta)

        # Archiv actions
        self.act_prohl_archiv.triggered.connect(self._open_archiv_prohlizeni)
        self.act_uklid.triggered.connect(self._open_archiv_uklid)
        self.act_zpetny.triggered.connect(self._open_archiv_zpetny)

        # Díly actions
        self.act_zakl_dily.triggered.connect(self._open_zakladni_dily)
        self.act_skl_sestavy.triggered.connect(self._open_sklenikove_sestavy)

        # Texty actions
        self.act_info_texty.triggered.connect(lambda: self._open_texty_zprav("info"))
        self.act_email_texty.triggered.connect(lambda: self._open_texty_zprav("email"))
        self.act_sms_texty.triggered.connect(lambda: self._open_texty_zprav("sms"))

        # Servisní actions
        self.act_konfigurace.triggered.connect(self._open_konfigurace)
        self.act_uzivatele.triggered.connect(self._open_uzivatele)
        self.act_psc.triggered.connect(self._open_psc)
        self.act_zaloha.triggered.connect(self._open_zaloha)
        self.act_migrace.triggered.connect(self._open_migrace_db)

    def _show_menu(self, button: QPushButton, menu: QMenu):
        pos = button.mapToGlobal(button.rect().bottomRight())
        menu.exec(pos)

    def _set_buttons_enabled(self, enabled: bool):
        for btn in [self.btn_objednavky, self.btn_rozvozni, self.btn_archiv,
                     self.btn_dily, self.btn_texty, self.btn_servis]:
            btn.setEnabled(enabled)

    def _check_password(self):
        password = self.password_edit.text().strip()
        if not password:
            return
        # Check against tsd01a users table
        try:
            users = self.ctx.db.read_all("tsd01a")
        except Exception as e:
            QMessageBox.warning(self, "Chyba", f"Nelze načíst uživatele:\n{e}")
            return

        for user in users:
            stored_pw = str(user.get("HESLO", "")).strip()

            # Plain-text comparison (normal case)
            if password.upper() == stored_pw.upper():
                self._login_success()
                return

            # Migration: old VFP encrypted password (contains non-printable chars)
            if any(ord(c) < 32 for c in stored_pw):
                # Accept the entered password and migrate to plain text
                try:
                    self.ctx.db.update("tsd01a", "KOD", user.get("KOD", ""), {
                        "HESLO": password.upper()
                    })
                except Exception:
                    pass  # If update fails, still allow login
                self._login_success()
                return

        QMessageBox.warning(self, "Chyba", "Nesprávné heslo!")
        self.password_edit.clear()
        self.password_edit.setFocus()

    def _login_success(self):
        self.authenticated = True
        self._set_buttons_enabled(True)
        self.password_edit.setReadOnly(True)
        self.password_edit.setStyleSheet("background-color: #2E7D32; color: white;")

    # --- Dialog openers ---
    def _open_nova_objednavka(self):
        from app.views.objednavka_dialog import ObjednavkaDialog
        dlg = ObjednavkaDialog(self.ctx, mode="new", parent=self)
        dlg.exec()

    def _open_zmena_objednavky(self):
        from app.views.objednavka_dialog import ObjednavkaDialog
        dlg = ObjednavkaDialog(self.ctx, mode="change", parent=self)
        dlg.exec()

    def _open_oprava_objednavky(self):
        from app.views.vyhledani_objednavky_dialog import VyhledaniObjednavkyDialog
        lookup = VyhledaniObjednavkyDialog(self.ctx, parent=self)
        if lookup.exec() == QDialog.Accepted and lookup.selected_cislo:
            from app.views.objednavka_dialog import ObjednavkaDialog
            dlg = ObjednavkaDialog(self.ctx, cislo_obj=lookup.selected_cislo, parent=self)
            dlg.exec()

    def _open_seznam_objednavek(self):
        from app.views.seznam_objednavek_dialog import SeznamObjednavekDialog
        dlg = SeznamObjednavekDialog(self.ctx, parent=self)
        dlg.exec()

    def _open_vyhledani_sestavy_obj(self):
        from app.views.vyhledani_sestavy_v_objednavkach_dialog import VyhledaniSestavyVObjednavkachDialog
        dlg = VyhledaniSestavyVObjednavkachDialog(self.ctx, parent=self)
        dlg.exec()

    def _open_vlastni_odvozy(self):
        from app.views.vlastni_odvozy_dialog import VlastniOdvozyDialog
        dlg = VlastniOdvozyDialog(self.ctx, parent=self)
        dlg.exec()

    def _open_eposta(self):
        from app.views.elektronicka_posta_dialog import ElektronickaPostaDialog
        dlg = ElektronickaPostaDialog(self.ctx, parent=self)
        dlg.exec()

    def _open_rozvozni_plany(self):
        from app.views.rozvozni_plany_dialog import RozvozniPlanyDialog
        dlg = RozvozniPlanyDialog(self.ctx, parent=self)
        dlg.exec()

    def _open_archiv_prohlizeni(self):
        from app.views.seznam_objednavek_dialog import SeznamObjednavekDialog
        dlg = SeznamObjednavekDialog(self.ctx, source_table="tsd06", parent=self)
        dlg.exec()

    def _open_archiv_uklid(self):
        # Find completed orders (DATUM_VYR is set) in active table tsd06
        all_orders = self.ctx.db.read_all("tsd04")
        completed_all = [r for r in all_orders if r.get("DATUM_VYR")]
        if not completed_all:
            QMessageBox.information(self, "Archiv", "Žádné vyřízené objednávky k archivaci.")
            return

        dlg = UklidArchivuDialog(self)
        if dlg.exec() != QDialog.Accepted:
            return

        target_qdate = dlg.selected_date()

        completed = []
        for r in completed_all:
            val = r.get("DATUM_VYR")
            if val:
                q_date = None
                if isinstance(val, str):
                    if len(val) >= 10:
                        parts = val[:10].split("-")
                        if len(parts) == 3:
                            try:
                                q_date = QDate(int(parts[0]), int(parts[1]), int(parts[2]))
                            except ValueError:
                                pass
                else:
                    try:
                        q_date = QDate(val.year, val.month, val.day)
                    except AttributeError:
                        pass
                
                if q_date and q_date <= target_qdate:
                    completed.append(r)

        if not completed:
            QMessageBox.information(self, "Archiv", f"K vybranému datu ({target_qdate.toString('dd.MM.yyyy')}) nebyly nalezeny žádné vyřízené objednávky.")
            return
            
        if QMessageBox.question(
            self, "Úklid do archivu",
            f"Přesunout {len(completed)} vyřízených objednávek do archivu?",
            QMessageBox.Yes | QMessageBox.No
        ) != QMessageBox.Yes:
            return

        cisla = {str(r.get("CISLO_OBJ", "")).strip() for r in completed}

        progress = QProgressDialog("Archivace objednávek...", None, 0, 0, self)
        progress.setWindowTitle("Archiv")
        progress.setWindowModality(Qt.WindowModal)
        progress.setMinimumDuration(0)
        progress.setValue(0)

        def do_archive(progress_cb):
            progress_cb(0, "Načítání položek...")
            # Pre-load all related items/details in ONE scan each
            items_by_cislo = self.ctx.db.read_where_in("tsd04a", "CISLO_OBJ", cisla)
            details_by_cislo = self.ctx.db.read_where_in("tsd04b", "CISLO_OBJ", cisla)

            progress_cb(1, "Kopírování do archivu...")
            # Batch insert orders
            self.ctx.db.batch_insert("tsd06", completed)
            # Batch insert items + details
            all_items = [it for lst in items_by_cislo.values() for it in lst]
            all_details = [dt for lst in details_by_cislo.values() for dt in lst]
            self.ctx.db.batch_insert("tsd06a", all_items)
            self.ctx.db.batch_insert("tsd06b", all_details)

            progress_cb(2, "Mazání z aktivních tabulek...")
            # Batch delete from active tables
            self.ctx.db.batch_delete("tsd04", "CISLO_OBJ", cisla)
            self.ctx.db.batch_delete("tsd04a", "CISLO_OBJ", cisla)
            self.ctx.db.batch_delete("tsd04b", "CISLO_OBJ", cisla)
            return len(completed)

        from app.services.db_worker import DbWorker
        self._archive_worker = DbWorker(do_archive)
        self._archive_progress = progress

        def on_finished(ok, msg, result):
            progress.close()
            self._archive_worker = None
            if ok:
                QMessageBox.information(self, "Archiv", f"Do archivu přesunuto {result} objednávek.")
            else:
                QMessageBox.warning(self, "Chyba", f"Chyba při archivaci: {msg}")

        self._archive_worker.progress.connect(lambda step, lbl: progress.setLabelText(lbl))
        self._archive_worker.finished.connect(on_finished)
        self._archive_worker.start()

    def _open_archiv_zpetny(self):
        # Show archive orders and let user select one to move back
        all_archive = self.ctx.db.read_all("tsd06")
        if not all_archive:
            QMessageBox.information(self, "Archiv", "Archiv je prázdný.")
            return
        from app.views.archiv_zpetny_dialog import ArchivZpetnyDialog
        dlg = ArchivZpetnyDialog(self.ctx, parent=self)
        dlg.exec()

    def _open_zakladni_dily(self):
        from app.views.zakladni_dily_dialog import ZakladniDilyDialog
        dlg = ZakladniDilyDialog(self.ctx, parent=self)
        dlg.exec()

    def _open_sklenikove_sestavy(self):
        from app.views.sklenikove_sestavy_dialog import SklenikoveSestavyDialog
        dlg = SklenikoveSestavyDialog(self.ctx, parent=self)
        dlg.exec()

    def _init_theme_combo(self):
        settings = QSettings("TSSkleniky", "TS_Evidence")
        current = settings.value("theme", "dark")
        idx = self.combo_theme.findData(current)
        if idx >= 0:
            self.combo_theme.blockSignals(True)
            self.combo_theme.setCurrentIndex(idx)
            self.combo_theme.blockSignals(False)

    def _on_theme_changed(self, index):
        theme_code = self.combo_theme.itemData(index)
        if not theme_code:
            return
        settings = QSettings("TSSkleniky", "TS_Evidence")
        settings.setValue("theme", theme_code)

        # Apply instantly
        from app.main import apply_theme
        apply_theme(QApplication.instance(), theme_code)

    def _open_texty_zprav(self, typ: str):
        from app.views.texty_zprav_dialog import TextyZpravDialog
        dlg = TextyZpravDialog(self.ctx, typ=typ, parent=self)
        dlg.exec()

    def _open_konfigurace(self):
        from app.views.konfigurace_dialog import KonfiguraceDialog
        dlg = KonfiguraceDialog(self.ctx, parent=self)
        dlg.exec()

    def _open_uzivatele(self):
        from app.views.uzivatele_dialog import UzivateleDialog
        dlg = UzivateleDialog(self.ctx, parent=self)
        dlg.exec()

    def _open_psc(self):
        from app.views.psc_dialog import PscDialog
        dlg = PscDialog(self.ctx, parent=self)
        dlg.exec()

    def _open_zaloha(self):
        from app.views.backup_dialog import BackupDialog
        dlg = BackupDialog(self.ctx, parent=self)
        dlg.exec()

    def _open_migrace_db(self):
        from app.views.migrace_db_dialog import MigraceDbDialog
        dlg = MigraceDbDialog(self.ctx, parent=self)
        dlg.exec()

    def closeEvent(self, event):
        from app.services.backup_service import BackupService
        svc = BackupService(self.ctx)

        if not svc.auto_backup:
            event.accept()
            return

        reply = QMessageBox.question(
            self,
            "Automatická záloha",
            "Chcete před ukončením aplikace provést zálohu dat?",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            progress = QProgressDialog("Probíhá záloha dat...\nProsím čekejte.", None, 0, 0, self)
            progress.setWindowTitle("Záloha")
            progress.setWindowModality(Qt.WindowModal)
            progress.setMinimumDuration(0)
            progress.show()

            from PySide6.QtWidgets import QApplication
            QApplication.processEvents()

            try:
                svc.auto_daily_backup()
            except Exception as e:
                QMessageBox.warning(self, "Chyba zálohy", f"Zálohování selhalo:\n{e}")

            progress.close()

        event.accept()
