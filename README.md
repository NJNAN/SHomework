# 智能家居控制助手

2023级智能科学与技术1班 · Python编程综合实训课程设计（2025–2026学年）

## 项目简介

基于自然语言处理的中文智能家居指令解析系统。用户通过文本或语音输入家居控制指令（如"打开客厅空调"），系统自动识别指令意图，提取**位置**、**设备**、**操作**三个槽位，并给出置信度评估。

## 功能特性

- **意图分类** — 区分"家居控制"与"非家居控制"指令（二分类）
- **槽位填充** — 提取地点（7类）、设备（8类）、操作（开/关）三个关键信息
- **语义帧输出** — 将自然语言解析为意图、槽位和可执行控制动作
- **场景模式** — 支持"我出门了"、"睡觉了"、"看电影"等场景级意图
- **批量控制** — 支持"关闭所有空调"、"把客厅和卧室的灯都关了"等多设备控制
- **OOS 拒识** — 识别非家居控制语句，避免"打开原神"这类输入误触发设备
- **GUI 交互** — Tkinter 桌面界面，支持指令输入、结果展示与执行日志
- **内置 2D 家居面板** — 在软件右侧直接查看各房间电器开启/关闭状态
- **语音输入** — 可选麦克风语音识别，支持中文普通话
- **自动训练** — 首次运行若缺少模型文件，自动生成数据集并训练
- **Linux 大数据侧车** — 独立采集家居状态变化，生成事件日志、批处理报表和流式窗口统计

## 项目结构

```text
智能家居系统/
├── data/                       # 生成的数据集
│   ├── binary_intent_dataset.csv   # 二分类数据集（家居控制/非家居控制）
│   └── multi_slot_dataset.csv      # 多分类数据集（位置/设备/操作）
├── models/                     # 训练好的模型
│   ├── binary_intent_model.joblib  # 二分类模型
│   ├── location_model.joblib       # 位置识别模型
│   ├── device_model.joblib         # 设备识别模型
│   ├── action_model.joblib         # 操作识别模型
│   └── metrics.json                # 各模型评估指标
├── src/                        # 源代码
│   ├── app.py                      # Tkinter GUI 主界面
│   ├── intent_engine.py            # 意图解析引擎
│   ├── state_bridge.py             # 软件内部家居状态读写
│   ├── data_builder.py             # 数据集构建
│   ├── trainer.py                  # 模型训练
│   └── voice_input.py              # 语音输入（可选）
├── linux_bigdata/              # Linux + 大数据侧车模块，不干扰原主程序
│   ├── event_collector.py          # 监听状态文件，追加设备事件日志
│   ├── command_replay.py           # 生成演示事件数据
│   ├── batch_analyze.py            # 批处理统计分析
│   ├── stream_window.py            # 模拟实时窗口统计
│   └── linux/                      # Linux 启动脚本和 systemd 服务模板
├── runtime/home_state.json      # GUI 面板和数据侧车共享的家居状态
├── train_models.py             # 训练入口脚本
├── run_app.py                  # 启动入口
├── run_console.py              # 命令行控制台入口
├── requirements.txt            # 核心依赖
└── requirements-voice.txt      # 语音功能可选依赖
```

## 环境要求

- Python 3.10+
- Windows / macOS / Linux

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

如需语音输入功能，额外安装：

```bash
pip install -r requirements-voice.txt
```

### 2. 启动应用

```bash
python run_app.py
```

首次运行会自动检测模型文件，若缺失则自动生成数据集并训练。

### 3. 使用内置 2D 家居状态面板

软件右侧提供 2D 家居面板。输入指令并点击"分析指令"后，对应房间里的设备状态会立即点亮或关闭，不需要再启动额外的可视化程序。

也可以使用命令行控制台写入同一份家居状态：

```bash
python run_console.py
```

输入下面这类指令后，软件右侧 2D 面板会更新：

```text
打开客厅的灯
关闭客厅的灯
打开卧室灯
打开卧室窗帘
打开卧室床帘
打开卫生间排气扇
打开厨房油烟机
关闭书房窗帘
关闭所有空调
把客厅和卧室的灯都关了
我出门了
睡觉了
看电影
厨房太闷了
```

### 4. 重新训练模型

```bash
python train_models.py
```

## Linux 大数据扩展

本项目额外提供一个独立的 Linux 大数据侧车模块，目录为：

```text
linux_bigdata/
```

它不修改原来的 GUI 和意图识别模型，只把智能家居状态变化整理成事件日志，再做批处理和流式窗口统计。

数据链路如下：

```text
runtime/home_state.json
  → linux_bigdata/event_collector.py
  → linux_bigdata/data/events.jsonl
  → batch_analyze.py / stream_window.py
  → linux_bigdata/output/
```

Windows 上可以直接验证：

```bash
python linux_bigdata/command_replay.py
python linux_bigdata/show_events.py --limit 5
python linux_bigdata/batch_analyze.py
python linux_bigdata/show_report.py
python linux_bigdata/stream_window.py --once
```

Linux 上可以运行：

```bash
bash linux_bigdata/linux/bootstrap_linux.sh
bash linux_bigdata/linux/run_pipeline_demo.sh
```

详细设计见：

```text
docs/Linux大数据侧车模块说明.md
linux_bigdata/README.md
```

## 使用说明

|操作|说明|
|------|------|
|**文本输入**|在输入框中输入中文指令，点击"分析指令"|
|**语音输入**|点击"语音输入"，说出指令后自动识别分析|
|**清空**|清空当前输入框内容|

### 示例指令

|指令|位置|设备|操作|
|------|------|------|------|
|打开客厅空调|客厅|空调|打开|
|关闭卧室灯|卧室|灯|关闭|
|把书房窗帘打开|书房|窗帘|打开|
|关掉厨房油烟机|厨房|油烟机|关闭|
|关闭所有空调|多个房间|空调|关闭|
|我出门了|多个房间|多设备|场景联动|
|厨房太闷了|厨房|油烟机|打开|

## 技术方案

### 算法选型

|模块|算法|说明|
|------|------|------|
|特征提取|TF-IDF (char级, 1-3 gram)|中文无需分词，字级n-gram覆盖常见组合|
|分类器|Logistic Regression|线性模型，训练快、可解释、适合中小规模数据|
|二分类|同上|判断是否属于家居控制语句|
|槽位分类|同上|分别训练位置/设备/操作三个独立分类器|

### 推理流程

```text
用户指令 → 语音/口语归一化
         → 场景意图识别（离家/回家/睡眠/观影）
         → 环境语义推理（热/暗/闷等口语表达）
         → OOS 拒识与二分类模型判断
         → 地点/设备/操作槽位抽取
         → 语义帧与控制动作生成
         → 更新软件右侧 2D 家居状态面板
```

### 模型指标

|模型|准确率|
|------|--------|
|二分类（binary_intent）|99.7%|
|位置识别（location）|100%|
|设备识别（device）|100%|
|操作识别（action）|100%|

> 注：当前数据集为模板构造，覆盖全面但缺乏真实场景噪声，指标仅供参考。

## NLP 论文与应用设计

项目的自然语言处理增强方案参考了意图识别、槽位填充、IoT 语音交互、Out-of-Scope 拒识和语音助手 SLU 相关论文。详细总结见：

```text
docs/NLP论文调研与智能家居应用设计.md
```

## 依赖说明

|包|用途|必须|
|----|------|------|
|pandas|数据处理与CSV读写|是|
|scikit-learn|特征提取与模型训练|是|
|joblib|模型持久化|是|
|SpeechRecognition|语音识别|否|
|PyAudio|麦克风录音|否|

## 课程信息

- **学校**：福州理工学院
- **专业**：2023级智能科学与技术1班
- **课程**：Python编程综合实训
- **学年**：2025–2026
