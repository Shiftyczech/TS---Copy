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

    def _dump_mariadb(self, out_sql_path: str):
        """Export MariaDB database to an SQL dump file."""
        if getattr(self.ctx, "backend_name", "") != "mariadb" or not getattr(self.ctx, "db", None):
            return
        conn = getattr(self.ctx.db, "_get_connection", lambda: None)()
        if not conn:
            return

        with open(out_sql_path, "w", encoding="utf-8") as f:
            f.write("-- TS Skleniky MariaDB Dump\n")
            f.write(f"-- Generated: {datetime.datetime.now().isoformat()}\n\n")
            f.write("SET FOREIGN_KEY_CHECKS=0;\n\n")

            with conn.cursor() as cur:
                cur.execute("SHOW TABLES;")
                tables = [r[0] for r in cur.fetchall()]

                for tbl in tables:
                    cur.execute(f"SHOW CREATE TABLE `{tbl}`;")
                    create_stmt = cur.fetchone()[1]
                    f.write(f"DROP TABLE IF EXISTS `{tbl}`;\n")
                    f.write(f"{create_stmt};\n\n")

                    cur.execute(f"SELECT * FROM `{tbl}`;")
                    rows = cur.fetchall()
                    if rows:
                        col_names = [d[0] for d in cur.description]
                        col_str = ", ".join(f"`{c}`" for c in col_names)
                        f.write(f"INSERT INTO `{tbl}` ({col_str}) VALUES\n")
                        batch_lines = []
                        for r in rows:
                            vals = []
                            for val in r:
                                if val is None:
                                    vals.append("NULL")
                                elif isinstance(val, (int, float)):
                                    vals.append(str(val))
                                elif isinstance(val, (datetime.date, datetime.datetime)):
                                    vals.append(f"'{val}'")
                                else:
                                    escaped = str(val).replace("\\", "\\\\").replace("'", "\\'")
                                    vals.append(f"'{escaped}'")
                            batch_lines.append(f"  ({', '.join(vals)})")
                        f.write(",\n".join(batch_lines) + ";\n\n")

            f.write("SET FOREIGN_KEY_CHECKS=1;\n")

    def _sync_mariadb_to_sqlite(self):
        """Mirror current MariaDB tables into local SQLite ts_data.db as offline cache and backup."""
        if getattr(self.ctx, "backend_name", "") != "mariadb" or not getattr(self.ctx, "db", None):
            return
        conn = getattr(self.ctx.db, "_get_connection", lambda: None)()
        if not conn:
            return

        import sqlite3
        sqlite_file = os.path.join(self.data_dir, "ts_data.db")
        os.makedirs(self.data_dir, exist_ok=True)

        try:
            sq_conn = sqlite3.connect(sqlite_file, timeout=30.0)
            sq_cur = sq_conn.cursor()

            with conn.cursor() as cur:
                cur.execute("SHOW TABLES;")
                tables = [r[0] for r in cur.fetchall()]

                for tbl in tables:
                    cur.execute(
                        "SELECT COLUMN_NAME, DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS "
                        "WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s ORDER BY ORDINAL_POSITION;",
                        (self.ctx.db.database, tbl)
                    )
                    cols_info = cur.fetchall()
                    if not cols_info:
                        continue

                    data_cols = []
                    col_defs = []
                    for c_name, d_type in cols_info:
                        cu = c_name.upper()
                        dt = (d_type or "").upper()
                        if cu in ("_RECNO", "ROWID"):
                            continue
                        data_cols.append(cu)
                        if any(t in dt for t in ("INT", "BIGINT", "SMALLINT", "TINYINT")):
                            sq_t = "INTEGER"
                        elif any(t in dt for t in ("FLOAT", "DOUBLE", "DECIMAL", "NUMERIC", "REAL")):
                            sq_t = "REAL"
                        elif "DATE" in dt or cu.startswith("DATUM"):
                            sq_t = "DATE"
                        else:
                            sq_t = "TEXT"
                        col_defs.append(f'"{cu}" {sq_t}')

                    if not data_cols:
                        continue

                    sq_cur.execute(f'DROP TABLE IF EXISTS "{tbl}";')
                    sq_cur.execute(f'CREATE TABLE "{tbl}" ({", ".join(col_defs)});')

                    col_str = ", ".join(f"`{c}`" for c in data_cols)
                    cur.execute(f"SELECT {col_str} FROM `{tbl}`;")
                    rows = cur.fetchall()
                    if rows:
                        clean_rows = []
                        for r in rows:
                            clean_rows.append(tuple(
                                v.strftime("%Y-%m-%d") if isinstance(v, (datetime.date, datetime.datetime)) else v
                                for v in r
                            ))
                        placeholders = ", ".join("?" for _ in data_cols)
                        sq_cur.executemany(f'INSERT INTO "{tbl}" ({", ".join(f"`{c}`" for c in data_cols)}) VALUES ({placeholders});', clean_rows)

            sq_conn.commit()
            sq_conn.close()
        except Exception as e:
            print(f"[BackupService] Error syncing MariaDB to local SQLite: {e}")

    def backup_local(self, dest_dir, progress_cb=None):
        """Create a ZIP backup of the DATA folder (and MariaDB dump if active) to dest_dir."""
        if hasattr(self.ctx, "db") and self.ctx.db and hasattr(self.ctx.db, "checkpoint"):
            try:
                self.ctx.db.checkpoint()
            except Exception as e:
                print(f"[BackupService] Checkpoint error: {e}")

        # Dump MariaDB to SQL file and mirror to local SQLite inside DATA if active
        mariadb_sql_path = None
        if getattr(self.ctx, "backend_name", "") == "mariadb":
            try:
                self._sync_mariadb_to_sqlite()
            except Exception as e:
                print(f"[BackupService] MariaDB to SQLite sync error: {e}")
            try:
                mariadb_sql_path = os.path.join(self.data_dir, "mariadb_backup.sql")
                self._dump_mariadb(mariadb_sql_path)
            except Exception as e:
                print(f"[BackupService] MariaDB dump error: {e}")

        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        zip_name = f"{self.BACKUP_PREFIX}{timestamp}.zip"
        zip_path = os.path.join(dest_dir, zip_name)

        files = self._get_data_files()
        if mariadb_sql_path and os.path.isfile(mariadb_sql_path) and mariadb_sql_path not in files:
            files.append(mariadb_sql_path)

        # Include db_config.ini in the backup if it exists
        db_cfg_path = os.path.join(self.ctx.app_dir, "db_config.ini")
        if os.path.isfile(db_cfg_path):
            files.append(db_cfg_path)

        total = len(files)

        try:
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for i, fpath in enumerate(files):
                    arcname = os.path.relpath(fpath, self.ctx.app_dir)
                    zf.write(fpath, arcname)
                    if progress_cb:
                        progress_cb(int((i + 1) / total * 100))
        finally:
            if mariadb_sql_path and os.path.isfile(mariadb_sql_path):
                try:
                    os.remove(mariadb_sql_path)
                except Exception:
                    pass

        return zip_path

    def restore_local(self, zip_path, progress_cb=None):
        """Restore DATA folder from a ZIP backup."""
        if not os.path.isfile(zip_path):
            raise FileNotFoundError(f"Záloha nenalezena: {zip_path}")

        if hasattr(self.ctx, "close_db"):
            self.ctx.close_db()

        with zipfile.ZipFile(zip_path, "r") as zf:
            # Skip any .db-shm files (temporary shared memory, should never be restored)
            members = [m for m in zf.namelist() if not m.lower().endswith(".db-shm")]
            total = len(members)
            for i, member in enumerate(members):
                # Security: prevent path traversal
                target = os.path.normpath(os.path.join(self.ctx.app_dir, member))
                if not target.startswith(os.path.normpath(self.ctx.app_dir)):
                    continue
                zf.extract(member, self.ctx.app_dir)
                if progress_cb:
                    progress_cb(int((i + 1) / total * 100))

        # Clean up any leftover temporary SQLite WAL/SHM files on disk
        for extra in ["ts_data.db-shm", "ts_data.db-wal"]:
            extra_path = os.path.join(self.data_dir, extra)
            if os.path.isfile(extra_path):
                try:
                    os.remove(extra_path)
                except Exception as e:
                    print(f"[BackupService] Upozornění: Nelze smazat dočasný {extra}: {e}")

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
            "*.db", "*.sqlite", "*.db-wal"
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
