"""Dashboard Streamlit para vigilancia forestal."""

from __future__ import annotations

import hashlib
import os

import requests
import streamlit as st
from streamlit_autorefresh import st_autorefresh
from streamlit_folium import st_folium

from geo_pipeline import CAMERA
from dashboard.kpi_panel import render_contexto, render_meteo, render_riesgo
from dashboard.map_builder import construir_mapa

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
API_INTERNAL_URL = os.getenv("API_INTERNAL_URL", API_BASE_URL)
API_PUBLIC_URL = os.getenv("API_PUBLIC_URL", API_BASE_URL)

st.set_page_config(page_title="Fire Smoke AI - Tejeda", layout="wide")


def api_get(path: str, default):
    try:
        r = requests.get(f"{API_INTERNAL_URL}{path}", timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as exc:  # noqa: BLE001
        st.error(f"No se pudo conectar con la API: {exc}")
        return default


def api_delete(path: str, default):
    try:
        r = requests.delete(f"{API_INTERNAL_URL}{path}", timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as exc:  # noqa: BLE001
        st.error(f"No se pudo completar la accion: {exc}")
        return default


if "focus" not in st.session_state:
    st.session_state["focus"] = {"lat": CAMERA["lat"], "lon": CAMERA["lon"]}
if "layers" not in st.session_state:
    st.session_state["layers"] = {"zari": True, "combustible": False, "firms": False, "alertas": True}


with st.sidebar:
    st.title("Fire Smoke AI")
    auto_refresh = st.checkbox("Autoactualizar cada 60 s", value=False)
    if auto_refresh:
        st_autorefresh(interval=60_000, key="refresh")
    if st.button("Actualizar datos"):
        focus = st.session_state["focus"]
        risk = api_get(f"/risk?force=true&lat={focus['lat']}&lon={focus['lon']}", {})
    else:
        focus = st.session_state["focus"]
        risk = api_get(f"/risk?lat={focus['lat']}&lon={focus['lon']}", {})

    uploaded = st.file_uploader("Probar inferencia con imagen", type=["jpg", "jpeg", "png"])
    if uploaded:
        file_bytes = uploaded.getvalue()
        file_hash = hashlib.sha256(file_bytes).hexdigest()
        st.caption("La imagen solo se analiza al pulsar el boton; no se reenvia en cada refresco.")
        if st.button("Analizar imagen", type="primary"):
            files = {"file": (uploaded.name, file_bytes, uploaded.type)}
            try:
                resp = requests.post(f"{API_INTERNAL_URL}/predict", files=files, timeout=30)
                resp.raise_for_status()
                st.session_state["last_prediction_hash"] = file_hash
                st.session_state["last_prediction"] = resp.json()
            except Exception as exc:  # noqa: BLE001
                st.error(f"Fallo en /predict: {exc}")
        result = st.session_state.get("last_prediction")
        if result and st.session_state.get("last_prediction_hash") == file_hash:
            st.json(result)
            if result.get("imagen_resultado_url"):
                st.image(f"{API_PUBLIC_URL}{result['imagen_resultado_url']}", use_container_width=True)

    if st.checkbox("Modo simulacion de alerta"):
        st.info("Simulacion visual activa. Para Telegram usa /predict con una imagen positiva.")

    st.divider()
    st.subheader("Capas del mapa")
    st.session_state["layers"]["zari"] = st.checkbox("ZARI Gran Canaria", value=st.session_state["layers"]["zari"])
    st.session_state["layers"]["combustible"] = st.checkbox("Combustible", value=st.session_state["layers"]["combustible"])
    st.session_state["layers"]["firms"] = st.checkbox("FIRMS historico", value=st.session_state["layers"]["firms"])
    st.session_state["layers"]["alertas"] = st.checkbox("Alertas recientes", value=st.session_state["layers"]["alertas"])

    st.divider()
    st.subheader("Alertas")
    confirm_reset = st.checkbox("Confirmar limpieza")
    if st.button("Reiniciar historial", disabled=not confirm_reset):
        result = api_delete("/alerts", {})
        st.success(f"Alertas eliminadas: {result.get('deleted', 0)}")
        st.rerun()

    st.divider()
    st.subheader("Video o pantalla")
    st.link_button("Abrir detector de pantalla", f"{API_PUBLIC_URL}/screen-capture")
    st.caption("Usa el boton, elige pantalla/ventana/pestana y deja que el navegador envie frames a la API.")

if not risk:
    focus = st.session_state["focus"]
    risk = api_get(f"/risk?lat={focus['lat']}&lon={focus['lon']}", {})
alerts = api_get("/alerts?limite=50", [])

indice = risk.get("indice_riesgo", {"indice": 0, "nivel": "N/D", "color_hex": "#95a5a6", "componentes": {}})
meteo = risk.get("meteo", {})
zari = risk.get("zari", {})
combustible = risk.get("combustible", {})
firms = risk.get("firms", {})
foco = risk.get("foco", st.session_state["focus"])

left, right = st.columns([7, 3])
with left:
    st.subheader("Mapa territorial")
    mapa = construir_mapa(indice, meteo, alerts, foco, combustible, st.session_state["layers"])
    map_state = st_folium(mapa, height=760, use_container_width=True, returned_objects=["last_clicked"], key="risk_map")
    clicked = map_state.get("last_clicked") if map_state else None
    if clicked:
        new_focus = {"lat": round(clicked["lat"], 6), "lon": round(clicked["lng"], 6)}
        if new_focus != st.session_state["focus"]:
            st.session_state["focus"] = new_focus
            st.rerun()

with right:
    render_riesgo(indice, foco)
    render_meteo(meteo)
    render_contexto(zari, combustible, firms)
    st.subheader("Historial de alertas")
    st.dataframe(alerts[:10], use_container_width=True, hide_index=True)
