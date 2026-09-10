#!/usr/bin/env python3
"""Build an auditable description-versus-use comparison from saved results."""

from __future__ import annotations

import hashlib
import json
import math
import os
import time
from datetime import datetime
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import psutil


ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / "4_中间产物"
RESULTS = WORK / "我算出来的结果"
OUTPUT = RESULTS / "description_vs_use"
REBUILD = ROOT / "5_最终交付包" / "_rebuild" / "MA-Hackathon-Final-2026-09-04"
RAW_DESCRIPTION = "masked description hashed TF-IDF"
RESIDUAL_DESCRIPTION = "recurring-language-removed description hashed TF-IDF"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def atomic_text(text: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    os.replace(temporary, path)


def atomic_json(payload: dict, path: Path) -> None:
    atomic_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", path)


def f(value: float, digits: int = 6) -> str:
    return f"{value:.{digits}f}"


def p(value: float) -> str:
    return f"{value:.3g}"


def main() -> int:
    started = time.time()
    paths = {
        "use_model_results": RESULTS / "outputs" / "rq1_main_table.csv",
        "use_robustness": RESULTS / "outputs" / "robustness.csv",
        "use_boilerplate_phrases": RESULTS / "outputs" / "boilerplate_like_phrases.csv",
        "use_boilerplate_distribution": RESULTS / "outputs" / "boilerplate_share_distribution.csv",
        "description_model_results": RESULTS / "outputs" / "description_robustness.csv",
        "description_boilerplate_phrases": RESULTS / "outputs" / "description_boilerplate_phrases.csv",
        "description_boilerplate_distribution": RESULTS / "outputs" / "description_boilerplate_share_distribution.csv",
        "description_manifest": RESULTS / "audit" / "description_robustness_manifest.json",
        "text_field_diagnostics": RESULTS / "outputs" / "text_field_diagnostics.csv",
        "text_selection_diagnostics": RESULTS / "outputs" / "text_selection_diagnostics.csv",
        "scaler_parameters": RESULTS / "outputs" / "scaler_parameters.csv",
        "description_model_data": WORK / "data" / "description_model.parquet",
    }
    missing = [str(path) for path in paths.values() if not path.exists()]
    if missing:
        raise FileNotFoundError(f"Missing required inputs: {missing}")

    manifest = json.loads(paths["description_manifest"].read_text(encoding="utf-8"))
    if manifest["identity_passed"] is not True:
        raise AssertionError("Description pool identity gate did not pass")
    if float(manifest["identity_max_abs_error"]) > 1e-9:
        raise AssertionError("Description pool identity error exceeds 1e-9")
    if int(manifest["model_rows"]) != 1_234_124:
        raise AssertionError("Unexpected description model row count")
    if int(manifest["residual_model_rows"]) != 1_230_306:
        raise AssertionError("Unexpected residual description model row count")
    if int(manifest["approved_recurring_phrases"]) != 9_334:
        raise AssertionError("Unexpected recurring description phrase count")
    if int(manifest["recurring_minimum_training_documents"]) != 659:
        raise AssertionError("Unexpected recurring-language frequency threshold")
    if int(manifest["recurring_minimum_countries"]) != 3:
        raise AssertionError("Unexpected recurring-language country threshold")

    use = pd.read_csv(paths["use_model_results"])
    use = use[
        (use["model"] == "active_raw_main")
        & (use["outcome"] == "log_funding_hours")
    ].copy()
    description_all = pd.read_csv(paths["description_model_results"]).copy()
    if set(description_all["representation"]) != {RAW_DESCRIPTION, RESIDUAL_DESCRIPTION}:
        raise AssertionError("Unexpected description representations")
    description = description_all[
        description_all["representation"].eq(RAW_DESCRIPTION)
    ].copy()
    description_residual = description_all[
        description_all["representation"].eq(RESIDUAL_DESCRIPTION)
    ].copy()
    expected_terms = {"C", "H", "CH", "V", "G", "VG"}
    if (
        set(use["term"]) != expected_terms
        or set(description["term"]) != expected_terms
        or set(description_residual["term"]) != expected_terms
        or not description["term"].is_unique
        or not description_residual["term"].is_unique
    ):
        raise AssertionError("Unexpected coefficient terms")
    if description["n"].nunique() != 1 or int(description["n"].iloc[0]) != int(manifest["model_rows"]):
        raise AssertionError("Raw description rows do not match manifest")
    if (
        description_residual["n"].nunique() != 1
        or int(description_residual["n"].iloc[0]) != int(manifest["residual_model_rows"])
    ):
        raise AssertionError("Residual description rows do not match manifest")
    for frame in (use, description, description_residual):
        values = frame[["estimate", "std_error", "p_value", "ci_low", "ci_high"]].to_numpy()
        if not np.isfinite(values).all():
            raise AssertionError("Non-finite model result")

    # Confirm that the working outputs reproduce the latest corrected rebuild.
    rebuild_use = pd.read_csv(REBUILD / "outputs" / "rq1_main_table.csv")
    rebuild_use = rebuild_use[
        (rebuild_use["model"] == "active_raw_main")
        & (rebuild_use["outcome"] == "log_funding_hours")
    ].sort_values("term")
    rebuild_description = pd.read_csv(REBUILD / "outputs" / "description_robustness.csv")
    if "representation" in rebuild_description.columns:
        rebuild_description = rebuild_description[
            rebuild_description["representation"].eq(RAW_DESCRIPTION)
        ]
    rebuild_description = rebuild_description.sort_values("term")
    use_sorted = use.sort_values("term")
    description_sorted = description.sort_values("term")
    for metric in ("estimate", "std_error", "p_value", "ci_low", "ci_high"):
        np.testing.assert_allclose(
            use_sorted[metric], rebuild_use[metric], rtol=1e-6, atol=1e-8
        )
        np.testing.assert_allclose(
            description_sorted[metric], rebuild_description[metric], rtol=1e-6, atol=1e-8
        )

    use_robustness = pd.read_csv(paths["use_robustness"])
    use_raw_check = use_robustness[
        (use_robustness["model"] == "active_raw_main")
        & (use_robustness["outcome"] == "log_funding_hours")
        & (use_robustness["term"].isin(["CH", "VG"]))
    ].sort_values("term")
    use_residual = use_robustness[
        (use_robustness["model"] == "active_residual_text")
        & (use_robustness["outcome"] == "log_funding_hours")
        & (use_robustness["term"].isin(["CH", "VG"]))
    ].copy()
    use_main_check = use[use["term"].isin(["CH", "VG"])].sort_values("term")
    if set(use_residual["term"]) != {"CH", "VG"} or not use_residual["term"].is_unique:
        raise AssertionError("Unexpected residual use terms")
    for metric in ("estimate", "std_error", "p_value", "ci_low", "ci_high"):
        np.testing.assert_allclose(
            use_raw_check[metric], use_main_check[metric], rtol=1e-12, atol=1e-12
        )
    values = use_residual[["estimate", "std_error", "p_value", "ci_low", "ci_high"]].to_numpy()
    if not np.isfinite(values).all():
        raise AssertionError("Non-finite residual use result")

    use_phrases = pd.read_csv(paths["use_boilerplate_phrases"])
    description_phrases = pd.read_csv(paths["description_boilerplate_phrases"])
    use_distribution = pd.read_csv(paths["use_boilerplate_distribution"]).iloc[0]
    description_distribution = pd.read_csv(
        paths["description_boilerplate_distribution"]
    ).iloc[0]
    if len(use_phrases) != 409:
        raise AssertionError("Unexpected recurring use phrase count")
    if len(description_phrases) != int(manifest["approved_recurring_phrases"]):
        raise AssertionError("Description phrase rows do not match manifest")
    if int(description_distribution["approved_phrases"]) != len(description_phrases):
        raise AssertionError("Description phrase rows do not match distribution")
    for recurring_frame in (use_phrases, description_phrases):
        if int(recurring_frame["training_document_frequency"].min()) < 659:
            raise AssertionError("Recurring-language document threshold violated")
        if int(recurring_frame["countries_present"].min()) < 3:
            raise AssertionError("Recurring-language country threshold violated")
    for distribution in (use_distribution, description_distribution):
        if not 0 <= float(distribution["nonzero_share_pct"]) <= 100:
            raise AssertionError("Invalid nonzero recurring-language percentage")
        shares = [float(distribution[key]) for key in ("p50", "p90", "p99")]
        if not (0 <= shares[0] <= shares[1] <= shares[2] <= 1):
            raise AssertionError("Invalid recurring-language share quantiles")

    scalers = pd.read_csv(paths["scaler_parameters"])
    scalers = scalers[scalers["specification"] == "active_raw"].set_index("variable")
    use_params = {
        variable: {
            key: float(scalers.loc[variable, key])
            for key in ("mean", "std", "p25", "p50", "p75")
        }
        for variable in ("C", "H", "V", "G")
    }

    model_sql = str(paths["description_model_data"]).replace("'", "''")
    con = duckdb.connect()
    description_params = con.execute(
        f"""
        SELECT
          AVG(H_active_description) AS H_mean,
          STDDEV_SAMP(H_active_description) AS H_std,
          QUANTILE_CONT(H_active_description, 0.25) AS H_p25,
          QUANTILE_CONT(H_active_description, 0.50) AS H_p50,
          QUANTILE_CONT(H_active_description, 0.75) AS H_p75,
          AVG(G_lag_description) AS G_mean,
          STDDEV_SAMP(G_lag_description) AS G_std,
          QUANTILE_CONT(G_lag_description, 0.25) AS G_p25,
          QUANTILE_CONT(G_lag_description, 0.50) AS G_p50,
          QUANTILE_CONT(G_lag_description, 0.75) AS G_p75,
          COUNT(*) AS n
        FROM read_parquet('{model_sql}')
        """
    ).fetchdf().iloc[0].to_dict()

    correlations = con.execute(
        f"""
        WITH z AS (
          SELECT
            (C_active - {use_params['C']['mean']}) / {use_params['C']['std']} AS Cz,
            (H_active_raw - {use_params['H']['mean']}) / {use_params['H']['std']} AS H_use_z,
            (V_lag - {use_params['V']['mean']}) / {use_params['V']['std']} AS Vz,
            (G_lag_raw - {use_params['G']['mean']}) / {use_params['G']['std']} AS G_use_z,
            (H_active_description - {float(description_params['H_mean'])})
              / {float(description_params['H_std'])} AS H_description_z,
            (G_lag_description - {float(description_params['G_mean'])})
              / {float(description_params['G_std'])} AS G_description_z
          FROM read_parquet('{model_sql}')
        )
        SELECT
          COUNT(*) AS n,
          CORR(H_use_z, H_description_z) AS corr_H,
          CORR(G_use_z, G_description_z) AS corr_G,
          CORR(Cz * H_use_z, Cz * H_description_z) AS corr_CH,
          CORR(Vz * G_use_z, Vz * G_description_z) AS corr_VG
        FROM z
        """
    ).fetchdf().iloc[0].to_dict()

    model_data_sql = str(RESULTS / "data" / "model_data.parquet").replace("'", "''")
    sample_relation = con.execute(
        f"""
        WITH use_sample AS (
          SELECT id
          FROM read_parquet('{model_data_sql}')
          WHERE analysis_washin_eligible
            AND fundraising_year BETWEEN 2016 AND 2024
            AND raw_text_nonempty
            AND pool_size_active >= 10
            AND lag_kish_n >= 10
        ), description_sample AS (
          SELECT id FROM read_parquet('{model_sql}')
        )
        SELECT
          (SELECT COUNT(*) FROM use_sample) AS use_n,
          (SELECT COUNT(*) FROM description_sample) AS description_n,
          (SELECT COUNT(*) FROM use_sample ANTI JOIN description_sample USING (id)) AS use_only,
          (SELECT COUNT(*) FROM description_sample ANTI JOIN use_sample USING (id)) AS description_only
        """
    ).fetchdf().iloc[0].to_dict()
    con.close()

    field = pd.read_csv(paths["text_field_diagnostics"]).set_index("field")
    selection = pd.read_csv(paths["text_selection_diagnostics"]).set_index("field")
    use_terms = use.set_index("term")
    description_terms = description.set_index("term")
    use_residual_terms = use_residual.set_index("term")
    description_residual_terms = description_residual.set_index("term")

    coefficient_rows = []
    for term in ("C", "H", "CH", "V", "G", "VG"):
        coefficient_rows.append(
            {
                "term": term,
                "use_estimate": float(use_terms.loc[term, "estimate"]),
                "use_ci_low": float(use_terms.loc[term, "ci_low"]),
                "use_ci_high": float(use_terms.loc[term, "ci_high"]),
                "use_p_value": float(use_terms.loc[term, "p_value"]),
                "description_estimate": float(description_terms.loc[term, "estimate"]),
                "description_ci_low": float(description_terms.loc[term, "ci_low"]),
                "description_ci_high": float(description_terms.loc[term, "ci_high"]),
                "description_p_value": float(description_terms.loc[term, "p_value"]),
                "point_estimate_difference_description_minus_use": float(
                    description_terms.loc[term, "estimate"] - use_terms.loc[term, "estimate"]
                ),
            }
        )

    sensitivity_rows = []
    for text_field, raw_terms, residual_terms in (
        ("use", use_terms, use_residual_terms),
        ("description", description_terms, description_residual_terms),
    ):
        for term in ("CH", "VG"):
            raw = raw_terms.loc[term]
            residual = residual_terms.loc[term]
            sensitivity_rows.append(
                {
                    "field": text_field,
                    "term": term,
                    "raw_n": int(raw["n"]),
                    "raw_estimate": float(raw["estimate"]),
                    "raw_ci_low": float(raw["ci_low"]),
                    "raw_ci_high": float(raw["ci_high"]),
                    "raw_p_value": float(raw["p_value"]),
                    "residual_n": int(residual["n"]),
                    "residual_estimate": float(residual["estimate"]),
                    "residual_ci_low": float(residual["ci_low"]),
                    "residual_ci_high": float(residual["ci_high"]),
                    "residual_p_value": float(residual["p_value"]),
                    "point_estimate_change_residual_minus_raw": float(
                        residual["estimate"] - raw["estimate"]
                    ),
                }
            )

    payload = {
        "status": "validated sensitivity comparison; not a final-package update",
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "comparison_scope": {
            "outcome": "log1p funding hours",
            "period": "2016-2024 training sample",
            "pools": "active same-sector and 35-65 day lagged same-sector",
            "model": "same controls, fixed effects, and country/week two-way CRV1",
            "difference_test": "descriptive point-estimate comparison only; no formal cross-model equality test",
        },
        "quality_gates": {
            "description_identity_passed": bool(manifest["identity_passed"]),
            "description_identity_max_abs_error": float(manifest["identity_max_abs_error"]),
            "identity_threshold": 1e-9,
            "working_raw_results_match_corrected_rebuild_with_tolerance": True,
        },
        "sample_relation": {key: int(value) for key, value in sample_relation.items()},
        "text_diagnostics": {
            text_field: {
                "nonempty_pct": float(field.loc[text_field, "nonempty_pct"]),
                "median_tokens": float(field.loc[text_field, "median_tokens"]),
                "random_pair_zero_overlap_pct": float(
                    selection.loc[text_field, "pair_zero_overlap_pct"]
                ),
                "window_H_variance": float(
                    selection.loc[text_field, "sample_window_h_variance"]
                ),
            }
            for text_field in ("use", "description")
        },
        "common_sample_correlations": {
            key: float(correlations[key]) for key in ("n", "corr_H", "corr_G", "corr_CH", "corr_VG")
        },
        "coefficients": coefficient_rows,
        "recurring_language": {
            "rule": {
                "definition_period": "2016-2024 training documents only",
                "unit": "masked contiguous 5-gram",
                "minimum_training_documents": 659,
                "minimum_countries": 3,
                "attribution_boundary": "boilerplate-like recurring language; no Lending Partner attribution is possible without partner identifiers",
            },
            "field_diagnostics": {
                "use": {
                    "approved_phrases": int(len(use_phrases)),
                    "loans": int(use_distribution["loans"]),
                    "nonzero_share_pct": float(use_distribution["nonzero_share_pct"]),
                    "p50_removed_token_share": float(use_distribution["p50"]),
                    "p90_removed_token_share": float(use_distribution["p90"]),
                    "p99_removed_token_share": float(use_distribution["p99"]),
                },
                "description": {
                    "approved_phrases": int(len(description_phrases)),
                    "loans": int(description_distribution["loans"]),
                    "nonzero_share_pct": float(description_distribution["nonzero_share_pct"]),
                    "emptied_pct": float(description_distribution["emptied_pct"]),
                    "mean_removed_token_share": float(description_distribution["mean_share"]),
                    "p50_removed_token_share": float(description_distribution["p50"]),
                    "p90_removed_token_share": float(description_distribution["p90"]),
                    "p99_removed_token_share": float(description_distribution["p99"]),
                },
            },
            "coefficient_sensitivity": sensitivity_rows,
        },
        "limitations": [
            "The recurring-language comparison is an in-sample sensitivity analysis; the matched 2025 raw-field holdout is reported separately, and template-removed 2025 extrapolation has not been tested.",
            "The two model samples differ by seven rows; description is a strict subset of the use sample.",
            "Raw-versus-residual and field-versus-field point-estimate changes are not formal coefficient-difference tests, and residual samples differ from raw samples.",
            "Descriptions are much longer than use text, so recurring phrase counts are not directly comparable as a rate of institutional templating.",
            "The data contain no Lending Partner identifier, so recurring phrases cannot be attributed to a specific institution.",
            "All estimates are conditional associations, not causal effects.",
        ],
        "input_sha256": {name: sha256(path) for name, path in paths.items()},
        "runtime": {
            "elapsed_seconds": round(time.time() - started, 3),
            "rss_gib": round(psutil.Process().memory_info().rss / 1024**3, 3),
        },
    }

    table_lines = [
        "| Term | use estimate (95% CI; p) | description estimate (95% CI; p) | desc - use |",
        "| --- | ---: | ---: | ---: |",
    ]
    for row in coefficient_rows:
        table_lines.append(
            "| {term} | {ue} ({ul}, {uh}; {up}) | {de} ({dl}, {dh}; {dp}) | {diff} |".format(
                term=row["term"],
                ue=f(row["use_estimate"]),
                ul=f(row["use_ci_low"]),
                uh=f(row["use_ci_high"]),
                up=p(row["use_p_value"]),
                de=f(row["description_estimate"]),
                dl=f(row["description_ci_low"]),
                dh=f(row["description_ci_high"]),
                dp=p(row["description_p_value"]),
                diff=f(row["point_estimate_difference_description_minus_use"]),
            )
        )

    sensitivity_table_lines = [
        "| Field / term | Raw estimate (95% CI; p; n) | After recurring-language removal (95% CI; p; n) | Residual - raw |",
        "| --- | ---: | ---: | ---: |",
    ]
    for row in sensitivity_rows:
        sensitivity_table_lines.append(
            "| {field} / {term} | {re} ({rl}, {rh}; {rp}; {rn:,}) | "
            "{se} ({sl}, {sh}; {sp}; {sn:,}) | {change} |".format(
                field=row["field"],
                term=row["term"],
                re=f(row["raw_estimate"]),
                rl=f(row["raw_ci_low"]),
                rh=f(row["raw_ci_high"]),
                rp=p(row["raw_p_value"]),
                rn=row["raw_n"],
                se=f(row["residual_estimate"]),
                sl=f(row["residual_ci_low"]),
                sh=f(row["residual_ci_high"]),
                sp=p(row["residual_p_value"]),
                sn=row["residual_n"],
                change=f(row["point_estimate_change_residual_minus_raw"]),
            )
        )

    use_ch = use_terms.loc["CH"]
    description_ch = description_terms.loc["CH"]
    use_vg = use_terms.loc["VG"]
    description_vg = description_terms.loc["VG"]
    use_residual_ch = use_residual_terms.loc["CH"]
    description_residual_ch = description_residual_terms.loc["CH"]
    markdown = f"""# Description vs use · sensitivity comparison

Status: validated comparison generated from the corrected 2026-08-31 working run. This is not a final-package update.

## Bottom line

- **Current channel is directionally robust.** `CH` is positive under both `use` ({f(float(use_ch['estimate']))}, 95% CI {f(float(use_ch['ci_low']))} to {f(float(use_ch['ci_high']))}) and `description` ({f(float(description_ch['estimate']))}, 95% CI {f(float(description_ch['ci_low']))} to {f(float(description_ch['ci_high']))}). The description point estimate is {f(float(description_ch['estimate'] - use_ch['estimate']))} higher, but this is not a formal cross-model difference test.
- **Recent interaction is representation-sensitive.** `use` gives a positive `VG` ({f(float(use_vg['estimate']))}, 95% CI {f(float(use_vg['ci_low']))} to {f(float(use_vg['ci_high']))}); `description` gives {f(float(description_vg['estimate']))} with a confidence interval crossing zero ({f(float(description_vg['ci_low']))} to {f(float(description_vg['ci_high']))}).
- **The current-channel estimate is sensitive to recurring language.** After removing train-only recurring 5-grams, `use` CH changes from {f(float(use_ch['estimate']))} to {f(float(use_residual_ch['estimate']))} (95% CI {f(float(use_residual_ch['ci_low']))} to {f(float(use_residual_ch['ci_high']))}; p={p(float(use_residual_ch['p_value']))}), while `description` CH changes from {f(float(description_ch['estimate']))} to {f(float(description_residual_ch['estimate']))} (95% CI {f(float(description_residual_ch['ci_low']))} to {f(float(description_residual_ch['ci_high']))}; p={p(float(description_residual_ch['p_value']))}). Both point estimates are substantially attenuated; this is sensitivity evidence, not a decomposition of how much templates "explain."
- The fields measure closely related but non-identical environments: common-sample correlations are H={f(float(correlations['corr_H']), 4)}, G={f(float(correlations['corr_G']), 4)}, CH={f(float(correlations['corr_CH']), 4)}, and VG={f(float(correlations['corr_VG']), 4)}.

## Comparability checks

- Model rows: `use` {int(sample_relation['use_n']):,}; `description` {int(sample_relation['description_n']):,}. Description is a strict subset, missing only {int(sample_relation['use_only'])} rows from the use sample.
- Nonempty coverage: use {float(field.loc['use', 'nonempty_pct']):.4f}%; description {float(field.loc['description', 'nonempty_pct']):.4f}%.
- Median tokens: use {int(field.loc['use', 'median_tokens'])}; description {int(field.loc['description', 'median_tokens'])}.
- Description identity check: max absolute error {float(manifest['identity_max_abs_error']):.3e} against threshold 1e-9; passed.
- Working use and description coefficients match the corrected `_rebuild` outputs at rtol=1e-6 and atol=1e-8.

## Coefficients

{chr(10).join(table_lines)}

## Recurring-language sensitivity

- Rule: masked 5-grams defined using 2016-2024 training documents only, appearing in at least 659 training documents and at least 3 countries.
- Approved recurring phrases: use {len(use_phrases):,}; description {len(description_phrases):,}.
- Loans with a nonzero removed-token share: use {float(use_distribution['nonzero_share_pct']):.4f}%; description {float(description_distribution['nonzero_share_pct']):.4f}%.
- Median removed-token share: use {float(use_distribution['p50']):.4f}; description {float(description_distribution['p50']):.4f}. Description is much longer (median {int(field.loc['description', 'median_tokens'])} vs {int(field.loc['use', 'median_tokens'])} tokens), so phrase counts are not directly comparable as an institutional-template rate.

{chr(10).join(sensitivity_table_lines)}

## Interpretation boundary

This report covers raw field choice and recurring-language sensitivity for the 2016-2024 log-duration HDFE model. The matched-sample raw-field 2025 holdout is reported separately in `HOLDOUT_2025.md`; template-removed 2025 extrapolation, the description 72-hour HDFE model, heterogeneity, and a description-based Narrative Attention Engine have not been tested. The data have no Lending Partner identifier, so phrases are described only as recurring or boilerplate-like language. Coefficient differences are descriptive and all estimates are conditional associations, not causal effects.

## Sources

- `4_中间产物/我算出来的结果/outputs/rq1_main_table.csv`
- `4_中间产物/我算出来的结果/outputs/robustness.csv`
- `4_中间产物/我算出来的结果/outputs/description_robustness.csv`
- `4_中间产物/我算出来的结果/outputs/boilerplate_like_phrases.csv`
- `4_中间产物/我算出来的结果/outputs/boilerplate_share_distribution.csv`
- `4_中间产物/我算出来的结果/outputs/description_boilerplate_phrases.csv`
- `4_中间产物/我算出来的结果/outputs/description_boilerplate_share_distribution.csv`
- `4_中间产物/我算出来的结果/audit/description_robustness_manifest.json`
- `4_中间产物/我算出来的结果/outputs/text_field_diagnostics.csv`
- `4_中间产物/我算出来的结果/outputs/text_selection_diagnostics.csv`
- `4_中间产物/data/description_model.parquet`
"""

    atomic_json(payload, OUTPUT / "comparison_audit.json")
    atomic_text(markdown, OUTPUT / "README.md")
    print(
        f"comparison complete | coefficients={len(coefficient_rows)} | "
        f"common_sample={int(correlations['n']):,} | "
        f"identity_error={float(manifest['identity_max_abs_error']):.3e} | "
        f"rss_gib={psutil.Process().memory_info().rss / 1024**3:.3f} | "
        f"elapsed_s={time.time() - started:.3f}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
