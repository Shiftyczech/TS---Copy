"""
PSČ – Grid (PSČ* / Název pošty*) + Opravit / Přidat / Vymazat / Hledat / Konec
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QMessageBox, QFormLayout
)
from PySide6.QtCore import Qt


class PscDialog(QDialog):
    def __init__(self, ctx, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self.setWindowTitle("PSČ")
        self.setMinimumSize(500, 450)
        self.resize(500, 450)
        self._build_ui()
        self._load_data()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        lbl = QLabel("PSČ")
        lbl.setObjectName("titleLabel")
        lbl.setAlignment(Qt.AlignCenter)
        layout.addWidget(lbl)

        self.table = QTableWidget()
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["PSČ", "Název pošty"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSortingEnabled(True)
        self.table.doubleClicked.connect(self._edit)
        layout.addWidget(self.table)

        btn_row = QHBoxLayout()
        self.btn_edit = QPushButton("Opravit")
        self.btn_add = QPushButton("Přidat")
        self.btn_del = QPushButton("Vymazat")
        self.btn_del.setObjectName("dangerButton")
        self.btn_search = QPushButton("Hledat")
        self.btn_close = QPushButton("Konec")
        for b in [self.btn_edit, self.btn_add, self.btn_del, self.btn_search, self.btn_close]:
            btn_row.addWidget(b)
        layout.addLayout(btn_row)

        self.btn_edit.clicked.connect(self._edit)
        self.btn_add.clicked.connect(self._add)
        self.btn_del.clicked.connect(self._delete)
        self.btn_search.clicked.connect(self._search)
        self.btn_close.clicked.connect(self.accept)

    def _load_data(self, filter_text=None):
        rows = self.ctx.db.read_all("tsd01b")
        if filter_text:
            ft = filter_text.lower()
            rows = [r for r in rows if ft in str(r.get("PSC", "")).lower()
                    or ft in str(r.get("NAZ_POSTY", "")).lower()]
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            self.table.setItem(i, 0, QTableWidgetItem(str(r.get("PSC", ""))))
            self.table.setItem(i, 1, QTableWidgetItem(str(r.get("NAZ_POSTY", ""))))
        self.table.setSortingEnabled(True)
        self.table.sortByColumn(1, Qt.AscendingOrder)

    def _selected_row(self):
        sel = self.table.currentRow()
        if sel < 0:
            QMessageBox.warning(self, "PSČ", "Vyberte položku.")
            return None
        return sel

    def _edit(self):
        row = self._selected_row()
        if row is None:
            return
        psc_val = self.table.item(row, 0).text()
        rec = self.ctx.db.read_by_key("tsd01b", "PSC", psc_val)
        if not rec:
            return
        r = rec[0] if isinstance(rec, list) else rec
        dlg = EditPscDialog(r, self)
        if dlg.exec() == QDialog.Accepted:
            data = dlg.get_data()
            self.ctx.db.update("tsd01b", "PSC", psc_val, data)
            self._load_data()

    def _add(self):
        dlg = EditPscDialog(None, self)
        if dlg.exec() == QDialog.Accepted:
            data = dlg.get_data()
            self.ctx.db.insert("tsd01b", data)
            self._load_data()

    def _delete(self):
        row = self._selected_row()
        if row is None:
            return
        psc_val = self.table.item(row, 0).text()
        if QMessageBox.question(
            self, "Potvrzení", f"Opravdu vymazat PSČ {psc_val}?",
            QMessageBox.Yes | QMessageBox.No
        ) == QMessageBox.Yes:
            self.ctx.db.delete("tsd01b", "PSC", psc_val)
            self._load_data()

    def _search(self):
        from PySide6.QtWidgets import QInputDialog
        text, ok = QInputDialog.getText(self, "Hledat", "PSČ nebo název pošty:")
        if ok and text:
            self._load_data(filter_text=text)


class EditPscDialog(QDialog):
    def __init__(self, record=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("PSČ" if record else "Nové PSČ")
        self.setMinimumWidth(350)
        self._build_ui()
        if record:
            self._fill(record)

    def _build_ui(self):
        layout = QFormLayout(self)
        self.edit_psc = QLineEdit()
        self.edit_psc.setMaximumWidth(80)
        self.edit_nazev = QLineEdit()
        layout.addRow("PSČ:", self.edit_psc)
        layout.addRow("Název pošty:", self.edit_nazev)

        btn_row = QHBoxLayout()
        btn_ok = QPushButton("Uložit")
        btn_ok.setObjectName("accentButton")
        btn_cancel = QPushButton("Zpět")
        btn_row.addWidget(btn_ok)
        btn_row.addWidget(btn_cancel)
        layout.addRow(btn_row)

        btn_ok.clicked.connect(self.accept)
        btn_cancel.clicked.connect(self.reject)

    def _fill(self, rec):
        self.edit_psc.setText(str(rec.get("PSC", "")))
        self.edit_nazev.setText(str(rec.get("NAZ_POSTY", "")))

    def get_data(self):
        return {
            "PSC": self.edit_psc.text().strip(),
            "NAZ_POSTY": self.edit_nazev.text().strip(),
        }


class PscBrowseDialog(QDialog):
    """Popup dialog for selecting PSČ – used from objednavka_dialog '...' buttons."""
    def __init__(self, ctx, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self.setWindowTitle("Vybrat PSČ")
        self.setMinimumSize(450, 400)
        self.resize(450, 400)
        self.selected_psc = ""
        self.selected_nazev = ""
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
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["PSČ", "Název pošty"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
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

    def _load_data(self, filter_text=None):
        self._all_rows = self.ctx.db.read_all("tsd01b")
        self._display(self._all_rows if not filter_text else self._filtered(filter_text))

    def _filtered(self, ft):
        ft = ft.lower()
        return [r for r in self._all_rows
                if ft in str(r.get("PSC", "")).lower()
                or ft in str(r.get("NAZ_POSTY", "")).lower()]

    def _filter(self, text):
        self._display(self._filtered(text) if text else self._all_rows)

    def _display(self, rows):
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            self.table.setItem(i, 0, QTableWidgetItem(str(r.get("PSC", ""))))
            self.table.setItem(i, 1, QTableWidgetItem(str(r.get("NAZ_POSTY", ""))))
        self.table.setSortingEnabled(True)
        self.table.sortByColumn(1, Qt.AscendingOrder)

    def _select(self):
        row = self.table.currentRow()
        if row < 0:
            return
        self.selected_psc = self.table.item(row, 0).text()
        self.selected_nazev = self.table.item(row, 1).text()
        self.accept()
