#!/usr/bin/env bash
set -euo pipefail

# 定位到项目根目录，保证从任意位置执行脚本都能找到 requirements.txt。
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$PROJECT_ROOT"

# 为 Linux 侧车模块创建独立虚拟环境，避免污染系统 Python。
python3 -m venv .venv-linux-bigdata
source .venv-linux-bigdata/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

echo "Linux big-data environment is ready."
echo "Activate it with: source .venv-linux-bigdata/bin/activate"
