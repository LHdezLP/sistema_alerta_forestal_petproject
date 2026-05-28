"""Pipeline territorial para el prototipo de alerta forestal."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

CAMERA = {
    "nombre": "Camara Forestal - Tejeda GC (simulada)",
    "lat": 27.9938,
    "lon": -15.5963,
    "descripcion": (
        "Punto de vigilancia simulado en el termino municipal de Tejeda, "
        "area afectada por el incendio de agosto de 2023."
    ),
}

RADIO_ANILLOS_KM = [1.0, 2.5, 5.0]
RADIO_FIRMS_KM = 15.0
RADIO_AEMET_KM = 50.0

GC_BBOX = {
    "lon_min": -15.85,
    "lon_max": -15.35,
    "lat_min": 27.70,
    "lat_max": 28.20,
}

CRS_WGS84 = "EPSG:4326"
CRS_CANARIAS_UTM = "EPSG:32628"
