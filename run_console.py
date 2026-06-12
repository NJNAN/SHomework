from src.intent_engine import SmartHomeIntentEngine
from src.state_bridge import apply_parse_result, ensure_state_file


def intent_label(intent: str) -> str:
    labels = {
        "device_control": "单设备控制",
        "batch_control": "批量控制",
        "scene_mode": "场景模式",
        "environment_control": "环境语义控制",
        "out_of_scope": "非家居控制",
    }
    return labels.get(intent, "家居控制")


def main() -> None:
    engine = SmartHomeIntentEngine()
    ensure_state_file()
    print("智能家居控制台已启动。输入 q 退出。")
    print("示例：打开客厅的灯 / 关闭所有空调 / 我出门了 / 厨房太闷了")

    while True:
        text = input("\n请输入指令：").strip()
        if text.lower() in {"q", "quit", "exit"}:
            break
        if not text:
            continue

        result = engine.parse(text)
        if not result.is_control:
            print(f"结果：{result.reason or '非家居控制'}")
            continue

        synced = apply_parse_result(result)
        print(f"结果：{intent_label(result.intent)} | {result.message}")
        if result.normalized_text and result.normalized_text != result.text:
            print(f"归一化：{result.normalized_text}")
        if synced:
            print("已更新本地家居状态，可在软件右侧 2D 面板查看")
        else:
            print("已识别，但未写入状态：请确认地点和设备在系统房间中存在")


if __name__ == "__main__":
    main()
