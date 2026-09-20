"""
Migration Service - Converts FoxPro DBF files to SQLite (ts_data.db).
Cleans up deleted records, creates typed SQLite tables and high-performance indexes.
"""
import os
import glob
import sqlite3
import datetime
import zipfile
import dbf
from typing import Callable, Optional


class MigrationService:
    def __init__(self, data_path: str, dest_db_file: Optional[str] = None):
        self.data_path = os.path.normpath(data_path)
        self.dest_db_file = dest_db_file or os.path.join(self.data_path, "ts_data.db")

    def create_pre_migration_backup(self, backup_dir: str) -> str:
        """Create a complete ZIP backup of all files in DATA before migration."""
        os.makedirs(backup_dir, exist_ok=True)
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        zip_path = os.path.join(backup_dir, f"TS_backup_pre_sqlite_{ts}.zip")

        patterns = ["*.DBF", "*.FPT", "*.CDX", "*.DBC", "*.DCT", "*.DCX"]
        files = []
        for p in patterns:
            files.extend(glob.glob(os.path.join(self.data_path, p)))
            files.extend(glob.glob(os.path.join(self.data_path, p.lower())))
        files = sorted(list(set(files)))

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for fpath in files:
                arcname = os.path.join("DATA", os.path.basename(fpath))
                zf.write(fpath, arcname)

        return zip_path

    def _get_dbf_tables(self) -> list[tuple[str, str]]:
        """Return list of (clean_name, full_path) for all DBF files."""
        tables = {}
        for fname in os.listdir(self.data_path):
            if fname.lower().endswith(".dbf"):
                clean = os.path.splitext(fname)[0].lower()
                full_path = os.path.join(self.data_path, fname)
                # Avoid duplicates
                if clean not in tables:
                    tables[clean] = full_path
        # Order known tables first for clean dependencies
        order = [
            "tsd00", "tsd01a", "tsd01b", "tsd01c", "tsd01d",
            "tsd02", "tsd02a", "tsd03", "tsd03a",
            "tsd04", "tsd04a", "tsd04b",
            "tsd05", "tsd05a", "tsd05b",
            "tsd06", "tsd06a", "tsd06b",
            "tsd07", "tsd08"
        ]
        sorted_tables = []
        for t in order:
            if t in tables:
                sorted_tables.append((t, tables.pop(t)))
        for k, v in sorted(tables.items()):
            sorted_tables.append((k, v))
        return sorted_tables

    def _map_field_type(self, field_info) -> str:
        """Map DBF field info to SQLite type."""
        # field_info is (type_char_or_ascii, length, decimals, python_type)
        t_char = field_info[0]
        if isinstance(t_char, int):
            t_char = chr(t_char)

        if t_char in ('C', 'M'):
            return "TEXT"
        elif t_char == 'N':
            return "INTEGER" if field_info[2] == 0 else "REAL"
        elif t_char in ('F', 'B', 'Y'):
            return "REAL"
        elif t_char in ('I', '+'):
            return "INTEGER"
        elif t_char == 'D':
            return "DATE"
        elif t_char in ('T', '@'):
            return "DATETIME"
        elif t_char == 'L':
            return "INTEGER"  # boolean 0 / 1
        return "TEXT"

    def _serialize_record(self, record, field_names: list) -> tuple:
        row = []
        for f in field_names:
            val = getattr(record, f.lower())
            if isinstance(val, str):
                val = val.strip()
            elif isinstance(val, (datetime.date, datetime.datetime)):
                year = val.year
                if year < 100:
                    corrected = year + 2000
                elif year < 1900:
                    two_digit = year % 100
                    corrected = two_digit + (2000 if two_digit < 50 else 1900)
                else:
                    corrected = None
                if corrected is not None:
                    try:
                        val = val.replace(year=corrected)
                    except Exception:
                        pass
                val = val.strftime("%Y-%m-%d")
            elif isinstance(val, bool):
                val = 1 if val else 0
            row.append(val)
        return tuple(row)

    def migrate(self, progress_callback: Optional[Callable[[int, str], None]] = None) -> dict[str, int]:
        """Execute full DBF to SQLite migration. Returns {table_name: imported_count}."""
        dbf_tables = self._get_dbf_tables()
        total_tables = len(dbf_tables)
        stats = {}

        temp_db_file = self.dest_db_file + ".tmp"
        if os.path.exists(temp_db_file):
            try:
                os.remove(temp_db_file)
            except Exception:
                pass

        conn = sqlite3.connect(temp_db_file, timeout=60.0)
        conn.execute("PRAGMA journal_mode=OFF;")
        conn.execute("PRAGMA synchronous=OFF;")
        conn.execute("PRAGMA cache_size=-64000;")  # 64MB cache

        try:
            for idx, (tbl_name, dbf_path) in enumerate(dbf_tables):
                pct = int((idx / max(1, total_tables)) * 85)
                if progress_callback:
                    progress_callback(pct, f"Převod tabulky {tbl_name.upper()}...")

                try:
                    table = dbf.Table(dbf_path, codepage='cp1250')
                    table.open(dbf.READ_ONLY)
                except Exception as e:
                    print(f"[MIGRATE] Nelze otevřít {dbf_path}: {e}")
                    continue

                try:
                    field_names = list(table.field_names)
                    # Build CREATE TABLE
                    col_defs = []
                    for f in field_names:
                        f_info = table.field_info(f)
                        sql_type = self._map_field_type(f_info)
                        col_defs.append(f'"{f.upper()}" {sql_type}')

                    # Auto add SYMBOL to tsd02 and tsd03 if missing in legacy DBF
                    if tbl_name in ("tsd02", "tsd03") and "SYMBOL" not in [fn.upper() for fn in field_names]:
                        col_defs.append('"SYMBOL" TEXT')

                    sql_create = f'CREATE TABLE "{tbl_name}" (\n    ' + ",\n    ".join(col_defs) + "\n);"
                    conn.execute(sql_create)

                    # Stream active rows
                    insert_cols = ", ".join(f'"{f.upper()}"' for f in field_names)
                    placeholders = ", ".join("?" for _ in field_names)
                    insert_sql = f'INSERT INTO "{tbl_name}" ({insert_cols}) VALUES ({placeholders});'

                    batch = []
                    imported_count = 0
                    conn.execute("BEGIN TRANSACTION;")

                    for record in table:
                        if not dbf.is_deleted(record):
                            batch.append(self._serialize_record(record, field_names))
                            if len(batch) >= 2000:
                                conn.executemany(insert_sql, batch)
                                imported_count += len(batch)
                                batch = []

                    if batch:
                        conn.executemany(insert_sql, batch)
                        imported_count += len(batch)

                    conn.execute("COMMIT;")
                    stats[tbl_name] = imported_count

                finally:
                    table.close()

            # Create Indexes
            if progress_callback:
                progress_callback(88, "Vytváření indexů pro bleskový přístup...")

            indexes = [
                # Orders
                'CREATE INDEX IF NOT EXISTS idx_tsd04_cislo ON tsd04(CISLO_OBJ);',
                'CREATE INDEX IF NOT EXISTS idx_tsd04_trasa ON tsd04(TRASA);',
                'CREATE INDEX IF NOT EXISTS idx_tsd04a_cislo ON tsd04a(CISLO_OBJ);',
                'CREATE INDEX IF NOT EXISTS idx_tsd04b_cislo ON tsd04b(CISLO_OBJ);',
                'CREATE INDEX IF NOT EXISTS idx_tsd04b_kod ON tsd04b(KOD);',
                'CREATE INDEX IF NOT EXISTS idx_tsd04b_final ON tsd04b(FINAL);',
                # Archive
                'CREATE INDEX IF NOT EXISTS idx_tsd06_cislo ON tsd06(CISLO_OBJ);',
                'CREATE INDEX IF NOT EXISTS idx_tsd06_trasa ON tsd06(TRASA);',
                'CREATE INDEX IF NOT EXISTS idx_tsd06a_cislo ON tsd06a(CISLO_OBJ);',
                'CREATE INDEX IF NOT EXISTS idx_tsd06b_cislo ON tsd06b(CISLO_OBJ);',
                'CREATE INDEX IF NOT EXISTS idx_tsd06b_kod ON tsd06b(KOD);',
                'CREATE INDEX IF NOT EXISTS idx_tsd06b_final ON tsd06b(FINAL);',
                # Routes
                'CREATE INDEX IF NOT EXISTS idx_tsd05_cislo ON tsd05(CISLO);',
                'CREATE INDEX IF NOT EXISTS idx_tsd05a_cislo ON tsd05a(CISLO_OBJ);',
                # Basic parts & assemblies
                'CREATE INDEX IF NOT EXISTS idx_tsd02_kod ON tsd02(KOD);',
                'CREATE INDEX IF NOT EXISTS idx_tsd02a_final ON tsd02a(FINAL);',
                'CREATE INDEX IF NOT EXISTS idx_tsd02a_kod ON tsd02a(KOD);',
                'CREATE INDEX IF NOT EXISTS idx_tsd03_kod ON tsd03(KOD);',
                # Postal codes & users
                'CREATE INDEX IF NOT EXISTS idx_tsd01b_psc ON tsd01b(PSC);',
                'CREATE INDEX IF NOT EXISTS idx_tsd01a_kod ON tsd01a(KOD);',
                # Messages & emails
                'CREATE INDEX IF NOT EXISTS idx_tsd07_typ ON tsd07(TYP);',
                'CREATE INDEX IF NOT EXISTS idx_tsd08_cislo ON tsd08(CISLO_OBJ);',
            ]

            conn.execute("BEGIN TRANSACTION;")
            for idx_sql in indexes:
                try:
                    conn.execute(idx_sql)
                except Exception as e:
                    print(f"[MIGRATE] Index error: {e}")
            conn.execute("COMMIT;")

            if progress_callback:
                progress_callback(95, "Optimalizace databáze (WAL a VACUUM)...")

            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
            conn.close()

            # Swap temp file into place atomically
            if os.path.exists(self.dest_db_file):
                old_bak = self.dest_db_file + ".old"
                if os.path.exists(old_bak):
                    try: os.remove(old_bak)
                    except Exception: pass
                try:
                    os.rename(self.dest_db_file, old_bak)
                except Exception:
                    pass

            if os.path.exists(self.dest_db_file):
                os.remove(self.dest_db_file)
            os.rename(temp_db_file, self.dest_db_file)

            if progress_callback:
                progress_callback(100, "Převod úspěšně dokončen!")

            return stats

        except Exception:
            conn.close()
            if os.path.exists(temp_db_file):
                try: os.remove(temp_db_file)
                except Exception: pass
            raise
