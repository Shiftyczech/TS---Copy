"""
Dialog pro zadání / potvrzení data vyřízení zakázky nebo trasy.
"""
import datetime
from typing import Optional, Union
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QDateEdit, QPushButton
)
from PySide6.QtCore import Qt, QDate


class DatumVyrizeniDialog(QDialog):
    """Dialog umožňující vybrat datum vyřízení (předvyplněné např. datem rozvozu)."""

    def __init__(
        self,
        parent=None,
        title: str = "Datum vyřízení",
        prompt: str = "Zadejte datum vyřízení zakázky:",
        initial_date: Optional[Union[datetime.date, datetime.datetime, QDate, str]] = None,
        info_text: Optional[str] = None
    ):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(360)
        self._build_ui(prompt, initial_date, info_text)

    def _build_ui(self, prompt: str, initial_date, info_text: Optional[str]):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        if info_text:
            lbl_info = QLabel(info_text)
            lbl_info.setWordWrap(True)
            lbl_info.setStyleSheet("font-weight: bold;")
            layout.addWidget(lbl_info)

        lbl_prompt = QLabel(prompt)
        lbl_prompt.setWordWrap(True)
        layout.addWidget(lbl_prompt)

        date_row = QHBoxLayout()
        date_row.addWidget(QLabel("Datum:"))
        self.date_edit = QDateEdit(self)
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat("dd.MM.yyyy")
        self.date_edit.setMinimumWidth(130)

        # Parse initial_date or fallback to today
        qdate = self._to_qdate(initial_date)
        if not qdate.isValid():
            qdate = QDate.currentDate()
        self.date_edit.setDate(qdate)
        date_row.addWidget(self.date_edit)
        date_row.addStretch()
        layout.addLayout(date_row)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self.btn_ok = QPushButton("Potvrdit")
        self.btn_ok.setObjectName("accentButton")
        self.btn_ok.setDefault(True)
        self.btn_cancel = QPushButton("Zrušit")

        self.btn_ok.clicked.connect(self.accept)
        self.btn_cancel.clicked.connect(self.reject)

        btn_row.addWidget(self.btn_ok)
        btn_row.addWidget(self.btn_cancel)
        layout.addLayout(btn_row)

    @staticmethod
    def _to_qdate(val) -> QDate:
        if isinstance(val, QDate):
            return val
        if isinstance(val, (datetime.date, datetime.datetime)):
            return QDate(val.year, val.month, val.day)
        if isinstance(val, str) and val.strip():
            s = val.strip()
            # Try YYYY-MM-DD
            if len(s) >= 10 and s[4] == '-' and s[7] == '-':
                try:
                    parts = s[:10].split('-')
                    return QDate(int(parts[0]), int(parts[1]), int(parts[2]))
                except ValueError:
                    pass
            # Try DD.MM.YYYY
            if '.' in s:
                try:
                    parts = s.split('.')
                    if len(parts) >= 3:
                        return QDate(int(parts[2]), int(parts[1]), int(parts[0]))
                except ValueError:
                    pass
        return QDate()

    def selected_date(self) -> datetime.date:
        """Vrátí vybrané datum jako standardní datetime.date."""
        qd = self.date_edit.date()
        return datetime.date(qd.year(), qd.month(), qd.day())

    def selected_date_str(self) -> str:
        """Vrátí vybrané datum ve formátu YYYY-MM-DD."""
        return self.selected_date().strftime("%Y-%m-%d")
