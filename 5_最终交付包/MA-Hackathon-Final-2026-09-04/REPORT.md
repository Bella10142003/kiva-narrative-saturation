# 当每个故事听起来都一样：Kiva 叙事注意力研究最终报告

**团队：5 GUYS · UNSW Marketing Analytics Hackathon 2026 Finalist**  
**最终演示日：2026 年 9 月 4 日（以 UNSW 官方页面为准）**  
**报告状态：完整真实数据分析；未做外部提交；所有结果均为条件相关性。**

## 技术摘要

本研究把“融资慢”拆成两个待检验的注意力通道：**当前竞争**（同一板块此刻在募的贷款又多又像）与**近期列表语言代理**（上架于 35–65 天前的同板块贷款又多又像）。后者没有观测 impressions、page exit 或记忆，因此只能作为 wear-out 假设的 posting-age proxy。主模型使用 1,234,131 笔 2016–2024 训练贷款，2025 年 133,409 笔主样本保持为时间留出集。[来源：`outputs/model_sample_flow.csv`、`outputs/frozen_spec.csv`]

最强结论来自当前环境。在 `log(1 + funding hours)` 模型中，当前 volume 与 focal-to-pool lexical overlap 同时从训练样本 P25 移到 P75，对应 **`1 + funding hours` 条件几何均值增加 124.35%**（95% CI 103.71% 至 147.08%），比值为 **2.24**。这不是算术平均融资时长。独立的 72 小时共同结果显示，完成融资概率下降 **14.68 个百分点**（95% CI -17.69 至 -11.67 个百分点）。[来源：`outputs/scenario_contrasts.csv`]

近期列表代理没有得到同等强度的结果：联合 P25→P75 情景在同一 log-time back-transform 上为 **-1.42%**（95% CI -15.81% 至 15.43%），72 小时概率为 **-0.51 个百分点**（95% CI -3.86 至 2.84）。两个区间均跨零，因此不能把局部 `V×G` interaction 升格为稳健的 average wear-out 结论。[来源：`outputs/scenario_contrasts.csv`]

2025 留出验证进一步收窄了可执行边界：加入叙事特征后，35 天完整随访样本的 log-hour MAE 为 0.9822，controls-only 为 0.9663；72 小时 Brier 为 0.1370 对 0.1357，AUC 为 0.8921 对 0.8986。Log-loss 从 0.4317 小幅改善到 0.4301，但整体不足以支持部署 borrower scoring。[来源：`outputs/holdout_validation.csv`]

**决策建议：不要部署 Narrative Attention Engine 给借款人打分。把当前饱和度用作实验触发条件，优先测试 listing 排期/曝光多样化与 partner-approved 模板替代方案。**

## 研究范围与数据边界

- 官方数据共 1,453,846 条贷款，覆盖 2016-01-01 至 2025-12-31；其中 6 条 `raisedDate < fundraisingDate` 被排除。[来源：`outputs/data_profile_summary.csv`]
- 数据集中每条记录都有 `raisedDate`。因此本提取物不能识别真正的 right censoring，也不支持把结果解释为“所有上架贷款的融资成功概率”；本研究分析的是提取物中已观察到 raisedDate 的贷款。[来源：`outputs/status_raised_crosstab.csv`]
- 主结果使用 `log(1 + funding hours)`；并报告 72 小时快速融资的共同结果。2025 年末随访不足 72 小时的记录不进入 72 小时评估。[来源：`outputs/followup_eligibility.csv`]
- 所有时间统一为 UTC。训练期为 2016–2024；IDF、标准化参数和所有学习步骤只在训练期拟合，然后固定应用于 2025。[来源：`outputs/frozen_spec.csv`]
- `fundsLentInCountry` 等上架后才确定的字段不进入模型；输出不包含姓名、精确地点或完整叙事原文。

## 测量设计：在贷款上架的一刻重建注意力市场

对每笔 focal loan，我们计算同板块的两套环境：

1. **Current channel**：`C = log1p(active same-sector count)`；`H = focal narrative 与 active pool 的平均余弦相似度`（focal-to-pool lexical overlap，不是 pool 内 pairwise homogeneity）；当前饱和度为标准化后的 `C×H`。
2. **Recent-listing proxy**：`V = [35,65)` 天 posting-age 窗口内按 7 天半衰期加权的较早贷款量；`G = 同一加权池的平均相似度`；代理饱和度为标准化后的 `V×G`。主池不要求较早贷款已经结束，也没有 lender exposure 数据；completed-only lag 仅作为灵敏度检验。

主文本字段是经过姓名、地点、金额、日期等 masking 的 `use`；TF–IDF 使用 hashed word unigram/bigram（2^17 features）与只在训练期拟合的 smooth IDF。409 个在至少 659 份训练文档且跨至少 3 个国家出现的逐字 5-gram 被定义为 recurring language；因为数据没有 partner ID，“跨国家”只是来源代理，不能用于归因某一机构。[来源：`audit/stage2_text_manifest.json`、`outputs/boilerplate_like_phrases.csv`]

相似度不是两两暴力枚举，而使用严格恒等式 `mean cosine = focal vector · mean pool vector`。200 笔 focal loans × 3 个池的 600 次验证中，raw 最大绝对误差为 2.909e-14，residual 为 2.509e-14，低于 1e-9 验收线。[来源：`outputs/pool_identity_summary.csv`、`audit/stage3_feature_manifest.json`]

P25/P75 联合情景也通过了局部支持检查：在两个维度均为 ±0.10 IQR 的邻域中，每个 current/recent 端点至少有 4,716 笔真实训练记录。这个检查只说明情景端点并非空洞外推，不建立可交换性或因果识别。[来源：`outputs/joint_support_summary.csv`]

## 发现一：当前市场饱和是强烈但非因果的诊断信号

主 HDFE 模型控制 loan amount、borrower count、repayment term、平台 7 天上架量，并吸收 country、activity、week、gender、repayment interval、posting day/hour fixed effects；标准误按 country 与 week 双向聚类。`C×H` 系数为 0.1017（95% CI 0.0357 至 0.1677，p=0.003308）。[来源：`outputs/rq1_main_table.csv`]

实际解释采用完整联合情景而不是把 interaction coefficient 单独翻译成百分比：当前 volume 与 focal-to-pool lexical overlap 同时从 P25 移到 P75，对应 `1 + funding hours` 条件几何均值 **+124.35%**、72 小时概率 **-14.68pp**。前者不是算术平均融资时长；两者都是观测数据下的 conditional association，不是 Kiva 改版后的 intervention forecast。[来源：`outputs/scenario_contrasts.csv`]

## 发现二：模板语言可能贡献当前信号，但不能做因果分解

原始 masked use 的 `C×H` 为 0.1017（p=0.003308）；移除 recurring language 后为 0.0523（p=0.129）。估计约减半且不再达到常规显著性，但这不等于“模板解释了一半”，因为两套系数的差异没有经过正式的跨模型差异检验。[来源：`outputs/robustness.csv`]

description 灵敏度提供补充证据：masked description 的 `C×H` 为 0.1298（95% CI 0.0875 至 0.1721，p=1.663e-07），而 `V×G` 为 -0.0136（95% CI -0.0441 至 0.0170，p=0.376）。50 笔 focal loans × 2 个池的恒等式检查最大误差 1.721e-15，通过 1e-9 标准。[来源：`outputs/description_robustness.csv`、`audit/description_robustness_manifest.json`]

管理含义不是要求 borrower “讲得更响”，而是测试平台与 Lending Partner 的模板、排期和曝光流程。

## 发现三：局部 recent-listing interaction 不能升级为平均 wear-out

Raw `V×G` 系数为 0.0417（p=0.003658），residual 为 0.0585（p=0.0007078）。但这两个系数检验的是 posting-age proxy 的 conditional interaction；联合 P25→P75 情景同时包含 `V`、`G` 与 `V×G`，其 log-time back-transform 为 -1.42% 且置信区间跨零。[来源：`outputs/robustness.csv`、`outputs/scenario_contrasts.csv`]

同时，14 天与 16 天 posting window 下 current `C×H` 保持正向且显著，而 time-based specification 中 lagged `V×G` 不显著。这说明 current 结果对窗口较稳健，但对文本分解敏感；recent 结果不足以支持优先投入 wear-out editorial intervention。[来源：`outputs/robustness.csv`]

## 时间与板块异质性：存在变化，但不应用于排名

2016–2024 的 year-specific scenario contrasts 显示两条通道显著波动；year、sector 与 country 的全局异质性筛查均提示差异。[来源：`outputs/rq3_year_effects.csv`、`outputs/rq3_global_tests.csv`、`outputs/rq4_sector_global_tests.csv`、`outputs/rq4_country_global_tests.csv`]

这些结果保持探索性：country heterogeneity 只覆盖训练量最高的 15 个国家，sector 模型覆盖 14 个达到估计门槛的板块；许多 subgroup 置信区间较宽，且全局 Q screen 没有估计“共享 week shocks 导致的跨组协方差”。因此报告不从排序中挑选“最佳国家/板块”，更不把异质性用于 borrower targeting。

## 2025 留出验证：解释性信号没有转化为稳定增量预测

在 2025 至少 35 天随访的 123,489 笔贷款上，controls-only 与 controls+narrative 的 log-hour MAE 分别为 0.9663 与 0.9822；hour MAE 为 168.28 与 168.61。[来源：`outputs/holdout_validation.csv`]

在 72 小时评估中，Brier 为 0.1357 对 0.1370，AUC 为 0.8986 对 0.8921；log-loss 为 0.4317 对 0.4301。我们没有为这些 metric differences 计算 paired uncertainty，因此准确表述是“叙事模型没有在主要运营指标上超过 baseline”，而不是“显著变差”。[来源：`outputs/holdout_validation.csv`]

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
- 官方挑战目标、日期与评审标准：[UNSW Marketing Analytics Hackathon Challenge 2026](https://www.unsw.edu.au/business/our-schools/marketing/news-events/student-events/MA-hackathon)。

> 版本说明：本报告根据全量真实输出写成；附件中的 runbook/prompt 仅作为团队早期来源材料，实际执行以保存的代码、审计和冻结规格为准。
