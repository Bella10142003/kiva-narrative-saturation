# %% [markdown]
# # 步骤 1：数据画像与质量检查
#
# 对应 `src/profile_and_prepare.py`。需要先跑完 `步骤0_读取原始数据.py`。
# 每格 `Shift+Enter`。

# %%
# ============ 第 1 格：连上 duckdb，把 parquet 挂成一张表 ============
# 145 万行不往 pandas 里塞，交给 duckdb 直接查 parquet。
import duckdb, pandas as pd
from pathlib import Path

def find_project_root():
    here = Path.cwd().resolve()
    for c in [here, *here.parents]:
        if (c / "3_分析步骤").is_dir() and (c / "5_最终交付包").is_dir():
            return c
    raise RuntimeError("找不到项目根目录。请确认 notebook 在 3_分析步骤/详解版/ 里打开。")

ROOT = find_project_root()
print("项目根目录:", ROOT)

WORK = ROOT / "4_中间产物"
RAW_GLOB = str(WORK / "data/raw_parquet/*.parquet")

con = duckdb.connect()
con.execute("SET threads=8")
con.execute("SET memory_limit='8GB'")
con.execute("SET TimeZone='UTC'")      # ← 时区钉死 UTC，否则换台机器结果会漂
con.execute(f"CREATE OR REPLACE VIEW raw AS SELECT * FROM read_parquet('{RAW_GLOB}', union_by_name=true)")

print(con.execute("SELECT COUNT(*) AS 行数 FROM raw").fetchdf())
con.execute("DESCRIBE SELECT * FROM raw").fetchdf()

# %%
# ============ 第 2 格：把 3 个日期字符串解析成时间戳 ============
# TRY_CAST 解析失败返回 NULL 而不是报错，这样能把"有多少条日期是坏的"量出来。
con.execute("""
CREATE OR REPLACE TEMP VIEW typed AS
SELECT *,
  TRY_CAST(fundraisingDate AS TIMESTAMPTZ) AS fundraising_ts,
  TRY_CAST(raisedDate       AS TIMESTAMPTZ) AS raised_ts,
  TRY_CAST(disbursalDate    AS TIMESTAMPTZ) AS disbursal_ts
FROM raw
""")

con.execute("""
SELECT id, fundraisingDate, fundraising_ts, raisedDate, raised_ts,
       EPOCH(raised_ts - fundraising_ts)/3600.0 AS funding_hours
FROM typed LIMIT 8
""").fetchdf()

# %%
# ============ 第 3 格：整体体检 ============
# 重点看 negative_durations —— 到款时间早于上架时间，属于不可能事件。
row_summary = con.execute("""
SELECT
  COUNT(*) AS rows,
  COUNT(DISTINCT id) AS distinct_ids,
  SUM(CASE WHEN id IS NULL THEN 1 ELSE 0 END) AS null_ids,
  SUM(CASE WHEN fundraising_ts IS NULL THEN 1 ELSE 0 END) AS invalid_fundraising_dates,
  SUM(CASE WHEN raisedDate IS NOT NULL AND raised_ts IS NULL THEN 1 ELSE 0 END) AS invalid_raised_dates,
  SUM(CASE WHEN raised_ts < fundraising_ts THEN 1 ELSE 0 END) AS negative_durations,
  SUM(CASE WHEN raised_ts = fundraising_ts THEN 1 ELSE 0 END) AS zero_durations,
  MIN(fundraising_ts) AS min_fundraising_ts,
  MAX(fundraising_ts) AS max_fundraising_ts,
  COUNT(DISTINCT sector) AS sectors,
  COUNT(DISTINCT activity) AS activities,
  COUNT(DISTINCT country_name) AS countries
FROM typed
""").fetchdf()
row_summary.T          # 转置了更好读

# %%
# ============ 第 4 格：status × 是否有到款日 交叉表 ============
# 这张表回答一个关键问题：这份数据是不是"只有已筹满的贷款"？
con.execute("""
SELECT COALESCE(status,'<NULL>') AS status,
       COUNT(*) AS loans,
       SUM(CASE WHEN raised_ts IS NOT NULL THEN 1 ELSE 0 END) AS raised_date_present,
       SUM(CASE WHEN raised_ts IS NULL     THEN 1 ELSE 0 END) AS raised_date_missing,
       ROUND(100.0*AVG(CASE WHEN raised_ts >= fundraising_ts THEN 1.0 ELSE 0.0 END),4) AS valid_pct
FROM typed GROUP BY 1 ORDER BY loans DESC
""").fetchdf()

# %%
# ============ 第 5 格：筹款时长分位数 ============
# 看这条分布，就明白为什么后面建模要对时长取 log(1+x)：右尾拖得极长。
con.execute("""
SELECT COUNT(*) AS valid_funded_loans,
  QUANTILE_CONT(EPOCH(raised_ts-fundraising_ts)/3600.0, 0.01) AS p01_hours,
  QUANTILE_CONT(EPOCH(raised_ts-fundraising_ts)/3600.0, 0.25) AS p25_hours,
  QUANTILE_CONT(EPOCH(raised_ts-fundraising_ts)/3600.0, 0.50) AS p50_hours,
  QUANTILE_CONT(EPOCH(raised_ts-fundraising_ts)/3600.0, 0.75) AS p75_hours,
  QUANTILE_CONT(EPOCH(raised_ts-fundraising_ts)/3600.0, 0.95) AS p95_hours,
  QUANTILE_CONT(EPOCH(raised_ts-fundraising_ts)/3600.0, 0.99) AS p99_hours,
  MAX(EPOCH(raised_ts-fundraising_ts)/3600.0) AS max_hours
FROM typed WHERE raised_ts >= fundraising_ts
""").fetchdf().T

# %%
# ============ 第 6 格：逐年分布 ============
# 2016–2024 是训练期，2025 留作 holdout。这里能看到每年样本量。
con.execute("""
SELECT EXTRACT(YEAR FROM fundraising_ts)::INTEGER AS year,
       COUNT(*) AS loans,
       SUM(CASE WHEN raised_ts >= fundraising_ts THEN 1 ELSE 0 END) AS valid_events,
       SUM(CASE WHEN raised_ts IS NULL THEN 1 ELSE 0 END) AS raised_missing
FROM typed GROUP BY 1 ORDER BY 1
""").fetchdf()

# %%
# ============ 第 7 格：三个文本字段的可用性 ============
# use / description / whySpecial 哪个够长够全？这决定了下一步 TF-IDF 用哪个字段。
con.execute(r"""
SELECT * FROM (
  SELECT 'use' AS field, COUNT(*) AS rows,
    SUM(CASE WHEN use IS NOT NULL AND TRIM(use)<>'' THEN 1 ELSE 0 END) AS nonempty,
    ROUND(100.0*AVG(CASE WHEN use IS NOT NULL AND TRIM(use)<>'' THEN 1.0 ELSE 0.0 END),2) AS nonempty_pct,
    QUANTILE_CONT(LIST_COUNT(REGEXP_EXTRACT_ALL(COALESCE(use,''),'\S+')),0.50) AS median_tokens,
    QUANTILE_CONT(LIST_COUNT(REGEXP_EXTRACT_ALL(COALESCE(use,''),'\S+')),0.90) AS p90_tokens
  FROM raw
  UNION ALL SELECT 'description', COUNT(*),
    SUM(CASE WHEN description IS NOT NULL AND TRIM(description)<>'' THEN 1 ELSE 0 END),
    ROUND(100.0*AVG(CASE WHEN description IS NOT NULL AND TRIM(description)<>'' THEN 1.0 ELSE 0.0 END),2),
    QUANTILE_CONT(LIST_COUNT(REGEXP_EXTRACT_ALL(COALESCE(description,''),'\S+')),0.50),
    QUANTILE_CONT(LIST_COUNT(REGEXP_EXTRACT_ALL(COALESCE(description,''),'\S+')),0.90)
  FROM raw
  UNION ALL SELECT 'whySpecial', COUNT(*),
    SUM(CASE WHEN whySpecial IS NOT NULL AND TRIM(whySpecial)<>'' THEN 1 ELSE 0 END),
    ROUND(100.0*AVG(CASE WHEN whySpecial IS NOT NULL AND TRIM(whySpecial)<>'' THEN 1.0 ELSE 0.0 END),2),
    QUANTILE_CONT(LIST_COUNT(REGEXP_EXTRACT_ALL(COALESCE(whySpecial,''),'\S+')),0.50),
    QUANTILE_CONT(LIST_COUNT(REGEXP_EXTRACT_ALL(COALESCE(whySpecial,''),'\S+')),0.90)
  FROM raw
) ORDER BY field
""").fetchdf()

# %%
# ============ 第 8 格：每列空值率 ============
cols = con.execute("DESCRIBE SELECT * FROM raw").fetchdf()["column_name"].tolist()
exprs = [f'SUM(CASE WHEN "{c}" IS NULL THEN 1 ELSE 0 END) AS "{c}"' for c in cols]
nulls = con.execute("SELECT " + ",".join(exprs) + " FROM raw").fetchdf()
n = int(row_summary.iloc[0]["rows"])
pd.DataFrame({"column": cols,
              "null_count": [int(nulls.iloc[0][c]) for c in cols],
              "null_pct": [round(100.0*int(nulls.iloc[0][c])/n, 4) for c in cols]}
             ).sort_values("null_pct", ascending=False)

# %%
# ============ 第 9 格：和定稿结果对一下 ============
# 你自己算出来的，应该和交付包里的 CSV 完全一致。
FINAL = ROOT / "5_最终交付包" / "MA-Hackathon-Final-2026-09-04" / "outputs"
print("=== 定稿包里的 data_profile_summary.csv ===")
print(pd.read_csv(FINAL / "data_profile_summary.csv").T)
