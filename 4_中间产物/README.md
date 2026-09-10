# 4 · Intermediates

> 中间产物。数据文件不入库，可由 notebook 重跑。

Everything here is regenerable by re-running [`../3_分析步骤/`](../3_分析步骤/). Bulk `.parquet` files
(~1.7 GB) are excluded from the repository; the scripts, tables and audit manifests are kept because they
record *how* the numbers were arrived at.

| Path | What it is |
|---|---|
| `EDA/` | Exploratory scripts and their output tables and figures, plus a written summary of what they found |
| `演示复算/` | Independent recomputation of the numbers quoted in the presentation |
| `audit/` | Stage-by-stage manifests: row counts, hashes, and column contracts |
| `我算出来的结果/outputs/` | The result tables as produced locally, before packaging |
| `我算出来的结果/model_artifacts/` | Fitted TF-IDF IDF vectors and the vectorizer configuration |
| `说明.md` | Notes on what is safe to delete |
