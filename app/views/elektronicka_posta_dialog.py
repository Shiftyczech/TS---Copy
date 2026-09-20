"""
Elektronická pošta – 2 tabs: Pošta k odeslání / Odeslaná pošta
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget,
    QLabel, QLineEdit, QPushButton, QCheckBox, QTableWidget,
    QTableWidgetItem, QTextEdit, QHeaderView, QMessageBox,
    QAbstractItemView, QSplitter
)
from PySide6.QtCore import Qt
from app.views.sort_items import DateSortItem


class ElektronickaPostaDialog(QDialog):
    def __init__(self, ctx, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self.setWindowTitle("Elektronická pošta")
        self.setMinimumSize(960, 600)
        self.resize(960, 600)
        self._build_ui()
        self._load_data()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_k_odeslani_tab(), "Pošta k odeslání")
        self.tabs.addTab(self._build_odeslana_tab(), "Odeslaná pošta")
        layout.addWidget(self.tabs)

        # Default to sent tab if no pending messages
        self._build_ui_done = True

    # ---- Tab 1: Pošta k odeslání ----
    def _build_k_odeslani_tab(self):
        tab = QWidget()
        layout = QHBoxLayout(tab)

        left = QVBoxLayout()
        # Table
        self.tbl_k_odeslani = QTableWidget(0, 4)
        self.tbl_k_odeslani.setHorizontalHeaderLabels(["Komu", "Předmět", "Připraveno", "Čís.obj."])
        self.tbl_k_odeslani.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.tbl_k_odeslani.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.tbl_k_odeslani.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tbl_k_odeslani.setAlternatingRowColors(True)
        self.tbl_k_odeslani.setSortingEnabled(True)
        self.tbl_k_odeslani.currentCellChanged.connect(self._on_pending_selected)
        left.addWidget(self.tbl_k_odeslani)

        # Detail box
        detail = QVBoxLayout()
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Komu:"))
        self.lbl_p_komu = QLabel()
        self.lbl_p_komu.setStyleSheet("font-weight: bold;")
        row1.addWidget(self.lbl_p_komu)
        row1.addSpacing(20)
        row1.addWidget(QLabel("El. adresa:"))
        self.lbl_p_adresa = QLabel()
        row1.addWidget(self.lbl_p_adresa)
        detail.addLayout(row1)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Předmět:"))
        self.lbl_p_predmet = QLabel()
        row2.addWidget(self.lbl_p_predmet)
        row2.addStretch()
        self.chk_plany = QCheckBox("+plány")
        row2.addWidget(self.chk_plany)
        detail.addLayout(row2)

        self.txt_p_zprava = QTextEdit()
        self.txt_p_zprava.setReadOnly(True)
        detail.addWidget(self.txt_p_zprava)
        left.addLayout(detail)

        layout.addLayout(left, stretch=3)

        # Right buttons
        right = QVBoxLayout()
        self.btn_novy_email = QPushButton("Nový email")
        self.btn_novy_email.setObjectName("accentButton")
        self.btn_odeslat = QPushButton("Odeslat")
        self.btn_odeslat_vse = QPushButton("Odeslat vše")
        self.btn_p_vymazat = QPushButton("Vymazat")
        self.btn_zobrazit_prilohu = QPushButton("Zobrazit přílohu")
        self.btn_editovat_zpravu = QPushButton("Editovat zprávu")

        for btn in [self.btn_novy_email, self.btn_odeslat, self.btn_odeslat_vse, self.btn_p_vymazat,
                     self.btn_zobrazit_prilohu, self.btn_editovat_zpravu]:
            right.addWidget(btn)
        right.addStretch()

        self.btn_p_zpet = QPushButton("Zpět")
        self.btn_p_zpet.setObjectName("dangerButton")
        right.addWidget(self.btn_p_zpet)

        self.btn_novy_email.clicked.connect(self._new_email)
        self.btn_odeslat.clicked.connect(self._send_one)
        self.btn_odeslat_vse.clicked.connect(self._send_all)
        self.btn_p_vymazat.clicked.connect(self._delete_pending)
        self.btn_editovat_zpravu.clicked.connect(self._edit_message)
        self.btn_zobrazit_prilohu.clicked.connect(self._show_attachment)
        self.btn_p_zpet.clicked.connect(self.reject)

        layout.addLayout(right)
        return tab

    # ---- Tab 2: Odeslaná pošta ----
    def _build_odeslana_tab(self):
        tab = QWidget()
        layout = QHBoxLayout(tab)

        left = QVBoxLayout()
        self.tbl_odeslana = QTableWidget(0, 5)
        self.tbl_odeslana.setHorizontalHeaderLabels(["Typ", "Komu", "Předmět", "Odesláno", "Čís.obj."])
        self.tbl_odeslana.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.tbl_odeslana.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.tbl_odeslana.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tbl_odeslana.setAlternatingRowColors(True)
        self.tbl_odeslana.setSortingEnabled(True)
        self.tbl_odeslana.currentCellChanged.connect(self._on_sent_selected)
        left.addWidget(self.tbl_odeslana)

        # Detail
        detail = QVBoxLayout()
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Komu:"))
        self.lbl_s_komu = QLabel()
        self.lbl_s_komu.setStyleSheet("font-weight: bold;")
        row1.addWidget(self.lbl_s_komu)
        row1.addSpacing(20)
        row1.addWidget(QLabel("El. adresa:"))
        self.lbl_s_adresa = QLabel()
        row1.addWidget(self.lbl_s_adresa)
        detail.addLayout(row1)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Předmět:"))
        self.lbl_s_predmet = QLabel()
        row2.addWidget(self.lbl_s_predmet)
        row2.addStretch()
        row2.addWidget(QLabel("Odesláno:"))
        self.lbl_s_odeslano = QLabel()
        self.lbl_s_odeslano.setStyleSheet("font-weight: bold;")
        row2.addWidget(self.lbl_s_odeslano)
        detail.addLayout(row2)

        self.txt_s_zprava = QTextEdit()
        self.txt_s_zprava.setReadOnly(True)
        detail.addWidget(self.txt_s_zprava)
        left.addLayout(detail)

        layout.addLayout(left, stretch=3)

        # Right buttons
        right = QVBoxLayout()
        self.btn_zpet_k_odesl = QPushButton("Zpět k odeslání")
        self.btn_s_vymazat = QPushButton("Vymazat")
        self.btn_s_zobrazit_prilohu = QPushButton("Zobrazit přílohu")
        right.addWidget(self.btn_zpet_k_odesl)
        right.addWidget(self.btn_s_vymazat)
        right.addWidget(self.btn_s_zobrazit_prilohu)
        right.addStretch()
        self.btn_s_zpet = QPushButton("Zpět")
        self.btn_s_zpet.setObjectName("dangerButton")
        right.addWidget(self.btn_s_zpet)

        self.btn_zpet_k_odesl.clicked.connect(self._move_back_to_pending)
        self.btn_s_vymazat.clicked.connect(self._delete_sent)
        self.btn_s_zobrazit_prilohu.clicked.connect(self._show_attachment)
        self.btn_s_zpet.clicked.connect(self.reject)

        layout.addLayout(right)
        return tab

    # ---- Data ----
    def _load_data(self):
        messages = self.ctx.db.read_all("tsd08")
        self.tbl_k_odeslani.setSortingEnabled(False)
        self.tbl_odeslana.setSortingEnabled(False)
        self.tbl_k_odeslani.setRowCount(0)
        self.tbl_odeslana.setRowCount(0)
        self._pending_records = []
        self._sent_records = []

        for msg in messages:
            odeslano = msg.get("ODESLANO", msg.get("odeslano"))
            if odeslano:
                row = self.tbl_odeslana.rowCount()
                self.tbl_odeslana.insertRow(row)
                item_typ = QTableWidgetItem(str(msg.get("TYP", "Mail")))
                item_typ.setData(Qt.UserRole, msg)  # store record
                self.tbl_odeslana.setItem(row, 0, item_typ)
                self.tbl_odeslana.setItem(row, 1, QTableWidgetItem(str(msg.get("KOMU_JMENO", ""))))
                self.tbl_odeslana.setItem(row, 2, QTableWidgetItem(str(msg.get("PREDMET", ""))))
                self.tbl_odeslana.setItem(row, 3, DateSortItem(str(odeslano)))
                self.tbl_odeslana.setItem(row, 4, QTableWidgetItem(str(msg.get("CISLO_OBJ", ""))))
                self._sent_records.append(msg)
            else:
                row = self.tbl_k_odeslani.rowCount()
                self.tbl_k_odeslani.insertRow(row)
                item_komu = QTableWidgetItem(str(msg.get("KOMU_JMENO", "")))
                item_komu.setData(Qt.UserRole, msg)  # store record
                self.tbl_k_odeslani.setItem(row, 0, item_komu)
                self.tbl_k_odeslani.setItem(row, 1, QTableWidgetItem(str(msg.get("PREDMET", ""))))
                self.tbl_k_odeslani.setItem(row, 2, DateSortItem(str(msg.get("VYTVORENO", ""))))
                self.tbl_k_odeslani.setItem(row, 3, QTableWidgetItem(str(msg.get("CISLO_OBJ", ""))))
                self._pending_records.append(msg)

        self.tbl_k_odeslani.setSortingEnabled(True)
        self.tbl_odeslana.setSortingEnabled(True)
        self.tbl_k_odeslani.sortByColumn(2, Qt.DescendingOrder)
        self.tbl_odeslana.sortByColumn(3, Qt.DescendingOrder)
        # Switch to sent tab if nothing pending
        if self.tbl_k_odeslani.rowCount() == 0 and self.tbl_odeslana.rowCount() > 0:
            self.tabs.setCurrentIndex(1)

    def _get_pending_record(self, row):
        if row < 0: return None
        item = self.tbl_k_odeslani.item(row, 0)
        return item.data(Qt.UserRole) if item else None

    def _get_sent_record(self, row):
        if row < 0: return None
        item = self.tbl_odeslana.item(row, 0)
        return item.data(Qt.UserRole) if item else None

    def _on_pending_selected(self, row, col, prev_row, prev_col):
        if row < 0:
            return
        msg = self._get_pending_record(row)
        if not msg:
            return
        self.lbl_p_komu.setText(str(msg.get("KOMU_JMENO", "")))
        self.lbl_p_predmet.setText(str(msg.get("PREDMET", "")))
        self.lbl_p_adresa.setText(str(msg.get("KOMU_MAIL", "")))
        self.txt_p_zprava.setPlainText(str(msg.get("ZPRAVA", "")))
        self.txt_p_zprava.setReadOnly(True)
        
        self.btn_editovat_zpravu.setText("Editovat zprávu")
        self.btn_editovat_zpravu.setStyleSheet("")

    def _on_sent_selected(self, row, col, prev_row, prev_col):
        if row < 0:
            return
        msg = self._get_sent_record(row)
        if not msg:
            return
        self.lbl_s_komu.setText(str(msg.get("KOMU_JMENO", "")))
        self.lbl_s_predmet.setText(str(msg.get("PREDMET", "")))
        self.lbl_s_odeslano.setText(str(msg.get("ODESLANO", "")))
        self.lbl_s_adresa.setText(str(msg.get("KOMU_MAIL", "")))
        self.txt_s_zprava.setPlainText(str(msg.get("ZPRAVA", "")))

    def _send_one(self):
        row = self.tbl_k_odeslani.currentRow()
        msg = self._get_pending_record(row)
        if not msg:
            return
        try:
            from app.services.email_service import EmailService
            svc = EmailService(self.ctx)
            svc.send_from_queue(msg)
            QMessageBox.information(self, "Odesláno", "Zpráva byla odeslána.")
            self._load_data()
        except Exception as e:
            QMessageBox.warning(self, "Chyba", f"Odeslání se nezdařilo:\n{e}")

    def _send_all(self):
        from app.services.email_service import EmailService
        svc = EmailService(self.ctx)
        sent, errors = svc.send_all_pending()
        if errors:
            QMessageBox.warning(self, "Chyby", f"Odesláno {sent} zpráv.\nChyby:\n" + "\n".join(errors))
        else:
            QMessageBox.information(self, "Odesláno", f"Odesláno {sent} zpráv.")
        self._load_data()

    def _delete_pending(self):
        row = self.tbl_k_odeslani.currentRow()
        msg = self._get_pending_record(row)
        if msg and "_RECNO" in msg:
            self.ctx.db.delete_record("tsd08", msg["_RECNO"])
            self._load_data()

    def _delete_sent(self):
        row = self.tbl_odeslana.currentRow()
        msg = self._get_sent_record(row)
        if msg and "_RECNO" in msg:
            self.ctx.db.delete_record("tsd08", msg["_RECNO"])
            self._load_data()

    def _move_back_to_pending(self):
        row = self.tbl_odeslana.currentRow()
        msg = self._get_sent_record(row)
        if msg and "_RECNO" in msg:
            self.ctx.db.update_record("tsd08", msg["_RECNO"], {"ODESLANO": None})
            self._load_data()

    def _edit_message(self):
        row = self.tbl_k_odeslani.currentRow()
        if row < 0:
            return
            
        if self.btn_editovat_zpravu.text() == "Editovat zprávu":
            self.txt_p_zprava.setReadOnly(False)
            self.txt_p_zprava.setFocus()
            self.btn_editovat_zpravu.setText("Uložit změny")
            self.btn_editovat_zpravu.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        else:
            msg = self._get_pending_record(row)
            if msg and "_RECNO" in msg:
                new_text = self.txt_p_zprava.toPlainText()
                self.ctx.db.update_record("tsd08", msg["_RECNO"], {"ZPRAVA": new_text})
                
            self.txt_p_zprava.setReadOnly(True)
            self.btn_editovat_zpravu.setText("Editovat zprávu")
            self.btn_editovat_zpravu.setStyleSheet("")
            
            # Reload to reflect changes safely
            self._load_data()
            if row < self.tbl_k_odeslani.rowCount():
                self.tbl_k_odeslani.selectRow(row)

    def _get_selected_msg(self):
        """Get the selected record from whichever tab is active."""
        if self.tabs.currentIndex() == 0:
            row = self.tbl_k_odeslani.currentRow()
            return self._get_pending_record(row)
        else:
            row = self.tbl_odeslana.currentRow()
            return self._get_sent_record(row)

    def _show_attachment(self):
        msg = self._get_selected_msg()
        if not msg:
            return
        priloha = str(msg.get("PRILOHA", ""))
        if not priloha.strip():
            QMessageBox.information(self, "Příloha", "Zpráva nemá přílohu.")
            return
        from app.views.document_preview_dialog import open_html_in_browser
        open_html_in_browser(priloha, f"priloha_{msg.get('CISLO_OBJ', '')}")

    def _new_email(self):
        from app.views.novy_email_dialog import NovyEmailDialog
        dlg = NovyEmailDialog(self.ctx, parent=self)
        if dlg.exec() == QDialog.Accepted:
            self._load_data()
