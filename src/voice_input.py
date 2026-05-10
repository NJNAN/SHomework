"""Optional speech recognition wrapper.

The GUI can run without this dependency. If SpeechRecognition is installed and a
microphone is available, it records one command and converts it to Chinese text.
"""

from __future__ import annotations


class VoiceInputError(RuntimeError):
    pass


def listen_once(timeout: int = 5, phrase_time_limit: int = 8, energy_threshold: int = 300) -> str:
    try:
        import speech_recognition as sr
    except Exception as exc:  # pragma: no cover - depends on local install
        raise VoiceInputError("缺少 SpeechRecognition 依赖，请先安装 requirements-voice.txt。") from exc

    recognizer = sr.Recognizer()
    recognizer.energy_threshold = energy_threshold
    recognizer.dynamic_energy_threshold = True
    recognizer.pause_threshold = 1.0

    try:
        with sr.Microphone() as source:
            recognizer.adjust_for_ambient_noise(source, duration=0.6)
            audio = recognizer.listen(
                source,
                timeout=timeout,
                phrase_time_limit=phrase_time_limit,
            )
    except Exception as exc:  # pragma: no cover - microphone dependent
        raise VoiceInputError(f"录音失败：{exc}") from exc

    try:
        return recognizer.recognize_google(audio, language="zh-CN")
    except Exception as exc:  # pragma: no cover - network/service dependent
        raise VoiceInputError(f"语音识别失败：{exc}") from exc
