"""Load trained models and parse smart home commands."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import joblib

HOME_LOCATIONS = ["客厅", "卧室", "厨房", "卫生间", "书房", "阳台", "餐厅"]
HOME_DEVICES = ["灯", "空调", "电视", "窗帘", "风扇", "油烟机", "热水器", "排风扇"]
OPEN_WORDS = ["打开", "开启", "启动", "开"]
CLOSE_WORDS = ["关闭", "关掉", "停止", "关"]
ACTION_KEYWORDS = OPEN_WORDS + CLOSE_WORDS
DEFAULT_LOCATION_BY_DEVICE = {
    "电视": "客厅",
    "油烟机": "厨房",
    "排风扇": "卫生间",
}


@dataclass
class ParseResult:
    text: str
    is_control: bool
    confidence: float
    location: str | None = None
    device: str | None = None
    action: str | None = None


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

    @classmethod
    def _extract_action(cls, text: str) -> str | None:
        if cls._find_first(text, CLOSE_WORDS):
            return "关闭"
        if cls._find_first(text, OPEN_WORDS):
            return "打开"
        return None

    def parse(self, text: str) -> ParseResult:
        clean_text = text.strip()
        if not clean_text:
            return ParseResult(text=text, is_control=False, confidence=0.0)

        if not self._looks_like_home_command(clean_text):
            return ParseResult(text=clean_text, is_control=False, confidence=1.0)

        confidence = self._max_probability(self.binary_model, clean_text)
        location = self._find_first(clean_text, HOME_LOCATIONS)
        device = self._find_first(clean_text, HOME_DEVICES)
        action = self._extract_action(clean_text)

        if device is None:
            device = str(self.device_model.predict([clean_text])[0])
        if action is None:
            action = str(self.action_model.predict([clean_text])[0])
        if location is None:
            location = DEFAULT_LOCATION_BY_DEVICE.get(device, "未指定")

        return ParseResult(
            text=clean_text,
            is_control=True,
            confidence=confidence,
            location=location,
            device=device,
            action=action,
        )
