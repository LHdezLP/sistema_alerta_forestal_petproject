from __future__ import annotations

import argparse
import random
import re
import shutil
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import yaml
from PIL import Image
from ultralytics import YOLO

IMAGE_EXTS = {".jpg", ".jpeg", ".png"}
SEED = 42


@dataclass
class Sample:
    block: str
    strata: str
    image: Path
    label: Path | None
    n_boxes: int
    hard_score: float = 0.0


def original_name_from_processed(path: str) -> str:
    name = Path(path).name
    return re.sub(r"^(dfire|wildfire_smoke|cloud_fog)_\d+_", "", name)


def used_original_names(manifest_dir: Path) -> set[str]:
    used: set[str] = set()
    for manifest in manifest_dir.glob("*manifest*.csv"):
        df = pd.read_csv(manifest)
        for image in df["image"].astype(str):
            used.add(original_name_from_processed(image))
    return used


def read_yolo_classes(label_path: Path) -> list[int]:
    classes: list[int] = []
    if not label_path.exists():
        return classes
    for line in label_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        parts = line.strip().split()
        if len(parts) >= 5:
            classes.append(int(float(parts[0])))
    return classes


def remap_dfire_label(src_label: Path, dst_label: Path) -> int:
    n = 0
    lines = []
    for line in src_label.read_text(encoding="utf-8", errors="ignore").splitlines():
        parts = line.strip().split()
        if len(parts) < 5:
            continue
        raw_cls = int(float(parts[0]))
        # ADAPTADO: D-Fire local declara 0=smoke, 1=fire; proyecto final usa 0=fire, 1=smoke.
        final_cls = 1 if raw_cls == 0 else 0
        lines.append(" ".join([str(final_cls), *parts[1:5]]))
        n += 1
    dst_label.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    return n


def voc_to_yolo(src_xml: Path, dst_label: Path, class_id: int = 1) -> int:
    root = ET.parse(src_xml).getroot()
    size = root.find("size")
    width = float(size.findtext("width"))
    height = float(size.findtext("height"))
    lines = []
    for obj in root.findall("object"):
        box = obj.find("bndbox")
        if box is None:
            continue
        xmin = float(box.findtext("xmin"))
        ymin = float(box.findtext("ymin"))
        xmax = float(box.findtext("xmax"))
        ymax = float(box.findtext("ymax"))
        x = ((xmin + xmax) / 2) / width
        y = ((ymin + ymax) / 2) / height
        w = (xmax - xmin) / width
        h = (ymax - ymin) / height
        if w > 0 and h > 0:
            lines.append(f"{class_id} {x:.6f} {y:.6f} {w:.6f} {h:.6f}")
    dst_label.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    return len(lines)


def collect_dfire(raw_root: Path, used: set[str]) -> list[Sample]:
    samples = []
    for image in raw_root.rglob("*"):
        if image.suffix.lower() not in IMAGE_EXTS or image.name in used:
            continue
        label = Path(str(image).replace("\\images\\", "\\labels\\")).with_suffix(".txt")
        if not label.exists():
            label = image.parents[1] / "labels" / f"{image.stem}.txt"
        classes = read_yolo_classes(label)
        if not classes:
            continue
        has_smoke = 0 in classes
        has_fire = 1 in classes
        if has_fire and has_smoke:
            strata = "dfire_both"
        elif has_fire:
            strata = "dfire_fire"
        elif has_smoke:
            strata = "dfire_smoke"
        else:
            continue
        samples.append(Sample("dfire", strata, image, label, len(classes)))
    return samples


def collect_wildfire(raw_root: Path, used: set[str]) -> list[Sample]:
    xmls = {p.stem: p for p in raw_root.rglob("*.xml")}
    samples = []
    for image in raw_root.rglob("*"):
        if image.suffix.lower() not in IMAGE_EXTS or image.name in used:
            continue
        xml = xmls.get(image.stem)
        if not xml:
            continue
        n = len(ET.parse(xml).getroot().findall("object"))
        if n:
            samples.append(Sample("wildfire_smoke", "smoke", image, xml, n))
    return samples


def collect_cloud(raw_root: Path, used: set[str]) -> list[Sample]:
    samples = []
    for image in raw_root.rglob("*"):
        if image.suffix.lower() not in IMAGE_EXTS or image.name in used:
            continue
        if image.name.startswith("._") or image.stat().st_size < 1024:
            continue
        samples.append(Sample("cloud_fog", "hard_negative", image, None, 0))
    return samples


def score_hard_negatives(samples: list[Sample], model_path: Path, max_images: int, conf: float) -> list[Sample]:
    if not samples:
        return []
    model = YOLO(str(model_path))
    scored = []
    for sample in samples[:max_images]:
        result = model.predict(str(sample.image), conf=conf, imgsz=640, verbose=False)[0]
        score = float(result.boxes.conf.max().item()) if len(result.boxes) else 0.0
        scored.append(Sample(sample.block, sample.strata, sample.image, sample.label, sample.n_boxes, score))
    return sorted(scored, key=lambda s: s.hard_score, reverse=True)


def take(samples: list[Sample], n: int, rng: random.Random) -> list[Sample]:
    if len(samples) <= n:
        return list(samples)
    copy = list(samples)
    rng.shuffle(copy)
    return copy[:n]


def split_samples(samples: list[Sample], rng: random.Random) -> list[tuple[str, Sample]]:
    by_strata: dict[str, list[Sample]] = {}
    for sample in samples:
        by_strata.setdefault(sample.strata, []).append(sample)
    out = []
    for strata_samples in by_strata.values():
        rng.shuffle(strata_samples)
        n = len(strata_samples)
        n_train = round(n * 0.70)
        n_val = round(n * 0.15)
        for i, sample in enumerate(strata_samples):
            split = "train" if i < n_train else "val" if i < n_train + n_val else "test"
            out.append((split, sample))
    rng.shuffle(out)
    return out


def copy_dataset(assignments: list[tuple[str, Sample]], out_dir: Path) -> pd.DataFrame:
    if out_dir.exists():
        shutil.rmtree(out_dir)
    rows = []
    for split in ("train", "val", "test"):
        (out_dir / "images" / split).mkdir(parents=True, exist_ok=True)
        (out_dir / "labels" / split).mkdir(parents=True, exist_ok=True)
    counters = {}
    for split, sample in assignments:
        counters[sample.block] = counters.get(sample.block, 0) + 1
        stem = f"{sample.block}_{counters[sample.block]:04d}_{sample.image.stem}"
        dst_img = out_dir / "images" / split / f"{stem}{sample.image.suffix.lower()}"
        dst_lbl = out_dir / "labels" / split / f"{stem}.txt"
        shutil.copy2(sample.image, dst_img)
        if sample.block == "dfire":
            n_boxes = remap_dfire_label(sample.label, dst_lbl)
        elif sample.block == "wildfire_smoke":
            n_boxes = voc_to_yolo(sample.label, dst_lbl, class_id=1)
        else:
            dst_lbl.write_text("", encoding="utf-8")
            n_boxes = 0
        rows.append(
            {
                "split": split,
                "block": sample.block,
                "strata": sample.strata,
                "source_image": str(sample.image),
                "source_label": str(sample.label) if sample.label else "",
                "image": str(dst_img),
                "label": str(dst_lbl),
                "n_boxes": n_boxes,
                "hard_score": sample.hard_score,
            }
        )
    yaml_path = out_dir.parent / "dataset_v4_hardneg_smoke.yaml"
    yaml_path.write_text(
        yaml.safe_dump(
            {
                "path": str(out_dir.resolve()),
                "train": "images/train",
                "val": "images/val",
                "test": "images/test",
                "nc": 2,
                "names": {0: "fire", 1: "smoke"},
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="data/processed_v4_hardneg_smoke")
    parser.add_argument("--model", default="exports/best_fire_smoke.pt")
    parser.add_argument("--dfire", type=int, default=500)
    parser.add_argument("--wildfire", type=int, default=700)
    parser.add_argument("--cloud", type=int, default=400)
    parser.add_argument("--hard-conf", type=float, default=0.10)
    args = parser.parse_args()

    rng = random.Random(SEED)
    root = Path.cwd()
    used = used_original_names(root / "data" / "processed")
    print(f"Imagenes originales excluidas por manifests previos: {len(used)}")

    dfire = collect_dfire(root / "data" / "raw" / "dfire", used)
    wildfire = collect_wildfire(root / "data" / "raw" / "wildfire_smoke", used)
    cloud = collect_cloud(root / "data" / "raw" / "cloud_fog", used)
    print(f"Candidatas no vistas: D-Fire={len(dfire)}, Wildfire={len(wildfire)}, Cloud/Fog={len(cloud)}")

    fire_only = [s for s in dfire if s.strata == "dfire_fire"]
    both = [s for s in dfire if s.strata == "dfire_both"]
    smoke_dfire = [s for s in dfire if s.strata == "dfire_smoke"]
    selected_dfire = take(fire_only, 350, rng) + take(both, 120, rng) + take(smoke_dfire, max(args.dfire - 470, 0), rng)
    if len(selected_dfire) < args.dfire:
        selected_dfire += take([s for s in dfire if s not in selected_dfire], args.dfire - len(selected_dfire), rng)
    selected_dfire = selected_dfire[: args.dfire]

    selected_wildfire = take(wildfire, args.wildfire, rng)
    rng.shuffle(cloud)
    scored_cloud = score_hard_negatives(cloud, root / args.model, max_images=len(cloud), conf=args.hard_conf)
    hard_hits = [s for s in scored_cloud if s.hard_score >= args.hard_conf]
    fallback = [s for s in scored_cloud if s.hard_score < args.hard_conf]
    selected_cloud = (hard_hits + fallback)[: args.cloud]
    print(f"Hard negatives con deteccion >= {args.hard_conf}: {len(hard_hits)}")

    selected = selected_dfire + selected_wildfire + selected_cloud
    assignments = split_samples(selected, rng)
    manifest = copy_dataset(assignments, root / args.out)
    manifest_path = root / args.out / "selection_manifest_fire_smoke_v4_hardneg_smoke.csv"
    manifest.to_csv(manifest_path, index=False)
    print(manifest.groupby(["split", "block", "strata"]).size().to_string())
    print(f"Dataset escrito en {root / args.out}")
    print(f"YAML: {root / 'data' / 'dataset_v4_hardneg_smoke.yaml'}")
    print(f"Manifest: {manifest_path}")


if __name__ == "__main__":
    main()
