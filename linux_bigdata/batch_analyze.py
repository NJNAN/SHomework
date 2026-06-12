"""Batch analytics for smart-home event logs.

The script reads JSONL events and writes small CSV/Markdown reports. It is
kept outside the main app so analytics can run on Linux without touching the
original GUI or intent models.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_DIR = Path(__file__).resolve().parent
DEFAULT_EVENTS = MODULE_DIR / "data" / "events.jsonl"
DEFAULT_OUTPUT = MODULE_DIR / "output"


def load_events(path: Path) -> list[dict]:
    events: list[dict] = []
    if not path.exists():
        return events

    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{line_number} 不是合法 JSONL: {exc}") from exc
    return events


def event_hour(event: dict) -> str:
    raw_time = str(event.get("event_time", ""))
    try:
        return datetime.fromisoformat(raw_time).strftime("%H:00")
    except ValueError:
        return "unknown"


def count_by(events: list[dict], *keys: str) -> list[dict]:
    counter: Counter[tuple[str, ...]] = Counter()
    for event in events:
        counter[tuple(str(event.get(key, "未知")) for key in keys)] += 1

    rows: list[dict] = []
    for values, count in counter.most_common():
        row = {key: value for key, value in zip(keys, values)}
        row["count"] = count
        rows.append(row)
    return rows


def count_by_hour(events: list[dict]) -> list[dict]:
    counter = Counter(event_hour(event) for event in events)
    return [{"hour": hour, "count": count} for hour, count in sorted(counter.items())]


def write_csv(path: Path, rows: list[dict], headers: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [",".join(headers)]
    for row in rows:
        lines.append(",".join(str(row.get(header, "")) for header in headers))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def make_markdown_report(events: list[dict], room_rows: list[dict], device_rows: list[dict], hour_rows: list[dict]) -> str:
    lines = [
        "# 智能家居事件批处理分析报告",
        "",
        f"- 事件总数：{len(events)}",
        f"- 房间种类：{len({event.get('room') for event in events})}",
        f"- 设备种类：{len({event.get('device') for event in events})}",
        "",
        "## 房间控制次数 Top 5",
        "",
        "| 房间 | 次数 |",
        "| --- | ---: |",
    ]
    for row in room_rows[:5]:
        lines.append(f"| {row['room']} | {row['count']} |")

    lines.extend(["", "## 设备控制次数 Top 5", "", "| 设备 | 次数 |", "| --- | ---: |"])
    for row in device_rows[:5]:
        lines.append(f"| {row['device']} | {row['count']} |")

    lines.extend(["", "## 按小时事件量", "", "| 小时 | 次数 |", "| --- | ---: |"])
    for row in hour_rows:
        lines.append(f"| {row['hour']} | {row['count']} |")

    lines.extend(
        [
            "",
            "## 结论",
            "",
            "这个报表来自设备事件日志，适合在 Linux 服务器上定时运行。",
            "原智能家居程序负责控制，侧车模块负责数据沉淀和统计，两部分职责分开。",
        ]
    )
    return "\n".join(lines) + "\n"


def analyze(events_path: Path, output_dir: Path) -> None:
    events = load_events(events_path)
    if not events:
        raise SystemExit(f"没有找到事件数据，请先运行: python {MODULE_DIR / 'command_replay.py'}")

    room_rows = count_by(events, "room")
    device_rows = count_by(events, "device")
    room_device_rows = count_by(events, "room", "device")
    action_rows = count_by(events, "action")
    hour_rows = count_by_hour(events)

    output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(output_dir / "room_summary.csv", room_rows, ["room", "count"])
    write_csv(output_dir / "device_summary.csv", device_rows, ["device", "count"])
    write_csv(output_dir / "room_device_summary.csv", room_device_rows, ["room", "device", "count"])
    write_csv(output_dir / "action_summary.csv", action_rows, ["action", "count"])
    write_csv(output_dir / "hour_summary.csv", hour_rows, ["hour", "count"])
    (output_dir / "report.md").write_text(
        make_markdown_report(events, room_rows, device_rows, hour_rows),
        encoding="utf-8",
    )

    print(f"已分析 {len(events)} 条事件")
    print(f"报表目录: {output_dir}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze smart-home event JSONL logs.")
    parser.add_argument("--events", type=Path, default=DEFAULT_EVENTS, help="JSONL event file path.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Report output directory.")
    args = parser.parse_args()
    analyze(args.events, args.output)


if __name__ == "__main__":
    main()

