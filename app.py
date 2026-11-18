"""Series XXI — las mejores series del siglo XXI, curadas por el Peri.

    streamlit run app.py
El panel de administración no aparece en el menú: se entra con  http://localhost:8501/?admin
"""
import random

import streamlit as st

st.set_page_config(page_title="Series XXI", page_icon="📺", layout="wide")

import admin  # noqa: E402
import db  # noqa: E402
import ui  # noqa: E402
from ui import NARANJA, anios_txt, cargar, grilla, poster, temps_txt  # noqa: E402

ui.estilos()
st.logo("logo.svg", size="large")

if not db.PG and not db.DB_PATH.exists():
    st.error("Falta configurar la base de datos: agrega `db_url` en los Secrets de la app.")
    st.stop()

# Unánimes: el Peri, IMDb y Rotten Tomatoes coinciden en que hay que verla
UNAN_PERI, UNAN_IMDB, UNAN_RT = 9.0, 8.0, 80


def _vistas(df):
    return df[df["peri_rate"].notna()]


def _unanimes(df):
    u = df[(df["peri_rate"] >= UNAN_PERI) & (df["imdb"] >= UNAN_IMDB) & (df["rt"] >= UNAN_RT)].copy()
    u["consenso"] = (u["peri_rate"] + u["imdb"] + u["rt"] / 10) / 3
    return u.sort_values(["consenso", "peri_rate"], ascending=False)


def _infaltables(df):
    v = _vistas(df)
    v = v[~v["id"].isin(_unanimes(df)["id"])]
    return v.sort_values(["peri_rate", "imdb"], ascending=False)


def _recientes(df):
    v = df[df["estado"] == "vista"]
    return v.assign(_f=v["fecha_vista"].fillna(v["fecha_agregada"])).sort_values(
        ["_f", "anio_inicio", "id"], ascending=False)


# ------------------------------------------------------------------- portada

def _muro(df):
    """Fondo de la portada: filas de pósters moviéndose muy despacio."""
    mejores = df.sort_values(["peri_rate", "score_critica"], ascending=False, na_position="last")
    urls = [poster(u, 220) for u in mejores["poster"].dropna().head(48)]
    random.Random(7).shuffle(urls)
    filas = ""
    for i in range(4):
        tramo = urls[i * 12:(i + 1) * 12]
        imgs = "".join(f'<img src="{u}" alt="">' for u in tramo * 2)
        filas += f'<div class="row">{imgs}</div>'
    st.markdown(f'<div class="wall" aria-hidden="true"><div class="rows">{filas}</div></div>', unsafe_allow_html=True)


def _accesos(df):
    tres = lambda d: [poster(u, 200) for u in d["poster"].dropna().head(3)]  # noqa: E731
    items = [
        ("coleccion", PAG_COLECCION, "La colección", f"Las {len(df)} series, vistas y por ver.",
         tres(df.sort_values("score_critica", ascending=False).sample(frac=1, random_state=11))),
        ("infaltables", PAG_INFALTABLES, "Infaltables", "Las que tienes que ver sí o sí, según el Peri.",
         tres(_infaltables(df))),
        ("unanimes", PAG_UNANIMES, "Unánimes", "El Peri, IMDb y Rotten Tomatoes de acuerdo.", tres(_unanimes(df))),
        ("ultimo", PAG_ULTIMO, "Lo último", "Lo más reciente que vio el Peri.", tres(_recientes(df))),
        ("sumar", PAG_SUMAR, "Sumar una serie", "¿Falta una que te gusta? Recomiéndala.", []),
    ]
    css = ""
    for clave, _, _, texto, posters in items:
        sel = f'.st-key-acc_{clave} [data-testid="stPageLink-NavLink"]'
        css += f'{sel}::after{{content:"{texto}"}}'
        if posters:
            capas = ", ".join(f'url("{u}")' for u in posters)
            pos = ", ".join(f"right {i * 99}px top 0" for i in range(len(posters)))
            tam = ", ".join("auto 100%" for _ in posters)
            css += (f'{sel}{{background-image:linear-gradient(90deg,#141210 40%,rgba(20,18,16,.86) 60%,rgba(20,18,16,.3)), {capas};'
                    f'background-position:0 0, {pos};background-size:100% 100%, {tam}}}')
        else:
            css += f'{sel}{{border-style:dashed;border-color:rgba(255,140,0,.4);background-color:rgba(255,140,0,.04)}}'
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)
    with st.container(key="accesos"):
        for clave, pagina, titulo, _, _ in items:
            with st.container(key=f"acc_{clave}"):
                st.page_link(pagina, label=titulo)


def inicio():
    df = cargar()
    vistas = _vistas(df)
    _muro(df)
    st.markdown(
        f"""<div class="hero">
        <div class="eyebrow">Las mejores series del siglo XXI</div>
        <div class="tit">Series <em>XXI</em></div>
        <p class="baj">Cada serie, evaluada por IMDb, Rotten Tomatoes y el Peri. Encuentra la próxima que vas a ver.</p>
        <div class="cifras">
          <div><b>{len(df)}</b><small>series</small></div>
          <div><b>{len(vistas)}</b><small>vistas por el Peri</small></div>
          <div><b>{len(_unanimes(df))}</b><small>unánimes</small></div>
        </div></div>""",
        unsafe_allow_html=True,
    )

    with st.container(key="dado"):
        if st.button("🎲  Tirar el dado", type="primary",
                     help="Una serie al azar entre las que el Peri calificó con 9 o más"):
            buenas = vistas[vistas["peri_rate"] >= 9]["id"].tolist()
            previa = st.session_state.get("dado")
            if buenas:
                st.session_state["dado"] = int(random.choice([i for i in buenas if i != previa] or buenas))
    if "dado" in st.session_state:
        s = db.obtener(st.session_state["dado"])
        if s:
            grande = poster(s["poster"], 400)
            criticos = " · ".join(x for x in [
                f"IMDb {s['imdb']:.1f}" if s["imdb"] is not None else "",
                f"RT {s['rt']}%" if s["rt"] is not None else ""] if x)
            nota = f"{s['peri_rate']:.1f}" if s["peri_rate"] is not None else "—"
            st.markdown(
                f"""<div class="pick" style="--p:url('{grande}')"><img src="{grande}" alt="">
                <div><div class="eyebrow">El dado dice</div><div class="pt">{ui._e(s['titulo'])}</div>
                <div class="pm">{anios_txt(s)} · {temps_txt(s)}</div>
                <div class="pn"><b>{nota}</b><span>Nota del Peri · {criticos}</span></div>
                <p class="ps">{ui._e(s['sinopsis'] or '')}</p></div></div>""",
                unsafe_allow_html=True,
            )

    _accesos(df)
    st.markdown('<div class="pie">Series XXI · Curada por el Peri · Datos de IMDb y Rotten Tomatoes</div>',
                unsafe_allow_html=True)


# ------------------------------------------------------------------- páginas

def coleccion():
    df = cargar()
    total_vistas = int(df["peri_rate"].notna().sum())
    ui.encabezado("El archivo completo", "La <em>colección</em>",
                  f"Las {len(df)} series del siglo XXI: {total_vistas} ya tienen la nota del Peri "
                  f"y {len(df) - total_vistas} están por ver. Elige una década y explora.")

    # --- décadas y años, lo primero y lo más grande
    conteo = df["decada"].value_counts()
    decadas = sorted(d for d in conteo.index if d != "—s")
    with st.container(key="decadas"):
        dec = st.pills("Década", decadas, selection_mode="single", label_visibility="collapsed",
                       format_func=lambda d: f"{d}  ·  {conteo[d]}")
    anio = None
    if dec:
        en_dec = df[df["decada"] == dec]["anio_inicio"].dropna().astype(int).value_counts().sort_index()
        with st.container(key="anios"):
            anio = st.pills("Año de estreno", list(en_dec.index), selection_mode="single",
                            label_visibility="collapsed", format_func=lambda a: f"{a}  ·  {en_dec[a]}")

    f1, f2, f3 = st.columns([2.2, 2, 1.2])
    texto = f1.text_input("Buscar", placeholder="Breaking Bad, Fleabag…")
    mostrar = f2.segmented_control("Mostrar", ["Todas", "Vistas por el Peri", "Por ver"], default="Todas")
    orden = f3.selectbox("Ordenar por", ["Nota del Peri", "IMDb", "Rotten Tomatoes", "Más nuevas", "Título"])
    generos = sorted({g.strip() for gs in df["generos"].dropna() for g in gs.split(",")})
    gen = st.multiselect("Géneros", generos, placeholder="Todos los géneros")

    f = df
    if dec:
        f = f[f["decada"] == dec]
    if anio:
        f = f[f["anio_inicio"] == anio]
    if texto:
        f = f[f["titulo"].str.contains(texto, case=False, na=False, regex=False)]
    if mostrar == "Vistas por el Peri":
        f = f[f["peri_rate"].notna()]
    elif mostrar == "Por ver":
        f = f[f["peri_rate"].isna()]
    if gen:
        f = f[f["generos"].fillna("").apply(lambda s: any(g in s for g in gen))]
    col = {"Nota del Peri": "peri_rate", "IMDb": "imdb", "Rotten Tomatoes": "rt", "Más nuevas": "anio_inicio",
           "Título": "titulo"}[orden]
    asc = orden == "Título"
    f = f.sort_values([col, "score_critica"], ascending=[asc, False], na_position="last")

    firma = (dec, anio, texto, mostrar, orden, tuple(gen))
    if st.session_state.get("col_firma") != firma:
        st.session_state["col_firma"], st.session_state["col_n"] = firma, 30
    n = st.session_state["col_n"]
    vistas_f = int(f["peri_rate"].notna().sum())
    st.markdown(
        f'<div class="conteo"><b>{len(f)}</b> series <span class="sep"></span>'
        f'<span class="tag peri">{vistas_f} vistas por el Peri</span>'
        f'<span class="tag pv">{len(f) - vistas_f} por ver</span></div>', unsafe_allow_html=True)
    if not len(f):
        st.info("No hay series con esos filtros.")
        return
    grilla(f.head(n), "col")
    if len(f) > n:
        with st.container(key="mas"):
            if st.button(f"Ver más  ·  quedan {len(f) - n}"):
                st.session_state["col_n"] = n + 30
                st.rerun()


def infaltables():
    df = cargar()
    ui.encabezado("Según el Peri", "<em>Infaltables</em>",
                  "Las 50 series que tienes que ver sí o sí según el Peri, aunque la crítica no siempre "
                  "esté tan de acuerdo. Las que también aman IMDb y Rotten Tomatoes están en Unánimes.")
    lista = _infaltables(df)
    decadas = ["Todas"] + sorted(d for d in lista["decada"].unique() if d != "—s")
    dec = st.segmented_control("Década", decadas, default="Todas", label_visibility="collapsed")
    if dec and dec != "Todas":
        lista = lista[lista["decada"] == dec]
    top = lista.head(50)
    st.markdown(
        f'<div class="leyenda"><span style="--c:{NARANJA}">Nota del Peri (0 a 10)</span>'
        f'<span style="--c:{ui.AMARILLO_IMDB}">IMDb · el público</span>'
        f'<span style="--c:{ui.ROJO_RT}">Rotten Tomatoes · la crítica</span></div>', unsafe_allow_html=True)
    ui.podio(top.head(3))
    ui.lista_top(top.iloc[3:], desde=4)


def unanimes():
    df = cargar()
    u = _unanimes(df)
    ui.encabezado("Consenso total", "<em>Unánimes</em>",
                  "Las series que tienes que ver según el Peri, IMDb y Rotten Tomatoes: los tres coinciden.")
    st.markdown(
        f'<div class="regla"><span><b>{UNAN_PERI:g}+</b>Nota del Peri</span><span><b>{UNAN_IMDB:g}+</b>IMDb</span>'
        f'<span><b>{UNAN_RT}%+</b>Rotten Tomatoes</span><span class="tot"><b>{len(u)}</b>series</span></div>',
        unsafe_allow_html=True)
    grilla(u, "unan")


def lo_ultimo():
    ui.encabezado("Recién vistas", "Lo <em>último</em>", "Las series más recientes que vio el Peri.")
    grilla(_recientes(cargar()).head(24), "ult")


def sumar():
    with st.container(key="angosto"):
        ui.encabezado("Recomendaciones", "Sumar <em>una serie</em>",
                      "¿Falta una serie que te gusta y no está? Recomiéndasela al Peri para que la vea "
                      "y la sume a la colección.")
        with st.form("recomendar", clear_on_submit=True):
            titulo = st.text_input("¿Qué serie?", placeholder="Ej: The Bear")
            quien = st.text_input("Tu nombre (opcional)")
            motivo = st.text_area("¿Por qué tiene que verla? (opcional)", max_chars=400, height=110)
            if st.form_submit_button("Enviar recomendación", type="primary"):
                if not titulo.strip():
                    st.warning("Escribe el nombre de la serie.")
                else:
                    ya = cargar()
                    existe = ya[ya["titulo"].str.lower() == titulo.strip().lower()]
                    if len(existe):
                        st.info(f"«{existe.iloc[0]['titulo']}» ya está en la colección. Búscala en La colección.")
                    else:
                        db.recomendar(titulo, quien.strip(), motivo.strip())
                        st.success("¡Gracias! El Peri va a recibir tu recomendación.")


PAG_INICIO = st.Page(inicio, title="Inicio", default=True)
PAG_COLECCION = st.Page(coleccion, title="Colección", url_path="coleccion")
PAG_INFALTABLES = st.Page(infaltables, title="Infaltables", url_path="infaltables")
PAG_UNANIMES = st.Page(unanimes, title="Unánimes", url_path="unanimes")
PAG_ULTIMO = st.Page(lo_ultimo, title="Lo último", url_path="lo-ultimo")
PAG_SUMAR = st.Page(sumar, title="Sumar una serie", url_path="sumar")
PAG_ADMIN = st.Page(admin.pagina_admin, title="Admin", url_path="admin")

paginas = [PAG_INICIO, PAG_COLECCION, PAG_INFALTABLES, PAG_UNANIMES, PAG_ULTIMO, PAG_SUMAR]
# El admin solo aparece si entras con ?admin en la URL (o ya iniciaste sesión)
if "admin" in st.query_params:
    st.session_state["mostrar_admin"] = True
if st.session_state.get("mostrar_admin") or st.session_state.get("admin"):
    paginas.append(PAG_ADMIN)

st.navigation(paginas, position="top").run()
