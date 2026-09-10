# %% [markdown]
# # 步骤 0：安全读取原始 pickle
#
# **怎么用**：把光标放进下面任意一格，按 `Shift+Enter` 执行这一格。
# 执行后右边会弹出 Interactive 窗口显示结果，变量会一直留在内存里。

# %%
# ============ 第 1 格：参数 ============
from pathlib import Path

def find_project_root():
    here = Path.cwd().resolve()
    for c in [here, *here.parents]:
        if (c / "3_分析步骤").is_dir() and (c / "5_最终交付包").is_dir():
            return c
    raise RuntimeError("找不到项目根目录。请确认 notebook 在 3_分析步骤/详解版/ 里打开。")

ROOT = find_project_root()
print("项目根目录:", ROOT)

PKL = ROOT / "1_题目与数据" / "Kiva_Loans.pkl"
WORK = ROOT / "4_中间产物"          # 中间产物，可随时删
(WORK / "data/raw_parquet").mkdir(parents=True, exist_ok=True)
(WORK / "audit").mkdir(parents=True, exist_ok=True)

print("原始文件:", PKL)
print("大小: %.2f GB" % (PKL.stat().st_size / 1024**3))

# %%
# ============ 第 2 格：静态扫描字节码（不执行 pickle）============
# pickle 是可执行格式，直接 load 等于运行陌生程序。
# 这里只读 opcode，不执行，看有没有能 import 模块 / 调函数的危险指令。
import collections, pickletools, time

DANGEROUS = {"GLOBAL", "STACK_GLOBAL", "REDUCE", "BUILD", "OBJ", "INST",
             "NEWOBJ", "NEWOBJ_EX", "EXT1", "EXT2", "EXT4", "PERSID", "BINPERSID"}

MAX_OPS = None   # 先扫 200 万条指令快速看结果；想全量扫描改成 None（约 98 秒）

counts = collections.Counter()
danger_hits = []
t0 = time.time()
with PKL.open("rb") as f:
    for i, (op, arg, pos) in enumerate(pickletools.genops(f)):
        counts[op.name] += 1
        if op.name in DANGEROUS:
            danger_hits.append((op.name, pos))
        if MAX_OPS and i >= MAX_OPS:
            break

print(f"扫描指令数 {sum(counts.values()):,}，耗时 {time.time()-t0:.1f}s")
print(f"危险指令命中：{len(danger_hits)}")
print("\n出现过的 opcode：")
for name, n in counts.most_common():
    print(f"  {name:20s} {n:>12,}")

# %%
# ============ 第 3 格：受限反序列化 ============
# 即使静态扫描说安全，仍然把两个逃逸口堵死：不许解析类，不许持久化 id。
import pickle

class RestrictedUnpickler(pickle.Unpickler):
    def find_class(self, module, name):
        raise pickle.UnpicklingError(f"class loading blocked: {module}.{name}")
    def persistent_load(self, pid):
        raise pickle.UnpicklingError("persistent ids are blocked")

t0 = time.time()
with PKL.open("rb") as f:
    records = RestrictedUnpickler(f).load()
print(f"载入 {len(records):,} 行，耗时 {time.time()-t0:.1f}s，类型 {type(records).__name__}")

# %%
# ============ 第 4 格：看一条真实记录长什么样 ============
r = records[0]
print(f"共 {len(r)} 个字段\n")
for k, v in r.items():
    s = str(v)
    print(f"  {k:22s} = {s[:70]}{'...' if len(s) > 70 else ''}")

# %%
# ============ 第 5 格：抽样推断每列的 Python 类型 ============
# 这一步决定 parquet 的列类型。规则很保守：出现无法安全合并的混合类型就直接报错。
from collections import defaultdict
import pyarrow as pa

sample = records[::max(1, len(records) // 25_000)][:25_000]
observed, keys = defaultdict(set), set()
for rec in sample:
    keys.update(rec)
    for k, v in rec.items():
        if v is not None:
            observed[k].add(type(v))

for k in sorted(keys):
    types = observed.get(k, set())
    if not types or types <= {str}:            arrow = pa.string()
    elif types <= {bool}:                      arrow = pa.bool_()
    elif types <= {int, bool}:                 arrow = pa.int64()
    elif types <= {int, float, bool}:          arrow = pa.float64()
    else:                                      arrow = "❌ 不支持的混合类型"
    print(f"  {k:22s} python={sorted(t.__name__ for t in types)!s:24s} -> {arrow}")

# %%
# ============ 第 6 格：分片写成 parquet ============
# 每 5 万行写一片，写完立刻把源数据那一段置空并回收，内存才不会爆。
import gc
import pyarrow.parquet as pq

fields = []
for k in sorted(keys):
    types = observed.get(k, set())
    if not types or types <= {str}:      t = pa.string()
    elif types <= {bool}:                t = pa.bool_()
    elif types <= {int, bool}:           t = pa.int64()
    else:                                t = pa.float64()
    fields.append(pa.field(k, t, nullable=True))
schema = pa.schema(fields)

OUT = WORK / "data/raw_parquet"
CHUNK = 50_000
written = 0
t0 = time.time()
for part, start in enumerate(range(0, len(records), CHUNK)):
    end = min(start + CHUNK, len(records))
    chunk = records[start:end]
    table = pa.Table.from_pylist(chunk, schema=schema)
    table = table.append_column("_source_row", pa.array(range(start, end), type=pa.int64()))
    pq.write_table(table, OUT / f"part-{part:04d}.parquet",
                   compression="zstd", compression_level=5,
                   use_dictionary=True, write_statistics=True)
    written += len(chunk)
    records[start:end] = [None] * (end - start)   # ← 关键：立刻释放
    del chunk, table
    gc.collect()
    if part % 5 == 0:
        print(f"  已写 {written:,} 行")

print(f"\n完成：{written:,} 行 / {part+1} 个分片 / {time.time()-t0:.1f}s")
print("输出目录:", OUT)
