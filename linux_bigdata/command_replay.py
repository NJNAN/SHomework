"""Generate realistic demo events from smart-home commands.

This script is for big-data demonstration only. It parses sample commands with
the existing intent engine, but it writes a separate JSONL event log and does
not change the original GUI, models, or home-state file.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_DIR = Path(__file__).resolve().parent
DEFAULT_OUTPUT = MODULE_DIR / "data" / "events.jsonl"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.intent_engine import SmartHomeIntentEngine  # noqa: E402


SAMPLE_COMMANDS = [
    "打开客厅的灯",
    "打开客厅空调",
    "关闭客厅的灯",
    "打开卧室灯",
    "打开卧室窗帘",
    "关闭卧室空调",
    "打开厨房油烟机",
    "打开厨房灯",
    "关闭厨房油烟机",
    "打开卫生间排气扇",
    "关闭卫生间灯",
    "打开书房灯",
    "打开书房窗帘",
    "关闭书房风扇",
    "打开阳台灯",
    "关闭阳台窗帘",
    "打开餐厅灯",
    "关闭餐厅空调",
]


def result_to_event(result, event_time: datetime, source: str) -> dict | None:
    if not result.is_control:
        return None
    if not result.location or not result.device or not result.action:
        return None
    if result.location == "未指定":
        return None

    return {
        "event_time": event_time.isoformat(timespec="seconds"),
        "room": result.location,
        "device": result.device,
        "action": result.action,
        "value": result.action == "打开",
        "command": result.text,
        "confidence": round(result.confidence, 4),
        "source": source,
    }


def generate_events(repeat: int) -> list[dict]:
    engine = SmartHomeIntentEngine(ROOT / "models")
    start_time = datetime.now().replace(minute=0, second=0, microsecond=0)
    events: list[dict] = []

    for batch in range(repeat):
        for index, command in enumerate(SAMPLE_COMMANDS):
            result = engine.parse(command)
            event_time = start_time + timedelta(minutes=batch * len(SAMPLE_COMMANDS) + index)
            event = result_to_event(result, event_time, "command_replay")
            if event is not None:
                events.append(event)
    return events


def write_events(path: Path, events: list[dict], append: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = "a" if append else "w"
    with path.open(mode, encoding="utf-8") as file:
        for event in events:
            file.write(json.dumps(event, ensure_ascii=False) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Replay smart-home commands into a JSONL event log.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Output JSONL path.")
    parser.add_argument("--repeat", type=int, default=3, help="How many times to replay sample commands.")
    parser.add_argument("--append", action="store_true", help="Append instead of overwriting.")
    args = parser.parse_args()

    events = generate_events(max(args.repeat, 1))
    write_events(args.output, events, args.append)
    print(f"已生成 {len(events)} 条演示事件: {args.output}")


if __name__ == "__main__":
    main()
