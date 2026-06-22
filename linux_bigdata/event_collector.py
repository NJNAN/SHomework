"""把智能家居状态变化采集为追加式 JSONL 事件。

采集器监听 runtime/home_state.json，每发现一个设备状态变化就写一条事件。
它是侧车进程：不导入 GUI、不修改 GUI，也不会把数据写回状态文件。

新手阅读提示：
1. JSONL 是“一行一个 JSON”的日志格式，适合不断追加事件。
2. “侧车”可以理解成主程序旁边的辅助程序，主程序负责控制设备，
   侧车只负责记录和分析数据。
3. 这个脚本通过“上一次状态”和“当前状态”对比，找出哪些设备变了。
"""

from __future__ import annotations

# argparse 用来读取命令行参数，例如 --once、--interval。
import argparse
# json 用来读取 home_state.json 和写 events.jsonl。
import json
# time.sleep 用来控制轮询间隔。
import time
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_DIR = Path(__file__).resolve().parent
# 默认读取主程序共享状态文件。
DEFAULT_STATE = ROOT / "runtime" / "home_state.json"
# 默认把事件追加到 linux_bigdata/data/events.jsonl。
DEFAULT_OUTPUT = MODULE_DIR / "data" / "events.jsonl"


def load_state(path: Path) -> dict | None:
    """读取状态文件；文件不存在或 JSON 损坏时返回 None。"""

    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def flatten_state(state: dict) -> dict[tuple[str, str], bool]:
    """把嵌套的房间状态压平成 {(房间, 设备): 开关值}，方便比较差异。

    原状态是嵌套结构：
    {"客厅": {"灯": true, "空调": false}}
    压平后变成：
    {("客厅", "灯"): true, ("客厅", "空调"): false}
    这样比较前后两次状态更简单。
    """

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
    """把一次设备状态变化转换成事件日志中的一行 JSON 对象。

    事件就是“某个时间、某个房间、某个设备发生了什么”。
    例如：2026-06-21 10:00，客厅，灯，打开。
    """

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
    """把事件追加写入 JSONL 文件，一行代表一条事件。"""

    if not events:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as file:
        for event in events:
            file.write(json.dumps(event, ensure_ascii=False) + "\n")


def collect_once(state_path: Path, output_path: Path, previous: dict[tuple[str, str], bool] | None) -> dict[tuple[str, str], bool]:
    """执行一次状态对比，返回本次状态作为下一轮基线。

    previous 是上一轮状态，current 是这一轮状态。
    如果同一个 (房间, 设备) 的布尔值不一样，就说明这个设备发生了开关变化。
    """

    state = load_state(state_path)
    if state is None:
        return previous or {}

    current = flatten_state(state)
    if previous is None:
        # 第一次运行只建立基线，不把当前全量状态误当成变化事件。
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
    """命令行入口：支持持续监听，也支持 --once 单次检查。"""

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
        # 轮询方式：每隔 interval 秒读一次状态文件。
        # 对课程项目来说足够简单，不需要引入复杂的文件监听库。
        time.sleep(max(args.interval, 0.2))
        previous = collect_once(args.state, args.output, previous)


if __name__ == "__main__":
    main()
