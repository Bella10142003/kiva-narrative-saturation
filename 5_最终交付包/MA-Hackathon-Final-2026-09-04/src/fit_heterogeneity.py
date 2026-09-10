#!/usr/bin/env python3
"""Stage 5: pre-specified year, sector, and country heterogeneity checks."""

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
from scipy.stats import chi2
from statsmodels.stats.multitest import multipletests

from fit_main_models import (
    CORE_CONTROLS,
    FIXED_EFFECTS,
    add_standardized_columns,
    formula,
    load_scalers,
    scenario_contrast,
)


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


def fit_group(
    data: pd.DataFrame,
    mapping: dict[str, str],
    fixed_effects: list[str],
    vcov: dict[str, str],
) -> object:
    regressors = [mapping[key] for key in ("C", "H", "CH", "V", "G", "VG")] + CORE_CONTROLS
    fml = f"log_funding_hours ~ {' + '.join(regressors)} | {' + '.join(fixed_effects)}"
    return pf.feols(
        fml,
        data,
        vcov=vcov,
        copy_data=False,
        store_data=False,
        lean=True,
        fixef_rm="singleton",
    )


def extract_effect_rows(
    fit: object,
    mapping: dict[str, str],
    scaler: dict,
    dimension: str,
    group: str,
    vcov_label: str,
) -> list[dict]:
    tidy = fit.tidy()
    rows: list[dict] = []
    scenarios = {
        channel: scenario_contrast(
            fit,
            mapping,
            scaler,
            channel,
            "log_funding_hours",
            f"{dimension}:{group}",
        )
        for channel in ("current", "recent")
    }
    for channel, term in (("current", "CH"), ("recent", "VG")):
        coefficient = mapping[term]
        values = tidy.loc[coefficient]
        rows.append(
            {
                "dimension": dimension,
                "group": group,
                "channel": channel,
                "term": term,
                "estimate": float(values["Estimate"]),
                "std_error": float(values["Std. Error"]),
                "ci_low": float(values["2.5%"]),
                "ci_high": float(values["97.5%"]),
                "p_value": float(values["Pr(>|t|)"]),
                "scenario_percent_change": float(scenarios[channel]["translated_effect"]),
                "scenario_ci_low": float(scenarios[channel]["translated_ci_low"]),
                "scenario_ci_high": float(scenarios[channel]["translated_ci_high"]),
                "scenario_unit": str(scenarios[channel]["translated_unit"]),
                "n": int(getattr(fit, "_N", 0)),
                "vcov": vcov_label,
            }
        )
    return rows


def add_fdr(frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame.copy()
    frame["q_value_bh"] = np.nan
    for channel in frame["channel"].unique():
        mask = frame["channel"] == channel
        p_values = frame.loc[mask, "p_value"].to_numpy(dtype=float)
        frame.loc[mask, "q_value_bh"] = multipletests(p_values, method="fdr_bh")[1]
    return frame


def global_q_tests(frame: pd.DataFrame, dimension: str) -> pd.DataFrame:
    rows: list[dict] = []
    for channel, group in frame.groupby("channel"):
        valid = group[np.isfinite(group["estimate"]) & (group["std_error"] > 0)].copy()
        weights = 1.0 / np.square(valid["std_error"].to_numpy(dtype=float))
        estimates = valid["estimate"].to_numpy(dtype=float)
        pooled = float(np.sum(weights * estimates) / np.sum(weights))
        statistic = float(np.sum(weights * np.square(estimates - pooled)))
        degrees = max(0, len(valid) - 1)
        p_value = float(chi2.sf(statistic, degrees)) if degrees > 0 else np.nan
        rows.append(
            {
                "dimension": dimension,
                "channel": channel,
                "groups_tested": len(valid),
                "q_statistic": statistic,
                "degrees_of_freedom": degrees,
                "p_value": p_value,
                "method": "inverse-variance Wald/Q screen across non-overlapping subgroup fits",
                "limitation": "does not estimate cross-group covariance from shared platform-week shocks; inspect group CIs and BH q-values",
            }
        )
    return pd.DataFrame(rows)


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: fit_heterogeneity.py OUTPUT_DIR")
    output_dir = Path(sys.argv[1]).resolve()
    outputs = output_dir / "outputs"
    audit = output_dir / "audit"
    model_path = output_dir / "data" / "model_data.parquet"
    log_path = audit / "stage5_heterogeneity.log"
    log_path.write_text("", encoding="utf-8")
    started = time.time()

    def log(message: str) -> None:
        line = f"{time.strftime('%Y-%m-%dT%H:%M:%S%z')} {message}"
        print(line, flush=True)
        with log_path.open("a", encoding="utf-8") as stream:
            stream.write(line + "\n")

    _, scalers = load_scalers(outputs / "scaler_parameters.csv")
    columns = [
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
        "analysis_washin_eligible",
        "raw_text_nonempty",
        "pool_size_active",
        "lag_kish_n",
        "C_active",
        "H_active_raw",
        "V_lag",
        "G_lag_raw",
    ] + CORE_CONTROLS
    columns = list(dict.fromkeys(columns))
    data = pd.read_parquet(model_path, columns=columns)
    for column in ["gender", "repaymentInterval", "sector", "activity", "country_name", "week_id"]:
        data[column] = data[column].astype("category")
    data["posting_dow"] = data["posting_dow"].astype("category")
    data["posting_hour"] = data["posting_hour"].astype("category")
    mappings = add_standardized_columns(data, {"active_raw": scalers["active_raw"]})
    mapping = mappings["active_raw"]
    base = (
        data["analysis_washin_eligible"]
        & data["raw_text_nonempty"]
        & (data["pool_size_active"] >= 10)
        & (data["lag_kish_n"] >= 10)
        & data["fundraising_year"].between(2016, 2024)
    )
    train = data.loc[base].copy()
    log(f"heterogeneity sample rows={len(train):,} rss_gib={psutil.Process().memory_info().rss / 1024**3:.2f}")

    year_rows: list[dict] = []
    for year in range(2016, 2025):
        subset = train[train["fundraising_year"] == year].copy()
        fit = fit_group(
            subset,
            mapping,
            FIXED_EFFECTS,
            {"CRV1": "country_name + week_id"},
        )
        year_rows.extend(
            extract_effect_rows(
                fit,
                mapping,
                scalers["active_raw"],
                "year",
                str(year),
                "country + week two-way CRV1",
            )
        )
        log(f"year_complete year={year} n={int(getattr(fit, '_N', 0)):,}")
    year_effects = add_fdr(pd.DataFrame(year_rows))
    atomic_csv(year_effects, outputs / "rq3_year_effects.csv")
    atomic_csv(global_q_tests(year_effects, "year"), outputs / "rq3_global_tests.csv")

    sector_counts = train.groupby("sector", observed=True).size().sort_values(ascending=False)
    selected_sectors = sector_counts[sector_counts >= 5000].index.astype(str).tolist()
    sector_rows: list[dict] = []
    sector_failures: list[dict] = []
    for sector in selected_sectors:
        subset = train[train["sector"].astype(str) == sector].copy()
        try:
            fit = fit_group(
                subset,
                mapping,
                FIXED_EFFECTS,
                {"CRV1": "country_name + week_id"},
            )
            sector_rows.extend(
                extract_effect_rows(
                    fit,
                    mapping,
                    scalers["active_raw"],
                    "sector",
                    sector,
                    "country + week two-way CRV1",
                )
            )
            log(f"sector_effect_complete sector={sector} n={int(getattr(fit, '_N', 0)):,}")
        except Exception as error:
            sector_failures.append({"sector": sector, "error": f"{type(error).__name__}: {error}"})
            log(f"sector_effect_failed sector={sector} error={type(error).__name__}")
    sector_effects = add_fdr(pd.DataFrame(sector_rows))
    atomic_csv(sector_effects, outputs / "rq4_sector_effects.csv")
    atomic_csv(global_q_tests(sector_effects, "sector"), outputs / "rq4_sector_global_tests.csv")

    country_counts = train.groupby("country_name", observed=True).size().sort_values(ascending=False)
    selected_countries = country_counts.head(15).index.astype(str).tolist()
    country_selection = pd.DataFrame(
        {"country": selected_countries, "training_model_sample_loans": country_counts.loc[selected_countries].to_numpy()}
    )
    atomic_csv(country_selection, outputs / "rq4_country_preselection.csv")
    country_rows: list[dict] = []
    country_failures: list[dict] = []
    country_fixed_effects = [effect for effect in FIXED_EFFECTS if effect != "country_name"]
    for country in selected_countries:
        subset = train[train["country_name"].astype(str) == country].copy()
        try:
            fit = fit_group(subset, mapping, country_fixed_effects, {"CRV1": "week_id"})
            country_rows.extend(
                extract_effect_rows(
                    fit,
                    mapping,
                    scalers["active_raw"],
                    "country",
                    country,
                    "week CRV1 within country",
                )
            )
            log(f"country_effect_complete country={country} n={int(getattr(fit, '_N', 0)):,}")
        except Exception as error:
            country_failures.append({"country": country, "error": f"{type(error).__name__}: {error}"})
            log(f"country_effect_failed country={country} error={type(error).__name__}")
    country_effects = add_fdr(pd.DataFrame(country_rows))
    atomic_csv(country_effects, outputs / "rq4_country_effects.csv")
    atomic_csv(global_q_tests(country_effects, "country"), outputs / "rq4_country_global_tests.csv")

    failures = pd.DataFrame(sector_failures + country_failures)
    if len(failures):
        atomic_csv(failures, audit / "heterogeneity_failures.csv")
    atomic_json(
        {
            "year_groups": 9,
            "sector_minimum_training_n": 5000,
            "sectors_selected": selected_sectors,
            "countries_selected_by_training_volume": selected_countries,
            "multiple_testing": "Benjamini-Hochberg separately within each dimension and channel",
            "global_test": "inverse-variance Wald/Q screening across non-overlapping subgroup estimates",
            "failures": sector_failures + country_failures,
            "elapsed_seconds": round(time.time() - started, 3),
        },
        audit / "stage5_heterogeneity_manifest.json",
    )
    log(f"stage5 complete elapsed_seconds={time.time() - started:.1f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
