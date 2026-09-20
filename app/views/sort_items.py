"""
Custom QTableWidgetItem subclasses for proper column sorting.
"""
from PySide6.QtWidgets import QTableWidgetItem


class NumericSortItem(QTableWidgetItem):
    """Sorts numerically instead of alphabetically."""
    def __lt__(self, other):
        try:
            return float(self.text().replace(" ", "").replace(",", ".")) < \
                   float(other.text().replace(" ", "").replace(",", "."))
        except (ValueError, AttributeError):
            return super().__lt__(other)


class DateSortItem(QTableWidgetItem):
    """Sorts dates in dd.mm.yyyy format correctly."""
    def __lt__(self, other):
        if not isinstance(other, QTableWidgetItem):
            return False
            
        t1 = self.text()
        t2 = other.text()
        
        if t1 == t2: return False
        if not t1: return True
        if not t2: return False
        
        # Helper to parse dd.mm.yyyy or dd.mm.yyyy <rest>
        def parse(t):
            parts = t.strip().split(".")
            if len(parts) >= 3:
                try:
                    day = int(parts[0])
                    month = int(parts[1])
                    year_and_rest = parts[2].split(None, 1)
                    year = int(year_and_rest[0])
                    rest = year_and_rest[1].strip().lower() if len(year_and_rest) > 1 else ""
                    return (year, month, day, rest)
                except (ValueError, IndexError):
                    pass
            return None

        v1 = parse(t1)
        v2 = parse(t2)
        
        if v1 is not None and v2 is not None:
            return v1 < v2
        
        # Fallback to simple text comparison to avoid recursion
        return t1 < t2
