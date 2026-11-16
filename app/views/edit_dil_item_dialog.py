"""
Edit dil item – Dialog pro úpravu ceny a počtu kusů dílu nebo příslušenství v objednávce.
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QSpinBox,
    QPushButton, QFormLayout, QGroupBox
)
from PySide6.QtCore import Qt


class EditDilItemDialog(QDialog):
    """Dialog pro úpravu ceny a množství dílu/příslušenství v rámci konkrétní zakázky."""

    def __init__(self, nazev: str, current_cena: int, current_pocet: int = 1, is_glass: bool = False, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Oprava položky zakázky")
        self.setMinimumWidth(360)
        self._build_ui(nazev, current_cena, current_pocet, is_glass)

    def _build_ui(self, nazev: str, current_cena: int, current_pocet: int, is_glass: bool):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        lbl_nazev = QLabel(nazev)
        lbl_nazev.setStyleSheet("font-weight: bold; font-size: 13px;")
        lbl_nazev.setWordWrap(True)
        layout.addWidget(lbl_nazev)

        if is_glass:
            lbl_info = QLabel("Poznámka: Standardní skla jsou v ceně skleníku (0 Kč). Pro doobjednaná skla navíc zde můžete uvést cenu.")
            lbl_info.setStyleSheet("color: #888888; font-size: 11px;")
            lbl_info.setWordWrap(True)
            layout.addWidget(lbl_info)

        grp = QGroupBox("Parametry položky")
        form = QFormLayout(grp)
        form.setLabelAlignment(Qt.AlignRight)

        self.spin_cena = QSpinBox()
        self.spin_cena.setMinimum(0)
        self.spin_cena.setMaximum(9_999_999)
        self.spin_cena.setSingleStep(500)
        self.spin_cena.setValue(max(0, current_cena))
        self.spin_cena.setSuffix(" Kč")
        form.addRow("Cena za kus:", self.spin_cena)

        self.spin_pocet = QSpinBox()
        self.spin_pocet.setMinimum(1)
        self.spin_pocet.setMaximum(9_999)
        self.spin_pocet.setValue(max(1, current_pocet))
        self.spin_pocet.setSuffix(" ks")
        form.addRow("Počet kusů:", self.spin_pocet)

        layout.addWidget(grp)

        btn_row = QHBoxLayout()
        btn_ok = QPushButton("OK")
        btn_ok.setObjectName("accentButton")
        btn_cancel = QPushButton("Zpět")
        btn_row.addWidget(btn_ok)
        btn_row.addWidget(btn_cancel)
        layout.addLayout(btn_row)

        btn_ok.clicked.connect(self.accept)
        btn_cancel.clicked.connect(self.reject)

    def get_cena(self) -> int:
        return self.spin_cena.value()

    def get_pocet(self) -> int:
        return self.spin_pocet.value()
