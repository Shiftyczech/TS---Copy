from PySide6.QtWidgets import QApplication, QDialog, QLineEdit, QVBoxLayout, QCompleter
from PySide6.QtCore import Qt
import sys

app = QApplication(sys.argv)
class Dlg(QDialog):
    def __init__(self):
        super().__init__()
        self.l = QVBoxLayout(self)
        self.z_p = QLineEdit()
        self.z_c = QLineEdit()
        self.m_p = QLineEdit()
        self.m_c = QLineEdit()
        self.l.addWidget(self.z_p)
        self.l.addWidget(self.z_c)
        self.l.addWidget(self.m_p)
        self.l.addWidget(self.m_c)
        
        names = ["Praha", "Brno"]
        zips = ["10000", "60000"]
        self._psc_map = {"Praha": "10000", "Brno": "60000"}
        self._city_map = {"10000": "Praha", "60000": "Brno"}
        
        for edit_posta, edit_psc in (
            (self.z_p, self.z_c),
            (self.m_p, self.m_c),
        ):
            comp_city = QCompleter(names, self)
            edit_posta.setCompleter(comp_city)
            comp_city.activated.connect(
                lambda text, ep=edit_psc: ep.setText(self._psc_map.get(text, ""))
            )

            comp_zip = QCompleter(zips, self)
            edit_psc.setCompleter(comp_zip)
            comp_zip.activated.connect(
                lambda text, ep=edit_posta: ep.setText(self._city_map.get(text, ""))
            )

d = Dlg()
d.z_p.completer().activated.emit("Praha")
print("z_c text:", d.z_c.text())
d.m_p.completer().activated.emit("Brno")
print("m_c text:", d.m_c.text())
