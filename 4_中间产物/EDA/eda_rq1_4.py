#!/usr/bin/env python3
"""RQ1-RQ4 探索性数据分析 (EDA)

只读 4_中间产物/我算出来的结果/data/model_data.parquet，
输出全部写入 4_中间产物/EDA/{tables,figures}，不触碰任何既有交付物。

变量口径与 06/07 号 notebook 完全一致：
  z 标准化用 outputs/scaler_parameters.csv（2016-2024 训练期拟合），
  先标准化再造交互项 CH = Cz*Hz, VG = Vz*Gz。
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "4_中间产物" / "我算出来的结果"
EDA = ROOT / "4_中间产物" / "EDA"
TAB = EDA / "tables"
FIG = EDA / "figures"
for d in (TAB, FIG):
    d.mkdir(parents=True, exist_ok=True)

T0 = time.time()
LOG = EDA / "eda_run.log"
LOG.write_text("", encoding="utf-8")


def log(msg: str) -> None:
    line = f"[{time.time() - T0:7.1f}s] {msg}"
    print(line, flush=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def save(frame: pd.DataFrame, name: str) -> None:
    frame.to_csv(TAB / f"{name}.csv", index=False)
    log(f"  -> tables/{name}.csv  ({len(frame)} rows)")


# ----------------------------------------------------------------------------
# 0. 载入
# ----------------------------------------------------------------------------
COLS = [
    "id", "status", "gender", "repaymentInterval", "sector", "activity",
    "country_name", "country_ppp", "fundraising_year", "week_id",
    "posting_dow", "posting_hour",
    "funding_hours", "log_funding_hours",
    "eligible_72h_followup", "funded_within_72h", "eligible_35d_followup",
    "analysis_washin_eligible", "raw_text_nonempty", "residual_text_nonempty",
    "boilerplate_share",
    "pool_size_active", "C_active", "H_active_raw", "H_active_residual",
    "pool_size_14d", "C_14d", "H_14d_raw",
    "pool_size_16d", "C_16d", "H_16d_raw",
    "lag_pool_raw_count", "lag_weight", "V_lag", "lag_kish_n",
    "G_lag_raw", "G_lag_residual",
    "V_lag_completed", "lag_completed_kish_n", "G_lag_completed_raw",
    "log_loan_amount", "log_borrower_count", "log_repayment_term",
    "log_platform_posting_7d", "loanAmount", "borrowerCount",
]
log("载入 model_data.parquet ...")
df = pd.read_parquet(OUT / "data" / "model_data.parquet", columns=COLS)
log(f"rows={len(df):,}  cols={df.shape[1]}  mem={df.memory_usage(deep=False).sum()/2**30:.2f} GiB")

# ----------------------------------------------------------------------------
# 1. 衍生变量：z 标准化 + 交互项（口径同 07）
# ----------------------------------------------------------------------------
sc = pd.read_csv(OUT / "outputs" / "scaler_parameters.csv")
scalers: dict[str, dict[str, dict]] = {}
for r in sc.itertuples(index=False):
    scalers.setdefault(r.specification, {})[r.variable] = {
        "col": r.source_column, "mean": float(r.mean), "std": float(r.std),
        "p25": float(r.p25), "p50": float(r.p50), "p75": float(r.p75),
    }

MAPS: dict[str, dict[str, str]] = {}
for spec, vs in scalers.items():
    m = {}
    for v in ("C", "H", "V", "G"):
        p = vs[v]
        zc = f"{spec}_{v}z"
        df[zc] = ((df[p["col"]].astype("float64") - p["mean"]) / p["std"]).astype("float32")
        m[v] = zc
    df[f"{spec}_CH"] = (df[m["C"]] * df[m["H"]]).astype("float32")
    df[f"{spec}_VG"] = (df[m["V"]] * df[m["G"]]).astype("float32")
    m["CH"], m["VG"] = f"{spec}_CH", f"{spec}_VG"
    MAPS[spec] = m
log(f"已构造 {len(MAPS)} 套 z 标准化 + 交互项：{list(MAPS)}")

SPEC = "active_raw"          # 主口径
M = MAPS[SPEC]
FOCAL = [M[k] for k in ("C", "H", "CH", "V", "G", "VG")]
CTRL = ["log_loan_amount", "log_borrower_count", "log_repayment_term", "log_platform_posting_7d"]

# ----------------------------------------------------------------------------
# 2. 分析样本掩码（口径同 07）
# ----------------------------------------------------------------------------
base = (
    df["analysis_washin_eligible"]
    & df["raw_text_nonempty"]
    & (df["pool_size_active"] >= 10)
    & (df["lag_kish_n"] >= 10)
)
train = base & df["fundraising_year"].between(2016, 2024)
hold = base & (df["fundraising_year"] == 2025)
resid_train = (
    df["analysis_washin_eligible"] & df["residual_text_nonempty"]
    & (df["pool_size_active"] >= 10) & (df["lag_kish_n"] >= 10)
    & df["fundraising_year"].between(2016, 2024)
)
df["_train"] = train
log(f"train={train.sum():,}  holdout2025={hold.sum():,}  residual_train={resid_train.sum():,}")

# ============================================================================
# A. 样本流与覆盖
# ============================================================================
log("A. 样本流与覆盖")
steps = [
    ("00 全部有效时长行", pd.Series(True, index=df.index)),
    ("01 wash-in 合格", df["analysis_washin_eligible"]),
    ("02 + use 文本非空", df["analysis_washin_eligible"] & df["raw_text_nonempty"]),
    ("03 + 主动池 n>=10", df["analysis_washin_eligible"] & df["raw_text_nonempty"] & (df["pool_size_active"] >= 10)),
    ("04 + 滞后 Kish n>=10 (=主样本)", base),
]
rows = []
prev = None
for name, mask in steps:
    n = int(mask.sum())
    rows.append({
        "step": name, "loans": n,
        "share_of_all": round(100 * n / len(df), 3),
        "dropped_vs_prev": 0 if prev is None else prev - n,
        "train_2016_2024": int((mask & df["fundraising_year"].between(2016, 2024)).sum()),
        "holdout_2025": int((mask & (df["fundraising_year"] == 2025)).sum()),
    })
    prev = n
save(pd.DataFrame(rows), "A1_sample_flow")

yr = (
    df.assign(in_main=base.astype(int))
    .groupby("fundraising_year", observed=True)
    .agg(loans_all=("id", "size"), loans_main=("in_main", "sum"),
         median_funding_hours=("funding_hours", "median"),
         mean_log_fh=("log_funding_hours", "mean"),
         median_pool_active=("pool_size_active", "median"),
         median_lag_kish=("lag_kish_n", "median"))
    .reset_index()
)
yr["retention_pct"] = (100 * yr["loans_main"] / yr["loans_all"]).round(2)
save(yr, "A2_by_year_coverage")

# 关键变量缺失率（主样本内）
miss = []
for c in FOCAL + CTRL + ["log_funding_hours", "funding_hours", "boilerplate_share",
                         "H_active_residual", "G_lag_residual", "pool_size_active", "lag_kish_n"]:
    s = df.loc[train, c]
    miss.append({"variable": c, "n": int(s.size), "n_missing": int(s.isna().sum()),
                 "pct_missing": round(100 * s.isna().mean(), 4),
                 "n_inf": int(np.isinf(s.to_numpy(dtype="float64", na_value=np.nan)).sum())
                 if s.dtype.kind == "f" else 0})
save(pd.DataFrame(miss), "A3_missingness_main_sample")

# ============================================================================
# B. 单变量分布
# ============================================================================
log("B. 单变量分布")
QS = [0.01, 0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95, 0.99]


def describe(frame: pd.DataFrame, cols: list[str], label: str) -> pd.DataFrame:
    out = []
    for c in cols:
        s = pd.to_numeric(frame[c], errors="coerce").dropna()
        if s.empty:
            continue
        q = s.quantile(QS)
        d = {"sample": label, "variable": c, "n": int(s.size),
             "mean": s.mean(), "std": s.std(), "min": s.min(), "max": s.max(),
             "skew": s.skew(), "kurtosis": s.kurtosis(),
             "pct_zero": 100 * float((s == 0).mean()),
             "iqr": float(q.loc[0.75] - q.loc[0.25])}
        for k in QS:
            d[f"p{int(k*100):02d}"] = float(q.loc[k])
        out.append(d)
    return pd.DataFrame(out)


UNI = (["funding_hours", "log_funding_hours", "funded_within_72h",
        "pool_size_active", "C_active", "H_active_raw", "H_active_residual",
        "pool_size_14d", "C_14d", "H_14d_raw", "pool_size_16d", "C_16d", "H_16d_raw",
        "lag_pool_raw_count", "lag_weight", "lag_kish_n", "V_lag",
        "G_lag_raw", "G_lag_residual", "V_lag_completed", "G_lag_completed_raw",
        "boilerplate_share", "loanAmount", "borrowerCount", "country_ppp"]
       + CTRL + FOCAL + [MAPS["active_residual"][k] for k in ("H", "G", "CH", "VG")])
uni = pd.concat([
    describe(df.loc[train], UNI, "train_2016_2024"),
    describe(df.loc[hold], UNI, "holdout_2025"),
    describe(df, UNI, "all_rows"),
], ignore_index=True)
save(uni, "B1_univariate_distributions")

# 类别型变量分布
cat_rows = []
for c in ["sector", "country_name", "gender", "repaymentInterval", "status", "activity"]:
    vc = df.loc[train, c].value_counts(dropna=False)
    top = vc.head(25)
    for k, v in top.items():
        cat_rows.append({"variable": c, "level": str(k), "n": int(v),
                         "share_pct": round(100 * v / vc.sum(), 3),
                         "n_levels_total": int(vc.size)})
save(pd.DataFrame(cat_rows), "B2_categorical_top_levels")

# 结果变量厚尾诊断
fh = df.loc[train, "funding_hours"]
tail = pd.DataFrame([{
    "metric": "funding_hours", "n": int(fh.size), "mean": fh.mean(), "median": fh.median(),
    "p99": fh.quantile(0.99), "p999": fh.quantile(0.999), "max": fh.max(),
    "pct_under_24h": 100 * float((fh < 24).mean()),
    "pct_under_72h": 100 * float((fh < 72).mean()),
    "pct_over_30d": 100 * float((fh > 720).mean()),
    "pct_exact_zero": 100 * float((fh == 0).mean()),
    "mean_over_median": float(fh.mean() / fh.median()),
}])
save(tail, "B3_outcome_tail_diagnostics")

# ============================================================================
# C. 相关结构与共线性
# ============================================================================
log("C. 相关结构与共线性")
CORR_SET = FOCAL + CTRL + ["log_funding_hours", "boilerplate_share",
                           "pool_size_active", "lag_kish_n"]
sub = df.loc[train, CORR_SET].astype("float64")
pear = sub.corr(method="pearson")
samp = sub.sample(n=min(300_000, len(sub)), random_state=20260901)
spear = samp.corr(method="spearman")


def long_corr(mat: pd.DataFrame, kind: str) -> pd.DataFrame:
    m = mat.where(~np.tril(np.ones(mat.shape, dtype=bool)))
    s = m.stack().reset_index()
    s.columns = ["var_a", "var_b", "corr"]
    s["method"] = kind
    return s


save(pd.concat([long_corr(pear, "pearson"), long_corr(spear, "spearman_300k")],
               ignore_index=True).sort_values("corr", key=abs, ascending=False),
     "C1_correlation_pairs")
pear.round(4).to_csv(TAB / "C2_correlation_matrix_pearson.csv")
log("  -> tables/C2_correlation_matrix_pearson.csv")

# VIF（六个焦点回归元 + 控制变量）
X = df.loc[train, FOCAL + CTRL].astype("float64").to_numpy()
X = np.column_stack([np.ones(len(X)), X])
names = ["const"] + FOCAL + CTRL
XtX_inv = np.linalg.inv(X.T @ X)
vif_rows = []
for j in range(1, X.shape[1]):
    others = [k for k in range(X.shape[1]) if k != j]
    b, *_ = np.linalg.lstsq(X[:, others], X[:, j], rcond=None)
    resid = X[:, j] - X[:, others] @ b
    r2 = 1 - resid.var() / X[:, j].var()
    vif_rows.append({"variable": names[j], "r2_on_others": r2,
                     "vif": 1 / max(1e-12, 1 - r2)})
cond = np.linalg.cond(np.corrcoef(df.loc[train, FOCAL].astype("float64").to_numpy(), rowvar=False))
vif = pd.DataFrame(vif_rows)
vif["focal_block_condition_number"] = cond
save(vif, "C3_vif_collinearity")

# ============================================================================
# D. FE 近似残差化（country + activity + week 交替投影去均值）
#    用于让 EDA 的双变量图接近主模型的识别变异
# ============================================================================
log("D. 三重固定效应交替投影去均值")
DEMEAN_COLS = ["log_funding_hours"] + FOCAL + CTRL
work = df.loc[train, DEMEAN_COLS + ["country_name", "activity", "week_id",
                                    "sector", "fundraising_year"]].copy()
Y = work[DEMEAN_COLS].astype("float64").to_numpy()
keys = [work["country_name"].astype("category").cat.codes.to_numpy(),
        work["activity"].astype("category").cat.codes.to_numpy(),
        work["week_id"].astype("category").cat.codes.to_numpy()]
counts = [np.bincount(k) for k in keys]
for it in range(60):
    delta = 0.0
    for k, cnt in zip(keys, counts):
        sums = np.zeros((cnt.size, Y.shape[1]))
        np.add.at(sums, k, Y)
        means = sums / cnt[:, None]
        step = means[k]
        delta = max(delta, float(np.abs(step).max()))
        Y -= step
    if delta < 1e-8:
        break
log(f"  交替投影收敛：iter={it+1} max_step={delta:.2e}")
DM = pd.DataFrame(Y, columns=[f"dm_{c}" for c in DEMEAN_COLS], index=work.index)
work = pd.concat([work, DM], axis=1)
dm_corr = work[[f"dm_{c}" for c in DEMEAN_COLS]].corr()
save(long_corr(dm_corr, "pearson_fe_demeaned").sort_values("corr", key=abs, ascending=False),
     "D1_fe_demeaned_correlation_pairs")

# 去均值后各变量剩余变异比例（FE 吸收了多少）
absorb = []
for c in DEMEAN_COLS:
    raw_v = float(work[c].astype("float64").var())
    dm_v = float(work[f"dm_{c}"].var())
    absorb.append({"variable": c, "var_raw": raw_v, "var_after_FE": dm_v,
                   "share_within_FE_pct": round(100 * dm_v / raw_v, 2),
                   "share_absorbed_by_FE_pct": round(100 * (1 - dm_v / raw_v), 2)})
save(pd.DataFrame(absorb), "D2_variance_absorbed_by_FE")

# ============================================================================
# E. RQ1 —— 当前池 C × H
# ============================================================================
log("E. RQ1: C x H")


def grid(frame: pd.DataFrame, xc: str, yc: str, outcome: str, q: int = 5,
         extra: dict | None = None) -> pd.DataFrame:
    f = frame[[xc, yc, outcome]].dropna()
    xb = pd.qcut(f[xc], q, labels=False, duplicates="drop")
    yb = pd.qcut(f[yc], q, labels=False, duplicates="drop")
    g = f.groupby([xb, yb], observed=True)[outcome].agg(["size", "mean", "median", "std"])
    g = g.reset_index()
    g.columns = ["x_bin", "y_bin", "n", "mean", "median", "std"]
    g["x_var"], g["y_var"], g["outcome"] = xc, yc, outcome
    if extra:
        for k, v in extra.items():
            g[k] = v
    return g


tr = work  # 已含 dm_ 列
rq1 = []
rq1.append(grid(df.loc[train], M["C"], M["H"], "log_funding_hours", 5,
                {"view": "raw"}))
rq1.append(grid(tr, f"dm_{M['C']}", f"dm_{M['H']}", "dm_log_funding_hours", 5,
                {"view": "FE_demeaned"}))
save(pd.concat(rq1, ignore_index=True), "E1_rq1_CxH_quintile_grid")

# H 十分位 × C 三分位 的边际形态
f = df.loc[train, [M["C"], M["H"], "log_funding_hours", "funding_hours",
                   "funded_within_72h", "eligible_72h_followup"]].dropna(subset=[M["C"], M["H"]])
f["C_tercile"] = pd.qcut(f[M["C"]], 3, labels=["C_low", "C_mid", "C_high"])
f["H_decile"] = pd.qcut(f[M["H"]], 10, labels=False)
prof = (f.groupby(["C_tercile", "H_decile"], observed=True)
        .agg(n=("log_funding_hours", "size"),
             mean_log_fh=("log_funding_hours", "mean"),
             median_fh=("funding_hours", "median"))
        .reset_index())
elig = f[f["eligible_72h_followup"] == 1]
p72 = (elig.groupby(["C_tercile", "H_decile"], observed=True)["funded_within_72h"]
       .mean().mul(100).rename("pct_funded_72h").reset_index())
save(prof.merge(p72, on=["C_tercile", "H_decile"], how="left"),
     "E2_rq1_H_decile_profile_by_C_tercile")

# 交互项本身的十分位 → 结果
def decile_profile(frame: pd.DataFrame, var: str, outcome: str, label: str) -> pd.DataFrame:
    f = frame[[var, outcome]].dropna()
    b = pd.qcut(f[var], 10, labels=False, duplicates="drop")
    g = f.groupby(b, observed=True).agg(n=(outcome, "size"), mean_outcome=(outcome, "mean"),
                                        median_outcome=(outcome, "median"))
    g = g.reset_index().rename(columns={g.index.name or "index": "decile"})
    g.columns = ["decile", "n", "mean_outcome", "median_outcome"]
    edges = f.groupby(b, observed=True)[var].agg(["min", "max", "mean"]).reset_index(drop=True)
    g[["bin_min", "bin_max", "bin_mean"]] = edges[["min", "max", "mean"]].to_numpy()
    g["variable"], g["outcome"], g["view"] = var, outcome, label
    return g


dp = []
for v in FOCAL:
    dp.append(decile_profile(df.loc[train], v, "log_funding_hours", "raw"))
    dp.append(decile_profile(tr, f"dm_{v}", "dm_log_funding_hours", "FE_demeaned"))
save(pd.concat(dp, ignore_index=True), "E3_focal_decile_profiles")

# ============================================================================
# F. RQ2 —— 滞后池 V × G，raw vs residual
# ============================================================================
log("F. RQ2: V x G, raw vs residual")
rq2 = [grid(df.loc[train], M["V"], M["G"], "log_funding_hours", 5, {"view": "raw"}),
       grid(tr, f"dm_{M['V']}", f"dm_{M['G']}", "dm_log_funding_hours", 5, {"view": "FE_demeaned"})]
save(pd.concat(rq2, ignore_index=True), "F1_rq2_VxG_quintile_grid")

# raw vs residual 文本表示对比
RM = MAPS["active_residual"]
cmp_rows = []
both = train & df["residual_text_nonempty"]
for a, b, lab in [("H_active_raw", "H_active_residual", "H_current"),
                  ("G_lag_raw", "G_lag_residual", "G_lag")]:
    s = df.loc[both, [a, b]].dropna()
    cmp_rows.append({
        "pair": lab, "n": int(len(s)),
        "mean_raw": s[a].mean(), "mean_residual": s[b].mean(),
        "median_raw": s[a].median(), "median_residual": s[b].median(),
        "std_raw": s[a].std(), "std_residual": s[b].std(),
        "pearson": float(s[a].corr(s[b])),
        "spearman": float(s.sample(min(300_000, len(s)), random_state=1).corr(method="spearman").iloc[0, 1]),
        "mean_drop_pct": round(100 * (1 - s[b].mean() / s[a].mean()), 2),
    })
save(pd.DataFrame(cmp_rows), "F2_raw_vs_residual_text_representation")

# 两通道是否可分：CH vs VG，以及 C/V、H/G 之间
sep = []
s = df.loc[train, [M["C"], M["H"], M["V"], M["G"], M["CH"], M["VG"]]].astype("float64")
for a, b in [(M["C"], M["V"]), (M["H"], M["G"]), (M["CH"], M["VG"]),
             (M["C"], M["H"]), (M["V"], M["G"])]:
    sep.append({"var_a": a, "var_b": b, "pearson_raw": float(s[a].corr(s[b])),
                "pearson_FE_demeaned": float(tr[f"dm_{a}"].corr(tr[f"dm_{b}"]))})
save(pd.DataFrame(sep), "F3_channel_separability")

# boilerplate share 与饱和度
bp = df.loc[train, ["boilerplate_share", "H_active_raw", "H_active_residual",
                    "G_lag_raw", "G_lag_residual", "log_funding_hours"]].dropna()
bp["bp_decile"] = pd.qcut(bp["boilerplate_share"], 10, labels=False, duplicates="drop")
save(bp.groupby("bp_decile", observed=True).agg(
    n=("boilerplate_share", "size"),
    mean_boilerplate_share=("boilerplate_share", "mean"),
    mean_H_raw=("H_active_raw", "mean"), mean_H_residual=("H_active_residual", "mean"),
    mean_G_raw=("G_lag_raw", "mean"), mean_G_residual=("G_lag_residual", "mean"),
    mean_log_fh=("log_funding_hours", "mean")).reset_index(),
     "F4_boilerplate_share_profile")

# ============================================================================
# G. RQ3 —— 年度演化
# ============================================================================
log("G. RQ3: 年度演化")


def within_slopes(frame: pd.DataFrame, regs: list[str], outcome: str) -> dict:
    """组内 OLS（已 FE 去均值的数据上），返回系数与 R2。"""
    f = frame[regs + [outcome]].dropna()
    if len(f) < 200:
        return {}
    Xm = f[regs].to_numpy(dtype="float64")
    ym = f[outcome].to_numpy(dtype="float64")
    Xm = np.column_stack([np.ones(len(Xm)), Xm])
    beta, *_ = np.linalg.lstsq(Xm, ym, rcond=None)
    resid = ym - Xm @ beta
    r2 = 1 - resid.var() / ym.var()
    out = {"n": int(len(f)), "r2": float(r2)}
    for name, b in zip(["const"] + regs, beta):
        out[f"b_{name}"] = float(b)
    return out


dm_focal = [f"dm_{v}" for v in FOCAL]
dm_ctrl = [f"dm_{c}" for c in CTRL]
yrows = []
for y, g in tr.groupby("fundraising_year", observed=True):
    r = {"fundraising_year": int(y)}
    r.update(within_slopes(g, dm_focal + dm_ctrl, "dm_log_funding_hours"))
    raw = df.loc[train & (df["fundraising_year"] == y)]
    r.update({
        "median_funding_hours": float(raw["funding_hours"].median()),
        "mean_log_fh": float(raw["log_funding_hours"].mean()),
        "pct_funded_72h": float(100 * raw.loc[raw["eligible_72h_followup"] == 1,
                                              "funded_within_72h"].mean()),
        "mean_C": float(raw[M["C"]].mean()), "mean_H": float(raw[M["H"]].mean()),
        "mean_V": float(raw[M["V"]].mean()), "mean_G": float(raw[M["G"]].mean()),
        "mean_CH": float(raw[M["CH"]].mean()), "mean_VG": float(raw[M["VG"]].mean()),
        "median_pool_active": float(raw["pool_size_active"].median()),
        "median_H_raw": float(raw["H_active_raw"].median()),
        "median_G_raw": float(raw["G_lag_raw"].median()),
        "mean_boilerplate_share": float(raw["boilerplate_share"].mean()),
    })
    yrows.append(r)
year_tab = pd.DataFrame(yrows).sort_values("fundraising_year")
save(year_tab, "G1_rq3_by_year_moments_and_slopes")

# 年度 × 关键变量分位数（分布漂移）
qrows = []
for y, g in df.loc[train | hold].groupby("fundraising_year", observed=True):
    for c in ["funding_hours", "H_active_raw", "G_lag_raw", "C_active", "V_lag",
              "pool_size_active", "boilerplate_share"]:
        s = g[c].dropna()
        if s.empty:
            continue
        qq = s.quantile([0.25, 0.5, 0.75])
        qrows.append({"fundraising_year": int(y), "variable": c, "n": int(s.size),
                      "p25": float(qq.loc[0.25]), "p50": float(qq.loc[0.5]),
                      "p75": float(qq.loc[0.75]), "mean": float(s.mean())})
save(pd.DataFrame(qrows), "G2_rq3_year_quantile_drift")

# ============================================================================
# H. RQ4 —— 板块 / 国家异质性
# ============================================================================
log("H. RQ4: 板块与国家异质性")
grp_rows = []
for keycol, minimum in [("sector", 2000), ("country_name", 5000)]:
    for k, g in tr.groupby(keycol, observed=True):
        if len(g) < minimum:
            continue
        r = {"grouping": keycol, "level": str(k)}
        r.update(within_slopes(g, dm_focal + dm_ctrl, "dm_log_funding_hours"))
        raw = df.loc[train & (df[keycol] == k)]
        r.update({
            "loans": int(len(raw)),
            "share_of_train_pct": round(100 * len(raw) / int(train.sum()), 3),
            "median_funding_hours": float(raw["funding_hours"].median()),
            "pct_funded_72h": float(100 * raw.loc[raw["eligible_72h_followup"] == 1,
                                                  "funded_within_72h"].mean()),
            "mean_H_raw": float(raw["H_active_raw"].mean()),
            "median_H_raw": float(raw["H_active_raw"].median()),
            "mean_G_raw": float(raw["G_lag_raw"].mean()),
            "median_pool_active": float(raw["pool_size_active"].median()),
            "mean_boilerplate_share": float(raw["boilerplate_share"].mean()),
            "mean_log_loan_amount": float(raw["log_loan_amount"].mean()),
        })
        grp_rows.append(r)
het = pd.DataFrame(grp_rows)
save(het[het["grouping"] == "sector"].sort_values("loans", ascending=False), "H1_rq4_by_sector")
save(het[het["grouping"] == "country_name"].sort_values("loans", ascending=False), "H2_rq4_by_country")

# 方差分解：H 与 G 的变异有多少在板块之间 vs 板块之内（注意力市场边界）
dec_rows = []
for var in ["H_active_raw", "G_lag_raw", "C_active", "V_lag", "log_funding_hours"]:
    s = df.loc[train, [var, "sector", "country_name", "activity", "fundraising_year"]].dropna(subset=[var])
    total = float(s[var].var())
    for by in ["sector", "country_name", "activity", "fundraising_year"]:
        gm = s.groupby(by, observed=True)[var].agg(["mean", "size"])
        grand = float(s[var].mean())
        between = float((gm["size"] * (gm["mean"] - grand) ** 2).sum() / (len(s) - 1))
        dec_rows.append({"variable": var, "grouping": by, "var_total": total,
                         "var_between": between, "var_within": total - between,
                         "between_share_pct": round(100 * between / total, 2),
                         "n_groups": int(len(gm))})
save(pd.DataFrame(dec_rows), "H3_variance_decomposition")

# 板块 × 年份的双向格子（RQ3 x RQ4 交叉）
cell = (df.loc[train].groupby(["sector", "fundraising_year"], observed=True)
        .agg(n=("id", "size"), median_fh=("funding_hours", "median"),
             mean_H=("H_active_raw", "mean"), mean_CH=(M["CH"], "mean"))
        .reset_index())
save(cell, "H4_sector_by_year_cells")

# ============================================================================
# I. 反事实支撑域：P25 -> P75 情景端点是否有样本
# ============================================================================
log("I. 支撑域检查")
sup_rows = []
for spec in ["active_raw", "active_residual"]:
    m = MAPS[spec]
    v = scalers[spec]
    q = {k: ((v[k]["p25"] - v[k]["mean"]) / v[k]["std"],
             (v[k]["p75"] - v[k]["mean"]) / v[k]["std"]) for k in ("C", "H", "V", "G")}
    mask = train if spec == "active_raw" else resid_train
    d = df.loc[mask]
    for chan, (a, b) in [("current_CH", ("C", "H")), ("recent_VG", ("V", "G"))]:
        lo = (d[m[a]] <= q[a][0]) & (d[m[b]] <= q[b][0])
        hi = (d[m[a]] >= q[a][1]) & (d[m[b]] >= q[b][1])
        sup_rows.append({
            "specification": spec, "channel": chan,
            "z_p25_" + a: q[a][0], "z_p75_" + a: q[a][1],
            "z_p25_" + b: q[b][0], "z_p75_" + b: q[b][1],
            "n_at_or_below_p25_corner": int(lo.sum()),
            "n_at_or_above_p75_corner": int(hi.sum()),
            "pct_low_corner": round(100 * float(lo.mean()), 3),
            "pct_high_corner": round(100 * float(hi.mean()), 3),
            "median_fh_low_corner": float(d.loc[lo, "funding_hours"].median()) if lo.any() else np.nan,
            "median_fh_high_corner": float(d.loc[hi, "funding_hours"].median()) if hi.any() else np.nan,
        })
save(pd.DataFrame(sup_rows), "I1_counterfactual_support")

# 训练期 vs 2025 holdout 的分布漂移
drift_rows = []
for c in ["funding_hours", "log_funding_hours", "C_active", "H_active_raw",
          "V_lag", "G_lag_raw", M["CH"], M["VG"], "pool_size_active",
          "lag_kish_n", "log_loan_amount", "boilerplate_share"]:
    a = df.loc[train, c].dropna().astype("float64")
    b = df.loc[hold, c].dropna().astype("float64")
    if a.empty or b.empty:
        continue
    # 标准化均值差 + 分位差
    sd = np.sqrt((a.var() + b.var()) / 2)
    drift_rows.append({
        "variable": c, "n_train": int(a.size), "n_holdout": int(b.size),
        "mean_train": a.mean(), "mean_holdout": b.mean(),
        "std_mean_diff": float((b.mean() - a.mean()) / sd) if sd > 0 else np.nan,
        "p50_train": a.median(), "p50_holdout": b.median(),
        "p90_train": a.quantile(0.9), "p90_holdout": b.quantile(0.9),
    })
save(pd.DataFrame(drift_rows).sort_values("std_mean_diff", key=abs, ascending=False),
     "I2_train_vs_holdout_drift")

# ============================================================================
# J. 图
# ============================================================================
log("J. 出图")
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

plt.rcParams.update({"figure.dpi": 130, "savefig.dpi": 160, "font.size": 9,
                     "axes.grid": True, "grid.alpha": 0.25})


def fig_save(fig, name):
    fig.tight_layout()
    fig.savefig(FIG / f"{name}.png", bbox_inches="tight")
    plt.close(fig)
    log(f"  -> figures/{name}.png")


# J1 结果变量分布
fig, ax = plt.subplots(1, 3, figsize=(12, 3.4))
ax[0].hist(df.loc[train, "funding_hours"].clip(upper=2000), bins=100, color="#4C78A8")
ax[0].set_title("funding_hours (clipped 2000h)")
ax[1].hist(df.loc[train, "log_funding_hours"], bins=100, color="#4C78A8")
ax[1].set_title("log(1+funding_hours)")
s = np.sort(df.loc[train, "funding_hours"].to_numpy())
ax[2].plot(np.linspace(0, 100, len(s)), s)
ax[2].set_yscale("log")
ax[2].set_title("funding_hours ECDF (log y)")
ax[2].set_xlabel("percentile")
fig_save(fig, "J1_outcome_distribution")

# J2 C/H/V/G 分布
fig, ax = plt.subplots(2, 4, figsize=(14, 6))
for j, (col, ttl) in enumerate([("C_active", "C = log(1+active pool n)"),
                                ("H_active_raw", "H current cosine"),
                                ("V_lag", "V = log(1+lag weight)"),
                                ("G_lag_raw", "G lag cosine")]):
    ax[0, j].hist(df.loc[train, col], bins=100, color="#54A24B")
    ax[0, j].set_title(ttl)
for j, key in enumerate(["C", "H", "V", "G"]):
    ax[1, j].hist(df.loc[train, M[key]].clip(-4, 6), bins=100, color="#E45756")
    ax[1, j].set_title(f"{key}z (standardised)")
fig_save(fig, "J2_focal_variable_distributions")

# J3 RQ1 热力图（FE 去均值）
def heat(ax, tabl, title):
    p = tabl.pivot(index="y_bin", columns="x_bin", values="mean")
    im = ax.imshow(p.to_numpy(), origin="lower", cmap="RdYlBu_r", aspect="auto")
    ax.set_title(title, fontsize=9)
    ax.set_xlabel("x quintile")
    ax.set_ylabel("y quintile")
    ax.grid(False)
    for (i, jj), v in np.ndenumerate(p.to_numpy()):
        ax.text(jj, i, f"{v:.3f}", ha="center", va="center", fontsize=7)
    return im


g1 = pd.concat(rq1, ignore_index=True)
g2 = pd.concat(rq2, ignore_index=True)
fig, ax = plt.subplots(2, 2, figsize=(11, 8))
heat(ax[0, 0], g1[g1["view"] == "raw"], "RQ1 raw: mean log_fh by C(x) x H(y)")
heat(ax[0, 1], g1[g1["view"] == "FE_demeaned"], "RQ1 FE-demeaned: C(x) x H(y)")
heat(ax[1, 0], g2[g2["view"] == "raw"], "RQ2 raw: mean log_fh by V(x) x G(y)")
heat(ax[1, 1], g2[g2["view"] == "FE_demeaned"], "RQ2 FE-demeaned: V(x) x G(y)")
fig_save(fig, "J3_interaction_heatmaps")

# J4 H decile profile by C tercile
prof2 = prof.merge(p72, on=["C_tercile", "H_decile"], how="left")
fig, ax = plt.subplots(1, 2, figsize=(11, 3.8))
for lab, g in prof2.groupby("C_tercile", observed=True):
    ax[0].plot(g["H_decile"], g["mean_log_fh"], marker="o", label=str(lab))
    ax[1].plot(g["H_decile"], g["pct_funded_72h"], marker="o", label=str(lab))
ax[0].set_xlabel("H decile"); ax[0].set_ylabel("mean log(1+funding hours)")
ax[0].set_title("RQ1 raw: slower funding at high H, steeper when C high")
ax[1].set_xlabel("H decile"); ax[1].set_ylabel("% funded within 72h")
ax[1].set_title("72h fast-funding rate")
ax[0].legend(); ax[1].legend()
fig_save(fig, "J4_rq1_H_profile_by_C")

# J5 年度演化
fig, ax = plt.subplots(1, 3, figsize=(13, 3.6))
ax[0].plot(year_tab["fundraising_year"], year_tab["median_funding_hours"], marker="o")
ax[0].set_title("median funding hours by year")
ax[1].plot(year_tab["fundraising_year"], year_tab["median_H_raw"], marker="o", label="H current")
ax[1].plot(year_tab["fundraising_year"], year_tab["median_G_raw"], marker="s", label="G lag")
ax[1].set_title("median cosine similarity by year"); ax[1].legend()
if f"b_dm_{M['CH']}" in year_tab:
    ax[2].plot(year_tab["fundraising_year"], year_tab[f"b_dm_{M['CH']}"], marker="o", label="CH slope")
    ax[2].plot(year_tab["fundraising_year"], year_tab[f"b_dm_{M['VG']}"], marker="s", label="VG slope")
    ax[2].axhline(0, color="k", lw=0.8)
    ax[2].set_title("within-year FE-demeaned OLS slope"); ax[2].legend()
fig_save(fig, "J5_rq3_year_evolution")

# J6 板块异质性
sec = het[het["grouping"] == "sector"].sort_values(f"b_dm_{M['CH']}")
fig, ax = plt.subplots(1, 2, figsize=(13, 4.6))
ax[0].barh(sec["level"], sec[f"b_dm_{M['CH']}"], color="#4C78A8")
ax[0].axvline(0, color="k", lw=0.8)
ax[0].set_title("RQ4 sector: within-sector CH slope (FE-demeaned)")
ax[1].barh(sec["level"], sec[f"b_dm_{M['VG']}"], color="#F58518")
ax[1].axvline(0, color="k", lw=0.8)
ax[1].set_title("RQ4 sector: within-sector VG slope (FE-demeaned)")
fig_save(fig, "J6_rq4_sector_slopes")

# J7 相关热图
fig, ax = plt.subplots(1, 2, figsize=(14, 6))
for a, mat, ttl in [(ax[0], pear, "Pearson (raw, train)"),
                    (ax[1], dm_corr, "Pearson (FE-demeaned)")]:
    im = a.imshow(mat.to_numpy(), cmap="RdBu_r", vmin=-1, vmax=1)
    a.set_xticks(range(len(mat))); a.set_xticklabels(mat.columns, rotation=90, fontsize=6)
    a.set_yticks(range(len(mat))); a.set_yticklabels(mat.index, fontsize=6)
    a.set_title(ttl); a.grid(False)
    fig.colorbar(im, ax=a, shrink=0.8)
fig_save(fig, "J7_correlation_heatmaps")

# J8 训练 vs holdout 漂移
fig, ax = plt.subplots(1, 3, figsize=(13, 3.6))
for a, col in zip(ax, ["H_active_raw", "C_active", "funding_hours"]):
    a.hist(df.loc[train, col].clip(upper=df.loc[train, col].quantile(0.99)), bins=80,
           density=True, alpha=0.55, label="train 2016-24")
    a.hist(df.loc[hold, col].clip(upper=df.loc[train, col].quantile(0.99)), bins=80,
           density=True, alpha=0.55, label="holdout 2025")
    a.set_title(col); a.legend(fontsize=7)
fig_save(fig, "J8_train_vs_holdout_drift")

log("EDA 完成")
json.dump({"elapsed_seconds": round(time.time() - T0, 1),
           "tables": sorted(p.name for p in TAB.glob("*.csv")),
           "figures": sorted(p.name for p in FIG.glob("*.png"))},
          open(EDA / "eda_manifest.json", "w"), indent=2, ensure_ascii=False)
