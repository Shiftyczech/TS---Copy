"""
DateLineEdit – QLineEdit subclass for intuitive Czech date entry (dd.mm.yyyy).

Dots are inserted automatically after the 2nd and 4th digit so the user
only types numbers.  Backspace works naturally: deleting a dot also
removes the preceding digit so the cursor never gets "stuck".
"""
from PySide6.QtWidgets import QLineEdit
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent


class DateLineEdit(QLineEdit):
    """A QLineEdit that auto-formats typed digits into dd.mm.yyyy."""

    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setPlaceholderText("dd.mm.rrrr")
        self.setMaximumWidth(120)
        self.setMaxLength(10)  # dd.mm.yyyy = 10 chars
        self.textChanged.connect(self._on_text_changed)
        self._reformatting = False

    # ------------------------------------------------------------------ #
    # Core auto-format logic
    # ------------------------------------------------------------------ #

    def _on_text_changed(self, text: str):
        if self._reformatting:
            return
        self._reformatting = True
        try:
            # Strip everything except digits and dots already placed
            digits = "".join(ch for ch in text if ch.isdigit())

            # Build formatted string: dd.mm.yyyy
            formatted = ""
            for i, d in enumerate(digits[:8]):  # max 8 digits (ddmmyyyy)
                if i == 2 or i == 4:
                    formatted += "."
                formatted += d

            # Only update if different to avoid infinite loop
            if formatted != text:
                self.setText(formatted)
                # Place cursor at end
                self.setCursorPosition(len(formatted))
        finally:
            self._reformatting = False

    def keyPressEvent(self, event: QKeyEvent):
        """Handle Backspace so that deleting a dot removes the digit before it."""
        if event.key() == Qt.Key_Backspace:
            pos = self.cursorPosition()
            text = self.text()
            # If cursor is right after a dot, skip the dot and delete the
            # digit before it too (feels natural).
            if pos >= 2 and text[pos - 1:pos] == ".":
                # Remove the dot AND the preceding digit
                self._reformatting = True
                new_text = text[:pos - 2] + text[pos:]
                digits = "".join(ch for ch in new_text if ch.isdigit())
                formatted = ""
                for i, d in enumerate(digits[:8]):
                    if i == 2 or i == 4:
                        formatted += "."
                    formatted += d
                self.setText(formatted)
                # Place cursor where the removed digit was
                new_pos = max(0, pos - 2)
                self.setCursorPosition(new_pos)
                self._reformatting = False
                return

        super().keyPressEvent(event)
