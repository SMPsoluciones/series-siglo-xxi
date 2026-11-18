"""Vincular series con IMDb y refrescar sus scores (lo usa la app y el script programado).

Uso por consola:
    python sincronizar.py              # vincula las que faltan y actualiza todas
    python sincronizar.py --solo-vincular
    python sincronizar.py --limite 50
"""
import argparse
import re
import time
from difflib import SequenceMatcher

import db
import fuentes


# Series que guardas con otro nombre (en español u original) -> como aparecen en IMDb
ALIAS = {
    "Dr. House": "House",
    "Casa de Papel": "Money Heist",
    "Les Revenants (The Returned)": "The Returned",
    "Shingeki no Kyojin: Attack on Titan": "Attack on Titan",
    "The Honourable Woman": "The Honorable Woman",
    "The End of the Fucking World": "The End of the F***ing World",
    "Unsolved: Tupac and Biggie": "Unsolved: The Murders of Tupac and the Notorious B.I.G.",
    "American Family: Journey of Dreams": "American Family",
    "Mr and Mrs Smith": "Mr. & Mrs. Smith",
}


def _omdb_por_titulo(titulo, anio):
    """Busca el IMDb ID usando título + año de estreno para no agarrar otra serie con el mismo nombre."""
    variantes = [titulo]
    if titulo in ALIAS:
        variantes.insert(0, ALIAS[titulo])
    if " and " in titulo.lower():
        variantes.append(re.sub(r"\s+and\s+", " & ", titulo, flags=re.I))
    for t in variantes:
        encontrado = _omdb_una_variante(t, anio)
        if encontrado:
            return encontrado
    return None


def _parecido(a, b):
    """OMDb a veces devuelve otra serie que solo contiene el título (p. ej. 'CSI SFP: Law and Order')."""
    return SequenceMatcher(None, fuentes.normalizar(a), fuentes.normalizar(b)).ratio() >= 0.85


def _omdb_una_variante(titulo, anio):
    if anio:
        d = fuentes._omdb(t=titulo, y=anio, type="series")
        if d and _parecido(d["Title"], titulo):
            return d["imdbID"]
    d = fuentes._omdb(t=titulo, type="series")
    if d and _parecido(d["Title"], titulo):
        inicio, _, _ = fuentes._anios(d.get("Year", ""))
        if not anio or (inicio and abs(inicio - anio) <= 1):
            return d["imdbID"]
    res = fuentes._omdb(s=titulo, type="series")
    for c in (res or {}).get("Search", []):
        inicio, _, _ = fuentes._anios(c.get("Year", ""))
        if (anio and inicio and abs(inicio - anio) <= 1
                and fuentes.normalizar(c["Title"]) == fuentes.normalizar(titulo)):
            return c["imdbID"]
    return None


def refrescar(serie, vincular=True):
    """Actualiza una serie de la base. Devuelve (estado, mensaje)."""
    imdb_id = serie.get("imdb_id")
    if not imdb_id:
        if not vincular:
            return "sin_vincular", "Sin IMDb ID"
        imdb_id = _omdb_por_titulo(serie["titulo"], serie.get("anio_inicio"))
        if not imdb_id:
            return "no_encontrada", "No se encontró en IMDb"
        otra = db.buscar_por_imdb(imdb_id)
        if otra and otra["id"] != serie["id"]:
            return "duplicada", f"Ese IMDb ID ya es de «{otra['titulo']}»"

    # Contar episodios cuesta 1 llamada por temporada: solo si cambió algo o falta el dato
    base = fuentes.detalle_omdb(imdb_id, con_episodios=False)
    if not base:
        return "error", "OMDb no respondió"
    if (not serie.get("episodios") or serie.get("en_emision") or base["en_emision"]
            or base["temporadas"] != serie.get("temporadas")):
        emitidas, episodios = fuentes.contar_episodios(imdb_id, base["temporadas"])
        base["temporadas"] = emitidas or base["temporadas"]
        base["episodios"] = episodios or serie.get("episodios")
    else:
        base["temporadas"] = serie.get("temporadas")  # no se recontó: conservar las ya emitidas

    rt = fuentes.datos_rt(base["titulo"], base["anio_inicio"], serie.get("rt_url"))
    if not rt and fuentes.normalizar(serie["titulo"]) != fuentes.normalizar(base["titulo"]):
        rt = fuentes.datos_rt(serie["titulo"], base["anio_inicio"])  # RT a veces usa tu nombre, no el de IMDb
    base.update(rt)
    # Conservar lo que ya tenemos si la fuente no trae el dato
    nuevos = {k: v for k, v in base.items() if v is not None}
    nuevos["titulo"] = serie["titulo"]  # siempre se respeta el nombre que tú le pusiste
    nuevos["actualizado_en"] = db.ahora()
    db.actualizar(serie["id"], nuevos)

    cambios = []
    if serie.get("imdb") != nuevos.get("imdb", serie.get("imdb")):
        cambios.append(f"IMDb {serie.get('imdb')} → {nuevos['imdb']}")
    if serie.get("rt") != nuevos.get("rt", serie.get("rt")):
        cambios.append(f"RT {serie.get('rt')} → {nuevos['rt']}")
    if "rt" not in base:
        cambios.append("RT no encontrado")
    return "ok", ", ".join(cambios) or "Sin cambios"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--solo-vincular", action="store_true", help="Solo las que no tienen IMDb ID")
    ap.add_argument("--limite", type=int, default=None)
    args = ap.parse_args()

    df = db.todas()
    if args.solo_vincular:
        df = df[df["imdb_id"].isna()]
    df = df.sort_values("actualizado_en", na_position="first")
    if args.limite:
        df = df.head(args.limite)

    resumen = {}
    for i, serie in enumerate(df.to_dict("records"), 1):
        serie = {k: (None if v != v else v) for k, v in serie.items()}  # NaN -> None
        try:
            estado, msg = refrescar(serie)
        except fuentes.LimiteOMDb as e:
            print(f"⛔ {e} Quedaron {len(df) - i + 1} series sin revisar.")
            break
        except Exception as e:  # una serie con problemas no frena el resto
            estado, msg = "error", str(e)
        resumen[estado] = resumen.get(estado, 0) + 1
        print(f"[{i}/{len(df)}] {serie['titulo']}: {estado} — {msg}", flush=True)
        time.sleep(0.3)
    print("Resumen:", resumen)


if __name__ == "__main__":
    main()
