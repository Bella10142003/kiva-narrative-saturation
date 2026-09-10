#!/usr/bin/env python3
"""「相似度稀有 => 叙事饱和/疲劳没意义吗」的针对性检验。

四问：
 Q1 H 的低水平是不是度量本身造成的（池越大均值向量越发散）？
 Q2 信号住在分布的哪一段？只在稀有的高尾，还是全程都有？
 Q3 高相似度那批的绝对规模与代价有多大？值不值得干预？
 Q4 疲劳通道（G/VG）的「没信号」，是被大片无关区间稀释了，
    还是即使只看高 G 的那批也确实没有？
"""
from __future__ import annotations

import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "4_中间产物" / "我算出来的结果"
TAB = ROOT / "4_中间产物" / "EDA" / "tables"
T0 = time.time()


def log(m: str) -> None:
    print(f"[{time.time()-T0:6.1f}s] {m}", flush=True)


COLS = ["funding_hours", "log_funding_hours", "fundraising_year",
        "analysis_washin_eligible", "raw_text_nonempty",
        "pool_size_active", "lag_kish_n", "lag_pool_raw_count",
        "C_active", "H_active_raw", "V_lag", "G_lag_raw",
        "country_name", "activity", "week_id", "sector",
        "log_loan_amount", "log_borrower_count", "log_repayment_term",
        "log_platform_posting_7d", "eligible_72h_followup", "funded_within_72h"]
log("载入 …")
df = pd.read_parquet(OUT / "data" / "model_data.parquet", columns=COLS)
sc = pd.read_csv(OUT / "outputs" / "scaler_parameters.csv")
p = {r.variable: r for r in sc[sc.specification == "active_raw"].itertuples(index=False)}
for v, src in [("C", "C_active"), ("H", "H_active_raw"), ("V", "V_lag"), ("G", "G_lag_raw")]:
    df[v + "z"] = (df[src] - p[v].mean) / p[v].std
df["CH"] = df["Cz"] * df["Hz"]
df["VG"] = df["Vz"] * df["Gz"]

tr = (df.analysis_washin_eligible & df.raw_text_nonempty
      & (df.pool_size_active >= 10) & (df.lag_kish_n >= 10)
      & df.fundraising_year.between(2016, 2024))
d = df.loc[tr].copy()
log(f"训练期主样本 {len(d):,}")

# ---------------------------------------------------------------- 三重固定效应去均值
DM = ["log_funding_hours", "Cz", "Hz", "CH", "Vz", "Gz", "VG",
      "log_loan_amount", "log_borrower_count", "log_repayment_term",
      "log_platform_posting_7d"]
Y = d[DM].to_numpy(dtype="float64")
keys = [d[c].astype("category").cat.codes.to_numpy()
        for c in ("country_name", "activity", "week_id")]
cnts = [np.bincount(k) for k in keys]
for it in range(60):
    delta = 0.0
    for k, c in zip(keys, cnts):
        s = np.zeros((c.size, Y.shape[1]))
        np.add.at(s, k, Y)
        step = (s / c[:, None])[k]
        delta = max(delta, float(np.abs(step).max()))
        Y -= step
    if delta < 1e-8:
        break
for i, c in enumerate(DM):
    d["dm_" + c] = Y[:, i]
log(f"去均值收敛 iter={it+1}")

REG = ["dm_Cz", "dm_Hz", "dm_CH", "dm_Vz", "dm_Gz", "dm_VG",
       "dm_log_loan_amount", "dm_log_borrower_count",
       "dm_log_repayment_term", "dm_log_platform_posting_7d"]


def ols(frame: pd.DataFrame, regs: list[str], y: str) -> dict:
    f = frame[regs + [y]].dropna()
    if len(f) < 500:
        return {}
    X = np.column_stack([np.ones(len(f)), f[regs].to_numpy()])
    yy = f[y].to_numpy()
    b, *_ = np.linalg.lstsq(X, yy, rcond=None)
    r = yy - X @ b
    # 简易稳健标准误
    XtXi = np.linalg.pinv(X.T @ X)
    meat = (X * (r ** 2)[:, None]).T @ X
    se = np.sqrt(np.diag(XtXi @ meat @ XtXi))
    out = {"n": int(len(f)), "r2": float(1 - r.var() / yy.var())}
    for name, bb, ss in zip(["const"] + regs, b, se):
        out["b_" + name] = float(bb)
        out["se_" + name] = float(ss)
    return out


# ================================================================ Q1 度量伪影
log("Q1  H 的水平是不是池规模造成的")
q1 = []
d["pool_dec"] = pd.qcut(d["pool_size_active"], 10, labels=False)
for k, g in d.groupby("pool_dec", observed=True):
    q1.append({"pool_decile": int(k), "n": len(g),
               "median_pool_size": float(g["pool_size_active"].median()),
               "mean_H": float(g["H_active_raw"].mean()),
               "median_H": float(g["H_active_raw"].median()),
               "p95_H": float(g["H_active_raw"].quantile(.95)),
               "pct_H_gt_05": round(100 * float((g["H_active_raw"] > .5).mean()), 3)})
q1 = pd.DataFrame(q1)
q1.to_csv(TAB / "P1_H_vs_pool_size.csv", index=False)
print(q1.round(4).to_string(index=False))
print(f"\n  H 与 log 池规模的相关: {d['H_active_raw'].corr(d['C_active']):.4f}"
      f"  (Spearman {d[['H_active_raw','C_active']].sample(300000, random_state=1).corr(method='spearman').iloc[0,1]:.4f})")

# ================================================================ Q2 信号住在哪一段
log("Q2  信号住在 H / G 分布的哪一段")
bands = [(0, 10), (10, 25), (25, 50), (50, 75), (75, 90),
         (90, 95), (95, 99), (99, 100)]
q2 = []
for var, lab in [("H_active_raw", "H"), ("G_lag_raw", "G")]:
    pr = d[var].rank(pct=True) * 100
    for lo, hi in bands:
        m = (pr > lo) & (pr <= hi) if lo > 0 else (pr <= hi)
        g = d.loc[m]
        if len(g) < 500:
            continue
        q2.append({
            "variable": lab, "band": f"p{lo}-p{hi}", "n": int(len(g)),
            "share_pct": round(100 * len(g) / len(d), 2),
            f"{lab}_lo": float(g[var].min()), f"{lab}_hi": float(g[var].max()),
            "mean_dm_outcome": float(g["dm_log_funding_hours"].mean()),
            "median_funding_hours": float(g["funding_hours"].median()),
            "pct_funded_72h": round(100 * float(
                g.loc[g.eligible_72h_followup == 1, "funded_within_72h"].mean()), 2),
        })
q2 = pd.DataFrame(q2)
q2.to_csv(TAB / "P2_signal_by_band.csv", index=False)
for lab in ("H", "G"):
    print(f"\n--- {lab} ---")
    print(q2[q2.variable == lab].round(4).to_string(index=False))

# ================================================================ Q3 规模与代价
log("Q3  高相似度那批的规模与代价")
base_med = float(d["funding_hours"].median())
q3 = []
for thr, lab in [(0.5, "H>0.5"), (0.4, "H>0.4"), (0.3, "H>0.3"), (0.2, "H>0.2"),
                 (float(d["H_active_raw"].quantile(.90)), "H>p90"),
                 (float(d["H_active_raw"].quantile(.75)), "H>p75")]:
    m = d["H_active_raw"] > thr
    g = d.loc[m]
    q3.append({"cut": lab, "threshold": round(thr, 4), "n": int(m.sum()),
               "share_pct": round(100 * float(m.mean()), 3),
               "median_funding_hours": float(g["funding_hours"].median()),
               "mean_dm_outcome": float(g["dm_log_funding_hours"].mean()),
               "vs_全样本_dm": float(g["dm_log_funding_hours"].mean()
                                     - d["dm_log_funding_hours"].mean()),
               "pct_funded_72h": round(100 * float(
                   g.loc[g.eligible_72h_followup == 1, "funded_within_72h"].mean()), 2),
               "总募资小时占比": round(100 * float(g["funding_hours"].sum()
                                                  / d["funding_hours"].sum()), 3)})
q3 = pd.DataFrame(q3)
q3.to_csv(TAB / "P3_high_similarity_scale.csv", index=False)
print(q3.round(4).to_string(index=False))
print(f"\n  全样本中位募资时长 = {base_med:.1f}h；72h 达成率 = "
      f"{100*d.loc[d.eligible_72h_followup==1,'funded_within_72h'].mean():.2f}%")

# ================================================================ Q4 疲劳通道分段检验
log("Q4  疲劳通道：只看高 G 的那批，有没有信号")
q4 = []
gpr = d["G_lag_raw"].rank(pct=True) * 100
for lo, hi in [(0, 50), (50, 75), (75, 90), (90, 95), (95, 99), (99, 100),
               (90, 100), (0, 100)]:
    m = (gpr > lo) & (gpr <= hi) if lo > 0 else (gpr <= hi)
    r = ols(d.loc[m], REG, "dm_log_funding_hours")
    if not r:
        continue
    r.update({"band": f"G p{lo}-p{hi}", "share_pct": round(100 * float(m.mean()), 2),
              "G_lo": float(d.loc[m, "G_lag_raw"].min()),
              "G_hi": float(d.loc[m, "G_lag_raw"].max())})
    q4.append(r)
q4 = pd.DataFrame(q4)
keep = ["band", "n", "share_pct", "G_lo", "G_hi", "r2",
        "b_dm_Gz", "se_dm_Gz", "b_dm_VG", "se_dm_VG", "b_dm_Hz", "se_dm_Hz",
        "b_dm_CH", "se_dm_CH"]
q4[keep].to_csv(TAB / "P4_fatigue_by_G_band.csv", index=False)
q4d = q4[keep].copy()
q4d["t_Gz"] = (q4d.b_dm_Gz / q4d.se_dm_Gz).round(2)
q4d["t_VG"] = (q4d.b_dm_VG / q4d.se_dm_VG).round(2)
q4d["t_CH"] = (q4d.b_dm_CH / q4d.se_dm_CH).round(2)
print(q4d[["band", "n", "share_pct", "G_lo", "G_hi",
           "b_dm_Gz", "t_Gz", "b_dm_VG", "t_VG", "b_dm_CH", "t_CH"]]
      .round(4).to_string(index=False))

# 对照：同样分段但按 H 切，看饱和通道是不是也只在高段
log("Q4b 对照：按 H 分段看饱和通道")
q5 = []
hpr = d["H_active_raw"].rank(pct=True) * 100
for lo, hi in [(0, 50), (50, 75), (75, 90), (90, 95), (95, 99), (99, 100),
               (90, 100), (0, 100)]:
    m = (hpr > lo) & (hpr <= hi) if lo > 0 else (hpr <= hi)
    r = ols(d.loc[m], REG, "dm_log_funding_hours")
    if not r:
        continue
    r.update({"band": f"H p{lo}-p{hi}", "share_pct": round(100 * float(m.mean()), 2),
              "H_lo": float(d.loc[m, "H_active_raw"].min()),
              "H_hi": float(d.loc[m, "H_active_raw"].max())})
    q5.append(r)
q5 = pd.DataFrame(q5)
keep2 = ["band", "n", "share_pct", "H_lo", "H_hi", "r2",
         "b_dm_Hz", "se_dm_Hz", "b_dm_CH", "se_dm_CH", "b_dm_Gz", "se_dm_Gz"]
q5[keep2].to_csv(TAB / "P5_saturation_by_H_band.csv", index=False)
q5d = q5[keep2].copy()
q5d["t_Hz"] = (q5d.b_dm_Hz / q5d.se_dm_Hz).round(2)
q5d["t_CH"] = (q5d.b_dm_CH / q5d.se_dm_CH).round(2)
print(q5d[["band", "n", "share_pct", "H_lo", "H_hi", "b_dm_Hz", "t_Hz",
           "b_dm_CH", "t_CH"]].round(4).to_string(index=False))

log("完成 -> P1..P5")
