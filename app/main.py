"""
TS Skleníky – main entry point
"""
import sys
import os

# Ensure network and Czech encodings are bundled and registered
import encodings.idna
import encodings.cp1250
import encodings.utf_8

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
        log_dir = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else APP_DIR
        with open(os.path.join(log_dir, "crash.log"), "a", encoding="utf-8") as f:
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
    from PySide6.QtGui import QTextDocument, QPdfWriter
    try:
        import PySide6.QtPrintSupport
    except ImportError:
        pass
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
        self.data_dir = os.path.join(self.app_dir, "DATA")
        os.makedirs(self.data_dir, exist_ok=True)
        os.makedirs(os.path.join(self.app_dir, "Zaloha"), exist_ok=True)
        os.makedirs(os.path.join(self.app_dir, "_temp"), exist_ok=True)
        self.is_restarting = False
        self.mariadb_connection_error = None
        self._cache = {}
        self._init_backend()

    def _init_backend(self):
        import configparser
        ini_path = os.path.join(self.app_dir, "db_config.ini")
        cp = configparser.ConfigParser()
        if os.path.exists(ini_path):
            try:
                cp.read(ini_path, encoding="utf-8")
            except Exception:
                pass

        backend = cp.get("database", "backend", fallback=None) if cp.has_section("database") else None
        if not backend:
            from PySide6.QtCore import QSettings
            settings = QSettings("TSSkleniky", "TS_Evidence")
            backend = settings.value("db_backend", "auto")

        data_dir = os.path.join(self.app_dir, "DATA")
        sqlite_file = os.path.join(data_dir, "ts_data.db")

        if backend == "mariadb":
            try:
                from app.services.mariadb_service import MariaDbService
                cfg = dict(cp["database"]) if cp.has_section("database") else {}
                self.db = MariaDbService(
                    host=cfg.get("host", "10.0.0.20"),
                    port=int(cfg.get("port", 3306)),
                    user=cfg.get("user", "root"),
                    password=cfg.get("password", ""),
                    database=cfg.get("database", "ts_skleniky"),
                    data_path=self.data_dir
                )
                self.backend_name = "mariadb"
                self.mariadb_connection_error = None
            except Exception as e:
                err_msg = str(e)
                print(f"[AppContext] Chyba připojení k MariaDB ({err_msg}), přepínám na lokální SQLite...")
                self.mariadb_connection_error = err_msg
                from app.services.sqlite_service import SqliteService
                self.db = SqliteService(data_dir)
                self.backend_name = "sqlite"
        elif backend == "sqlite" or (backend == "auto" and os.path.exists(sqlite_file) and os.path.getsize(sqlite_file) > 50000):
            from app.services.sqlite_service import SqliteService
            self.db = SqliteService(data_dir)
            self.backend_name = "sqlite"
        else:
            from app.services.dbf_service import DbfService
            self.db = DbfService(data_dir)
            self.backend_name = "dbf"

        self.db.on_mutation = self.invalidate_cache

    def close_db(self):
        """Close active database service and release all locks/handles."""
        if hasattr(self, "db") and self.db:
            try:
                if hasattr(self.db, "close"):
                    self.db.close()
            except Exception as e:
                print(f"[AppContext] Chyba při zavírání DB: {e}")
            self.db = None
        self.invalidate_cache()

    def reopen_db(self):
        """Re-open database service after restore or switch."""
        self.close_db()
        self._init_backend()
        self.invalidate_cache()

    def switch_database_backend(self, backend: str):
        """Switch active database backend ('mariadb', 'sqlite' or 'dbf') and clear cache."""
        import configparser
        ini_path = os.path.join(self.app_dir, "db_config.ini")
        cp = configparser.ConfigParser()
        if os.path.exists(ini_path):
            try:
                cp.read(ini_path, encoding="utf-8")
            except Exception:
                pass
        if not cp.has_section("database"):
            cp.add_section("database")
        cp.set("database", "backend", backend)
        try:
            with open(ini_path, "w", encoding="utf-8") as f:
                cp.write(f)
        except Exception:
            pass

        from PySide6.QtCore import QSettings
        settings = QSettings("TSSkleniky", "TS_Evidence")
        settings.setValue("db_backend", backend)
        self.reopen_db()

    def restart_application(self):
        """Restart application smoothly."""
        import os
        import sys
        from PySide6.QtCore import QProcess
        from PySide6.QtWidgets import QApplication
        
        self.is_restarting = True
        self.close_db()
        for var in ("_MEIPASS2", "_MEIPASS", "PYTHONPATH", "PYTHONHOME"):
            os.environ.pop(var, None)
        QProcess.startDetached(sys.executable, sys.argv[1:])
        app = QApplication.instance()
        if app:
            app.quit()

    def get_cached_table(self, table_name: str) -> list[dict]:
        """Lazy load a table into memory cache with 30s TTL for multi-user."""
        import time
        now = time.time()
        entry = self._cache.get(table_name)
        # Refresh if not cached or if in multi-user mode and older than 30 seconds
        if entry is None or (getattr(self, "backend_name", "") == "mariadb" and (now - entry.get("_ts", 0)) > 30):
            try:
                rows = self.db.read_all(table_name)
                self._cache[table_name] = {"rows": rows, "_ts": now}
            except Exception:
                self._cache[table_name] = {"rows": [], "_ts": now}
        return self._cache[table_name]["rows"]

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



def cleanup_orphaned_mei_dirs():
    """Clean up leftover _MEI temporary folders from previous closed runs in %TEMP%."""
    import tempfile
    import shutil
    try:
        temp_dir = tempfile.gettempdir()
        current_mei = os.path.abspath(getattr(sys, "_MEIPASS", ""))
        for entry in os.listdir(temp_dir):
            if entry.startswith("_MEI"):
                full_path = os.path.join(temp_dir, entry)
                if current_mei and os.path.abspath(full_path) == current_mei:
                    continue
                try:
                    shutil.rmtree(full_path, ignore_errors=True)
                except Exception:
                    pass
    except Exception:
        pass


def main():
    try:
        from app.services.github_updater import cleanup_old_executable
        cleanup_old_executable()
    except Exception:
        pass

    try:
        cleanup_orphaned_mei_dirs()
    except Exception:
        pass

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

    ret = app.exec()

    # Clean up before process terminates
    try:
        ctx.close_db()
    except Exception:
        pass

    import gc
    gc.collect()

    sys.exit(ret)


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
            with open(os.path.join(BASE_DIR, "crash.log"), "w", encoding="utf-8") as f:
                f.write(crash_msg)
        except Exception:
            pass
            
        sys.exit(1)
