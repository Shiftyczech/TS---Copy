"""
Backup service – ZIP local + Google Drive backup/restore
"""
import os
import zipfile
import datetime
import glob
import shutil
import configparser


class BackupService:
    BACKUP_PREFIX = "TS_backup_"

    def __init__(self, ctx):
        self.ctx = ctx
        self.data_dir = os.path.join(ctx.app_dir, "DATA")
        self._load_config()

    # ── Config ──────────────────────────────────────────────────
    def _get_ini_path(self):
        return os.path.join(self.ctx.app_dir, "backup_config.ini")

    def _load_config(self):
        cp = configparser.ConfigParser()
        cp.read(self._get_ini_path(), encoding="utf-8")
        self.auto_backup = cp.getboolean("backup", "auto_backup", fallback=True)
        self.keep_count = cp.getint("backup", "keep_count", fallback=7)
        backup_dir_raw = cp.get("backup", "backup_dir", fallback="Zaloha")
        if os.path.isabs(backup_dir_raw):
            self.backup_dir = backup_dir_raw
        else:
            self.backup_dir = os.path.join(self.ctx.app_dir, backup_dir_raw)

    def save_config(self, auto_backup=None, keep_count=None, backup_dir=None):
        """Save settings to backup_config.ini."""
        if auto_backup is not None:
            self.auto_backup = auto_backup
        if keep_count is not None:
            self.keep_count = keep_count
        if backup_dir is not None:
            self.backup_dir = backup_dir

        # Store relative path when inside app_dir
        store_dir = self.backup_dir
        try:
            rel = os.path.relpath(self.backup_dir, self.ctx.app_dir)
            if not rel.startswith(".."):
                store_dir = rel
        except ValueError:
            pass

        cp = configparser.ConfigParser()
        cp.add_section("backup")
        cp.set("backup", "; Automatická denní záloha při ukončení aplikace (yes/no)", "")
        cp.set("backup", "auto_backup", "yes" if self.auto_backup else "no")
        cp.set("backup", "; Počet uchovávaných záloh (starší se automaticky mažou)", "")
        cp.set("backup", "keep_count", str(self.keep_count))
        cp.set("backup", "; Složka pro lokální zálohy", "")
        cp.set("backup", "backup_dir", store_dir)
        with open(self._get_ini_path(), "w", encoding="utf-8") as f:
            cp.write(f)

    # ── List / info ─────────────────────────────────────────────
    def list_backups(self, directory=None):
        """Return list of backup dicts sorted newest first.
        Each dict: {path, name, date, size_bytes, size_display}."""
        d = directory or self.backup_dir
        if not os.path.isdir(d):
            return []
        files = sorted(
            glob.glob(os.path.join(d, f"{self.BACKUP_PREFIX}*.zip")),
            key=os.path.getmtime, reverse=True,
        )
        result = []
        for fpath in files:
            stat = os.stat(fpath)
            size = stat.st_size
            name = os.path.basename(fpath)
            # Parse timestamp from name: TS_backup_YYYYMMDD_HHMMSS.zip
            ts_str = name.replace(self.BACKUP_PREFIX, "").replace(".zip", "")
            try:
                dt = datetime.datetime.strptime(ts_str, "%Y%m%d_%H%M%S")
                date_display = dt.strftime("%d.%m.%Y  %H:%M:%S")
            except ValueError:
                date_display = datetime.datetime.fromtimestamp(stat.st_mtime).strftime("%d.%m.%Y  %H:%M:%S")
            result.append({
                "path": fpath,
                "name": name,
                "date": date_display,
                "size_bytes": size,
                "size_display": self._format_size(size),
            })
        return result

    def get_last_backup_info(self):
        """Return info string about the most recent backup, or None."""
        backups = self.list_backups()
        if not backups:
            return None
        b = backups[0]
        return f"{b['date']}  ({b['size_display']})"

    @staticmethod
    def _format_size(size_bytes):
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        else:
            return f"{size_bytes / (1024 * 1024):.1f} MB"

    def delete_backup(self, zip_path):
        """Delete a single backup file."""
        if os.path.isfile(zip_path):
            os.remove(zip_path)

    def backup_local(self, dest_dir, progress_cb=None):
        """Create a ZIP backup of the DATA folder to dest_dir."""
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        zip_name = f"{self.BACKUP_PREFIX}{timestamp}.zip"
        zip_path = os.path.join(dest_dir, zip_name)

        files = self._get_data_files()
        total = len(files)

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for i, fpath in enumerate(files):
                arcname = os.path.relpath(fpath, self.ctx.app_dir)
                zf.write(fpath, arcname)
                if progress_cb:
                    progress_cb(int((i + 1) / total * 100))

        return zip_path

    def restore_local(self, zip_path, progress_cb=None):
        """Restore DATA folder from a ZIP backup."""
        if not os.path.isfile(zip_path):
            raise FileNotFoundError(f"Záloha nenalezena: {zip_path}")

        with zipfile.ZipFile(zip_path, "r") as zf:
            members = zf.namelist()
            total = len(members)
            for i, member in enumerate(members):
                # Security: prevent path traversal
                target = os.path.normpath(os.path.join(self.ctx.app_dir, member))
                if not target.startswith(os.path.normpath(self.ctx.app_dir)):
                    continue
                zf.extract(member, self.ctx.app_dir)
                if progress_cb:
                    progress_cb(int((i + 1) / total * 100))

    def backup_gdrive(self, progress_cb=None):
        """Backup DATA folder to Google Drive."""
        from app.services.gdrive_helper import GDriveHelper
        helper = GDriveHelper(self.ctx)

        # First create local temp ZIP
        temp_dir = os.path.join(self.ctx.app_dir, "_temp")
        os.makedirs(temp_dir, exist_ok=True)
        zip_path = self.backup_local(temp_dir, progress_cb=lambda v: progress_cb(v // 2) if progress_cb else None)

        try:
            helper.upload(zip_path, progress_cb=lambda v: progress_cb(50 + v // 2) if progress_cb else None)
        finally:
            # Clean temp
            if os.path.isfile(zip_path):
                os.remove(zip_path)
            if os.path.isdir(temp_dir) and not os.listdir(temp_dir):
                os.rmdir(temp_dir)

    def restore_gdrive(self, progress_cb=None):
        """Restore DATA folder from latest Google Drive backup."""
        from app.services.gdrive_helper import GDriveHelper
        helper = GDriveHelper(self.ctx)

        temp_dir = os.path.join(self.ctx.app_dir, "_temp")
        os.makedirs(temp_dir, exist_ok=True)

        try:
            zip_path = helper.download_latest(temp_dir,
                progress_cb=lambda v: progress_cb(v // 2) if progress_cb else None)
            self.restore_local(zip_path,
                progress_cb=lambda v: progress_cb(50 + v // 2) if progress_cb else None)
        finally:
            if os.path.isdir(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)

    def auto_daily_backup(self):
        """Run automatic backup at shutdown if enabled."""
        if not self.auto_backup:
            return False

        os.makedirs(self.backup_dir, exist_ok=True)
        self.backup_local(self.backup_dir)
        self._cleanup_old_backups(self.backup_dir, keep=self.keep_count)

        return True

    def _get_data_files(self):
        """Get all DATA files for backup."""
        patterns = [
            "*.DBF", "*.FPT", "*.CDX", "*.DBC", "*.DCT", "*.DCX",
            "*.db", "*.sqlite", "*.db-wal", "*.db-shm"
        ]
        files = []
        for pattern in patterns:
            files.extend(glob.glob(os.path.join(self.data_dir, pattern)))
            files.extend(glob.glob(os.path.join(self.data_dir, pattern.lower())))
        return list(set(files))

    def _cleanup_old_backups(self, directory, keep=7):
        """Remove oldest backups, keeping only 'keep' most recent."""
        backups = sorted(
            glob.glob(os.path.join(directory, f"{self.BACKUP_PREFIX}*.zip")),
            key=os.path.getmtime, reverse=True
        )
        for old in backups[keep:]:
            os.remove(old)
