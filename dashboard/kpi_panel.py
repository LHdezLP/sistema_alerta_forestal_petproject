"""Componentes de KPI para Streamlit."""

from __future__ import annotations

import pandas as pd
import streamlit as st


def render_riesgo(indice: dict, foco: dict | None = None) -> None:
    color = indice.get("color_hex", "#f39c12")
    nivel = indice.get("nivel", "N/D")
    valor = indice.get("indice", 0.0)
    st.markdown(
        f"""
        <div style="background:{color};color:white;padding:16px;border-radius:8px;margin-bottom:12px">
          <div style="font-size:0.85rem;font-weight:700">RIESGO DEL FOCO</div>
          <div style="font-size:1.8rem;font-weight:800">{nivel} - {valor:.2f}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if foco:
        st.caption(f"Foco: {float(foco.get('lat', 0)):.5f}, {float(foco.get('lon', 0)):.5f}")


def render_meteo(meteo: dict) -> None:
    st.subheader("Meteorologia")
    if meteo.get("error"):
        st.warning(meteo["error"])
        return
    c1, c2 = st.columns(2)
    c1.metric("Temperatura", f"{meteo.get('temperatura', 'N/D')} C")
    c2.metric("Humedad", f"{meteo.get('humedad', 'N/D')} %")
    c1.metric("Viento", f"{meteo.get('viento_vel', 'N/D')} km/h")
    c2.metric("Direccion", meteo.get("viento_dir_texto") or "N/D")
    st.caption(f"{meteo.get('estacion_nombre') or 'Estacion desconocida'} - {meteo.get('timestamp') or 'sin timestamp'}")


def render_contexto(zari: dict, combustible: dict, firms: dict) -> None:
    st.subheader("Contexto territorial")
    st.write("ZARI:", "Dentro" if zari.get("dentro") else "Fuera")
    st.write("Zona:", zari.get("zona") or "No aplica")
    principal = combustible.get("codigo_combustible_principal")
    descripcion = combustible.get("descripcion_combustible_principal")
    st.write("Combustible principal:", f"{principal or 'N/D'} - {descripcion or 'N/D'}")
    st.write("Peligrosidad ponderada 5 km:", f"{float(combustible.get('peso') or 0.0):.2f}")
    st.progress(float(combustible.get("peso") or 0.0))
    presentes = combustible.get("combustibles_presentes") or []
    if presentes:
        tabla = pd.DataFrame(presentes)[["codigo", "descripcion", "porcentaje", "peso"]].head(8)
        st.dataframe(tabla, use_container_width=True, hide_index=True)
    else:
        st.caption("Sin combustible clasificado en el radio del foco.")
    st.metric("Focos FIRMS historicos 15 km", firms.get("n_hotspots", 0))
    st.caption(f"Anio pico: {firms.get('anio_pico') or 'N/D'} - Mes pico: {firms.get('mes_pico') or 'N/D'}")
