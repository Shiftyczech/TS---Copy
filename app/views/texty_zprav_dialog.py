"""
Texty zpráv a dokumentů – Informační texty / E-Mail / SMS
Grid: Druh dokumentu | Způsob expedice + Opravit/Konec
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QHeaderView, QAbstractItemView, QMessageBox,
    QLabel, QTextEdit, QLineEdit
)
from PySide6.QtCore import Qt


TYP_LABELS = {
    "OR": ("Potvrzení objednávky", "Rozvoz"),
    "OV": ("Potvrzení objednávky", "Vlastní odvoz"),
    "ZR": ("Změna objednávky", "Rozvoz"),
    "ZV": ("Změna objednávky", "Vlastní odvoz"),
    "VR": ("Výzva k expedici", "Rozvoz"),
    "VV": ("Výzva k expedici", "Vlastní odvoz"),
}


class TextyZpravDialog(QDialog):
    def __init__(self, ctx, typ="info", parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self.typ = typ
        titles = {
            "info": "Informační texty dokumentů",
            "email": "Standardní texty E-Mail zpráv",
            "sms": "Standardní texty SMS zpráv",
        }
        self.setWindowTitle(titles.get(typ, "Texty zpráv"))
        self.setMinimumSize(700, 400)
        self.resize(700, 400)
        self._build_ui()
        self._load_data()

    def _build_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["Druh dokumentu", "Způsob expedice"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSortingEnabled(True)
        self.table.doubleClicked.connect(self._edit)
        layout.addWidget(self.table, stretch=3)

        btn_layout = QVBoxLayout()
        self.btn_opravit = QPushButton("Opravit")
        btn_layout.addWidget(self.btn_opravit)
        btn_layout.addStretch()
        self.btn_konec = QPushButton("Konec")
        self.btn_konec.setObjectName("dangerButton")
        btn_layout.addWidget(self.btn_konec)
        layout.addLayout(btn_layout)

        self.btn_opravit.clicked.connect(self._edit)
        self.btn_konec.clicked.connect(self.reject)

    def _load_data(self):
        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)
        rows = self.ctx.db.read_all("tsd07")
        for r in rows:
            typ = str(r.get("TYP", "")).strip()
            labels = TYP_LABELS.get(typ, (typ, ""))
            row = self.table.rowCount()
            self.table.insertRow(row)
            item_typ = QTableWidgetItem(labels[0])
            item_typ.setData(Qt.UserRole, typ)  # store raw TYP for lookup
            self.table.setItem(row, 0, item_typ)
            self.table.setItem(row, 1, QTableWidgetItem(labels[1]))
        self.table.setSortingEnabled(True)
        self.table.sortByColumn(0, Qt.AscendingOrder)

    def _edit(self):
        row = self.table.currentRow()
        if row < 0:
            return
        typ = self.table.item(row, 0).data(Qt.UserRole)

        record = self.ctx.db.read_by_key("tsd07", "TYP", typ)
        if not record:
            return

        # Determine which text field to edit based on dialog type
        text2 = None
        if self.typ == "email":
            text = str(record.get("TEXT_MAIL", ""))
            predmet = str(record.get("PREDMET_E", ""))
        elif self.typ == "sms":
            text = str(record.get("TEXT_SMS", ""))
            predmet = str(record.get("PREDMET_S", ""))
        else:  # info = document text (TEXT_POLE1 + TEXT_POLE2)
            text = str(record.get("TEXT_POLE1", ""))
            text2 = str(record.get("TEXT_POLE2", ""))
            predmet = ""

        label = TYP_LABELS.get(typ, (typ, ""))[0]
        dlg = EditTextDialog(typ=label, text=text, predmet=predmet, text2=text2, parent=self)
        if dlg.exec() == QDialog.Accepted:
            data = {}
            if self.typ == "email":
                data["TEXT_MAIL"] = dlg.txt_body.toPlainText()
                data["PREDMET_E"] = dlg.edit_predmet.text()
            elif self.typ == "sms":
                data["TEXT_SMS"] = dlg.txt_body.toPlainText()
                data["PREDMET_S"] = dlg.edit_predmet.text()
            else:
                data["TEXT_POLE1"] = dlg.txt_body.toPlainText()
                if text2 is not None:
                    data["TEXT_POLE2"] = dlg.txt_body2.toPlainText()
            self.ctx.db.update("tsd07", "TYP", typ, data)
            self._load_data()


class EditTextDialog(QDialog):
    def __init__(self, typ="", text="", predmet="", text2=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Úprava textu – {typ}")
        self.setMinimumSize(600, 500)
        layout = QVBoxLayout(self)

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Druh:"))
        row1.addWidget(QLabel(typ))
        row1.addStretch()
        layout.addLayout(row1)

        if predmet:
            row2 = QHBoxLayout()
            row2.addWidget(QLabel("Předmět:"))
            self.edit_predmet = QLineEdit(predmet)
            row2.addWidget(self.edit_predmet)
            layout.addLayout(row2)
        else:
            self.edit_predmet = QLineEdit()

        layout.addWidget(QLabel("Text 1 (Základní text):" if text2 is not None else "Text:"))
        self.txt_body = QTextEdit()
        self.txt_body.setPlainText(text)
        layout.addWidget(self.txt_body)
        
        if text2 is not None:
            layout.addWidget(QLabel("Text 2 (Doplňující text / Patička):"))
            self.txt_body2 = QTextEdit()
            self.txt_body2.setPlainText(text2)
            layout.addWidget(self.txt_body2)

        btn_row = QHBoxLayout()
        btn_ok = QPushButton("Uložit")
        btn_ok.setObjectName("accentButton")
        btn_cancel = QPushButton("Zpět")
        btn_ok.clicked.connect(self.accept)
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_ok)
        btn_row.addStretch()
        btn_row.addWidget(btn_cancel)
        layout.addLayout(btn_row)
