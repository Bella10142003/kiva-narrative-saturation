# 演示层数字的可复现脚本（PPTX v2.7）

交付包 `5_最终交付包/.../outputs/` 覆盖了模型与稳健性产物，但**幻灯片上还有一批数字没有对应脚本**——
月内日历脉冲、分板块同质性存活率、年度中位数、以及 A4 上那个预注册的 RQ2 联合检验。
本文件夹把这些全部固化下来，评委索要复现代码时可以当场跑。

## 运行

```bash
python3 presentation_recompute.py            # 第 1–5 部分（约 1 分钟）
python3 _part6.py base                       # 主模型 + RQ2/RQ1 联合检验（约 1 分钟）
python3 _part6.py dom                        # 加入月内日期固定效应（约 1 分钟）
```

依赖：`pandas pyarrow numpy scipy pyfixest`。数据源默认 `../我算出来的结果/data/model_data.parquet`。
`_part6.py` 拆成两次运行是因为两个 HDFE 同进程会吃满内存。

## 口径（锁定，不要改）

| 项 | 口径 |
|---|---|
| 月内日期 | **太平洋日历日**（`fundraising_ts` / `raised_ts` 转 US/Pacific 后取 `.day`） |
| 星期 / 小时 | **UTC** 的 `posting_dow` / `posting_hour` |
| 指数 | 该日日均条数 ÷ 全期日均条数（等价于「每月均值 = 1.00」） |
| 建模样本 | `analysis_washin_eligible ∧ raw_text_nonempty ∧ pool_size_active ≥ 10 ∧ lag_kish_n ≥ 10` |
| 标准化 | 总体标准差（`ddof=0`）。交付包用的是冻结 scaler，系数会差在第三位小数 |

> ⚠️ **DuckDB `EXTRACT(DOW)` 是 0 = 星期日**，不是 0 = 星期一。
> PPTX v2.6 的 A6 星期面板就是按 0=Monday 贴的标签，整体错位一天，v2.7 已修正。

## 输出与对应的幻灯片

| 文件 | 支撑 | 关键值 |
|---|---|---|
| `year_profile.csv` | S2、A7 右panel | Q1–Q3 中位 **121.16 → 68.12 h（−43.77%）**；mean H 2025 = 0.1564（十年最高）、2018 = 0.0569（最低）；mean C 6.5206 → 6.2518；中位在架池 1030 → 769 |
| `calendar_day_of_month_index.csv` | S6、A6 上两panel | 2024–25 上架峰 18 号 **5.921**、完成峰 18 号 **2.751**（19 号 2.414）；18 号占全期上架 **19.58%**、净进 **+1,208 条/日**；2016–25 上架峰 17 号 **3.061**（18 号 2.177）、完成峰 18 号 2.243 |
| `weekday_index.csv` | A6 左下panel | Mon 1.037 · **Tue 1.082（最高）** · Wed 1.039 · Thu 1.036 · Fri 1.049 · **Sat 0.862（最低）** · Sun 0.896 |
| `hour_index.csv` | A6 右下panel | 0.513 – 1.697 |
| `day_of_month_profile_2024_2025.csv` | S6 讲者备注 | 18 号 mean H **0.2045**、中位在架池 **969**、菲律宾占比 **70.96%**；12–16 号 H 0.056–0.066、池 762–801 |
| `sector_homogeneity_survival.csv` | S7 横条图 | 全平台基准 **75.20%**；Housing 100.4%（boilerplate 0.4%）、Services 95.6%、Retail 58.4%、Clean Energy 57.9%、Philippines × General Store **57.1%（n = 117,291，boilerplate 57.8%）** |
| `day_of_month_fe_robustness.csv` | S6 讲者备注 | C×H **0.1009 → 0.0975**（加入月内日期 FE）。脉冲不是头条结果的来源 |
| `rq_joint_tests.csv` | **A4 新增行** | RQ2 预注册联合约束 V = G = V×G = 0：**χ²(3) = 17.77, p = 4.9e-04；F(3,45) = 5.92, p = 1.7e-03 — 拒绝**。V×G 单独 p = .0041。RQ1 联合 F(3,45) = 90.90, p = 4.0e-19 |

## 为什么 A4 要加那一行

提案 PDF 第 2 页原文：**"RQ1 tests C×H; RQ2 jointly tests V, G and V×G."**
即 RQ2 预注册的是 β_V = β_G = β_V×G = 0 的联合约束检验。交付包里没有这个检验的产物，
而 v2.6 的 A4 用了 "Joint test — not distinguishable from zero" 的措辞——那说的其实是
P25→P75 联合**情景对照**（净 −1.4%，区间跨零），不是联合约束检验。

真跑这个检验：**p = .002，拒绝**。滞后池有信号（G = −0.139 显著为负，V×G = +0.042 显著为正），
只是两者方向相反、互相抵消，所以那个特定情景的净效应约等于零。

v2.7 的口径：**"Signal present, no net drag"** —— 有信号，但没有可观测规模的净拖累。

## 图

`figures/` 下是 v2.7 重画的两张图与其生成脚本：
- `fig_a6.py` + `a6_data.json` → A6 四面板日历图（**修正了星期标签错位**）
- `fig_s7.py` → S7 分板块存活率横条图（Services 95% → **96%**，四舍五入口径统一）

配色沿用版式：绿 `#2f8f4e`、紫 `#6a4c93`、浅绿 `#9fbfac`、深绿标题 `#0e3b2b`、灰字 `#56655d`、底色 `#fafcfa`。
