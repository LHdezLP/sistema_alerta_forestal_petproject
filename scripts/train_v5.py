from __future__ import annotations

from pathlib import Path

from ultralytics import YOLO


def main() -> None:
    model = YOLO("exports/best_fire_smoke.pt")
    model.train(
        data="data/dataset_v5_all_wildfire.yaml",
        epochs=60,
        patience=12,
        batch=16,
        imgsz=640,
        optimizer="AdamW",
        lr0=0.00025,
        cos_lr=True,
        device=0,
        project=str((Path("models") / "runs").resolve()),
        name="fire_smoke_v5_all_wildfire",
        exist_ok=True,
        seed=42,
        workers=4,
        plots=True,
        save_period=10,
    )


if __name__ == "__main__":
    main()
