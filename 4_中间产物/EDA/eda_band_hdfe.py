#!/usr/bin/env python3
"""对分段结果做正式 HDFE 复核（国家+活动+周固定效应，国家/周双向聚类）。

上一步 P4/P5 用的是稳健但未聚类的标准误，t 值会被严重高估。
这一步用与主模型完全相同的规格，只换样本，看结论还站不站得住。
"""
from __future__ import annotations

import time
from pathlib import Path

import numpy as np
import pandas as pd
import pyfixest as pf

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "4_中间产物" / "我算出来的结果"
TAB = ROOT / "4_中间产物" / "EDA" / "tables"
T0 = time.time()

CTRL = ["log_loan_amount", "log_borrower_count", "log_repayment_term",
        "log_platform_posting_7d"]
FE = ["country_name", "activity", "week_id", "gender",
      "repaymentInterval", "posting_dow", "posting_hour"]
VCOV = {"CRV1": "country_name + week_id"}


def log(m: str) -> None:
    print(f"[{time.time()-T0:6.1f}s] {m}", flush=True)


cols = (["log_funding_hours", "fundraising_year", "analysis_washin_eligible",
         "raw_text_nonempty", "pool_size_active", "lag_kish_n",
         "C_active", "H_active_raw", "V_lag", "G_lag_raw",
         "country_name", "activity", "week_id", "gender", "repaymentInterval",
         "posting_dow", "posting_hour"] + CTRL)
log("载入 …")
df = pd.read_parquet(OUT / "data" / "model_data.parquet", columns=cols)
sc = pd.read_csv(OUT / "outputs" / "scaler_parameters.csv")
p = {r.variable: r for r in sc[sc.specification == "active_raw"].itertuples(index=False)}
for v, src in [("C", "C_active"), ("H", "H_active_raw"), ("V", "V_lag"), ("G", "G_lag_raw")]:
    df[v + "z"] = ((df[src] - p[v].mean) / p[v].std).astype("float32")
df["CH"] = (df["Cz"] * df["Hz"]).astype("float32")
df["VG"] = (df["Vz"] * df["Gz"]).astype("float32")
for c in FE:
    df[c] = df[c].astype("category")

tr = (df.analysis_washin_eligible & df.raw_text_nonempty
      & (df.pool_size_active >= 10) & (df.lag_kish_n >= 10)
      & df.fundraising_year.between(2016, 2024))
d = df.loc[tr].copy()
log(f"训练期主样本 {len(d):,}")

REGS = ["Cz", "Hz", "CH", "Vz", "Gz", "VG"]
FORM = ("log_funding_hours ~ " + " + ".join(REGS + CTRL)
        + " | " + " + ".join(FE))

hq = d["H_active_raw"].rank(pct=True) * 100
gq = d["G_lag_raw"].rank(pct=True) * 100
SUBS = [
    ("全样本（主模型口径）", pd.Series(True, index=d.index)),
    ("H 下半段 p0-p50", hq <= 50),
    ("H p50-p90", (hq > 50) & (hq <= 90)),
    ("H 高尾 p90-p100", hq > 90),
    ("H 极高尾 p95-p100", hq > 95),
    ("G 下 90% p0-p90", gq <= 90),
    ("G 高尾 p90-p100", gq > 90),
    ("G 极高尾 p95-p100", gq > 95),
]

rows = []
for name, mask in SUBS:
    frame = d.loc[mask]
    if len(frame) < 5000:
        continue
    fit = pf.feols(FORM, frame, vcov=VCOV, copy_data=False,
                   store_data=False, lean=True, fixef_rm="singleton")
    t = fit.tidy().reset_index()
    t.columns = ["coefficient"] + list(t.columns[1:])
    t = t[t["coefficient"].isin(REGS)]
    for r in t.itertuples(index=False):
        rows.append({
            "subsample": name, "n": int(getattr(fit, "_N", len(frame))),
            "share_pct": round(100 * float(mask.mean()), 2),
            "term": r.coefficient, "estimate": float(r.Estimate),
            "std_error": float(r._2), "t": float(r._3), "p_value": float(r._4),
            "ci_low": float(r._5), "ci_high": float(r._6),
            "sig": "***" if r._4 < .01 else ("**" if r._4 < .05 else
                                             ("*" if r._4 < .10 else "")),
        })
    log(f"  {name}: n={int(getattr(fit,'_N',0)):,}")

res = pd.DataFrame(rows)
res.to_csv(TAB / "P6_hdfe_by_band.csv", index=False)

pd.set_option("display.width", 220)
for name, _ in SUBS:
    g = res[res.subsample == name]
    if g.empty:
        continue
    print(f"\n=== {name}  (n={g['n'].iloc[0]:,}, 占 {g['share_pct'].iloc[0]}%)")
    print(g[["term", "estimate", "std_error", "t", "p_value", "sig"]]
          .round(4).to_string(index=False))
log("完成 -> P6_hdfe_by_band.csv")
