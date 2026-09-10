# Claude 独立审批记录

## 审查信息

| 项目 | 内容 |
| --- | --- |
| 首轮审查日期 | 2026-08-15。审查对象为 `proposal.md`（SHA-256 `e94b34d5…`）与 `UNSW_MA_Hackathon_Proposal_Draft.docx`（SHA-256 `ea55bc40…`，1,440 词，4 页） |
| 本轮修改日期 | 2026-08-15。用户明确批准 8 项 Major 并要求 Claude 直接修改（CLAUDE.md「除非用户明确要求直接修改」条款） |
| 当前版本 | `proposal.md` SHA-256 `ebc4e5a2…`；`UNSW_MA_Hackathon_Proposal_Draft.docx` SHA-256 `e175e819…`（43,970 bytes，1,442 词，4 页） |
| 审查范围 | CLAUDE.md、AGENTS.md、CONTEST_RULES.md、proposal/requirements.md、evidence.md、assumptions.md、outline.md、proposal.md、compliance-matrix.md、DOCX；并独立复核官方数据字典 `HKS/Kiva Data Dictionary.xlsx` 与样本 `HKS/Kiva_Loans_Sample.pkl`（只读、受限反序列化） |
| 使用的 `CONTEST_RULES.md` 版本 | §9 变更记录截至 2026-08-15 第三条 |
| 是否逐项核查要求与评分标准 | 是。REQ-CON-001～010、REQ-DATA-001～002、SCORE-001～005 逐项核查；DOCX 逐段文本比对、保守字数重算、4 页逐页渲染 |
| 执行方式 | 前台单智能体；未启动 Workflow、subagent、多智能体或后台任务 |
| 原件备份 | 修改前版本已备份至会话 scratchpad：`backup/proposal.ORIGINAL.md`、`backup/UNSW_MA_Hackathon_Proposal_Draft.ORIGINAL.docx` |

## Blocker

以下三项按用户要求单列为 **submission blockers**，均须由人工解决，Claude 不自行补全。本轮修改未触及、也无法解决这三项。

| 编号 | 位置 | 对应标准 | 原因与影响 | 修改建议 | 状态 |
| --- | --- | --- | --- | --- | --- |
| SB-01 | `proposal.md:3-4`；DOCX 第 2–3 段（第 1 页）："Team members: [TO CONFIRM]"、"Affiliations: [TO CONFIRM]" | REQ-CON-004（官网推荐结构第一项）；REQ-CON-009（2–5 名合资格学生）；ASM-012；GAP-012 | 官网推荐结构的首个组件仍为占位符。评委无法核验团队规模与资格；以占位符提交等于交付不完整文件 | 由人工提供准确姓名与 affiliations 后填入，并重算字数（当前余量 58 词）；若团队含博士生，先确认资格。Claude 不代拟、不推断 | 未解决 |
| SB-02 | CONTEST_RULES.md §5、§8；ASM-013；GAP-013；REQ-CON-010 | REQ-CON-010（2026-08-16 前完成注册） | 注册截止为 2026-08-16，今日为 2026-08-15；官网所指 Qualtrics 表单标题仍为 2025；团队注册是否生效未确认。未有效注册将直接丧失资格 | 今日内经官网渠道或 `MA.Hackathon@unsw.edu.au` 书面确认表单 2026 适用性、注册回执与截止准确时间/时区，结果写入 CONTEST_RULES.md | 未解决（紧急） |
| SB-03 | CONTEST_RULES.md §4、§5、§8；GAP-003/004/005/011；ASM-009/010/011 | REQ-CON-005、REQ-CON-008；CONTEST_RULES §7 规则 2 | 提交窗口时区、文件格式与命名、排版、引用、附件、AI 工具/外部数据、数据许可与隐私规则均未确认。任一项不符都可能导致提交无效或违规；正文仍有一处以 "AI rules remain unconfirmed" 为条件的表述 | 定稿前书面确认，答复写入 CONTEST_RULES.md 与 assumptions.md，并据此定文件名与排版，再由人工提交 | 未解决 |

## Major

8 项均已按用户批准修改并复核。原始表述见 scratchpad 备份。

| 编号 | 位置（修改后） | 对应标准 | 原问题 | 已执行的修改 | 状态 |
| --- | --- | --- | --- | --- | --- |
| M-01 | `proposal.md:20`（DOCX 第 1 页） | SCORE-002；规则 10 | A_i 由他人结果（end_j）定义，风险集系统性过度代表慢贷款；原文"This snapshot precedes the outcome"过度断言 | 删除该断言；改写为"Membership ends at end_j, however, so any risk set over-represents slow loans and partly reflects other loans' outcomes."，并把前 14 天发布队列由稳健性提升为并列对照："Every headline model is therefore repeated on an outcome-independent pool of loans posted in the prior 14 days, and we interpret only associations that agree across both." | 已修改 |
| M-02 | `proposal.md:34`、`:40` | SCORE-002 | year-month 固定效应粒度与秒级时间戳结果不匹配，无法吸收日内至日级需求冲击 | 主规格改为"one indicator per fundraising week … at the timescale on which pool composition and lender demand actually move"，year-month 降为稳健性；H4 年度交互同步改为"while retaining week fixed effects" | 已修改 |
| M-03 | `proposal.md:10`、`:34` | SCORE-002；REQ-DATA-002 | 结果变量时间粒度未定义；"admits zero days"暗示日历日截断 | §1 改为"the elapsed time between the *fundraisingDate* and *raisedDate* timestamps, in fractional days"；模型段改为"Duration keeps its sub-day resolution … handles right skew and near-zero values; calendar-day rounding is a robustness check" | 已修改 |
| M-04 | `proposal.md:28`、`:70` | SCORE-002；SCORE-001 | 合作机构模板文本这一替代解释未处理，且 27 字段无 partner 标识 | 方法段新增预先冻结的缓解规则："Descriptions are partner-written and reuse template phrasing, so before outcomes are viewed we strip sequences recurring verbatim across a pre-set share of loans and keep each loan's boilerplate share as a control."；限制段新增"Descriptions are partner-written and no partner identifier is released, so saturation partly reflects template prevalence that country and sector adjustment cannot absorb." | 已修改 |
| M-05 | 全篇 | SCORE-001；SCORE-003；SCORE-005 | 承载 50% 权重的两节仅占 27% 篇幅，方法细节挤占 | §2 由 882 词压至 788 词（−94）：删除 min_df/max_df/100,000 特征等具体参数、100,000 抽样对阈值细节、AFT 位移说明与重复的删失句。§1 增至 216 词（+18，新增注意力机制陈述），§4 增至 248 词（+63，新增双受众管理含义）。总计 1,442 词 | 已修改 |
| M-06 | `proposal.md:12`、`:40`、`:48`、`:64` | SCORE-003（20%） | 20% 权重仅由"最先删除"的探索性 H4 承担 | §1 改为"that variation is a committed descriptive deliverable, and only its inferential reading is exploratory"；H4 段新增"Sector and year profiles are reported descriptively whatever the joint tests show"；降级顺序改为"we drop robustness variants first, then H4's inferential tests while keeping its descriptive profiles, then H3"；§4 交付物新增"a descriptive profile of sector and year variation" | 已修改 |
| M-07 | `proposal.md:52`、`:68` | REQ-CON-001；SCORE-003；SCORE-001 | 未使用/未讨论 disbursalDate 与先放款后回填结构；管理含义仅面向平台，未接入 subsistence marketplaces | 数据项加入 *disbursalDate*，并新增"Where *disbursalDate* precedes posting, faster funding refreshes partner capital rather than bringing the borrower's cash forward; we will audit how often this holds and control for the gap."；§4 新增借款人/合作机构一侧的含义并点名 subsistence marketplaces | 已修改 |
| M-08 | 全篇字段名；`proposal.md:52` | SCORE-005；REQ-CON-003 | 字段名与普通英文词无排版区分；数据项首句歧义 | DOCX 中全部字段名统一改为斜体（*description*、*use*、*fundraisingDate*、*raisedDate*、*loanAmount*、*borrowerCount*、*lenderRepaymentTerm*、*repaymentInterval*、*sector*、*country_name*、*disbursalDate*、*whySpecial*），与已有的数学变量斜体约定一致；首句改为"…define timing; *description* supplies the primary text, and *use* supplies the H3 features." | 已修改 |

## Minor

本轮只执行已批准的 8 项 Major。下列 Minor 中，m-04、m-07、m-09 在 Major 改写过程中一并消解；其余仍未处理。m-03 因本轮修改而升级为**实际版本漂移**。

| 编号 | 位置 | 对应标准 | 原因与影响 | 修改建议 | 状态 |
| --- | --- | --- | --- | --- | --- |
| m-03 | `<HOME>/Desktop/UNSW_MA_Hackathon_Proposal_Draft.docx`（SHA-256 `ea55bc40…`）vs `proposal/UNSW_MA_Hackathon_Proposal_Draft.docx`（`e175e819…`） | 版本管理；SB-03 | 桌面副本仍是修改前的旧版，两者已不一致，存在误发旧稿的实际风险 | 删除桌面旧副本，或用 `proposal/` 下的新版覆盖；提交前以哈希确认发出的是哪一版 | **未解决（已升级）** |
| m-01 | DOCX 第 4 节标题设 `pageBreakBefore` | SCORE-005 | 第 3 页下部约 45% 留白、第 4 页约 45% 充满；无空白页 | 删除强制分页可压缩为 3 页 | 未解决 |
| m-02 | 文件名与 `docProps/core.xml`（`contentStatus` "Draft"、`dc:title` 含 Draft、`dc:description` 说明由 proposal.md 生成） | SB-03；SCORE-005 | 提交件文件名与属性仍标记 Draft，并暴露生成流程 | 按主办方命名规则重命名并清理属性；`dc:creator`/`lastModifiedBy` 当前为空 | 未解决 |
| m-05 | `proposal.md:40`（sector 阈值 500） | SCORE-002 | 完整数据 1,453,846 笔、sector 仅十余个，阈值近乎不触发 | 改为对 sector×year 报告单元设最小观测数 | 未解决 |
| m-06 | `proposal.md:38`（"the interaction is descriptive or omitted"） | SCORE-002 | 预注册规则给出二选一的不确定结果 | 写成确定规则：F1 < 0.80 → 仅描述性；任一类流行率 < 1% → 删除 | 未解决 |
| m-08 | DOCX 公式段 "Σ[j in A_i]" | SCORE-005 | 非标准求和记法；为文本+下标而非公式对象 | 改为 Σ 下标形式或 Word 公式对象 | 未解决 |
| m-10 | `proposal.md:48`（AFT 分支仍在交付段） | SCORE-005 | 主模型选择依赖 Day 1 数据事实，但分支规则出现在模型段之后 | 在模型段开头一句说明分支规则 | 未解决 |
| m-11 | `proposal.md:38`（H3 双编码） | SCORE-002 | 未预设编码者间一致性指标与分歧裁定规则 | 补充 Cohen's κ 与裁定方式 | 未解决 |
| m-12 | `word/styles.xml`（Heading2 与正文同为 11pt） | SCORE-005 | 二级标题仅靠加粗区分 | H2 提至 12pt 或加段前距 | 未解决 |
| m-04 | `proposal.md:34` | SCORE-002 | 聚类降级规则逻辑不对称 | 已随 M-05 改写为"If country clusters are too few, week-clustered errors become primary with a country wild-cluster bootstrap." | 已消解 |
| m-07 | `proposal.md:58` | SCORE-005 | "unconfirmed AI rules" 原出现三次 | 已随 M-05 删减为一处（Data items 段） | 已消解 |
| m-09 | `proposal.md:66` | SCORE-005 | "Subject to code rules, …" 悬垂修饰 | 已改为"Versioned dictionaries, logs, specifications, and scripts will trace reported numbers to inputs." | 已消解 |

## 本轮修改的副作用与须知

1. **为控制字数而删除的表述**（原文有、现文无，均为可接受的取舍，但请人工确认）：
   - "Same-timestamp loans are batched, include one another, and exclude themselves."（同时间戳批处理规则）
   - "A_i proxies concurrently available measurable loans, not actual exposure, search results, or ranking."（§4 限制段仍保留"The reconstructed pool is not individual exposure"）
   - 交付段中重复的删失句"Only loans confirmed active at an organiser-supported observation end are censored there…"（同一规则仍完整保留在池定义段）
   - "Blank or too-short use records are reported and excluded only from H3."
   - H3 数字特征的"per-100-word count is a robustness check"
   - §1 中的可选扩展句（同一门槛仍保留在 §2 交付段）
   - "We will audit text coverage by language and sector"（language 仍在 §3 的审计清单中；公平性表述压缩为"We will not interpret duration as borrower quality."）
2. **Codex 台账已与正文脱节，须同步**（本轮未修改起草台账，以免越过角色分工）：
   - `requirements.md` §8：MTH-001（14 天并列对照池）、MTH-004（week FE、fractional days）、MTH-006（模板短语剔除与 boilerplate share）
   - `assumptions.md`：ASM-004、ASM-005、ASM-006、ASM-015
   - `outline.md`：SEC-00 字数预算（现为 19/216/788/171/248）、SEC-04（disbursalDate）、SEC-05～06（week FE、fractional days、模板剔除）、SEC-08（H4 描述性承诺）、SEC-09（7/30 天）、SEC-14（Day 3 降级顺序）
   - `compliance-matrix.md`：CMP-WF-010 字数、§6 降级顺序（原为"先删 H4，再删 H3"，现为"先删稳健性变体 → H4 推断部分 → H3"）
3. **H4 降级顺序的变更改动了此前由人工冻结的规则**（CONTEST_RULES §3.1 与 compliance-matrix §6）。该变更源自用户已批准的 M-06；建议在 CONTEST_RULES §9 变更记录中补记一行，以维持"唯一竞赛标准"的可追溯性。

## 逐项检查摘要（修改后复核）

| 要求/评分项 | 检查结果 | 说明 |
| --- | --- | --- |
| REQ-CON-001 目标与受众 | 满足 | §1 接入 subsistence-market 语境，§4 区分平台与借款人/合作机构含义 |
| REQ-CON-002 自行形成研究问题 | 满足 | H1–H4 由团队提出 |
| REQ-CON-003 必答内容 | 满足 | 五项内容齐备；数据项首句歧义已消除 |
| REQ-CON-004 推荐结构五组件 | 部分满足 | 结构完整；names/affiliations 仍为占位符（SB-01） |
| REQ-CON-005 ≤1,500 words | 满足 | 1,442 词，余量 58 词 |
| REQ-CON-006 无需完成完整分析 | 满足 | 全文为计划表述 |
| REQ-CON-007 一周可完成 | 满足 | Day 1–7 与降级顺序完整；week FE 与 14 天对照池不增加实质计算量 |
| REQ-CON-008／009／010 | 未满足 | SB-03／SB-01／SB-02 |
| REQ-DATA-001 数据口径 | 满足 | 规模、期间、PPP 阈值与官网一致 |
| REQ-DATA-002 funding speed | 满足 | 已明确为两时间戳之差的小数天数 |
| SCORE-001 原创性（30%） | 满足（文本层面） | 新增注意力机制陈述；模板文本替代解释已显式处理 |
| SCORE-002 严谨性（30%） | 满足（文本层面） | 风险集内生性、时间粒度、结果粒度、模板混杂四项均已写入并给出预定处理 |
| SCORE-003 战略深度（20%） | 满足（文本层面） | sector/year 变异成为受保护的描述性交付物，并在 §1/§4 双处点明 |
| SCORE-004 可行性（10%） | 满足 | 计算路径与降级顺序自洽 |
| SCORE-005 清晰度（10%） | 满足 | 字段名统一斜体；歧义句已改写；仍有 m-01/m-08/m-12 待优化 |
| 规则 4／5／6／9／10／11／12 | 满足 | 英文正文；无结果化表述；1,442 词；同池与池规模标准化不变；全文仍只作 association；100 条样本边界句保留；不显著不等于无关联的条件表述保留 |
| 隐私 | 满足 | 无姓名、坐标、图片 URL 或完整故事；文档属性无作者信息 |

## DOCX 核查（修改后）

- **文本比对**：DOCX 35 段与 `proposal.md` 35 段逐段一一对应，字符级完全一致（除 Markdown 标记移除、`*…*` 转为斜体、`_i`/`_j` 转为 `vertAlign=subscript`）；`min_df` 等下划线字面已随参数删减不再出现，`country_name` 的下划线正确保留。
- **字数**：DOCX 全部内容保守计数 **1,442** 词（标题区 19／§1 216／§2 788／§3 171／§4 248），低于官网 1,500 上限，余量 58 词。
- **样式**：沿用原 `styles.xml`、页眉页脚与节设置（A4、四边 1 英寸、Arial 11pt、两端对齐、页脚居中 PAGE 域）。前置行的居中与紧凑行距已按原稿还原。
- **逐页渲染（Word 导出 PDF，4 页）**：

| 页 | 内容 | 结果 |
| --- | --- | --- |
| 1 | 标题、姓名/单位、§1、§2 起至"Empty-pool loans…" | 无乱码、无截断、无重叠；斜体字段名与下标显示正确；公式居中完整；页码 1 |
| 2 | §2 主体至 Day 1–7 计划 | 同上；页码 2 |
| 3 | §2 末段、§3 全部 | 正文正常；下部约 45% 留白（强制分页，m-01）；页码 3 |
| 4 | §4 全部 | 正文正常；非空白页；页码 4 |

## 审批结论

<!-- 审查完成后，下一行必须且只能填写 APPROVED 或 CHANGES REQUIRED；审查前保持为空。 -->

CHANGES REQUIRED
