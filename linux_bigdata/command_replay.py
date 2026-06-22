"""根据智能家居指令生成演示事件。

这个脚本只用于大数据展示：它复用现有意图引擎解析样例指令，但把结果写入独立
JSONL 事件日志，不会修改 GUI、模型文件或 runtime/home_state.json。

新手阅读提示：
1. 如果没有真实用户一直操作 GUI，就没有足够事件给大数据模块分析。
2. 这个脚本通过“回放样例指令”生成演示数据，方便课堂展示。
3. 它调用 intent_engine.py 解析指令，但不会调用 state_bridge.py，所以不会改当前家居状态。
"""

from __future__ import annotations

# argparse 读取 --repeat、--append 等命令行参数。
import argparse
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_DIR = Path(__file__).resolve().parent
DEFAULT_OUTPUT = MODULE_DIR / "data" / "events.jsonl"

if str(ROOT) not in sys.path:
    # 让脚本无论从哪里运行，都能 import src.intent_engine。
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
    """把单条解析结果转换为事件；不可执行指令返回 None。

    result 是意图解析结果，event 是大数据日志里需要的一行记录。
    """

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
        # value 是布尔值，True 表示开启，False 表示关闭。
        "value": result.action == "打开",
        "command": result.text,
        "confidence": round(result.confidence, 4),
        "source": source,
    }


def generate_events(repeat: int) -> list[dict]:
    """按时间顺序重复回放样例指令，生成演示事件列表。

    repeat 表示把 SAMPLE_COMMANDS 重复几轮。
    每条事件时间相差 1 分钟，方便后续按小时统计。
    """

    engine = SmartHomeIntentEngine(ROOT / "models")
    start_time = datetime.now().replace(minute=0, second=0, microsecond=0)
    events: list[dict] = []

    for batch in range(repeat):
        for index, command in enumerate(SAMPLE_COMMANDS):
            # 复用主程序解析引擎，保证演示事件和真实解析逻辑一致。
            result = engine.parse(command)
            event_time = start_time + timedelta(minutes=batch * len(SAMPLE_COMMANDS) + index)
            event = result_to_event(result, event_time, "command_replay")
            if event is not None:
                events.append(event)
    return events


def write_events(path: Path, events: list[dict], append: bool) -> None:
    """写出 JSONL 事件文件，可选择覆盖或追加。

    append=False 时覆盖旧文件；append=True 时接着旧文件往后写。
    """

    path.parent.mkdir(parents=True, exist_ok=True)
    mode = "a" if append else "w"
    with path.open(mode, encoding="utf-8") as file:
        for event in events:
            file.write(json.dumps(event, ensure_ascii=False) + "\n")


def main() -> None:
    """命令行入口：生成或追加演示事件数据。"""

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
