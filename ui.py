"""Piezas visuales compartidas: estilos, tarjetas, ficha de serie y cálculos."""
import html
import re

import pandas as pd
import plotly.express as px
import streamlit as st

import db

NARANJA = "#ff8c00"
AMARILLO_IMDB = "#f5c518"
ROJO_RT = "#fa4a2a"
SIN_POSTER = ("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 200 300'>"
              "<rect width='200' height='300' fill='%23171513'/><text x='100' y='156' font-size='15' "
              "text-anchor='middle' fill='%236b645c' font-family='sans-serif' letter-spacing='3'>SIN PÓSTER</text></svg>")
ICONO_ESTADO = {"vista": "✅", "viendo": "▶️", "pendiente": "⏳", "abandonada": "🛑"}


# ------------------------------------------------------------------ datos

@st.cache_data(ttl=600, show_spinner=False)
def _todas():
    return db.todas()


def cargar():
    df = _todas().copy()
    df["decada"] = (df["anio_inicio"] // 10 * 10).astype("Int64").astype(str).str.replace("<NA>", "—") + "s"
    df["score_critica"] = df[["imdb"]].assign(rt10=df["rt"] / 10).mean(axis=1, skipna=True)
    return df


def anios_txt(s):
    ini, fin = s.get("anio_inicio"), s.get("anio_fin")
    if pd.isna(ini):
        return "—"
    ini = int(ini)
    if s.get("en_emision"):
        return f"{ini} – presente"
    if pd.isna(fin) or int(fin) == ini:
        return str(ini)
    return f"{ini} – {int(fin)}"


def temps_txt(s):
    t, e = s.get("temporadas"), s.get("episodios")
    partes = []
    if pd.notna(t):
        partes.append(f"{int(t)} temporada" + ("s" if int(t) != 1 else ""))
    if pd.notna(e):
        partes.append(f"{int(e)} episodios")
    return " · ".join(partes) or "—"


def afinidad(df):
    """Score de pendientes ajustado por tus gustos: cuánto más (o menos) que IMDb le pones a cada género."""
    vistas = df[(df["estado"] == "vista") & df["peri_rate"].notna() & df["imdb"].notna() & df["generos"].notna()]
    delta = {}
    for _, s in vistas.iterrows():
        for g in s["generos"].split(","):
            delta.setdefault(g.strip(), []).append(s["peri_rate"] - s["imdb"])
    delta = {g: sum(v) / len(v) for g, v in delta.items() if len(v) >= 3}

    def score(s):
        base = s["score_critica"]
        if pd.isna(base):
            return None
        if not isinstance(s["generos"], str):
            return round(base, 2)
        ajustes = [delta[g.strip()] for g in s["generos"].split(",") if g.strip() in delta]
        return round(base + (sum(ajustes) / len(ajustes) if ajustes else 0) * 0.5, 2)

    return df.apply(score, axis=1), delta


def poster(url, ancho=400):
    """URL del póster al ancho pedido (los de IMDb se pueden pedir en cualquier tamaño)."""
    if not isinstance(url, str) or not url:
        return SIN_POSTER
    if "media-amazon.com" in url and "._V1_" in url:
        return re.sub(r"\._V1_.*$", f"._V1_UX{ancho}_.jpg", url)
    return url


def _e(texto):
    return html.escape(str(texto))


# ----------------------------------------------------------------- estilos

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,300..700;1,9..144,300..700&family=Inter:wght@400;500;600;700&display=swap');

:root {
  --bg:#0b0a09; --surface:#141210; --surface2:#1c1917; --line:rgba(255,255,255,.085);
  --text:#f4efe8; --soft:#cfc7bc; --muted:#8f877d; --accent:#ff8c00; --accent2:#ffb357;
  --serif:'Fraunces', Georgia, 'Times New Roman', serif;
  --sans:'Inter', -apple-system, 'Segoe UI', Roboto, sans-serif;
}

/* ---------- base ---------- */
.stApp {background: radial-gradient(1100px 520px at 50% -180px, rgba(255,140,0,.11), transparent 65%), var(--bg);}
.stApp, .stApp p, .stApp label, .stApp input, .stApp textarea, .stApp button, .stApp li {font-family:var(--sans);}
[data-testid="stMarkdownContainer"], [data-testid="stCaptionContainer"] {font-family:var(--sans);}
[data-testid="stMainBlockContainer"] {max-width:1180px; padding:5.2rem 1.5rem 5rem; position:relative; z-index:0;}
[data-testid="stHeaderActionElements"], [data-testid="stMainMenu"], [data-testid="stToolbarActions"] {display:none !important;}
.stApp h1, .stApp h2, .stApp h3 {font-family:var(--serif); font-weight:500; letter-spacing:-.015em;}
::selection {background:rgba(255,140,0,.35);}

/* ---------- barra superior ---------- */
[data-testid="stHeader"] {background:rgba(11,10,9,.74); backdrop-filter:blur(16px) saturate(1.3);
  -webkit-backdrop-filter:blur(16px) saturate(1.3); border-bottom:1px solid var(--line);}
[data-testid="stTopNavLink"] {border-radius:0 !important; background:transparent !important; padding:.55rem .15rem !important;
  margin:0 .7rem; border-bottom:2px solid transparent; transition:color .15s, border-color .15s;}
[data-testid="stTopNavLink"] span {font-family:var(--sans); font-size:.76rem; font-weight:600; letter-spacing:.13em;
  text-transform:uppercase; color:var(--muted); transition:color .15s;}
[data-testid="stTopNavLink"]:hover span {color:var(--text);}
[data-testid="stTopNavLink"][aria-current="page"] {border-bottom-color:var(--accent);}
[data-testid="stTopNavLink"][aria-current="page"] span {color:var(--text);}

/* ---------- botones y formularios ---------- */
[data-testid="stBaseButton-primary"], [data-testid="stBaseButton-primaryFormSubmit"] {
  background:linear-gradient(180deg,#ffa234,#ff7f00) !important; border:0 !important; color:#1a0f00 !important;
  border-radius:999px !important; padding:.62rem 1.5rem !important;
  box-shadow:0 8px 26px -8px rgba(255,140,0,.6), inset 0 1px 0 rgba(255,255,255,.35); transition:transform .15s, box-shadow .15s;}
[data-testid="stBaseButton-primary"] p, [data-testid="stBaseButton-primaryFormSubmit"] p {font-weight:650; color:#1a0f00 !important;}
[data-testid="stBaseButton-primary"]:hover, [data-testid="stBaseButton-primaryFormSubmit"]:hover {
  transform:translateY(-1px); box-shadow:0 12px 32px -8px rgba(255,140,0,.75), inset 0 1px 0 rgba(255,255,255,.35);}
[data-testid="stBaseButton-secondary"] {border-radius:999px !important; border:1px solid var(--line) !important;
  background:transparent !important; transition:border-color .15s, background .15s;}
[data-testid="stBaseButton-secondary"]:hover {border-color:rgba(255,140,0,.6) !important; background:rgba(255,140,0,.06) !important;}
[data-testid="stForm"] {border:1px solid var(--line); border-radius:22px; background:var(--surface); padding:1.7rem 1.7rem 1.4rem;}
[data-testid="stMetric"] {background:var(--surface); border:1px solid var(--line); border-radius:16px; padding:12px 16px;}
[data-testid="stMetricValue"] {font-family:var(--serif); color:var(--accent2);}

/* ---------- encabezado de página ---------- */
.eyebrow {font:600 .7rem/1 var(--sans); letter-spacing:.26em; text-transform:uppercase; color:var(--accent2);}
.cab {margin:1.2rem 0 2rem;}
.cab .tit {font-family:var(--serif); font-weight:500; font-size:clamp(2.2rem,5vw,3.6rem); line-height:1.02;
  letter-spacing:-.025em; margin:.7rem 0 .6rem; color:var(--text);}
.cab .tit em {font-style:italic; font-weight:400; color:var(--accent);}
.cab .baj {color:var(--soft); font-size:1.05rem; max-width:40rem; line-height:1.55; margin:0;}

/* ---------- portada ---------- */
.wall {position:fixed; inset:0; z-index:-1; overflow:hidden; pointer-events:none;}
.wall .rows {position:absolute; inset:-25% -15%; transform:rotate(-7deg); display:flex; flex-direction:column;
  gap:14px; justify-content:center; opacity:.55;}
.wall .row {display:flex; gap:14px; width:max-content; animation:deriva 120s linear infinite;}
.wall .row:nth-child(even) {animation-direction:reverse; animation-duration:150s;}
.wall img {width:148px; aspect-ratio:2/3; object-fit:cover; border-radius:10px; display:block;}
.wall::after {content:""; position:absolute; inset:0;
  background:radial-gradient(ellipse 75% 62% at 50% 38%, rgba(11,10,9,.80) 0%, rgba(11,10,9,.90) 48%, var(--bg) 82%);}
@keyframes deriva {from {transform:translateX(0);} to {transform:translateX(-50%);}}
@media (prefers-reduced-motion: reduce) {.wall .row {animation:none;}}

.hero {text-align:center; padding:8vh 0 1.2rem;}
.hero .tit {font-family:var(--serif); font-weight:500; font-size:clamp(3.1rem,10vw,7rem); line-height:.93;
  letter-spacing:-.035em; margin:1.3rem 0 1.4rem; color:var(--text); text-wrap:balance;}
.hero .tit em {font-style:italic; font-weight:400; color:var(--accent);}
.hero .baj {color:var(--soft); font-size:clamp(1rem,2.2vw,1.2rem); max-width:33rem; margin:0 auto; line-height:1.55; text-wrap:balance;}
.cifras {display:flex; justify-content:center; margin:2.3rem 0 .6rem;}
.cifras div {padding:0 clamp(1rem,3.5vw,2.4rem); border-left:1px solid var(--line);}
.cifras div:first-child {border-left:0;}
.cifras b {display:block; font-family:var(--serif); font-weight:500; font-size:clamp(1.7rem,4vw,2.5rem); line-height:1; color:var(--text);}
.cifras small {display:block; margin-top:.55rem; font-size:.66rem; font-weight:600; letter-spacing:.2em; text-transform:uppercase; color:var(--muted);}

.st-key-dado {align-items:center; margin:1.1rem 0 .4rem;}
.st-key-dado [data-testid="stBaseButton-primary"] {padding:.8rem 2.1rem !important;}
.st-key-dado [data-testid="stBaseButton-primary"] p {font-size:1.02rem;}

.pick {position:relative; overflow:hidden; display:grid; grid-template-columns:132px 1fr; gap:22px; align-items:center;
  max-width:680px; margin:1rem auto 0; padding:18px; border:1px solid rgba(255,140,0,.35); border-radius:22px;
  background:rgba(20,18,16,.82); backdrop-filter:blur(8px); animation:aparece .45s cubic-bezier(.2,.8,.2,1);}
.pick::before {content:""; position:absolute; inset:-30%; background:var(--p) center/cover; filter:blur(46px) saturate(1.3); opacity:.3;}
.pick > * {position:relative;}
.pick img {width:132px; aspect-ratio:2/3; object-fit:cover; border-radius:12px; box-shadow:0 18px 40px -14px #000;}
.pick .pt {font-family:var(--serif); font-size:1.75rem; font-weight:500; line-height:1.1; margin:.5rem 0 .45rem; color:var(--text);}
.pick .pm {color:var(--muted); font-size:.86rem;}
.pick .ps {color:var(--soft); font-size:.92rem; line-height:1.5; margin:.7rem 0 0;
  display:-webkit-box; -webkit-line-clamp:3; -webkit-box-orient:vertical; overflow:hidden;}
.pick .pn {display:flex; align-items:baseline; gap:.9rem; margin-top:.7rem; font-size:.86rem; color:var(--soft);}
.pick .pn b {font-family:var(--serif); font-size:1.9rem; font-weight:500; color:var(--accent); line-height:1;}
@keyframes aparece {from {opacity:0; transform:translateY(10px) scale(.985);} to {opacity:1; transform:none;}}

.st-key-accesos {display:grid !important; grid-template-columns:repeat(3,minmax(0,1fr)); gap:14px !important; margin-top:2.6rem;}
[class*="st-key-acc_"], [class*="st-key-acc_"] [data-testid="stElementContainer"], [class*="st-key-acc_"] [data-testid="stPageLink"],
[class*="st-key-acc_"] [data-testid="stPageLink"] > div {width:100% !important; min-width:0;}
[class*="st-key-acc_"] [data-testid="stPageLink"] {line-height:0;}
[class*="st-key-acc_"] {gap:0 !important; height:148px;}
@media (max-width: 1000px) {.st-key-accesos {grid-template-columns:repeat(2,minmax(0,1fr));}}
[class*="st-key-acc_"] [data-testid="stPageLink-NavLink"] {position:relative; display:flex; flex-direction:column;
  align-items:flex-start; justify-content:flex-end; gap:.25rem; height:148px; padding:18px 20px; border-radius:18px;
  border:1px solid var(--line); background-color:var(--surface); background-repeat:no-repeat; overflow:hidden;
  transition:transform .2s cubic-bezier(.2,.8,.2,1), border-color .2s, box-shadow .2s;}
[class*="st-key-acc_"] [data-testid="stPageLink-NavLink"]:hover {transform:translateY(-3px); border-color:rgba(255,140,0,.55);
  box-shadow:0 20px 44px -22px rgba(255,140,0,.45);}
[class*="st-key-acc_"] [data-testid="stPageLink-NavLink"] p {font-family:var(--serif); font-size:1.42rem; font-weight:500;
  letter-spacing:-.01em; color:var(--text); line-height:1.1;}
[class*="st-key-acc_"] [data-testid="stPageLink-NavLink"]::after {font:500 .8rem/1.35 var(--sans); color:var(--muted); max-width:62%;}
.pie {text-align:center; color:var(--muted); font-size:.74rem; letter-spacing:.06em; margin-top:3.2rem;}

/* ---------- grilla de pósters ---------- */
[class*="st-key-grid_"] {display:grid !important; grid-template-columns:repeat(auto-fill,minmax(160px,1fr)); gap:30px 20px;}
[class*="st-key-card_"] {position:relative; gap:0 !important; min-width:0;}
[class*="st-key-card_"] > [data-testid="stElementContainer"]:has(.stButton),
[class*="st-key-fila_"] > [data-testid="stElementContainer"]:has(.stButton),
[class*="st-key-pod_"] > [data-testid="stElementContainer"]:has(.stButton) {position:absolute; inset:0; z-index:2; width:100%; height:100%;}
[class*="st-key-card_"] .stButton, [class*="st-key-fila_"] .stButton, [class*="st-key-pod_"] .stButton {height:100%;}
[class*="st-key-card_"] .stButton button, [class*="st-key-fila_"] .stButton button, [class*="st-key-pod_"] .stButton button {
  width:100%; height:100%; min-height:0; opacity:0; cursor:pointer; border-radius:14px !important;}
[class*="st-key-card_"] .stButton button:focus-visible, [class*="st-key-fila_"] .stButton button:focus-visible,
[class*="st-key-pod_"] .stButton button:focus-visible {opacity:1; background:transparent !important; color:transparent !important;
  outline:2px solid var(--accent); outline-offset:3px;}
[class*="st-key-card_"] .stButton button:focus-visible p {color:transparent;}

.card .ph {position:relative; border-radius:14px; overflow:hidden; background:var(--surface); aspect-ratio:2/3;
  box-shadow:0 0 0 1px var(--line); transition:transform .25s cubic-bezier(.2,.8,.2,1), box-shadow .25s;}
.card .ph img {width:100%; height:100%; object-fit:cover; display:block; transition:transform .5s cubic-bezier(.2,.8,.2,1);}
[class*="st-key-card_"]:hover .ph {transform:translateY(-5px); box-shadow:0 0 0 1px rgba(255,140,0,.6), 0 24px 44px -20px rgba(0,0,0,.9), 0 18px 46px -26px rgba(255,140,0,.6);}
[class*="st-key-card_"]:hover .ph img {transform:scale(1.045);}
.card .nota {position:absolute; top:9px; left:9px; padding:.2rem .55rem .24rem; border-radius:999px;
  background:rgba(11,10,9,.78); backdrop-filter:blur(8px); border:1px solid rgba(255,140,0,.55);
  font-family:var(--serif); font-weight:600; font-size:1rem; line-height:1; color:var(--accent2);}
.card .t {margin-top:.75rem; font-weight:600; font-size:.93rem; line-height:1.3; color:var(--text);
  display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; overflow:hidden;}
.card .m {margin-top:.25rem; font-size:.78rem; color:var(--muted); white-space:nowrap; overflow:hidden; text-overflow:ellipsis;}
.card .m i {font-style:normal; color:var(--soft);}

/* ---------- medidores ---------- */
.med {display:grid; grid-template-columns:auto 1fr auto; align-items:center; gap:10px; margin:5px 0; font-size:.8rem;}
.med .l {color:var(--muted); min-width:3.1rem; font-weight:500;}
.med .b {height:4px; border-radius:4px; background:rgba(255,255,255,.09); overflow:hidden;}
.med .b i {display:block; height:100%; border-radius:4px;}
.med .v {color:var(--text); font-weight:600; min-width:2.6rem; text-align:right; font-variant-numeric:tabular-nums;}

/* ---------- top 50 ---------- */
.st-key-podio {display:grid !important; grid-template-columns:repeat(3,minmax(0,1fr)); gap:22px; margin-bottom:2.2rem;}
[class*="st-key-pod_"] {position:relative; gap:0 !important; min-width:0;}
.pod .ph {position:relative; border-radius:18px; overflow:hidden; aspect-ratio:2/3; box-shadow:0 0 0 1px var(--line);
  transition:transform .25s cubic-bezier(.2,.8,.2,1), box-shadow .25s;}
.pod .ph img {width:100%; height:100%; object-fit:cover; display:block;}
.pod .ph::after {content:""; position:absolute; inset:42% 0 0; background:linear-gradient(180deg,transparent,rgba(11,10,9,.78) 58%,rgba(11,10,9,.97));}
[class*="st-key-pod_"]:hover .ph {transform:translateY(-5px); box-shadow:0 0 0 1px rgba(255,140,0,.6), 0 30px 60px -28px rgba(255,140,0,.55);}
.pod .num {position:absolute; left:16px; bottom:2px; z-index:1; font-family:var(--serif); font-weight:500; font-style:italic;
  font-size:clamp(3.6rem,9vw,6.4rem); line-height:1; color:var(--text); text-shadow:0 6px 30px rgba(0,0,0,.6);}
.pod .sc {position:absolute; right:16px; bottom:18px; z-index:1; text-align:right;}
.pod .sc b {display:block; font-family:var(--serif); font-size:clamp(1.6rem,4vw,2.4rem); font-weight:500; color:var(--accent); line-height:1;}
.pod .sc small {font-size:.6rem; letter-spacing:.2em; text-transform:uppercase; color:var(--soft); font-weight:600;}
.pod .t {margin-top:.9rem; font-family:var(--serif); font-size:clamp(1.05rem,2.4vw,1.4rem); font-weight:500; line-height:1.15; color:var(--text);}
.pod .m {margin-top:.3rem; font-size:.8rem; color:var(--muted);}

.st-key-lista {gap:0 !important;}
[class*="st-key-fila_"] {position:relative; gap:0 !important;}
.fila {display:grid; grid-template-columns:3.4rem 50px minmax(0,1fr) 200px 4.6rem; align-items:center; gap:18px;
  padding:12px 14px; border-top:1px solid var(--line); border-radius:0; transition:background .15s;}
[class*="st-key-fila_"]:hover .fila {background:rgba(255,140,0,.055);}
.fila .n {font-family:var(--serif); font-style:italic; font-size:1.7rem; font-weight:400; color:var(--muted); text-align:center; line-height:1;}
.fila img {width:50px; height:75px; object-fit:cover; border-radius:7px; display:block; box-shadow:0 0 0 1px var(--line);}
.fila .ft {font-weight:600; font-size:1.04rem; color:var(--text); line-height:1.25; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;}
.fila .fm {font-size:.8rem; color:var(--muted); margin-top:.2rem; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;}
.fila .nota {font-family:var(--serif); font-size:1.85rem; font-weight:500; color:var(--accent); text-align:right; line-height:1;
  font-variant-numeric:tabular-nums;}
.leyenda {display:flex; flex-wrap:wrap; gap:.4rem 1.4rem; color:var(--muted); font-size:.8rem; margin:.2rem 0 1.4rem;}
.leyenda span::before {content:""; display:inline-block; width:9px; height:9px; border-radius:50%; background:var(--c); margin-right:.45rem;}

/* ---------- ficha ---------- */
div[role="dialog"] {background:var(--surface) !important; border:1px solid var(--line); border-radius:24px !important; overflow:hidden;}
.ficha {position:relative; display:grid; grid-template-columns:230px minmax(0,1fr); gap:30px; align-items:start;}
.ficha::before {content:""; position:absolute; inset:-120px -80px auto; height:340px; background:var(--p) center/cover;
  filter:blur(60px) saturate(1.3); opacity:.28; pointer-events:none;}
.ficha > * {position:relative;}
.ficha .fp {width:100%; aspect-ratio:2/3; object-fit:cover; border-radius:14px; box-shadow:0 26px 54px -22px #000, 0 0 0 1px var(--line);}
.ficha .tt {font-family:var(--serif); font-weight:500; font-size:clamp(1.8rem,4vw,2.5rem); line-height:1.05; letter-spacing:-.02em;
  margin:.65rem 0 .8rem; color:var(--text);}
.ficha .gen {display:flex; flex-wrap:wrap; gap:6px; margin-bottom:1.3rem;}
.ficha .gen span {font-size:.74rem; padding:.28rem .7rem; border-radius:999px; border:1px solid var(--line); color:var(--soft);}
.ficha .sco {display:grid; grid-template-columns:auto minmax(0,1fr); gap:26px; align-items:center; padding:1rem 0;
  border-top:1px solid var(--line); border-bottom:1px solid var(--line);}
.ficha .pr b {display:block; font-family:var(--serif); font-size:3.4rem; font-weight:500; line-height:.9; color:var(--accent);}
.ficha .pr small {display:block; margin-top:.5rem; font-size:.62rem; font-weight:600; letter-spacing:.2em; text-transform:uppercase; color:var(--muted);}
.ficha .pr.pend b {font-size:1.5rem; color:var(--soft); font-style:italic; line-height:1.1;}
.ficha .sin {color:var(--soft); line-height:1.6; font-size:.95rem; margin:1.1rem 0 0;}
.ficha .lk {display:flex; flex-wrap:wrap; gap:8px; margin-top:1.2rem;}
.ficha .lk a {font-size:.8rem; font-weight:600; color:var(--text); text-decoration:none; padding:.45rem .95rem; border-radius:999px;
  border:1px solid var(--line); transition:border-color .15s, color .15s;}
.ficha .lk a:hover {border-color:var(--accent); color:var(--accent2);}

/* ---------- listas del análisis ---------- */
.mini {border:1px solid var(--line); border-radius:18px; background:var(--surface); padding:1.1rem 1.2rem .6rem; height:100%;}
.mini h4 {font-family:var(--serif); font-weight:500; font-size:1.25rem; margin:0 0 .15rem; padding:0; color:var(--text);}
.mini .d {color:var(--muted); font-size:.8rem; margin-bottom:.7rem;}
.mini .r {display:grid; grid-template-columns:minmax(0,1fr) auto auto; gap:12px; align-items:baseline; padding:.5rem 0; border-top:1px solid var(--line); font-size:.9rem;}
.mini .r span:first-child {white-space:nowrap; overflow:hidden; text-overflow:ellipsis; color:var(--text);}
.mini .r b {font-family:var(--serif); font-weight:500; font-size:1.05rem; color:var(--accent);}
.mini .r i {font-style:normal; color:var(--muted); font-size:.8rem; font-variant-numeric:tabular-nums; min-width:3.4rem; text-align:right;}

.st-key-angosto {max-width:600px; margin:0 auto;}
.st-key-mas {align-items:center; margin-top:2rem;}

/* ---------- celular ---------- */
@media (max-width: 760px) {
  [data-testid="stMainBlockContainer"] {padding:4.6rem 1rem 4rem;}
  .st-key-accesos {grid-template-columns:repeat(2,minmax(0,1fr)); gap:10px;}
  [class*="st-key-acc_"] {height:118px;}
  [class*="st-key-acc_"] [data-testid="stPageLink-NavLink"] {height:118px; padding:14px; background-image:none !important;}
  [class*="st-key-acc_"] [data-testid="stPageLink-NavLink"] p {font-size:1.15rem;}
  [class*="st-key-acc_"] [data-testid="stPageLink-NavLink"]::after {max-width:100%; font-size:.74rem;}
  [class*="st-key-grid_"] {grid-template-columns:repeat(auto-fill,minmax(104px,1fr)); gap:20px 12px;}
  .card .t {font-size:.84rem;} .card .m {font-size:.72rem;}
  .st-key-podio {gap:10px;}
  .pod .num {left:9px;} .pod .sc {right:9px; bottom:10px;} .pod .sc small {display:none;}
  .fila {grid-template-columns:2rem 42px minmax(0,1fr) 3.4rem; gap:12px; padding:10px 4px;}
  .fila .crit {display:none;} .fila .n {font-size:1.25rem;} .fila img {width:42px; height:63px;} .fila .nota {font-size:1.5rem;}
  .ficha {grid-template-columns:1fr; gap:18px;} .ficha .fp {max-width:170px;}
  .pick {grid-template-columns:92px 1fr; gap:14px; padding:14px;} .pick img {width:92px;} .pick .pt {font-size:1.3rem;}
  .wall img {width:104px;}
}
/* ---------- Series XXI ---------- */
[data-testid="stLogo"] {height:2rem !important; max-width:none;}
.card .nota small {font:600 .52rem/1 var(--sans); letter-spacing:.14em; text-transform:uppercase; color:var(--muted); margin-right:.32rem; vertical-align:2px;}
.card .nota.pv {border-color:rgba(255,255,255,.18); color:var(--soft); font:600 .62rem/1 var(--sans); letter-spacing:.14em;
  text-transform:uppercase; padding:.36rem .6rem;}

.st-key-accesos {grid-template-columns:repeat(6,minmax(0,1fr)) !important;}
.st-key-accesos > * {grid-column:span 2;}
.st-key-accesos > :has(.st-key-acc_ultimo), .st-key-accesos > :has(.st-key-acc_sumar) {grid-column:span 3;}

.st-key-decadas [data-testid="stButtonGroup"] {gap:10px;}
.st-key-decadas button {border-radius:16px !important; padding:.85rem 1.4rem !important; min-height:0 !important;
  border:1px solid var(--line) !important; background:var(--surface) !important; transition:all .15s;}
.st-key-decadas button p {font-family:var(--serif) !important; font-size:1.35rem !important; font-weight:500 !important;}
.st-key-decadas button:hover {border-color:rgba(255,140,0,.55) !important;}
.st-key-decadas button[kind="pillsActive"], .st-key-decadas button[data-testid="stBaseButton-pillsActive"] {
  background:linear-gradient(180deg,#ffa234,#ff7f00) !important; border-color:transparent !important;}
.st-key-decadas button[data-testid="stBaseButton-pillsActive"] p {color:#1a0f00 !important;}
.st-key-anios {margin:-.2rem 0 .6rem;}
.st-key-anios button {border-radius:999px !important; background:transparent !important;}
.st-key-anios button[data-testid="stBaseButton-pillsActive"] {background:rgba(255,140,0,.16) !important; border-color:rgba(255,140,0,.6) !important;}

.conteo {display:flex; align-items:center; flex-wrap:wrap; gap:.6rem; margin:.6rem 0 1.4rem; color:var(--soft); font-size:.9rem;}
.conteo b {font-family:var(--serif); font-size:1.5rem; font-weight:500; color:var(--text);}
.conteo .sep {width:1px; height:1.1rem; background:var(--line); margin:0 .3rem;}
.conteo .tag {font-size:.72rem; font-weight:600; letter-spacing:.08em; text-transform:uppercase; padding:.32rem .7rem; border-radius:999px; border:1px solid var(--line);}
.conteo .tag.peri {color:var(--accent2); border-color:rgba(255,140,0,.45);}
.conteo .tag.pv {color:var(--muted);}

.regla {display:flex; flex-wrap:wrap; gap:12px; margin:-.8rem 0 2.2rem;}
.regla span {display:flex; align-items:baseline; gap:.55rem; padding:.7rem 1.1rem; border:1px solid var(--line); border-radius:14px;
  background:var(--surface); font-size:.78rem; font-weight:600; letter-spacing:.1em; text-transform:uppercase; color:var(--muted);}
.regla b {font-family:var(--serif); font-size:1.45rem; font-weight:500; letter-spacing:0; color:var(--accent2); text-transform:none;}
.regla .tot {margin-left:auto; border-color:rgba(255,140,0,.4);}
.regla .tot b {color:var(--text);}

@media (max-width: 1000px) {
  .st-key-accesos {grid-template-columns:repeat(2,minmax(0,1fr)) !important;}
  .st-key-accesos > *, .st-key-accesos > :has(.st-key-acc_ultimo) {grid-column:span 1;}
  .st-key-accesos > :has(.st-key-acc_sumar) {grid-column:span 2;}
}
@media (max-width: 760px) {
  .st-key-decadas button {padding:.6rem .9rem !important;} .st-key-decadas button p {font-size:1.05rem !important;}
  .regla .tot {margin-left:0;}
}
</style>
"""


def estilos():
    st.markdown(CSS, unsafe_allow_html=True)


# -------------------------------------------------------------- componentes

def encabezado(sobre, titulo, bajada=None):
    """Título de página: `titulo` admite <em> para la palabra en naranja."""
    baj = f'<p class="baj">{bajada}</p>' if bajada else ""
    st.markdown(f'<div class="cab"><div class="eyebrow">{_e(sobre)}</div><div class="tit">{titulo}</div>{baj}</div>',
                unsafe_allow_html=True)


def medidor(etiqueta, valor, maximo, color, texto):
    if valor is None or pd.isna(valor):
        return f'<div class="med"><span class="l">{etiqueta}</span><span class="b"></span><span class="v">—</span></div>'
    pct = max(0, min(100, valor / maximo * 100))
    return (f'<div class="med"><span class="l">{etiqueta}</span><span class="b"><i style="width:{pct:.0f}%;'
            f'background:{color}"></i></span><span class="v">{texto}</span></div>')


def _criticos(s):
    partes = []
    if pd.notna(s.get("imdb")):
        partes.append(f'IMDb <i>{s["imdb"]:.1f}</i>')
    if pd.notna(s.get("rt")):
        partes.append(f'RT <i>{int(s["rt"])}%</i>')
    return " · ".join(partes)


def _abrir(s, clave):
    """Botón invisible que cubre la tarjeta y abre la ficha."""
    if st.button(f"Ver ficha de {s['titulo']}", key=f"b_{clave}_{s['id']}"):
        ficha(int(s["id"]))


def tarjeta(s, clave):
    if pd.notna(s.get("peri_rate")):
        nota = f'<span class="nota"><small>Peri</small>{s["peri_rate"]:.1f}</span>'
    else:
        nota = '<span class="nota pv">Por ver</span>'
    extra = _criticos(s)
    with st.container(key=f"card_{clave}_{s['id']}"):
        st.markdown(
            f'<div class="card"><div class="ph"><img src="{_e(poster(s.get("poster"), 400))}" loading="lazy" alt="">{nota}</div>'
            f'<div class="t">{_e(s["titulo"])}</div>'
            f'<div class="m">{anios_txt(s)}</div>{f'<div class="m">{extra}</div>' if extra else ""}</div>',
            unsafe_allow_html=True,
        )
        _abrir(s, clave)


def grilla(df, clave):
    with st.container(key=f"grid_{clave}"):
        for s in df.to_dict("records"):
            tarjeta(s, clave)


def podio(df):
    with st.container(key="podio"):
        for i, s in enumerate(df.to_dict("records"), 1):
            with st.container(key=f"pod_{s['id']}"):
                st.markdown(
                    f'<div class="pod"><div class="ph"><img src="{_e(poster(s.get("poster"), 600))}" alt="">'
                    f'<span class="num">{i}</span><span class="sc"><b>{s["peri_rate"]:.1f}</b><small>Nota del Peri</small></span></div>'
                    f'<div class="t">{_e(s["titulo"])}</div><div class="m">{anios_txt(s)}</div></div>',
                    unsafe_allow_html=True,
                )
                _abrir(s, "pod")


def lista_top(df, desde=1):
    with st.container(key="lista"):
        for i, s in enumerate(df.to_dict("records"), desde):
            generos = s["generos"] if isinstance(s.get("generos"), str) else ""
            imdb_txt = f'{s["imdb"]:.1f}' if pd.notna(s.get("imdb")) else "—"
            rt_txt = f'{int(s["rt"])}%' if pd.notna(s.get("rt")) else "—"
            with st.container(key=f"fila_{s['id']}"):
                st.markdown(
                    f'<div class="fila"><span class="n">{i}</span>'
                    f'<img src="{_e(poster(s.get("poster"), 120))}" loading="lazy" alt="">'
                    f'<div><div class="ft">{_e(s["titulo"])}</div><div class="fm">{anios_txt(s)} · {_e(generos)}</div></div>'
                    f'<div class="crit">{medidor("IMDb", s.get("imdb"), 10, AMARILLO_IMDB, imdb_txt)}'
                    f'{medidor("RT", s.get("rt"), 100, ROJO_RT, rt_txt)}</div>'
                    f'<span class="nota">{s["peri_rate"]:.1f}</span></div>',
                    unsafe_allow_html=True,
                )
                _abrir(s, "fila")


@st.dialog(" ", width="large")
def ficha(serie_id):
    s = db.obtener(serie_id)
    if not s:
        st.write("No encontré esa serie.")
        return
    generos = "".join(f"<span>{_e(g.strip())}</span>" for g in (s["generos"] or "").split(",") if g.strip())
    if s["peri_rate"] is not None:
        peri = f'<div class="pr"><b>{s["peri_rate"]:.1f}</b><small>Nota del Peri</small></div>'
    else:
        peri = '<div class="pr pend"><b>Por ver</b><small>El Peri todavía no la ve</small></div>'
    medidores = (
        medidor("IMDb", s["imdb"], 10, AMARILLO_IMDB, f'{s["imdb"]:.1f}' if s["imdb"] is not None else "")
        + medidor("Crítica", s["rt"], 100, ROJO_RT, f'{s["rt"]}%' if s["rt"] is not None else "")
        + medidor("Público", s["rt_audiencia"], 100, "#f0a35e", f'{s["rt_audiencia"]}%' if s["rt_audiencia"] is not None else "")
    )
    links = ""
    if s["imdb_id"]:
        links += f'<a href="https://www.imdb.com/title/{s["imdb_id"]}/" target="_blank" rel="noopener">IMDb ↗</a>'
    if s["rt_url"]:
        links += f'<a href="{_e(s["rt_url"])}" target="_blank" rel="noopener">Rotten Tomatoes ↗</a>'
    sinopsis = f'<p class="sin">{_e(s["sinopsis"])}</p>' if s["sinopsis"] else ""
    grande = poster(s["poster"], 600)
    st.markdown(
        f'<div class="ficha" style="--p:url(\'{_e(grande)}\')"><img class="fp" src="{_e(grande)}" alt="">'
        f'<div><div class="eyebrow">{anios_txt(s)} · {temps_txt(s)}</div><div class="tt">{_e(s["titulo"])}</div>'
        f'<div class="gen">{generos}</div><div class="sco">{peri}<div>{medidores}</div></div>'
        f'{sinopsis}<div class="lk">{links}</div></div></div>',
        unsafe_allow_html=True,
    )
    if st.session_state.get("admin"):  # lo interno solo lo ve el dueño
        if s["notas"]:
            st.info(s["notas"])
        h = db.historial(serie_id)
        if len(h) > 1:
            h["rt/10"] = h["rt"] / 10
            fig = px.line(h, x="fecha", y=["imdb", "rt/10"], markers=True, color_discrete_sequence=[AMARILLO_IMDB, ROJO_RT])
            st.plotly_chart(plantilla(fig, alto=230), use_container_width=True)
        if s["actualizado_en"]:
            st.caption(f"Scores actualizados: {s['actualizado_en'][:16].replace('T', ' ')}")


def mini_lista(titulo, detalle, df, col_extra, fmt):
    filas = "".join(
        f'<div class="r"><span>{_e(r["titulo"])}</span><b>{r["peri_rate"]:.1f}</b><i>{fmt(r[col_extra])}</i></div>'
        for r in df.to_dict("records")
    )
    st.markdown(f'<div class="mini"><h4>{_e(titulo)}</h4><div class="d">{_e(detalle)}</div>{filas}</div>',
                unsafe_allow_html=True)


def plantilla(fig, alto=460):
    eje = dict(gridcolor="rgba(255,255,255,.06)", zeroline=False, linecolor="rgba(255,255,255,.12)",
               tickfont=dict(color="#8f877d", size=12), title_font=dict(color="#cfc7bc", size=13))
    fig.update_layout(
        height=alto, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, sans-serif", color="#cfc7bc"), margin=dict(l=10, r=10, t=20, b=10),
        legend=dict(title=None, orientation="h", y=1.08, x=0, font=dict(color="#cfc7bc")),
        hoverlabel=dict(bgcolor="#1c1917", bordercolor="rgba(255,140,0,.5)", font=dict(family="Inter, sans-serif", color="#f4efe8")),
        xaxis=eje, yaxis=eje,
    )
    return fig
