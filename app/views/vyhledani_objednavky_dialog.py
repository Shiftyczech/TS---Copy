"""
Vyhledání objednávky – lookup dialog for finding an order by number, name, etc.
Used by the "Oprava objednávky" menu action to select which order to edit.
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView
)
from PySide6.QtCore import Qt
import datetime
from app.views.sort_items import DateSortItem


class VyhledaniObjednavkyDialog(QDialog):
    """Small dialog that lets the user search for and select an existing order."""

    def __init__(self, ctx, source_table="tsd04", parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self.source_table = source_table
        self.selected_cislo = None
        self.setWindowTitle("Vyhledání objednávky")
        self.setMinimumSize(750, 450)
        self.resize(800, 500)
        self._build_ui()
        self._load_data()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        lbl = QLabel("Vyhledání objednávky")
        lbl.setObjectName("titleLabel")
        lbl.setAlignment(Qt.AlignCenter)
        layout.addWidget(lbl)

        search_row = QHBoxLayout()
        search_row.addWidget(QLabel("Hledat:"))
        self.edit_search = QLineEdit()
        self.edit_search.setPlaceholderText("Číslo obj., jméno, PSČ, pošta...")
        self.edit_search.textChanged.connect(self._filter)
        search_row.addWidget(self.edit_search)
        layout.addLayout(search_row)

        self.table = QTableWidget()
        cols = ["Č.obj.", "Jméno zákazníka", "Ulice", "PSČ", "Pošta", "Přijato"]
        self.table.setColumnCount(len(cols))
        self.table.setHorizontalHeaderLabels(cols)
        
        self.table.setColumnWidth(0, 60)   # Č.obj.
        self.table.setColumnWidth(1, 160)  # Jméno zákazníka
        self.table.setColumnWidth(2, 150)  # Ulice
        self.table.setColumnWidth(3, 65)   # PSČ
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch) # Pošta
        self.table.setColumnWidth(5, 90)   # Přijato
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.DoubleClicked | QTableWidget.EditKeyPressed)
        self.table.verticalHeader().setVisible(False)
        self.table.setSortingEnabled(True)
        self.table.itemChanged.connect(self._on_item_changed)
        layout.addWidget(self.table)

        self.lbl_count = QLabel("Počet: 0")
        layout.addWidget(self.lbl_count)

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
        all_rows = self.ctx.db.read_all(self.source_table)
        # Show only unresolved orders (no completion date) in the active table view
        if self.source_table == "tsd04":
            all_rows = [r for r in all_rows if not r.get("DATUM_VYR")]
        self._all_rows = all_rows
        self._display(self._all_rows)

    def _filter(self):
        search = self.edit_search.text().strip().lower()
        if not search:
            self._display(self._all_rows)
            return
        rows = [r for r in self._all_rows if
                search in str(r.get("CISLO_OBJ", "")).lower() or
                search in str(r.get("Z_JMENO", "")).lower() or
                search in str(r.get("Z_PSC", "")).lower() or
                search in str(r.get("Z_POSTA", "")).lower()]
        self._display(rows)

    def _display(self, rows):
        self.table.blockSignals(True)
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            vals = [
                str(r.get("CISLO_OBJ", "")),
                str(r.get("Z_JMENO", "")),
                str(r.get("Z_ULICE", "")),
                str(r.get("Z_PSC", "")),
                str(r.get("Z_POSTA", "")),
                self._fmt_date(r.get("DATUM_PR"))
            ]
            for j, v in enumerate(vals):
                if j == 5:
                    item = DateSortItem(v)
                else:
                    item = QTableWidgetItem(v)
                    
                if j in (1, 2, 3, 4):
                    item.setFlags(item.flags() | Qt.ItemIsEditable)
                else:
                    item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                self.table.setItem(i, j, item)
        self.table.setSortingEnabled(True)
        self.table.sortByColumn(5, Qt.DescendingOrder)
        self.lbl_count.setText(f"Počet: {len(rows)}")
        self.table.blockSignals(False)

    def _on_item_changed(self, item):
        row = item.row()
        col = item.column()
        cislo_item = self.table.item(row, 0)
        if not cislo_item:
            return
        cislo = cislo_item.text()
        
        field_map = {
            1: "Z_JMENO",
            2: "Z_ULICE",
            3: "Z_PSC",
            4: "Z_POSTA"
        }
        db_field = field_map.get(col)
        if not db_field:
            return
            
        new_val = item.text()
        self.ctx.db.update(self.source_table, "CISLO_OBJ", cislo, {db_field: new_val})
        self.ctx.invalidate_cache(self.source_table)
        
        for r in self._all_rows:
            if str(r.get("CISLO_OBJ", "")).strip() == cislo.strip():
                r[db_field] = new_val
                break

    @staticmethod
    def _fmt_date(d):
        if isinstance(d, (datetime.date, datetime.datetime)):
            return d.strftime("%d.%m.%Y")
        return str(d) if d else ""

    def _select(self):
        row = self.table.currentRow()
        if row < 0:
            return
        self.selected_cislo = self.table.item(row, 0).text()
        self.accept()
