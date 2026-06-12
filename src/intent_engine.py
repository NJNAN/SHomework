"""Load trained models and parse smart home commands."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import joblib

HOME_LOCATIONS = ["客厅", "卧室", "厨房", "卫生间", "书房", "阳台", "餐厅"]
HOME_DEVICES = ["排风扇", "油烟机", "热水器", "空调", "电视", "窗帘", "风扇", "灯"]
DEVICES_BY_LOCATION = {
    "客厅": ["灯", "空调", "电视", "窗帘", "风扇"],
    "卧室": ["灯", "空调", "窗帘", "风扇"],
    "厨房": ["灯", "油烟机", "热水器"],
    "卫生间": ["灯", "热水器", "排风扇"],
    "书房": ["灯", "空调", "窗帘", "风扇"],
    "阳台": ["灯", "窗帘"],
    "餐厅": ["灯", "空调", "风扇"],
}
DEVICE_ALIASES = {
    "床帘": "窗帘",
    "窗户帘": "窗帘",
    "排气扇": "排风扇",
    "换气扇": "排风扇",
    "电灯": "灯",
    "灯光": "灯",
}
TEXT_ALIASES = {
    "开一下": "打开",
    "开开": "打开",
    "关一下": "关闭",
    "关上": "关闭",
    "关了": "关闭",
}
OPEN_WORDS = ["打开", "开启", "启动", "开"]
CLOSE_WORDS = ["关闭", "关掉", "停止", "关"]
ACTION_KEYWORDS = OPEN_WORDS + CLOSE_WORDS
DEFAULT_LOCATION_BY_DEVICE = {
    "电视": "客厅",
    "油烟机": "厨房",
    "排风扇": "卫生间",
}
ALL_SCOPE_WORDS = ["所有", "全部", "全屋", "全家", "家里所有", "每个房间"]
CONTROL_CONFIDENCE_THRESHOLD = 0.55


@dataclass(frozen=True)
class ControlCommand:
    location: str
    device: str
    action: str


@dataclass
class ParseResult:
    text: str
    is_control: bool
    confidence: float
    location: str | None = None
    device: str | None = None
    action: str | None = None
    intent: str = "out_of_scope"
    scene: str | None = None
    normalized_text: str | None = None
    reason: str | None = None
    message: str | None = None
    commands: list[ControlCommand] = field(default_factory=list)


SCENE_COMMANDS = {
    "离家模式": [
        ControlCommand("客厅", "灯", "关闭"),
        ControlCommand("客厅", "电视", "关闭"),
        ControlCommand("客厅", "空调", "关闭"),
        ControlCommand("卧室", "空调", "关闭"),
        ControlCommand("书房", "空调", "关闭"),
        ControlCommand("餐厅", "空调", "关闭"),
    ],
    "回家模式": [
        ControlCommand("客厅", "灯", "打开"),
        ControlCommand("客厅", "空调", "打开"),
        ControlCommand("卧室", "窗帘", "打开"),
    ],
    "睡眠模式": [
        ControlCommand("客厅", "灯", "关闭"),
        ControlCommand("客厅", "电视", "关闭"),
        ControlCommand("卧室", "空调", "打开"),
        ControlCommand("卧室", "窗帘", "关闭"),
        ControlCommand("卧室", "灯", "关闭"),
    ],
    "观影模式": [
        ControlCommand("客厅", "电视", "打开"),
        ControlCommand("客厅", "窗帘", "关闭"),
        ControlCommand("客厅", "灯", "关闭"),
    ],
}

SCENE_PATTERNS = {
    "离家模式": ["我出门了", "出门了", "离家模式", "离家", "外出模式", "家里没人"],
    "回家模式": ["我回来了", "回家了", "到家了", "回家模式", "回来啦"],
    "睡眠模式": ["睡觉了", "我要睡觉", "准备睡觉", "晚安", "睡眠模式"],
    "观影模式": ["看电影", "观影模式", "电影模式", "我要看片", "开始观影"],
}


class SmartHomeIntentEngine:
    def __init__(self, model_dir: Path | None = None):
        root = Path(__file__).resolve().parents[1]
        self.model_dir = model_dir or root / "models"
        self.binary_model = joblib.load(self.model_dir / "binary_intent_model.joblib")
        self.location_model = joblib.load(self.model_dir / "location_model.joblib")
        self.device_model = joblib.load(self.model_dir / "device_model.joblib")
        self.action_model = joblib.load(self.model_dir / "action_model.joblib")

    @staticmethod
    def _max_probability(model, text: str) -> float:
        if not hasattr(model, "predict_proba"):
            return 0.0
        probabilities = model.predict_proba([text])[0]
        return float(max(probabilities))

    @staticmethod
    def _normalize_terms(text: str) -> str:
        normalized = text
        for old, new in TEXT_ALIASES.items():
            normalized = normalized.replace(old, new)
        for old, new in DEVICE_ALIASES.items():
            normalized = normalized.replace(old, new)
        for location in HOME_LOCATIONS:
            normalized = normalized.replace(f"{location}等", f"{location}灯")
        return normalized

    @staticmethod
    def _looks_like_home_command(text: str) -> bool:
        has_device = any(word in text for word in HOME_DEVICES)
        has_action = any(word in text for word in ACTION_KEYWORDS)

        # A valid home command must at least mention a controllable device and
        # an action. Location can be omitted, for example "打开灯".
        return has_device and has_action

    @staticmethod
    def _find_first(text: str, words: list[str]) -> str | None:
        for word in words:
            if word in text:
                return word
        return None

    @staticmethod
    def _find_all(text: str, words: list[str]) -> list[str]:
        return [word for word in words if word in text]

    @staticmethod
    def _find_devices(text: str) -> list[str]:
        devices: list[str] = []
        for device in HOME_DEVICES:
            if device == "风扇" and "排风扇" in text:
                continue
            if device in text:
                devices.append(device)
        return devices

    @classmethod
    def _extract_action(cls, text: str) -> str | None:
        if cls._find_first(text, CLOSE_WORDS):
            return "关闭"
        if cls._find_first(text, OPEN_WORDS):
            return "打开"
        return None

    @staticmethod
    def _has_all_scope(text: str) -> bool:
        return any(word in text for word in ALL_SCOPE_WORDS)

    @staticmethod
    def _dedupe_commands(commands: list[ControlCommand]) -> list[ControlCommand]:
        deduped: list[ControlCommand] = []
        seen: set[tuple[str, str, str]] = set()
        for command in commands:
            key = (command.location, command.device, command.action)
            if key not in seen:
                deduped.append(command)
                seen.add(key)
        return deduped

    @classmethod
    def _commands_for_device_across_home(cls, device: str, action: str) -> list[ControlCommand]:
        return [
            ControlCommand(location, device, action)
            for location in HOME_LOCATIONS
            if device in DEVICES_BY_LOCATION.get(location, [])
        ]

    @classmethod
    def _build_commands(
        cls,
        locations: list[str],
        devices: list[str],
        action: str | None,
        all_scope: bool,
    ) -> list[ControlCommand]:
        if not devices or not action:
            return []

        commands: list[ControlCommand] = []
        if all_scope:
            for device in devices:
                commands.extend(cls._commands_for_device_across_home(device, action))
            return cls._dedupe_commands(commands)

        if locations:
            for location in locations:
                for device in devices:
                    if device in DEVICES_BY_LOCATION.get(location, []):
                        commands.append(ControlCommand(location, device, action))
            return cls._dedupe_commands(commands)

        for device in devices:
            location = DEFAULT_LOCATION_BY_DEVICE.get(device)
            if location:
                commands.append(ControlCommand(location, device, action))
        return cls._dedupe_commands(commands)

    @staticmethod
    def _join_values(values: list[str]) -> str:
        return "、".join(dict.fromkeys(values))

    @classmethod
    def _message_for_commands(cls, commands: list[ControlCommand], scene: str | None = None) -> str:
        if scene:
            return f"{scene}：已生成 {len(commands)} 个设备控制动作"
        if not commands:
            return "已解析，但没有可执行的设备动作"
        if len(commands) == 1:
            command = commands[0]
            action_text = "开启" if command.action == "打开" else "关闭"
            return f"{command.location} {command.device} {action_text}"

        rooms = cls._join_values([command.location for command in commands])
        devices = cls._join_values([command.device for command in commands])
        actions = cls._join_values([command.action for command in commands])
        return f"{rooms} / {devices} / {actions}（{len(commands)} 个动作）"

    @classmethod
    def _match_scene(cls, text: str) -> tuple[str, list[ControlCommand]] | None:
        for scene, patterns in SCENE_PATTERNS.items():
            if any(pattern in text for pattern in patterns):
                return scene, SCENE_COMMANDS[scene]
        return None

    @classmethod
    def _match_environment_intent(cls, text: str) -> list[ControlCommand]:
        locations = cls._find_all(text, HOME_LOCATIONS)
        if not locations:
            return []

        commands: list[ControlCommand] = []
        for location in locations:
            if any(word in text for word in ["太热", "有点热", "很热", "闷热"]):
                if "空调" in DEVICES_BY_LOCATION.get(location, []):
                    commands.append(ControlCommand(location, "空调", "打开"))
            if any(word in text for word in ["太暗", "有点黑", "看不清"]):
                if "灯" in DEVICES_BY_LOCATION.get(location, []):
                    commands.append(ControlCommand(location, "灯", "打开"))
            if "闷" in text:
                if location == "厨房":
                    commands.append(ControlCommand("厨房", "油烟机", "打开"))
                if location == "卫生间":
                    commands.append(ControlCommand("卫生间", "排风扇", "打开"))
        return cls._dedupe_commands(commands)

    def parse(self, text: str) -> ParseResult:
        original_text = text.strip()
        clean_text = self._normalize_terms(original_text)
        if not original_text:
            return ParseResult(text=text, is_control=False, confidence=0.0, reason="空输入")

        scene_match = self._match_scene(clean_text)
        if scene_match:
            scene, commands = scene_match
            message = self._message_for_commands(commands, scene)
            return ParseResult(
                text=original_text,
                is_control=True,
                confidence=1.0,
                location=self._join_values([command.location for command in commands]),
                device=self._join_values([command.device for command in commands]),
                action="场景联动",
                intent="scene_mode",
                scene=scene,
                normalized_text=clean_text,
                message=message,
                commands=commands,
            )

        environment_commands = self._match_environment_intent(clean_text)
        if environment_commands:
            return ParseResult(
                text=original_text,
                is_control=True,
                confidence=0.9,
                location=self._join_values([command.location for command in environment_commands]),
                device=self._join_values([command.device for command in environment_commands]),
                action=self._join_values([command.action for command in environment_commands]),
                intent="environment_control",
                normalized_text=clean_text,
                message=self._message_for_commands(environment_commands),
                commands=environment_commands,
            )

        if not self._looks_like_home_command(clean_text):
            return ParseResult(
                text=original_text,
                is_control=False,
                confidence=1.0,
                intent="out_of_scope",
                normalized_text=clean_text,
                reason="该指令不属于智能家居控制范围",
            )

        confidence = self._max_probability(self.binary_model, clean_text)
        if confidence < CONTROL_CONFIDENCE_THRESHOLD:
            return ParseResult(
                text=original_text,
                is_control=False,
                confidence=confidence,
                intent="out_of_scope",
                normalized_text=clean_text,
                reason="模型置信度低于安全阈值",
            )

        locations = self._find_all(clean_text, HOME_LOCATIONS)
        devices = self._find_devices(clean_text)
        action = self._extract_action(clean_text)

        if action is None:
            action = str(self.action_model.predict([clean_text])[0])
        if not devices:
            devices = [str(self.device_model.predict([clean_text])[0])]
        if not locations and len(devices) == 1:
            default_location = DEFAULT_LOCATION_BY_DEVICE.get(devices[0])
            if default_location:
                locations = [default_location]

        all_scope = self._has_all_scope(clean_text)
        commands = self._build_commands(locations, devices, action, all_scope)
        intent = "batch_control" if all_scope or len(commands) > 1 else "device_control"
        location = self._join_values([command.location for command in commands]) if commands else (locations[0] if locations else "未指定")
        device = self._join_values([command.device for command in commands]) if commands else self._join_values(devices)
        action_value = self._join_values([command.action for command in commands]) if commands else action

        return ParseResult(
            text=original_text,
            is_control=True,
            confidence=confidence,
            location=location,
            device=device,
            action=action_value,
            intent=intent,
            normalized_text=clean_text,
            message=self._message_for_commands(commands),
            commands=commands,
        )
