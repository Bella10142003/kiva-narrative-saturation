# RUNBOOK · Full Analysis and Audit Replay

The final notebooks are quick, independently executable audit views of saved aggregate checkpoints. The full-data computations live in `src/` and require the original Kiva pickle in a private work directory. Never copy raw text or the original pickle into this package. The external ZIP also omits row-level model/feature checkpoints and per-loan triage scores; regenerate them only inside the controlled work environment.

## Environment

Create a Python 3.13 virtual environment and install the versions in `requirements-lock.txt`. Commands below use placeholders so no private machine path is embedded:

```bash
export WORK_DIR=/absolute/private/work-directory
export OUTPUT_DIR=/absolute/final-output-directory
export RAW_GLOB="$WORK_DIR/data/raw_parquet/*.parquet"
export PYTHON=/absolute/venv/bin/python
```

`src/create_and_execute_notebooks.py` executes the audit notebooks against a kernel named
`hackathon-final`; register it from the same virtual environment before running the
pipeline, or that step fails with `NoSuchKernel`:

```bash
$PYTHON -m ipykernel install --user --name hackathon-final --display-name "Hackathon Final (Python)"
```

## Safe intake

Before deserialising any pickle, run `src/safe_pickle_audit.py`. Convert only with the restricted primitive unpickler in `src/convert_pickle_to_parquet.py`. The provided final archive intentionally omits the original pickle and private text checkpoints.

## Full pipeline

```bash
$PYTHON src/profile_and_prepare.py "$RAW_GLOB" "$WORK_DIR" "$OUTPUT_DIR"
$PYTHON src/freeze_spec.py "$WORK_DIR" "$OUTPUT_DIR" "$WORK_DIR/data/clean/core.parquet"
$PYTHON src/text_pipeline.py "$WORK_DIR" "$OUTPUT_DIR"
$PYTHON src/build_pool_features.py "$WORK_DIR" "$OUTPUT_DIR"
$PYTHON src/prepare_model_data.py "$WORK_DIR" "$OUTPUT_DIR"
$PYTHON src/fit_main_models.py "$OUTPUT_DIR"
$PYTHON src/fit_heterogeneity.py "$OUTPUT_DIR"
$PYTHON src/predict_engine.py "$OUTPUT_DIR"
$PYTHON src/description_robustness.py "$WORK_DIR" "$OUTPUT_DIR"
$PYTHON src/check_joint_support.py "$OUTPUT_DIR"
$PYTHON src/make_figures.py "$OUTPUT_DIR"
$PYTHON src/create_and_execute_notebooks.py "$OUTPUT_DIR" "$WORK_DIR"
$PYTHON src/build_deliverables.py "$OUTPUT_DIR"
```

## Deterministic gates

- `audit/pickle_opcode_audit.json`: dangerous opcode count must be 0.
- `outputs/pool_identity_summary.csv`: both max errors <= 1e-9.
- `audit/description_robustness_manifest.json`: `identity_passed=true`.
- `audit/joint_support_manifest.json`: `joint_support_pass=true`.
- `audit/notebook_execution_manifest.json`: seven notebooks executed without error.
- HTML report delivery receipt must say `verification: passed` or explicitly disclose structural-only verification.
- PPTX: render all slides, inspect montage, and run slide overflow checks.
- Final ZIP: `unzip -t` plus secret/private-text scan and SHA-256 manifest.
