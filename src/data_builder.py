"""构造智能家居助手使用的小型标注数据集。

任务要求包含两类数据：
1. 二分类数据集：判断句子是否属于智能家居控制。
2. 多分类数据集：给句子标注地点、设备和动作三个槽位。

本文件用模板自动生成数据，避免课程项目依赖外部下载数据。

新手阅读提示：
1. “数据集”就是很多句子和标准答案组成的表格。
2. “标签”就是每个句子的答案。
   例如句子“打开客厅灯”的地点标签是“客厅”，设备标签是“灯”，动作标签是“打开”。
3. 本文件不是训练模型本身，而是先把训练用的 CSV 表格造出来。
"""

from __future__ import annotations

# csv 用来写 CSV 文件；CSV 可以理解成用逗号分隔的表格。
import csv
# random 用来打乱样本顺序，避免同类样本都挤在一起。
import random
from pathlib import Path


# 训练数据里允许出现的地点。
LOCATIONS = ["客厅", "卧室", "厨房", "卫生间", "书房", "阳台", "餐厅"]

# 每个地点允许出现的设备，和 intent_engine.py 中的配置保持一致。
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
    # 左边“打开/关闭”是标准标签；右边列表是用户可能说出来的不同表达。
    "打开": ["打开", "开启", "启动", "帮我开", "请打开", "开一下", "把"],
    "关闭": ["关闭", "关掉", "停止", "帮我关", "请关闭", "关上", "关一下", "把"],
}

# 正样本模板：这些句式都会被认为是家居控制。
# {location}/{device}/{action} 是占位符，后面会替换成具体房间、设备和动作。
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

# 负样本：这些句子不是家居控制，用来教模型“哪些话不能执行设备动作”。
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

# 场景类正样本：没有直接写设备，但属于家居控制。
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

# 批量控制正样本：一句话可能控制多个设备。
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

# 环境语义正样本：用户描述环境，系统推理出该控制什么设备。
ENVIRONMENT_POSITIVE_SENTENCES = [
    "客厅有点热",
    "卧室太热了",
    "厨房太闷了",
    "卫生间有点闷",
    "书房太暗了",
    "餐厅有点黑",
]


def _normalize_action(word: str, label: str) -> str:
    """处理“把”字句模板，让动作词符合自然中文表达。

    例如模板是“把{location}{device}{action}”。
    如果 action 直接填“把”，就会变成“把客厅灯把”，这显然不对。
    所以遇到 word=="把" 时，要根据标准标签改成“打开”或“关掉”。
    """

    if word == "把":
        return "打开" if label == "打开" else "关掉"
    return word


def build_rows(seed: int = 42) -> tuple[list[dict[str, object]], list[dict[str, str]]]:
    """生成二分类样本和槽位分类样本。

    返回两个列表：
    - binary_rows：二分类表，每行只有 text 和 label。
      label=1 表示家居控制，label=0 表示不是家居控制。
    - multi_rows：槽位表，每行有 text、location、device、action。
    """

    # 固定随机种子，保证每次生成和打乱顺序稳定，方便复现实验。
    random.seed(seed)
    binary_rows: list[dict[str, object]] = []
    multi_rows: list[dict[str, str]] = []

    # 下面四层循环会枚举所有“房间-设备-动作-句式”的组合。
    # 例如：客厅 + 灯 + 打开 + “请{action}{location}{device}”
    # 会生成：“请打开客厅灯”。
    for location in LOCATIONS:
        for device in DEVICES_BY_LOCATION[location]:
            for action_label, action_words in ACTION_WORDS.items():
                for action_word in action_words:
                    for template in POSITIVE_TEMPLATES:
                        # 正样本同时进入二分类数据和多槽位数据。
                        text = template.format(
                            location=location,
                            device=device,
                            action=_normalize_action(action_word, action_label),
                        )
                        binary_rows.append({"text": text, "label": 1})
                        multi_rows.append(
                            {
                                "text": text,
                                # 这些就是槽位分类模型要学习的标准答案。
                                "location": location,
                                "device": device,
                                "action": action_label,
                            }
                        )

    # 负样本覆盖聊天、软件、游戏、提醒等非家居请求，用来训练 OOS 拒识能力。
    polite_prefixes = ["", "请问", "小助手", "你好", "帮我", "麻烦你"]
    for sentence in NEGATIVE_SENTENCES:
        for prefix in polite_prefixes:
            # 给负样本加不同礼貌前缀，让模型看到更多日常说法。
            text = f"{prefix}{sentence}" if prefix else sentence
            binary_rows.append({"text": text, "label": 0})

    for sentence in SCENE_POSITIVE_SENTENCES + BATCH_POSITIVE_SENTENCES + ENVIRONMENT_POSITIVE_SENTENCES:
        for prefix in ["", "请", "帮我"]:
            # 场景、批量、环境语义属于家居控制，因此只加入二分类正样本。
            text = f"{prefix}{sentence}" if prefix else sentence
            binary_rows.append({"text": text, "label": 1})

    # 打乱数据顺序，避免训练时先看到一大堆同类句子。
    random.shuffle(binary_rows)
    random.shuffle(multi_rows)
    return binary_rows, multi_rows


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    """按 UTF-8 BOM 写出 CSV，方便 Windows Excel 直接打开中文。

    fieldnames 是表头，例如 ["text", "label"]。
    rows 是每一行数据，例如 {"text": "打开客厅灯", "label": 1}。
    """

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def build_dataset_files(data_dir: Path) -> tuple[Path, Path]:
    """生成并保存两个训练数据文件，返回它们的路径。

    返回值是 (二分类CSV路径, 槽位CSV路径)。
    """

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
