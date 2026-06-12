"""Print the generated Markdown report with explicit UTF-8 decoding."""

from __future__ import annotations

import argparse
from pathlib import Path


MODULE_DIR = Path(__file__).resolve().parent
DEFAULT_REPORT = MODULE_DIR / "output" / "report.md"


def main() -> None:
    parser = argparse.ArgumentParser(description="Show the smart-home analytics report.")
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT, help="Markdown report path.")
    args = parser.parse_args()

    if not args.report.exists():
        print("没有找到报表，请先运行: python linux_bigdata\\batch_analyze.py")
        return

    print(args.report.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()

