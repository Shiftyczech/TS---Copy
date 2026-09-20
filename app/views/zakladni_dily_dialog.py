"""
Základní díly a doplňky – Grid + CRUD buttons
Columns: Číslo*, Název základního dílu nebo doplňku*, Cena, Symbol, Pozice
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QHeaderView, QAbstractItemView, QMessageBox,
    QLabel, QLineEdit, QFormLayout
)
from PySide6.QtCore import Qt
from app.views.sort_items import NumericSortItem


class ZakladniDilyDialog(QDialog):
    def __init__(self, ctx, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self.setWindowTitle("Aktualizace základních dílů a doplňků")
        self.setMinimumSize(880, 500)
        self.resize(880, 500)
        self._build_ui()
        self._load_data()

    def _build_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Číslo*", "Název základního dílu nebo doplňku*", "Cena", "Symbol", "Pozice"])
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setSortingEnabled(True)
        self.table.doubleClicked.connect(self._edit)
        layout.addWidget(self.table, stretch=3)

        btn_layout = QVBoxLayout()
        self.btn_opravit = QPushButton("Opravit")
        self.btn_pridat = QPushButton("Přidat")
        self.btn_vymazat = QPushButton("Vymazat")
        btn_layout.addWidget(self.btn_opravit)
        btn_layout.addWidget(self.btn_pridat)
        btn_layout.addWidget(self.btn_vymazat)
        btn_layout.addStretch()
        self.btn_konec = QPushButton("Konec")
        self.btn_konec.setObjectName("dangerButton")
        btn_layout.addWidget(self.btn_konec)
        layout.addLayout(btn_layout)

        self.btn_opravit.clicked.connect(self._edit)
        self.btn_pridat.clicked.connect(self._add)
        self.btn_vymazat.clicked.connect(self._delete)
        self.btn_konec.clicked.connect(self.reject)

    def _load_data(self):
        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)
        rows = self.ctx.db.read_all("tsd03")
        for r in rows:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, NumericSortItem(str(r.get("KOD", ""))))
            self.table.setItem(row, 1, QTableWidgetItem(str(r.get("NAZEV", ""))))
            self.table.setItem(row, 2, NumericSortItem(str(r.get("CENA", 0))))
            self.table.setItem(row, 3, QTableWidgetItem(str(r.get("SYMBOL", ""))))
            self.table.setItem(row, 4, QTableWidgetItem(str(r.get("POZICE", ""))))
        self.table.setSortingEnabled(True)
        self.table.sortByColumn(1, Qt.AscendingOrder)

    def _add(self):
        dlg = EditDilDialog(self.ctx, is_new=True, parent=self)
        if dlg.exec() == QDialog.Accepted:
            data = dlg.get_data()
            self.ctx.db.insert("tsd03", data)
            self._load_data()

    def _edit(self):
        row = self.table.currentRow()
        if row < 0:
            return
        kod = self.table.item(row, 0).text()
        nazev = self.table.item(row, 1).text()
        cena = self.table.item(row, 2).text()
        symbol = self.table.item(row, 3).text() if self.table.item(row, 3) else ""
        pozice = self.table.item(row, 4).text() if self.table.item(row, 4) else ""
        dlg = EditDilDialog(self.ctx, kod=kod, nazev=nazev, cena=cena, symbol=symbol, pozice=pozice, is_new=False, parent=self)
        if dlg.exec() == QDialog.Accepted:
            data = dlg.get_data()
            self.ctx.db.update("tsd03", "KOD", int(kod), data)
            self._load_data()

    def _delete(self):
        row = self.table.currentRow()
        if row < 0:
            return
        kod = self.table.item(row, 0).text()
        nazev = self.table.item(row, 1).text()
        
        if self.ctx.db.read_where("tsd04b", {"KOD": int(kod)}):
            QMessageBox.warning(self, "Chyba", "Díl nelze vymazat, protože je použit v aktivních objednávkách (tsd06b).")
            return
        if self.ctx.db.read_where("tsd02a", {"KOD": int(kod)}):
            QMessageBox.warning(self, "Chyba", "Díl nelze vymazat, protože je součástí některé sestavy (tsd02a).")
            return
            
        reply = QMessageBox.question(self, "Potvrzení",
                                      f"Opravdu vymazat díl '{nazev}'?")
        if reply == QMessageBox.Yes:
            self.ctx.db.delete("tsd03", "KOD", int(kod))
            self._load_data()


class EditDilDialog(QDialog):
    def __init__(self, ctx=None, kod="", nazev="", cena="0", symbol="", pozice="", is_new=False, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self.is_new = is_new
        self.setWindowTitle("Díl / doplněk")
        self.setMinimumWidth(400)
        layout = QFormLayout(self)
        self.edit_kod = QLineEdit(str(kod))
        self.edit_nazev = QLineEdit(nazev)
        self.edit_cena = QLineEdit(str(cena))
        self.edit_symbol = QLineEdit(symbol)
        self.edit_symbol.setMaxLength(1)
        self.edit_pozice = QLineEdit(pozice)
        layout.addRow("Číslo:", self.edit_kod)
        layout.addRow("Název:", self.edit_nazev)
        layout.addRow("Cena:", self.edit_cena)
        layout.addRow("Symbol:", self.edit_symbol)
        layout.addRow("Pozice:", self.edit_pozice)

        btn_row = QHBoxLayout()
        btn_ok = QPushButton("OK")
        btn_ok.setObjectName("accentButton")
        btn_cancel = QPushButton("Storno")
        btn_ok.clicked.connect(self.accept)
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_ok)
        btn_row.addWidget(btn_cancel)
        layout.addRow(btn_row)

    def accept(self):
        try:
            kod = int(self.edit_kod.text() or 0)
        except ValueError:
            QMessageBox.warning(self, "Chyba", "Kód musí být celé číslo.")
            return
            
        if self.is_new and self.ctx and self.ctx.db.read_where("tsd03", {"KOD": kod}):
            QMessageBox.warning(self, "Chyba", f"Zadaný kód {kod} již existuje!")
            return
            
        super().accept()

    def get_data(self) -> dict:
        return {
            "KOD": int(self.edit_kod.text() or 0),
            "NAZEV": self.edit_nazev.text().strip(),
            "CENA": float(self.edit_cena.text() or 0),
            "SYMBOL": self.edit_symbol.text().strip()[:1],
            "POZICE": self.edit_pozice.text().strip(),
        }
