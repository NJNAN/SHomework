"""智能家居事件日志的批处理统计分析。

脚本读取 JSONL 事件，输出 CSV 和 Markdown 报表。它独立于主程序，便于在
Linux 环境定时运行，不影响原 GUI 或意图模型。

新手阅读提示：
1. “批处理”就是一次性读入一批历史数据，然后统计结果。
2. 这里统计的是房间控制次数、设备控制次数、动作次数、小时事件量等。
3. Counter 是 Python 自带计数工具，适合统计“每个值出现几次”。
"""

from __future__ import annotations

import argparse
import json
# Counter 用于计数，例如统计“客厅”出现了多少次。
from collections import Counter
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_DIR = Path(__file__).resolve().parent
DEFAULT_EVENTS = MODULE_DIR / "data" / "events.jsonl"
DEFAULT_OUTPUT = MODULE_DIR / "output"


def load_events(path: Path) -> list[dict]:
    """读取 JSONL 事件文件，并在行格式错误时给出具体位置。

    JSONL 文件每一行都是一个 JSON 对象，所以要逐行读取、逐行解析。
    """

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
    """把事件时间归并到小时维度，用于统计小时事件量。"""

    raw_time = str(event.get("event_time", ""))
    try:
        return datetime.fromisoformat(raw_time).strftime("%H:00")
    except ValueError:
        return "unknown"


def count_by(events: list[dict], *keys: str) -> list[dict]:
    """按一个或多个字段统计次数，并按次数从高到低返回。

    *keys 表示可以传入任意多个字段名：
    - count_by(events, "room") 按房间统计。
    - count_by(events, "room", "device") 按房间+设备组合统计。
    """

    counter: Counter[tuple[str, ...]] = Counter()
    for event in events:
        # tuple(...) 把多个统计字段组成一个 key，Counter 会自动累加次数。
        counter[tuple(str(event.get(key, "未知")) for key in keys)] += 1

    rows: list[dict] = []
    for values, count in counter.most_common():
        row = {key: value for key, value in zip(keys, values)}
        row["count"] = count
        rows.append(row)
    return rows


def count_by_hour(events: list[dict]) -> list[dict]:
    """统计每个小时的事件数量。"""

    counter = Counter(event_hour(event) for event in events)
    return [{"hour": hour, "count": count} for hour, count in sorted(counter.items())]


def write_csv(path: Path, rows: list[dict], headers: list[str]) -> None:
    """写出简单 CSV 报表。

    这里手动拼 CSV，是因为报表很简单，不必额外引入 pandas。
    """

    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [",".join(headers)]
    for row in rows:
        lines.append(",".join(str(row.get(header, "")) for header in headers))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def make_markdown_report(events: list[dict], room_rows: list[dict], device_rows: list[dict], hour_rows: list[dict]) -> str:
    """生成适合课程报告引用的 Markdown 统计摘要。

    Markdown 表格可以直接复制到报告或 README 里。
    """

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
    """执行完整批处理：读取事件、生成多张统计表和 Markdown 报告。"""

    events = load_events(events_path)
    if not events:
        raise SystemExit(f"没有找到事件数据，请先运行: python {MODULE_DIR / 'command_replay.py'}")

    # 分别从不同角度统计同一批事件。
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
    """命令行入口。"""

    parser = argparse.ArgumentParser(description="Analyze smart-home event JSONL logs.")
    parser.add_argument("--events", type=Path, default=DEFAULT_EVENTS, help="JSONL event file path.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Report output directory.")
    args = parser.parse_args()
    analyze(args.events, args.output)


if __name__ == "__main__":
    main()
