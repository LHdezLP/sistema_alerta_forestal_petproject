"""Inferencia YOLOv8 mediante ONNX, con fallback opcional a Ultralytics .pt."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

CLASSES = {0: "fire", 1: "smoke"}
COLORS = {"fire": (0, 69, 255), "smoke": (160, 160, 160)}


def _letterbox(img: np.ndarray, size: int = 640):
    h, w = img.shape[:2]
    scale = min(size / h, size / w)
    nh, nw = int(round(h * scale)), int(round(w * scale))
    resized = cv2.resize(img, (nw, nh), interpolation=cv2.INTER_LINEAR)
    canvas = np.full((size, size, 3), 114, dtype=np.uint8)
    top, left = (size - nh) // 2, (size - nw) // 2
    canvas[top : top + nh, left : left + nw] = resized
    return canvas, scale, left, top


def _iou(box, boxes):
    x1 = np.maximum(box[0], boxes[:, 0])
    y1 = np.maximum(box[1], boxes[:, 1])
    x2 = np.minimum(box[2], boxes[:, 2])
    y2 = np.minimum(box[3], boxes[:, 3])
    inter = np.maximum(0, x2 - x1) * np.maximum(0, y2 - y1)
    area1 = (box[2] - box[0]) * (box[3] - box[1])
    area2 = (boxes[:, 2] - boxes[:, 0]) * (boxes[:, 3] - boxes[:, 1])
    return inter / np.maximum(area1 + area2 - inter, 1e-6)


def _nms(dets, iou_thr=0.45):
    if not dets:
        return []
    out = []
    for cls in sorted({d["class_id"] for d in dets}):
        cls_dets = [d for d in dets if d["class_id"] == cls]
        boxes = np.array([d["bbox"] for d in cls_dets], dtype=np.float32)
        scores = np.array([d["confianza"] for d in cls_dets], dtype=np.float32)
        order = scores.argsort()[::-1]
        while order.size:
            i = order[0]
            out.append(cls_dets[int(i)])
            if order.size == 1:
                break
            keep = _iou(boxes[i], boxes[order[1:]]) < iou_thr
            order = order[1:][keep]
    return out


class FireSmokeModel:
    def __init__(self, model_path: str, pt_fallback: str | None = None):
        self.model_path = Path(model_path)
        self.backend = None
        self.session = None
        self.pt_model = None
        if self.model_path.exists() and self.model_path.suffix.lower() == ".onnx":
            import onnxruntime as ort

            self.session = ort.InferenceSession(str(self.model_path), providers=["CPUExecutionProvider"])
            self.input_name = self.session.get_inputs()[0].name
            self.backend = "onnx"
        elif pt_fallback and Path(pt_fallback).exists():
            from ultralytics import YOLO

            self.pt_model = YOLO(str(pt_fallback))
            self.backend = "pt"

    @property
    def loaded(self) -> bool:
        return self.backend is not None

    def predict(self, bgr: np.ndarray, conf_fire: float, conf_smoke: float) -> list[dict]:
        if self.backend == "pt":
            results = self.pt_model.predict(bgr, conf=min(conf_fire, conf_smoke), verbose=False)[0]
            dets = []
            for box in results.boxes:
                cls_id = int(box.cls.item())
                cls = CLASSES.get(cls_id, str(cls_id))
                conf = float(box.conf.item())
                if (cls == "fire" and conf < conf_fire) or (cls == "smoke" and conf < conf_smoke):
                    continue
                dets.append({"clase": cls, "class_id": cls_id, "confianza": conf, "bbox": [round(float(v), 2) for v in box.xyxy[0].tolist()]})
            return dets
        if self.backend != "onnx":
            return []

        img, scale, pad_x, pad_y = _letterbox(bgr, 640)
        rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
        tensor = np.transpose(rgb, (2, 0, 1))[None]
        pred = self.session.run(None, {self.input_name: tensor})[0]
        pred = np.squeeze(pred)
        if pred.shape[0] < pred.shape[1]:
            pred = pred.T

        raw = []
        h0, w0 = bgr.shape[:2]
        for row in pred:
            scores = row[4:6]
            cls_id = int(np.argmax(scores))
            conf = float(scores[cls_id])
            cls = CLASSES.get(cls_id, str(cls_id))
            if (cls == "fire" and conf < conf_fire) or (cls == "smoke" and conf < conf_smoke):
                continue
            x, y, w, h = row[:4]
            x1 = (x - w / 2 - pad_x) / scale
            y1 = (y - h / 2 - pad_y) / scale
            x2 = (x + w / 2 - pad_x) / scale
            y2 = (y + h / 2 - pad_y) / scale
            bbox = [
                float(np.clip(x1, 0, w0)),
                float(np.clip(y1, 0, h0)),
                float(np.clip(x2, 0, w0)),
                float(np.clip(y2, 0, h0)),
            ]
            raw.append({"clase": cls, "class_id": cls_id, "confianza": conf, "bbox": bbox})
        final = _nms(raw)
        for d in final:
            d["bbox"] = [round(float(v), 2) for v in d["bbox"]]
        return final


def dibujar_detecciones(bgr: np.ndarray, detecciones: list[dict]) -> np.ndarray:
    out = bgr.copy()
    for det in detecciones:
        x1, y1, x2, y2 = map(int, det["bbox"])
        cls = det["clase"]
        color = COLORS.get(cls, (255, 255, 255))
        cv2.rectangle(out, (x1, y1), (x2, y2), color, 2)
        label = f"{cls} {det['confianza']:.2f}"
        cv2.putText(out, label, (x1, max(20, y1 - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
    return out
