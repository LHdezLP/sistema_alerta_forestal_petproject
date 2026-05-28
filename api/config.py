"""Configuracion por variables de entorno."""

from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv(PROJECT_ROOT / ".env")

AEMET_API_KEY = os.getenv("AEMET_API_KEY", "")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
MODEL_PATH = os.getenv("MODEL_PATH", str(PROJECT_ROOT / "exports" / "best_fire_smoke.onnx"))
MODEL_PT_FALLBACK = os.getenv("MODEL_PT_FALLBACK", str(PROJECT_ROOT / "exports" / "best_fire_smoke.pt"))
CONF_THRESHOLD_FIRE = float(os.getenv("CONF_THRESHOLD_FIRE", "0.25"))
CONF_THRESHOLD_SMOKE = float(os.getenv("CONF_THRESHOLD_SMOKE", "0.10"))
ALERT_COOLDOWN_SECONDS = int(os.getenv("ALERT_COOLDOWN_SECONDS", "30"))
SIMULATE_RANDOM_ALERT_POINT = os.getenv("SIMULATE_RANDOM_ALERT_POINT", "1") == "1"
ALERT_CONFIRM_SECONDS = float(os.getenv("ALERT_CONFIRM_SECONDS", "5"))
TEMPORAL_MAX_GAP_SECONDS = float(os.getenv("TEMPORAL_MAX_GAP_SECONDS", "4"))
