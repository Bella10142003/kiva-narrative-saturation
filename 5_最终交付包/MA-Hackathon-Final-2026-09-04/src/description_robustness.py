#!/usr/bin/env python3
"""Train-only-IDF description-field robustness for active and lagged overlap."""

from __future__ import annotations

import hashlib
import heapq
import html
import json
import math
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
import pyarrow as pa
import pyarrow.dataset as ds
import pyarrow.parquet as pq
import pyfixest as pf
from sklearn.feature_extraction.text import HashingVectorizer
from sklearn.preprocessing import normalize

from fit_main_models import CORE_CONTROLS, FIXED_EFFECTS, load_scalers


FEATURES = 2**17
BATCH_SIZE = 25000
DAY_NS = 86_400 * 1_000_000_000
LAG_GAP_NS = 35 * DAY_NS
LAG_END_NS = 65 * DAY_NS
HALF_LIFE_NS = 7 * DAY_NS
DECAY_LAMBDA = math.log(2.0) / HALF_LIFE_NS
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


def mask_description(row: tuple) -> str:
    raw = row.description
    if raw is None or (isinstance(raw, float) and np.isnan(raw)):
        return ""
    value = TAG_RE.sub(" ", html.unescape(str(raw)))
    for original, placeholder in (
        (row.name, "NAME"),
        (row.city, "LOC"),
        (row.country_name, "LOC"),
        (row.region, "LOC"),
    ):
        original = "" if original is None else str(original).strip()
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


def append_parquet(writer: pq.ParquetWriter | None, frame: pd.DataFrame, path: Path) -> pq.ParquetWriter:
    table = pa.Table.from_pandas(frame, preserve_index=False)
    if writer is None:
        writer = pq.ParquetWriter(path, table.schema, compression="zstd", compression_level=5)
    writer.write_table(table, row_group_size=BATCH_SIZE)
    return writer


def tfidf(values: list[str], vectorizer: HashingVectorizer, idf: np.ndarray):
    matrix = vectorizer.transform(values).tocsr().astype(np.float32, copy=False)
    matrix.data *= idf[matrix.indices]
    normalize(matrix, norm="l2", axis=1, copy=False)
    return matrix


def dot_record(row, record: tuple) -> float:
    positions = np.searchsorted(row.indices, record[2])
    valid = positions < len(row.indices)
    if not np.any(valid):
        return 0.0
    candidate = positions[valid]
    exact = row.indices[candidate] == record[2][valid]
    if not np.any(exact):
        return 0.0
    return float(np.dot(row.data[candidate[exact]].astype(float), record[3][valid][exact]))


class DescriptionState:
    def __init__(self) -> None:
        self.active_sum = np.zeros(FEATURES, dtype=np.float64)
        self.active_heap: list[tuple[int, int, tuple]] = []
        self.active_count = 0
        self.recent: deque[tuple] = deque()
        self.lag: deque[tuple] = deque()
        self.lag_sum = np.zeros(FEATURES, dtype=np.float64)
        self.lag_base_w = 0.0
        self.scale = 1.0
        self.last_time: int | None = None
        self.sequence = 0

    def add_vector(self, target: np.ndarray, record: tuple, multiplier: float) -> None:
        target[record[2]] += multiplier * record[3]

    def current_weight(self, post_ns: int, now_ns: int) -> float:
        return math.exp(-DECAY_LAMBDA * ((now_ns - post_ns) - LAG_GAP_NS))

    def advance(self, now_ns: int) -> None:
        if self.last_time is None:
            self.last_time = now_ns
        elif now_ns > self.last_time:
            self.scale *= math.exp(-DECAY_LAMBDA * (now_ns - self.last_time))
            self.last_time = now_ns
            if self.scale < 1e-40:
                self.lag_sum *= self.scale
                self.lag_base_w *= self.scale
                self.scale = 1.0
        while self.active_heap and self.active_heap[0][0] <= now_ns:
            _, _, record = heapq.heappop(self.active_heap)
            self.add_vector(self.active_sum, record, -1.0)
            self.active_count -= 1
        enter = now_ns - LAG_GAP_NS
        exit_time = now_ns - LAG_END_NS
        while self.recent and self.recent[0][0] <= enter:
            record = self.recent.popleft()
            if record[0] > exit_time:
                base_weight = self.current_weight(record[0], now_ns) / self.scale
                self.add_vector(self.lag_sum, record, base_weight)
                self.lag_base_w += base_weight
                self.lag.append(record)
        while self.lag and self.lag[0][0] <= exit_time:
            record = self.lag.popleft()
            base_weight = self.current_weight(record[0], now_ns) / self.scale
            self.add_vector(self.lag_sum, record, -base_weight)
            self.lag_base_w -= base_weight
        if -1e-8 < self.lag_base_w < 0:
            self.lag_base_w = 0.0

    def add(self, record: tuple) -> None:
        self.sequence += 1
        self.add_vector(self.active_sum, record, 1.0)
        self.active_count += 1
        heapq.heappush(self.active_heap, (record[1], self.sequence, record))
        self.recent.append(record)


def main() -> int:
    if len(sys.argv) != 3:
        raise SystemExit("usage: description_robustness.py WORK_DIR OUTPUT_DIR")
    work_dir = Path(sys.argv[1]).resolve()
    output_dir = Path(sys.argv[2]).resolve()
    core_path = work_dir / "data" / "clean" / "core.parquet"
    text_path = work_dir / "data" / "private" / "text_private.parquet"
    private_dir = work_dir / "data" / "private"
    desc_feature_dir = work_dir / "data" / "description_features"
    outputs = output_dir / "outputs"
    audit = output_dir / "audit"
    for directory in (private_dir, desc_feature_dir, outputs, audit, work_dir / "tmp" / "duckdb"):
        directory.mkdir(parents=True, exist_ok=True)
    log_path = audit / "description_robustness.log"
    log_path.write_text("", encoding="utf-8")
    started = time.time()

    def log(message: str) -> None:
        line = f"{time.strftime('%Y-%m-%dT%H:%M:%S%z')} {message}"
        print(line, flush=True)
        with log_path.open("a", encoding="utf-8") as stream:
            stream.write(line + "\n")

    base_path = private_dir / "description_model_base.parquet"
    con = duckdb.connect(str(work_dir / "tmp" / "description.duckdb"))
    con.execute("SET TimeZone='UTC'")
    con.execute("SET threads=8")
    con.execute("SET memory_limit='8GB'")
    con.execute(f"SET temp_directory={sql_literal(work_dir / 'tmp' / 'duckdb')}")
    con.execute(
        f"""
        COPY (
          SELECT c.id, c.sector, c.fundraising_ts, c.raised_ts, c.fundraising_year,
                 t.country_name, t.name, t.city, t.region, t.description
          FROM read_parquet({sql_literal(core_path)}) c
          JOIN read_parquet({sql_literal(text_path)}) t USING (id, _source_row)
          WHERE c.fundraising_year BETWEEN 2016 AND 2025
            AND c.raised_ts >= c.fundraising_ts
          ORDER BY c.sector, c.fundraising_ts, c.id
        ) TO {sql_literal(base_path)}
        (FORMAT PARQUET, COMPRESSION ZSTD, COMPRESSION_LEVEL 5, ROW_GROUP_SIZE {BATCH_SIZE})
        """
    )
    con.close()
    log(f"description private base bytes={base_path.stat().st_size:,}")

    binary_vectorizer = HashingVectorizer(
        n_features=FEATURES,
        alternate_sign=False,
        binary=True,
        norm=None,
        ngram_range=(1, 2),
        lowercase=False,
        token_pattern=r"(?u)\b\w\w+\b",
        dtype=np.float32,
    )
    document_frequency = np.zeros(FEATURES, dtype=np.int64)
    train_documents = 0
    masked_tmp = private_dir / "masked_description.parquet.tmp"
    masked_path = private_dir / "masked_description.parquet"
    writer = None
    parquet = pq.ParquetFile(base_path)
    for batch_number, batch in enumerate(parquet.iter_batches(batch_size=BATCH_SIZE), start=1):
        frame = batch.to_pandas()
        masked = [mask_description(row) for row in frame.itertuples(index=False)]
        out = frame[["id", "sector", "fundraising_ts", "raised_ts", "fundraising_year"]].copy()
        out["masked_description"] = masked
        writer = append_parquet(writer, out, masked_tmp)
        train_mask = frame["fundraising_year"].to_numpy() <= 2024
        if np.any(train_mask):
            values = [masked[index] for index in np.flatnonzero(train_mask)]
            matrix = binary_vectorizer.transform(values).tocsr()
            document_frequency += np.bincount(matrix.indices, minlength=FEATURES)
            train_documents += len(values)
        if batch_number % 10 == 0:
            log(f"description mask/idf batches={batch_number} rows~={batch_number * BATCH_SIZE:,} rss_gib={psutil.Process().memory_info().rss / 1024**3:.2f}")
    if writer is not None:
        writer.close()
    os.replace(masked_tmp, masked_path)
    idf = (np.log((1.0 + train_documents) / (1.0 + document_frequency)) + 1.0).astype(np.float32)
    np.save(output_dir / "model_artifacts" / "idf_description.npy", idf, allow_pickle=False)

    vectorizer = HashingVectorizer(
        n_features=FEATURES,
        alternate_sign=False,
        norm=None,
        ngram_range=(1, 2),
        lowercase=False,
        token_pattern=r"(?u)\b\w\w+\b",
        dtype=np.float32,
    )
    dataset = ds.dataset(masked_path, format="parquet")
    sectors = sorted(value.as_py() for value in dataset.to_table(columns=["sector"])["sector"].unique())
    feature_paths: list[Path] = []
    identity_rows: list[dict] = []
    for sector_index, sector in enumerate(sectors, start=1):
        frame = (
            dataset.to_table(filter=ds.field("sector") == sector)
            .to_pandas()
            .sort_values(["fundraising_ts", "id"], kind="mergesort")
            .reset_index(drop=True)
        )
        matrix = tfidf(frame["masked_description"].fillna("").astype(str).tolist(), vectorizer, idf)
        timestamps = (
            pd.to_datetime(frame["fundraising_ts"], utc=True)
            .dt.tz_localize(None)
            .to_numpy(dtype="datetime64[ns]")
            .astype(np.int64)
        )
        end_times = (
            pd.to_datetime(frame["raised_ts"], utc=True)
            .dt.tz_localize(None)
            .to_numpy(dtype="datetime64[ns]")
            .astype(np.int64)
        )
        active_h = np.full(len(frame), np.nan, dtype=float)
        lag_g = np.full(len(frame), np.nan, dtype=float)
        state = DescriptionState()
        start = 0
        while start < len(frame):
            stop = start + 1
            while stop < len(frame) and timestamps[stop] == timestamps[start]:
                stop += 1
            now = int(timestamps[start])
            state.advance(now)
            active_records = [item[2] for item in state.active_heap]
            lag_records = list(state.lag)
            for row_index in range(start, stop):
                row = matrix.getrow(row_index)
                if row.nnz and state.active_count > 0:
                    active_h[row_index] = float(
                        np.dot(row.data.astype(float), state.active_sum[row.indices]) / state.active_count
                    )
                if row.nnz and state.lag_base_w > 0:
                    lag_g[row_index] = float(
                        np.dot(row.data.astype(float), state.lag_sum[row.indices]) / state.lag_base_w
                    )
                rank = (int(frame.iloc[row_index]["id"]) * 11400714819323198485) & ((1 << 64) - 1)
                if rank % 10000 == 0 and state.active_count >= 10 and len(state.lag) >= 10 and row.nnz:
                    brute_active = sum(dot_record(row, record) for record in active_records) / len(active_records)
                    weights = np.asarray(
                        [math.exp(-DECAY_LAMBDA * ((now - record[0]) - LAG_GAP_NS)) for record in lag_records]
                    )
                    brute_lag = float(
                        np.dot(weights, [dot_record(row, record) for record in lag_records]) / weights.sum()
                    )
                    key = hashlib.sha256(str(int(frame.iloc[row_index]["id"])).encode()).hexdigest()[:12]
                    identity_rows.extend(
                        [
                            {"focal_key": key, "rank": rank, "pool": "active", "formula": active_h[row_index], "brute": brute_active, "abs_error": abs(active_h[row_index] - brute_active)},
                            {"focal_key": key, "rank": rank, "pool": "lag_weighted", "formula": lag_g[row_index], "brute": brute_lag, "abs_error": abs(lag_g[row_index] - brute_lag)},
                        ]
                    )
            for row_index in range(start, stop):
                row = matrix.getrow(row_index)
                begin, end = row.indptr[0], row.indptr[1]
                record = (
                    int(timestamps[row_index]),
                    int(end_times[row_index]),
                    row.indices[begin:end].copy(),
                    row.data[begin:end].astype(float, copy=True),
                )
                state.add(record)
            start = stop
        features = frame[["id"]].copy()
        features["H_active_description"] = active_h
        features["G_lag_description"] = lag_g
        slug = re.sub(r"[^a-z0-9]+", "_", sector.lower()).strip("_")
        feature_path = desc_feature_dir / f"sector_{slug}.parquet"
        features.to_parquet(feature_path, index=False, compression="zstd")
        feature_paths.append(feature_path)
        log(f"description sector {sector_index}/{len(sectors)} complete sector={sector} rows={len(frame):,} nnz={matrix.nnz:,} elapsed={time.time()-started:.1f}s")

    identity = pd.DataFrame(identity_rows)
    selected = (
        identity[["focal_key", "rank"]]
        .drop_duplicates()
        .sort_values("rank")
        .head(50)
        .reset_index(drop=True)
    )
    selected["check_id"] = np.arange(1, len(selected) + 1, dtype=np.int64)
    identity = (
        identity.merge(selected, on=["focal_key", "rank"], how="inner")
        .drop(columns=["focal_key", "rank"])
        .sort_values(["check_id", "pool"])
    )
    atomic_csv(identity, outputs / "description_pool_identity_check.csv")

    feature_list = "[" + ",".join(sql_literal(path) for path in feature_paths) + "]"
    model_path = output_dir / "data" / "model_data.parquet"
    desc_model_path = work_dir / "data" / "description_model.parquet"
    con = duckdb.connect(str(work_dir / "tmp" / "description_join.duckdb"))
    con.execute("SET TimeZone='UTC'")
    con.execute(
        f"""
        COPY (
          SELECT m.*, d.H_active_description, d.G_lag_description
          FROM read_parquet({sql_literal(model_path)}) m
          JOIN read_parquet({feature_list}) d USING (id)
          WHERE m.analysis_washin_eligible
            AND m.fundraising_year BETWEEN 2016 AND 2024
            AND m.pool_size_active >= 10
            AND m.lag_kish_n >= 10
            AND d.H_active_description IS NOT NULL
            AND d.G_lag_description IS NOT NULL
        ) TO {sql_literal(desc_model_path)}
        (FORMAT PARQUET, COMPRESSION ZSTD)
        """
    )
    con.close()
    model_columns = [
        "country_name", "activity", "week_id", "gender", "repaymentInterval", "posting_dow", "posting_hour",
        "log_funding_hours", "C_active", "V_lag", "H_active_description", "G_lag_description",
    ] + CORE_CONTROLS
    model_columns = list(dict.fromkeys(model_columns))
    model = pd.read_parquet(desc_model_path, columns=model_columns)
    for column in ["country_name", "activity", "week_id", "gender", "repaymentInterval", "posting_dow", "posting_hour"]:
        model[column] = model[column].astype("category")
    _, main_scalers = load_scalers(outputs / "scaler_parameters.csv")
    main = main_scalers["active_raw"]
    desc_scaler = {
        "C": main["C"],
        "V": main["V"],
        "H": {"mean": float(model["H_active_description"].mean()), "std": float(model["H_active_description"].std()), "p25": float(model["H_active_description"].quantile(.25)), "p50": float(model["H_active_description"].quantile(.5)), "p75": float(model["H_active_description"].quantile(.75))},
        "G": {"mean": float(model["G_lag_description"].mean()), "std": float(model["G_lag_description"].std()), "p25": float(model["G_lag_description"].quantile(.25)), "p50": float(model["G_lag_description"].quantile(.5)), "p75": float(model["G_lag_description"].quantile(.75))},
    }
    sources = {"C": "C_active", "H": "H_active_description", "V": "V_lag", "G": "G_lag_description"}
    mapping: dict[str, str] = {}
    for variable, source in sources.items():
        column = f"desc_{variable}z"
        model[column] = ((model[source] - float(desc_scaler[variable]["mean"])) / float(desc_scaler[variable]["std"])).astype(np.float32)
        mapping[variable] = column
    model["desc_CH"] = model["desc_Cz"] * model["desc_Hz"]
    model["desc_VG"] = model["desc_Vz"] * model["desc_Gz"]
    mapping.update({"CH": "desc_CH", "VG": "desc_VG"})
    regressors = [mapping[key] for key in ("C", "H", "CH", "V", "G", "VG")] + CORE_CONTROLS
    fit = pf.feols(
        f"log_funding_hours ~ {' + '.join(regressors)} | {' + '.join(FIXED_EFFECTS)}",
        model,
        vcov={"CRV1": "country_name + week_id"},
        copy_data=False,
        store_data=False,
        lean=True,
    )
    tidy = fit.tidy().reset_index().rename(columns={"Coefficient": "coefficient"})
    if "coefficient" not in tidy.columns:
        tidy = tidy.rename(columns={tidy.columns[0]: "coefficient"})
    reverse = {value: key for key, value in mapping.items()}
    tidy = tidy[tidy["coefficient"].isin(reverse)].copy()
    tidy["term"] = tidy["coefficient"].map(reverse)
    tidy["n"] = int(getattr(fit, "_N", 0))
    tidy["representation"] = "masked description hashed TF-IDF"
    tidy = tidy.rename(columns={"Estimate": "estimate", "Std. Error": "std_error", "Pr(>|t|)": "p_value", "2.5%": "ci_low", "97.5%": "ci_high"})
    atomic_csv(tidy[["representation", "n", "term", "estimate", "std_error", "p_value", "ci_low", "ci_high"]], outputs / "description_robustness.csv")
    atomic_json(
        {
            "training_documents": train_documents,
            "features": FEATURES,
            "ngrams": [1, 2],
            "idf_fit_period": "2016-2024 only",
            "model_rows": int(getattr(fit, "_N", 0)),
            "identity_focal_loans": int(identity["check_id"].nunique()),
            "identity_max_abs_error": float(identity["abs_error"].max()),
            "identity_threshold": 1e-9,
            "identity_passed": bool(len(identity) >= 100 and identity["abs_error"].max() <= 1e-9),
            "elapsed_seconds": round(time.time() - started, 3),
        },
        audit / "description_robustness_manifest.json",
    )
    log(f"description robustness complete n={int(getattr(fit, '_N', 0)):,} elapsed={time.time()-started:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
