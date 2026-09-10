# Kiva 叙事饱和提案 · 模拟验证工作区

在提交前用合成数据实际跑一遍提案的分析流程，检验每个环节的必要性与可行性。

## 依赖

```bash
pip install numpy pandas scipy scikit-learn openpyxl
```

## 四个脚本，按顺序跑

| 脚本 | 作用 | 耗时 |
|---|---|---|
| `generate_kiva_sim.py` | 生成 20,000 条模拟数据 + 答案本。改 `CFG['N']` 换规模，改 `TRUE` 字典换效应量 | 30 秒 |
| `分析流程_逐步详解.py` | **先看这个。** 扮演分析者跑完 Day1–Day5，15 个步骤逐步打印中间产物 | 36 秒 |
| `analysis_pipeline.py` | 同样的流程，紧凑版，用于计时与批量产出 | 38 秒 |
| `compare_to_truth.py` | 把估计与植入的真值逐项对答案（需先跑 `analysis_pipeline.py`） | 3 秒 |
| `extra_specs.py` | 九个对照规格 + 功效外推（需先跑 `analysis_pipeline.py`） | 8 秒 |

```bash
python3 generate_kiva_sim.py
python3 分析流程_逐步详解.py | less        # 想看清每一步就看这个
python3 analysis_pipeline.py
python3 compare_to_truth.py
python3 extra_specs.py
```

## 数据文件

| 文件 | 能不能用于分析 | 说明 |
|---|---|---|
| `kiva_sim_20k.pkl` / `.csv` | ✅ | 模拟数据本身，27 个字段与官方 100 条样本同构 |
| `kiva_sim_truth.csv` | ❌ **答案本** | 合作机构、真实 C/H/V/G、不可观测的行业-周冲击。真实 Kiva 数据里没有这些字段 |
| `kiva_sim_meta.json` | — | 生成参数与植入的真实系数 |

## 结论文档

- `模拟验证报告.md` —— 16 个环节逐条判定保留 / 简化 / 删除
- `提案第2节_简化版.md` —— 可直接替换 v4 Section 2 的英文正文（702 词）
- `分析流程_逐步输出.txt` / `对答案_完整输出.txt` / `补充规格_完整输出.txt` —— 完整运行记录

## 三点提醒

1. **池规模只有真实数据的约 1/70。** 20,000 条摊到 10 年、11 个行业，行业主动池平均只有 9 条。所有涉及精度与门槛的结论都偏保守。
2. **真值是设定出来的，不是发现。** 「use 比 description 更贴近真值」「机构混杂不构成偏误」「效应量是这么大」这三条都是生成端的设定。
3. **随机种子固定为 20260823**，重跑结果完全一致。
