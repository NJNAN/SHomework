"""Build small labeled datasets for the smart home assistant.

The task book asks for two datasets:
1. A binary dataset: smart-home control sentence or not.
2. A multi-class dataset: location, device and action labels.

This file generates those datasets with simple, readable Python code so the
project can run without downloading external data.
"""

from __future__ import annotations

import csv
import random
from pathlib import Path


LOCATIONS = ["客厅", "卧室", "厨房", "卫生间", "书房", "阳台", "餐厅"]

DEVICES_BY_LOCATION = {
    "客厅": ["灯", "空调", "电视", "窗帘", "风扇"],
    "卧室": ["灯", "空调", "窗帘", "风扇"],
    "厨房": ["灯", "油烟机", "热水器"],
    "卫生间": ["灯", "热水器", "排风扇"],
    "书房": ["灯", "空调", "窗帘", "风扇"],
    "阳台": ["灯", "窗帘"],
    "餐厅": ["灯", "空调", "风扇"],
}

ACTION_WORDS = {
    "打开": ["打开", "开启", "启动", "帮我开", "请打开", "开一下", "把"],
    "关闭": ["关闭", "关掉", "停止", "帮我关", "请关闭", "关上", "关一下", "把"],
}

POSITIVE_TEMPLATES = [
    "{action}{location}{device}",
    "帮我{action}{location}的{device}",
    "请{action}{location}{device}",
    "把{location}{device}{action}",
    "我想{action}{location}{device}",
    "{location}的{device}{action}一下",
    "现在{action}{location}{device}",
    "麻烦{action}{location}里面的{device}",
]

NEGATIVE_SENTENCES = [
    "今天天气怎么样",
    "帮我订一份外卖",
    "播放一首周杰伦的歌",
    "玩原神",
    "我要玩原神",
    "帮我打开原神",
    "启动原神",
    "关闭原神",
    "打开游戏",
    "关闭游戏",
    "我想玩游戏",
    "打开微信",
    "关闭微信",
    "打开浏览器",
    "关闭浏览器",
    "打开网页",
    "关闭网页",
    "打开文件夹",
    "关闭电脑",
    "启动Python程序",
    "运行这个软件",
    "停止下载任务",
    "帮我打开视频",
    "关闭播放器",
    "打开音乐软件",
    "打开学习通",
    "关闭这个窗口",
    "明天早上七点叫我起床",
    "现在几点了",
    "讲一个笑话",
    "查询一下附近的电影院",
    "帮我打开浏览器",
    "今天有什么新闻",
    "我想学习Python编程",
    "给妈妈打电话",
    "导航去学校",
    "帮我翻译这句话",
    "计算一下一百乘以二十三",
    "提醒我晚上写作业",
    "搜索人工智能的发展历史",
    "今天适合跑步吗",
    "帮我查一下快递",
    "我想看电影",
    "附近有什么好吃的",
    "打开原神",
    "关闭原神",
    "打开微信",
    "关闭微信",
    "打开QQ",
    "关闭QQ",
    "播放音乐",
    "暂停音乐",
    "打开浏览器搜索资料",
    "关闭这个网页",
    "帮我查天气",
    "给妈妈打电话",
    "发一条微信",
    "打开课程表",
    "帮我写作业",
    "运行代码",
    "停止程序",
    "打开摄像头拍照",
    "关闭闹钟",
]

SCENE_POSITIVE_SENTENCES = [
    "我出门了",
    "出门了",
    "启动离家模式",
    "家里没人了",
    "我回来了",
    "回家了",
    "到家了",
    "启动回家模式",
    "睡觉了",
    "我要睡觉",
    "晚安",
    "启动睡眠模式",
    "我要看电影",
    "打开观影模式",
    "启动电影模式",
]

BATCH_POSITIVE_SENTENCES = [
    "关闭所有灯",
    "打开所有灯",
    "关闭全部空调",
    "打开全屋灯",
    "把客厅和卧室的灯都关了",
    "把客厅和书房的空调都打开",
    "关闭客厅电视和灯",
    "打开卧室灯和窗帘",
]

ENVIRONMENT_POSITIVE_SENTENCES = [
    "客厅有点热",
    "卧室太热了",
    "厨房太闷了",
    "卫生间有点闷",
    "书房太暗了",
    "餐厅有点黑",
]


def _normalize_action(word: str, label: str) -> str:
    """Handle templates that use the direct object before the action word."""
    if word == "把":
        return "打开" if label == "打开" else "关掉"
    return word


def build_rows(seed: int = 42) -> tuple[list[dict[str, object]], list[dict[str, str]]]:
    random.seed(seed)
    binary_rows: list[dict[str, object]] = []
    multi_rows: list[dict[str, str]] = []

    for location in LOCATIONS:
        for device in DEVICES_BY_LOCATION[location]:
            for action_label, action_words in ACTION_WORDS.items():
                for action_word in action_words:
                    for template in POSITIVE_TEMPLATES:
                        text = template.format(
                            location=location,
                            device=device,
                            action=_normalize_action(action_word, action_label),
                        )
                        binary_rows.append({"text": text, "label": 1})
                        multi_rows.append(
                            {
                                "text": text,
                                "location": location,
                                "device": device,
                                "action": action_label,
                            }
                        )

    # Duplicate and slightly vary negative samples so the binary model sees
    # enough daily-chat and software-control examples.
    polite_prefixes = ["", "请问", "小助手", "你好", "帮我", "麻烦你"]
    for sentence in NEGATIVE_SENTENCES:
        for prefix in polite_prefixes:
            text = f"{prefix}{sentence}" if prefix else sentence
            binary_rows.append({"text": text, "label": 0})

    for sentence in SCENE_POSITIVE_SENTENCES + BATCH_POSITIVE_SENTENCES + ENVIRONMENT_POSITIVE_SENTENCES:
        for prefix in ["", "请", "帮我"]:
            text = f"{prefix}{sentence}" if prefix else sentence
            binary_rows.append({"text": text, "label": 1})

    random.shuffle(binary_rows)
    random.shuffle(multi_rows)
    return binary_rows, multi_rows


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def build_dataset_files(data_dir: Path) -> tuple[Path, Path]:
    binary_rows, multi_rows = build_rows()
    binary_path = data_dir / "binary_intent_dataset.csv"
    multi_path = data_dir / "multi_slot_dataset.csv"
    write_csv(binary_path, binary_rows, ["text", "label"])
    write_csv(multi_path, multi_rows, ["text", "location", "device", "action"])
    return binary_path, multi_path


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    binary_file, multi_file = build_dataset_files(root / "data")
    print(f"已生成二分类数据集: {binary_file}")
    print(f"已生成多分类数据集: {multi_file}")
