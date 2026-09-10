#!/usr/bin/env python3
"""Create and execute the seven reader-facing audit notebooks.

The memory-intensive pipeline lives in the versioned scripts under src/. These
notebooks provide independently executable, checkpoint-based audit views of
each stage without duplicating the multi-hour full-data calculations.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import nbformat as nbf
from nbclient import NotebookClient


def code(text: str):
    return nbf.v4.new_code_cell(text.strip())


def md(text: str):
    return nbf.v4.new_markdown_cell(text.strip())


COMMON = r'''
from pathlib import Path
import json, time
import pandas as pd
import numpy as np
import psutil
from IPython.display import display, Image

ROOT = Path.cwd().parent
OUTPUTS = ROOT / "outputs"
AUDIT = ROOT / "audit"
LOGS = ROOT / "logs"
LOGS.mkdir(exist_ok=True)
RUN_LOG = LOGS / "run_log.txt"

def checkpoint(label, *frames, started=None):
    elapsed = time.time() - started if started is not None else 0.0
    shapes = [getattr(x, "shape", None) for x in frames]
    nulls = []
    for frame in frames:
        if hasattr(frame, "isna"):
            nulls.append(round(float(frame.isna().mean(numeric_only=False).mean()), 6))
    rss = psutil.Process().memory_info().rss / 1024**3
    line = f"{label} | shapes={shapes} | mean_null_rates={nulls} | rss_gib={rss:.3f} | elapsed_s={elapsed:.3f}"
    print(line)
    with RUN_LOG.open("a", encoding="utf-8") as stream:
        stream.write(line + "\n")

t0 = time.time()
print(f"Audit root: {ROOT}")
checkpoint("setup", started=t0)
'''


NOTEBOOKS = {
    "S0_prepare.ipynb": [
        md("""# S0 · Safe source intake and conversion audit

This notebook audits the safe conversion checkpoint. The original pickle is deliberately excluded from the final package. The full conversion implementation is in `src/profile_and_prepare.py` and the restricted unpickler audit is preserved under `audit/`."""),
        code(COMMON),
        code(r'''
t0 = time.time()
profile = json.loads((AUDIT / "raw_conversion_profile.json").read_text())
schema = pd.read_csv(AUDIT / "raw_schema.csv")
flow = pd.read_csv(OUTPUTS / "analysis_sample_flow.csv")
display(pd.DataFrame([profile]))
display(schema)
display(flow)
checkpoint("S0 source manifests", schema, flow, started=t0)
'''),
        code(r'''
t0 = time.time()
opcode = json.loads((AUDIT / "pickle_opcode_audit.json").read_text())
assert opcode["dangerous_opcode_count"] == 0
assert int(flow.iloc[0]["loans"]) == 1_453_846
assert not (ROOT / "data" / "Kiva_Loans.pkl").exists()
print("PASS: restricted opcode audit, expected source row count, and raw-data exclusion")
display(pd.DataFrame([opcode]))
checkpoint("S0 safety assertions", flow, started=t0)
'''),
    ],
    "S1_audit.ipynb": [
        md("""# S1 · Data quality and frozen analytical specification

This notebook makes the final sample and timing decisions inspectable. It documents a key limitation discovered in the full extract: every valid loan has a `raisedDate`, so the data do not support a true right-censored survival analysis."""),
        code(COMMON),
        code(r'''
t0 = time.time()
profile = pd.read_csv(OUTPUTS / "data_profile_summary.csv")
spec = pd.read_csv(OUTPUTS / "frozen_spec.csv")
quantiles = pd.read_csv(OUTPUTS / "funding_duration_quantiles_train_2016_2024.csv")
display(profile)
display(spec)
display(quantiles)
checkpoint("S1 profile and freeze", profile, spec, quantiles, started=t0)
'''),
        code(r'''
t0 = time.time()
nulls = pd.read_csv(OUTPUTS / "column_null_rates.csv")
status = pd.read_csv(OUTPUTS / "status_raised_crosstab.csv")
pool = pd.read_csv(OUTPUTS / "pool_size_distribution.csv")
display(status)
display(pool)
assert int(profile.loc[0, "negative_durations"]) == 6
print("PASS: six negative-duration records are isolated; all claims use the frozen UTC rules")
checkpoint("S1 quality assertions", nulls, status, pool, started=t0)
'''),
    ],
    "S2_text.ipynb": [
        md("""# S2 · Text representation and recurring-language audit

The primary representation is masked `use` text. Description is retained as a sensitivity check. Train-only hashed TF–IDF avoids vocabulary leakage; recurring exact 5-grams are removed in the residual representation without attributing them to a specific institution."""),
        code(COMMON),
        code(r'''
t0 = time.time()
diagnostics = pd.read_csv(OUTPUTS / "text_selection_diagnostics.csv")
shares = pd.read_csv(OUTPUTS / "boilerplate_share_distribution.csv")
phrases = pd.read_csv(OUTPUTS / "boilerplate_like_phrases.csv")
manifest = json.loads((AUDIT / "stage2_text_manifest.json").read_text())
display(diagnostics)
display(shares)
display(phrases.head(20))
public_manifest = {key: value for key, value in manifest.items() if key != "processed_private_path"}
public_manifest["processed_private_checkpoint"] = "omitted from external delivery"
print(json.dumps(public_manifest, indent=2))
checkpoint("S2 text outputs", diagnostics, shares, phrases, started=t0)
'''),
        code(r'''
t0 = time.time()
description = pd.read_csv(OUTPUTS / "description_robustness.csv")
desc_identity = pd.read_csv(OUTPUTS / "description_pool_identity_check.csv")
desc_manifest = json.loads((AUDIT / "description_robustness_manifest.json").read_text())
assert desc_manifest["identity_passed"]
assert desc_manifest["identity_max_abs_error"] <= 1e-9
display(description)
print(f"Description identity maximum absolute error: {desc_manifest['identity_max_abs_error']:.3e}")
checkpoint("S2 description sensitivity", description, desc_identity, started=t0)
'''),
    ],
    "S3_pools.ipynb": [
        md("""# S3 · Attention-pool construction and exact-identity validation

Pool homogeneity uses the exact identity `mean cosine = focal vector · mean pool vector`. The full implementation maintains sparse rolling vector sums; this notebook verifies its brute-force checks and empirical support."""),
        code(COMMON),
        code(r'''
t0 = time.time()
identity = pd.read_csv(OUTPUTS / "pool_identity_check.csv")
identity_summary = pd.read_csv(OUTPUTS / "pool_identity_summary.csv")
pool_dist = pd.read_csv(OUTPUTS / "pool_size_distribution.csv")
display(identity_summary)
display(pool_dist)
max_error = max(identity["abs_error_raw"].max(), identity["abs_error_residual"].max())
assert max_error <= 1e-9
print(f"PASS: {len(identity):,} brute-force comparisons; max abs error={max_error:.3e}")
checkpoint("S3 pool identity", identity, identity_summary, pool_dist, started=t0)
'''),
        code(r'''
t0 = time.time()
support = pd.read_csv(OUTPUTS / "joint_support_summary.csv")
cells = pd.read_csv(OUTPUTS / "joint_support_quartile_cells.csv")
manifest = json.loads((AUDIT / "joint_support_manifest.json").read_text())
display(support)
assert manifest["joint_support_pass"]
print("PASS: each P25/P75 endpoint has at least 1,000 nearby observed training loans")
checkpoint("S3 joint support", support, cells, started=t0)
'''),
    ],
    "S4_models.ipynb": [
        md("""# S4 · Main HDFE models and bounded robustness

Country, activity and week fixed effects are combined with country/week two-way clustered standard errors. Results are conditional associations. The practical scenarios combine main and interaction terms; a significant interaction alone is not promoted into an operational claim."""),
        code(COMMON),
        code(r'''
t0 = time.time()
main = pd.read_csv(OUTPUTS / "rq1_main_table.csv")
representations = pd.read_csv(OUTPUTS / "rq2_raw_vs_residual.csv")
scenarios = pd.read_csv(OUTPUTS / "scenario_contrasts.csv")
display(main)
display(representations)
display(scenarios)
checkpoint("S4 main estimates", main, representations, scenarios, started=t0)
'''),
        code(r'''
t0 = time.time()
robust = pd.read_csv(OUTPUTS / "robustness.csv")
description = pd.read_csv(OUTPUTS / "description_robustness.csv")
display(robust)
display(description)
current = scenarios[(scenarios.channel == "current") & (scenarios.outcome == "log_funding_hours")].iloc[0]
recent = scenarios[(scenarios.channel == "recent") & (scenarios.outcome == "log_funding_hours")].iloc[0]
assert current.translated_ci_low > 0
assert recent.translated_ci_low < 0 < recent.translated_ci_high
print(f"Current joint contrast: {current.translated_effect:.2f}% [{current.translated_ci_low:.2f}, {current.translated_ci_high:.2f}]")
print(f"Recent joint contrast: {recent.translated_effect:.2f}% [{recent.translated_ci_low:.2f}, {recent.translated_ci_high:.2f}]")
checkpoint("S4 interpretation assertions", robust, description, started=t0)
'''),
    ],
    "S5_hetero.ipynb": [
        md("""# S5 · Temporal and segment heterogeneity

Heterogeneity is treated as descriptive and exploratory. BH-adjusted q-values and global screens are reported, but subgroup rankings are not used to target borrowers or claim stable causal differences."""),
        code(COMMON),
        code(r'''
t0 = time.time()
years = pd.read_csv(OUTPUTS / "rq3_year_effects.csv")
year_global = pd.read_csv(OUTPUTS / "rq3_global_tests.csv")
sectors = pd.read_csv(OUTPUTS / "rq4_sector_effects.csv")
countries = pd.read_csv(OUTPUTS / "rq4_country_effects.csv")
display(year_global)
display(years)
display(sectors.head(30))
display(countries.head(30))
checkpoint("S5 heterogeneity tables", years, year_global, sectors, countries, started=t0)
'''),
        code(r'''
t0 = time.time()
display(Image(filename=str(ROOT / "figures" / "fig03_year_scenarios.png"), width=1000))
display(Image(filename=str(ROOT / "figures" / "fig02_specification_forest.png"), width=1000))
print("Visuals are paired with source CSV files under figures/source_data/.")
checkpoint("S5 rendered figures", years, started=t0)
'''),
    ],
    "S6_engine.ipynb": [
        md("""# S6 · 2025 holdout and experiment-triage boundary

The proposed “Narrative Attention Engine” is not validated for deployment. This stage compares narrative features against a controls-only baseline out of time and retains scores only as an interpretable experiment-triage prototype."""),
        code(COMMON),
        code(r'''
t0 = time.time()
holdout = pd.read_csv(OUTPUTS / "holdout_validation.csv")
calibration = pd.read_csv(OUTPUTS / "holdout_calibration.csv")
actions = pd.read_csv(OUTPUTS / "engine_action_summary.csv")
fairness = pd.read_csv(OUTPUTS / "fairness_diagnostics.csv")
display(holdout)
display(actions)
display(fairness)
checkpoint("S6 holdout diagnostics", holdout, calibration, actions, fairness, started=t0)
'''),
        code(r'''
t0 = time.time()
def metric(task, slice_name, model, name):
    row = holdout[(holdout.task == task) & (holdout.evaluation_slice == slice_name) & (holdout.model == model) & (holdout.metric == name)]
    return float(row.value.iloc[0])

assert metric("funding_duration", "2025_at_least_35d_followup", "controls_plus_narrative", "mae_log_hours") > metric("funding_duration", "2025_at_least_35d_followup", "controls_only", "mae_log_hours")
assert metric("fast_funding_72h", "2025_72h_eligible", "controls_plus_narrative", "brier") > metric("fast_funding_72h", "2025_72h_eligible", "controls_only", "brier")
assert metric("fast_funding_72h", "2025_72h_eligible", "controls_plus_narrative", "roc_auc") < metric("fast_funding_72h", "2025_72h_eligible", "controls_only", "roc_auc")
print("NO-DEPLOYMENT: narrative features do not outperform controls on log-MAE, Brier, or AUC.")
print("Permitted use: generate prospective platform experiments; forbidden use: borrower ranking, approval, or penalty.")
checkpoint("S6 deployment boundary", holdout, started=t0)
'''),
    ],
}


def main() -> int:
    if len(sys.argv) != 3:
        raise SystemExit("usage: create_and_execute_notebooks.py OUTPUT_DIR WORK_DIR")
    root = Path(sys.argv[1]).resolve()
    work = Path(sys.argv[2]).resolve()
    notebooks = root / "notebooks"
    notebooks.mkdir(parents=True, exist_ok=True)
    (root / "logs").mkdir(exist_ok=True)
    (root / "logs" / "run_log.txt").write_text("", encoding="utf-8")
    os.environ["JUPYTER_PATH"] = str(work) + os.pathsep + os.environ.get("JUPYTER_PATH", "")
    execution_rows = []

    for filename, cells in NOTEBOOKS.items():
        notebook = nbf.v4.new_notebook(
            cells=cells,
            metadata={
                "kernelspec": {
                    "display_name": "Hackathon Final (Python)",
                    "language": "python",
                    "name": "hackathon-final",
                },
                "language_info": {"name": "python", "version": "3.13"},
                "pipeline_note": "Reader-facing audit notebook; heavy stage implementation is versioned under src/.",
            },
        )
        path = notebooks / filename
        started = time.time()
        client = NotebookClient(
            notebook,
            timeout=300,
            kernel_name="hackathon-final",
            resources={"metadata": {"path": str(notebooks)}},
            allow_errors=False,
        )
        client.execute()
        nbf.write(notebook, path)
        execution_rows.append(
            {
                "notebook": filename,
                "executed": True,
                "code_cells": sum(cell.cell_type == "code" for cell in notebook.cells),
                "elapsed_seconds": round(time.time() - started, 3),
            }
        )
        print(f"executed {filename} in {execution_rows[-1]['elapsed_seconds']:.3f}s")

    manifest = {
        "notebooks": execution_rows,
        "kernel": str(work / "kernels" / "hackathon-final" / "kernel.json"),
        "scope": "checkpoint-based reproducibility and audit; full-data computation is in src scripts",
    }
    (root / "audit" / "notebook_execution_manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
