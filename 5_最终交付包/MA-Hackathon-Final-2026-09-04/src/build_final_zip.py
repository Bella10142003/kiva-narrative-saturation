#!/usr/bin/env python3
"""Build and validate the privacy-bounded external finalist ZIP."""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
import zipfile
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parents[1]
WORK_ROOT = ROOT.with_name(f"{ROOT.name}_work")
DESTINATION = ROOT.with_suffix(".zip")
PACKAGE_PREFIX = ROOT.name
SOURCE_ZIP_SHA256 = "c9eb61b5702f41daedb244640edb72f50844ef78612172d5048f6ce56055029a"

ROOT_FILES = {
    "DELIVERY_MAP.md",
    "FINAL_QA.md",
    "JUDGE_QA_BILINGUAL.md",
    "Kiva_Final_Presentation_2026-09-04.pptx",
    "Kiva_Final_Report_2026-09-04.html",
    "METHODS_APPENDIX.md",
    "PACKAGE_EXCLUSIONS.md",
    "REPORT.md",
    "RUNBOOK.md",
    "SPEAKER_CUES_ZH.md",
    "SPEAKER_NOTES_EN.md",
    "environment.txt",
    "report_artifact.json",
    "requirements-lock.txt",
}

TEXT_SUFFIXES = {
    ".csv",
    ".html",
    ".ipynb",
    ".json",
    ".log",
    ".md",
    ".mjs",
    ".ndjson",
    ".py",
    ".txt",
}

SECRET_PATTERNS = [
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    re.compile(
        r"(?i)(?:api[_-]?key|password|access[_-]?token|client[_-]?secret)"
        r"\s*[:=]\s*['\"][^'\"]{8,}['\"]"
    ),
]


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def is_dev_path(relative: Path) -> bool:
    return any("_dev" in part.lower() for part in relative.parts)


def include_path(relative: Path) -> bool:
    if not relative.parts or relative.name == ".DS_Store":
        return False
    if any(part == "__pycache__" for part in relative.parts):
        return False
    if relative.suffix.lower() == ".pyc" or is_dev_path(relative):
        return False

    if len(relative.parts) == 1:
        return relative.name in ROOT_FILES

    top = relative.parts[0]
    if top in {"data", "source"}:
        return False
    if top == "figures":
        return relative.suffix.lower() in {".png", ".pdf", ".csv"}
    if top == "outputs":
        return (
            relative.suffix.lower() == ".csv"
            and relative.name not in {"engine_scores_2025.csv", "country_counts.csv"}
        )
    if top == "model_artifacts":
        return relative.suffix.lower() in {".npy", ".json"}
    if top == "notebooks":
        return relative.suffix.lower() == ".ipynb" and relative.name.startswith("S")
    if top == "src":
        return relative.suffix.lower() in {".py", ".mjs"}
    if top == "logs":
        return relative.name == "run_log.txt"
    if top == "audit":
        if len(relative.parts) != 2:
            return False
        if relative.name in {
            "package_build_receipt.json",
            "presentation_contact_sheet.png",
            "presentation_inspect.ndjson",
            "presentation_montage.webp",
        }:
            return False
        if relative.name == "pptx_contact_sheet.png":
            return True
        return relative.suffix.lower() in {".json", ".md", ".log", ".csv", ".txt"}
    return False


def sanitise_text(relative: Path, payload: bytes) -> bytes:
    if relative.suffix.lower() not in TEXT_SUFFIXES:
        return payload
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError:
        return payload
    replacements = [
        (str(WORK_ROOT), "<PRIVATE_WORK_DIR>"),
        (str(ROOT), "<FINAL_ROOT>"),
        (str(Path.home()), "<USER_HOME>"),
    ]
    for original, replacement in replacements:
        text = text.replace(original, replacement)
    return text.encode("utf-8")


def validate_entries(entries: list[tuple[str, bytes]]) -> dict[str, object]:
    errors: list[str] = []
    names = [name for name, _ in entries]
    personal_seed = "550" + "0172"
    private_path_markers = ("wx" + "id_", "xwechat" + "_files")
    if len(names) != len(set(names)):
        errors.append("duplicate archive member")

    for name, payload in entries:
        pure = PurePosixPath(name)
        relative = PurePosixPath(*pure.parts[1:])
        if pure.is_absolute() or ".." in pure.parts or pure.parts[0] != PACKAGE_PREFIX:
            errors.append(f"unsafe member path: {name}")
        if relative.parts and relative.parts[0] in {"data", "source"}:
            errors.append(f"forbidden directory: {name}")
        if "_dev" in name.lower() or "engine_scores_2025.csv" in name or "country_counts.csv" in name:
            errors.append(f"forbidden output: {name}")
        if name.endswith(".pptx.inspect.ndjson") or "/__pycache__/" in name or name.endswith(".pyc"):
            errors.append(f"forbidden generated artifact: {name}")

        suffix = Path(relative.name).suffix.lower()
        if suffix in TEXT_SUFFIXES:
            text = payload.decode("utf-8", errors="ignore")
            for forbidden in (str(Path.home()), personal_seed, *private_path_markers):
                if forbidden in text:
                    errors.append(f"private marker {forbidden!r}: {name}")
            for pattern in SECRET_PATTERNS:
                if pattern.search(text):
                    errors.append(f"credential-like pattern: {name}")

    required = {f"{PACKAGE_PREFIX}/{name}" for name in ROOT_FILES}
    missing = sorted(required - set(names))
    if missing:
        errors.append(f"missing required root files: {missing}")

    return {
        "status": "PASS" if not errors else "FAIL",
        "checks": {
            "unique_members": len(names) == len(set(names)),
            "safe_relative_paths": not any("unsafe member path" in item for item in errors),
            "no_source_or_row_level_data": not any(
                "forbidden directory" in item or "forbidden output" in item for item in errors
            ),
            "no_dev_cache_or_redundant_inspection": not any(
                "forbidden generated artifact" in item for item in errors
            ),
            "no_local_path_personal_seed_or_credentials": not any(
                "private marker" in item or "credential-like" in item for item in errors
            ),
            "required_deliverables_present": not missing,
        },
        "errors": errors,
    }


def zip_info(name: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name, date_time=(2026, 8, 28, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o100644 << 16
    return info


def main() -> int:
    selected: list[tuple[str, bytes]] = []
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file() or path.is_symlink():
            continue
        relative = path.relative_to(ROOT)
        if not include_path(relative):
            continue
        payload = sanitise_text(relative, path.read_bytes())
        selected.append((f"{PACKAGE_PREFIX}/{relative.as_posix()}", payload))

    validation = validate_entries(selected)
    if validation["status"] != "PASS":
        raise SystemExit(json.dumps(validation, ensure_ascii=False, indent=2))

    manifest_lines = [
        f"{sha256_bytes(payload)}  {len(payload):>12}  {name}"
        for name, payload in selected
    ]
    sha_manifest = ("\n".join(manifest_lines) + "\n").encode("utf-8")

    package_manifest = {
        "package": PACKAGE_PREFIX,
        "generated_at_local": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "source_archive_sha256": SOURCE_ZIP_SHA256,
        "artifact_files_hashed": len(selected),
        "artifact_bytes_uncompressed": sum(len(payload) for _, payload in selected),
        "manifest_scope": "MANIFEST_SHA256.txt hashes every packaged artifact except the two generated package metadata members",
        "privacy_boundary": {
            "source_material": "excluded",
            "row_level_data": "excluded",
            "per_loan_scores": "excluded",
            "small_country_counts": "excluded",
            "local_paths_in_text_copies": "redacted",
            "student_derived_seed": "replaced by neutral seed 20260904 and affected outputs regenerated",
        },
        "validation": validation,
    }
    package_manifest_bytes = json.dumps(
        package_manifest, ensure_ascii=False, indent=2
    ).encode("utf-8") + b"\n"

    internal_validation = {
        "status": "PASS",
        "checks": validation["checks"],
        "artifact_members": len(selected),
        "generated_metadata_members": 3,
        "expected_total_members": len(selected) + 3,
    }
    internal_validation_bytes = json.dumps(
        internal_validation, ensure_ascii=False, indent=2
    ).encode("utf-8") + b"\n"

    temporary = DESTINATION.with_name(f"{DESTINATION.name}.tmp")
    with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, payload in selected:
            archive.writestr(zip_info(name), payload)
        archive.writestr(zip_info(f"{PACKAGE_PREFIX}/MANIFEST_SHA256.txt"), sha_manifest)
        archive.writestr(zip_info(f"{PACKAGE_PREFIX}/PACKAGE_MANIFEST.json"), package_manifest_bytes)
        archive.writestr(zip_info(f"{PACKAGE_PREFIX}/PACKAGE_VALIDATION.json"), internal_validation_bytes)
    os.replace(temporary, DESTINATION)

    with zipfile.ZipFile(DESTINATION) as archive:
        bad_member = archive.testzip()
        members = archive.namelist()
    if bad_member is not None or len(members) != len(selected) + 3:
        raise SystemExit(f"post-write ZIP validation failed: bad_member={bad_member!r}, members={len(members)}")

    receipt = {
        "status": "PASS",
        "zip": str(DESTINATION),
        "zip_size_bytes": DESTINATION.stat().st_size,
        "zip_sha256": sha256_file(DESTINATION),
        "members": len(members),
        "artifact_members": len(selected),
        "bad_member": bad_member,
        "validation": validation,
    }
    receipt_path = ROOT / "audit" / "package_build_receipt.json"
    temporary_receipt = receipt_path.with_suffix(".json.tmp")
    temporary_receipt.write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    os.replace(temporary_receipt, receipt_path)
    print(json.dumps(receipt, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
