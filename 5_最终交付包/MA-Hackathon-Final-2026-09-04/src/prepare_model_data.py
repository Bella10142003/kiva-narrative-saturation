#!/usr/bin/env python3
"""Stage 4a: assemble a privacy-safe model table and freeze train-only scalers."""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import duckdb
import pandas as pd
import psutil


OBSERVATION_CUTOFF_UTC = "2026-01-01 00:00:00+00"


def sql_literal(value: Path | str) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def atomic_csv(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    frame.to_csv(temporary, index=False)
    os.replace(temporary, path)


def atomic_json(payload: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def main() -> int:
    if len(sys.argv) != 3:
        raise SystemExit("usage: prepare_model_data.py WORK_DIR OUTPUT_DIR")
    work_dir = Path(sys.argv[1]).resolve()
    output_dir = Path(sys.argv[2]).resolve()
    core_path = work_dir / "data" / "clean" / "core.parquet"
    manifest = json.loads((output_dir / "audit" / "stage3_feature_manifest.json").read_text())
    feature_paths = [Path(path) for path in manifest["feature_parts"]]
    model_dir = output_dir / "data"
    outputs = output_dir / "outputs"
    audit = output_dir / "audit"
    duck_tmp = work_dir / "tmp" / "duckdb"
    for directory in (model_dir, outputs, audit, duck_tmp):
        directory.mkdir(parents=True, exist_ok=True)
    model_path = model_dir / "model_data.parquet"
    log_path = audit / "stage4a_prepare_model.log"
    log_path.write_text("", encoding="utf-8")
    started = time.time()

    def log(message: str) -> None:
        line = f"{time.strftime('%Y-%m-%dT%H:%M:%S%z')} {message}"
        print(line, flush=True)
        with log_path.open("a", encoding="utf-8") as stream:
            stream.write(line + "\n")

    feature_list = "[" + ",".join(sql_literal(path) for path in feature_paths) + "]"
    con = duckdb.connect(str(work_dir / "tmp" / "model_prepare.duckdb"))
    con.execute("SET TimeZone='UTC'")
    con.execute("SET threads=8")
    con.execute("SET memory_limit='8GB'")
    con.execute(f"SET temp_directory={sql_literal(duck_tmp)}")
    con.execute(
        f"""
        CREATE OR REPLACE VIEW core_aug AS
        SELECT
          *,
          COUNT(*) OVER (
            ORDER BY fundraising_ts
            RANGE BETWEEN INTERVAL '7 days' PRECEDING AND INTERVAL '1 microsecond' PRECEDING
          ) AS platform_posting_7d_count
        FROM read_parquet({sql_literal(core_path)})
        WHERE fundraising_year BETWEEN 2016 AND 2025
        """
    )
    con.execute(f"CREATE OR REPLACE VIEW features AS SELECT * FROM read_parquet({feature_list})")
    con.execute(
        f"""
        COPY (
          SELECT
            f.id,
            c.status,
            c.borrowerCount,
            c.gender,
            c.loanAmount,
            c.lenderRepaymentTerm,
            c.repaymentInterval,
            c.sector,
            c.activity,
            c.country_name,
            c.country_ppp,
            c.fundraising_ts,
            c.raised_ts,
            c.fundraising_year,
            STRFTIME(c.fundraising_week, '%Y-%m-%d') AS week_id,
            EXTRACT(DOW FROM c.fundraising_ts)::INTEGER AS posting_dow,
            EXTRACT(HOUR FROM c.fundraising_ts)::INTEGER AS posting_hour,
            c.funding_hours,
            LN(1.0 + c.funding_hours) AS log_funding_hours,
            c.eligible_72h_followup,
            c.funded_within_72h,
            CASE
              WHEN c.fundraising_ts <= TIMESTAMPTZ {sql_literal(OBSERVATION_CUTOFF_UTC)} - INTERVAL '35 days'
              THEN 1 ELSE 0
            END AS eligible_35d_followup,
            c.platform_posting_7d_count,
            LN(1.0 + c.loanAmount) AS log_loan_amount,
            LN(1.0 + c.borrowerCount) AS log_borrower_count,
            LN(1.0 + c.lenderRepaymentTerm) AS log_repayment_term,
            LN(1.0 + c.platform_posting_7d_count) AS log_platform_posting_7d,
            f.analysis_washin_eligible,
            f.raw_text_nonempty,
            f.residual_text_nonempty,
            f.boilerplate_share,
            f.pool_size_active,
            LN(1.0 + f.pool_size_active) AS C_active,
            f.H_active_raw,
            f.H_active_residual,
            f.pool_size_14d,
            LN(1.0 + f.pool_size_14d) AS C_14d,
            f.H_14d_raw,
            f.H_14d_residual,
            f.pool_size_16d,
            LN(1.0 + f.pool_size_16d) AS C_16d,
            f.H_16d_raw,
            f.H_16d_residual,
            f.lag_pool_raw_count,
            f.lag_weight,
            LN(1.0 + f.lag_weight) AS V_lag,
            f.lag_kish_n,
            f.G_lag_raw,
            f.G_lag_residual,
            f.lag_completed_raw_count,
            f.lag_completed_weight,
            LN(1.0 + f.lag_completed_weight) AS V_lag_completed,
            f.lag_completed_kish_n,
            f.G_lag_completed_raw,
            f.G_lag_completed_residual
          FROM features f
          JOIN core_aug c USING (id)
          WHERE c.raised_ts >= c.fundraising_ts
        ) TO {sql_literal(model_path)}
        (FORMAT PARQUET, COMPRESSION ZSTD, COMPRESSION_LEVEL 5, ROW_GROUP_SIZE 100000)
        """
    )
    log(f"model table written bytes={model_path.stat().st_size:,}")
    con.execute(f"CREATE OR REPLACE VIEW model AS SELECT * FROM read_parquet({sql_literal(model_path)})")

    flow = con.execute(
        """
        SELECT 'valid duration rows' AS step, COUNT(*) AS loans FROM model
        UNION ALL
        SELECT 'wash-in eligible', COUNT(*) FROM model WHERE analysis_washin_eligible
        UNION ALL
        SELECT 'raw text nonempty', COUNT(*) FROM model WHERE analysis_washin_eligible AND raw_text_nonempty
        UNION ALL
        SELECT 'main pool thresholds', COUNT(*) FROM model
          WHERE analysis_washin_eligible AND raw_text_nonempty
            AND pool_size_active >= 10 AND lag_kish_n >= 10
        UNION ALL
        SELECT 'main train 2016-2024', COUNT(*) FROM model
          WHERE analysis_washin_eligible AND raw_text_nonempty
            AND pool_size_active >= 10 AND lag_kish_n >= 10
            AND fundraising_year BETWEEN 2016 AND 2024
        UNION ALL
        SELECT 'main holdout 2025', COUNT(*) FROM model
          WHERE analysis_washin_eligible AND raw_text_nonempty
            AND pool_size_active >= 10 AND lag_kish_n >= 10
            AND fundraising_year = 2025
        UNION ALL
        SELECT 'main holdout 2025 with 35d follow-up', COUNT(*) FROM model
          WHERE analysis_washin_eligible AND raw_text_nonempty
            AND pool_size_active >= 10 AND lag_kish_n >= 10
            AND fundraising_year = 2025 AND eligible_35d_followup = 1
        UNION ALL
        SELECT 'main 72h eligible', COUNT(*) FROM model
          WHERE analysis_washin_eligible AND raw_text_nonempty
            AND pool_size_active >= 10 AND lag_kish_n >= 10
            AND eligible_72h_followup = 1
        """
    ).fetchdf()
    atomic_csv(flow, outputs / "model_sample_flow.csv")

    pool_specs = [
        ("active", "pool_size_active"),
        ("posting_14d", "pool_size_14d"),
        ("posting_16d", "pool_size_16d"),
        ("lag_kish", "lag_kish_n"),
        ("lag_completed_kish", "lag_completed_kish_n"),
    ]
    coverage_rows: list[dict] = []
    for period, where in (
        ("all", "TRUE"),
        ("train_2016_2024", "fundraising_year BETWEEN 2016 AND 2024"),
        ("holdout_2025", "fundraising_year = 2025"),
    ):
        for pool_name, column in pool_specs:
            row = con.execute(
                f"""
                SELECT
                  COUNT(*) AS loans,
                  QUANTILE_CONT({column}, 0.01) AS p01,
                  QUANTILE_CONT({column}, 0.25) AS p25,
                  QUANTILE_CONT({column}, 0.50) AS p50,
                  QUANTILE_CONT({column}, 0.75) AS p75,
                  QUANTILE_CONT({column}, 0.99) AS p99,
                  100.0 * AVG(CASE WHEN {column} < 5 THEN 1.0 ELSE 0.0 END) AS pct_below_5,
                  100.0 * AVG(CASE WHEN {column} < 10 THEN 1.0 ELSE 0.0 END) AS pct_below_10,
                  100.0 * AVG(CASE WHEN {column} < 20 THEN 1.0 ELSE 0.0 END) AS pct_below_20
                FROM model WHERE {where}
                """
            ).fetchdf().iloc[0].to_dict()
            row.update({"period": period, "pool": pool_name})
            coverage_rows.append(row)
    pool_coverage = pd.DataFrame(coverage_rows)[
        [
            "period",
            "pool",
            "loans",
            "p01",
            "p25",
            "p50",
            "p75",
            "p99",
            "pct_below_5",
            "pct_below_10",
            "pct_below_20",
        ]
    ]
    atomic_csv(pool_coverage, outputs / "pool_size_distribution.csv")

    by_sector = con.execute(
        """
        SELECT
          sector,
          COUNT(*) AS loans,
          QUANTILE_CONT(pool_size_active, 0.50) AS median_active_n,
          QUANTILE_CONT(pool_size_16d, 0.50) AS median_posting_16d_n,
          QUANTILE_CONT(lag_kish_n, 0.50) AS median_lag_kish_n,
          100.0 * AVG(CASE WHEN pool_size_active < 10 OR lag_kish_n < 10 THEN 1.0 ELSE 0.0 END) AS pct_below_main_thresholds
        FROM model
        GROUP BY sector
        ORDER BY loans DESC
        """
    ).fetchdf()
    atomic_csv(by_sector, outputs / "pool_size_by_sector.csv")

    scaler_specs = {
        "active_raw": {
            "C": "C_active",
            "H": "H_active_raw",
            "V": "V_lag",
            "G": "G_lag_raw",
            "where": "pool_size_active >= 10 AND lag_kish_n >= 10 AND raw_text_nonempty",
        },
        "active_residual": {
            "C": "C_active",
            "H": "H_active_residual",
            "V": "V_lag",
            "G": "G_lag_residual",
            "where": "pool_size_active >= 10 AND lag_kish_n >= 10 AND residual_text_nonempty",
        },
        "posting_14d_raw": {
            "C": "C_14d",
            "H": "H_14d_raw",
            "V": "V_lag",
            "G": "G_lag_raw",
            "where": "pool_size_14d >= 10 AND lag_kish_n >= 10 AND raw_text_nonempty",
        },
        "posting_16d_raw": {
            "C": "C_16d",
            "H": "H_16d_raw",
            "V": "V_lag",
            "G": "G_lag_raw",
            "where": "pool_size_16d >= 10 AND lag_kish_n >= 10 AND raw_text_nonempty",
        },
        "active_completed_lag_raw": {
            "C": "C_active",
            "H": "H_active_raw",
            "V": "V_lag_completed",
            "G": "G_lag_completed_raw",
            "where": "pool_size_active >= 10 AND lag_completed_kish_n >= 10 AND raw_text_nonempty",
        },
    }
    scaler_rows: list[dict] = []
    for specification, spec in scaler_specs.items():
        for variable, column in ((key, spec[key]) for key in ("C", "H", "V", "G")):
            stats = con.execute(
                f"""
                SELECT
                  COUNT({column}) AS n_fit,
                  AVG({column}) AS mean,
                  STDDEV_SAMP({column}) AS std,
                  QUANTILE_CONT({column}, 0.25) AS p25,
                  QUANTILE_CONT({column}, 0.50) AS p50,
                  QUANTILE_CONT({column}, 0.75) AS p75
                FROM model
                WHERE analysis_washin_eligible
                  AND fundraising_year BETWEEN 2016 AND 2024
                  AND {spec['where']}
                  AND {column} IS NOT NULL
                """
            ).fetchdf().iloc[0].to_dict()
            stats.update(
                {
                    "specification": specification,
                    "variable": variable,
                    "source_column": column,
                }
            )
            scaler_rows.append(stats)
    scalers = pd.DataFrame(scaler_rows)[
        ["specification", "variable", "source_column", "n_fit", "mean", "std", "p25", "p50", "p75"]
    ]
    atomic_csv(scalers, outputs / "scaler_parameters.csv")

    atomic_json(
        {
            "model_data_path": str(model_path),
            "rows": int(con.execute("SELECT COUNT(*) FROM model").fetchone()[0]),
            "bytes": model_path.stat().st_size,
            "feature_parts": [str(path) for path in feature_paths],
            "platform_volume_control": "same-platform listings posted during prior 7 days; same timestamp excluded",
            "scalers_fit_period": "2016-2024 only",
            "elapsed_seconds": round(time.time() - started, 3),
        },
        audit / "stage4a_model_data_manifest.json",
    )
    log(
        f"stage4a complete elapsed_seconds={time.time() - started:.1f} "
        f"rows={con.execute('SELECT COUNT(*) FROM model').fetchone()[0]:,} "
        f"rss_gib={psutil.Process().memory_info().rss / 1024**3:.2f}"
    )
    con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
