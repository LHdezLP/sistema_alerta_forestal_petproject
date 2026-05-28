"""FastAPI para inferencia, riesgo territorial y alertas."""

from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path
import math
import random

import cv2
import geopandas as gpd
import numpy as np
from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from shapely.geometry import Point

from api import alerts_db
from api.config import (
    AEMET_API_KEY,
    ALERT_CONFIRM_SECONDS,
    ALERT_COOLDOWN_SECONDS,
    CONF_THRESHOLD_FIRE,
    CONF_THRESHOLD_SMOKE,
    MODEL_PATH,
    MODEL_PT_FALLBACK,
    PROJECT_ROOT,
    SIMULATE_RANDOM_ALERT_POINT,
    TEMPORAL_MAX_GAP_SECONDS,
)
from api.models import FireSmokeModel, dibujar_detecciones
from api.telegram_bot import enviar_alerta_telegram
from geo_pipeline import CAMERA, CRS_CANARIAS_UTM, CRS_WGS84, GC_BBOX, RADIO_AEMET_KM, RADIO_FIRMS_KM
from geo_pipeline.aemet_client import obtener_datos_meteorologicos
from geo_pipeline.combustible_loader import cargar_combustible_gc, combustible_en_punto
from geo_pipeline.firms_loader import cargar_firms, densidad_hotspots
from geo_pipeline.risk_index import calcular_indice_riesgo
from geo_pipeline.zari_loader import cargar_zari, punto_en_zari

app = FastAPI(title="Fire Smoke Territorial API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8501", "http://127.0.0.1:8501"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
STATE = {
    "model": None,
    "zari": None,
    "comb": None,
    "firms": None,
    "risk_cache": {},
    "meteo_cache": {"ts": 0.0, "data": None},
    "last_alert_ts": 0.0,
    "temporal_sessions": {},
}
ALERT_DIR = Path(__file__).resolve().parent / "alert_images"
GEO_DIR = PROJECT_ROOT / "dashboard" / "static" / "geo"


@app.on_event("startup")
def startup():
    alerts_db.init_db()
    ALERT_DIR.mkdir(parents=True, exist_ok=True)
    STATE["model"] = FireSmokeModel(MODEL_PATH, MODEL_PT_FALLBACK)
    territoriales = PROJECT_ROOT / "Datasets Territoriales"
    STATE["zari"] = cargar_zari(territoriales / "ZARI")
    STATE["comb"] = cargar_combustible_gc(territoriales / "Modelos de Combustible por Isla" / "GRAN CANARIA")
    STATE["firms"] = cargar_firms(territoriales / "NASA Firms", GC_BBOX)


def _random_point_near_camera(radius_km: float = 5.0) -> dict:
    center = gpd.GeoSeries([Point(CAMERA["lon"], CAMERA["lat"])], crs=CRS_WGS84).to_crs(CRS_CANARIAS_UTM).iloc[0]
    angle = random.random() * 2 * math.pi
    distance = radius_km * 1000 * math.sqrt(random.random())
    point_utm = Point(center.x + math.cos(angle) * distance, center.y + math.sin(angle) * distance)
    point_wgs = gpd.GeoSeries([point_utm], crs=CRS_CANARIAS_UTM).to_crs(CRS_WGS84).iloc[0]
    return {"lat": round(point_wgs.y, 6), "lon": round(point_wgs.x, 6), "radio_origen_km": radius_km}


def _risk(force: bool = False, lat: float | None = None, lon: float | None = None) -> dict:
    lat = CAMERA["lat"] if lat is None else lat
    lon = CAMERA["lon"] if lon is None else lon
    now = time.time()
    cache_key = f"{lat:.4f},{lon:.4f}"
    cached = STATE["risk_cache"].get(cache_key)
    if not force and cached and now - cached["ts"] < 600:
        return cached["payload"]
    zari = punto_en_zari(STATE["zari"], lat, lon)
    comb = combustible_en_punto(STATE["comb"], lat, lon, 5.0)
    firms = densidad_hotspots(STATE["firms"], lat, lon, RADIO_FIRMS_KM)
    meteo = _meteo_cached(force)
    indice = calcular_indice_riesgo(zari["dentro"], comb["peso"], firms, meteo)
    payload = {"indice_riesgo": indice, "meteo": meteo, "zari": zari, "combustible": comb, "firms": firms, "camara": CAMERA, "foco": {"lat": lat, "lon": lon}}
    STATE["risk_cache"][cache_key] = {"ts": now, "payload": payload}
    return payload


def _meteo_cached(force: bool = False) -> dict:
    now = time.time()
    cached = STATE["meteo_cache"]
    if not force and cached["data"] and now - cached["ts"] < 600:
        return cached["data"]
    meteo = obtener_datos_meteorologicos(CAMERA["lat"], CAMERA["lon"], AEMET_API_KEY, RADIO_AEMET_KM)
    STATE["meteo_cache"] = {"ts": now, "data": meteo}
    return meteo


def _best_detection_for_class(detecciones: list[dict], clase: str) -> dict | None:
    candidates = [d for d in detecciones if d.get("clase") == clase]
    return max(candidates, key=lambda d: d.get("confianza", 0.0)) if candidates else None


def _temporal_confirmation(session_id: str, detecciones: list[dict]) -> tuple[dict | None, dict]:
    """Confirma alertas de video/pantalla solo si la deteccion persiste."""
    now = time.time()
    session = STATE["temporal_sessions"].setdefault(session_id, {})
    confirmed: dict | None = None
    status = {
        "modo": "temporal",
        "session_id": session_id,
        "confirm_seconds": ALERT_CONFIRM_SECONDS,
        "classes": {},
    }

    for clase in ("fire", "smoke"):
        best = _best_detection_for_class(detecciones, clase)
        state = session.get(clase)
        if best:
            if not state or now - state.get("last_seen", 0.0) > TEMPORAL_MAX_GAP_SECONDS:
                state = {
                    "first_seen": now,
                    "last_seen": now,
                    "best_conf": best["confianza"],
                    "best_detection": best,
                    "alerted": False,
                }
            else:
                state["last_seen"] = now
                if best["confianza"] >= state.get("best_conf", 0.0):
                    state["best_conf"] = best["confianza"]
                    state["best_detection"] = best
            session[clase] = state
            elapsed = now - state["first_seen"]
            status["classes"][clase] = {
                "visible": True,
                "elapsed_seconds": round(elapsed, 1),
                "confirmed": elapsed >= ALERT_CONFIRM_SECONDS,
                "already_alerted": state["alerted"],
                "best_conf": round(float(state["best_conf"]), 3),
            }
            if elapsed >= ALERT_CONFIRM_SECONDS and not state["alerted"]:
                candidate = {**state["best_detection"], "confianza": state["best_conf"]}
                if confirmed is None or candidate["confianza"] > confirmed["confianza"]:
                    confirmed = candidate
        elif state and now - state.get("last_seen", 0.0) <= TEMPORAL_MAX_GAP_SECONDS:
            elapsed = now - state["first_seen"]
            status["classes"][clase] = {
                "visible": False,
                "elapsed_seconds": round(elapsed, 1),
                "confirmed": elapsed >= ALERT_CONFIRM_SECONDS,
                "already_alerted": state["alerted"],
                "best_conf": round(float(state["best_conf"]), 3),
            }
        elif state:
            session.pop(clase, None)

    return confirmed, status


@app.get("/health")
def health():
    return {"status": "ok", "model_loaded": bool(STATE["model"] and STATE["model"].loaded), "db_ok": True}


@app.get("/screen-capture", response_class=HTMLResponse)
def screen_capture_page():
    return """
<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Fire Smoke AI - Captura de pantalla</title>
  <style>
    :root { color-scheme: dark; font-family: Inter, Segoe UI, Arial, sans-serif; }
    body { margin: 0; background: #0d1117; color: #f5f7fb; }
    main { max-width: 1080px; margin: 0 auto; padding: 28px; }
    h1 { margin: 0 0 8px; font-size: 28px; }
    p { color: #bac2cf; line-height: 1.5; }
    .bar { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; margin: 18px 0; }
    button, input { border-radius: 8px; border: 1px solid #303846; padding: 10px 14px; font-size: 15px; }
    button { background: #1f6feb; color: white; cursor: pointer; font-weight: 700; }
    button.stop { background: #b42318; }
    button:disabled { opacity: .5; cursor: not-allowed; }
    input { width: 80px; background: #161b22; color: #f5f7fb; }
    video { width: 100%; max-height: 58vh; background: #05070a; border: 1px solid #303846; border-radius: 8px; }
    pre { white-space: pre-wrap; background: #161b22; border: 1px solid #303846; border-radius: 8px; padding: 14px; min-height: 110px; }
    .status { padding: 8px 10px; border-radius: 8px; background: #1d283a; color: #d8e2f0; }
  </style>
</head>
<body>
<main>
  <h1>Deteccion por pantalla o video</h1>
  <p>Comparte una pantalla, ventana o pestana del navegador. El frontend captura frames y los envia a la API; si hay deteccion, se registra alerta, riesgo territorial y Telegram.</p>
  <div class="bar">
    <button id="start">Iniciar captura</button>
    <button id="stop" class="stop" disabled>Detener</button>
    <label>Intervalo (s) <input id="interval" type="number" min="1" step="1" value="2" /></label>
    <span id="status" class="status">Parado</span>
  </div>
  <video id="preview" autoplay muted playsinline></video>
  <h2>Ultimo resultado</h2>
  <pre id="result">Sin capturas todavia.</pre>
</main>
<script>
const startBtn = document.getElementById("start");
const stopBtn = document.getElementById("stop");
const statusEl = document.getElementById("status");
const resultEl = document.getElementById("result");
const intervalInput = document.getElementById("interval");
const video = document.getElementById("preview");
let stream = null;
let timer = null;
let sessionId = crypto.randomUUID ? crypto.randomUUID() : String(Date.now());

async function sendFrame() {
  if (!stream || video.videoWidth === 0) return;
  const canvas = document.createElement("canvas");
  canvas.width = video.videoWidth;
  canvas.height = video.videoHeight;
  canvas.getContext("2d").drawImage(video, 0, 0, canvas.width, canvas.height);
  const blob = await new Promise(resolve => canvas.toBlob(resolve, "image/jpeg", 0.9));
  const form = new FormData();
  form.append("file", blob, "screen_frame.jpg");
  form.append("temporal_confirm", "true");
  form.append("session_id", sessionId);
  try {
    const response = await fetch("/predict", { method: "POST", body: form });
    const data = await response.json();
    const n = (data.detecciones || []).length;
    const temporal = data.temporal_status || {};
    const classes = temporal.classes || {};
    const fire = classes.fire ? ` fire ${classes.fire.elapsed_seconds || 0}s` : "";
    const smoke = classes.smoke ? ` smoke ${classes.smoke.elapsed_seconds || 0}s` : "";
    statusEl.textContent = `${new Date().toLocaleTimeString()} - detecciones: ${n}${fire}${smoke} - alerta: ${data.alerta_enviada}`;
    resultEl.textContent = JSON.stringify(data, null, 2);
  } catch (err) {
    statusEl.textContent = "Error enviando frame";
    resultEl.textContent = String(err);
  }
}

startBtn.onclick = async () => {
  try {
    stream = await navigator.mediaDevices.getDisplayMedia({ video: true, audio: false });
    sessionId = crypto.randomUUID ? crypto.randomUUID() : String(Date.now());
    video.srcObject = stream;
    startBtn.disabled = true;
    stopBtn.disabled = false;
    statusEl.textContent = "Captura activa";
    const everyMs = Math.max(1, Number(intervalInput.value || 2)) * 1000;
    timer = setInterval(sendFrame, everyMs);
    stream.getVideoTracks()[0].addEventListener("ended", stopCapture);
  } catch (err) {
    statusEl.textContent = "Captura cancelada o no permitida";
    resultEl.textContent = String(err);
  }
};

function stopCapture() {
  if (timer) clearInterval(timer);
  timer = null;
  if (stream) stream.getTracks().forEach(track => track.stop());
  stream = null;
  video.srcObject = null;
  startBtn.disabled = false;
  stopBtn.disabled = true;
  statusEl.textContent = "Parado";
  fetch(`/temporal-session/${sessionId}`, { method: "DELETE" }).catch(() => {});
}
stopBtn.onclick = stopCapture;
</script>
</body>
</html>
    """


@app.get("/risk")
def risk(force: bool = False, lat: float | None = None, lon: float | None = None):
    return _risk(force=force, lat=lat, lon=lon)


@app.get("/alerts")
def alerts(limite: int = 50, clase: str | None = None):
    return alerts_db.obtener_alertas(limite, clase)


@app.delete("/alerts")
def reset_alerts():
    n = alerts_db.limpiar_alertas()
    image_count = 0
    for path in ALERT_DIR.glob("alert_*.jpg"):
        path.unlink(missing_ok=True)
        image_count += 1
    STATE["last_alert_ts"] = 0.0
    STATE["temporal_sessions"].clear()
    return {"status": "ok", "deleted": n, "images_deleted": image_count}


@app.delete("/temporal-session/{session_id}")
def clear_temporal_session(session_id: str):
    STATE["temporal_sessions"].pop(session_id, None)
    return {"status": "cleared", "session_id": session_id}


@app.post("/predict")
async def predict(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    temporal_confirm: bool = Form(False),
    session_id: str = Form("default"),
):
    model = STATE["model"]
    if not model or not model.loaded:
        raise HTTPException(status_code=503, detail="Modelo no cargado")
    data = await file.read()
    arr = np.frombuffer(data, dtype=np.uint8)
    bgr = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if bgr is None:
        raise HTTPException(status_code=400, detail="Imagen no valida")

    detecciones = model.predict(bgr, CONF_THRESHOLD_FIRE, CONF_THRESHOLD_SMOKE)
    confirmed_detection = None
    temporal_status = None
    if temporal_confirm:
        confirmed_detection, temporal_status = _temporal_confirmation(session_id, detecciones)
    should_alert = bool(confirmed_detection if temporal_confirm else detecciones)

    foco = _random_point_near_camera() if should_alert and SIMULATE_RANDOM_ALERT_POINT else {"lat": CAMERA["lat"], "lon": CAMERA["lon"]}
    risk_payload = _risk(lat=foco["lat"], lon=foco["lon"])
    imagen_url = None
    alerta = False
    if should_alert and time.time() - STATE["last_alert_ts"] >= ALERT_COOLDOWN_SECONDS:
        dibujada = dibujar_detecciones(bgr, detecciones)
        filename = f"alert_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.jpg"
        out = ALERT_DIR / filename
        cv2.imwrite(str(out), dibujada)
        imagen_url = f"/images/{filename}"
        best = confirmed_detection or max(detecciones, key=lambda d: d["confianza"])
        idx = risk_payload["indice_riesgo"]
        alerts_db.insertar_alerta(best["clase"], best["confianza"], str(out), foco["lat"], foco["lon"], idx["indice"], idx["nivel"])
        background_tasks.add_task(enviar_alerta_telegram, best["clase"], best["confianza"], idx, str(out))
        STATE["last_alert_ts"] = time.time()
        if temporal_confirm and session_id in STATE["temporal_sessions"] and best["clase"] in STATE["temporal_sessions"][session_id]:
            STATE["temporal_sessions"][session_id][best["clase"]]["alerted"] = True
        alerta = True

    return {
        "detecciones": detecciones,
        "alerta_enviada": alerta,
        "indice_riesgo": risk_payload["indice_riesgo"],
        "foco": risk_payload["foco"],
        "imagen_resultado_url": imagen_url,
        "temporal_status": temporal_status,
    }


@app.get("/images/{filename}")
def images(filename: str):
    path = ALERT_DIR / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="Imagen no encontrada")
    return FileResponse(path)


@app.get("/geo/{filename}")
def geo(filename: str):
    path = GEO_DIR / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="GeoJSON no encontrado")
    return FileResponse(path)
