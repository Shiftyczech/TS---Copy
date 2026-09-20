"""
Skleníkové sestavy – Master-detail dialog
Top: Sestavy grid + buttons
Bottom: Díly of selected sestava + buttons
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QHeaderView, QAbstractItemView, QMessageBox,
    QLabel, QLineEdit, QFormLayout, QSplitter, QWidget
)
from PySide6.QtCore import Qt
from app.views.sort_items import NumericSortItem


class SklenikoveSestavyDialog(QDialog):
    def __init__(self, ctx, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self.setWindowTitle("Skleníkové sestavy")
        self.setMinimumSize(920, 580)
        self.resize(920, 580)
        self._build_ui()
        self._load_sestavy()

    def _build_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)

        left_layout = QVBoxLayout()

        # Top: Sestavy
        self.tbl_sestavy = QTableWidget(0, 5)
        self.tbl_sestavy.setHorizontalHeaderLabels(["Číslo*", "Název sestavy*", "Cena", "Základy", "Symbol"])
        self.tbl_sestavy.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.tbl_sestavy.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tbl_sestavy.setAlternatingRowColors(True)
        self.tbl_sestavy.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tbl_sestavy.verticalHeader().setVisible(False)
        self.tbl_sestavy.setSortingEnabled(True)
        self.tbl_sestavy.currentCellChanged.connect(self._on_sestava_selected)
        self.tbl_sestavy.doubleClicked.connect(self._edit_sestava)
        left_layout.addWidget(self.tbl_sestavy)

        # Label: Sestava: [název]
        self.lbl_sestava = QLabel("Sestava:")
        self.lbl_sestava.setObjectName("sectionLabel")
        left_layout.addWidget(self.lbl_sestava)

        # Bottom: Díly
        self.tbl_dily = QTableWidget(0, 4)
        self.tbl_dily.setHorizontalHeaderLabels(["Číslo", "Název dílu", "Cena", "Množství"])
        self.tbl_dily.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.tbl_dily.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tbl_dily.verticalHeader().setVisible(False)
        self.tbl_dily.setAlternatingRowColors(True)
        self.tbl_dily.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tbl_dily.setSortingEnabled(True)
        self.tbl_dily.doubleClicked.connect(self._edit_dil)
        left_layout.addWidget(self.tbl_dily)

        main_layout.addLayout(left_layout, stretch=3)

        # Right: buttons
        btn_layout = QVBoxLayout()

        self.btn_opravit_sestavu = QPushButton("Opravit sestavu")
        self.btn_pridat_sestavu = QPushButton("Přidat sestavu")
        self.btn_vymazat_sestavu = QPushButton("Vymazat sestavu")
        self.btn_konec = QPushButton("Konec")
        self.btn_konec.setObjectName("dangerButton")

        btn_layout.addWidget(self.btn_opravit_sestavu)
        btn_layout.addWidget(self.btn_pridat_sestavu)
        btn_layout.addWidget(self.btn_vymazat_sestavu)
        btn_layout.addWidget(self.btn_konec)
        btn_layout.addSpacing(30)

        self.btn_opravit_dil = QPushButton("Opravit díl")
        self.btn_pridat_dil = QPushButton("Přidat díl")
        self.btn_vymazat_dil = QPushButton("Vymazat díl")
        self.btn_novy_dil = QPushButton("Nový díl")
        btn_layout.addWidget(self.btn_opravit_dil)
        btn_layout.addWidget(self.btn_pridat_dil)
        btn_layout.addWidget(self.btn_vymazat_dil)
        btn_layout.addWidget(self.btn_novy_dil)
        btn_layout.addStretch()

        main_layout.addLayout(btn_layout)

        # Connections
        self.btn_opravit_sestavu.clicked.connect(self._edit_sestava)
        self.btn_pridat_sestavu.clicked.connect(self._add_sestava)
        self.btn_vymazat_sestavu.clicked.connect(self._delete_sestava)
        self.btn_konec.clicked.connect(self.reject)
        self.btn_opravit_dil.clicked.connect(self._edit_dil)
        self.btn_pridat_dil.clicked.connect(self._add_dil)
        self.btn_vymazat_dil.clicked.connect(self._delete_dil)
        self.btn_novy_dil.clicked.connect(self._new_dil)

    def _load_sestavy(self):
        self.tbl_sestavy.setSortingEnabled(False)
        self.tbl_sestavy.setRowCount(0)
        rows = self.ctx.db.read_all("tsd02")
        # Pre-load all parts grouped by FINAL (assembly code)
        all_dily = self.ctx.db.read_all("tsd02a")
        self._dily_cache = {}
        for d in all_dily:
            key = d.get("FINAL")
            if key is not None:
                self._dily_cache.setdefault(int(key) if not isinstance(key, int) else key, []).append(d)
        for r in rows:
            row = self.tbl_sestavy.rowCount()
            self.tbl_sestavy.insertRow(row)
            self.tbl_sestavy.setItem(row, 0, NumericSortItem(str(r.get("KOD", ""))))
            self.tbl_sestavy.setItem(row, 1, QTableWidgetItem(str(r.get("NAZEV", ""))))
            self.tbl_sestavy.setItem(row, 2, NumericSortItem(str(r.get("CENA", 0))))
            self.tbl_sestavy.setItem(row, 3, QTableWidgetItem(str(r.get("TYP_ZAKLAD", ""))))
            self.tbl_sestavy.setItem(row, 4, QTableWidgetItem(str(r.get("SYMBOL", ""))))
        self.tbl_sestavy.setSortingEnabled(True)
        self.tbl_sestavy.sortByColumn(1, Qt.AscendingOrder)

    def _on_sestava_selected(self, row, col, prev_row, prev_col):
        if row < 0:
            return
        nazev_item = self.tbl_sestavy.item(row, 1)
        kod_item = self.tbl_sestavy.item(row, 0)
        nazev = nazev_item.text() if nazev_item else ""
        self.lbl_sestava.setText(f"Sestava: {nazev}")

        # Load parts from cache
        self.tbl_dily.setSortingEnabled(False)
        self.tbl_dily.setRowCount(0)
        if kod_item:
            kod = int(kod_item.text())
            dily = self._dily_cache.get(kod, [])
            for d in dily:
                row = self.tbl_dily.rowCount()
                self.tbl_dily.insertRow(row)
                self.tbl_dily.setItem(row, 0, NumericSortItem(str(d.get("KOD", ""))))
                self.tbl_dily.setItem(row, 1, QTableWidgetItem(str(d.get("NAZEV", ""))))
                self.tbl_dily.setItem(row, 2, NumericSortItem(str(d.get("CENA", 0))))
                self.tbl_dily.setItem(row, 3, NumericSortItem(str(d.get("MNOZSTVI", 1))))
        self.tbl_dily.setSortingEnabled(True)
        self.tbl_dily.sortByColumn(1, Qt.AscendingOrder)

    def _add_sestava(self):
        dlg = EditSestavDialog(self.ctx, is_new=True, parent=self)
        if dlg.exec() == QDialog.Accepted:
            data = dlg.get_data()
            self.ctx.db.insert("tsd02", data)
            self._load_sestavy()

    def _edit_sestava(self):
        row = self.tbl_sestavy.currentRow()
        if row < 0:
            return
        kod = self.tbl_sestavy.item(row, 0).text()
        nazev = self.tbl_sestavy.item(row, 1).text()
        cena = self.tbl_sestavy.item(row, 2).text()
        zaklady = self.tbl_sestavy.item(row, 3).text() if self.tbl_sestavy.item(row, 3) else ""
        symbol = self.tbl_sestavy.item(row, 4).text() if self.tbl_sestavy.item(row, 4) else ""
        dlg = EditSestavDialog(self.ctx, kod=kod, nazev=nazev, cena=cena, zaklady=zaklady, symbol=symbol, is_new=False, parent=self)
        if dlg.exec() == QDialog.Accepted:
            data = dlg.get_data()
            self.ctx.db.update("tsd02", "KOD", int(kod), data)
            self._load_sestavy()

    def _delete_sestava(self):
        row = self.tbl_sestavy.currentRow()
        if row < 0:
            return
        kod = self.tbl_sestavy.item(row, 0).text()
        reply = QMessageBox.question(self, "Potvrzení", "Opravdu vymazat sestavu? Smažou se i všechny její díly.")
        if reply == QMessageBox.Yes:
            self.ctx.db.delete("tsd02", "KOD", int(kod))
            self.ctx.db.delete("tsd02a", "FINAL", int(kod))
            self._load_sestavy()

    def _get_current_sestava_kod(self):
        row = self.tbl_sestavy.currentRow()
        if row < 0:
            return None
        return int(self.tbl_sestavy.item(row, 0).text())

    def _add_dil(self):
        kod_sestavy = self._get_current_sestava_kod()
        if kod_sestavy is None:
            return
        # Show list of available parts from tsd02
        from app.views.vyber_dilu_dialog import VyberDiluDialog
        dlg = VyberDiluDialog(self.ctx, parent=self)
        if dlg.exec() == QDialog.Accepted and dlg.selected:
            data = {
                "FINAL": kod_sestavy,
                "KOD": dlg.selected.get("KOD", dlg.selected.get("kod")),
                "NAZEV": dlg.selected.get("NAZEV", dlg.selected.get("nazev")),
                "CENA": dlg.selected.get("CENA", dlg.selected.get("cena")),
                "MNOZSTVI": 1,
            }
            self.ctx.db.insert("tsd02a", data)
            self._load_sestavy()
            self._on_sestava_selected(self.tbl_sestavy.currentRow(), 0, -1, -1)

    def _edit_dil(self):
        row = self.tbl_dily.currentRow()
        if row < 0:
            return
        from app.views.edit_pocet_dialog import EditPocetDialog
        current = int(self.tbl_dily.item(row, 3).text()) if self.tbl_dily.item(row, 3) else 1
        dlg = EditPocetDialog(current, parent=self)
        if dlg.exec() == QDialog.Accepted:
            kod = int(self.tbl_dily.item(row, 0).text())
            kod_sestavy = self._get_current_sestava_kod()
            
            dily_list = self._dily_cache.get(kod_sestavy, [])
            recno = None
            for d in dily_list:
                if int(d.get("KOD", 0)) == kod:
                    recno = d.get("_RECNO")
                    break
                    
            if recno is not None:
                self.ctx.db.update("tsd02a", "_RECNO", recno, {"MNOZSTVI": dlg.value})
                self._load_sestavy()
                self._on_sestava_selected(self.tbl_sestavy.currentRow(), 0, -1, -1)

    def _delete_dil(self):
        row = self.tbl_dily.currentRow()
        if row < 0:
            return
        kod = int(self.tbl_dily.item(row, 0).text())
        kod_sestavy = self._get_current_sestava_kod()
        
        dily_list = self._dily_cache.get(kod_sestavy, [])
        recno = None
        for d in dily_list:
            if int(d.get("KOD", 0)) == kod:
                recno = d.get("_RECNO")
                break
                
        if recno is not None:
            self.ctx.db.delete("tsd02a", "_RECNO", recno)
            self._load_sestavy()
            self._on_sestava_selected(self.tbl_sestavy.currentRow(), 0, -1, -1)

    def _new_dil(self):
        kod_sestavy = self._get_current_sestava_kod()
        if kod_sestavy is None:
            return
        from app.views.zakladni_dily_dialog import EditDilDialog
        dlg = EditDilDialog(self.ctx, is_new=True, parent=self)
        if dlg.exec() == QDialog.Accepted:
            data = dlg.get_data()
            self.ctx.db.insert("tsd03", data)
            
            new_part = {
                "FINAL": kod_sestavy,
                "KOD": data["KOD"],
                "NAZEV": data["NAZEV"],
                "CENA": data["CENA"],
                "MNOZSTVI": 1,
            }
            self.ctx.db.insert("tsd02a", new_part)
            self._load_sestavy()
            self._on_sestava_selected(self.tbl_sestavy.currentRow(), 0, -1, -1)


class EditSestavDialog(QDialog):
    def __init__(self, ctx=None, kod="", nazev="", cena="0", zaklady="", symbol="", is_new=False, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self.is_new = is_new
        self.setWindowTitle("Sestava")
        self.setMinimumWidth(400)
        layout = QFormLayout(self)
        self.edit_kod = QLineEdit(str(kod))
        self.edit_nazev = QLineEdit(nazev)
        self.edit_cena = QLineEdit(str(cena))
        self.edit_zaklady = QLineEdit(zaklady)
        self.edit_symbol = QLineEdit(symbol)
        self.edit_symbol.setMaxLength(1)
        layout.addRow("Číslo:", self.edit_kod)
        layout.addRow("Název:", self.edit_nazev)
        layout.addRow("Cena:", self.edit_cena)
        layout.addRow("Základy:", self.edit_zaklady)
        layout.addRow("Symbol:", self.edit_symbol)

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
            
        if self.is_new and self.ctx and self.ctx.db.read_where("tsd02", {"KOD": kod}):
            QMessageBox.warning(self, "Chyba", f"Zadaná sestava s kódem {kod} již existuje!")
            return
            
        super().accept()

    def get_data(self) -> dict:
        return {
            "KOD": int(self.edit_kod.text() or 0),
            "NAZEV": self.edit_nazev.text().strip(),
            "CENA": float(self.edit_cena.text() or 0),
            "TYP_ZAKLAD": self.edit_zaklady.text().strip(),
            "SYMBOL": self.edit_symbol.text().strip()[:1],
        }
