#!/usr/bin/env python3
"""Stage 1: create privacy-separated checkpoints and an aggregate data audit."""

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


def sql_literal(path: Path | str) -> str:
    return "'" + str(path).replace("'", "''") + "'"


def write_csv(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    frame.to_csv(temporary, index=False)
    os.replace(temporary, path)


def main() -> int:
    if len(sys.argv) != 4:
        raise SystemExit("usage: profile_and_prepare.py RAW_GLOB WORK_DIR OUTPUT_DIR")
    raw_glob = sys.argv[1]
    work_dir = Path(sys.argv[2]).resolve()
    output_dir = Path(sys.argv[3]).resolve()
    outputs = output_dir / "outputs"
    audit = output_dir / "audit"
    logs = output_dir / "audit"
    private_dir = work_dir / "data" / "private"
    clean_dir = work_dir / "data" / "clean"
    duck_tmp = work_dir / "tmp" / "duckdb"
    for directory in (outputs, audit, logs, private_dir, clean_dir, duck_tmp):
        directory.mkdir(parents=True, exist_ok=True)

    log_path = logs / "stage1_profile.log"
    log_path.write_text("", encoding="utf-8")
    started = time.time()

    def log(message: str) -> None:
        line = f"{time.strftime('%Y-%m-%dT%H:%M:%S%z')} {message}"
        print(line, flush=True)
        with log_path.open("a", encoding="utf-8") as stream:
            stream.write(line + "\n")

    con = duckdb.connect(str(work_dir / "tmp" / "kiva_profile.duckdb"))
    con.execute("SET threads=8")
    con.execute("SET memory_limit='8GB'")
    # Freeze all timestamp parsing, display, date-part extraction, and follow-up
    # boundaries to UTC so the 2016--2025 competition period does not drift with
    # the analyst machine's local timezone.
    con.execute("SET TimeZone='UTC'")
    con.execute(f"SET temp_directory={sql_literal(duck_tmp)}")
    con.execute(
        f"CREATE OR REPLACE VIEW raw AS SELECT * FROM read_parquet({sql_literal(raw_glob)}, union_by_name=true)"
    )
    con.execute(
        """
        CREATE OR REPLACE TEMP VIEW typed AS
        SELECT
          *,
          TRY_CAST(fundraisingDate AS TIMESTAMPTZ) AS fundraising_ts,
          TRY_CAST(raisedDate AS TIMESTAMPTZ) AS raised_ts,
          TRY_CAST(disbursalDate AS TIMESTAMPTZ) AS disbursal_ts
        FROM raw
        """
    )

    log(f"raw view ready rss_gib={psutil.Process().memory_info().rss / 1024**3:.2f}")

    core_path = clean_dir / "core.parquet"
    text_path = private_dir / "text_private.parquet"
    con.execute(
        f"""
        COPY (
          SELECT
            id,
            _source_row,
            status,
            borrowerCount,
            gender,
            loanAmount,
            lenderRepaymentTerm,
            repaymentInterval,
            sector,
            activity,
            country_iso,
            country_name,
            region,
            country_ppp,
            disbursal_ts,
            fundraising_ts,
            raised_ts,
            EXTRACT(YEAR FROM fundraising_ts)::INTEGER AS fundraising_year,
            DATE_TRUNC('week', fundraising_ts) AS fundraising_week,
            CASE
              WHEN fundraising_ts IS NOT NULL AND raised_ts >= fundraising_ts
              THEN EPOCH(raised_ts - fundraising_ts) / 3600.0
              ELSE NULL
            END AS funding_hours,
            CASE
              WHEN fundraising_ts IS NOT NULL AND raised_ts >= fundraising_ts
              THEN 1 ELSE 0
            END AS valid_raised_event,
            CASE
              WHEN fundraising_ts <= TIMESTAMPTZ {sql_literal(OBSERVATION_CUTOFF_UTC)} - INTERVAL '72 hours'
              THEN 1 ELSE 0
            END AS eligible_72h_followup,
            CASE
              WHEN fundraising_ts <= TIMESTAMPTZ {sql_literal(OBSERVATION_CUTOFF_UTC)} - INTERVAL '14 days'
              THEN 1 ELSE 0
            END AS eligible_14d_followup,
            CASE
              WHEN fundraising_ts IS NOT NULL AND raised_ts >= fundraising_ts
                   AND raised_ts <= fundraising_ts + INTERVAL '72 hours'
              THEN 1 ELSE 0
            END AS funded_within_72h,
            CASE
              WHEN fundraising_ts IS NOT NULL AND raised_ts >= fundraising_ts
                   AND raised_ts <= fundraising_ts + INTERVAL '14 days'
              THEN 1 ELSE 0
            END AS funded_within_14d
          FROM typed
        ) TO {sql_literal(core_path)}
        (FORMAT PARQUET, COMPRESSION ZSTD, COMPRESSION_LEVEL 5, ROW_GROUP_SIZE 100000)
        """
    )
    con.execute(
        f"""
        COPY (
          SELECT
            id,
            _source_row,
            name,
            city,
            country_name,
            region,
            use,
            description,
            whySpecial
          FROM raw
        ) TO {sql_literal(text_path)}
        (FORMAT PARQUET, COMPRESSION ZSTD, COMPRESSION_LEVEL 5, ROW_GROUP_SIZE 50000)
        """
    )
    log(
        f"privacy-separated checkpoints written core_bytes={core_path.stat().st_size:,} "
        f"private_text_bytes={text_path.stat().st_size:,}"
    )

    schema = con.execute("DESCRIBE SELECT * FROM raw").fetchdf()
    write_csv(schema, audit / "raw_schema.csv")

    row_summary = con.execute(
        """
        SELECT
          COUNT(*) AS rows,
          COUNT(DISTINCT id) AS distinct_ids,
          SUM(CASE WHEN id IS NULL THEN 1 ELSE 0 END) AS null_ids,
          SUM(CASE WHEN fundraising_ts IS NULL THEN 1 ELSE 0 END) AS invalid_fundraising_dates,
          SUM(CASE WHEN raisedDate IS NOT NULL AND raised_ts IS NULL THEN 1 ELSE 0 END) AS invalid_raised_dates,
          SUM(CASE WHEN raised_ts < fundraising_ts THEN 1 ELSE 0 END) AS negative_durations,
          SUM(CASE WHEN raised_ts = fundraising_ts THEN 1 ELSE 0 END) AS zero_durations,
          MIN(fundraising_ts) AS min_fundraising_ts,
          MAX(fundraising_ts) AS max_fundraising_ts,
          MIN(raised_ts) AS min_raised_ts,
          MAX(raised_ts) AS max_raised_ts,
          COUNT(DISTINCT sector) AS sectors,
          COUNT(DISTINCT activity) AS activities,
          COUNT(DISTINCT country_name) AS countries
        FROM typed
        """
    ).fetchdf()
    write_csv(row_summary, outputs / "data_profile_summary.csv")

    duplicate_summary = con.execute(
        """
        WITH duplicate_ids AS (
          SELECT id, COUNT(*) AS n
          FROM raw
          GROUP BY id
          HAVING COUNT(*) > 1
        )
        SELECT
          COUNT(*) AS duplicate_id_keys,
          COALESCE(SUM(n), 0) AS rows_with_duplicated_id,
          COALESCE(SUM(n - 1), 0) AS excess_duplicate_rows
        FROM duplicate_ids
        """
    ).fetchdf()
    write_csv(duplicate_summary, outputs / "duplicate_id_summary.csv")

    status = con.execute(
        """
        SELECT
          COALESCE(status, '<NULL>') AS status,
          COUNT(*) AS loans,
          SUM(CASE WHEN raised_ts IS NOT NULL THEN 1 ELSE 0 END) AS raised_date_present,
          SUM(CASE WHEN raised_ts IS NULL THEN 1 ELSE 0 END) AS raised_date_missing,
          SUM(CASE WHEN raised_ts >= fundraising_ts THEN 1 ELSE 0 END) AS valid_raised_event,
          ROUND(100.0 * AVG(CASE WHEN raised_ts >= fundraising_ts THEN 1.0 ELSE 0.0 END), 4) AS valid_raised_event_pct
        FROM typed
        GROUP BY 1
        ORDER BY loans DESC
        """
    ).fetchdf()
    write_csv(status, outputs / "status_raised_crosstab.csv")

    duration = con.execute(
        """
        SELECT
          COUNT(*) AS valid_funded_loans,
          QUANTILE_CONT(EPOCH(raised_ts - fundraising_ts) / 3600.0, 0.01) AS p01_hours,
          QUANTILE_CONT(EPOCH(raised_ts - fundraising_ts) / 3600.0, 0.25) AS p25_hours,
          QUANTILE_CONT(EPOCH(raised_ts - fundraising_ts) / 3600.0, 0.50) AS p50_hours,
          QUANTILE_CONT(EPOCH(raised_ts - fundraising_ts) / 3600.0, 0.75) AS p75_hours,
          QUANTILE_CONT(EPOCH(raised_ts - fundraising_ts) / 3600.0, 0.90) AS p90_hours,
          QUANTILE_CONT(EPOCH(raised_ts - fundraising_ts) / 3600.0, 0.95) AS p95_hours,
          QUANTILE_CONT(EPOCH(raised_ts - fundraising_ts) / 3600.0, 0.99) AS p99_hours,
          MAX(EPOCH(raised_ts - fundraising_ts) / 3600.0) AS max_hours
        FROM typed
        WHERE raised_ts >= fundraising_ts
        """
    ).fetchdf()
    write_csv(duration, outputs / "funding_duration_quantiles.csv")

    duration_train = con.execute(
        """
        SELECT
          COUNT(*) AS valid_funded_loans,
          QUANTILE_CONT(EPOCH(raised_ts - fundraising_ts) / 3600.0, 0.50) AS p50_hours,
          QUANTILE_CONT(EPOCH(raised_ts - fundraising_ts) / 3600.0, 0.75) AS p75_hours,
          QUANTILE_CONT(EPOCH(raised_ts - fundraising_ts) / 3600.0, 0.95) AS p95_hours
        FROM typed
        WHERE raised_ts >= fundraising_ts
          AND EXTRACT(YEAR FROM fundraising_ts) BETWEEN 2016 AND 2024
        """
    ).fetchdf()
    write_csv(duration_train, outputs / "funding_duration_quantiles_train_2016_2024.csv")

    year_counts = con.execute(
        """
        SELECT
          EXTRACT(YEAR FROM fundraising_ts)::INTEGER AS fundraising_year,
          COUNT(*) AS loans,
          SUM(CASE WHEN raised_ts >= fundraising_ts THEN 1 ELSE 0 END) AS valid_raised_events,
          SUM(CASE WHEN raised_ts IS NULL THEN 1 ELSE 0 END) AS raised_date_missing,
          ROUND(100.0 * AVG(CASE WHEN raised_ts >= fundraising_ts THEN 1.0 ELSE 0.0 END), 4) AS valid_raised_event_pct
        FROM typed
        GROUP BY 1
        ORDER BY 1
        """
    ).fetchdf()
    write_csv(year_counts, outputs / "year_counts.csv")

    sector_counts = con.execute(
        """
        SELECT
          COALESCE(sector, '<NULL>') AS sector,
          COUNT(*) AS loans,
          SUM(CASE WHEN raised_ts >= fundraising_ts THEN 1 ELSE 0 END) AS valid_raised_events
        FROM typed
        GROUP BY 1
        ORDER BY loans DESC, sector
        """
    ).fetchdf()
    write_csv(sector_counts, outputs / "sector_counts.csv")

    country_counts = con.execute(
        """
        SELECT
          COALESCE(country_name, '<NULL>') AS country,
          COUNT(*) AS loans,
          SUM(CASE WHEN raised_ts >= fundraising_ts THEN 1 ELSE 0 END) AS valid_raised_events
        FROM typed
        GROUP BY 1
        ORDER BY loans DESC, country
        """
    ).fetchdf()
    write_csv(country_counts, outputs / "country_counts.csv")

    text_diagnostics = con.execute(
        """
        SELECT * FROM (
          SELECT
            'use' AS field,
            COUNT(*) AS rows,
            SUM(CASE WHEN use IS NOT NULL AND TRIM(use) <> '' THEN 1 ELSE 0 END) AS nonempty,
            ROUND(100.0 * AVG(CASE WHEN use IS NOT NULL AND TRIM(use) <> '' THEN 1.0 ELSE 0.0 END), 4) AS nonempty_pct,
            QUANTILE_CONT(LIST_COUNT(REGEXP_EXTRACT_ALL(COALESCE(use, ''), '\\S+')), 0.50) AS median_tokens,
            QUANTILE_CONT(LIST_COUNT(REGEXP_EXTRACT_ALL(COALESCE(use, ''), '\\S+')), 0.90) AS p90_tokens
          FROM raw
          UNION ALL
          SELECT
            'description', COUNT(*),
            SUM(CASE WHEN description IS NOT NULL AND TRIM(description) <> '' THEN 1 ELSE 0 END),
            ROUND(100.0 * AVG(CASE WHEN description IS NOT NULL AND TRIM(description) <> '' THEN 1.0 ELSE 0.0 END), 4),
            QUANTILE_CONT(LIST_COUNT(REGEXP_EXTRACT_ALL(COALESCE(description, ''), '\\S+')), 0.50),
            QUANTILE_CONT(LIST_COUNT(REGEXP_EXTRACT_ALL(COALESCE(description, ''), '\\S+')), 0.90)
          FROM raw
          UNION ALL
          SELECT
            'whySpecial', COUNT(*),
            SUM(CASE WHEN whySpecial IS NOT NULL AND TRIM(whySpecial) <> '' THEN 1 ELSE 0 END),
            ROUND(100.0 * AVG(CASE WHEN whySpecial IS NOT NULL AND TRIM(whySpecial) <> '' THEN 1.0 ELSE 0.0 END), 4),
            QUANTILE_CONT(LIST_COUNT(REGEXP_EXTRACT_ALL(COALESCE(whySpecial, ''), '\\S+')), 0.50),
            QUANTILE_CONT(LIST_COUNT(REGEXP_EXTRACT_ALL(COALESCE(whySpecial, ''), '\\S+')), 0.90)
          FROM raw
        ) ORDER BY field
        """
    ).fetchdf()
    write_csv(text_diagnostics, outputs / "text_field_diagnostics.csv")

    columns = schema["column_name"].tolist()
    null_expressions = []
    for column in columns:
        escaped = '"' + column.replace('"', '""') + '"'
        null_expressions.append(
            f"SUM(CASE WHEN {escaped} IS NULL THEN 1 ELSE 0 END) AS {escaped}"
        )
    null_row = con.execute("SELECT " + ",".join(null_expressions) + " FROM raw").fetchdf()
    null_summary = pd.DataFrame(
        {
            "column": columns,
            "null_count": [int(null_row.iloc[0][column]) for column in columns],
        }
    )
    row_count = int(row_summary.iloc[0]["rows"])
    null_summary["null_pct"] = (100.0 * null_summary["null_count"] / row_count).round(6)
    write_csv(null_summary, outputs / "column_null_rates.csv")

    followup = con.execute(
        f"""
        SELECT
          COUNT(*) AS loans,
          SUM(CASE WHEN fundraising_ts <= TIMESTAMPTZ {sql_literal(OBSERVATION_CUTOFF_UTC)} - INTERVAL '72 hours' THEN 1 ELSE 0 END) AS eligible_72h,
          SUM(CASE WHEN fundraising_ts <= TIMESTAMPTZ {sql_literal(OBSERVATION_CUTOFF_UTC)} - INTERVAL '14 days' THEN 1 ELSE 0 END) AS eligible_14d,
          SUM(CASE WHEN raised_ts >= fundraising_ts AND raised_ts <= fundraising_ts + INTERVAL '72 hours' THEN 1 ELSE 0 END) AS funded_within_72h,
          SUM(CASE WHEN raised_ts >= fundraising_ts AND raised_ts <= fundraising_ts + INTERVAL '14 days' THEN 1 ELSE 0 END) AS funded_within_14d
        FROM typed
        """
    ).fetchdf()
    write_csv(followup, outputs / "followup_eligibility.csv")

    data_quality = {
        "as_of_utc": OBSERVATION_CUTOFF_UTC,
        "raw_rows": row_count,
        "distinct_ids": int(row_summary.iloc[0]["distinct_ids"]),
        "duplicate_id_keys": int(duplicate_summary.iloc[0]["duplicate_id_keys"]),
        "invalid_fundraising_dates": int(row_summary.iloc[0]["invalid_fundraising_dates"]),
        "invalid_raised_dates": int(row_summary.iloc[0]["invalid_raised_dates"]),
        "negative_durations": int(row_summary.iloc[0]["negative_durations"]),
        "zero_durations": int(row_summary.iloc[0]["zero_durations"]),
        "sectors": int(row_summary.iloc[0]["sectors"]),
        "activities": int(row_summary.iloc[0]["activities"]),
        "countries": int(row_summary.iloc[0]["countries"]),
        "partner_identifier_present": any(
            any(token in column.lower() for token in ("partner", "lenderid", "partner_id"))
            for column in columns
        ),
        "excluded_lookahead_fields": ["fundsLentInCountry"],
        "raw_personal_fields_excluded_from_final_outputs": [
            "name", "city", "latitude", "longitude", "image_url", "description"
        ],
        "elapsed_seconds": round(time.time() - started, 3),
    }
    quality_path = audit / "data_quality_report.json"
    temporary = quality_path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(data_quality, indent=2), encoding="utf-8")
    os.replace(temporary, quality_path)

    summary_md = audit / "data_quality_summary.md"
    summary_md.write_text(
        "\n".join(
            [
                "# Data Quality Summary",
                "",
                f"- Source rows: {row_count:,}",
                f"- Distinct loan IDs: {data_quality['distinct_ids']:,}",
                f"- Duplicate ID keys: {data_quality['duplicate_id_keys']:,}",
                f"- Invalid fundraising dates: {data_quality['invalid_fundraising_dates']:,}",
                f"- Invalid raised dates: {data_quality['invalid_raised_dates']:,}",
                f"- Negative funding durations: {data_quality['negative_durations']:,}",
                f"- Partner/source identifier present: {data_quality['partner_identifier_present']}",
                "- `fundsLentInCountry` is excluded from modeling as a post-listing/look-ahead field.",
                "- Borrower names, exact locations, coordinates, image URLs, and raw narratives are excluded from final outputs.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    log(
        f"stage1 complete elapsed_seconds={time.time() - started:.1f} "
        f"rss_gib={psutil.Process().memory_info().rss / 1024**3:.2f}"
    )
    con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
