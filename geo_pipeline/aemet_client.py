"""Cliente defensivo para AEMET OpenData."""

from __future__ import annotations

import math
from typing import Any

import requests


def _error(msg: str) -> dict:
    return {
        "estacion_nombre": None,
        "estacion_id": None,
        "distancia_km": None,
        "temperatura": None,
        "humedad": None,
        "viento_vel": None,
        "viento_dir": None,
        "viento_dir_texto": None,
        "precipitacion": None,
        "timestamp": None,
        "error": msg,
    }


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * r * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def grados_a_texto(grados: float | None) -> str | None:
    if grados is None:
        return None
    puntos = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSO", "SO", "OSO", "O", "ONO", "NO", "NNO"]
    return puntos[int((float(grados) + 11.25) // 22.5) % 16]


def _to_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(str(value).replace(",", "."))
    except ValueError:
        return None


def obtener_datos_meteorologicos(lat: float, lon: float, api_key: str, radio_km: float = 50.0) -> dict:
    if not api_key:
        return _error("AEMET_API_KEY no configurada")
    try:
        url = "https://opendata.aemet.es/opendata/api/observacion/convencional/todas"
        first = requests.get(url, headers={"api_key": api_key}, timeout=15)
        first.raise_for_status()
        data_url = first.json().get("datos")
        if not data_url:
            return _error("AEMET no devolvio URL de datos")
        second = requests.get(data_url, timeout=20)
        second.raise_for_status()
        estaciones = second.json()
    except Exception as exc:  # noqa: BLE001
        return _error(f"Fallo consultando AEMET: {exc}")

    candidatas = []
    for obs in estaciones:
        elat = _to_float(obs.get("lat"))
        elon = _to_float(obs.get("lon"))
        if elat is None or elon is None:
            continue
        dist = haversine_km(lat, lon, elat, elon)
        if dist <= radio_km:
            candidatas.append((dist, obs))
    if not candidatas:
        return _error(f"Sin estaciones AEMET en {radio_km} km")

    dist, obs = sorted(candidatas, key=lambda x: x[0])[0]
    viento_dir = _to_float(obs.get("dv"))
    return {
        "estacion_nombre": obs.get("ubi"),
        "estacion_id": obs.get("idema"),
        "distancia_km": round(dist, 2),
        "temperatura": _to_float(obs.get("ta")),
        "humedad": _to_float(obs.get("hr")),
        "viento_vel": _to_float(obs.get("vv")),
        "viento_dir": viento_dir,
        "viento_dir_texto": grados_a_texto(viento_dir),
        "precipitacion": _to_float(obs.get("prec")),
        "timestamp": obs.get("fint"),
        "error": None,
    }
