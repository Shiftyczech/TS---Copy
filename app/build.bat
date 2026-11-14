@echo off
echo Building EvidenceSkleniků...
pyinstaller --onefile --windowed --name "EvidenceSkleniků" --add-data "styles;styles" --hidden-import default_symbols --hidden-import PySide6.QtPrintSupport --hidden-import encodings.idna --hidden-import encodings.cp1250 --hidden-import pymysql --hidden-import app.version --paths ".." main.py
echo Done!
pause
