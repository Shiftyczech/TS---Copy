"""
Zpětný převod z archivu – select archived orders to move back to active.
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QMessageBox, QProgressDialog
)
from PySide6.QtCore import Qt
import datetime
from app.views.sort_items import DateSortItem


class ArchivZpetnyDialog(QDialog):
    def __init__(self, ctx, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self.setWindowTitle("Zpětný převod z archivu")
        self.setMinimumSize(900, 500)
        self.resize(1000, 550)
        self._build_ui()
        self._load_data()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        lbl = QLabel("Vyberte objednávky k převodu zpět")
        lbl.setObjectName("titleLabel")
        lbl.setAlignment(Qt.AlignCenter)
        layout.addWidget(lbl)

        self.table = QTableWidget()
        cols = ["Č.obj.", "Jméno zákazníka", "Ulice", "PSČ", "Pošta",
                "Telefon", "Přijato", "Vyřízeno"]
        self.table.setColumnCount(len(cols))
        self.table.setHorizontalHeaderLabels(cols)
        
        self.table.setColumnWidth(0, 60)   # Č.obj.
        self.table.setColumnWidth(1, 160)  # Jméno zákazníka
        self.table.setColumnWidth(2, 150)  # Ulice
        self.table.setColumnWidth(3, 65)   # PSČ
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch) # Pošta
        self.table.setColumnWidth(5, 100)  # Telefon
        self.table.setColumnWidth(6, 90)   # Přijato
        self.table.setColumnWidth(7, 100)  # Vyřízeno
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.MultiSelection)
        self.table.setEditTriggers(QTableWidget.DoubleClicked | QTableWidget.EditKeyPressed)
        self.table.setSortingEnabled(True)
        self.table.itemChanged.connect(self._on_item_changed)
        layout.addWidget(self.table)

        self.lbl_count = QLabel("Počet: 0")
        layout.addWidget(self.lbl_count)

        btn_row = QHBoxLayout()
        self.btn_prevod = QPushButton("Převést zpět")
        self.btn_prevod.setObjectName("accentButton")
        self.btn_close = QPushButton("Konec")
        btn_row.addWidget(self.btn_prevod)
        btn_row.addWidget(self.btn_close)
        layout.addLayout(btn_row)

        self.btn_prevod.clicked.connect(self._do_transfer)
        self.btn_close.clicked.connect(self.accept)

    def _load_data(self):
        self._all_rows = self.ctx.db.read_all("tsd06")
        self.table.blockSignals(True)
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(self._all_rows))
        for i, r in enumerate(self._all_rows):
            vals = [
                str(r.get("CISLO_OBJ", "")),
                str(r.get("Z_JMENO", "")),
                str(r.get("Z_ULICE", "")),
                str(r.get("Z_PSC", "")),
                str(r.get("Z_POSTA", "")),
                str(r.get("TELEFON", "")),
                self._fmt_date(r.get("DATUM_PR")),
                self._fmt_date(r.get("DATUM_VYR")),
            ]
            for j, v in enumerate(vals):
                item = DateSortItem(v) if j in (6, 7) else QTableWidgetItem(v)
                
                if j in (1, 2, 3, 4, 5):
                    item.setFlags(item.flags() | Qt.ItemIsEditable)
                else:
                    item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                    
                if j == 0:
                    item.setData(Qt.UserRole, i)  # store original index
                self.table.setItem(i, j, item)
        self.table.setSortingEnabled(True)
        self.table.sortByColumn(6, Qt.DescendingOrder)
        self.lbl_count.setText(f"Počet: {len(self._all_rows)}")
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
            4: "Z_POSTA",
            5: "TELEFON"
        }
        db_field = field_map.get(col)
        if not db_field:
            return
            
        new_val = item.text()
        self.ctx.db.update("tsd06", "CISLO_OBJ", cislo, {db_field: new_val})
        self.ctx.invalidate_cache("tsd06")
        
        for r in self._all_rows:
            if str(r.get("CISLO_OBJ", "")).strip() == cislo.strip():
                r[db_field] = new_val
                break

    @staticmethod
    def _fmt_date(d):
        if isinstance(d, (datetime.date, datetime.datetime)):
            return d.strftime("%d.%m.%Y")
        return str(d) if d else ""

    def _do_transfer(self):
        selected_rows = set(idx.row() for idx in self.table.selectedIndexes())
        if not selected_rows:
            QMessageBox.warning(self, "Převod", "Vyberte alespoň jednu objednávku.")
            return
        if QMessageBox.question(
            self, "Zpětný převod",
            f"Převést {len(selected_rows)} objednávek zpět z archivu?",
            QMessageBox.Yes | QMessageBox.No
        ) != QMessageBox.Yes:
            return

        selected_indices = []
        for row in selected_rows:
            item = self.table.item(row, 0)
            if item:
                orig_idx = item.data(Qt.UserRole)
                if orig_idx is not None:
                    selected_indices.append(orig_idx)

        if not selected_indices:
            return

        orders = [self._all_rows[i] for i in selected_indices]
        cisla = {str(o.get("CISLO_OBJ", "")).strip() for o in orders}

        progress = QProgressDialog("Převod z archivu...", None, 0, 0, self)
        progress.setWindowTitle("Zpětný převod")
        progress.setWindowModality(Qt.WindowModal)
        progress.setMinimumDuration(0)
        progress.setValue(0)

        def do_transfer(progress_cb):
            progress_cb(0, "Načítání položek...")
            items_by_cislo = self.ctx.db.read_where_in("tsd06a", "CISLO_OBJ", cisla)
            details_by_cislo = self.ctx.db.read_where_in("tsd06b", "CISLO_OBJ", cisla)

            progress_cb(1, "Kopírování do aktivních tabulek...")
            self.ctx.db.batch_insert("tsd04", orders)
            all_items = [it for lst in items_by_cislo.values() for it in lst]
            all_details = [dt for lst in details_by_cislo.values() for dt in lst]
            self.ctx.db.batch_insert("tsd04a", all_items)
            self.ctx.db.batch_insert("tsd04b", all_details)

            progress_cb(2, "Mazání z archivu...")
            self.ctx.db.batch_delete("tsd06", "CISLO_OBJ", cisla)
            self.ctx.db.batch_delete("tsd06a", "CISLO_OBJ", cisla)
            self.ctx.db.batch_delete("tsd06b", "CISLO_OBJ", cisla)
            return len(orders)

        from app.services.db_worker import DbWorker
        self._worker = DbWorker(do_transfer)

        def on_finished(ok, msg, result):
            progress.close()
            self._worker = None
            if ok:
                QMessageBox.information(self, "Převod", f"Zpět převedeno {result} objednávek.")
            else:
                QMessageBox.warning(self, "Chyba", f"Chyba při převodu: {msg}")
            self._load_data()

        self._worker.progress.connect(lambda step, lbl: progress.setLabelText(lbl))
        self._worker.finished.connect(on_finished)
        self._worker.start()
