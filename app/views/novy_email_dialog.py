"""
Nový email – compose a free-form email to a customer (optionally linked to an order).
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTextEdit, QMessageBox, QCompleter
)
from PySide6.QtCore import Qt
from datetime import datetime


class NovyEmailDialog(QDialog):
    def __init__(self, ctx, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self.setWindowTitle("Nový email")
        self.setMinimumSize(600, 450)
        self.resize(650, 480)
        self._build_customer_cache()
        self._build_ui()

    def _build_customer_cache(self):
        self._customers = {}
        for table in ("tsd04", "tsd06"):
            try:
                rows = self.ctx.db.read_all(table)
            except Exception:
                continue
            for r in rows:
                cislo = str(r.get("CISLO_OBJ", "")).strip()
                name = str(r.get("Z_JMENO", "")).strip()
                email = str(r.get("E_MAIL", "")).strip()
                if name:
                    self._customers[name] = {
                        "CISLO_OBJ": cislo,
                        "Z_JMENO": name,
                        "E_MAIL": email,
                    }

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)

        # Číslo objednávky
        row_cislo = QHBoxLayout()
        row_cislo.addWidget(QLabel("Číslo obj.:"))
        self.edit_cislo = QLineEdit()
        self.edit_cislo.setMaximumWidth(120)
        self.edit_cislo.setPlaceholderText("nepovinné")
        row_cislo.addWidget(self.edit_cislo)
        row_cislo.addStretch()
        layout.addLayout(row_cislo)

        # Komu (jméno s autocomplete)
        row_komu = QHBoxLayout()
        row_komu.addWidget(QLabel("Komu:"))
        self.edit_komu = QLineEdit()
        names = list(self._customers.keys())
        completer = QCompleter(names, self)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        completer.setFilterMode(Qt.MatchContains)
        self.edit_komu.setCompleter(completer)
        completer.activated.connect(self._on_customer_selected)
        row_komu.addWidget(self.edit_komu)
        layout.addLayout(row_komu)

        # Email adresa
        row_email = QHBoxLayout()
        row_email.addWidget(QLabel("Email:"))
        self.edit_email = QLineEdit()
        row_email.addWidget(self.edit_email)
        layout.addLayout(row_email)

        # Předmět
        row_predmet = QHBoxLayout()
        row_predmet.addWidget(QLabel("Předmět:"))
        self.edit_predmet = QLineEdit()
        row_predmet.addWidget(self.edit_predmet)
        layout.addLayout(row_predmet)

        # Zpráva
        layout.addWidget(QLabel("Zpráva:"))
        self.txt_zprava = QTextEdit()
        layout.addWidget(self.txt_zprava)

        # Buttons
        btn_row = QHBoxLayout()
        self.btn_ulozit = QPushButton("Uložit k odeslání")
        self.btn_ulozit.setObjectName("accentButton")
        self.btn_zrusit = QPushButton("Zrušit")
        btn_row.addWidget(self.btn_ulozit)
        btn_row.addStretch()
        btn_row.addWidget(self.btn_zrusit)
        layout.addLayout(btn_row)

        self.btn_ulozit.clicked.connect(self._save)
        self.btn_zrusit.clicked.connect(self.reject)

    def _on_customer_selected(self, name):
        entry = self._customers.get(name)
        if entry:
            self.edit_email.setText(entry.get("E_MAIL", ""))
            cislo = entry.get("CISLO_OBJ", "")
            if cislo and not self.edit_cislo.text().strip():
                self.edit_cislo.setText(cislo)

    def _save(self):
        komu = self.edit_komu.text().strip()
        email = self.edit_email.text().strip()
        predmet = self.edit_predmet.text().strip()
        zprava = self.txt_zprava.toPlainText().strip()

        if not email:
            QMessageBox.warning(self, "Chyba", "Vyplňte emailovou adresu.")
            return
        if not predmet:
            QMessageBox.warning(self, "Chyba", "Vyplňte předmět zprávy.")
            return

        cislo_text = self.edit_cislo.text().strip()
        try:
            cislo_obj = int(cislo_text) if cislo_text else 0
        except ValueError:
            QMessageBox.warning(self, "Chyba", "Číslo objednávky musí být číslo.")
            return

        data = {
            "TYP": "E",
            "CISLO_OBJ": cislo_obj,
            "KOMU_JMENO": komu,
            "KOMU_MAIL": email,
            "PREDMET": predmet,
            "ZPRAVA": zprava,
            "VYTVORENO": datetime.now(),
            "TYP_ZPRAVY": "E",
            "PRILOHA": "",
            "PLANY": "",
        }
        try:
            self.ctx.db.insert("tsd08", data)
            QMessageBox.information(self, "Uloženo", "Email byl zařazen k odeslání.")
            self.accept()
        except Exception as e:
            QMessageBox.warning(self, "Chyba", f"Nepodařilo se uložit: {e}")
