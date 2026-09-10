#!/usr/bin/env python3
"""Stage 4b: HDFE main models, representation checks, and bounded robustness."""

from __future__ import annotations

import json
import math
import os
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import psutil
import pyfixest as pf
from scipy.stats import t as student_t


# Proposal (p.4): "controlling for loan, borrower, repayment and posting-time
# characteristics, platform-wide volume, and country, activity and week fixed
# effects". The four categorical characteristics enter as controls, not as fixed
# effects, so the frozen "Country + Activity + Week FE" specification stands.
CORE_CONTROLS = [
    "log_loan_amount",
    "log_borrower_count",
    "log_repayment_term",
    "log_platform_posting_7d",
    "gender",
    "repaymentInterval",
    "posting_dow",
    "posting_hour",
]
FIXED_EFFECTS = [
    "country_name",
    "activity",
    "week_id",
]


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


def load_scalers(path: Path) -> tuple[pd.DataFrame, dict[str, dict[str, dict[str, float | str]]]]:
    frame = pd.read_csv(path)
    result: dict[str, dict[str, dict[str, float | str]]] = {}
    for row in frame.itertuples(index=False):
        result.setdefault(row.specification, {})[row.variable] = {
            "source_column": row.source_column,
            "mean": float(row.mean),
            "std": float(row.std),
            "p25": float(row.p25),
            "p50": float(row.p50),
            "p75": float(row.p75),
        }
    return frame, result


def add_standardized_columns(
    data: pd.DataFrame, scalers: dict[str, dict[str, dict[str, float | str]]]
) -> dict[str, dict[str, str]]:
    column_maps: dict[str, dict[str, str]] = {}
    for specification, variables in scalers.items():
        mapping: dict[str, str] = {}
        for variable in ("C", "H", "V", "G"):
            parameters = variables[variable]
            column = str(parameters["source_column"])
            z_column = f"{specification}_{variable}z"
            data[z_column] = (
                (data[column].astype(np.float64) - float(parameters["mean"]))
                / float(parameters["std"])
            ).astype(np.float32)
            mapping[variable] = z_column
        current_interaction = f"{specification}_CH"
        recent_interaction = f"{specification}_VG"
        data[current_interaction] = (data[mapping["C"]] * data[mapping["H"]]).astype(np.float32)
        data[recent_interaction] = (data[mapping["V"]] * data[mapping["G"]]).astype(np.float32)
        mapping["CH"] = current_interaction
        mapping["VG"] = recent_interaction
        column_maps[specification] = mapping
    return column_maps


def formula(outcome: str, mapping: dict[str, str]) -> str:
    regressors = [mapping[key] for key in ("C", "H", "CH", "V", "G", "VG")] + CORE_CONTROLS
    return f"{outcome} ~ {' + '.join(regressors)} | {' + '.join(FIXED_EFFECTS)}"


def fit_model(
    data: pd.DataFrame,
    outcome: str,
    mapping: dict[str, str],
    vcov: dict[str, str],
) -> object:
    return pf.feols(
        formula(outcome, mapping),
        data,
        vcov=vcov,
        copy_data=False,
        store_data=False,
        lean=True,
        fixef_rm="singleton",
    )


def tidy_core(
    fit: object,
    mapping: dict[str, str],
    model_name: str,
    outcome: str,
    representation: str,
    vcov_label: str,
) -> pd.DataFrame:
    tidy = fit.tidy().reset_index().rename(columns={"Coefficient": "coefficient"})
    if "coefficient" not in tidy.columns:
        tidy = tidy.rename(columns={tidy.columns[0]: "coefficient"})
    reverse = {column: key for key, column in mapping.items()}
    tidy = tidy[tidy["coefficient"].isin(reverse)].copy()
    tidy["term"] = tidy["coefficient"].map(reverse)
    tidy["model"] = model_name
    tidy["outcome"] = outcome
    tidy["representation"] = representation
    tidy["vcov"] = vcov_label
    tidy["n"] = int(getattr(fit, "_N", np.nan))
    tidy["r2"] = float(getattr(fit, "_r2", np.nan))
    tidy["within_r2"] = float(getattr(fit, "_r2_within", np.nan))
    tidy = tidy.rename(
        columns={
            "Estimate": "estimate",
            "Std. Error": "std_error",
            "t value": "statistic",
            "Pr(>|t|)": "p_value",
            "2.5%": "ci_low",
            "97.5%": "ci_high",
        }
    )
    return tidy[
        [
            "model",
            "outcome",
            "representation",
            "vcov",
            "n",
            "r2",
            "within_r2",
            "term",
            "coefficient",
            "estimate",
            "std_error",
            "statistic",
            "p_value",
            "ci_low",
            "ci_high",
        ]
    ]


def scenario_contrast(
    fit: object,
    mapping: dict[str, str],
    scaler: dict[str, dict[str, float | str]],
    channel: str,
    outcome: str,
    model_name: str,
    critical_value: float = 1.96,
    ci_degrees_of_freedom: int | None = None,
) -> dict[str, float | int | str | None]:
    if channel == "current":
        left, right, interaction = "C", "H", "CH"
    else:
        left, right, interaction = "V", "G", "VG"
    left_low = (float(scaler[left]["p25"]) - float(scaler[left]["mean"])) / float(
        scaler[left]["std"]
    )
    left_high = (float(scaler[left]["p75"]) - float(scaler[left]["mean"])) / float(
        scaler[left]["std"]
    )
    right_low = (float(scaler[right]["p25"]) - float(scaler[right]["mean"])) / float(
        scaler[right]["std"]
    )
    right_high = (float(scaler[right]["p75"]) - float(scaler[right]["mean"])) / float(
        scaler[right]["std"]
    )
    changes = {
        mapping[left]: left_high - left_low,
        mapping[right]: right_high - right_low,
        mapping[interaction]: left_high * right_high - left_low * right_low,
    }
    coefficients = fit.coef()
    names = list(getattr(fit, "_coefnames"))
    vector = np.zeros(len(names), dtype=float)
    for column, value in changes.items():
        vector[names.index(column)] = value
    beta = coefficients.reindex(names).to_numpy(dtype=float)
    estimate = float(np.dot(vector, beta))
    variance = float(vector @ np.asarray(getattr(fit, "_vcov")) @ vector)
    standard_error = math.sqrt(max(0.0, variance))
    ci_low = estimate - critical_value * standard_error
    ci_high = estimate + critical_value * standard_error
    if outcome == "log_funding_hours":
        effect = 100.0 * math.expm1(estimate)
        effect_low = 100.0 * math.expm1(ci_low)
        effect_high = 100.0 * math.expm1(ci_high)
        effect_unit = "percent change in conditional geometric mean of (1 + funding hours)"
    else:
        effect = 100.0 * estimate
        effect_low = 100.0 * ci_low
        effect_high = 100.0 * ci_high
        effect_unit = "percentage-point change in 72h fast-funding rate"
    return {
        "model": model_name,
        "outcome": outcome,
        "channel": channel,
        "scenario": f"joint training P25 to P75 shift in {left} and {right}",
        "estimate_model_scale": estimate,
        "std_error_model_scale": standard_error,
        "ci_low_model_scale": ci_low,
        "ci_high_model_scale": ci_high,
        "translated_effect": effect,
        "translated_ci_low": effect_low,
        "translated_ci_high": effect_high,
        "translated_unit": effect_unit,
        "ci_critical_value": critical_value,
        "ci_degrees_of_freedom": ci_degrees_of_freedom,
        "n": int(getattr(fit, "_N", np.nan)),
    }


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: fit_main_models.py OUTPUT_DIR")
    output_dir = Path(sys.argv[1]).resolve()
    model_path = output_dir / "data" / "model_data.parquet"
    outputs = output_dir / "outputs"
    audit = output_dir / "audit"
    log_path = audit / "stage4b_models.log"
    log_path.write_text("", encoding="utf-8")
    started = time.time()

    def log(message: str) -> None:
        line = f"{time.strftime('%Y-%m-%dT%H:%M:%S%z')} {message}"
        print(line, flush=True)
        with log_path.open("a", encoding="utf-8") as stream:
            stream.write(line + "\n")

    _, scalers = load_scalers(outputs / "scaler_parameters.csv")
    columns = [
        "id",
        "status",
        "gender",
        "repaymentInterval",
        "sector",
        "activity",
        "country_name",
        "fundraising_year",
        "week_id",
        "posting_dow",
        "posting_hour",
        "log_funding_hours",
        "eligible_72h_followup",
        "funded_within_72h",
        "analysis_washin_eligible",
        "raw_text_nonempty",
        "residual_text_nonempty",
        "pool_size_active",
        "pool_size_14d",
        "pool_size_16d",
        "lag_kish_n",
        "lag_completed_kish_n",
        "C_active",
        "H_active_raw",
        "H_active_residual",
        "C_14d",
        "H_14d_raw",
        "C_16d",
        "H_16d_raw",
        "V_lag",
        "G_lag_raw",
        "G_lag_residual",
        "V_lag_completed",
        "G_lag_completed_raw",
    ] + CORE_CONTROLS
    columns = list(dict.fromkeys(columns))
    data = pd.read_parquet(model_path, columns=columns)
    for column in ["status", "gender", "repaymentInterval", "sector", "activity", "country_name", "week_id"]:
        data[column] = data[column].astype("category")
    data["posting_dow"] = data["posting_dow"].astype("category")
    data["posting_hour"] = data["posting_hour"].astype("category")
    mappings = add_standardized_columns(data, scalers)
    log(f"model data loaded rows={len(data):,} columns={len(data.columns)} rss_gib={psutil.Process().memory_info().rss / 1024**3:.2f}")

    base = (
        data["analysis_washin_eligible"]
        & data["raw_text_nonempty"]
        & (data["pool_size_active"] >= 10)
        & (data["lag_kish_n"] >= 10)
    )
    train_base = base & data["fundraising_year"].between(2016, 2024)
    residual_base = (
        data["analysis_washin_eligible"]
        & data["residual_text_nonempty"]
        & (data["pool_size_active"] >= 10)
        & (data["lag_kish_n"] >= 10)
        & data["fundraising_year"].between(2016, 2024)
    )
    vcov_two = {"CRV1": "country_name + week_id"}

    model_results: list[pd.DataFrame] = []
    robustness_results: list[pd.DataFrame] = []
    scenario_rows: list[dict] = []
    model_manifest: list[dict] = []

    def run(
        model_name: str,
        outcome: str,
        specification: str,
        mask: pd.Series,
        representation: str,
        vcov: dict[str, str] = vcov_two,
        vcov_label: str = "country + week two-way CRV1",
        add_to_main: bool = False,
    ) -> object:
        frame = data.loc[mask].copy()
        before = len(frame)
        fit = fit_model(frame, outcome, mappings[specification], vcov)
        tidy = tidy_core(fit, mappings[specification], model_name, outcome, representation, vcov_label)
        robustness_results.append(tidy[tidy["term"].isin(["CH", "VG"])].copy())
        if add_to_main:
            model_results.append(tidy)
        model_manifest.append(
            {
                "model": model_name,
                "outcome": outcome,
                "specification": specification,
                "input_rows": before,
                "estimated_rows": int(getattr(fit, "_N", 0)),
                "formula": formula(outcome, mappings[specification]),
                "vcov": vcov_label,
            }
        )
        log(
            f"fit_complete model={model_name} n={int(getattr(fit, '_N', 0)):,} "
            f"elapsed_seconds={time.time() - started:.1f}"
        )
        return fit

    main_fit = run(
        "active_raw_main",
        "log_funding_hours",
        "active_raw",
        train_base,
        "masked use TF-IDF",
        add_to_main=True,
    )
    lpm_fit = run(
        "active_raw_72h_lpm",
        "funded_within_72h",
        "active_raw",
        train_base & (data["eligible_72h_followup"] == 1),
        "masked use TF-IDF",
        add_to_main=True,
    )
    residual_fit = run(
        "active_residual_text",
        "log_funding_hours",
        "active_residual",
        residual_base,
        "recurring-language-removed use TF-IDF",
        add_to_main=True,
    )

    posting14_mask = (
        data["analysis_washin_eligible"]
        & data["raw_text_nonempty"]
        & (data["pool_size_14d"] >= 10)
        & (data["lag_kish_n"] >= 10)
        & data["fundraising_year"].between(2016, 2024)
    )
    posting16_mask = (
        data["analysis_washin_eligible"]
        & data["raw_text_nonempty"]
        & (data["pool_size_16d"] >= 10)
        & (data["lag_kish_n"] >= 10)
        & data["fundraising_year"].between(2016, 2024)
    )
    completed_mask = (
        data["analysis_washin_eligible"]
        & data["raw_text_nonempty"]
        & (data["pool_size_active"] >= 10)
        & (data["lag_completed_kish_n"] >= 10)
        & data["fundraising_year"].between(2016, 2024)
    )
    run("posting_14d_precommitted", "log_funding_hours", "posting_14d_raw", posting14_mask, "masked use TF-IDF")
    run("posting_16d_calibrated", "log_funding_hours", "posting_16d_raw", posting16_mask, "masked use TF-IDF")
    run(
        "completed_only_lag",
        "log_funding_hours",
        "active_completed_lag_raw",
        completed_mask,
        "masked use TF-IDF",
    )
    run(
        "minimum_pool_5",
        "log_funding_hours",
        "active_raw",
        data["analysis_washin_eligible"]
        & data["raw_text_nonempty"]
        & (data["pool_size_active"] >= 5)
        & (data["lag_kish_n"] >= 5)
        & data["fundraising_year"].between(2016, 2024),
        "masked use TF-IDF",
    )
    run(
        "minimum_pool_20",
        "log_funding_hours",
        "active_raw",
        data["analysis_washin_eligible"]
        & data["raw_text_nonempty"]
        & (data["pool_size_active"] >= 20)
        & (data["lag_kish_n"] >= 20)
        & data["fundraising_year"].between(2016, 2024),
        "masked use TF-IDF",
    )
    run(
        "exclude_refunded",
        "log_funding_hours",
        "active_raw",
        train_base & (data["status"].astype(str) != "refunded"),
        "masked use TF-IDF",
    )
    run(
        "country_cluster_only",
        "log_funding_hours",
        "active_raw",
        train_base,
        "masked use TF-IDF",
        vcov={"CRV1": "country_name"},
        vcov_label="country CRV1",
    )
    run(
        "week_cluster_only",
        "log_funding_hours",
        "active_raw",
        train_base,
        "masked use TF-IDF",
        vcov={"CRV1": "week_id"},
        vcov_label="week CRV1",
    )

    for fit, outcome, model_name, scenario_mask in (
        (main_fit, "log_funding_hours", "active_raw_main", train_base),
        (
            lpm_fit,
            "funded_within_72h",
            "active_raw_72h_lpm",
            train_base & (data["eligible_72h_followup"] == 1),
        ),
    ):
        scenario_frame = data.loc[scenario_mask]
        scenario_df = min(
            int(scenario_frame["country_name"].nunique()),
            int(scenario_frame["week_id"].nunique()),
        ) - 1
        scenario_critical = float(student_t.ppf(0.975, scenario_df))
        for channel in ("current", "recent"):
            scenario_rows.append(
                scenario_contrast(
                    fit,
                    mappings["active_raw"],
                    scalers["active_raw"],
                    channel,
                    outcome,
                    model_name,
                    critical_value=scenario_critical,
                    ci_degrees_of_freedom=scenario_df,
                )
            )

    main_table = pd.concat(model_results, ignore_index=True)
    atomic_csv(main_table[main_table["model"].isin(["active_raw_main", "active_raw_72h_lpm"])], outputs / "rq1_main_table.csv")
    rq2 = main_table[
        main_table["model"].isin(["active_raw_main", "active_residual_text"])
        & main_table["term"].isin(["V", "G", "VG"])
    ].copy()
    atomic_csv(rq2, outputs / "rq2_raw_vs_residual.csv")
    robustness = pd.concat(robustness_results, ignore_index=True)
    atomic_csv(robustness, outputs / "robustness.csv")
    atomic_csv(pd.DataFrame(scenario_rows), outputs / "scenario_contrasts.csv")
    atomic_json(
        {
            "pyfixest_version": pf.__version__,
            "models": model_manifest,
            "standardization_order": "fit 2016-2024 component means/stds; standardize C/H/V/G; then construct CH and VG; apply unchanged to 2025",
            "outcome_scope": "All rows in the extract have raisedDate; duration and 72h results are conditional on loans present in this official extract.",
            "elapsed_seconds": round(time.time() - started, 3),
            "rss_gib_at_end": round(psutil.Process().memory_info().rss / 1024**3, 3),
        },
        audit / "stage4b_model_manifest.json",
    )
    log(f"stage4b complete models={len(model_manifest)} elapsed_seconds={time.time() - started:.1f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
