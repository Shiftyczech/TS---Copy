"""
PhoneLineEdit – Specializované editační pole pro telefonní čísla.
Zajišťuje živé doplňování mezer po 3 číslicích během psaní (i při vkládání ze schránky),
podporuje mezinárodní předvolby (+420) i více čísel oddělených čárkou nebo lomítkem,
a zachovává přirozený pohyb kurzoru i mazání klávesou Backspace.
"""
import re
from PySide6.QtWidgets import QLineEdit
from PySide6.QtCore import Qt


def format_single_phone(s: str) -> str:
    """Zformátuje jedno telefonní číslo rozdělením na trojice číslic."""
    if not s:
        return ""
    s = s.strip()
    is_plus = s.startswith("+")
    raw = s[1:] if is_plus else s
    digits = "".join(c for c in raw if c.isdigit())
    if not digits:
        return "+" if is_plus else ""

    parts = []
    if is_plus:
        prefix_len = min(3, len(digits))
        parts.append("+" + digits[:prefix_len])
        rest = digits[prefix_len:]
    elif digits.startswith("00") and len(digits) >= 5:
        parts.append("00" + digits[2:5])
        rest = digits[5:]
    else:
        rest = digits

    for i in range(0, len(rest), 3):
        parts.append(rest[i:i + 3])

    return " ".join(parts)


def format_phone_live(s: str) -> str:
    """Zformátuje text obsahující jedno nebo více čísel (oddělených čárkou či lomítkem)."""
    if not s:
        return ""
    pieces = re.split(r'([,/])', s)
    res = []
    for p in pieces:
        if p in (',', '/'):
            res.append(f" {p} ")
        else:
            fmt = format_single_phone(p)
            if fmt:
                res.append(fmt)
            elif not res and p.strip() == "+":
                res.append("+")
    result = "".join(res)
    # Vyčistit vícenásobné mezery
    return re.sub(r'[ \t]+', ' ', result).strip()


class PhoneLineEdit(QLineEdit):
    """QLineEdit s automatickým živým formátováním telefonních čísel."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._formatting = False
        self.textEdited.connect(self._on_text_edited)

    def setText(self, text: str):
        formatted = format_phone_live(str(text or ""))
        super().setText(formatted)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Backspace and self.selectionLength() == 0:
            cursor = self.cursorPosition()
            # Pokud je před kurzorem mezera, posuneme se před ni, aby Backspace smazal číslici
            if cursor > 0 and self.text()[cursor - 1] == ' ':
                self.setCursorPosition(cursor - 1)
        super().keyPressEvent(event)

    def _on_text_edited(self, new_text: str):
        if self._formatting:
            return

        old_cursor = self.cursorPosition()
        num_non_spaces = sum(1 for c in new_text[:old_cursor] if c != ' ')

        formatted = format_phone_live(new_text)

        # Spočítat novou pozici kurzoru podle počtu platných znaků
        count = 0
        new_cursor = 0
        for idx, c in enumerate(formatted):
            if count >= num_non_spaces:
                break
            if c != ' ':
                count += 1
            new_cursor = idx + 1

        self._formatting = True
        try:
            super().setText(formatted)
            self.setCursorPosition(new_cursor)
        finally:
            self._formatting = False
