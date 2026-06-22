"""模型训练入口脚本。

新手阅读提示：
1. 运行 `python train_models.py` 会重新生成数据集并训练模型。
2. 训练逻辑不写在这里，而是放在 src/trainer.py。
3. 这个文件只是调用 train_all()，然后把各模型准确率打印出来。
"""

from src.trainer import train_all

if __name__ == "__main__":
    # 训练入口：生成数据集、训练四个模型，并把评估结果保存到 models/metrics.json。
    result = train_all()
    print("模型训练完成，准确率如下：")
    for name, item in result.items():
        # result 是一个字典，name 是模型名，item["accuracy"] 是该模型准确率。
        print(f"  {name}: {item['accuracy']}")
    print(f"\n详细报告已保存至 models/metrics.json")
