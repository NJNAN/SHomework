"""智能家居事件的轻量流式窗口统计。

脚本持续读取 JSONL 日志尾部，打印最近窗口内的房间/设备计数。它是
Kafka/Flink 流处理任务的本地简化版，适合课程项目演示。

新手阅读提示：
1. “流式”就是数据一边产生，程序一边处理，不等全部数据结束。
2. “窗口”就是只看最近一段时间的数据，例如最近 30 分钟。
3. 这个脚本没有真正启动 Kafka/Flink，只用 Python 模拟相同思想。
"""

from __future__ import annotations

import argparse
import json
import time
# Counter 负责计数，deque 是双端队列，适合不断从左边删除过期事件。
from collections import Counter, deque
from datetime import datetime, timedelta
from pathlib import Path


MODULE_DIR = Path(__file__).resolve().parent
DEFAULT_EVENTS = MODULE_DIR / "data" / "events.jsonl"


def parse_time(value: str) -> datetime:
    """解析 ISO 时间字符串，失败时使用当前时间兜底。"""

    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return datetime.now()


def read_events(path: Path, start_offset: int = 0) -> tuple[list[dict], int]:
    """从上次偏移位置继续读取新事件，实现简单 tail 效果。

    offset 是文件读取位置。
    第一次从 0 开始读，后面从上次读到的位置继续，避免重复处理旧事件。
    """

    if not path.exists():
        return [], start_offset

    events: list[dict] = []
    with path.open("r", encoding="utf-8") as file:
        # seek 跳到上次读取结束的位置。
        file.seek(start_offset)
        for line in file:
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        # tell 返回当前读取到文件的哪个位置，下次从这里继续。
        return events, file.tell()


def print_window(events: deque[dict], window_minutes: int) -> None:
    """打印当前滑动窗口内的房间 Top3 和设备 Top3。"""

    room_counter = Counter(str(event.get("room", "未知")) for event in events)
    device_counter = Counter(str(event.get("device", "未知")) for event in events)
    latest = datetime.now().isoformat(timespec="seconds")

    print(f"\n[{latest}] 最近 {window_minutes} 分钟窗口，事件数: {len(events)}")
    print("房间Top3:", ", ".join(f"{room}={count}" for room, count in room_counter.most_common(3)) or "无")
    print("设备Top3:", ", ".join(f"{device}={count}" for device, count in device_counter.most_common(3)) or "无")


def run(events_path: Path, window_minutes: int, interval: float, once: bool) -> None:
    """循环读取事件并维护最近 window_minutes 分钟的滑动窗口。

    window 里只保留最近窗口时间内的事件。
    新事件从右边 append，过期事件从左边 popleft。
    """

    offset = 0
    window: deque[dict] = deque()

    while True:
        new_events, offset = read_events(events_path, offset)
        now = datetime.now()
        for event in new_events:
            # 给事件临时加一个 _parsed_time 字段，便于比较时间。
            event["_parsed_time"] = parse_time(str(event.get("event_time", "")))
            window.append(event)

        min_time = now - timedelta(minutes=window_minutes)
        # 把窗口左侧已经过期的事件移除。
        while window and window[0].get("_parsed_time", now) < min_time:
            window.popleft()

        print_window(window, window_minutes)
        if once:
            return
        time.sleep(max(interval, 1.0))


def main() -> None:
    """命令行入口。"""

    parser = argparse.ArgumentParser(description="Stream-style window aggregation over smart-home JSONL events.")
    parser.add_argument("--events", type=Path, default=DEFAULT_EVENTS, help="JSONL event file path.")
    parser.add_argument("--window-minutes", type=int, default=30, help="Window size in minutes.")
    parser.add_argument("--interval", type=float, default=5.0, help="Refresh interval in seconds.")
    parser.add_argument("--once", action="store_true", help="Print one window and exit.")
    args = parser.parse_args()
    run(args.events, max(args.window_minutes, 1), args.interval, args.once)


if __name__ == "__main__":
    main()
