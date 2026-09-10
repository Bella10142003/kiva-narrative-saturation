# Claude 审查记录 — v2.6 → v2.7 修订清单

- 产出：`5_最终交付包/When_Every_Story_Sounds_The_Same v2.7.pptx`（20 页，页序与版式未动）
- 依据：`Claude审查记录_PPTX_v2.6独立复核_2026-09-03.md` 与 `Claude审查记录_PPTX_v2.6附录逐页_2026-09-03.md`
- 新增可复现产物：`4_中间产物/演示复算/`（脚本 + 8 个 CSV + 两张图的生成脚本）
- 未改动：叙事骨架、页序、配色、A2 / A9 / A11 三页

---

## 一、页面改动（9 页）

| 页 | 改动 | 为什么 |
|---|---|---|
| **S4** | 两栏标题 `ACTIVE / RECENT SATURATION` → **`JOINT MOVE IN C AND H` / `JOINT MOVE IN V AND G`** | `scenario_component_decomposition.csv`：+124%（log 0.8080）= C 主效应 +0.618（76.5%）+ H 主效应 +0.215（26.6%）+ **C×H 交互 −0.025（−3.1%）**。原标题会被读成「124% 由交互撑起」，而交互在这个情景里贡献为负 |
| **S4** | 底栏 `Broad wear-out is not.` → **`Recent saturation leaves no net drag.`** | 配合 RQ2 口径统一，见下 |
| **S6** | 顶栏 `Volume-driven in 2018` → **`similarity at its decade low in 2018`** | 2018 的 mean C = 5.79，是十年第三低。原措辞会被读成「2018 上架量高」，那是错的；逐年也只估了 C×H，没有逐年 C、H 主效应产物 |
| **S7** | 横条图重画：**Services 95% → 96%** | 实测 95.566%，其余 14 行都按四舍五入，只有这行是截断，口径不统一 |
| **A1** | RQ2 答案行 → **`Signal present, no net drag — the joint restriction rejects, but the components offset.`** | 见第二节 |
| **A3** | Result 列**每一行补上 V×G** | 原先五行只报 C×H，而 residual 下 V×G 恰恰变强（0.042 → 0.058, p=.0007），只报一半属选择性呈现 |
| **A4** | 标题 → `RQ2: a rejected joint restriction, and a scenario that nets to zero`；`Joint test — not distinguishable from zero` → **`Joint scenario — interval covers zero`**；**新增一行 `Joint restriction  rejected, p = .002`**；左栏 V×G 行 → `recent saturation — RQ2 tests all three jointly`；底栏 → `The lagged channel carries signal — but its components offset, leaving no net drag.` | 见第二节 |
| **A4** | `L sits at the fundraising cap` → **`L = the 95th percentile of funding duration, so lagged loans have nearly all left the page.`** | L=35 天来自训练样本筹资时长 P95 = 826.89h = 34.45 天，不是平台募资期限上限；约 5% 的贷款第 35 天仍在架，原来的 "by construction" 站不住 |
| **A5** | `Rule  high-frequency verbatim sequences` → **`Rule  5-grams, ≥500 loans, ≥3 countries`** | 「≥3 个国家」是这页的隐藏亮点：它保证被判为模板的是跨机构复用的措辞，而不是某国的自然表达。数据里没有 partner identifier，这是最接近机构层面的代理 |
| **A6** | **四面板图重画**：星期标签整体右移一格 | 原图柱子数值与 DuckDB `EXTRACT(DOW)`（**0 = 星期日**）逐位吻合，但标签从 Mon 写起。真实形态是 **Tue 1.082 最高、Sat 0.862 最低、Sun 0.896 次低**——一个干净的「周末停摆」节律，正好支撑底栏 "supply-side rhythms — not lender mood" |
| **A6** | `day 18 is the only day arrivals clearly exceed completions` → **`day 18 carries almost all of the month's net accumulation`** | 2024–25 太平洋口径下 17 号净流入 +242 条/日，15、16、24 号也为正 |
| **A6** | `Week / hour / month  0.86–1.08 and 0.51–1.70` → **`Week / hour  0.86–1.08 (Sat low) and 0.51–1.70`** | 原文两个范围对应三样东西 |
| **A10** | `Hoberg & Phillips (2016)` 标 **†**，加注 `read during analysis; not in the submitted proposal` | 已比对提案 PDF 第 6 页原件：提案 7 条参考文献不含此条 |

讲者备注：S4 / S6 / A1 / A3 / A4 / A5 / A6 / A8 / A10 九页各加了一段【v2.7 修订】，写明改动理由、完整数字与现场答法。

---

## 二、这次最重要的一处：RQ2 的口径

提案 PDF 第 2 页原文：**"RQ1 tests C×H; RQ2 jointly tests V, G and V×G."**
即 RQ2 预注册的是 β_V = β_G = β_V×G = 0 的**联合约束检验**。

- 交付包内**没有**这个检验的任何产物（全项目检索 `wald` / `f_test`，"joint" 一律指 P25→P75 情景对照与其支持度检查）。
- 本次实际估计（主模型规格，n = 1,234,131，country + week 双向聚类）：

| 检验 | 统计量 | p |
|---|---|---|
| **RQ2 预注册联合约束 V = G = V×G = 0** | **F(3,45) = 5.92**（χ²(3) = 17.77） | **0.0017**（χ²: 0.00049） |
| V×G 单独 | F(1,45) = 9.14 | 0.0041 |
| RQ1 联合 C = H = C×H = 0 | F(3,45) = 90.90 | 4.0e-19 |
| C×H 单独 | F(1,45) = 9.52 | 0.0035 |

**预注册的那个检验是拒绝的。** v2.6 上写的 "not distinguishable from zero" 说的其实是另一件事——
V、G、V×G 三项同时从 P25 移到 P75 这一个**特定情景**的净效应（−1.4%，CI −15.8% ~ +15.4%），
null 来自 G 主效应 −0.139 与 V×G +0.042 方向相反、互相抵消。

两句话都对，但 v2.6 用了 "joint test" 这个词，读过提案的评委会默认联合检验跑过且是 null。

**v2.7 的统一口径**：**有信号，但没有可观测规模的净拖累。**
现场答法（已写进 A4 备注）：
> 滞后池不是空的——提案预注册的联合约束检验以 p=.002 被拒绝，我们没有藏。但 G 是负的、V×G 是正的，两者抵消，所以 P25→P75 的净移动是 −1.4%、区间从 −15.8% 到 +15.4%。我们的结论是「没有可观测规模的净磨损拖累」，不是「磨损不存在」。要真正检验 wear-out 需要 lender 级浏览日志——见 A10。

---

## 三、没有改页面、只写进备注的两处

1. **A8 与 S7 的 Housing 张力**：森林图里 Housing 的 C×H = **−0.092（p = 3.7e-07）**，与全平台 +0.102 反号（Construction −0.513 同样反号），而 S7 恰恰把 Housing 立为 Type A 的旗舰例子。
   备注里的答法：**Housing 的同质性是真实的产品同质，这一点很确定；但它的 C×H 反号，所以它恰恰是最该先做实验、而不是先动手的市场——这正是 Phase 1 存在的理由。**
2. **Wang, R. (2024), AMPROC 2024(1), 15320**：在提案参考文献表内，DOI 格式符合 AOM 规范，但公开检索无法独立确认（AOM Proceedings 摘要通常不被外部索引收录）。**上台前请作者本人再确认一次。**

---

## 四、新增的可复现产物

`4_中间产物/演示复算/`：

```
presentation_recompute.py      第 1–5 部分（年度中位数、日历脉冲、星期/小时、月内画像、分板块存活率）
_part6.py base | dom           主模型 + RQ2/RQ1 联合检验 | 加入月内日期 FE
outputs/  8 个 CSV
figures/  fig_a6.py · fig_s7.py · a6_data.json · 两张重画的 PNG
README.md 口径锁定、输出对照表、DOW 编码陷阱
```

这填上了上一轮核查里「数字能复算但交付包内无脚本」的缺口——评委索要复现代码时可以当场跑。
其中 `outputs/day_of_month_fe_robustness.csv` 记录了 **C×H 0.1009 → 0.0975**（加入月内日期固定效应），
证明 18 号脉冲不是头条结果的来源。

---

*本记录由 Claude 于 2026-09-03 产出。所有改动均已在 v2.7 中落地并通过整档渲染检查（20 页，无溢出、无图片丢失、shape id 唯一）。*
