"""Small streaming-style window aggregation for smart-home events.

It tails the JSONL log and prints recent room/device counts. This is a light
local stand-in for a Kafka/Flink style streaming task, suitable for a course
project without adding a heavy cluster dependency.
"""

from __future__ import annotations

import argparse
import json
import time
from collections import Counter, deque
from datetime import datetime, timedelta
from pathlib import Path


MODULE_DIR = Path(__file__).resolve().parent
DEFAULT_EVENTS = MODULE_DIR / "data" / "events.jsonl"


def parse_time(value: str) -> datetime:
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return datetime.now()


def read_events(path: Path, start_offset: int = 0) -> tuple[list[dict], int]:
    if not path.exists():
        return [], start_offset

    events: list[dict] = []
    with path.open("r", encoding="utf-8") as file:
        file.seek(start_offset)
        for line in file:
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return events, file.tell()


def print_window(events: deque[dict], window_minutes: int) -> None:
    room_counter = Counter(str(event.get("room", "未知")) for event in events)
    device_counter = Counter(str(event.get("device", "未知")) for event in events)
    latest = datetime.now().isoformat(timespec="seconds")

    print(f"\n[{latest}] 最近 {window_minutes} 分钟窗口，事件数: {len(events)}")
    print("房间Top3:", ", ".join(f"{room}={count}" for room, count in room_counter.most_common(3)) or "无")
    print("设备Top3:", ", ".join(f"{device}={count}" for device, count in device_counter.most_common(3)) or "无")


def run(events_path: Path, window_minutes: int, interval: float, once: bool) -> None:
    offset = 0
    window: deque[dict] = deque()

    while True:
        new_events, offset = read_events(events_path, offset)
        now = datetime.now()
        for event in new_events:
            event["_parsed_time"] = parse_time(str(event.get("event_time", "")))
            window.append(event)

        min_time = now - timedelta(minutes=window_minutes)
        while window and window[0].get("_parsed_time", now) < min_time:
            window.popleft()

        print_window(window, window_minutes)
        if once:
            return
        time.sleep(max(interval, 1.0))


def main() -> None:
    parser = argparse.ArgumentParser(description="Stream-style window aggregation over smart-home JSONL events.")
    parser.add_argument("--events", type=Path, default=DEFAULT_EVENTS, help="JSONL event file path.")
    parser.add_argument("--window-minutes", type=int, default=30, help="Window size in minutes.")
    parser.add_argument("--interval", type=float, default=5.0, help="Refresh interval in seconds.")
    parser.add_argument("--once", action="store_true", help="Print one window and exit.")
    args = parser.parse_args()
    run(args.events, max(args.window_minutes, 1), args.interval, args.once)


if __name__ == "__main__":
    main()

