"""Base de datos de la colección.

Si hay una conexión configurada (`db_url` en .streamlit/secrets.toml o la variable DATABASE_URL)
usa Postgres en Supabase (esquema `series_xxi`); si no, usa el archivo local series.db (SQLite).
"""
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

import pandas as pd

DB_PATH = Path(__file__).parent / "series.db"


def _db_url():
    url = os.environ.get("DATABASE_URL")
    if url:
        return url
    try:
        import streamlit as st
        url = st.secrets.get("db_url")
        if url:
            return url
    except Exception:
        pass
    try:
        import tomllib
        p = Path(__file__).parent / ".streamlit" / "secrets.toml"
        return tomllib.loads(p.read_text(encoding="utf-8")).get("db_url")
    except Exception:
        return None


DB_URL = _db_url()
PG = bool(DB_URL)

ESTADOS = ["vista", "viendo", "pendiente", "abandonada"]

ESQUEMA = """
CREATE TABLE IF NOT EXISTS series (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    titulo          TEXT NOT NULL,
    imdb_id         TEXT UNIQUE,
    rt_url          TEXT,
    estado          TEXT NOT NULL DEFAULT 'pendiente',
    peri_rate       REAL,
    posteada        INTEGER NOT NULL DEFAULT 0,
    notas           TEXT,
    imdb            REAL,
    imdb_votos      INTEGER,
    rt              INTEGER,
    rt_audiencia    INTEGER,
    anio_inicio     INTEGER,
    anio_fin        INTEGER,
    en_emision      INTEGER NOT NULL DEFAULT 0,
    temporadas      INTEGER,
    episodios       INTEGER,
    generos         TEXT,
    sinopsis        TEXT,
    poster          TEXT,
    fecha_agregada  TEXT NOT NULL,
    fecha_vista     TEXT,
    actualizado_en  TEXT
);
CREATE TABLE IF NOT EXISTS historial_scores (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    serie_id    INTEGER NOT NULL REFERENCES series(id) ON DELETE CASCADE,
    fecha       TEXT NOT NULL,
    imdb        REAL,
    rt          INTEGER,
    rt_audiencia INTEGER
);
CREATE TABLE IF NOT EXISTS recomendaciones (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    titulo      TEXT NOT NULL,
    quien       TEXT,
    motivo      TEXT,
    fecha       TEXT NOT NULL,
    estado      TEXT NOT NULL DEFAULT 'nueva'   -- nueva | agregada | descartada
);
"""

CAMPOS = [
    "titulo", "imdb_id", "rt_url", "estado", "peri_rate", "posteada", "notas",
    "imdb", "imdb_votos", "rt", "rt_audiencia", "anio_inicio", "anio_fin",
    "en_emision", "temporadas", "episodios", "generos", "sinopsis", "poster",
    "fecha_agregada", "fecha_vista", "actualizado_en",
]


def ahora():
    return datetime.now().isoformat(timespec="seconds")


def refrescar_config():
    """Vuelve a leer la conexión (en la nube los Secrets pueden llegar después de importar el módulo)."""
    global DB_URL, PG
    if not PG:
        DB_URL = _db_url()
        PG = bool(DB_URL)
    return PG


def conectar():
    """Conexión cruda (SQLite o Postgres). Para scripts; en la app se usa _con()."""
    refrescar_config()
    if PG:
        import psycopg
        from psycopg.rows import dict_row
        return psycopg.connect(DB_URL, row_factory=dict_row, prepare_threshold=None, connect_timeout=15)
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    con.executescript(ESQUEMA)
    return con


@contextmanager
def _con():
    con = conectar()
    try:
        yield con
        con.commit()
    finally:
        con.close()


def _invalidar():
    """Después de escribir, borra la copia en memoria de la app para que se vea el cambio."""
    try:
        import streamlit as st
        st.cache_data.clear()
    except Exception:
        pass


def _sql(q):
    return q.replace("?", "%s") if PG else q


def _ejecutar(con, q, params=()):
    return con.execute(_sql(q), params)


def _uno(con, q, params=()):
    r = _ejecutar(con, q, params).fetchone()
    return dict(r) if r else None


def _tabla(con, q, params=()):
    cur = _ejecutar(con, q, params)
    cols = [d[0] for d in cur.description]
    return pd.DataFrame([tuple(dict(r).values()) if PG else tuple(r) for r in cur.fetchall()], columns=cols)


def todas():
    with _con() as con:
        return _tabla(con, "SELECT * FROM series ORDER BY id")


def obtener(serie_id):
    with _con() as con:
        return _uno(con, "SELECT * FROM series WHERE id = ?", (int(serie_id),))


def buscar_por_imdb(imdb_id):
    with _con() as con:
        return _uno(con, "SELECT * FROM series WHERE imdb_id = ?", (imdb_id,))


def _limpio(v):
    """Convierte tipos de numpy/pandas a tipos de Python (Postgres no los acepta)."""
    if v is None:
        return None
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    return v.item() if hasattr(v, "item") else v


def insertar(datos):
    datos = {k: _limpio(v) for k, v in datos.items() if k in CAMPOS}
    datos.setdefault("fecha_agregada", ahora())
    cols = ", ".join(datos)
    marcas = ", ".join("?" for _ in datos)
    try:
        with _con() as con:
            if PG:
                sid = _uno(con, f"INSERT INTO series ({cols}) VALUES ({marcas}) RETURNING id", list(datos.values()))["id"]
            else:
                sid = _ejecutar(con, f"INSERT INTO series ({cols}) VALUES ({marcas})", list(datos.values())).lastrowid
            _snapshot(con, sid, datos)
            return sid
    finally:
        _invalidar()


def actualizar(serie_id, datos):
    datos = {k: _limpio(v) for k, v in datos.items() if k in CAMPOS}
    if not datos:
        return
    serie_id = int(serie_id)
    sets = ", ".join(f"{k} = ?" for k in datos)
    try:
        with _con() as con:
            antes = _uno(con, "SELECT imdb, rt, rt_audiencia FROM series WHERE id = ?", (serie_id,))
            _ejecutar(con, f"UPDATE series SET {sets} WHERE id = ?", [*datos.values(), serie_id])
            if any(k in datos for k in ("imdb", "rt", "rt_audiencia")):
                nuevo = {k: datos.get(k, antes[k] if antes else None) for k in ("imdb", "rt", "rt_audiencia")}
                if antes is None or any(nuevo[k] != antes[k] for k in nuevo):
                    _snapshot(con, serie_id, nuevo)
    finally:
        _invalidar()


def borrar(serie_id):
    try:
        with _con() as con:
            _ejecutar(con, "DELETE FROM series WHERE id = ?", (int(serie_id),))
    finally:
        _invalidar()


def historial(serie_id):
    with _con() as con:
        return _tabla(con, "SELECT fecha, imdb, rt, rt_audiencia FROM historial_scores WHERE serie_id = ? ORDER BY fecha",
                      (int(serie_id),))


def cambios_recientes(limite=30):
    """Series cuyo IMDb o RT cambió entre sus dos últimos registros."""
    q = """
    WITH h AS (
        SELECT serie_id, fecha, imdb, rt,
               ROW_NUMBER() OVER (PARTITION BY serie_id ORDER BY fecha DESC, id DESC) AS n
        FROM historial_scores
    )
    SELECT s.id, s.titulo, a.fecha, b.imdb AS imdb_antes, a.imdb AS imdb_ahora,
           b.rt AS rt_antes, a.rt AS rt_ahora
    FROM h a JOIN h b ON a.serie_id = b.serie_id AND a.n = 1 AND b.n = 2
    JOIN series s ON s.id = a.serie_id
    WHERE COALESCE(a.imdb, -1) != COALESCE(b.imdb, -1) OR COALESCE(a.rt, -1) != COALESCE(b.rt, -1)
    ORDER BY a.fecha DESC LIMIT ?
    """
    with _con() as con:
        return _tabla(con, q, (int(limite),))


def recomendar(titulo, quien=None, motivo=None):
    try:
        with _con() as con:
            _ejecutar(con, "INSERT INTO recomendaciones (titulo, quien, motivo, fecha) VALUES (?, ?, ?, ?)",
                      (titulo.strip(), quien or None, motivo or None, ahora()))
    finally:
        _invalidar()


def recomendaciones(estado="nueva"):
    with _con() as con:
        return _tabla(con, "SELECT * FROM recomendaciones WHERE estado = ? ORDER BY fecha DESC", (estado,))


def marcar_recomendacion(rec_id, estado):
    try:
        with _con() as con:
            _ejecutar(con, "UPDATE recomendaciones SET estado = ? WHERE id = ?", (estado, int(rec_id)))
    finally:
        _invalidar()


def _snapshot(con, serie_id, datos):
    if any(datos.get(k) is not None for k in ("imdb", "rt", "rt_audiencia")):
        _ejecutar(con,
                  "INSERT INTO historial_scores (serie_id, fecha, imdb, rt, rt_audiencia) VALUES (?, ?, ?, ?, ?)",
                  (int(serie_id), ahora(), datos.get("imdb"), datos.get("rt"), datos.get("rt_audiencia")))
