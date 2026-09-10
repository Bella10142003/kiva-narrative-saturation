"""补充规格：逐项检验提案中各设计环节的边际贡献。"""
import numpy as np, pandas as pd, json, warnings
from scipy import sparse
warnings.filterwarnings("ignore")

d = pd.DataFrame(pd.read_pickle("kiva_sim_20k.pkl"))
d["fundraisingDate"] = pd.to_datetime(d.fundraisingDate, utc=True)
d["raisedDate"] = pd.to_datetime(d.raisedDate, utc=True)
d["disbursalDate"] = pd.to_datetime(d.disbursalDate, utc=True)
d = d.sort_values("fundraisingDate", ignore_index=True)
d["hours"] = (d.raisedDate - d.fundraisingDate).dt.total_seconds()/3600
d["funded"] = d.status.eq("funded")
P = pd.read_csv("pipeline_pools.csv")
TR = pd.read_csv("kiva_sim_truth.csv").set_index("id").loc[d.id].reset_index()
T = json.load(open("kiva_sim_meta.json"))["TRUE_STANDARDISED"]

post_h = d.fundraisingDate.values.astype("datetime64[s]").astype(np.int64)/3600.0
d["week"] = ((post_h - post_h.min())//(24*7)).astype(int)
d["year"] = d.fundraisingDate.dt.year
CTRL = np.column_stack([
    np.log(d.loanAmount.values/300.0), (d.borrowerCount.values > 1).astype(float),
    (d.gender.values == "male").astype(float), d.lenderRepaymentTerm.values-12.0,
    (d.repaymentInterval.values == "at_end").astype(float),
    np.clip((d.fundraisingDate-d.disbursalDate).dt.days.values, -60, 120)/30.0])
CN = ["logAmt","group","male","term","atEnd","disbGap"]

def z(x):
    x = np.asarray(x, float); s = np.nanstd(x)
    return (x-np.nanmean(x))/s if s > 0 else x*0

def fe_mat(mask, extra_fe=None):
    specs = dict(country=pd.Categorical(d.country_name).codes,
                 activity=pd.Categorical(d.activity).codes, week=d.week.values)
    mats = []
    items = [(n, codes[mask]) for n, codes in specs.items()]
    if extra_fe is not None: items.append(("extra", pd.Categorical(extra_fe).codes))
    for _, codes in items:
        c = pd.Categorical(codes).codes; k = c.max()+1
        if k > 1:
            M = sparse.csr_matrix((np.ones(mask.sum()), (np.arange(mask.sum()), c)),
                                  shape=(mask.sum(), k))
            mats.append(M[:, 1:])
    return sparse.hstack(mats).tocsr()

def est(y, Xd, mask, names, extra_fe=None):
    X = sparse.hstack([sparse.csr_matrix(Xd), fe_mat(mask, extra_fe),
                       sparse.csr_matrix(np.ones((mask.sum(),1)))]).tocsr()
    XtX = (X.T@X).toarray(); Xi = np.linalg.pinv(XtX); b = Xi@(X.T@y); e = y - X@b
    def meat(g):
        gg = pd.Categorical(g).codes
        G = sparse.csr_matrix((np.ones(len(gg)), (gg, np.arange(len(gg)))), shape=(gg.max()+1, len(gg)))
        S = (G@X.multiply(e[:,None])).toarray(); return S.T@S
    c1, c2 = d.country_name.values[mask], d.week.values[mask]
    V = Xi@(meat(c1)+meat(c2)-meat([f"{a}|{b_}" for a,b_ in zip(c1,c2)]))@Xi
    se = np.sqrt(np.clip(np.diag(V), 0, None)); k = len(names)
    return dict(names=names, coef=b[:k], se=se[:k], n=int(mask.sum()))

def spec(cols, min_pool=10, pool_col=None, lag=True, extra=None, extra_names=(),
         mask0=None, extra_fe=None):
    pool_col = pool_col or cols[0]
    m = d.funded.values.copy()
    m &= P[pool_col].values >= min_pool
    for c in cols: m &= np.isfinite(P[c].values)
    m &= np.isfinite(CTRL).all(axis=1)
    if mask0 is not None: m &= mask0
    y = np.log1p(d.hours.values[m])
    Zc, Zh = z(np.log1p(P[cols[0]].values))[m], z(P[cols[1]].values)[m]
    X = [Zc, Zh, Zc*Zh]; names = ["C","H","CxH"]
    if lag:
        Zv, Zg = z(np.log1p(P[cols[2]].values))[m], z(P[cols[3]].values)[m]
        X += [Zv, Zg, Zv*Zg]; names += ["V","G","VxG"]
    Xd = np.column_stack(X + [CTRL[m]]); names = names + CN
    if extra is not None:
        Xd = np.column_stack([Xd, extra[m]]); names = names + list(extra_names)
    fe = None if extra_fe is None else extra_fe[m]
    return est(y, Xd, m, names, extra_fe=fe)

def row(tag, r, keys=("C","H","CxH","V","G","VxG")):
    i = {n:j for j,n in enumerate(r["names"])}
    out = f"{tag:<34}{r['n']:>7}"
    for k in keys:
        if k in i: out += f"{r['coef'][i[k]]:>9.3f}({r['se'][i[k]]:.3f})"
        else:      out += f"{'—':>18}"
    return out

C4 = ["C_use","H_use","V_use","G_use"]
M4 = ["Cm","Hm","V_use","G_use"]
hdr = f"{'规格':<34}{'N':>7}" + "".join(f"{k:>18}" for k in ["C","H","C×H","V","G","V×G"])
print("真值:", {k: round(v,3) for k,v in T.items()}); print(hdr); print("-"*len(hdr))
R = {}
R["A_active_thr10"]   = spec(C4, 10)
R["B_active_thr0"]    = spec(C4, 0)
R["C_mirror_thr10"]   = spec(M4, 10, pool_col="Cm")
R["D_mirror_thr0"]    = spec(M4, 0,  pool_col="Cm")
R["E_mirror_nolag"]   = spec(M4, 0,  pool_col="Cm", lag=False)
R["F_active_nolag"]   = spec(C4, 0,  lag=False)
R["G_oracle_partner"] = spec(C4, 0,  extra_fe=TR.partner_id.values)
R["H_oracle_shock"]   = spec(C4, 0,  extra=z(TR.sector_week_shock.values)[:,None],
                             extra_names=["shock"])
for k, r in R.items(): print(row(k, r))

# ---- 衰减半衰期是否必要：把滞后池换成无衰减均匀权重 ----
print("\n【衰减参数的边际贡献】")
import subprocess
print(row("D_mirror_thr0 (7天半衰期)", R["D_mirror_thr0"]))

# ---- 样条：真值是线性的，样条应当不贡献 ----
def rcs(x, knots=(5,35,65,95)):
    k = np.nanpercentile(x, knots); t = []
    for j in range(1, len(k)-1):
        num = (np.maximum(x-k[j],0)**3 - np.maximum(x-k[-2],0)**3*(k[-1]-k[j])/(k[-1]-k[-2])
               + np.maximum(x-k[-1],0)**3*(k[-2]-k[j])/(k[-1]-k[-2]))
        t.append(num/(k[-1]-k[0])**2)
    return np.column_stack(t)
sp = rcs(P.Hm.values)
R["I_spline_H"] = spec(M4, 0, pool_col="Cm", extra=sp, extra_names=[f"sp{j}" for j in range(sp.shape[1])])
print("\n【样条（真值为线性 → 样条项应不显著）】")
i = {n:j for j,n in enumerate(R["I_spline_H"]["names"])}
for j in range(sp.shape[1]):
    b, s_ = R["I_spline_H"]["coef"][i[f"sp{j}"]], R["I_spline_H"]["se"][i[f"sp{j}"]]
    print(f"  样条项 {j}: {b:+.4f} (se {s_:.4f}, t {b/s_:+.2f})")
print(row("I_spline_H", R["I_spline_H"]))

# ---- RQ3：连续年度交互 vs 前后半段分样本 ----
print("\n【RQ3 两种写法】")
yr = (d.year.values-2016).astype(float)
Zc, Zh = z(np.log1p(P.Cm.values)), z(P.Hm.values)
Zv, Zg = z(np.log1p(P.V_use.values)), z(P.G_use.values)
ex = np.column_stack([Zc*Zh*yr, Zv*Zg*yr, Zc*yr, Zh*yr])
r = spec(M4, 0, pool_col="Cm", extra=ex, extra_names=["CxHxYr","VxGxYr","CxYr","HxYr"])
i = {n:j for j,n in enumerate(r["names"])}
print(f"  连续交互 C×H×年: {r['coef'][i['CxHxYr']]:+.4f} (se {r['se'][i['CxHxYr']]:.4f}) "
      f"真值≈{T['b3_CH']*0.055:+.4f}")
print(f"  连续交互 V×G×年: {r['coef'][i['VxGxYr']]:+.4f} (se {r['se'][i['VxGxYr']]:.4f}) "
      f"真值≈{T['b6_VG']*0.130:+.4f}")
for lab, mk in [("2016-2020", d.year.values <= 2020), ("2021-2025", d.year.values >= 2021)]:
    rr = spec(M4, 0, pool_col="Cm", mask0=mk)
    print(row(f"  分样本 {lab}", rr))

# ---- 功效外推：β₃ 的标准误随样本量的变化 ----
print("\n【功效外推：β₃(C×H) 标准误 vs 样本量】")
rows = []
for frac in (0.25, 0.5, 1.0):
    rs = np.random.default_rng(7).random(len(d)) < frac
    rr = spec(M4, 0, pool_col="Cm", mask0=rs)
    i = {n:j for j,n in enumerate(rr["names"])}
    rows.append((rr["n"], rr["se"][i["CxH"]], rr["coef"][i["CxH"]]))
    print(f"  N={rr['n']:>6}  β₃={rr['coef'][i['CxH']]:+.4f}  se={rr['se'][i['CxH']]:.4f}")
n1, se1, _ = rows[-1]
for N in (150_000, 1_453_846):
    print(f"  外推 N={N:>9,}  se≈{se1*np.sqrt(n1/N):.4f}  "
          f"（真值 {T['b3_CH']:.3f} → t≈{T['b3_CH']/(se1*np.sqrt(n1/N)):.1f}）")

json.dump({k: {kk: (vv.tolist() if isinstance(vv, np.ndarray) else vv)
               for kk, vv in v.items()} for k, v in R.items()},
          open("extra_specs.json","w"), indent=1, default=float)

# ---- 功效的真正约束：行数 vs 聚类数 ----
print("\n【SE 的约束来自行数还是聚类数】")
def est_se(mask0, cluster=True):
    m = d.funded.values & np.isfinite(P.Cm.values) & np.isfinite(P.Hm.values) \
        & np.isfinite(P.V_use.values) & np.isfinite(P.G_use.values) & np.isfinite(CTRL).all(axis=1)
    if mask0 is not None: m &= mask0
    y = np.log1p(d.hours.values[m])
    Zc, Zh = z(np.log1p(P.Cm.values))[m], z(P.Hm.values)[m]
    Zv, Zg = z(np.log1p(P.V_use.values))[m], z(P.G_use.values)[m]
    Xd = np.column_stack([Zc, Zh, Zc*Zh, Zv, Zg, Zv*Zg, CTRL[m]])
    X = sparse.hstack([sparse.csr_matrix(Xd), fe_mat(m),
                       sparse.csr_matrix(np.ones((m.sum(),1)))]).tocsr()
    XtX = (X.T@X).toarray(); Xi = np.linalg.pinv(XtX); b = Xi@(X.T@y); e = y - X@b
    if not cluster:
        s2 = (e@e)/(m.sum()-X.shape[1]); V = Xi*s2
    else:
        def meat(g):
            gg = pd.Categorical(g).codes
            G = sparse.csr_matrix((np.ones(len(gg)),(gg,np.arange(len(gg)))),shape=(gg.max()+1,len(gg)))
            S = (G@X.multiply(e[:,None])).toarray(); return S.T@S
        c1, c2 = d.country_name.values[m], d.week.values[m]
        V = Xi@(meat(c1)+meat(c2)-meat([f"{a}|{b_}" for a,b_ in zip(c1,c2)]))@Xi
    return b[2], np.sqrt(max(V[2,2],0)), int(m.sum()), len(np.unique(d.week.values[m]))

b, se_c, n_, g_ = est_se(None, True); _, se_i, _, _ = est_se(None, False)
print(f"  全样本 β₃={b:+.4f}  聚类SE={se_c:.4f}  独立同分布SE={se_i:.4f}  "
      f"设计效应={se_c/se_i:.2f}×  (周聚类数={g_})")
print("  A) 随机抽行（聚类数不变）:")
for f in (0.25, 0.5):
    mk = np.random.default_rng(11).random(len(d)) < f
    b_, s_, n_, g_ = est_se(mk); print(f"     行数={n_:>6} 周数={g_:>4}  se={s_:.4f}")
print("  B) 随机抽周（行数与聚类数同比例下降）:")
wks = np.unique(d.week.values)
for f in (0.25, 0.5):
    keep = set(np.random.default_rng(11).choice(wks, int(len(wks)*f), replace=False))
    mk = np.array([w in keep for w in d.week.values])
    b_, s_, n_, g_ = est_se(mk); print(f"     行数={n_:>6} 周数={g_:>4}  se={s_:.4f}")

# ---- 校正后的功效外推（考虑组内相关随每簇行数上升）----
print("\n【校正后的功效外推：真实 145 万条】")
m_bar = n_/max(g_,1)
def project(se_c_now, se_i_now, n_now, m_bar_now, G_now, N_target, true_val, G_target=None):
    G_target = G_target or G_now
    rho = max((se_c_now**2/se_i_now**2 - 1)/max(m_bar_now-1, 1), 0)
    m_new = N_target/G_target
    se_i_new = se_i_now*np.sqrt(n_now/N_target)
    se_c_new = se_i_new*np.sqrt(1 + rho*(m_new-1))
    return se_c_new, true_val/se_c_new, rho
b_, se_c, n_all, g_all = est_se(None, True); _, se_i, _, _ = est_se(None, False)
m_bar = n_all/g_all
for lab, true_val, se_here in [("β₃ (C×H)", T["b3_CH"], se_c),
                               ("β₆ (V×G)", T["b6_VG"], 0.0153),
                               ("C×H×年 交互", T["b3_CH"]*0.055, 0.0051),
                               ("V×G×年 交互", T["b6_VG"]*0.130, 0.0049)]:
    scale = se_here/se_c
    s_new, t_new, rho = project(se_c, se_i, n_all, m_bar, g_all, 1_453_846, true_val)
    s_new *= scale
    print(f"  {lab:<14} 真值={true_val:+.4f}  20k的se={se_here:.4f}  "
          f"→ 145万的se≈{s_new:.4f}  t≈{true_val/s_new:.1f}")
print(f"  （组内相关 ρ≈{rho:.4f}，每周行数由 {m_bar:.0f} 升至 {1_453_846/g_all:.0f}）")
