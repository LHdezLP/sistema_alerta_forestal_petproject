"""Construccion del mapa Folium del dashboard."""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path

import folium
from folium.plugins import HeatMap, MarkerCluster

from geo_pipeline import CAMERA

GEO_DIR = Path(__file__).resolve().parent / "static" / "geo"


def _load_geo(name: str) -> dict | None:
    path = GEO_DIR / name
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _fuel_color(peso: float) -> str:
    if peso < 0.3:
        return "#27ae60"
    if peso < 0.6:
        return "#f1c40f"
    if peso < 0.8:
        return "#e67e22"
    return "#e74c3c"


def _ring_opacity(base: float, peso_combustible: float) -> float:
    return min(base + float(peso_combustible or 0.0) * 0.16, 0.62)


def _destino_viento(lat: float, lon: float, grados_desde: float, distancia_km: float) -> tuple[float, float]:
    # AEMET da direccion de procedencia; sumamos 180 para dibujar hacia donde empuja el viento.
    bearing = math.radians((float(grados_desde) + 180.0) % 360.0)
    dlat = (distancia_km / 111.0) * math.cos(bearing)
    dlon = (distancia_km / (111.0 * math.cos(math.radians(lat)))) * math.sin(bearing)
    return lat + dlat, lon + dlon


def construir_mapa(
    indice_riesgo: dict,
    datos_meteo: dict,
    alertas: list,
    foco: dict,
    combustible: dict,
    capas: dict | None = None,
    firms_points=None,
) -> folium.Map:
    capas = capas or {"zari": True, "combustible": False, "firms": False, "alertas": True}
    foco_lat = foco.get("lat", CAMERA["lat"])
    foco_lon = foco.get("lon", CAMERA["lon"])
    mapa = folium.Map(location=[foco_lat, foco_lon], zoom_start=13, tiles="CartoDB positron", control_scale=True)

    zari = _load_geo("zari_gc.geojson")
    if zari and capas.get("zari", True):
        folium.GeoJson(
            zari,
            name="ZARI Gran Canaria",
            style_function=lambda _: {"fillColor": "#e74c3c", "color": "#c0392b", "weight": 2, "fillOpacity": 0.20},
            tooltip=folium.GeoJsonTooltip(fields=["ZONA"], aliases=["Zona"]),
        ).add_to(mapa)

    comb = _load_geo("combustible_gc.geojson")
    if comb and capas.get("combustible", False):
        folium.GeoJson(
            comb,
            name="Combustible",
            style_function=lambda feature: {
                "fillColor": _fuel_color(float(feature["properties"].get("peso") or 0.0)),
                "color": _fuel_color(float(feature["properties"].get("peso") or 0.0)),
                "weight": 0.5,
                "fillOpacity": 0.35,
            },
            tooltip=folium.GeoJsonTooltip(fields=["codigo", "descripcion", "peso"], aliases=["Modelo", "Descripcion", "Peso"]),
        ).add_to(mapa)

    firms = _load_geo("firms_heatmap_gc.geojson")
    if firms and capas.get("firms", False):
        heat = []
        for feature in firms.get("features", []):
            coords = feature["geometry"]["coordinates"]
            props = feature.get("properties", {})
            heat.append([coords[1], coords[0], float(props.get("frp") or 1.0)])
        HeatMap(heat, name="FIRMS historico", radius=15, blur=20, min_opacity=0.3).add_to(mapa)

    peso_combustible = float(combustible.get("peso") or 0.0)
    rings = [
        (1.0, "Riesgo inmediato", "#d73027", _ring_opacity(0.28, peso_combustible), None),
        (2.5, "Riesgo alto", "#fc8d59", _ring_opacity(0.18, peso_combustible), "8,6"),
        (5.0, "Riesgo potencial", "#fee08b", _ring_opacity(0.09, peso_combustible), "2,8"),
    ]
    for radio, label, color, opacidad, dash in rings:
        folium.Circle(
            [foco_lat, foco_lon],
            radius=radio * 1000,
            color=color,
            fill=True,
            fill_color=color,
            fill_opacity=opacidad,
            dash_array=dash,
            tooltip=f"{label}: {radio} km - combustible {peso_combustible:.2f}",
        ).add_to(mapa)

    ultima = alertas[0] if alertas else None
    icon_color = "gray"
    popup = f"{CAMERA['nombre']}<br>Ultima deteccion: {ultima['clase'] if ultima else 'sin alertas'}"
    folium.Marker(
        [CAMERA["lat"], CAMERA["lon"]],
        tooltip=CAMERA["nombre"],
        popup=popup,
        icon=folium.Icon(color=icon_color, icon="camera", prefix="fa"),
    ).add_to(mapa)

    if datos_meteo and not datos_meteo.get("error") and datos_meteo.get("viento_dir") is not None:
        viento_vel = float(datos_meteo.get("viento_vel") or 0.0)
        distancia = min(max(viento_vel / 8.0, 0.8), 3.5)
        end_lat, end_lon = _destino_viento(foco_lat, foco_lon, float(datos_meteo["viento_dir"]), distancia)
        factor_viento = indice_riesgo.get("componentes", {}).get("viento", 0.0)
        factor_temp = indice_riesgo.get("componentes", {}).get("temperatura", 0.0)
        popup = (
            f"Viento: {viento_vel:.1f} km/h {datos_meteo.get('viento_dir_texto') or ''}<br>"
            f"Temperatura: {datos_meteo.get('temperatura')} C<br>"
            f"Factor viento: {factor_viento:.2f}<br>"
            f"Factor temperatura: {factor_temp:.2f}"
        )
        folium.PolyLine(
            [[foco_lat, foco_lon], [end_lat, end_lon]],
            color="#2980b9",
            weight=4,
            opacity=0.85,
            tooltip=popup,
        ).add_to(mapa)
        folium.RegularPolygonMarker(
            [end_lat, end_lon],
            number_of_sides=3,
            radius=9,
            rotation=float(datos_meteo["viento_dir"]),
            color="#2980b9",
            fill=True,
            fill_color="#2980b9",
            fill_opacity=0.9,
            tooltip=popup,
        ).add_to(mapa)

    folium.Marker(
        [foco_lat, foco_lon],
        tooltip="Foco seleccionado",
        popup=(
            f"Foco seleccionado<br>"
            f"Riesgo: {indice_riesgo.get('nivel')} ({indice_riesgo.get('indice', 0):.2f})<br>"
            f"Combustible principal: {combustible.get('codigo_combustible_principal') or combustible.get('codigo_predominante') or 'N/D'}<br>"
            f"Combustible ponderado 5 km: {peso_combustible:.2f}"
        ),
        icon=folium.Icon(color="red", icon="map-marker", prefix="fa"),
    ).add_to(mapa)

    if datos_meteo and not datos_meteo.get("error") and datos_meteo.get("distancia_km") is not None:
        folium.Marker(
            [CAMERA["lat"] + 0.01, CAMERA["lon"] + 0.01],
            tooltip="Estacion AEMET mas cercana",
            popup=(
                f"{datos_meteo.get('estacion_nombre')}<br>"
                f"Temp: {datos_meteo.get('temperatura')} C<br>"
                f"Viento: {datos_meteo.get('viento_vel')} km/h {datos_meteo.get('viento_dir_texto')}"
            ),
            icon=folium.Icon(color="blue", icon="cloud", prefix="fa"),
        ).add_to(mapa)

    cluster = MarkerCluster(name="Alertas recientes").add_to(mapa) if capas.get("alertas", True) else None
    ahora = datetime.now(timezone.utc)
    for alerta in alertas:
        try:
            ts = datetime.fromisoformat(alerta["timestamp"].replace("Z", "+00:00"))
            if (ahora - ts).total_seconds() > 24 * 3600:
                continue
        except Exception:
            pass
        if cluster is not None:
            folium.CircleMarker(
                [alerta.get("lat") or CAMERA["lat"], alerta.get("lon") or CAMERA["lon"]],
                radius=8,
                color="#c0392b",
                fill=True,
                fill_opacity=0.45,
                popup=f"{alerta.get('clase')} {float(alerta.get('confianza', 0)):.0%}",
            ).add_to(cluster)

    return mapa
