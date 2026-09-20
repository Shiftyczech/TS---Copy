"""
Rozvozní plány / Aktualizace výjezdních tras
Grid with routes + action buttons on the right.
Routes are identified by tsd05.CISLO (C10 random string).
Orders link via tsd06.TRASA = tsd05.CISLO.
"""
from collections import Counter
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QHeaderView, QAbstractItemView, QMessageBox,
    QInputDialog, QDateEdit, QLineEdit, QLabel, QCheckBox
)
from PySide6.QtCore import Qt, QDate
import datetime
import random
from PySide6.QtGui import QColor
from app.views.sort_items import NumericSortItem, DateSortItem
from app.utils import format_phone_number, get_effective_address


class RozvozniPlanyDialog(QDialog):
    def __init__(self, ctx, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self.setWindowTitle("Aktualizace výjezdních tras")
        self.setMinimumSize(860, 540)
        self.resize(860, 540)
        self._build_ui()
        self._load_data()

    def _build_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        # Left: table (5 cols, CISLO is hidden)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Datum", "Směr trasy", "Počet obj.", "Dnů", ""])
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.setColumnHidden(4, True)  # hidden CISLO column
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSortingEnabled(True)
        self.table.doubleClicked.connect(self._edit_route)
        layout.addWidget(self.table, stretch=3)

        # Right: buttons
        btn_layout = QVBoxLayout()
        
        self.chk_show_completed = QCheckBox("Zobrazit vyřízené trasy")
        self.chk_show_completed.stateChanged.connect(self._load_data)
        btn_layout.addWidget(self.chk_show_completed)
        
        self.btn_opravit = QPushButton("Opravit trasu")
        self.btn_pridat = QPushButton("Přidat novou trasu")
        self.btn_zrusit = QPushButton("Zrušit trasu")
        self.btn_seznam = QPushButton("Seznam objednávek")
        self.btn_tisk = QPushButton("Tisk rozvozního plánu")
        self.btn_odeslat_vyzvy = QPushButton("Zařadit výzvy (do e-mailové fronty)")
        self.btn_vyrizeni = QPushButton("Vyřízení trasy")
        self.btn_ukoncit = QPushButton("Ukončit")
        self.btn_ukoncit.setObjectName("dangerButton")

        for btn in [self.btn_opravit, self.btn_pridat, self.btn_zrusit,
                     self.btn_seznam, self.btn_tisk,
                     self.btn_odeslat_vyzvy, self.btn_vyrizeni]:
            btn_layout.addWidget(btn)

        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_ukoncit)
        layout.addLayout(btn_layout)

        # Connections
        self.btn_pridat.clicked.connect(self._add_route)
        self.btn_opravit.clicked.connect(self._edit_route)
        self.btn_zrusit.clicked.connect(self._delete_route)
        self.btn_seznam.clicked.connect(self._show_orders)
        self.btn_tisk.clicked.connect(self._print_plan)
        self.btn_odeslat_vyzvy.clicked.connect(self._send_notices)
        self.btn_vyrizeni.clicked.connect(self._complete_route)
        self.btn_ukoncit.clicked.connect(self.reject)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_selected_route(self):
        """Return dict {cislo, datum_str, smer, datum_date} or None."""
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Trasy", "Vyberte trasu.")
            return None
        datum_str = self.table.item(row, 0).text() if self.table.item(row, 0) else ""
        smer = self.table.item(row, 1).text() if self.table.item(row, 1) else ""
        cislo = self.table.item(row, 4).text() if self.table.item(row, 4) else ""
        datum_date = None
        if datum_str:
            try:
                parts = datum_str.split(".")
                datum_date = datetime.date(int(parts[2]), int(parts[1]), int(parts[0]))
            except (ValueError, IndexError):
                pass
        return {"cislo": cislo, "datum_str": datum_str, "smer": smer, "datum_date": datum_date}

    def _get_orders_for_route(self, cislo):
        """Return list of orders from tsd06 where TRASA == cislo."""
        return self.ctx.db.read_where("tsd04", {"TRASA": cislo.strip()})

    def _generate_cislo(self):
        """Generate a guaranteed unique 8-digit route ID."""
        while True:
            cislo = str(random.randint(10000000, 99999999))
            if not self.ctx.db.read_where("tsd05", {"CISLO": cislo}):
                return cislo

    @staticmethod
    def _fmt_date(d):
        if isinstance(d, (datetime.date, datetime.datetime)):
            return d.strftime("%d.%m.%Y")
        return str(d) if d else ""

    # ------------------------------------------------------------------
    # Load data
    # ------------------------------------------------------------------

    def _load_data(self):
        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)
        routes = self.ctx.db.read_all("tsd05")
        all_orders = self.ctx.db.read_all("tsd04")
        today = datetime.date.today()
        show_completed = self.chk_show_completed.isChecked()

        # Pre-compute order counts per route in one pass O(n)
        order_counts = Counter(
            str(o.get("TRASA", "")).strip() for o in all_orders
        )

        for r in routes:
            is_completed = str(r.get("STATUS", "")).strip().upper() == "C"
            if is_completed and not show_completed:
                continue

            row = self.table.rowCount()
            self.table.insertRow(row)

            cislo = str(r.get("CISLO", "")).strip()
            datum = r.get("DATUM", "")
            datum_date = datum if isinstance(datum, datetime.date) else None
            datum_str = datum.strftime("%d.%m.%Y") if datum_date else str(datum)
            smer = str(r.get("SMER", "")).strip()

            pocet = order_counts.get(cislo, 0)

            # Days until route
            dnu = (datum_date - today).days if datum_date else ""

            items = [
                DateSortItem(datum_str),
                QTableWidgetItem(smer),
                NumericSortItem(str(pocet)),
                NumericSortItem(str(dnu)),
                QTableWidgetItem(cislo)  # hidden
            ]
            
            # Visual distinction for completed routes
            if is_completed:
                gray_color = QColor("#d3d3d3")
                for item in items:
                    item.setBackground(gray_color)

            for col_idx, item in enumerate(items):
                self.table.setItem(row, col_idx, item)
                
        self.table.setSortingEnabled(True)
        self.table.sortByColumn(0, Qt.DescendingOrder)

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def _add_route(self):
        dlg = EditRouteDialog(parent=self)
        if dlg.exec() == QDialog.Accepted:
            data = {
                "CISLO": self._generate_cislo(),
                "DATUM": dlg.date_edit.date().toPython(),
                "SMER": dlg.edit_smer.text().strip(),
                "POCET_OBJ": 0,
                "STATUS": "",
                "DEL_ROZVOZ": 0,
                "ROZPIS_NAK": False,
            }
            self.ctx.db.insert("tsd05", data)
            self.ctx.invalidate_cache("tsd05")
            self._load_data()

    def _edit_route(self):
        sel = self._get_selected_route()
        if not sel:
            return
        dlg = EditRouteDialog(datum_str=sel["datum_str"], smer=sel["smer"], parent=self)
        if dlg.exec() == QDialog.Accepted:
            new_date = dlg.date_edit.date().toPython()
            
            orders = self._get_orders_for_route(sel["cislo"])
            if orders:
                conflict_orders = []
                for o in orders:
                    d_po = o.get("DATUM_PO")
                    if d_po and hasattr(d_po, 'year'):
                        d_po_date = datetime.date(d_po.year, d_po.month, d_po.day) if isinstance(d_po, datetime.datetime) else d_po
                        if new_date < d_po_date:
                            conflict_orders.append(str(o.get("CISLO_OBJ", "")))
                
                if conflict_orders:
                    QMessageBox.warning(self, "Chyba data", f"Nelze změnit datum trasy na {new_date.strftime('%d.%m.%Y')}, protože následující objednávky mají nastaveno 'dodat po' na pozdější datum:\n" + ", ".join(conflict_orders))
                    return
            
            data = {
                "DATUM": new_date,
                "SMER": dlg.edit_smer.text().strip(),
            }
            self.ctx.db.update("tsd05", "CISLO", sel["cislo"], data)
            self.ctx.invalidate_cache("tsd05")
            
            if orders:
                updates = {str(o.get("CISLO_OBJ", "")): {"DATUM_NA": new_date} for o in orders}
                self.ctx.db.batch_update("tsd04", "CISLO_OBJ", updates)
                self.ctx.invalidate_cache("tsd04")
                
            self._load_data()

    def _delete_route(self):
        sel = self._get_selected_route()
        if not sel:
            return
        orders = self._get_orders_for_route(sel["cislo"])
        if orders:
            QMessageBox.warning(
                self, "Nelze smazat",
                f"Trasa '{sel['smer']}' má přiřazeno {len(orders)} objednávek.\n"
                "Nejdříve odeberte objednávky z trasy."
            )
            return
        reply = QMessageBox.question(self, "Potvrzení",
                                      f"Opravdu chcete zrušit trasu '{sel['smer']}'?")
        if reply == QMessageBox.Yes:
            self.ctx.db.delete("tsd05", "CISLO", sel["cislo"])
            self.ctx.invalidate_cache("tsd05")
            self._load_data()

    # ------------------------------------------------------------------
    # Seznam objednávek
    # ------------------------------------------------------------------

    def _show_orders(self):
        sel = self._get_selected_route()
        if not sel:
            return
        from app.views.seznam_objednavek_dialog import SeznamObjednavekDialog
        dlg = SeznamObjednavekDialog(
            self.ctx, trasa_filter=sel["cislo"], parent=self)
        dlg.setWindowTitle(f"Objednávky trasy {sel['datum_str']} – {sel['smer']}")
        dlg.exec()
        self._load_data()

    # ------------------------------------------------------------------
    # Tisk rozvozního plánu
    # ------------------------------------------------------------------

    def _print_plan(self):
        sel = self._get_selected_route()
        if not sel:
            return
        orders = self._get_orders_for_route(sel["cislo"])
        if not orders:
            QMessageBox.information(self, "Tisk", "Trasa nemá žádné přiřazené objednávky.")
            return

        # Pre-load all items for these orders in ONE scan
        order_cisla = {str(o.get("CISLO_OBJ", "")).strip() for o in orders}
        items_by_cislo = self.ctx.db.read_where_in("tsd04a", "CISLO_OBJ", order_cisla)

        html_rows = []
        for o in orders:
            cislo = str(o.get("CISLO_OBJ", ""))
            eff_addr = get_effective_address(o)
            jmeno = eff_addr["jmeno"]
            adresa = ", ".join(filter(None, [
                eff_addr["ulice"],
                eff_addr["psc"],
                eff_addr["posta"],
            ]))
            telefon = format_phone_number(str(o.get("MOBIL", "") or o.get("TELEFON", "")).strip())
            cena = int(float(o.get("CENA_CELK", 0) or 0))
            vl = "Ano" if o.get("VL_ODVOZ") else ""

            items = items_by_cislo.get(cislo.strip(), [])
            produkty = ", ".join(
                str(it.get("NAZEV", "")).strip()
                for it in items if str(it.get("NAZEV", "")).strip()
            )

            html_rows.append(
                f"<tr>"
                f"<td>{cislo}</td>"
                f"<td>{jmeno}</td>"
                f"<td>{adresa}</td>"
                f"<td>{telefon}</td>"
                f"<td>{produkty}</td>"
                f"<td style='text-align:right'>{cena}&nbsp;Kč</td>"
                f"<td style='text-align:center'>{vl}</td>"
                f"</tr>"
            )

        datum_str = sel["datum_str"]
        smer = sel["smer"]
        html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<title>Rozvozní plán</title>
<style>
  body {{ font-family: Arial, sans-serif; margin: 20px; }}
  h2 {{ margin-bottom: 4px; }}
  h3 {{ color: #555; margin-top: 0; }}
  table {{ border-collapse: collapse; width: 100%; }}
  th, td {{ border: 1px solid #999; padding: 5px 8px; font-size: 12px; }}
  th {{ background: #ddd; }}
</style>
</head><body>
<h2>Rozvozní plán</h2>
<h3>{datum_str} &mdash; {smer}</h3>
<p>Počet objednávek: {len(orders)}</p>
<table>
<tr><th>Č.obj.</th><th>Jméno</th><th>Adresa</th><th>Telefon</th>
<th>Produkty</th><th>Cena</th><th>Vl.odvoz</th></tr>
{"".join(html_rows)}
</table>
</body></html>"""

        from app.views.document_preview_dialog import open_html_in_browser
        open_html_in_browser(html, f"plan_{datum_str}_{smer}")

    # ------------------------------------------------------------------
    # Odeslat výzvy
    # ------------------------------------------------------------------

    def _send_notices(self):
        sel = self._get_selected_route()
        if not sel:
            return
        orders = self._get_orders_for_route(sel["cislo"])
        if not orders:
            QMessageBox.information(self, "Výzvy", "Trasa nemá žádné přiřazené objednávky.")
            return

        already_sent_count = sum(1 for o in orders if o.get("DATUM_VYZ"))
        send_to_all = False

        if already_sent_count > 0:
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle("Odeslat výzvy")
            msg_box.setText(f"Některé objednávky ({already_sent_count} z {len(orders)}) na této trase již mají výzvu odeslanou.\n\nChcete odeslat výzvu všem, nebo jen těm, kteří ji ještě nedostali?")
            btn_only_new = msg_box.addButton("Jen těm, co ještě nedostali", QMessageBox.ActionRole)
            btn_all = msg_box.addButton("Všem", QMessageBox.ActionRole)
            btn_cancel = msg_box.addButton("Zrušit", QMessageBox.RejectRole)
            
            msg_box.exec()
            
            if msg_box.clickedButton() == btn_cancel:
                return
            elif msg_box.clickedButton() == btn_all:
                send_to_all = True
        else:
            reply = QMessageBox.question(
                self, "Odeslat výzvy",
                f"Odeslat výzvy k expedici pro {len(orders)} objednávek na trase\n"
                f"{sel['datum_str']} – {sel['smer']}?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply != QMessageBox.Yes:
                return

        from app.services.document_generator import DocumentGenerator
        from app.services.email_service import EmailService
        gen = DocumentGenerator(self.ctx)
        mail_svc = EmailService(self.ctx)

        # Pre-load templates once (instead of per-order)
        tmpl_cache = {}
        for typ in ("VV", "VR"):
            tmpl = self.ctx.db.read_where("tsd07", {"TYP": typ})
            if tmpl:
                t = tmpl[0] if isinstance(tmpl, list) else tmpl
                tmpl_cache[typ] = t

        sent = 0
        skipped = 0
        errors = []
        today = datetime.date.today()
        updates_to_apply = {}  # cislo -> {DATUM_VYZ: today}

        for o in orders:
            cislo = str(o.get("CISLO_OBJ", ""))
            # Skip if notice already sent and not sending to all
            if o.get("DATUM_VYZ") and not send_to_all:
                skipped += 1
                continue

            email = str(o.get("E_MAIL", "")).strip()
            if not email:
                skipped += 1
                continue

            try:
                html = gen.generate_delivery_notice(cislo)

                vl_odvoz = o.get("VL_ODVOZ", False)
                typ = "VV" if vl_odvoz else "VR"
                t = tmpl_cache.get(typ)
                predmet = str(t.get("PREDMET_E", "")).strip() if t else ""
                if not predmet:
                    predmet = f"Výzva k expedici – objednávka č. {cislo}"
                predmet = gen.replace_text_placeholders(predmet, cislo, "tsd04")

                jmeno = str(o.get("Z_JMENO", "")).strip()

                zprava = str(t.get("TEXT_MAIL", "")).strip() if t else ""
                if not zprava:
                    zprava = (f"Vážený zákazníku,\n\n"
                              f"v příloze zasíláme výzvu k expedici "
                              f"Vaší objednávky č. {cislo}.\n\nS pozdravem")
                zprava = gen.replace_text_placeholders(zprava, cislo, "tsd04")
                
                plany = mail_svc._collect_plans_for_order(cislo, "tsd04a", fallback_plan=o.get("PLAN", ""))

                mail_svc.queue_message(cislo, jmeno, email, predmet, zprava, typ="V", priloha=html, plany=plany)
                updates_to_apply[cislo] = {"DATUM_VYZ": today}
                sent += 1

            except Exception as e:
                errors.append(f"Obj. {cislo}: {e}")

        # Batch update all sent notices at once
        if updates_to_apply:
            self.ctx.db.batch_update("tsd04", "CISLO_OBJ", updates_to_apply)

        msg = (f"Zařazeno do fronty: {sent}\n"
               f"Přeskočeno: {skipped}\n\n"
               f"Nezapomeňte zprávy skutečně odeslat přes "
               f"hlavní menu (Elektronická pošta).")
        if errors:
            msg += "\n\nChyby:\n" + "\n".join(errors)
        QMessageBox.information(self, "Výzvy do fronty", msg)
        self._load_data()

    # ------------------------------------------------------------------
    # Vyřízení trasy
    # ------------------------------------------------------------------

    def _complete_route(self):
        sel = self._get_selected_route()
        if not sel:
            return
        orders = self._get_orders_for_route(sel["cislo"])

        reply = QMessageBox.question(
            self, "Vyřízení trasy",
            f"Opravdu vyřídit trasu '{sel['smer']}' ze dne {sel['datum_str']}?\n"
            f"Bude označeno {len(orders)} objednávek jako vyřízených.",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        today = datetime.date.today()
        updates = {}
        for o in orders:
            c = str(o.get("CISLO_OBJ", ""))
            if not o.get("DATUM_VYR"):
                updates[c] = {"DATUM_VYR": today}
        if updates:
            self.ctx.db.batch_update("tsd04", "CISLO_OBJ", updates)

        # Mark route as completed
        self.ctx.db.update("tsd05", "CISLO", sel["cislo"], {"STATUS": "C"})
        self.ctx.invalidate_cache("tsd05")
        if updates:
            self.ctx.invalidate_cache("tsd04")

        QMessageBox.information(
            self, "Vyřízení trasy",
            f"Trasa '{sel['smer']}' byla vyřízena.\n"
            f"Označeno objednávek: {len(orders)}"
        )
        self._load_data()


class EditRouteDialog(QDialog):
    def __init__(self, datum_str="", smer="", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Trasa")
        self.setMinimumWidth(350)
        layout = QVBoxLayout(self)

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Datum:"))
        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat("dd.MM.yyyy")
        if datum_str:
            try:
                parts = datum_str.split(".")
                self.date_edit.setDate(QDate(int(parts[2]), int(parts[1]), int(parts[0])))
            except (ValueError, IndexError):
                self.date_edit.setDate(QDate.currentDate())
        else:
            self.date_edit.setDate(QDate.currentDate())
        row1.addWidget(self.date_edit)
        layout.addLayout(row1)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Směr:"))
        self.edit_smer = QLineEdit(smer)
        row2.addWidget(self.edit_smer)
        layout.addLayout(row2)

        btn_row = QHBoxLayout()
        btn_ok = QPushButton("OK")
        btn_ok.setObjectName("accentButton")
        btn_cancel = QPushButton("Storno")
        btn_ok.clicked.connect(self.accept)
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_ok)
        btn_row.addWidget(btn_cancel)
        layout.addLayout(btn_row)


class PrirazeniObjednavekDialog(QDialog):
    """Dialog for assigning unassigned orders to a route."""

    def __init__(self, ctx, route_cislo, datum_str, smer, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self.route_cislo = route_cislo
        self.datum_str = datum_str
        self.setWindowTitle(f"Přiřadit objednávky k trase {smer}")
        self.setMinimumSize(900, 500)
        self.resize(900, 550)
        self._label_text = f"Nepřiřazené objednávky — vyberte k přiřazení na trasu {datum_str} – {smer}"
        self._build_ui()
        self._load_data()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        lbl = QLabel(self._label_text)
        lbl.setWordWrap(True)
        layout.addWidget(lbl)

        # Filter
        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("Hledat:"))
        self.edit_search = QLineEdit()
        self.edit_search.setPlaceholderText("Jméno, číslo obj., PSČ...")
        self.edit_search.textChanged.connect(self._filter)
        filter_row.addWidget(self.edit_search)
        self.chk_show_all = QCheckBox("Zobrazit i přiřazené")
        self.chk_show_all.stateChanged.connect(self._filter)
        filter_row.addWidget(self.chk_show_all)
        layout.addLayout(filter_row)

        # Table with checkboxes
        self.table = QTableWidget()
        cols = ["", "Č.obj.", "Jméno zákazníka", "Ulice", "PSČ", "Pošta",
                "Telefon", "Přijato", "Vl.odvoz"]
        self.table.setColumnCount(len(cols))
        self.table.setHorizontalHeaderLabels(cols)
        
        self.table.setColumnWidth(0, 30)
        self.table.setColumnWidth(1, 60)   # Č.obj.
        self.table.setColumnWidth(2, 160)  # Jméno zákazníka
        self.table.setColumnWidth(3, 150)  # Ulice
        self.table.setColumnWidth(4, 65)   # PSČ
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.Stretch) # Pošta
        self.table.setColumnWidth(6, 100)  # Telefon
        self.table.setColumnWidth(7, 90)   # Přijato
        self.table.setColumnWidth(8, 80)   # Vl.odvoz
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSortingEnabled(True)
        layout.addWidget(self.table)

        self.lbl_count = QLabel("Počet: 0")
        layout.addWidget(self.lbl_count)

        # Buttons
        btn_row = QHBoxLayout()
        self.btn_select_all = QPushButton("Vybrat vše")
        self.btn_select_all.clicked.connect(self._select_all)
        self.btn_deselect = QPushButton("Zrušit výběr")
        self.btn_deselect.clicked.connect(self._deselect_all)
        self.btn_assign = QPushButton("Přiřadit vybrané")
        self.btn_assign.setObjectName("accentButton")
        self.btn_assign.clicked.connect(self._assign)
        self.btn_cancel = QPushButton("Zavřít")
        self.btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(self.btn_select_all)
        btn_row.addWidget(self.btn_deselect)
        btn_row.addStretch()
        btn_row.addWidget(self.btn_assign)
        btn_row.addWidget(self.btn_cancel)
        layout.addLayout(btn_row)

    def _load_data(self):
        self._all_orders = self.ctx.db.read_all("tsd04")
        self._filter()

    def _filter(self, *_args):
        show_all = self.chk_show_all.isChecked()
        search = self.edit_search.text().strip().lower()

        rows = []
        import datetime
        route_date = None
        if hasattr(self, "datum_str") and self.datum_str:
            try:
                parts = self.datum_str.split(".")
                route_date = datetime.date(int(parts[2]), int(parts[1]), int(parts[0]))
            except:
                pass

        for o in self._all_orders:
            # Filter: only unassigned by default
            if not show_all:
                trasa = str(o.get("TRASA", "")).strip()
                if trasa:
                    continue
            
            # Ochrana: nezobrazovat objednávky, které mají "Dodat po" později než je datum trasy
            if route_date:
                d_po = o.get("DATUM_PO")
                if d_po and hasattr(d_po, 'year'):
                    d_po_date = datetime.date(d_po.year, d_po.month, d_po.day) if isinstance(d_po, datetime.datetime) else d_po
                    if route_date < d_po_date:
                        continue
                        
            # Skip already completed
            if o.get("DATUM_VYR"):
                continue
            # Skip Vlastni odvoz (cannot be assigned to routes)
            if o.get("VL_ODVOZ"):
                continue
            eff_addr = get_effective_address(o)
            
            # Text search
            if search:
                haystack = " ".join([
                    str(o.get("CISLO_OBJ", "")),
                    eff_addr["jmeno"],
                    eff_addr["ulice"],
                    eff_addr["psc"],
                    eff_addr["posta"],
                    str(o.get("Z_JMENO", "")),
                    str(o.get("Z_ULICE", "")),
                    str(o.get("Z_PSC", "")),
                    str(o.get("Z_POSTA", "")),
                ]).lower()
                if search not in haystack:
                    continue
            rows.append(o)

        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(rows))
        for i, o in enumerate(rows):
            chk = QTableWidgetItem()
            chk.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            chk.setCheckState(Qt.Unchecked)
            chk.setData(Qt.UserRole, str(o.get("CISLO_OBJ", "")))
            self.table.setItem(i, 0, chk)
            self.table.setItem(i, 1, QTableWidgetItem(str(o.get("CISLO_OBJ", ""))))
            
            eff_addr = get_effective_address(o)
            self.table.setItem(i, 2, QTableWidgetItem(eff_addr["jmeno"]))
            self.table.setItem(i, 3, QTableWidgetItem(eff_addr["ulice"]))
            self.table.setItem(i, 4, QTableWidgetItem(eff_addr["psc"]))
            self.table.setItem(i, 5, QTableWidgetItem(eff_addr["posta"]))
            self.table.setItem(i, 6, QTableWidgetItem(
                str(o.get("MOBIL", "") or o.get("TELEFON", "")).strip()))
            d = o.get("DATUM_PR")
            datum_str = d.strftime("%d.%m.%Y") if hasattr(d, 'strftime') else str(d or "")
            self.table.setItem(i, 7, DateSortItem(datum_str))
            self.table.setItem(i, 8, QTableWidgetItem("Ano" if o.get("VL_ODVOZ") else ""))

        self.table.setSortingEnabled(True)
        self.table.sortByColumn(7, Qt.DescendingOrder)
        self.lbl_count.setText(f"Počet: {len(rows)}")

    def _select_all(self):
        for i in range(self.table.rowCount()):
            item = self.table.item(i, 0)
            if item:
                item.setCheckState(Qt.Checked)

    def _deselect_all(self):
        for i in range(self.table.rowCount()):
            item = self.table.item(i, 0)
            if item:
                item.setCheckState(Qt.Unchecked)

    def _assign(self):
        selected = []
        for i in range(self.table.rowCount()):
            item = self.table.item(i, 0)
            if item and item.checkState() == Qt.Checked:
                cislo = item.data(Qt.UserRole)
                if cislo:
                    selected.append(cislo)

        if not selected:
            QMessageBox.warning(self, "Přiřazení", "Nevybrali jste žádné objednávky.")
            return

        reply = QMessageBox.question(
            self, "Přiřadit k trase",
            f"Přiřadit {len(selected)} objednávek k vybrané trase?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        import datetime
        route_date = None
        if hasattr(self, "datum_str") and self.datum_str:
            try:
                parts = self.datum_str.split(".")
                route_date = datetime.date(int(parts[2]), int(parts[1]), int(parts[0]))
            except (ValueError, IndexError):
                pass

        if route_date:
            updates = {cislo: {"TRASA": self.route_cislo, "DATUM_NA": route_date} for cislo in selected}
        else:
            updates = {cislo: {"TRASA": self.route_cislo} for cislo in selected}
            
        self.ctx.db.batch_update("tsd04", "CISLO_OBJ", updates)
        self.ctx.invalidate_cache("tsd04")

        QMessageBox.information(
            self, "Přiřazeno",
            f"Přiřazeno {len(selected)} objednávek k trase."
        )
        self.accept()
