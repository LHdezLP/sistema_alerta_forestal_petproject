from __future__ import annotations

import shutil
from pathlib import Path

import pandas as pd
import yaml


RUN_NAME = "fire_smoke_v6_replay_mix"
SOURCES = [
    ("v3", Path("data/processed"), Path("data/processed/selection_manifest_fire_smoke_v3_balanced.csv")),
    (
        "v5",
        Path("data/processed_v5_all_wildfire"),
        Path("data/processed_v5_all_wildfire/selection_manifest_fire_smoke_v5_all_wildfire.csv"),
    ),
]


def normalise_path(path_text: str, root: Path) -> Path:
    path = Path(path_text)
    if path.is_absolute():
        return path
    return root / path


def source_key(row: pd.Series) -> str:
    if "source_image" in row and pd.notna(row["source_image"]):
        return Path(str(row["source_image"])).stem.lower()
    return Path(str(row["image"])).stem.lower()


def clean_output(out_dir: Path) -> None:
    if out_dir.exists():
        shutil.rmtree(out_dir)
    for split in ("train", "val", "test"):
        (out_dir / "images" / split).mkdir(parents=True, exist_ok=True)
        (out_dir / "labels" / split).mkdir(parents=True, exist_ok=True)


def main() -> None:
    root = Path.cwd()
    out_dir = root / "data" / "processed_v6_replay_mix"
    clean_output(out_dir)

    seen: set[str] = set()
    rows: list[dict[str, object]] = []

    for source_name, base_dir, manifest_path in SOURCES:
        manifest = pd.read_csv(root / manifest_path)
        for _, row in manifest.iterrows():
            key = f"{row['block']}::{source_key(row)}"
            if key in seen:
                continue
            seen.add(key)

            split = str(row["split"])
            src_image = normalise_path(str(row["image"]), root)
            src_label = normalise_path(str(row["label"]), root)
            suffix = src_image.suffix.lower()
            safe_stem = f"{source_name}_{src_image.stem}"
            dst_image = out_dir / "images" / split / f"{safe_stem}{suffix}"
            dst_label = out_dir / "labels" / split / f"{safe_stem}.txt"

            shutil.copy2(src_image, dst_image)
            shutil.copy2(src_label, dst_label)

            rows.append(
                {
                    "split": split,
                    "source_dataset": source_name,
                    "block": row["block"],
                    "strata": row["strata"],
                    "image": str(dst_image),
                    "label": str(dst_label),
                    "source_image": str(src_image),
                    "source_label": str(src_label),
                    "dedupe_key": key,
                    "n_boxes": int(row.get("n_boxes", 0)),
                }
            )

    manifest = pd.DataFrame(rows)
    manifest_path = out_dir / f"selection_manifest_{RUN_NAME}.csv"
    manifest.to_csv(manifest_path, index=False)

    dataset_yaml = {
        "path": str(out_dir.resolve()),
        "train": "images/train",
        "val": "images/val",
        "test": "images/test",
        "nc": 2,
        "names": {0: "fire", 1: "smoke"},
    }
    yaml_path = root / "data" / "dataset_v6_replay_mix.yaml"
    yaml_path.write_text(yaml.safe_dump(dataset_yaml, sort_keys=False), encoding="utf-8")

    counts = {0: 0, 1: 0}
    for label_path in manifest["label"]:
        for line in Path(label_path).read_text(encoding="utf-8").splitlines():
            if line.strip():
                counts[int(float(line.split()[0]))] += 1

    duplicates = len(rows) - len(set(manifest["dedupe_key"]))
    print(f"Dataset escrito en {out_dir}")
    print(f"YAML: {yaml_path}")
    print(f"Manifest: {manifest_path}")
    print(f"Imagenes: {len(manifest)}")
    print(f"Duplicados internos omitidos: {duplicates}")
    print(manifest.groupby(["split", "source_dataset", "block", "strata"]).size().to_string())
    print(f"Cajas por clase: {counts}")


if __name__ == "__main__":
    main()
