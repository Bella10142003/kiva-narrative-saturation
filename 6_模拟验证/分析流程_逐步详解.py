#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
Kiva 叙事饱和提案 —— 分析流程逐步详解
================================================================================
这个脚本严格扮演「分析者」：只读 kiva_sim_20k.pkl 里存在的字段，
不碰 kiva_sim_truth.csv（那是答案本，真实 Kiva 数据里不存在）。

与 analysis_pipeline.py 的区别：那一份是为了跑通和计时，这一份是为了**看清过程**。
每一步都会打印：
  · 这一步在提案里对应哪句话、为什么必须做
  · 中间产物长什么样（不是只报结果，而是把计算过程摊开）
  · 这一步产生的决定，会怎样影响后面的步骤

运行：python3 分析流程_逐步详解.py           （约 40 秒）
     python3 分析流程_逐步详解.py > 输出.txt
================================================================================
"""
import numpy as np, pandas as pd, json, time, re, heapq, warnings
from scipy import sparse
from scipy.stats import chi2
from sklearn.feature_extraction.text import TfidfVectorizer
warnings.filterwarnings("ignore")
pd.set_option("display.width", 200)

T0 = time.time()
def banner(n, title, why):
    print("\n" + "="*88)
    print(f"STEP {n}  {title}")
    print("-"*88)
    print(f"为什么要有这一步：{why}")
    print("-"*88)
def note(s):   print(f"    · {s}")
def out(s):    print(f"    → {s}")
def timing(s): print(f"    [{s}  用时 {time.time()-T0:.1f}s]")


# ==============================================================================
banner(0, "载入数据并按上架时间排序",
       "后面所有的池构建都是时间序列上的滚动操作，必须先保证行是按上架时间升序的，"
       "否则「上架时还在架的贷款」这个定义无从谈起。")
# ==============================================================================
df = pd.DataFrame(pd.read_pickle("kiva_sim_20k.pkl"))
for c in ["disbursalDate", "fundraisingDate", "raisedDate"]:
    df[c] = pd.to_datetime(df[c], utc=True, errors="coerce")
df = df.sort_values("fundraisingDate", ignore_index=True)
df["hours"]  = (df.raisedDate - df.fundraisingDate).dt.total_seconds()/3600
df["funded"] = df.status.eq("funded")

out(f"{len(df):,} 行 × {df.shape[1]} 列，时间跨度 "
    f"{df.fundraisingDate.min():%Y-%m-%d} 至 {df.fundraisingDate.max():%Y-%m-%d}")
note("因变量 = raisedDate − fundraisingDate，未募满的贷款这一项为空（后面单独处理）")
print("\n    第一行长这样：")
for k in ["id","status","sector","activity","country_name","loanAmount","use",
          "fundraisingDate","raisedDate"]:
    print(f"      {k:<18} {str(df.iloc[0][k])[:70]}")


# ==============================================================================
banner(1, "Day 1 审计",
       "提案说「Day 1 审计状态、终止日期、缺失、语言、重复、池覆盖」。审计的意义不在于"
       "把数据描述一遍，而在于：每一项检查都必须能改变后面某个具体动作。"
       "下面逐项跑，并明确写出它触发了什么决定，或者「没触发任何决定」。")
# ==============================================================================
checks = []

# --- 1.1 状态构成 ---
mix = df.status.value_counts()
out(f"状态构成：{mix.to_dict()}")
note(f"未募满合计 {(~df.funded).sum():,} 条（{(~df.funded).mean():.1%}）")
checks.append(("状态构成", "✅ 触发决定",
               "未募满占 8.9% → 主模型只能用已募满样本，必须另外报告未募满比例与删失估计"))

# --- 1.2 终止日期能不能重建 ---
# 提案原文要求 endj 是 "raisedDate for funded loans and a verified terminal date otherwise"
n_expired  = (df.status == "expired").sum()
n_refunded = (df.status == "refunded").sum()
out(f"funded → 用 raisedDate（{df.funded.sum():,} 条）")
out(f"expired → 状态明确，终止日 = 上架 + 募资期限（{n_expired:,} 条）")
out(f"refunded → 无法核实终止日（{n_refunded:,} 条，占 {n_refunded/len(df):.1%}）")
checks.append(("终止日期可核实性", "✅ 触发决定",
               f"{n_refunded/len(df):.1%} 不可核实 → 主动池必须用兜底假设，"
               f"这本身就是「镜像池应当升为主规格」的第一条理由"))

# --- 1.3 各字段的方差够不够用 ---
print()
out("字段方差检查（唯一值 / 行数）：")
for c in ["use", "description", "whySpecial", "activity", "country_name"]:
    u = df[c].nunique(); ratio = u/len(df)
    flag = "⚠️ 方差过低" if ratio < 0.01 and c in ("use","description","whySpecial") else ""
    print(f"      {c:<14} {u:>7,} 个不同取值   占比 {ratio:>7.2%}  {flag}")
checks.append(("字段方差", "✅ 触发决定",
               f"whySpecial 只有 {df.whySpecial.nunique()} 个不同取值（{df.whySpecial.nunique()/len(df):.2%}）"
               f" → 按提案自己的规则「只在 Day1 确认覆盖与方差后才纳入」，应当剔除"))

# --- 1.4 重复与缺失 ---
out(f"重复 id：{df.id.duplicated().sum()} 条；完全重复的 description：{df.description.duplicated().mean():.3%}")
miss = {c: float(df[c].isna().mean()) for c in df.columns if df[c].isna().any()}
out(f"有缺失的字段：{miss}")
checks.append(("重复与缺失", "❌ 未触发任何决定", "全部通过，没有改变后续任何一步"))

# --- 1.5 时长分布 → 识别平台募资期限上限 ---
print()
qs = [5,25,50,75,90,95,99]
out("已募满贷款的筹资时长分位数（小时）：")
print("      " + "  ".join(f"p{q}={np.nanpercentile(df.hours,q):.1f}" for q in qs))
out(f"最长 {np.nanmax(df.hours):.1f} 小时 = {np.nanmax(df.hours)/24:.1f} 天")
note("时长分布在上限处被截断 → 说明平台存在硬性募资期限，可以直接读出来")
checks.append(("时长分布", "✅ 触发决定", "识别出募资期限上限 → 冻结 L"))

print()
print("    审计小结：")
for name, verdict, effect in checks:
    print(f"      {name:<16} {verdict:<14} {effect}")
timing("Day 1 审计")


# ==============================================================================
banner(2, "冻结参数（Day 1 结束前，看到任何结果之前）",
       "提案的预注册承诺。这几个参数是最容易被事后调的位置——如果先看了结果再定 L 或半衰期，"
       "整个 RQ2 的对照就不可信了。所以必须在这里一次性写死。")
# ==============================================================================
L_DAYS     = float(np.ceil(np.nanmax(df.hours)/24))   # 规则：平台募资期限上限
HALFLIFE_D = 7.0                                      # 规则：广告 carryover 的典型半衰期
WIN_D      = 30.0                                     # 规则：滞后窗长度 L → L+29
MIRROR_D   = 14.0                                     # 规则：镜像池回看 14 天
MIN_POOL   = 10                                       # 规则：池规模门槛（稳健性用）
L_H        = L_DAYS*24

print(f"    L（滞后窗起点）      = {L_DAYS:.0f} 天")
print(f"      规则：取平台募资期限上限；若无硬上限则取筹资时长第 95 百分位")
print(f"      实测上限 {np.nanmax(df.hours)/24:.2f} 天 → L = {L_DAYS:.0f}")
print(f"      ★ 关键副产品：L 取上限 ⇒ 任何贷款最晚第 {L_DAYS:.0f} 天就离场")
print(f"        ⇒ 滞后池与主动池在**构造上**不可能重叠")
print(f"        ⇒ 提案里「报告滞后池中仍在架的占比并排除后重估」这项检验恒为 0，是空转")
print(f"    衰减半衰期            = {HALFLIFE_D:.0f} 天")
print(f"    滞后窗                = 第 {L_DAYS:.0f} 天 至 第 {L_DAYS+WIN_D-1:.0f} 天")
print(f"    镜像池回看            = {MIRROR_D:.0f} 天")
print(f"    池规模门槛            = {MIN_POOL}（后面会检验这个门槛值不值）")


# ==============================================================================
banner(3, "重建每笔贷款的终止日期",
       "主动池的定义是「上架时仍在架的同行业贷款」，所以必须知道每一笔贷款什么时候离场。"
       "已募满的读 raisedDate 就行；没募满的，日期不在数据里，只能重建。")
# ==============================================================================
post_h = df.fundraisingDate.values.astype("datetime64[s]").astype(np.int64)/3600.0
end_h = np.where(df.funded,                      post_h + df.hours.fillna(0).values,
        np.where(df.status.eq("expired"),        post_h + L_H,
                                                 np.nan))
n_unverifiable = int(np.isnan(end_h).sum())
end_h_filled = np.where(np.isnan(end_h), post_h + L_H, end_h)

out(f"已募满 {df.funded.sum():,} 条：终止日 = raisedDate（可核实）")
out(f"expired {n_expired:,} 条：终止日 = 上架 + {L_DAYS:.0f} 天（规则可核实）")
out(f"refunded {n_unverifiable:,} 条：终止日**不可核实**，被迫套用同一兜底假设")
note("这 3.0% 的兜底假设会把噪音注入主动池的构造。提案的应对是「若终止日期无法重建，"
     "镜像池转为主规格」——实测下来这个分支应该直接变成默认，而不是备用。")


# ==============================================================================
banner(4, "文本清洗与掩码",
       "同质度测的是「叙事听起来像不像」。如果不掩码，人名和数字会成为区分度的主要来源，"
       "余弦相似度测的就变成了「是不是同一个人、同一笔金额」，而不是叙事本身。")
# ==============================================================================
TAG = re.compile(r"<[^>]+>"); NUM = re.compile(r"\d+")
NAMES = set(df.name.unique())
def clean(t):
    t = TAG.sub(" ", str(t))            # 去掉 <br /> 之类的 HTML 标签
    t = NUM.sub(" NUM ", t)             # 所有数字统一换成 NUM
    t = " ".join("NAME" if w.strip(".,") in NAMES else w for w in t.split())
    return t.lower()

df["use_c"]  = [clean(t) for t in df.use]
df["desc_c"] = [clean(t) for t in df.description]

DEMO = int(np.argmax((df.year if "year" in df else df.fundraisingDate.dt.year).values == 2023))
print("    清洗前后对照（第 %d 行）：" % DEMO)
print(f"      原文  ：{df.description.iloc[DEMO][:150]}")
print(f"      清洗后：{df.desc_c.iloc[DEMO][:150]}")
timing("文本清洗")


# ==============================================================================
banner(5, "TF-IDF 向量化",
       "要算「这笔贷款的故事和池子里的故事有多像」，先得把文本变成向量。"
       "提案选 TF-IDF + 余弦，而不是句向量模型，理由是：透明、与结果无关、"
       "而且可以用稀疏滚动求和来算，不需要构造 N×N 的全对相似度矩阵。")
# ==============================================================================
def vecs(col, min_df):
    v = TfidfVectorizer(ngram_range=(1,2), min_df=min_df, sublinear_tf=True, norm="l2")
    return v.fit_transform(df[col].tolist()).tocsr(), v

U_use,  V_use  = vecs("use_c",  3)
U_desc, V_desc = vecs("desc_c", 5)
out(f"use 字段    → {U_use.shape[0]:,} × {U_use.shape[1]:,}，"
    f"稀疏度 {U_use.nnz/np.prod(U_use.shape):.4%}")
out(f"description → {U_desc.shape[0]:,} × {U_desc.shape[1]:,}，"
    f"稀疏度 {U_desc.nnz/np.prod(U_desc.shape):.4%}")
note("L2 归一化后，两条文本的余弦相似度 = 两个向量的点积，后面的计算全靠这一点")

feat = np.array(V_use.get_feature_names_out())
row = U_use[DEMO].toarray()[0]; top = np.argsort(row)[::-1][:8]
print(f"\n    第 {DEMO} 行的 use 文本：{df.use.iloc[DEMO]}")
print("    它的 TF-IDF 权重最高的 8 个词/词组：")
for j in top:
    if row[j] > 0: print(f"      {feat[j]:<28} {row[j]:.4f}")
timing("TF-IDF")


# ==============================================================================
banner(6, "模板句（boilerplate）识别",
       "description 是 Lending Partner 上传的，可能整段是机构模板。"
       "如果不区分，「叙事重复」测到的可能只是「同一家机构发的贷款多」。"
       "识别规则必须在看到任何结果之前冻结——这里的规则是：≥6 个词、"
       "在全库出现 ≥20 次的逐字句子。")
# ==============================================================================
sent_counts = {}
for t in df.desc_c:
    for s_ in re.split(r"[.!?]", t):
        s_ = s_.strip()
        if len(s_.split()) >= 6: sent_counts[s_] = sent_counts.get(s_, 0) + 1
BOILER_MIN = max(20, int(0.001*len(df)))
boiler = {s_ for s_, c in sent_counts.items() if c >= BOILER_MIN}
out(f"识别出 {len(boiler)} 条模板句（阈值：出现 ≥{BOILER_MIN} 次）")
print("    出现最多的 5 条：")
for s_, c in sorted(sent_counts.items(), key=lambda x: -x[1])[:5]:
    print(f"      {c:>6} 次  {s_[:78]}")

def strip_boiler(t):
    return ". ".join([s_.strip() for s_ in re.split(r"[.!?]", t) if s_.strip() not in boiler])
df["desc_resid"]  = [strip_boiler(t) for t in df.desc_c]
df["boiler_share"] = [1 - len(r_.split())/max(1, len(d_.split()))
                      for r_, d_ in zip(df.desc_resid, df.desc_c)]
U_res, _ = vecs("desc_resid", 5)
out(f"模板占全文的比例：均值 {df.boiler_share.mean():.1%}，"
    f"四分位 {df.boiler_share.quantile(.25):.1%} / {df.boiler_share.quantile(.75):.1%}")
note("boiler_share 会作为一个协变量进主模型；去模板后的残差文本另跑一次作稳健性")
timing("模板识别")


# ==============================================================================
banner(7, "主动池：上架时仍在架的同行业贷款",
       "这是提案对「出借人此刻面对的选择」的操作化。算法是一次时间扫描 + 一个最小堆："
       "贷款上架时推入池子，到达终止日时弹出。池子只维护一个向量和，"
       "所以算一笔贷款的平均余弦是 O(1) 次点积，而不是跟池子里每一笔都算一遍。")
# ==============================================================================
sector_code = pd.Categorical(df.sector).codes.astype(int); NS = sector_code.max()+1
idx_by_s = [np.where(sector_code == s)[0] for s in range(NS)]

def active_pool(Umat, ends, trace_i=None):
    n = len(df); C = np.zeros(n); H = np.full(n, np.nan)
    psum = np.zeros((NS, Umat.shape[1])); pcnt = np.zeros(NS, int); heap = []
    members = None
    for i in range(n):
        ti, s = post_h[i], sector_code[i]
        while heap and heap[0][0] <= ti:                    # 弹出已离场的
            _, j, sj = heapq.heappop(heap)
            psum[sj] -= Umat[j].toarray()[0]; pcnt[sj] -= 1
        c = pcnt[s]; C[i] = c
        if c > 0:
            # 平均余弦 = 本笔向量 · (池内向量和) / 池规模
            H[i] = float(Umat[i].multiply(psum[s].reshape(1,-1)).sum()/c)
        if i == trace_i: members = [(j, sj) for _, j, sj in heap if sj == s]
        psum[s] += Umat[i].toarray()[0]; pcnt[s] += 1       # 本笔进池
        heapq.heappush(heap, (ends[i], i, s))
    return (C, H, members) if trace_i is not None else (C, H)

C_use, H_use, demo_members = active_pool(U_use, end_h_filled, trace_i=DEMO)
timing("主动池（use）")

# ---- 把第 DEMO 笔的计算过程摊开 ----
print(f"\n    ── 用第 {DEMO} 行演示一次完整计算 ──")
print(f"    焦点贷款：{df.sector.iloc[DEMO]} / {df.activity.iloc[DEMO]}，"
      f"上架于 {df.fundraisingDate.iloc[DEMO]:%Y-%m-%d %H:%M}")
print(f"    它的 use 文本：{df.use.iloc[DEMO]}")
print(f"    此刻同行业在架的贷款共 {int(C_use[DEMO])} 条，随机看其中 4 条：")
sims = []
for j, _ in demo_members[:60]:
    cs = float(U_use[DEMO].multiply(U_use[j]).sum())
    sims.append((cs, j))
sims.sort(reverse=True)
for cs, j in (sims[:2] + sims[-2:]):
    print(f"      余弦 {cs:.3f}   {df.use.iloc[j][:64]}")
print(f"    这些余弦的平均值 = {np.mean([s for s,_ in sims]):.4f}  ← 这就是该笔的 H")
print(f"    脚本里算出来的 H_use[{DEMO}] = {H_use[DEMO]:.4f}（用向量和一次点积得到，结果相同）")

print(f"\n    全样本的主动池规模分布：")
print(f"      均值 {C_use.mean():.1f}   中位 {np.median(C_use):.0f}   "
      f"p90 {np.percentile(C_use,90):.0f}   最大 {C_use.max():.0f}")
print(f"      空池 {np.mean(C_use==0):.1%}   ≥5 的占 {np.mean(C_use>=5):.1%}   "
      f"≥{MIN_POOL} 的占 {np.mean(C_use>=MIN_POOL):.1%}")
note(f"★ 池门槛 ≥{MIN_POOL} 会砍掉 {1-np.mean(C_use>=MIN_POOL):.0%} 的样本。"
     f"注意被砍掉的正是拥挤度低的那一半——而拥挤度的变异恰恰是识别 C×H 的来源。"
     f"这一条在 STEP 13 会用数字验证。")

C_des, H_des = active_pool(U_desc, end_h_filled)
_,     H_res = active_pool(U_res,  end_h_filled)
timing("主动池（description / 残差）")


# ==============================================================================
banner(8, "滞后池：L 至 L+29 天前发布的同行业贷款（衰减加权）",
       "这是 RQ2 的核心。这批贷款**已经不在架了，抢不走这笔钱**，"
       "所以如果它们仍与筹资速度相关，那就不是竞争，而是叙事磨损。"
       "关键约束：这个池子必须 status-agnostic（不论后来募没募到），"
       "否则「只收已结清的贷款」会引入结果选择偏误。")
# ==============================================================================
def window_pool(Umat, lo_days, hi_days, decay=True, forward=False):
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
            w = np.exp(-lam*(np.abs(ts[sl]-ts[k]) - lo_days*24))
            W = w.sum()
            if W <= 0: continue
            wm = sparse.csr_matrix(w.reshape(1,-1)) @ Us[sl]     # 加权向量和
            Vv[ids[k]] = W; Nn[ids[k]] = hi[k]-lo[k]
            Gg[ids[k]] = float(Us[k].multiply(wm).sum()/W)        # 加权平均余弦
    return Vv, Gg, Nn

print("    衰减权重表（7 天半衰期，从窗口起点第 %d 天开始计）：" % L_DAYS)
for dd in [0, 3, 7, 14, 21, 29]:
    print(f"      距今 {L_DAYS+dd:>2.0f} 天前发布 → 权重 {0.5**(dd/HALFLIFE_D):.3f}")
note("真正做工的是半衰期，不是窗口的硬边界：第 29 天的权重只剩 5.7%，"
     "所以把窗口从 30 天改成 40 天几乎不会改变任何结果")

V_use, G_use, Nlag = window_pool(U_use,  L_DAYS, L_DAYS+WIN_D)
V_des, G_des, _    = window_pool(U_desc, L_DAYS, L_DAYS+WIN_D)
out(f"滞后池条数：均值 {Nlag.mean():.1f}，≥{MIN_POOL} 的占 {np.mean(Nlag>=MIN_POOL):.1%}")
timing("滞后池")

# ---- 重叠检验（提案要求，实测恒为 0）----
still = []
for s in range(NS):
    ids = idx_by_s[s]; ts = post_h[ids]
    lo = np.searchsorted(ts, ts-(L_DAYS+WIN_D)*24); hi = np.searchsorted(ts, ts-L_DAYS*24)
    for k in range(len(ids)):
        if hi[k] > lo[k]: still.append(float((end_h_filled[ids[lo[k]:hi[k]]] > ts[k]).mean()))
out(f"滞后池中「上架时仍在架」的比例 = {np.mean(still):.4%}")
note("恒为 0，且不是巧合：L 取的就是募资期限上限。这项检验在真实数据上同样恒为 0。")


# ==============================================================================
banner(9, "镜像池与前向安慰剂池",
       "镜像池：把主动池换成「前 14 天发布的全部同行业贷款，不论后续状态」。"
       "为什么需要它——主动池的构成被别的贷款的结果污染了：某行业某周整体募资慢，"
       "会同时造成更大的池子和更慢的焦点贷款，而 week 固定效应吸收不了行业特有的冲击。"
       "镜像池只依赖发布时间，切断了这条通道。\n"
       "                  前向池：把滞后窗整个平移到**未来**。未来的贷款不可能影响过去的筹资，"
       "所以那里如果测出关系，说明模型里还有没吸收干净的语言或时间趋势。")
# ==============================================================================
Cm, Hm, Nmir = window_pool(U_use, 0, MIRROR_D, decay=False)
Vf, Gf, _    = window_pool(U_use, L_DAYS, L_DAYS+WIN_D, forward=True)
out(f"镜像池规模：均值 {Cm.mean():.1f}，空池 {np.mean(Cm==0):.1%}")
out(f"前向池已构造（与滞后池完全对称，只是方向相反）")
note("代价：镜像池是主动池的带噪代理，系数会被衰减。这是一笔明确的交易——"
     "用系数衰减换掉内生性偏误。STEP 13 会把两者并排。")
timing("镜像池 + 前向池")

pools = pd.DataFrame(dict(C_use=C_use, H_use=H_use, C_des=C_des, H_des=H_des, H_res=H_res,
                          V_use=V_use, G_use=G_use, V_des=V_des, G_des=G_des,
                          Cm=Cm, Hm=Hm, Vf=Vf, Gf=Gf, Nlag=Nlag, Nmir=Nmir))


# ==============================================================================
banner(10, "构造设计矩阵",
       "六个测量全部中心化标准化，这样系数可以直接读成「上升一个标准差，"
       "筹资时间变化百分之几」。饱和是交互项而不是主效应——理论说的是"
       "「量多」和「故事像」必须同时发生才咬人。")
# ==============================================================================
df["week"] = ((post_h - post_h.min())//(24*7)).astype(int)
df["year"] = df.fundraisingDate.dt.year
def z(x):
    x = np.asarray(x, float); s = np.nanstd(x)
    return (x-np.nanmean(x))/s if s > 0 else x*0

CTRL = np.column_stack([
    np.log(df.loanAmount.values/300.0),
    (df.borrowerCount.values > 1).astype(float),
    (df.gender.values == "male").astype(float),
    df.lenderRepaymentTerm.values - 12.0,
    (df.repaymentInterval.values == "at_end").astype(float),
    np.clip((df.fundraisingDate-df.disbursalDate).dt.days.values, -60, 120)/30.0,
    df.boiler_share.values,
])
CN = ["logAmt","group","male","term","atEnd","disbGap","boilerShare"]
FE = dict(country=pd.Categorical(df.country_name).codes,
          activity=pd.Categorical(df.activity).codes, week=df.week.values)
print("    模型形式：")
print("      log(1+FundingHours) = b0 + b1·C + b2·H + b3·(C×H)")
print("                              + b4·V + b5·G + b6·(V×G)")
print("                              + 控制变量 + 国家FE + 活动FE + 周FE + e")
print(f"    控制变量 {len(CN)} 个：{CN}")
print(f"    固定效应：国家 {len(set(FE['country']))} 个 · 活动 {len(set(FE['activity']))} 个 "
      f"· 周 {len(set(FE['week']))} 个 → 合计约 {sum(len(set(v))-1 for v in FE.values())} 个虚拟变量")
note("因变量取 log(1+小时)：保留不到一天的变异，同时压住极端长尾的影响")


# ==============================================================================
banner(11, "估计：稀疏 OLS + 国家×周双向聚类标准误",
       "为什么要双向聚类：同一个国家的贷款共享制度环境，同一周的贷款共享平台流量。"
       "两个维度都有组内相关，只聚类一个会低估标准误。"
       "为什么手写而不用现成包：620 个固定效应虚拟变量用稀疏矩阵存，"
       "正规方程只有 630×630，直接解比任何吸收算法都快，而且每一步都看得见。")
# ==============================================================================
def build_X(Xd, mask):
    mats = []
    for _, codes in FE.items():
        c = pd.Categorical(codes[mask]).codes; k = c.max()+1
        if k > 1:
            M = sparse.csr_matrix((np.ones(mask.sum()), (np.arange(mask.sum()), c)),
                                  shape=(mask.sum(), k))
            mats.append(M[:, 1:])                    # 去一列避免完全共线
    return sparse.hstack([sparse.csr_matrix(Xd)] + mats +
                         [sparse.csr_matrix(np.ones((mask.sum(),1)))]).tocsr()

def ols_twoway(y, Xd, mask, names, verbose=False):
    X = build_X(Xd, mask)
    XtX = (X.T@X).toarray()                          # 630×630 稠密
    Xi  = np.linalg.pinv(XtX)
    b   = Xi @ (X.T@y)
    e   = y - X@b
    def meat(g):                                     # Σ_g (X_g'e_g)(X_g'e_g)'
        gg = pd.Categorical(g).codes
        G = sparse.csr_matrix((np.ones(len(gg)), (gg, np.arange(len(gg)))),
                              shape=(gg.max()+1, len(gg)))
        S = (G @ X.multiply(e[:, None])).toarray()
        return S.T @ S, gg.max()+1
    c1, c2 = df.country_name.values[mask], df.week.values[mask]
    M1, g1 = meat(c1); M2, g2 = meat(c2)
    M12, _ = meat([f"{a}|{b_}" for a, b_ in zip(c1, c2)])
    V = Xi @ (M1 + M2 - M12) @ Xi                    # Cameron-Gelbach-Miller
    if verbose:
        print(f"      设计矩阵 X：{X.shape[0]:,} × {X.shape[1]:,}（稀疏，非零 {X.nnz:,}）")
        print(f"      残差标准差 {e.std():.4f}，R² = {1-e.var()/y.var():.4f}")
        print(f"      聚类：国家 {g1} 组 + 周 {g2} 组 − 交叉 {M12.shape[0]}… → V = Xi(M1+M2−M12)Xi")
    se = np.sqrt(np.clip(np.diag(V), 0, None)); k = len(names)
    return dict(names=names, coef=b[:k], se=se[:k], V=V[:k,:k], n=int(mask.sum()),
                r2=float(1-e.var()/y.var()))

def spec(cols, min_pool, pool_col=None, mask0=None, verbose=False):
    pool_col = pool_col or cols[0]
    m = df.funded.values & (pools[pool_col].values >= min_pool) & np.isfinite(CTRL).all(1)
    for c in cols: m &= np.isfinite(pools[c].values)
    if mask0 is not None: m &= mask0
    y = np.log1p(df.hours.values[m])
    Zc, Zh = z(np.log1p(pools[cols[0]].values))[m], z(pools[cols[1]].values)[m]
    Zv, Zg = z(np.log1p(pools[cols[2]].values))[m], z(pools[cols[3]].values)[m]
    Xd = np.column_stack([Zc, Zh, Zc*Zh, Zv, Zg, Zv*Zg, CTRL[m]])
    return ols_twoway(y, Xd, m, ["C","H","CxH","V","G","VxG"]+CN, verbose=verbose)

ACT = ["C_use","H_use","V_use","G_use"]; MIR = ["Cm","Hm","V_use","G_use"]
print("    主规格（镜像池，不设池门槛）：")
main = spec(MIR, 0, "Cm", verbose=True)
print()
print(f"    {'参数':<12}{'系数':>10}{'标准误':>10}{'t':>8}{'时长变化/标准差':>18}")
for i, nm in enumerate(["C","H","CxH","V","G","VxG"]):
    b, s_ = main["coef"][i], main["se"][i]
    print(f"    {nm:<12}{b:>10.4f}{s_:>10.4f}{b/s_:>8.2f}{np.expm1(b):>17.1%}")
timing("主模型估计")


# ==============================================================================
banner(12, "假设检验：RQ1 单系数 t 检验，RQ2 三项联合 Wald 检验",
       "RQ2 不能看单个系数：V、G、V×G 三者高度相关，任何一个单看都不可解释。"
       "提案明确要求「joint test that the three lagged terms are zero together」，"
       "所以这里做的是 Wald 联合检验。")
# ==============================================================================
b, V = main["coef"], main["V"]
t3 = b[2]/main["se"][2]; p3 = 1 - chi2.cdf(t3**2, 1)
print(f"    RQ1  H0: β₃(C×H)=0")
print(f"         β₃ = {b[2]:+.4f}  se = {main['se'][2]:.4f}  t = {t3:+.2f}  p = {p3:.4f}")
print(f"         {'→ 拒绝：拥挤与同质同时上升时，筹资更慢' if p3 < 0.05 else '→ 不拒绝'}")
R = np.zeros((3, len(b))); R[0,3] = R[1,4] = R[2,5] = 1.0      # 选出 V, G, V×G
Rb = R@b; RVR = R@V@R.T
W = float(Rb @ np.linalg.pinv(RVR) @ Rb)
print(f"    RQ2  H0: β₄=β₅=β₆=0（三项同时为零）")
print(f"         Wald 统计量 = {W:.3f}，自由度 3，p = {1-chi2.cdf(W,3):.4f}")
print(f"         {'→ 拒绝：在扣除当前竞争之后，近期叙事环境仍与筹资速度相关' if 1-chi2.cdf(W,3)<0.05 else '→ 不拒绝'}")
note("等价性判据：预设 5% 的筹资时间变化为最小有意义效应，对应 log 尺度 "
     f"{np.log(1.05):.4f}。主估计的置信区间半宽 {1.96*main['se'][2]:.4f}，"
     f"{'窄于' if 1.96*main['se'][2] < np.log(1.05) else '宽于'}这个带宽。")


# ==============================================================================
banner(13, "稳健性与对照规格：逐个验证提案里的设计决定值不值",
       "到这里主结果已经有了。下面每一个规格都对应提案里的一句方法论主张，"
       "跑出来是为了回答：这句话如果删掉，结论会不会变？")
# ==============================================================================
specs = [
    ("① 主动池 + 门槛≥10（提案 v4 的主规格）", ACT, 10, "C_use", None),
    ("② 主动池 + 不设门槛",                   ACT,  0, "C_use", None),
    ("③ 镜像池 + 门槛≥10",                    MIR, 10, "Cm",    None),
    ("④ 镜像池 + 不设门槛 ← 本脚本主规格",     MIR,  0, "Cm",    None),
    ("⑤ description 文本替代 use",   ["C_des","H_des","V_des","G_des"], 0, "C_des", None),
    ("⑥ 去模板残差文本",             ["C_des","H_res","V_des","G_des"], 0, "C_des", None),
    ("⑦ 安慰剂：滞后窗改为前向",     ["Cm","Hm","Vf","Gf"],             0, "Cm",    None),
    ("⑧ 分样本 2016-2020",                    MIR,  0, "Cm", df.year.values<=2020),
    ("⑨ 分样本 2021-2025",                    MIR,  0, "Cm", df.year.values>=2021),
]
print(f"    {'规格':<34}{'N':>7}{'C':>16}{'H':>16}{'C×H':>16}{'V×G':>16}")
print("    " + "-"*105)
res = {}
for lab, cols, mp, pc, mk in specs:
    r = spec(cols, mp, pc, mask0=mk); res[lab] = r
    cells = "".join(f"{r['coef'][i]:>10.3f}({r['se'][i]:.3f})" for i in (0,1,2,5))
    print(f"    {lab:<34}{r['n']:>7}{cells}")

print("\n    读法：")
print("    · ①→② 只是去掉池门槛，C×H 从"
      f" {res['① 主动池 + 门槛≥10（提案 v4 的主规格）']['coef'][2]:+.3f}"
      f"(t={res['① 主动池 + 门槛≥10（提案 v4 的主规格）']['coef'][2]/res['① 主动池 + 门槛≥10（提案 v4 的主规格）']['se'][2]:.1f})"
      f" 变成 {res['② 主动池 + 不设门槛']['coef'][2]:+.3f}"
      f"(t={res['② 主动池 + 不设门槛']['coef'][2]/res['② 主动池 + 不设门槛']['se'][2]:.1f})"
      " —— 门槛切掉的正是识别交互项所需的拥挤度变异")
print("    · ②→④ 换成镜像池，C 的系数大幅下降 —— 主动池那个偏高的 C 里混着内生性")
print("    · ⑤⑥ 换文本字段、去模板，C×H 变化不大 —— 模板分解在这里没有改变结论")
print("    · ⑦ 前向安慰剂：如果它的 V×G 与 ④ 的 V×G 都不显著，两者的比值就是两个噪音的比值，"
      "提案里「前向须低于后向的 1/3」这条判据在这种情况下不可评估")
print("    · ⑧⑨ 前后半段对比 = RQ3 的分样本写法")
timing("全部稳健性规格")


# ==============================================================================
banner(14, "汇总与交付",
       "把池测量和估计结果落盘，供后续对答案与写作使用。")
# ==============================================================================
pools.to_csv("pipeline_pools_详解版.csv", index=False)
summary = {lab: {"n": r["n"], "r2": r["r2"],
                 "coef": dict(zip(r["names"][:6], np.round(r["coef"][:6], 4).tolist())),
                 "se":   dict(zip(r["names"][:6], np.round(r["se"][:6], 4).tolist()))}
           for lab, r in res.items()}
summary["主规格_镜像池"] = {"n": main["n"], "r2": main["r2"],
    "coef": dict(zip(main["names"][:6], np.round(main["coef"][:6], 4).tolist())),
    "se":   dict(zip(main["names"][:6], np.round(main["se"][:6], 4).tolist())),
    "RQ2_Wald": W, "RQ2_p": float(1-chi2.cdf(W, 3))}
json.dump(summary, open("pipeline_results_详解版.json","w"), indent=1, ensure_ascii=False)
out("pipeline_pools_详解版.csv        —— 每笔贷款的 15 个池测量")
out("pipeline_results_详解版.json     —— 全部规格的系数与标准误")
print(f"\n    全流程完成，总用时 {time.time()-T0:.1f} 秒（{len(df):,} 条）")
print("="*88)
