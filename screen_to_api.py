"""Captura pantalla/video y envia frames a la API del aplicativo.

Uso tipico:
    python screen_to_api.py --show --interval 2

Poner YouTube a pantalla completa antes de lanzarlo. Cada N segundos se envia un
frame a /predict, por lo que el flujo completo registra alerta, riesgo y Telegram.
"""

from __future__ import annotations

import argparse
import time

import cv2
import mss
import numpy as np
import requests


def parse_region(value: str | None):
    if not value:
        return None
    x, y, w, h = [int(v.strip()) for v in value.split(",")]
    return {"left": x, "top": y, "width": w, "height": h}


def post_frame(api_base: str, frame: np.ndarray) -> dict:
    ok, encoded = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
    if not ok:
        raise RuntimeError("No se pudo codificar el frame como JPG")
    files = {"file": ("screen_frame.jpg", encoded.tobytes(), "image/jpeg")}
    data = {"temporal_confirm": "true", "session_id": "screen_to_api"}
    response = requests.post(f"{api_base.rstrip('/')}/predict", files=files, data=data, timeout=30)
    response.raise_for_status()
    return response.json()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api", default="http://127.0.0.1:8000")
    parser.add_argument("--interval", type=float, default=2.0, help="Segundos entre frames enviados")
    parser.add_argument("--screen-region", default=None, help="x,y,w,h. Ejemplo: 0,0,1920,1080")
    parser.add_argument("--show", action="store_true")
    args = parser.parse_args()

    last_send = 0.0
    with mss.mss() as sct:
        monitor = parse_region(args.screen_region) or sct.monitors[1]
        print("Captura activa. Pulsa q en la ventana para parar.")
        while True:
            shot = np.array(sct.grab(monitor))
            frame = cv2.cvtColor(shot, cv2.COLOR_BGRA2BGR)
            now = time.time()
            if now - last_send >= args.interval:
                try:
                    result = post_frame(args.api, frame)
                    detecciones = result.get("detecciones", [])
                    foco = result.get("foco", {})
                    print(
                        f"{time.strftime('%H:%M:%S')} detecciones={len(detecciones)} "
                        f"alerta={result.get('alerta_enviada')} foco={foco}"
                    )
                except Exception as exc:  # noqa: BLE001
                    print(f"Error enviando frame: {exc}")
                last_send = now

            if args.show:
                cv2.imshow("Screen to API", frame)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break
            else:
                time.sleep(0.05)

    if args.show:
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
