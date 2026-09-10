#!/usr/bin/env bash
# 一键建立分析环境。用法：bash 建立环境.sh
set -e
cd "$(dirname "$0")"

echo "▸ 检查 Python 3.13 ..."
if ! command -v python3.13 >/dev/null 2>&1; then
  echo "✗ 没找到 python3.13。请先到 https://www.python.org/downloads/ 安装 Python 3.13.x"
  exit 1
fi
python3.13 --version

echo "▸ 建立虚拟环境 .venv ..."
[ -d .venv ] && { echo "  .venv 已存在，跳过"; } || python3.13 -m venv .venv

echo "▸ 安装依赖（约 2 分钟）..."
./.venv/bin/pip install -q --upgrade pip
./.venv/bin/pip install -q -r requirements-lock.txt

echo "▸ 注册 Jupyter 内核 ..."
./.venv/bin/python -m ipykernel install --user --name kiva-venv --display-name "Kiva 竞赛 (.venv)" >/dev/null

echo "▸ 验证 ..."
./.venv/bin/python -c "import duckdb,pandas,pyfixest,statsmodels; print(f'  duckdb {duckdb.__version__} | pandas {pandas.__version__} | pyfixest {pyfixest.__version__}')"

echo ""
echo "✓ 完成。接下来："
echo "  1. 把 Kiva_Loans.pkl 放进 1_题目与数据/"
echo "  2. VS Code 打开 3_分析步骤/00_安全审计pickle.ipynb"
echo "  3. 右上角选内核 → Kiva 竞赛 (.venv)"
