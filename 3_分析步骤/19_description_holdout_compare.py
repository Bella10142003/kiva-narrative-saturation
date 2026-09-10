#!/usr/bin/env python3
"""Compare use and description narrative features on the untouched 2025 holdout."""

from __future__ import annotations

import gc
import hashlib
import json
import math
import os
import time
import warnings
from datetime import datetime
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import psutil
from scipy import sparse
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
from sklearn.preprocessing import OneHotEncoder, StandardScaler


ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / "4_中间产物"
RESULTS = WORK / "我算出来的结果"
OUTPUT = RESULTS / "description_vs_use"
MODEL_PATH = RESULTS / "data" / "model_data.parquet"
SCALER_PATH = RESULTS / "outputs" / "scaler_parameters.csv"
DESCRIPTION_FEATURE_DIR = WORK / "data" / "description_features"
RANDOM_SEED = 20260904

BASELINE_NUMERIC = [
    "log_loan_amount",
    "log_borrower_count",
    "log_repayment_term",
    "log_platform_posting_7d",
]
USE_NARRATIVE = ["use_Cz", "use_Hz", "use_CH", "use_Vz", "use_Gz", "use_VG"]
DESCRIPTION_NARRATIVE = [
    "description_Cz",
    "description_Hz",
    "description_CH",
    "description_Vz",
    "description_Gz",
    "description_VG",
]
CATEGORICAL = [
    "country_name",
    "activity",
    "sector",
    "gender",
    "repaymentInterval",
    "month",
    "posting_dow",
    "posting_hour",
]


def sql_literal(value: Path | str) -> str:
    return "'" + str(value).replace("'", "''") + "'"


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


def duration_metrics(actual_log: np.ndarray, predicted_log: np.ndarray, max_train_hours: float) -> dict:
    predicted_hours = np.expm1(np.clip(predicted_log, 0.0, math.log1p(max_train_hours)))
    actual_hours = np.expm1(actual_log)
    return {
        "mae_log_hours": float(mean_absolute_error(actual_log, predicted_log)),
        "median_ae_log_hours": float(median_absolute_error(actual_log, predicted_log)),
        "rmse_log_hours": float(math.sqrt(mean_squared_error(actual_log, predicted_log))),
        "r2_log_hours": float(r2_score(actual_log, predicted_log)),
        "mae_hours": float(mean_absolute_error(actual_hours, predicted_hours)),
        "median_ae_hours": float(median_absolute_error(actual_hours, predicted_hours)),
    }


def classification_metrics(actual: np.ndarray, probability: np.ndarray) -> dict:
    clipped = np.clip(probability, 1e-6, 1 - 1e-6)
    return {
        "brier": float(brier_score_loss(actual, clipped)),
        "roc_auc": float(roc_auc_score(actual, clipped)),
        "average_precision": float(average_precision_score(actual, clipped)),
        "log_loss": float(log_loss(actual, clipped)),
        "accuracy_at_0.5": float(np.mean((clipped >= 0.5) == actual)),
    }


def main() -> int:
    started = time.time()
    feature_paths = sorted(DESCRIPTION_FEATURE_DIR.glob("sector_*.parquet"))
    if len(feature_paths) != 19:
        raise FileNotFoundError(f"Expected 19 description feature files; found {len(feature_paths)}")
    if not MODEL_PATH.exists() or not SCALER_PATH.exists():
        raise FileNotFoundError("Missing model_data.parquet or scaler_parameters.csv")

    features_sql = "[" + ",".join(sql_literal(path) for path in feature_paths) + "]"
    con = duckdb.connect()
    con.execute("SET TimeZone='UTC'")
    con.execute("SET threads=4")
    con.execute("SET memory_limit='6GB'")
    feature_identity = con.execute(
        f"""
        SELECT COUNT(*) AS rows, COUNT(DISTINCT id) AS unique_ids
        FROM read_parquet({features_sql})
        """
    ).fetchdf().iloc[0]
    if int(feature_identity["rows"]) != 1_453_840 or int(feature_identity["unique_ids"]) != 1_453_840:
        raise AssertionError(f"Description feature identity failed: {feature_identity.to_dict()}")

    columns = [
        "m.id",
        "m.gender",
        "m.repaymentInterval",
        "m.sector",
        "m.activity",
        "m.country_name",
        "m.fundraising_ts",
        "m.fundraising_year",
        "m.posting_dow",
        "m.posting_hour",
        "m.log_funding_hours",
        "m.funding_hours",
        "m.eligible_72h_followup",
        "m.eligible_35d_followup",
        "m.funded_within_72h",
        "m.C_active",
        "m.H_active_raw",
        "m.V_lag",
        "m.G_lag_raw",
        "d.H_active_description",
        "d.G_lag_description",
    ] + [f"m.{column}" for column in BASELINE_NUMERIC]
    select_columns = ",\n          ".join(columns)
    relation = f"""
        SELECT
          {select_columns}
        FROM read_parquet({sql_literal(MODEL_PATH)}) m
        JOIN read_parquet({features_sql}) d USING (id)
        WHERE m.analysis_washin_eligible
          AND m.raw_text_nonempty
          AND m.fundraising_year BETWEEN 2016 AND 2025
          AND m.pool_size_active >= 10
          AND m.lag_kish_n >= 10
          AND d.H_active_description IS NOT NULL
          AND d.G_lag_description IS NOT NULL
    """

    description_scalers = con.execute(
        f"""
        SELECT
          AVG(H_active_description) AS H_mean,
          STDDEV_SAMP(H_active_description) AS H_std,
          AVG(G_lag_description) AS G_mean,
          STDDEV_SAMP(G_lag_description) AS G_std
        FROM ({relation})
        WHERE fundraising_year BETWEEN 2016 AND 2024
        """
    ).fetchdf().iloc[0]
    data = con.execute(relation + "\n        ORDER BY id").fetchdf()
    con.close()

    scaler_frame = pd.read_csv(SCALER_PATH)
    use_scaler = scaler_frame[scaler_frame["specification"] == "active_raw"].set_index("variable")
    for variable, source in (("C", "C_active"), ("H", "H_active_raw"), ("V", "V_lag"), ("G", "G_lag_raw")):
        data[f"use_{variable}z"] = (
            (data[source].astype(np.float64) - float(use_scaler.loc[variable, "mean"]))
            / float(use_scaler.loc[variable, "std"])
        ).astype(np.float32)
    data["use_CH"] = (data["use_Cz"] * data["use_Hz"]).astype(np.float32)
    data["use_VG"] = (data["use_Vz"] * data["use_Gz"]).astype(np.float32)

    data["description_Cz"] = data["use_Cz"]
    data["description_Vz"] = data["use_Vz"]
    data["description_Hz"] = (
        (data["H_active_description"].astype(np.float64) - float(description_scalers["H_mean"]))
        / float(description_scalers["H_std"])
    ).astype(np.float32)
    data["description_Gz"] = (
        (data["G_lag_description"].astype(np.float64) - float(description_scalers["G_mean"]))
        / float(description_scalers["G_std"])
    ).astype(np.float32)
    data["description_CH"] = (data["description_Cz"] * data["description_Hz"]).astype(np.float32)
    data["description_VG"] = (data["description_Vz"] * data["description_Gz"]).astype(np.float32)

    data["month"] = pd.to_datetime(data["fundraising_ts"], utc=True).dt.month.astype(str)
    for column in CATEGORICAL:
        data[column] = data[column].astype(str)
    for column in BASELINE_NUMERIC:
        data[column] = data[column].astype(np.float64)
    for column in USE_NARRATIVE + DESCRIPTION_NARRATIVE:
        data[column] = data[column].astype(np.float32)

    train_mask = data["fundraising_year"].between(2016, 2024).to_numpy()
    holdout_mask = (data["fundraising_year"] == 2025).to_numpy()
    train_n = int(train_mask.sum())
    holdout_n = int(holdout_mask.sum())
    if train_n != 1_234_124:
        raise AssertionError(f"Unexpected matched training rows: {train_n}")
    if holdout_n != 133_409:
        raise AssertionError(f"Unexpected matched holdout rows: {holdout_n}")

    all_numeric = BASELINE_NUMERIC + USE_NARRATIVE + DESCRIPTION_NARRATIVE
    preprocessor = ColumnTransformer(
        [
            ("numeric", StandardScaler(), all_numeric),
            (
                "categorical",
                OneHotEncoder(handle_unknown="ignore", dtype=np.float32),
                CATEGORICAL,
            ),
        ],
        sparse_threshold=1.0,
    )
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", ConvergenceWarning)
        x_train_all = preprocessor.fit_transform(data.loc[train_mask, all_numeric + CATEGORICAL])
        x_holdout_all = preprocessor.transform(data.loc[holdout_mask, all_numeric + CATEGORICAL])
    if not sparse.issparse(x_train_all):
        x_train_all = sparse.csr_matrix(x_train_all)
        x_holdout_all = sparse.csr_matrix(x_holdout_all)
    x_train_all = x_train_all.tocsr().astype(np.float32)
    x_holdout_all = x_holdout_all.tocsr().astype(np.float32)

    numeric_count = len(all_numeric)
    categorical_indices = np.arange(numeric_count, x_train_all.shape[1])
    model_indices = {
        "controls_only": np.concatenate([np.arange(0, len(BASELINE_NUMERIC)), categorical_indices]),
        "controls_plus_use": np.concatenate(
            [
                np.arange(0, len(BASELINE_NUMERIC) + len(USE_NARRATIVE)),
                categorical_indices,
            ]
        ),
        "controls_plus_description": np.concatenate(
            [
                np.arange(0, len(BASELINE_NUMERIC)),
                np.arange(
                    len(BASELINE_NUMERIC) + len(USE_NARRATIVE),
                    len(BASELINE_NUMERIC) + len(USE_NARRATIVE) + len(DESCRIPTION_NARRATIVE),
                ),
                categorical_indices,
            ]
        ),
    }

    y_train_log = data.loc[train_mask, "log_funding_hours"].to_numpy(dtype=float)
    y_holdout_log = data.loc[holdout_mask, "log_funding_hours"].to_numpy(dtype=float)
    holdout_35d = data.loc[holdout_mask, "eligible_35d_followup"].to_numpy() == 1
    max_train_hours = float(data.loc[train_mask, "funding_hours"].max())

    duration_predictions: dict[str, np.ndarray] = {}
    for label, indices in model_indices.items():
        model = SGDRegressor(
            loss="squared_error",
            penalty="l2",
            alpha=1e-5,
            max_iter=100,
            tol=1e-4,
            average=True,
            random_state=RANDOM_SEED,
        )
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", ConvergenceWarning)
            model.fit(x_train_all[:, indices], y_train_log)
        duration_predictions[label] = model.predict(x_holdout_all[:, indices])
        del model
        gc.collect()

    duration_results: dict[str, dict[str, dict]] = {"2025_all_observed": {}, "2025_at_least_35d_followup": {}}
    for label, prediction in duration_predictions.items():
        duration_results["2025_all_observed"][label] = duration_metrics(
            y_holdout_log, prediction, max_train_hours
        )
        duration_results["2025_at_least_35d_followup"][label] = duration_metrics(
            y_holdout_log[holdout_35d], prediction[holdout_35d], max_train_hours
        )

    train_72 = data.loc[train_mask, "eligible_72h_followup"].to_numpy() == 1
    holdout_72 = data.loc[holdout_mask, "eligible_72h_followup"].to_numpy() == 1
    y_train_72 = data.loc[train_mask, "funded_within_72h"].to_numpy(dtype=int)[train_72]
    y_holdout_72 = data.loc[holdout_mask, "funded_within_72h"].to_numpy(dtype=int)[holdout_72]
    holdout_72_35d = holdout_35d[holdout_72]

    classification_predictions: dict[str, np.ndarray] = {}
    for label, indices in model_indices.items():
        model = SGDClassifier(
            loss="log_loss",
            penalty="l2",
            alpha=1e-5,
            max_iter=100,
            tol=1e-4,
            average=True,
            random_state=RANDOM_SEED,
        )
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", ConvergenceWarning)
            model.fit(x_train_all[train_72][:, indices], y_train_72)
        classification_predictions[label] = model.predict_proba(x_holdout_all[holdout_72][:, indices])[:, 1]
        del model
        gc.collect()

    classification_results: dict[str, dict[str, dict]] = {
        "2025_72h_eligible": {},
        "2025_72h_eligible_at_least_35d": {},
    }
    for label, probability in classification_predictions.items():
        classification_results["2025_72h_eligible"][label] = classification_metrics(
            y_holdout_72, probability
        )
        classification_results["2025_72h_eligible_at_least_35d"][label] = classification_metrics(
            y_holdout_72[holdout_72_35d], probability[holdout_72_35d]
        )

    primary_duration = duration_results["2025_at_least_35d_followup"]
    primary_72h = classification_results["2025_72h_eligible_at_least_35d"]
    lower_duration = ("mae_log_hours", "rmse_log_hours", "mae_hours")
    higher_duration = ("r2_log_hours",)
    lower_72h = ("brier", "log_loss")
    higher_72h = ("roc_auc", "average_precision", "accuracy_at_0.5")
    description_beats_use = all(
        primary_duration["controls_plus_description"][metric]
        < primary_duration["controls_plus_use"][metric]
        for metric in lower_duration
    ) and all(
        primary_duration["controls_plus_description"][metric]
        > primary_duration["controls_plus_use"][metric]
        for metric in higher_duration
    ) and all(
        primary_72h["controls_plus_description"][metric]
        < primary_72h["controls_plus_use"][metric]
        for metric in lower_72h
    ) and all(
        primary_72h["controls_plus_description"][metric]
        > primary_72h["controls_plus_use"][metric]
        for metric in higher_72h
    )
    if not description_beats_use:
        raise AssertionError("Expected description to outperform use on all primary table metrics")

    payload = {
        "status": "matched-sample 2025 holdout comparison; not a final-package update",
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "design": {
            "training_period": "2016-2024",
            "holdout_period": "2025",
            "common_sample": True,
            "baseline": "four posting-time numeric controls plus categorical context",
            "use_model": "baseline plus use C/H/CH/V/G/VG",
            "description_model": "baseline plus description C/H/CH/V/G/VG",
            "recurring_language_share_included": False,
            "reason_recurring_language_excluded": "Use raw H/G on both sides to isolate field choice; recurring-language-removed 2025 extrapolation is a separate, untested specification.",
            "estimators": {
                "duration": "SGDRegressor squared-error on log1p funding hours",
                "72h": "SGDClassifier logistic loss",
            },
            "random_seed": RANDOM_SEED,
            "paired_metric_uncertainty": "not estimated; comparisons are descriptive",
            "working_checkpoint_note": "Working model_data/scalers are numerically aligned with the corrected rebuild; this diagnostic remains outside the final package.",
            "description_train_scalers": {
                "H_mean": float(description_scalers["H_mean"]),
                "H_std": float(description_scalers["H_std"]),
                "G_mean": float(description_scalers["G_mean"]),
                "G_std": float(description_scalers["G_std"]),
            },
        },
        "samples": {
            "train": train_n,
            "holdout_all_observed": holdout_n,
            "holdout_at_least_35d": int(holdout_35d.sum()),
            "holdout_72h_eligible": int(holdout_72.sum()),
            "holdout_72h_eligible_at_least_35d": int(holdout_72_35d.sum()),
        },
        "duration": duration_results,
        "fast_funding_72h": classification_results,
        "interpretation": {
            "description_beats_use_on_all_primary_table_metrics": description_beats_use,
            "description_vs_controls_primary_wins": [
                "duration.mae_hours",
                "fast_funding_72h.log_loss",
            ],
            "description_vs_controls_primary_losses": [
                "duration.mae_log_hours",
                "duration.rmse_log_hours",
                "duration.r2_log_hours",
                "fast_funding_72h.brier",
                "fast_funding_72h.roc_auc",
                "fast_funding_72h.average_precision",
                "fast_funding_72h.accuracy_at_0.5",
            ],
            "conclusion": "Description is consistently better than use in this matched raw-field comparison, but narrative features do not stably improve on controls only.",
        },
        "input_sha256": {
            "model_data": sha256(MODEL_PATH),
            "scaler_parameters": sha256(SCALER_PATH),
            "description_features_combined": hashlib.sha256(
                "".join(sha256(path) for path in feature_paths).encode()
            ).hexdigest(),
        },
        "runtime": {
            "elapsed_seconds": round(time.time() - started, 3),
            "rss_gib": round(psutil.Process().memory_info().rss / 1024**3, 3),
            "design_matrix_train_shape": list(x_train_all.shape),
            "design_matrix_holdout_shape": list(x_holdout_all.shape),
        },
        "limitations": [
            "This is a raw-field holdout comparison; recurring-language-removed use and description features were not evaluated on 2025.",
            "No paired uncertainty was calculated for metric differences.",
            "Out-of-time prediction does not establish causal validity or authorize deployment.",
        ],
    }
    atomic_json(payload, OUTPUT / "holdout_2025_comparison.json")

    markdown = f"""# 2025 holdout · use vs description

Status: matched-sample diagnostic generated from the corrected working checkpoints. This is not a final-package update.

## Design

- Train: 2016-2024 ({train_n:,} loans); untouched holdout: 2025 ({holdout_n:,} loans).
- All three models use the same rows and categorical context.
- `controls_plus_use` adds use-based C/H/CH/V/G/VG; `controls_plus_description` adds description-based C/H/CH/V/G/VG.
- Both sides use raw H/G and exclude recurring-language share to isolate field choice; this holdout does not test the template-removed specification.

## Bottom line

- Description outperforms use on every metric in the two primary tables, but the margins are small.
- Description does not stably outperform controls only: it improves hour MAE ({primary_duration['controls_plus_description']['mae_hours']:.2f} vs {primary_duration['controls_only']['mae_hours']:.2f}) and 72-hour log-loss ({primary_72h['controls_plus_description']['log_loss']:.4f} vs {primary_72h['controls_only']['log_loss']:.4f}), while the other seven reported primary metrics are worse.
- These are descriptive metric differences without paired uncertainty; they do not support deployment of borrower-level narrative scoring.

## Primary 35-day-follow-up duration metrics

| Model | log-hour MAE | log-hour RMSE | log-hour R2 | hour MAE |
| --- | ---: | ---: | ---: | ---: |
| Controls only | {primary_duration['controls_only']['mae_log_hours']:.4f} | {primary_duration['controls_only']['rmse_log_hours']:.4f} | {primary_duration['controls_only']['r2_log_hours']:.4f} | {primary_duration['controls_only']['mae_hours']:.2f} |
| Controls + use | {primary_duration['controls_plus_use']['mae_log_hours']:.4f} | {primary_duration['controls_plus_use']['rmse_log_hours']:.4f} | {primary_duration['controls_plus_use']['r2_log_hours']:.4f} | {primary_duration['controls_plus_use']['mae_hours']:.2f} |
| Controls + description | {primary_duration['controls_plus_description']['mae_log_hours']:.4f} | {primary_duration['controls_plus_description']['rmse_log_hours']:.4f} | {primary_duration['controls_plus_description']['r2_log_hours']:.4f} | {primary_duration['controls_plus_description']['mae_hours']:.2f} |

## Primary 72-hour metrics with at least 35 days of follow-up

| Model | Brier | ROC AUC | Average precision | Log-loss | Accuracy |
| --- | ---: | ---: | ---: | ---: | ---: |
| Controls only | {primary_72h['controls_only']['brier']:.4f} | {primary_72h['controls_only']['roc_auc']:.4f} | {primary_72h['controls_only']['average_precision']:.4f} | {primary_72h['controls_only']['log_loss']:.4f} | {primary_72h['controls_only']['accuracy_at_0.5']:.4f} |
| Controls + use | {primary_72h['controls_plus_use']['brier']:.4f} | {primary_72h['controls_plus_use']['roc_auc']:.4f} | {primary_72h['controls_plus_use']['average_precision']:.4f} | {primary_72h['controls_plus_use']['log_loss']:.4f} | {primary_72h['controls_plus_use']['accuracy_at_0.5']:.4f} |
| Controls + description | {primary_72h['controls_plus_description']['brier']:.4f} | {primary_72h['controls_plus_description']['roc_auc']:.4f} | {primary_72h['controls_plus_description']['average_precision']:.4f} | {primary_72h['controls_plus_description']['log_loss']:.4f} | {primary_72h['controls_plus_description']['accuracy_at_0.5']:.4f} |

Metric differences are descriptive; paired uncertainty was not estimated. Lower is better for MAE, RMSE, Brier, and log-loss; higher is better for R2, AUC, average precision, and accuracy.
"""
    atomic_text(markdown, OUTPUT / "HOLDOUT_2025.md")
    print(
        f"holdout comparison complete | train={train_n:,} | holdout={holdout_n:,} | "
        f"matrix={x_train_all.shape} | rss_gib={psutil.Process().memory_info().rss / 1024**3:.2f} | "
        f"elapsed_s={time.time() - started:.1f}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
