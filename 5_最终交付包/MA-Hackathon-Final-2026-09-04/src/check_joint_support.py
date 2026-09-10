#!/usr/bin/env python3
"""Check whether the precommitted P25-to-P75 joint contrasts have data support.

This is a descriptive diagnostic only. It does not turn the HDFE contrasts into
causal estimates. The script uses the exact main training sample and reports
both quartile-cell counts and small joint neighbourhoods around each scenario
endpoint.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import duckdb
import pandas as pd


def atomic_csv(frame: pd.DataFrame, path: Path) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    frame.to_csv(temporary, index=False)
    os.replace(temporary, path)


def atomic_json(payload: dict, path: Path) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: check_joint_support.py OUTPUT_DIR")
    root = Path(sys.argv[1]).resolve()
    outputs = root / "outputs"
    audit = root / "audit"
    model = root / "data" / "model_data.parquet"
    scalers = pd.read_csv(outputs / "scaler_parameters.csv")
    scale = scalers[scalers["specification"].eq("active_raw")].set_index("variable")

    con = duckdb.connect()
    quoted = str(model).replace("'", "''")
    con.execute(
        f"""
        CREATE TEMP VIEW main_train AS
        SELECT C_active, H_active_raw, V_lag, G_lag_raw,
               funding_hours, funded_within_72h
        FROM read_parquet('{quoted}')
        WHERE analysis_washin_eligible
          AND raw_text_nonempty
          AND pool_size_active >= 10
          AND lag_kish_n >= 10
          AND fundraising_year BETWEEN 2016 AND 2024
        """
    )
    n = int(con.execute("SELECT count(*) FROM main_train").fetchone()[0])
    rows: list[dict] = []
    cells: list[pd.DataFrame] = []
    for channel, left, right in [
        ("current", "C_active", "H_active_raw"),
        ("recent", "V_lag", "G_lag_raw"),
    ]:
        left_key, right_key = (("C", "H") if channel == "current" else ("V", "G"))
        lq = scale.loc[left_key]
        rq = scale.loc[right_key]
        left_iqr = float(lq.p75 - lq.p25)
        right_iqr = float(rq.p75 - rq.p25)
        # A +/-10% IQR box is narrow enough to diagnose local support while
        # retaining a directly interpretable count around the exact endpoint.
        left_half = 0.10 * left_iqr
        right_half = 0.10 * right_iqr
        corr = float(
            con.execute(f"SELECT corr({left}, {right}) FROM main_train").fetchone()[0]
        )
        for endpoint, left_target, right_target in [
            ("P25_P25", float(lq.p25), float(rq.p25)),
            ("P75_P75", float(lq.p75), float(rq.p75)),
        ]:
            values = con.execute(
                f"""
                SELECT count(*) AS n_near,
                       median(funding_hours) AS median_funding_hours,
                       avg(CAST(funded_within_72h AS DOUBLE)) AS fast_72h_rate
                FROM main_train
                WHERE abs({left} - ?) <= ? AND abs({right} - ?) <= ?
                """,
                [left_target, left_half, right_target, right_half],
            ).fetchone()
            rows.append(
                {
                    "channel": channel,
                    "endpoint": endpoint,
                    "left_variable": left,
                    "right_variable": right,
                    "left_target": left_target,
                    "right_target": right_target,
                    "left_halfwidth_0_10_iqr": left_half,
                    "right_halfwidth_0_10_iqr": right_half,
                    "n_near_endpoint": int(values[0]),
                    "share_main_train": float(values[0]) / n,
                    "median_funding_hours_near": float(values[1]),
                    "fast_72h_rate_near": float(values[2]),
                    "left_right_correlation": corr,
                    "main_train_n": n,
                }
            )

        cell = con.execute(
            f"""
            WITH q AS (
              SELECT *, ntile(4) OVER (ORDER BY {left}) AS left_quartile,
                        ntile(4) OVER (ORDER BY {right}) AS right_quartile
              FROM main_train
            )
            SELECT '{channel}' AS channel, left_quartile, right_quartile,
                   count(*) AS n,
                   median(funding_hours) AS median_funding_hours,
                   avg(CAST(funded_within_72h AS DOUBLE)) AS fast_72h_rate,
                   avg({left}) AS mean_left,
                   avg({right}) AS mean_right
            FROM q
            GROUP BY left_quartile, right_quartile
            ORDER BY left_quartile, right_quartile
            """
        ).df()
        cells.append(cell)

    summary = pd.DataFrame(rows)
    cell_frame = pd.concat(cells, ignore_index=True)
    atomic_csv(summary, outputs / "joint_support_summary.csv")
    atomic_csv(cell_frame, outputs / "joint_support_quartile_cells.csv")
    passed = bool((summary["n_near_endpoint"] >= 1000).all())
    atomic_json(
        {
            "main_train_n": n,
            "neighbourhood_definition": "+/- 0.10 IQR on both dimensions",
            "minimum_endpoint_count_rule": 1000,
            "joint_support_pass": passed,
            "interpretation": (
                "PASS supports describing the P25/P75 endpoints as empirically populated; "
                "it does not establish exchangeability, causality, or intervention validity."
            ),
            "outputs": [
                "outputs/joint_support_summary.csv",
                "outputs/joint_support_quartile_cells.csv",
            ],
        },
        audit / "joint_support_manifest.json",
    )
    print(summary.to_string(index=False))
    print(f"joint_support_pass={passed}")
    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
