#!/usr/bin/env python3
"""Stage 6: out-of-time validation and a non-causal Narrative Attention triage engine."""

from __future__ import annotations

import json
import math
import os
import sys
import time
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import psutil
from sklearn.compose import ColumnTransformer
from sklearn.exceptions import ConvergenceWarning
from sklearn.linear_model import SGDClassifier, SGDRegressor
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    log_loss,
    mean_absolute_error,
    mean_squared_error,
    median_absolute_error,
    r2_score,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from fit_main_models import add_standardized_columns, load_scalers


RANDOM_SEED = 20260904


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


def build_pipeline(
    numeric_columns: list[str], categorical_columns: list[str], classifier: bool
) -> Pipeline:
    preprocessor = ColumnTransformer(
        [
            ("numeric", StandardScaler(), numeric_columns),
            (
                "categorical",
                OneHotEncoder(handle_unknown="ignore", dtype=np.float32),
                categorical_columns,
            ),
        ],
        sparse_threshold=1.0,
    )
    if classifier:
        estimator = SGDClassifier(
            loss="log_loss",
            penalty="l2",
            alpha=1e-5,
            max_iter=100,
            tol=1e-4,
            average=True,
            random_state=RANDOM_SEED,
        )
    else:
        estimator = SGDRegressor(
            loss="squared_error",
            penalty="l2",
            alpha=1e-5,
            max_iter=100,
            tol=1e-4,
            average=True,
            random_state=RANDOM_SEED,
        )
    return Pipeline([("preprocess", preprocessor), ("model", estimator)])


def percentile_score(train_values: np.ndarray, values: np.ndarray) -> np.ndarray:
    clean = np.sort(train_values[np.isfinite(train_values)])
    left = np.searchsorted(clean, values, side="left")
    right = np.searchsorted(clean, values, side="right")
    return 100.0 * (left + right) / (2.0 * len(clean))


def continuous_metrics(
    actual_log: np.ndarray,
    predicted_log: np.ndarray,
    model: str,
    evaluation_slice: str,
    max_train_hours: float,
) -> list[dict]:
    predicted_hours = np.expm1(np.clip(predicted_log, 0.0, math.log1p(max_train_hours)))
    actual_hours = np.expm1(actual_log)
    values = {
        "mae_log_hours": mean_absolute_error(actual_log, predicted_log),
        "median_ae_log_hours": median_absolute_error(actual_log, predicted_log),
        "rmse_log_hours": math.sqrt(mean_squared_error(actual_log, predicted_log)),
        "r2_log_hours": r2_score(actual_log, predicted_log),
        "mae_hours": mean_absolute_error(actual_hours, predicted_hours),
        "median_ae_hours": median_absolute_error(actual_hours, predicted_hours),
    }
    return [
        {
            "task": "funding_duration",
            "evaluation_slice": evaluation_slice,
            "model": model,
            "metric": metric,
            "value": float(value),
            "n": len(actual_log),
        }
        for metric, value in values.items()
    ]


def classification_metrics(
    actual: np.ndarray, probability: np.ndarray, model: str, evaluation_slice: str
) -> list[dict]:
    clipped = np.clip(probability, 1e-6, 1 - 1e-6)
    values = {
        "brier": brier_score_loss(actual, clipped),
        "roc_auc": roc_auc_score(actual, clipped),
        "average_precision": average_precision_score(actual, clipped),
        "log_loss": log_loss(actual, clipped),
        "accuracy_at_0.5": float(np.mean((clipped >= 0.5) == actual)),
    }
    return [
        {
            "task": "fast_funding_72h",
            "evaluation_slice": evaluation_slice,
            "model": model,
            "metric": metric,
            "value": float(value),
            "n": len(actual),
        }
        for metric, value in values.items()
    ]


def calibration_table(actual: np.ndarray, probability: np.ndarray, model: str) -> pd.DataFrame:
    frame = pd.DataFrame({"actual": actual, "probability": probability})
    frame["decile"] = pd.qcut(frame["probability"], 10, labels=False, duplicates="drop") + 1
    result = (
        frame.groupby("decile", observed=True)
        .agg(loans=("actual", "size"), predicted_rate=("probability", "mean"), observed_rate=("actual", "mean"))
        .reset_index()
    )
    result["calibration_gap"] = result["predicted_rate"] - result["observed_rate"]
    result["model"] = model
    return result[["model", "decile", "loans", "predicted_rate", "observed_rate", "calibration_gap"]]


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: predict_engine.py OUTPUT_DIR")
    output_dir = Path(sys.argv[1]).resolve()
    outputs = output_dir / "outputs"
    audit = output_dir / "audit"
    model_path = output_dir / "data" / "model_data.parquet"
    log_path = audit / "stage6_engine.log"
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
        "gender",
        "repaymentInterval",
        "sector",
        "activity",
        "country_name",
        "fundraising_ts",
        "fundraising_year",
        "posting_dow",
        "posting_hour",
        "log_funding_hours",
        "funding_hours",
        "eligible_72h_followup",
        "eligible_35d_followup",
        "funded_within_72h",
        "analysis_washin_eligible",
        "raw_text_nonempty",
        "pool_size_active",
        "lag_kish_n",
        "boilerplate_share",
        "C_active",
        "H_active_raw",
        "V_lag",
        "G_lag_raw",
        "log_loan_amount",
        "log_borrower_count",
        "log_repayment_term",
        "log_platform_posting_7d",
    ]
    data = pd.read_parquet(model_path, columns=columns)
    data["month"] = pd.to_datetime(data["fundraising_ts"], utc=True).dt.month.astype(str)
    for column in [
        "gender",
        "repaymentInterval",
        "sector",
        "activity",
        "country_name",
        "month",
        "posting_dow",
        "posting_hour",
    ]:
        data[column] = data[column].astype(str)
    mapping = add_standardized_columns(data, {"active_raw": scalers["active_raw"]})["active_raw"]
    base = (
        data["analysis_washin_eligible"]
        & data["raw_text_nonempty"]
        & (data["pool_size_active"] >= 10)
        & (data["lag_kish_n"] >= 10)
    )
    train_mask = base & data["fundraising_year"].between(2016, 2024)
    holdout_mask = base & (data["fundraising_year"] == 2025)
    train = data.loc[train_mask].copy()
    holdout = data.loc[holdout_mask].copy()
    log(f"prediction samples train={len(train):,} holdout={len(holdout):,} rss_gib={psutil.Process().memory_info().rss / 1024**3:.2f}")

    categorical = [
        "country_name",
        "activity",
        "sector",
        "gender",
        "repaymentInterval",
        "month",
        "posting_dow",
        "posting_hour",
    ]
    baseline_numeric = [
        "log_loan_amount",
        "log_borrower_count",
        "log_repayment_term",
        "log_platform_posting_7d",
    ]
    narrative_numeric = [mapping[key] for key in ("C", "H", "CH", "V", "G", "VG")] + [
        "boilerplate_share"
    ]
    enhanced_numeric = baseline_numeric + narrative_numeric

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", ConvergenceWarning)
        reg_baseline = build_pipeline(baseline_numeric, categorical, classifier=False)
        reg_enhanced = build_pipeline(enhanced_numeric, categorical, classifier=False)
        reg_baseline.fit(train, train["log_funding_hours"])
        reg_enhanced.fit(train, train["log_funding_hours"])
    log(f"duration predictors fit elapsed_seconds={time.time() - started:.1f}")

    pred_log_baseline = reg_baseline.predict(holdout)
    pred_log_enhanced = reg_enhanced.predict(holdout)
    max_train_hours = float(train["funding_hours"].max())
    metrics: list[dict] = []
    for label, mask in (
        ("2025_all_observed", np.ones(len(holdout), dtype=bool)),
        ("2025_at_least_35d_followup", holdout["eligible_35d_followup"].to_numpy() == 1),
    ):
        actual = holdout.loc[mask, "log_funding_hours"].to_numpy(dtype=float)
        metrics.extend(
            continuous_metrics(actual, pred_log_baseline[mask], "controls_only", label, max_train_hours)
        )
        metrics.extend(
            continuous_metrics(actual, pred_log_enhanced[mask], "controls_plus_narrative", label, max_train_hours)
        )

    train_72 = train[train["eligible_72h_followup"] == 1].copy()
    holdout_72_mask = holdout["eligible_72h_followup"].to_numpy() == 1
    holdout_72 = holdout.loc[holdout_72_mask].copy()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", ConvergenceWarning)
        clf_baseline = build_pipeline(baseline_numeric, categorical, classifier=True)
        clf_enhanced = build_pipeline(enhanced_numeric, categorical, classifier=True)
        clf_baseline.fit(train_72, train_72["funded_within_72h"])
        clf_enhanced.fit(train_72, train_72["funded_within_72h"])
    probability_baseline = clf_baseline.predict_proba(holdout_72)[:, 1]
    probability_enhanced = clf_enhanced.predict_proba(holdout_72)[:, 1]
    actual_72 = holdout_72["funded_within_72h"].to_numpy(dtype=int)
    metrics.extend(
        classification_metrics(actual_72, probability_baseline, "controls_only", "2025_72h_eligible")
    )
    metrics.extend(
        classification_metrics(
            actual_72, probability_enhanced, "controls_plus_narrative", "2025_72h_eligible"
        )
    )
    # Right-truncation sensitivity for the binary co-outcome. Loans posted within 35
    # days of the observation cutoff come from a right-truncated population: only the
    # ones that resolved before the extract appear, so their observed 72h rate is
    # inflated (62.2% in that band versus 51.6% with full follow-up). Re-score on the
    # >=35d subset so the fast-funding task carries the same truncation check the
    # duration task already reports as "2025_at_least_35d_followup".
    mask_72_35d = holdout_72["eligible_35d_followup"].to_numpy() == 1
    metrics.extend(
        classification_metrics(
            actual_72[mask_72_35d],
            probability_baseline[mask_72_35d],
            "controls_only",
            "2025_72h_eligible_at_least_35d",
        )
    )
    metrics.extend(
        classification_metrics(
            actual_72[mask_72_35d],
            probability_enhanced[mask_72_35d],
            "controls_plus_narrative",
            "2025_72h_eligible_at_least_35d",
        )
    )
    validation = pd.DataFrame(metrics)
    atomic_csv(validation, outputs / "holdout_validation.csv")
    calibration = pd.concat(
        [
            calibration_table(actual_72, probability_baseline, "controls_only"),
            calibration_table(actual_72, probability_enhanced, "controls_plus_narrative"),
        ],
        ignore_index=True,
    )
    atomic_csv(calibration, outputs / "holdout_calibration.csv")
    log(f"classification predictors fit/evaluated elapsed_seconds={time.time() - started:.1f}")

    main_terms = pd.read_csv(outputs / "rq1_main_table.csv")
    main_terms = main_terms[
        (main_terms["model"] == "active_raw_main")
        & (main_terms["outcome"] == "log_funding_hours")
    ]
    beta = dict(zip(main_terms["term"], main_terms["estimate"]))
    train_current = (
        beta["C"] * train[mapping["C"]]
        + beta["H"] * train[mapping["H"]]
        + beta["CH"] * train[mapping["CH"]]
    ).to_numpy(dtype=float)
    train_recent = (
        beta["V"] * train[mapping["V"]]
        + beta["G"] * train[mapping["G"]]
        + beta["VG"] * train[mapping["VG"]]
    ).to_numpy(dtype=float)
    holdout_current = (
        beta["C"] * holdout[mapping["C"]]
        + beta["H"] * holdout[mapping["H"]]
        + beta["CH"] * holdout[mapping["CH"]]
    ).to_numpy(dtype=float)
    holdout_recent = (
        beta["V"] * holdout[mapping["V"]]
        + beta["G"] * holdout[mapping["G"]]
        + beta["VG"] * holdout[mapping["VG"]]
    ).to_numpy(dtype=float)

    engine = pd.DataFrame(
        {
            "posting_month": pd.to_datetime(holdout["fundraising_ts"], utc=True).dt.strftime("%Y-%m"),
            "sector": holdout["sector"].to_numpy(),
            "current_volume_score": percentile_score(
                train[mapping["C"]].to_numpy(dtype=float), holdout[mapping["C"]].to_numpy(dtype=float)
            ),
            "current_overlap_score": percentile_score(
                train[mapping["H"]].to_numpy(dtype=float), holdout[mapping["H"]].to_numpy(dtype=float)
            ),
            "current_pressure_score": percentile_score(train_current, holdout_current),
            "recent_volume_score": percentile_score(
                train[mapping["V"]].to_numpy(dtype=float), holdout[mapping["V"]].to_numpy(dtype=float)
            ),
            "recent_overlap_score": percentile_score(
                train[mapping["G"]].to_numpy(dtype=float), holdout[mapping["G"]].to_numpy(dtype=float)
            ),
            "recent_pressure_score": percentile_score(train_recent, holdout_recent),
            "boilerplate_score": percentile_score(
                train["boilerplate_share"].to_numpy(dtype=float),
                holdout["boilerplate_share"].to_numpy(dtype=float),
            ),
            "predicted_funding_hours": np.expm1(
                np.clip(pred_log_enhanced, 0.0, math.log1p(max_train_hours))
            ),
        }
    )
    probability_all = clf_enhanced.predict_proba(holdout)[:, 1]
    engine["predicted_72h_probability"] = probability_all
    conditions = [
        (engine["current_pressure_score"] >= 80) & (engine["recent_pressure_score"] < 80),
        (engine["recent_pressure_score"] >= 80) & (engine["boilerplate_score"] < 80),
        engine["boilerplate_score"] >= 80,
        (engine["predicted_72h_probability"] < 0.35)
        & (engine["current_pressure_score"] < 60)
        & (engine["recent_pressure_score"] < 60),
    ]
    actions = [
        "test listing cadence or diversify related-loan exposure",
        "test platform-side narrative refresh",
        "offer recurring-language template support; do not shift burden to borrower",
        "test exposure support for a distinctive but slow-risk listing",
    ]
    engine["triage_action"] = np.select(conditions, actions, default="monitor; no automated intervention")
    engine["scope_note"] = "risk triage only; not a causal treatment recommendation"
    action_summary = (
        engine.groupby("triage_action", observed=True)
        .agg(loans=("triage_action", "size"), mean_predicted_72h=("predicted_72h_probability", "mean"))
        .reset_index()
        .sort_values("loans", ascending=False)
    )
    action_summary["loan_pct"] = 100.0 * action_summary["loans"] / len(engine)
    atomic_csv(action_summary, outputs / "engine_action_summary.csv")

    fairness_rows: list[dict] = []
    holdout_72_eval = holdout_72.copy()
    holdout_72_eval["predicted_probability"] = probability_enhanced
    holdout_72_eval["predicted_hours"] = np.expm1(
        np.clip(pred_log_enhanced[holdout_72_mask], 0.0, math.log1p(max_train_hours))
    )
    for dimension in ("gender", "sector", "country_name"):
        for group, subset in holdout_72_eval.groupby(dimension, observed=True):
            if len(subset) < 1000:
                continue
            fairness_rows.append(
                {
                    "dimension": dimension,
                    "group": group,
                    "loans": len(subset),
                    "observed_72h_rate": float(subset["funded_within_72h"].mean()),
                    "predicted_72h_rate": float(subset["predicted_probability"].mean()),
                    "calibration_gap": float(
                        subset["predicted_probability"].mean() - subset["funded_within_72h"].mean()
                    ),
                    "median_absolute_error_hours": float(
                        median_absolute_error(subset["funding_hours"], subset["predicted_hours"])
                    ),
                    "use_boundary": "diagnostic guardrail only; no protected-group targeting",
                }
            )
    atomic_csv(pd.DataFrame(fairness_rows), outputs / "fairness_diagnostics.csv")

    atomic_json(
        {
            "training_period": "2016-2024",
            "holdout_period": "2025",
            "baseline": "posting-time controls and categorical context",
            "enhanced": "baseline plus C/H/CH/V/G/VG and recurring-language share",
            "estimators": {
                "duration": "SGDRegressor squared-error on log1p hours",
                "72h": "SGDClassifier logistic loss",
            },
            "random_seed": RANDOM_SEED,
            "duration_primary_holdout_slice": "2025 focal loans with at least 35 calendar days to observation cutoff",
            "72h_holdout_slice": "2025 focal loans with at least 72 hours to observation cutoff",
            "engine_scope": "triage and experiment prioritization; not a causal or automated decision system",
            "raw_identifiers_in_engine": False,
            "row_level_scores_persisted": False,
            "elapsed_seconds": round(time.time() - started, 3),
            "rss_gib_at_end": round(psutil.Process().memory_info().rss / 1024**3, 3),
        },
        audit / "stage6_engine_manifest.json",
    )
    log(f"stage6 complete engine_rows={len(engine):,} elapsed_seconds={time.time() - started:.1f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
