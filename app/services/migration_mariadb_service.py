"""
Migration Service from SQLite (ts_data.db) to MariaDB.
Transfers all tables, columns, indexes, and records efficiently using bulk inserts.
"""
import os
import sqlite3
import datetime
from typing import Callable, Optional
import pymysql


class SqliteToMariaDbMigrator:
    INDEXED_COLS = {
        "CISLO_OBJ", "TRASA", "KOD", "FINAL", "PSC", "SYMBOL",
        "STATUS", "SMER", "CISLO", "TYP", "ICO", "DIC", "KOD_DILU"
    }

    INDEXES = [
        # Orders
        "CREATE INDEX idx_tsd04_cislo ON tsd04(CISLO_OBJ);",
        "CREATE INDEX idx_tsd04_trasa ON tsd04(TRASA);",
        "CREATE INDEX idx_tsd04a_cislo ON tsd04a(CISLO_OBJ);",
        "CREATE INDEX idx_tsd04b_cislo ON tsd04b(CISLO_OBJ);",
        "CREATE INDEX idx_tsd04b_kod ON tsd04b(KOD);",
        "CREATE INDEX idx_tsd04b_final ON tsd04b(FINAL);",
        # Archive
        "CREATE INDEX idx_tsd06_cislo ON tsd06(CISLO_OBJ);",
        "CREATE INDEX idx_tsd06_trasa ON tsd06(TRASA);",
        "CREATE INDEX idx_tsd06a_cislo ON tsd06a(CISLO_OBJ);",
        "CREATE INDEX idx_tsd06b_cislo ON tsd06b(CISLO_OBJ);",
        "CREATE INDEX idx_tsd06b_kod ON tsd06b(KOD);",
        "CREATE INDEX idx_tsd06b_final ON tsd06b(FINAL);",
        # Routes
        "CREATE INDEX idx_tsd05_cislo ON tsd05(CISLO);",
        "CREATE INDEX idx_tsd05a_cislo ON tsd05a(CISLO_OBJ);",
        # Basic parts & assemblies
        "CREATE INDEX idx_tsd02_kod ON tsd02(KOD);",
        "CREATE INDEX idx_tsd02a_final ON tsd02a(FINAL);",
        "CREATE INDEX idx_tsd02a_kod ON tsd02a(KOD);",
        "CREATE INDEX idx_tsd03_kod ON tsd03(KOD);",
        # Postal codes & users
        "CREATE INDEX idx_tsd01b_psc ON tsd01b(PSC);",
        "CREATE INDEX idx_tsd01a_kod ON tsd01a(KOD);",
        # Messages & emails
        "CREATE INDEX idx_tsd07_typ ON tsd07(TYP);",
        "CREATE INDEX idx_tsd08_cislo ON tsd08(CISLO_OBJ);",
    ]

    def __init__(self, sqlite_path: str, host: str, port: int, user: str, password: str, database: str = "ts_skleniky"):
        self.sqlite_path = sqlite_path
        self.host = host
        self.port = int(port)
        self.user = user
        self.password = password
        self.database = database

    def migrate(self, progress_callback: Optional[Callable[[int, str], None]] = None) -> dict[str, int]:
        if not os.path.isfile(self.sqlite_path):
            raise FileNotFoundError(f"SQLite soubor nenalezen: {self.sqlite_path}")

        if progress_callback:
            progress_callback(2, "Připojování k SQLite a MariaDB...")

        # Connect SQLite
        sqlite_conn = sqlite3.connect(self.sqlite_path, timeout=30.0)
        sqlite_cur = sqlite_conn.cursor()

        # Connect MariaDB
        maria_conn = pymysql.connect(
            host=self.host,
            port=self.port,
            user=self.user,
            password=self.password,
            database=self.database,
            charset="utf8mb4",
            autocommit=False
        )

        stats = {}
        try:
            # 1. Get all tables in SQLite
            sqlite_cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name;")
            tables = [r[0] for r in sqlite_cur.fetchall()]
            total_tables = len(tables)

            with maria_conn.cursor() as maria_cur:
                maria_cur.execute("SET FOREIGN_KEY_CHECKS=0;")

                for idx, tbl in enumerate(tables):
                    pct = 5 + int((idx / total_tables) * 80)
                    if progress_callback:
                        progress_callback(pct, f"Přenáším tabulku {tbl}...")

                    # Get SQLite columns
                    sqlite_cur.execute(f'PRAGMA table_info("{tbl}");')
                    cols_info = sqlite_cur.fetchall()  # (cid, name, type, notnull, dflt_value, pk)

                    col_defs = ["`_recno` INT AUTO_INCREMENT PRIMARY KEY"]
                    col_names = []
                    date_col_indices = set()

                    for c_idx, c in enumerate(cols_info):
                        c_name = c[1].upper()
                        c_type = (c[2] or "").upper()
                        col_names.append(c_name)

                        if "INT" in c_type:
                            m_type = "BIGINT"
                        elif "REAL" in c_type or "FLOAT" in c_type or "DOUBLE" in c_type or "NUM" in c_type:
                            m_type = "DOUBLE"
                        elif "DATE" in c_type or c_name.startswith("DATUM"):
                            m_type = "DATE"
                            date_col_indices.add(c_idx)
                        elif c_name in self.INDEXED_COLS:
                            m_type = "VARCHAR(100)"
                        else:
                            m_type = "TEXT"

                        col_defs.append(f"`{c_name}` {m_type}")

                    # Drop & Create MariaDB table
                    maria_cur.execute(f"DROP TABLE IF EXISTS `{tbl}`;")
                    create_sql = f"CREATE TABLE `{tbl}` ({', '.join(col_defs)}) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;"
                    maria_cur.execute(create_sql)

                    # Fetch rows from SQLite
                    col_list_str = ", ".join(f'"{c}"' for c in col_names)
                    sqlite_cur.execute(f'SELECT {col_list_str} FROM "{tbl}";')

                    # Bulk insert in batches of 1000
                    placeholders = ", ".join("%s" for _ in col_names)
                    maria_insert_sql = f"INSERT INTO `{tbl}` ({', '.join(f'`{c}`' for c in col_names)}) VALUES ({placeholders});"

                    batch = []
                    table_count = 0
                    while True:
                        rows = sqlite_cur.fetchmany(1000)
                        if not rows:
                            break
                        clean_rows = []
                        for r in rows:
                            row_vals = []
                            for c_i, val in enumerate(r):
                                if c_i in date_col_indices and val:
                                    # Parse date if string
                                    if isinstance(val, str):
                                        val = val.strip()
                                        if len(val) >= 10:
                                            try:
                                                val = datetime.date.fromisoformat(val[:10])
                                            except Exception:
                                                val = None
                                        else:
                                            val = None
                                elif isinstance(val, str):
                                    val = val.strip()
                                row_vals.append(val)
                            clean_rows.append(tuple(row_vals))

                        maria_cur.executemany(maria_insert_sql, clean_rows)
                        table_count += len(rows)

                    maria_conn.commit()
                    stats[tbl] = table_count

                # Create indexes
                if progress_callback:
                    progress_callback(90, "Vytváření indexů pro rychlé vyhledávání...")

                for idx_sql in self.INDEXES:
                    try:
                        maria_cur.execute(idx_sql)
                    except Exception as e:
                        # Index may already exist or column missing
                        pass

                maria_cur.execute("SET FOREIGN_KEY_CHECKS=1;")
                maria_conn.commit()

            if progress_callback:
                progress_callback(100, "Převod do MariaDB byl úspěšně dokončen!")

            return stats
        finally:
            sqlite_conn.close()
            maria_conn.close()
