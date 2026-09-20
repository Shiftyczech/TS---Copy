"""
DBF Service - Unified access to FoxPro DBF/FPT data files.
Uses the 'dbf' library with cp1250 encoding for Czech text.
"""
import os
import dbf
from contextlib import contextmanager
from collections import defaultdict
from typing import Optional


class DatabaseError(Exception):
    """Custom exception for DBF file access errors (missing, locked, corrupted)."""
    pass


class DbfService:
    def __init__(self, data_path: str):
        self.data_path = os.path.normpath(data_path)
        self._active_session = None
        self.on_mutation = None
        self._ensure_schema()

    def _notify_mutation(self, table_name: str):
        if self.on_mutation:
            try:
                clean_name = os.path.splitext(table_name)[0].lower()
                self.on_mutation(clean_name)
            except Exception:
                pass

    def _ensure_schema(self):
        """Auto-add SYMBOL column and resize Z_POSTA / U_POSTA to 80 chars if needed."""
        import shutil

        # 1) SYMBOL in tsd02 / tsd03
        for table_name in ["tsd02.dbf", "tsd03.dbf"]:
            path = self._table_path(table_name)
            if not os.path.exists(path):
                continue
            try:
                table = dbf.Table(path, codepage='cp1250')
                table.open(dbf.READ_WRITE)
                
                if 'SYMBOL' not in table.field_names:
                    table.add_fields('SYMBOL C(1)')

                table.close()
            except Exception:
                pass  # Ignore if locked or unable to upgrade

        # 2) Resize Z_POSTA and U_POSTA in order tables (tsd04, tsd06) to 80 chars
        for base_name in ["tsd04", "tsd06"]:
            path = self._table_path(f"{base_name}.dbf")
            if not os.path.exists(path):
                path = self._table_path(f"{base_name}.DBF")
            if not os.path.exists(path):
                continue

            try:
                table = dbf.Table(path, codepage='cp1250')
                table.open(dbf.READ_WRITE)
                
                needs_resize = False
                for field in ("Z_POSTA", "U_POSTA"):
                    if field in table.field_names:
                        info = table.field_info(field)
                        if info.length < 80:
                            needs_resize = True
                            break

                if needs_resize:
                    # Create safe backup before schema mutation
                    base_no_ext, ext = os.path.splitext(path)
                    try:
                        shutil.copy2(path, f"{base_no_ext}.bak")
                        for sidecar_ext in [".fpt", ".FPT", ".cdx", ".CDX"]:
                            sidecar = f"{base_no_ext}{sidecar_ext}"
                            if os.path.exists(sidecar):
                                shutil.copy2(sidecar, f"{sidecar}.bak")
                    except Exception:
                        pass

                    for field in ("Z_POSTA", "U_POSTA"):
                        if field in table.field_names:
                            info = table.field_info(field)
                            if info.length < 80:
                                table.resize_field(field, 80)

                table.close()
            except Exception as e:
                print(f"[DBF] Chyba při kontrole/rozšíření schématu {path}: {e}")
                pass

    def _table_path(self, table_name: str) -> str:
        return os.path.join(self.data_path, table_name)

    def _do_open(self, table_name: str, mode) -> dbf.Table:
        path = self._table_path(table_name)
        
        if self._active_session is not None:
            cache_key = (table_name, mode)
            if cache_key in self._active_session:
                return self._active_session[cache_key]
                
        try:
            table = dbf.Table(path, codepage='cp1250')
            table.open(mode)
            
            if self._active_session is not None:
                self._active_session[cache_key] = table
                
            return table
        except dbf.DbfError as e:
            raise DatabaseError(f"Chyba DBF formátu u tabulky {table_name}: {str(e)}") from e
        except FileNotFoundError as e:
            raise DatabaseError(f"Nenalezena tabulka {table_name} v cestě {path}.") from e
        except PermissionError as e:
            raise DatabaseError(f"Přístup odepřen k tabulce {table_name} (soubor je pravděpodobně uzamčen jiným uživatelem).") from e

    def _close_table(self, table: dbf.Table):
        """Close table only if it's not managed by an active session."""
        if self._active_session is not None:
            return
        table.close()

    @contextmanager
    def session(self):
        """Temporary cache for dbf.Table objects to avoid repeated open/close."""
        if self._active_session is not None:
            yield self
            return
            
        self._active_session = {}
        try:
            yield self
        finally:
            for table in self._active_session.values():
                try:
                    table.close()
                except Exception:
                    pass
            self._active_session = None

    def open_table(self, table_name: str) -> dbf.Table:
        return self._do_open(table_name, dbf.READ_WRITE)

    def open_table_readonly(self, table_name: str) -> dbf.Table:
        return self._do_open(table_name, dbf.READ_ONLY)

    def read_all(self, table_name: str) -> list[dict]:
        table = self.open_table_readonly(table_name)
        try:
            field_names = list(table.field_names)
            rows = []
            for record in table:
                if not dbf.is_deleted(record):
                    rows.append(self._record_to_dict(record, field_names))
            return rows
        finally:
            self._close_table(table)

    def read_by_key(self, table_name: str, key_field: str, key_value) -> Optional[dict]:
        table = self.open_table_readonly(table_name)
        try:
            field_names = list(table.field_names)
            for record in table:
                if not dbf.is_deleted(record):
                    val = self._get_field(record, key_field)
                    if self._values_equal(val, key_value):
                        return self._record_to_dict(record, field_names)
            return None
        finally:
            self._close_table(table)

    def read_where(self, table_name: str, conditions: dict) -> list[dict]:
        table = self.open_table_readonly(table_name)
        try:
            field_names = list(table.field_names)
            rows = []
            for record in table:
                if not dbf.is_deleted(record):
                    match = True
                    for field, value in conditions.items():
                        if not self._values_equal(self._get_field(record, field), value):
                            match = False
                            break
                    if match:
                        rows.append(self._record_to_dict(record, field_names))
            return rows
        finally:
            self._close_table(table)

    def insert(self, table_name: str, data: dict):
        table = self.open_table(table_name)
        try:
            table.append(data)
            self._notify_mutation(table_name)
        except dbf.DataOverflowError as e:
            raise DatabaseError(f"Chyba při vkládání do tabulky {table_name}: Hodnota je příliš dlouhá ({str(e)})") from e
        except Exception as e:
            raise DatabaseError(f"Chyba při vkládání do tabulky {table_name}: {str(e)}") from e
        finally:
            self._close_table(table)

    def update(self, table_name: str, key_field: str, key_value, data: dict) -> int:
        table = self.open_table(table_name)
        try:
            count = 0
            for record in table:
                if not dbf.is_deleted(record):
                    val = self._get_field(record, key_field)
                    if self._values_equal(val, key_value):
                        with record as r:
                            for field, value in data.items():
                                setattr(r, field, value)
                        count += 1
            if count > 0:
                self._notify_mutation(table_name)
            return count
        except dbf.DataOverflowError as e:
            raise DatabaseError(f"Chyba při aktualizaci tabulky {table_name}: Hodnota je příliš dlouhá ({str(e)})") from e
        except Exception as e:
            raise DatabaseError(f"Chyba při aktualizaci tabulky {table_name}: {str(e)}") from e
        finally:
            self._close_table(table)

    def update_record(self, table_name: str, record_index: int, data: dict):
        table = self.open_table(table_name)
        try:
            record = table[record_index]
            with record as r:
                for field, value in data.items():
                    setattr(r, field, value)
            self._notify_mutation(table_name)
        finally:
            self._close_table(table)

    def delete_record(self, table_name: str, record_index: int):
        table = self.open_table(table_name)
        try:
            record = table[record_index]
            if not dbf.is_deleted(record):
                dbf.delete(record)
                self._notify_mutation(table_name)
        finally:
            self._close_table(table)

    def delete(self, table_name: str, key_field: str, key_value) -> int:
        table = self.open_table(table_name)
        try:
            count = 0
            for record in table:
                if not dbf.is_deleted(record):
                    val = self._get_field(record, key_field)
                    if self._values_equal(val, key_value):
                        dbf.delete(record)
                        count += 1
            if count > 0:
                self._notify_mutation(table_name)
            return count
        finally:
            self._close_table(table)

    def delete_where(self, table_name: str, conditions: dict) -> int:
        table = self.open_table(table_name)
        try:
            count = 0
            for record in table:
                if not dbf.is_deleted(record):
                    match = True
                    for field, value in conditions.items():
                        if not self._values_equal(self._get_field(record, field), value):
                            match = False
                            break
                    if match:
                        dbf.delete(record)
                        count += 1
            if count > 0:
                self._notify_mutation(table_name)
            return count
        finally:
            self._close_table(table)

    def get_field_names(self, table_name: str) -> list[str]:
        table = self.open_table_readonly(table_name)
        try:
            return list(table.field_names)
        finally:
            self._close_table(table)

    def get_first_record(self, table_name: str) -> Optional[dict]:
        table = self.open_table_readonly(table_name)
        try:
            field_names = list(table.field_names)
            for record in table:
                if not dbf.is_deleted(record):
                    return self._record_to_dict(record, field_names)
            return None
        finally:
            self._close_table(table)

    def count(self, table_name: str) -> int:
        table = self.open_table_readonly(table_name)
        try:
            return sum(1 for r in table if not dbf.is_deleted(r))
        finally:
            self._close_table(table)

    def get_max_value(self, table_name: str, field: str):
        table = self.open_table_readonly(table_name)
        try:
            max_val = None
            max_num = None  # numeric shadow for numeric fields
            for record in table:
                if not dbf.is_deleted(record):
                    val = self._get_field(record, field)
                    # Try numeric comparison first to avoid lexicographic errors
                    # e.g. "9" > "1000" lexicographically but 9 < 1000 numerically
                    try:
                        num = float(val) if val not in (None, "") else None
                    except (ValueError, TypeError):
                        num = None

                    if num is not None:
                        if max_num is None or num > max_num:
                            max_num = num
                            max_val = val
                    else:
                        if max_val is None or val > max_val:
                            max_val = val
            return max_val
        finally:
            self._close_table(table)

    # ------------------------------------------------------------------
    # Batch / bulk operations (single open-close for many rows)
    # ------------------------------------------------------------------

    @contextmanager
    def open_context(self, table_name: str, readonly: bool = False):
        table = self.open_table_readonly(table_name) if readonly else self.open_table(table_name)
        try:
            yield table
        finally:
            self._close_table(table)

    def batch_insert(self, table_name: str, rows: list[dict]):
        if not rows:
            return
        table = self.open_table(table_name)
        try:
            for data in rows:
                clean = {k: v for k, v in data.items() if k != "_RECNO"}
                table.append(clean)
            self._notify_mutation(table_name)
        finally:
            self._close_table(table)

    def batch_update(self, table_name: str, key_field: str,
                     updates: dict) -> int:
        """updates: {key_value: {field: value, ...}, ...}
        Single pass through the table, applies matching updates.
        Returns number of records updated."""
        if not updates:
            return 0
        pending = dict(updates)
        count = 0
        table = self.open_table(table_name)
        try:
            for record in table:
                if not pending:
                    break
                if not dbf.is_deleted(record):
                    val = self._get_field(record, key_field)
                    str_val = str(val).strip()
                    data = pending.pop(val, None)
                    if data is None:
                        data = pending.pop(str_val, None)
                    if data:
                        with record as r:
                            for field, value in data.items():
                                setattr(r, field, value)
                        count += 1
            if count > 0:
                self._notify_mutation(table_name)
            return count
        finally:
            self._close_table(table)

    def batch_delete(self, table_name: str, key_field: str,
                     key_values: set) -> int:
        """Delete all records whose key_field value is in key_values.
        Single pass, single open-close. Returns number deleted."""
        if not key_values:
            return 0
        str_values = {str(v).strip() for v in key_values}
        count = 0
        table = self.open_table(table_name)
        try:
            for record in table:
                if not dbf.is_deleted(record):
                    val = str(self._get_field(record, key_field)).strip()
                    if val in str_values:
                        dbf.delete(record)
                        count += 1
            if count > 0:
                self._notify_mutation(table_name)
            return count
        finally:
            self._close_table(table)

    def read_where_in(self, table_name: str, field: str,
                      values: set) -> dict[str, list[dict]]:
        """Read records where field value is in values.
        Returns {str(value): [rows,...]} grouped by the field value.
        Single table scan."""
        if not values:
            return {}
        str_values = {str(v).strip() for v in values}
        result = defaultdict(list)
        table = self.open_table_readonly(table_name)
        try:
            field_names = list(table.field_names)
            for record in table:
                if not dbf.is_deleted(record):
                    val = str(self._get_field(record, field)).strip()
                    if val in str_values:
                        result[val].append(self._record_to_dict(record, field_names))
            return dict(result)
        finally:
            self._close_table(table)

    @staticmethod
    def _get_field(record, field_name: str):
        val = getattr(record, field_name.lower())
        if isinstance(val, str):
            return val.strip()
        return val

    @staticmethod
    def _values_equal(db_val, search_val):
        """Compare values with type coercion (str↔int/float)."""
        if db_val == search_val:
            return True
        # Try numeric comparison to handle leading zeros in IDs (e.g. 9812 == "009812")
        try:
            if float(db_val) == float(search_val):
                return True
        except (ValueError, TypeError):
            pass
        try:
            return str(db_val).strip() == str(search_val).strip()
        except Exception:
            return False

    @staticmethod
    def _record_to_dict(record, field_names: list) -> dict:
        import datetime as _dt
        d = {"_RECNO": dbf.recno(record)}
        for name in field_names:
            val = getattr(record, name.lower())
            if isinstance(val, str):
                val = val.strip()
            elif isinstance(val, (_dt.date, _dt.datetime)):
                year = val.year
                # Fix bad century from old VFP data:
                # - year < 100: 2-digit year stored without century (22 → 2022)
                # - year 100-1899: wrong century prefix (1202 → last 2 digits → 2002)
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
            d[name] = val
        return d
