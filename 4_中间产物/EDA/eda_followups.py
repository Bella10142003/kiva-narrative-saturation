#!/usr/bin/env python3
"""EDA 追问：结果变量双峰、H 的 1.0 尖峰、交互项 DiD 对比、截断迹象。"""
from __future__ import annotations
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "4_中间产物" / "我算出来的结果"
TAB = ROOT / "4_中间产物" / "EDA" / "tables"

cols = ["fundraising_year", "funding_hours", "log_funding_hours", "H_active_raw",
        "G_lag_raw", "C_active", "V_lag", "pool_size_active", "lag_kish_n",
        "analysis_washin_eligible", "raw_text_nonempty", "sector", "status",
        "eligible_72h_followup", "funded_within_72h", "boilerplate_share"]
df = pd.read_parquet(OUT / "data" / "model_data.parquet", columns=cols)
sc = pd.read_csv(OUT / "outputs" / "scaler_parameters.csv")
p = {r.variable: r for r in sc[sc.specification == "active_raw"].itertuples(index=False)}
for v, src in [("C", "C_active"), ("H", "H_active_raw"), ("V", "V_lag"), ("G", "G_lag_raw")]:
    df[v + "z"] = (df[src] - p[v].mean) / p[v].std
df["CH"] = df["Cz"] * df["Hz"]
df["VG"] = df["Vz"] * df["Gz"]
tr = (df["analysis_washin_eligible"] & df["raw_text_nonempty"]
      & (df["pool_size_active"] >= 10) & (df["lag_kish_n"] >= 10)
      & df["fundraising_year"].between(2016, 2024))
d = df.loc[tr]

# 1. 结果变量双峰性：log_funding_hours 直方
h, e = np.histogram(d["log_funding_hours"], bins=60)
bimod = pd.DataFrame({"bin_left": e[:-1], "bin_right": e[1:], "count": h,
                      "share_pct": 100 * h / h.sum(),
                      "hours_left": np.expm1(e[:-1]), "hours_right": np.expm1(e[1:])})
bimod.round(4).to_csv(TAB / "K1_outcome_histogram.csv", index=False)

# 2. 结果变量顶端是否有截断/堆积
top = d["funding_hours"]
cap = pd.DataFrame([{
    "max_hours": float(top.max()), "max_days": float(top.max() / 24),
    "n_within_1pct_of_max": int((top > 0.99 * top.max()).sum()),
    "n_over_1000h": int((top > 1000).sum()), "pct_over_1000h": 100 * float((top > 1000).mean()),
    "n_over_2000h": int((top > 2000).sum()), "pct_over_2000h": 100 * float((top > 2000).mean()),
    "p999_hours": float(top.quantile(0.999)),
    "gap_p999_to_max_hours": float(top.max() - top.quantile(0.999)),
}])
# 每年最大值（看是否逐年被同一个上限截断）
ymax = d.groupby("fundraising_year")["funding_hours"].agg(
    ["max", "count", lambda s: float((s > 1000).mean() * 100)]).reset_index()
ymax.columns = ["fundraising_year", "max_hours", "n", "pct_over_1000h"]
cap.round(4).to_csv(TAB / "K2_outcome_ceiling_check.csv", index=False)
ymax.round(3).to_csv(TAB / "K3_outcome_max_by_year.csv", index=False)

# 3. H / G 的取值堆积（完全重复文本？零相似？）
spike_rows = []
for c in ["H_active_raw", "G_lag_raw"]:
    s = d[c].dropna()
    spike_rows.append({
        "variable": c, "n": int(s.size),
        "pct_exactly_0": 100 * float((s == 0).mean()),
        "pct_below_0.01": 100 * float((s < 0.01).mean()),
        "pct_above_0.5": 100 * float((s > 0.5).mean()),
        "pct_above_0.9": 100 * float((s > 0.9).mean()),
        "pct_exactly_1": 100 * float((s == 1.0).mean()),
        "n_exactly_1": int((s == 1.0).sum()),
    })
pd.DataFrame(spike_rows).round(5).to_csv(TAB / "K4_similarity_value_spikes.csv", index=False)

# 4. 交互项的非参 DiD：C/H 各按中位数二分，看 2x2 差中差（原始 + 年内）
did_rows = []
for label, frame in [("all_train", d)] + [(f"year_{y}", g) for y, g in d.groupby("fundraising_year")]:
    for (a, b, name) in [("Cz", "Hz", "current_CH"), ("Vz", "Gz", "recent_VG")]:
        ma, mb = frame[a].median(), frame[b].median()
        lo_a, lo_b = frame[a] <= ma, frame[b] <= mb
        cells = {}
        for ka, sa in [("lo", lo_a), ("hi", ~lo_a)]:
            for kb, sb in [("lo", lo_b), ("hi", ~lo_b)]:
                m = sa & sb
                cells[ka + kb] = (float(frame.loc[m, "log_funding_hours"].mean()), int(m.sum()))
        did = (cells["hihi"][0] - cells["hilo"][0]) - (cells["lohi"][0] - cells["lolo"][0])
        did_rows.append({
            "sample": label, "channel": name,
            "mean_lolo": cells["lolo"][0], "mean_lohi": cells["lohi"][0],
            "mean_hilo": cells["hilo"][0], "mean_hihi": cells["hihi"][0],
            "n_lolo": cells["lolo"][1], "n_lohi": cells["lohi"][1],
            "n_hilo": cells["hilo"][1], "n_hihi": cells["hihi"][1],
            "diff_in_diff_logpts": did,
            "corner_gap_logpts": cells["hihi"][0] - cells["lolo"][0],
            "corner_gap_pct": 100 * (np.expm1(cells["hihi"][0]) / np.expm1(cells["lolo"][0]) - 1),
        })
pd.DataFrame(did_rows).round(4).to_csv(TAB / "K5_nonparametric_did.csv", index=False)

# 5. 板块层面：mean_H 与 median funding hours 的横截面关系（辛普森悖论证据）
sec = (d.groupby("sector", observed=True)
       .agg(n=("funding_hours", "size"), median_fh=("funding_hours", "median"),
            mean_log_fh=("log_funding_hours", "mean"), mean_H=("H_active_raw", "mean"),
            median_pool=("pool_size_active", "median")).reset_index())
sec = sec[sec["n"] >= 2000]
simp = pd.DataFrame([{
    "level": "between-sector (n=%d sectors)" % len(sec),
    "corr_meanH_vs_meanlogfh": float(sec["mean_H"].corr(sec["mean_log_fh"])),
    "spearman": float(sec["mean_H"].corr(sec["mean_log_fh"], method="spearman")),
}, {
    "level": "pooled loan-level (raw)",
    "corr_meanH_vs_meanlogfh": float(d["H_active_raw"].corr(d["log_funding_hours"])),
    "spearman": float(d[["H_active_raw", "log_funding_hours"]]
                      .sample(300000, random_state=1).corr(method="spearman").iloc[0, 1]),
}])
# 板块内（去板块均值后）
dd = d[["H_active_raw", "log_funding_hours", "sector"]].dropna()
dd["H_c"] = dd["H_active_raw"] - dd.groupby("sector", observed=True)["H_active_raw"].transform("mean")
dd["Y_c"] = dd["log_funding_hours"] - dd.groupby("sector", observed=True)["log_funding_hours"].transform("mean")
simp = pd.concat([simp, pd.DataFrame([{
    "level": "within-sector (sector-demeaned)",
    "corr_meanH_vs_meanlogfh": float(dd["H_c"].corr(dd["Y_c"])),
    "spearman": np.nan}])], ignore_index=True)
simp.round(4).to_csv(TAB / "K6_simpson_H_vs_outcome.csv", index=False)
sec.round(4).to_csv(TAB / "K7_sector_cross_section.csv", index=False)

# 6. status 分布 —— 是否存在未募满/过期贷款混入
st = d["status"].value_counts().reset_index()
st.columns = ["status", "n"]
st["share_pct"] = (100 * st["n"] / st["n"].sum()).round(3)
st.to_csv(TAB / "K8_status_distribution.csv", index=False)

print("K1..K8 written")
for f in ["K2_outcome_ceiling_check", "K4_similarity_value_spikes", "K6_simpson_H_vs_outcome",
          "K8_status_distribution"]:
    print("\n==", f, "==")
    print(pd.read_csv(TAB / f"{f}.csv").to_string(index=False))
print("\n== K5 (all_train + 3 years) ==")
k5 = pd.read_csv(TAB / "K5_nonparametric_did.csv")
print(k5[k5["sample"].isin(["all_train", "year_2017", "year_2020", "year_2024"])].to_string(index=False))
print("\n== K3 max by year ==")
print(pd.read_csv(TAB / "K3_outcome_max_by_year.csv").to_string(index=False))
