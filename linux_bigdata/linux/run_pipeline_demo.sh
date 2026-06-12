#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$PROJECT_ROOT"

if [ -d ".venv-linux-bigdata" ]; then
  source .venv-linux-bigdata/bin/activate
fi

python linux_bigdata/command_replay.py
python linux_bigdata/show_events.py --limit 5
python linux_bigdata/batch_analyze.py
python linux_bigdata/show_report.py
python linux_bigdata/stream_window.py --once

echo "Reports are in linux_bigdata/output"
