# Claude 审查记录 — PPTX v2.3 全量数据核查与 v2.4 修正

- 审查对象：`When_Every_Story_Sounds_The_Same v2.3.pptx`（18 页：7 页正文 + A1–A10）
- 核查依据：`5_最终交付包/MA-Hackathon-Final-2026-09-04/`（outputs / audit / src / METHODS_APPENDIX）、`4_中间产物/我算出来的结果/`、`4_中间产物/EDA/tables/`、`2_提案/5 GUYS 提案.pdf`、`2_提案/证据来源.md`
- 复算数据：`4_中间产物/我算出来的结果/data/model_data.parquet`（1,453,840 行；主建模样本 1,367,540 行）
- 产出：`When_Every_Story_Sounds_The_Same v2.4.pptx`
- 结论：**叙事框架整体经得起核查**。7 处已修正（1 处为用户指出的 pulse，5 处为本次新发现，1 处为占位图补齐）。

---

## 一、核对通过、有产物出处的数字

| 页 | 主张 | 出处 | 状态 |
|---|---|---|---|
| S1 | 1,453,846 笔贷款，2016-01-01 – 2025-12-31 | `outputs/data_profile_summary.csv` | ✅ |
| S2 | 2025 H 是十年最高的平均余弦 | 复算主样本 mean H：2025 = **0.1564**，次高 2021 = 0.1330 | ✅ |
| S2 | 2025 Volume C 下降 | mean C 6.5206 → **6.2518**；中位在架池 1,030 → **769** | ✅ |
| S3 | 1.23M training loans | `outputs/model_sample_flow.csv` = **1,234,131** | ✅ |
| S3 | Lagged pool L 到 L+29 天、约 35–65 天 | `outputs/frozen_spec.csv`「Age [35,65) days; 7-day half-life」 | ✅ |
| S3 | 国家 + 活动 + 周固定效应 | `audit/stage4b_model_manifest.json` 实际公式 `\| country_name + activity + week_id` | ✅ |
| S4 | **+124% / ×2.24** | `outputs/scenario_contrasts.csv` = **124.351%**（CI 103.71–147.08） | ✅ |
| S4 | **−14.7 pp** 72h | 同上 = **−14.682 pp** | ✅ |
| S4 | H +1SD：**+42.5%**（低 C）/ **+60.7%**（高 C） | `我算出来的结果/outputs/marginal_effects_C_H.csv` = **42.45 / 60.74** | ✅ |
| S4 | **−1.4%**，CI **−15.8% ~ +15.4%**，**−0.5 pp** | `scenario_contrasts.csv` = −1.421%，−15.811 ~ +15.429，−0.510 pp | ✅ |
| S5 | **+13.6%**、**−3.37 pp** | `我算出来的结果/outputs/template_share_effects.csv`，模型 C_both / E_both = **0.13594 / −0.03374** | ✅ |
| S5 | description 上 boilerplate 无独立关联 | 同表 B_description_only p = **0.453** | ✅ |
| S5 / A5 | Raw **0.102** p=.003 → Residual **0.052** p=.129 | `outputs/rq1_main_table.csv` 0.10166 / p=.00331；`outputs/robustness.csv` 0.05232 / p=.1287 | ✅ |
| S6 | 2018 H 低、2020–21 boilerplate 抬高 H、2025 boilerplate 回常态 | mean H 2018 = 0.0569（十年最低）；boilerplate 2020 = 0.321、2021 = 0.351；2025 = 0.2225 ≈ 2024 的 0.2220 | ✅ |
| A1 | 四个 RQ 的答案 | 与 `REPORT.md` 一致 | ✅ |
| A2 | 池门槛「同板块、最小 10」 | `frozen_spec.csv`「Raw n>=10; weighted Kish n>=10」 | ✅ |
| A5 | use 平均余弦 **0.26** | `outputs/text_selection_diagnostics.csv` = **0.2593** | ✅ |
| A9 | 加入叙事变量未稳定改善 2025 个体预测 | `outputs/holdout_validation.csv`；MAE 0.9663→0.9822、AUC 0.8986→0.8921 | ✅ |
| A10 | Ly & Mason (2012)、Pieters et al. (1999)、Chae et al. (2019)、Williamson et al. (2021)、UNSW (2026) | 逐条见于提案 PDF 参考文献页，且经公开检索确认真实存在 | ✅ |
| A10 | Hoberg & Phillips (2016) | JPE 124(5)，真实存在；但**不在已提交提案的参考文献表内**，属新增 | ⚠️ 可保留，注意与提案不完全一致 |
| A10 | Wang, R. (2024), AMPROC 2024(1), 15320 | 在提案参考文献表内；公开检索未能独立确认，建议由作者本人复核 | ⚠️ 待确认 |

---

## 二、已修正的 7 处

### ① 第 6 页 pulse —— 两条脉冲不是错开的，是同一天见顶（用户指出）

原图把上架峰画在 18 号、完成峰画在 **22 号**，并用「两条脉冲之间的落差」解释月内饱和。复算（太平洋日历日，指数以当月均值 = 1.00 标准化）：

| 期间 | 上架峰 | 完成峰 |
|---|---|---|
| 2024–2025 | **18 号，指数 5.92**（占该期间全部上架量的 19.58%） | **18 号，指数 2.75**（19 号 2.41） |
| 2016–2025 | 17 号，指数 3.06（18 号 2.18） | 18 号，指数 2.24 |

日均条数净额（2024–25）：18 号 **+1,208 条**；19–23 号全部为净流出（−439 / −192 / −105 / −150 / −76）。也就是说净累积集中在**一天**，之后五天池子在排空。

**修正**：完成脉冲的峰改到 18 号；两条脉冲统一按 2024–25 实测逐日指数的形状重绘；标注改为「day 18: arrivals 5.9× — completions only 2.8×」；底栏改为「Both pulses peak on the same day — arrivals spike far higher than completions release.」；讲者备注重写并补上口径纪律。

> 与 `Claude审查记录_讲稿叙事核查_2026-09-02.md` 的 M-3 一致：论点应是「两只时钟已对齐，问题是整月供给砸在同一天」，不是「时钟没对齐」。

### ② 第 2 页 107.6 → 61.3（−43%）口径不当

`107.64 / 61.32` 出自 `EDA/tables/A2_by_year_coverage.csv`，用的是 **wash-in 样本、全年**，与全套模型用的主样本不同；且 2025 年末存在右截断（`METHODS_APPENDIX.md`：中位时长从完整随访 65.4h 掉到最后 72 小时的 5.7h），全年口径会让 2025 显得更快。

三组可辩护的数对：

| 口径 | 2024 | 2025 | 变化 |
|---|---:|---:|---:|
| wash-in 样本，全年（原稿） | 107.6 h | 61.3 h | −43% |
| 主建模样本，全年 | 110.6 h | 65.2 h | −41% |
| **主建模样本，Q1–Q3（已采用）** | **121.2 h** | **68.1 h** | **−44%** |

**修正**：改用主样本 Q1–Q3，两年同口径、避开右截断，说服力反而更强；标题改为 `MEDIAN FUNDING HOURS · Q1–Q3`（顺带修掉原稿 "FUNDINGHOURS" 少一个空格），下方句子改为「Model sample, Q1–Q3 only, so year-end truncation cannot flatter 2025.」，条形图比例同步重算。

### ③ A5 description 平均余弦 0.44 → 0.41

`outputs/text_selection_diagnostics.csv`：随机同板块配对平均余弦 use = 0.2593、description = **0.4089**。0.44 在项目内查无出处（最接近的 0.4285 是窗口内 H 的中位数，不是配对余弦）。**修正**：改为 0.41，条形图比例同步。

### ④ A2「已做删失 AFT 稳健性检验」与方法附录直接矛盾

`METHODS_APPENDIX.md` 明写：*"No AFT model: the extract has no missing raisedDate, so true right censoring cannot be identified."* 交付包内也无任何 AFT 产物。**修正**：脚注改为「Every row carries a raisedDate, so right censoring cannot be identified and no AFT model is fitted.」

### ⑤ A3 三行稳健性检验在交付包内查无产物

| 原行 | 核查结果 |
|---|---|
| Exact-date pools | ❌ 无对应脚本、CSV 或日志 |
| Lag window and decay：L shifted 14/16 days, half-life 3/14 | ❌ 14/16 天是 **current pool 的 posting window**，不是 lag window；半衰期在 `src/build_pool_features.py:37` 冻结为 7 天，**没有跑过 3/14 天敏感性** |
| Falsification (forward) | ❌ 交付包内没有前向窗口安慰剂检验（模拟阶段设计过，最终流水线未纳入） |

**修正**：换成 `outputs/robustness.csv` 里真实存在的五项——precommitted 14 天池（0.089）、P75 校准 16 天池（0.099）、池门槛 n≥5 / n≥20（0.101 / 0.099）、residual text（0.102→0.052）、description 替代 use（0.130）。脚注补上「7 天半衰期为冻结值，未做前向窗口证伪」。讲者备注列出全部可交出的系数，并给出被问到「有没有做安慰剂」时的诚实答法。

### ⑥ 第 7 页把 Clean Energy 归为「产品同质」——实测正好相反

按「去掉 recurring language 后 H 掉多少」这一判据复算（主训练样本，全平台基准 −24.8%）：

| 板块 | mean H（raw） | mean H（residual） | 变化 | boilerplate 占比 |
|---|---:|---:|---:|---:|
| **Housing** | 0.3008 | 0.3019 | **−0.4%** | 0.004 |
| Arts | 0.1044 | 0.1051 | −0.7% | 0.060 |
| Transportation | 0.0672 | 0.0660 | +1.8% | 0.065 |
| **Clean Energy** | 0.4208 | 0.2438 | **+42.1%↓** | 0.394 |
| Retail | 0.1159 | 0.0677 | 41.6%↓ | 0.367 |
| Food | 0.0452 | 0.0275 | 39.2%↓ | 0.282 |

Clean Energy 去模板后 H 掉 42%，是典型的**流程同质**。另外原稿「certain high-boilerplate Retail country–activity markets」过于含糊，实测最干净的例子是 **Philippines × General Store**（117,291 笔，H 0.1999 → 0.1141，−42.9%，boilerplate 0.578）。

**修正**：A 类改为 Housing / Arts / Transportation 并附 Housing 0.301 → 0.302；B 类改为 Philippines × General Store（Retail, 117k）与 Clean Energy 并附 0.200 → 0.114（−43%）。讲者备注写明这是描述性判据、不是分行业重估的模型系数。

> ⚠️ 需注意：`outputs/rq4_sector_effects.csv` 里 Housing 的 **C×H 系数是 −0.0917（p<1e-6）**，与全平台 +0.102 反号。第 7 页讲的是「同质性来源」，不是分板块效应量，两者不冲突，但被追问时不要把二者混为一谈。

### ⑦ A6 / A7 / A8 三处 `PASTE FIGURE HERE` 已补齐

全部按真实数据新绘（300 dpi，配色沿用版式）：

- **A6**：四面板日历图——(1) 2024–25 逐日上架 / 完成指数（同一刻度，上下对称），(2) 2016–2025 同图，(3) 星期指数（0.86–1.08），(4) 小时指数（0.51–1.70）。同时把右栏四条要点改成实测口径（含年份限定，避免「arrivals peak near day 18」被当成全十年结论）。
- **A7**：左panel 逐年 C×H 系数及 95% CI（2016–2024，`outputs/rq3_year_effects.csv`，实心点 = 区间不含 0，虚线为合并值 0.102）；右panel 2016–2025 的 mean H、mean C、mean boilerplate share，直接支撑「2018 / 2020–21 / 2025」三站。
- **A8**：分板块（14 组）与分国家（前 15）森林图，含 ±ln(1.05) 等价带、合并值参考线、Q 检验统计量（Q=99.5, p=2e-15；Q=111.6, p=3e-17）。

---

## 三、未改动但建议现场注意的三点

1. **S6 顶栏「Volume-driven in 2018」**：2018 年 C×H 系数 0.431 是十年最高、mean H 0.057 是十年最低，方向成立；但逐年交互是把主效应再切十份，`REPORT.md` 已标为探索性，口播不要说成已证明。
2. **A9 的 R²/AUC 与主表 C×H 来自两个模型**（SGD 预测模型 vs HDFE），不可互证。表述只能是「叙事特征没有在主要运营指标上超过 baseline」，**不能说「变差了」**——`REPORT.md:70` 自陈未算 paired uncertainty。
3. **`REPORT.md` 正文仍写七重固定效应**（"country、activity、week、gender、repayment interval、posting day/hour fixed effects"），而实际执行与 PPTX 均为三重 FE + 四项控制变量。PPTX 这边是对的，**建议同步修 `REPORT.md`**，否则评委对照会发现文档打架。

---

## 四、变更清单（v2.3 → v2.4）

| 页 | 变更 |
|---|---|
| S2 | 121.2 h / 68.1 h / −44%；标题加 · Q1–Q3 并补空格；说明句改写；条形比例重算；讲者备注重写 |
| S5 | 「+13.6%」的说明改为 0%→100% 全区间口径 |
| S6 | 完成脉冲峰 22 号 → 18 号；两条脉冲按 2024–25 实测逐日指数重绘并加宽；标注、图注、底栏改写；讲者备注重写 |
| S7 | A 类 = Housing / Arts / Transportation；B 类 = Philippines × General Store + Clean Energy；两侧 signature 补实测数字；讲者备注重写 |
| A2 | 删除 AFT 主张，改为事实陈述；讲者备注重写 |
| A3 | 五行稳健性检验全部换成 `robustness.csv` 内实际存在的规格；脚注补冻结与未做项说明；讲者备注重写 |
| A5 | description 平均余弦 0.44 → 0.41，条形比例重算；讲者备注补出处 |
| A6 | 四条要点改实测口径；插入四面板日历图 |
| A7 | 插入逐年 C×H + CI 与 H / C / boilerplate 走势图 |
| A8 | 插入分板块 / 分国家森林图（含等价带） |

叙事框架、页序、版式与配色全部未动。

---

## 五、v2.4 → v2.5 追加变更（可视化与 demo）

| 页 | 变更 | 数据出处 |
|---|---|---|
| S7 | 两栏文字改为一张横条图：各板块「去掉 recurring language 后 H 还剩多少」，按存活率排序，绿=A 类、紫=B 类，右列标 boilerplate 占比。右侧只保留两张压缩卡（类型 + lever） | 复算主训练样本 `H_active_raw` / `H_active_residual` 均值；平台基准 75% |
| S8 | 四栏文字每栏压到一句；底行改为「Next: the same four steps, running on the real 2016–2024 data.」 | — |
| **新 S8（第 8 页）** | LIVE DEMO 引入页：三张卡（WHEN / WHICH KIND / WHERE IT STOPS）+ 底栏 + 兜底指引；讲者备注含完整演示脚本与口径纪律 | — |
| **新 A11** | demo 兜底页：Housing day 14（WATCH ONLY）与 day 18（TYPE A）两张实拍截图 + 三条要点 | 实拍自 Kiva Pulse 演示页 |

### Kiva Pulse demo 的口径边界（务必对齐）

- 界面上的 **saturation index = √(C 百分位 × H 百分位)**，是用于分诊的**监测启发式，不是模型系数**；它指向的模型量是 `C×H = 0.1017 (p = .0033)`。
- 三条判据阈值（在架池 ≥ 250 笔、H 百分位 ≥ 50、H 存活率 90% / 80%）是**运营门槛**，不是估计出来的临界值。改动须预注册。
- 全部数据来自 2016–2024 训练样本（1,234,131 笔，`model_data.parquet` 复算），2025 完全留出；均为条件关联。
- 界面**刻意不显示各日的实际中位筹款时长**——18 号批次结构本身不同（71% 来自菲律宾），未调整的原始量拿来对比会误导。
- Housing day 14 → 在架 127 笔（低于门槛）→ WATCH ONLY；day 18 → 298 笔、H 由 P69 升至 P95、存活率 100% → TYPE A。这一「同市场、隔四天、结论翻转」是演示的核心桥段。

---

## 六、v2.5 → v2.6 结构修正：TEST / LEARN 属于上线前，不属于运行中的系统

**问题**：v2.5 把 SENSE → DIAGNOSE → TEST → LEARN 排成一条四步产品回路，等于宣称随机实验是运行中系统的一部分。实际关系是两段：

- **Phase 1 · Validate（上线之前）**＝ TEST + LEARN。随机 A/B 实验，唯一产出是一份**通过验证的手段清单**。
- **Phase 2 · Operate（上线之后，demo 演示的就是这段）**＝ SENSE → DIAGNOSE → ACT → MONITOR。系统读市场状态、判断同质性来源、调用清单里已通过验证的手段（或不动），并持续按同一套指标与护栏监测、触发 revert。

| 位置 | 变更 |
|---|---|
| S7（RECOMMENDATIONS & IMPLICATIONS） | 四栏改为左右两块：Phase 1（浅底，TEST / LEARN + 关卡语「Only levers that clear this gate enter the catalogue.」）→ 箭头 → Phase 2（深底卡，SENSE / DIAGNOSE / ACT / MONITOR）。标题改为「Validate first, then operate — the demo is the second half.」 |
| S8（LIVE DEMO） | 标题改「Kiva Pulse — Phase 2, the live system.」；第三张卡由「Every read-out ends in a trigger」改为「It acts on the market, never on the loan」；页脚注明所有手段处于 shadow mode |
| demo 页面 | 顶部新增 Phase 条（Phase 1 灰色已关闭 → GATE → Phase 2 高亮「this screen」）；第 3 步由 TEST 改为 **ACT**（Action / Applies to / Lever status / Revert if），带状态 chip；第 4 步由 LEARN 改为 **MONITOR**（主次指标 / 护栏 / Stop rule / Why watch） |
| A11 | 页脚补「no Phase 1 pilot has run, so all levers sit in shadow mode」；截图重拍 |

**诚实性处理**：本研究没有跑过任何 pilot，所以 demo 里每一条建议动作都显示 `SHADOW MODE · PILOT A/B PENDING`（橙色 chip），措辞为「记录、不下发」。手段清单是空的，界面不假装它是满的——这同时也是「我们不是请你相信一个估计，是请你跑一次实验」这句话的现场落地。
