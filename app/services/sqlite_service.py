"""
SQLite Service - High-performance replacement for FoxPro DBF storage.
Provides 100% API compatibility with DbfService.
Uses SQLite with WAL mode, parameterized queries, and B-tree indexes.
"""
import os
import sqlite3
import datetime
import threading
from contextlib import contextmanager
from collections import defaultdict
from typing import Optional, Any


class DatabaseError(Exception):
    """Database access or execution error."""
    pass


def ensure_glass_pricing_consistency(conn: sqlite3.Connection):
    """Idempotently reset CENA = 0 and TYPDILU = 'S' for standard kit glass
    in order item detail tables (tsd04b, tsd06b) matching assembly recipe quotas (tsd02a),
    and recalculate CENA_DOPL and CENA_CELK in order header tables (tsd04, tsd06).
    
    This fixes legacy FoxPro DBF imports where glass was stored with non-zero replacement prices
    and empty TYPDILU, inflating CENA_CELK in order headers.
    """
    try:
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = {r[0].lower() for r in cur.fetchall()}

        # Always ensure existing explicit TYPDILU='S' has CENA=0 for backward compatibility
        for tbl in ("tsd04b", "tsd06b"):
            if tbl in tables:
                cur.execute(f'PRAGMA table_info("{tbl}");')
                cols = {r[1].upper() for r in cur.fetchall()}
                if "TYPDILU" in cols and "CENA" in cols:
                    cur.execute(f'UPDATE "{tbl}" SET "CENA" = 0 WHERE UPPER(TRIM("TYPDILU")) = \'S\' AND "CENA" != 0;')

        if "tsd02a" not in tables:
            return

        # Pre-load recipe quotas from tsd02a
        cur.execute("SELECT FINAL, KOD, MNOZSTVI FROM tsd02a")
        recipe_map = {}
        for r in cur.fetchall():
            try:
                recipe_map[(int(r[0]), int(r[1]))] = int(r[2] or 1)
            except (ValueError, TypeError):
                continue

        for order_tbl, item_tbl, detail_tbl in (("tsd04", "tsd04a", "tsd04b"), ("tsd06", "tsd06a", "tsd06b")):
            if order_tbl not in tables or item_tbl not in tables or detail_tbl not in tables:
                continue

            # Fast check: are there any candidate rows with CENA > 0 that might be kit glass?
            cur.execute(f"""
                SELECT DISTINCT CISLO_OBJ 
                FROM "{detail_tbl}" 
                WHERE CENA > 0 
                  AND (UPPER(TRIM(COALESCE(TYPDILU, ''))) = 'S' OR TRIM(COALESCE(TYPDILU, '')) = '')
                  AND (LOWER(NAZEV) LIKE '%sklo%' OR LOWER(NAZEV) LIKE '%souprava%')
            """)
            candidate_cisla = [r[0] for r in cur.fetchall()]
            if not candidate_cisla:
                continue

            for cislo in candidate_cisla:
                cur.execute(f'SELECT CENA_SEST, CENA_DOPL, CENA_DOPR, CENA_CELK FROM "{order_tbl}" WHERE CISLO_OBJ=?', (cislo,))
                order = cur.fetchone()
                if not order:
                    continue

                cur.execute(f'SELECT KOD, CENA, MNOZSTVI, DOPRAVNE FROM "{item_tbl}" WHERE CISLO_OBJ=?', (cislo,))
                items = cur.fetchall()

                cur.execute(f'SELECT rowid, FINAL, KOD, NAZEV, CENA, MNOZSTVI, TYPDILU FROM "{detail_tbl}" WHERE CISLO_OBJ=?', (cislo,))
                details = cur.fetchall()

                quotas = {}
                for it in items:
                    try:
                        ikod = int(it[0] or 0)
                        imnoz = int(it[2] or 1)
                        for (fkod, pkod), qmnoz in recipe_map.items():
                            if fkod == ikod:
                                quotas[(ikod, pkod)] = quotas.get((ikod, pkod), 0) + qmnoz * imnoz
                    except Exception:
                        pass

                total_sest = sum(float(it[1] or 0) * int(it[2] or 1) for it in items)
                total_dopr = sum(float(it[3] or 0) * int(it[2] or 1) for it in items)

                total_dopl = 0.0
                row_updates = []
                for d in details:
                    rid = d[0]
                    try:
                        dfinal = int(d[1] or 0)
                    except (ValueError, TypeError):
                        dfinal = 0
                    try:
                        dkod = int(d[2] or 0)
                    except (ValueError, TypeError):
                        dkod = 0
                    try:
                        dmnoz = int(d[5] or 1)
                    except (ValueError, TypeError):
                        dmnoz = 1
                    try:
                        dcena = float(d[4] or 0)
                    except (ValueError, TypeError):
                        dcena = 0.0
                    typ = str(d[6] or '').strip().upper()
                    nazev = str(d[3] or '').lower()

                    is_glass = False
                    if typ == 'S':
                        is_glass = True
                    elif typ == 'D':
                        is_glass = False
                    elif (dfinal, dkod) in quotas:
                        avail = quotas[(dfinal, dkod)]
                        if avail >= dmnoz:
                            quotas[(dfinal, dkod)] -= dmnoz
                            is_glass = True
                        elif avail > 0:
                            quotas[(dfinal, dkod)] = 0
                            is_glass = False
                    elif ('sklo' in nazev or 'souprava' in nazev) and dcena == 0:
                        is_glass = True

                    new_typ = 'S' if is_glass else ('D' if not typ else typ)
                    new_cena = 0.0 if is_glass else dcena

                    if new_cena != dcena or new_typ != typ:
                        row_updates.append((new_cena, new_typ, rid))

                    total_dopl += new_cena * dmnoz

                new_celk = int(round(total_sest + total_dopl + total_dopr))
                new_dopl = int(round(total_dopl))

                # Apply detail updates
                for u_cena, u_typ, u_rid in row_updates:
                    cur.execute(f'UPDATE "{detail_tbl}" SET "CENA" = ?, "TYPDILU" = ? WHERE rowid = ?', (u_cena, u_typ, u_rid))

                # Apply order header update
                cur.execute(f'UPDATE "{order_tbl}" SET "CENA_DOPL" = ?, "CENA_CELK" = ? WHERE CISLO_OBJ = ?', (new_dopl, new_celk, cislo))

            conn.commit()
    except Exception as e:
        print(f"[SqliteService] ensure_glass_pricing_consistency warning: {e}")


def ensure_phone_formatting_consistency(conn: sqlite3.Connection):
    """Idempotently format phone numbers in order headers (tsd04, tsd06) and config (tsd00)."""
    try:
        from app.utils import format_phone_number
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = {r[0].lower() for r in cur.fetchall()}

        targets = [
            ("tsd04", ["TELEFON", "MOBIL"]),
            ("tsd06", ["TELEFON", "MOBIL"]),
            ("tsd00", ["TELEFON", "FAX"]),
        ]

        for tbl, cols in targets:
            if tbl not in tables:
                continue
            cur.execute(f'PRAGMA table_info("{tbl}");')
            existing_cols = {r[1].upper() for r in cur.fetchall()}
            for col in cols:
                if col not in existing_cols:
                    continue
                cur.execute(f'SELECT rowid, "{col}" FROM "{tbl}" WHERE "{col}" IS NOT NULL AND "{col}" != \'\'')
                rows = cur.fetchall()
                updates = []
                for rid, val in rows:
                    fmt = format_phone_number(val)
                    if fmt != val:
                        updates.append((fmt, rid))
                if updates:
                    cur.executemany(f'UPDATE "{tbl}" SET "{col}" = ? WHERE rowid = ?', updates)
        conn.commit()
    except Exception as e:
        print(f"[SqliteService] ensure_phone_formatting_consistency warning: {e}")


class SqliteService:
    def __init__(self, db_path: str):
        # Support either full file path to .db or directory path containing ts_data.db
        if os.path.isdir(db_path):
            self.data_path = os.path.normpath(db_path)
            self.db_file = os.path.join(self.data_path, "ts_data.db")
        else:
            self.db_file = os.path.normpath(db_path)
            self.data_path = os.path.dirname(self.db_file)

        self.on_mutation = None
        self._local = threading.local()
        self._conn_lock = threading.Lock()
        self._all_connections = []
        self._column_cache = {}
        self._date_columns_cache = {}
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """Thread-safe connection retrieval with WAL mode enabled."""
        if not hasattr(self._local, "conn") or self._local.conn is None:
            conn = sqlite3.connect(
                self.db_file,
                timeout=30.0,
                check_same_thread=False,
                isolation_level=None  # autocommit mode; we manage transactions explicitly
            )
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
            conn.execute("PRAGMA foreign_keys=OFF;")
            self._local.conn = conn
            with self._conn_lock:
                self._all_connections.append(conn)
        return self._local.conn

    def checkpoint(self):
        """Flush WAL changes into the main database file."""
        try:
            if hasattr(self._local, "conn") and self._local.conn:
                self._local.conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
            elif self._all_connections:
                self._all_connections[0].execute("PRAGMA wal_checkpoint(TRUNCATE);")
            elif os.path.isfile(self.db_file):
                conn = self._get_connection()
                conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
        except Exception as e:
            print(f"[SqliteService] Checkpoint warning: {e}")

    def close(self):
        """Flush WAL and close all open connections across all threads."""
        try:
            self.checkpoint()
        except Exception:
            pass

        with self._conn_lock:
            for conn in self._all_connections:
                try:
                    conn.close()
                except Exception:
                    pass
            self._all_connections.clear()

        self._local.conn = None
        self._column_cache.clear()
        self._date_columns_cache.clear()

    def _init_db(self):
        """Ensure database directory exists and sanitize legacy data."""
        os.makedirs(os.path.dirname(self.db_file), exist_ok=True)
        # Touch DB connection
        conn = self._get_connection()
        self._ensure_glass_pricing_consistency(conn)
        ensure_phone_formatting_consistency(conn)

    def _ensure_glass_pricing_consistency(self, conn: sqlite3.Connection):
        ensure_glass_pricing_consistency(conn)

    def _clean_table_name(self, table_name: str) -> str:
        """Strip path and extension and return lower-case table name."""
        base = os.path.basename(table_name)
        return os.path.splitext(base)[0].lower()

    def _notify_mutation(self, table_name: str):
        if self.on_mutation:
            try:
                self.on_mutation(self._clean_table_name(table_name))
            except Exception:
                pass

    def _get_table_columns(self, table_name: str) -> list[str]:
        """Return list of uppercase column names for table (excluding rowid)."""
        tbl = self._clean_table_name(table_name)
        if tbl not in self._column_cache:
            conn = self._get_connection()
            cur = conn.cursor()
            try:
                cur.execute(f"PRAGMA table_info({tbl});")
                rows = cur.fetchall()
                if not rows:
                    return []
                # col[1] = column name, col[2] = data type
                cols = [r[1].upper() for r in rows if r[1].upper() != "_RECNO"]
                date_cols = {
                    r[1].upper() for r in rows 
                    if "DATE" in r[2].upper() or r[1].upper().startswith("DATUM")
                }
                self._column_cache[tbl] = cols
                self._date_columns_cache[tbl] = date_cols
            except Exception:
                return []
        return self._column_cache.get(tbl, [])

    def _get_date_columns(self, table_name: str) -> set[str]:
        tbl = self._clean_table_name(table_name)
        if tbl not in self._date_columns_cache:
            self._get_table_columns(tbl)
        return self._date_columns_cache.get(tbl, set())

    def _row_to_dict(self, table_name: str, row: tuple, col_names: list[str]) -> dict:
        """Convert a SQLite row (with rowid as first column) to dict matching DbfService format."""
        d = {"_RECNO": row[0]}
        date_cols = self._get_date_columns(table_name)

        for name, val in zip(col_names, row[1:]):
            if isinstance(val, str):
                val = val.strip()
                if name in date_cols and val:
                    # Parse ISO date YYYY-MM-DD
                    try:
                        if len(val) == 10 and val[4] == "-" and val[7] == "-":
                            val = datetime.date.fromisoformat(val)
                    except Exception:
                        pass
            elif isinstance(val, datetime.datetime):
                val = val.date()
            d[name] = val
        return d

    def _serialize_val(self, val: Any) -> Any:
        """Format Python values for SQLite storage."""
        if isinstance(val, (datetime.date, datetime.datetime)):
            return val.strftime("%Y-%m-%d")
        if isinstance(val, bool):
            return 1 if val else 0
        if isinstance(val, str):
            return val.strip()
        return val

    @contextmanager
    def session(self):
        """Context manager matching DbfService.session() for bulk operations."""
        conn = self._get_connection()
        nested = conn.in_transaction
        if not nested:
            conn.execute("BEGIN IMMEDIATE;")
        try:
            yield self
            if not nested:
                conn.execute("COMMIT;")
        except Exception:
            if not nested:
                conn.execute("ROLLBACK;")
            raise

    @contextmanager
    def open_context(self, table_name: str, readonly: bool = False):
        """Mock open_context for compatibility."""
        yield self

    # ------------------------------------------------------------------
    # CRUD Operations
    # ------------------------------------------------------------------

    def read_all(self, table_name: str) -> list[dict]:
        tbl = self._clean_table_name(table_name)
        cols = self._get_table_columns(tbl)
        if not cols:
            return []

        conn = self._get_connection()
        cur = conn.cursor()
        col_list = ", ".join(f'"{c}"' for c in cols)
        cur.execute(f'SELECT rowid, {col_list} FROM "{tbl}";')
        return [self._row_to_dict(tbl, r, cols) for r in cur.fetchall()]

    def read_by_key(self, table_name: str, key_field: str, key_value) -> Optional[dict]:
        tbl = self._clean_table_name(table_name)
        cols = self._get_table_columns(tbl)
        if not cols:
            return None

        key_col = key_field.upper()
        conn = self._get_connection()
        cur = conn.cursor()
        col_list = ", ".join(f'"{c}"' for c in cols)

        # Build condition handling both text and numeric representation (e.g. 9812 vs "009812")
        val = self._serialize_val(key_value)
        try:
            num_val = float(val) if val not in (None, "") else None
        except (ValueError, TypeError):
            num_val = None

        if num_val is not None:
            query = f'SELECT rowid, {col_list} FROM "{tbl}" WHERE "{key_col}" = ? OR "{key_col}" = ? LIMIT 1;'
            cur.execute(query, (val, int(num_val) if num_val.is_integer() else num_val))
        else:
            query = f'SELECT rowid, {col_list} FROM "{tbl}" WHERE "{key_col}" = ? LIMIT 1;'
            cur.execute(query, (val,))

        row = cur.fetchone()
        return self._row_to_dict(tbl, row, cols) if row else None

    def read_where(self, table_name: str, conditions: dict) -> list[dict]:
        tbl = self._clean_table_name(table_name)
        cols = self._get_table_columns(tbl)
        if not cols:
            return []

        if not conditions:
            return self.read_all(table_name)

        conn = self._get_connection()
        cur = conn.cursor()
        col_list = ", ".join(f'"{c}"' for c in cols)

        where_parts = []
        params = []
        for field, value in conditions.items():
            f_upper = field.upper()
            if value is None:
                where_parts.append(f'"{f_upper}" IS NULL')
                continue
            val = self._serialize_val(value)
            if val is None:
                where_parts.append(f'"{f_upper}" IS NULL')
                continue
            try:
                num_val = float(val) if val not in (None, "") else None
            except (ValueError, TypeError):
                num_val = None

            if num_val is not None and not isinstance(value, (datetime.date, datetime.datetime)):
                int_or_float = int(num_val) if num_val.is_integer() else num_val
                where_parts.append(f'("{f_upper}" = ? OR "{f_upper}" = ?)')
                params.extend([val, int_or_float])
            else:
                where_parts.append(f'"{f_upper}" = ?')
                params.append(val)

        where_clause = " AND ".join(where_parts)
        query = f'SELECT rowid, {col_list} FROM "{tbl}" WHERE {where_clause};'
        cur.execute(query, tuple(params))
        return [self._row_to_dict(tbl, r, cols) for r in cur.fetchall()]

    def read_where_in(self, table_name: str, field: str, values: set) -> dict[str, list[dict]]:
        """Read records where field value is in values. Returns {str(value): [rows,...]}."""
        if not values:
            return {}

        tbl = self._clean_table_name(table_name)
        cols = self._get_table_columns(tbl)
        if not cols:
            return {}

        conn = self._get_connection()
        cur = conn.cursor()
        col_list = ", ".join(f'"{c}"' for c in cols)
        f_upper = field.upper()

        val_list = list(values)
        # Handle IN batches to avoid SQLite variable limits if values > 900
        batch_size = 500
        result = defaultdict(list)

        for i in range(0, len(val_list), batch_size):
            chunk = val_list[i:i + batch_size]
            serialized_chunk = []
            for v in chunk:
                sv = self._serialize_val(v)
                serialized_chunk.append(sv)
                try:
                    num = float(sv)
                    serialized_chunk.append(int(num) if num.is_integer() else num)
                except (ValueError, TypeError):
                    pass

            placeholders = ", ".join("?" for _ in serialized_chunk)
            query = f'SELECT rowid, {col_list} FROM "{tbl}" WHERE "{f_upper}" IN ({placeholders});'
            cur.execute(query, tuple(serialized_chunk))
            for row in cur.fetchall():
                d = self._row_to_dict(tbl, row, cols)
                key_str = str(d.get(f_upper, "")).strip()
                result[key_str].append(d)

        return dict(result)

    def insert(self, table_name: str, data: dict):
        tbl = self._clean_table_name(table_name)
        cols = self._get_table_columns(tbl)
        clean = {k.upper(): self._serialize_val(v) for k, v in data.items() if k.upper() != "_RECNO"}
        if not clean:
            return

        valid_cols = [c for c in clean.keys() if c in cols]
        if not valid_cols:
            return

        col_names = ", ".join(f'"{c}"' for c in valid_cols)
        placeholders = ", ".join("?" for _ in valid_cols)
        values = [clean[c] for c in valid_cols]

        conn = self._get_connection()
        try:
            conn.execute(f'INSERT INTO "{tbl}" ({col_names}) VALUES ({placeholders});', tuple(values))
            self._notify_mutation(tbl)
        except Exception as e:
            raise DatabaseError(f"Chyba při vkládání do tabulky {tbl}: {str(e)}") from e

    def update(self, table_name: str, key_field: str, key_value, data: dict) -> int:
        tbl = self._clean_table_name(table_name)
        cols = self._get_table_columns(tbl)
        key_col = key_field.upper()

        clean = {k.upper(): self._serialize_val(v) for k, v in data.items() if k.upper() != "_RECNO" and k.upper() in cols}
        if not clean:
            return 0

        set_clause = ", ".join(f'"{c}" = ?' for c in clean.keys())
        params = list(clean.values())

        val = self._serialize_val(key_value)
        try:
            num_val = float(val) if val not in (None, "") else None
        except (ValueError, TypeError):
            num_val = None

        if num_val is not None:
            where_clause = f'"{key_col}" = ? OR "{key_col}" = ?'
            params.extend([val, int(num_val) if num_val.is_integer() else num_val])
        else:
            where_clause = f'"{key_col}" = ?'
            params.append(val)

        conn = self._get_connection()
        try:
            cur = conn.execute(f'UPDATE "{tbl}" SET {set_clause} WHERE {where_clause};', tuple(params))
            count = cur.rowcount
            if count > 0:
                self._notify_mutation(tbl)
            return count
        except Exception as e:
            raise DatabaseError(f"Chyba při aktualizaci tabulky {tbl}: {str(e)}") from e

    def update_record(self, table_name: str, record_index: int, data: dict):
        tbl = self._clean_table_name(table_name)
        cols = self._get_table_columns(tbl)

        clean = {k.upper(): self._serialize_val(v) for k, v in data.items() if k.upper() != "_RECNO" and k.upper() in cols}
        if not clean:
            return

        set_clause = ", ".join(f'"{c}" = ?' for c in clean.keys())
        params = list(clean.values())
        params.append(record_index)

        conn = self._get_connection()
        try:
            conn.execute(f'UPDATE "{tbl}" SET {set_clause} WHERE rowid = ?;', tuple(params))
            self._notify_mutation(tbl)
        except Exception as e:
            raise DatabaseError(f"Chyba při aktualizaci záznamu {record_index} v tabulce {tbl}: {str(e)}") from e

    def delete(self, table_name: str, key_field: str, key_value) -> int:
        tbl = self._clean_table_name(table_name)
        key_col = key_field.upper()

        val = self._serialize_val(key_value)
        try:
            num_val = float(val) if val not in (None, "") else None
        except (ValueError, TypeError):
            num_val = None

        params = []
        if num_val is not None:
            where_clause = f'"{key_col}" = ? OR "{key_col}" = ?'
            params.extend([val, int(num_val) if num_val.is_integer() else num_val])
        else:
            where_clause = f'"{key_col}" = ?'
            params.append(val)

        conn = self._get_connection()
        try:
            cur = conn.execute(f'DELETE FROM "{tbl}" WHERE {where_clause};', tuple(params))
            count = cur.rowcount
            if count > 0:
                self._notify_mutation(tbl)
            return count
        except Exception as e:
            raise DatabaseError(f"Chyba při mazání z tabulky {tbl}: {str(e)}") from e

    def delete_record(self, table_name: str, record_index: int):
        tbl = self._clean_table_name(table_name)
        conn = self._get_connection()
        try:
            conn.execute(f'DELETE FROM "{tbl}" WHERE rowid = ?;', (record_index,))
            self._notify_mutation(tbl)
        except Exception as e:
            raise DatabaseError(f"Chyba při mazání záznamu {record_index} z tabulky {tbl}: {str(e)}") from e

    def delete_where(self, table_name: str, conditions: dict) -> int:
        tbl = self._clean_table_name(table_name)
        if not conditions:
            return 0

        where_parts = []
        params = []
        for field, value in conditions.items():
            f_upper = field.upper()
            if value is None:
                where_parts.append(f'"{f_upper}" IS NULL')
                continue
            val = self._serialize_val(value)
            if val is None:
                where_parts.append(f'"{f_upper}" IS NULL')
                continue
            try:
                num_val = float(val) if val not in (None, "") else None
            except (ValueError, TypeError):
                num_val = None

            if num_val is not None and not isinstance(value, (datetime.date, datetime.datetime)):
                where_parts.append(f'("{f_upper}" = ? OR "{f_upper}" = ?)')
                params.extend([val, int(num_val) if num_val.is_integer() else num_val])
            else:
                where_parts.append(f'"{f_upper}" = ?')
                params.append(val)

        where_clause = " AND ".join(where_parts)
        conn = self._get_connection()
        try:
            cur = conn.execute(f'DELETE FROM "{tbl}" WHERE {where_clause};', tuple(params))
            count = cur.rowcount
            if count > 0:
                self._notify_mutation(tbl)
            return count
        except Exception as e:
            raise DatabaseError(f"Chyba při delete_where v tabulce {tbl}: {str(e)}") from e

    # ------------------------------------------------------------------
    # Batch / Bulk operations
    # ------------------------------------------------------------------

    def batch_insert(self, table_name: str, rows: list[dict]):
        if not rows:
            return
        tbl = self._clean_table_name(table_name)
        cols = self._get_table_columns(tbl)
        if not cols:
            return

        # Use first row or all valid cols
        all_keys = set()
        for r in rows:
            all_keys.update(k.upper() for k in r.keys() if k.upper() != "_RECNO" and k.upper() in cols)

        insert_cols = sorted(list(all_keys))
        if not insert_cols:
            return

        col_names = ", ".join(f'"{c}"' for c in insert_cols)
        placeholders = ", ".join("?" for _ in insert_cols)
        sql = f'INSERT INTO "{tbl}" ({col_names}) VALUES ({placeholders});'

        records = []
        for r in rows:
            clean_row = {k.upper(): v for k, v in r.items()}
            records.append(tuple(self._serialize_val(clean_row.get(c)) for c in insert_cols))

        conn = self._get_connection()
        nested = conn.in_transaction
        try:
            if not nested:
                conn.execute("BEGIN IMMEDIATE;")
            conn.executemany(sql, records)
            if not nested:
                conn.execute("COMMIT;")
            self._notify_mutation(tbl)
        except Exception as e:
            if not nested:
                conn.execute("ROLLBACK;")
            raise DatabaseError(f"Chyba při batch_insert do {tbl}: {str(e)}") from e

    def batch_update(self, table_name: str, key_field: str, updates: dict) -> int:
        """updates: {key_value: {field: value, ...}, ...}"""
        if not updates:
            return 0
        tbl = self._clean_table_name(table_name)
        cols = self._get_table_columns(tbl)
        key_col = key_field.upper()

        conn = self._get_connection()
        total_count = 0
        nested = conn.in_transaction
        try:
            if not nested:
                conn.execute("BEGIN IMMEDIATE;")
            for k_val, fields in updates.items():
                clean = {k.upper(): self._serialize_val(v) for k, v in fields.items() if k.upper() != "_RECNO" and k.upper() in cols}
                if not clean:
                    continue

                set_clause = ", ".join(f'"{c}" = ?' for c in clean.keys())
                params = list(clean.values())

                val = self._serialize_val(k_val)
                try:
                    num_val = float(val) if val not in (None, "") else None
                except (ValueError, TypeError):
                    num_val = None

                if num_val is not None:
                    where_clause = f'"{key_col}" = ? OR "{key_col}" = ?'
                    params.extend([val, int(num_val) if num_val.is_integer() else num_val])
                else:
                    where_clause = f'"{key_col}" = ?'
                    params.append(val)

                cur = conn.execute(f'UPDATE "{tbl}" SET {set_clause} WHERE {where_clause};', tuple(params))
                total_count += cur.rowcount

            if not nested:
                conn.execute("COMMIT;")
            if total_count > 0:
                self._notify_mutation(tbl)
            return total_count
        except Exception as e:
            if not nested:
                conn.execute("ROLLBACK;")
            raise DatabaseError(f"Chyba při batch_update v {tbl}: {str(e)}") from e

    def batch_delete(self, table_name: str, key_field: str, key_values: set) -> int:
        if not key_values:
            return 0
        tbl = self._clean_table_name(table_name)
        key_col = key_field.upper()

        val_list = list(key_values)
        total_deleted = 0
        conn = self._get_connection()
        nested = conn.in_transaction
        try:
            if not nested:
                conn.execute("BEGIN IMMEDIATE;")
            for i in range(0, len(val_list), 500):
                chunk = val_list[i:i + 500]
                serialized_chunk = []
                for v in chunk:
                    sv = self._serialize_val(v)
                    serialized_chunk.append(sv)
                    try:
                        num = float(sv)
                        serialized_chunk.append(int(num) if num.is_integer() else num)
                    except (ValueError, TypeError):
                        pass

                placeholders = ", ".join("?" for _ in serialized_chunk)
                cur = conn.execute(f'DELETE FROM "{tbl}" WHERE "{key_col}" IN ({placeholders});', tuple(serialized_chunk))
                total_deleted += cur.rowcount
            if not nested:
                conn.execute("COMMIT;")
            if total_deleted > 0:
                self._notify_mutation(tbl)
            return total_deleted
        except Exception as e:
            if not nested:
                conn.execute("ROLLBACK;")
            raise DatabaseError(f"Chyba při batch_delete v {tbl}: {str(e)}") from e

    # ------------------------------------------------------------------
    # Metadata and Utilities
    # ------------------------------------------------------------------

    def get_field_names(self, table_name: str) -> list[str]:
        return list(self._get_table_columns(table_name))

    def get_first_record(self, table_name: str) -> Optional[dict]:
        tbl = self._clean_table_name(table_name)
        cols = self._get_table_columns(tbl)
        if not cols:
            return None

        conn = self._get_connection()
        cur = conn.cursor()
        col_list = ", ".join(f'"{c}"' for c in cols)
        cur.execute(f'SELECT rowid, {col_list} FROM "{tbl}" LIMIT 1;')
        row = cur.fetchone()
        return self._row_to_dict(tbl, row, cols) if row else None

    def count(self, table_name: str) -> int:
        tbl = self._clean_table_name(table_name)
        conn = self._get_connection()
        cur = conn.cursor()
        try:
            cur.execute(f'SELECT COUNT(*) FROM "{tbl}";')
            row = cur.fetchone()
            return row[0] if row else 0
        except Exception:
            return 0

    def get_column_values(self, table_name: str, column: str) -> list[Any]:
        """Fetch distinct non-null values for a single column efficiently."""
        tbl = self._clean_table_name(table_name)
        col = column.upper()
        cols = self._get_table_columns(tbl)
        if col not in cols:
            return []
        conn = self._get_connection()
        cur = conn.cursor()
        try:
            cur.execute(f'SELECT DISTINCT "{col}" FROM "{tbl}" WHERE "{col}" IS NOT NULL AND "{col}" != "";')
            return [r[0] for r in cur.fetchall()]
        except Exception:
            return []

    def get_max_value(self, table_name: str, field: str):
        tbl = self._clean_table_name(table_name)
        f_upper = field.upper()
        conn = self._get_connection()
        cur = conn.cursor()
        try:
            # First try CAST to real to compare numerically
            cur.execute(f'SELECT MAX(CAST("{f_upper}" AS REAL)), MAX("{f_upper}") FROM "{tbl}";')
            row = cur.fetchone()
            if row and row[0] is not None:
                max_num = row[0]
                return int(max_num) if max_num.is_integer() else max_num
            return row[1] if row else None
        except Exception:
            return None
