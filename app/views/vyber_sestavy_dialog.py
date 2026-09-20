"""
Výběr sestavy – popup grid to pick a greenhouse set (tsd03)
Used from objednavka_dialog when adding an assembly to the order.
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView
)
from PySide6.QtCore import Qt
from app.views.sort_items import NumericSortItem


class VyberSestavyDialog(QDialog):
    def __init__(self, ctx, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self.setWindowTitle("Výběr sestavy")
        self.setMinimumSize(550, 400)
        self.resize(550, 450)
        self.selected = None  # dict with KOD, NAZEV, CENA
        self._build_ui()
        self._load_data()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        search_row = QHBoxLayout()
        search_row.addWidget(QLabel("Hledat:"))
        self.edit_search = QLineEdit()
        self.edit_search.textChanged.connect(self._filter)
        search_row.addWidget(self.edit_search)
        layout.addLayout(search_row)

        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Kód", "Název sestavy", "Cena"])
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setSortingEnabled(True)
        self.table.doubleClicked.connect(self._select)
        layout.addWidget(self.table)

        btn_row = QHBoxLayout()
        btn_ok = QPushButton("Vybrat")
        btn_ok.setObjectName("accentButton")
        btn_cancel = QPushButton("Zpět")
        btn_row.addWidget(btn_ok)
        btn_row.addWidget(btn_cancel)
        layout.addLayout(btn_row)

        btn_ok.clicked.connect(self._select)
        btn_cancel.clicked.connect(self.reject)

    def _load_data(self):
        self._all_rows = self.ctx.db.read_all("tsd02")
        self._display(self._all_rows)

    def _filter(self, text):
        if not text:
            self._display(self._all_rows)
            return
        ft = text.lower()
        filtered = [r for r in self._all_rows
                    if ft in str(r.get("KOD", "")).lower()
                    or ft in str(r.get("NAZEV", "")).lower()]
        self._display(filtered)

    def _display(self, rows):
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            self.table.setItem(i, 0, NumericSortItem(str(r.get("KOD", ""))))
            self.table.setItem(i, 1, QTableWidgetItem(str(r.get("NAZEV", ""))))
            self.table.setItem(i, 2, NumericSortItem(str(r.get("CENA", ""))))
        self.table.setSortingEnabled(True)

    def _select(self):
        row = self.table.currentRow()
        if row < 0:
            return
        self.selected = {
            "KOD": self.table.item(row, 0).text(),
            "NAZEV": self.table.item(row, 1).text(),
            "CENA": self.table.item(row, 2).text(),
        }
        self.accept()
