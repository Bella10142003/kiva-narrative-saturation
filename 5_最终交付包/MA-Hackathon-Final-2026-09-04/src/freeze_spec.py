#!/usr/bin/env python3
"""Stage 1b: freeze analysis definitions using outcome-blind diagnostics.

The script never writes raw text to the deliverable directory. Text diagnostics
are aggregate and are computed on a deterministic 5% training-period sample.
"""

from __future__ import annotations

import html
import json
import os
import re
import sys
import time
from collections import deque
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import psutil
from scipy import sparse
from sklearn.feature_extraction.text import HashingVectorizer


CURRENT_P75_HOURS = 394.781875
CURRENT_P75_DAYS = CURRENT_P75_HOURS / 24.0
LAG_GAP_DAYS = 35
LAG_SPAN_DAYS = 30
OBSERVATION_CUTOFF_UTC = "2026-01-01 00:00:00+00"
RANDOM_SEED = 20260904

TAG_RE = re.compile(r"<[^>]+>")
DATE_RE = re.compile(
    r"\b(?:\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?|\d{4}[/-]\d{1,2}[/-]\d{1,2}|"
    r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{1,2}(?:,\s*\d{4})?)\b",
    flags=re.IGNORECASE,
)
AMOUNT_RE = re.compile(
    r"(?<!\w)(?:usd|ksh|kes|php|ugx|tzs|rwf|xof|eur|\$|€|£)?\s*"
    r"\d[\d,.]*(?:\s*(?:usd|dollars?|pesos?|shillings?|francs?))?(?!\w)",
    flags=re.IGNORECASE,
)
ORG_RE = re.compile(r"\b[A-Z][A-Z&.-]{1,9}\b")
SPACE_RE = re.compile(r"\s+")
TOKEN_RE = re.compile(r"(?u)\b\w\w+\b")


def sql_literal(value: Path | str) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def atomic_csv(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    frame.to_csv(temporary, index=False)
    os.replace(temporary, path)


def mask_text(text: object, exact_values: list[tuple[str, str]]) -> str:
    if text is None or (isinstance(text, float) and np.isnan(text)):
        return ""
    value = html.unescape(str(text))
    value = TAG_RE.sub(" ", value)
    for original, placeholder in exact_values:
        original = str(original).strip() if original is not None else ""
        if len(original) >= 2:
            value = re.sub(re.escape(original), f" [{placeholder.lower()}] ", value, flags=re.IGNORECASE)
    # Placeholders are lower-case on purpose. ORG_RE is \b[A-Z][A-Z&.-]{1,9}\b and
    # only matches all-caps runs; upper-case placeholders such as [DATE]/[AMT]/[NAME]
    # were themselves rewritten to [ORG] by the final substitution, collapsing four
    # entity classes into one token. The function lower-cases at the end anyway, so
    # this preserves the intended output while keeping the classes distinct.
    value = DATE_RE.sub(" [date] ", value)
    value = AMOUNT_RE.sub(" [amt] ", value)
    value = ORG_RE.sub(" [org] ", value)
    return SPACE_RE.sub(" ", value).strip().lower()


def token_count(value: str) -> int:
    return len(TOKEN_RE.findall(value))


def diagnostic_overlap(
    frame: pd.DataFrame, masked: list[str], field: str
) -> tuple[dict[str, float | int | str], np.ndarray]:
    vectorizer = HashingVectorizer(
        n_features=32768,
        alternate_sign=False,
        norm="l2",
        ngram_range=(1, 2),
        lowercase=False,
        token_pattern=r"(?u)\b\w\w+\b",
        dtype=np.float32,
    )
    matrix = vectorizer.transform(masked).tocsr()
    rng = np.random.default_rng(RANDOM_SEED + (1 if field == "description" else 0))
    left: list[int] = []
    right: list[int] = []
    grouped = frame.groupby("sector", sort=True).indices
    eligible_groups = [np.asarray(v, dtype=np.int64) for v in grouped.values() if len(v) >= 2]
    weights = np.asarray([len(v) for v in eligible_groups], dtype=float)
    weights /= weights.sum()
    for group_index in rng.choice(len(eligible_groups), size=10000, replace=True, p=weights):
        indices = eligible_groups[int(group_index)]
        pair = rng.choice(indices, size=2, replace=False)
        left.append(int(pair[0]))
        right.append(int(pair[1]))
    pair_cos = np.asarray(matrix[left].multiply(matrix[right]).sum(axis=1)).ravel()

    h_values: list[float] = []
    pool_sizes: list[int] = []
    horizon_ns = int(CURRENT_P75_HOURS * 3600.0 * 1e9)
    for _, group in frame.assign(_pos=np.arange(len(frame))).groupby("sector", sort=False):
        group = group.sort_values(["fundraising_ts", "id"], kind="mergesort")
        positions = group["_pos"].to_numpy(dtype=np.int64)
        # DuckDB currently returns datetime64[us, UTC]; explicitly normalize to
        # nanoseconds before comparing with the nanosecond horizon below.
        timestamps = (
            pd.to_datetime(group["fundraising_ts"], utc=True)
            .dt.tz_localize(None)
            .to_numpy(dtype="datetime64[ns]")
            .astype(np.int64)
        )
        running = np.zeros(matrix.shape[1], dtype=np.float64)
        history: deque[tuple[int, np.ndarray, np.ndarray]] = deque()
        start = 0
        while start < len(positions):
            stop = start + 1
            while stop < len(positions) and timestamps[stop] == timestamps[start]:
                stop += 1
            now = int(timestamps[start])
            cutoff = now - horizon_ns
            while history and history[0][0] < cutoff:
                _, old_idx, old_data = history.popleft()
                running[old_idx] -= old_data
            n_pool = len(history)
            if n_pool >= 5:
                for local in range(start, stop):
                    row = matrix.getrow(int(positions[local]))
                    h_values.append(float(np.dot(row.data.astype(np.float64), running[row.indices]) / n_pool))
                    pool_sizes.append(n_pool)
            for local in range(start, stop):
                row = matrix.getrow(int(positions[local]))
                idx = row.indices.copy()
                data = row.data.astype(np.float64, copy=True)
                running[idx] += data
                history.append((now, idx, data))
            start = stop

    h_array = np.asarray(h_values, dtype=float)
    result: dict[str, float | int | str] = {
        "field": field,
        "diagnostic_sample_rows": int(len(frame)),
        "random_same_sector_pairs": 10000,
        "pair_zero_overlap_pct": round(100.0 * float(np.mean(pair_cos <= 1e-12)), 4),
        "pair_cosine_mean": round(float(np.mean(pair_cos)), 8),
        "pair_cosine_variance": round(float(np.var(pair_cos)), 10),
        "sample_window_h_n": int(len(h_array)),
        "sample_window_h_variance": round(float(np.var(h_array)), 10) if len(h_array) else np.nan,
        "sample_window_h_median": round(float(np.median(h_array)), 8) if len(h_array) else np.nan,
        "sample_pool_size_median": round(float(np.median(pool_sizes)), 3) if pool_sizes else np.nan,
        "representation_note": "deterministic 5% training sample; hashed unigram+bigram TF-IDF for field selection only",
    }
    return result, pair_cos


def main() -> int:
    if len(sys.argv) != 4:
        raise SystemExit("usage: freeze_spec.py WORK_DIR OUTPUT_DIR CORE_PARQUET")
    work_dir = Path(sys.argv[1]).resolve()
    output_dir = Path(sys.argv[2]).resolve()
    core_path = Path(sys.argv[3]).resolve()
    text_path = work_dir / "data" / "private" / "text_private.parquet"
    outputs = output_dir / "outputs"
    audit = output_dir / "audit"
    logs = output_dir / "audit"
    for directory in (outputs, audit, logs, work_dir / "tmp" / "duckdb"):
        directory.mkdir(parents=True, exist_ok=True)

    log_path = logs / "stage1_freeze.log"
    log_path.write_text("", encoding="utf-8")
    started = time.time()

    def log(message: str) -> None:
        line = f"{time.strftime('%Y-%m-%dT%H:%M:%S%z')} {message}"
        print(line, flush=True)
        with log_path.open("a", encoding="utf-8") as stream:
            stream.write(line + "\n")

    con = duckdb.connect(str(work_dir / "tmp" / "freeze_spec.duckdb"))
    con.execute("SET TimeZone='UTC'")
    con.execute("SET threads=8")
    con.execute("SET memory_limit='8GB'")
    con.execute(f"SET temp_directory={sql_literal(work_dir / 'tmp' / 'duckdb')}")
    con.execute(f"CREATE OR REPLACE VIEW core AS SELECT * FROM read_parquet({sql_literal(core_path)})")
    con.execute(f"CREATE OR REPLACE VIEW txt AS SELECT * FROM read_parquet({sql_literal(text_path)})")
    con.execute(
        """
        CREATE OR REPLACE TEMP VIEW valid AS
        SELECT *
        FROM core
        WHERE fundraising_ts IS NOT NULL
          AND raised_ts >= fundraising_ts
          AND fundraising_year BETWEEN 2016 AND 2025
        """
    )

    coverage_frames: list[pd.DataFrame] = []
    windows = [
        ("posting_14d", "INTERVAL '14 days'", "INTERVAL '1 microsecond'"),
        ("posting_16d", "INTERVAL '16 days'", "INTERVAL '1 microsecond'"),
        (
            "posting_train_p75_394.782h",
            f"INTERVAL '{CURRENT_P75_HOURS:.9f} hours'",
            "INTERVAL '1 microsecond'",
        ),
        ("lag_35_to_65d_raw", "INTERVAL '65 days'", "INTERVAL '35 days'"),
    ]
    for name, lower, upper in windows:
        counts = con.execute(
            f"""
            WITH sizes AS (
              SELECT
                fundraising_year,
                sector,
                COUNT(*) OVER (
                  PARTITION BY sector
                  ORDER BY fundraising_ts
                  RANGE BETWEEN {lower} PRECEDING AND {upper} PRECEDING
                ) AS pool_n
              FROM valid
            )
            SELECT
              {sql_literal(name)} AS pool,
              COUNT(*) AS focal_loans,
              QUANTILE_CONT(pool_n, 0.01) AS p01,
              QUANTILE_CONT(pool_n, 0.25) AS p25,
              QUANTILE_CONT(pool_n, 0.50) AS p50,
              QUANTILE_CONT(pool_n, 0.75) AS p75,
              QUANTILE_CONT(pool_n, 0.99) AS p99,
              ROUND(100.0 * AVG(CASE WHEN pool_n < 5 THEN 1.0 ELSE 0.0 END), 4) AS pct_below_5,
              ROUND(100.0 * AVG(CASE WHEN pool_n < 10 THEN 1.0 ELSE 0.0 END), 4) AS pct_below_10,
              ROUND(100.0 * AVG(CASE WHEN pool_n < 20 THEN 1.0 ELSE 0.0 END), 4) AS pct_below_20
            FROM sizes
            """
        ).fetchdf()
        coverage_frames.append(counts)
        log(f"pool coverage calculated name={name}")
    pool_coverage = pd.concat(coverage_frames, ignore_index=True)
    atomic_csv(pool_coverage, outputs / "pool_size_precheck.csv")

    late_followup = con.execute(
        f"""
        SELECT
          CASE
            WHEN fundraising_ts > TIMESTAMPTZ {sql_literal(OBSERVATION_CUTOFF_UTC)} - INTERVAL '72 hours'
            THEN 'less_than_72h_followup'
            WHEN fundraising_ts > TIMESTAMPTZ {sql_literal(OBSERVATION_CUTOFF_UTC)} - INTERVAL '35 days'
            THEN '72h_to_35d_followup'
            ELSE 'at_least_35d_followup'
          END AS followup_band,
          COUNT(*) AS loans,
          QUANTILE_CONT(funding_hours, 0.50) AS median_funding_hours,
          QUANTILE_CONT(funding_hours, 0.95) AS p95_funding_hours
        FROM valid
        WHERE fundraising_year = 2025
        GROUP BY 1
        ORDER BY 1
        """
    ).fetchdf()
    atomic_csv(late_followup, outputs / "late_2025_followup_audit.csv")

    # Pre-registered justification for the 72-hour co-outcome threshold. Binarising a
    # duration at the median maximises Bernoulli variance p(1-p), hence power; this
    # records the candidates that were evaluated so the choice is auditable rather
    # than asserted in prose.
    threshold_choice = con.execute(
        """
        WITH train AS (
          SELECT funding_hours FROM valid WHERE fundraising_year BETWEEN 2016 AND 2024
        ), candidates AS (
          SELECT 24 AS candidate_hours, '1 day' AS label UNION ALL
          SELECT 72, '3 days (selected)' UNION ALL
          SELECT 168, '7 days' UNION ALL
          SELECT 336, '14 days'
        )
        SELECT
          c.candidate_hours,
          c.label,
          ROUND(100.0 * AVG(CASE WHEN t.funding_hours <= c.candidate_hours THEN 1.0 ELSE 0.0 END), 4)
            AS pct_funded_within,
          ROUND(
            AVG(CASE WHEN t.funding_hours <= c.candidate_hours THEN 1.0 ELSE 0.0 END)
            * (1.0 - AVG(CASE WHEN t.funding_hours <= c.candidate_hours THEN 1.0 ELSE 0.0 END)),
            6
          ) AS bernoulli_variance,
          ROUND(QUANTILE_CONT(t.funding_hours, 0.5), 4) AS train_median_hours
        FROM candidates c CROSS JOIN train t
        GROUP BY c.candidate_hours, c.label
        ORDER BY c.candidate_hours
        """
    ).fetchdf()
    atomic_csv(threshold_choice, outputs / "co_outcome_threshold_choice.csv")
    log("co-outcome threshold candidates evaluated")

    sample = con.execute(
        """
        SELECT
          c.id,
          c.sector,
          c.fundraising_ts,
          t.name,
          t.city,
          t.country_name,
          t.region,
          t.use,
          t.description
        FROM valid c
        JOIN txt t USING (id, _source_row)
        WHERE c.fundraising_year BETWEEN 2016 AND 2024
          AND (hash(c.id) % 100) < 5
        ORDER BY c.sector, c.fundraising_ts, c.id
        """
    ).fetchdf()
    log(f"text diagnostic sample loaded rows={len(sample):,} rss_gib={psutil.Process().memory_info().rss / 1024**3:.2f}")

    text_rows: list[dict[str, float | int | str]] = []
    for field in ("use", "description"):
        original_tokens: list[int] = []
        masked_tokens: list[int] = []
        masked_values: list[str] = []
        for row in sample.itertuples(index=False):
            raw_value = getattr(row, field)
            original = "" if raw_value is None else TAG_RE.sub(" ", html.unescape(str(raw_value)))
            exact = [
                (row.name, "NAME"),
                (row.city, "LOC"),
                (row.country_name, "LOC"),
                (row.region, "LOC"),
            ]
            masked = mask_text(raw_value, exact)
            original_tokens.append(token_count(original))
            masked_tokens.append(token_count(masked))
            masked_values.append(masked)
        result, _ = diagnostic_overlap(sample, masked_values, field)
        result.update(
            {
                "nonempty_pct": round(100.0 * float(np.mean(np.asarray(original_tokens) > 0)), 4),
                "tokens_before_median": round(float(np.median(original_tokens)), 3),
                "tokens_after_median": round(float(np.median(masked_tokens)), 3),
                "tokens_after_p90": round(float(np.quantile(masked_tokens, 0.9)), 3),
            }
        )
        text_rows.append(result)
        log(f"text diagnostic complete field={field}")
    text_diagnostics = pd.DataFrame(text_rows)
    atomic_csv(text_diagnostics, outputs / "text_selection_diagnostics.csv")

    split_counts = con.execute(
        """
        SELECT
          COUNT(*) FILTER (WHERE fundraising_year BETWEEN 2016 AND 2024) AS training_valid,
          COUNT(*) FILTER (WHERE fundraising_year = 2025) AS holdout_valid
        FROM valid
        """
    ).fetchone()
    training_valid = int(split_counts[0])
    holdout_valid = int(split_counts[1])

    sample_flow = pd.DataFrame(
        [
            {"step": "Raw official extract", "loans": 1453846, "excluded_at_step": 0, "reason": "Source total"},
            {"step": "Unique loan IDs", "loans": 1453846, "excluded_at_step": 0, "reason": "No duplicate IDs"},
            {"step": "Valid nonnegative duration", "loans": 1453840, "excluded_at_step": 6, "reason": "raisedDate earlier than fundraisingDate"},
            {"step": "72-hour label eligible", "loans": 1453346, "excluded_at_step": 494, "reason": "At least 72 hours of calendar follow-up; also excludes 6 invalid durations"},
            {"step": "Training 2016-2024, valid duration", "loans": training_valid, "excluded_at_step": 0, "reason": "Learned preprocessing and estimation period"},
            {"step": "2025 holdout, valid duration", "loans": holdout_valid, "excluded_at_step": 0, "reason": "Untouched out-of-time evaluation period"},
        ]
    )
    atomic_csv(sample_flow, outputs / "analysis_sample_flow.csv")

    frozen_spec = pd.DataFrame(
        [
            ("Sample split", "2016-2024 train; 2025 untouched holdout", "All learned text rules, IDF, thresholds and scaling use training only"),
            ("Time and wash-in", "UTC; first 65 days excluded as focal observations", "Lag window needs 35-day gap plus 30-day span; pools continue across 2024/2025"),
            ("Outcome", "log1p(funding hours); 72h fast-funding flag as co-outcome", "All 1,453,846 rows have raisedDate; 6 negative durations quarantined; claims are conditional on observed loans"),
            ("Current choice set", "Active same-sector pool primary", "All exit timestamps present; compute at posting with same-time ties excluded"),
            ("Time-based checks", "14-day precommitted and 16-day calibrated posting pools", f"Training P75={CURRENT_P75_HOURS:.3f}h ({CURRENT_P75_DAYS:.2f}d); 14d remains proposal benchmark"),
            ("Recent-history pool", "Age [35,65) days; 7-day half-life", "Training P95=826.891h (34.45d), rounded up before modeling; posting-age proxy, not observed exposure or page exit"),
            ("Text", "use primary; description robustness", "Both 97.31% nonempty; use is the browse-view field and has median 10 tokens vs 93"),
            ("Narrative representation", "Masked hashed unigram+bigram TF-IDF; recurring 5-gram removal sensitivity", "Rules fit on 2016-2024; no partner ID, so no institutional attribution"),
            ("Pool threshold", "Raw n>=10; weighted Kish n>=10; 5/20 sensitivity", "Proposal rule retained; small and empty pools reported, never encoded as zero"),
            ("Model and claim", "HDFE with Country + Activity + Week FE; country/week clustered SE", "Conditional association only; Engine scores triage and experiment priority, not treatment effects"),
        ],
        columns=["specification_item", "frozen_value", "evidence_and_rationale"],
    )
    atomic_csv(frozen_spec, outputs / "frozen_spec.csv")

    manifest = {
        "generated_at_local": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "observation_cutoff_utc": OBSERVATION_CUTOFF_UTC,
        "train_years": [2016, 2024],
        "holdout_year": 2025,
        "current_calibrated_hours": CURRENT_P75_HOURS,
        "current_calibrated_days": CURRENT_P75_DAYS,
        "lag_gap_days": LAG_GAP_DAYS,
        "lag_span_days": LAG_SPAN_DAYS,
        "text_diagnostic_sample_rule": "hash(id) % 100 < 5 on 2016-2024",
        "random_seed": RANDOM_SEED,
        "elapsed_seconds": round(time.time() - started, 3),
    }
    manifest_path = audit / "frozen_spec_manifest.json"
    temporary = manifest_path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    os.replace(temporary, manifest_path)
    log(f"stage1b complete elapsed_seconds={time.time() - started:.1f} rss_gib={psutil.Process().memory_info().rss / 1024**3:.2f}")
    con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
