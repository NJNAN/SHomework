"""可选的 API 大模型语义帧解析器。

主程序默认使用本地规则和传统机器学习模型；本模块用于接入 DeepSeek 或其他
OpenAI-compatible Chat Completions 接口，处理更复杂的口语表达。

新手阅读提示：
1. “API”可以理解成向网上的模型服务发送请求。
2. “语义帧”就是把一句自然语言整理成固定格式的数据。
   例如“打开客厅灯”整理成：
   {"location": "客厅", "device": "灯", "action": "打开"}
3. 大模型可能会返回格式不对、设备不存在、动作写错等内容，
   所以本文件不仅请求模型，还负责校验模型输出。
"""

from __future__ import annotations

# json 用来把请求体转成 JSON 字符串，也用来解析模型返回的 JSON。
import json
# os 用来读取环境变量，例如 DEEPSEEK_API_KEY。
import os
# re 是正则表达式库，用来从模型输出中提取 JSON。
import re
# urllib 是 Python 标准库里的 HTTP 请求工具，这里不用额外安装 requests。
import urllib.error
import urllib.request
from dataclasses import dataclass

from .intent_engine import (
    DEVICES_BY_LOCATION,
    ControlCommand,
    ParseResult,
    SmartHomeIntentEngine,
)


DEFAULT_MODEL = "deepseek-v4-flash"
DEFAULT_API_URL = "https://api.deepseek.com/chat/completions"


class ApiLLMError(RuntimeError):
    """API 模型解析相关错误。

    统一用这个异常，可以让 GUI 和控制台用同一种方式提示错误。
    """

    pass


@dataclass
class ApiLLMConfig:
    """API 模型配置，优先从环境变量读取，方便命令行和 GUI 共用。

    环境变量就是系统里保存的一些配置值，例如 API Key。
    这样密钥不用写死在代码里，避免泄露。
    """

    # DEEPSEEK_API_KEY 是默认密钥名；SMART_HOME_API_KEY 是项目自定义备用名。
    api_key: str = os.getenv("DEEPSEEK_API_KEY") or os.getenv("SMART_HOME_API_KEY", "")
    # 可以通过环境变量切换模型，不需要改代码。
    model: str = os.getenv("SMART_HOME_API_MODEL") or os.getenv("DEEPSEEK_MODEL", DEFAULT_MODEL)
    url: str = os.getenv("SMART_HOME_API_URL", DEFAULT_API_URL)
    # 超时时间，单位是秒。网络太慢时不要让程序一直等。
    timeout: int = int(os.getenv("SMART_HOME_API_TIMEOUT", "30"))


class ApiLLMParser:
    """把 API 模型返回的 JSON 语义帧转换为项目内部 ParseResult。

    注意：这个类最终也返回 ParseResult，和本地 intent_engine.py 保持一致。
    因此 GUI 不需要关心结果来自本地模型还是 API 模型。
    """

    def __init__(self, config: ApiLLMConfig | None = None):
        self.config = config or ApiLLMConfig()

    def parse(self, text: str, fallback_engine: SmartHomeIntentEngine | None = None) -> ParseResult:
        """调用 API 解析文本；API 输出无效时可回退到本地解析引擎。

        fallback_engine 是“兜底方案”：
        如果大模型返回的结果不能执行，就再试一次本地解析器。
        """

        clean_text = text.strip()
        if not clean_text:
            return ParseResult(text=text, is_control=False, confidence=0.0, reason="空输入", intent="out_of_scope")

        # 1. 请求 API，拿到模型返回的文本。
        payload = self._request_chat_completion(clean_text)
        # 2. 从模型文本中解析出 JSON 字典。
        frame = self._decode_frame(payload)
        # 3. 把 JSON 字典转成项目统一使用的 ParseResult。
        result = self._frame_to_result(clean_text, frame)
        if result.is_control and result.commands:
            return result
        if fallback_engine is not None:
            # 大模型没有给出有效动作时，不直接失败，而是交给本地引擎兜底。
            fallback = fallback_engine.parse(clean_text)
            fallback.reason = result.reason or fallback.reason
            return fallback
        return result

    def _request_chat_completion(self, text: str) -> str:
        """发送 Chat Completions 请求，并返回模型消息内容。

        Chat Completions 是 OpenAI/DeepSeek 这类聊天模型常用的接口形式：
        发送 messages 列表，模型返回 choices。
        """

        if not self.config.api_key:
            raise ApiLLMError("缺少 API Key，请先设置 DEEPSEEK_API_KEY。")

        # request_body 是要发给模型服务的 JSON 请求体。
        request_body = {
            "model": self.config.model,
            "stream": False,
            # 要求模型返回 JSON 对象，这样后续更容易解析。
            "response_format": {"type": "json_object"},
            "messages": [
                # system 是系统提示词，负责约束模型应该怎么回答。
                {"role": "system", "content": self._system_prompt()},
                # user 是用户真正输入的指令。
                {"role": "user", "content": text},
            ],
            # temperature 越低，模型输出越稳定。
            "temperature": 0.1,
            "max_tokens": 512,
        }
        # HTTP 请求发送的是字节，所以要先把 JSON 字符串 encode 成 utf-8。
        data = json.dumps(request_body, ensure_ascii=False).encode("utf-8")
        # 使用标准库 urllib，减少课程项目额外依赖。
        request = urllib.request.Request(
            self.config.url,
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.config.api_key}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.config.timeout) as response:
                # 读取接口响应，并从 JSON 字符串转成 Python 字典。
                response_data = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            raise ApiLLMError(f"API 请求失败：HTTP {exc.code} {error_body[:200]}") from exc
        except urllib.error.URLError as exc:
            raise ApiLLMError("API 服务连接失败，请检查网络或接口地址。") from exc
        except TimeoutError as exc:
            raise ApiLLMError("API 响应超时。") from exc
        except json.JSONDecodeError as exc:
            raise ApiLLMError("API 返回了无法解析的响应。") from exc

        # Chat Completions 的标准返回结构通常是 choices[0].message.content。
        choices = response_data.get("choices")
        if not isinstance(choices, list) or not choices:
            raise ApiLLMError("API 响应缺少 choices。")
        message = choices[0].get("message", {})
        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            raise ApiLLMError("API 没有返回有效内容。")
        return content

    @staticmethod
    def _system_prompt() -> str:
        """限制模型只能输出项目允许的房间、设备和 JSON 字段。

        这段提示词越明确，模型越不容易输出多余解释或不存在的设备。
        """

        return """你是中文智能家居语义解析器。只输出一个 JSON 对象，不要输出解释。
允许房间和设备：
客厅: 灯, 空调, 电视, 窗帘, 风扇
卧室: 灯, 空调, 窗帘, 风扇
厨房: 灯, 油烟机, 热水器
卫生间: 灯, 热水器, 排风扇
书房: 灯, 空调, 窗帘, 风扇
阳台: 灯, 窗帘
餐厅: 灯, 空调, 风扇

输出格式：
{
  "is_control": true,
  "intent": "device_control",
  "scene": null,
  "commands": [
    {"location": "客厅", "device": "灯", "action": "打开"}
  ],
  "reason": ""
}

规则：
1. action 只能是 "打开" 或 "关闭"。
2. location/device 必须来自允许列表，不要创造新房间或新设备。
3. 不属于智能家居控制时，is_control=false，intent="out_of_scope"，commands=[]。
4. "睡觉了/出门了/回家了/看电影" 可以转成多个设备动作。
5. "太热/太暗/太闷" 可以转成合理设备动作。
6. 只输出 JSON，不要 markdown。"""

    @staticmethod
    def _decode_frame(content: str) -> dict:
        """从模型文本中提取 JSON 语义帧，并兼容少量多余输出。

        理想情况下模型直接返回 JSON。
        但有些模型可能会多输出解释文字，所以这里用正则再尝试截取 {...}。
        """

        # 某些模型可能输出 <think>...</think> 推理内容，这里先删除。
        content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
        try:
            # 第一优先：把整段内容当作 JSON 解析。
            return json.loads(content)
        except json.JSONDecodeError:
            # 第二优先：如果整段不是 JSON，就从里面找第一个大括号对象。
            match = re.search(r"\{.*\}", content, flags=re.DOTALL)
            if not match:
                raise ApiLLMError("API 模型没有按 JSON 格式返回语义帧。")
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError as exc:
                raise ApiLLMError("API 模型返回的 JSON 语义帧无效。") from exc

    @classmethod
    def _frame_to_result(cls, text: str, frame: dict) -> ParseResult:
        """把 API 返回的语义帧转换成 GUI 和状态模块可用的解析结果。

        frame 是模型返回的字典，ParseResult 是项目内部统一格式。
        """

        is_control = bool(frame.get("is_control"))
        intent = str(frame.get("intent") or ("device_control" if is_control else "out_of_scope"))
        reason = str(frame.get("reason") or "")
        if not is_control:
            return ParseResult(
                text=text,
                is_control=False,
                confidence=0.75,
                intent="out_of_scope",
                reason=reason or "API 模型判断为非家居控制",
            )

        # 大模型给出的 commands 不能直接信任，必须先校验。
        commands = cls._validated_commands(frame.get("commands"))
        if not commands:
            return ParseResult(
                text=text,
                is_control=False,
                confidence=0.45,
                intent="out_of_scope",
                reason=reason or "API 模型没有生成有效设备动作",
            )

        scene = frame.get("scene")
        if scene is not None:
            scene = str(scene)
        location = cls._join_values([command.location for command in commands])
        device = cls._join_values([command.device for command in commands])
        action = cls._join_values([command.action for command in commands])
        return ParseResult(
            text=text,
            is_control=True,
            confidence=0.85,
            location=location,
            device=device,
            action=action,
            intent=intent,
            scene=scene,
            normalized_text=text,
            message=cls._message_for_commands(commands, scene),
            commands=commands,
        )

    @staticmethod
    def _validated_commands(raw_commands: object) -> list[ControlCommand]:
        """校验模型生成的动作，只保留项目中真实存在的房间和设备。

        这是安全检查：
        - action 必须是“打开”或“关闭”。
        - device 必须真的属于 location。
        - 重复动作只保留一条。
        """

        if not isinstance(raw_commands, list):
            return []

        commands: list[ControlCommand] = []
        seen: set[tuple[str, str, str]] = set()
        for item in raw_commands:
            # 每个动作必须是字典，例如 {"location": "客厅", "device": "灯", "action": "打开"}。
            if not isinstance(item, dict):
                continue
            location = str(item.get("location") or "").strip()
            device = str(item.get("device") or "").strip()
            action = str(item.get("action") or "").strip()
            # 把模型常见同义动作归一化到“打开/关闭”。
            if action in {"开启", "启动", "开"}:
                action = "打开"
            if action in {"关掉", "关上", "停止", "关"}:
                action = "关闭"
            if action not in {"打开", "关闭"}:
                continue
            # 如果模型编造了不存在的组合，例如“厨房空调”，这里会丢弃。
            if device not in DEVICES_BY_LOCATION.get(location, []):
                continue
            key = (location, device, action)
            if key in seen:
                continue
            commands.append(ControlCommand(location, device, action))
            seen.add(key)
        return commands

    @staticmethod
    def _join_values(values: list[str]) -> str:
        """去重后用顿号拼接多个房间、设备或动作。"""

        return "、".join(dict.fromkeys(values))

    @classmethod
    def _message_for_commands(cls, commands: list[ControlCommand], scene: str | None = None) -> str:
        """生成 API 解析结果的展示摘要。"""

        if scene:
            return f"{scene}：API 模型生成 {len(commands)} 个动作"
        if len(commands) == 1:
            command = commands[0]
            action_text = "开启" if command.action == "打开" else "关闭"
            return f"{command.location} {command.device} {action_text}"
        rooms = cls._join_values([command.location for command in commands])
        devices = cls._join_values([command.device for command in commands])
        actions = cls._join_values([command.action for command in commands])
        return f"{rooms} / {devices} / {actions}（API 模型 {len(commands)} 个动作）"
