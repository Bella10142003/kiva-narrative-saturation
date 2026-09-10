# 3 · Analysis pipeline

> 分析步骤，18 个 notebook 按编号顺序跑。

Eighteen notebooks, run in numeric order. Paths are hard-coded relative to the repository root, so nothing
needs editing. Notebook prose is Chinese; all outputs are English.

| # | Step | What it does |
|---|---|---|
| 00 | 安全审计pickle | Pickle is executable. Statically scan the bytecode before deserialising anything |
| 01 | 转换成parquet | Restricted unpickler → 30 parquet shards |
| 02 | 数据画像与质量门 | Null rates, duplicate IDs, duration distribution, negative durations |
| 03 | ★ 冻结变量定义 | **Freeze every definition before looking at any result.** Guards against post-hoc tuning |
| 04 | 文本处理与TFIDF | Clean descriptions, strip template language, L2-normalised TF-IDF |
| 05 | ★ 构造池特征CHVG | **The core of the project** — rebuild the market as it stood the moment each loan went live |
| 06 | 准备建模矩阵 | Standardise; split train (2016–24) and holdout (2025) |
| 07 | ★ 主模型HDFE | Country + activity + week fixed effects, 8 controls, two-way clustering |
| 08 | 异质性分析 | By year (RQ3), by sector and country (RQ4) |
| 09 | 2025外推评估 | Out-of-sample incremental predictive power. **Result is negative**, reported as found |
| 10 | 文本表示稳健性 | Re-run under alternative text representations |
| 11 | ★ 反事实支撑域检查 | Do the P25 → P75 scenario endpoints have actual support in the data? |
| 12 | 出图 | 8 figures as PNG + PDF, with their source tables |
| 13 | 生成复现notebook | Auto-generate and execute the S0–S6 audit notebooks |
| 14 | 组装交付物 | HTML report, methods appendix, speaker notes |
| 15 | 最终QA二十道门 | 20 deterministic checks |
| 16 | 打包ZIP | ZIP + SHA-256 manifest + sensitive-content scan |
| 17 | 脱敏外部输出 | Replace private paths with placeholders |

★ = the four steps with the most technical weight.

`详解版/` holds hand-written walkthroughs of steps 05 and 07 that explain *why* each cell does what it does,
rather than only what it does.
