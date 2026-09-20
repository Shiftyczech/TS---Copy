"""
TS Skleníky – main entry point
"""
import sys
import os

# Ensure app package is importable
APP_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(APP_DIR)
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

def global_excepthook(type, value, tb):
    import traceback
    import datetime
    msg = f"Unhandled Exception at {datetime.datetime.now()}\n"
    msg += "".join(traceback.format_exception(type, value, tb))
    print(msg, file=sys.stderr)
    try:
        with open("crash.log", "a", encoding="utf-8") as f:
            f.write(msg)
    except:
        pass

import sys
sys.excepthook = global_excepthook

# Determine base directories for data files and bundled resources
if getattr(sys, 'frozen', False):
    # Running as PyInstaller .exe – data files live next to the executable
    BASE_DIR = os.path.dirname(sys.executable)
    BUNDLE_DIR = sys._MEIPASS
else:
    # Running as .py script – locate data directory
    BUNDLE_DIR = APP_DIR
    if os.path.isdir(os.path.join(APP_DIR, "DATA")):
        BASE_DIR = APP_DIR
    elif os.path.isdir(os.path.join(APP_DIR, "dist", "DATA")):
        BASE_DIR = os.path.join(APP_DIR, "dist")
    elif os.path.isdir(os.path.join(ROOT_DIR, "DATA")):
        BASE_DIR = ROOT_DIR
    else:
        BASE_DIR = APP_DIR

try:
    from PySide6.QtWidgets import QApplication, QDialog, QPushButton, QTableWidget, QTextEdit, QPlainTextEdit
    from PySide6.QtCore import QFile, QTextStream, QObject, QEvent, Qt, QSettings
except ModuleNotFoundError as e:
    missing = getattr(e, "name", "unknown")
    if missing == "PySide6":
        install_msg = (
            "Missing dependency: PySide6\n"
            "Install project dependencies with:\n"
            "  pip install -r app/requirements.txt\n"
        )
        print(install_msg, file=sys.stderr)
        try:
            with open("crash.log", "a", encoding="utf-8") as f:
                f.write(install_msg + "\n")
        except Exception:
            pass
        sys.exit(1)
    raise


class AppKeyboardFilter(QObject):
    """Application-wide keyboard navigation.

    - Disables autoDefault on QPushButtons inside every QDialog so that
      Enter is not silently swallowed by an arbitrary button.
    - Sets the 'accentButton' (primary action) as the true default.
    - Enter / Return on a QTableWidget emits doubleClicked for the
      current row (same as double-clicking).
    - Enter / Return inside a QDialog (not in a multi-line editor or
      table) clicks the default / accent button.
    """

    def eventFilter(self, obj, event):
        etype = event.type()

        # --- When a QDialog is first shown, fix button defaults ----------
        if etype == QEvent.Type.Show and isinstance(obj, QDialog):
            self._fix_dialog_buttons(obj)
            return False

        # --- Key-press handling -------------------------------------------
        if etype == QEvent.Type.KeyPress:
            key = event.key()

            if key in (Qt.Key_Return, Qt.Key_Enter):
                return self._handle_enter(obj, event)

        return False

    # -- helpers ----------------------------------------------------------

    @staticmethod
    def _fix_dialog_buttons(dialog: QDialog):
        accent = None
        for btn in dialog.findChildren(QPushButton):
            btn.setAutoDefault(False)
            btn.setDefault(False)
            if btn.objectName() == "accentButton":
                accent = btn
        if accent:
            accent.setDefault(True)

    @staticmethod
    def _handle_enter(obj, event):
        # 1) If the focused widget is a multi-line editor, let it insert a newline
        if isinstance(obj, (QTextEdit, QPlainTextEdit)):
            return False

        # 2) If the focused widget is a QTableWidget, activate the current row
        if isinstance(obj, QTableWidget):
            row = obj.currentRow()
            if row >= 0:
                idx = obj.model().index(row, 0)
                obj.doubleClicked.emit(idx)
                return True  # consumed
            return False

        # 3) Inside a QDialog, click the default / accent button
        dialog = obj.window() if hasattr(obj, 'window') else None
        if isinstance(dialog, QDialog):
            # Find the default button or the accent button
            target = None
            for btn in dialog.findChildren(QPushButton):
                if btn.isDefault() and btn.isEnabled():
                    target = btn
                    break
            if target is None:
                for btn in dialog.findChildren(QPushButton):
                    if btn.objectName() == "accentButton" and btn.isEnabled():
                        target = btn
                        break
            if target:
                target.click()
                return True

        return False


class AppContext:
    """Holds shared state: DB service, app directory paths, and cache."""
    def __init__(self, app_dir):
        self.app_dir = app_dir
        self._cache = {}
        
        from PySide6.QtCore import QSettings
        settings = QSettings("TSSkleniky", "TS_Evidence")
        backend = settings.value("db_backend", "auto")
        
        data_dir = os.path.join(app_dir, "DATA")
        sqlite_file = os.path.join(data_dir, "ts_data.db")
        
        if backend == "sqlite" or (backend == "auto" and os.path.exists(sqlite_file) and os.path.getsize(sqlite_file) > 50000):
            from app.services.sqlite_service import SqliteService
            self.db = SqliteService(data_dir)
            self.backend_name = "sqlite"
        else:
            from app.services.dbf_service import DbfService
            self.db = DbfService(data_dir)
            self.backend_name = "dbf"
            
        self.db.on_mutation = self.invalidate_cache

    def switch_database_backend(self, backend: str):
        """Switch active database backend ('sqlite' or 'dbf') and clear cache."""
        from PySide6.QtCore import QSettings
        settings = QSettings("TSSkleniky", "TS_Evidence")
        settings.setValue("db_backend", backend)
        
        data_dir = os.path.join(self.app_dir, "DATA")
        if backend == "sqlite":
            from app.services.sqlite_service import SqliteService
            self.db = SqliteService(data_dir)
            self.backend_name = "sqlite"
        else:
            from app.services.dbf_service import DbfService
            self.db = DbfService(data_dir)
            self.backend_name = "dbf"
            
        self.db.on_mutation = self.invalidate_cache
        self.invalidate_cache()

    def get_cached_table(self, table_name: str) -> list[dict]:
        """Lazy load a table into memory cache."""
        if table_name not in self._cache:
            try:
                self._cache[table_name] = self.db.read_all(table_name)
            except Exception:
                self._cache[table_name] = []
        return self._cache[table_name]

    def get_psc_maps(self) -> tuple[dict[str, str], dict[str, str]]:
        """Return (psc_map, city_map). Lazy loads from tsd01b."""
        cache_key = "_psc_maps_parsed"
        if cache_key not in self._cache:
            psc_map = {}
            city_map = {}
            rows = self.get_cached_table("tsd01b")
            for r in rows:
                nazev = str(r.get("NAZ_POSTY", "")).strip()
                psc = str(r.get("PSC", "")).strip()
                if nazev and psc:
                    psc_map[nazev] = psc
                    city_map[psc] = nazev
            self._cache[cache_key] = (psc_map, city_map)
        return self._cache[cache_key]

    def invalidate_cache(self, table_name: str = None):
        """Clear cache for a specific table or completely."""
        if table_name:
            self._cache.pop(table_name, None)
            if table_name == "tsd01b":
                self._cache.pop("_psc_maps_parsed", None)
        else:
            self._cache.clear()



def apply_theme(app, theme_name):
    if theme_name == "light":
        theme_file = "light_theme.qss"
    elif theme_name == "blue":
        theme_file = "blue_theme.qss"
    else:
        theme_file = "dark_theme.qss"

    qss_path = os.path.join(BUNDLE_DIR, "styles", theme_file)
    if os.path.isfile(qss_path):
        try:
            with open(qss_path, "r", encoding="utf-8") as f:
                app.setStyleSheet(f.read())
        except Exception as e:
            print(f"Warning: Could not load stylesheet: {e}")

def load_stylesheet(app):
    settings = QSettings("TSSkleniky", "TS_Evidence")
    theme = settings.value("theme", "dark")
    apply_theme(app, theme)



def main():
    app = QApplication(sys.argv)
    
    # Load Czech translations for standard Qt dialogs (QMessageBox buttons etc.)
    from PySide6.QtCore import QTranslator, QLibraryInfo
    translator = QTranslator(app)
    if translator.load("qtbase_cs", QLibraryInfo.path(QLibraryInfo.TranslationsPath)):
        app.installTranslator(translator)
        
    app.setApplicationName("TS Skleníky")

    # All data/config files are inside app/ (or next to the .exe)
    workspace_dir = BASE_DIR
    ctx = AppContext(workspace_dir)

    load_stylesheet(app)

    # Install global keyboard navigation filter
    kb_filter = AppKeyboardFilter(app)
    app.installEventFilter(kb_filter)

    from app.views.main_window import MainWindow
    window = MainWindow(ctx)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except BaseException as e:
        import traceback
        import sys
        import datetime
        
        crash_msg = f"Crash at {datetime.datetime.now()}\n"
        crash_msg += traceback.format_exc()
        
        print("CRITICAL ERROR DURING STARTUP:", file=sys.stderr)
        print(crash_msg, file=sys.stderr)
        
        try:
            with open("crash.log", "w", encoding="utf-8") as f:
                f.write(crash_msg)
        except Exception:
            pass
            
        sys.exit(1)
