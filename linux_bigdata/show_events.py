"""Print smart-home events in a Windows-friendly table."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


MODULE_DIR = Path(__file__).resolve().parent
DEFAULT_EVENTS = MODULE_DIR / "data" / "events.jsonl"


def load_events(path: Path, limit: int) -> list[dict]:
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
        print(
            f"{event.get('event_time', ''):<20} "
            f"{event.get('room', ''):<6} "
            f"{event.get('device', ''):<8} "
            f"{event.get('action', ''):<6} "
            f"{event.get('source', '')}"
        )


if __name__ == "__main__":
    main()

