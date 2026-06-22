"""用 UTF-8 显式读取并打印已生成的 Markdown 报告。

新手阅读提示：
1. batch_analyze.py 负责生成报告。
2. show_report.py 只负责把报告内容打印出来，方便在终端查看。
"""

from __future__ import annotations

import argparse
from pathlib import Path


MODULE_DIR = Path(__file__).resolve().parent
DEFAULT_REPORT = MODULE_DIR / "output" / "report.md"


def main() -> None:
    """命令行入口：查看 batch_analyze.py 生成的报告。"""

    parser = argparse.ArgumentParser(description="Show the smart-home analytics report.")
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT, help="Markdown report path.")
    args = parser.parse_args()

    if not args.report.exists():
        print("没有找到报表，请先运行: python linux_bigdata\\batch_analyze.py")
        return

    # Windows 下中文文件建议明确使用 encoding="utf-8" 读取。
    print(args.report.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
