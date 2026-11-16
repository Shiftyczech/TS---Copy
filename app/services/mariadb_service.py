"""
MariaDB Service - High-performance multi-user database service for Synology NAS.
Provides 100% API compatibility with SqliteService and DbfService.
Uses PyMySQL with connection pooling, parameterized queries, and ACID transactions.
"""
import os
import decimal
import datetime
import threading
from contextlib import contextmanager
from collections import defaultdict
from typing import Optional, Any, Callable

try:
    import pymysql
    from pymysql.cursors import Cursor
except ImportError:
    pymysql = None
    Cursor = None


class DatabaseError(Exception):
    """Database access or execution error."""
    pass


class MariaDbService:
    def __init__(self, host: str = "10.0.0.20", port: int = 3306,
                 user: str = "root", password: str = "",
                 database: str = "ts_skleniky", connect_timeout: int = 10,
                 data_path: Optional[str] = None):
        if pymysql is None:
            raise DatabaseError("Knihovna 'pymysql' není nainstalována. Spusťte: pip install pymysql")

        self.host = host
        self.port = int(port)
        self.user = user
        self.password = password
        self.database = database
        self.connect_timeout = connect_timeout
        self.data_path = os.path.normpath(data_path) if data_path else os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "DATA"))

        self.on_mutation = None
        self._local = threading.local()
        self._conn_lock = threading.Lock()
        self._all_connections = []
        self._column_cache = {}
        self._date_columns_cache = {}

        self._ensure_database()

    def _create_raw_connection(self, select_db: bool = True):
        """Create a new raw PyMySQL connection."""
        return pymysql.connect(
            host=self.host,
            port=self.port,
            user=self.user,
            password=self.password,
            database=self.database if select_db else None,
            charset="utf8mb4",
            connect_timeout=self.connect_timeout,
            autocommit=True
        )

    def _ensure_database(self):
        """Ensure the target database exists on MariaDB server."""
        try:
            conn = self._create_raw_connection(select_db=False)
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        f"CREATE DATABASE IF NOT EXISTS `{self.database}` "
                        "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
                    )
            finally:
                conn.close()
        except Exception as e:
            raise DatabaseError(f"Nelze se připojit k MariaDB na {self.host}:{self.port} - {e}") from e

    def _get_connection(self):
        """Thread-safe connection retrieval with auto-reconnect."""
        conn = getattr(self._local, "conn", None)
        if conn is not None:
            try:
                conn.ping(reconnect=True)
                return conn
            except Exception:
                conn = None

        new_conn = self._create_raw_connection(select_db=True)
        self._local.conn = new_conn
        with self._conn_lock:
            self._all_connections.append(new_conn)
        return new_conn

    def checkpoint(self):
        """No-op for MariaDB (handled automatically by InnoDB)."""
        pass

    def close(self):
        """Close all open connections across all threads."""
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
        """Return list of uppercase column names for table (excluding _recno)."""
        tbl = self._clean_table_name(table_name)
        if tbl not in self._column_cache:
            conn = self._get_connection()
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT COLUMN_NAME, DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS "
                        "WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s "
                        "ORDER BY ORDINAL_POSITION;",
                        (self.database, tbl)
                    )
                    rows = cur.fetchall()
                    if not rows:
                        return []
                    cols = [r[0].upper() for r in rows if r[0].upper() not in ("_RECNO", "ROWID")]
                    date_cols = {
                        r[0].upper() for r in rows
                        if "DATE" in r[1].upper() or r[0].upper().startswith("DATUM")
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
        """Convert a MariaDB row (with _recno as first column) to dict matching Dbf/Sqlite format."""
        d = {"_RECNO": row[0]}
        date_cols = self._get_date_columns(table_name)

        for name, val in zip(col_names, row[1:]):
            if isinstance(val, str):
                val = val.strip()
                if name in date_cols and val:
                    try:
                        if len(val) == 10 and val[4] == "-" and val[7] == "-":
                            val = datetime.date.fromisoformat(val)
                    except Exception:
                        pass
            elif isinstance(val, datetime.datetime):
                val = val.date()
            elif isinstance(val, decimal.Decimal):
                # Convert decimal to float or int for compatibility
                if val % 1 == 0:
                    val = int(val)
                else:
                    val = float(val)
            d[name] = val
        return d

    def _serialize_val(self, val: Any) -> Any:
        """Format Python values for MariaDB storage."""
        if isinstance(val, datetime.datetime):
            return val.strftime("%Y-%m-%d %H:%M:%S")
        if isinstance(val, datetime.date):
            return val.strftime("%Y-%m-%d")
        if isinstance(val, bool):
            return 1 if val else 0
        if isinstance(val, str):
            return val.strip()
        return val

    @contextmanager
    def session(self):
        """Context manager for explicit atomic transaction blocks."""
        conn = self._get_connection()
        conn.autocommit(False)
        try:
            yield self
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.autocommit(True)

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
        col_list = ", ".join(f"`{c}`" for c in cols)
        with conn.cursor() as cur:
            cur.execute(f"SELECT `_recno`, {col_list} FROM `{tbl}`;")
            return [self._row_to_dict(tbl, r, cols) for r in cur.fetchall()]

    def read_by_key(self, table_name: str, key_field: str, key_value) -> Optional[dict]:
        tbl = self._clean_table_name(table_name)
        cols = self._get_table_columns(tbl)
        if not cols:
            return None

        key_col = key_field.upper()
        conn = self._get_connection()
        col_list = ", ".join(f"`{c}`" for c in cols)

        val = self._serialize_val(key_value)
        try:
            num_val = float(val) if val not in (None, "") else None
        except (ValueError, TypeError):
            num_val = None

        with conn.cursor() as cur:
            if num_val is not None:
                query = f"SELECT `_recno`, {col_list} FROM `{tbl}` WHERE `{key_col}` = %s OR `{key_col}` = %s LIMIT 1;"
                cur.execute(query, (val, int(num_val) if num_val.is_integer() else num_val))
            else:
                query = f"SELECT `_recno`, {col_list} FROM `{tbl}` WHERE `{key_col}` = %s LIMIT 1;"
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
        col_list = ", ".join(f"`{c}`" for c in cols)

        where_parts = []
        params = []
        for field, value in conditions.items():
            f_upper = field.upper()
            val = self._serialize_val(value)
            try:
                num_val = float(val) if val not in (None, "") else None
            except (ValueError, TypeError):
                num_val = None

            if num_val is not None and not isinstance(value, (datetime.date, datetime.datetime)):
                int_or_float = int(num_val) if num_val.is_integer() else num_val
                where_parts.append(f"(`{f_upper}` = %s OR `{f_upper}` = %s)")
                params.extend([val, int_or_float])
            else:
                where_parts.append(f"`{f_upper}` = %s")
                params.append(val)

        where_clause = " AND ".join(where_parts)
        query = f"SELECT `_recno`, {col_list} FROM `{tbl}` WHERE {where_clause};"
        with conn.cursor() as cur:
            cur.execute(query, tuple(params))
            return [self._row_to_dict(tbl, r, cols) for r in cur.fetchall()]

    def read_where_in(self, table_name: str, field: str, values: set) -> dict[str, list[dict]]:
        if not values:
            return {}

        tbl = self._clean_table_name(table_name)
        cols = self._get_table_columns(tbl)
        if not cols:
            return {}

        conn = self._get_connection()
        col_list = ", ".join(f"`{c}`" for c in cols)
        f_upper = field.upper()

        val_list = list(values)
        batch_size = 500
        result = defaultdict(list)

        with conn.cursor() as cur:
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

                placeholders = ", ".join("%s" for _ in serialized_chunk)
                query = f"SELECT `_recno`, {col_list} FROM `{tbl}` WHERE `{f_upper}` IN ({placeholders});"
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

        col_names = ", ".join(f"`{c}`" for c in valid_cols)
        placeholders = ", ".join("%s" for _ in valid_cols)
        values = [clean[c] for c in valid_cols]

        conn = self._get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(f"INSERT INTO `{tbl}` ({col_names}) VALUES ({placeholders});", tuple(values))
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

        set_clause = ", ".join(f"`{c}` = %s" for c in clean.keys())
        params = list(clean.values())

        val = self._serialize_val(key_value)
        try:
            num_val = float(val) if val not in (None, "") else None
        except (ValueError, TypeError):
            num_val = None

        if num_val is not None:
            where_clause = f"`{key_col}` = %s OR `{key_col}` = %s"
            params.extend([val, int(num_val) if num_val.is_integer() else num_val])
        else:
            where_clause = f"`{key_col}` = %s"
            params.append(val)

        conn = self._get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(f"UPDATE `{tbl}` SET {set_clause} WHERE {where_clause};", tuple(params))
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

        set_clause = ", ".join(f"`{c}` = %s" for c in clean.keys())
        params = list(clean.values())
        params.append(record_index)

        conn = self._get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(f"UPDATE `{tbl}` SET {set_clause} WHERE `_recno` = %s;", tuple(params))
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
            where_clause = f"`{key_col}` = %s OR `{key_col}` = %s"
            params.extend([val, int(num_val) if num_val.is_integer() else num_val])
        else:
            where_clause = f"`{key_col}` = %s"
            params.append(val)

        conn = self._get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(f"DELETE FROM `{tbl}` WHERE {where_clause};", tuple(params))
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
            with conn.cursor() as cur:
                cur.execute(f"DELETE FROM `{tbl}` WHERE `_recno` = %s;", (record_index,))
            self._notify_mutation(tbl)
        except Exception as e:
            raise DatabaseError(f"Chyba při mazání záznamu {record_index} z tabulce {tbl}: {str(e)}") from e

    def delete_where(self, table_name: str, conditions: dict) -> int:
        tbl = self._clean_table_name(table_name)
        if not conditions:
            return 0

        where_parts = []
        params = []
        for field, value in conditions.items():
            f_upper = field.upper()
            val = self._serialize_val(value)
            try:
                num_val = float(val) if val not in (None, "") else None
            except (ValueError, TypeError):
                num_val = None

            if num_val is not None and not isinstance(value, (datetime.date, datetime.datetime)):
                where_parts.append(f"(`{f_upper}` = %s OR `{f_upper}` = %s)")
                params.extend([val, int(num_val) if num_val.is_integer() else num_val])
            else:
                where_parts.append(f"`{f_upper}` = %s")
                params.append(val)

        where_clause = " AND ".join(where_parts)
        conn = self._get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(f"DELETE FROM `{tbl}` WHERE {where_clause};", tuple(params))
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

        all_keys = set()
        for r in rows:
            all_keys.update(k.upper() for k in r.keys() if k.upper() != "_RECNO" and k.upper() in cols)

        insert_cols = sorted(list(all_keys))
        if not insert_cols:
            return

        col_names = ", ".join(f"`{c}`" for c in insert_cols)
        placeholders = ", ".join("%s" for _ in insert_cols)
        sql = f"INSERT INTO `{tbl}` ({col_names}) VALUES ({placeholders});"

        records = []
        for r in rows:
            clean_row = {k.upper(): v for k, v in r.items()}
            records.append(tuple(self._serialize_val(clean_row.get(c)) for c in insert_cols))

        conn = self._get_connection()
        try:
            with conn.cursor() as cur:
                cur.executemany(sql, records)
            self._notify_mutation(tbl)
        except Exception as e:
            raise DatabaseError(f"Chyba při batch_insert do {tbl}: {str(e)}") from e

    def batch_update(self, table_name: str, key_field: str, updates: dict) -> int:
        if not updates:
            return 0
        tbl = self._clean_table_name(table_name)
        cols = self._get_table_columns(tbl)
        key_col = key_field.upper()

        conn = self._get_connection()
        total_count = 0
        try:
            with conn.cursor() as cur:
                for k_val, fields in updates.items():
                    clean = {k.upper(): self._serialize_val(v) for k, v in fields.items() if k.upper() != "_RECNO" and k.upper() in cols}
                    if not clean:
                        continue

                    set_clause = ", ".join(f"`{c}` = %s" for c in clean.keys())
                    params = list(clean.values())

                    val = self._serialize_val(k_val)
                    try:
                        num_val = float(val) if val not in (None, "") else None
                    except (ValueError, TypeError):
                        num_val = None

                    if num_val is not None:
                        where_clause = f"`{key_col}` = %s OR `{key_col}` = %s"
                        params.extend([val, int(num_val) if num_val.is_integer() else num_val])
                    else:
                        where_clause = f"`{key_col}` = %s"
                        params.append(val)

                    cur.execute(f"UPDATE `{tbl}` SET {set_clause} WHERE {where_clause};", tuple(params))
                    total_count += cur.rowcount
            if total_count > 0:
                self._notify_mutation(tbl)
            return total_count
        except Exception as e:
            raise DatabaseError(f"Chyba při batch_update v {tbl}: {str(e)}") from e

    def batch_delete(self, table_name: str, key_field: str, key_values: set) -> int:
        if not key_values:
            return 0
        tbl = self._clean_table_name(table_name)
        key_col = key_field.upper()

        val_list = list(key_values)
        total_deleted = 0
        conn = self._get_connection()
        try:
            with conn.cursor() as cur:
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

                    placeholders = ", ".join("%s" for _ in serialized_chunk)
                    cur.execute(f"DELETE FROM `{tbl}` WHERE `{key_col}` IN ({placeholders});", tuple(serialized_chunk))
                    total_deleted += cur.rowcount
            if total_deleted > 0:
                self._notify_mutation(tbl)
            return total_deleted
        except Exception as e:
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
        col_list = ", ".join(f"`{c}`" for c in cols)
        with conn.cursor() as cur:
            cur.execute(f"SELECT `_recno`, {col_list} FROM `{tbl}` LIMIT 1;")
            row = cur.fetchone()
            return self._row_to_dict(tbl, row, cols) if row else None

    def count(self, table_name: str) -> int:
        tbl = self._clean_table_name(table_name)
        conn = self._get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(f"SELECT COUNT(*) FROM `{tbl}`;")
                row = cur.fetchone()
                return row[0] if row else 0
        except Exception:
            return 0

    def get_max_value(self, table_name: str, field: str):
        tbl = self._clean_table_name(table_name)
        f_upper = field.upper()
        conn = self._get_connection()
        try:
            with conn.cursor() as cur:
                # `field + 0` casts text to number in MySQL/MariaDB cleanly
                cur.execute(f"SELECT MAX(`{f_upper}` + 0), MAX(`{f_upper}`) FROM `{tbl}`;")
                row = cur.fetchone()
                if row and row[0] is not None:
                    max_num = row[0]
                    return int(max_num) if float(max_num).is_integer() else max_num
                return row[1] if row else None
        except Exception:
            return None


def test_mariadb_connection(host: str, port: int, user: str, password: str, database: str = "ts_skleniky") -> tuple[bool, str]:
    """Test connection to MariaDB server. Returns (success, message)."""
    if pymysql is None:
        return False, "Knihovna pymysql není nainstalována."
    try:
        conn = pymysql.connect(
            host=host,
            port=int(port),
            user=user,
            password=password,
            connect_timeout=5
        )
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT VERSION();")
                ver = cur.fetchone()[0]
                cur.execute(f"CREATE DATABASE IF NOT EXISTS `{database}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;")
            return True, f"Připojení úspěšné! MariaDB verze: {ver}"
        finally:
            conn.close()
    except pymysql.err.OperationalError as e:
        return False, f"Chyba připojení k serveru {host}:{port}: {e}"
    except Exception as e:
        return False, f"Chyba: {e}"
