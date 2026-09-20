"""
Edit počet – small dialog to enter quantity when adding item to order
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QSpinBox,
    QPushButton
)
from PySide6.QtCore import Qt


class EditPocetDialog(QDialog):
    def __init__(self, nazev="", current_qty=1, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Počet kusů")
        self.setMinimumWidth(300)
        self._build_ui(nazev, current_qty)

    def _build_ui(self, nazev, current_qty):
        layout = QVBoxLayout(self)

        if nazev:
            lbl = QLabel(nazev)
            lbl.setStyleSheet("font-weight: bold;")
            layout.addWidget(lbl)

        row = QHBoxLayout()
        row.addWidget(QLabel("Počet:"))
        self.spin = QSpinBox()
        self.spin.setMinimum(1)
        self.spin.setMaximum(9999)
        self.spin.setValue(current_qty)
        row.addWidget(self.spin)
        layout.addLayout(row)

        btn_row = QHBoxLayout()
        btn_ok = QPushButton("OK")
        btn_ok.setObjectName("accentButton")
        btn_cancel = QPushButton("Zpět")
        btn_row.addWidget(btn_ok)
        btn_row.addWidget(btn_cancel)
        layout.addLayout(btn_row)

        btn_ok.clicked.connect(self.accept)
        btn_cancel.clicked.connect(self.reject)

    def get_pocet(self):
        return self.spin.value()
