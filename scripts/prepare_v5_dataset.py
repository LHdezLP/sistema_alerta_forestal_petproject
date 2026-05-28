from __future__ import annotations

import random
from pathlib import Path

import pandas as pd

from prepare_v4_dataset import (
    SEED,
    collect_cloud,
    collect_dfire,
    collect_wildfire,
    copy_dataset,
    split_samples,
    take,
    used_original_names,
)


def main() -> None:
    root = Path.cwd()
    rng = random.Random(SEED)
    used = used_original_names(root / "data" / "processed")

    dfire = collect_dfire(root / "data" / "raw" / "dfire", used)
    wildfire = collect_wildfire(root / "data" / "raw" / "wildfire_smoke", used)
    cloud = collect_cloud(root / "data" / "raw" / "cloud_fog", used)

    fire_only = [s for s in dfire if s.strata == "dfire_fire"]
    both = [s for s in dfire if s.strata == "dfire_both"]
    smoke_dfire = [s for s in dfire if s.strata == "dfire_smoke"]

    selected_dfire = (
        take(fire_only, 600, rng)
        + take(both, 170, rng)
        + take(smoke_dfire, 30, rng)
    )
    selected_wildfire = list(wildfire)
    selected_cloud = list(cloud)

    selected = selected_dfire + selected_wildfire + selected_cloud
    assignments = split_samples(selected, rng)
    out_dir = root / "data" / "processed_v5_all_wildfire"
    manifest = copy_dataset(assignments, out_dir)

    yaml_src = root / "data" / "dataset_v4_hardneg_smoke.yaml"
    yaml_dst = root / "data" / "dataset_v5_all_wildfire.yaml"
    text = yaml_src.read_text(encoding="utf-8")
    text = text.replace(str((root / "data" / "processed_v4_hardneg_smoke").resolve()), str(out_dir.resolve()))
    yaml_dst.write_text(text, encoding="utf-8")
    if (root / "data" / "processed_v4_hardneg_smoke").exists():
        yaml_src.write_text(
            text.replace(str(out_dir.resolve()), str((root / "data" / "processed_v4_hardneg_smoke").resolve())),
            encoding="utf-8",
        )

    manifest_path = out_dir / "selection_manifest_fire_smoke_v5_all_wildfire.csv"
    manifest.to_csv(manifest_path, index=False)

    print(f"Imagenes originales excluidas por manifests v1-v3: {len(used)}")
    print(f"Candidatas no vistas: D-Fire={len(dfire)}, Wildfire={len(wildfire)}, Cloud/Fog={len(cloud)}")
    print(f"Seleccionadas: D-Fire={len(selected_dfire)}, Wildfire={len(selected_wildfire)}, Cloud/Fog={len(selected_cloud)}")
    print(manifest.groupby(["split", "block", "strata"]).size().to_string())
    print("Cajas por clase:")
    counts = {0: 0, 1: 0}
    for label in manifest["label"]:
        for line in Path(label).read_text(encoding="utf-8").splitlines():
            if line.strip():
                counts[int(float(line.split()[0]))] += 1
    print(counts)
    print(f"Dataset escrito en {out_dir}")
    print(f"YAML: {yaml_dst}")
    print(f"Manifest: {manifest_path}")


if __name__ == "__main__":
    main()
