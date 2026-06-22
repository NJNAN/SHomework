#!/usr/bin/env bash
set -euo pipefail

# 持续监听 runtime/home_state.json，把状态变化追加到 JSONL 事件日志。
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$PROJECT_ROOT"

# 有专用虚拟环境时优先使用，方便 Linux 服务器部署。
if [ -d ".venv-linux-bigdata" ]; then
  source .venv-linux-bigdata/bin/activate
fi

python linux_bigdata/event_collector.py
