"""Persist smart-home device state for the desktop app.

The GUI writes runtime/home_state.json after every valid command. The same file
is read by the built-in 2D home panel and by the optional analytics sidecar.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from .intent_engine import ControlCommand, ParseResult


ROOT = Path(__file__).resolve().parents[1]
STATE_PATH = ROOT / "runtime" / "home_state.json"

ROOMS = ["客厅", "卧室", "厨房", "卫生间", "书房", "阳台", "餐厅"]

DEVICES_BY_ROOM = {
    "客厅": ["灯", "空调", "电视", "窗帘", "风扇"],
    "卧室": ["灯", "空调", "窗帘", "风扇"],
    "厨房": ["灯", "油烟机", "热水器"],
    "卫生间": ["灯", "热水器", "排风扇"],
    "书房": ["灯", "空调", "窗帘", "风扇"],
    "阳台": ["灯", "窗帘"],
    "餐厅": ["灯", "空调", "风扇"],
}


def make_default_state() -> dict:
    rooms = {}
    for room in ROOMS:
        rooms[room] = {}
        for device in DEVICES_BY_ROOM[room]:
            rooms[room][device] = False

    return {
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "last_command": "",
        "last_result": "",
        "rooms": rooms,
    }


def load_state() -> dict:
    if not STATE_PATH.exists():
        return make_default_state()

    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return make_default_state()


def save_state(state: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def ensure_state_file() -> None:
    if not STATE_PATH.exists():
        save_state(make_default_state())


def apply_parse_result(result: ParseResult) -> bool:
    """Apply parsed control commands to the shared home-state file.

    Returns True when at least one known room/device state was changed.
    """

    if not result.is_control:
        return False

    commands = list(result.commands)
    if not commands and result.location and result.device and result.action and result.location != "未指定":
        commands = [ControlCommand(result.location, result.device, result.action)]

    if not commands:
        return False

    state = load_state()
    rooms = state.setdefault("rooms", {})
    applied: list[str] = []

    for command in commands:
        room_devices = rooms.setdefault(command.location, {})

        # Only known devices are shown in the built-in home panel. Unknown
        # entries are ignored to keep the presentation view predictable.
        if command.device not in DEVICES_BY_ROOM.get(command.location, []):
            continue

        is_on = command.action == "打开"
        room_devices[command.device] = is_on
        applied.append(f"{command.location}{command.device}{'开启' if is_on else '关闭'}")

    if not applied:
        return False

    state["updated_at"] = datetime.now().isoformat(timespec="seconds")
    state["last_command"] = result.text
    if result.scene:
        state["last_result"] = f"{result.scene}：{len(applied)} 个动作"
    elif len(applied) == 1:
        state["last_result"] = applied[0]
    else:
        state["last_result"] = f"批量控制：{len(applied)} 个动作"
    save_state(state)
    return True


if __name__ == "__main__":
    save_state(make_default_state())
    print(f"已初始化家居状态文件: {STATE_PATH}")
