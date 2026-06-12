"""Collect smart-home state changes as append-only JSONL events.

The collector watches runtime/home_state.json and emits one event for each
device state change. It is a sidecar process: it never imports or changes the
GUI, and it never writes back to the home-state file.
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_DIR = Path(__file__).resolve().parent
DEFAULT_STATE = ROOT / "runtime" / "home_state.json"
DEFAULT_OUTPUT = MODULE_DIR / "data" / "events.jsonl"


def load_state(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def flatten_state(state: dict) -> dict[tuple[str, str], bool]:
    flat: dict[tuple[str, str], bool] = {}
    rooms = state.get("rooms", {})
    if not isinstance(rooms, dict):
        return flat

    for room, devices in rooms.items():
        if not isinstance(devices, dict):
            continue
        for device, value in devices.items():
            flat[(str(room), str(device))] = bool(value)
    return flat


def make_event(room: str, device: str, value: bool, state: dict) -> dict:
    return {
        "event_time": datetime.now().isoformat(timespec="seconds"),
        "state_updated_at": state.get("updated_at", ""),
        "room": room,
        "device": device,
        "action": "打开" if value else "关闭",
        "value": value,
        "command": state.get("last_command", ""),
        "source": "home_state",
    }


def append_events(path: Path, events: list[dict]) -> None:
    if not events:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as file:
        for event in events:
            file.write(json.dumps(event, ensure_ascii=False) + "\n")


def collect_once(state_path: Path, output_path: Path, previous: dict[tuple[str, str], bool] | None) -> dict[tuple[str, str], bool]:
    state = load_state(state_path)
    if state is None:
        return previous or {}

    current = flatten_state(state)
    if previous is None:
        return current

    events: list[dict] = []
    for key, value in current.items():
        if previous.get(key) != value:
            room, device = key
            events.append(make_event(room, device, value, state))

    append_events(output_path, events)
    if events:
        print(f"{datetime.now().isoformat(timespec='seconds')} 采集到 {len(events)} 条状态变化")
    return current


def main() -> None:
    parser = argparse.ArgumentParser(description="Watch home_state.json and append device-change events.")
    parser.add_argument("--state", type=Path, default=DEFAULT_STATE, help="runtime/home_state.json path.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Output JSONL event path.")
    parser.add_argument("--interval", type=float, default=1.0, help="Polling interval in seconds.")
    parser.add_argument("--once", action="store_true", help="Run one check and exit.")
    args = parser.parse_args()

    previous: dict[tuple[str, str], bool] | None = None
    previous = collect_once(args.state, args.output, previous)
    if args.once:
        print("已完成一次状态读取。首次读取只建立基线，不写事件。")
        return

    print(f"开始监听: {args.state}")
    print(f"事件输出: {args.output}")
    while True:
        time.sleep(max(args.interval, 0.2))
        previous = collect_once(args.state, args.output, previous)


if __name__ == "__main__":
    main()

