#!/usr/bin/env bash
set -euo pipefail

# 一键运行大数据侧车演示链路：回放事件、查看事件、生成报表、查看窗口统计。
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$PROJECT_ROOT"

# 如果已经通过 bootstrap_linux.sh 创建虚拟环境，则自动启用它。
if [ -d ".venv-linux-bigdata" ]; then
  source .venv-linux-bigdata/bin/activate
fi

python linux_bigdata/command_replay.py
python linux_bigdata/show_events.py --limit 5
python linux_bigdata/batch_analyze.py
python linux_bigdata/show_report.py
python linux_bigdata/stream_window.py --once

echo "Reports are in linux_bigdata/output"
