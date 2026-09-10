# 全流程执行指令

> 这份文件是给 AI 的总指令。用户只需要说一句：
> **「读 `~/Desktop/hackathon/02_RUN_ALL.md`，按它执行。」**

---

## 第一步：环境自检（在写任何分析代码之前）

先跑下面这段，把结果原样贴给我：

```python
import sys, platform, shutil, importlib, subprocess
print("Python", sys.version.split()[0], "|", platform.platform())
try:
    import psutil; print("内存 GB:", round(psutil.virtual_memory().total/1e9,1))
except ImportError:
    print("内存 GB: psutil 未安装")
print("磁盘可用 GB:", round(shutil.disk_usage(".").free/1e9,1))
for m in ["pandas","numpy","scipy","sklearn","statsmodels","pyarrow","matplotlib","pyfixest","lifelines"]:
    try:
        print(" ", m, importlib.import_module(m).__version__)
    except Exception:
        print(" ", m, "MISSING")
r = subprocess.run([sys.executable,"-m","pip","install","--quiet","--dry-run","pyfixest"],
                   capture_output=True, text=True, timeout=60)
print("能否联网装包:", "可以" if r.returncode==0 else "不行 → " + r.stderr.strip()[:200])
```

然后判断你走哪条路线，**明确告诉我你选了哪条**：

| 条件 | 路线 |
|---|---|
| 内存 ≥ 12 GB **且** 缺的包能装上 | **路线 A —— 你自己跑全流程** |
| 不满足 | **路线 B —— 你只写代码，我在本机跑** |

如果内存在 8–12 GB 之间：走路线 A，但全量阶段必须严格分块，不要整表载入。

⚠️ 如果自检显示内存只有 3 GB、且装不了包 —— 你在一个受限沙盒里，**不要尝试读 `Kiva_Loans.pkl`，会被系统 kill**。直接走路线 B。

---

## 第二步：读背景

读完 `00_CONTEXT.md`（项目宪法）和 `01_PROMPTS.md`（分阶段细则）。

读完之后，在开始之前先回答三件事：

1. 用三句话复述研究问题
2. 说出宪法里最容易出错、或写得不够清楚的两个地方
3. 基于你的环境自检结果，说明你打算怎么控制内存

---

## 路线 A：你自己跑全流程

### 授权范围

**你可以自主连着跑，不必每一步都问我。** 但有三个**强制停靠点**，到了必须停下来等我确认：

| 停靠点 | 在哪一步 | 为什么不能自己决定 |
|---|---|---|
| **G1 口径冻结** | S1 结束 | 主文本字段选哪个、active pool 用不用、窗口多少天 —— 这些是学术判断，会改变整篇论文的结构，必须我签字 |
| **G2 恒等式校验** | S3 结束 | 200 笔暴力比对的误差必须 ≤ 1e-9。误差大说明实现有 bug，后面所有系数都是错的，不能带着 bug 往下跑 |
| **G3 标准化顺序** | S4 开始前 | 必须是「先用 2016–2024 fit scaler，**再**造 C×H 和 V×G」。跑之前把你的代码这一段贴给我看一眼 |

除这三处之外，你可以一路跑到底。

### 执行顺序

**先在小样本上速通。** S0 生成 `data/dev_sample.parquet`（10 万行，按 sector × year 分层）之后，先用它把 S1→S6 整条链跑通一遍，报错自己改。目的是暴露接口问题，不是拿结论。速通完告诉我：整条链跑通了、耗时多少、全量预估多久。

**然后才上全量**，按 S0 → S1 →〔G1〕→ S2 → S3 →〔G2〕→〔G3〕→ S4 → S5 → S6 → S7 的顺序。

每个 stage 的详细要求见 `01_PROMPTS.md` 对应章节 —— 里面的「验收标准」一栏是硬要求，不是建议。

### 内存纪律（这个项目最容易翻车的地方）

- `Kiva_Loans.pkl` 只在 S0 读一次。读完立刻拆成按年分区的 parquet，`del` 掉原 DataFrame 并 `gc.collect()`。**此后再也不碰 pkl。**
- 之后每个 stage 只读它需要的列。文本列用 `string[pyarrow]` dtype。
- TF-IDF 稀疏矩阵按 sector × year 分块写 `.npz`，不要整体驻留内存。
- 每个 cell 结尾打印当前进程内存占用。内存超过总量 70% 就停下来告诉我。

---

## 路线 B：你只写代码，我在本机跑

工作方式是一个循环：

```
你写 .ipynb  →  落进 notebooks/  →  我在本机 Jupyter 里跑
     ↑                                       ↓
你读 logs/ 和 outputs/  ←  notebook 把结果写回文件夹
```

规则：

- **一次只写一个 stage**，写完停下等我回传运行结果。前一步的真实输出会改变后一步的写法。
- 每个 notebook 必须**可独立重跑** —— 只依赖 `data/` 里上一步的落盘文件，不依赖内存里的变量。
- 每个 cell 结尾 print：shape、关键字段缺失率、内存占用、本 cell 耗时，并追加写入 `logs/run_log.txt`。这是我回传给你的唯一凭据。

---

## 两条路线共同的铁律

**一、数字必须有出处。** 任何写进报告、注释、总结里的数字，都要能追到 `outputs/` 或 `logs/` 里某个具体文件的具体列。查不到就写 `【待填：来源 outputs/xxx.csv】`，**不许估一个看起来合理的值**。我会逐条核对。

**二、绝不静默降级。** 跑不动、包缺失、内存不够 —— 明确说出来，给出降级方案，让我决定要不要接受。不许偷偷换成一个更简单的做法然后当原方案汇报。

**三、口径不明就停下来问。** 遇到宪法里没写死的选择（阈值、分箱、剔除规则），列出选项和各自后果，问我。不要自己选一个默认值继续。

**四、留痕。** 每张表同时存 CSV 到 `outputs/`，每张图同时存 300 dpi 的 PNG 和 PDF 到 `figures/`，并配一个同名 CSV（图上每个点都要能查到）。

---

## 最终交付清单

跑完之后，我应该在文件夹里看到：

- `notebooks/` —— S0 到 S6 共七个 .ipynb，每个可独立重跑
- `outputs/` —— 至少包含 `frozen_spec.csv`、`pool_identity_check.csv`、`rq1_main_table.csv`、`rq2_raw_vs_residual.csv`、`robustness.csv`、`rq3_year_effects.csv`、`rq4_sector_effects.csv`、`engine_scores_2025.csv`、`holdout_validation.csv`
- `figures/` —— 主图是 `rq3_year_marginal_effects.png`（两条通道 2016→2024 的年度边际效应，带 95% 置信带）
- `logs/run_log.txt` —— 完整运行记录
- **`REPORT.md`** —— 中文结论报告，结构见 `01_PROMPTS.md` 的 Stage 7；报告里每个数字都要脚注标出它来自哪个文件

---

## 开始

现在执行第一步的环境自检，把结果贴给我，并告诉我你选哪条路线。
