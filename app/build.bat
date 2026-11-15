@echo off
chcp 65001 >nul
echo Sestavovani EvidenceSkleniku pomoci PyInstaller...
pyinstaller --clean -y EvidenceSkleniku.spec
echo.
if exist dist\EvidenceSkleniku.exe (
    echo Hotovo! Soubor dist\EvidenceSkleniku.exe byl uspesne vytvoren.
) else (
    echo Chyba: Sestaveni se nezdarilo!
)
pause
