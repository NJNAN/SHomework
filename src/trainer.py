"""训练二分类意图模型和三个槽位分类模型。

新手阅读提示：
1. “训练模型”可以理解成让程序看很多例句，学会以后怎么分类。
2. 本项目训练 4 个模型：
   - binary_intent：判断一句话是不是智能家居控制。
   - location：判断地点，例如客厅、卧室。
   - device：判断设备，例如灯、空调。
   - action：判断动作，例如打开、关闭。
3. 训练完成后会生成 models/*.joblib 文件，intent_engine.py 启动时会读取这些文件。
"""

from __future__ import annotations

# json 用来把模型评估结果写成 metrics.json，方便报告引用。
import json
from pathlib import Path

# joblib 用来保存和读取机器学习模型。
import joblib
# pandas 用来读取 CSV 表格数据，常用别名是 pd。
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline

from .data_builder import build_dataset_files


def make_text_classifier() -> Pipeline:
    """构建字符级 TF-IDF + 逻辑回归分类器，适合小规模中文短句。

    白话解释：
    - TF-IDF：把文字变成数字特征。模型不能直接理解中文，必须先把句子转成数字。
    - analyzer="char"：按“字”切分，不用中文分词，适合短句。
    - ngram_range=(1, 3)：同时看 1 个字、2 个字、3 个字的组合。
      例如“客厅灯”会产生“客”“厅”“灯”“客厅”“厅灯”“客厅灯”等特征。
    - LogisticRegression：逻辑回归分类器，名字里有“回归”，但这里用于分类。
    - Pipeline：流水线，把“文本转数字”和“分类器训练”串在一起。
    """

    return Pipeline(
        steps=[
            # 第一步：把中文短句转换成数字向量。
            ("tfidf", TfidfVectorizer(analyzer="char", ngram_range=(1, 3))),
            # 第二步：用逻辑回归学习这些数字向量和标签之间的关系。
            ("clf", LogisticRegression(max_iter=1000, class_weight="balanced")),
        ]
    )


def train_one_model(texts, labels, random_state: int = 42) -> tuple[Pipeline, dict]:
    """训练单个分类模型，并返回模型对象和测试集评估指标。

    参数说明：
    - texts：训练句子，例如“打开客厅灯”。
    - labels：每个句子的答案，例如“客厅”或“打开”。
    - random_state：固定随机种子，保证每次划分训练集/测试集结果基本一致。
    """

    # train_test_split 把数据拆成训练集和测试集：
    # 训练集负责“学习”，测试集负责“考试”。
    x_train, x_test, y_train, y_test = train_test_split(
        texts,
        labels,
        test_size=0.2,
        random_state=random_state,
        # stratify 表示按标签比例分层抽样，避免某个类别在测试集中太少。
        stratify=labels,
    )
    model = make_text_classifier()
    # fit 就是正式训练模型。
    model.fit(x_train, y_train)
    # predict 用测试集做预测，看看模型学得怎么样。
    pred = model.predict(x_test)
    metrics = {
        # accuracy 是准确率，例如 0.98 表示 98% 测试样本预测正确。
        "accuracy": round(float(accuracy_score(y_test, pred)), 4),
        # classification_report 包含每个类别的 precision/recall/f1-score。
        "report": classification_report(y_test, pred, zero_division=0),
    }
    return model, metrics


def train_all(root: Path | None = None) -> dict:
    """生成数据集、训练全部模型，并把模型和指标写入项目目录。

    运行 `python train_models.py` 时，最后实际会调用这个函数。
    """

    root = root or Path(__file__).resolve().parents[1]
    data_dir = root / "data"
    model_dir = root / "models"
    # 如果 models/ 不存在，就自动创建。
    model_dir.mkdir(parents=True, exist_ok=True)

    # 每次训练前重新生成 CSV，保证 data/ 与当前模板配置一致。
    binary_path, multi_path = build_dataset_files(data_dir)
    # read_csv 把 CSV 文件读成 DataFrame，可以理解成 Python 里的表格。
    binary_df = pd.read_csv(binary_path)
    multi_df = pd.read_csv(multi_path)

    metrics: dict[str, object] = {}

    # 二分类模型判断一句话是否属于智能家居控制范围。
    binary_model, binary_metrics = train_one_model(binary_df["text"], binary_df["label"])
    # dump 把训练好的模型保存到硬盘，之后运行程序就不用每次重新训练。
    joblib.dump(binary_model, model_dir / "binary_intent_model.joblib")
    metrics["binary_intent"] = binary_metrics

    for target in ["location", "device", "action"]:
        # 三个槽位模型分别预测房间、设备和动作。
        model, target_metrics = train_one_model(
            multi_df["text"],
            multi_df[target],
            random_state=42,
        )
        # f"{target}_model.joblib" 会生成 location_model.joblib 等文件名。
        joblib.dump(model, model_dir / f"{target}_model.joblib")
        metrics[target] = target_metrics

    metrics_path = model_dir / "metrics.json"
    # ensure_ascii=False 表示保留中文，不转成 \uXXXX 这种难读格式。
    metrics_path.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    return metrics


if __name__ == "__main__":
    result = train_all()
    print("模型训练完成，主要准确率如下：")
    for name, item in result.items():
        print(f"- {name}: {item['accuracy']}")
