# 分阶段指令 · 可直接复制粘贴

> 用法：每次开始一个新 stage，把对应那一段**整段复制**给 AI。
> 每段都已经内置了「目标 / 输入 / 产出 / 硬约束 / 验收标准」五件套 —— 其中**验收标准**是防止 AI 糊弄的关键，不要删。

---

## 第一条指令（每个新会话的开场白，必须先发这条）

```
读 ~/Desktop/hackathon/00_CONTEXT.md，完整读完。

读完后先回答我三件事，不要写任何代码：
1. 用三句话复述研究问题
2. 说出你被允许做什么、被禁止做什么
3. 指出这份宪法里你认为最容易出错、或者写得不够清楚的两个地方

我确认之后你才开始做事。
```

> **为什么要有这一步：** 让 AI 先复述再动手，能把「它以为它懂了」和「它真的懂了」区分开。第 3 问尤其重要 —— 一个真读懂了的 AI 会指出真实的模糊点；一个没读懂的会泛泛夸奖你的设计。

---

## Stage 0 · 数据落地（这一步我自己在本机跑，你只写代码）

```
【目标】把 1.6 GB 的 pkl 拆成后续所有 stage 都能分块读的 parquet，此后再不碰 pkl。

【硬约束】
- 这段代码只会跑一次，跑在我 Mac 的原生 Jupyter 里（不是你的沙盒）
- 假设可用内存 16 GB，但要按「峰值不超过 10 GB」来写
- 读进来之后立刻分列写盘，写完一块就 del 一块并 gc.collect()

【产出】notebooks/S0_prepare.ipynb，写进 ~/Desktop/hackathon/notebooks/，做四件事：
1. 读一次 pkl，打印：shape、每列 dtype、每列内存占用、每列缺失数
2. 拆成两份，按 fundraisingDate 的年份分区写进 data/：
   - core/  → id + 所有数值/类别/日期字段（category 与 datetime64 dtype）
   - text/  → id + description + use + whySpecial（dtype = string[pyarrow]）
3. 切一份 10 万行的分层抽样（按 sector × year 分层）存 data/dev_sample.parquet
   —— 之后所有代码先在 dev 集跑通再上全量
4. 把 1 的所有打印结果写进 logs/S0_schema.txt

【验收标准】我跑完之后会把 logs/S0_schema.txt 回传给你。在拿到它之前，
不要假设任何字段存在、不要假设任何字段的取值范围。

【完成后】停下来等我回传，不要继续写 S1。
```

---

## Stage 1 · 数据体检与口径冻结

```
【目标】把宪法里所有还没写死的口径全部定死，并产出一张「口径冻结表」。
这一步做完之后，任何口径都不再改动。

【输入】data/core/、data/text/、logs/S0_schema.txt（你已经读过）

【产出】notebooks/S1_audit.ipynb + outputs/frozen_spec.csv + logs/S1_audit.txt

【必须回答的六个问题，每个都要有具体数字支撑】

1. 主文本字段选 description 还是 use？
   对两者各报四个数：非空率、masking 前后的 token 数中位数、随机 1 万对的
   零重叠率、H 的分布方差。whySpecial 只有非空率过关才进模型，否则当场剔除。

2. active pool 能不能用？
   把 raisedDate 的缺失情况按 status 交叉制表。对没有 raisedDate 的贷款，
   检查是否有其他字段能推出退出时间。
   → 推不出来，就当场把 14 天池转正为主口径，active pool 降级为附录。

3. 14 天窗口该是多少天？
   用全量重算融资时长分布，报出 P25 / P50 / P75 / P90 / P95。
   提案基于 100 笔样本假设「75% 在 15 天内融满」—— 现在有 145 万笔，验证它。
   若实测 P75 明显偏离 15 天，就把窗口改成实测 P75。

4. 最小池规模 10 站得住吗？
   算 sector × date 的池规模分布，报出「池 < 10 的贷款占比」。
   若占比 > 15%，说明 sector 粒度可能不合适，列出替代方案让我选。

5. 数据里有没有 Lending Partner 相关字段？
   有就报出字段名和 nunique；没有就明确说没有（模板检测的"跨来源"条件会改用 country_name 代理）。

6. 清洗规则一次定完：
   时区是否统一、负融资时长有多少、重复 id 有多少、2016 与 2025 的边界怎么截、
   FundingHours 的 P99 和最大值是多少。

【硬约束】
- 只读你需要的列，不要整表载入
- 每个结论都要有对应的 print 输出，我要能在 logs/S1_audit.txt 里找到它

【验收标准】outputs/frozen_spec.csv 必须是一张 10 行以内的表，
每行格式为：口径项 | 最终取值 | 判断依据（具体数字）。
这张表会原样做成一页 slide 给评委看，所以「依据」一栏不能写"根据惯例"，
必须写"实测 P75 = X 天"这样的话。

【完成后】停下来等我回传 logs/S1_audit.txt。
```

---

## Stage 2 · 文本管线

```
【目标】把原始文本变成可用于相似度计算的 TF-IDF 向量，并识别机构模板。

【输入】data/text/、outputs/frozen_spec.csv（主文本字段已在 S1 定死）

【产出】notebooks/S2_text.ipynb + data/tfidf/（分年分块）+ data/boilerplate.parquet

【四个步骤】

1. Masking
   - 借款人姓名、country_name、region 这些数据里本来就有字段 →
     用精确字符串替换，不要用 NER（又快又准）
   - 金额 / 货币 / 日期 / 机构缩写 → regex
   - 全部换成固定 placeholder：[NAME] [LOC] [AMT] [DATE] [ORG]
   - ⚠️ 不要换成空字符串，否则 bigram 会跨越缺口生成假搭配

2. TF-IDF
   - unigram + bigram，L2 归一化
   - 词表必须压：min_df=20 或 max_features=200_000
     （145 万文档的 bigram 词表不压会到千万量级）
   - 用全量 fit 一次 vectorizer，然后按 sector × year 分块 transform 并落盘

3. 模板检测
   - 对 masking 后的文本取 5-gram 哈希计数
   - 判定条件：文档频率 > 阈值 且 跨 ≥3 个不同来源
     （来源字段见 S1 第 5 问的答案）
   - 移除模板得 residual text，重新跑一次 TF-IDF
   - 同时产出每笔贷款的 boilerplate_share 变量

4. 落盘两套向量：raw 和 residual

【硬约束】
- 先在 data/dev_sample.parquet 上跑通全流程，打印耗时，估算全量耗时，
  报给我之后再上全量
- 稀疏矩阵不要整体驻留内存，按块写 .npz

【验收标准】
- 打印 5 个 boilerplate 5-gram 的实际文本 —— 我要能一眼看出它们确实是模板
- 打印 boilerplate_share 的分布（P10/50/90）
- 打印词表大小和稀疏矩阵的 nnz 总数

【完成后】停下来等我回传。
```

---

## Stage 3 · 三个池的 C / H / V / G

```
【目标】算出六个核心指标。这是整个项目技术上最难的一步。

【务必先读】宪法第 8 节第（一）条的恒等式。
如果你打算写两两相似度的双重循环，说明你没读，回去重读。

【产出】notebooks/S3_pools.ipynb + data/features.parquet + outputs/pool_identity_check.csv

【三个池的实现方式】
- 14 天池     → 按 sector 分组、按上架日排序，滑动窗口：进一条加向量，出一条减向量
- active 池   → 扫描线：fundraisingDate 事件 +x，raisedDate 事件 −x，按时间归并
- 30 天衰减池 → 按 sector×day 存日桶向量和，每天把 30 个日桶按七天半衰期加权求和
                （权重变了但桶不用重算）

【features.parquet 必须包含】
id, C, H, V, G, C×H, V×G（raw 和 residual 各一套）,
boilerplate_share, pool_size_active, pool_size_14d, pool_size_lag

【验收标准 —— 这一条不做完就不算完成】
随机抽 200 笔贷款，用最笨的双重循环暴力算出它们真实的池内两两平均余弦，
与增量算法的结果逐笔比对，把比对表存成 outputs/pool_identity_check.csv，
并打印最大绝对误差。**误差应在 1e-9 量级。**
如果误差大于 1e-6，说明实现有 bug，不要往下走，回来找我。

【为什么必须做】这张比对表会放进 slides 附录。它是我们最省力的可信度信号。

【完成后】停下来等我回传 outputs/pool_identity_check.csv。
```

---

## Stage 4 · 主模型（RQ1 + RQ2）

```
【目标】拿到能写上 slides 的第一批系数。

【产出】notebooks/S4_models.ipynb + outputs/rq1_main_table.csv +
        outputs/rq2_raw_vs_residual.csv + outputs/robustness.csv

【标准化顺序 —— 极易搞错，照此执行】
1. 用 2016–2024 fit 一次 scaler，标准化 C、H、V、G
2. 然后才构造 C×H 和 V×G
3. 把同一套缩放参数应用到 2025 holdout，不重新 fit

【主回归】用 pyfixest：
feols("log_fh ~ C + H + C:H + V + G + V:G + <控制变量> | country_name + activity + week", data)

【聚类标准误】按 country 与 week 双向聚类（同国共享制度冲击，同周共享平台流量冲击）。
另外跑单向 country、单向 week 各一次存进 outputs/robustness.csv，
评委问起来我要能当场翻附录。

【RQ2 的关键对照】raw text 一栏、residual text 一栏并排。
如果 V×G 在去掉模板后仍显著 —— 说明磨损来自真实的叙事重复而不是复制粘贴 ——
这是全场最强的一个结果，请在输出里明确标出来。

【稳健性一次跑完】
- 最小池 5 / 10 / 20 三档
- 剔除滞后窗口内仍在募的贷款
- AFT 删失模型：⚠️ lifelines 在 145 万行 + 高维 FE 上跑不动。
  抽 20 万行 + 只保 country/sector 粗固定效应，作为附录证据即可，
  不要在这里耗掉半天。

【验收标准】
每个系数除了数值和 p 值，还要附一句人话翻译：
「C×H 每增加 1 个标准差，融资时间变化 X%」。
评委不看星号，看幅度。

【完成后】停下来等我回传三个 csv。
```

---

## Stage 5 · 异质性（RQ3 + RQ4）

```
【目标】RQ3 的年度演化图是整场演讲的高潮，这一步的图比数字更重要。

【产出】notebooks/S5_hetero.ipynb + outputs/rq3_year_effects.csv +
        outputs/rq4_sector_effects.csv + figures/（定稿图）

【RQ3 · 年度演化】
C×H 和 V×G 分别与年份指示变量交互，2016 为基准。
画成两条带 95% 置信带的折线：横轴 2016→2024，纵轴各年边际效应。
⚠️ 注意报告的是「基线系数 + 交互系数」的组内边际效应，不是交互系数本身。
如果两条线交叉 —— 竞争通道走弱、磨损通道走强 —— 在输出里明确指出来。

【RQ4 · 板块与国家】
两个交互项分别与 sector、country 交互 + Wald 联合检验。
用森林图不用热力图：按边际效应排序的横向误差棒，评委三秒看出哪个板块最受挤压。
国家只保留贷款量前 15，其余合并为 Other。

【图表规范】
- 300 dpi，同时存 PNG 和 PDF
- 坐标轴标签写人话：不是 log_fh，是「融资时长（对数小时）」
- 去掉 matplotlib 默认的上边框和右边框
- 每张图配一个同名的 .csv，图上的每个点都能在 csv 里找到

【完成后】停下来等我回传。
```

---

## Stage 6 · Narrative Attention Engine

```
【目标】做出评委能带走的那个东西。这一步决定 managerial relevance 的得分。

【产出】notebooks/S6_engine.ipynb + outputs/engine_scores_2025.csv +
        outputs/holdout_validation.csv + figures/action_matrix.png

【四个分数】current crowding、homogeneity、saturation、boilerplate share，
各自转成同板块内的百分位（0–100）。

【2025 holdout 验证 —— 必须有真数字】
用 2016–24 的系数给 2025 的贷款打分，报告高分组与低分组的实际融资时长差异。
提案里承诺了「scoring transfers」，这里必须兑现成一个具体数字。

【72 小时压力测试】
在假设情景下有多少笔贷款会跌破 72 小时预测阈值。
⚠️ 输出里必须原样带上这句限定：
「这是情景推演，不是干预效果预测；真正的因果结论需要平台侧的前瞻性实验。」

【四象限行动矩阵】
- 高 current saturation  → 错峰上架 / 分类页多样化
- 高 recent saturation   → 更换叙事框架
- 高 boilerplate share   → 给 Lending Partner 做模板支持
- 低饱和却仍然慢         → 给曝光扶持，而不是逼借款人重写

报出每个象限在 2025 里的贷款数与占比。

【完成后】停下来等我回传。
```

---

## Stage 7 · 结论报告

```
【目标】写 REPORT.md。中文，写给我们自己的团队看，之后要能直接搬进 slides。

【输入】outputs/ 里的所有 csv、figures/ 里的所有图、logs/ 里的所有 log。
写之前请逐个读一遍，不要凭印象写。

【结构】
1. 一句话结论（这份研究最重要的一个发现，一句话）
2. 数据与口径（附 frozen_spec 表；说清楚哪些口径是数据逼出来的、哪些是我们选的）
3. RQ1：当前饱和度  —— 结论 + 主表 + 人话翻译
4. RQ2：磨损与模板  —— raw / residual 对照，明确回答「是不是只是复制粘贴」
5. RQ3：两条通道的演化 —— 主图 + 拐点在哪一年
6. RQ4：板块与国家边界
7. Narrative Attention Engine：四个分数 + 2025 holdout 的实测数字 + 行动矩阵
8. 稳健性小结（一张表说完，不展开）
9. 局限与后续（诚实写：内生性、TF-IDF 只捕词汇不捕语义、情景推演≠因果）
10. 附录索引：报告里每个数字对应到哪个 outputs 文件

【硬约束 —— 最重要的一条】
报告里出现的每一个数字，后面用脚注标出它来自哪个文件的哪一列。
凡是你没有在 outputs/ 里实际读到的数字，一律写成
【待填：来源 outputs/xxx.csv】
而不是估一个看起来合理的值。我会逐条核对。

【语气】
- 不要用"显著地"三个字代替具体幅度
- 零结果也要写清楚，一个明确的零结果讲好了不输给正结果
- 每一节末尾用一句话说明「这一节支撑 slides 的哪一页」
```

---

## 附：三条随时可以插进去的护栏指令

**当 AI 开始编数字时：**
```
停。你刚才写的这几个数字，逐个告诉我它们来自 outputs/ 里的哪个文件、哪一行、哪一列。
说不出来的，全部改成【待填】。
```

**当 AI 一口气写了太多：**
```
你一次写了太多步。回到 Stage X，只保留那一步的代码。
我需要看到那一步的真实输出，才能判断下一步该怎么写。
```

**当 AI 的方案跑不动时：**
```
不要静默降级。明确告诉我：哪一步跑不动、为什么、你打算怎么降级、
降级之后哪些结论会受影响。让我来决定要不要接受这个降级。
```
