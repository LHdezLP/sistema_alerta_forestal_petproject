"""Envio opcional de alertas por Telegram."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

import requests

from api.config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

logger = logging.getLogger(__name__)


def enviar_alerta_telegram(clase: str, confianza: float, indice_riesgo: dict, imagen_path: str | None = None):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.warning("Telegram no configurado; alerta no enviada")
        return

    nivel = indice_riesgo.get("nivel", "N/D")
    indice = indice_riesgo.get("indice", 0.0)
    mensaje = (
        "ALERTA DE INCENDIO FORESTAL\n"
        "----------------------------\n"
        f"Deteccion: {clase.upper()}\n"
        f"Confianza: {confianza:.0%}\n"
        "Zona: Tejeda, Gran Canaria\n"
        f"Riesgo: {nivel} ({indice:.2f})\n"
        "----------------------------\n"
        f"Hora UTC: {datetime.now(timezone.utc).strftime('%H:%M:%S')}"
    )
    try:
        base = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
        if imagen_path and Path(imagen_path).exists():
            with open(imagen_path, "rb") as fh:
                r = requests.post(
                    f"{base}/sendPhoto",
                    data={"chat_id": TELEGRAM_CHAT_ID, "caption": mensaje},
                    files={"photo": fh},
                    timeout=15,
                )
        else:
            r = requests.post(
                f"{base}/sendMessage",
                data={"chat_id": TELEGRAM_CHAT_ID, "text": mensaje},
                timeout=15,
            )
        r.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Fallo enviando Telegram: %s", exc)
