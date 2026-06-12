#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$PROJECT_ROOT"

python3 -m venv .venv-linux-bigdata
source .venv-linux-bigdata/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

echo "Linux big-data environment is ready."
echo "Activate it with: source .venv-linux-bigdata/bin/activate"

