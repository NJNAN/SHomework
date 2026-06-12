# Linux 大数据侧车模块说明

## 为什么这样设计

原来的智能家居系统已经有清晰职责：

- 中文指令识别
- 地点、设备、动作解析
- Tkinter 界面展示
- 内置 2D 家居状态面板

如果直接把 Kafka、Spark 或 Linux 服务代码塞进 `src/app.py`，会让原系统变复杂，也不符合大数据项目的真实结构。真实的大数据系统通常不是把分析逻辑写进业务界面里，而是把业务行为转成事件，再由旁路数据管道分析。

所以本项目新增 `linux_bigdata/` 作为侧车模块：

```text
原智能家居程序负责控制
Linux 大数据侧车负责采集和分析
```

两者只通过 `runtime/home_state.json` 或独立事件日志连接，互不干扰。

## 大数据元素在哪里

本模块把“开灯、关空调、开窗帘”等操作转成事件数据：

```json
{"event_time":"2026-05-17T20:00:00","room":"客厅","device":"灯","action":"打开","value":true}
```

这类数据天然适合大数据处理，因为它是连续产生的时间序列事件：

- 可以长期追加保存
- 可以按房间、设备、时间窗口聚合
- 可以做用户行为分析
- 可以做异常检测，例如频繁开关设备
- 可以迁移到 Kafka、Flink、Spark 等更重的平台

当前实现选择轻量版本，是为了课程项目可运行、可解释、可验证。

## Linux 元素在哪里

`linux_bigdata/linux/` 提供 Linux 运行入口：

| 文件 | 作用 |
| --- | --- |
| `bootstrap_linux.sh` | 创建 Linux Python 虚拟环境并安装依赖 |
| `run_collector.sh` | 在 Linux 上启动状态监听采集 |
| `run_pipeline_demo.sh` | 一键跑演示数据、批处理和流式窗口统计 |
| `smart-home-bigdata.service` | systemd 后台服务模板 |

这部分把项目从“本地 Python 程序”扩展成“可以在 Linux 服务器后台运行的数据采集服务”。

## 数据处理链路

```text
runtime/home_state.json
        |
        v
event_collector.py
        |
        v
linux_bigdata/data/events.jsonl
        |
        +--> batch_analyze.py 生成 CSV 和 Markdown 报告
        |
        +--> stream_window.py 模拟实时窗口统计
```

## 适合答辩的说法

本项目原本解决的是“自然语言控制智能家居”的问题。扩展后，系统不只会执行控制，还能把设备控制行为沉淀成事件数据，在 Linux 环境下进行采集、批处理和流式统计。

这体现了一个小型大数据系统的基本结构：

```text
数据源 -> 数据采集 -> 事件日志 -> 批处理分析 -> 实时窗口统计 -> 报表输出
```

同时，扩展模块没有侵入原来的 GUI 和模型代码，保留了系统稳定性。
