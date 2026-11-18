"""Carga inicial: pasa TOP_SERIES_SIGLOXXI_NUEVA.xlsx a series.db (solo se corre una vez).

    python migrar_excel.py
Después: python sincronizar.py   (vincula cada serie con IMDb y actualiza scores)
"""
import re
import sys

import pandas as pd

import db

EXCEL = "TOP_SERIES_SIGLOXXI_NUEVA.xlsx"


def anios(valor):
    s = str(valor).strip().lower()
    nums = [int(n) for n in re.findall(r"\d{4}", s)]
    if not nums:
        return None, None, 0
    if "presente" in s:
        return nums[0], None, 1
    if len(nums) == 1:
        return nums[0], nums[0], 0
    return nums[0], nums[1], 0


def temporadas_episodios(valor):
    if pd.isna(valor):
        return None, None
    s = str(valor).upper()
    t = re.search(r"(\d+)\s*TEMPORADA", s)
    e = re.search(r"(\d+)\s*EPISODIO", s)
    return (int(t.group(1)) if t else None), (int(e.group(1)) if e else None)


def limpio(v):
    return None if pd.isna(v) else v


def main():
    if len(db.todas()):
        sys.exit("series.db ya tiene datos; bórrala si quieres migrar de nuevo.")

    df = pd.read_excel(EXCEL, sheet_name="Todas las Series")
    df = df.drop_duplicates(subset="Serie", keep="first")
    n = 0
    for fila in df.to_dict("records"):
        inicio, fin, emision = anios(fila["Fecha al Aire"])
        temps, eps = temporadas_episodios(fila["Temporadas/Episodios"])
        peri = limpio(fila["Peri Rate"])
        rt = limpio(fila["RT%"])
        db.insertar({
            "titulo": str(fila["Serie"]).strip(),
            "estado": "vista" if peri is not None else "pendiente",
            "peri_rate": peri,
            "imdb": limpio(fila["IMDb"]),
            "rt": int(rt) if rt is not None else None,
            "anio_inicio": inicio,
            "anio_fin": fin,
            "en_emision": emision,
            "temporadas": temps,
            "episodios": eps,
        })
        n += 1
    print(f"{n} series migradas a {db.DB_PATH.name}")


if __name__ == "__main__":
    main()
