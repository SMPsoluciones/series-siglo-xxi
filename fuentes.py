"""Datos externos: OMDb (IMDb, años, temporadas, episodios) y Rotten Tomatoes (web)."""
import html
import json
import os
import re
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from datetime import date

import requests

OMDB_URL = "http://www.omdbapi.com/"
RT_BASE = "https://www.rottentomatoes.com"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36"}
TIMEOUT = 15


def omdb_key():
    key = os.environ.get("OMDB_API_KEY")
    if key:
        return key
    try:
        import streamlit as st
        return st.secrets["omdb_api_key"]
    except Exception:
        pass
    # Lectura directa de secrets.toml para scripts fuera de Streamlit
    import tomllib
    from pathlib import Path
    p = Path(__file__).parent / ".streamlit" / "secrets.toml"
    return tomllib.loads(p.read_text(encoding="utf-8"))["omdb_api_key"]


def _num(v, tipo=float):
    if v in (None, "", "N/A"):
        return None
    try:
        return tipo(str(v).replace(",", "").replace("%", "").strip())
    except ValueError:
        return None


def normalizar(t):
    t = unicodedata.normalize("NFKD", str(t)).encode("ascii", "ignore").decode().lower()
    t = t.replace("&", "and")
    t = re.sub(r"^the\s+", "", t)
    return re.sub(r"[^a-z0-9]", "", t)


# ---------------------------------------------------------------- OMDb

class LimiteOMDb(Exception):
    """Se acabó el cupo diario de OMDb (plan gratis: ~1000 consultas por día)."""


def _omdb(**params):
    params["apikey"] = omdb_key()
    r = requests.get(OMDB_URL, params=params, timeout=TIMEOUT)
    if r.status_code == 401:
        raise LimiteOMDb("Se acabó el cupo diario de OMDb; vuelve a intentar mañana.")
    r.raise_for_status()
    data = r.json()
    if data.get("Response") == "False":
        return None
    return data


def buscar_omdb(texto):
    """Lista de candidatos [{imdb_id, titulo, anio, poster}] para el buscador del admin."""
    data = _omdb(s=texto, type="series")
    if not data:
        # A veces la búsqueda falla pero el título exacto sí existe
        d = _omdb(t=texto, type="series")
        return [_candidato(d)] if d else []
    return [_candidato(d) for d in data.get("Search", [])]


def _candidato(d):
    return {
        "imdb_id": d["imdbID"],
        "titulo": d["Title"],
        "anio": d.get("Year", ""),
        "poster": d.get("Poster") if d.get("Poster") not in (None, "N/A") else None,
    }


def _anios(year):
    """'2008–2013' -> (2008, 2013, False); '2022–' -> (2022, None, True); '2019' -> (2019, 2019, False)."""
    partes = [p.strip() for p in str(year).replace("–", "-").split("-")]
    inicio = _num(partes[0], int)
    if len(partes) == 1:
        return inicio, inicio, False
    fin = _num(partes[1], int)
    return inicio, fin, fin is None


def _emitido(fecha, hoy):
    """IMDb pone temporadas anunciadas con episodios sin fecha o con fecha 1900-01-01: esos no cuentan."""
    return bool(fecha) and "1901-01-01" <= fecha <= hoy


def contar_episodios(imdb_id, temporadas):
    """(temporadas ya emitidas, episodios ya emitidos). Ignora temporadas anunciadas que no han salido."""
    if not temporadas:
        return None, None
    hoy = date.today().isoformat()

    def una(n):
        d = _omdb(i=imdb_id, Season=n)
        return sum(_emitido(e.get("Released"), hoy) for e in d.get("Episodes", [])) if d else 0

    with ThreadPoolExecutor(max_workers=6) as ex:
        por_temporada = list(ex.map(una, range(1, temporadas + 1)))
    emitidas = sum(1 for n in por_temporada if n)
    return (emitidas or None), (sum(por_temporada) or None)


def detalle_omdb(imdb_id, con_episodios=True):
    d = _omdb(i=imdb_id, plot="short")
    if not d:
        return None
    inicio, fin, en_emision = _anios(d.get("Year", ""))
    temporadas = _num(d.get("totalSeasons"), int)
    datos = {
        "imdb_id": d["imdbID"],
        "titulo": d["Title"],
        "imdb": _num(d.get("imdbRating")),
        "imdb_votos": _num(d.get("imdbVotes"), int),
        "anio_inicio": inicio,
        "anio_fin": fin,
        "en_emision": int(en_emision),
        "temporadas": temporadas,
        "generos": d.get("Genre") if d.get("Genre") != "N/A" else None,
        "sinopsis": d.get("Plot") if d.get("Plot") != "N/A" else None,
        "poster": d.get("Poster") if d.get("Poster") != "N/A" else None,
    }
    if con_episodios:
        emitidas, episodios = contar_episodios(imdb_id, temporadas)
        datos["temporadas"] = emitidas or temporadas
        datos["episodios"] = episodios
    return datos


# ---------------------------------------------------------- Rotten Tomatoes

_FILA = re.compile(r"<search-page-media-row(?P<attrs>[^>]*)>(?P<body>.*?)</search-page-media-row>", re.S)


def _attr(attrs, nombre):
    m = re.search(rf'{nombre}="([^"]*)"', attrs)
    return m.group(1) if m else ""


def buscar_rt(titulo):
    """Series de TV en el buscador de RT: [{titulo, url, inicio, fin, rt}]."""
    r = requests.get(f"{RT_BASE}/search", params={"search": titulo}, headers=HEADERS, timeout=TIMEOUT)
    r.raise_for_status()
    seccion = re.search(r'type="tvSeries"\s*>(.*?)</search-page-result>', r.text, re.S)
    if not seccion:
        return []
    out = []
    for m in _FILA.finditer(seccion.group(1)):
        body = m.group("body")
        link = re.search(r'href="([^"]+)"[^>]*data-qa="info-name"[^>]*>\s*(.*?)\s*</a>', body, re.S)
        if not link:
            continue
        out.append({
            "titulo": html.unescape(link.group(2).strip()),
            "url": link.group(1),
            "inicio": _num(_attr(m.group("attrs"), "startyear"), int),
            "fin": _num(_attr(m.group("attrs"), "endyear"), int),
            "rt": _num(_attr(m.group("attrs"), "tomatometerscore"), int),
        })
    return out


def emparejar_rt(titulo, anio_inicio=None):
    """Elige el resultado de RT que coincide por título (y año de estreno si lo tenemos)."""
    candidatos = buscar_rt(titulo)
    objetivo = normalizar(titulo)
    mismos = [c for c in candidatos if normalizar(c["titulo"]) == objetivo]
    if anio_inicio:
        por_anio = [c for c in mismos if c["inicio"] and abs(c["inicio"] - anio_inicio) <= 3]
        if por_anio:
            return min(por_anio, key=lambda c: abs(c["inicio"] - anio_inicio))
        if len(mismos) == 1:  # un único resultado con el mismo título
            return mismos[0]
        # Sin título exacto: aceptar uno cuyo año coincida y el título se parezca
        parecidos = [c for c in candidatos
                     if c["inicio"] and abs(c["inicio"] - anio_inicio) <= 1
                     and (objetivo in normalizar(c["titulo"]) or normalizar(c["titulo"]) in objetivo)]
        if parecidos:
            return parecidos[0]
        return None
    return mismos[0] if mismos else None


def scores_rt(url):
    """Tomatometer y Popcornmeter desde la página de la serie."""
    r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    r.raise_for_status()
    m = re.search(r'id="media-scorecard-json"[^>]*>\s*(\{.*?\})\s*</script>', r.text, re.S)
    if not m:
        return {}
    data = json.loads(m.group(1))
    return {
        "rt": _num((data.get("criticsScore") or {}).get("scorePercent"), int),
        "rt_audiencia": _num((data.get("audienceScore") or {}).get("scorePercent"), int),
    }


def datos_rt(titulo, anio_inicio=None, rt_url=None):
    try:
        if not rt_url:
            match = emparejar_rt(titulo, anio_inicio)
            if not match:
                return {}
            rt_url = match["url"]
        return {"rt_url": rt_url, **scores_rt(rt_url)}
    except requests.RequestException:
        return {}


# ------------------------------------------------------------ Todo junto

def ficha_completa(imdb_id, rt_url=None, con_episodios=True):
    """Datos de OMDb + RT listos para guardar en la base."""
    datos = detalle_omdb(imdb_id, con_episodios=con_episodios)
    if not datos:
        return None
    datos.update(datos_rt(datos["titulo"], datos["anio_inicio"], rt_url))
    return datos
