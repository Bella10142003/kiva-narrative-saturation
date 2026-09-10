#!/usr/bin/env python3
"""G 的负号能不能读成「模仿近期范式能加快筹款」？三个检验。

T1 偏效应 vs 总效应：G 单独放进模型（不控制 H/C）是什么符号？
    ——业务建议是「去模仿」，那是沿着 G 与 H 的联合分布移动，
      对应总导数，不是控制住 H 的偏导数。
T2 「近期同行队列本身有多好募」作为混淆：
    按 sector×day 重建 [35,65) 天前同行队列的真实募资速度（7 天半衰期加权，
    这些贷款在焦点上架前已结束，不构成前视），加入模型后 G 还剩多少。
T3 规格稳健性：G 在挂牌池规格下还显著吗（子群稳定 ≠ 规格稳健）。
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
VC = {"CRV1": "country_name + week_id"}
GAP, SPAN, HALF = 35, 30, 7.0          # 与 05 号 notebook 的滞后池定义一致


def log(m: str) -> None:
    print(f"[{time.time()-T0:6.1f}s] {m}", flush=True)


cols = (["log_funding_hours", "funded_within_72h", "eligible_72h_followup",
         "fundraising_ts", "fundraising_year", "sector",
         "analysis_washin_eligible", "raw_text_nonempty",
         "pool_size_active", "pool_size_14d", "lag_kish_n",
         "C_active", "H_active_raw", "C_14d", "H_14d_raw",
         "V_lag", "G_lag_raw", "country_name", "activity", "week_id",
         "gender", "repaymentInterval", "posting_dow", "posting_hour"] + CTRL)
log("载入 …")
d = pd.read_parquet(OUT / "data" / "model_data.parquet", columns=cols)
sc = pd.read_csv(OUT / "outputs" / "scaler_parameters.csv")


def zmap(spec: str) -> dict[str, str]:
    p = {r.variable: r for r in sc[sc.specification == spec].itertuples(index=False)}
    m = {}
    for v in ("C", "H", "V", "G"):
        c = f"{spec}_{v}z"
        d[c] = ((d[p[v].source_column] - p[v].mean) / p[v].std).astype("float32")
        m[v] = c
    d[f"{spec}_CH"] = (d[m["C"]] * d[m["H"]]).astype("float32")
    d[f"{spec}_VG"] = (d[m["V"]] * d[m["G"]]).astype("float32")
    m["CH"], m["VG"] = f"{spec}_CH", f"{spec}_VG"
    return m


MA, M14 = zmap("active_raw"), zmap("posting_14d_raw")

# ---------------------------------------------------------------- 近期同行队列的实际表现
log("重建 sector×day 的「近期同行队列实际募资速度」")
d["day"] = d["fundraising_ts"].dt.floor("D")
day0 = d["day"].min()
d["di"] = ((d["day"] - day0).dt.days).astype("int32")
ND = int(d["di"].max()) + 1
sectors = d["sector"].astype("category")
d["si"] = sectors.cat.codes.astype("int16")
NS = len(sectors.cat.categories)

# 每个 sector×day 的：笔数、log 时长之和、72h 成功数、72h 合格数
cnt = np.zeros((NS, ND)); s_lfh = np.zeros((NS, ND))
s_f72 = np.zeros((NS, ND)); n_f72 = np.zeros((NS, ND))
np.add.at(cnt, (d["si"].to_numpy(), d["di"].to_numpy()), 1.0)
np.add.at(s_lfh, (d["si"].to_numpy(), d["di"].to_numpy()),
          d["log_funding_hours"].to_numpy())
e72 = d["eligible_72h_followup"].to_numpy() == 1
np.add.at(n_f72, (d.loc[e72, "si"].to_numpy(), d.loc[e72, "di"].to_numpy()), 1.0)
np.add.at(s_f72, (d.loc[e72, "si"].to_numpy(), d.loc[e72, "di"].to_numpy()),
          d.loc[e72, "funded_within_72h"].to_numpy().astype(float))

# 核：年龄 a ∈ [GAP, GAP+SPAN) 的日子，权重 0.5^((a-GAP)/HALF)
ages = np.arange(GAP, GAP + SPAN)
kern = 0.5 ** ((ages - GAP) / HALF)


def conv(mat: np.ndarray) -> np.ndarray:
    """out[s,t] = Σ_a kern[a] * mat[s, t-a]"""
    o = np.zeros_like(mat)
    for a, w in zip(ages, kern):
        o[:, a:] += w * mat[:, :-a]
    return o


w_cnt, w_lfh = conv(cnt), conv(s_lfh)
w_n72, w_s72 = conv(n_f72), conv(s_f72)
with np.errstate(invalid="ignore", divide="ignore"):
    lag_speed = np.where(w_cnt > 0, w_lfh / w_cnt, np.nan)     # 队列平均 log 时长
    lag_r72 = np.where(w_n72 > 0, w_s72 / w_n72, np.nan)       # 队列 72h 达成率
si, di = d["si"].to_numpy(), d["di"].to_numpy()
d["lag_cohort_logfh"] = lag_speed[si, di]
d["lag_cohort_r72"] = lag_r72[si, di]
d["lag_cohort_logn"] = np.log1p(w_cnt[si, di])
log(f"  队列速度缺失率 {100*d['lag_cohort_logfh'].isna().mean():.3f}%")

for c in FE:
    d[c] = d[c].astype("category")
base = (d.analysis_washin_eligible & d.raw_text_nonempty
        & (d.lag_kish_n >= 10) & d.fundraising_year.between(2016, 2024))
S = base & (d.pool_size_active >= 10)
S14 = base & (d.pool_size_14d >= 10)
log(f"主样本 {int(S.sum()):,}")

print("\n  近期同行队列速度 与 G 的相关（主样本）:",
      round(float(d.loc[S, "lag_cohort_logfh"].corr(d.loc[S, MA['G']])), 4))
print("  近期同行队列速度 与 结果 的相关:",
      round(float(d.loc[S, "lag_cohort_logfh"].corr(d.loc[S, "log_funding_hours"])), 4))


def run(tag, regs, mask, extra=()):
    f = ("log_funding_hours ~ " + " + ".join(list(regs) + CTRL + list(extra))
         + " | " + " + ".join(FE))
    frame = d.loc[mask].dropna(subset=list(extra)) if extra else d.loc[mask]
    fit = pf.feols(f, frame, vcov=VC, copy_data=False, store_data=False,
                   lean=True, fixef_rm="singleton")
    t = fit.tidy().reset_index()
    t.columns = ["coef"] + list(t.columns[1:])
    rows = []
    for r in t.itertuples(index=False):
        rows.append({"spec": tag, "n": int(getattr(fit, "_N", 0)), "term": r.coef,
                     "estimate": float(r.Estimate), "se": float(r._2),
                     "p": float(r._4)})
    print(f"\n{tag}   n={int(getattr(fit,'_N',0)):,}")
    for r in rows:
        if r["term"] in list(regs) + list(extra):
            st = "***" if r["p"] < .01 else ("**" if r["p"] < .05 else
                                             ("*" if r["p"] < .1 else "   "))
            print(f"   {r['term']:<28} {r['estimate']:+.4f}  se {r['se']:.4f}"
                  f"  p {r['p']:.4f} {st}")
    return rows


all_rows = []
print("\n" + "=" * 72)
print("T1  偏效应 vs 总效应：G 在不同控制集下的符号")
all_rows += run("T1a 完整主模型（控制 C,H,V）",
                [MA[k] for k in ("C", "H", "CH", "V", "G", "VG")], S)
all_rows += run("T1b 只放 G（不控制 H/C/V）", [MA["G"]], S)
all_rows += run("T1c 放 G 与 V（不控制当前通道）", [MA["V"], MA["G"], MA["VG"]], S)
all_rows += run("T1d 放 G 与 H（叙事维度的总效应）", [MA["H"], MA["G"]], S)

print("\n" + "=" * 72)
print("T2  控制「近期同行队列实际有多好募」之后，G 还剩多少")
all_rows += run("T2a 主模型 + 队列速度",
                [MA[k] for k in ("C", "H", "CH", "V", "G", "VG")], S,
                extra=("lag_cohort_logfh",))
all_rows += run("T2b 主模型 + 队列速度 + 队列72h率 + 队列规模",
                [MA[k] for k in ("C", "H", "CH", "V", "G", "VG")], S,
                extra=("lag_cohort_logfh", "lag_cohort_r72", "lag_cohort_logn"))

print("\n" + "=" * 72)
print("T3  规格稳健性：G 在挂牌池规格下")
all_rows += run("T3a 14天规格 · 主样本",
                [M14[k] for k in ("C", "H", "CH", "V", "G", "VG")], S)
all_rows += run("T3b 14天规格 · 14天样本",
                [M14[k] for k in ("C", "H", "CH", "V", "G", "VG")], S14)

pd.DataFrame(all_rows).to_csv(TAB / "Q1_G_causal_probe.csv", index=False)

print("\n" + "=" * 72)
print("T4  «模仿» 会同时抬高 G 和 H —— 两者在格子内的相关与系数比")
sub = d.loc[S, [MA["H"], MA["G"], "log_funding_hours"]].astype("float64")
print(f"   H 与 G 的原始相关: {sub[MA['H']].corr(sub[MA['G']]):.4f}")
g = [r for r in all_rows if r["spec"].startswith("T1a")]
bH = [r for r in g if r["term"] == MA["H"]][0]["estimate"]
bG = [r for r in g if r["term"] == MA["G"]][0]["estimate"]
print(f"   βH = {bH:+.4f}   βG = {bG:+.4f}   |βH/βG| = {abs(bH/bG):.2f}")
print(f"   若模仿使 G 与 H 各 +1 SD：净 = {bH+bG:+.4f} log 点 "
      f"→ 筹款时长 ×{np.exp(bH+bG):.3f}（{100*(np.exp(bH+bG)-1):+.1f}%）")
log("完成 -> Q1_G_causal_probe.csv")
