#!/usr/bin/env python3
"""Statically inspect a pickle stream without deserializing it.

The script records opcode counts and flags any opcode that could introduce or
invoke Python objects. It never prints pickle arguments, because those include
borrower-level personal information.
"""

from __future__ import annotations

import collections
import json
import os
import pickletools
import sys
import time
from pathlib import Path


DANGEROUS_OPCODES = {
    "GLOBAL",
    "STACK_GLOBAL",
    "REDUCE",
    "BUILD",
    "OBJ",
    "INST",
    "NEWOBJ",
    "NEWOBJ_EX",
    "EXT1",
    "EXT2",
    "EXT4",
    "PERSID",
    "BINPERSID",
}


def main() -> int:
    if len(sys.argv) != 3:
        raise SystemExit("usage: safe_pickle_audit.py INPUT.pkl OUTPUT.json")

    input_path = Path(sys.argv[1]).resolve()
    output_path = Path(sys.argv[2]).resolve()
    size = input_path.stat().st_size
    counts: collections.Counter[str] = collections.Counter()
    dangerous: list[dict[str, int | str]] = []
    stop_position: int | None = None
    max_text_length = 0
    max_bytes_length = 0
    next_progress = 100_000_000
    started = time.time()

    with input_path.open("rb") as stream:
        for op, arg, position in pickletools.genops(stream):
            counts[op.name] += 1
            if op.name in DANGEROUS_OPCODES and len(dangerous) < 100:
                dangerous.append({"opcode": op.name, "position": position})
            if isinstance(arg, str):
                max_text_length = max(max_text_length, len(arg))
            elif isinstance(arg, bytes):
                max_bytes_length = max(max_bytes_length, len(arg))
            if position >= next_progress:
                elapsed = time.time() - started
                print(
                    f"scanned={position:,}/{size:,} ({position / size:.1%}) "
                    f"elapsed={elapsed:.1f}s",
                    flush=True,
                )
                next_progress += 100_000_000
            if op.name == "STOP":
                stop_position = position

    result = {
        "input_file": input_path.name,
        "input_size_bytes": size,
        "scan_elapsed_seconds": round(time.time() - started, 3),
        "stop_position": stop_position,
        "trailing_bytes_after_stop": (
            None if stop_position is None else size - stop_position - 1
        ),
        "dangerous_opcode_count": sum(counts[name] for name in DANGEROUS_OPCODES),
        "dangerous_opcodes_first_100": dangerous,
        "max_text_length": max_text_length,
        "max_bytes_length": max_bytes_length,
        "opcode_counts": dict(sorted(counts.items())),
        "safe_for_restricted_primitive_deserialization": (
            stop_position is not None
            and size - stop_position - 1 == 0
            and not dangerous
        ),
        "privacy_note": "Arguments were not logged because the pickle contains borrower-level records.",
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_suffix(output_path.suffix + ".tmp")
    temporary_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    os.replace(temporary_path, output_path)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
