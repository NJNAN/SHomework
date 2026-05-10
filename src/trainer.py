"""Train the binary intent model and the three slot classification models."""

from __future__ import annotations

import json
from pathlib import Path

import joblib
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline

from .data_builder import build_dataset_files


def make_text_classifier() -> Pipeline:
    return Pipeline(
        steps=[
            ("tfidf", TfidfVectorizer(analyzer="char", ngram_range=(1, 3))),
            ("clf", LogisticRegression(max_iter=1000, class_weight="balanced")),
        ]
    )


def train_one_model(texts, labels, random_state: int = 42) -> tuple[Pipeline, dict]:
    x_train, x_test, y_train, y_test = train_test_split(
        texts,
        labels,
        test_size=0.2,
        random_state=random_state,
        stratify=labels,
    )
    model = make_text_classifier()
    model.fit(x_train, y_train)
    pred = model.predict(x_test)
    metrics = {
        "accuracy": round(float(accuracy_score(y_test, pred)), 4),
        "report": classification_report(y_test, pred, zero_division=0),
    }
    return model, metrics


def train_all(root: Path | None = None) -> dict:
    root = root or Path(__file__).resolve().parents[1]
    data_dir = root / "data"
    model_dir = root / "models"
    model_dir.mkdir(parents=True, exist_ok=True)

    binary_path, multi_path = build_dataset_files(data_dir)
    binary_df = pd.read_csv(binary_path)
    multi_df = pd.read_csv(multi_path)

    metrics: dict[str, object] = {}

    binary_model, binary_metrics = train_one_model(binary_df["text"], binary_df["label"])
    joblib.dump(binary_model, model_dir / "binary_intent_model.joblib")
    metrics["binary_intent"] = binary_metrics

    for target in ["location", "device", "action"]:
        model, target_metrics = train_one_model(
            multi_df["text"],
            multi_df[target],
            random_state=42,
        )
        joblib.dump(model, model_dir / f"{target}_model.joblib")
        metrics[target] = target_metrics

    metrics_path = model_dir / "metrics.json"
    metrics_path.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    return metrics


if __name__ == "__main__":
    result = train_all()
    print("模型训练完成，主要准确率如下：")
    for name, item in result.items():
        print(f"- {name}: {item['accuracy']}")
