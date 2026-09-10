#!/usr/bin/env python3
"""Safely convert the primitive-only Kiva pickle to chunked Parquet files."""

from __future__ import annotations

import gc
import json
import os
import pickle
import resource
import sys
import threading
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

import psutil
import pyarrow as pa
import pyarrow.parquet as pq


MAX_ADDRESS_SPACE_BYTES = 13 * 1024**3
MEMORY_ABORT_BYTES = int(12.5 * 1024**3)
CHUNK_ROWS = 50_000


class RestrictedUnpickler(pickle.Unpickler):
    """Reject every path that could resolve a Python class or persistent id."""

    def find_class(self, module: str, name: str) -> Any:  # pragma: no cover - safety gate
        raise pickle.UnpicklingError(f"class loading blocked: {module}.{name}")

    def persistent_load(self, pid: object) -> Any:  # pragma: no cover - safety gate
        raise pickle.UnpicklingError("persistent ids are blocked")


def rss_gib() -> float:
    return psutil.Process().memory_info().rss / 1024**3


def log(message: str, log_path: Path) -> None:
    line = f"{time.strftime('%Y-%m-%dT%H:%M:%S%z')} {message}"
    print(line, flush=True)
    with log_path.open("a", encoding="utf-8") as stream:
        stream.write(line + "\n")


def infer_schema(records: list[dict[str, object]]) -> tuple[pa.Schema, dict[str, list[str]]]:
    if not records:
        raise ValueError("empty pickle")
    sample_count = min(25_000, len(records))
    step = max(1, len(records) // sample_count)
    sampled = records[::step][:sample_count]
    observed: dict[str, set[type]] = defaultdict(set)
    keys: set[str] = set()
    for record in sampled:
        if not isinstance(record, dict):
            raise TypeError(f"expected dict records, found {type(record).__name__}")
        keys.update(record)
        for key, value in record.items():
            if value is not None:
                observed[key].add(type(value))

    fields: list[pa.Field] = []
    type_audit: dict[str, list[str]] = {}
    for key in sorted(keys):
        types = observed.get(key, set())
        type_audit[key] = sorted(t.__name__ for t in types)
        if not types or types <= {str}:
            arrow_type = pa.string()
        elif types <= {bool}:
            arrow_type = pa.bool_()
        elif types <= {int, bool}:
            arrow_type = pa.int64()
        elif types <= {int, float, bool}:
            arrow_type = pa.float64()
        else:
            raise TypeError(f"unsupported mixed types for {key}: {type_audit[key]}")
        fields.append(pa.field(key, arrow_type, nullable=True))
    return pa.schema(fields), type_audit


def main() -> int:
    if len(sys.argv) != 5:
        raise SystemExit(
            "usage: convert_pickle_to_parquet.py INPUT.pkl OUTPUT_DIR PROFILE.json LOG.txt"
        )
    input_path = Path(sys.argv[1]).resolve()
    output_dir = Path(sys.argv[2]).resolve()
    profile_path = Path(sys.argv[3]).resolve()
    log_path = Path(sys.argv[4]).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    profile_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text("", encoding="utf-8")

    try:
        _, hard_limit = resource.getrlimit(resource.RLIMIT_AS)
        resource.setrlimit(
            resource.RLIMIT_AS,
            (MAX_ADDRESS_SPACE_BYTES, hard_limit),
        )
        address_space_note = "address_space_soft_limit_gib=13"
    except (OSError, ValueError):
        address_space_note = "address_space_limit=unsupported_on_host"

    def memory_watchdog() -> None:
        process = psutil.Process()
        while True:
            rss = process.memory_info().rss
            if rss > MEMORY_ABORT_BYTES:
                log(
                    f"ABORT memory watchdog rss_gib={rss / 1024**3:.2f} "
                    "threshold_gib=12.50",
                    log_path,
                )
                os._exit(137)
            time.sleep(0.5)

    threading.Thread(target=memory_watchdog, daemon=True).start()
    pickle._extension_registry.clear()
    pickle._inverted_registry.clear()
    pickle._extension_cache.clear()

    started = time.time()
    log(
        f"restricted load start input_bytes={input_path.stat().st_size:,} "
        f"rss_gib={rss_gib():.2f} {address_space_note} watchdog_gib=12.50",
        log_path,
    )
    with input_path.open("rb") as stream:
        unpickler = RestrictedUnpickler(stream)
        records = unpickler.load()
    del unpickler
    gc.collect()
    if not isinstance(records, list):
        raise TypeError(f"expected root list, found {type(records).__name__}")
    log(
        f"restricted load complete rows={len(records):,} rss_gib={rss_gib():.2f} "
        f"elapsed_seconds={time.time() - started:.1f}",
        log_path,
    )

    schema, type_audit = infer_schema(records)
    log(
        f"schema inferred columns={len(schema)} fields={','.join(schema.names)}",
        log_path,
    )
    written_rows = 0
    part_count = 0
    for start in range(0, len(records), CHUNK_ROWS):
        end = min(start + CHUNK_ROWS, len(records))
        chunk = records[start:end]
        for record in chunk:
            if not isinstance(record, dict):
                raise TypeError(
                    f"row {written_rows:,} expected dict, found {type(record).__name__}"
                )
        table = pa.Table.from_pylist(chunk, schema=schema)
        source_rows = pa.array(range(start, end), type=pa.int64())
        table = table.append_column("_source_row", source_rows)
        part_path = output_dir / f"part-{part_count:04d}.parquet"
        pq.write_table(
            table,
            part_path,
            compression="zstd",
            compression_level=5,
            use_dictionary=True,
            write_statistics=True,
        )
        written_rows += len(chunk)
        part_count += 1
        records[start:end] = [None] * (end - start)
        del chunk, table, source_rows
        gc.collect()
        log(
            f"wrote part={part_count:04d} rows={written_rows:,} "
            f"rss_gib={rss_gib():.2f}",
            log_path,
        )

    elapsed = time.time() - started
    profile = {
        "input_file": input_path.name,
        "input_size_bytes": input_path.stat().st_size,
        "row_count": written_rows,
        "column_count": len(schema),
        "columns": schema.names,
        "arrow_schema": str(schema),
        "sampled_python_types": type_audit,
        "part_count": part_count,
        "chunk_rows": CHUNK_ROWS,
        "elapsed_seconds": round(elapsed, 3),
        "restricted_unpickler": True,
        "raw_personal_data_in_final_package": False,
    }
    temporary_path = profile_path.with_suffix(profile_path.suffix + ".tmp")
    temporary_path.write_text(json.dumps(profile, indent=2), encoding="utf-8")
    os.replace(temporary_path, profile_path)
    log(
        f"conversion complete rows={written_rows:,} parts={part_count} "
        f"elapsed_seconds={elapsed:.1f}",
        log_path,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
