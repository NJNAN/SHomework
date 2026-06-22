"""用 Windows 终端友好的表格打印智能家居事件。

新手阅读提示：
1. events.jsonl 是给程序处理的，不适合人直接看。
2. 这个脚本把前几条事件整理成对齐的表格，方便快速检查数据是否正常。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


MODULE_DIR = Path(__file__).resolve().parent
DEFAULT_EVENTS = MODULE_DIR / "data" / "events.jsonl"


def load_events(path: Path, limit: int) -> list[dict]:
    """读取前 limit 条合法 JSONL 事件。

    limit 用来控制最多显示多少条，避免终端一次刷太多内容。
    """

    events: list[dict] = []
    if not path.exists():
        return events

    with path.open("r", encoding="utf-8") as file:
        for line in file:
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
            if len(events) >= limit:
                break
    return events


def main() -> None:
    """命令行入口：快速查看事件日志内容。"""

    parser = argparse.ArgumentParser(description="Show smart-home events as a readable table.")
    parser.add_argument("--events", type=Path, default=DEFAULT_EVENTS, help="JSONL event file path.")
    parser.add_argument("--limit", type=int, default=10, help="How many events to show.")
    args = parser.parse_args()

    events = load_events(args.events, max(args.limit, 1))
    if not events:
        print("没有找到事件数据，请先运行: python linux_bigdata\\command_replay.py")
        return

    print("时间                 房间    设备      动作    来源")
    print("-" * 64)
    for event in events:
        # :<20 这类写法表示左对齐并占固定宽度，让表格看起来整齐。
        print(
            f"{event.get('event_time', ''):<20} "
            f"{event.get('room', ''):<6} "
            f"{event.get('device', ''):<8} "
            f"{event.get('action', ''):<6} "
            f"{event.get('source', '')}"
        )


if __name__ == "__main__":
    main()
