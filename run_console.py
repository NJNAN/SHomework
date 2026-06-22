"""命令行版本入口。

新手阅读提示：
1. GUI 是窗口版，run_console.py 是终端版。
2. 它和 GUI 共用同一个解析引擎、API 模块和状态文件。
3. 如果你想快速测试“某句话会被解析成什么”，终端版比打开 GUI 更方便。
"""

import argparse

from src.api_llm import ApiLLMError, ApiLLMParser
from src.intent_engine import SmartHomeIntentEngine
from src.state_bridge import apply_parse_result, ensure_state_file


def intent_label(intent: str) -> str:
    """把内部意图代码转换成适合命令行展示的中文名称。"""

    labels = {
        "device_control": "单设备控制",
        "batch_control": "批量控制",
        "scene_mode": "场景模式",
        "environment_control": "环境语义控制",
        "out_of_scope": "非家居控制",
    }
    return labels.get(intent, "家居控制")


def main() -> None:
    """命令行控制台入口，适合不打开 Tkinter 界面时快速测试解析效果。"""

    # argparse 用来解析命令行参数，例如 python run_console.py --api。
    parser = argparse.ArgumentParser(description="Smart-home command console.")
    parser.add_argument("--api", action="store_true", help="使用 DeepSeek/OpenAI-compatible API 解析指令。")
    parser.add_argument("--llm", action="store_true", help="兼容旧参数，等同于 --api。")
    args = parser.parse_args()

    # 本地解析引擎始终创建；即使 API 模式开启，也可以作为失败后的兜底。
    engine = SmartHomeIntentEngine()
    api_llm = ApiLLMParser() if args.api or args.llm else None
    # 确保共享状态文件存在，否则后面 apply_parse_result 没地方写。
    ensure_state_file()
    print("智能家居控制台已启动。输入 q 退出。")
    print("示例：打开客厅的灯 / 关闭所有空调 / 我出门了 / 厨房太闷了")
    if api_llm:
        print(f"API 模型模式：{api_llm.config.model}")

    while True:
        # input 会等待用户在终端输入一行文字。
        text = input("\n请输入指令：").strip()
        if text.lower() in {"q", "quit", "exit"}:
            break
        if not text:
            continue

        # API 模式用于验证复杂口语；普通模式直接走本地规则和机器学习模型。
        if api_llm:
            try:
                result = api_llm.parse(text, fallback_engine=engine)
            except ApiLLMError as exc:
                print(f"API 模型不可用：{exc}")
                print("请确认已设置 DEEPSEEK_API_KEY。")
                continue
        else:
            result = engine.parse(text)
        if not result.is_control:
            # 非家居控制只打印原因，不写状态文件。
            print(f"结果：{result.reason or '非家居控制'}")
            continue

        # 与 GUI 共用同一份 runtime/home_state.json，所以控制台执行后看板也会变化。
        synced = apply_parse_result(result)
        print(f"结果：{intent_label(result.intent)} | {result.message}")
        if result.normalized_text and result.normalized_text != result.text:
            print(f"归一化：{result.normalized_text}")
        if synced:
            print("已更新本地家居状态，可在状态看板或 HTML 看板查看")
        else:
            print("已识别，但未写入状态：请确认地点和设备在系统房间中存在")


if __name__ == "__main__":
    main()
