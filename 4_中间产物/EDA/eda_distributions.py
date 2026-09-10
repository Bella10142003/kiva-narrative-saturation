#!/usr/bin/env python3
"""逐变量分布画像：结果变量 + 全部过程变量。

对每个变量回答：什么形状、集中在哪、尾巴多长、有没有堆积/断点/边界质量、
离散还是连续、缺失多少、逐年有没有漂移。

输出 4_中间产物/EDA/tables/M*.csv，不改动任何既有交付物。
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "4_中间产物" / "我算出来的结果"
TAB = ROOT / "4_中间产物" / "EDA" / "tables"
TAB.mkdir(parents=True, exist_ok=True)
T0 = time.time()


def log(m: str) -> None:
    print(f"[{time.time()-T0:6.1f}s] {m}", flush=True)


GROUPS: dict[str, list[str]] = {
    "结果变量": ["funding_hours", "log_funding_hours", "funded_within_72h",
                 "eligible_72h_followup", "eligible_35d_followup"],
    "池规模": ["pool_size_active", "pool_size_14d", "pool_size_16d",
               "lag_pool_raw_count", "lag_weight", "lag_kish_n",
               "lag_completed_raw_count", "lag_completed_weight", "lag_completed_kish_n"],
    "拥挤度 C/V": ["C_active", "C_14d", "C_16d", "V_lag", "V_lag_completed"],
    "相似度 H/G": ["H_active_raw", "H_active_residual", "H_14d_raw", "H_14d_residual",
                   "H_16d_raw", "H_16d_residual", "G_lag_raw", "G_lag_residual",
                   "G_lag_completed_raw", "G_lag_completed_residual"],
    "文本": ["boilerplate_share"],
    "控制变量": ["loanAmount", "log_loan_amount", "borrowerCount", "log_borrower_count",
                 "lenderRepaymentTerm", "log_repayment_term",
                 "platform_posting_7d_count", "log_platform_posting_7d", "country_ppp"],
    "衍生 z 与交互": ["Cz", "Hz", "Vz", "Gz", "CH", "VG",
                      "Cz_res", "Hz_res", "Vz_res", "Gz_res", "CH_res", "VG_res"],
    "时间与设计": ["fundraising_year", "posting_dow", "posting_hour"],
}
CATS = ["status", "sector", "activity", "country_name", "gender",
        "repaymentInterval", "week_id"]
BOOLS = ["analysis_washin_eligible", "raw_text_nonempty", "residual_text_nonempty"]
DERIVED = {"Cz", "Hz", "Vz", "Gz", "CH", "VG",
           "Cz_res", "Hz_res", "Vz_res", "Gz_res", "CH_res", "VG_res"}

BASE_COLS = sorted(({c for g in GROUPS.values() for c in g} - DERIVED)
                   | set(CATS) | set(BOOLS) | {"id"})

log("载入 …")
df = pd.read_parquet(OUT / "data" / "model_data.parquet", columns=BASE_COLS)
log(f"rows={len(df):,} cols={df.shape[1]}")

sc = pd.read_csv(OUT / "outputs" / "scaler_parameters.csv")
for spec, suffix in [("active_raw", ""), ("active_residual", "_res")]:
    p = {r.variable: r for r in sc[sc.specification == spec].itertuples(index=False)}
    for v in ("C", "H", "V", "G"):
        df[f"{v}z{suffix}"] = ((df[p[v].source_column] - p[v].mean) / p[v].std).astype("float32")
    df[f"CH{suffix}"] = (df[f"Cz{suffix}"] * df[f"Hz{suffix}"]).astype("float32")
    df[f"VG{suffix}"] = (df[f"Vz{suffix}"] * df[f"Gz{suffix}"]).astype("float32")

MAIN = (df["analysis_washin_eligible"] & df["raw_text_nonempty"]
        & (df["pool_size_active"] >= 10) & (df["lag_kish_n"] >= 10)
        & df["fundraising_year"].between(2016, 2024))
log(f"主样本（训练期）= {int(MAIN.sum()):,}")
d = df.loc[MAIN]

VAR2GROUP = {v: g for g, vs in GROUPS.items() for v in vs}
ALLNUM = [v for g in GROUPS.values() for v in g if v in d.columns]

# ---------------------------------------------------------------- M1 变量目录
log("M1 变量目录")
rows = []
for v in ALLNUM:
    s = pd.to_numeric(d[v], errors="coerce")
    nn = s.dropna()
    if nn.empty:
        continue
    vc = nn.value_counts()
    q = nn.quantile([.01, .05, .25, .5, .75, .95, .99])
    nuniq = int(nn.nunique())
    top10 = float(vc.iloc[:10].sum() / len(nn))
    rows.append({
        "group": VAR2GROUP[v], "variable": v,
        "n": int(len(nn)), "pct_missing": round(100 * float(s.isna().mean()), 4),
        "n_unique": nuniq,
        "discreteness": "离散" if nuniq <= 60 else ("准离散" if top10 > .25 else "连续"),
        "min": float(nn.min()), "p01": float(q.loc[.01]), "p25": float(q.loc[.25]),
        "p50": float(q.loc[.5]), "p75": float(q.loc[.75]), "p95": float(q.loc[.95]),
        "p99": float(q.loc[.99]), "max": float(nn.max()),
        "mean": float(nn.mean()), "std": float(nn.std()),
        "iqr": float(q.loc[.75] - q.loc[.25]),
        "skew": float(nn.skew()), "kurtosis": float(nn.kurtosis()),
        "mean_over_median": float(nn.mean() / q.loc[.5]) if q.loc[.5] else np.nan,
        "p99_over_p50": float(q.loc[.99] / q.loc[.5]) if q.loc[.5] else np.nan,
        "pct_zero": round(100 * float((nn == 0).mean()), 4),
        "pct_negative": round(100 * float((nn < 0).mean()), 4),
        "mode_value": float(vc.index[0]), "mode_pct": round(100 * int(vc.iloc[0]) / len(nn), 3),
        "top10_values_pct": round(100 * top10, 2),
    })
pd.DataFrame(rows).to_csv(TAB / "M1_variable_catalog.csv", index=False)
log(f"  -> M1 ({len(rows)} 个变量)")

# ---------------------------------------------------------------- M2 直方图
log("M2 直方图")
hrows = []
for v in ALLNUM:
    nn = pd.to_numeric(d[v], errors="coerce").dropna()
    if nn.empty:
        continue
    lo, hi = float(nn.quantile(.001)), float(nn.quantile(.999))
    if hi <= lo:
        lo, hi = float(nn.min()), float(nn.max())
    if hi <= lo:
        continue
    cnt, edge = np.histogram(nn.clip(lo, hi), bins=40, range=(lo, hi))
    for i in range(40):
        hrows.append({"variable": v, "group": VAR2GROUP[v], "bin": i,
                      "left": float(edge[i]), "right": float(edge[i + 1]),
                      "count": int(cnt[i]), "share_pct": round(100 * cnt[i] / len(nn), 4)})
pd.DataFrame(hrows).to_csv(TAB / "M2_histograms.csv", index=False)
log("  -> M2")

# ---------------------------------------------------------------- M3/M4 堆积与边界
log("M3 取值堆积 / M4 相似度边界")
srows = []
for v in ALLNUM:
    nn = pd.to_numeric(d[v], errors="coerce").dropna()
    if nn.empty:
        continue
    for rank, (val, n) in enumerate(nn.value_counts().head(8).items(), 1):
        if n / len(nn) < 0.001 and rank > 3:
            continue
        srows.append({"group": VAR2GROUP[v], "variable": v, "rank": rank,
                      "value": float(val), "n": int(n),
                      "share_pct": round(100 * n / len(nn), 4)})
pd.DataFrame(srows).to_csv(TAB / "M3_value_spikes.csv", index=False)

brows = []
for v in GROUPS["相似度 H/G"]:
    nn = pd.to_numeric(d[v], errors="coerce").dropna()
    if nn.empty:
        continue
    brows.append({"variable": v, "n": int(len(nn)),
                  "pct_eq_0": round(100 * float((nn == 0).mean()), 5),
                  "pct_lt_001": round(100 * float((nn < .01).mean()), 3),
                  "pct_lt_005": round(100 * float((nn < .05).mean()), 3),
                  "pct_gt_05": round(100 * float((nn > .5).mean()), 3),
                  "pct_gt_09": round(100 * float((nn > .9).mean()), 4),
                  "pct_eq_1": round(100 * float((nn == 1.0).mean()), 5),
                  "max": float(nn.max())})
pd.DataFrame(brows).to_csv(TAB / "M4_similarity_bounds.csv", index=False)
log("  -> M3 / M4")

# ---------------------------------------------------------------- M5 逐年中位数
log("M5 逐年中位数")
yrows = []
dy = df.loc[df["analysis_washin_eligible"] & df["raw_text_nonempty"]
            & (df["pool_size_active"] >= 10) & (df["lag_kish_n"] >= 10)]
for v in ALLNUM:
    med = dy.groupby("fundraising_year", observed=True)[v].median()
    if med.isna().all():
        continue
    early = med.reindex(range(2016, 2020)).dropna()
    late = med.reindex(range(2020, 2025)).dropna()
    e = float(early.median()) if len(early) else np.nan
    l = float(late.median()) if len(late) else np.nan
    row = {"group": VAR2GROUP[v], "variable": v,
           "med_2016_2019": e, "med_2020_2024": l,
           "ratio_late_over_early": round(l / e, 3) if e else np.nan,
           "med_2025": float(med.loc[2025]) if 2025 in med.index else np.nan}
    for y in range(2016, 2026):
        row[f"y{y}"] = float(med.loc[y]) if y in med.index else np.nan
    yrows.append(row)
pd.DataFrame(yrows).to_csv(TAB / "M5_by_year_median.csv", index=False)
log("  -> M5")

# ---------------------------------------------------------------- M6/M7 类别
log("M6 / M7 类别与布尔变量")
crows = []
for c in CATS:
    s = d[c].astype("string")
    vc = s.value_counts(dropna=False)
    share = vc / vc.sum()
    crows.append({"variable": c, "n": int(len(s)), "n_levels": int(vc.size),
                  "pct_missing": round(100 * float(s.isna().mean()), 4),
                  "top1_level": str(vc.index[0]), "top1_pct": round(100 * float(share.iloc[0]), 3),
                  "top3_pct": round(100 * float(share.iloc[:3].sum()), 3),
                  "top10_pct": round(100 * float(share.iloc[:10].sum()), 3),
                  "hhi": round(float((share ** 2).sum()), 4),
                  "levels_for_90pct": int((share.cumsum() <= .90).sum() + 1)})
for c in BOOLS:
    s = df[c]
    crows.append({"variable": c, "n": int(len(s)), "n_levels": 2, "pct_missing": 0.0,
                  "top1_level": "True", "top1_pct": round(100 * float(s.mean()), 3),
                  "top3_pct": 100.0, "top10_pct": 100.0, "hhi": np.nan, "levels_for_90pct": 1})
pd.DataFrame(crows).to_csv(TAB / "M6_categorical_profile.csv", index=False)

lrows = []
for c in CATS:
    for rank, (lvl, n) in enumerate(d[c].astype("string").value_counts(dropna=False).head(20).items(), 1):
        lrows.append({"variable": c, "rank": rank, "level": str(lvl), "n": int(n),
                      "share_pct": round(100 * n / len(d), 3)})
pd.DataFrame(lrows).to_csv(TAB / "M7_categorical_levels.csv", index=False)
log("  -> M6 / M7")

# ---------------------------------------------------------------- M8 上架节律
log("M8 上架时点节律")
parts = []
for col, axis in [("posting_dow", "posting_dow"), ("posting_hour", "posting_hour")]:
    g = (d.groupby(col, observed=True)
         .agg(n=("funding_hours", "size"), median_fh=("funding_hours", "median"))
         .reset_index().rename(columns={col: "value"}))
    g["axis"] = axis
    g["share_pct"] = (100 * g["n"] / g["n"].sum()).round(3)
    parts.append(g)
pd.concat(parts, ignore_index=True)[["axis", "value", "n", "share_pct", "median_fh"]] \
    .to_csv(TAB / "M8_posting_rhythm.csv", index=False)
log("  -> M8")

# ---------------------------------------------------------------- M9 结果变量精细
log("M9 结果变量精细形态")
fh = d["funding_hours"]
fine = []
for lo, hi, lab in [(0, .5, "<0.5h"), (.5, 1, "0.5-1h"), (1, 3, "1-3h"), (3, 6, "3-6h"),
                    (6, 12, "6-12h"), (12, 24, "12-24h"), (24, 48, "1-2d"), (48, 72, "2-3d"),
                    (72, 168, "3-7d"), (168, 336, "7-14d"), (336, 504, "14-21d"),
                    (504, 600, "21-25d"), (600, 672, "25-28d"), (672, 720, "28-30d"),
                    (720, 768, "30-32d"), (768, 840, "32-35d"), (840, 1000, "35-42d"),
                    (1000, 1e9, ">42d")]:
    m = (fh >= lo) & (fh < hi)
    fine.append({"band": lab, "lo_h": lo, "hi_h": hi, "n": int(m.sum()),
                 "share_pct": round(100 * float(m.mean()), 3)})
fdf = pd.DataFrame(fine)
fdf["cum_pct"] = fdf["share_pct"].cumsum().round(3)
fdf.to_csv(TAB / "M9_outcome_fine_bands.csv", index=False)

json.dump({"elapsed_s": round(time.time() - T0, 1), "n_numeric_vars": len(ALLNUM),
           "n_cat_vars": len(CATS) + len(BOOLS), "main_sample": int(MAIN.sum())},
          open(ROOT / "4_中间产物" / "EDA" / "dist_manifest.json", "w"), indent=2)
log("完成")
