"""
Dialog pro jednoduchou aktualizaci aplikace z GitHub Releases.
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QProgressBar, QMessageBox
)
from PySide6.QtCore import Qt, QThread, Signal
from app.version import APP_VERSION
from app.services.github_updater import download_and_install_update, UpdateInfo


class DownloadWorker(QThread):
    progress = Signal(int)
    finished = Signal(bool, str)

    def __init__(self, download_url: str, parent=None):
        super().__init__(parent)
        self.download_url = download_url

    def run(self):
        try:
            def on_progress(pct: int):
                self.progress.emit(pct)

            download_and_install_update(self.download_url, progress_callback=on_progress)
            self.finished.emit(True, "")
        except Exception as e:
            self.finished.emit(False, str(e))


class UpdateDialog(QDialog):
    def __init__(self, update_info: UpdateInfo, parent=None):
        super().__init__(parent)
        self.update_info = update_info
        self._worker = None

        self.setWindowTitle("Aktualizace programu")
        self.setFixedSize(420, 200)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(20, 20, 20, 20)

        title = QLabel("K dispozici je nová verze aplikace")
        title.setStyleSheet("font-size: 15px; font-weight: bold;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        info_text = (
            f"Byla vydána nová verze: <b>v{self.update_info.latest_version}</b>\n"
            f"Vaše aktuální verze: v{APP_VERSION}\n\n"
            "Přejete si aplikaci nyní automaticky aktualizovat a restartovat?"
        )
        self.lbl_info = QLabel(info_text)
        self.lbl_info.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.lbl_info)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        self.lbl_status = QLabel("")
        self.lbl_status.setAlignment(Qt.AlignCenter)
        self.lbl_status.setVisible(False)
        layout.addWidget(self.lbl_status)

        layout.addStretch()

        self.btn_layout = QHBoxLayout()
        self.btn_update = QPushButton("Aktualizovat")
        self.btn_update.setObjectName("accentButton")
        self.btn_update.clicked.connect(self._start_download)
        self.btn_layout.addWidget(self.btn_update)

        self.btn_later = QPushButton("Později")
        self.btn_later.clicked.connect(self.reject)
        self.btn_layout.addWidget(self.btn_later)

        layout.addLayout(self.btn_layout)

    def _start_download(self):
        import sys
        if not getattr(sys, "frozen", False):
            QMessageBox.information(
                self,
                "Vývojářský režim",
                "Aplikace běží ze zdrojového kódu Pythonu (.py), nikoliv jako zkompilovaný .exe soubor.\n"
                "Aktualizace stažením .exe je určena pro ostré nasazení."
            )
            self.accept()
            return

        self.btn_update.setEnabled(False)
        self.btn_later.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.lbl_status.setVisible(True)
        self.lbl_status.setText("Stahuji novou verzi...")

        self._worker = DownloadWorker(self.update_info.download_url, parent=self)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.start()

    def _on_progress(self, pct: int):
        self.progress_bar.setValue(pct)
        self.lbl_status.setText(f"Stahuji novou verzi... {pct} %")

    def _on_finished(self, ok: bool, err_msg: str):
        if ok:
            import os
            import sys
            from PySide6.QtCore import QProcess
            from PySide6.QtWidgets import QApplication

            self.lbl_status.setText("Restartuji aplikaci...")
            parent = self.parent()
            if parent:
                parent._is_restarting_for_update = True
                if hasattr(parent, "ctx") and parent.ctx:
                    parent.ctx.is_restarting = True
                    parent.ctx.close_db()

            self.accept()

            # Clean PyInstaller environment variables so new process extracts its own fresh environment
            for var in ("_MEIPASS2", "_MEIPASS", "PYTHONPATH", "PYTHONHOME"):
                os.environ.pop(var, None)

            QProcess.startDetached(sys.executable, sys.argv[1:])
            app = QApplication.instance()
            if app:
                app.quit()
            else:
                sys.exit(0)
        else:
            self.btn_update.setEnabled(True)
            self.btn_later.setEnabled(True)
            self.progress_bar.setVisible(False)
            self.lbl_status.setText("")
            QMessageBox.critical(
                self,
                "Chyba aktualizace",
                f"Nepodařilo se stáhnout nebo nainstalovat aktualizaci:\n\n{err_msg}"
            )
