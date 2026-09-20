"""
Uživatelé – Grid (Os.číslo / Příjmení a jméno) + Opravit / Přidat / Vymazat / Konec
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QMessageBox, QFormLayout
)
from PySide6.QtCore import Qt


class UzivateleDialog(QDialog):
    def __init__(self, ctx, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self.setWindowTitle("Uživatelé")
        self.setMinimumSize(500, 400)
        self.resize(500, 400)
        self._build_ui()
        self._load_data()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        lbl = QLabel("Uživatelé")
        lbl.setObjectName("titleLabel")
        lbl.setAlignment(Qt.AlignCenter)
        layout.addWidget(lbl)

        self.table = QTableWidget()
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["Os.číslo", "Příjmení a jméno"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSortingEnabled(True)
        self.table.doubleClicked.connect(self._edit)
        layout.addWidget(self.table)

        btn_row = QHBoxLayout()
        self.btn_edit = QPushButton("Opravit")
        self.btn_add = QPushButton("Přidat")
        self.btn_del = QPushButton("Vymazat")
        self.btn_del.setObjectName("dangerButton")
        self.btn_close = QPushButton("Konec")
        for b in [self.btn_edit, self.btn_add, self.btn_del, self.btn_close]:
            btn_row.addWidget(b)
        layout.addLayout(btn_row)

        self.btn_edit.clicked.connect(self._edit)
        self.btn_add.clicked.connect(self._add)
        self.btn_del.clicked.connect(self._delete)
        self.btn_close.clicked.connect(self.accept)

    def _load_data(self):
        rows = self.ctx.db.read_all("tsd01a")
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            self.table.setItem(i, 0, QTableWidgetItem(str(r.get("KOD", ""))))
            self.table.setItem(i, 1, QTableWidgetItem(str(r.get("JMENO", ""))))
        self.table.setSortingEnabled(True)
        self.table.sortByColumn(1, Qt.AscendingOrder)

    def _selected_row(self):
        sel = self.table.currentRow()
        if sel < 0:
            QMessageBox.warning(self, "Uživatelé", "Vyberte uživatele.")
            return None
        return sel

    def _edit(self):
        row = self._selected_row()
        if row is None:
            return
        kod = self.table.item(row, 0).text()
        rec = self.ctx.db.read_by_key("tsd01a", "KOD", kod)
        if not rec:
            return
        dlg = EditUzivatelDialog(rec[0] if isinstance(rec, list) else rec, self)
        if dlg.exec() == QDialog.Accepted:
            data = dlg.get_data()
            self.ctx.db.update("tsd01a", "KOD", kod, data)
            self._load_data()

    def _add(self):
        dlg = EditUzivatelDialog(None, self)
        if dlg.exec() == QDialog.Accepted:
            data = dlg.get_data()
            self.ctx.db.insert("tsd01a", data)
            self._load_data()

    def _delete(self):
        row = self._selected_row()
        if row is None:
            return
        kod = self.table.item(row, 0).text()
        jmeno = self.table.item(row, 1).text()
        if QMessageBox.question(
            self, "Potvrzení", f"Opravdu vymazat uživatele {jmeno}?",
            QMessageBox.Yes | QMessageBox.No
        ) == QMessageBox.Yes:
            self.ctx.db.delete("tsd01a", "KOD", kod)
            self._load_data()


class EditUzivatelDialog(QDialog):
    def __init__(self, record=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Uživatel" if record else "Nový uživatel")
        self.setMinimumWidth(350)
        self.record = record
        self._build_ui()
        if record:
            self._fill(record)

    def _build_ui(self):
        layout = QFormLayout(self)
        self.edit_kod = QLineEdit()
        self.edit_kod.setMaximumWidth(60)
        self.edit_jmeno = QLineEdit()
        self.edit_heslo = QLineEdit()
        self.edit_heslo.setEchoMode(QLineEdit.Password)
        self.edit_pravo = QLineEdit()
        self.edit_pravo.setMaximumWidth(60)
        layout.addRow("Os.číslo:", self.edit_kod)
        layout.addRow("Příjmení a jméno:", self.edit_jmeno)
        layout.addRow("Heslo:", self.edit_heslo)
        layout.addRow("Právo:", self.edit_pravo)

        btn_row = QHBoxLayout()
        btn_ok = QPushButton("Uložit")
        btn_ok.setObjectName("accentButton")
        btn_cancel = QPushButton("Zpět")
        btn_row.addWidget(btn_ok)
        btn_row.addWidget(btn_cancel)
        layout.addRow(btn_row)

        btn_ok.clicked.connect(self.accept)
        btn_cancel.clicked.connect(self.reject)

    def _fill(self, rec):
        self.edit_kod.setText(str(rec.get("KOD", "")))
        self.edit_jmeno.setText(str(rec.get("JMENO", "")))
        self.edit_heslo.setText(str(rec.get("HESLO", "")))
        self.edit_pravo.setText(str(rec.get("PRAVO", "")))

    def get_data(self):
        return {
            "KOD": self.edit_kod.text().strip(),
            "JMENO": self.edit_jmeno.text().strip(),
            "HESLO": self.edit_heslo.text().strip(),
            "PRAVO": self.edit_pravo.text().strip(),
        }
