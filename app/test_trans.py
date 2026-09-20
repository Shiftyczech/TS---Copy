from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import QTranslator, QLibraryInfo
import sys

app = QApplication(sys.argv)
translator = QTranslator()
path = QLibraryInfo.path(QLibraryInfo.TranslationsPath)
print("Loading from", path)
loaded = translator.load("qtbase_cs", path)
print("Loaded:", loaded)
if loaded:
    app.installTranslator(translator)

msg = QMessageBox()
msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel)
print("Yes text:", msg.buttonText(QMessageBox.Yes))
print("Cancel text:", msg.buttonText(QMessageBox.Cancel))
