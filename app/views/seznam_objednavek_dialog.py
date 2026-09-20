"""
Seznam objednávek – grid with orders, filtering, CRUD
Shown from main window Objednávky menu and from Rozvozní plány "Seznam objednávek"
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QMessageBox, QComboBox, QCheckBox, QDateEdit, QProgressDialog,
    QSplitter, QWidget, QAbstractItemView
)
from PySide6.QtGui import QAction
from PySide6.QtCore import Qt, QDate, Signal
from app.utils import format_phone_number, get_effective_address
import json
import os
import datetime
from app.views.sort_items import DateSortItem, NumericSortItem
from app.services.db_worker import DbWorker


class DraggableTableWidget(QTableWidget):
    orderChanged = Signal()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.viewport().setAcceptDrops(True)
        self.setDragDropOverwriteMode(False)
        self.setDropIndicatorShown(True)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setDragDropMode(QAbstractItemView.InternalMove)

    def dropEvent(self, event):
        if event.source() != self:
            return

        selected = self.selectedItems()
        if not selected:
            return
        source_row = selected[0].row()

        if source_row < 0:
            return

        try:
            pos = event.position().toPoint()
        except AttributeError:
            pos = event.pos()

        target_index = self.indexAt(pos)
        target_row = target_index.row()

        if target_row < 0:
            target_row = self.rowCount()
        else:
            rect = self.visualRect(target_index)
            if pos.y() > rect.center().y():
                target_row += 1

        if source_row == target_row or source_row + 1 == target_row:
            event.ignore()
            return

        was_sorting = self.isSortingEnabled()
        self.setSortingEnabled(False)
        
        items = []
        for col in range(self.columnCount()):
            items.append(self.takeItem(source_row, col))
            
        self.removeRow(source_row)
        
        if target_row > source_row:
            target_row -= 1
            
        self.insertRow(target_row)
        for col, item in enumerate(items):
            self.setItem(target_row, col, item)
            
        po_col = self.columnCount() - 1
        for i in range(self.rowCount()):
            po_item = self.item(i, po_col)
            if po_item:
                po_item.setText(str(i))
                
        if was_sorting:
            self.setSortingEnabled(True)
            self.sortByColumn(po_col, Qt.AscendingOrder)
            
        event.ignore()
        self.orderChanged.emit()

class SeznamObjednavekDialog(QDialog):
    def __init__(self, ctx, trasa_filter=None, source_table="tsd04", parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self.trasa_filter = trasa_filter
        self.source_table = source_table
        self.is_archive = (source_table == "tsd06")
        title = "Archiv objednávek" if self.is_archive else "Seznam objednávek"
        self.setWindowTitle(title)
        self.setMinimumSize(1000, 600)
        self.resize(1100, 650)
        self._build_ui()
        self._load_data()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        lbl = QLabel("Archiv objednávek" if self.is_archive else "Seznam objednávek")
        lbl.setObjectName("titleLabel")
        lbl.setAlignment(Qt.AlignCenter)
        layout.addWidget(lbl)

        # Filter row
        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("Hledat:"))
        self.edit_search = QLineEdit()
        self.edit_search.setPlaceholderText("Jméno, číslo obj., PSČ...")
        self.edit_search.textChanged.connect(self._filter)
        filter_row.addWidget(self.edit_search)

        filter_row.addWidget(QLabel("Stav:"))
        self.combo_stav = QComboBox()
        self.combo_stav.addItems(["Všechny", "Nové", "Vyřízené", "Storno"])
        self.combo_stav.currentIndexChanged.connect(self._filter)
        filter_row.addWidget(self.combo_stav)

        layout.addLayout(filter_row)

        # Table
        if self.trasa_filter:
            self.table = DraggableTableWidget()
            self.table.orderChanged.connect(self._save_custom_order)
            cols = ["Č.obj.", "Zkratky", "Jméno zákazníka", "Ulice", "PSČ", "Pošta",
                    "Přijato", "Trasa", "Pořadí"]
        else:
            self.table = QTableWidget()
            if not self.is_archive:
                cols = ["Č.obj.", "Zkratky", "Jméno zákazníka", "Ulice", "PSČ", "Pošta",
                        "Přijato", "Dodat po", "Trasa"]
            else:
                cols = ["Č.obj.", "Zkratky", "Jméno zákazníka", "Ulice", "PSČ", "Pošta",
                        "Přijato", "Trasa"]
        self.table.setColumnCount(len(cols))
        self.table.setHorizontalHeaderLabels(cols)
        
        self.table.setColumnWidth(0, 60)   # Č.obj.
        self.table.setColumnWidth(1, 100)  # Zkratky
        self.table.setColumnWidth(2, 150)  # Jméno zákazníka
        self.table.setColumnWidth(3, 140)  # Ulice
        self.table.setColumnWidth(4, 65)   # PSČ
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.Stretch) # Pošta
        self.table.setColumnWidth(6, 90)   # Přijato
        
        if not self.is_archive and not self.trasa_filter:
            self.table.setColumnWidth(7, 90)   # Dodat po
            self.table.setColumnWidth(8, 140)  # Trasa
        else:
            self.table.setColumnWidth(7, 140)  # Trasa
        
        self.table.verticalHeader().setDefaultSectionSize(35)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.DoubleClicked | QTableWidget.EditKeyPressed)
        if self.trasa_filter:
            self.table.setColumnHidden(8, True)
        self.table.setSortingEnabled(True)
        self.table.itemChanged.connect(self._on_item_changed)

        if self.trasa_filter:
            # Table parts is still needed to aggregate data for print, but we hide it from UI
            self.table_parts = QTableWidget()
            self.table_parts.setColumnCount(3)
            self.table_parts.setHorizontalHeaderLabels(["Kód", "Název", "Množství"])
            self.table_parts.setSortingEnabled(True)

        layout.addWidget(self.table)
        self.lbl_count = QLabel("Počet: 0")
        layout.addWidget(self.lbl_count)

        # Buttons
        btn_row = QHBoxLayout()
        self.btn_open = QPushButton("Otevřít")
        self.btn_open.setObjectName("accentButton")
        self.btn_new = QPushButton("Nová objednávka")
        self.btn_complete = QPushButton("Označit jako vyřízené")
        self.btn_complete.clicked.connect(self._mark_as_completed)
        self.btn_del = QPushButton("Vymazat")
        self.btn_del.setObjectName("dangerButton")
        self.btn_print = QPushButton("Tisk")
        self.btn_close = QPushButton("Konec")
        
        buttons = [self.btn_open]
        if not self.trasa_filter:
            buttons.append(self.btn_new)
            
        if not self.is_archive:
            buttons.append(self.btn_complete)
            
        buttons.extend([self.btn_del, self.btn_print])
        
        # Archive single order button — only available outside the archive view and route view
        if not self.is_archive and not self.trasa_filter:
            self.btn_archive = QPushButton("Archivovat")
            self.btn_archive.clicked.connect(self._archive_order)
            buttons.append(self.btn_archive)
            
        # Add route-related buttons when viewing orders for a specific route
        if self.trasa_filter:
            self.btn_assign_orders = QPushButton("Přiřadit objednávky")
            self.btn_assign_orders.clicked.connect(self._assign_orders)
            buttons.append(self.btn_assign_orders)
            self.btn_remove_route = QPushButton("Odebrat z trasy")
            self.btn_remove_route.clicked.connect(self._remove_from_route)
            buttons.append(self.btn_remove_route)
            
            self.btn_print_skla = QPushButton("Tisk skel a doplňků")
            self.btn_print_skla.clicked.connect(self._print_skla_route)
            buttons.append(self.btn_print_skla)
            
        buttons.append(self.btn_close)
        for b in buttons:
            btn_row.addWidget(b)
        layout.addLayout(btn_row)

        self.btn_open.clicked.connect(self._open_order)
        self.btn_new.clicked.connect(self._new_order)
        self.btn_del.clicked.connect(self._delete_order)
        self.btn_print.clicked.connect(self._print)
        self.btn_close.clicked.connect(self.accept)

        if self.is_archive:
            self.btn_new.setEnabled(False)

    def _load_data(self):
        self._all_rows = []
        self._trasy_cache = {}
        self._symbols_cache = {}

        source_table = self.source_table
        is_archive = self.is_archive
        trasa_filter = self.trasa_filter
        db = self.ctx.db

        items_table = "tsd06a" if is_archive else "tsd04a"
        details_table = "tsd06b" if is_archive else "tsd04b"

        progress = QProgressDialog("Načítání objednávek...", None, 0, 6, self)
        progress.setWindowTitle("Archiv objednávek" if is_archive else "Seznam objednávek")
        progress.setWindowModality(Qt.WindowModal)
        progress.setMinimumDuration(0)
        progress.setValue(0)

        def do_load(progress_cb):
            with db.session():
                progress_cb(0, "Načítání objednávek...")
                all_rows = db.read_all(source_table)
                # Exclude orders that are already in the archive (tsd06) to avoid
                # showing archived records in the active order list (tsd04)
                if not is_archive:
                    active_cisla = {
                        str(r.get("CISLO_OBJ", "")).strip()
                        for r in all_rows if r.get("CISLO_OBJ")
                    }
                    if active_cisla:
                        archived_matches = set(db.read_where_in("tsd06", "CISLO_OBJ", active_cisla).keys())
                        all_rows = [
                            r for r in all_rows
                            if str(r.get("CISLO_OBJ", "")).strip() not in archived_matches
                        ]
                if self.trasa_filter:
                    norm_filter = SeznamObjednavekDialog._norm_trasa_key(self.trasa_filter)
                    all_rows = [r for r in all_rows
                                if SeznamObjednavekDialog._norm_trasa_key(r.get("TRASA")) == norm_filter]

                progress_cb(1, "Načítání tras...")
                trasy_cache = {}
                for route in self.ctx.get_cached_table("tsd05"):
                    key = SeznamObjednavekDialog._norm_trasa_key(route.get("CISLO"))
                    if key:
                        trasy_cache[key] = route

                progress_cb(2, "Načítání sestav...")
                _sym_sestavy = {}
                for s in self.ctx.get_cached_table("tsd02"):
                    sym = str(s.get("SYMBOL", "")).strip()
                    if sym:
                        _sym_sestavy[s.get("KOD")] = sym

                progress_cb(3, "Načítání dílů...")
                _sym_dily = {}
                for d in self.ctx.get_cached_table("tsd03"):
                    sym = str(d.get("SYMBOL", "")).strip()
                    if sym:
                        _sym_dily[d.get("KOD")] = sym

                _parts_of_sestava = {}
                if trasa_filter:
                    for pd in self.ctx.get_cached_table("tsd02a"):
                        final = pd.get("FINAL")
                        if final is not None:
                            try:
                                key = int(final) if not isinstance(final, int) else final
                                _parts_of_sestava.setdefault(key, []).append(pd)
                            except ValueError:
                                pass

                symbols_cache = {}
                items_by_obj = {}
                progress_cb(4, "Načítání položek objednávek...")
                for item in db.read_all(items_table):
                    cislo = str(item.get("CISLO_OBJ", "")).strip()
                    if trasa_filter:
                        items_by_obj.setdefault(cislo, []).append(item)
                    sym = _sym_sestavy.get(item.get("KOD"), "")
                    if sym:
                        symbols_cache.setdefault(cislo, set()).add(sym)

                details_by_obj = {}
                progress_cb(5, "Načítání detailů objednávek...")
                for item in db.read_all(details_table):
                    cislo = str(item.get("CISLO_OBJ", "")).strip()
                    if trasa_filter:
                        details_by_obj.setdefault(cislo, []).append(item)
                    sym = _sym_dily.get(item.get("KOD"), "")
                    if sym:
                        symbols_cache.setdefault(cislo, set()).add(sym)

                progress_cb(6, "Hotovo")
            return all_rows, trasy_cache, symbols_cache, items_by_obj, details_by_obj, _parts_of_sestava

        self._load_worker = DbWorker(do_load)
        self._load_progress = progress

        def on_progress(step, label):
            progress.setValue(step)
            progress.setLabelText(label)

        def on_finished(ok, msg, result):
            progress.close()
            self._load_worker = None
            if not ok:
                QMessageBox.warning(self, "Chyba", f"Chyba při načítání: {msg}")
                return
            self._all_rows, self._trasy_cache, self._symbols_cache, self._items_by_obj, self._details_by_obj, self._parts_of_sestava = result
            self._filter()

        self._load_worker.progress.connect(on_progress)
        self._load_worker.finished.connect(on_finished)
        self._load_worker.start()

    def _filter(self, *_args):
        rows = self._all_rows
        search = self.edit_search.text().strip().lower()
        if search:
            search_is_num = search.isdigit()
            def _cislo_matches(r):
                raw = r.get("CISLO_OBJ", "")
                # Normalize: int(float()) handles both int and float DBF storage
                if search_is_num:
                    try:
                        return int(search) == int(float(str(raw)))
                    except (ValueError, TypeError):
                        pass
                # Fallback: substring match on normalized string
                cislo_str = str(int(float(str(raw)))) if raw not in (None, "") else ""
                try:
                    cislo_str = str(int(float(str(raw))))
                except (ValueError, TypeError):
                    cislo_str = str(raw).strip()
                return search in cislo_str.lower()

            rows = [r for r in rows if
                    _cislo_matches(r) or
                    search in str(r.get("Z_JMENO", "")).lower() or
                    search in str(r.get("Z_ULICE", "")).lower() or
                    search in str(r.get("Z_PSC", "")).lower() or
                    search in str(r.get("Z_POSTA", "")).lower() or
                    search in str(r.get("U_JMENO", "")).lower() or
                    search in str(r.get("U_ULICE", "")).lower() or
                    search in str(r.get("U_PSC", "")).lower() or
                    search in str(r.get("U_POSTA", "")).lower()]

        stav_idx = self.combo_stav.currentIndex()
        if stav_idx == 1:
            rows = [r for r in rows if not r.get("DATUM_VYR")]
        elif stav_idx == 2:
            rows = [r for r in rows if r.get("DATUM_VYR")]
        elif stav_idx == 3:
            rows = [r for r in rows if str(r.get("STATUS", "")).upper() == "S"]

        # Odvozy se řeší v samostatném okně, tady je skryjeme úplně (ale v archivu je zobrazíme)
        if not self.is_archive:
            rows = [r for r in rows if r.get("VL_ODVOZ") not in ("1", 1, True, "True", "true")]

        self._display(rows)

    def _get_route_orders_path(self):
        return os.path.join(self.ctx.db.data_path, "route_orders.json")

    def _load_custom_order(self):
        path = self._get_route_orders_path()
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return data.get(str(self.trasa_filter), [])
            except Exception:
                pass
        return []

    def _save_custom_order(self):
        current_order = []
        for i in range(self.table.rowCount()):
            item = self.table.item(i, 0)
            if item:
                current_order.append(item.text())
        
        path = self._get_route_orders_path()
        data = {}
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                pass
                
        data[str(self.trasa_filter)] = current_order
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f)
        except Exception as e:
            print(f"Error saving custom order: {e}")

    def _display(self, rows):
        self.table.blockSignals(True)
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(rows))
        
        custom_order = []
        order_map = {}
        if self.trasa_filter:
            custom_order = self._load_custom_order()
            order_map = {cislo: idx for idx, cislo in enumerate(custom_order)}

        # Pre-fetch route date for date widgets when viewing a route
        route_date = None
        if self.trasa_filter:
            norm_filter = SeznamObjednavekDialog._norm_trasa_key(self.trasa_filter)
            route = self._trasy_cache.get(norm_filter)
            if route:
                d = route.get("DATUM")
                if isinstance(d, (datetime.date, datetime.datetime)):
                    route_date = d

        self._route_date_widgets = []  # track date widgets for bulk refresh

        for i, r in enumerate(rows):
            # Normalize CISLO_OBJ: strip ".0" from float-stored integers
            raw_cislo = r.get("CISLO_OBJ", "")
            try:
                cislo = str(int(float(str(raw_cislo)))) if raw_cislo not in (None, "") else ""
            except (ValueError, TypeError):
                cislo = str(raw_cislo).strip()
            syms = self._symbols_cache.get(cislo, set()) or self._symbols_cache.get(str(raw_cislo), set())
            syms_str = "".join(sorted(syms))
            
            eff_addr = get_effective_address(r)
            use_delivery = eff_addr["has_delivery"]

            vals = [
                cislo,
                syms_str,
                eff_addr["jmeno"],
                eff_addr["ulice"],
                eff_addr["psc"],
                eff_addr["posta"],
                self._fmt_date(r.get("DATUM_PR")),
            ]
            if not self.is_archive and not self.trasa_filter:
                vals.append(self._fmt_date(r.get("DATUM_PO")))
            vals.append(self._fmt_trasa(r))
                
            for j, v in enumerate(vals):
                is_prijato_col = j == 6
                is_dodat_po_col = (not self.is_archive and not self.trasa_filter and j == 7)
                
                if j == 0:   # Č.obj. – numeric sort
                    item = NumericSortItem(v)
                elif is_prijato_col or is_dodat_po_col:  # Date columns
                    item = DateSortItem(v)
                else:
                    item = QTableWidgetItem(v)
                    
                if j in (2, 3, 4, 5): # Editable columns: Jmeno, Ulice, PSC, Posta
                    item.setFlags(item.flags() | Qt.ItemIsEditable)
                    item.setData(Qt.UserRole, use_delivery)
                else:
                    item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                    
                self.table.setItem(i, j, item)
            
            if self.trasa_filter:
                idx = order_map.get(cislo, 999999 + i)
                self.table.setItem(i, 8, NumericSortItem(str(idx)))
                
        self.table.setSortingEnabled(True)
        if self.trasa_filter:
            self.table.sortByColumn(8, Qt.AscendingOrder)
        else:
            self.table.sortByColumn(6, Qt.DescendingOrder)
        self.lbl_count.setText(f"Počet: {len(rows)}")
        self.table.blockSignals(False)
        
        if self.trasa_filter:
            self._update_aggregated_items(rows)
            
    def _on_item_changed(self, item):
        row = item.row()
        col = item.column()
        cislo_item = self.table.item(row, 0)
        if not cislo_item:
            return
        cislo = cislo_item.text()
        
        is_delivery = bool(item.data(Qt.UserRole))
        
        if is_delivery:
            field_map = {
                2: "U_JMENO",
                3: "U_ULICE",
                4: "U_PSC",
                5: "U_POSTA"
            }
        else:
            field_map = {
                2: "Z_JMENO",
                3: "Z_ULICE",
                4: "Z_PSC",
                5: "Z_POSTA"
            }
            
        db_field = field_map.get(col)
        if not db_field:
            return
            
        new_val = item.text().strip()
        try:
            self.ctx.db.update(self.source_table, "CISLO_OBJ", cislo, {db_field: new_val})
            self.ctx.invalidate_cache(self.source_table)
            for r in self._all_rows:
                if str(r.get("CISLO_OBJ", "")).strip() == cislo.strip():
                    r[db_field] = new_val
                    break
        except Exception as e:
            QMessageBox.warning(self, "Chyba při ukládání", f"Změnu se nepodařilo uložit:\n{str(e)}")
            # Revert item text to original
            orig_val = ""
            for r in self._all_rows:
                if str(r.get("CISLO_OBJ", "")).strip() == cislo.strip():
                    orig_val = str(r.get(db_field, ""))
                    break
            self.table.blockSignals(True)
            item.setText(orig_val)
            self.table.blockSignals(False)

    def _update_aggregated_items(self, rows):
        from collections import defaultdict
        # key -> {"kod": kod, "nazev": nazev, "mnozstvi": qty}
        aggregated = defaultdict(lambda: {"kod": "", "nazev": "", "mnozstvi": 0})
        
        for r in rows:
            cislo = str(r.get("CISLO_OBJ", ""))
            
            # Sestavy (greenhouse systems) -> unpack to parts
            for item in self._items_by_obj.get(cislo, []):
                try:
                    kod_sestavy = int(item.get("KOD")) if item.get("KOD") is not None else None
                except ValueError:
                    kod_sestavy = None
                    
                mnozstvi_sestavy = int(float(item.get("MNOZSTVI", 1) or 1))
                
                parts = self._parts_of_sestava.get(kod_sestavy) if kod_sestavy is not None else []
                for p in parts:
                    p_kod = p.get("KOD", "")
                    p_nazev = p.get("NAZEV", "")
                    p_mnozstvi = int(float(p.get("MNOZSTVI", 1) or 1))
                    
                    key = str(p_kod) if p_kod else p_nazev
                    aggregated[key]["kod"] = p_kod
                    aggregated[key]["nazev"] = p_nazev
                    aggregated[key]["mnozstvi"] += (p_mnozstvi * mnozstvi_sestavy)
            
            # Díly (loose parts)
            for detail in self._details_by_obj.get(cislo, []):
                d_kod = detail.get("KOD", "")
                d_nazev = detail.get("NAZEV", "")
                d_mnozstvi = int(float(detail.get("MNOZSTVI", 1) or 1))
                
                key = str(d_kod) if d_kod else d_nazev
                aggregated[key]["kod"] = d_kod
                aggregated[key]["nazev"] = d_nazev
                aggregated[key]["mnozstvi"] += d_mnozstvi
                
        self.table_parts.setSortingEnabled(False)
        self.table_parts.setRowCount(0)
        
        for item in aggregated.values():
            if item["mnozstvi"] <= 0:
                continue
            row_idx = self.table_parts.rowCount()
            self.table_parts.insertRow(row_idx)
            
            from app.views.sort_items import NumericSortItem
            self.table_parts.setItem(row_idx, 0, NumericSortItem(str(item["kod"])))
            self.table_parts.setItem(row_idx, 1, QTableWidgetItem(str(item["nazev"])))
            self.table_parts.setItem(row_idx, 2, NumericSortItem(str(item["mnozstvi"])))
            
        self.table_parts.setSortingEnabled(True)
        self.table_parts.sortByColumn(1, Qt.AscendingOrder)

    @staticmethod
    def _fmt_date(d):
        if isinstance(d, (datetime.date, datetime.datetime)):
            # Guard: fix any remaining 2-digit year dates not caught by dbf_service
            if d.year < 100:
                try:
                    d = d.replace(year=d.year + 2000)
                except Exception:
                    pass
            return d.strftime("%d.%m.%Y")
        return str(d) if d else ""

    @staticmethod
    def _norm_trasa_key(val):
        if val is None: return ""
        s = str(val).strip()
        try:
            return str(int(float(s)))
        except (ValueError, TypeError):
            return s

    def _fmt_trasa(self, r):
        trasa = str(r.get("TRASA", "")).strip()
        if not trasa:
            return ""
        norm_trasa = SeznamObjednavekDialog._norm_trasa_key(trasa)
        route = self._trasy_cache.get(norm_trasa)
        if not route:
            try:
                route = self.ctx.db.read_by_key("tsd05", "CISLO", trasa)
                if route:
                    self._trasy_cache[norm_trasa] = route
            except Exception:
                route = None
        if not route:
            return trasa
        smer = str(route.get("SMER", "")).strip()
        if smer:
            return smer
        d = route.get("DATUM")
        if isinstance(d, (datetime.date, datetime.datetime)):
            return d.strftime("%d.%m.%Y")
        return trasa

    def _on_route_date_changed(self, new_date):
        """Update route date in tsd05 and sync all date widgets in the table."""
        if not self.trasa_filter:
            return
        new_py_date = new_date.toPython()
        
        # Kontrola dodat_po
        orders = self.ctx.db.read_where("tsd04", {"TRASA": self.trasa_filter})
        if orders:
            import datetime
            conflict_orders = []
            for o in orders:
                d_po = o.get("DATUM_PO")
                if d_po and hasattr(d_po, 'year'):
                    d_po_date = datetime.date(d_po.year, d_po.month, d_po.day) if isinstance(d_po, datetime.datetime) else d_po
                    if new_py_date < d_po_date:
                        conflict_orders.append(str(o.get("CISLO_OBJ", "")))
            
            if conflict_orders:
                QMessageBox.warning(self, "Chyba data", f"Nelze změnit datum trasy na {new_py_date.strftime('%d.%m.%Y')}, protože následující objednávky mají nastaveno 'dodat po' na pozdější datum:\n" + ", ".join(conflict_orders))
                # Reset widget to old date
                route_key = SeznamObjednavekDialog._norm_trasa_key(self.trasa_filter)
                if route_key in self._trasy_cache:
                    old_date = self._trasy_cache[route_key].get("DATUM")
                    if old_date and hasattr(old_date, 'year'):
                        sender_widget = self.sender()
                        if sender_widget:
                            sender_widget.blockSignals(True)
                            sender_widget.setDate(QDate(old_date.year, old_date.month, old_date.day))
                            sender_widget.blockSignals(False)
                return

        self.ctx.db.update("tsd05", "CISLO", self.trasa_filter, {"DATUM": new_py_date})
        self.ctx.invalidate_cache("tsd05")
        
        # Update DATUM_NA on all assigned orders
        orders = self.ctx.db.read_where("tsd04", {"TRASA": self.trasa_filter})
        if orders:
            updates = {str(o.get("CISLO_OBJ", "")): {"DATUM_NA": new_py_date} for o in orders}
            self.ctx.db.batch_update("tsd04", "CISLO_OBJ", updates)
            self.ctx.invalidate_cache("tsd04")
            
        # Update the trasy_cache so other displays stay consistent
        route_key = SeznamObjednavekDialog._norm_trasa_key(self.trasa_filter)
        if route_key in self._trasy_cache:
            self._trasy_cache[route_key]["DATUM"] = new_py_date
        # Sync all other date widgets to the new date (block signals to avoid loops)
        for widget in getattr(self, "_route_date_widgets", []):
            if widget is not self.sender():
                widget.blockSignals(True)
                widget.setDate(new_date)
                widget.blockSignals(False)
        # Update window title with new date
        smer = ""
        if route_key in self._trasy_cache:
            smer = str(self._trasy_cache[route_key].get("SMER", "")).strip()
        datum_str = new_py_date.strftime("%d.%m.%Y")
        self.setWindowTitle(f"Objednávky trasy {datum_str} – {smer}")

    def _selected_cisla(self):
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            QMessageBox.warning(self, "Objednávky", "Vyberte objednávku.")
            return []
        return [self.table.item(index.row(), 0).text() for index in rows if self.table.item(index.row(), 0)]

    def _selected_cislo(self):
        cisla = self._selected_cisla()
        if not cisla:
            return None
        if len(cisla) > 1:
            QMessageBox.warning(self, "Objednávky", "Tato akce vyžaduje výběr pouze jedné objednávky.")
            return None
        return cisla[0]

    def _open_order(self):
        cislo = self._selected_cislo()
        if cislo is None:
            return
        from app.views.objednavka_dialog import ObjednavkaDialog
        dlg = ObjednavkaDialog(self.ctx, cislo_obj=cislo, source_table=self.source_table, parent=self)
        if dlg.exec() == QDialog.Accepted:
            self._load_data()

    def _new_order(self):
        from app.views.objednavka_dialog import ObjednavkaDialog
        dlg = ObjednavkaDialog(self.ctx, cislo_obj=None, parent=self)
        if dlg.exec() == QDialog.Accepted:
            self._load_data()

    def _delete_order(self):
        cisla = self._selected_cisla()
        if not cisla:
            return
        msg = f"Opravdu vymazat objednávku č. {cisla[0]}?" if len(cisla) == 1 else f"Opravdu vymazat {len(cisla)} vybraných objednávek?"
        if QMessageBox.question(
            self, "Potvrzení", msg,
            QMessageBox.Yes | QMessageBox.No
        ) == QMessageBox.Yes:
            table = self.source_table
            table_a = table + "a"
            table_b = table + "b"
            
            with self.ctx.db.session():
                self.ctx.db.batch_delete(table, "CISLO_OBJ", set(cisla))
                self.ctx.db.batch_delete(table_a, "CISLO_OBJ", set(cisla))
                self.ctx.db.batch_delete(table_b, "CISLO_OBJ", set(cisla))
                
            self._load_data()

    def _mark_as_completed(self):
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            QMessageBox.warning(self, "Objednávky", "Vyberte objednávku.")
            return
            
        cisla = []
        for index in rows:
            cislo = self.table.item(index.row(), 0).text()
            if cislo:
                cisla.append(cislo)
                
        if not cisla:
            return
            
        to_complete = []
        for c in cisla:
            row_data = next((r for r in self._all_rows if str(r.get("CISLO_OBJ", "")).strip() == str(c).strip()), None)
            if row_data and not row_data.get("DATUM_VYR"):
                to_complete.append(c)
                
        if not to_complete:
            QMessageBox.information(self, "Vyřízení", "Všechny vybrané objednávky jsou již vyřízené.")
            return
            
        msg = f"Opravdu chcete označit {len(to_complete)} objednávek jako vyřízených?" if len(to_complete) > 1 else f"Opravdu chcete označit objednávku č. {to_complete[0]} jako vyřízenou?"
        if QMessageBox.question(self, "Označit jako vyřízené", msg, QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            today = datetime.date.today()
            updates = {c: {"DATUM_VYR": today} for c in to_complete}
            self.ctx.db.batch_update(self.source_table, "CISLO_OBJ", updates)
            QMessageBox.information(self, "Vyřízeno", "Objednávky byly označeny jako vyřízené s dnešním datem.")
            self._load_data()

    def _archive_order(self):
        cisla_list = self._selected_cisla()
        if not cisla_list:
            return
        
        rows_to_archive = []
        for c in cisla_list:
            row = next((r for r in self._all_rows if str(r.get("CISLO_OBJ", "")).strip() == str(c).strip()), None)
            if row:
                if not row.get("DATUM_VYR"):
                    QMessageBox.warning(
                        self, "Archiv",
                        f"Nelze archivovat objednávku č. {c}, protože není vyřízená (nemá datum vyřízení).\nLze archivovat pouze vyřízené objednávky."
                    )
                    return
                rows_to_archive.append(row)
                
        if not rows_to_archive:
            return
            
        msg = f"Přesunout objednávku č. {cisla_list[0]} do archivu?" if len(cisla_list) == 1 else f"Přesunout {len(cisla_list)} objednávek do archivu?"
        if QMessageBox.question(
            self, "Archivovat", msg,
            QMessageBox.Yes | QMessageBox.No
        ) != QMessageBox.Yes:
            return

        cisla_set = {str(c).strip() for c in cisla_list}
        db = self.ctx.db

        progress = QProgressDialog("Archivace objednávek...", None, 0, 0, self)
        progress.setWindowTitle("Archiv")
        progress.setWindowModality(Qt.WindowModal)
        progress.setMinimumDuration(0)
        progress.setValue(0)

        def do_archive(progress_cb):
            progress_cb(0, "Načítání položek...")
            items_by = db.read_where_in("tsd04a", "CISLO_OBJ", cisla_set)
            details_by = db.read_where_in("tsd04b", "CISLO_OBJ", cisla_set)

            progress_cb(1, "Kopírování do archivu...")
            db.batch_insert("tsd06", rows_to_archive)
            all_items = [it for lst in items_by.values() for it in lst]
            all_details = [dt for lst in details_by.values() for dt in lst]
            db.batch_insert("tsd06a", all_items)
            db.batch_insert("tsd06b", all_details)

            progress_cb(2, "Mazání z aktivních tabulek...")
            db.batch_delete("tsd04", "CISLO_OBJ", cisla_set)
            db.batch_delete("tsd04a", "CISLO_OBJ", cisla_set)
            db.batch_delete("tsd04b", "CISLO_OBJ", cisla_set)
            return len(cisla_list)

        self._archive_worker = DbWorker(do_archive)

        def on_finished(ok, msg, result):
            progress.close()
            self._archive_worker = None
            if ok:
                msg_text = f"Objednávka přesunuta do archivu." if result == 1 else f"Přesunuto {result} objednávek do archivu."
                QMessageBox.information(self, "Archiv", msg_text)
                self._load_data()
            else:
                QMessageBox.warning(self, "Chyba", f"Chyba při archivaci: {msg}")

        self._archive_worker.progress.connect(lambda step, lbl: progress.setLabelText(lbl))
        self._archive_worker.finished.connect(on_finished)
        self._archive_worker.start()

    def _print(self):
        # If viewing orders for a specific route, print all orders; otherwise print selected
        if self.trasa_filter:
            self._print_all_orders_for_route()
        else:
            cisla = self._selected_cisla()
            if not cisla:
                return
            for cislo in cisla:
                self._print_order(cislo)

    def _print_all_orders_for_route(self):
        """Print all orders visible in the current route view - detailed format with customer info and items."""
        try:
            # Collect all visible order numbers from the table
            cisla_list = []
            
            for row_idx in range(self.table.rowCount()):
                item = self.table.item(row_idx, 0)
                if item:
                    cislo = item.text().strip()
                    if cislo:
                        cisla_list.append(cislo)
            
            if not cisla_list:
                QMessageBox.information(self, "Tisk", "Není co tisknout. Žádné objednávky nejsou zobrazeny.")
                return
            
            def format_price(price):
                return f"{int(price):,}".replace(",", " ")
            
            # Build custom HTML with detailed order information
            html_parts = []
            route_dopravne = 0
            route_celkem = 0
            route_zalohy = 0
            route_k_uhrade = 0
            
            # Route header
            route = self.ctx.db.read_by_key("tsd05", "CISLO", self.trasa_filter)
            d = route.get("DATUM") if route else None
            route_datum_str = d.strftime("%d.%m.%Y") if isinstance(d, (datetime.date, datetime.datetime)) else ""
            route_smer = str(route.get("SMER", "")).strip() if route else self.trasa_filter

            html_parts.append(f"""
            <div style="font-family: Arial, sans-serif; font-size: 20px; font-weight: bold; margin-bottom: 2px;">Rozvozní plán</div>
            <table style="width: 100%; font-family: Arial, sans-serif; border-bottom: 1px solid black; margin-bottom: 8px;" cellpadding="0" cellspacing="0">
                <tr>
                    <td style="font-size: 12px; padding-bottom: 2px;">{route_datum_str} {route_smer}</td>
                    <td style="font-size: 12px; text-align: right; padding-bottom: 2px;">List 1</td>
                </tr>
            </table>
            """)

            items_table = "tsd06a" if self.is_archive else "tsd04a"
            details_table = "tsd06b" if self.is_archive else "tsd04b"
            
            for idx, cislo in enumerate(cisla_list):
                try:
                    # Get order data
                    order = self.ctx.db.read_by_key(self.source_table, "CISLO_OBJ", cislo)
                    if not order:
                        continue
                    if isinstance(order, list):
                        order = order[0]
                    
                    items = self.ctx.db.read_where(items_table, {"CISLO_OBJ": cislo})
                    details = self.ctx.db.read_where(details_table, {"CISLO_OBJ": cislo})

                    # Format data with preferred delivery address
                    eff_addr = get_effective_address(order)
                    jmeno = eff_addr["jmeno"]
                    ulice = eff_addr["ulice"]
                    psc = eff_addr["psc"]
                    posta = eff_addr["posta"]
                    telefon = format_phone_number(str(order.get("TELEFON", "")).strip())
                    mobil = format_phone_number(str(order.get("MOBIL", "")).strip())
                    pozn_int = str(order.get("POZNAMKA", "")).strip()
                    pozn_zak = str(order.get("POZN_ZAK", "")).strip()
                    cena_celk = int(float(order.get("CENA_CELK", 0) or 0))
                    zaloha = int(float(order.get("ZALOHA", 0) or 0))
                    k_uhrade = cena_celk - zaloha
                    
                    route_celkem += cena_celk
                    route_zalohy += zaloha
                    route_k_uhrade += k_uhrade
                    
                    # Symbols (abbreviations)
                    syms = self._symbols_cache.get(cislo, set()) or self._symbols_cache.get(str(cislo), set())
                    syms_str = " ".join(sorted(syms))
                    if syms_str:
                        syms_str = f" {syms_str}"
                        
                    seq_num = idx + 1
                    
                    # Order Header block
                    order_html = f"""
                    <div style="page-break-inside: avoid; border-bottom: 1px solid #ccc; padding-bottom: 10px; margin-bottom: 10px;">
                        <table style="width: 100%; font-size: 14px;" cellpadding="1" cellspacing="0">
                            <tr>
                                <td style="width: 70px; font-weight: bold; vertical-align: top;">{cislo}</td>
                                <td style="font-weight: bold; vertical-align: top;">{jmeno}{syms_str}</td>
                                <td style="width: 200px; font-weight: bold; vertical-align: top;">{posta}</td>
                                <td style="width: 40px; text-align: right; vertical-align: top;">
                                    <div style="border: 2px solid black; font-weight: bold; text-align: center; padding: 2px;">{seq_num}</div>
                                </td>
                            </tr>
                            <tr>
                                <td></td>
                                <td style="vertical-align: top;">{ulice}</td>
                                <td style="vertical-align: top;" colspan="2">Tel.: {telefon}{' ' + mobil if mobil else ''}</td>
                            </tr>
                        </table>
                    """
                    
                    # Notes block
                    if pozn_int or pozn_zak:
                        order_html += "<div style='margin-left: 70px; margin-top: 2px; font-size: 12px;'>"
                        if pozn_int:
                            order_html += f"<strong>Poznámka:</strong> Interní - {pozn_int}<br>"
                        if pozn_zak:
                            prefix = "Zákaznická -" if pozn_int else "<strong>Poznámka:</strong> Zákaznická -"
                            order_html += f"{prefix} {pozn_zak}"
                        order_html += "</div>"
                        
                    # Build items table including accessories (details)
                    items_html = ""
                    printed_details = set()
                    order_dopravne_sum = 0
                    
                    has_items = bool(items) or bool(details)
                    if has_items:
                        items_html = '<table style="width: 100%; font-size: 12px; margin-top: 4px;" cellpadding="0" cellspacing="0">'
                        for it in items:
                            nazev = str(it.get("NAZEV", "")).strip()
                            mnozstvi = int(float(it.get("MNOZSTVI", 1) or 1))
                            cena = int(float(it.get("CENA", 0) or 0))
                            dopravne = int(float(it.get("DOPRAVNE", 0) or 0))
                            
                            celk = cena * mnozstvi
                            
                            items_html += f"""
                            <tr>
                                <td style="width: 70px;"></td>
                                <td style="vertical-align: top;">{nazev}</td>
                                <td style="width: 50px; text-align: right; vertical-align: top;">{mnozstvi}</td>
                                <td style="width: 80px; text-align: right; vertical-align: top;">{format_price(celk)}</td>
                            </tr>
                            """
                            
                            if dopravne > 0:
                                order_dopravne_sum += dopravne * mnozstvi
                                route_dopravne += dopravne * mnozstvi
                                items_html += f"""
                                <tr>
                                    <td style="width: 70px;"></td>
                                    <td style="padding-left: 20px; vertical-align: top;">dopravné</td>
                                    <td style="width: 50px; text-align: right; vertical-align: top;">{mnozstvi}</td>
                                    <td style="width: 80px; text-align: right; vertical-align: top;">{format_price(dopravne * mnozstvi)}</td>
                                </tr>
                                """
                                
                            # Find accessories for this item (details with FINAL == KOD)
                            try:
                                kod = int(float(it.get("KOD", 0) or 0))
                            except Exception:
                                kod = None
                            
                            if details and kod is not None:
                                try:
                                    assembly_parts = self.ctx.db.read_where("tsd02a", {"FINAL": kod})
                                    glass_kods = {int(float(p.get("KOD", 0) or 0)) for p in assembly_parts}
                                except Exception:
                                    glass_kods = set()
                                    
                                for d in details:
                                    try:
                                        final = int(float(d.get("FINAL", 0) or 0))
                                    except Exception:
                                        final = None
                                    if final == kod:
                                        printed_details.add(id(d))
                                        d_kod = int(float(d.get("KOD", 0) or 0))
                                        is_glass = d_kod in glass_kods
                                        
                                        d_nazev = str(d.get("NAZEV", "")).strip()
                                        d_mnoz = int(float(d.get("MNOZSTVI", 1) or 1))
                                        d_cena = int(float(d.get("CENA", 0) or 0))
                                        d_celk = d_cena * d_mnoz
                                        
                                        if is_glass or d_celk == 0:
                                            continue
                                            
                                        items_html += f"""
                                        <tr>
                                            <td style="width: 70px;"></td>
                                            <td style="padding-left: 20px; vertical-align: top;">{d_nazev}</td>
                                            <td style="width: 50px; text-align: right; vertical-align: top;">{d_mnoz}</td>
                                            <td style="width: 80px; text-align: right; vertical-align: top;">{format_price(d_celk)}</td>
                                        </tr>
                                        """
                                        
                        # Unlinked accessories
                        if details:
                            for d in details:
                                if id(d) not in printed_details:
                                    d_nazev = str(d.get("NAZEV", "")).strip()
                                    d_mnoz = int(float(d.get("MNOZSTVI", 1) or 1))
                                    d_cena = int(float(d.get("CENA", 0) or 0))
                                    d_celk = d_cena * d_mnoz
                                    
                                    if d_celk == 0:
                                        continue
                                        
                                    items_html += f"""
                                    <tr>
                                        <td style="width: 70px;"></td>
                                        <td style="padding-left: 20px; vertical-align: top;">{d_nazev}</td>
                                        <td style="width: 50px; text-align: right; vertical-align: top;">{d_mnoz}</td>
                                        <td style="width: 80px; text-align: right; vertical-align: top;">{format_price(d_celk)}</td>
                                    </tr>
                                    """
                                    
                        # Missing shipping from header
                        cena_dopr = int(float(order.get("CENA_DOPR", 0) or 0))
                        if order_dopravne_sum == 0 and cena_dopr > 0:
                            route_dopravne += cena_dopr
                            items_html += f"""
                            <tr>
                                <td style="width: 70px;"></td>
                                <td style="padding-left: 20px; vertical-align: top;">dopravné</td>
                                <td style="width: 50px; text-align: right; vertical-align: top;">1</td>
                                <td style="width: 80px; text-align: right; vertical-align: top;">{format_price(cena_dopr)}</td>
                            </tr>
                            """
                            
                        items_html += "</table>"
                        order_html += items_html
                        
                    # Single order total HTML
                    order_html += f"""
                        <table style="width: 100%; font-size: 12px; margin-top: 2px;" cellpadding="0" cellspacing="0">
                    """
                    if zaloha > 0:
                        order_html += f"""
                            <tr>
                                <td style="text-align: right; padding-top: 5px;">Celkem:</td>
                                <td style="width: 80px; text-align: right; padding-top: 5px;">{format_price(cena_celk)}</td>
                            </tr>
                            <tr>
                                <td style="text-align: right; padding-top: 2px;">Záloha:</td>
                                <td style="width: 80px; text-align: right; padding-top: 2px;">{format_price(zaloha)}</td>
                            </tr>
                        """
                        
                    order_html += f"""
                            <tr>
                                <td style="text-align: right; font-weight: bold; padding-top: 5px;">Celkem v hotovosti</td>
                                <td style="width: 80px; text-align: right; font-weight: bold; padding-top: 5px;">{format_price(k_uhrade)}</td>
                            </tr>
                        </table>
                    </div>
                    """
                    
                    html_parts.append(order_html)
                
                except Exception as e:
                    print(f"Chyba při zpracování objednávky {cislo}: {e}")
                    continue
            
            if not html_parts:
                QMessageBox.warning(self, "Chyba", "Nebylo možné načíst data objednávek.")
                return
                
            # Route Summary
            route_vyrobky = route_celkem - route_dopravne
            summary_html = f"""
            <table style="width: 100%; font-size: 12px; margin-top: 10px; border-top: 1px solid black; padding-top: 5px;" cellpadding="0" cellspacing="0">
                <tr>
                    <td>Celkem výrobky</td>
                    <td style="text-align: right; width: 80px;">{format_price(route_vyrobky)},-</td>
                    <td style="padding-left: 30px;">Celkem dopravné</td>
                    <td style="text-align: right; width: 80px;">{format_price(route_dopravne)},-</td>
                    <td style="padding-left: 30px; font-weight: bold;">Celkem za objednávky</td>
                    <td style="text-align: right; width: 80px; font-weight: bold;">{format_price(route_celkem)},-</td>
                </tr>
            """
            
            if route_zalohy > 0:
                summary_html += f"""
                <tr>
                    <td colspan="4"></td>
                    <td style="padding-left: 30px; padding-top: 5px;">Zálohy celkem</td>
                    <td style="text-align: right; width: 80px; padding-top: 5px;">{format_price(route_zalohy)},-</td>
                </tr>
                """
                
            summary_html += f"""
                <tr>
                    <td colspan="4"></td>
                    <td style="padding-left: 30px; font-weight: bold; padding-top: 5px; font-size: 14px;">K vybrání v hotovosti</td>
                    <td style="text-align: right; width: 80px; font-weight: bold; padding-top: 5px; font-size: 14px;">{format_price(route_k_uhrade)},-</td>
                </tr>
            </table>
            """
            html_parts.append(summary_html)
            
            # Combine all into one HTML document
            combined_html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Rozvozní plán</title>
    <style>
        body {{ font-family: Arial, Calibri, sans-serif; margin: 10px; font-size: 12px; }}
        table {{ border-collapse: collapse; }}
    </style>
</head>
<body>
{''.join(html_parts)}
</body>
</html>"""
            
            from app.views.document_preview_dialog import DocumentPreviewDialog
            dlg = DocumentPreviewDialog(combined_html, f"Tisk tras - {len(cisla_list)} objednávek", parent=self)
            dlg.exec()
        except Exception as e:
            QMessageBox.warning(self, "Chyba tisku", str(e))

    def _print_order(self, cislo):
        try:
            from app.services.document_generator import DocumentGenerator
            gen = DocumentGenerator(self.ctx)
            table = self.source_table
            items_table = "tsd06a" if self.is_archive else "tsd04a"
            html = gen.generate_order(cislo, table=table, items_table=items_table, force_creation_text=True)
            from app.views.document_preview_dialog import DocumentPreviewDialog
            dlg = DocumentPreviewDialog(html, f"Objednávka č. {cislo}", parent=self)
            dlg.exec()
        except Exception as e:
            QMessageBox.warning(self, "Chyba tisku", str(e))

    def _assign_orders(self):
        route = self.ctx.db.read_by_key("tsd05", "CISLO", self.trasa_filter)
        if not route:
            QMessageBox.warning(self, "Chyba", "Trasa nenalezena.")
            return
        d = route.get("DATUM")
        datum_str = d.strftime("%d.%m.%Y") if isinstance(d, (datetime.date, datetime.datetime)) else ""
        smer = str(route.get("SMER", "")).strip()
        from app.views.rozvozni_plany_dialog import PrirazeniObjednavekDialog
        dlg = PrirazeniObjednavekDialog(
            self.ctx, self.trasa_filter, datum_str, smer, parent=self)
        if dlg.exec() == QDialog.Accepted:
            self._load_data()

    def _remove_from_route(self):
        cisla = self._selected_cisla()
        if not cisla:
            return
            
        msg = f"Odebrat objednávku č. {cisla[0]} z této trasy?" if len(cisla) == 1 else f"Odebrat {len(cisla)} vybraných objednávek z této trasy?"
        if QMessageBox.question(
            self, "Odebrat z trasy", msg,
            QMessageBox.Yes | QMessageBox.No
        ) == QMessageBox.Yes:
            updates = {c: {"TRASA": "", "DATUM_NA": None} for c in cisla}
            self.ctx.db.batch_update("tsd04", "CISLO_OBJ", updates)
            self.ctx.invalidate_cache("tsd04")
            self._load_data()

    def _print_skla_route(self):
        if self.table_parts.rowCount() == 0:
            QMessageBox.information(self, "Tisk", "Žádné položky k tisku.")
            return

        import re
        skla = []
        doplnky = []
        dim_pattern = re.compile(r'(\d+(?:[.,]\d+)?)\s*[xX*]\s*(\d+(?:[.,]\d+)?)')

        for i in range(self.table_parts.rowCount()):
            kod_item = self.table_parts.item(i, 0)
            nazev_item = self.table_parts.item(i, 1)
            mnozstvi_item = self.table_parts.item(i, 2)
            
            if not kod_item or not nazev_item or not mnozstvi_item:
                continue

            kod_str = kod_item.text().strip()
            nazev = nazev_item.text().strip()
            mnozstvi = mnozstvi_item.text().strip()

            try:
                kod_int = int(float(kod_str)) if kod_str else 999999
            except ValueError:
                kod_int = 999999

            item_dict = {"kod": kod_str, "nazev": nazev, "mnozstvi": mnozstvi}

            if "sklo" in nazev.lower():
                m = dim_pattern.search(nazev)
                area = 0.0
                if m:
                    w = float(m.group(1).replace(',', '.'))
                    h = float(m.group(2).replace(',', '.'))
                    area = w * h
                skla.append((area, kod_int, item_dict))
            else:
                doplnky.append((kod_int, item_dict))

        skla.sort(key=lambda x: (-x[0], x[1]))
        doplnky.sort(key=lambda x: x[0])

        route_title = f"Trasa: {self.trasa_filter}"
        route = self.ctx.db.read_by_key("tsd05", "CISLO", self.trasa_filter)
        if route:
            d = route.get("DATUM")
            datum_str = d.strftime("%d.%m.%Y") if hasattr(d, "strftime") else str(d)
            smer = str(route.get("SMER", "")).strip()
            route_title = f"Trasa: {datum_str} {smer}"

        html_parts = []
        html_parts.append(f"""
        <div style="font-size: 24px; font-weight: bold; margin-bottom: 5px;">Seznam skel a doplňků k naložení</div>
        <table style="width: 100%; border-bottom: 1px solid black; margin-bottom: 20px;" cellpadding="0" cellspacing="0">
            <tr>
                <td style="font-size: 16px; padding-bottom: 5px;">{route_title}</td>
            </tr>
        </table>
        """)

        html_parts.append('<table style="width: 100%; font-size: 15px;" cellpadding="4" cellspacing="0">')
        html_parts.append('<tr><th style="text-align: left; border-bottom: 1px solid #ccc;">Kód</th><th style="text-align: left; border-bottom: 1px solid #ccc;">Název</th><th style="text-align: right; border-bottom: 1px solid #ccc;">Množství</th></tr>')

        if skla:
            html_parts.append('<tr><td colspan="3" style="font-weight: bold; padding-top: 15px; font-size: 18px;">Skla</td></tr>')
            for _, _, item in skla:
                html_parts.append(f"""
                <tr>
                    <td style="width: 80px;">{item['kod']}</td>
                    <td>{item['nazev']}</td>
                    <td style="text-align: right; font-weight: bold;">{item['mnozstvi']}</td>
                </tr>
                """)

        if doplnky:
            html_parts.append('<tr><td colspan="3" style="font-weight: bold; padding-top: 15px; font-size: 18px;">Doplňky</td></tr>')
            for _, item in doplnky:
                html_parts.append(f"""
                <tr>
                    <td style="width: 80px;">{item['kod']}</td>
                    <td>{item['nazev']}</td>
                    <td style="text-align: right; font-weight: bold;">{item['mnozstvi']}</td>
                </tr>
                """)

        html_parts.append('</table>')

        combined_html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Skla a doplňky</title>
    <style>
        body {{ font-family: "Times New Roman", serif; margin: 20px; }}
        table {{ border-collapse: collapse; }}
    </style>
</head>
<body>
{''.join(html_parts)}
</body>
</html>"""

        from app.views.document_preview_dialog import DocumentPreviewDialog
        dlg = DocumentPreviewDialog(combined_html, f"Skla a doplňky - {self.trasa_filter}", parent=self)
        dlg.exec()
