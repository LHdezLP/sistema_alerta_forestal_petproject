"""Inference utility for the YOLOv8 fire/smoke detector.

The script is intentionally self-contained: with a trained model in
exports/best_fire_smoke.pt it can process images, folders, videos, GIFs and
screen captures without needing the notebooks.
"""

from __future__ import annotations

import argparse
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

import cv2
import imageio.v2 as imageio
import numpy as np
from tqdm import tqdm
from ultralytics import YOLO


IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tiff", ".tif"}
VIDEO_EXTS = {".mp4", ".avi", ".mov", ".mkv"}
GIF_EXTS = {".gif"}
COLORS = {
    "fire": (0, 69, 255),      # RGB #FF4500 converted to BGR for OpenCV
    "smoke": (160, 160, 160),  # RGB #A0A0A0 converted to BGR
}
NO_DETECTIONS_COLOR = (0, 200, 0)


@dataclass
class RunStats:
    frames: int = 0
    elapsed: float = 0.0
    detections: dict[str, int] = field(default_factory=lambda: {"fire": 0, "smoke": 0})
    outputs: list[Path] = field(default_factory=list)

    def add_result(self, result) -> None:
        if result.boxes is None:
            return
        names = result.names or {}
        for cls_id in result.boxes.cls.cpu().numpy().astype(int).tolist():
            label = str(names.get(cls_id, cls_id)).lower()
            if label in self.detections:
                self.detections[label] += 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run YOLOv8 fire/smoke inference on images, videos, GIFs or screen capture."
    )
    parser.add_argument("--source", required=True, help='Path to media or "screen".')
    parser.add_argument("--model", default="exports/best_fire_smoke.pt", help="Path to .pt model.")
    parser.add_argument("--conf", type=float, default=0.25, help="Confidence threshold.")
    parser.add_argument("--iou", type=float, default=0.45, help="NMS IoU threshold.")
    parser.add_argument("--imgsz", type=int, default=640, help="Model input size.")
    parser.add_argument("--output", default="inference_results", help="Output folder.")
    parser.add_argument("--show", action="store_true", help="Show OpenCV window while processing.")
    parser.add_argument(
        "--screen-region",
        default=None,
        help='Screen region as "x,y,w,h" when --source screen.',
    )
    parser.add_argument("--device", default="0", help='Device: "0" for GPU or "cpu".')
    return parser.parse_args()


def ensure_model(model_path: Path) -> None:
    if not model_path.exists():
        raise FileNotFoundError(
            f"Model not found: {model_path}. Train/export first or pass --model path/to/model.pt"
        )


def iter_images(source: Path) -> list[Path]:
    if source.is_file() and source.suffix.lower() in IMAGE_EXTS:
        return [source]
    if source.is_dir():
        return sorted(p for p in source.rglob("*") if p.suffix.lower() in IMAGE_EXTS)
    raise ValueError(f"Unsupported image source: {source}")


def safe_output_name(path: Path, root: Path | None = None) -> str:
    if root and root.is_dir():
        try:
            rel = path.relative_to(root)
            return "__".join(rel.parts)
        except ValueError:
            pass
    return path.name


def draw_text(
    frame: np.ndarray,
    text: str,
    origin: tuple[int, int],
    color: tuple[int, int, int],
    scale: float = 0.55,
    thickness: int = 1,
) -> None:
    x, y = origin
    font = cv2.FONT_HERSHEY_SIMPLEX
    (tw, th), baseline = cv2.getTextSize(text, font, scale, thickness)
    cv2.rectangle(frame, (x, max(0, y - th - baseline - 4)), (x + tw + 6, y + 4), (0, 0, 0), -1)
    cv2.putText(frame, text, (x + 3, y), font, scale, color, thickness, cv2.LINE_AA)


def draw_detections(
    frame: np.ndarray,
    result,
    model_name: str,
    conf_threshold: float,
    fps: float | None = None,
) -> np.ndarray:
    annotated = frame.copy()
    boxes = result.boxes
    names = result.names or {}

    if boxes is None or len(boxes) == 0:
        draw_text(annotated, "No detections", (10, 28), NO_DETECTIONS_COLOR, scale=0.7, thickness=2)
    else:
        xyxy = boxes.xyxy.cpu().numpy()
        cls_ids = boxes.cls.cpu().numpy().astype(int)
        confs = boxes.conf.cpu().numpy()
        for box, cls_id, score in zip(xyxy, cls_ids, confs):
            label = str(names.get(int(cls_id), cls_id))
            color = COLORS.get(label.lower(), (255, 255, 255))
            x1, y1, x2, y2 = [int(v) for v in box]
            cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)
            draw_text(annotated, f"{label} {score:.2f}", (x1, max(20, y1 - 6)), color)

    meta = f"{model_name} | conf {conf_threshold:.2f}"
    if fps is not None:
        meta = f"FPS {fps:.1f} | " + meta
    (tw, _), _ = cv2.getTextSize(meta, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 1)
    draw_text(annotated, meta, (max(10, annotated.shape[1] - tw - 18), 28), (255, 255, 255))
    return annotated


def predict_frame(model: YOLO, frame: np.ndarray, args: argparse.Namespace):
    start = time.perf_counter()
    result = model.predict(
        frame,
        conf=args.conf,
        iou=args.iou,
        imgsz=args.imgsz,
        device=args.device,
        verbose=False,
    )[0]
    elapsed = time.perf_counter() - start
    return result, elapsed


def process_images(model: YOLO, args: argparse.Namespace) -> RunStats:
    source = Path(args.source)
    images = iter_images(source)
    if not images:
        raise ValueError(f"No supported images found in {source}")

    output_dir = Path(args.output) / "images"
    output_dir.mkdir(parents=True, exist_ok=True)
    stats = RunStats()
    start_total = time.perf_counter()

    for image_path in tqdm(images, desc="Images"):
        frame = cv2.imread(str(image_path))
        if frame is None:
            print(f"[WARN] Could not read {image_path}")
            continue
        result, infer_time = predict_frame(model, frame, args)
        annotated = draw_detections(frame, result, Path(args.model).name, args.conf)
        out_path = output_dir / safe_output_name(image_path, source if source.is_dir() else None)
        cv2.imwrite(str(out_path), annotated)

        names = result.names or {}
        detected = []
        if result.boxes is not None:
            for cls_id, score in zip(result.boxes.cls.cpu().numpy(), result.boxes.conf.cpu().numpy()):
                detected.append(f"{names.get(int(cls_id), int(cls_id))}:{score:.2f}")
        print(f"{image_path.name}: {', '.join(detected) if detected else 'No detections'} ({infer_time*1000:.1f} ms)")

        stats.frames += 1
        stats.add_result(result)
        stats.outputs.append(out_path)

    stats.elapsed = time.perf_counter() - start_total
    return stats


def open_video_writer(path: Path, fps: float, width: int, height: int) -> cv2.VideoWriter:
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    return cv2.VideoWriter(str(path), fourcc, max(fps, 1.0), (width, height))


def maybe_show(window_name: str, frame: np.ndarray, enabled: bool) -> bool:
    if not enabled:
        return True
    cv2.imshow(window_name, frame)
    return (cv2.waitKey(1) & 0xFF) != ord("q")


def process_video(model: YOLO, args: argparse.Namespace) -> RunStats:
    source = Path(args.source)
    cap = cv2.VideoCapture(str(source))
    if not cap.isOpened():
        raise ValueError(f"Could not open video: {source}")

    fps_in = cap.get(cv2.CAP_PROP_FPS) or 25.0
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)

    output_dir = Path(args.output) / "videos"
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / f"{source.stem}_detections.mp4"
    writer = open_video_writer(out_path, fps_in, width, height)

    stats = RunStats(outputs=[out_path])
    start_total = time.perf_counter()
    progress = tqdm(total=total or None, desc="Video frames")

    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            result, infer_time = predict_frame(model, frame, args)
            fps_now = 1.0 / max(infer_time, 1e-6)
            annotated = draw_detections(frame, result, Path(args.model).name, args.conf, fps=fps_now)
            writer.write(annotated)

            stats.frames += 1
            stats.add_result(result)
            progress.set_postfix({"fps": f"{fps_now:.1f}"})
            progress.update(1)

            if not maybe_show("Fire/smoke inference", annotated, args.show):
                break
    finally:
        progress.close()
        cap.release()
        writer.release()
        if args.show:
            cv2.destroyAllWindows()

    stats.elapsed = time.perf_counter() - start_total
    return stats


def process_gif(model: YOLO, args: argparse.Namespace) -> RunStats:
    source = Path(args.source)
    output_dir = Path(args.output) / "gifs"
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / f"{source.stem}_detections.gif"

    reader = imageio.get_reader(str(source))
    meta = reader.get_meta_data()
    duration = meta.get("duration", 100)
    frames_rgb = []
    stats = RunStats(outputs=[out_path])
    start_total = time.perf_counter()

    try:
        for frame_rgb in tqdm(reader, desc="GIF frames"):
            frame_bgr = cv2.cvtColor(np.asarray(frame_rgb), cv2.COLOR_RGB2BGR)
            result, infer_time = predict_frame(model, frame_bgr, args)
            fps_now = 1.0 / max(infer_time, 1e-6)
            annotated_bgr = draw_detections(frame_bgr, result, Path(args.model).name, args.conf, fps=fps_now)
            frames_rgb.append(cv2.cvtColor(annotated_bgr, cv2.COLOR_BGR2RGB))

            stats.frames += 1
            stats.add_result(result)
    finally:
        reader.close()

    imageio.mimsave(str(out_path), frames_rgb, duration=duration / 1000 if duration > 10 else duration)
    stats.elapsed = time.perf_counter() - start_total
    return stats


def parse_screen_region(region: str | None) -> dict[str, int] | None:
    if not region:
        return None
    try:
        x, y, w, h = [int(part.strip()) for part in region.split(",")]
    except ValueError as exc:
        raise ValueError('--screen-region must use the format "x,y,w,h"') from exc
    if w <= 0 or h <= 0:
        raise ValueError("Screen region width and height must be positive")
    return {"left": x, "top": y, "width": w, "height": h}


def process_screen(model: YOLO, args: argparse.Namespace) -> RunStats:
    import mss

    output_dir = Path(args.output) / "screen"
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / time.strftime("screen_detections_%Y%m%d_%H%M%S.mp4")

    # To locate a YouTube video region in Chrome, put the browser where it will
    # stay during capture, take a screenshot, and note the pixel coordinates of
    # the video rectangle: x,y for the top-left corner and w,h for its size.
    # Pass those values as --screen-region x,y,w,h. No browser automation is
    # needed; mss only captures the pixels in that rectangle.
    region = parse_screen_region(args.screen_region)
    stats = RunStats(outputs=[out_path])
    start_total = time.perf_counter()

    with mss.mss() as sct:
        monitor = region or sct.monitors[1]
        width = int(monitor["width"])
        height = int(monitor["height"])
        writer = open_video_writer(out_path, 20.0, width, height)
        print("Screen capture started. Press q in the OpenCV window to stop.")
        try:
            while True:
                shot = np.asarray(sct.grab(monitor))
                frame = cv2.cvtColor(shot, cv2.COLOR_BGRA2BGR)
                result, infer_time = predict_frame(model, frame, args)
                fps_now = 1.0 / max(infer_time, 1e-6)
                annotated = draw_detections(frame, result, Path(args.model).name, args.conf, fps=fps_now)
                writer.write(annotated)

                stats.frames += 1
                stats.add_result(result)
                if not maybe_show("Fire/smoke screen inference", annotated, True):
                    break
        finally:
            writer.release()
            cv2.destroyAllWindows()

    stats.elapsed = time.perf_counter() - start_total
    print_summary(stats)
    return stats


def dispatch(model: YOLO, args: argparse.Namespace) -> RunStats:
    if args.source.lower() == "screen":
        return process_screen(model, args)

    source = Path(args.source)
    if not source.exists():
        raise FileNotFoundError(f"Source not found: {source}")
    suffix = source.suffix.lower()
    if source.is_dir() or suffix in IMAGE_EXTS:
        return process_images(model, args)
    if suffix in VIDEO_EXTS:
        return process_video(model, args)
    if suffix in GIF_EXTS:
        return process_gif(model, args)
    raise ValueError(f"Unsupported source type: {source}")


def print_summary(stats: RunStats) -> None:
    mean_ms = (stats.elapsed / stats.frames * 1000) if stats.frames else 0.0
    print("\nInference summary")
    print("-----------------")
    print(f"Frames/images processed: {stats.frames}")
    print(f"Total time: {stats.elapsed:.2f} s")
    print(f"Mean time per frame: {mean_ms:.1f} ms")
    print(f"Detections: {stats.detections.get('fire', 0)} fire, {stats.detections.get('smoke', 0)} smoke")
    print("Outputs:")
    for path in stats.outputs:
        print(f"  {path}")


def main() -> None:
    args = parse_args()
    model_path = Path(args.model)
    ensure_model(model_path)
    model = YOLO(str(model_path))
    stats = dispatch(model, args)
    if args.source.lower() != "screen":
        print_summary(stats)


if __name__ == "__main__":
    main()
