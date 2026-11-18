"""Panel de administración (solo para el dueño de la colección)."""
import pandas as pd
import streamlit as st

import db
import fuentes
import sincronizar
from ui import ICONO_ESTADO, SIN_POSTER, anios_txt, temps_txt


def _buscador(clave):
    texto = st.text_input("Nombre de la serie", key=f"q_{clave}", placeholder="Ej: The Bear")
    if not texto:
        return None
    try:
        with st.spinner("Buscando en IMDb…"):
            candidatos = fuentes.buscar_omdb(texto)
    except fuentes.LimiteOMDb as e:
        st.error(f"⛔ {e}")
        return None
    if not candidatos:
        st.warning("No encontré nada con ese nombre. Prueba con el título en inglés.")
        return None
    cols = st.columns(5)
    for col, c in zip(cols * 2, candidatos[:10]):
        with col:
            st.image(c["poster"] or SIN_POSTER, use_container_width=True)
            if st.button(f"{c['titulo']} ({c['anio']})", key=f"pick_{clave}_{c['imdb_id']}",
                         use_container_width=True):
                st.session_state[f"elegida_{clave}"] = c["imdb_id"]
    return st.session_state.get(f"elegida_{clave}")


def panel_agregar():
    imdb_id = _buscador("nueva")
    if not imdb_id:
        return
    existente = db.buscar_por_imdb(imdb_id)
    if existente:
        st.info(f"«{existente['titulo']}» ya está en la colección; edítala en la pestaña ✏️ Editar.")
        return
    if st.session_state.get("ficha_nueva", {}).get("imdb_id") != imdb_id:
        with st.spinner("Trayendo IMDb, Rotten Tomatoes, temporadas y episodios…"):
            st.session_state["ficha_nueva"] = fuentes.ficha_completa(imdb_id)
    datos = st.session_state["ficha_nueva"]
    if not datos:
        st.error("No pude traer los datos de esa serie.")
        return

    c1, c2 = st.columns([1, 3])
    c1.image(datos["poster"] or SIN_POSTER, use_container_width=True)
    with c2:
        st.subheader(datos["titulo"])
        st.caption(f"{anios_txt(datos)} · {temps_txt(datos)} · {datos.get('generos') or ''}")
        m = st.columns(3)
        m[0].metric("IMDb", datos["imdb"] or "—")
        m[1].metric("Tomatómetro", f"{datos['rt']}%" if datos.get("rt") is not None else "No encontrado")
        m[2].metric("Audiencia RT", f"{datos['rt_audiencia']}%" if datos.get("rt_audiencia") is not None else "—")
        with st.form("guardar_nueva"):
            estado = st.segmented_control("Estado", db.ESTADOS, default="vista",
                                          format_func=lambda e: f"{ICONO_ESTADO[e]} {e.capitalize()}")
            peri = st.slider("Tu Peri Rate", 0.0, 10.0, 8.5, 0.1)
            posteada = st.checkbox("Ya la posteé")
            notas = st.text_area("Notas (opcional)")
            rt_manual = st.text_input("URL de Rotten Tomatoes (solo si no la encontró o es otra)",
                                      value=datos.get("rt_url") or "")
            if st.form_submit_button("💾 Guardar en la colección", type="primary"):
                estado = estado or "vista"
                if rt_manual and rt_manual != datos.get("rt_url"):
                    datos.update(fuentes.datos_rt(datos["titulo"], rt_url=rt_manual.strip()))
                db.insertar({
                    **datos,
                    "estado": estado,
                    "peri_rate": peri if estado in ("vista", "viendo", "abandonada") else None,
                    "posteada": int(posteada),
                    "notas": notas or None,
                    "fecha_vista": db.ahora() if estado == "vista" else None,
                    "actualizado_en": db.ahora(),
                })
                st.session_state.pop("ficha_nueva", None)
                st.session_state.pop("elegida_nueva", None)
                st.session_state["agregada_ok"] = True
                st.toast(f"«{datos['titulo']}» agregada 🎉")
                st.balloons()


def _selector_serie(df, clave):
    opciones = df.sort_values("titulo")
    etiquetas = {int(r.id): f"{ICONO_ESTADO.get(r.estado, '')} {r.titulo}" for r in opciones.itertuples()}
    return st.selectbox("Serie", list(etiquetas), format_func=etiquetas.get, key=clave, index=None,
                        placeholder="Escribe para buscar…")


def panel_editar():
    df = db.todas()
    sid = _selector_serie(df, "sel_editar")
    if sid is None:
        return
    s = db.obtener(sid)
    c1, c2 = st.columns([1, 3])
    c1.image(s["poster"] or SIN_POSTER, use_container_width=True)
    with c2:
        st.caption(f"{anios_txt(s)} · {temps_txt(s)} · IMDb {s['imdb'] or '—'} · RT {s['rt'] or '—'}%")
        with st.form(f"editar_{sid}"):
            titulo = st.text_input("Título", s["titulo"])
            estado = st.segmented_control("Estado", db.ESTADOS, default=s["estado"],
                                          format_func=lambda e: f"{ICONO_ESTADO[e]} {e.capitalize()}")
            tiene_nota = st.checkbox("Tiene Peri Rate", value=s["peri_rate"] is not None)
            peri = st.slider("Peri Rate", 0.0, 10.0, float(s["peri_rate"] or 8.5), 0.1)
            posteada = st.checkbox("Posteada", value=bool(s["posteada"]))
            notas = st.text_area("Notas", s["notas"] or "")
            rt_url = st.text_input("URL de Rotten Tomatoes", s["rt_url"] or "")
            b1, b2 = st.columns(2)
            guardar = b1.form_submit_button("💾 Guardar", type="primary", use_container_width=True)
            refrescar = b2.form_submit_button("🔄 Guardar y actualizar scores", use_container_width=True)
        if guardar or refrescar:
            estado = estado or s["estado"]
            cambios = {
                "titulo": titulo.strip(), "estado": estado, "peri_rate": peri if tiene_nota else None,
                "posteada": int(posteada), "notas": notas or None, "rt_url": rt_url.strip() or None,
            }
            if estado == "vista" and s["estado"] != "vista":
                cambios["fecha_vista"] = db.ahora()
            db.actualizar(sid, cambios)
            if refrescar:
                with st.spinner("Actualizando desde IMDb y Rotten Tomatoes…"):
                    _, msg = sincronizar.refrescar(db.obtener(sid))
                st.toast(f"Actualizada: {msg}")
            else:
                st.toast("Guardada ✅")
        with st.popover("🗑️ Eliminar serie"):
            st.write(f"¿Seguro que quieres eliminar «{s['titulo']}»? No se puede deshacer.")
            if st.button("Sí, eliminar", type="primary", key=f"del_{sid}"):
                db.borrar(sid)
                st.rerun()


def panel_sin_vincular():
    df = db.todas()
    faltan = df[df["imdb_id"].isna()].sort_values("titulo")
    sin_rt = df[df["imdb_id"].notna() & df["rt_url"].isna()]
    st.caption(f"{len(faltan)} series sin vincular con IMDb · {len(sin_rt)} vinculadas pero sin Rotten Tomatoes.")
    if not len(faltan):
        st.success("Todas las series están vinculadas con IMDb 🎉")
    else:
        sid = _selector_serie(faltan, "sel_vincular")
        if sid is not None:
            s = db.obtener(sid)
            st.write(f"Busca la correcta para **{s['titulo']}** ({anios_txt(s)}):")
            st.session_state.setdefault("q_vinc", s["titulo"])
            imdb_id = _buscador("vinc")
            if imdb_id:
                otra = db.buscar_por_imdb(imdb_id)
                if otra:
                    st.warning(f"Ese título ya está en la colección como «{otra['titulo']}».")
                elif st.button("🔗 Vincular y actualizar", type="primary"):
                    db.actualizar(sid, {"imdb_id": imdb_id})
                    with st.spinner("Actualizando…"):
                        _, msg = sincronizar.refrescar(db.obtener(sid))
                    st.session_state.pop("elegida_vinc", None)
                    st.session_state.pop("q_vinc", None)
                    st.toast(f"Vinculada: {msg}")
                    st.rerun()
    if len(sin_rt):
        with st.expander("Series sin Rotten Tomatoes (pon la URL en ✏️ Editar)"):
            st.dataframe(sin_rt[["titulo", "anio_inicio", "rt"]], hide_index=True, use_container_width=True)


def panel_actualizar():
    df = db.todas()
    st.write("Vuelve a consultar IMDb y Rotten Tomatoes para tus series. Las de más tiempo sin actualizar van primero.")
    st.caption("OMDb gratis permite ~1000 consultas por día; cada serie usa 1 (más 1 por temporada si sigue en emisión).")
    c1, c2 = st.columns(2)
    alcance = c1.radio("¿Cuáles?", ["En emisión", "Vistas", "Todas"], horizontal=True)
    limite = c2.number_input("Máximo de series", 1, len(df) or 1, min(50, len(df) or 1))
    if st.button("🔄 Actualizar ahora", type="primary"):
        f = df[df["imdb_id"].notna()]
        if alcance == "En emisión":
            f = f[f["en_emision"] == 1]
        elif alcance == "Vistas":
            f = f[f["estado"] == "vista"]
        f = f.sort_values("actualizado_en", na_position="first").head(int(limite))
        barra = st.progress(0.0)
        log = []
        for i, s in enumerate(f.to_dict("records"), 1):
            s = {k: (None if v != v else v) for k, v in s.items()}
            try:
                estado, msg = sincronizar.refrescar(s, vincular=False)
            except fuentes.LimiteOMDb as e:
                st.warning(f"⛔ {e} Se revisaron {i - 1} de {len(f)}.")
                break
            except Exception as e:
                estado, msg = "error", str(e)
            if msg != "Sin cambios":
                log.append(f"**{s['titulo']}**: {msg}")
            barra.progress(i / len(f), text=f"{i}/{len(f)} · {s['titulo']}")
        st.success(f"Listo: {len(f)} series revisadas, {len(log)} con cambios.")
        for linea in log:
            st.markdown(f"- {linea}")


def panel_recomendaciones():
    recs = db.recomendaciones("nueva")
    if not len(recs):
        st.info("No hay recomendaciones nuevas. 📭")
        return
    st.caption(f"{len(recs)} recomendaciones nuevas de la gente.")

    def preparar(titulo, rec_id):
        st.session_state["q_nueva"] = titulo
        st.session_state.pop("elegida_nueva", None)
        st.session_state["rec_en_curso"] = rec_id

    for r in recs.itertuples():
        with st.container(border=True):
            c1, c2, c3 = st.columns([5, 1.4, 1.2])
            quien = f" · de **{r.quien}**" if r.quien else ""
            c1.markdown(f"**{r.titulo}**{quien}  \n<small>{r.fecha[:10]}</small>", unsafe_allow_html=True)
            if r.motivo:
                c1.caption(f"“{r.motivo}”")
            c2.button("➕ Agregar", key=f"rec_add_{r.id}", on_click=preparar, args=(r.titulo, r.id),
                      use_container_width=True, help="La deja escrita en la pestaña ➕ Agregar serie")
            if c3.button("Descartar", key=f"rec_del_{r.id}", use_container_width=True):
                db.marcar_recomendacion(r.id, "descartada")
                st.rerun()
    if st.session_state.get("rec_en_curso"):
        st.success("Listo: ve a la pestaña ➕ Agregar serie, ya está buscada.")


def panel_cambios():
    cambios = db.cambios_recientes(60)
    if not len(cambios):
        st.info("Todavía no hay cambios de scores registrados.")
        return
    st.caption("Solo lo ves tú: series cuyo IMDb o RT cambió en las últimas actualizaciones.")
    for _, r in cambios.iterrows():
        partes = []
        for nombre, antes, ahora, fmt in [("IMDb", r["imdb_antes"], r["imdb_ahora"], "{:.1f}"),
                                          ("RT", r["rt_antes"], r["rt_ahora"], "{:.0f}%")]:
            if pd.isna(ahora) or antes == ahora:
                continue
            if pd.isna(antes):
                partes.append(f"🆕 {nombre} {fmt.format(ahora)}")
            else:
                flecha = "🟢" if ahora > antes else "🔴"
                partes.append(f"{flecha} {nombre} {fmt.format(antes)} → {fmt.format(ahora)}")
        if partes:
            st.markdown(f"**{r['titulo']}** · " + " · ".join(partes) + f"  <small>({r['fecha'][:10]})</small>",
                        unsafe_allow_html=True)


def pagina_admin():
    st.title("🔐 Administración")
    if not st.session_state.get("admin"):
        with st.form("login"):
            clave = st.text_input("Contraseña", type="password")
            if st.form_submit_button("Entrar", type="primary"):
                if clave == st.secrets.get("admin_password"):
                    st.session_state["admin"] = True
                    st.rerun()
                st.error("Contraseña incorrecta")
        return

    nuevas = len(db.recomendaciones("nueva"))
    pestañas = st.tabs(["➕ Agregar serie", f"📬 Recomendaciones ({nuevas})", "✏️ Editar", "🔗 Sin vincular",
                        "🔄 Actualizar scores", "📈 Cambios de scores"])
    with pestañas[0]:
        panel_agregar()
        rec = st.session_state.get("rec_en_curso")
        if rec and st.session_state.get("agregada_ok"):
            db.marcar_recomendacion(rec, "agregada")
            st.session_state.pop("rec_en_curso", None)
            st.session_state.pop("agregada_ok", None)
    with pestañas[1]:
        panel_recomendaciones()
    with pestañas[2]:
        panel_editar()
    with pestañas[3]:
        panel_sin_vincular()
    with pestañas[4]:
        panel_actualizar()
    with pestañas[5]:
        panel_cambios()
    st.divider()
    if st.button("Cerrar sesión"):
        st.session_state.pop("admin", None)
        st.rerun()
