"""
提案 Day1–Day5 分析流程 —— 在模拟数据上实际执行
=====================================================================
本脚本严格扮演「分析者」角色：只使用 kiva_sim_20k.pkl 里存在的字段，
不读取真值表。每一步记录耗时与产出，最后由 compare_to_truth.py 对答案。
"""
import numpy as np, pandas as pd, json, time, re, heapq, warnings
from scipy import sparse
from sklearn.feature_extraction.text import TfidfVectorizer
warnings.filterwarnings("ignore")

T0 = time.time(); TIMING = {}
def tick(step):
    now = time.time(); TIMING[step] = round(now - tick.last, 2); tick.last = now
    print(f"  [{step}] {TIMING[step]}s")
tick.last = T0
LOG = {}

# =====================================================================
# DAY 1 — 审计与冻结
# =====================================================================
print("== DAY 1 审计 ==")
df = pd.DataFrame(pd.read_pickle("kiva_sim_20k.pkl"))
for c in ["disbursalDate", "fundraisingDate", "raisedDate"]:
    df[c] = pd.to_datetime(df[c], utc=True, errors="coerce")
df = df.sort_values("fundraisingDate", ignore_index=True)

df["hours"] = (df.raisedDate - df.fundraisingDate).dt.total_seconds() / 3600
df["funded"] = df.status.eq("funded")
audit = dict(
    n=len(df),
    status_mix=df.status.value_counts().to_dict(),
    pct_no_raised_date=float(df.raisedDate.isna().mean()),
    dup_ids=int(df.id.duplicated().sum()),
    dup_use_text=float(df.use.duplicated().mean()),
    dup_description=float(df.description.duplicated().mean()),
    missing_by_field={c: float(df[c].isna().mean()) for c in df.columns if df[c].isna().any()},
    whySpecial_unique=int(df.whySpecial.nunique()),
    whySpecial_unique_per_row=float(df.whySpecial.nunique()/len(df)),
    use_unique_per_row=float(df.use.nunique()/len(df)),
    neg_disbursal_gap_share=float(((df.fundraisingDate-df.disbursalDate).dt.days < 0).mean()),
    hours_pct={f"p{q}": float(np.nanpercentile(df.hours, q)) for q in (5,25,50,75,90,95,99)},
    max_hours=float(np.nanmax(df.hours)),
)
# ---- 冻结 L：平台募资期限上限（由已募满贷款的最长时长识别），否则取 p95 ----
cap_days = float(np.ceil(np.nanmax(df.hours)/24))
L_DAYS = cap_days
audit["L_days_frozen"] = L_DAYS
audit["L_rule"] = "observed fundraising cap (max funded duration, rounded up)"
HALFLIFE_D = 7.0; WIN_D = 30.0; MIN_POOL = 10; MIRROR_D = 14.0
audit.update(halflife_days=HALFLIFE_D, lag_window_days=WIN_D,
             min_pool=MIN_POOL, mirror_days=MIRROR_D)
LOG["day1_audit"] = audit
print(json.dumps({k: audit[k] for k in
                  ["n","status_mix","pct_no_raised_date","whySpecial_unique_per_row",
                   "use_unique_per_row","L_days_frozen"]}, ensure_ascii=False, indent=1))
tick("day1_audit")

# ---- 终止日期重建 ----
# funded → raisedDate；expired → 上架 + L；refunded → 无法核实（提案要求「verified terminal date」）
L_H = L_DAYS*24
post_h = df.fundraisingDate.values.astype("datetime64[s]").astype(np.int64)/3600.0
end_h = np.where(df.funded, post_h + df.hours.fillna(0).values,
                 np.where(df.status.eq("expired"), post_h + L_H, np.nan))
audit["terminal_date_unverifiable_share"] = float(np.isnan(end_h).mean())
end_h_filled = np.where(np.isnan(end_h), post_h + L_H, end_h)   # 兜底假设
LOG["day1_audit"] = audit

# =====================================================================
# DAY 2–3 — 文本表示与双池构建
# =====================================================================
print("== DAY 2-3 文本与池 ==")
TAG = re.compile(r"<[^>]+>"); NUM = re.compile(r"\d+")
NAMES = set(df.name.unique())
def clean(t, mask_names=True):
    t = TAG.sub(" ", str(t))
    t = NUM.sub(" NUM ", t)
    if mask_names:
        t = " ".join("NAME" if w.strip(".,") in NAMES else w for w in t.split())
    return t.lower()

df["use_c"]  = [clean(t) for t in df.use]
df["desc_c"] = [clean(t) for t in df.description]
tick("text_clean")

def vecs(col, min_df=3):
    v = TfidfVectorizer(ngram_range=(1,2), min_df=min_df, sublinear_tf=True, norm="l2")
    return v.fit_transform(df[col].tolist()).tocsr(), v
U_use,  V_use  = vecs("use_c")
U_desc, V_desc = vecs("desc_c", min_df=5)
LOG["vocab"] = dict(use=U_use.shape[1], description=U_desc.shape[1])
tick("tfidf")

# ---- 模板（boilerplate）识别：高频逐字句子 ----
sent_counts = {}
for t in df.desc_c:
    for s_ in re.split(r"[.!?]", t):
        s_ = s_.strip()
        if len(s_.split()) >= 6: sent_counts[s_] = sent_counts.get(s_, 0) + 1
BOILER_MIN = max(20, int(0.001*len(df)))
boiler = {s_ for s_, c in sent_counts.items() if c >= BOILER_MIN}
def strip_boiler(t):
    keep = [s_ for s_ in re.split(r"([.!?])", t)]
    out, buf = [], ""
    for s_ in re.split(r"[.!?]", t):
        if s_.strip() not in boiler: out.append(s_.strip())
    return ". ".join([o for o in out if o])
df["desc_resid"] = [strip_boiler(t) for t in df.desc_c]
df["boiler_share"] = [
    1 - len(r_.split())/max(1, len(d_.split())) for r_, d_ in zip(df.desc_resid, df.desc_c)]
U_res, _ = vecs("desc_resid", min_df=5)
LOG["boilerplate"] = dict(n_boiler_sentences=len(boiler),
                          mean_boiler_share=float(df.boiler_share.mean()),
                          resid_vocab=U_res.shape[1])
tick("boilerplate")

sector_code = pd.Categorical(df.sector).codes.astype(int); NS = sector_code.max()+1
idx_by_s = [np.where(sector_code == s)[0] for s in range(NS)]

def active_pool(Umat, ends):
    """当前池：上架时仍在架的同行业贷款。返回 (计数, 平均余弦)。"""
    n = len(df); C = np.zeros(n); H = np.full(n, np.nan)
    vocab = Umat.shape[1]
    psum = np.zeros((NS, vocab)); pcnt = np.zeros(NS, int); heap = []
    for i in range(n):
        ti, s = post_h[i], sector_code[i]
        while heap and heap[0][0] <= ti:
            _, j, sj = heapq.heappop(heap)
            psum[sj] -= Umat[j].toarray()[0]; pcnt[sj] -= 1
        c = pcnt[s]; C[i] = c
        if c > 0: H[i] = float(Umat[i].multiply(psum[s].reshape(1,-1)).sum()/c)
        psum[s] += Umat[i].toarray()[0]; pcnt[s] += 1
        heapq.heappush(heap, (ends[i], i, s))
    return C, H

def window_pool(Umat, lo_days, hi_days, decay=True, forward=False):
    """滞后/前向窗口池：只依赖发布时间（status-agnostic）。"""
    n = len(df); Vv = np.zeros(n); Gg = np.full(n, np.nan); Nn = np.zeros(n, int)
    lam = np.log(2)/(HALFLIFE_D*24) if decay else 0.0
    for s in range(NS):
        ids = idx_by_s[s]; ts = post_h[ids]; Us = Umat[ids]
        if forward:
            lo = np.searchsorted(ts, ts + lo_days*24); hi = np.searchsorted(ts, ts + hi_days*24)
        else:
            lo = np.searchsorted(ts, ts - hi_days*24); hi = np.searchsorted(ts, ts - lo_days*24)
        for k in range(len(ids)):
            if hi[k] <= lo[k]: continue
            sl = slice(lo[k], hi[k])
            dt = np.abs(ts[sl] - ts[k]) - lo_days*24
            w = np.exp(-lam*dt)
            W = w.sum()
            if W <= 0: continue
            wm = sparse.csr_matrix(w.reshape(1,-1)) @ Us[sl]
            Vv[ids[k]] = W; Nn[ids[k]] = hi[k]-lo[k]
            Gg[ids[k]] = float(Us[k].multiply(wm).sum()/W)
    return Vv, Gg, Nn

C_use, H_use = active_pool(U_use, end_h_filled);            tick("pool_active_use")
C_des, H_des = active_pool(U_desc, end_h_filled);           tick("pool_active_desc")
_,     H_res = active_pool(U_res,  end_h_filled);           tick("pool_active_resid")
V_use, G_use, Nlag = window_pool(U_use, L_DAYS, L_DAYS+WIN_D);   tick("pool_lag_use")
V_des, G_des, _    = window_pool(U_desc, L_DAYS, L_DAYS+WIN_D);  tick("pool_lag_desc")
Cm, Hm, Nmir = window_pool(U_use, 0, MIRROR_D, decay=False);     tick("pool_mirror")
Vf, Gf, _ = window_pool(U_use, L_DAYS, L_DAYS+WIN_D, forward=True); tick("pool_forward")

# 平台级池（RQ4：注意力市场在行业级还是平台级）
sector_code_bak = sector_code.copy()
sector_code = np.zeros(len(df), int); NS = 1; idx_by_s = [np.arange(len(df))]
C_plat, H_plat = active_pool(U_use, end_h_filled); tick("pool_platform")
sector_code = sector_code_bak; NS = sector_code.max()+1
idx_by_s = [np.where(sector_code == s)[0] for s in range(NS)]

pools = pd.DataFrame(dict(
    C_use=C_use, H_use=H_use, C_des=C_des, H_des=H_des, H_res=H_res,
    V_use=V_use, G_use=G_use, V_des=V_des, G_des=G_des,
    Cm=Cm, Hm=Hm, Vf=Vf, Gf=Gf, Nlag=Nlag, Nmir=Nmir,
    C_plat=C_plat, H_plat=H_plat))
LOG["pool_coverage"] = dict(
    mean_active_pool=float(C_use.mean()),
    share_active_ge10=float((C_use >= MIN_POOL).mean()),
    share_active_ge5=float((C_use >= 5).mean()),
    share_active_zero=float((C_use == 0).mean()),
    mean_lag_pool=float(Nlag.mean()), share_lag_ge10=float((Nlag >= MIN_POOL).mean()),
    mean_mirror_pool=float(Nmir.mean()), share_mirror_ge10=float((Nmir >= MIN_POOL).mean()),
    mean_platform_pool=float(C_plat.mean()),
)
print(json.dumps(LOG["pool_coverage"], indent=1))
pools.to_csv("pipeline_pools.csv", index=False)

# ---- 滞后窗与主动池的重叠（提案要求报告）----
still_active = []
for s in range(NS):
    ids = idx_by_s[s]; ts = post_h[ids]
    lo = np.searchsorted(ts, ts - (L_DAYS+WIN_D)*24); hi = np.searchsorted(ts, ts - L_DAYS*24)
    for k in range(len(ids)):
        if hi[k] <= lo[k]: continue
        sl = ids[lo[k]:hi[k]]
        still_active.append(float((end_h_filled[sl] > ts[k]).mean()))
LOG["lag_overlap_share_still_active"] = float(np.mean(still_active)) if still_active else 0.0
print("滞后池中上架时仍在架的比例:", round(LOG["lag_overlap_share_still_active"], 4))
tick("overlap_check")

# =====================================================================
# DAY 4–5 — 估计
# =====================================================================
print("== DAY 4-5 估计 ==")
def z(x):
    x = np.asarray(x, float); m = np.nanmean(x); s = np.nanstd(x)
    return (x-m)/s if s > 0 else x*0

df["week"] = ((post_h - post_h.min())//(24*7)).astype(int)
df["year"] = df.fundraisingDate.dt.year
fe_specs = dict(country=pd.Categorical(df.country_name).codes,
                activity=pd.Categorical(df.activity).codes,
                week=df.week.values)

def build_fe(mask):
    mats = []
    for name, codes in fe_specs.items():
        c = pd.Categorical(codes[mask]).codes
        k = c.max()+1
        if k > 1:
            M = sparse.csr_matrix((np.ones(mask.sum()), (np.arange(mask.sum()), c)),
                                  shape=(mask.sum(), k))
            mats.append(M[:, 1:])           # 去掉一列避免共线
    return sparse.hstack(mats).tocsr()

def ols_fe(y, Xd, mask, cl1, cl2, names):
    """稀疏 OLS + 双向聚类标准误（country × week）。"""
    Xf = build_fe(mask)
    X = sparse.hstack([sparse.csr_matrix(Xd), Xf,
                       sparse.csr_matrix(np.ones((mask.sum(), 1)))]).tocsr()
    XtX = (X.T @ X).toarray(); Xty = X.T @ y
    XtX_inv = np.linalg.pinv(XtX); b = XtX_inv @ Xty
    e = y - X @ b
    def meat(g):
        gg = pd.Categorical(g).codes; ng = gg.max()+1
        G = sparse.csr_matrix((np.ones(len(gg)), (gg, np.arange(len(gg)))), shape=(ng, len(gg)))
        S = (G @ X.multiply(e[:, None])).toarray()
        return S.T @ S, ng
    M1, n1 = meat(cl1); M2, n2 = meat(cl2); M12, _ = meat([f"{a}_{b_}" for a, b_ in zip(cl1, cl2)])
    M = M1 + M2 - M12
    V = XtX_inv @ M @ XtX_inv
    se = np.sqrt(np.clip(np.diag(V), 0, None))
    k = len(names)
    return dict(names=names, coef=b[:k].tolist(), se=se[:k].tolist(),
                t=(b[:k]/np.maximum(se[:k], 1e-12)).tolist(),
                n=int(mask.sum()), V=V[:k, :k], b_full=b, X=X, resid=e)

def run(label, cols, extra=None, mask=None, min_pool_col="C_use", min_pool=MIN_POOL):
    m = df.funded.values.copy()
    if min_pool_col is not None: m &= (pools[min_pool_col].values >= min_pool)
    for c in cols: m &= np.isfinite(pools[c].values)
    m &= np.isfinite(CTRL).all(axis=1)
    if mask is not None: m &= mask
    y = np.log1p(df.hours.values[m])
    Zc, Zh = z(np.log1p(pools[cols[0]].values))[m], z(pools[cols[1]].values)[m]
    Zv, Zg = z(np.log1p(pools[cols[2]].values))[m], z(pools[cols[3]].values)[m]
    base = np.column_stack([Zc, Zh, Zc*Zh, Zv, Zg, Zv*Zg])
    names = ["C", "H", "CxH", "V", "G", "VxG"]
    X = np.column_stack([base, CTRL[m]]); names = names + CTRL_NAMES
    if extra is not None:
        X = np.column_stack([X, extra[m]]); names = names + extra_names
    r = ols_fe(y, X, m, df.country_name.values[m], df.week.values[m], names)
    r["label"] = label
    return r

CTRL = np.column_stack([
    np.log(df.loanAmount.values/300.0), (df.borrowerCount.values > 1).astype(float),
    (df.gender.values == "male").astype(float), df.lenderRepaymentTerm.values - 12.0,
    (df.repaymentInterval.values == "at_end").astype(float),
    np.clip((df.fundraisingDate - df.disbursalDate).dt.days.values, -60, 120)/30.0,
])
CTRL_NAMES = ["logAmt", "group", "male", "term", "atEnd", "disbGap"]

RES = {}
t_est = time.time()
RES["main_use"]   = run("主模型（use 文本，行业池）", ["C_use","H_use","V_use","G_use"])
tick("est_main_use")
RES["main_desc"]  = run("description 文本", ["C_des","H_des","V_des","G_des"], min_pool_col="C_des")
tick("est_main_desc")
RES["resid_desc"] = run("description 去模板残差", ["C_des","H_res","V_des","G_des"], min_pool_col="C_des")
tick("est_resid")
RES["mirror"]     = run("镜像池（前14天发布，不论状态）", ["Cm","Hm","V_use","G_use"],
                        min_pool_col="Cm")
tick("est_mirror")
RES["platform"]   = run("平台级池", ["C_plat","H_plat","V_use","G_use"], min_pool_col="C_plat")
tick("est_platform")
RES["placebo"]    = run("安慰剂（前向窗口）", ["C_use","H_use","Vf","Gf"])
tick("est_placebo")
RES["nopool_thr"] = run("不设池规模门槛", ["C_use","H_use","V_use","G_use"], min_pool=0)
RES["thr5"]       = run("池规模门槛=5", ["C_use","H_use","V_use","G_use"], min_pool=5)
tick("est_thresholds")

# ---- RQ3：年度交互 ----
yr = df.year.values - 2016
m = df.funded.values & (pools.C_use.values >= MIN_POOL) & ~np.isnan(pools.H_use.values)
Zc, Zh = z(np.log1p(pools.C_use.values)), z(pools.H_use.values)
Zv, Zg = z(np.log1p(pools.V_use.values)), z(pools.G_use.values)
extra = np.column_stack([Zc*Zh*yr, Zv*Zg*yr, Zc*yr, Zh*yr, Zv*yr, Zg*yr, ])
extra_names = ["CxHxYr", "VxGxYr", "CxYr", "HxYr", "VxYr", "GxYr"]
RES["rq3"] = run("RQ3 年度交互", ["C_use","H_use","V_use","G_use"], extra=extra)
tick("est_rq3")

# ---- RQ4：分行业 ----
RES["rq4"] = {}
for s in df.sector.value_counts().index[:6]:
    try:
        RES["rq4"][s] = run(f"RQ4 {s}", ["C_use","H_use","V_use","G_use"],
                            mask=(df.sector.values == s))
    except Exception as e:
        RES["rq4"][s] = dict(error=str(e))
tick("est_rq4")

# ---- 未募满：删失（Tobit 风格：用 AFT 近似——右删失于 L）----
from scipy.optimize import minimize
def aft_censored(cols):
    m = (pools[cols[0]].values >= MIN_POOL) & ~np.isnan(pools[cols[1]].values)
    y = np.where(df.funded.values, df.hours.values, L_H)
    yl = np.log1p(np.where(np.isnan(y), L_H, y))[m]
    d = df.funded.values[m].astype(float)
    Zc, Zh = z(np.log1p(pools[cols[0]].values))[m], z(pools[cols[1]].values)[m]
    Zv, Zg = z(np.log1p(pools[cols[2]].values))[m], z(pools[cols[3]].values)[m]
    X = np.column_stack([np.ones(m.sum()), Zc, Zh, Zc*Zh, Zv, Zg, Zv*Zg, CTRL[m]])
    from scipy.stats import norm
    def nll(p):
        b, ls = p[:-1], p[-1]; s = np.exp(ls); r_ = (yl - X@b)/s
        return -(d*(norm.logpdf(r_)-ls) + (1-d)*norm.logsf(r_)).sum()
    p0 = np.append(np.linalg.lstsq(X, yl, rcond=None)[0], 0.0)
    o = minimize(nll, p0, method="L-BFGS-B")
    return dict(names=["const","C","H","CxH","V","G","VxG"]+CTRL_NAMES,
                coef=o.x[:7+len(CTRL_NAMES)].tolist(), n=int(m.sum()), sigma=float(np.exp(o.x[-1])))
RES["aft_censored"] = aft_censored(["C_use","H_use","V_use","G_use"])
tick("est_aft")

TIMING["total"] = round(time.time()-T0, 1)
def slim(r):
    if "coef" not in r: return r
    return {k: r[k] for k in ("label","names","coef","se","t","n") if k in r}
out = dict(log=LOG, timing=TIMING,
           results={k: (slim(v) if isinstance(v, dict) and "coef" in v
                        else {kk: slim(vv) for kk, vv in v.items()} if isinstance(v, dict) else v)
                    for k, v in RES.items()})
json.dump(out, open("pipeline_results.json","w"), indent=1, ensure_ascii=False, default=float)
print("\n=== 耗时 ==="); print(json.dumps(TIMING, indent=1))
