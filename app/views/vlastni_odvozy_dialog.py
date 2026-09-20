import datetime
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget, 
    QTableWidgetItem, QHeaderView, QMessageBox, QLabel
)
from PySide6.QtCore import Qt
from app.views.sort_items import DateSortItem, NumericSortItem
from app.services.document_generator import DocumentGenerator
from app.services.email_service import EmailService

class VlastniOdvozyDialog(QDialog):
    def __init__(self, ctx, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self.setWindowTitle("Objednávky s vlastním odvozem")
        self.resize(900, 500)
        
        layout = QVBoxLayout(self)

        self.table = QTableWidget()
        cols = ["Č.obj.", "Jméno zákazníka", "Přijato", "Telefon", "E-mail", "Výzva na den", "Cena"]
        self.table.setColumnCount(len(cols))
        self.table.setHorizontalHeaderLabels(cols)
        
        self.table.setColumnWidth(0, 60)   # Č.obj.
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch) # Jméno zákazníka
        self.table.setColumnWidth(2, 90)   # Přijato
        self.table.setColumnWidth(3, 100)  # Telefon
        self.table.setColumnWidth(4, 150)  # E-mail
        self.table.setColumnWidth(5, 100)  # Výzva na den
        self.table.setColumnWidth(6, 80)   # Cena
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.DoubleClicked | QTableWidget.EditKeyPressed)
        self.table.setSortingEnabled(True)
        self.table.itemChanged.connect(self._on_item_changed)

        layout.addWidget(self.table)
        
        self.lbl_count = QLabel("Počet: 0")
        layout.addWidget(self.lbl_count)

        btn_row = QHBoxLayout()
        self.btn_open = QPushButton("Oprava objednávky")
        self.btn_send_notice = QPushButton("Odeslat výzvu k vyzvednutí")
        self.btn_change_date = QPushButton("Změnit datum vyzvednutí")
        self.btn_complete = QPushButton("Vyřídit objednávku")
        self.btn_close = QPushButton("Zavřít")
        
        self.btn_open.clicked.connect(self._open_order)
        self.btn_send_notice.clicked.connect(self._send_notices)
        self.btn_change_date.clicked.connect(self._change_pickup_date)
        self.btn_complete.clicked.connect(self._complete_orders)
        self.btn_close.clicked.connect(self.accept)
        
        btn_row.addWidget(self.btn_open)
        btn_row.addWidget(self.btn_send_notice)
        btn_row.addWidget(self.btn_change_date)
        btn_row.addWidget(self.btn_complete)
        btn_row.addStretch()
        btn_row.addWidget(self.btn_close)
        layout.addLayout(btn_row)

        self._load_data()

    def _load_data(self):
        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)
        
        # Read active orders (tsd04)
        all_orders = self.ctx.db.read_all("tsd04")
        
        # We need to exclude archived orders (tsd06) in case some active orders are actually archived
        # This mirrors the logic in SeznamObjednavekDialog
        archived_cisla = {
            str(r.get("CISLO_OBJ", "")).strip()
            for r in self.ctx.db.read_all("tsd06")
        }
        
        filtered = []
        for r in all_orders:
            cislo = str(r.get("CISLO_OBJ", "")).strip()
            if cislo in archived_cisla:
                continue
                
            # Must be vlastní odvoz (VL_ODVOZ) and not completed (DATUM_VYR is empty)
            vl_odvoz = r.get("VL_ODVOZ")
            if vl_odvoz in ("1", 1, True, "True", "true"):
                if not r.get("DATUM_VYR"):
                    filtered.append(r)
        
        def _fmt_date(d):
            if isinstance(d, (datetime.date, datetime.datetime)):
                if getattr(d, 'year', 2000) < 100:
                    try:
                        d = d.replace(year=d.year + 2000)
                    except Exception:
                        pass
                return d.strftime("%d.%m.%Y")
            return str(d) if d else ""

        self.table.blockSignals(True)
        self.table.setRowCount(len(filtered))
        for row, r in enumerate(filtered):
            cislo = str(r.get("CISLO_OBJ", ""))
            item_cislo = NumericSortItem(cislo)
            item_cislo.setData(Qt.UserRole, r)
            item_cislo.setFlags(item_cislo.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(row, 0, item_cislo)
            
            item_jmeno = QTableWidgetItem(str(r.get("Z_JMENO", "")))
            item_jmeno.setFlags(item_jmeno.flags() | Qt.ItemIsEditable)
            self.table.setItem(row, 1, item_jmeno)
            
            datum_pri = r.get("DATUM_PR")
            item_pri = DateSortItem(_fmt_date(datum_pri))
            item_pri.setFlags(item_pri.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(row, 2, item_pri)
            
            item_tel = QTableWidgetItem(str(r.get("TEL", "")))
            item_tel.setFlags(item_tel.flags() | Qt.ItemIsEditable)
            self.table.setItem(row, 3, item_tel)
            
            item_email = QTableWidgetItem(str(r.get("E_MAIL", "")))
            item_email.setFlags(item_email.flags() | Qt.ItemIsEditable)
            self.table.setItem(row, 4, item_email)
            
            datum_vyz = r.get("DATUM_NA")
            item_vyz = DateSortItem(_fmt_date(datum_vyz))
            item_vyz.setFlags(item_vyz.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(row, 5, item_vyz)
            
            cena = r.get("CENA_CELK", 0)
            item_cena = NumericSortItem(f"{cena:.2f}" if isinstance(cena, (int, float)) else str(cena))
            item_cena.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            item_cena.setFlags(item_cena.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(row, 6, item_cena)
            
        self.lbl_count.setText(f"Počet: {len(filtered)}")
        self.table.setSortingEnabled(True)
        self.table.blockSignals(False)

    def _on_item_changed(self, item):
        row = item.row()
        col = item.column()
        cislo_item = self.table.item(row, 0)
        if not cislo_item:
            return
            
        order_data = cislo_item.data(Qt.UserRole)
        cislo = str(order_data.get("CISLO_OBJ", "")) if order_data else cislo_item.text()
        
        field_map = {
            1: "Z_JMENO",
            3: "TEL",
            4: "E_MAIL"
        }
        db_field = field_map.get(col)
        if not db_field:
            return
            
        new_val = item.text()
        self.ctx.db.update("tsd04", "CISLO_OBJ", cislo, {db_field: new_val})
        self.ctx.invalidate_cache("tsd04")
        if order_data:
            order_data[db_field] = new_val

    def _open_order(self):
        selected = self.table.selectedItems()
        if not selected:
            QMessageBox.warning(self, "Upozornění", "Vyberte objednávku.")
            return
        
        row = selected[0].row()
        item = self.table.item(row, 0)
        order_data = item.data(Qt.UserRole)
        cislo = str(order_data.get("CISLO_OBJ", ""))
        
        from app.views.objednavka_dialog import ObjednavkaDialog
        dlg = ObjednavkaDialog(self.ctx, cislo_obj=cislo, mode="edit", parent=self)
        if dlg.exec() == QDialog.Accepted:
            self._load_data()

    def _send_notices(self):
        selected_rows = set()
        for item in self.table.selectedItems():
            selected_rows.add(item.row())
            
        if not selected_rows:
            QMessageBox.warning(self, "Upozornění", "Vyberte alespoň jednu objednávku.")
            return
            
        gen = DocumentGenerator(self.ctx)
        mail_svc = EmailService(self.ctx)
        
        # Read template for Vlastní odvoz (VV)
        tmpl = self.ctx.db.read_where("tsd07", {"TYP": "VV"})
        t = tmpl[0] if isinstance(tmpl, list) and tmpl else (tmpl if tmpl else {})
        
        sent = 0
        skipped = 0
        errors = []
        today = datetime.date.today()
        updates_to_apply = {}

        for row in selected_rows:
            item = self.table.item(row, 0)
            o = item.data(Qt.UserRole)
            cislo = str(o.get("CISLO_OBJ", ""))
            email = str(o.get("E_MAIL", "")).strip()
            
            if not email:
                skipped += 1
                errors.append(f"Obj. {cislo}: Chybí e-mailová adresa.")
                continue

            try:
                html = gen.generate_delivery_notice(cislo)
                
                predmet = str(t.get("PREDMET_E", "")).strip()
                if not predmet:
                    predmet = f"Výzva k expedici – objednávka č. {cislo}"

                jmeno = str(o.get("Z_JMENO", "")).strip()

                zprava = str(t.get("TEXT_MAIL", "")).strip()
                if not zprava:
                    zprava = (f"Vážený zákazníku,\n\n"
                              f"v příloze zasíláme výzvu k expedici "
                              f"Vaší objednávky č. {cislo}.\n\nS pozdravem")

                predmet = gen.replace_text_placeholders(predmet, cislo, table="tsd04")
                zprava = gen.replace_text_placeholders(zprava, cislo, table="tsd04")

                # Email type V for Výzva
                plany = mail_svc._collect_plans_for_order(cislo, "tsd04a", fallback_plan=o.get("PLAN", ""))
                mail_svc.queue_message(cislo, jmeno, email, predmet, zprava, typ="V", priloha=html, plany=plany)
                updates_to_apply[cislo] = {"DATUM_VYZ": today}
                sent += 1

            except Exception as e:
                errors.append(f"Obj. {cislo}: {e}")

        # Batch update DATUM_VYZ
        if updates_to_apply:
            self.ctx.db.batch_update("tsd04", "CISLO_OBJ", updates_to_apply)
            self.ctx.invalidate_cache("tsd04")

        msg = f"Do fronty elektronické pošty bylo úspěšně zařazeno: {sent} výzev."
        if skipped or errors:
            msg += f"\n\nNebylo odesláno: {len(errors)} (viz detaily)"
            
        if errors:
            QMessageBox.warning(self, "Výsledek", msg + "\n\nDetaily:\n" + "\n".join(errors))
        else:
            QMessageBox.information(self, "Výsledek", msg)
            
        if updates_to_apply:
            self._load_data()

    def _complete_orders(self):
        selected_rows = set()
        for item in self.table.selectedItems():
            selected_rows.add(item.row())
            
        if not selected_rows:
            QMessageBox.warning(self, "Upozornění", "Vyberte alespoň jednu objednávku.")
            return
            
        ret = QMessageBox.question(
            self, 
            "Potvrzení", 
            f"Opravdu chcete vyřídit vybrané objednávky ({len(selected_rows)}) a nastavit datum vyřízení na dnešek?",
            QMessageBox.Yes | QMessageBox.No, 
            QMessageBox.No
        )
        
        if ret != QMessageBox.Yes:
            return
            
        today = datetime.date.today()
        updates_to_apply = {}
        
        for row in selected_rows:
            item = self.table.item(row, 0)
            o = item.data(Qt.UserRole)
            cislo = str(o.get("CISLO_OBJ", ""))
            updates_to_apply[cislo] = {"DATUM_VYR": today}
            
        if updates_to_apply:
            self.ctx.db.batch_update("tsd04", "CISLO_OBJ", updates_to_apply)
            self.ctx.invalidate_cache("tsd04")
            QMessageBox.information(self, "Úspěch", f"Úspěšně vyřízeno {len(selected_rows)} objednávek.")
            self._load_data()

    def _change_pickup_date(self):
        selected_rows = set()
        for item in self.table.selectedItems():
            selected_rows.add(item.row())
            
        if not selected_rows:
            QMessageBox.warning(self, "Upozornění", "Vyberte alespoň jednu objednávku.")
            return
            
        from PySide6.QtWidgets import QInputDialog, QLineEdit
        import datetime
        
        default_date = (datetime.date.today() + datetime.timedelta(days=1)).strftime("%d.%m.%Y")
        
        text, ok = QInputDialog.getText(
            self, 
            "Změna data vyzvednutí", 
            "Zadejte nové datum vyzvednutí (např. 15.08.2026). Nechte prázdné pro vymazání data:",
            QLineEdit.Normal,
            default_date
        )
        
        if not ok:
            return
            
        parsed_date = None
        if text.strip():
            try:
                parsed_date = datetime.datetime.strptime(text.strip(), "%d.%m.%Y").date()
            except ValueError:
                QMessageBox.warning(self, "Chyba", "Neplatný formát data. Použijte formát DD.MM.RRRR nebo nechte prázdné.")
                return
                
        updates_to_apply = {}
        for row in selected_rows:
            item = self.table.item(row, 0)
            o = item.data(Qt.UserRole)
            cislo = str(o.get("CISLO_OBJ", ""))
            updates_to_apply[cislo] = {"DATUM_NA": parsed_date}
            
        if updates_to_apply:
            self.ctx.db.batch_update("tsd04", "CISLO_OBJ", updates_to_apply)
            self.ctx.invalidate_cache("tsd04")
            
            # Po změně data nabídnout odeslání e-mailu
            if QMessageBox.question(
                self, 
                "Odeslat výzvy k vyzvednutí?", 
                "Datum úspěšně změněno. Chcete nyní zákazníkům odeslat e-mailem novou výzvu k vyzvednutí?",
                QMessageBox.Yes | QMessageBox.No
            ) == QMessageBox.Yes:
                self._send_notices()
            else:
                self._load_data()
