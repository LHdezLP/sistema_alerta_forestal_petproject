from __future__ import annotations

from ultralytics import YOLO


def main() -> None:
    model = YOLO("exports/best_fire_smoke.pt")
    model.train(
        data="data/dataset_v4_hardneg_smoke.yaml",
        epochs=50,
        patience=10,
        batch=16,
        imgsz=640,
        optimizer="AdamW",
        lr0=0.0003,
        cos_lr=True,
        device=0,
        project="models/runs",
        name="fire_smoke_v4_hardneg_smoke",
        exist_ok=True,
        seed=42,
        workers=4,
        plots=True,
        save_period=10,
    )


if __name__ == "__main__":
    main()
