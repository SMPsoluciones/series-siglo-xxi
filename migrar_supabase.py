"""Copia series.db (SQLite) a Supabase, conservando los ids. Se corre una sola vez.

    DATABASE_URL=... python migrar_supabase.py
"""
import os
import sqlite3
import sys

import psycopg

URL = os.environ.get("DATABASE_URL") or sys.exit("Falta DATABASE_URL")
TABLAS = ["series", "historial_scores", "recomendaciones"]

src = sqlite3.connect("series.db")
with psycopg.connect(URL, prepare_threshold=None) as pg:
    if pg.execute("SELECT count(*) FROM series").fetchone()[0]:
        sys.exit("Supabase ya tiene series; no copio nada.")
    for t in TABLAS:
        cur = src.execute(f"SELECT * FROM {t}")
        cols = [d[0] for d in cur.description]
        filas = cur.fetchall()
        if filas:
            with pg.cursor() as c:
                c.executemany(f"INSERT INTO {t} ({', '.join(cols)}) VALUES ({', '.join(['%s'] * len(cols))})", filas)
        pg.execute(f"SELECT setval(pg_get_serial_sequence('{t}', 'id'), COALESCE((SELECT max(id) FROM {t}), 0) + 1, false)")
        print(f"{t}: {len(filas)} filas")
