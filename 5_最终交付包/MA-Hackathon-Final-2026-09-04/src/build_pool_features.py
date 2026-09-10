#!/usr/bin/env python3
"""Stage 3: reconstruct active, posting-time, and recent-history narrative pools.

Average focal-to-pool cosine is calculated through the exact centroid identity;
deterministically sampled focal loans are also checked by brute force.
"""

from __future__ import annotations

import hashlib
import heapq
import json
import math
import os
import re
import sys
import time
from collections import deque
from pathlib import Path

import numpy as np
import pandas as pd
import psutil
import pyarrow.dataset as ds
import pyarrow.parquet as pq
from scipy import sparse
from sklearn.feature_extraction.text import HashingVectorizer
from sklearn.preprocessing import normalize


TFIDF_FEATURES = 2**17
DAY_NS = 86_400 * 1_000_000_000
WINDOW_14_NS = 14 * DAY_NS
WINDOW_16_NS = 16 * DAY_NS
LAG_GAP_NS = 35 * DAY_NS
LAG_END_NS = 65 * DAY_NS
HALF_LIFE_NS = 7 * DAY_NS
DECAY_LAMBDA = math.log(2.0) / HALF_LIFE_NS
GLOBAL_START_NS = np.datetime64("2016-01-01T00:00:00", "ns").astype(np.int64)
WASH_IN_END_NS = GLOBAL_START_NS + LAG_END_NS
TOKEN_RE = re.compile(r"(?u)\b\w\w+\b")


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


def residual_analyzer(value: str) -> list[str]:
    features: list[str] = []
    for segment in str(value).split(" __gap__ "):
        tokens = TOKEN_RE.findall(segment)
        features.extend(tokens)
        features.extend(" ".join(tokens[index : index + 2]) for index in range(len(tokens) - 1))
    return features


def tfidf_matrix(
    values: list[str], vectorizer: HashingVectorizer, idf: np.ndarray
) -> sparse.csr_matrix:
    matrix = vectorizer.transform(values).tocsr().astype(np.float32, copy=False)
    matrix.data *= idf[matrix.indices]
    normalize(matrix, norm="l2", axis=1, copy=False)
    return matrix


def row_record(
    post_ns: int,
    end_ns: int,
    raw: sparse.csr_matrix,
    residual: sparse.csr_matrix,
    row_index: int,
) -> tuple[int, int, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    raw_start, raw_stop = raw.indptr[row_index : row_index + 2]
    res_start, res_stop = residual.indptr[row_index : row_index + 2]
    return (
        int(post_ns),
        int(end_ns),
        raw.indices[raw_start:raw_stop].copy(),
        raw.data[raw_start:raw_stop].astype(np.float64, copy=True),
        residual.indices[res_start:res_stop].copy(),
        residual.data[res_start:res_stop].astype(np.float64, copy=True),
    )


def add_record(
    raw_sum: np.ndarray,
    residual_sum: np.ndarray,
    record: tuple,
    multiplier: float = 1.0,
) -> None:
    raw_sum[record[2]] += multiplier * record[3]
    residual_sum[record[4]] += multiplier * record[5]


def overlap(row: sparse.csr_matrix, centroid_sum: np.ndarray, denominator: float) -> float:
    if denominator <= 0 or row.nnz == 0:
        return float("nan")
    return float(np.dot(row.data.astype(np.float64), centroid_sum[row.indices]) / denominator)


def brute_overlap(row: sparse.csr_matrix, records: list[tuple], residual: bool = False) -> float:
    if not records or row.nnz == 0:
        return float("nan")
    indices_position = 4 if residual else 2
    data_position = 5 if residual else 3
    total = 0.0
    for record in records:
        positions = np.searchsorted(row.indices, record[indices_position])
        valid = positions < len(row.indices)
        if np.any(valid):
            candidate_positions = positions[valid]
            exact = row.indices[candidate_positions] == record[indices_position][valid]
            if np.any(exact):
                total += float(
                    np.dot(
                        row.data[candidate_positions[exact]].astype(np.float64),
                        record[data_position][valid][exact],
                    )
                )
    return total / len(records)


def brute_weighted_overlap(
    row: sparse.csr_matrix,
    records: list[tuple],
    now_ns: int,
    residual: bool = False,
) -> float:
    if not records or row.nnz == 0:
        return float("nan")
    indices_position = 4 if residual else 2
    data_position = 5 if residual else 3
    numerator = 0.0
    denominator = 0.0
    for record in records:
        age_after_gap = (now_ns - record[0]) - LAG_GAP_NS
        weight = math.exp(-DECAY_LAMBDA * age_after_gap)
        positions = np.searchsorted(row.indices, record[indices_position])
        valid = positions < len(row.indices)
        dot = 0.0
        if np.any(valid):
            candidate_positions = positions[valid]
            exact = row.indices[candidate_positions] == record[indices_position][valid]
            if np.any(exact):
                dot = float(
                    np.dot(
                        row.data[candidate_positions[exact]].astype(np.float64),
                        record[data_position][valid][exact],
                    )
                )
        numerator += weight * dot
        denominator += weight
    return numerator / denominator if denominator > 0 else float("nan")


def selection_rank(loan_id: int) -> int:
    return (int(loan_id) * 11400714819323198485) & ((1 << 64) - 1)


class PoolState:
    def __init__(self) -> None:
        self.active_raw = np.zeros(TFIDF_FEATURES, dtype=np.float64)
        self.active_res = np.zeros(TFIDF_FEATURES, dtype=np.float64)
        self.active_heap: list[tuple[int, int, tuple]] = []
        self.active_count = 0
        self.sequence = 0

        self.q14_raw = np.zeros(TFIDF_FEATURES, dtype=np.float64)
        self.q14_res = np.zeros(TFIDF_FEATURES, dtype=np.float64)
        self.q14: deque[tuple] = deque()
        self.q16_raw = np.zeros(TFIDF_FEATURES, dtype=np.float64)
        self.q16_res = np.zeros(TFIDF_FEATURES, dtype=np.float64)
        self.q16: deque[tuple] = deque()

        self.recent: deque[tuple] = deque()
        self.lag: deque[tuple] = deque()
        self.lag_raw = np.zeros(TFIDF_FEATURES, dtype=np.float64)
        self.lag_res = np.zeros(TFIDF_FEATURES, dtype=np.float64)
        self.lag_base_w = 0.0
        self.lag_base_w2 = 0.0

        self.completed_events: list[tuple[int, int, tuple]] = []
        self.completed_active: list[tuple[int, int, tuple]] = []
        self.completed_raw = np.zeros(TFIDF_FEATURES, dtype=np.float64)
        self.completed_res = np.zeros(TFIDF_FEATURES, dtype=np.float64)
        self.completed_base_w = 0.0
        self.completed_base_w2 = 0.0
        self.completed_count = 0

        self.scale = 1.0
        self.last_time: int | None = None

    def _current_weight(self, post_ns: int, now_ns: int) -> float:
        return math.exp(-DECAY_LAMBDA * ((now_ns - post_ns) - LAG_GAP_NS))

    def _rebase_if_needed(self) -> None:
        if self.scale >= 1e-40:
            return
        for array in (self.lag_raw, self.lag_res, self.completed_raw, self.completed_res):
            array *= self.scale
        self.lag_base_w *= self.scale
        self.completed_base_w *= self.scale
        self.lag_base_w2 *= self.scale * self.scale
        self.completed_base_w2 *= self.scale * self.scale
        self.scale = 1.0

    def advance(self, now_ns: int) -> None:
        if self.last_time is None:
            self.last_time = now_ns
        elif now_ns > self.last_time:
            self.scale *= math.exp(-DECAY_LAMBDA * (now_ns - self.last_time))
            self.last_time = now_ns
            self._rebase_if_needed()

        while self.active_heap and self.active_heap[0][0] <= now_ns:
            _, _, record = heapq.heappop(self.active_heap)
            add_record(self.active_raw, self.active_res, record, -1.0)
            self.active_count -= 1

        cutoff_14 = now_ns - WINDOW_14_NS
        while self.q14 and self.q14[0][0] < cutoff_14:
            record = self.q14.popleft()
            add_record(self.q14_raw, self.q14_res, record, -1.0)
        cutoff_16 = now_ns - WINDOW_16_NS
        while self.q16 and self.q16[0][0] < cutoff_16:
            record = self.q16.popleft()
            add_record(self.q16_raw, self.q16_res, record, -1.0)

        enter_cutoff = now_ns - LAG_GAP_NS
        exit_cutoff = now_ns - LAG_END_NS
        while self.recent and self.recent[0][0] <= enter_cutoff:
            record = self.recent.popleft()
            if record[0] > exit_cutoff:
                weight_current = self._current_weight(record[0], now_ns)
                weight_base = weight_current / self.scale
                add_record(self.lag_raw, self.lag_res, record, weight_base)
                self.lag_base_w += weight_base
                self.lag_base_w2 += weight_base * weight_base
                self.lag.append(record)
        while self.lag and self.lag[0][0] <= exit_cutoff:
            record = self.lag.popleft()
            weight_current = self._current_weight(record[0], now_ns)
            weight_base = weight_current / self.scale
            add_record(self.lag_raw, self.lag_res, record, -weight_base)
            self.lag_base_w -= weight_base
            self.lag_base_w2 -= weight_base * weight_base

        while self.completed_active and self.completed_active[0][0] <= now_ns:
            _, _, record = heapq.heappop(self.completed_active)
            weight_current = self._current_weight(record[0], now_ns)
            weight_base = weight_current / self.scale
            add_record(self.completed_raw, self.completed_res, record, -weight_base)
            self.completed_base_w -= weight_base
            self.completed_base_w2 -= weight_base * weight_base
            self.completed_count -= 1
        while self.completed_events and self.completed_events[0][0] <= now_ns:
            _, sequence, record = heapq.heappop(self.completed_events)
            end_window = record[0] + LAG_END_NS
            if end_window <= now_ns:
                continue
            weight_current = self._current_weight(record[0], now_ns)
            weight_base = weight_current / self.scale
            add_record(self.completed_raw, self.completed_res, record, weight_base)
            self.completed_base_w += weight_base
            self.completed_base_w2 += weight_base * weight_base
            self.completed_count += 1
            heapq.heappush(self.completed_active, (end_window, sequence, record))

        for name in (
            "lag_base_w",
            "lag_base_w2",
            "completed_base_w",
            "completed_base_w2",
        ):
            if -1e-8 < getattr(self, name) < 0:
                setattr(self, name, 0.0)

    def add_after_focals(self, record: tuple) -> None:
        post_ns, end_ns = record[0], record[1]
        self.sequence += 1
        if end_ns > post_ns:
            add_record(self.active_raw, self.active_res, record, 1.0)
            self.active_count += 1
            heapq.heappush(self.active_heap, (end_ns, self.sequence, record))
        add_record(self.q14_raw, self.q14_res, record, 1.0)
        self.q14.append(record)
        add_record(self.q16_raw, self.q16_res, record, 1.0)
        self.q16.append(record)
        self.recent.append(record)

        start = max(post_ns + LAG_GAP_NS, end_ns)
        end_window = post_ns + LAG_END_NS
        if start < end_window:
            heapq.heappush(self.completed_events, (start, self.sequence, record))

    def lag_weight(self) -> float:
        return max(0.0, self.scale * self.lag_base_w)

    def completed_weight(self) -> float:
        return max(0.0, self.scale * self.completed_base_w)

    @staticmethod
    def kish(sum_w: float, sum_w2: float) -> float:
        if sum_w <= 0 or sum_w2 <= 0:
            return 0.0
        return max(0.0, (sum_w * sum_w) / sum_w2)


def process_sector(
    frame: pd.DataFrame,
    raw_matrix: sparse.csr_matrix,
    residual_matrix: sparse.csr_matrix,
    identity_rows: list[dict],
) -> pd.DataFrame:
    n_rows = len(frame)
    columns = {
        "pool_size_active": np.zeros(n_rows, dtype=np.int32),
        "H_active_raw": np.full(n_rows, np.nan, dtype=np.float64),
        "H_active_residual": np.full(n_rows, np.nan, dtype=np.float64),
        "pool_size_14d": np.zeros(n_rows, dtype=np.int32),
        "H_14d_raw": np.full(n_rows, np.nan, dtype=np.float64),
        "H_14d_residual": np.full(n_rows, np.nan, dtype=np.float64),
        "pool_size_16d": np.zeros(n_rows, dtype=np.int32),
        "H_16d_raw": np.full(n_rows, np.nan, dtype=np.float64),
        "H_16d_residual": np.full(n_rows, np.nan, dtype=np.float64),
        "lag_pool_raw_count": np.zeros(n_rows, dtype=np.int32),
        "lag_weight": np.zeros(n_rows, dtype=np.float64),
        "lag_kish_n": np.zeros(n_rows, dtype=np.float64),
        "G_lag_raw": np.full(n_rows, np.nan, dtype=np.float64),
        "G_lag_residual": np.full(n_rows, np.nan, dtype=np.float64),
        "lag_completed_raw_count": np.zeros(n_rows, dtype=np.int32),
        "lag_completed_weight": np.zeros(n_rows, dtype=np.float64),
        "lag_completed_kish_n": np.zeros(n_rows, dtype=np.float64),
        "G_lag_completed_raw": np.full(n_rows, np.nan, dtype=np.float64),
        "G_lag_completed_residual": np.full(n_rows, np.nan, dtype=np.float64),
    }
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
    state = PoolState()
    start = 0
    while start < n_rows:
        stop = start + 1
        while stop < n_rows and timestamps[stop] == timestamps[start]:
            stop += 1
        now_ns = int(timestamps[start])
        state.advance(now_ns)
        active_records = [entry[2] for entry in state.active_heap]
        lag_records = list(state.lag)
        for row_index in range(start, stop):
            raw_row = raw_matrix.getrow(row_index)
            residual_row = residual_matrix.getrow(row_index)
            columns["pool_size_active"][row_index] = state.active_count
            columns["H_active_raw"][row_index] = overlap(raw_row, state.active_raw, state.active_count)
            columns["H_active_residual"][row_index] = overlap(
                residual_row, state.active_res, state.active_count
            )
            columns["pool_size_14d"][row_index] = len(state.q14)
            columns["H_14d_raw"][row_index] = overlap(raw_row, state.q14_raw, len(state.q14))
            columns["H_14d_residual"][row_index] = overlap(
                residual_row, state.q14_res, len(state.q14)
            )
            columns["pool_size_16d"][row_index] = len(state.q16)
            columns["H_16d_raw"][row_index] = overlap(raw_row, state.q16_raw, len(state.q16))
            columns["H_16d_residual"][row_index] = overlap(
                residual_row, state.q16_res, len(state.q16)
            )
            lag_weight = state.lag_weight()
            columns["lag_pool_raw_count"][row_index] = len(state.lag)
            columns["lag_weight"][row_index] = lag_weight
            columns["lag_kish_n"][row_index] = state.kish(state.lag_base_w, state.lag_base_w2)
            columns["G_lag_raw"][row_index] = overlap(raw_row, state.lag_raw, state.lag_base_w)
            columns["G_lag_residual"][row_index] = overlap(
                residual_row, state.lag_res, state.lag_base_w
            )
            completed_weight = state.completed_weight()
            columns["lag_completed_raw_count"][row_index] = state.completed_count
            columns["lag_completed_weight"][row_index] = completed_weight
            columns["lag_completed_kish_n"][row_index] = state.kish(
                state.completed_base_w, state.completed_base_w2
            )
            columns["G_lag_completed_raw"][row_index] = overlap(
                raw_row, state.completed_raw, state.completed_base_w
            )
            columns["G_lag_completed_residual"][row_index] = overlap(
                residual_row, state.completed_res, state.completed_base_w
            )

            loan_id = int(frame.iloc[row_index]["id"])
            rank = selection_rank(loan_id)
            if (
                rank % 3000 == 0
                and state.active_count >= 10
                and len(state.q16) >= 10
                and len(state.lag) >= 10
                and raw_row.nnz > 0
                and residual_row.nnz > 0
            ):
                focal_key = hashlib.sha256(str(loan_id).encode("utf-8")).hexdigest()[:12]
                checks = [
                    (
                        "active",
                        columns["H_active_raw"][row_index],
                        brute_overlap(raw_row, active_records, False),
                        columns["H_active_residual"][row_index],
                        brute_overlap(residual_row, active_records, True),
                        len(active_records),
                    ),
                    (
                        "posting_16d",
                        columns["H_16d_raw"][row_index],
                        brute_overlap(raw_row, list(state.q16), False),
                        columns["H_16d_residual"][row_index],
                        brute_overlap(residual_row, list(state.q16), True),
                        len(state.q16),
                    ),
                    (
                        "lag_weighted_35_65d",
                        columns["G_lag_raw"][row_index],
                        brute_weighted_overlap(raw_row, lag_records, now_ns, False),
                        columns["G_lag_residual"][row_index],
                        brute_weighted_overlap(residual_row, lag_records, now_ns, True),
                        len(lag_records),
                    ),
                ]
                for pool_type, formula_raw, brute_raw, formula_res, brute_res, pool_n in checks:
                    identity_rows.append(
                        {
                            "focal_key": focal_key,
                            "selection_rank": rank,
                            "pool_type": pool_type,
                            "pool_n": pool_n,
                            "formula_raw": formula_raw,
                            "brute_raw": brute_raw,
                            "abs_error_raw": abs(formula_raw - brute_raw),
                            "formula_residual": formula_res,
                            "brute_residual": brute_res,
                            "abs_error_residual": abs(formula_res - brute_res),
                        }
                    )

        for row_index in range(start, stop):
            state.add_after_focals(
                row_record(
                    int(timestamps[row_index]),
                    int(end_times[row_index]),
                    raw_matrix,
                    residual_matrix,
                    row_index,
                )
            )
        start = stop

    result = frame[["id", "sector", "fundraising_ts", "fundraising_year", "boilerplate_share"]].copy()
    result["analysis_washin_eligible"] = timestamps >= WASH_IN_END_NS
    result["raw_text_nonempty"] = np.diff(raw_matrix.indptr) > 0
    result["residual_text_nonempty"] = np.diff(residual_matrix.indptr) > 0
    for name, values in columns.items():
        result[name] = values
    return result


def main() -> int:
    if len(sys.argv) not in (3, 4):
        raise SystemExit("usage: build_pool_features.py WORK_DIR OUTPUT_DIR [SECTOR_REGEX]")
    work_dir = Path(sys.argv[1]).resolve()
    output_dir = Path(sys.argv[2]).resolve()
    sector_regex = re.compile(sys.argv[3]) if len(sys.argv) == 4 else None
    processed_path = work_dir / "data" / "private" / "processed_use.parquet"
    idf_raw = np.load(output_dir / "model_artifacts" / "idf_raw_use.npy", allow_pickle=False)
    idf_residual = np.load(
        output_dir / "model_artifacts" / "idf_residual_use.npy", allow_pickle=False
    )
    feature_dir = output_dir / "data" / "features"
    outputs = output_dir / "outputs"
    audit = output_dir / "audit"
    for directory in (feature_dir, outputs, audit):
        directory.mkdir(parents=True, exist_ok=True)
    log_path = audit / ("stage3_pools_dev.log" if sector_regex else "stage3_pools.log")
    log_path.write_text("", encoding="utf-8")
    started = time.time()

    def log(message: str) -> None:
        line = f"{time.strftime('%Y-%m-%dT%H:%M:%S%z')} {message}"
        print(line, flush=True)
        with log_path.open("a", encoding="utf-8") as stream:
            stream.write(line + "\n")

    dataset = ds.dataset(processed_path, format="parquet")
    sectors = sorted(value.as_py() for value in ds.dataset(processed_path).to_table(columns=["sector"])["sector"].unique())
    if sector_regex:
        sectors = [sector for sector in sectors if sector_regex.search(sector)]
    raw_vectorizer = HashingVectorizer(
        n_features=TFIDF_FEATURES,
        alternate_sign=False,
        norm=None,
        ngram_range=(1, 2),
        lowercase=False,
        token_pattern=r"(?u)\b\w\w+\b",
        dtype=np.float32,
    )
    residual_vectorizer = HashingVectorizer(
        n_features=TFIDF_FEATURES,
        alternate_sign=False,
        norm=None,
        analyzer=residual_analyzer,
        dtype=np.float32,
    )
    identity_rows: list[dict] = []
    feature_paths: list[Path] = []
    total_rows = 0
    for sector_index, sector in enumerate(sectors, start=1):
        table = dataset.to_table(filter=ds.field("sector") == sector)
        frame = table.to_pandas().sort_values(["fundraising_ts", "id"], kind="mergesort").reset_index(drop=True)
        valid = pd.to_datetime(frame["raised_ts"], utc=True) >= pd.to_datetime(
            frame["fundraising_ts"], utc=True
        )
        frame = frame.loc[valid].reset_index(drop=True)
        raw_matrix = tfidf_matrix(frame["masked_use"].fillna("").astype(str).tolist(), raw_vectorizer, idf_raw)
        residual_matrix = tfidf_matrix(
            frame["residual_use"].fillna("").astype(str).tolist(), residual_vectorizer, idf_residual
        )
        log(
            f"sector_start {sector_index}/{len(sectors)} sector={sector} rows={len(frame):,} "
            f"raw_nnz={raw_matrix.nnz:,} residual_nnz={residual_matrix.nnz:,} "
            f"rss_gib={psutil.Process().memory_info().rss / 1024**3:.2f}"
        )
        features = process_sector(frame, raw_matrix, residual_matrix, identity_rows)
        slug = re.sub(r"[^a-z0-9]+", "_", sector.lower()).strip("_") or "unknown"
        suffix = "_dev" if sector_regex else ""
        path = feature_dir / f"sector_{slug}{suffix}.parquet"
        features.to_parquet(path, index=False, compression="zstd")
        feature_paths.append(path)
        total_rows += len(features)
        log(
            f"sector_complete sector={sector} elapsed_seconds={time.time() - started:.1f} "
            f"feature_bytes={path.stat().st_size:,} rss_gib={psutil.Process().memory_info().rss / 1024**3:.2f}"
        )
        del table, frame, raw_matrix, residual_matrix, features

    identity = pd.DataFrame(identity_rows)
    if len(identity):
        selected = (
            identity[["focal_key", "selection_rank"]]
            .drop_duplicates()
            .sort_values("selection_rank")
            .head(200)
            .reset_index(drop=True)
        )
        selected["check_id"] = np.arange(1, len(selected) + 1, dtype=np.int64)
        identity = (
            identity.merge(selected, on=["focal_key", "selection_rank"], how="inner")
            .sort_values(["selection_rank", "pool_type"])
            .drop(columns=["focal_key", "selection_rank"])
            .reset_index(drop=True)
        )
    identity_name = "pool_identity_check_dev.csv" if sector_regex else "pool_identity_check.csv"
    atomic_csv(identity, outputs / identity_name)
    summary = pd.DataFrame(
        [
            {
                "focal_loans": int(identity["check_id"].nunique()) if len(identity) else 0,
                "pool_checks": int(len(identity)),
                "max_abs_error_raw": float(identity["abs_error_raw"].max()) if len(identity) else np.nan,
                "max_abs_error_residual": float(identity["abs_error_residual"].max()) if len(identity) else np.nan,
                "acceptance_threshold": 1e-9,
                "passed": bool(
                    len(identity) >= 600
                    and identity["abs_error_raw"].max() <= 1e-9
                    and identity["abs_error_residual"].max() <= 1e-9
                )
                if len(identity)
                else False,
            }
        ]
    )
    summary_name = "pool_identity_summary_dev.csv" if sector_regex else "pool_identity_summary.csv"
    atomic_csv(summary, outputs / summary_name)

    manifest = {
        "sectors_processed": sectors,
        "rows_processed": total_rows,
        "feature_parts": [str(path) for path in feature_paths],
        "same_timestamp_rule": "remove exits at or before t; calculate focal features; then add all listings posted at t",
        "active_pool": "same sector, fundraising_ts < focal_ts < raised_ts",
        "posting_windows_days": [14, 16],
        "lag_pool": "same sector, posting age in [35,65) days, 7-day half-life",
        "lag_completed_sensitivity": "lag member also has raised_ts <= focal_ts",
        "wash_in_end_utc": "2016-03-06T00:00:00Z",
        "identity_focal_loans": int(identity["check_id"].nunique()) if len(identity) else 0,
        "identity_passed": bool(summary.iloc[0]["passed"]),
        "elapsed_seconds": round(time.time() - started, 3),
    }
    manifest_name = "stage3_feature_manifest_dev.json" if sector_regex else "stage3_feature_manifest.json"
    atomic_json(manifest, audit / manifest_name)
    log(
        f"stage3 complete rows={total_rows:,} identity_pass={bool(summary.iloc[0]['passed'])} "
        f"elapsed_seconds={time.time() - started:.1f}"
    )
    return 0 if (sector_regex or bool(summary.iloc[0]["passed"])) else 2


if __name__ == "__main__":
    raise SystemExit(main())
