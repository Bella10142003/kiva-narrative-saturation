#!/usr/bin/env python3
"""Remove linkable row keys from aggregate validation outputs before delivery."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]


def atomic_csv(frame: pd.DataFrame, path: Path) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    frame.to_csv(temporary, index=False)
    os.replace(temporary, path)


def atomic_json(payload: dict, path: Path) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def replace_focal_key(path: Path) -> None:
    frame = pd.read_csv(path)
    if "focal_key" not in frame.columns:
        return
    frame.insert(0, "check_id", pd.factorize(frame["focal_key"], sort=False)[0] + 1)
    frame = frame.drop(columns=["focal_key"])
    atomic_csv(frame, path)


def main() -> int:
    replace_focal_key(ROOT / "outputs" / "pool_identity_check.csv")
    replace_focal_key(ROOT / "outputs" / "description_pool_identity_check.csv")

    text_manifest_path = ROOT / "audit" / "stage2_text_manifest.json"
    text_manifest = json.loads(text_manifest_path.read_text(encoding="utf-8"))
    text_manifest.pop("processed_private_path", None)
    text_manifest["processed_private_checkpoint"] = "omitted from external delivery"
    atomic_json(text_manifest, text_manifest_path)

    engine_manifest_path = ROOT / "audit" / "stage6_engine_manifest.json"
    engine_manifest = json.loads(engine_manifest_path.read_text(encoding="utf-8"))
    engine_manifest["row_level_scores_persisted_in_external_zip"] = False
    atomic_json(engine_manifest, engine_manifest_path)

    for filename in (
        "rq3_year_effects.csv",
        "rq4_country_effects.csv",
        "rq4_sector_effects.csv",
    ):
        path = ROOT / "outputs" / filename
        frame = pd.read_csv(path)
        frame["scenario_unit"] = (
            "percent change in conditional geometric mean of (1 + funding hours)"
        )
        atomic_csv(frame, path)

    print("Sanitized validation keys, metadata and scenario-unit labels for external delivery.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
