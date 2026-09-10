> # ⛔ 未提交的早期草稿 — 不是基准
>
> **实际提交的提案是 [`5 GUYS 提案.pdf`](../5%20GUYS%20提案.pdf)**
> —《WHEN EVERY STORY SOUNDS THE SAME — Separating Market Crowding, Active Narrative
> Competition, and Narrative Wear-Out on Kiva》，结构为 **RQ1–RQ4**。
>
> 本文件是另一版草稿，从未提交，团队栏仍为 `[TO CONFIRM]`，数据描述仍是 100 条样本。
> 同一目录下的 `提案定稿_BeyondCrowding_未提交.docx` **也是这份草稿**（尽管文件名含「定稿」），同样不是基准。
> 两者在四个维度上不同：
>
> | | 已提交 PDF | 本草稿 |
> |---|---|---|
> | 结构 | RQ1–RQ4 | H1–H4 |
> | 核心估计量 | **C×H 交互**（"neither alone is sufficient"） | S_i 主效应 + 嵌套 H1→H2 |
> | 滞后 wear-out 通道 V/G/V×G | **有，是 RQ2 的全部内容** | 完全不存在 |
> | 次级问题 | 无 H3 | H3 需 200 条盲编码 + F1≥0.80 |
> | 主文本字段 | 看诊断后确定（实际选 `use`） | 写死 "description only" |
>
> 交付物（`5_最终交付包/`）是按 PDF 实现的。**审批、合规核查和结果解释一律以 PDF 为准。**
> 详见 [7_审查记录/Claude审查记录_提案基准更正_2026-09-01.md](../../7_审查记录/Claude审查记录_提案基准更正_2026-09-01.md) 的 B-01。
>
> ⚠️ 提案 PDF 本身尚未归档进本项目，建议放入 `2_提案/`。

---

# Beyond Crowding: Is Narrative Saturation Associated with Slower Funding in Prosocial Crowdfunding?

**Team members:** [TO CONFIRM]  
**Affiliations:** [TO CONFIRM]

## 1. Project Aim and Research Questions

This project asks whether narrative saturation is associated with slower funding beyond market crowding. A lender screening subsistence-market loans spends limited attention: when many appeals repeat the same wording, no borrower stands out, comparison is harder, and choice can be deferred. Crowding and saturation are different conditions, yet loan counts conflate them. We construct both from the same contemporaneous pool: its size and average narrative similarity.

The official challenge data cover 1,453,846 Kiva loans issued from 1 January 2016 to 31 December 2025 in countries with PPP GDP per capita below US$4,500. Funding duration is the elapsed time between the *fundraisingDate* and *raisedDate* timestamps, in fractional days. H1 predicts that higher narrative saturation at posting is associated with longer duration. H2 predicts that this association remains after accounting for market crowding and pre-specified loan characteristics.

H3 is secondary: the association may be weaker when the *use* field names a concrete use of funds or gives numerical detail. H4 asks how the association differs across sectors and evolves across fundraising years; that variation is a committed descriptive deliverable, and only its inferential reading is exploratory. These are hypotheses and planned comparisons, not findings. Because the design is observational, every estimate will be interpreted as an association rather than a causal effect.

## 2. Proposed Analytical Approaches

### Primary measurement

For loan i at posting time t_i, A_i contains every other loan j with usable *description* and valid dates satisfying *fundraisingDate*_j ≤ t_i < end_j. For funded loans end_j is *raisedDate*; confirmed ongoing loans use the organiser-supported observation end, and earlier exits their verified terminal dates.

One pool for both measures means H2 contrasts composition after size, not artefacts of temporal coverage. Membership ends at end_j, however, so any risk set over-represents slow loans and partly reflects other loans’ outcomes. Every headline model is therefore repeated on an outcome-independent pool of loans posted in the prior 14 days, and we interpret only associations that agree across both.

Market crowding is N_i, the size of A_i, entered as log(1 + N_i). Narrative saturation is the mean similarity between loan i and that same pool:

S_i = (1/N_i) × Σ[j in A_i] cosine(v_i, v_j).

Dividing by N_i standardises saturation for pool size, making S_i an average rather than a total that rises mechanically with crowding; S_i is then z-standardised. Empty-pool loans are excluded and reported, not coded as zero.

The primary text is *description* only, avoiding mechanical overlap with H3’s *use* measure and the repeated *whySpecial* text seen in the sample. We clean HTML, Unicode, case, and whitespace and replace *description* numbers with a common token; H3’s indicator comes from untouched *use*. Descriptions are partner-written and reuse template phrasing, so before outcomes are viewed we strip sequences recurring verbatim across a pre-set share of loans and keep each loan’s boilerplate share as a control. The representation is an L2-normalised word unigram/bigram TF–IDF matrix with pre-set frequency filters and a capped vocabulary. Cosine is transparent, outcome-independent, auditable, and needs no external model.

Because vectors are L2-normalised, S_i is v_i’s dot product with the pool mean, so a sparse running sum over posting and end_j events scales to the full data; a checked subset verifies it.

### Core, secondary, and exploratory models

Duration keeps its sub-day resolution, so H1 uses ordinary least squares on log(1 + fractional days), which handles right skew and near-zero values; calendar-day rounding is a robustness check. It includes standardised S_i, pre-specified controls, and fixed effects. H2 adds log(1 + N_i) and is the primary model. Controls are log1p(*loanAmount*), log1p(*borrowerCount*), linear *lenderRepaymentTerm*, and categorical *repaymentInterval*, after units are harmonised. Country, sector, and one indicator per fundraising week provide baseline adjustment at the timescale on which pool composition and lender demand actually move; year-month indicators are a robustness check, and week indicators adjust baseline timing only. Unresolved variables are excluded. Standard errors are two-way clustered by country and week. If country clusters are too few, week-clustered errors become primary with a country wild-cluster bootstrap. We report coefficients, intervals, magnitudes, and diagnostics for collinearity, influential durations, and residuals, not significance alone.

The nested models test conditional predictive information, not an independent effect.

A concrete use names a purchasable input, product, service, or action, not a generic purpose. Numerical detail means at least one identifiable digit-based quantity. Before outcome modelling we freeze a codebook and rules and draw 200 stratified records; two members, blind to duration, code them. If rule F1 is below 0.80 or either class is under 1%, the interaction is descriptive or omitted. Each accepted feature enters H2 with its main term and separate S_i interaction.

H4 adds S_i-by-sector interactions, beginning with a joint test. Sectors under 500 loans are pooled before outcomes are viewed, and comparisons use a 5% Benjamini–Hochberg false-discovery rate. Annual evolution uses S_i interacted with centred fundraising year while retaining week fixed effects. Sector and year profiles are reported descriptively whatever the joint tests show.

### Robustness, reproducibility, and one-week delivery

Further checks use prior 7- and 30-day pools, character n-gram TF–IDF, alternative text fields, a pool-normalised threshold share, raw counts, and untransformed days, each matched across both measures. Specifications are frozen before results, and all variants reported.

Day 1 audits data and freezes H1/H2 and the H3 codebook; Day 2 builds measures and draws H3’s blinded sample; Day 3 reproduces H1/H2; Day 4 completes H3 coding; Day 5 completes H4 and robustness; Days 6–7 cover interpretation, reruns, and quality checks.

If active intervals cannot be reconstructed, the 14-day cohort carries both measures alone, renamed recent-listing density and similarity. If the core pipeline slips by Day 3, we drop robustness variants first, then H4’s inferential tests while keeping its descriptive profiles, then H3. Geography, monthly heterogeneity, or COVID starts only after H1/H2, H3, H4, and core quality checks are complete. Unknown risk-set ends trigger the 14-day fallback or stop the branch. Censored data use log-normal AFT on the same shifted duration, with a pre-specified country/week block bootstrap. If all loans are funded, the estimand is funded-loan duration, not funding success.

## 3. Data Items to Be Used

The loan is the analysis unit. *fundraisingDate* and *raisedDate* define timing; *description* supplies the primary text, and *use* supplies the H3 features. Candidate structured fields are *loanAmount*, *borrowerCount*, *lenderRepaymentTerm*, *repaymentInterval*, *sector*, *country_name*, *disbursalDate*, and posting time. Where *disbursalDate* precedes posting, faster funding refreshes partner capital rather than bringing the borrower’s cash forward; we will audit how often this holds and control for the gap. Before modelling we audit types, missingness, duplicates, date errors, censoring, language, and category sizes.

The available file has 100 funded loans, 27 fields, and unique identifiers; its sampling and representativeness are unknown. It will test parsing, cleaning, pool reconstruction, feature coding, and model code only—not population associations, power, funding success, or causation.

Names, exact locations, image links, and full stories may increase borrower re-identification risk; they will not appear in outputs. We minimise fields and report aggregates. Data licence, privacy, and AI rules remain unconfirmed; any unpermitted field or tool will be removed.

We will not interpret duration as borrower quality.

## 4. Expected Outcomes and Managerial Relevance

The project will deliver an auditable crowding/saturation framework, uncertainty-aware H1/H2 estimates, and a descriptive profile of sector and year variation. Subject to pre-set validation and feasibility gates, it also reports H3 interactions and inferential H4 tests. Results may support, oppose, or remain inconclusive for each hypothesis.

Versioned dictionaries, logs, specifications, and scripts will trace reported numbers to inputs.

If saturation remains positively associated with duration after measured crowding is included, platforms could test similarity monitoring at posting, diversified listing pages, and writing support where queues are most repetitive. For borrowers and field partners in subsistence marketplaces, the same estimates address a lever cheaper than loan size or terms: how an appeal is written and when it is posted. Only a confidence-interval upper bound below a pre-defined minimum managerially meaningful positive association would support deprioritising repetition-based intervention; otherwise evidence is inconclusive. H3 patterns can inform candidate guidance for a later experiment, not establish that adding a feature accelerates funding. Sector or annual differences identify contexts for validation, not universal rules.

The reconstructed pool is not individual exposure, and TF–IDF cosine measures lexical overlap rather than psychological fatigue. Descriptions are partner-written and no partner identifier is released, so saturation partly reflects template prevalence that country and sector adjustment cannot absorb. Ranking, traffic, translation, unobserved loan quality, and lender demand may relate to both text and duration. The study therefore supports conditional associations, not causation; platform changes require prospective experimental or otherwise credible causal evaluation.
