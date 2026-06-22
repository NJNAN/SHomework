"""为桌面端持久化智能家居设备状态。

GUI、命令行控制台、HTML 看板和 Linux 数据侧车共用 runtime/home_state.json。
这个模块只负责读写状态文件，不负责判断自然语言指令。

新手阅读提示：
1. 这个项目没有连接真实电灯、空调、电视。
2. 所谓“执行控制”，其实是把设备开关状态写进 runtime/home_state.json。
3. GUI 看板、HTML 看板和大数据侧车再读取这个 JSON 文件，显示或分析设备状态。
"""

from __future__ import annotations

# json 用来读写 runtime/home_state.json。
import json
from datetime import datetime
from pathlib import Path

from .intent_engine import ControlCommand, ParseResult


ROOT = Path(__file__).resolve().parents[1]
# 共享状态文件的位置。项目里所有“当前家居状态”都以这个文件为准。
STATE_PATH = ROOT / "runtime" / "home_state.json"

# 状态文件中的房间和设备清单需要与 intent_engine.py 保持一致。
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
    """生成一份所有设备默认关闭的初始状态。

    返回的数据结构大概长这样：
    {
      "updated_at": "更新时间",
      "last_command": "最近一次用户输入",
      "last_result": "最近一次执行结果",
      "rooms": {
        "客厅": {"灯": false, "空调": false}
      }
    }
    false 表示关闭，true 表示开启。
    """

    rooms = {}
    for room in ROOMS:
        rooms[room] = {}
        for device in DEVICES_BY_ROOM[room]:
            # 初始状态下所有设备都关闭。
            rooms[room][device] = False

    return {
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "last_command": "",
        "last_result": "",
        "rooms": rooms,
    }


def load_state() -> dict:
    """读取当前家居状态；文件不存在或损坏时回退到默认状态。

    “回退到默认状态”是为了让程序更稳：
    如果 JSON 文件被误删或写坏，GUI 仍然可以启动。
    """

    if not STATE_PATH.exists():
        return make_default_state()

    try:
        # read_text 读出 JSON 字符串，json.loads 把字符串转成 Python 字典。
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return make_default_state()


def save_state(state: dict) -> None:
    """把状态写回 JSON 文件，供 GUI、HTML 页面和侧车模块读取。"""

    # parents=True 表示 runtime/ 不存在时自动创建。
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    # ensure_ascii=False 保证中文正常显示；indent=2 让 JSON 文件更好读。
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def ensure_state_file() -> None:
    """确保 runtime/home_state.json 存在。"""

    if not STATE_PATH.exists():
        save_state(make_default_state())


def apply_parse_result(result: ParseResult) -> bool:
    """把解析结果中的控制动作应用到共享家居状态文件。

    返回 True 表示至少有一个已知房间/设备状态被成功修改。
    """

    # 如果解析结果明确说“不是家居控制”，这里直接不执行。
    if not result.is_control:
        return False

    # 新版解析结果会携带 commands；保留单槽位回退逻辑，兼容旧调用方式。
    commands = list(result.commands)
    if not commands and result.location and result.device and result.action and result.location != "未指定":
        # 旧版逻辑可能只有 location/device/action，没有 commands 列表；
        # 这里把它包装成一条 ControlCommand，保持兼容。
        commands = [ControlCommand(result.location, result.device, result.action)]

    if not commands:
        # 没有可执行动作，就不改状态文件。
        return False

    state = load_state()
    # setdefault 的意思是：如果 state 里没有 rooms，就创建一个空字典。
    rooms = state.setdefault("rooms", {})
    applied: list[str] = []

    for command in commands:
        # 找到对应房间的设备状态字典；如果房间不存在，就先创建空字典。
        room_devices = rooms.setdefault(command.location, {})

        # 内置看板只展示预定义设备，未知设备忽略，避免状态文件被写入脏数据。
        if command.device not in DEVICES_BY_ROOM.get(command.location, []):
            continue

        is_on = command.action == "打开"
        # 真正修改状态：打开写 True，关闭写 False。
        room_devices[command.device] = is_on
        applied.append(f"{command.location}{command.device}{'开启' if is_on else '关闭'}")

    if not applied:
        # commands 存在但都不是已知设备时，也不保存文件。
        return False

    # 更新元信息，方便看板显示“最近一次操作”。
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
