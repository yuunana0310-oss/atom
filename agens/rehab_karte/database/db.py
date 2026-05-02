import sqlite3
import os
from config import DB_PATH, SCHEMA_PATH


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def initialize_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with open(SCHEMA_PATH, encoding="utf-8") as f:
        schema = f.read()
    conn = get_connection()
    conn.executescript(schema)
    # patients テーブルへの列追加マイグレーション
    for col in ("early_bonus_14 DATE", "early_bonus_30 DATE"):
        try:
            conn.execute(f"ALTER TABLE patients ADD COLUMN {col}")
        except Exception:
            pass
    # 既存テーブルへの列追加マイグレーション
    for table in ("staff", "doctors"):
        try:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN order_index INTEGER NOT NULL DEFAULT 0")
        except Exception:
            pass  # 列が既に存在する場合はスキップ
        # 全レコードが order_index=0 のままなら id 順に連番を振る
        all_zero = conn.execute(
            f"SELECT COUNT(*) FROM {table} WHERE order_index != 0"
        ).fetchone()[0] == 0
        if all_zero:
            rows = conn.execute(f"SELECT id FROM {table} ORDER BY id").fetchall()
            for i, row in enumerate(rows):
                conn.execute(f"UPDATE {table} SET order_index=? WHERE id=?", (i, row[0]))
    conn.commit()
    conn.close()
