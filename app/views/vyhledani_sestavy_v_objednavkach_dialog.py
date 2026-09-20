"""
Vyhledávání sestavy v objednávkách – dialog pro vyhledání a zobrazení aktivních objednávek
podle vybrané skleníkové sestavy.
"""
import datetime
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QCheckBox,
    QLineEdit, QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QMessageBox
)
from PySide6.QtCore import Qt
from app.views.sort_items import NumericSortItem, DateSortItem


class VyhledaniSestavyVObjednavkachDialog(QDialog):
    def __init__(self, ctx, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self.setWindowTitle("Vyhledávání sestavy v objednávkách")
        self.setMinimumSize(950, 560)
        self.resize(1000, 600)

        self._sestavy = []
        self._all_orders = []
        self._items_by_sestava = {}  # kod_sestavy -> {cislo_obj: celkove_mnozstvi}
        self._orders_by_cislo = {}   # cislo_obj -> order dict
        self._trasy_cache = {}

        self._build_ui()
        self._load_data()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # Title
        lbl_title = QLabel("Vyhledávání sestavy v objednávkách")
        lbl_title.setObjectName("titleLabel")
        lbl_title.setAlignment(Qt.AlignCenter)
        layout.addWidget(lbl_title)

        # Top selection / filter row
        top_row = QHBoxLayout()
        top_row.setSpacing(8)

        lbl_sestava = QLabel("Sestava:")
        lbl_sestava.setStyleSheet("font-weight: bold;")
        top_row.addWidget(lbl_sestava)

        self.combo_sestavy = QComboBox()
        self.combo_sestavy.setEditable(True)
        self.combo_sestavy.setInsertPolicy(QComboBox.NoInsert)
        if self.combo_sestavy.completer():
            self.combo_sestavy.completer().setFilterMode(Qt.MatchContains)
        self.combo_sestavy.setMinimumWidth(360)
        self.combo_sestavy.currentIndexChanged.connect(self._refresh_table)
        top_row.addWidget(self.combo_sestavy)

        self.chk_pouze_nevyrizene = QCheckBox("Pouze nevyřízené")
        self.chk_pouze_nevyrizene.setChecked(True)
        self.chk_pouze_nevyrizene.stateChanged.connect(self._refresh_table)
        top_row.addWidget(self.chk_pouze_nevyrizene)

        top_row.addSpacing(10)
        top_row.addWidget(QLabel("Filtr:"))
        self.edit_filter = QLineEdit()
        self.edit_filter.setPlaceholderText("Číslo obj., zákazník, město...")
        self.edit_filter.textChanged.connect(self._refresh_table)
        top_row.addWidget(self.edit_filter)

        layout.addLayout(top_row)

        # Table of orders
        self.table = QTableWidget()
        cols = ["Č. obj.", "Zákazník", "Obec/Město", "PSČ", "Přijato", "Množství", "Trasa", "Stav"]
        self.table.setColumnCount(len(cols))
        self.table.setHorizontalHeaderLabels(cols)

        self.table.setColumnWidth(0, 80)   # Č. obj.
        self.table.setColumnWidth(1, 180)  # Zákazník
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)  # Obec/Město
        self.table.setColumnWidth(3, 70)   # PSČ
        self.table.setColumnWidth(4, 90)   # Přijato
        self.table.setColumnWidth(5, 80)   # Množství
        self.table.setColumnWidth(6, 140)  # Trasa
        self.table.setColumnWidth(7, 100)  # Stav

        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setSortingEnabled(True)
        self.table.doubleClicked.connect(self._open_order)

        layout.addWidget(self.table)

        # Bottom summary & buttons row
        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(10)

        self.lbl_summary = QLabel("Počet objednávek: 0 | Celkem kusů sestavy: 0 ks")
        self.lbl_summary.setStyleSheet("font-weight: bold; font-size: 13px;")
        bottom_row.addWidget(self.lbl_summary)

        bottom_row.addStretch()

        self.btn_open = QPushButton("Otevřít objednávku")
        self.btn_open.setObjectName("accentButton")
        self.btn_open.clicked.connect(self._open_order)
        bottom_row.addWidget(self.btn_open)

        self.btn_close = QPushButton("Zavřít")
        self.btn_close.clicked.connect(self.accept)
        bottom_row.addWidget(self.btn_close)

        layout.addLayout(bottom_row)

    @staticmethod
    def _norm_cislo(raw_val):
        if raw_val is None or raw_val == "":
            return ""
        s = str(raw_val).strip()
        try:
            return str(int(float(s)))
        except (ValueError, TypeError):
            return s

    @staticmethod
    def _norm_kod(raw_val):
        if raw_val is None or raw_val == "":
            return None
        try:
            return int(float(str(raw_val).strip()))
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _fmt_date(d):
        if not d:
            return ""
        if isinstance(d, (datetime.date, datetime.datetime)):
            return d.strftime("%d.%m.%Y")
        s = str(d).strip()
        if len(s) >= 10 and s[4] == "-" and s[7] == "-":
            try:
                parts = s[:10].split("-")
                return f"{parts[2]}.{parts[1]}.{parts[0]}"
            except Exception:
                pass
        return s

    def _fmt_trasa(self, r):
        trasa = str(r.get("TRASA", "")).strip()
        if not trasa:
            return ""
        route = self._trasy_cache.get(trasa)
        if not route:
            return trasa
        smer = str(route.get("SMER", "")).strip()
        if smer:
            return smer
        d = route.get("DATUM")
        if isinstance(d, (datetime.date, datetime.datetime)):
            return d.strftime("%d.%m.%Y")
        return trasa

    def _fmt_stav(self, r):
        status = str(r.get("STATUS", "")).strip().upper()
        if status == "S":
            return "Storno"
        if r.get("DATUM_VYR"):
            return f"Vyřízeno ({self._fmt_date(r.get('DATUM_VYR'))})"
        return "Nevyřízeno"

    def _load_data(self):
        db = self.ctx.db
        with db.session():
            # 1. Sestavy (tsd02)
            raw_sestavy = db.read_all("tsd02")
            self._sestavy = sorted(
                raw_sestavy,
                key=lambda x: str(x.get("NAZEV", "")).lower()
            )

            # 2. Trasy (tsd05)
            self._trasy_cache = {}
            for t in db.read_all("tsd05"):
                cislo = str(t.get("CISLO", "")).strip()
                if cislo:
                    self._trasy_cache[cislo] = t

            # 3. Objednávky (tsd04) - exclude archived (tsd06)
            raw_orders = db.read_all("tsd04")
            active_cisla = {
                str(r.get("CISLO_OBJ", "")).strip()
                for r in raw_orders if r.get("CISLO_OBJ")
            }
            archived_cisla = set(db.read_where_in("tsd06", "CISLO_OBJ", active_cisla).keys()) if active_cisla else set()
            self._orders_by_cislo = {}
            self._all_orders = []
            for o in raw_orders:
                c = self._norm_cislo(o.get("CISLO_OBJ"))
                if c and str(c) not in archived_cisla:
                    self._orders_by_cislo[c] = o
                    self._all_orders.append(o)

            # 4. Položky sestav (tsd04a)
            # Map: kod_sestavy -> {cislo_obj: sum(mnozstvi)}
            self._items_by_sestava = {}
            for item in db.read_all("tsd04a"):
                cislo = self._norm_cislo(item.get("CISLO_OBJ"))
                if not cislo or cislo not in self._orders_by_cislo:
                    continue
                kod = self._norm_kod(item.get("KOD"))
                if kod is None:
                    continue
                try:
                    qty = int(float(item.get("MNOZSTVI", 1) or 1))
                except (ValueError, TypeError):
                    qty = 1

                if kod not in self._items_by_sestava:
                    self._items_by_sestava[kod] = {}
                self._items_by_sestava[kod][cislo] = self._items_by_sestava[kod].get(cislo, 0) + qty

        # Fill combo
        cur_kod = self.combo_sestavy.currentData()
        self.combo_sestavy.blockSignals(True)
        self.combo_sestavy.clear()
        self.combo_sestavy.addItem("-- Vyberte sestavu --", userData=None)

        selected_idx = 0
        for i, s in enumerate(self._sestavy):
            kod = self._norm_kod(s.get("KOD"))
            nazev = str(s.get("NAZEV", "")).strip()
            display_text = f"{nazev} (kód: {kod})" if kod is not None else nazev
            self.combo_sestavy.addItem(display_text, userData=kod)
            if cur_kod is not None and kod == cur_kod:
                selected_idx = i + 1

        self.combo_sestavy.setCurrentIndex(selected_idx)
        self.combo_sestavy.blockSignals(False)

        self._refresh_table()

    def _refresh_table(self):
        sel_kod = self.combo_sestavy.currentData()
        pouze_nevyrizene = self.chk_pouze_nevyrizene.isChecked()
        search_filter = self.edit_filter.text().strip().lower()

        self.table.blockSignals(True)
        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)

        if sel_kod is None:
            self.lbl_summary.setText("Počet objednávek: 0 | Celkem kusů sestavy: 0 ks")
            self.table.setSortingEnabled(True)
            self.table.blockSignals(False)
            return

        order_quantities = self._items_by_sestava.get(sel_kod, {})
        matching_rows = []
        total_pcs = 0

        for cislo, qty in order_quantities.items():
            order = self._orders_by_cislo.get(cislo)
            if not order:
                continue

            # Filter out finished orders if requested
            if pouze_nevyrizene and order.get("DATUM_VYR"):
                continue

            # Quick search filter
            z_jmeno = str(order.get("Z_JMENO", ""))
            z_mesto = str(order.get("Z_POSTA", "") or order.get("Z_MESTO", ""))
            z_psc = str(order.get("Z_PSC", ""))
            if search_filter:
                terms = [cislo.lower(), z_jmeno.lower(), z_mesto.lower(), z_psc.lower()]
                if not any(search_filter in t for t in terms):
                    continue

            matching_rows.append((order, qty))
            total_pcs += qty

        self.table.setRowCount(len(matching_rows))
        for row_idx, (order, qty) in enumerate(matching_rows):
            cislo = self._norm_cislo(order.get("CISLO_OBJ"))
            z_jmeno = str(order.get("Z_JMENO", ""))
            z_mesto = str(order.get("Z_POSTA", "") or order.get("Z_MESTO", ""))
            z_psc = str(order.get("Z_PSC", ""))
            datum_pr = self._fmt_date(order.get("DATUM_PR"))
            trasa = self._fmt_trasa(order)
            stav = self._fmt_stav(order)

            item_cislo = NumericSortItem(cislo)
            item_jmeno = QTableWidgetItem(z_jmeno)
            item_mesto = QTableWidgetItem(z_mesto)
            item_psc = QTableWidgetItem(z_psc)
            item_prijato = DateSortItem(datum_pr)
            item_mnozstvi = NumericSortItem(str(qty))
            item_mnozstvi.setTextAlignment(Qt.AlignCenter)
            item_trasa = QTableWidgetItem(trasa)
            item_stav = QTableWidgetItem(stav)

            self.table.setItem(row_idx, 0, item_cislo)
            self.table.setItem(row_idx, 1, item_jmeno)
            self.table.setItem(row_idx, 2, item_mesto)
            self.table.setItem(row_idx, 3, item_psc)
            self.table.setItem(row_idx, 4, item_prijato)
            self.table.setItem(row_idx, 5, item_mnozstvi)
            self.table.setItem(row_idx, 6, item_trasa)
            self.table.setItem(row_idx, 7, item_stav)

        self.table.setSortingEnabled(True)
        self.table.sortByColumn(0, Qt.AscendingOrder)
        self.table.blockSignals(False)

        self.lbl_summary.setText(
            f"Počet objednávek: {len(matching_rows)} | Celkem kusů sestavy: {total_pcs} ks"
        )

    def _selected_cislo(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Objednávka", "Vyberte objednávku v tabulce.")
            return None
        item = self.table.item(row, 0)
        return item.text().strip() if item else None

    def _open_order(self):
        cislo = self._selected_cislo()
        if not cislo:
            return
        from app.views.objednavka_dialog import ObjednavkaDialog
        dlg = ObjednavkaDialog(self.ctx, cislo_obj=cislo, parent=self)
        dlg.exec()
        # Reload and refresh in case items or status changed
        self._load_data()
