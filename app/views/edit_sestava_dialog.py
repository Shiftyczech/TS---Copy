"""
Edit sestava – dialog pro úpravu ceny sestavy a dopravy při opravě objednávky.
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QSpinBox,
    QPushButton, QFormLayout, QGroupBox
)
from PySide6.QtCore import Qt

DEFAULT_DOPRAVNE = 17_000


class EditSestavyDialog(QDialog):
    """Dialog pro opravu ceny skleníku a ceny dopravy u vybrané sestavy."""

    def __init__(self, nazev: str, current_cena: int, current_pocet: int = 1, current_dopravne: int | None = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Oprava sestavy")
        self.setMinimumWidth(360)

        if current_dopravne is None:
            current_dopravne = DEFAULT_DOPRAVNE

        self._build_ui(nazev, current_cena, current_pocet, current_dopravne)

    def _build_ui(self, nazev: str, current_cena: int, current_pocet: int, current_dopravne: int):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # Název sestavy (nadpis)
        lbl_nazev = QLabel(nazev)
        lbl_nazev.setStyleSheet("font-weight: bold; font-size: 13px;")
        lbl_nazev.setWordWrap(True)
        layout.addWidget(lbl_nazev)

        # Formulář s cenami
        grp = QGroupBox("Ceny")
        form = QFormLayout(grp)
        form.setLabelAlignment(Qt.AlignRight)

        self.spin_cena = QSpinBox()
        self.spin_cena.setMinimum(0)
        self.spin_cena.setMaximum(9_999_999)
        self.spin_cena.setSingleStep(1_000)
        self.spin_cena.setValue(current_cena)
        self.spin_cena.setSuffix(" Kč")
        form.addRow("Cena skleníku:", self.spin_cena)

        self.spin_pocet = QSpinBox()
        self.spin_pocet.setMinimum(1)
        self.spin_pocet.setMaximum(999)
        self.spin_pocet.setValue(current_pocet)
        self.spin_pocet.setSuffix(" ks")
        form.addRow("Počet skleníků:", self.spin_pocet)

        self.spin_dopravne = QSpinBox()
        self.spin_dopravne.setMinimum(0)
        self.spin_dopravne.setMaximum(999_999)
        self.spin_dopravne.setSingleStep(500)
        self.spin_dopravne.setValue(current_dopravne)
        self.spin_dopravne.setSuffix(" Kč")
        form.addRow("Cena dopravy:", self.spin_dopravne)

        layout.addWidget(grp)

        # Tlačítka
        btn_row = QHBoxLayout()
        btn_ok = QPushButton("OK")
        btn_ok.setObjectName("accentButton")
        btn_ok.setDefault(False)
        btn_ok.setAutoDefault(False)
        btn_cancel = QPushButton("Zpět")
        btn_cancel.setDefault(False)
        btn_cancel.setAutoDefault(False)
        btn_row.addWidget(btn_ok)
        btn_row.addWidget(btn_cancel)
        layout.addLayout(btn_row)

        btn_ok.clicked.connect(self.accept)
        btn_cancel.clicked.connect(self.reject)

    def get_cena(self) -> int:
        return self.spin_cena.value()

    def get_pocet(self) -> int:
        return self.spin_pocet.value()

    def get_dopravne(self) -> int:
        return self.spin_dopravne.value()
