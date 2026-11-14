"""
Dialog pro konfiguraci a převod databáze do MariaDB na Synology NAS.
Umožňuje otestovat spojení, jedním klikem přenést všechna data z SQLite do MariaDB
a nastavit MariaDB jako výchozí úložiště aplikace.
"""
import os
import configparser
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QProgressBar, QTextEdit, QMessageBox, QGroupBox,
    QFormLayout, QSpinBox
)
from PySide6.QtCore import Qt, QThread, Signal
from app.services.mariadb_service import test_mariadb_connection
from app.services.migration_mariadb_service import SqliteToMariaDbMigrator


class MigrationWorker(QThread):
    progress = Signal(int, str)
    finished = Signal(bool, str, dict)

    def __init__(self, sqlite_path, host, port, user, password, database, parent=None):
        super().__init__(parent)
        self.sqlite_path = sqlite_path
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.database = database

    def run(self):
        try:
            migrator = SqliteToMariaDbMigrator(
                sqlite_path=self.sqlite_path,
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password,
                database=self.database
            )

            def on_progress(pct, text):
                self.progress.emit(pct, text)

            stats = migrator.migrate(progress_callback=on_progress)
            self.finished.emit(True, "Převod byl úspěšně dokončen.", stats)
        except Exception as e:
            self.finished.emit(False, str(e), {})


class MigraceMariaDbDialog(QDialog):
    def __init__(self, ctx, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self.setWindowTitle("Nastavení a převod do MariaDB (Synology NAS)")
        self.setMinimumSize(620, 560)
        self.resize(650, 600)
        self._worker = None

        self._ini_path = os.path.join(self.ctx.app_dir, "db_config.ini")
        self._build_ui()
        self._load_config()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        title = QLabel("Centrální databáze MariaDB na Synology")
        title.setObjectName("titleLabel")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        desc = QLabel(
            "Umožňuje bezpečný a rychlý souběžný běh programu na více počítačích najednou.\n"
            "Data jsou uložena centrálně na Synology NASu v MariaDB 10 a automaticky chráněna denní zálohou."
        )
        desc.setWordWrap(True)
        layout.addWidget(desc)

        # Connection Form Group
        grp_conn = QGroupBox("Parametry připojení k Synology MariaDB 10")
        form = QFormLayout(grp_conn)
        form.setSpacing(8)

        self.edit_host = QLineEdit()
        self.edit_host.setPlaceholderText("např. 10.0.0.20 nebo IP vašeho Synology")
        form.addRow("IP adresa / Hostitel:", self.edit_host)

        port_row = QHBoxLayout()
        self.spin_port = QSpinBox()
        self.spin_port.setRange(1, 65535)
        self.spin_port.setValue(3306)
        self.spin_port.setMinimumWidth(100)
        port_row.addWidget(self.spin_port)
        port_row.addStretch()
        form.addRow("Port (výchozí 3306):", port_row)

        self.edit_database = QLineEdit("ts_skleniky")
        form.addRow("Název databáze:", self.edit_database)

        self.edit_user = QLineEdit("root")
        form.addRow("Uživatel:", self.edit_user)

        self.edit_password = QLineEdit()
        self.edit_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.edit_password.setPlaceholderText("Heslo zadané při instalaci MariaDB 10")
        form.addRow("Heslo:", self.edit_password)

        btn_test_row = QHBoxLayout()
        self.btn_test = QPushButton("Otestovat připojení")
        self.btn_test.clicked.connect(self._test_connection)
        btn_test_row.addWidget(self.btn_test)
        self.lbl_test_result = QLabel("")
        btn_test_row.addWidget(self.lbl_test_result)
        btn_test_row.addStretch()
        form.addRow("", btn_test_row)

        layout.addWidget(grp_conn)

        # Action Buttons Group
        grp_actions = QGroupBox("Převod a aktivace")
        act_layout = QVBoxLayout(grp_actions)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        act_layout.addWidget(self.progress_bar)

        self.lbl_status = QLabel("Připraveno k testu nebo převodu dat.")
        self.lbl_status.setAlignment(Qt.AlignCenter)
        act_layout.addWidget(self.lbl_status)

        self.txt_log = QTextEdit()
        self.txt_log.setReadOnly(True)
        self.txt_log.setMaximumHeight(140)
        act_layout.addWidget(self.txt_log)

        btn_box = QHBoxLayout()
        self.btn_migrate = QPushButton("Převést data z SQLite do MariaDB")
        self.btn_migrate.setObjectName("accentButton")
        self.btn_migrate.clicked.connect(self._start_migration)
        btn_box.addWidget(self.btn_migrate)

        self.btn_activate = QPushButton("Aktivovat MariaDB v aplikaci")
        self.btn_activate.clicked.connect(self._activate_mariadb)
        btn_box.addWidget(self.btn_activate)

        self.btn_switch_sqlite = QPushButton("Přepnout zpět na lokální SQLite")
        self.btn_switch_sqlite.clicked.connect(self._switch_to_sqlite)
        btn_box.addWidget(self.btn_switch_sqlite)

        act_layout.addLayout(btn_box)
        layout.addWidget(grp_actions)

        # Bottom row
        bot_row = QHBoxLayout()
        self.btn_save_cfg = QPushButton("Uložit nastavení")
        self.btn_save_cfg.clicked.connect(self._save_config)
        bot_row.addWidget(self.btn_save_cfg)

        bot_row.addStretch()
        self.btn_close = QPushButton("Zavřít")
        self.btn_close.clicked.connect(self.accept)
        bot_row.addWidget(self.btn_close)
        layout.addLayout(bot_row)

    def _load_config(self):
        cp = configparser.ConfigParser()
        if os.path.exists(self._ini_path):
            cp.read(self._ini_path, encoding="utf-8")

        host = cp.get("database", "host", fallback="10.0.0.20")
        port = cp.getint("database", "port", fallback=3306)
        db = cp.get("database", "database", fallback="ts_skleniky")
        user = cp.get("database", "user", fallback="root")
        pwd = cp.get("database", "password", fallback="")

        self.edit_host.setText(host)
        self.spin_port.setValue(port)
        self.edit_database.setText(db)
        self.edit_user.setText(user)
        self.edit_password.setText(pwd)

        backend = getattr(self.ctx, "backend_name", "sqlite").lower()
        if backend == "mariadb":
            self.lbl_status.setText("Aktivní databáze: MariaDB (Synology)")
            self.btn_activate.setEnabled(False)
            self.btn_switch_sqlite.setEnabled(True)
        else:
            self.lbl_status.setText(f"Aktivní databáze: {backend.upper()} (lokální)")
            self.btn_activate.setEnabled(True)
            self.btn_switch_sqlite.setEnabled(False)

    def _save_config(self):
        cp = configparser.ConfigParser()
        if os.path.exists(self._ini_path):
            cp.read(self._ini_path, encoding="utf-8")

        if not cp.has_section("database"):
            cp.add_section("database")

        cp.set("database", "host", self.edit_host.text().strip())
        cp.set("database", "port", str(self.spin_port.value()))
        cp.set("database", "database", self.edit_database.text().strip())
        cp.set("database", "user", self.edit_user.text().strip())
        cp.set("database", "password", self.edit_password.text())

        with open(self._ini_path, "w", encoding="utf-8") as f:
            cp.write(f)

    def _test_connection(self):
        self._save_config()
        host = self.edit_host.text().strip()
        port = self.spin_port.value()
        user = self.edit_user.text().strip()
        pwd = self.edit_password.text()
        db = self.edit_database.text().strip()

        self.lbl_test_result.setText("Testuji připojení...")
        ok, msg = test_mariadb_connection(host, port, user, pwd, db)
        if ok:
            self.lbl_test_result.setStyleSheet("color: #4CAF50; font-weight: bold;")
            self.lbl_test_result.setText("✓ Připojení v pořádku!")
            QMessageBox.information(self, "Test připojení", msg)
        else:
            self.lbl_test_result.setStyleSheet("color: #f44336; font-weight: bold;")
            self.lbl_test_result.setText("✗ Připojení selhalo")
            QMessageBox.critical(self, "Chyba připojení", msg)

    def _start_migration(self):
        self._save_config()
        sqlite_file = os.path.join(self.ctx.app_dir, "DATA", "ts_data.db")
        if not os.path.exists(sqlite_file):
            QMessageBox.critical(self, "Chyba", f"Zdrojová SQLite databáze nebyla nalezena:\n{sqlite_file}")
            return

        reply = QMessageBox.question(
            self,
            "Potvrdit převod do MariaDB",
            "Tato operace přenese všechny tabulky a data z lokální SQLite databáze do MariaDB na Synology.\n\n"
            "Chcete pokračovat?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes
        )
        if reply != QMessageBox.Yes:
            return

        self.btn_migrate.setEnabled(False)
        self.btn_activate.setEnabled(False)
        self.btn_test.setEnabled(False)
        self.txt_log.clear()
        self.progress_bar.setValue(0)

        host = self.edit_host.text().strip()
        port = self.spin_port.value()
        user = self.edit_user.text().strip()
        pwd = self.edit_password.text()
        db = self.edit_database.text().strip()

        self._worker = MigrationWorker(sqlite_file, host, port, user, pwd, db, parent=self)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.start()

    def _on_progress(self, pct: int, text: str):
        self.progress_bar.setValue(pct)
        self.lbl_status.setText(text)
        self.txt_log.append(f"[{pct}%] {text}")

    def _on_finished(self, ok: bool, msg: str, stats: dict):
        self.btn_migrate.setEnabled(True)
        self.btn_activate.setEnabled(True)
        self.btn_test.setEnabled(True)

        if ok:
            self.progress_bar.setValue(100)
            self.lbl_status.setText("Převod úspěšně dokončen!")
            log_summary = "\n".join(f"  • {tbl}: {cnt} záznamů" for tbl, cnt in stats.items())
            self.txt_log.append("\n=== PŘENENESENÁ DATA ===\n" + log_summary)

            ans = QMessageBox.question(
                self,
                "Převod dokončen",
                "Data byla úspěšně přenesena do MariaDB na Synology!\n\n"
                "Přejete si nyní aktivovat MariaDB jako výchozí databázi aplikace?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes
            )
            if ans == QMessageBox.Yes:
                self._activate_mariadb()
        else:
            self.lbl_status.setText("Chyba při převodu!")
            self.txt_log.append(f"\n[CHYBA] {msg}")
            QMessageBox.critical(self, "Chyba převodu", f"Během převodu došlo k chybě:\n\n{msg}")

    def _activate_mariadb(self):
        self._save_config()
        # Set backend in db_config.ini
        cp = configparser.ConfigParser()
        if os.path.exists(self._ini_path):
            cp.read(self._ini_path, encoding="utf-8")
        if not cp.has_section("database"):
            cp.add_section("database")
        cp.set("database", "backend", "mariadb")
        with open(self._ini_path, "w", encoding="utf-8") as f:
            cp.write(f)

        from PySide6.QtCore import QSettings
        settings = QSettings("TSSkleniky", "TS_Evidence")
        settings.setValue("db_backend", "mariadb")

        try:
            self.ctx.switch_database_backend("mariadb")
            self.lbl_status.setText("Aktivní databáze: MariaDB (Synology)")
            self.btn_activate.setEnabled(False)
            self.btn_switch_sqlite.setEnabled(True)
            QMessageBox.information(
                self,
                "Aktivováno",
                "Aplikace byla úspěšně přepnuta na centrální MariaDB na Synology NASu!\n"
                "Od této chvíle mohou obě PC pracovat současně."
            )
        except Exception as e:
            QMessageBox.critical(self, "Chyba přepnutí", f"Nelze se připojit k MariaDB:\n{e}")

    def _switch_to_sqlite(self):
        reply = QMessageBox.question(
            self,
            "Přepnout na lokální SQLite?",
            "Opravdu si přejete přepnout aplikaci zpět na lokální soubor SQLite?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        cp = configparser.ConfigParser()
        if os.path.exists(self._ini_path):
            cp.read(self._ini_path, encoding="utf-8")
        if not cp.has_section("database"):
            cp.add_section("database")
        cp.set("database", "backend", "sqlite")
        with open(self._ini_path, "w", encoding="utf-8") as f:
            cp.write(f)

        from PySide6.QtCore import QSettings
        settings = QSettings("TSSkleniky", "TS_Evidence")
        settings.setValue("db_backend", "sqlite")

        try:
            self.ctx.switch_database_backend("sqlite")
            self.lbl_status.setText("Aktivní databáze: SQLite (lokální)")
            self.btn_activate.setEnabled(True)
            self.btn_switch_sqlite.setEnabled(False)
            QMessageBox.information(self, "Přepnuto", "Aplikace byla přepnuta na lokální SQLite.")
        except Exception as e:
            QMessageBox.critical(self, "Chyba", str(e))
