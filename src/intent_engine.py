"""加载训练模型并解析中文智能家居指令。

新手阅读提示：
1. 这个文件是整个项目的“理解中文指令”的核心。
2. 用户输入一句话，例如“打开客厅的灯”，程序要把它变成结构化结果：
   - 地点：客厅
   - 设备：灯
   - 动作：打开
3. 程序不是直接控制真实硬件，而是生成 ControlCommand，再交给 state_bridge.py
   去修改 runtime/home_state.json，用这个 JSON 文件模拟家里的设备状态。
4. 这里同时用了“规则”和“模型”：
   - 规则：用 if、in、列表匹配等明确逻辑处理“我出门了”“厨房太闷了”等固定表达。
   - 模型：用已经训练好的机器学习模型处理普通句子分类，例如判断是不是家居控制。
"""

from __future__ import annotations

# dataclass 可以少写很多 __init__ 样板代码，适合保存一组字段。
from dataclasses import dataclass, field
from pathlib import Path

# joblib 用来读取 .joblib 模型文件，这些文件由 src/trainer.py 训练得到。
import joblib

# 系统允许控制的房间。后续只要出现“地点/房间/位置”，基本都指这个列表里的值。
HOME_LOCATIONS = ["客厅", "卧室", "厨房", "卫生间", "书房", "阳台", "餐厅"]

# 系统允许控制的设备。注意“排风扇”放在“风扇”前面，是为了后面匹配时少出错。
HOME_DEVICES = ["排风扇", "油烟机", "热水器", "空调", "电视", "窗帘", "风扇", "灯"]

# 每个房间有哪些设备。这个表很重要：
# 例如厨房没有“空调”，所以“打开厨房空调”不会被当成有效控制动作。
DEVICES_BY_LOCATION = {
    "客厅": ["灯", "空调", "电视", "窗帘", "风扇"],
    "卧室": ["灯", "空调", "窗帘", "风扇"],
    "厨房": ["灯", "油烟机", "热水器"],
    "卫生间": ["灯", "热水器", "排风扇"],
    "书房": ["灯", "空调", "窗帘", "风扇"],
    "阳台": ["灯", "窗帘"],
    "餐厅": ["灯", "空调", "风扇"],
}
# 常见口语别名，用于把输入归一化到系统定义的标准设备名称。
# “归一化”就是把不同说法统一成同一个标准词：
# 例如用户说“排气扇”，程序内部统一当成“排风扇”处理。
DEVICE_ALIASES = {
    "床帘": "窗帘",
    "窗户帘": "窗帘",
    "排气扇": "排风扇",
    "换气扇": "排风扇",
    "电灯": "灯",
    "灯光": "灯",
}
# 动作类口语归一化，减少模型和规则需要覆盖的表达数量。
# 比如“关上客厅灯”和“关闭客厅灯”意思相同，统一后后续逻辑更简单。
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

# 没有写房间时，给某些强位置属性的设备补默认房间。
# 例如“打开电视”通常默认是客厅电视；“打开油烟机”默认是厨房油烟机。
DEFAULT_LOCATION_BY_DEVICE = {
    "电视": "客厅",
    "油烟机": "厨房",
    "排风扇": "卫生间",
}
ALL_SCOPE_WORDS = ["所有", "全部", "全屋", "全家", "家里所有", "每个房间"]

# 二分类模型的安全阈值。
# 置信度可以理解成“模型有多确定”。低于 0.55 就不执行，避免误操作。
CONTROL_CONFIDENCE_THRESHOLD = 0.55


@dataclass(frozen=True)
class ControlCommand:
    """一个最终可执行的设备控制动作。

    可以把它理解成一张很小的控制单：
    - location：去哪个房间
    - device：控制哪个设备
    - action：打开还是关闭

    例子：ControlCommand("客厅", "灯", "打开")
    表示“把客厅的灯打开”。
    """

    location: str
    device: str
    action: str


@dataclass
class ParseResult:
    """一次指令解析的完整结果，既给界面展示，也给状态同步模块执行。

    为什么不用普通字符串返回？
    因为 GUI、控制台和状态同步需要的信息不一样：
    - GUI 要显示置信度、意图类型、地点、设备、动作。
    - state_bridge.py 要拿 commands 真正更新状态文件。
    - 控制台要显示 reason 或 message 给用户看。
    所以这里把所有解析信息放进一个对象里，后面用起来更清楚。
    """

    text: str
    # is_control=True 表示这是家居控制；False 表示闲聊、软件操作、天气等非家居内容。
    is_control: bool
    # confidence 是置信度，范围通常是 0 到 1，越接近 1 表示越确定。
    confidence: float
    # location/device/action 是给界面展示的汇总字段，批量控制时可能是多个值拼在一起。
    location: str | None = None
    device: str | None = None
    action: str | None = None
    # intent 是意图类型，例如单设备控制、批量控制、场景模式、非家居控制。
    intent: str = "out_of_scope"
    # scene 只在“离家模式、睡眠模式”等场景指令里使用。
    scene: str | None = None
    # normalized_text 保存归一化后的文本，用来展示“床帘”被理解成“窗帘”等情况。
    normalized_text: str | None = None
    # reason 表示拒识原因，例如“该指令不属于智能家居控制范围”。
    reason: str | None = None
    # message 是给用户看的结果摘要，例如“客厅 灯 开启”。
    message: str | None = None
    # commands 是真正要执行的动作列表，批量控制和场景模式会有多条。
    commands: list[ControlCommand] = field(default_factory=list)


# 场景模式：一句话对应多个设备动作。
# 例如“我出门了”不是控制某一个设备，而是触发“离家模式”，一次关闭多台设备。
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

# 场景触发词列表。
# 只要用户输入里包含这些词，就可以直接判断为对应场景，不需要交给模型猜。
# 这样做更稳定，因为“晚安”这类句子没有明确写“灯/空调/关闭”，普通槽位模型不好处理。
SCENE_PATTERNS = {
    "离家模式": ["我出门了", "出门了", "离家模式", "离家", "外出模式", "家里没人"],
    "回家模式": ["我回来了", "回家了", "到家了", "回家模式", "回来啦"],
    "睡眠模式": ["睡觉了", "我要睡觉", "准备睡觉", "晚安", "睡眠模式"],
    "观影模式": ["看电影", "观影模式", "电影模式", "我要看片", "开始观影"],
}


class SmartHomeIntentEngine:
    """本地智能家居意图解析引擎。

    “引擎”这个词不用想复杂，可以理解成一个工具箱：
    给它一句中文，它返回 ParseResult。
    """

    def __init__(self, model_dir: Path | None = None):
        root = Path(__file__).resolve().parents[1]
        self.model_dir = model_dir or root / "models"
        # 四个模型分别负责：
        # 1. binary_intent_model：二分类，判断“是不是家居控制”。
        # 2. location_model：预测地点，例如客厅、卧室。
        # 3. device_model：预测设备，例如灯、空调。
        # 4. action_model：预测动作，例如打开、关闭。
        self.binary_model = joblib.load(self.model_dir / "binary_intent_model.joblib")
        self.location_model = joblib.load(self.model_dir / "location_model.joblib")
        self.device_model = joblib.load(self.model_dir / "device_model.joblib")
        self.action_model = joblib.load(self.model_dir / "action_model.joblib")

    @staticmethod
    def _max_probability(model, text: str) -> float:
        """取分类器最高概率，作为是否继续执行控制的安全依据。

        predict_proba 会返回每个类别的概率。
        例如二分类可能返回 [0.10, 0.90]，表示：
        - 不是家居控制的概率 0.10
        - 是家居控制的概率 0.90
        这里取最大值 0.90，作为模型“最有把握”的程度。
        """

        if not hasattr(model, "predict_proba"):
            return 0.0
        probabilities = model.predict_proba([text])[0]
        return float(max(probabilities))

    @staticmethod
    def _normalize_terms(text: str) -> str:
        """把口语别名和易错词统一成系统可识别的标准词。

        示例：
        - “打开卧室床帘”会变成“打开卧室窗帘”
        - “打开卫生间排气扇”会变成“打开卫生间排风扇”
        这样后面匹配设备时只需要处理标准词。
        """

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
        """先用规则粗筛，避免明显非家居指令进入模型执行链路。

        为什么要粗筛？
        用户可能输入“打开原神”“打开微信”。这些句子虽然有“打开”，
        但没有项目支持的家居设备，所以不能执行。
        """

        has_device = any(word in text for word in HOME_DEVICES)
        has_action = any(word in text for word in ACTION_KEYWORDS)

        # 合法家居控制至少要包含设备和动作，房间可以省略，例如“打开灯”。
        return has_device and has_action

    @staticmethod
    def _find_first(text: str, words: list[str]) -> str | None:
        """在文本中找第一个出现的关键词。

        words 是候选词列表，例如 ["关闭", "关掉", "停止", "关"]。
        返回值是找到的词；如果一个都没找到，就返回 None。
        """

        for word in words:
            if word in text:
                return word
        return None

    @staticmethod
    def _find_all(text: str, words: list[str]) -> list[str]:
        """找出文本中出现过的所有候选词。

        例如 text="把客厅和卧室的灯都关了"，
        words=HOME_LOCATIONS 时，返回 ["客厅", "卧室"]。
        """

        return [word for word in words if word in text]

    @staticmethod
    def _find_devices(text: str) -> list[str]:
        """从句子中找出设备名，并避免“排风扇”被误拆成“风扇”。

        这里的细节对新手很重要：
        “排风扇”这个词里面包含“风扇”，如果不特殊处理，
        程序可能同时认为用户说了“排风扇”和“风扇”两个设备。
        """

        devices: list[str] = []
        for device in HOME_DEVICES:
            if device == "风扇" and "排风扇" in text:
                continue
            if device in text:
                devices.append(device)
        return devices

    @classmethod
    def _extract_action(cls, text: str) -> str | None:
        """优先用关键词识别开关动作，识别不到再交给动作模型。

        动作只有两个标准结果：“打开”或“关闭”。
        用户说“开启、启动、开”都归为“打开”；
        用户说“关掉、停止、关”都归为“关闭”。
        """

        if cls._find_first(text, CLOSE_WORDS):
            return "关闭"
        if cls._find_first(text, OPEN_WORDS):
            return "打开"
        return None

    @staticmethod
    def _has_all_scope(text: str) -> bool:
        """判断是不是“全屋/所有/全部”这种批量控制范围。"""

        return any(word in text for word in ALL_SCOPE_WORDS)

    @staticmethod
    def _dedupe_commands(commands: list[ControlCommand]) -> list[ControlCommand]:
        """去掉重复动作，防止批量控制同一设备被执行多次。

        seen 是一个集合，用来记录已经出现过的动作。
        集合的特点是不能有重复元素，所以很适合做去重。
        """

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
        """把“全屋/所有设备”类指令展开到每个拥有该设备的房间。

        例子：
        “关闭所有空调”会变成：
        - 关闭客厅空调
        - 关闭卧室空调
        - 关闭书房空调
        - 关闭餐厅空调
        厨房没有空调，所以不会生成“关闭厨房空调”。
        """

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
        """根据地点、设备、动作和作用范围生成最终可执行动作列表。

        这一步是“从理解到执行”的关键：
        前面只是识别出了地点、设备、动作；
        这里要真正组合成一条或多条 ControlCommand。
        """

        if not devices or not action:
            return []

        commands: list[ControlCommand] = []
        if all_scope:
            # 如果是“所有灯/全屋空调”，就把设备扩展到所有包含该设备的房间。
            for device in devices:
                commands.extend(cls._commands_for_device_across_home(device, action))
            return cls._dedupe_commands(commands)

        if locations:
            # 如果用户明确说了房间，就只在这些房间里生成动作。
            for location in locations:
                for device in devices:
                    # 房间里必须真实存在这个设备，才会生成控制动作。
                    if device in DEVICES_BY_LOCATION.get(location, []):
                        commands.append(ControlCommand(location, device, action))
            return cls._dedupe_commands(commands)

        for device in devices:
            # 如果没有房间，只能给少数有默认房间的设备补位置。
            location = DEFAULT_LOCATION_BY_DEVICE.get(device)
            if location:
                commands.append(ControlCommand(location, device, action))
        return cls._dedupe_commands(commands)

    @staticmethod
    def _join_values(values: list[str]) -> str:
        """把多个值去重后用顿号拼起来，主要用于界面显示。"""

        return "、".join(dict.fromkeys(values))

    @classmethod
    def _message_for_commands(cls, commands: list[ControlCommand], scene: str | None = None) -> str:
        """生成给 GUI/控制台展示的自然语言摘要。"""

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
        """匹配离家、回家、睡眠、观影等场景级指令。

        返回值是二元组：(场景名称, 这个场景对应的动作列表)。
        如果没有匹配到任何场景，就返回 None。
        """

        for scene, patterns in SCENE_PATTERNS.items():
            if any(pattern in text for pattern in patterns):
                return scene, SCENE_COMMANDS[scene]
        return None

    @classmethod
    def _match_environment_intent(cls, text: str) -> list[ControlCommand]:
        """把“太热、太暗、太闷”等环境描述推理成设备动作。

        这叫“环境语义控制”：用户没有直接说“打开空调”，
        但他说“卧室太热了”，系统可以推理出“打开卧室空调”。
        """

        locations = cls._find_all(text, HOME_LOCATIONS)
        if not locations:
            return []

        commands: list[ControlCommand] = []
        for location in locations:
            if any(word in text for word in ["太热", "有点热", "很热", "闷热"]):
                # 热通常需要打开空调，但前提是这个房间有空调。
                if "空调" in DEVICES_BY_LOCATION.get(location, []):
                    commands.append(ControlCommand(location, "空调", "打开"))
            if any(word in text for word in ["太暗", "有点黑", "看不清"]):
                # 暗通常需要开灯。
                if "灯" in DEVICES_BY_LOCATION.get(location, []):
                    commands.append(ControlCommand(location, "灯", "打开"))
            if "闷" in text:
                # 厨房闷优先开油烟机，卫生间闷优先开排风扇。
                if location == "厨房":
                    commands.append(ControlCommand("厨房", "油烟机", "打开"))
                if location == "卫生间":
                    commands.append(ControlCommand("卫生间", "排风扇", "打开"))
        return cls._dedupe_commands(commands)

    def parse(self, text: str) -> ParseResult:
        """解析一条中文指令，返回是否可控制、槽位、置信度和动作列表。

        你可以按下面顺序读这个函数：
        1. 清理输入并做口语归一化。
        2. 先判断场景模式，比如“我出门了”。
        3. 再判断环境语义，比如“厨房太闷了”。
        4. 再过滤明显不是家居控制的句子。
        5. 用二分类模型检查置信度。
        6. 抽取地点、设备、动作。
        7. 生成最终可执行 commands。
        """

        original_text = text.strip()
        clean_text = self._normalize_terms(original_text)
        if not original_text:
            return ParseResult(text=text, is_control=False, confidence=0.0, reason="空输入")

        # 场景和环境语义优先走规则，因为它们往往对应多设备联动，不是普通单槽位预测。
        scene_match = self._match_scene(clean_text)
        if scene_match:
            scene, commands = scene_match
            message = self._message_for_commands(commands, scene)
            # 场景模式不需要模型预测槽位，直接返回预先配置好的多条动作。
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
            # 环境语义规则能推理出动作时，也直接返回，不再走普通槽位模型。
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

        # 明显不像家居控制的句子直接拒识，降低“打开游戏”等误触发风险。
        if not self._looks_like_home_command(clean_text):
            return ParseResult(
                text=original_text,
                is_control=False,
                confidence=1.0,
                intent="out_of_scope",
                normalized_text=clean_text,
                reason="该指令不属于智能家居控制范围",
            )

        # 二分类模型作为第二道安全阈值，置信度太低时不执行任何设备动作。
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

        # 规则能直接抽到的槽位优先使用，缺失项再由训练好的槽位模型补齐。
        locations = self._find_all(clean_text, HOME_LOCATIONS)
        devices = self._find_devices(clean_text)
        action = self._extract_action(clean_text)

        if action is None:
            # 规则没找到动作时，才用模型预测动作。
            action = str(self.action_model.predict([clean_text])[0])
        if not devices:
            # 规则没找到设备时，才用模型预测设备。
            devices = [str(self.device_model.predict([clean_text])[0])]
        if not locations and len(devices) == 1:
            # 没有地点时，尝试给电视、油烟机、排风扇这类设备补默认地点。
            default_location = DEFAULT_LOCATION_BY_DEVICE.get(devices[0])
            if default_location:
                locations = [default_location]

        all_scope = self._has_all_scope(clean_text)
        commands = self._build_commands(locations, devices, action, all_scope)
        # intent 是给界面看的意图标签：批量动作多于 1 条时，显示为批量控制。
        intent = "batch_control" if all_scope or len(commands) > 1 else "device_control"

        # 下面三个变量是给界面展示用的汇总字段；
        # 真正执行状态修改时，state_bridge.py 主要看 commands 列表。
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
