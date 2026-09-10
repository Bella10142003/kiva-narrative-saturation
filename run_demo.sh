#!/usr/bin/env bash
# ---------------------------------------------------------------------------
#  Simulation validation — runs end to end in ~90 s, no competition data needed.
#
#  Generates 20,000 synthetic Kiva-shaped loans with the true coefficients
#  planted in them, runs the full analysis pipeline against that data, and
#  scores every estimate against the ground truth it was never allowed to see.
#
#  Requires: python3 with numpy, pandas, scipy, scikit-learn
#      pip install numpy pandas scipy scikit-learn
#
#  Everything is written to 6_模拟验证/_run/ and is safe to delete.
# ---------------------------------------------------------------------------
set -euo pipefail
cd "$(dirname "$0")/6_模拟验证"

python3 - <<'PY'
import importlib, sys
missing = [m for m in ("numpy", "pandas", "scipy", "sklearn") if not importlib.util.find_spec(m)]
if missing:
    sys.exit("Missing packages: " + ", ".join(missing) +
             "\nInstall with:  pip install numpy pandas scipy scikit-learn")
PY

mkdir -p _run
cp ./*.py _run/
cd _run

echo "[1/3] generating 20,000 synthetic loans with a known ground truth ..."
python3 generate_kiva_sim.py > generate.log
echo "      -> kiva_sim_20k.pkl, kiva_sim_truth.csv (the answer key)"

echo "[2/3] running the analysis pipeline (it never reads the answer key) ..."
python3 analysis_pipeline.py > pipeline.log
echo "      -> pipeline_results.json"

echo "[3/3] scoring every specification against the planted truth ..."
python3 compare_to_truth.py | tee compare_to_truth.txt

cat <<'MSG'

---------------------------------------------------------------------------
Done. Output is in 6_模拟验证/_run/ .

What to look for: the "active pool" specification overstates the crowding
coefficient C several times over, because the simulation plants a sector-week
shock the analyst cannot observe. The mirror pool — built only from posting
time, so it cannot be contaminated by outcomes — pulls the estimate back.
That single finding is why the mirror pool exists in the real analysis.

The written verdict on all 14 methodology components is in
6_模拟验证/模拟验证报告.md (Chinese).
---------------------------------------------------------------------------
MSG
