# Research Proposal 收敛大纲（已获用户确认）

> ## ⛔ 2026-09-01 基准更正：本文件不可用于审批
>
> 本文件以未提交的草稿 [`提案正文_BeyondCrowding_未提交.md`](提案正文_BeyondCrowding_未提交.md)（H1–H4）为基准建立。
> **实际提交的提案是 PDF《WHEN EVERY STORY SOUNDS THE SAME》，结构为 RQ1–RQ4**，
> 其研究问题、核心估计量、次级问题与主文本字段均与草稿不同（对照表见 `提案正文_BeyondCrowding_未提交.md` 顶部）。
>
> 本文件中共 60 处 `H1`–`H4` 引用需按 PDF 的 RQ1–RQ4 重建。重建涉及团队自身的合规论证，
> 不由 Claude 代写；**在重建完成前，本文件不得作为审批或合规核查的依据**。
>
> 详见 [7_审查记录/Claude审查记录_提案基准更正_2026-09-01.md](../../7_审查记录/Claude审查记录_提案基准更正_2026-09-01.md) 的 B-01。


## SEC-00 阶段状态、边界与官网结构

- 用户于 2026-08-15 确认正式采用“叙事饱和是否在市场拥挤之外与更长筹资时长相关”为研究问题，并授权 Codex 使用英文起草 Proposal。
- 用户确认 H1、H2 为核心；H3 为次级，仅保留“具体用途”和“数字细节”；H4 为探索性，仅保留 sector 和年度趋势。
- 地理、月份和 COVID 分析仅为时间允许时的可选扩展，不纳入核心交付承诺。
- 当前 100 条样本仅用于验证字段、清洗、指标和代码流程，不用于总体、效果量或因果结论。
- Proposal 只提出尚待完整数据实施的观察性分析；使用 association、relationship 和 prediction，不使用因果化表述。
- 官网未说明的时区、文件格式/命名、排版、引用、附件、AI 和隐私规则仍为【待确认】；团队姓名和 affiliations 写 [TO CONFIRM]。
- 目标计数为 1,400–1,450 words，低于官网 1,500 words（参考文献除外）上限。

### 官网推荐五部分映射

| 官网推荐部分 | 大纲位置 | 英文初稿目标字数 |
| --- | --- | ---: |
| Title, names, and affiliations | SEC-01 | 25 |
| Project aim and research questions | SEC-02～SEC-03 | 225 |
| Proposed analytical approaches | SEC-05～SEC-10 | 690 |
| Data items to be used | SEC-04 | 190 |
| Expected outcomes and managerial relevance | SEC-11～SEC-13 | 245 |
| Feasibility / limitations（嵌入上述五部分） | SEC-12～SEC-14 | 50 |
| **目标合计** | — | **1,425** |

## SEC-01 Title, names, and affiliations

- 暂定英文标题：**Beyond Crowding: Is Narrative Saturation Associated with Slower Funding in Prosocial Crowdfunding?**
- Team members: [TO CONFIRM]
- Affiliations: [TO CONFIRM]

## SEC-02 Project aim and decision relevance

- 目标：检验贷款上线时的叙事饱和是否与更长筹资时长相关，以及这一关联在控制同一参照贷款池的规模后是否仍然存在。
- 原创性：将“可选贷款多”与“可选贷款故事相似”分解；两项指标使用完全相同的上线时活跃贷款池，避免由不同参照集合造成不可比性。
- 管理受众：资源受限环境中的借款人与众筹平台。任何内容支持、排序或呈现建议都以完整数据的关联证据为条件；不承诺政策实施会加快筹资。

## SEC-03 Research questions and hypotheses

### 核心分析（最高优先级）

- **H1:** Higher narrative saturation at a loan’s posting time is associated with longer funding duration.
- **H2:** The positive association in H1 remains after accounting for market crowding measured from the same reference pool and pre-specified loan characteristics.

### 次级分析

- **H3:** The association between narrative saturation and funding duration is weaker when a narrative contains (a) a concrete use of funds or (b) numerical detail. 两个调节项分开估计；方向性表述是待检验假设，不是结果。

### 探索性分析

- **H4:** The H2 association may vary across sector and across fundraising years. 不预设具体 sector 或年份的方向。

### 可选扩展

- 只有在 H1/H2 已复现、H3 验证决策已完成、H4 sector/年度分析已完成、核心 QA 已通过且仍有时间时，才考虑地理、月份和 COVID 时段；不将其写成承诺交付物，也不得以可选扩展替代被降级的较高优先级分析。

## SEC-04 Data items, analysis unit, and sample boundary

- 分析单位为单笔贷款。官网说明完整数据包含 1,453,846 笔 Kiva 贷款，发放日期为 2016-01-01 至 2025-12-31，并聚焦 PPP GDP per capita 低于 US$4,500 的国家。
- 当前 pickle 包含 100 条、27 个字段和 100 个唯一 id；全部为 funded。它只用于检查数据类型、时间逻辑、文本清洗和代码可行性，不用于总体关联估计、显著性检验、总体外推或因果结论。
- 结果字段：fundraisingDate、raisedDate；核心叙事字段：description；H3 字段：use；结构化字段：loanAmount、borrowerCount、lenderRepaymentTerm、repaymentInterval、sector、country_name 及上线年份。
- 主分析只纳入具有可解析上线时间及可用 description 的记录，并报告每一步排除数量。
- 如完整数据仅含已筹满且有效 raisedDate 的贷款，估计对象限于“已筹满贷款的筹资时长”，不解释筹满成功或选择过程。
- 如完整数据含未筹满/仍活跃贷款，Day 1 须先根据 status 与可用终止字段区分：只有确认在官方 observation end 仍活跃的贷款才在该日右删失；提前退出/过期/撤回用经验证的更早终止日；风险区间终点无法确定时触发 14 日队列备选或停止该分支。删失主模型为对 1 + duration_days（删失时间同样 +1）的 log-normal AFT，以处理右删失并保留时长解释；不确定性使用预指定 country/week 双向块 bootstrap。

## SEC-05 Primary measurement specification

### 5.1 Funding duration

- duration_i = raisedDate_i − fundraisingDate_i，单位为天；数值越大表示筹满越慢。
- 主模型使用 log(1 + duration_i)，以允许零天记录并降低对极长持续时间的敏感性；原始天数只作稳健性规格。

### 5.2 两项核心指标的共同参照池

对在时间 t_i = fundraisingDate_i 上线的目标贷款 i，主参照池定义为：

A_i = {j ≠ i : fundraisingDate_j ≤ t_i < end_j，且 j 有有效日期与可用 description}。已筹满贷款的 end_j = raisedDate_j；确认在截止日仍活跃的贷款 end_j = observation end；其他终止状态仅使用经验证的终止日。

- A_i 是数据可重建的“上线时尚未筹满且文本可测量贷款池”代理，不声称等同于个人实际看到的页面、排序或曝光。
- 市场拥挤和叙事饱和始终使用同一 A_i；不允许为两项指标分别挑选时间窗口。
- 同一时间戳上线的贷款按批次处理，互相纳入但排除自身，避免任意排序。
- 主分析对 |A_i| > 0 的贷款定义饱和度；空池记录的数量单独报告，不把缺失相似度解释成“零相似”。

### 5.3 Market crowding

- 贷款池规模 N_i = |A_i|。
- 主回归使用 C_i = log(1 + N_i)，不强迫原始计数与结果呈线性关系；原始 N_i 仅作稳健性检查。

### 5.4 Text representation and narrative saturation

- 为避免核心饱和指标与 H3 的 use 特征机械重叠，也避免样本中重复 whySpecial 主导测量，主文本只使用 description；description + use 及加入 whySpecial 仅作稳健性检查。
- 主清洗：独立移除 description 的 HTML，统一 Unicode、大小写与空白，并将其数字序列统一为占位符；H3 数字指示变量另行从未修改的 use 提取。
- 主文本表示：结果无关的 word unigram/bigram TF–IDF；min_df = 5、max_df = 0.95、最多 100,000 个按语料频率选择的特征，L2 归一化。理由是透明、可审计、可本地扩展，且无需在 AI 规则未确认时依赖外部模型。
- 主相似度：归一化向量的 cosine similarity，sim(i,j) = v_i′v_j。
- 主叙事饱和指标：S_i = (1/N_i) × Σ[j∈A_i] sim(i,j)。除以 N_i 后，S_i 是按贷款池规模标准化的池内平均词汇相似度，而不是相似贷款的未标准化总量。进入回归前再对 S_i 做 z-score。
- 计算方案：按时间排序维护活跃池的稀疏向量和，在 end_j 移除贷款。因向量已归一化，S_i 可由 v_i 与活跃池质心的点积精确得到，无需存储全量成对相似度。

## SEC-06 Primary models for H1 and H2

- **H1 model:** 对 log(1 + duration_i) 使用 ordinary least squares（OLS）：log(1 + duration_i) = α + β₁S_i + controls + fixed effects + ε_i。OLS 透明且可扩展；log1p 允许零天记录并降低对极长时长的敏感性。
- **H2 model（主模型）:** 在 H1 模型中加入 C_i；关注控制同池市场拥挤后 S_i 的条件关联，不称“独立效应”。
- 预指定 controls：单位统一且为正后使用 log1p(loanAmount)，log1p(borrowerCount)、线性 lenderRepaymentTerm 和分类 repaymentInterval；加入 country、sector 和每个独立 year-month（如 2016-01）的 fixed effects。Year-month FE 仅用于基线时间调整，不报告月份特定推断；可选“月份分析”专指饱和斜率的月度异质性。单位无法确认的变量不进入主模型。
- 标准误主规格按 country 和 fundraising calendar week 双向聚类。如任一维少于 30 个聚类，则主报告 week-clustered 标准误，并用 country wild-cluster bootstrap 作敏感性检查；该决策在查看系数前固定。
- 报告系数、置信区间、实际量级和模型诊断，不只报告显著性。平台排序、曝光、流量、合作伙伴、翻译和其他未观测因素可能同时关联文本与筹资时长，因此 H1/H2 只能支持 association。

## SEC-07 Secondary analysis for H3

- 只保留两个预指定内容特征：
  1. **Concrete use:** use 文本是否命名特定可购买的投入、产品、服务或行动，而非只给出泛化目的。
  2. **Numerical detail:** 原始 use 文本是否含至少一个可识别的数字、数量或金额表达；每百词表达数仅作稳健性检查。
- Day 1–2 在查看筹资结果前固定编码手册/规则，并从完整数据抽取 200 条分层记录；Day 4 由两名团队成员在不知筹资结果时完成双编码验证。自动规则 F1 低于 0.80，或正/负任一类别流行率低于 1% 时，对应交互不作推断性报告。空白或过短 use 记为 H3 不可测并报告排除数，不影响 H1/H2 样本。
- 在 H2 模型中分别加入 S_i × concrete_use_i 和 S_i × numerical_detail_i 及各自主效应。不得把交互关联写成特征“抵消”或“导致”更快筹资。

## SEC-08 Exploratory analysis for H4

- **Sector:** 在 H2 模型中加入 S_i × sector，先做联合检验；只对至少 500 条贷款的 sector 报告分组估计，稀疏组在查看结果前并为 Other，并对 sector-specific 比较使用 Benjamini–Hochberg 5% false-discovery-rate 校正。
- **Annual trend:** 在 year-month fixed effects 下加入 S_i × centered fundraising year，检验超出共同时间变化的线性年度斜率变化；年份特定斜率仅作稳健性或描述性可视化。
- H4 不作方向性承诺，并在报告中与 H1/H2 的核心推断分开。

## SEC-09 Robustness checks only

以下规格只用于报告敏感性，不用于挑选最支持假设的结果：

- 用上线前 7、14 或 30 天的贷款代替活跃池；每个规格的拥挤与饱和仍必须使用同一参照池。
- 使用 character n-gram TF–IDF、更换文本字段组合，或使用“超过预定阈值的贷款数 / N_i”代替全池平均。阈值固定为使用已记录随机种子从有效活跃池均匀抽取 100,000 个配对所得 cosine 分布的第 95 百分位，在查看时长模型前计算。所有饱和规格均按对应池规模标准化。
- 使用原始池规模、原始筹资天数或经诊断支持的持续时间模型复核方向与不确定性。
- 检查拥挤和饱和的相关性/共线性，并对重复文本、语言、缺失和极端持续时间做敏感性说明。
- 只有在官方 AI/外部模型规则允许时，才可用预先固定的多语句子表示作额外稳健性检查；不是必做步骤。

## SEC-10 Reproducibility and pre-outcome controls

- 在查看主模型结果前冻结：分析样本、时间规则、共同参照池、文本清洗、主表示、相似度、两项指标、H1/H2 模型与 controls。
- 保留数据版本、字段字典、清洗日志、代码、环境和随机种子；用可人工核对的小子集验证活跃池计数和平均 cosine 的精确实现。
- 分开核心、次级、探索性和可选分析；不选择性只报告支持假设的结果。

## SEC-11 Privacy, ethics, and fairness

- 默认不展示姓名、精确坐标、图片 URL 或可识别的完整故事；Proposal 只列字段和聚合方法。
- 最终分析前确认数据许可、隐私及 AI/外部模型规则。不把筹资速度差异归因于借款人的个人品质，并检查文本测量是否在语言或 sector 之间有系统差异。

## SEC-12 Limitations and interpretation boundary

- 当前 100 条样本的抽样与代表性不明，且全部已筹满；它不能支持总体关联、“是否筹满”比较或右删失方案。
- 参照池只是数据可观察的平台贷款集合代理，不是个人曝光；TF–IDF 平均 cosine 测量词汇相似性，不等同于心理上的说服或疲劳。
- 平台排序、流量、翻译、合作伙伴和未观测需求均可能构成混杂。因此任何估计只支持 association，不支持 causation 或对政策效果的保证。

## SEC-13 Expected outcomes and managerial relevance

### 预期交付物（不预设实证方向）

- 一套使用同一参照贷款池、分别测量市场拥挤与池规模标准化叙事饱和的可审计框架。
- H1/H2 核心关联估计；只有通过预设验证/可行性门槛时，才交付 H3 次级交互估计和 H4 sector/年度探索性结果。所有保留结果配置不确定性与稳健性说明。
- 如果饱和在控制拥挤后仍与更长时长相关，平台可进一步试验相似度监测、多样化展示或写作支持。只有当置信区间上界低于事前定义的最小 managerially meaningful 正关联时，才可支持降低基于重复度的干预优先级；否则结论是 inconclusive 或支持进一步测试，不能简化为“无关联”。
- 如果经验证的具体用途/数字细节与较弱饱和关联同时出现，可将其作为后续随机或准实验测试的候选写作支持，而不宣称已证明能加快筹资。
- sector/年度差异只用于识别值得进一步验证的情境，不将探索性切片写成普遍规律。

## SEC-14 One-week execution plan and explicit downgrade rules

| Day | 核心交付 | 当日降级条件 |
| --- | --- | --- |
| 1 | 核验完整数据、字段单位、日期/删失与语言；冻结样本、H1/H2 主规格和 H3 编码手册/规则 | 若关键时间戳不足以可靠重建活跃池，将前 14 天上线队列同时作为两项指标的代理池，并改称 recent-listing density/similarity |
| 2 | 文本清洗与 TF–IDF；构建同池 C_i/S_i；小子集精确核对；盲于结果抽取 H3 样本 | 若增量质心算法未通过手工成对复核，停止回归并先修正指标，不使用未验证近似值 |
| 3 | 运行 H1/H2，完成诊断、效应量/区间和复现脚本 | 若核心管线仍不可复现，先删除 H4，再删除 H3；只交付经验证的描述/核心分析 |
| 4 | 在不知结果时完成 H3 双编码验证，按预设门槛保留/降级并运行次级模型 | 未达 F1 0.80 或正/负任一类流行率 1% 的特征降为描述性或删除，不继续调参追求假设支持 |
| 5 | 运行 H4 sector/年度探索；完成预指定稳健性检查 | 样本不足、估计不稳定或核心 QA 未完成时，不报告单项异质性并禁止启动可选扩展 |
| 6 | 形成条件性管理解读、核心图表和隐私/公平检查 | 不由估计支持或暗示因果的建议一律删除 |
| 7 | 从原始输入重跑；完成事实、方法、字数、隐私和格式 QA | 未通过复现、证据、隐私或格式检查的内容不进入最终展示 |

可选扩展启动门槛：只有 H1/H2 已复现、H3 验证决策已按预设门槛完成、H4 sector/年度分析已完成，且 Day 5 结束时核心 QA/图表/解读已成型，才允许分析地理、月份或 COVID。如 H3/H4 因时间、管线或样本不足而未完成，不得用可选扩展替代。

## 大纲内部一致性结论

| 检查项 | 对应位置 | 结论 |
| --- | --- | --- |
| H1/H2 核心、H3 次级、H4 探索 | SEC-03、SEC-06～SEC-08 | 已固定优先级 |
| 市场拥挤与叙事饱和使用同池 | SEC-05 | 主规格已固定 |
| 饱和按贷款池规模标准化 | SEC-05 | 已定义为池内平均 cosine |
| 文本、相似度、窗口和主模型 | SEC-05～SEC-06 | 主规格与理由已固定 |
| 其他方法 | SEC-09 | 仅稳健性检查 |
| 100 条样本边界 | SEC-04、SEC-12 | 仅结构/方法验证，无总体或因果结论 |
| 观察性 association 边界 | SEC-00、SEC-06、SEC-12～SEC-13 | 已明确 |
| 一周可行性与降级条件 | SEC-14 | 已收紧 |
| 官网推荐五部分 | SEC-01～SEC-14 | 全部覆盖 |
| 五项评分 | 原创性 SEC-02～03；严谨性 SEC-04～10；战略深度 SEC-07～08、13；可行性 SEC-14；清晰度全篇 | 全部覆盖 |
| 1,500-word 上限 | SEC-00 | 初稿目标 1,400–1,450 words |
| 姓名/单位、时区、格式、AI 等未知项 | SEC-00、SEC-11、SEC-14 | 保留 [TO CONFIRM]/【待确认】，不自行补全 |
