# Linux 大数据侧车模块

这个目录是智能家居项目的独立扩展，不参与原来的 GUI、语音识别、意图分类和 2D 家居面板展示流程。

它只读取 `runtime/home_state.json` 或独立生成演示事件，把智能家居控制行为整理成事件日志，再做批处理和流式统计。这样项目可以自然地扩展到“智能家居设备事件数据分析”，而不是把大数据组件硬塞进原来的控制程序。

## 数据链路

```text
原智能家居系统
  └─ runtime/home_state.json
       └─ event_collector.py 监听状态变化
            └─ data/events.jsonl 追加设备事件
                 ├─ batch_analyze.py 生成统计报表
                 └─ stream_window.py 模拟实时窗口统计
```

## 事件格式

每一行是一条 JSON 事件：

```json
{"event_time":"2026-05-17T20:00:00","room":"客厅","device":"灯","action":"打开","value":true,"source":"home_state"}
```

字段含义：

| 字段 | 说明 |
| --- | --- |
| `event_time` | 事件产生时间 |
| `room` | 房间 |
| `device` | 设备 |
| `action` | 打开或关闭 |
| `value` | `true` 表示开启，`false` 表示关闭 |
| `source` | 数据来源 |

## Windows 上快速验证

在项目根目录运行：

```powershell
python linux_bigdata\command_replay.py
python linux_bigdata\show_events.py --limit 5
python linux_bigdata\batch_analyze.py
python linux_bigdata\show_report.py
python linux_bigdata\stream_window.py --once
```

输出文件在：

```text
linux_bigdata/data/events.jsonl
linux_bigdata/output/room_summary.csv
linux_bigdata/output/device_summary.csv
linux_bigdata/output/hour_summary.csv
linux_bigdata/output/report.md
```

## Linux 上运行

进入项目根目录：

```bash
bash linux_bigdata/linux/bootstrap_linux.sh
bash linux_bigdata/linux/run_pipeline_demo.sh
```

如果要做成 Linux 后台服务，可以参考：

```text
linux_bigdata/linux/smart-home-bigdata.service
```

## 和原项目的关系

- 原项目：负责识别中文家居指令，并更新当前家居状态。
- 本模块：负责把状态变化变成事件数据，再做统计分析。
- 两者通过文件松耦合连接，不需要修改原 GUI 和模型代码。
