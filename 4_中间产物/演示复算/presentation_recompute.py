"""
演示层数字的可复现脚本（PPTX v2.7）。
覆盖交付包 outputs/ 未包含、但幻灯片上出现的每一个数字：
  S2 年度中位筹款时长与年度均值 · S6/A6 月内日历脉冲与星期/小时指数
  S6 月内日期固定效应稳健性 · S7 分板块同质性存活率 · A4 RQ2 预注册联合检验
用法：  python3 presentation_recompute.py  [MODEL_DATA_PARQUET]
输出：  ./outputs/*.csv
依赖：  pandas pyarrow numpy scipy pyfixest
口径锁定：月内日期 = 太平洋日历日；星期/小时 = UTC 的 posting_dow / posting_hour；
         指数 = 该日日均条数 ÷ 全期日均条数（每月均值 = 1.00）。
"""
import sys, calendar, json
from pathlib import Path
import numpy as np, pandas as pd

SRC = Path(sys.argv[1] if len(sys.argv) > 1
           else Path(__file__).resolve().parents[1] / "我算出来的结果/data/model_data.parquet")
OUT = Path(__file__).resolve().parent / "outputs"; OUT.mkdir(parents=True, exist_ok=True)
def save(df, name): df.to_csv(OUT / name, index=False); print(f"  -> outputs/{name}  ({len(df)} rows)")

MODEL_FILTER = "analysis_washin_eligible & raw_text_nonempty & pool_size_active>=10 & lag_kish_n>=10"
print(f"reading {SRC}")

# ---------- 1. 年度中位数与年度均值（S2 / A7 右panel） ----------
cols = ['fundraising_ts','raised_ts','fundraising_year','funding_hours','analysis_washin_eligible',
        'raw_text_nonempty','pool_size_active','lag_kish_n','C_active','H_active_raw',
        'H_active_residual','boilerplate_share','sector','country_name','activity']
df = pd.read_parquet(SRC, columns=cols)
m = df.query(MODEL_FILTER).copy()
m['q'] = m.fundraising_ts.dt.quarter
print(f"model sample all years = {len(m):,}; train 2016-2024 = {m.fundraising_year.between(2016,2024).sum():,}")

yearly = m.groupby('fundraising_year').agg(
    loans=('funding_hours','size'), median_funding_hours=('funding_hours','median'),
    mean_H=('H_active_raw','mean'), mean_C=('C_active','mean'),
    median_pool=('pool_size_active','median'), mean_boilerplate=('boilerplate_share','mean')).reset_index()
q13 = m[m.q<=3].groupby('fundraising_year').agg(
    loans_q1q3=('funding_hours','size'),
    median_funding_hours_q1q3=('funding_hours','median')).reset_index()
save(yearly.merge(q13, on='fundraising_year'), "year_profile.csv")
a, b = [float(m[(m.fundraising_year==y)&(m.q<=3)].funding_hours.median()) for y in (2024,2025)]
print(f"  S2: Q1-Q3 median {a:.2f} -> {b:.2f} h  ({(b/a-1)*100:.2f}%)")

# ---------- 2. 月内日历脉冲（S6 / A6 上两panel） ----------
def dom_index(ts, lo, hi):
    s = ts[(ts.dt.year>=lo)&(ts.dt.year<=hi)]
    n = s.dt.day.value_counts().sort_index()
    occ = pd.Series(0, index=range(1,32))
    for y, mo in sorted({(y,mo) for y,mo in zip(s.dt.year, s.dt.month)}):
        occ.loc[1:calendar.monthrange(y,mo)[1]] += 1
    daily = n/occ
    return pd.DataFrame({'day':daily.index,'loans':n.values,'daily_mean':daily.values,
                         'index':(daily/daily.mean()).values,'share_pct':(n/n.sum()*100).values})

f = df.fundraising_ts.dt.tz_convert('US/Pacific'); r = df.raised_ts.dt.tz_convert('US/Pacific')
frames = []
for lo, hi in [(2024,2025),(2016,2025)]:
    arr, comp = dom_index(f,lo,hi), dom_index(r,lo,hi)
    t = arr.rename(columns={'loans':'arrivals','daily_mean':'arrivals_per_day',
                            'index':'arrivals_index','share_pct':'arrivals_share_pct'})
    t['completions_index'] = comp['index'].values
    t['completions_per_day'] = comp['daily_mean'].values
    t['net_per_day'] = t.arrivals_per_day - t.completions_per_day
    t.insert(0,'period',f"{lo}-{hi}")
    frames.append(t)
cal = pd.concat(frames, ignore_index=True); save(cal, "calendar_day_of_month_index.csv")
for p in cal.period.unique():
    s = cal[cal.period==p]
    print(f"  {p}: arrivals peak day {int(s.loc[s.arrivals_index.idxmax(),'day'])} "
          f"= {s.arrivals_index.max():.3f}; completions peak day "
          f"{int(s.loc[s.completions_index.idxmax(),'day'])} = {s.completions_index.max():.3f}")

# ---------- 3. 星期 / 小时指数（A6 下两panel，UTC） ----------
mm = df.query(MODEL_FILTER)
dow = pd.read_parquet(SRC, columns=['posting_dow','posting_hour','analysis_washin_eligible',
                                    'raw_text_nonempty','pool_size_active','lag_kish_n']).query(MODEL_FILTER)
DOW = {0:'Sunday',1:'Monday',2:'Tuesday',3:'Wednesday',4:'Thursday',5:'Friday',6:'Saturday'}
v = dow.posting_dow.value_counts().sort_index()
save(pd.DataFrame({'duckdb_dow_code':v.index,'weekday':[DOW[i] for i in v.index],
                   'loans':v.values,'index':(v/v.mean()).values}), "weekday_index.csv")
h = dow.posting_hour.value_counts().sort_index()
save(pd.DataFrame({'hour_utc':h.index,'loans':h.values,'index':(h/h.mean()).values}), "hour_index.csv")
print("  ⚠ DuckDB EXTRACT(DOW): 0 = Sunday。画图时不要按 0=Monday 贴标签。")

# ---------- 4. 月内日期画像（S6 备注：18 号的 H 与在架池） ----------
m24 = m[m.fundraising_year.isin([2024,2025])].copy()
m24['dom'] = m24.fundraising_ts.dt.tz_convert('US/Pacific').dt.day
prof = m24.groupby('dom').agg(loans=('H_active_raw','size'), mean_H=('H_active_raw','mean'),
                              median_pool=('pool_size_active','median')).reset_index()
prof['philippines_share_pct'] = [
    (m24[m24.dom==d].country_name.eq('Philippines').mean()*100) for d in prof.dom]
save(prof, "day_of_month_profile_2024_2025.csv")

# ---------- 5. 分板块同质性存活率（S7） ----------
tr = m[m.fundraising_year.between(2016,2024)]
g = tr.groupby('sector').agg(loans=('H_active_raw','size'), mean_H_raw=('H_active_raw','mean'),
                             mean_H_residual=('H_active_residual','mean'),
                             mean_boilerplate=('boilerplate_share','mean')).reset_index()
g['survival_pct'] = g.mean_H_residual/g.mean_H_raw*100
ph = tr[(tr.country_name=='Philippines')&(tr.activity=='General Store')]
rows = [{'sector':'PLATFORM (all)','loans':len(tr),'mean_H_raw':tr.H_active_raw.mean(),
         'mean_H_residual':tr.H_active_residual.mean(),'mean_boilerplate':tr.boilerplate_share.mean(),
         'survival_pct':tr.H_active_residual.mean()/tr.H_active_raw.mean()*100},
        {'sector':'Philippines x General Store','loans':len(ph),'mean_H_raw':ph.H_active_raw.mean(),
         'mean_H_residual':ph.H_active_residual.mean(),'mean_boilerplate':ph.boilerplate_share.mean(),
         'survival_pct':ph.H_active_residual.mean()/ph.H_active_raw.mean()*100}]
save(pd.concat([g.sort_values('survival_pct',ascending=False), pd.DataFrame(rows)], ignore_index=True),
     "sector_homogeneity_survival.csv")

# ---------- 6. 月内日期 FE 稳健性 + RQ2 预注册联合检验 ----------
try:
    import pyfixest as pf
    from scipy import stats
except ImportError:
    print("  pyfixest / scipy 缺失，跳过第 6 部分"); sys.exit(0)

need = ['log_funding_hours','C_active','H_active_raw','V_lag','G_lag_raw','log_loan_amount',
        'log_borrower_count','log_repayment_term','log_platform_posting_7d','gender',
        'repaymentInterval','posting_dow','posting_hour','country_name','activity','week_id',
        'fundraising_ts','analysis_washin_eligible','raw_text_nonempty','pool_size_active',
        'lag_kish_n','fundraising_year']
d = pd.read_parquet(SRC, columns=need).query(MODEL_FILTER)
d = d[d.fundraising_year.between(2016,2024)].copy()
for s_, t_ in [('C_active','Cz'),('H_active_raw','Hz'),('V_lag','Vz'),('G_lag_raw','Gz')]:
    d[t_] = (d[s_]-d[s_].mean())/d[s_].std(ddof=0)
d['CH'] = d.Cz*d.Hz; d['VG'] = d.Vz*d.Gz
d['dom'] = d.fundraising_ts.dt.tz_convert('US/Pacific').dt.day.astype(str)
BASE = ("log_funding_hours ~ Cz+Hz+CH+Vz+Gz+VG+log_loan_amount+log_borrower_count"
        "+log_repayment_term+log_platform_posting_7d+gender+repaymentInterval+posting_dow+posting_hour")
V = {"CRV1":"country_name+week_id"}
fit = pf.feols(BASE+" | country_name+activity+week_id", d, vcov=V, fixef_rm="singleton")
fit_dom = pf.feols(BASE+" | country_name+activity+week_id+dom", d, vcov=V, fixef_rm="singleton")
res = []
for lbl, fo in [("baseline (country+activity+week FE)", fit), ("+ day-of-month FE", fit_dom)]:
    t = fo.tidy()
    for term in ["Cz","Hz","CH","Vz","Gz","VG"]:
        res.append({'model':lbl,'term':term,'estimate':t.loc[term,'Estimate'],
                    'std_error':t.loc[term,'Std. Error'],'p_value':t.loc[term,'Pr(>|t|)'],
                    'n':int(fo._N)})
save(pd.DataFrame(res), "day_of_month_fe_robustness.csv")
print(f"  C×H: baseline {fit.tidy().loc['CH','Estimate']:.4f} -> "
      f"+dom FE {fit_dom.tidy().loc['CH','Estimate']:.4f}")

names = list(fit._coefnames); Vc = np.asarray(fit._vcov); bh = np.asarray(fit._beta_hat).ravel()
G_DOF = int(fit._G.min()-1) if hasattr(fit,"_G") else 45
def wald(terms, label):
    idx = [names.index(t) for t in terms]
    R = np.zeros((len(idx), len(names)))
    for i, j in enumerate(idx): R[i, j] = 1
    Rb = R@bh; W = float(Rb@np.linalg.solve(R@Vc@R.T, Rb)); q = len(idx); F = W/q
    return {'test':label,'restrictions':q,'chi2':W,'chi2_p':stats.chi2.sf(W,q),
            'F':F,'F_dof2':G_DOF,'F_p':stats.f.sf(F,q,G_DOF)}
jt = pd.DataFrame([wald(['Vz','Gz','VG'], "RQ2 pre-registered: V = G = V x G = 0"),
                   wald(['VG'], "V x G alone"),
                   wald(['Cz','Hz','CH'], "RQ1: C = H = C x H = 0"),
                   wald(['CH'], "C x H alone")])
save(jt, "rq_joint_tests.csv")
print(jt.to_string(index=False))
print("\ndone.")
