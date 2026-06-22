"""可选语音识别封装。

GUI 不依赖这个模块也能运行；只有安装 SpeechRecognition 并且麦克风可用时，
才会录制一句指令并转换成中文文本。

新手阅读提示：
1. 这个模块是可选功能，不安装语音依赖也不影响文本输入。
2. SpeechRecognition 是第三方库，负责调用麦克风和语音识别服务。
3. 识别出来的文本会回到 app.py，再走普通文本解析流程。
"""

from __future__ import annotations


class VoiceInputError(RuntimeError):
    """语音录制或识别失败时抛出的统一异常。"""

    pass


def listen_once(timeout: int = 5, phrase_time_limit: int = 8, energy_threshold: int = 300) -> str:
    """录制一次麦克风输入，并调用 Google 中文语音识别。

    参数说明：
    - timeout：等待用户开始说话的最长秒数。
    - phrase_time_limit：一次最多录几秒。
    - energy_threshold：声音能量阈值，越高越不容易把环境噪声当成人声。
    """

    try:
        # 这里放在函数内部导入，是为了没有安装语音依赖时，主程序仍可启动。
        import speech_recognition as sr
    except Exception as exc:  # pragma: no cover - depends on local install
        raise VoiceInputError("缺少 SpeechRecognition 依赖，请先安装 requirements-voice.txt。") from exc

    recognizer = sr.Recognizer()
    # 动态能量阈值可以适应宿舍、教室等不同背景噪声。
    recognizer.energy_threshold = energy_threshold
    recognizer.dynamic_energy_threshold = True
    recognizer.pause_threshold = 1.0

    try:
        with sr.Microphone() as source:
            # 先听一小段环境声音，用于自动估计背景噪声。
            recognizer.adjust_for_ambient_noise(source, duration=0.6)
            # listen 会阻塞等待用户说话，所以 app.py 中要放到后台线程运行。
            audio = recognizer.listen(
                source,
                timeout=timeout,
                phrase_time_limit=phrase_time_limit,
            )
    except Exception as exc:  # pragma: no cover - microphone dependent
        raise VoiceInputError(f"录音失败：{exc}") from exc

    try:
        # language="zh-CN" 表示识别中文普通话。
        return recognizer.recognize_google(audio, language="zh-CN")
    except Exception as exc:  # pragma: no cover - network/service dependent
        raise VoiceInputError(f"语音识别失败：{exc}") from exc
