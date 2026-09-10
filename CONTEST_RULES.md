# 竞赛统一标准

本文件是 Codex 起草和 Claude 审批共用的唯一竞赛标准。内容必须来自竞赛官方要求、评分标准、官方模板或经人工确认的信息。不得凭经验补全；缺失、冲突或不明确之处统一标记为【待确认】。

## 1. 官方来源与效力

- 官方竞赛网页：[Marketing Analytics Hackathon Challenge 2026](https://www.unsw.edu.au/business/our-schools/marketing/news-events/student-events/MA-hackathon)
- 主办方：UNSW School of Marketing。
- 本次核验日期：2026-08-15。
- 官网关联的数据字典为 `Kiva Data Dictionary.xlsx`；官网下载文件与用户附件版本的 SHA-256 均为 `c92e762e33288f885404112151dcce618fd2a8c3dd3223fa5bfdab44f4c4cc94`，内容一致。
- 用户附件 PNG 是研究构想，不属于官网规则；只有用户于 2026-08-15 明确采用并收窄的部分可进入研究计划，其余仍是候选方案。
- 官网未明确说明的事项不得根据 UNSW 所在地、往届惯例或常识自行推断。

## 2. 基本信息

| 项目 | 已确认标准 | 官方出处 | 状态 |
| --- | --- | --- | --- |
| 比赛名称 | Marketing Analytics Hackathon Challenge 2026 | 官网标题 | 已确认 |
| 主题 | Winning Hearts Faster: What Drives Lender Decisions in Prosocial Crowdfunding? | 官网页首 | 已确认 |
| 比赛目标 | 识别公益众筹中影响出借人决策的关键因素，以筹资速度为反映；基于严谨的数据分析，为资源受限环境中的借款人和众筹平台形成更有效的策略洞察 | “Goal of the challenge” | 已确认 |
| 分析范围 | 使用 2016–2025 年贷款级数据，研究为何部分贷款比其他贷款更快获得资金，并鼓励考察说服性模式在不同细分群体间及随时间的差异 | “Goal of the challenge” | 已确认 |
| Proposal 评审对象 | 竞赛 judging panel | “Proposal evaluation” | 已确认 |
| 潜在管理受众 | 资源受限环境中的借款人和众筹平台 | “Goal of the challenge” | 已确认 |
| Proposal 正文语言 | English | 用户人工确认（2026-08-15）；官网未限定 | 已确认（人工决策） |
| 参赛资格 | 澳大利亚及国际大学的本科生和硕士生；应对使用分析工具解决现实营销问题感兴趣，并具备所需营销与分析技能。博士生资格【待确认】 | “Who can participate?” | 部分确认 |
| 团队规模 | 2–5 名学生 | “Who can participate?” | 已确认 |

## 3. 数据与研究任务

| 项目 | 已确认标准 | 官方出处 | 状态 |
| --- | --- | --- | --- |
| 数据来源 | Kiva 贷款级数据 | “Data” | 已确认 |
| 完整数据规模 | 1,453,846 笔贷款 | “Data”及官网数据图 | 已确认 |
| 完整数据期间 | 2016-01-01 至 2025-12-31 发放的贷款 | “Data” | 已确认 |
| 市场范围 | PPP GDP per capita 低于 US$4,500 的国家，聚焦 subsistence marketplaces | “Data” | 已确认 |
| 主要决策结果 | `funding speed`，官网数据图明确为 `fundraisingDate` 与 `raisedDate` 之间的天数 | “Data”及官网数据图 | 已确认 |
| 研究问题 | 团队应自行形成研究问题，而非回答预设的单一分析任务 | “Data” | 已确认 |
| Proposal 阶段数据用途 | 注册后提供样本数据，用于理解结构、测试代码/方法并发展研究问题和 proposal | “Data” | 已确认 |
| 完整分析要求 | Proposal 阶段不要求完成完整分析；晋级团队获得完整数据并有一周完成项目和最终展示 | “Submit your proposal” | 已确认 |
| 样本抽样方法与代表性 | 【待确认】 | 官网未说明 | 待确认 |
| 数据许可、隐私和可引用范围 | 【待确认】 | 官网未说明 | 待确认 |

### 3.1 团队人工确认的研究范围（非官网要求）

> **2026-09-01 基准更正**：以下范围按**实际提交的提案 PDF**《WHEN EVERY STORY SOUNDS THE SAME》重写。
> 此前本节记录的是 H1–H4，来自未提交的草稿 [`2_提案/_未提交草稿/提案正文_BeyondCrowding_未提交.md`](2_提案/_未提交草稿/提案正文_BeyondCrowding_未提交.md)，已作废。

- 核心问题：更慢的筹款是与**当前相似列表**相关、与**这些列表离开后的近期重复**相关，还是两者皆有。
- **RQ1（Active narrative saturation）**：当前同行业选择集既拥挤又叙事同质时筹款是否更慢。饱和是数量与同质度的**交互**，两者单独都不充分。指定检验：`C×H`。
- **RQ2（Competition versus wear-out）**：已离开页面的完成贷款之间的饱和是否仍与更慢筹款相关（market-level wear-out），并检验其在剥离机构模板后是否存活。指定检验：**V、G、V×G 的联合检验**。
- **RQ3（Evolution of the two channels）**：两条通道 2016–2025 的演化，报年度边际效应，不假定单一线性趋势，不归因于单一事件。
- **RQ4（Segment boundaries）**：①行业与国家上何处最强；②注意力市场主要运行在**行业内**还是**全平台**。
- 结果一律解释为 conditional association，不作因果。
- 当前 100 条样本仅用于验证结构和方法，不产生总体或因果结论。

## 4. Proposal 内容、篇幅与格式

| 项目 | 已确认标准 | 官方出处 | 状态 |
| --- | --- | --- | --- |
| 必答内容 | 项目目标、研究方法、计划使用的数据项、预期分析结果、预期管理启示 | “Submit your proposal – Requirements” | 已确认 |
| 推荐结构 | Title, names, and affiliations；Project aim and research questions；Proposed analytical approaches；Data items to be used；Expected outcomes and managerial relevance | “Recommended Proposal Structure” | 已确认 |
| 完整分析 | Proposal 阶段不要求完成 | “Requirements” | 已确认 |
| 最大字数 | 1,500 words，参考文献不计入 | “Requirements” | 已确认 |
| 本轮内部字数目标 | 1,400–1,450 words，以保留安全余量 | 用户人工确认（2026-08-15）；非官网分项要求 | 已确认 |
| 文件格式与命名 | 【待确认】 | 官网未说明 | 待确认 |
| 排版要求 | 【待确认】 | 官网未说明 | 待确认 |
| 引用与参考文献格式 | 【待确认】 | 官网未说明 | 待确认 |
| 附件、图表或补充材料规则 | 【待确认】 | 官网未说明 | 待确认 |
| 官方 proposal 模板 | 【待确认】 | 官网未提供模板 | 待确认 |

## 5. 关键日期与提交要求

| 项目 | 已确认标准 | 官方出处 | 状态 |
| --- | --- | --- | --- |
| 团队注册截止 | 2026-08-16；准确时间【待确认】 | “Key dates” | 部分确认 |
| 团队注册方式 | 官网指向 [Qualtrics 表单](https://unsw.au1.qualtrics.com/jfe/form/SV_e3d2YliOQYHsO2i)，但可读取页面标题为 “MA Hackathon 2025 Registration”；该链接是否适用于 2026【待确认】 | “Register your team”链接及表单页 | 存在冲突，待确认 |
| Proposal 提交窗口 | 2026-08-17 09:00 至 2026-08-24 17:00 | “Submission” | 已确认 |
| Proposal 截止 | 2026-08-24 17:00 | “Key dates”及“Submission” | 已确认 |
| 时间所用时区 | 【待确认】 | 官网未说明；不得自行假设为 Sydney time | 待确认 |
| 提交渠道 | 发送邮件至 `MA.Hackathon@unsw.edu.au` | “Submission” | 已确认 |
| 入围团队公布 | 2026-08-27 09:00 | “Key dates” | 已确认；时区待确认 |
| 最终展示及颁奖 | 2026-09-04 | “Key dates” | 已确认 |
| 入围数量 | 最多 8 支团队 | “What is the prize?”及“Proposal evaluation” | 已确认 |

## 6. Proposal 评分标准

| 评分项 | 权重 | 具体判定标准 | 官方出处 | 状态 |
| --- | --- | --- | --- | --- |
| Insightfulness and originality | 30% | 是否以深思熟虑且有创意的方式识别出借人决策关键驱动因素；是否超越表层分析并发现有意义的模式 | “Proposal judging criteria” | 已确认 |
| Analytical rigor and relevance | 30% | 分析能否形成稳健、数据驱动的筹资决策洞察；方法是否恰当、有充分理由且与研究目标一致 | “Proposal judging criteria” | 已确认 |
| Strategic depth and evolutionary perspective | 20% | 是否考虑说服性驱动因素在不同细分群体间的差异及其随时间的演化；是否理解出借人行为的动态性 | “Proposal judging criteria” | 已确认 |
| Project feasibility within one week | 10% | 项目能否在一周内使用所提供数据现实完成 | “Proposal judging criteria” | 已确认 |
| Clarity, structure, and communication quality | 10% | Proposal 是否清楚、逻辑有序，并能有效呈现目标、方法和预期结果 | “Proposal judging criteria” | 已确认 |
| 合计 | 100% | — | 官网 | 已确认 |

## 7. 强制规则

1. 禁止虚构信息，包括但不限于数据、引用、政策、用户反馈、访谈、合作关系、案例和实验结果。
2. 所有事实性主张必须有可追溯来源；无法确认的内容必须标记为【待确认】。
3. 竞赛原始材料默认只读；未经明确要求，不得修改、移动、重命名或删除。
4. Proposal 正文使用 English；这是用户人工决策，不得误写为官网语言要求。
5. Proposal 必须明确项目目标、研究问题、分析方法、数据项、预期结果及管理相关性，但不得把预期结果写成已完成分析的发现。
6. 除参考文献外，Proposal 内容合计不得超过 1,500 words。官网只明确排除参考文献；在主办方另行说明前，标题、姓名、单位等其他内容一并计入保守预算。
7. 研究设计必须能够在入围后的一周内以提供的数据现实完成。
8. Codex 不得自行宣布 proposal 获批；Claude 的审批也不替代人工责任。内容、合规性、提交版本和实际提交操作最终均由人工确认。
9. 市场拥挤与叙事饱和必须使用同一参照贷款池；叙事饱和必须按该池规模标准化。主文本表示、相似度、时间窗口和模型只保留一个有理由的主规格，其他方法只作稳健性检查。
10. 本项目为观察性研究，Proposal 必须明确只能检验 association，不得将关联声称为 causation、causal effect 或已证实的政策影响。
11. 当前 100 条样本不得用于报告总体效应、显著性、因果结论或抽样代表性；只可验证字段和方法流程。
12. 不得把“不显著”直接解释为无关联。只有置信区间上界低于事先人工确定的最小具有管理意义的正关联时，才可支持降低相关干预的优先级；未确定该阈值或未达到这一条件时，结论须保持为 inconclusive 或建议进一步检验。

## 8. 仍待人工确认

- 官网时间的时区，以及团队注册截止的准确时间。
- 团队是否已经完成注册，以及官网 Qualtrics 链接是否适用于 2026（其页面标题仍显示 2025）。
- 文件格式、文件名、排版、引用格式、附件和模板规则。
- AI 工具、外部数据、代码/模型、原创性、保密、数据隐私及伦理规则。
- 在查看完整数据结果前，人工确定“最小具有管理意义的正关联”阈值；该项不阻塞当前 Proposal 初稿，但会阻塞对空结果或不显著结果的管理解释。
- 姓名与 affiliations 的准确写法。**（PDF 已列出 5 名成员及学号；`2_提案/假设清单.md` ASM-012 可据此关闭）**
- 博士生是否符合参赛资格（若团队涉及）。
- ~~提案 PDF 未归档进本项目~~ **已解决（2026-09-01）**：原件在 [`2_提案/5 GUYS 提案.pdf`](2_提案/5%20GUYS%20提案.pdf)，SHA-256 `682480268af5db3de10a5dd661ea743e569b1d4b9a3c674c9241b478a6afcce4`。
- **`2_提案/合规对照矩阵.md`（31 处）与 `竞赛要求清单.md`（14 处）仍以 H1–H4 草稿为基准**，需按 PDF 的 RQ1–RQ4 重建；重建前不得据其审批。两份文件的其余内容（官网要求映射、评分权重、关键日期、提交渠道）与 H1–H4 无关，**仍然有效**，因此是局部改写而非推倒重来。
- ~~提案大纲需重建~~ **已解决（2026-09-01）**：核验确认 `提案大纲.md` 是 Beyond Crowding 的配套大纲（SEC-06「Primary models for **H1 and H2**」、SEC-07「Secondary analysis for **H3**」，且 wear-out／V×G 零命中），**不是提交版的大纲，无需按 RQ 重建**，已整体归档至 `2_提案/_未提交草稿/`。
- ~~`提案定稿.docx` 命名误导~~ **已解决（2026-09-01）**：已连同其余两份草稿归档并重命名为 `2_提案/_未提交草稿/提案定稿_BeyondCrowding_未提交.docx`。

## 9. 标准变更记录

| 日期 | 变更内容 | 依据 | 人工确认状态 |
| --- | --- | --- | --- |
| 2026-08-15 | 初始化规则模板 | 用户要求 | 已记录 |
| 2026-08-15 | 补入比赛官网，确认比赛目标、数据范围、proposal 结构、1,500 词限制、关键日期、提交邮箱及评分权重 | 用户提供的 UNSW 官方网页；官网数据图；官网 Dropbox 数据字典 | 待最终人工复核 |
| 2026-08-15 | 人工确认英文正文、叙事饱和核心问题、H1–H4 优先级/范围、可选扩展及 100 条样本使用边界，并授权起草 | 用户当前指令 | **已作废**（见 2026-09-01 条） |
| 2026-09-01 | **基准更正**：§3.1 由 H1–H4 改写为 RQ1–RQ4。此前记录的 H1–H4 来自未提交草稿 `2_提案/_未提交草稿/提案正文_BeyondCrowding_未提交.md`；实际提交的提案是 PDF《WHEN EVERY STORY SOUNDS THE SAME》，两者的研究问题、核心估计量、次级问题和主文本字段均不同 | 用户于 2026-09-01 提供提案 PDF 并确认其为最终提交版本 | 已确认（用户） |
| 2026-09-01 | §8 增列：提案 PDF 未归档进本项目；`2_提案/` 与 `7_审查记录/` 前三轮均以草稿为基准，需按 PDF 重建 | 同上 | 已记录，待人工处理 |
