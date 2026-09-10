#!/usr/bin/env python3
"""Run deterministic final-delivery checks and write an auditable receipt."""

from __future__ import annotations

import csv
import html
import json
import math
import re
import sys
import time
import zipfile
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq


ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "audit"
OUTPUT_JSON = AUDIT / "final_qa.json"
OUTPUT_MD = ROOT / "FINAL_QA.md"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def close(actual: float, expected: float, tolerance: float = 1e-9) -> bool:
    return math.isclose(actual, expected, rel_tol=tolerance, abs_tol=tolerance)


def main() -> int:
    checks: list[dict[str, Any]] = []

    def record(name: str, passed: bool, evidence: Any) -> None:
        checks.append({"name": name, "passed": bool(passed), "evidence": evidence})

    required = [
        "Kiva_Final_Presentation_2026-09-04.pptx",
        "Kiva_Final_Report_2026-09-04.html",
        "REPORT.md",
        "METHODS_APPENDIX.md",
        "SPEAKER_NOTES_EN.md",
        "SPEAKER_CUES_ZH.md",
        "JUDGE_QA_BILINGUAL.md",
        "DELIVERY_MAP.md",
        "RUNBOOK.md",
        "outputs/scenario_contrasts.csv",
        "outputs/holdout_validation.csv",
        "outputs/pool_identity_summary.csv",
        "outputs/joint_support_summary.csv",
        "audit/html_delivery_receipt.json",
        "audit/pickle_opcode_audit.json",
    ]
    missing = [relative for relative in required if not (ROOT / relative).is_file()]
    record("required deliverables present", not missing, {"missing": missing})

    all_files = [path for path in ROOT.rglob("*") if path.is_file()]
    symlinks = [str(path.relative_to(ROOT)) for path in ROOT.rglob("*") if path.is_symlink()]
    record("no symlinks", not symlinks, {"paths": symlinks})

    forbidden_payloads = [
        str(path.relative_to(ROOT))
        for path in all_files
        if path.suffix.lower() in {".pkl", ".pickle"}
        or any(part.lower() in {"private", "raw_parquet"} for part in path.relative_to(ROOT).parts)
    ]
    record(
        "no raw pickle or private/raw checkpoint directory",
        not forbidden_payloads,
        {"paths": forbidden_payloads},
    )

    invalid_json: list[dict[str, str]] = []
    json_files = [path for path in all_files if path.suffix.lower() == ".json" and path != OUTPUT_JSON]
    for path in json_files:
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except Exception as error:  # noqa: BLE001 - validation must report every parse failure
            invalid_json.append({"path": str(path.relative_to(ROOT)), "error": str(error)})
    record("JSON files parse", not invalid_json, {"files": len(json_files), "errors": invalid_json})

    invalid_csv: list[dict[str, str]] = []
    csv_rows = 0
    csv_files = [
        path
        for path in all_files
        if path.suffix.lower() == ".csv" and not path.stem.endswith("_dev")
    ]
    for path in csv_files:
        try:
            with path.open("r", encoding="utf-8-sig", newline="") as stream:
                reader = csv.reader(stream)
                header = next(reader, None)
                if not header:
                    raise ValueError("missing header")
                for row in reader:
                    if len(row) != len(header):
                        raise ValueError(
                            f"row width {len(row)} differs from header width {len(header)}"
                        )
                    csv_rows += 1
        except Exception as error:  # noqa: BLE001
            invalid_csv.append({"path": str(path.relative_to(ROOT)), "error": str(error)})
    record(
        "CSV files parse with stable row widths",
        not invalid_csv,
        {"files": len(csv_files), "data_rows": csv_rows, "errors": invalid_csv},
    )

    notebook_errors: list[dict[str, str]] = []
    notebooks = sorted((ROOT / "notebooks").glob("S*.ipynb"))
    for path in notebooks:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            for cell_index, cell in enumerate(payload.get("cells", [])):
                for output in cell.get("outputs", []):
                    if output.get("output_type") == "error":
                        notebook_errors.append(
                            {"path": path.name, "cell": str(cell_index), "error": output.get("ename", "unknown")}
                        )
        except Exception as error:  # noqa: BLE001
            notebook_errors.append({"path": path.name, "cell": "parse", "error": str(error)})
    record(
        "seven executed notebooks contain no error outputs",
        len(notebooks) == 7 and not notebook_errors,
        {"notebooks": [path.name for path in notebooks], "errors": notebook_errors},
    )

    html_receipt = json.loads((AUDIT / "html_delivery_receipt.json").read_text(encoding="utf-8"))
    html_passed = bool(html_receipt.get("ok")) and all(
        html_receipt.get("stages", {}).get(stage) == "passed"
        for stage in ("validation", "package", "verification")
    )
    record(
        "portable HTML report validation and browser verification passed",
        html_passed,
        {
            "stages": html_receipt.get("stages"),
            "viewports": html_receipt.get("viewports"),
            "sourceDialog": html_receipt.get("sourceDialog"),
        },
    )

    pptx_path = ROOT / "Kiva_Final_Presentation_2026-09-04.pptx"
    slide_pattern = re.compile(r"^ppt/slides/slide\d+\.xml$")
    note_pattern = re.compile(r"^ppt/notesSlides/notesSlide\d+\.xml$")
    with zipfile.ZipFile(pptx_path) as archive:
        names = archive.namelist()
        slides = [name for name in names if slide_pattern.match(name)]
        notes = [name for name in names if note_pattern.match(name)]
        notes_with_sources = sum(b"[Sources]" in archive.read(name) for name in notes)
        media = [name for name in names if name.startswith("ppt/media/") and not name.endswith("/")]
        bad_zip_member = archive.testzip()
    rendered = sorted((AUDIT / "pptx_render").glob("slide-*.png"))
    record(
        "PPTX has 16 slides, 16 notes, eight embedded figures and renders 16 pages",
        len(slides) == 16
        and len(notes) == 16
        and notes_with_sources >= 15
        and len(media) >= 8
        and len(rendered) == 16
        and bad_zip_member is None,
        {
            "slides": len(slides),
            "notes": len(notes),
            "notes_with_sources": notes_with_sources,
            "media": len(media),
            "rendered_pages": len(rendered),
            "zip_error": bad_zip_member,
        },
    )

    pickle_audit = json.loads((AUDIT / "pickle_opcode_audit.json").read_text(encoding="utf-8"))
    record(
        "pickle opcode intake gate passed",
        pickle_audit.get("dangerous_opcode_count") == 0
        and pickle_audit.get("safe_for_restricted_primitive_deserialization") is True,
        {
            "dangerous_opcode_count": pickle_audit.get("dangerous_opcode_count"),
            "safe_for_restricted_primitive_deserialization": pickle_audit.get(
                "safe_for_restricted_primitive_deserialization"
            ),
        },
    )

    identity = read_csv(ROOT / "outputs/pool_identity_summary.csv")[0]
    identity_passed = (
        identity["passed"].lower() == "true"
        and float(identity["max_abs_error_raw"]) <= float(identity["acceptance_threshold"])
        and float(identity["max_abs_error_residual"]) <= float(identity["acceptance_threshold"])
    )
    record("pool algebra identity gate passed", identity_passed, identity)

    support = read_csv(ROOT / "outputs/joint_support_summary.csv")
    min_support = min(int(row["n_near_endpoint"]) for row in support)
    record(
        "joint scenario endpoint support gate passed",
        min_support >= 1_000,
        {"minimum_endpoint_neighbourhood_n": min_support, "threshold": 1_000},
    )

    scenarios = read_csv(ROOT / "outputs/scenario_contrasts.csv")
    scenario_index = {(row["outcome"], row["channel"]): row for row in scenarios}
    current_duration = scenario_index[("log_funding_hours", "current")]
    current_fast = scenario_index[("funded_within_72h", "current")]
    recent_duration = scenario_index[("log_funding_hours", "recent")]
    recent_fast = scenario_index[("funded_within_72h", "recent")]
    # Regression lock on the headline scenario values. Updated when the privacy-mask
    # placeholder ordering was corrected (upper-case [DATE]/[AMT]/[NAME]/[LOC] were being
    # rewritten to [ORG] by the final substitution). The correction moved the duration
    # headline from 124.3813 to 124.3508 percent and the 72h headline from -14.6843 to
    # -14.6818 points; no coefficient changed sign and no significance verdict changed.
    # Updated again when the fixed-effect set was restored to the frozen specification.
    # freeze_spec.py and frozen_spec.csv commit to "Country + Activity + Week FE", but
    # fit_main_models.py had been estimating seven (adding gender, repaymentInterval,
    # posting_dow, posting_hour). Dropping the four undocumented effects moved the
    # duration headline from 124.3508 to 123.5064 percent and the 72h headline from
    # -14.6818 to -14.5695 points. Across rq1, rq2, robustness and scenario_contrasts
    # no coefficient changed sign and no significance verdict changed.
    # Updated a third time when the four dropped characteristics were reinstated as
    # controls rather than fixed effects. The submitted proposal (p.4) commits to
    # "controlling for loan, borrower, repayment and posting-time characteristics ...
    # and country, activity and week fixed effects": the four belong in the control
    # set, not the absorbed set, so both that commitment and the frozen
    # "Country + Activity + Week FE" specification now hold simultaneously. Entering
    # them as controls is algebraically equivalent to absorbing them, so the headline
    # returns to 124.3508 percent and -14.6818 points.
    claim_values_passed = (
        close(float(current_duration["translated_effect"]), 124.35083720023474)
        and close(float(current_fast["translated_effect"]), -14.681812357882182)
        and float(recent_duration["translated_ci_low"]) < 0 < float(recent_duration["translated_ci_high"])
        and float(recent_fast["translated_ci_low"]) < 0 < float(recent_fast["translated_ci_high"])
    )
    record(
        "headline scenario values and recent-null boundaries match source tables",
        claim_values_passed,
        {
            "current_duration_percent": float(current_duration["translated_effect"]),
            "current_fast_72h_percentage_points": float(current_fast["translated_effect"]),
            "recent_duration_ci": [
                float(recent_duration["translated_ci_low"]),
                float(recent_duration["translated_ci_high"]),
            ],
            "recent_fast_72h_ci": [
                float(recent_fast["translated_ci_low"]),
                float(recent_fast["translated_ci_high"]),
            ],
        },
    )

    sample_flow = {row["step"]: int(row["loans"]) for row in read_csv(ROOT / "outputs/analysis_sample_flow.csv")}
    sample_split_passed = (
        sample_flow.get("Valid nonnegative duration") == 1_453_840
        and sample_flow.get("Training 2016-2024, valid duration") == 1_316_678
        and sample_flow.get("2025 holdout, valid duration") == 137_162
        and sample_flow.get("Training 2016-2024, valid duration", 0)
        + sample_flow.get("2025 holdout, valid duration", 0)
        == sample_flow.get("Valid nonnegative duration", -1)
    )
    record(
        "analysis sample split reconciles exactly",
        sample_split_passed,
        sample_flow,
    )

    expected_t_critical = 2.014103388880846
    scenario_inference_passed = all(
        row["ci_degrees_of_freedom"] == "45"
        and close(float(row["ci_critical_value"]), expected_t_critical)
        and (
            row["translated_unit"]
            == "percent change in conditional geometric mean of (1 + funding hours)"
            if row["outcome"] == "log_funding_hours"
            else row["translated_unit"] == "percentage-point change in 72h fast-funding rate"
        )
        for row in scenarios
    )
    record(
        "scenario intervals use the documented t(45) critical value and bounded units",
        scenario_inference_passed,
        {
            "rows": len(scenarios),
            "degrees_of_freedom": sorted({row["ci_degrees_of_freedom"] for row in scenarios}),
            "critical_values": sorted({row["ci_critical_value"] for row in scenarios}),
            "units": sorted({row["translated_unit"] for row in scenarios}),
        },
    )

    semantic_paths = [
        ROOT / "REPORT.md",
        ROOT / "METHODS_APPENDIX.md",
        ROOT / "SPEAKER_NOTES_EN.md",
        ROOT / "SPEAKER_CUES_ZH.md",
        ROOT / "JUDGE_QA_BILINGUAL.md",
        ROOT / "src/build_presentation.mjs",
        ROOT / "src/make_figures.py",
    ]
    semantic_text = "\n".join(path.read_text(encoding="utf-8") for path in semantic_paths)
    with zipfile.ZipFile(pptx_path) as archive:
        slide_and_note_xml = "\n".join(
            archive.read(name).decode("utf-8", errors="ignore")
            for name in archive.namelist()
            if slide_pattern.match(name) or note_pattern.match(name)
        )
    presentation_text = html.unescape(re.sub(r"<[^>]+>", " ", slide_and_note_xml))
    combined_semantic_text = semantic_text + "\n" + presentation_text
    forbidden_semantics = [
        "percent change in expected funding time",
        "funding takes about 2.24 times as long",
        "estimated funding time is 124.38",
        "what lenders saw weeks ago",
        "after earlier listings leave",
        "Current homogeneity quartile",
        "Effects vary over time",
    ]
    semantic_hits = [phrase for phrase in forbidden_semantics if phrase.lower() in combined_semantic_text.lower()]
    semantic_text_lower = combined_semantic_text.lower()
    required_semantics = {
        "geometric_mean_boundary": (
            "conditional geometric mean" in semantic_text_lower
            and any(
                label in semantic_text_lower
                for label in ("1 + funding hours", "1 + funding_hours", "1 + hours", "one plus funding hours")
            )
        ),
        "recent_proxy_boundary": "posting-age proxy" in combined_semantic_text,
        "current_caveat": "CAVEAT" in combined_semantic_text,
        "raised_only_boundary": "raised-only" in combined_semantic_text,
    }
    record(
        "headline semantics are consistent across report, scripts, notes and PPTX",
        not semantic_hits and all(required_semantics.values()),
        {"forbidden_hits": semantic_hits, "required": required_semantics},
    )

    holdout = read_csv(ROOT / "outputs/holdout_validation.csv")
    metrics = {
        (row["task"], row["evaluation_slice"], row["model"], row["metric"]): float(row["value"])
        for row in holdout
    }
    controls_mae = metrics[("funding_duration", "2025_at_least_35d_followup", "controls_only", "mae_log_hours")]
    narrative_mae = metrics[("funding_duration", "2025_at_least_35d_followup", "controls_plus_narrative", "mae_log_hours")]
    controls_brier = metrics[("fast_funding_72h", "2025_72h_eligible", "controls_only", "brier")]
    narrative_brier = metrics[("fast_funding_72h", "2025_72h_eligible", "controls_plus_narrative", "brier")]
    controls_auc = metrics[("fast_funding_72h", "2025_72h_eligible", "controls_only", "roc_auc")]
    narrative_auc = metrics[("fast_funding_72h", "2025_72h_eligible", "controls_plus_narrative", "roc_auc")]
    holdout_boundary_passed = (
        narrative_mae >= controls_mae
        and narrative_brier >= controls_brier
        and narrative_auc <= controls_auc
    )
    record(
        "2025 no-deployment boundary matches holdout metrics",
        holdout_boundary_passed,
        {
            "mae_log_hours_controls": controls_mae,
            "mae_log_hours_narrative": narrative_mae,
            "brier_controls": controls_brier,
            "brier_narrative": narrative_brier,
            "auc_controls": controls_auc,
            "auc_narrative": narrative_auc,
        },
    )

    banned_columns = {
        "name",
        "description",
        "use",
        "whyspecial",
        "image_url",
        "location",
        "city",
        "region",
        "borrower_name",
        "loan_use",
    }
    parquet_schema_violations: list[dict[str, Any]] = []
    parquet_files = sorted((ROOT / "data").rglob("*.parquet"))
    for path in parquet_files:
        columns = pq.ParquetFile(path).schema_arrow.names
        violations = sorted({column.lower() for column in columns} & banned_columns)
        if violations:
            parquet_schema_violations.append(
                {"path": str(path.relative_to(ROOT)), "forbidden_columns": violations}
            )
    record(
        "working-copy parquet schemas omit names, exact locations and full narrative text",
        not parquet_schema_violations,
        {"files": len(parquet_files), "violations": parquet_schema_violations},
    )

    text_extensions = {".md", ".py", ".mjs", ".json", ".txt", ".html", ".csv"}
    secret_patterns = [
        re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
        re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
        re.compile(
            r"(?i)(?:api[_-]?key|password|access[_-]?token|client[_-]?secret)\s*[:=]\s*['\"][^'\"]{8,}['\"]"
        ),
    ]
    secret_hits: list[dict[str, str]] = []
    for path in all_files:
        if path.suffix.lower() not in text_extensions:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for pattern in secret_patterns:
            if pattern.search(text):
                secret_hits.append(
                    {"path": str(path.relative_to(ROOT)), "pattern": pattern.pattern}
                )
    record("no credential-like values in text artifacts", not secret_hits, {"hits": secret_hits})

    seed_paths = [
        ROOT / "src/freeze_spec.py",
        ROOT / "src/text_pipeline.py",
        ROOT / "src/predict_engine.py",
        ROOT / "model_artifacts/text_vectorizer_config.json",
        ROOT / "audit/frozen_spec_manifest.json",
        ROOT / "audit/stage6_engine_manifest.json",
    ]
    seed_text = "\n".join(path.read_text(encoding="utf-8") for path in seed_paths)
    personal_seed = "550" + "0172"
    record(
        "reproducibility seed is neutral and consistent",
        personal_seed not in seed_text and all("20260904" in path.read_text(encoding="utf-8") for path in seed_paths),
        {"paths": [str(path.relative_to(ROOT)) for path in seed_paths], "neutral_seed": 20260904},
    )

    external_reference_text = "\n".join(
        path.read_text(encoding="utf-8", errors="ignore")
        for path in (
            ROOT / "DELIVERY_MAP.md",
            ROOT / "PACKAGE_EXCLUSIONS.md",
            ROOT / "report_artifact.json",
            ROOT / "Kiva_Final_Report_2026-09-04.html",
        )
    )
    record(
        "external-facing artifacts omit archival source-file links",
        "source/2026 MA Hackathon" not in external_reference_text
        and "external ZIP omits all `source/` material" in external_reference_text,
        {"forbidden_reference": "source/2026 MA Hackathon", "declared_boundary": "omit all source material"},
    )

    passed = all(check["passed"] for check in checks)
    receipt = {
        "generated_at_local": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "root": str(ROOT),
        "status": "PASS" if passed else "FAIL",
        "checks_passed": sum(check["passed"] for check in checks),
        "checks_total": len(checks),
        "checks": checks,
    }
    AUDIT.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# Final QA Status",
        "",
        f"**{receipt['status']} · {receipt['checks_passed']}/{receipt['checks_total']} deterministic checks passed.**",
        "",
        "| Check | Status |",
        "|---|---:|",
    ]
    lines.extend(
        f"| {check['name']} | {'PASS' if check['passed'] else 'FAIL'} |" for check in checks
    )
    lines.extend(
        [
            "",
            "Full machine-readable evidence: `audit/final_qa.json`.",
            "",
            "This receipt validates internal consistency, artifact structure and privacy boundaries; it does not convert observational associations into causal evidence or authorize deployment.",
        ]
    )
    OUTPUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"status": receipt["status"], "passed": receipt["checks_passed"], "total": receipt["checks_total"]}))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
