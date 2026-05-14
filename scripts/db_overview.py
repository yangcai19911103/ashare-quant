"""列出 MySQL 库所有表 + 行数。"""
from __future__ import annotations

import io
import sys

import pymysql

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

c = pymysql.connect(
    host="localhost", port=3306, user="root", password="123456",
    database="ashare_quant", charset="utf8mb4",
)
cur = c.cursor()
cur.execute("SHOW TABLES")
tables = [r[0] for r in cur.fetchall()]
print(f"MySQL @ ashare_quant — {len(tables)} tables")
print("-" * 50)
for t in tables:
    cur.execute(f"SELECT COUNT(*) FROM `{t}`")
    n = cur.fetchone()[0]
    print(f"  {t:24s} rows={n}")
c.close()
