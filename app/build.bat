@echo off
echo Building EvidenceSkleniků...
pyinstaller --onefile --windowed --name "EvidenceSkleniků" --add-data "styles;styles" --hidden-import default_symbols --paths ".." main.py
echo Done!
pause
