#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$PROJECT_ROOT"

if [ -d ".venv-linux-bigdata" ]; then
  source .venv-linux-bigdata/bin/activate
fi

python linux_bigdata/event_collector.py

