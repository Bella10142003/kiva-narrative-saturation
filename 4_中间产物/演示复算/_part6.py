import sys, gc, numpy as np, pandas as pd, pyfixest as pf
from pathlib import Path
from scipy import stats
MODE = sys.argv[1]
SRC = Path(__file__).resolve().parents[1] / "我算出来的结果/data/model_data.parquet"
OUT = Path(__file__).resolve().parent / "outputs"
need = ['log_funding_hours','C_active','H_active_raw','V_lag','G_lag_raw','log_loan_amount',
        'log_borrower_count','log_repayment_term','log_platform_posting_7d','gender',
        'repaymentInterval','posting_dow','posting_hour','country_name','activity','week_id',
        'analysis_washin_eligible','raw_text_nonempty','pool_size_active','lag_kish_n','fundraising_year']
if MODE == 'dom': need.append('fundraising_ts')
d = pd.read_parquet(SRC, columns=need)
d = d[d.analysis_washin_eligible & d.raw_text_nonempty & (d.pool_size_active>=10) &
      (d.lag_kish_n>=10) & d.fundraising_year.between(2016,2024)].copy()
for c in ['analysis_washin_eligible','raw_text_nonempty','pool_size_active','lag_kish_n','fundraising_year']:
    del d[c]
for s_,t_ in [('C_active','Cz'),('H_active_raw','Hz'),('V_lag','Vz'),('G_lag_raw','Gz')]:
    d[t_]=(d[s_]-d[s_].mean())/d[s_].std(ddof=0); del d[s_]
d['CH']=d.Cz*d.Hz; d['VG']=d.Vz*d.Gz
FE = "country_name+activity+week_id"
if MODE=='dom':
    d['dom']=d.fundraising_ts.dt.tz_convert('US/Pacific').dt.day.astype(str); del d['fundraising_ts']
    FE += "+dom"
gc.collect()
BASE=("log_funding_hours ~ Cz+Hz+CH+Vz+Gz+VG+log_loan_amount+log_borrower_count"
      "+log_repayment_term+log_platform_posting_7d+gender+repaymentInterval+posting_dow+posting_hour")
fit = pf.feols(f"{BASE} | {FE}", d, vcov={"CRV1":"country_name+week_id"}, fixef_rm="singleton")
t = fit.tidy()
lbl = "baseline (country+activity+week FE)" if MODE=='base' else "+ day-of-month FE (Pacific)"
rows=[{'model':lbl,'term':k,'estimate':t.loc[k,'Estimate'],'std_error':t.loc[k,'Std. Error'],
       'p_value':t.loc[k,'Pr(>|t|)'],'n':int(fit._N)} for k in ["Cz","Hz","CH","Vz","Gz","VG"]]
pd.DataFrame(rows).to_csv(OUT/f"_fe_{MODE}.csv", index=False)
print(lbl, "C x H =", round(float(t.loc['CH','Estimate']),4), "N =", int(fit._N), flush=True)
if MODE=='base':
    names=list(fit._coefnames); V=np.asarray(fit._vcov); b=np.asarray(fit._beta_hat).ravel()
    try: G=int(np.min(fit._G)-1)
    except Exception: G=45
    def wald(terms,label):
        idx=[names.index(x) for x in terms]
        R=np.zeros((len(idx),len(names)))
        for i,j in enumerate(idx): R[i,j]=1
        Rb=R@b; W=float(Rb@np.linalg.solve(R@V@R.T,Rb)); q=len(idx); F=W/q
        return {'test':label,'restrictions':q,'chi2':W,'chi2_p':stats.chi2.sf(W,q),
                'F':F,'F_dof2':G,'F_p':stats.f.sf(F,q,G)}
    jt=pd.DataFrame([wald(['Vz','Gz','VG'],"RQ2 pre-registered: V = G = V x G = 0"),
                     wald(['VG'],"V x G alone"),
                     wald(['Cz','Hz','CH'],"RQ1: C = H = C x H = 0"),
                     wald(['CH'],"C x H alone")])
    jt.to_csv(OUT/"rq_joint_tests.csv", index=False)
    print(jt.to_string(index=False), flush=True)
