# Kiva 叙事饱和度研究 · 项目宪法

> **任何 AI 助手在写第一行代码之前，必须完整读完这份文件。**
> 读完后请用三句话复述：研究问题是什么、你被允许做什么、你被禁止做什么。复述不对就不要往下做。

---

## 0. 项目背景

UNSW Marketing Analytics Hackathon 2026，队名 5 GUYS，29 队中 8 强，目标前三。
提案标题：*When Every Story Sounds the Same — Separating Market Crowding, Active Narrative Competition, and Narrative Wear-Out on Kiva*

核心论点：Kiva 上的贷款融资变慢，可能出于三种**不同**的机制，而平台通常把它们混为一谈：

1. **市场拥挤（crowding）** —— 同类项目太多
2. **主动叙事竞争（active competition）** —— 此刻在募的替代品，故事跟你太像
3. **叙事磨损（wear-out）** —— 最近刚讲过同样的故事，即使那些贷款已经离开页面

三种机制对应三种完全不同的干预。本研究要把它们分开测量。

---

## 1. 四个研究问题

| 编号 | 问题 | 对应检验 |
|---|---|---|
| **RQ1** | 当前同板块选择集**又多又像**时，融资是否更慢？ | `C × H` 交互项 |
| **RQ2** | 已经离开页面的贷款，其饱和度是否仍与更慢的融资相关？去掉机构模板后还成立吗？ | `V`、`G`、`V × G` 联合检验；raw vs residual 两套对照 |
| **RQ3** | 两条通道从 2016 到 2025 如何演化？ | 两个交互项 × 年份指示变量 |
| **RQ4** | 在哪些板块和国家最强？注意力市场是板块内还是跨平台？ | 两个交互项 × sector / country + Wald 联合检验 |

---

## 2. 变量定义（已冻结，不得自行更改）

被解释变量：`log(1 + FundingHours)`，FundingHours = raisedDate − fundraisingDate，单位小时。

| 指标 | 当前窗口 | 滞后窗口 |
|---|---|---|
| Volume（量） | `C` = log(当前同板块在募贷款数) | `V` = 时间衰减的早期贷款计数 |
| Homogeneity（同质度） | `H` = 与当前池的平均余弦相似度 | `G` = 时间衰减的、与早期故事的平均余弦相似度 |
| Saturation（饱和度） | `C × H` | `V × G` |

三个池的定义：

- **active pool** —— 焦点贷款上架时**仍在募**的其他同板块贷款；从其 fundraisingDate 进入，到 raisedDate（或假定关闭日）离开。
- **14 天对照池** —— 焦点贷款上架前 14 天内上架的其他同板块贷款，**不论其后来是否融资成功**。设立它是因为 active pool 的构成本身受先前融资结果影响（内生）。
- **30 天滞后池** —— 大多数早期贷款已经**结束**募资的窗口，起点取募资期的 95 分位；越接近焦点贷款权重越高，**七天半衰期**指数衰减。

控制变量与固定效应：loanAmount、borrowerCount、gender、lenderRepaymentTerm、repaymentInterval、上架时点特征、平台级总量；**Country FE + Activity FE + Week FE**。

标准化顺序（**极易搞错，务必按此**）：
1. 用 **2016–2024** 的数据 fit 一次 scaler，得到标准化的 C、H、V、G
2. **然后**才构造 `C×H` 和 `V×G`
3. 把**同一套**缩放参数应用到 2025 holdout，不重新 fit

最小池规模：主分析要求池内至少 **10** 笔；用 5 和 20 做敏感性检验。小池与空池**单独报告，不当作 0 处理**。

---

## 3. 数据

- 路径：`~/Desktop/hackathon/Kiva_Loans.pkl`（1.6 GB）
- 规模：1,453,846 条，2016-01-01 至 2025-12-31
- 字段：id, status, fundraisingDate, raisedDate, description, use, whySpecial, loanAmount, borrowerCount, gender, lenderRepaymentTerm, repaymentInterval, sector, activity, country_name, region, country_ppp, disbursalDate
- **禁止使用**：`fundsLentInCountry` 及任何在上架之后才确定的字段（会造成前视偏差）
- 输出中不得出现：姓名、精确地点、完整描述原文

---

## 4. 运行环境（硬约束，实测得出）

这个项目有**两个**不同的计算环境，请务必分清：

### A. 你（AI）能直接跑命令的沙盒 —— 只能用来读写文件

实测配置：**内存 3 GB · 4 核 · 无 sudo · 无法开 swap · 无网络（pip 装不了任何东西）**
已安装：`pandas 2.3.3`、`numpy 2.2.6`、`matplotlib 3.10.9`
**未安装且装不上**：`scipy`、`scikit-learn`、`statsmodels`、`pyarrow`、`pyfixest`、`lifelines`

已实测：在这个环境里 `pd.read_pickle('Kiva_Loans.pkl')` 会被系统 **kill**。

> **结论：这个环境不能用来做分析。** 它的唯一作用是：读写连接文件夹里的文件、看小样本、检查中间产物。

### B. macOS 本机的 Jupyter —— 真正执行分析的地方

完整内存、完整包。**所有实际计算都在这里发生。**

### 因此本项目的工作方式是一个循环：

```
你写 .ipynb  →  写进连接的文件夹  →  我在本机 Jupyter 里运行
     ↑                                          ↓
你读 log 和 outputs  ←  notebook 把结果写回同一个文件夹
```

**你永远不会亲眼看到全量数据的运行结果，除非我把它写进 `outputs/` 或 `logs/` 里而你去读它。**

---

## 5. 五条铁律

1. **数字必须有来源。** 任何写进 markdown、注释或报告的数字，都必须来自 `outputs/` 或 `logs/` 里某个你实际读过的文件。**禁止根据"应该差不多是这样"填写任何数值**，包括系数、p 值、样本量、耗时、占比。不确定就写 `【待填：来源 outputs/xxx.csv】`。

2. **一次只做一个 stage。** 写完一个 stage 的 notebook 就停下，等我回传运行结果，再写下一个。不要一次性把六个 stage 都写完 —— 前一步的真实输出会改变后一步的写法。

3. **每个 cell 都要留痕。** 每个 cell 结尾必须 print：当前 DataFrame 的 shape、关键字段的缺失率、进程内存占用（`psutil` 或 `resource`）、本 cell 耗时。这些会进 `logs/run_log.txt`，是我回传给你的唯一凭据。

4. **口径不明就停下来问。** 遇到宪法里没写死的选择（阈值、分箱、剔除规则），**不要自己选一个默认值继续**。列出选项和各自后果，问我。

5. **绝不静默降级。** 如果某步跑不动、包缺失、内存不够，明确说出来并给出降级方案，不要偷偷换成一个更简单的做法然后当作原方案汇报。

---

## 6. 目录与命名规范

```
~/Desktop/hackathon/
├── Kiva_Loans.pkl              # 原始数据，只读一次
├── 00_CONTEXT.md               # 本文件
├── 01_PROMPTS.md               # 分阶段指令
├── notebooks/
│   ├── S0_prepare.ipynb
│   ├── S1_audit.ipynb
│   ├── S2_text.ipynb
│   ├── S3_pools.ipynb
│   ├── S4_models.ipynb
│   ├── S5_hetero.ipynb
│   └── S6_engine.ipynb
├── data/                       # 中间产物（parquet），每个 stage 落盘
├── outputs/                    # 所有表格，一律同时存 CSV
├── figures/                    # 所有图，300 dpi PNG + PDF
├── logs/                       # run_log.txt，每次运行追加
└── REPORT.md                   # 最终结论报告（中文）
```

命名规则：`outputs/` 里的每个文件名必须能对应到报告里的某一节，例如 `outputs/rq1_main_table.csv`、`figures/rq3_year_marginal_effects.png`。

---

## 7. 最终交付物

1. **七个 .ipynb**，每个可独立重跑（只依赖 `data/` 里上一步的 checkpoint，不依赖内存里的变量）
2. **`REPORT.md`** —— 中文结论报告，结构见 `01_PROMPTS.md` 的 Stage 7
3. **`outputs/` 与 `figures/`** —— 报告里每一个数字、每一张图都能在这里找到出处

---

## 8. 已知的技术关键点（提前告诉你，省得你走弯路）

**（一）不要做两两相似度。** 池内平均余弦相似度看起来是 O(N × 池规模)，145 万笔会到万亿量级点积，跑不完。但因为 TF-IDF 向量已经 L2 归一化，余弦即点积，而点积对求和线性：

```
H_i = mean_j cos(x_i, x_j) = mean_j (x_i · x_j) = x_i · ( Σ_j x_j / n )
```

**这是精确恒等，不是近似。** 每笔贷款只需一次"自己 × 池向量和"的稀疏点积，池向量和增量维护：14 天池用滑动窗口（进一条加、出一条减），active 池用扫描线（fundraisingDate 事件 `+x`，raisedDate 事件 `−x`），30 天衰减池按 sector×day 存日桶向量和再加权求和。全程 O(N)。

**必须验证：** 随机抽 200 笔暴力算真实的两两平均余弦，与增量结果比对，最大绝对误差应在 `1e-9` 量级。这个比对表要存成 `outputs/pool_identity_check.csv`。

**（二）固定效应用 `pyfixest`。** Country（≈90）× Activity（≈160）× Week（≈520）合计七百多个 dummy，`statsmodels` 展开会爆内存；`pyfixest` 是 R 的 `fixest` 的 Python 移植，几秒出结果。

**（三）内存纪律。** 原始 pkl 展开后可能到 8–14 GB。Stage 0 之后**再也不要碰 pkl**，只读 `data/` 里按年分区的 parquet，且只读当前 stage 需要的列。文本列用 `string[pyarrow]` dtype。

**（四）模板检测要加"跨来源"条件。** 判定 boilerplate 时，光看 5-gram 的文档频率不够 —— 某一家 Lending Partner 自己的写作风格会被误判成模板。正确条件是：文档频率超阈值 **且** 跨 ≥3 个不同来源出现。

⚠️ 但官方字段清单里**没有 Lending Partner ID**。Stage 1 必须先确认：全量数据里是否存在 partner / lenderId / partner_name 之类的字段。
- **有** → 直接用它做"跨来源"条件
- **没有** → 用 `country_name` 作代理（同一家 partner 通常只服务一到两个国家），并在报告里明确写出这是代理而非原生字段
