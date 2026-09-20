# -*- coding: utf-8 -*-
"""
Backup dialog - 3 tabs: Lokální zálohy / Nastavení / Google Drive
"""
import os

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QFileDialog, QMessageBox, QProgressBar,
    QTabWidget, QWidget, QTableWidget, QTableWidgetItem,
    QHeaderView, QCheckBox, QSpinBox, QFormLayout, QAbstractItemView,
    QLineEdit
)
from PySide6.QtCore import Qt, QThread, Signal


class BackupWorker(QThread):
    progress = Signal(int)
    finished = Signal(bool, str)

    def __init__(self, service, action, path=None):
        super().__init__()
        self.service = service
        self.action = action
        self.path = path

    def run(self):
        try:
            if self.action == "backup_local":
                self.service.backup_local(self.path, progress_cb=self.progress.emit)
            elif self.action == "restore_local":
                self.service.restore_local(self.path, progress_cb=self.progress.emit)
            elif self.action == "backup_gdrive":
                self.service.backup_gdrive(progress_cb=self.progress.emit)
            elif self.action == "restore_gdrive":
                self.service.restore_gdrive(progress_cb=self.progress.emit)
            self.finished.emit(True, "Operace dokončena úspěšně.")
        except Exception as e:
            self.finished.emit(False, str(e))


class BackupDialog(QDialog):
    def __init__(self, ctx, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self.setWindowTitle("Záloha a obnova dat")
        self.setMinimumSize(700, 520)
        self.resize(700, 520)
        self._svc = None
        self._build_ui()
        self._refresh_backup_list()
        self._load_settings()
        self._refresh_gdrive_status()

    def _get_svc(self):
        if not self._svc:
            from app.services.backup_service import BackupService
            self._svc = BackupService(self.ctx)
        return self._svc

    # ════════════════════════════════════════════════════════════
    #  UI BUILD
    # ════════════════════════════════════════════════════════════
    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_local_tab(), "Lokální zálohy")
        self.tabs.addTab(self._build_settings_tab(), "Nastavení")
        self.tabs.addTab(self._build_gdrive_tab(), "Google Drive")
        layout.addWidget(self.tabs)

        # Shared progress bar
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        self.lbl_status = QLabel("")
        self.lbl_status.setMinimumHeight(22)
        layout.addWidget(self.lbl_status)

        # Bottom close button
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self.btn_close = QPushButton("Zavřít")
        self.btn_close.clicked.connect(self.accept)
        btn_row.addWidget(self.btn_close)
        layout.addLayout(btn_row)

    # ── Tab 1: Lokální zálohy ──────────────────────────────────
    def _build_local_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        lbl = QLabel("Přehled existujících záloh")
        lbl.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(lbl)

        self.tbl_backups = QTableWidget(0, 3)
        self.tbl_backups.setHorizontalHeaderLabels(["Datum", "Název souboru", "Velikost"])
        self.tbl_backups.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.tbl_backups.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.tbl_backups.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.tbl_backups.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tbl_backups.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.tbl_backups.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tbl_backups.verticalHeader().setVisible(False)
        self.tbl_backups.setSortingEnabled(True)
        self.tbl_backups.setMinimumHeight(180)
        layout.addWidget(self.tbl_backups)

        btn_row1 = QHBoxLayout()
        self.btn_backup_now = QPushButton("Zálohovat nyní")
        self.btn_backup_now.setObjectName("accentButton")
        self.btn_restore_sel = QPushButton("Obnovit vybranou")
        self.btn_delete_sel = QPushButton("Smazat vybranou")
        self.btn_delete_sel.setObjectName("dangerButton")
        
        btn_row1.addWidget(self.btn_backup_now)
        btn_row1.addWidget(self.btn_restore_sel)
        btn_row1.addWidget(self.btn_delete_sel)
        btn_row1.addStretch()

        btn_row2 = QHBoxLayout()
        self.btn_backup_other = QPushButton("Zálohovat jinam...")
        self.btn_restore_other = QPushButton("Obnovit z jiné složky...")
        
        btn_row2.addWidget(self.btn_backup_other)
        btn_row2.addWidget(self.btn_restore_other)
        btn_row2.addStretch()

        layout.addLayout(btn_row1)
        layout.addSpacing(4)
        layout.addLayout(btn_row2)

        self.btn_backup_now.clicked.connect(self._backup_now)
        self.btn_restore_sel.clicked.connect(self._restore_selected)
        self.btn_delete_sel.clicked.connect(self._delete_selected)
        self.btn_backup_other.clicked.connect(self._backup_to_other)
        self.btn_restore_other.clicked.connect(self._restore_from_other)

        return tab

    # ── Tab 2: Nastavení ───────────────────────────────────────
    def _build_settings_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)

        lbl = QLabel("Nastavení automatické zálohy")
        lbl.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(lbl)

        form = QFormLayout()
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(14)
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.chk_auto = QCheckBox("Automaticky zálohovat při ukončení aplikace")
        self.chk_auto.setMinimumHeight(28)
        form.addRow("Auto-záloha:", self.chk_auto)

        self.spin_keep = QSpinBox()
        self.spin_keep.setMinimum(1)
        self.spin_keep.setMaximum(30)
        self.spin_keep.setValue(7)
        self.spin_keep.setMinimumHeight(32)
        self.spin_keep.setMinimumWidth(80)
        keep_row = QHBoxLayout()
        keep_row.addWidget(self.spin_keep)
        keep_row.addWidget(QLabel("(starší zálohy se automaticky mažou)"))
        keep_row.addStretch()
        form.addRow("Počet záloh:", keep_row)

        dir_row = QHBoxLayout()
        self.edit_backup_dir = QLineEdit()
        self.edit_backup_dir.setReadOnly(True)
        self.edit_backup_dir.setStyleSheet(
            "padding: 6px 10px; "
            "background-color: #2B2D42; border: 1px solid #4A4E69; border-radius: 4px; color: #E0E0E0;"
        )
        self.edit_backup_dir.setMinimumHeight(32)
        self.btn_browse_dir = QPushButton("...")
        self.btn_browse_dir.setMaximumWidth(36)
        self.btn_browse_dir.setMinimumHeight(32)
        dir_row.addWidget(self.edit_backup_dir, 1)
        dir_row.addWidget(self.btn_browse_dir)
        form.addRow("Složka záloh:", dir_row)

        layout.addLayout(form)

        # Last backup info
        layout.addSpacing(8)
        self.lbl_last_backup = QLabel("")
        self.lbl_last_backup.setStyleSheet("color: #B0BEC5;")
        layout.addWidget(self.lbl_last_backup)

        layout.addStretch()

        # Save button
        btn_row = QHBoxLayout()
        self.btn_save_settings = QPushButton("Uložit nastavení")
        self.btn_save_settings.setObjectName("accentButton")
        btn_row.addWidget(self.btn_save_settings)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self.btn_browse_dir.clicked.connect(self._browse_backup_dir)
        self.btn_save_settings.clicked.connect(self._save_settings)

        return tab

    # ── Tab 3: Google Drive ────────────────────────────────────
    def _build_gdrive_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)

        lbl = QLabel("Záloha na Google Drive")
        lbl.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(lbl)

        # Status
        grp_status = QGroupBox("Stav připojení")
        gs = QVBoxLayout(grp_status)
        self.lbl_gdrive_status = QLabel("")
        self.lbl_gdrive_status.setWordWrap(True)
        self.lbl_gdrive_status.setMinimumHeight(36)
        gs.addWidget(self.lbl_gdrive_status)
        layout.addWidget(grp_status)

        # Buttons
        grp_actions = QGroupBox("Akce")
        ga = QHBoxLayout(grp_actions)
        self.btn_gdrive_backup = QPushButton("Zálohovat na Drive")
        self.btn_gdrive_backup.setObjectName("accentButton")
        self.btn_gdrive_restore = QPushButton("Obnovit z Drive")
        self.btn_gdrive_disconnect = QPushButton("Odpojit účet")
        self.btn_gdrive_disconnect.setObjectName("dangerButton")
        ga.addWidget(self.btn_gdrive_backup)
        ga.addWidget(self.btn_gdrive_restore)
        ga.addWidget(self.btn_gdrive_disconnect)
        layout.addWidget(grp_actions)

        # Help text
        self.lbl_gdrive_help = QLabel(
            'Pro použití Google Drive zálohy je potřeba soubor <b>credentials.json</b> '
            'z Google Cloud Console.<br>Umístěte ho do složky aplikace a klikněte '
            'na "Zálohovat na Drive" - budete vyzváni k přihlášení.'
        )
        self.lbl_gdrive_help.setWordWrap(True)
        self.lbl_gdrive_help.setStyleSheet("color: #9E9E9E; font-size: 12px; margin-top: 8px;")
        layout.addWidget(self.lbl_gdrive_help)

        layout.addStretch()

        self.btn_gdrive_backup.clicked.connect(self._gdrive_backup)
        self.btn_gdrive_restore.clicked.connect(self._gdrive_restore)
        self.btn_gdrive_disconnect.clicked.connect(self._gdrive_disconnect)

        return tab

    # ════════════════════════════════════════════════════════════
    #  TAB 1 LOGIC: Lokální zálohy
    # ════════════════════════════════════════════════════════════
    def _refresh_backup_list(self):
        svc = self._get_svc()
        backups = svc.list_backups()
        self.tbl_backups.setSortingEnabled(False)
        self.tbl_backups.setRowCount(len(backups))
        for i, b in enumerate(backups):
            item_date = QTableWidgetItem(b["date"])
            item_name = QTableWidgetItem(b["name"])
            item_size = QTableWidgetItem(b["size_display"])
            item_size.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            # Store path in first column's data
            item_date.setData(Qt.ItemDataRole.UserRole, b["path"])
            self.tbl_backups.setItem(i, 0, item_date)
            self.tbl_backups.setItem(i, 1, item_name)
            self.tbl_backups.setItem(i, 2, item_size)
        self.tbl_backups.setSortingEnabled(True)
        # Update last backup info on settings tab
        info = svc.get_last_backup_info()
        self.lbl_last_backup.setText(f"Poslední záloha: {info}" if info else "Zatím nebyla vytvořena žádná záloha.")

    def _get_selected_backup_path(self):
        rows = self.tbl_backups.selectionModel().selectedRows()
        if not rows:
            QMessageBox.information(self, "Záloha", "Vyberte zálohu v tabulce.")
            return None
        return self.tbl_backups.item(rows[0].row(), 0).data(Qt.ItemDataRole.UserRole)

    def _backup_now(self):
        """Backup to configured backup directory."""
        svc = self._get_svc()
        os.makedirs(svc.backup_dir, exist_ok=True)
        self._start_worker("backup_local", svc.backup_dir)

    def _backup_to_other(self):
        """Backup to a user-chosen directory."""
        path = QFileDialog.getExistingDirectory(self, "Vybrat složku pro zálohu")
        if path:
            self._start_worker("backup_local", path)

    def _restore_from_other(self):
        """Restore from a user-chosen backup file outside the default backup directory."""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Vybrat soubor zálohy",
            "",
            "Zálohy (*.zip);;V\u0161echny soubory (*)"
        )
        if not path:
            return
        if QMessageBox.question(
            self, "Potvrzen\u00ed",
            f"Obnovit data ze souboru:\n{os.path.basename(path)}\n\nObnovení p\u0159epí\u0161e aktu\u00e1ln\u00ed data. Pokra\u010dovat?",
            QMessageBox.Yes | QMessageBox.No
        ) == QMessageBox.Yes:
            self._start_worker("restore_local", path)

    def _restore_selected(self):
        path = self._get_selected_backup_path()
        if not path:
            return
        if QMessageBox.question(
            self, "Potvrzení",
            "Obnovení zálohy přepíše aktuální data.\nPokračovat?",
            QMessageBox.Yes | QMessageBox.No
        ) == QMessageBox.Yes:
            self._start_worker("restore_local", path)

    def _delete_selected(self):
        path = self._get_selected_backup_path()
        if not path:
            return
        name = os.path.basename(path)
        if QMessageBox.question(
            self, "Smazat zálohu",
            f"Opravdu smazat zálohu?\n{name}",
            QMessageBox.Yes | QMessageBox.No
        ) == QMessageBox.Yes:
            self._get_svc().delete_backup(path)
            self._refresh_backup_list()
            self.lbl_status.setText(f"Záloha {name} smazána.")

    # ════════════════════════════════════════════════════════════
    #  TAB 2 LOGIC: Nastavení
    # ════════════════════════════════════════════════════════════
    def _load_settings(self):
        svc = self._get_svc()
        self.chk_auto.setChecked(svc.auto_backup)
        self.spin_keep.setValue(svc.keep_count)
        self.edit_backup_dir.setText(svc.backup_dir)

    def _browse_backup_dir(self):
        path = QFileDialog.getExistingDirectory(self, "Vybrat složku pro zálohy", self.edit_backup_dir.text())
        if path:
            self.edit_backup_dir.setText(path)

    def _save_settings(self):
        svc = self._get_svc()
        svc.save_config(
            auto_backup=self.chk_auto.isChecked(),
            keep_count=self.spin_keep.value(),
            backup_dir=self.edit_backup_dir.text().strip(),
        )
        QMessageBox.information(self, "Nastavení", "Nastavení zálohy bylo uloženo.")

    # ════════════════════════════════════════════════════════════
    #  TAB 3 LOGIC: Google Drive
    # ════════════════════════════════════════════════════════════
    def _refresh_gdrive_status(self):
        creds = os.path.join(self.ctx.app_dir, "credentials.json")
        token = os.path.join(self.ctx.app_dir, "token.json")
        has_creds = os.path.isfile(creds)
        has_token = os.path.isfile(token)

        if has_token:
            self.lbl_gdrive_status.setStyleSheet("color: #4CAF50; font-weight: bold;")
            self.lbl_gdrive_status.setText("Pripojeno - Google Drive ucet je autorizovan.")
            self.btn_gdrive_disconnect.setEnabled(True)
        elif has_creds:
            self.lbl_gdrive_status.setStyleSheet("color: #FFD54F;")
            self.lbl_gdrive_status.setText(
                "Soubor credentials.json nalezen.\n"
                'Klikněte na "Zálohovat na Drive" pro přihlášení k účtu.'
            )
            self.btn_gdrive_disconnect.setEnabled(False)
        else:
            self.lbl_gdrive_status.setStyleSheet("color: #FF5252;")
            self.lbl_gdrive_status.setText(
                "Nepripojeno - soubor credentials.json nebyl nalezen."
            )
            self.btn_gdrive_backup.setEnabled(False)
            self.btn_gdrive_restore.setEnabled(False)
            self.btn_gdrive_disconnect.setEnabled(False)

    def _gdrive_backup(self):
        self._start_worker("backup_gdrive")

    def _gdrive_restore(self):
        if QMessageBox.question(
            self, "Potvrzení",
            "Obnovení z Google Drive přepíše aktuální data.\nPokračovat?",
            QMessageBox.Yes | QMessageBox.No
        ) == QMessageBox.Yes:
            self._start_worker("restore_gdrive")

    def _gdrive_disconnect(self):
        token = os.path.join(self.ctx.app_dir, "token.json")
        if QMessageBox.question(
            self, "Odpojit Google Drive",
            "Odpojit Google Drive účet?\nPři dalším použití budete vyzváni k novému přihlášení.",
            QMessageBox.Yes | QMessageBox.No
        ) == QMessageBox.Yes:
            if os.path.isfile(token):
                os.remove(token)
            self._refresh_gdrive_status()
            self.lbl_status.setText("Google Drive účet odpojen.")

    # ════════════════════════════════════════════════════════════
    #  SHARED WORKER
    # ════════════════════════════════════════════════════════════
    def _start_worker(self, action, path=None):
        svc = self._get_svc()
        self.worker = BackupWorker(svc, action, path)
        self.worker.progress.connect(self._on_progress)
        self.worker.finished.connect(self._on_finished)
        self.progress.setVisible(True)
        self.progress.setValue(0)
        self.lbl_status.setText("Prob\u00edh\u00e1 operace...")
        self._set_buttons_enabled(False)
        self.worker.start()

    def _on_progress(self, val):
        self.progress.setValue(val)

    def _on_finished(self, ok, msg):
        self.progress.setVisible(False)
        self._set_buttons_enabled(True)
        self.lbl_status.setText(msg)
        if ok:
            QMessageBox.information(self, "Záloha", msg)
            self._refresh_backup_list()
            self._refresh_gdrive_status()
        else:
            QMessageBox.warning(self, "Chyba", msg)

    def _set_buttons_enabled(self, enabled):
        for b in [self.btn_backup_now, self.btn_restore_sel, self.btn_delete_sel,
                   self.btn_backup_other, self.btn_restore_other, self.btn_gdrive_backup,
                   self.btn_gdrive_restore, self.btn_gdrive_disconnect,
                   self.btn_save_settings]:
            b.setEnabled(enabled)
