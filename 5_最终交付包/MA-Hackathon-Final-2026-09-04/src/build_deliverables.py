#!/usr/bin/env python3
"""Build the evidence-linked report source and final supporting documents."""

from __future__ import annotations

import importlib.metadata
import json
import math
import os
import sys
from pathlib import Path

import pandas as pd


GENERATED_AT = "2026-08-28T12:00:00Z"
UNSW_URL = "https://www.unsw.edu.au/business/our-schools/marketing/news-events/student-events/MA-hackathon"


def atomic_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(content.rstrip() + "\n", encoding="utf-8")
    os.replace(temporary, path)


def atomic_json(path: Path, payload: dict) -> None:
    atomic_text(path, json.dumps(payload, indent=2, ensure_ascii=False))


def clean_records(frame: pd.DataFrame) -> list[dict]:
    return json.loads(frame.where(pd.notna(frame), None).to_json(orient="records"))


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: build_deliverables.py OUTPUT_DIR")
    root = Path(sys.argv[1]).resolve()
    out = root / "outputs"
    audit = root / "audit"

    scenario = pd.read_csv(out / "scenario_contrasts.csv")
    main_table = pd.read_csv(out / "rq1_main_table.csv")
    robust = pd.read_csv(out / "robustness.csv")
    residual = pd.read_csv(out / "rq2_raw_vs_residual.csv")
    description = pd.read_csv(out / "description_robustness.csv")
    holdout = pd.read_csv(out / "holdout_validation.csv")
    years = pd.read_csv(out / "rq3_year_effects.csv")
    year_global = pd.read_csv(out / "rq3_global_tests.csv")
    support = pd.read_csv(out / "joint_support_summary.csv")
    sample_flow = pd.read_csv(out / "model_sample_flow.csv")
    profile = pd.read_csv(out / "data_profile_summary.csv")
    text_share = pd.read_csv(out / "boilerplate_share_distribution.csv")
    fairness = pd.read_csv(out / "fairness_diagnostics.csv")

    def scenario_row(channel: str, outcome: str) -> pd.Series:
        return scenario[(scenario.channel == channel) & (scenario.outcome == outcome)].iloc[0]

    cur_time = scenario_row("current", "log_funding_hours")
    cur_72 = scenario_row("current", "funded_within_72h")
    rec_time = scenario_row("recent", "log_funding_hours")
    rec_72 = scenario_row("recent", "funded_within_72h")

    def coefficient(frame: pd.DataFrame, model: str, term: str) -> pd.Series:
        return frame[(frame.model == model) & (frame.term == term)].iloc[0]

    raw_ch = coefficient(robust, "active_raw_main", "CH")
    raw_vg = coefficient(robust, "active_raw_main", "VG")
    residual_ch = coefficient(robust, "active_residual_text", "CH")
    residual_vg = coefficient(robust, "active_residual_text", "VG")
    d_ch = description[description.term == "CH"].iloc[0]
    d_vg = description[description.term == "VG"].iloc[0]

    def hv(task: str, slice_name: str, model: str, metric: str) -> float:
        row = holdout[
            (holdout.task == task)
            & (holdout.evaluation_slice == slice_name)
            & (holdout.model == model)
            & (holdout.metric == metric)
        ]
        return float(row.value.iloc[0])

    log_mae_control = hv("funding_duration", "2025_at_least_35d_followup", "controls_only", "mae_log_hours")
    log_mae_narrative = hv("funding_duration", "2025_at_least_35d_followup", "controls_plus_narrative", "mae_log_hours")
    hour_mae_control = hv("funding_duration", "2025_at_least_35d_followup", "controls_only", "mae_hours")
    hour_mae_narrative = hv("funding_duration", "2025_at_least_35d_followup", "controls_plus_narrative", "mae_hours")
    brier_control = hv("fast_funding_72h", "2025_72h_eligible", "controls_only", "brier")
    brier_narrative = hv("fast_funding_72h", "2025_72h_eligible", "controls_plus_narrative", "brier")
    auc_control = hv("fast_funding_72h", "2025_72h_eligible", "controls_only", "roc_auc")
    auc_narrative = hv("fast_funding_72h", "2025_72h_eligible", "controls_plus_narrative", "roc_auc")
    logloss_control = hv("fast_funding_72h", "2025_72h_eligible", "controls_only", "log_loss")
    logloss_narrative = hv("fast_funding_72h", "2025_72h_eligible", "controls_plus_narrative", "log_loss")

    train_n = int(sample_flow.loc[sample_flow.step.eq("main train 2016-2024"), "loans"].iloc[0])
    holdout_n = int(sample_flow.loc[sample_flow.step.eq("main holdout 2025"), "loans"].iloc[0])
    rows = int(profile.loc[0, "rows"])
    text_manifest = json.loads((audit / "stage2_text_manifest.json").read_text())
    pool_manifest = json.loads((audit / "stage3_feature_manifest.json").read_text())
    pool_identity = pd.read_csv(out / "pool_identity_summary.csv").iloc[0]
    desc_manifest = json.loads((audit / "description_robustness_manifest.json").read_text())
    vectorizer_config = json.loads(
        (root / "model_artifacts" / "text_vectorizer_config.json").read_text()
    )["recurring_language"]
    threshold_choice = pd.read_csv(out / "co_outcome_threshold_choice.csv")
    selected_threshold = threshold_choice[threshold_choice.candidate_hours == 72].iloc[0]
    best_alternative = threshold_choice[threshold_choice.candidate_hours != 72].bernoulli_variance.max()
    washin_n = int(sample_flow.loc[sample_flow.step.eq("wash-in eligible"), "loans"].iloc[0])
    followup_audit = pd.read_csv(out / "late_2025_followup_audit.csv").set_index("followup_band")
    train_quantiles = pd.read_csv(out / "funding_duration_quantiles_train_2016_2024.csv").iloc[0]
    valid_n = int(sample_flow.iloc[0].loans)

    report = f"""# 当每个故事听起来都一样：Kiva 叙事注意力研究最终报告

**团队：5 GUYS · UNSW Marketing Analytics Hackathon 2026 Finalist**  
**最终演示日：2026 年 9 月 4 日（以 UNSW 官方页面为准）**  
**报告状态：完整真实数据分析；未做外部提交；所有结果均为条件相关性。**

## 技术摘要

本研究把“融资慢”拆成两个待检验的注意力通道：**当前竞争**（同一板块此刻在募的贷款又多又像）与**近期列表语言代理**（上架于 35–65 天前的同板块贷款又多又像）。后者没有观测 impressions、page exit 或记忆，因此只能作为 wear-out 假设的 posting-age proxy。主模型使用 {train_n:,} 笔 2016–2024 训练贷款，2025 年 {holdout_n:,} 笔主样本保持为时间留出集。[来源：`outputs/model_sample_flow.csv`、`outputs/frozen_spec.csv`]

最强结论来自当前环境。在 `log(1 + funding hours)` 模型中，当前 volume 与 focal-to-pool lexical overlap 同时从训练样本 P25 移到 P75，对应 **`1 + funding hours` 条件几何均值增加 {cur_time.translated_effect:.2f}%**（95% CI {cur_time.translated_ci_low:.2f}% 至 {cur_time.translated_ci_high:.2f}%），比值为 **{math.exp(cur_time.estimate_model_scale):.2f}**。这不是算术平均融资时长。独立的 72 小时共同结果显示，完成融资概率下降 **{abs(cur_72.translated_effect):.2f} 个百分点**（95% CI {cur_72.translated_ci_low:.2f} 至 {cur_72.translated_ci_high:.2f} 个百分点）。[来源：`outputs/scenario_contrasts.csv`]

近期列表代理没有得到同等强度的结果：联合 P25→P75 情景在同一 log-time back-transform 上为 **{rec_time.translated_effect:.2f}%**（95% CI {rec_time.translated_ci_low:.2f}% 至 {rec_time.translated_ci_high:.2f}%），72 小时概率为 **{rec_72.translated_effect:.2f} 个百分点**（95% CI {rec_72.translated_ci_low:.2f} 至 {rec_72.translated_ci_high:.2f}）。两个区间均跨零，因此不能把局部 `V×G` interaction 升格为稳健的 average wear-out 结论。[来源：`outputs/scenario_contrasts.csv`]

2025 留出验证进一步收窄了可执行边界：加入叙事特征后，35 天完整随访样本的 log-hour MAE 为 {log_mae_narrative:.4f}，controls-only 为 {log_mae_control:.4f}；72 小时 Brier 为 {brier_narrative:.4f} 对 {brier_control:.4f}，AUC 为 {auc_narrative:.4f} 对 {auc_control:.4f}。Log-loss 从 {logloss_control:.4f} 小幅改善到 {logloss_narrative:.4f}，但整体不足以支持部署 borrower scoring。[来源：`outputs/holdout_validation.csv`]

**决策建议：不要部署 Narrative Attention Engine 给借款人打分。把当前饱和度用作实验触发条件，优先测试 listing 排期/曝光多样化与 partner-approved 模板替代方案。**

## 研究范围与数据边界

- 官方数据共 {rows:,} 条贷款，覆盖 2016-01-01 至 2025-12-31；其中 6 条 `raisedDate < fundraisingDate` 被排除。[来源：`outputs/data_profile_summary.csv`]
- 数据集中每条记录都有 `raisedDate`。因此本提取物不能识别真正的 right censoring，也不支持把结果解释为“所有上架贷款的融资成功概率”；本研究分析的是提取物中已观察到 raisedDate 的贷款。[来源：`outputs/status_raised_crosstab.csv`]
- 主结果使用 `log(1 + funding hours)`；并报告 72 小时快速融资的共同结果。2025 年末随访不足 72 小时的记录不进入 72 小时评估。[来源：`outputs/followup_eligibility.csv`]
- 所有时间统一为 UTC。训练期为 2016–2024；IDF、标准化参数和所有学习步骤只在训练期拟合，然后固定应用于 2025。[来源：`outputs/frozen_spec.csv`]
- `fundsLentInCountry` 等上架后才确定的字段不进入模型；输出不包含姓名、精确地点或完整叙事原文。

## 测量设计：在贷款上架的一刻重建注意力市场

对每笔 focal loan，我们计算同板块的两套环境：

1. **Current channel**：`C = log1p(active same-sector count)`；`H = focal narrative 与 active pool 的平均余弦相似度`（focal-to-pool lexical overlap，不是 pool 内 pairwise homogeneity）；当前饱和度为标准化后的 `C×H`。
2. **Recent-listing proxy**：`V = [35,65)` 天 posting-age 窗口内按 7 天半衰期加权的较早贷款量；`G = 同一加权池的平均相似度`；代理饱和度为标准化后的 `V×G`。主池不要求较早贷款已经结束，也没有 lender exposure 数据；completed-only lag 仅作为灵敏度检验。

主文本字段是经过姓名、地点、金额、日期等 masking 的 `use`；TF–IDF 使用 hashed word unigram/bigram（2^17 features）与只在训练期拟合的 smooth IDF。409 个在至少 659 份训练文档且跨至少 3 个国家出现的逐字 5-gram 被定义为 recurring language；因为数据没有 partner ID，“跨国家”只是来源代理，不能用于归因某一机构。[来源：`audit/stage2_text_manifest.json`、`outputs/boilerplate_like_phrases.csv`]

相似度不是两两暴力枚举，而使用严格恒等式 `mean cosine = focal vector · mean pool vector`。200 笔 focal loans × 3 个池的 600 次验证中，raw 最大绝对误差为 {pool_identity.max_abs_error_raw:.3e}，residual 为 {pool_identity.max_abs_error_residual:.3e}，低于 1e-9 验收线。[来源：`outputs/pool_identity_summary.csv`、`audit/stage3_feature_manifest.json`]

P25/P75 联合情景也通过了局部支持检查：在两个维度均为 ±0.10 IQR 的邻域中，每个 current/recent 端点至少有 {int(support.n_near_endpoint.min()):,} 笔真实训练记录。这个检查只说明情景端点并非空洞外推，不建立可交换性或因果识别。[来源：`outputs/joint_support_summary.csv`]

## 发现一：当前市场饱和是强烈但非因果的诊断信号

主 HDFE 模型控制 loan amount、borrower count、repayment term、平台 7 天上架量，并吸收 country、activity、week、gender、repayment interval、posting day/hour fixed effects；标准误按 country 与 week 双向聚类。`C×H` 系数为 {raw_ch.estimate:.4f}（95% CI {raw_ch.ci_low:.4f} 至 {raw_ch.ci_high:.4f}，p={raw_ch.p_value:.4g}）。[来源：`outputs/rq1_main_table.csv`]

实际解释采用完整联合情景而不是把 interaction coefficient 单独翻译成百分比：当前 volume 与 focal-to-pool lexical overlap 同时从 P25 移到 P75，对应 `1 + funding hours` 条件几何均值 **+{cur_time.translated_effect:.2f}%**、72 小时概率 **{cur_72.translated_effect:.2f}pp**。前者不是算术平均融资时长；两者都是观测数据下的 conditional association，不是 Kiva 改版后的 intervention forecast。[来源：`outputs/scenario_contrasts.csv`]

## 发现二：模板语言可能贡献当前信号，但不能做因果分解

原始 masked use 的 `C×H` 为 {raw_ch.estimate:.4f}（p={raw_ch.p_value:.4g}）；移除 recurring language 后为 {residual_ch.estimate:.4f}（p={residual_ch.p_value:.3f}）。估计约减半且不再达到常规显著性，但这不等于“模板解释了一半”，因为两套系数的差异没有经过正式的跨模型差异检验。[来源：`outputs/robustness.csv`]

description 灵敏度提供补充证据：masked description 的 `C×H` 为 {d_ch.estimate:.4f}（95% CI {d_ch.ci_low:.4f} 至 {d_ch.ci_high:.4f}，p={d_ch.p_value:.4g}），而 `V×G` 为 {d_vg.estimate:.4f}（95% CI {d_vg.ci_low:.4f} 至 {d_vg.ci_high:.4f}，p={d_vg.p_value:.3f}）。50 笔 focal loans × 2 个池的恒等式检查最大误差 {desc_manifest['identity_max_abs_error']:.3e}，通过 1e-9 标准。[来源：`outputs/description_robustness.csv`、`audit/description_robustness_manifest.json`]

管理含义不是要求 borrower “讲得更响”，而是测试平台与 Lending Partner 的模板、排期和曝光流程。

## 发现三：局部 recent-listing interaction 不能升级为平均 wear-out

Raw `V×G` 系数为 {raw_vg.estimate:.4f}（p={raw_vg.p_value:.4g}），residual 为 {residual_vg.estimate:.4f}（p={residual_vg.p_value:.4g}）。但这两个系数检验的是 posting-age proxy 的 conditional interaction；联合 P25→P75 情景同时包含 `V`、`G` 与 `V×G`，其 log-time back-transform 为 {rec_time.translated_effect:.2f}% 且置信区间跨零。[来源：`outputs/robustness.csv`、`outputs/scenario_contrasts.csv`]

同时，14 天与 16 天 posting window 下 current `C×H` 保持正向且显著，而 time-based specification 中 lagged `V×G` 不显著。这说明 current 结果对窗口较稳健，但对文本分解敏感；recent 结果不足以支持优先投入 wear-out editorial intervention。[来源：`outputs/robustness.csv`]

## 时间与板块异质性：存在变化，但不应用于排名

2016–2024 的 year-specific scenario contrasts 显示两条通道显著波动；year、sector 与 country 的全局异质性筛查均提示差异。[来源：`outputs/rq3_year_effects.csv`、`outputs/rq3_global_tests.csv`、`outputs/rq4_sector_global_tests.csv`、`outputs/rq4_country_global_tests.csv`]

这些结果保持探索性：country heterogeneity 只覆盖训练量最高的 15 个国家，sector 模型覆盖 14 个达到估计门槛的板块；许多 subgroup 置信区间较宽，且全局 Q screen 没有估计“共享 week shocks 导致的跨组协方差”。因此报告不从排序中挑选“最佳国家/板块”，更不把异质性用于 borrower targeting。

## 2025 留出验证：解释性信号没有转化为稳定增量预测

在 2025 至少 35 天随访的 {int(holdout[(holdout.evaluation_slice == '2025_at_least_35d_followup')].n.iloc[0]):,} 笔贷款上，controls-only 与 controls+narrative 的 log-hour MAE 分别为 {log_mae_control:.4f} 与 {log_mae_narrative:.4f}；hour MAE 为 {hour_mae_control:.2f} 与 {hour_mae_narrative:.2f}。[来源：`outputs/holdout_validation.csv`]

在 72 小时评估中，Brier 为 {brier_control:.4f} 对 {brier_narrative:.4f}，AUC 为 {auc_control:.4f} 对 {auc_narrative:.4f}；log-loss 为 {logloss_control:.4f} 对 {logloss_narrative:.4f}。我们没有为这些 metric differences 计算 paired uncertainty，因此准确表述是“叙事模型没有在主要运营指标上超过 baseline”，而不是“显著变差”。[来源：`outputs/holdout_validation.csv`]

校准在多个性别与板块分组中仍有明显 gap；这些诊断只用于 guardrail，不能成为 protected-group targeting 的依据。[来源：`outputs/fairness_diagnostics.csv`]

## 决策建议：做平台实验，不做借款人评分

### Pilot A · 当前饱和下的排期与曝光实验

- 进入条件：预先定义 high-current-saturation 市场状态；不以 borrower quality 为条件。
- 随机化：business-as-usual exposure 对 staggered listing / diversified related-loan exposure。
- Primary outcomes：time-to-funding、72-hour funding probability。
- Guardrails：总融资量、不同 country/sector 的分配、公平性、borrower workload。

### Pilot B · Partner-approved 模板替代实验

- 随机化单位与干预内容必须由 Kiva/Lending Partner 在上线前确定。
- 对比现行模板与多个合规替代模板；不得要求 borrower 提供更敏感或更长的个人叙述。
- 先注册 MDE、分析窗口、停止规则与异质性检验，避免事后挑选结果。

### 明确禁止

- 不把 Narrative Attention Engine 部署为 borrower ranking、approval、penalty 或自动改写工具。
- 不把 saturation 分数解释为 borrower quality、creditworthiness 或 moral worth。
- 不基于未校准的 subgroup score 调整曝光。

## 关键限制与下一步问题

1. 数据没有 impressions、ranking、clicks、promotion、image quality 与 partner ID；这些遗漏因素可能同时影响饱和度与融资速度。
2. Active pool 的持续时间受此前融资结果影响，仍有内生性；14/16 天 precommitted posting windows 降低但不能完全消除混杂。
3. TF–IDF 衡量 lexical repetition，不代表语义、视觉或多语言感知；country 只是来源代理。Recent 主池按 posting age 定义，不证明较早贷款已离开页面、被 lender 看见或留下记忆。
4. Raised-only extract 限制外推；本结果不能代表全部 posted loans 的成功概率。
5. 2025 holdout 暴露 temporal drift；任何运营应用必须重新校准并通过 prospective experiment。

下一步最重要的两个问题是：加入真实 exposure/ranking logs 后 current association 还剩多少？随机改变 listing mix 是否能改善融资速度且不把注意力从其他弱势 borrower 转移走？

## 可复现性与文件索引

- 已执行 notebooks：`notebooks/S0_prepare.ipynb` 至 `notebooks/S6_engine.ipynb`。
- 全量实现：`src/`；执行顺序见 `RUNBOOK.md`。
- 核心结果：`outputs/scenario_contrasts.csv`、`outputs/robustness.csv`、`outputs/holdout_validation.csv`。
- 300 dpi 图与配对 source CSV：`figures/` 与 `figures/source_data/`。
- 质量与运行证据：`audit/`、`logs/run_log.txt`。
- 官方挑战目标、日期与评审标准：[UNSW Marketing Analytics Hackathon Challenge 2026]({UNSW_URL})。

> 版本说明：本报告根据全量真实输出写成；附件中的 runbook/prompt 仅作为团队早期来源材料，实际执行以保存的代码、审计和冻结规格为准。
"""
    atomic_text(root / "REPORT.md", report)

    methods = f"""# Methods and Validation Appendix

## Claim boundary

All reported effects are conditional associations. No coefficient is presented as a causal intervention effect, borrower-quality measure, or production-ready score.

## Cohorts

- Official extract: {rows:,} rows.
- Valid nonnegative funding duration: {valid_n:,} rows.
- After the 65-day wash-in: {washin_n:,}. The extract begins 2016-01-01, so focal loans posted
  in the first 65 days have no complete [35,65)-day lag window; they are excluded rather than
  scored against a partial pool. The exclusion depends only on the posting date, and the excluded
  and retained 2016 loans have near-identical duration distributions.
- Main HDFE training sample: {train_n:,} loans posted in 2016–2024.
- Untouched main holdout: {holdout_n:,} loans posted in 2025.
- 35-day holdout slice: {int(holdout[(holdout.evaluation_slice == '2025_at_least_35d_followup')].n.iloc[0]):,}.

## Outcomes

- Primary: `log(1 + funding_hours)`.
- A scenario back-transform, `exp(delta) - 1`, is the percent change in the conditional geometric mean of `1 + funding_hours`; it is not an arithmetic mean duration.
- Co-outcome: funded within 72 hours when at least 72 calendar hours of follow-up are observable.
  The eligibility window is not a separate choice: the label is undefined without 72 hours of
  observation. It removes no training loan, since 2016-2024 sits far inside the extract boundary.
- Why 72 hours: it is the nearest whole day to the training median of
  {selected_threshold.train_median_hours:.2f} hours. Binarising at the median gives
  {selected_threshold.pct_funded_within:.2f}% positives and Bernoulli variance
  {selected_threshold.bernoulli_variance:.4f}, the theoretical maximum, so the co-outcome carries
  maximal power; the best alternative among 1, 7 and 14 days reaches only {best_alternative:.4f}.
  Three days is also the unit Kiva triage already uses. Candidates: `outputs/co_outcome_threshold_choice.csv`.
- The binary co-outcome is immune to the extreme upper tail that `log(1 + funding_hours)` is
  sensitive to; agreement between the two is a specification check, and all six pool coefficients
  reverse sign across them as they must.
- No AFT model: the extract has no missing `raisedDate`, so true right censoring cannot be identified.

## Text and pools

- Masked hashed word (1,2)-gram TF–IDF, 2^17 features, train-only smooth IDF.
- Recurring-language threshold: exact 5-gram in at least {vectorizer_config['minimum_training_documents']:,}
  train documents and at least {vectorizer_config['minimum_countries']} countries;
  {vectorizer_config['approved_exact_phrases']:,} phrases qualified.
- Current active same-sector pool; 14-day and P75-calibrated 16-day posting pools as precommitted checks.
- Recent [35,65)-day posting-age pool with seven-day half-life; it is a lexical-environment proxy, not observed exposure or page exit. Completed-only lag is a sensitivity.
- Main raw pool threshold n>=10; lagged Kish effective n>=10; sensitivities n>=5 and n>=20.

## Model

`log_funding_hours ~ C + H + C×H + V + G + V×G + controls | country + activity + week`

Controls: log loan amount, log borrower count, log repayment term, log platform seven-day posting volume. Primary covariance: country/week two-way CRV1.

## Validation inventory

- Full pickle opcode audit: no dangerous opcodes; restricted primitive deserialization.
- Pool identity: 600 exact comparisons; max raw error {pool_identity.max_abs_error_raw:.3e}; max residual error {pool_identity.max_abs_error_residual:.3e}.
- Description identity: 100 exact comparisons; max error {desc_manifest['identity_max_abs_error']:.3e}.
- Joint support: minimum {int(support.n_near_endpoint.min()):,} loans inside an endpoint neighbourhood.
- Alternative windows, pool thresholds, completed-only lag, one-way/two-way clustering, raw/residual text and description sensitivity.
- 2025 out-of-time validation against a controls-only baseline. Both outcomes are scored on a
  full-follow-up slice as well as on all observed loans, so neither carries an unchecked
  truncation exposure.

## Right truncation at the 2025 boundary

The extract ends when the last loan finished fundraising, and every row carries a
`raisedDate`. A loan still raising at that instant is therefore absent rather than
censored: it appears only if `funding_hours <= T - t`, so the admissible window narrows
to zero as the posting time approaches the boundary and only the fastest survive. The
gradient in `outputs/late_2025_followup_audit.csv` is the signature — median duration
falls from {followup_audit.loc['at_least_35d_followup', 'median_funding_hours']:.1f}h with
full follow-up, to {followup_audit.loc['72h_to_35d_followup', 'median_funding_hours']:.1f}h
in the 72h-to-35d band, to {followup_audit.loc['less_than_72h_followup', 'median_funding_hours']:.1f}h
over the final 72 hours. This is truncation, not a year-end demand effect: a demand shift
moves the distribution but cannot pin the daily maximum observed duration to the remaining
window, which is what the data show.

Handling differs by outcome because the defect differs. For the binary co-outcome the
label is undefined, not biased, so the
{int(followup_audit.loc['less_than_72h_followup', 'loans']):,} loans with under 72 hours of
follow-up are ineligible. For the continuous outcome the recorded duration is correct and
nothing is deleted; instead `2025_all_observed` and `2025_at_least_35d_followup` are
reported side by side so the reader can see whether any conclusion depends on the choice.
The same 35-day constant serves both the lag pool and this slice, and for the same reason:
it is the training P95 of {train_quantiles.p95_hours:.2f} hours rounded up, so a focal loan
had a 95% chance to resolve. Because 35 days is 840 hours and exceeds that P95, a loan
posted exactly at the boundary loses under 5% of its conditional mass, and the loss falls
towards zero for earlier postings. Training years 2016-2024 sit at least one year inside
the boundary and are unaffected, so the main estimates carry no truncation exposure.

A second-order exposure is disclosed for completeness: pool features for late-2025 focal
loans are themselves built from the truncated population, since a loan that was live and
competing for attention but resolved after the extract is absent from the pool, which
understates the measured active pool. Kiva posts in batches, so the net distortion cannot
be given a clean point estimate. The `>=35d` slice removes this exposure as well, because
its focal loans look back over windows that close well inside the boundary.

## Known limitations

Missing exposure, ranking, click, promotion, image-quality and partner identifiers; active-pool endogeneity; the recent pool is a posting-age proxy rather than observed wear-out; lexical rather than semantic similarity; raised-only extract; temporal drift; country heterogeneity limited to the top 15 training-volume countries and sector heterogeneity to 14 estimable groups; subgroup cross-covariance not estimated in the Q screen.
"""
    atomic_text(root / "METHODS_APPENDIX.md", methods)

    runbook = """# RUNBOOK · Full Analysis and Audit Replay

The final notebooks are quick, independently executable audit views of saved aggregate checkpoints. The full-data computations live in `src/` and require the original Kiva pickle in a private work directory. Never copy raw text or the original pickle into this package. The external ZIP also omits row-level model/feature checkpoints and per-loan triage scores; regenerate them only inside the controlled work environment.

## Environment

Create a Python 3.13 virtual environment and install the versions in `requirements-lock.txt`. Commands below use placeholders so no private machine path is embedded:

```bash
export WORK_DIR=/absolute/private/work-directory
export OUTPUT_DIR=/absolute/final-output-directory
export RAW_GLOB="$WORK_DIR/data/raw_parquet/*.parquet"
export PYTHON=/absolute/venv/bin/python
```

`src/create_and_execute_notebooks.py` executes the audit notebooks against a kernel named
`hackathon-final`; register it from the same virtual environment before running the
pipeline, or that step fails with `NoSuchKernel`:

```bash
$PYTHON -m ipykernel install --user --name hackathon-final --display-name "Hackathon Final (Python)"
```

## Safe intake

Before deserialising any pickle, run `src/safe_pickle_audit.py`. Convert only with the restricted primitive unpickler in `src/convert_pickle_to_parquet.py`. The provided final archive intentionally omits the original pickle and private text checkpoints.

## Full pipeline

```bash
$PYTHON src/profile_and_prepare.py "$RAW_GLOB" "$WORK_DIR" "$OUTPUT_DIR"
$PYTHON src/freeze_spec.py "$WORK_DIR" "$OUTPUT_DIR" "$WORK_DIR/data/clean/core.parquet"
$PYTHON src/text_pipeline.py "$WORK_DIR" "$OUTPUT_DIR"
$PYTHON src/build_pool_features.py "$WORK_DIR" "$OUTPUT_DIR"
$PYTHON src/prepare_model_data.py "$WORK_DIR" "$OUTPUT_DIR"
$PYTHON src/fit_main_models.py "$OUTPUT_DIR"
$PYTHON src/fit_heterogeneity.py "$OUTPUT_DIR"
$PYTHON src/predict_engine.py "$OUTPUT_DIR"
$PYTHON src/description_robustness.py "$WORK_DIR" "$OUTPUT_DIR"
$PYTHON src/check_joint_support.py "$OUTPUT_DIR"
$PYTHON src/make_figures.py "$OUTPUT_DIR"
$PYTHON src/create_and_execute_notebooks.py "$OUTPUT_DIR" "$WORK_DIR"
$PYTHON src/build_deliverables.py "$OUTPUT_DIR"
```

## Deterministic gates

- `audit/pickle_opcode_audit.json`: dangerous opcode count must be 0.
- `outputs/pool_identity_summary.csv`: both max errors <= 1e-9.
- `audit/description_robustness_manifest.json`: `identity_passed=true`.
- `audit/joint_support_manifest.json`: `joint_support_pass=true`.
- `audit/notebook_execution_manifest.json`: seven notebooks executed without error.
- HTML report delivery receipt must say `verification: passed` or explicitly disclose structural-only verification.
- PPTX: render all slides, inspect montage, and run slide overflow checks.
- Final ZIP: `unzip -t` plus secret/private-text scan and SHA-256 manifest.
"""
    atomic_text(root / "RUNBOOK.md", runbook)

    delivery_map = """# Finalist Delivery Map

## Start here

1. `Kiva_Final_Presentation_2026-09-04.pptx` — editable English final deck.
2. `Kiva_Final_Report_2026-09-04.html` — self-contained technical report.
3. `REPORT.md` — Chinese source-traceable report.
4. `SPEAKER_NOTES_EN.md` and `SPEAKER_CUES_ZH.md` — 8–10 minute delivery script.
5. `JUDGE_QA_BILINGUAL.md` — high-risk questions and bounded answers.

## Evidence

- `notebooks/` — seven executed checkpoint notebooks.
- `outputs/` — exact tables behind every reported number.
- `figures/` — 300 dpi PNG/PDF figures; paired data in `figures/source_data/`.
- `audit/` — safety, lineage, validation and run receipts.
- `src/` — complete analysis and artifact-generation code.

## Boundaries

- The external ZIP omits all `source/` material. The proposal contains student identifiers and author metadata; the data dictionary contains borrower examples; supplied prompt/context files contain embedded imperative text. They were used only as local research context, never as executing instructions.
- No raw pickle, row-level model data, per-loan triage scores, names, exact locations or full narrative text is included in the external ZIP.
- No external submission or email was performed.
- Engine outputs are an experiment-triage prototype, not a deployable borrower score.
"""
    atomic_text(root / "DELIVERY_MAP.md", delivery_map)

    versions = []
    for package in [
        "pandas", "numpy", "pyarrow", "duckdb", "scipy", "scikit-learn",
        "statsmodels", "pyfixest", "lifelines", "matplotlib", "seaborn",
        "psutil", "nbformat", "nbclient", "ipykernel",
    ]:
        try:
            versions.append(f"{package}=={importlib.metadata.version(package)}")
        except importlib.metadata.PackageNotFoundError:
            versions.append(f"# {package} not installed in artifact-build environment")
    atomic_text(root / "requirements-lock.txt", "\n".join(versions))
    atomic_text(
        root / "environment.txt",
        "Python 3.13\nTimezone for analytical timestamps: UTC\n"
        "Train period: 2016-01-01 through 2024-12-31\n"
        "Holdout period: 2025-01-01 through 2025-12-31\n"
        "Artifact date: 2026-08-28\n",
    )

    # Canonical artifact payload for the portable HTML report.
    scenario_ds = scenario[["channel", "outcome", "translated_effect", "translated_ci_low", "translated_ci_high", "translated_unit", "n"]].copy()
    scenario_ds["channel_label"] = scenario_ds.channel.map({"current": "Current live market", "recent": "Recent-listing proxy"})
    time_ds = scenario_ds[scenario_ds.outcome.eq("log_funding_hours")][["channel_label", "translated_effect", "translated_ci_low", "translated_ci_high"]]

    spec_names = {
        "active_raw_main": "Active · masked use",
        "active_residual_text": "Active · recurring removed",
        "posting_14d_precommitted": "14-day posting",
        "posting_16d_calibrated": "16-day posting",
        "completed_only_lag": "Completed-only lag",
    }
    robust_ds = robust[robust.model.isin(spec_names) & robust.term.isin(["CH", "VG"])].copy()
    robust_ds["specification"] = robust_ds.model.map(spec_names)
    robust_ds["channel"] = robust_ds.term.map({"CH": "Current", "VG": "Recent"})
    robust_ds = robust_ds[["specification", "channel", "estimate", "ci_low", "ci_high", "p_value", "n"]]

    year_columns = ["group", "channel", "scenario_percent_change", "scenario_ci_low", "scenario_ci_high", "n"]
    if "scenario_unit" in years.columns:
        year_columns.append("scenario_unit")
    year_ds = years[year_columns].copy()
    year_ds = year_ds.rename(columns={"group": "year"})
    year_ds["channel"] = year_ds.channel.map({"current": "Current", "recent": "Recent"})

    hold_rows = []
    for label, task, slice_name, metric, higher_better in [
        ("Log-hour MAE", "funding_duration", "2025_at_least_35d_followup", "mae_log_hours", False),
        ("Hour MAE", "funding_duration", "2025_at_least_35d_followup", "mae_hours", False),
        ("Brier score", "fast_funding_72h", "2025_72h_eligible", "brier", False),
        ("ROC AUC", "fast_funding_72h", "2025_72h_eligible", "roc_auc", True),
        ("Log loss", "fast_funding_72h", "2025_72h_eligible", "log_loss", False),
    ]:
        base = hv(task, slice_name, "controls_only", metric)
        enhanced = hv(task, slice_name, "controls_plus_narrative", metric)
        relative = 100 * (enhanced / base - 1)
        deterioration = -relative if higher_better else relative
        hold_rows.append({"metric": label, "controls_only": base, "controls_plus_narrative": enhanced, "relative_deterioration_pct": deterioration})
    hold_ds = pd.DataFrame(hold_rows)

    headline = pd.DataFrame(
        [
            {
                "current_geo_1p_hours_pct": float(cur_time.translated_effect),
                "current_geo_1p_hours_ci_low": float(cur_time.translated_ci_low),
                "current_geo_1p_hours_ci_high": float(cur_time.translated_ci_high),
                "current_72_pp": float(cur_72.translated_effect),
                "recent_geo_1p_hours_pct": float(rec_time.translated_effect),
                "train_loans_m": train_n / 1_000_000,
                "holdout_auc_delta": auc_narrative - auc_control,
            }
        ]
    )

    def structured_source(identifier: str, label: str, path: str, description_text: str) -> dict:
        return {
            "id": identifier,
            "label": label,
            "path": path,
            "query": {
                "engine": "duckdb",
                "language": "sql",
                "sql": f"SELECT * FROM read_csv_auto('{path}')",
                "description": description_text,
                "executed_at": GENERATED_AT,
                "tables_used": [path],
            },
        }

    sources = [
        structured_source("scenario", "Scenario contrasts", "outputs/scenario_contrasts.csv", "Loads the reviewed joint P25-to-P75 current and recent-listing scenario estimates with explicit units."),
        structured_source("robustness", "Robustness specifications", "outputs/robustness.csv", "Loads the reviewed HDFE robustness coefficient table."),
        structured_source("holdout", "2025 holdout validation", "outputs/holdout_validation.csv", "Loads the reviewed controls-only and narrative-enhanced out-of-time metrics."),
        structured_source("year", "Year-specific effects", "outputs/rq3_year_effects.csv", "Loads the reviewed year-specific scenario effects and uncertainty."),
        structured_source("support", "Joint support diagnostic", "outputs/joint_support_summary.csv", "Loads the endpoint-neighbourhood support counts."),
        structured_source("sample", "Model sample flow", "outputs/model_sample_flow.csv", "Loads the reviewed analytical sample counts."),
        structured_source("description", "Description sensitivity", "outputs/description_robustness.csv", "Loads the reviewed description-text sensitivity model."),
        {"id": "unsw", "label": "UNSW Marketing Analytics Hackathon 2026", "href": UNSW_URL},
    ]

    cards = [
        {
            "id": "current_time_card", "dataset": "headline", "sourceId": "scenario",
            "description": "Back-transform of the log1p-hours scenario; this is not an arithmetic mean duration.",
            "metrics": [{"label": "Geo. mean(1 + hours) change (%)", "field": "current_geo_1p_hours_pct", "format": "number", "signed": True}],
        },
        {
            "id": "current_72_card", "dataset": "headline", "sourceId": "scenario",
            "description": "Percentage-point change in 72-hour funding probability.",
            "metrics": [{"label": "72-hour association (pp)", "field": "current_72_pp", "format": "number", "signed": True}],
        },
        {
            "id": "recent_time_card", "dataset": "headline", "sourceId": "scenario",
            "description": "Recent-listing P25→P75 log-time contrast; confidence interval crosses zero.",
            "metrics": [{"label": "Recent geo. mean(1 + hours) change (%)", "field": "recent_geo_1p_hours_pct", "format": "number", "signed": True}],
        },
        {
            "id": "sample_card", "dataset": "headline", "sourceId": "sample",
            "description": "Main HDFE estimation sample, 2016–2024.",
            "metrics": [{"label": "Training loans (M)", "field": "train_loans_m", "format": "number"}],
        },
    ]

    charts = [
        {
            "id": "channel_time_chart", "title": "Joint saturation scenarios", "subtitle": "Change in the conditional geometric mean of 1 + funding hours, 2016–2024", "showDescription": True,
            "type": "bar", "dataset": "channel_time", "sourceId": "scenario", "layout": "full", "valueFormat": "number", "unit": "%",
            "encodings": {"x": {"field": "channel_label", "type": "nominal", "label": "Attention channel"}, "y": {"field": "translated_effect", "type": "quantitative", "label": "Geo. mean(1 + hours) change", "unit": "%"}},
            "referenceLines": [{"axis": "y", "value": 0, "label": "No change"}],
        },
        {
            "id": "robust_chart", "title": "Interaction estimates across specifications", "subtitle": "Standardised HDFE coefficients; confidence intervals are shown in the adjacent table", "showDescription": True,
            "type": "bar", "dataset": "robustness", "sourceId": "robustness", "layout": "full", "valueFormat": "number",
            "encodings": {"x": {"field": "specification", "type": "nominal", "label": "Specification"}, "y": {"field": "estimate", "type": "quantitative", "label": "Interaction coefficient"}, "color": {"field": "channel", "type": "nominal", "label": "Channel"}},
            "referenceLines": [{"axis": "y", "value": 0, "label": "Null"}],
        },
        {
            "id": "year_chart", "title": "Year-specific joint scenario contrasts", "subtitle": "P25→P75 change in conditional geometric mean of 1 + funding hours", "showDescription": True,
            "type": "line", "dataset": "year_effects", "sourceId": "year", "layout": "full", "valueFormat": "number", "unit": "%",
            "encodings": {"x": {"field": "year", "type": "ordinal", "label": "Training year"}, "y": {"field": "scenario_percent_change", "type": "quantitative", "label": "Geo. mean(1 + hours) change", "unit": "%"}, "color": {"field": "channel", "type": "nominal", "label": "Channel"}},
            "referenceLines": [{"axis": "y", "value": 0, "label": "No change"}],
        },
        {
            "id": "holdout_chart", "title": "2025 relative deterioration after adding narrative features", "subtitle": "Positive values are worse; negative log-loss is the only slight improvement", "showDescription": True,
            "type": "bar", "dataset": "holdout_delta", "sourceId": "holdout", "layout": "full", "valueFormat": "number", "unit": "%",
            "encodings": {"x": {"field": "metric", "type": "nominal", "label": "Metric"}, "y": {"field": "relative_deterioration_pct", "type": "quantitative", "label": "Relative deterioration", "unit": "%"}},
            "referenceLines": [{"axis": "y", "value": 0, "label": "No difference"}],
        },
    ]

    tables = [
        {
            "id": "scenario_table", "title": "Scenario estimates and 95% intervals", "subtitle": "Joint P25→P75 contrasts in the main training sample", "showDescription": True,
            "dataset": "scenario", "sourceId": "scenario", "layout": "full", "density": "spacious", "defaultSort": {"field": "channel", "direction": "asc"},
            "columns": [
                {"field": "channel", "label": "Channel", "type": "text"},
                {"field": "outcome", "label": "Outcome", "type": "text"},
                {"field": "translated_effect", "label": "Effect", "format": "number"},
                {"field": "translated_ci_low", "label": "CI low", "format": "number"},
                {"field": "translated_ci_high", "label": "CI high", "format": "number"},
                {"field": "translated_unit", "label": "Unit", "type": "text"},
                {"field": "n", "label": "N", "format": "compact"},
            ],
        },
        {
            "id": "robust_table", "title": "Robustness coefficient detail", "subtitle": "Selected raw, residual, posting-window and completed-lag specifications", "showDescription": True,
            "dataset": "robustness", "sourceId": "robustness", "layout": "full", "density": "dense", "defaultSort": {"field": "specification", "direction": "asc"},
            "columns": [
                {"field": "specification", "label": "Specification", "type": "text"},
                {"field": "channel", "label": "Channel", "type": "text"},
                {"field": "estimate", "label": "Estimate", "format": "number"},
                {"field": "ci_low", "label": "CI low", "format": "number"},
                {"field": "ci_high", "label": "CI high", "format": "number"},
                {"field": "p_value", "label": "p-value", "format": "number"},
                {"field": "n", "label": "N", "format": "compact"},
            ],
        },
    ]

    blocks = [
        {"id": "title", "type": "markdown", "body": "# 当每个故事听起来都一样"},
        {"id": "technical_summary", "type": "markdown", "body": "## 技术摘要\n\n**最可靠的注意力信号发生在当下市场。** 当前同板块贷款又多、focal-to-pool lexical overlap 又高时，log-time 与 72 小时结果都更差；recent-listing posting-age proxy 不确定，2025 也没有提供一致的增量预测价值。结论因此指向平台实验，而不是借款人评分。"},
        {"id": "headline_metrics", "type": "metric-strip", "cardIds": ["current_time_card", "current_72_card", "recent_time_card", "sample_card"]},
        {"id": "scope", "type": "markdown", "body": "## 1. 数据与识别边界\n\n官方提取物覆盖 2016–2025。主分析只在 2016–2024 拟合文本、scaler 与 HDFE，并保留 2025 做 out-of-time 检验。每条有效记录都有 raisedDate，因此结果描述的是 extract 中已观察到 raisedDate 的贷款，而不是全部 posted loans 的成功概率。"},
        {"id": "main_result", "type": "markdown", "sourceId": "scenario", "body": f"## 2. 当前竞争是强烈的诊断信号\n\n当前 volume 与 focal-to-pool lexical overlap 联合从 P25 移到 P75 时，`1 + funding hours` 条件几何均值增加 **{cur_time.translated_effect:.2f}%**（95% CI {cur_time.translated_ci_low:.2f}% 至 {cur_time.translated_ci_high:.2f}%），72 小时融资概率下降 **{abs(cur_72.translated_effect):.2f}pp**。前者不是算术平均融资时长；两者都是条件相关性，不是干预预测。"},
        {"id": "channel_chart", "type": "chart", "chartId": "channel_time_chart"},
        {"id": "scenario_exact", "type": "table", "tableId": "scenario_table"},
        {"id": "representation", "type": "markdown", "body": "## 3. Recurring language 可能贡献当前信号\n\n移除 recurring language 后，current interaction 估计约减半并失去常规显著性；masked description 则再次呈现显著 current interaction、但不支持 recent interaction。数据没有 partner ID，因此不能把该语言归因于具体机构，也不能证明其造成了多少效果。"},
        {"id": "robust_chart_block", "type": "chart", "chartId": "robust_chart"},
        {"id": "robust_exact", "type": "table", "tableId": "robust_table"},
        {"id": "recent", "type": "markdown", "sourceId": "scenario", "body": f"## 4. Recent-listing proxy 不支持稳健的 average wear-out\n\nPosting-age proxy 的联合 P25→P75 log-time back-transform 为 **{rec_time.translated_effect:.2f}%**（95% CI {rec_time.translated_ci_low:.2f}% 至 {rec_time.translated_ci_high:.2f}%），72 小时结果为 **{rec_72.translated_effect:.2f}pp**（95% CI {rec_72.translated_ci_low:.2f} 至 {rec_72.translated_ci_high:.2f}）。主池不观测 exposure 或 page exit；局部 interaction 与联合净情景也回答不同问题。"},
        {"id": "heterogeneity", "type": "markdown", "body": "## 5. 时间异质性存在，但不适合排名\n\nYear、sector 与 country 的关联会变化。置信区间和跨组协方差限制意味着这些结果应作为实验分层线索，而不是国家、板块或借款人的 targeting 规则。"},
        {"id": "year_chart_block", "type": "chart", "chartId": "year_chart"},
        {"id": "holdout", "type": "markdown", "sourceId": "holdout", "body": f"## 6. 2025 留出结果划定 no-deployment 边界\n\n叙事模型在 log-hour MAE（{log_mae_narrative:.4f} vs {log_mae_control:.4f}）、Brier（{brier_narrative:.4f} vs {brier_control:.4f}）与 AUC（{auc_narrative:.4f} vs {auc_control:.4f}）上没有超过 controls-only；log-loss 略好。差异未提供 paired uncertainty，因此不声称显著变差。"},
        {"id": "holdout_chart_block", "type": "chart", "chartId": "holdout_chart"},
        {"id": "limitations", "type": "markdown", "body": "## 7. 哪些不确定性会改变结论\n\n缺少 impressions、ranking、clicks、promotion、image quality 与 partner ID；active pool 仍可能内生；recent 主池只是 posting-age proxy；TF–IDF 只测 lexical repetition；raised-only extract 限制外推；country/sector heterogeneity 只覆盖可估计子集；2025 显示 temporal drift。这些限制共同排除 causal 和 deployment 解释。"},
        {"id": "recommendation", "type": "markdown", "body": "## 8. 建议：改变故事周围的市场，再前瞻验证\n\n1. 在 high-current-saturation 状态下随机测试 staggered / diversified exposure。\n2. 单独测试 partner-approved template alternatives。\n3. Primary outcomes 为 time-to-funding 与 72-hour probability；guardrails 包括 total funding、公平性与 borrower workload。\n4. 不使用 borrower ranking、approval 或 penalty。"},
        {"id": "questions", "type": "markdown", "body": "## 9. 下一步问题\n\n加入真实 exposure/ranking logs 后 current association 还剩多少？随机改变 listing mix 能否加快融资且不把注意力从其他弱势 borrower 转移走？在这两个问题被 prospective evidence 回答之前，不应扩大部署。"},
    ]

    artifact = {
        "surface": "report",
        "manifest": {
            "version": 1,
            "surface": "report",
            "title": "当每个故事听起来都一样",
            "description": "Kiva 当前叙事竞争、recent-listing proxy 与 2025 留出验证的技术报告",
            "generatedAt": GENERATED_AT,
            "cards": cards,
            "charts": charts,
            "tables": tables,
            "sources": sources,
            "blocks": blocks,
        },
        "snapshot": {
            "version": 1,
            "generatedAt": GENERATED_AT,
            "status": "ready",
            "datasets": {
                "headline": clean_records(headline),
                "channel_time": clean_records(time_ds),
                "scenario": clean_records(scenario_ds),
                "robustness": clean_records(robust_ds),
                "year_effects": clean_records(year_ds),
                "holdout_delta": clean_records(hold_ds),
                "support": clean_records(support),
            },
        },
        "sources": sources,
        "package_info": {"originUrl": "artifact://kiva-narrative-attention-final"},
    }
    atomic_json(root / "report_artifact.json", artifact)

    print("built REPORT.md, methods, runbook, delivery map, environment lock, and report_artifact.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
