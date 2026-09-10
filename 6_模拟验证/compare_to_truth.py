"""对答案：把分析流程的估计与植入的真值逐项比对。"""
import json, numpy as np, pandas as pd
R = json.load(open("pipeline_results.json")); M = json.load(open("kiva_sim_meta.json"))
T = M["TRUE_STANDARDISED"]; truth = pd.read_csv("kiva_sim_truth.csv")
pools = pd.read_csv("pipeline_pools.csv")
d = pd.DataFrame(pd.read_pickle("kiva_sim_20k.pkl"))
d["fundraisingDate"] = pd.to_datetime(d.fundraisingDate, utc=True)
d = d.sort_values("fundraisingDate", ignore_index=True)
truth = truth.set_index("id").loc[d.id].reset_index()

TRUE_ORDER = ["b1_C","b2_H","b3_CH","b4_V","b5_G","b6_VG"]
LAB = ["C 市场拥挤","H 叙事同质度","C×H 主动饱和","V 近期上架量","G 近期同质度","V×G 近期饱和"]

def tab(key, title):
    r = R["results"][key]
    if "coef" not in r: return
    idx = {n: i for i, n in enumerate(r["names"])}
    print(f"\n### {title}   (N={r['n']})")
    print(f"{'参数':<16}{'真值':>9}{'估计':>9}{'标准误':>9}{'t':>7}{'偏差':>9}{'覆盖真值':>9}")
    for k, nm, lb in zip(TRUE_ORDER, ["C","H","CxH","V","G","VxG"], LAB):
        i = idx[nm]; b, se = r["coef"][i], r["se"][i]; tv = T[k]
        cov = "是" if abs(b - tv) <= 1.96*se else "否"
        print(f"{lb:<16}{tv:>9.4f}{b:>9.4f}{se:>9.4f}{r['t'][i]:>7.2f}{b-tv:>9.4f}{cov:>9}")

print("="*78); print("真值（标准化尺度）:", {k: round(v,4) for k,v in T.items()})
print("样本量:", M["n"], "| 未募满:", f"{M['pct_unfunded']:.1%}",
      "| 主动池均值:", round(M["mean_active_pool"],1))
print("="*78)
for k, t in [("main_use","主模型：use 文本 + 行业主动池"),
             ("main_desc","description 文本"),
             ("resid_desc","description 去模板残差"),
             ("mirror","镜像池（前14天发布，不论后续状态）"),
             ("platform","平台级池"),
             ("placebo","安慰剂：前向窗口"),
             ("nopool_thr","不设池规模门槛"),
             ("thr5","池规模门槛 = 5")]:
    tab(k, t)

# ---- 安慰剂判据 ----
mm = R["results"]["main_use"]; pl = R["results"]["placebo"]
im = {n:i for i,n in enumerate(mm["names"])}; ip = {n:i for i,n in enumerate(pl["names"])}
bwd, fwd = mm["coef"][im["VxG"]], pl["coef"][ip["VxG"]]
print(f"\n### 安慰剂判据：前向 V×G = {fwd:.4f}，后向 V×G = {bwd:.4f}，"
      f"比值 = {fwd/bwd if bwd else float('nan'):.2f}（提案要求 < 1/3）")

# ---- RQ3 ----
r3 = R["results"]["rq3"]; i3 = {n:i for i,n in enumerate(r3["names"])}
print("\n### RQ3 年度演化（真值：主动饱和年增 5.5%，近期饱和年增 13.0%）")
for nm, lb, base_true, g in [("CxHxYr","C×H × 年份", T["b3_CH"], 0.055),
                             ("VxGxYr","V×G × 年份", T["b6_VG"], 0.130)]:
    i = i3[nm]; b, se = r3["coef"][i], r3["se"][i]
    print(f"{lb:<14} 真值≈{base_true*g:+.4f}/年   估计={b:+.4f} (se {se:.4f}, t {r3['t'][i]:+.2f})")

# ---- RQ4 ----
print("\n### RQ4 分行业（真值：各行业同一组 β，不存在真实异质性）")
print(f"{'行业':<14}{'N':>7}{'C×H':>10}{'se':>8}{'t':>7}{'V×G':>10}{'se':>8}{'t':>7}")
for s, r in R["results"]["rq4"].items():
    if "coef" not in r: print(f"{s:<14} 估计失败"); continue
    i = {n:j for j,n in enumerate(r["names"])}
    print(f"{s:<14}{r['n']:>7}{r['coef'][i['CxH']]:>10.4f}{r['se'][i['CxH']]:>8.4f}"
          f"{r['t'][i['CxH']]:>7.2f}{r['coef'][i['VxG']]:>10.4f}{r['se'][i['VxG']]:>8.4f}"
          f"{r['t'][i['VxG']]:>7.2f}")

# ---- 删失模型 ----
ac = R["results"]["aft_censored"]; ia = {n:i for i,n in enumerate(ac["names"])}
mo = R["results"]["main_use"]; io = {n:i for i,n in enumerate(mo["names"])}
print("\n### 删失（AFT）vs 仅用已募满样本的 OLS")
print(f"{'参数':<10}{'真值':>9}{'OLS':>9}{'AFT':>9}")
for k, nm in zip(TRUE_ORDER, ["C","H","CxH","V","G","VxG"]):
    print(f"{nm:<10}{T[k]:>9.4f}{mo['coef'][io[nm]]:>9.4f}{ac['coef'][ia[nm]]:>9.4f}")

# ---- 测量质量：分析端构造的池 vs 真实池 ----
print("\n### 测量还原度（分析端 vs 生成端真值）")
def cc(a, b):
    m = np.isfinite(a) & np.isfinite(b)
    return np.corrcoef(a[m], b[m])[0,1]
print(f"  主动池计数 C：corr = {cc(pools.C_use.values, truth.C_true.values):.4f}")
print(f"  主动池同质度 H（use）：corr = {cc(pools.H_use.values, truth.H_true.values):.4f}")
print(f"  主动池同质度 H（description）：corr = {cc(pools.H_des.values, truth.H_true.values):.4f}")
print(f"  滞后池 V：corr = {cc(pools.V_use.values, truth.V_true.values):.4f}")
print(f"  滞后池 G（use）：corr = {cc(pools.G_use.values, truth.G_true.values):.4f}")
print(f"  滞后池 G（description）：corr = {cc(pools.G_des.values, truth.G_true.values):.4f}")

print("\n### 内生性：行业-周冲击（分析端不可观测）与各测量的相关")
sh = truth.sector_week_shock.values
for nm, v in [("主动池 C", np.log1p(pools.C_use.values)), ("主动池 H", pools.H_use.values),
              ("镜像池 C", np.log1p(pools.Cm.values)),   ("镜像池 H", pools.Hm.values),
              ("滞后池 V", np.log1p(pools.V_use.values)),("滞后池 G", pools.G_use.values)]:
    print(f"  corr(冲击, {nm}) = {cc(sh, v):+.4f}")

print("\n### 机构混杂：模板强度 / 机构效应 与同质度的相关")
for nm, v in [("H(use)", pools.H_use.values), ("H(description)", pools.H_des.values),
              ("H(去模板残差)", pools.H_res.values)]:
    print(f"  corr(模板强度, {nm}) = {cc(truth.tmpl_intensity.values, v):+.4f}   "
          f"corr(机构效应, {nm}) = {cc(truth.partner_effect.values, v):+.4f}")

print("\n### Day1 审计输出")
a = R["log"]["day1_audit"]
for k in ["status_mix","pct_no_raised_date","terminal_date_unverifiable_share",
          "whySpecial_unique","use_unique_per_row","dup_description","L_days_frozen"]:
    print(f"  {k}: {a.get(k)}")
print("  滞后池中仍在架比例:", R["log"]["lag_overlap_share_still_active"])
print("  模板识别:", R["log"]["boilerplate"])
print("  池覆盖:", R["log"]["pool_coverage"])
print("\n### 耗时（20,000 条）"); print(json.dumps(R["timing"], indent=1, ensure_ascii=False))
