"""
Objednávka Dialog – Nová/Změna/Oprava objednávky
3 tabs: Zákazník, Dodávka, Poznámka
1:1 layout match to the original VFP form.
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget,
    QLabel, QLineEdit, QPushButton, QCheckBox, QRadioButton, QComboBox,
    QGroupBox, QButtonGroup, QDateEdit, QTableWidget, QTableWidgetItem,
    QTextEdit, QHeaderView, QMessageBox, QFrame, QAbstractItemView,
    QCompleter
)
from PySide6.QtCore import Qt, QDate, QStringListModel, QThread, Signal
from PySide6.QtGui import QColor, QBrush
from datetime import date, datetime
from app.views.sort_items import NumericSortItem
from app.views.date_line_edit import DateLineEdit
from app.utils import format_phone_number



class ObjednavkaDialog(QDialog):
    def __init__(self, ctx, mode="new", cislo_obj=None, source_table="tsd04", parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self.mode = mode if cislo_obj is None else "edit"
        self.cislo_obj = cislo_obj
        self.source_table = source_table
        self._setup_title()
        self.setMinimumSize(960, 580)
        self.resize(960, 580)
        self._psc_map = {}  # nazev_posty -> psc
        self._city_map = {} # psc -> nazev_posty
        self._trasa_cislo = ""  # route CISLO reference for date sync
        self._loading_trasa = False  # guard to prevent dateChanged during load
        self._build_ui()

        # Load PSČ lookup table
        self._load_psc_map()
        if cislo_obj:
            self._load_data(cislo_obj)
        else:
            auto_num = self._generate_cislo_obj()
            self.edit_cislo_obj.setPlaceholderText(f"Auto ({auto_num})")

        from PySide6.QtWidgets import QApplication
        QApplication.instance().installEventFilter(self)

    def _setup_title(self):
        titles = {
            "new": "Nová objednávka",
            "change": "Změna objednávky",
            "edit": "Oprava objednávky",
            "vlastni_odvoz": "Vlastní odvoz",
            "vyrizeni_mimo": "Vyřízení objednávky mimo RP",
        }
        self.setWindowTitle(titles.get(self.mode, "Objednávka"))

    def _load_psc_map(self):
        """Load PSČ ↔ název pošty mapping from cache."""
        try:
            self._psc_map, self._city_map = self.ctx.get_psc_maps()
        except Exception:
            self._psc_map = {}
            self._city_map = {}
        self._setup_posta_completer()

    def _setup_posta_completer(self):
        """Attach completers to both Pošta and PSČ fields for bidirectional auto-fill."""
        names = sorted(self._psc_map.keys())
        zips = sorted(self._city_map.keys())
        if not hasattr(self, "_completers"):
            self._completers = []
        for edit_posta, edit_psc in (
            (self.edit_z_posta, self.edit_z_psc),
            (self.edit_m_posta, self.edit_m_psc),
        ):
            # City -> PSČ completer
            comp_city = QCompleter(names, self)
            comp_city.setCaseSensitivity(Qt.CaseInsensitive)
            comp_city.setFilterMode(Qt.MatchContains)
            edit_posta.setCompleter(comp_city)
            self._completers.append(comp_city)
            # Use default arguments to capture the current edit widgets
            comp_city.activated.connect(
                lambda text, ep=edit_psc: ep.setText(self._psc_map.get(text, ""))
            )

            # PSČ -> City completer
            comp_zip = QCompleter(zips, self)
            comp_zip.setCaseSensitivity(Qt.CaseInsensitive)
            comp_zip.setFilterMode(Qt.MatchContains)
            edit_psc.setCompleter(comp_zip)
            self._completers.append(comp_zip)
            comp_zip.activated.connect(
                lambda text, ep=edit_posta: ep.setText(self._city_map.get(text, ""))
            )


    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        # Top bar for order number
        top_bar = QHBoxLayout()
        top_bar.addWidget(QLabel("Číslo obj.:"))
        self.edit_cislo_obj = QLineEdit()
        self.edit_cislo_obj.setPlaceholderText("Auto")
        self.edit_cislo_obj.setMaximumWidth(150)
        self.edit_cislo_obj.setStyleSheet("font-weight: bold;")
        top_bar.addWidget(self.edit_cislo_obj)
        top_bar.addStretch()
        layout.addLayout(top_bar)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_zakaznik_tab(), "Zákazník")
        self.tabs.addTab(self._build_dodavka_tab(), "Dodávka")
        self.tabs.addTab(self._build_poznamka_tab(), "Poznámka")
        layout.addWidget(self.tabs)

        # Bottom button bar
        btn_bar = QHBoxLayout()
        self.btn_ulozit = QPushButton("Uložit")
        self.btn_ulozit.setObjectName("accentButton")
        self.btn_ulozit.setDefault(False)
        self.btn_ulozit.setAutoDefault(False)
        self.btn_ulozit_odeslat = QPushButton("Uložit a odeslat")
        self.btn_ulozit_odeslat.setObjectName("accentButton")
        self.btn_ulozit_odeslat.setDefault(False)
        self.btn_ulozit_odeslat.setAutoDefault(False)
        
        self.btn_ulozit_odeslat_nove = QPushButton("Uložit a odeslat jako NOVÉ")
        self.btn_ulozit_odeslat_nove.setObjectName("accentButton")
        self.btn_ulozit_odeslat_nove.setDefault(False)
        self.btn_ulozit_odeslat_nove.setAutoDefault(False)
        
        self.btn_tisk = QPushButton("Tisk")
        self.btn_tisk.setDefault(False)
        self.btn_tisk.setAutoDefault(False)
        self.btn_zpet = QPushButton("Zpět")
        self.btn_zpet.setObjectName("dangerButton")
        self.btn_zpet.setDefault(False)
        self.btn_zpet.setAutoDefault(False)

        btn_bar.addWidget(self.btn_ulozit)
        btn_bar.addWidget(self.btn_ulozit_odeslat)
        btn_bar.addWidget(self.btn_ulozit_odeslat_nove)
        btn_bar.addWidget(self.btn_tisk)
        btn_bar.addStretch()
        btn_bar.addWidget(self.btn_zpet)
        layout.addLayout(btn_bar)

        self.btn_ulozit.clicked.connect(lambda: self._save(send_now=False))
        self.btn_ulozit_odeslat.clicked.connect(lambda: self._save(send_now=True))
        self.btn_ulozit_odeslat_nove.clicked.connect(lambda: self._save(send_now=True, force_new_email=True))
        self.btn_tisk.clicked.connect(self._print_order)
        self.btn_zpet.clicked.connect(self.reject)

    def eventFilter(self, obj, event):
        """Block Enter/Return completely for this dialog and all its children."""
        from PySide6.QtCore import QEvent, Qt
        if event.type() == QEvent.Type.KeyPress:
            if event.key() in (Qt.Key_Return, Qt.Key_Enter):
                curr = obj
                while curr:
                    if curr == self:
                        return True
                    curr = curr.parent()
        return super().eventFilter(obj, event)

    def done(self, r):
        from PySide6.QtWidgets import QApplication
        QApplication.instance().removeEventFilter(self)
        super().done(r)

    # ===================== TAB 1: Zákazník =====================
    def _build_zakaznik_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(12, 12, 12, 12)

        # Top row: vlastní odvoz + zprávy + úhrada
        top_row = QHBoxLayout()

        self.chk_vlastni_odvoz = QCheckBox("vlastní odvoz")
        self.chk_vlastni_odvoz.stateChanged.connect(self._on_vlastni_odvoz_changed)
        top_row.addWidget(self.chk_vlastni_odvoz)
        top_row.addSpacing(40)

        # Zprávy odeslat
        lbl_zpravy = QLabel("Zprávy odeslat")
        top_row.addWidget(lbl_zpravy)
        self.grp_zpravy = QButtonGroup(self)
        self.rb_postou = QRadioButton("Poštou")
        self.rb_sms = QRadioButton("SMS")
        self.rb_email = QRadioButton("Emailem")
        self.rb_telefonicky = QRadioButton("Telefonicky")
        self.rb_postou.setChecked(True)
        for i, rb in enumerate([self.rb_postou, self.rb_sms, self.rb_email, self.rb_telefonicky]):
            self.grp_zpravy.addButton(rb, i + 1)
            top_row.addWidget(rb)

        layout.addLayout(top_row)

        # Způsob úhrady
        uhrada_row = QHBoxLayout()
        uhrada_row.addSpacing(self.chk_vlastni_odvoz.sizeHint().width() + 40)
        lbl_uhrada = QLabel("Způsob úhrady")
        uhrada_row.addWidget(lbl_uhrada)
        self.grp_uhrada = QButtonGroup(self)
        self.rb_hotovost = QRadioButton("hotově")
        self.rb_prevod = QRadioButton("převodem")
        self.rb_qr = QRadioButton("QR kódem")
        self.rb_hotovost.setChecked(True)
        self.grp_uhrada.addButton(self.rb_hotovost, 1)
        self.grp_uhrada.addButton(self.rb_prevod, 2)
        self.grp_uhrada.addButton(self.rb_qr, 3)
        uhrada_row.addWidget(self.rb_hotovost)
        uhrada_row.addWidget(self.rb_prevod)
        uhrada_row.addWidget(self.rb_qr)
        uhrada_row.addStretch()
        layout.addLayout(uhrada_row)

        # Address groups side by side
        addr_layout = QHBoxLayout()

        # Adresa zákazníka
        grp_zakaznik = QGroupBox("Adresa zákazníka")
        zak_layout = self._build_address_group("z")
        grp_zakaznik.setLayout(zak_layout)
        addr_layout.addWidget(grp_zakaznik)

        # Místo určení
        grp_misto = QGroupBox("Místo určení")
        mist_layout = self._build_address_group("m")
        grp_misto.setLayout(mist_layout)
        addr_layout.addWidget(grp_misto)

        layout.addLayout(addr_layout)

        self._auto_copy_enabled = False

        # Contact row: Telefon | Mobil | Email
        contact_row = QHBoxLayout()
        contact_row.addWidget(QLabel("Telefon:"))
        self.edit_telefon = QLineEdit()
        self.edit_telefon.setMaximumWidth(150)
        contact_row.addWidget(self.edit_telefon)
        contact_row.addWidget(QLabel("Mobil:"))
        self.edit_mobil = QLineEdit()
        self.edit_mobil.setMaximumWidth(150)
        contact_row.addWidget(self.edit_mobil)
        contact_row.addWidget(QLabel("Email:"))
        self.edit_email = QLineEdit()
        contact_row.addWidget(self.edit_email)
        layout.addLayout(contact_row)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setObjectName("separator")
        layout.addWidget(sep)

        # Date row 1: Datum přijetí | Dodat po | Dodací lhůta
        date_row1 = QHBoxLayout()
        lbl_dp = QLabel("Datum přijetí:")
        lbl_dp.setStyleSheet("font-weight: bold;")
        date_row1.addWidget(lbl_dp)
        self.date_prijeti = QDateEdit()
        self.date_prijeti.setCalendarPopup(True)
        self.date_prijeti.setDate(QDate.currentDate())
        self.date_prijeti.setDisplayFormat("dd.MM.yyyy")
        date_row1.addWidget(self.date_prijeti)
        date_row1.addSpacing(20)
        date_row1.addWidget(QLabel("Dodat po:"))
        self.date_dodat_po = DateLineEdit()
        date_row1.addWidget(self.date_dodat_po)
        date_row1.addSpacing(20)
        lbl_lhuta = QLabel("Dodací lhůta:")
        lbl_lhuta.setStyleSheet("font-weight: bold;")
        date_row1.addWidget(lbl_lhuta)
        self.edit_lhuta = QLineEdit("v průběhu 2 až 10 týdnů")
        date_row1.addWidget(self.edit_lhuta)
        layout.addLayout(date_row1)

        # Date row 2: Datum výzvy | Výzva na den | Datum vyřízení
        date_row2 = QHBoxLayout()
        date_row2.addWidget(QLabel("Datum výzvy:"))
        self.date_vyzvy = DateLineEdit()
        date_row2.addWidget(self.date_vyzvy)
        date_row2.addSpacing(20)
        date_row2.addWidget(QLabel("Výzva na den:"))
        self.date_vyzva_den = DateLineEdit()
        date_row2.addWidget(self.date_vyzva_den)
        date_row2.addSpacing(20)
        date_row2.addWidget(QLabel("Datum vyřízení:"))
        self.date_vyrizeni = DateLineEdit()
        date_row2.addWidget(self.date_vyrizeni)
        layout.addLayout(date_row2)

        return tab

    def _build_address_group(self, prefix: str):
        layout = QVBoxLayout()
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Jméno:"))
        edit_jmeno = QLineEdit()
        row1.addWidget(edit_jmeno)
        layout.addLayout(row1)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Ulice:"))
        edit_ulice = QLineEdit()
        row2.addWidget(edit_ulice)
        layout.addLayout(row2)

        row3 = QHBoxLayout()
        row3.addWidget(QLabel("Pošta:"))
        edit_posta = QLineEdit()
        row3.addWidget(edit_posta)
        layout.addLayout(row3)

        row4 = QHBoxLayout()
        row4.addWidget(QLabel("PSČ:"))
        edit_psc = QLineEdit()
        edit_psc.setMaximumWidth(70)
        row4.addWidget(edit_psc)
        row4.addStretch()
        layout.addLayout(row4)

        # Store references
        setattr(self, f"edit_{prefix}_jmeno", edit_jmeno)
        setattr(self, f"edit_{prefix}_ulice", edit_ulice)
        setattr(self, f"edit_{prefix}_posta", edit_posta)
        setattr(self, f"edit_{prefix}_psc", edit_psc)

        return layout

    def _sync_to_misto(self, field, text):
        if self._auto_copy_enabled:
            getattr(self, f"edit_m_{field}").setText(text)

    def _check_manual_edit(self):
        """Disable auto-copy if místo určení differs from zákazník."""
        for field in ("jmeno", "ulice", "psc", "posta"):
            z = getattr(self, f"edit_z_{field}").text()
            m = getattr(self, f"edit_m_{field}").text()
            if z != m:
                self._auto_copy_enabled = False
                return

    # ===================== TAB 2: Dodávka =====================
    def _build_dodavka_tab(self):
        tab = QWidget()
        layout = QHBoxLayout(tab)
        layout.setContentsMargins(8, 8, 8, 8)

        # Per-greenhouse parts data: {sestava_uid: [{kod, nazev, cena, pocet, is_glass}, ...]}
        # sestava_uid is a unique id assigned when adding a sestava
        self._dily_per_sestava = {}
        self._sestava_uid_counter = 0
        self._current_sestava_uid = None  # currently selected sestava UID

        # Left: tables
        tables_layout = QVBoxLayout()

        # Sestavy table – compact, fits 2-3 rows
        self.tbl_sestavy = QTableWidget(0, 5)
        self.tbl_sestavy.setHorizontalHeaderLabels(["Kód", "Název sestavy", "Cena", "Počet", "Doprava"])
        self.tbl_sestavy.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.tbl_sestavy.setColumnWidth(4, 80)
        self.tbl_sestavy.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tbl_sestavy.setAlternatingRowColors(True)
        self.tbl_sestavy.verticalHeader().setVisible(False)
        self.tbl_sestavy.verticalHeader().setDefaultSectionSize(36)
        self.tbl_sestavy.verticalHeader().setMinimumSectionSize(36)
        self.tbl_sestavy.setSortingEnabled(True)
        # Fixed height for 2-3 rows + header
        self.tbl_sestavy.setMinimumHeight(80)
        self.tbl_sestavy.setMaximumHeight(145)
        self.tbl_sestavy.currentCellChanged.connect(self._on_sestava_selected)
        # Hidden column 5 for UID tracking
        self.tbl_sestavy.setColumnCount(6)
        self.tbl_sestavy.setColumnHidden(5, True)
        self.tbl_sestavy.cellChanged.connect(self._on_sestava_cell_changed)
        tables_layout.addWidget(self.tbl_sestavy)

        # Label showing which greenhouse's parts are displayed
        self.lbl_dily_sestava = QLabel("Díly sestavy:")
        self.lbl_dily_sestava.setStyleSheet("font-weight: bold; margin-top: 4px; margin-bottom: 2px;")
        tables_layout.addWidget(self.lbl_dily_sestava)

        # Díly table – takes remaining space
        self.tbl_dily = QTableWidget(0, 4)
        self.tbl_dily.setHorizontalHeaderLabels(["Kód", "Název dílu", "Cena", "Počet"])
        self.tbl_dily.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.tbl_dily.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tbl_dily.setAlternatingRowColors(True)
        self.tbl_dily.verticalHeader().setVisible(False)
        self.tbl_dily.verticalHeader().setDefaultSectionSize(36)
        self.tbl_dily.verticalHeader().setMinimumSectionSize(36)
        self.tbl_dily.setSortingEnabled(False)  # We manage sorting manually
        self.tbl_dily.cellChanged.connect(self._on_dil_cell_changed)
        tables_layout.addWidget(self.tbl_dily)

        layout.addLayout(tables_layout, stretch=3)

        # Right: buttons + plánky
        right_layout = QVBoxLayout()

        # Sestava buttons
        self.btn_opravit_sestavu = QPushButton("Opravit sestavu")
        self.btn_pridat_sestavu = QPushButton("Přidat sestavu")
        self.btn_vymazat_sestavu = QPushButton("Vymazat sestavu")
        right_layout.addWidget(self.btn_opravit_sestavu)
        right_layout.addWidget(self.btn_pridat_sestavu)
        right_layout.addWidget(self.btn_vymazat_sestavu)
        right_layout.addSpacing(20)

        # Díl buttons
        self.btn_opravit_dil = QPushButton("Opravit díl")
        self.btn_pridat_dil = QPushButton("Přidat díl")
        self.btn_vymazat_dil = QPushButton("Vymazat díl")
        right_layout.addWidget(self.btn_opravit_dil)
        right_layout.addWidget(self.btn_pridat_dil)
        right_layout.addWidget(self.btn_vymazat_dil)
        right_layout.addSpacing(20)

        # Plánky základů
        right_layout.addWidget(QLabel("Plánek základů:"))
        self.cmb_planek = QComboBox()
        self.cmb_planek.addItem("Žádný", "")
        self.cmb_planek.addItem("CENTRAL", "A")
        self.cmb_planek.addItem("OPTIMAL", "B")
        self.cmb_planek.addItem("MAXIMAL", "C")
        self.cmb_planek.addItem("SATELIT 2", "D")
        self.cmb_planek.addItem("SATELIT 2.5", "E")
        right_layout.addWidget(self.cmb_planek)
        right_layout.addStretch()

        right_widget = QWidget()
        right_widget.setLayout(right_layout)
        right_widget.setFixedWidth(200)
        layout.addWidget(right_widget)

        # Connect buttons
        self.btn_pridat_sestavu.clicked.connect(self._add_sestava)
        self.btn_vymazat_sestavu.clicked.connect(self._remove_sestava)
        self.btn_opravit_sestavu.clicked.connect(self._edit_sestava)
        self.btn_pridat_dil.clicked.connect(self._add_dil)
        self.btn_vymazat_dil.clicked.connect(self._remove_dil)
        self.btn_opravit_dil.clicked.connect(self._edit_dil)

        return tab

    def _next_sestava_uid(self):
        """Generate a unique ID for each sestava row (used as dict key)."""
        self._sestava_uid_counter += 1
        return self._sestava_uid_counter

    def _get_current_sestava_uid(self):
        """Get the UID of the currently selected sestava row."""
        row = self.tbl_sestavy.currentRow()
        if row < 0:
            return None
        uid_item = self.tbl_sestavy.item(row, 5)
        if uid_item:
            return int(uid_item.text())
        return None

    def _on_sestava_selected(self, row, col, prev_row, prev_col):
        """When user clicks a different greenhouse, save current parts and show new ones."""
        # Save parts from the previously selected greenhouse
        self._save_current_dily_to_memory()

        if row < 0:
            self.lbl_dily_sestava.setText("Díly sestavy:")
            self.tbl_dily.setRowCount(0)
            self._current_sestava_uid = None
            return

        uid_item = self.tbl_sestavy.item(row, 5)
        if not uid_item:
            return
        uid = int(uid_item.text())
        self._current_sestava_uid = uid

        nazev_item = self.tbl_sestavy.item(row, 1)
        nazev = nazev_item.text() if nazev_item else ""
        self.lbl_dily_sestava.setText(f"Díly sestavy: {nazev}")

        # Load parts for this greenhouse
        self._display_dily_for_sestava(uid)

    def _on_sestava_cell_changed(self, row, col):
        if getattr(self, "_ignore_cell_changes", False):
            return
        
        uid_item = self.tbl_sestavy.item(row, 5)
        if not uid_item:
            return  # Row not fully initialized
            
        if col in (3, 4):  # Počet or Doprava
            if col == 3:
                uid = int(uid_item.text())
                kod_item = self.tbl_sestavy.item(row, 0)
                kod = int(kod_item.text() or 0) if kod_item else 0
                
                try:
                    new_pocet = int(float(self.tbl_sestavy.item(row, 3).text() or 1))
                except ValueError:
                    new_pocet = 1
                new_pocet = max(1, new_pocet)
                
                # Base glass definition
                base_glass = self._load_glass_for_sestava(kod)
                base_glass_dict = {p["kod"]: int(float(p["pocet"])) for p in base_glass}
                
                self._save_current_dily_to_memory()
                parts = self._dily_per_sestava.get(uid, [])
                for p in parts:
                    if p.get("is_glass") and p.get("kod") in base_glass_dict:
                        p["pocet"] = str(base_glass_dict[p["kod"]] * new_pocet)
                
                if self._current_sestava_uid == uid:
                    self._display_dily_for_sestava(uid)

            self._recalc_totals()

    def _on_dil_cell_changed(self, row, col):
        if getattr(self, "_ignore_cell_changes", False):
            return
        if col == 3:  # Počet
            # Let _recalc_totals handle saving memory and updating totals
            self._recalc_totals()

    def _save_current_dily_to_memory(self):
        """Read the current tbl_dily content back into _dily_per_sestava."""
        uid = self._current_sestava_uid
        if uid is None:
            return
        parts = []
        for r in range(self.tbl_dily.rowCount()):
            kod_item = self.tbl_dily.item(r, 0)
            nazev_item = self.tbl_dily.item(r, 1)
            cena_item = self.tbl_dily.item(r, 2)
            pocet_item = self.tbl_dily.item(r, 3)
            # Check if this is a glass item by its stored data
            is_glass = bool(nazev_item.data(Qt.UserRole)) if nazev_item else False
            parts.append({
                "kod": kod_item.text() if kod_item else "",
                "nazev": nazev_item.text() if nazev_item else "",
                "cena": cena_item.text() if cena_item else "0",
                "pocet": pocet_item.text() if pocet_item else "1",
                "is_glass": is_glass,
            })
        self._dily_per_sestava[uid] = parts

    def _display_dily_for_sestava(self, uid):
        """Display parts for the given sestava UID in the tbl_dily table.
        Glass items shown at top in red, then other parts sorted by code."""
        parts = self._dily_per_sestava.get(uid, [])

        # Split into glass and non-glass
        glass_parts = [p for p in parts if p.get("is_glass")]
        other_parts = [p for p in parts if not p.get("is_glass")]

        sorted_parts = glass_parts + other_parts

        self._ignore_cell_changes = True
        self.tbl_dily.setRowCount(len(sorted_parts))
        red_brush = QBrush(QColor(200, 30, 30))
        for i, p in enumerate(sorted_parts):
            kod_item = QTableWidgetItem(str(p.get("kod", "")))
            nazev_item = QTableWidgetItem(str(p.get("nazev", "")))
            cena_item = NumericSortItem(str(p.get("cena", "0")))
            pocet_item = NumericSortItem(str(p.get("pocet", "1")))

            if p.get("is_glass"):
                for item in (kod_item, nazev_item, cena_item, pocet_item):
                    item.setForeground(red_brush)
            
            # Store the is_glass flag directly in the item data
            nazev_item.setData(Qt.UserRole, bool(p.get("is_glass")))

            self.tbl_dily.setItem(i, 0, kod_item)
            self.tbl_dily.setItem(i, 1, nazev_item)
            self.tbl_dily.setItem(i, 2, cena_item)
            self.tbl_dily.setItem(i, 3, pocet_item)
        self._ignore_cell_changes = False

    def _load_glass_for_sestava(self, kod_sestavy):
        """Load glass/parts from tsd02a for the given assembly code.
        Returns list of dicts with is_glass=True and cena=0 (included in assembly price)."""
        try:
            all_parts = self.ctx.db.read_where("tsd02a", {"FINAL": int(kod_sestavy)})
        except Exception:
            return []
        glass_items = []
        for p in all_parts:
            glass_items.append({
                "kod": str(p.get("KOD", "")),
                "nazev": str(p.get("NAZEV", "")),
                "cena": "0",  # Included in assembly price
                "pocet": str(int(float(p.get("MNOZSTVI", 1) or 1))),
                "is_glass": True,
            })
        return glass_items

    # ===================== TAB 3: Poznámka =====================
    def _build_poznamka_tab(self):
        tab = QWidget()
        layout = QHBoxLayout(tab)
        layout.setContentsMargins(12, 12, 12, 12)

        # Left: text areas
        left_layout = QVBoxLayout()
        left_layout.addWidget(QLabel("Text poznámky (pro interní účely):"))
        self.txt_pozn_intern = QTextEdit()
        left_layout.addWidget(self.txt_pozn_intern)

        left_layout.addWidget(QLabel("Text poznámky (pro zákazníka):"))
        self.txt_pozn_zakaz = QTextEdit()
        left_layout.addWidget(self.txt_pozn_zakaz)

        # Bottom row: objednávka změněna + trasa
        bottom_row = QHBoxLayout()
        self.chk_zmenena = QCheckBox("objednávka změněna")
        bottom_row.addWidget(self.chk_zmenena)
        bottom_row.addSpacing(20)
        bottom_row.addWidget(QLabel("Trasa:"))
        self.lbl_trasa_info = QLineEdit()
        self.lbl_trasa_info.setReadOnly(True)
        bottom_row.addWidget(self.lbl_trasa_info)
        
        self.btn_zmenit_trasu = QPushButton("Změnit trasu")
        self.btn_zmenit_trasu.clicked.connect(self._on_zmenit_trasu)
        bottom_row.addWidget(self.btn_zmenit_trasu)
        
        self.btn_odebrat_trasu = QPushButton("Odebrat z trasy")
        self.btn_odebrat_trasu.clicked.connect(self._on_odebrat_trasu)
        self.btn_odebrat_trasu.setObjectName("dangerButton")
        bottom_row.addWidget(self.btn_odebrat_trasu)
        
        left_layout.addLayout(bottom_row)

        layout.addLayout(left_layout, stretch=3)

        # Right: summary
        right_layout = QVBoxLayout()
        right_layout.setAlignment(Qt.AlignTop)
        right_layout.addSpacing(20)

        for label_text, attr_name in [("Sestavy", "lbl_cena_sestavy"),
                                       ("Doplňky", "lbl_cena_doplnky"),
                                       ("Dopravné", "lbl_cena_dopravne")]:
            row = QHBoxLayout()
            row.addStretch()
            row.addWidget(QLabel(label_text))
            lbl = QLineEdit("0")
            lbl.setReadOnly(True)
            lbl.setMaximumWidth(80)
            lbl.setAlignment(Qt.AlignRight)
            row.addWidget(lbl)
            row.addWidget(QLabel("Kč"))
            right_layout.addLayout(row)
            setattr(self, attr_name, lbl)

        # Total - bold
        total_row = QHBoxLayout()
        total_row.addStretch()
        lbl_celkem = QLabel("Celkem")
        lbl_celkem.setStyleSheet("font-weight: bold;")
        total_row.addWidget(lbl_celkem)
        self.lbl_cena_celkem = QLineEdit("0")
        self.lbl_cena_celkem.setReadOnly(True)
        self.lbl_cena_celkem.setMaximumWidth(80)
        self.lbl_cena_celkem.setAlignment(Qt.AlignRight)
        self.lbl_cena_celkem.setStyleSheet("font-weight: bold;")
        total_row.addWidget(self.lbl_cena_celkem)
        total_row.addWidget(QLabel("Kč"))
        right_layout.addLayout(total_row)

        right_layout.addStretch()
        layout.addLayout(right_layout, stretch=1)

        return tab

    # ===================== Route date sync =====================
    def _update_trasa_label(self):
        trasa_cislo = getattr(self, "_trasa_cislo", "")
        if not trasa_cislo:
            self.lbl_trasa_info.setText("Zatím nepřiřazeno")
            return
        route = self.ctx.db.read_by_key("tsd05", "CISLO", trasa_cislo)
        if route:
            d = route.get("DATUM")
            if d and hasattr(d, 'year'):
                d_str = d.strftime("%d.%m.%Y")
            else:
                d_str = "?"
            smer = str(route.get("SMER", "")).strip()
            self.lbl_trasa_info.setText(f"{d_str} - {smer}")
        else:
            self.lbl_trasa_info.setText("Neznámá trasa")

    def _on_zmenit_trasu(self):
        if self.chk_vlastni_odvoz.isChecked():
            QMessageBox.warning(self, "Změnit trasu", "Objednávka má zvolený vlastní odvoz, nelze ji přiřadit na rozvozní trasu.")
            return
            
        all_routes = self.ctx.db.read_all("tsd05")
        import datetime
        
        # Parse DATUM_PO
        datum_po = None
        text_po = self.date_dodat_po.text().strip()
        if text_po and text_po != "dd.mm.rrrr":
            try:
                datum_po = datetime.datetime.strptime(text_po, "%d.%m.%Y").date()
            except ValueError:
                pass
                
        routes = []
        for r in all_routes:
            if str(r.get("STATUS", "")).strip().upper() == "C":
                continue
                
            if datum_po:
                d = r.get("DATUM")
                if d and hasattr(d, 'year'):
                    d_date = datetime.date(d.year, d.month, d.day) if isinstance(d, datetime.datetime) else d
                    if d_date < datum_po:
                        continue
                        
            routes.append(r)
            
        if not routes:
            QMessageBox.information(self, "Změnit trasu", "Nejsou k dispozici žádné aktivní trasy.")
            return
            
        import datetime
        routes.sort(key=lambda r: r.get("DATUM") or datetime.date.min)
        
        items = []
        cisla = []
        for r in routes:
            d = r.get("DATUM")
            d_str = d.strftime("%d.%m.%Y") if d and hasattr(d, 'year') else "?"
            smer = str(r.get("SMER", "")).strip()
            items.append(f"{d_str} - {smer}")
            cisla.append(r.get("CISLO", ""))
            
        from PySide6.QtWidgets import QInputDialog
        item, ok = QInputDialog.getItem(self, "Vyberte trasu", "Aktivní trasy:", items, 0, False)
        if ok and item:
            idx = items.index(item)
            self._trasa_cislo = cisla[idx]
            self._update_trasa_label()
            self.chk_zmenena.setChecked(True)

    def _on_odebrat_trasu(self):
        self._trasa_cislo = ""
        self._update_trasa_label()
        self.chk_zmenena.setChecked(True)

    def _on_vlastni_odvoz_changed(self, state):
        is_vlastni = self.chk_vlastni_odvoz.isChecked()
        default_dopr = self._default_dopravne()
        
        # Zobrazení okénka pro zadání data pouze při ruční změně (ne při načítání)
        if is_vlastni and not getattr(self, "_is_loading_data", False):
            from PySide6.QtWidgets import QInputDialog
            import datetime
            
            # Defaultně nabídneme datum za týden jako nápovědu
            default_date = (datetime.date.today() + datetime.timedelta(days=7)).strftime("%d.%m.%Y")
            
            text, ok = QInputDialog.getText(
                self, 
                "Výzva na den", 
                "Zadejte datum, kdy si zákazník přeje vyzvednout objednávku (např. 15.08.2026):",
                QLineEdit.Normal,
                default_date
            )
            
            if ok and text.strip():
                self.date_vyzva_den.setText(text.strip())
        
        self._ignore_cell_changes = True
        for r in range(self.tbl_sestavy.rowCount()):
            dopr_item = self.tbl_sestavy.item(r, 4)
            if dopr_item:
                if is_vlastni:
                    current_val = dopr_item.text()
                    if not dopr_item.data(Qt.UserRole):
                        dopr_item.setData(Qt.UserRole, current_val)
                    dopr_item.setText("0")
                else:
                    old_val = dopr_item.data(Qt.UserRole)
                    if old_val:
                        dopr_item.setText(str(old_val))
                    else:
                        dopr_item.setText(str(default_dopr))
        self._ignore_cell_changes = False
        self._recalc_totals()

    # ===================== Table operations =====================
    def _default_dopravne(self) -> int:
        """Return default shipping price from config (tsd00), fallback 17000."""
        try:
            cfg = self.ctx.db.get_first_record("tsd00")
            if cfg:
                val = cfg.get("DOPRAVNE", cfg.get("dopravne", 17000))
                return int(float(val or 17000))
        except Exception:
            pass
        return 17_000

    def _add_sestava(self):
        from app.views.vyber_sestavy_dialog import VyberSestavyDialog
        dlg = VyberSestavyDialog(self.ctx, parent=self)
        if dlg.exec() == QDialog.Accepted and dlg.selected:
            default_dopr = self._default_dopravne() if not self.chk_vlastni_odvoz.isChecked() else 0
            self.tbl_sestavy.setSortingEnabled(False)
            row = self.tbl_sestavy.rowCount()
            self.tbl_sestavy.insertRow(row)
            self.tbl_sestavy.setItem(row, 0, QTableWidgetItem(str(dlg.selected["KOD"])))
            self.tbl_sestavy.setItem(row, 1, QTableWidgetItem(dlg.selected["NAZEV"]))
            self.tbl_sestavy.setItem(row, 2, NumericSortItem(str(dlg.selected["CENA"])))
            self.tbl_sestavy.setItem(row, 3, NumericSortItem("1"))
            self.tbl_sestavy.setItem(row, 4, NumericSortItem(str(default_dopr)))
            # Assign UID and auto-load glass items from tsd02a
            uid = self._next_sestava_uid()
            self.tbl_sestavy.setItem(row, 5, QTableWidgetItem(str(uid)))
            glass_items = self._load_glass_for_sestava(dlg.selected["KOD"])
            self._dily_per_sestava[uid] = glass_items
            self.tbl_sestavy.setSortingEnabled(True)
            
            # Select the new row to show its parts (find it since it might have moved after sorting)
            for r in range(self.tbl_sestavy.rowCount()):
                uid_item = self.tbl_sestavy.item(r, 5)
                if uid_item and int(uid_item.text()) == uid:
                    self.tbl_sestavy.setCurrentCell(r, 0)
                    break
                    
            self._recalc_totals()

    def _remove_sestava(self):
        row = self.tbl_sestavy.currentRow()
        if row >= 0:
            uid_item = self.tbl_sestavy.item(row, 5)
            if uid_item:
                uid = int(uid_item.text())
                self._dily_per_sestava.pop(uid, None)
            self._current_sestava_uid = None
            self.tbl_sestavy.removeRow(row)
            # If rows remain, the selection will trigger _on_sestava_selected
            if self.tbl_sestavy.rowCount() == 0:
                self.tbl_dily.setRowCount(0)
                self.lbl_dily_sestava.setText("Díly sestavy:")
            self._recalc_totals()

    def _edit_sestava(self):
        row = self.tbl_sestavy.currentRow()
        if row < 0:
            return
        from app.views.edit_sestava_dialog import EditSestavyDialog
        nazev = self.tbl_sestavy.item(row, 1).text() if self.tbl_sestavy.item(row, 1) else ""
        current_cena = int(float(self.tbl_sestavy.item(row, 2).text() or 0)) if self.tbl_sestavy.item(row, 2) else 0
        current_pocet = int(float(self.tbl_sestavy.item(row, 3).text() or 1)) if self.tbl_sestavy.item(row, 3) else 1
        item_dopr = self.tbl_sestavy.item(row, 4)
        if item_dopr and item_dopr.text().strip():
            current_dopr = int(float(item_dopr.text()))
        else:
            current_dopr = self._default_dopravne() if not self.chk_vlastni_odvoz.isChecked() else 0
        dlg = EditSestavyDialog(nazev=nazev, current_cena=current_cena, current_pocet=current_pocet, current_dopravne=current_dopr, parent=self)
        if dlg.exec() == QDialog.Accepted:
            new_pocet = dlg.get_pocet()
            self._ignore_cell_changes = True
            self.tbl_sestavy.setSortingEnabled(False)
            self.tbl_sestavy.setItem(row, 2, NumericSortItem(str(dlg.get_cena())))
            self.tbl_sestavy.setItem(row, 3, NumericSortItem(str(new_pocet)))
            self.tbl_sestavy.setItem(row, 4, NumericSortItem(str(dlg.get_dopravne())))
            self.tbl_sestavy.resizeRowToContents(row)
            self.tbl_sestavy.setSortingEnabled(True)
            self._ignore_cell_changes = False
            
            # Přepočítat skla podle nového počtu skleníků
            if new_pocet != current_pocet and current_pocet > 0:
                uid_item = self.tbl_sestavy.item(row, 5)
                if uid_item:
                    uid = int(uid_item.text())
                    self._save_current_dily_to_memory()
                    parts = self._dily_per_sestava.get(uid, [])
                    for p in parts:
                        if p.get("is_glass"):
                            try:
                                old_val = float(p.get("pocet", 1))
                                new_val = round((old_val / current_pocet) * new_pocet)
                                p["pocet"] = str(int(max(1, new_val)))
                            except ValueError:
                                pass
                    # Pokud je tento skleník zrovna vybraný, překreslit
                    if self._current_sestava_uid == uid:
                        self._display_dily_for_sestava(uid)

            self._recalc_totals()

    def _add_dil(self):
        uid = self._get_current_sestava_uid()
        if uid is None:
            QMessageBox.warning(self, "Díl", "Nejprve vyberte sestavu, ke které chcete přidat díl.")
            return
        from app.views.vyber_dilu_dialog import VyberDiluDialog
        dlg = VyberDiluDialog(self.ctx, parent=self)
        if dlg.exec() == QDialog.Accepted and dlg.selected:
            # Save current table state, add new part, redisplay
            self._save_current_dily_to_memory()
            parts = self._dily_per_sestava.get(uid, [])
            parts.append({
                "kod": str(dlg.selected["KOD"]),
                "nazev": dlg.selected["NAZEV"],
                "cena": str(dlg.selected["CENA"]),
                "pocet": "1",
                "is_glass": False,
            })
            self._dily_per_sestava[uid] = parts
            self._display_dily_for_sestava(uid)
            self._recalc_totals()

    def _remove_dil(self):
        row = self.tbl_dily.currentRow()
        if row >= 0:
            # Save current state, remove the part, redisplay
            self._save_current_dily_to_memory()
            uid = self._current_sestava_uid
            if uid is not None:
                parts = self._dily_per_sestava.get(uid, [])
                if 0 <= row < len(parts):
                    del parts[row]
                    self._dily_per_sestava[uid] = parts
                self._display_dily_for_sestava(uid)
            self._recalc_totals()

    def _edit_dil(self):
        row = self.tbl_dily.currentRow()
        if row < 0:
            return
        from app.views.edit_pocet_dialog import EditPocetDialog
        current = self.tbl_dily.item(row, 3).text() if self.tbl_dily.item(row, 3) else "1"
        dlg = EditPocetDialog(current_qty=int(current), parent=self)
        if dlg.exec() == QDialog.Accepted:
            # Update the count in tbl_dily directly, then save to memory
            self._ignore_cell_changes = True
            self.tbl_dily.setItem(row, 3, NumericSortItem(str(dlg.get_pocet())))
            self._ignore_cell_changes = False
            self._save_current_dily_to_memory()
            self._recalc_totals()

    def _recalc_totals(self):
        # Save current table to memory first
        self._save_current_dily_to_memory()

        total_sestavy = 0.0
        total_dopravne = 0.0
        for r in range(self.tbl_sestavy.rowCount()):
            cena_item = self.tbl_sestavy.item(r, 2)
            pocet_item = self.tbl_sestavy.item(r, 3)
            dopr_item = self.tbl_sestavy.item(r, 4)
            cena = float(cena_item.text() or 0) if cena_item else 0.0
            pocet = int(pocet_item.text() or 0) if pocet_item else 0
            total_sestavy += cena * pocet
            if not self.chk_vlastni_odvoz.isChecked():
                dopr = float(dopr_item.text() or 0) if dopr_item else 0.0
                total_dopravne += dopr * pocet

        # Sum parts across ALL greenhouses (not just the currently displayed one)
        total_dily = 0.0
        for uid, parts in self._dily_per_sestava.items():
            for p in parts:
                try:
                    cena = float(p.get("cena", 0) or 0)
                    pocet = int(float(p.get("pocet", 1) or 1))
                except (ValueError, TypeError):
                    cena = 0.0
                    pocet = 1
                total_dily += cena * pocet

        self.lbl_cena_sestavy.setText(str(int(total_sestavy)))
        self.lbl_cena_doplnky.setText(str(int(total_dily)))
        self.lbl_cena_dopravne.setText(str(int(total_dopravne)))
        self.lbl_cena_celkem.setText(str(int(total_sestavy + total_dily + total_dopravne)))

    # ===================== Print =====================
    def _print_order(self):
        """Generate order HTML and open in browser for printing."""
        cislo = self.cislo_obj
        if not cislo:
            QMessageBox.information(
                self, "Tisk",
                "Objednávka ještě nebyla uložena. Nejprve uložte objednávku a pak ji vytiskněte."
            )
            return
        try:
            from app.services.document_generator import DocumentGenerator
            from app.views.document_preview_dialog import open_html_in_browser
            gen = DocumentGenerator(self.ctx)
            items_table = "tsd06a" if self.source_table == "tsd06" else "tsd04a"
            html = gen.generate_order(
                cislo,
                table=self.source_table,
                items_table=items_table,
                force_creation_text=True
            )
            open_html_in_browser(html, f"Objednavka_{cislo}")
        except Exception as e:
            QMessageBox.warning(self, "Chyba tisku", str(e))

    # ===================== Save / Load =====================
    def _generate_cislo_obj(self) -> str:
        """Generate the next available order number by finding max across both tables."""
        max_num = 0
        for table_name in ("tsd04", "tsd06"):
            try:
                raw = self.ctx.db.get_max_value(table_name, "CISLO_OBJ")
                if raw is not None and str(raw).strip():
                    num = int(float(str(raw).strip()))
                    if num > max_num:
                        max_num = num
            except (ValueError, TypeError):
                pass
        return str(max_num + 1)

    def _collect_data(self) -> dict:
        data = {}
        ui_val = getattr(self, "edit_cislo_obj", None)
        ui_text = ui_val.text().strip() if ui_val else ""
        if ui_text:
            data["CISLO_OBJ"] = ui_text
        else:
            data["CISLO_OBJ"] = self.cislo_obj or self._generate_cislo_obj()

        data["Z_JMENO"] = self.edit_z_jmeno.text().strip()
        data["Z_ULICE"] = self.edit_z_ulice.text().strip()
        data["Z_PSC"] = self.edit_z_psc.text().strip()
        data["Z_POSTA"] = self.edit_z_posta.text().strip()
        data["U_JMENO"] = self.edit_m_jmeno.text().strip()
        data["U_ULICE"] = self.edit_m_ulice.text().strip()
        data["U_PSC"] = self.edit_m_psc.text().strip()
        data["U_POSTA"] = self.edit_m_posta.text().strip()
        data["TELEFON"] = format_phone_number(self.edit_telefon.text().strip())
        data["MOBIL"] = format_phone_number(self.edit_mobil.text().strip())
        data["E_MAIL"] = self.edit_email.text().strip()
        data["VL_ODVOZ"] = self.chk_vlastni_odvoz.isChecked()
        if data["VL_ODVOZ"]:
            data["TRASA"] = ""
        data["TYP_ZPRAVY"] = self.grp_zpravy.checkedId()
        data["ZP_UHR"] = self.grp_uhrada.checkedId()
        data["PLAN"] = self.cmb_planek.currentData()
        
        # Dates and Lhuta
        data["DATUM_PR"] = self.date_prijeti.date().toPython()
        
        def _parse_date(text):
            text = text.strip()
            if not text or text == "dd.mm.rrrr":
                return None
            try:
                return datetime.strptime(text, "%d.%m.%Y").date()
            except ValueError:
                return None

        data["DATUM_PO"] = _parse_date(self.date_dodat_po.text())
        data["DATUM_VYZ"] = _parse_date(self.date_vyzvy.text())
        data["DATUM_NA"] = _parse_date(self.date_vyzva_den.text())
        data["DATUM_VYR"] = _parse_date(self.date_vyrizeni.text())
        data["DOD_LHUTA"] = self.edit_lhuta.text().strip()

        # Prices
        try:
            data["CENA_SEST"] = int(self.lbl_cena_sestavy.text() or 0)
        except ValueError:
            data["CENA_SEST"] = 0
        try:
            data["CENA_DOPL"] = int(self.lbl_cena_doplnky.text() or 0)
        except ValueError:
            data["CENA_DOPL"] = 0
        try:
            data["CENA_DOPR"] = int(self.lbl_cena_dopravne.text() or 0)
        except ValueError:
            data["CENA_DOPR"] = 0
        try:
            data["CENA_CELK"] = int(self.lbl_cena_celkem.text() or 0)
        except ValueError:
            data["CENA_CELK"] = 0
        # Poznámka tab fields
        data["POZNAMKA"] = self.txt_pozn_intern.toPlainText()
        data["POZN_ZAK"] = self.txt_pozn_zakaz.toPlainText()
        data["ZMENA"] = self.chk_zmenena.isChecked()
        data["TRASA"] = getattr(self, "_trasa_cislo", "")
        return data

    def _has_important_changes(self, data: dict) -> bool:
        """Return True if customer-relevant fields changed since the order was loaded."""
        snap = getattr(self, "_original_snapshot", None)
        if snap is None:
            return False  # no snapshot → new order handled separately

        # Compare scalar fields that matter to the customer
        customer_fields = [
            "U_JMENO", "U_ULICE", "U_PSC", "U_POSTA",
            "CENA_CELK", "POZN_ZAK", "E_MAIL", "MOBIL",
        ]
        for f in customer_fields:
            if str(data.get(f, "")) != str(snap.get(f, "")):
                return True

        # Compare order items (sestavy + díly) via their snapshots
        if self._sestavy_snapshot() != snap.get("_sestavy", []):
            return True
        if self._dily_snapshot() != snap.get("_dily", []):
            return True

        return False

    def _sestavy_snapshot(self) -> list:
        rows = []
        for r in range(self.tbl_sestavy.rowCount()):
            rows.append((
                self.tbl_sestavy.item(r, 0).text() if self.tbl_sestavy.item(r, 0) else "",
                self.tbl_sestavy.item(r, 3).text() if self.tbl_sestavy.item(r, 3) else "1",
            ))
        return sorted(rows)

    def _dily_snapshot(self) -> list:
        """Snapshot all parts across all greenhouses for change detection."""
        self._save_current_dily_to_memory()
        rows = []
        for uid, parts in self._dily_per_sestava.items():
            for p in parts:
                rows.append((
                    str(p.get("kod", "")),
                    str(p.get("pocet", "1")),
                ))
        return sorted(rows)

    def _save(self, send_now=False, force_new_email=False):
        self._save_current_dily_to_memory()
        has_any_parts = any(len(parts) > 0 for parts in self._dily_per_sestava.values())
        if self.tbl_sestavy.rowCount() == 0 and not has_any_parts:
            QMessageBox.warning(self, "Chyba", "Nelze uložit objednávku bez položek (sestav nebo dílů).")
            return

        data = self._collect_data()
        
        # Validace maximální délky textových polí pro databázi
        field_limits = [
            ("Z_POSTA", "Pošta (zákazník)", 80),
            ("U_POSTA", "Pošta (místo určení)", 80),
            ("Z_JMENO", "Jméno (zákazník)", 30),
            ("U_JMENO", "Jméno (místo určení)", 30),
            ("Z_ULICE", "Ulice (zákazník)", 30),
            ("U_ULICE", "Ulice (místo určení)", 30),
            ("Z_PSC", "PSČ (zákazník)", 5),
            ("U_PSC", "PSČ (místo určení)", 5),
            ("TELEFON", "Telefon", 16),
            ("MOBIL", "Mobil", 14),
            ("E_MAIL", "E-mail", 50),
            ("DOD_LHUTA", "Dodací lhůta", 25),
        ]
        for key, label, max_len in field_limits:
            val = str(data.get(key) or "")
            val_len = len(val.strip())
            if val_len > max_len:
                diff = val_len - max_len
                QMessageBox.warning(
                    self,
                    "Příliš dlouhý text",
                    f"Pole '{label}' je příliš dlouhé.\n\n"
                    f"Maximální povolená délka: {max_len} znaků\n"
                    f"Zadáno: {val_len} znaků (přebývá {diff} znaků)\n\n"
                    "Zkraťte prosím text a zkuste objednávku uložit znovu."
                )
                return

        # Ochrana proti uložení s DATUM_PO pozdějším než je datum přiřazené trasy
        if getattr(self, "_trasa_cislo", None) and data.get("DATUM_PO"):
            route = self.ctx.db.read_by_key("tsd05", "CISLO", self._trasa_cislo)
            if route:
                route_date = route.get("DATUM")
                if route_date and hasattr(route_date, 'year'):
                    import datetime
                    r_date = datetime.date(route_date.year, route_date.month, route_date.day) if isinstance(route_date, datetime.datetime) else route_date
                    d_po = data["DATUM_PO"]
                    d_po_date = datetime.date(d_po.year, d_po.month, d_po.day) if isinstance(d_po, datetime.datetime) else d_po
                    if d_po_date > r_date:
                        QMessageBox.warning(
                            self, "Chyba data",
                            f"Objednávka je přiřazena na trasu dne {r_date.strftime('%d.%m.%Y')}.\n"
                            f"Datum 'Dodat po' ({d_po_date.strftime('%d.%m.%Y')}) nesmí být pozdější než datum trasy.\n"
                            "Buď změňte datum, nebo nejprve odstraňte objednávku z trasy."
                        )
                        return

        is_new = self.mode == "new"

        if not is_new and send_now and not force_new_email:
            data["ZMENA"] = True
            self.chk_zmenena.setChecked(True)
            
        if data.get("ZMENA"):
            data["DATUM_ZM"] = date.today()

        try:
            if is_new:
                self.cislo_obj = data["CISLO_OBJ"]
                self.ctx.db.insert(self.source_table, data)
                old_cislo_obj = None
            else:
                old_cislo_obj = self.cislo_obj
                self.ctx.db.update(self.source_table, "CISLO_OBJ", old_cislo_obj, data)
                self.cislo_obj = data["CISLO_OBJ"]
        except Exception as e:
            QMessageBox.critical(self, "Chyba při ukládání", f"Nepodařilo se uložit objednávku do databáze:\n{str(e)}")
            return

        if not self._save_items(old_cislo_obj=old_cislo_obj):
            return
        QMessageBox.information(self, "Uloženo", "Objednávka byla aktualizována.")

        if send_now:
            has_email = bool(data.get("E_MAIL", "").strip())
            if not has_email:
                QMessageBox.warning(self, "Upozornění", "E-mailová adresa není vyplněna, zpráva nebyla odeslána.")
            else:
                from app.services.email_service import EmailService
                from PySide6.QtWidgets import QApplication
                from PySide6.QtCore import Qt
                svc = EmailService(self.ctx)
                if is_new or force_new_email:
                    svc.queue_confirmation(self.cislo_obj, table=self.source_table)
                else:
                    svc.queue_change_notification(self.cislo_obj, table=self.source_table)
                
                QApplication.setOverrideCursor(Qt.WaitCursor)
                try:
                    sent, errors = svc.send_all_pending()
                    if errors:
                        QMessageBox.warning(self, "Chyba při odesílání", f"Při odesílání e-mailu došlo k chybám:\n" + "\n".join(errors))
                    elif sent > 0:
                        QMessageBox.information(self, "Odesláno", "E-mail byl úspěšně odeslán.")
                except Exception as e:
                    QMessageBox.warning(self, "Chyba", f"Došlo k chybě: {str(e)}")
                finally:
                    QApplication.restoreOverrideCursor()

        self.accept()

    def _save_items(self, old_cislo_obj=None):
        if not self.cislo_obj:
            return False
        # Ensure in-memory data is current
        self._save_current_dily_to_memory()

        delete_cislo_obj = old_cislo_obj if old_cislo_obj else self.cislo_obj
        items_table = "tsd06a" if self.source_table == "tsd06" else "tsd04a"
        details_table = "tsd06b" if self.source_table == "tsd06" else "tsd04b"
        
        # Read existing items into memory for rollback
        old_sestavy = self.ctx.db.read_where(items_table, {"CISLO_OBJ": delete_cislo_obj})
        old_dily = self.ctx.db.read_where(details_table, {"CISLO_OBJ": delete_cislo_obj})

        # Collect sestavy and build UID->KOD mapping
        sestavy_rows = []
        uid_to_kod = {}  # Map UID to assembly KOD for linking parts
        for r in range(self.tbl_sestavy.rowCount()):
            kod_str = self.tbl_sestavy.item(r, 0).text() if self.tbl_sestavy.item(r, 0) else "0"
            cena_str = self.tbl_sestavy.item(r, 2).text() if self.tbl_sestavy.item(r, 2) else "0"
            mnozstvi_str = self.tbl_sestavy.item(r, 3).text() if self.tbl_sestavy.item(r, 3) else "1"
            dopr_item = self.tbl_sestavy.item(r, 4)
            dopr_str = dopr_item.text() if dopr_item else "0"
            uid_item = self.tbl_sestavy.item(r, 5)
            if uid_item:
                uid_to_kod[int(uid_item.text())] = int(kod_str or 0)
            sestavy_rows.append({
                "CISLO_OBJ": self.cislo_obj,
                "KOD": int(kod_str or 0),
                "NAZEV": self.tbl_sestavy.item(r, 1).text(),
                "CENA": float(cena_str or 0),
                "MNOZSTVI": int(mnozstvi_str or 1),
                "DOPRAVNE": float(dopr_str or 0),
            })
            
        # Collect díly from all greenhouses with FINAL set to assembly KOD
        dily_rows = []
        for uid, parts in self._dily_per_sestava.items():
            final_kod = uid_to_kod.get(uid, 0)
            for p in parts:
                kod_str = str(p.get("kod", "0"))
                cena_str = str(p.get("cena", "0"))
                mnozstvi_str = str(p.get("pocet", "1"))
                try:
                    mnozstvi = int(float(mnozstvi_str)) if mnozstvi_str and mnozstvi_str.strip() else 1
                except (ValueError, TypeError):
                    mnozstvi = 1
                try:
                    kod_int = int(kod_str or 0)
                except (ValueError, TypeError):
                    kod_int = 0
                dily_rows.append({
                    "CISLO_OBJ": self.cislo_obj,
                    "FINAL": final_kod,
                    "KOD": kod_int,
                    "NAZEV": str(p.get("nazev", "")),
                    "CENA": float(cena_str or 0),
                    "MNOZSTVI": mnozstvi,
                })

        print(f"[DEBUG_SAVE] Collected sestavy: {len(sestavy_rows)}, dily: {len(dily_rows)}")
        for i, d in enumerate(dily_rows):
            print(f"  Díl {i}: FINAL={d.get('FINAL')}, KOD={d.get('KOD')}, NAZEV={repr(d.get('NAZEV'))}, CENA={d.get('CENA')}, MNOZSTVI={d.get('MNOZSTVI')}")

        try:
            # Delete old items
            del_s = self.ctx.db.delete_where(items_table, {"CISLO_OBJ": delete_cislo_obj})
            del_d = self.ctx.db.delete_where(details_table, {"CISLO_OBJ": delete_cislo_obj})
            print(f"[DEBUG_SAVE] Deleted {del_s} sestavy, {del_d} díly pro {delete_cislo_obj}")
            
            # Batch insert new items
            if sestavy_rows:
                self.ctx.db.batch_insert(items_table, sestavy_rows)
            if dily_rows:
                self.ctx.db.batch_insert(details_table, dily_rows)
                
            print("[DEBUG_SAVE] Batch insert successful")
            return True
        except Exception as e:
            print(f"[DEBUG_SAVE] ERROR during batch_insert: {e}")
            import traceback
            traceback.print_exc()
            # Rollback
            try:
                self.ctx.db.delete_where(items_table, {"CISLO_OBJ": self.cislo_obj})
                self.ctx.db.delete_where(details_table, {"CISLO_OBJ": self.cislo_obj})
                if old_sestavy:
                    self.ctx.db.batch_insert(items_table, old_sestavy)
                if old_dily:
                    self.ctx.db.batch_insert(details_table, old_dily)
                QMessageBox.critical(self, "Chyba databáze", f"Chyba při ukládání položek: {str(e)}\n\nPůvodní položky byly obnoveny.")
            except Exception as rollback_err:
                QMessageBox.critical(self, "Kritická chyba", f"Kritická chyba při ukládání položek: {str(e)}\n\nPokus o obnovu původních dat selhal: {str(rollback_err)}")
            return False

    def _load_data(self, cislo_obj: str):  # noqa: C901
        self._is_loading_data = True
        self._auto_copy_enabled = False
        record = self.ctx.db.read_by_key(self.source_table, "CISLO_OBJ", cislo_obj)
        if not record:
            QMessageBox.warning(self, "Chyba", f"Objednávka {cislo_obj} nenalezena.")
            return
        self.edit_cislo_obj.setText(str(cislo_obj))
        self.edit_z_jmeno.setText(str(record.get("Z_JMENO", "")))
        self.edit_z_ulice.setText(str(record.get("Z_ULICE", "")))
        self.edit_z_psc.setText(str(record.get("Z_PSC", "")))
        self.edit_z_posta.setText(str(record.get("Z_POSTA", "")))
        self.edit_m_jmeno.setText(str(record.get("U_JMENO", "")))
        self.edit_m_ulice.setText(str(record.get("U_ULICE", "")))
        self.edit_m_psc.setText(str(record.get("U_PSC", "")))
        self.edit_m_posta.setText(str(record.get("U_POSTA", "")))
        self.edit_telefon.setText(format_phone_number(str(record.get("TELEFON", ""))))
        self.edit_mobil.setText(format_phone_number(str(record.get("MOBIL", ""))))
        self.edit_email.setText(str(record.get("E_MAIL", "")))
        self.chk_vlastni_odvoz.setChecked(bool(record.get("VL_ODVOZ", False)))
        
        # TYP_ZPRAVY
        typ_zpravy = record.get("TYP_ZPRAVY")
        if typ_zpravy:
            try:
                button = self.grp_zpravy.button(int(typ_zpravy))
                if button:
                    button.setChecked(True)
            except (ValueError, TypeError):
                pass

        # PLAN
        plan_val = str(record.get("PLAN", "")).strip()
        index = self.cmb_planek.findData(plan_val)
        if index >= 0:
            self.cmb_planek.setCurrentIndex(index)
            
        # Dates and Lhuta
        def _format_date(d):
            if hasattr(d, 'strftime'):
                return d.strftime("%d.%m.%Y")
            return ""

        pr_datum = record.get("DATUM_PR")
        if pr_datum and hasattr(pr_datum, 'year'):
            self.date_prijeti.setDate(QDate(pr_datum.year, pr_datum.month, pr_datum.day))

        self.date_dodat_po.setText(_format_date(record.get("DATUM_PO")))
        self.date_vyzvy.setText(_format_date(record.get("DATUM_VYZ")))
        self.date_vyzva_den.setText(_format_date(record.get("DATUM_NA")))
        self.date_vyrizeni.setText(_format_date(record.get("DATUM_VYR")))
        self.edit_lhuta.setText(str(record.get("DOD_LHUTA", "")))

        # Poznámka tab fields
        self.txt_pozn_intern.setPlainText(str(record.get("POZNAMKA", "")))
        self.txt_pozn_zakaz.setPlainText(str(record.get("POZN_ZAK", "")))
        self.chk_zmenena.setChecked(bool(record.get("ZMENA", False)))

        # Trasa lookup
        self._trasa_cislo = str(record.get("TRASA", "")).strip()
        self._update_trasa_label()

        # Load items
        items_table = "tsd06a" if self.source_table == "tsd06" else "tsd04a"
        details_table = "tsd06b" if self.source_table == "tsd06" else "tsd04b"
        sestavy = self.ctx.db.read_where(items_table, {"CISLO_OBJ": cislo_obj})
        all_dily = self.ctx.db.read_where(details_table, {"CISLO_OBJ": cislo_obj})

        # Load the glass items cache for each assembly from tsd02a
        # so we can mark which loaded parts are glass
        glass_kods_per_sestava = {}  # {sestava_kod: set of part KODs from tsd02a}
        for s in sestavy:
            s_kod = int(float(s.get("KOD", 0) or 0))
            try:
                assembly_parts = self.ctx.db.read_where("tsd02a", {"FINAL": s_kod})
                glass_kods_per_sestava[s_kod] = {int(float(p.get("KOD", 0) or 0)) for p in assembly_parts}
            except Exception:
                glass_kods_per_sestava[s_kod] = set()

        # Group díly by FINAL (assembly KOD)
        dily_by_final = {}  # {final_kod: [dily_records]}
        unlinked_dily = []  # Parts with FINAL=0 or missing
        for d in all_dily:
            final_raw = d.get("FINAL")
            try:
                final_val = int(float(str(final_raw).strip())) if final_raw not in (None, "") else 0
            except (ValueError, TypeError):
                final_val = 0
            if final_val > 0:
                dily_by_final.setdefault(final_val, []).append(d)
            else:
                unlinked_dily.append(d)

        self.tbl_sestavy.setSortingEnabled(False)
        self._dily_per_sestava = {}
        self._current_sestava_uid = None
        default_dopr = self._default_dopravne()

        for s in sestavy:
            row = self.tbl_sestavy.rowCount()
            self.tbl_sestavy.insertRow(row)
            s_kod = int(float(s.get("KOD", 0) or 0))
            mnozstvi_sestavy = int(float(s.get("MNOZSTVI", 1) or 1))
            self.tbl_sestavy.setItem(row, 0, QTableWidgetItem(str(s.get("KOD", ""))))
            self.tbl_sestavy.setItem(row, 1, QTableWidgetItem(str(s.get("NAZEV", ""))))
            self.tbl_sestavy.setItem(row, 2, NumericSortItem(str(s.get("CENA", 0))))
            self.tbl_sestavy.setItem(row, 3, NumericSortItem(str(mnozstvi_sestavy)))
            # Load per-row shipping
            raw_dopr = s.get("DOPRAVNE")
            if raw_dopr is None or str(raw_dopr).strip() in ("", "None"):
                dopr_val = default_dopr
            else:
                try:
                    dopr_val = int(float(str(raw_dopr)))
                except (ValueError, TypeError):
                    dopr_val = default_dopr
            self.tbl_sestavy.setItem(row, 4, NumericSortItem(str(dopr_val)))

            # Assign UID
            uid = self._next_sestava_uid()
            self.tbl_sestavy.setItem(row, 5, QTableWidgetItem(str(uid)))

            # Build parts list for this greenhouse
            glass_kods = glass_kods_per_sestava.get(s_kod, set())
            linked_parts = dily_by_final.get(s_kod, [])
            parts_list = []
            for d in linked_parts:
                d_kod = int(float(d.get("KOD", 0) or 0))
                mnoz = d.get("MNOZSTVI")
                if mnoz is None or str(mnoz).strip() in ("", "None"):
                    mnoz = 1
                else:
                    mnoz = int(float(mnoz))
                is_glass = d_kod in glass_kods
                parts_list.append({
                    "kod": str(d.get("KOD") or ""),
                    "nazev": str(d.get("NAZEV") or ""),
                    "cena": str(d.get("CENA") or 0),
                    "pocet": str(mnoz),
                    "is_glass": is_glass,
                })

            # Add unlinked parts to every greenhouse (legacy data)
            for d in unlinked_dily:
                d_kod = int(float(d.get("KOD", 0) or 0))
                mnoz = d.get("MNOZSTVI")
                if mnoz is None or str(mnoz).strip() in ("", "None"):
                    mnoz = 1
                else:
                    mnoz = int(float(mnoz))
                parts_list.append({
                    "kod": str(d.get("KOD") or ""),
                    "nazev": str(d.get("NAZEV") or ""),
                    "cena": str(d.get("CENA") or 0),
                    "pocet": str(mnoz),
                    "is_glass": False,
                })

            # If no glass items were loaded from DB, auto-load from tsd02a
            has_glass = any(p["is_glass"] for p in parts_list)
            if not has_glass and glass_kods:
                glass_from_def = self._load_glass_for_sestava(s_kod)
                if mnozstvi_sestavy > 1:
                    for gp in glass_from_def:
                        try:
                            gp["pocet"] = str(int(float(gp["pocet"]) * mnozstvi_sestavy))
                        except Exception:
                            pass
                parts_list = glass_from_def + parts_list

            self._dily_per_sestava[uid] = parts_list

        # Clear unlinked_dily after distributing to avoid double counting
        # (they were added to each greenhouse; if multiple greenhouses exist,
        #  keep them only on the first one to avoid duplication)
        if len(sestavy) > 1 and unlinked_dily:
            # Only keep unlinked parts on first greenhouse
            first_uid = None
            for r in range(self.tbl_sestavy.rowCount()):
                uid_item = self.tbl_sestavy.item(r, 5)
                if uid_item:
                    first_uid = int(uid_item.text())
                    break
            for uid in self._dily_per_sestava:
                if uid != first_uid:
                    # Remove unlinked parts (those without is_glass that came from unlinked_dily)
                    unlinked_kods = {str(d.get("KOD") or "") for d in unlinked_dily}
                    self._dily_per_sestava[uid] = [
                        p for p in self._dily_per_sestava[uid]
                        if p.get("is_glass") or p.get("kod") not in unlinked_kods
                    ]

        self.tbl_sestavy.setSortingEnabled(True)

        # Select first sestava to show its parts
        if self.tbl_sestavy.rowCount() > 0:
            self.tbl_sestavy.setCurrentCell(0, 0)

        self._recalc_totals()

        # Capture snapshot for smart email diff on save
        self._original_snapshot = {
            "U_JMENO": str(record.get("U_JMENO", "")),
            "U_ULICE": str(record.get("U_ULICE", "")),
            "U_PSC": str(record.get("U_PSC", "")),
            "U_POSTA": str(record.get("U_POSTA", "")),
            "CENA_CELK": str(record.get("CENA_CELK", 0) or 0),
            "POZN_ZAK": str(record.get("POZN_ZAK", "")),
            "E_MAIL": str(record.get("E_MAIL", "")),
            "MOBIL": str(record.get("MOBIL", "")),
            # Items snapshots captured after tables are populated
            "_sestavy": self._sestavy_snapshot(),
            "_dily": self._dily_snapshot(),
        }
        self._is_loading_data = False
