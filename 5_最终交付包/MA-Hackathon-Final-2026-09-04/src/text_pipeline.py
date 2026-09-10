#!/usr/bin/env python3
"""Stage 2: privacy masking, train-only recurring-language rules, and TF-IDF IDF.

The full narratives remain under the separate work directory. Only aggregate,
masked phrase diagnostics and non-text model artifacts enter the deliverable.
"""

from __future__ import annotations

import html
import json
import math
import os
import re
import sys
import time
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import psutil
import pyarrow as pa
import pyarrow.parquet as pq
from sklearn.feature_extraction.text import HashingVectorizer
from sklearn.utils import murmurhash3_32


TRAIN_END_YEAR = 2024
RANDOM_SEED = 20260904
TEMPLATE_HASH_FEATURES = 2**20
TFIDF_FEATURES = 2**17
TEMPLATE_MIN_SHARE = 0.0005
TEMPLATE_MIN_DOCS_FLOOR = 500
TEMPLATE_MIN_COUNTRIES = 3
BATCH_SIZE = 50000

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


def atomic_json(payload: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(temporary, path)


def mask_one(row: tuple) -> str:
    raw = row.use
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


def fivegrams(value: str) -> list[str]:
    tokens = TOKEN_RE.findall(value)
    return [" ".join(tokens[index : index + 5]) for index in range(max(0, len(tokens) - 4))]


def feature_index(phrase: str, n_features: int = TEMPLATE_HASH_FEATURES) -> int:
    return abs(murmurhash3_32(phrase, seed=0, positive=False)) % n_features


def remove_phrases(value: str, approved: set[str]) -> tuple[str, float]:
    tokens = TOKEN_RE.findall(value)
    if len(tokens) < 5 or not approved:
        return value, 0.0
    remove = np.zeros(len(tokens), dtype=bool)
    for index in range(len(tokens) - 4):
        phrase = " ".join(tokens[index : index + 5])
        if phrase in approved:
            remove[index : index + 5] = True
    segments: list[str] = []
    current: list[str] = []
    for index, token in enumerate(tokens):
        if remove[index]:
            if current:
                segments.append(" ".join(current))
                current = []
        else:
            current.append(token)
    if current:
        segments.append(" ".join(current))
    # Preserve an explicit boundary so the residual bigram analyzer cannot
    # create a synthetic phrase across removed boilerplate.
    return " __gap__ ".join(segments), float(np.mean(remove))


def residual_analyzer(value: str) -> list[str]:
    features: list[str] = []
    for segment in str(value).split(" __gap__ "):
        tokens = TOKEN_RE.findall(segment)
        features.extend(tokens)
        features.extend(" ".join(tokens[index : index + 2]) for index in range(len(tokens) - 1))
    return features


def append_parquet(writer: pq.ParquetWriter | None, frame: pd.DataFrame, path: Path) -> pq.ParquetWriter:
    table = pa.Table.from_pandas(frame, preserve_index=False)
    if writer is None:
        writer = pq.ParquetWriter(
            path,
            table.schema,
            compression="zstd",
            compression_level=5,
            use_dictionary=True,
        )
    writer.write_table(table, row_group_size=BATCH_SIZE)
    return writer


def accumulate_document_frequency(
    vectorizer: HashingVectorizer, values: list[str], target: np.ndarray
) -> None:
    matrix = vectorizer.transform(values).tocsr()
    target += np.bincount(matrix.indices, minlength=len(target)).astype(target.dtype, copy=False)


def main() -> int:
    if len(sys.argv) != 3:
        raise SystemExit("usage: text_pipeline.py WORK_DIR OUTPUT_DIR")
    work_dir = Path(sys.argv[1]).resolve()
    output_dir = Path(sys.argv[2]).resolve()
    core_path = work_dir / "data" / "clean" / "core.parquet"
    text_path = work_dir / "data" / "private" / "text_private.parquet"
    private_dir = work_dir / "data" / "private"
    model_artifacts = output_dir / "model_artifacts"
    outputs = output_dir / "outputs"
    audit = output_dir / "audit"
    logs = audit
    for directory in (private_dir, model_artifacts, outputs, audit, work_dir / "tmp" / "duckdb"):
        directory.mkdir(parents=True, exist_ok=True)

    log_path = logs / "stage2_text.log"
    log_path.write_text("", encoding="utf-8")
    started = time.time()

    def log(message: str) -> None:
        line = f"{time.strftime('%Y-%m-%dT%H:%M:%S%z')} {message}"
        print(line, flush=True)
        with log_path.open("a", encoding="utf-8") as stream:
            stream.write(line + "\n")

    con = duckdb.connect(str(work_dir / "tmp" / "text_pipeline.duckdb"))
    con.execute("SET TimeZone='UTC'")
    con.execute("SET threads=8")
    con.execute("SET memory_limit='8GB'")
    con.execute(f"SET temp_directory={sql_literal(work_dir / 'tmp' / 'duckdb')}")
    base_path = private_dir / "text_model_base.parquet"
    con.execute(
        f"""
        COPY (
          SELECT
            c.id,
            c._source_row,
            c.sector,
            c.fundraising_ts,
            c.raised_ts,
            c.fundraising_year,
            t.country_name,
            t.name,
            t.city,
            t.region,
            t.use
          FROM read_parquet({sql_literal(core_path)}) c
          JOIN read_parquet({sql_literal(text_path)}) t USING (id, _source_row)
          WHERE c.fundraising_year BETWEEN 2016 AND 2025
          ORDER BY c.sector, c.fundraising_ts, c.id
        ) TO {sql_literal(base_path)}
        (FORMAT PARQUET, COMPRESSION ZSTD, COMPRESSION_LEVEL 5, ROW_GROUP_SIZE {BATCH_SIZE})
        """
    )
    con.close()
    log(f"private model base ready bytes={base_path.stat().st_size:,}")

    parquet = pq.ParquetFile(base_path)
    countries = sorted(
        set(
            pq.read_table(base_path, columns=["country_name"])
            .column("country_name")
            .to_pylist()
        )
    )
    country_code = {country: index for index, country in enumerate(countries)}
    if len(country_code) > 63:
        raise RuntimeError("country bitset exceeds uint64 capacity")

    template_vectorizer = HashingVectorizer(
        n_features=TEMPLATE_HASH_FEATURES,
        alternate_sign=False,
        binary=True,
        norm=None,
        ngram_range=(5, 5),
        lowercase=False,
        token_pattern=r"(?u)\b\w\w+\b",
        dtype=np.float32,
    )
    template_df = np.zeros(TEMPLATE_HASH_FEATURES, dtype=np.int64)
    template_country_mask = np.zeros(TEMPLATE_HASH_FEATURES, dtype=np.uint64)
    train_documents = 0
    masked_tmp = private_dir / "masked_use.parquet.tmp"
    masked_path = private_dir / "masked_use.parquet"
    writer: pq.ParquetWriter | None = None
    for batch_number, batch in enumerate(parquet.iter_batches(batch_size=BATCH_SIZE), start=1):
        frame = batch.to_pandas()
        masked = [mask_one(row) for row in frame.itertuples(index=False)]
        out = frame[["id", "sector", "fundraising_ts", "raised_ts", "fundraising_year", "country_name"]].copy()
        out["masked_use"] = masked
        writer = append_parquet(writer, out, masked_tmp)

        train_mask = frame["fundraising_year"].to_numpy() <= TRAIN_END_YEAR
        if np.any(train_mask):
            train_values = [masked[index] for index in np.flatnonzero(train_mask)]
            matrix = template_vectorizer.transform(train_values).tocsr()
            template_df += np.bincount(matrix.indices, minlength=TEMPLATE_HASH_FEATURES)
            train_countries = frame.loc[train_mask, "country_name"].to_numpy()
            for country in np.unique(train_countries):
                rows = np.flatnonzero(train_countries == country)
                indices = np.unique(matrix[rows].indices)
                template_country_mask[indices] |= np.uint64(1) << np.uint64(country_code[country])
            train_documents += len(train_values)
        if batch_number % 5 == 0:
            log(
                f"mask/hash pass batches={batch_number} rows~={batch_number * BATCH_SIZE:,} "
                f"rss_gib={psutil.Process().memory_info().rss / 1024**3:.2f}"
            )
    if writer is not None:
        writer.close()
    os.replace(masked_tmp, masked_path)

    threshold = max(TEMPLATE_MIN_DOCS_FLOOR, math.ceil(train_documents * TEMPLATE_MIN_SHARE))
    candidate_bins = np.flatnonzero(template_df >= threshold)
    candidate_bins = np.asarray(
        [index for index in candidate_bins if int(template_country_mask[index]).bit_count() >= TEMPLATE_MIN_COUNTRIES],
        dtype=np.int64,
    )
    candidate_set = set(candidate_bins.tolist())
    log(
        f"template candidates train_docs={train_documents:,} threshold={threshold} "
        f"hash_bins={len(candidate_set):,}"
    )

    exact_df: dict[str, int] = {}
    exact_country_mask: dict[str, int] = {}
    masked_parquet = pq.ParquetFile(masked_path)
    for batch_number, batch in enumerate(
        masked_parquet.iter_batches(
            batch_size=BATCH_SIZE,
            columns=["fundraising_year", "country_name", "masked_use"],
        ),
        start=1,
    ):
        frame = batch.to_pandas()
        train = frame[frame["fundraising_year"] <= TRAIN_END_YEAR]
        for row in train.itertuples(index=False):
            phrases = {
                phrase for phrase in fivegrams(row.masked_use) if feature_index(phrase) in candidate_set
            }
            country_bit = 1 << country_code[row.country_name]
            for phrase in phrases:
                exact_df[phrase] = exact_df.get(phrase, 0) + 1
                exact_country_mask[phrase] = exact_country_mask.get(phrase, 0) | country_bit
        if batch_number % 8 == 0:
            log(f"exact phrase verification batches={batch_number} candidates={len(exact_df):,}")

    approved = {
        phrase
        for phrase, count in exact_df.items()
        if count >= threshold
        and int(exact_country_mask.get(phrase, 0)).bit_count() >= TEMPLATE_MIN_COUNTRIES
    }
    phrase_rows = [
        {
            "masked_fivegram": phrase,
            "training_document_frequency": exact_df[phrase],
            "training_document_pct": round(100.0 * exact_df[phrase] / train_documents, 6),
            "countries_present": int(exact_country_mask[phrase]).bit_count(),
            "interpretation": "cross-country recurring boilerplate-like phrase; not attributed to a Lending Partner",
        }
        for phrase in approved
    ]
    phrase_frame = pd.DataFrame(phrase_rows)
    if len(phrase_frame):
        phrase_frame = phrase_frame.sort_values(
            ["training_document_frequency", "masked_fivegram"], ascending=[False, True]
        ).reset_index(drop=True)
    else:
        phrase_frame = pd.DataFrame(
            columns=[
                "masked_fivegram",
                "training_document_frequency",
                "training_document_pct",
                "countries_present",
                "interpretation",
            ]
        )
    atomic_csv(phrase_frame, outputs / "boilerplate_like_phrases.csv")
    log(f"approved recurring phrases={len(approved):,}")

    tfidf_binary_raw = HashingVectorizer(
        n_features=TFIDF_FEATURES,
        alternate_sign=False,
        binary=True,
        norm=None,
        ngram_range=(1, 2),
        lowercase=False,
        token_pattern=r"(?u)\b\w\w+\b",
        dtype=np.float32,
    )
    tfidf_binary_residual = HashingVectorizer(
        n_features=TFIDF_FEATURES,
        alternate_sign=False,
        binary=True,
        norm=None,
        analyzer=residual_analyzer,
        dtype=np.float32,
    )
    raw_df = np.zeros(TFIDF_FEATURES, dtype=np.int64)
    residual_df = np.zeros(TFIDF_FEATURES, dtype=np.int64)
    processed_tmp = private_dir / "processed_use.parquet.tmp"
    processed_path = private_dir / "processed_use.parquet"
    writer = None
    boilerplate_shares: list[np.ndarray] = []
    for batch_number, batch in enumerate(masked_parquet.iter_batches(batch_size=BATCH_SIZE), start=1):
        frame = batch.to_pandas()
        residual_values: list[str] = []
        shares = np.empty(len(frame), dtype=np.float32)
        for index, value in enumerate(frame["masked_use"].fillna("").astype(str)):
            residual, share = remove_phrases(value, approved)
            residual_values.append(residual)
            shares[index] = share
        out = frame.copy()
        out["residual_use"] = residual_values
        out["boilerplate_share"] = shares
        writer = append_parquet(writer, out, processed_tmp)
        boilerplate_shares.append(shares.copy())

        train_mask = frame["fundraising_year"].to_numpy() <= TRAIN_END_YEAR
        if np.any(train_mask):
            positions = np.flatnonzero(train_mask)
            raw_values = frame.loc[train_mask, "masked_use"].fillna("").astype(str).tolist()
            train_residual = [residual_values[index] for index in positions]
            accumulate_document_frequency(tfidf_binary_raw, raw_values, raw_df)
            accumulate_document_frequency(tfidf_binary_residual, train_residual, residual_df)
        if batch_number % 5 == 0:
            log(
                f"residual/idf pass batches={batch_number} rows~={batch_number * BATCH_SIZE:,} "
                f"rss_gib={psutil.Process().memory_info().rss / 1024**3:.2f}"
            )
    if writer is not None:
        writer.close()
    os.replace(processed_tmp, processed_path)

    raw_idf = (np.log((1.0 + train_documents) / (1.0 + raw_df)) + 1.0).astype(np.float32)
    residual_idf = (np.log((1.0 + train_documents) / (1.0 + residual_df)) + 1.0).astype(np.float32)
    np.save(model_artifacts / "idf_raw_use.npy", raw_idf, allow_pickle=False)
    np.save(model_artifacts / "idf_residual_use.npy", residual_idf, allow_pickle=False)

    all_shares = np.concatenate(boilerplate_shares) if boilerplate_shares else np.asarray([], dtype=float)
    share_summary = pd.DataFrame(
        [
            {
                "loans": int(len(all_shares)),
                "nonzero_share_pct": round(100.0 * float(np.mean(all_shares > 0)), 6) if len(all_shares) else 0.0,
                "p10": round(float(np.quantile(all_shares, 0.10)), 6) if len(all_shares) else 0.0,
                "p50": round(float(np.quantile(all_shares, 0.50)), 6) if len(all_shares) else 0.0,
                "p90": round(float(np.quantile(all_shares, 0.90)), 6) if len(all_shares) else 0.0,
                "p99": round(float(np.quantile(all_shares, 0.99)), 6) if len(all_shares) else 0.0,
            }
        ]
    )
    atomic_csv(share_summary, outputs / "boilerplate_share_distribution.csv")

    config = {
        "training_documents": train_documents,
        "training_years": [2016, 2024],
        "holdout_year": 2025,
        "primary_text": "use",
        "masking": {
            "exact_fields": ["name", "city", "country_name", "region"],
            "regex_classes": ["date", "amount_or_currency", "uppercase_abbreviation"],
            "placeholders_retained": True,
        },
        "tfidf": {
            "implementation": "HashingVectorizer plus train-only smooth IDF",
            "features": TFIDF_FEATURES,
            "ngrams": [1, 2],
            "alternate_sign": False,
            "dtype": "float32",
            "normalization": "L2 after IDF weighting",
            "residual_boundary_rule": "removed 5-gram spans are separated before unigram/bigram generation; no synthetic cross-gap bigrams",
            "hash_collision_limitation": "Fixed-dimensional hashing is memory-bounded but may merge rare terms.",
        },
        "recurring_language": {
            "ngram": 5,
            "hash_features_for_candidate_screen": TEMPLATE_HASH_FEATURES,
            "minimum_training_documents": threshold,
            "minimum_training_document_share": TEMPLATE_MIN_SHARE,
            "minimum_countries": TEMPLATE_MIN_COUNTRIES,
            "approved_exact_phrases": len(approved),
            "claim_boundary": "cross-country recurring boilerplate-like language only; no Lending Partner identifier exists",
        },
        "random_seed": RANDOM_SEED,
        "processed_private_rows": int(len(all_shares)),
        "elapsed_seconds": round(time.time() - started, 3),
    }
    atomic_json(config, model_artifacts / "text_vectorizer_config.json")
    atomic_json(
        {
            "processed_private_path": str(processed_path),
            "processed_private_bytes": processed_path.stat().st_size,
            "raw_idf_nondefault_features": int(np.sum(raw_df > 0)),
            "residual_idf_nondefault_features": int(np.sum(residual_df > 0)),
            "rss_gib_at_end": round(psutil.Process().memory_info().rss / 1024**3, 3),
            "elapsed_seconds": round(time.time() - started, 3),
        },
        audit / "stage2_text_manifest.json",
    )
    log(
        f"stage2 complete elapsed_seconds={time.time() - started:.1f} "
        f"processed_bytes={processed_path.stat().st_size:,} rss_gib={psutil.Process().memory_info().rss / 1024**3:.2f}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
