"""
Migrace DB Dialog – Tool for converting legacy FoxPro DBF tables to high-performance SQLite database.
Runs in background QThread with progress bar, backup creation, and live log.
"""
import os
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QProgressBar, QTextEdit, QMessageBox, QGroupBox, QFormLayout
)
from PySide6.QtCore import Qt, QThread, Signal
from app.services.migration_service import MigrationService


class MigrationWorker(QThread):
    progress = Signal(int, str)
    finished = Signal(bool, str, dict)

    def __init__(self, data_path: str, backup_dir: str, create_backup: bool = True, parent=None):
        super().__init__(parent)
        self.data_path = data_path
        self.backup_dir = backup_dir
        self.create_backup = create_backup

    def run(self):
        try:
            svc = MigrationService(self.data_path)
            if self.create_backup:
                self.progress.emit(2, "Vytváření bezpečnostní zálohy složky DATA...")
                zip_path = svc.create_pre_migration_backup(self.backup_dir)
                msg = f"Záloha vytvořena: {os.path.basename(zip_path)}"
            else:
                msg = ""

            def on_progress(pct, text):
                self.progress.emit(pct, text)

            stats = svc.migrate(progress_callback=on_progress)
            self.finished.emit(True, msg, stats)
        except Exception as e:
            self.finished.emit(False, str(e), {})


class MigraceDbDialog(QDialog):
    def __init__(self, ctx, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self.setWindowTitle("Převod databáze do SQLite")
        self.setMinimumSize(560, 480)
        self.resize(600, 520)
        self._worker = None
        self._build_ui()
        self._update_status()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        title = QLabel("Převod databáze do SQLite")
        title.setObjectName("titleLabel")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        desc = QLabel(
            "Tento nástroj převede všechny původní tabulky FoxPro (DBF/FPT) do moderní "
            "vysokorychlostní databáze SQLite.\n\n"
            "• Radikálně zrychlí načítání i ukládání objednávek a rozvozních plánů.\n"
            "• Vyčistí statisíce starých smazaných záznamů.\n"
            "• Před zahájením převodu se automaticky vytvoří kompletní ZIP záloha."
        )
        desc.setWordWrap(True)
        layout.addWidget(desc)

        # Status Box
        grp_status = QGroupBox("Aktuální stav")
        status_form = QFormLayout(grp_status)
        self.lbl_backend = QLabel("")
        self.lbl_backend.setStyleSheet("font-weight: bold;")
        self.lbl_db_size = QLabel("")
        self.lbl_orders_count = QLabel("")

        status_form.addRow("Aktivní databáze:", self.lbl_backend)
        status_form.addRow("Velikost SQLite databáze:", self.lbl_db_size)
        status_form.addRow("Počet objednávek v DB:", self.lbl_orders_count)
        layout.addWidget(grp_status)

        # Progress Box
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        layout.addWidget(self.progress_bar)

        self.lbl_status = QLabel("Připraveno.")
        self.lbl_status.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.lbl_status)

        # Log
        self.txt_log = QTextEdit()
        self.txt_log.setReadOnly(True)
        self.txt_log.setPlaceholderText("Zde se zobrazí podrobnosti o průběhu převodu...")
        layout.addWidget(self.txt_log)

        # Buttons
        btn_layout = QHBoxLayout()
        self.btn_start = QPushButton("Spustit převod do SQLite")
        self.btn_start.setObjectName("accentButton")
        self.btn_start.clicked.connect(self._start_migration)
        btn_layout.addWidget(self.btn_start)

        self.btn_switch = QPushButton("Přepnout databázi")
        self.btn_switch.clicked.connect(self._toggle_backend)
        btn_layout.addWidget(self.btn_switch)

        self.btn_close = QPushButton("Zavřít")
        self.btn_close.clicked.connect(self.accept)
        btn_layout.addWidget(self.btn_close)

        layout.addLayout(btn_layout)

    def _update_status(self):
        backend = getattr(self.ctx, "backend_name", "dbf").upper()
        if backend == "SQLITE":
            self.lbl_backend.setText("SQLite (Vysokorychlostní režim)")
            self.lbl_backend.setStyleSheet("color: #4CAF50; font-weight: bold;")
            self.btn_switch.setText("Přepnout zpět na DBF")
        else:
            self.lbl_backend.setText("FoxPro DBF (Původní režim)")
            self.lbl_backend.setStyleSheet("color: #FFA726; font-weight: bold;")
            self.btn_switch.setText("Přepnout na SQLite")

        data_dir = os.path.join(self.ctx.app_dir, "DATA")
        sqlite_path = os.path.join(data_dir, "ts_data.db")
        if os.path.exists(sqlite_path):
            size_mb = os.path.getsize(sqlite_path) / (1024 * 1024)
            self.lbl_db_size.setText(f"{size_mb:.2f} MB ({sqlite_path})")
            self.btn_switch.setEnabled(True)
        else:
            self.lbl_db_size.setText("Neexistuje (je nutné provést převod)")
            self.btn_switch.setEnabled(False)

        try:
            cnt = self.ctx.db.count("tsd04")
            self.lbl_orders_count.setText(f"{cnt} aktivních objednávek")
        except Exception:
            self.lbl_orders_count.setText("Nelze zjistit")

    def _toggle_backend(self):
        current = getattr(self.ctx, "backend_name", "dbf")
        target = "dbf" if current == "sqlite" else "sqlite"

        if target == "sqlite":
            data_dir = os.path.join(self.ctx.app_dir, "DATA")
            sqlite_path = os.path.join(data_dir, "ts_data.db")
            if not os.path.exists(sqlite_path) or os.path.getsize(sqlite_path) < 1000:
                QMessageBox.warning(self, "Chyba", "Databáze SQLite ještě nebyla vytvořena. Nejprve spusťte převod.")
                return

        if hasattr(self.ctx, "switch_database_backend"):
            self.ctx.switch_database_backend(target)
            self._update_status()
            QMessageBox.information(
                self, "Změna databáze",
                f"Aplikace byla úspěšně přepnuta na {target.upper()} databázi."
            )

    def _start_migration(self):
        reply = QMessageBox.question(
            self,
            "Potvrzení převodu",
            "Opravdu si přejete zahájit převod dat z DBF do SQLite?\n\n"
            "Před převodem bude automaticky vytvořena bezpečnostní záloha stávající složky DATA.\n"
            "Proces může trvat cca 15–30 sekund.",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        self.btn_start.setEnabled(False)
        self.btn_switch.setEnabled(False)
        self.btn_close.setEnabled(False)
        self.progress_bar.setValue(0)
        self.txt_log.clear()
        self.txt_log.append("Zahajuji proces převodu...")

        data_dir = os.path.join(self.ctx.app_dir, "DATA")
        backup_dir = os.path.join(self.ctx.app_dir, "Zaloha")

        self._worker = MigrationWorker(data_dir, backup_dir, create_backup=True, parent=self)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.start()

    def _on_progress(self, pct: int, text: str):
        self.progress_bar.setValue(pct)
        self.lbl_status.setText(text)
        self.txt_log.append(f"[{pct}%] {text}")

    def _on_finished(self, ok: bool, msg: str, stats: dict):
        self.btn_start.setEnabled(True)
        self.btn_switch.setEnabled(True)
        self.btn_close.setEnabled(True)
        self._worker = None

        if not ok:
            self.lbl_status.setText("Chyba při převodu!")
            self.txt_log.append(f"\nCHYBA: {msg}")
            QMessageBox.critical(self, "Chyba převodu", f"Při převodu došlo k chybě:\n{msg}")
            return

        self.lbl_status.setText("Převod dokončen úspěšně!")
        self.txt_log.append("\n" + "=" * 45)
        self.txt_log.append("PŘEVOD DOKONČEN ÚSPĚŠNĚ!")
        if msg:
            self.txt_log.append(msg)
        self.txt_log.append("Převedené tabulky a počty platných záznamů:")
        for tbl, count in stats.items():
            self.txt_log.append(f"  • {tbl.upper():<10} : {count:>6} záznamů")
        self.txt_log.append("=" * 45)

        # Automatically switch to SQLite backend
        if hasattr(self.ctx, "switch_database_backend"):
            self.ctx.switch_database_backend("sqlite")

        self._update_status()

        QMessageBox.information(
            self,
            "Převod dokončen",
            "Převod do SQLite byl úspěšně dokončen!\n\n"
            "Aplikace byla automaticky přepnuta do vysokorychlostního režimu SQLite.\n"
            "Načítání a ukládání objednávek je nyní bleskové."
        )
