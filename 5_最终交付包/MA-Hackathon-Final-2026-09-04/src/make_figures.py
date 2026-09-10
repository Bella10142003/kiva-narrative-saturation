#!/usr/bin/env python3
"""Create publication-ready, source-paired figures from validated CSV outputs."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns


NAVY = "#102A43"
BLUE = "#2F6BFF"
TEAL = "#10A7A0"
CORAL = "#F0655B"
GOLD = "#E5A93D"
INK = "#1F2937"
MUTED = "#64748B"
GRID = "#DDE5EC"
PALE = "#F5F8FB"


def setup() -> None:
    mpl.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 11,
            "axes.titlesize": 15,
            "axes.titleweight": "bold",
            "axes.labelsize": 11,
            "axes.edgecolor": GRID,
            "axes.labelcolor": INK,
            "xtick.color": MUTED,
            "ytick.color": INK,
            "text.color": INK,
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "savefig.facecolor": "white",
            "savefig.bbox": "tight",
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )
    sns.set_style("whitegrid", {"grid.color": GRID, "grid.linestyle": "-"})


def save(fig: plt.Figure, figures: Path, stem: str) -> None:
    fig.savefig(figures / f"{stem}.png", dpi=300, pad_inches=0.12)
    fig.savefig(figures / f"{stem}.pdf", pad_inches=0.12)
    plt.close(fig)


def copy_source(frame: pd.DataFrame, source_dir: Path, name: str) -> None:
    target = source_dir / name
    temporary = target.with_suffix(target.suffix + ".tmp")
    frame.to_csv(temporary, index=False)
    os.replace(temporary, target)


def interval_panel(ax, frame: pd.DataFrame, title: str, xlabel: str, decimals: int = 1) -> None:
    order = ["current", "recent"]
    rows = frame.set_index("channel").loc[order].reset_index()
    y = np.arange(len(rows))[::-1]
    colors = [BLUE, GOLD]
    for yi, row, color in zip(y, rows.itertuples(index=False), colors):
        ax.plot([row.translated_ci_low, row.translated_ci_high], [yi, yi], color=color, lw=3)
        ax.scatter(row.translated_effect, yi, s=90, color=color, edgecolor="white", linewidth=1.2, zorder=3)
        fmt = f"{{:+.{decimals}f}}"
        label = (
            f"{fmt.format(row.translated_effect)}  "
            f"[{fmt.format(row.translated_ci_low)}, {fmt.format(row.translated_ci_high)}]"
        )
        # Keep labels inside their own panel. A white backing preserves legibility
        # without allowing long confidence intervals to collide across panels.
        ax.text(
            0.98,
            yi,
            label,
            transform=ax.get_yaxis_transform(),
            va="center",
            ha="right",
            fontsize=10,
            bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.88, "pad": 1.5},
        )
    ax.axvline(0, color=NAVY, lw=1.2)
    ax.set_yticks(y, ["Current live market", "Recent-listing proxy"])
    ax.margins(x=0.08, y=0.34)
    ax.set_xlabel(xlabel)
    ax.set_title(title, loc="left")
    ax.grid(axis="y", visible=False)
    ax.spines[["top", "right", "left"]].set_visible(False)


def fig_channels(outputs: Path, figures: Path, source_dir: Path) -> None:
    data = pd.read_csv(outputs / "scenario_contrasts.csv")
    copy_source(data, source_dir, "fig01_channel_scenarios.csv")
    fig, axes = plt.subplots(1, 2, figsize=(13.5, 4.7), gridspec_kw={"wspace": 0.38})
    interval_panel(
        axes[0],
        data[data["outcome"].eq("log_funding_hours")],
        "Log-time outcome",
        "Change in geometric mean of (1 + funding hours), %",
    )
    interval_panel(
        axes[1],
        data[data["outcome"].eq("funded_within_72h")],
        "72-hour funding probability",
        "Percentage-point change for joint P25 → P75 shift",
    )
    fig.suptitle("The strongest association is live competition—not the recent-listing proxy", x=0.02, y=1.02, ha="left", fontsize=20, fontweight="bold", color=NAVY)
    fig.text(0.02, -0.03, "HDFE associations, 2016–2024. Log-time panel back-transforms log(1 + hours); it is not an arithmetic mean or intervention forecast.", color=MUTED, fontsize=10)
    save(fig, figures, "fig01_channel_scenarios")


def fig_specification_forest(outputs: Path, figures: Path, source_dir: Path) -> None:
    robust = pd.read_csv(outputs / "robustness.csv")
    keep = {
        "active_raw_main": "Active pool · masked use",
        "active_residual_text": "Active pool · recurring language removed",
        "posting_14d_precommitted": "14-day posting window",
        "posting_16d_calibrated": "16-day posting window",
        "completed_only_lag": "Completed-only lag pool",
    }
    data = robust[robust["model"].isin(keep) & robust["term"].isin(["CH", "VG"])].copy()
    data["specification"] = data["model"].map(keep)
    desc_path = outputs / "description_robustness.csv"
    if desc_path.exists():
        desc = pd.read_csv(desc_path)
        # Normalise the optional description sensitivity table to the core schema.
        if "term" in desc and "estimate" in desc:
            desc = desc[desc["term"].isin(["CH", "VG"])].copy()
            desc["specification"] = "Active pool · masked description"
            data = pd.concat([data, desc], ignore_index=True, sort=False)
    order = list(keep.values()) + (["Active pool · masked description"] if "Active pool · masked description" in set(data["specification"]) else [])
    copy_source(data, source_dir, "fig02_specification_forest.csv")
    fig, axes = plt.subplots(1, 2, figsize=(13.8, 6.3), sharey=True, gridspec_kw={"wspace": 0.08})
    for ax, term, title, color in zip(axes, ["CH", "VG"], ["Current saturation interaction", "Recent saturation interaction"], [BLUE, GOLD]):
        part = data[data["term"].eq(term)].set_index("specification").reindex(order).dropna(subset=["estimate"])
        y = np.arange(len(part))[::-1]
        ax.hlines(y, part["ci_low"], part["ci_high"], color=color, lw=2.6)
        ax.scatter(part["estimate"], y, s=70, color=color, edgecolor="white", linewidth=1.0, zorder=3)
        ax.axvline(0, color=NAVY, lw=1.1)
        ax.set_yticks(y, part.index)
        ax.set_xlabel("Standardised interaction coefficient (log1p funding hours)")
        ax.set_title(title, loc="left")
        ax.grid(axis="y", visible=False)
        ax.spines[["top", "right", "left"]].set_visible(False)
    fig.suptitle("Robustness separates a persistent current signal from a fragile recent-listing proxy", x=0.02, y=1.01, ha="left", fontsize=19, fontweight="bold", color=NAVY)
    fig.text(0.02, -0.03, "Points are specification-specific HDFE coefficients with 95% clustered CIs. Different text representations use different eligible samples.", color=MUTED, fontsize=10)
    save(fig, figures, "fig02_specification_forest")


def fig_year_effects(outputs: Path, figures: Path, source_dir: Path) -> None:
    data = pd.read_csv(outputs / "rq3_year_effects.csv")
    copy_source(data, source_dir, "fig03_year_scenarios.csv")
    fig, axes = plt.subplots(1, 2, figsize=(13.6, 5.4), gridspec_kw={"wspace": 0.25})
    for ax, channel, title, color in zip(axes, ["current", "recent"], ["Current live market", "Recent-listing proxy"], [BLUE, GOLD]):
        part = data[data["channel"].eq(channel)].sort_values("group")
        x = part["group"].astype(int).to_numpy()
        y = part["scenario_percent_change"].to_numpy()
        lo = part["scenario_ci_low"].to_numpy()
        hi = part["scenario_ci_high"].to_numpy()
        ax.fill_between(x, lo, hi, color=color, alpha=0.16)
        ax.plot(x, y, color=color, marker="o", lw=2.5)
        ax.axhline(0, color=NAVY, lw=1)
        ax.set_xticks(x)
        ax.set_title(title, loc="left")
        ax.set_xlabel("Training year")
        ax.set_ylabel("P25 → P75 change in geo. mean(1 + hours), %")
        ax.spines[["top", "right"]].set_visible(False)
    fig.suptitle("Scenario associations vary over time—another reason to test prospectively", x=0.02, y=1.02, ha="left", fontsize=19, fontweight="bold", color=NAVY)
    fig.text(0.02, -0.03, "Year-specific HDFE scenario contrasts with 95% country/week clustered CIs. Heterogeneity is descriptive, not a ranking rule.", color=MUTED, fontsize=10)
    save(fig, figures, "fig03_year_scenarios")


def fig_holdout(outputs: Path, figures: Path, source_dir: Path) -> None:
    raw = pd.read_csv(outputs / "holdout_validation.csv")
    select = raw[
        ((raw["task"].eq("funding_duration")) & raw["evaluation_slice"].eq("2025_at_least_35d_followup") & raw["metric"].isin(["mae_log_hours", "mae_hours"]))
        | ((raw["task"].eq("fast_funding_72h")) & raw["metric"].isin(["brier", "roc_auc", "log_loss"]))
    ].copy()
    pivot = select.pivot_table(index=["task", "metric"], columns="model", values="value").reset_index()
    pivot["relative_change_pct"] = 100 * (pivot["controls_plus_narrative"] / pivot["controls_only"] - 1)
    pivot["deterioration_pct"] = pivot["relative_change_pct"]
    pivot.loc[pivot["metric"].eq("roc_auc"), "deterioration_pct"] *= -1
    labels = {
        "mae_log_hours": "Log-hour MAE",
        "mae_hours": "Hour MAE",
        "brier": "Brier score",
        "roc_auc": "ROC AUC",
        "log_loss": "Log loss",
    }
    pivot["label"] = pivot["metric"].map(labels)
    order = ["Log-hour MAE", "Hour MAE", "Brier score", "ROC AUC", "Log loss"]
    pivot["label"] = pd.Categorical(pivot["label"], order, ordered=True)
    pivot = pivot.sort_values("label")
    copy_source(pivot, source_dir, "fig04_holdout_comparison.csv")
    fig, ax = plt.subplots(figsize=(9.6, 5.5))
    y = np.arange(len(pivot))[::-1]
    colors = [CORAL if x > 0 else TEAL for x in pivot["deterioration_pct"]]
    ax.barh(y, pivot["deterioration_pct"], color=colors, height=0.58)
    ax.axvline(0, color=NAVY, lw=1.2)
    ax.set_yticks(y, pivot["label"].astype(str))
    ax.set_xlabel("Relative deterioration from adding narrative features (%)")
    ax.set_title("Narrative features do not outperform controls on the main 2025 metrics", loc="left", fontsize=18, color=NAVY)
    for yi, value in zip(y, pivot["deterioration_pct"]):
        if value >= 0:
            text_x, align = value + 0.12, "left"
        else:
            # Put the lone improvement label just to the right of zero so it
            # cannot collide with the y-axis category label.
            text_x, align = 0.05, "left"
        ax.text(text_x, yi, f"{value:+.2f}%", va="center", ha=align, fontsize=10)
    ax.grid(axis="y", visible=False)
    ax.spines[["top", "right", "left"]].set_visible(False)
    fig.text(0.01, -0.03, "Positive = worse. Log-loss improves slightly, but MAE, Brier and AUC do not. Differences are descriptive; no paired uncertainty is claimed.", color=MUTED, fontsize=10)
    save(fig, figures, "fig04_holdout_comparison")


def fig_calibration(outputs: Path, figures: Path, source_dir: Path) -> None:
    data = pd.read_csv(outputs / "holdout_calibration.csv")
    copy_source(data, source_dir, "fig05_holdout_calibration.csv")
    fig, ax = plt.subplots(figsize=(7.2, 6.2))
    ax.plot([0, 1], [0, 1], color=MUTED, linestyle="--", lw=1.4, label="Perfect calibration")
    for model, color, label in [
        ("controls_only", NAVY, "Controls only"),
        ("controls_plus_narrative", CORAL, "Controls + narrative"),
    ]:
        part = data[data["model"].eq(model)].sort_values("decile")
        ax.plot(part["predicted_rate"], part["observed_rate"], marker="o", lw=2.4, color=color, label=label)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlabel("Mean predicted 72-hour funding rate")
    ax.set_ylabel("Observed 72-hour funding rate")
    ax.set_title("2025 calibration remains imperfect", loc="left", fontsize=18, color=NAVY)
    ax.legend(frameon=False, loc="upper left")
    ax.spines[["top", "right"]].set_visible(False)
    save(fig, figures, "fig05_holdout_calibration")


def fig_sample_flow(outputs: Path, figures: Path, source_dir: Path) -> None:
    data = pd.read_csv(outputs / "model_sample_flow.csv")
    display = data.iloc[[0, 1, 2, 3, 4, 5]].copy()
    display["label"] = ["Valid durations", "After wash-in", "Text available", "Pool thresholds", "Train 2016–24", "Holdout 2025"]
    copy_source(display, source_dir, "fig06_sample_flow.csv")
    fig, ax = plt.subplots(figsize=(10, 5.4))
    y = np.arange(len(display))[::-1]
    colors = [NAVY, NAVY, NAVY, NAVY, BLUE, TEAL]
    ax.barh(y, display["loans"] / 1e6, color=colors, height=0.62)
    ax.set_yticks(y, display["label"])
    ax.set_xlabel("Loans (millions)")
    ax.set_title("The final design preserves a large, auditable sample", loc="left", fontsize=18, color=NAVY)
    for yi, loans in zip(y, display["loans"]):
        ax.text(loans / 1e6 + 0.015, yi, f"{loans:,}", va="center", fontsize=10)
    ax.grid(axis="y", visible=False)
    ax.spines[["top", "right", "left"]].set_visible(False)
    save(fig, figures, "fig06_sample_flow")


def fig_support(outputs: Path, figures: Path, source_dir: Path) -> None:
    data = pd.read_csv(outputs / "joint_support_quartile_cells.csv")
    current = data[data["channel"].eq("current")].copy()
    copy_source(current, source_dir, "fig07_current_joint_support.csv")
    count = current.pivot(index="right_quartile", columns="left_quartile", values="n").sort_index(ascending=False)
    hours = current.pivot(index="right_quartile", columns="left_quartile", values="median_funding_hours").sort_index(ascending=False)
    fig, axes = plt.subplots(1, 2, figsize=(12.2, 5.2), gridspec_kw={"wspace": 0.32})
    sns.heatmap(count, annot=True, fmt=",.0f", cmap="Blues", ax=axes[0], cbar=False, linewidths=1, linecolor="white")
    sns.heatmap(hours, annot=True, fmt=".0f", cmap="YlOrRd", ax=axes[1], cbar=False, linewidths=1, linecolor="white")
    axes[0].set_title("Loans per quartile cell", loc="left")
    axes[1].set_title("Observed median funding hours", loc="left")
    for ax in axes:
        ax.set_xlabel("Current volume quartile")
        ax.set_ylabel("Focal-to-current-pool overlap quartile")
    fig.suptitle("Both joint scenario endpoints lie in populated support", x=0.02, y=1.03, ha="left", fontsize=18, fontweight="bold", color=NAVY)
    fig.text(0.02, -0.03, "Descriptive cells only; patterns are not covariate-adjusted and do not establish causality.", color=MUTED, fontsize=10)
    save(fig, figures, "fig07_current_joint_support")


def fig_fairness(outputs: Path, figures: Path, source_dir: Path) -> None:
    data = pd.read_csv(outputs / "fairness_diagnostics.csv")
    sector = data[data["dimension"].eq("sector")].sort_values("calibration_gap")
    copy_source(sector, source_dir, "fig08_sector_calibration_gaps.csv")
    fig, ax = plt.subplots(figsize=(10.2, 6.8))
    y = np.arange(len(sector))
    colors = [CORAL if abs(x) >= 0.05 else TEAL for x in sector["calibration_gap"]]
    ax.barh(y, 100 * sector["calibration_gap"], color=colors, height=0.58)
    ax.axvline(0, color=NAVY, lw=1.1)
    ax.set_yticks(y, sector["group"])
    ax.set_xlabel("Predicted minus observed 72-hour rate (percentage points)")
    ax.set_title("Calibration gaps reinforce the no-deployment boundary", loc="left", fontsize=18, color=NAVY)
    ax.grid(axis="y", visible=False)
    ax.spines[["top", "right", "left"]].set_visible(False)
    fig.text(0.01, -0.03, "2025 diagnostic guardrail only; no protected-group or sector targeting is recommended.", color=MUTED, fontsize=10)
    save(fig, figures, "fig08_sector_calibration_gaps")


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: make_figures.py OUTPUT_DIR")
    root = Path(sys.argv[1]).resolve()
    outputs = root / "outputs"
    figures = root / "figures"
    source_dir = figures / "source_data"
    figures.mkdir(parents=True, exist_ok=True)
    source_dir.mkdir(parents=True, exist_ok=True)
    setup()
    fig_channels(outputs, figures, source_dir)
    fig_specification_forest(outputs, figures, source_dir)
    fig_year_effects(outputs, figures, source_dir)
    fig_holdout(outputs, figures, source_dir)
    fig_calibration(outputs, figures, source_dir)
    fig_sample_flow(outputs, figures, source_dir)
    fig_support(outputs, figures, source_dir)
    fig_fairness(outputs, figures, source_dir)
    print("created 8 figures as PNG and PDF with paired source CSV files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
