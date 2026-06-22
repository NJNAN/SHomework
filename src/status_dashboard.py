"""根据家居状态生成可自动刷新的 HTML 看板。

新手阅读提示：
1. 这个文件不负责解析指令，只负责把状态字典变成网页。
2. HTML 是网页结构，CSS 是网页样式。
3. 生成的文件是 runtime/home_status.html，可以直接用浏览器打开。
"""

from __future__ import annotations

from datetime import datetime
# escape 用于转义 HTML 特殊字符，避免状态文本破坏网页结构。
from html import escape
from pathlib import Path


def render_status_dashboard(
    state: dict,
    devices_by_room: dict[str, list[str]],
    recent_keys: set[tuple[str, str]] | None = None,
) -> str:
    """把状态字典渲染成完整 HTML 字符串。

    render 的意思是“渲染/生成显示内容”。
    这里返回的是一整段 HTML 文本，不是直接打开浏览器。
    """

    recent_keys = recent_keys or set()
    rooms = state.get("rooms", {})
    # active_count 统计所有房间里值为 True 的设备数量。
    active_count = sum(
        1
        for room_devices in rooms.values()
        for is_on in room_devices.values()
        if is_on
    )
    total_count = sum(len(devices) for devices in devices_by_room.values())
    # 从 JSON 读出来的内容会放进 HTML，先 escape 更稳妥。
    updated_at = escape(str(state.get("updated_at", "未知")))
    last_result = escape(str(state.get("last_result") or "暂无操作"))

    # 每个房间生成一张卡片，开启设备和本次操作会使用不同样式高亮。
    cards = []
    for room, devices in devices_by_room.items():
        room_state = rooms.get(room, {})
        # 当前开启的设备。
        active_devices = [device for device in devices if room_state.get(device)]
        # 本次刚刚被操作过的设备。
        recent_devices = [device for device in devices if (room, device) in recent_keys]
        card_class = "room-card active" if active_devices else "room-card"
        if recent_devices:
            card_class += " recent"
        if active_devices:
            # 每个开启设备生成一个 <span> 标签，CSS 会把它显示成绿色小标签。
            device_html = "".join(f"<span>{escape(device)}</span>" for device in active_devices)
        else:
            device_html = '<em>全部关闭</em>'
        recent_html = ""
        if recent_devices:
            recent_html = f'<div class="recent-line">本次操作：{"、".join(map(escape, recent_devices))}</div>'
        cards.append(
            # 这里使用 f-string 拼接 HTML。双大括号 {{ }} 是为了在 f-string 中输出 CSS 大括号。
            f"""
            <section class="{card_class}">
              <div class="room-head">
                <h2>{escape(room)}</h2>
                <strong>开启 {len(active_devices)}/{len(devices)}</strong>
              </div>
              <div class="devices">{device_html}</div>
              {recent_html}
            </section>
            """
        )

    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # HTML 内置 2 秒刷新，适合直接用浏览器查看 runtime/home_status.html。
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta http-equiv="refresh" content="2">
  <title>智能家居状态看板</title>
  <style>
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "Microsoft YaHei", "Segoe UI", Arial, sans-serif;
      background: #eef2f7;
      color: #0f172a;
    }}
    main {{
      max-width: 1180px;
      margin: 0 auto;
      padding: 32px;
    }}
    header {{
      display: flex;
      align-items: flex-end;
      justify-content: space-between;
      gap: 24px;
      margin-bottom: 22px;
    }}
    h1 {{
      margin: 0 0 8px;
      font-size: 32px;
      letter-spacing: 0;
    }}
    .sub {{
      margin: 0;
      color: #64748b;
      font-size: 15px;
    }}
    .summary {{
      min-width: 250px;
      border-radius: 14px;
      background: #0f172a;
      color: white;
      padding: 18px 20px;
      text-align: right;
    }}
    .summary b {{
      display: block;
      font-size: 30px;
      line-height: 1.1;
    }}
    .summary span {{
      color: #cbd5e1;
      font-size: 14px;
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 18px;
    }}
    .room-card {{
      min-height: 168px;
      border: 1px solid #dbe3ef;
      border-radius: 16px;
      background: #fff;
      padding: 22px;
      box-shadow: 0 12px 30px rgba(15, 23, 42, 0.06);
    }}
    .room-card.active {{
      border-color: #86efac;
      background: #f0fdf4;
    }}
    .room-card.recent {{
      border-color: #f97316;
      box-shadow: 0 0 0 3px rgba(249, 115, 22, 0.16);
    }}
    .room-head {{
      display: flex;
      justify-content: space-between;
      gap: 16px;
      align-items: center;
      margin-bottom: 22px;
    }}
    h2 {{
      margin: 0;
      font-size: 25px;
      letter-spacing: 0;
    }}
    .room-head strong {{
      flex: 0 0 auto;
      border-radius: 999px;
      padding: 7px 12px;
      background: #e2e8f0;
      color: #475569;
      font-size: 15px;
    }}
    .active .room-head strong {{
      background: #dcfce7;
      color: #15803d;
    }}
    .devices {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      min-height: 40px;
    }}
    .devices span {{
      border-radius: 999px;
      background: #dcfce7;
      color: #166534;
      padding: 8px 13px;
      font-weight: 700;
      font-size: 16px;
    }}
    .devices em {{
      color: #94a3b8;
      font-style: normal;
      font-size: 16px;
    }}
    .recent-line {{
      margin-top: 18px;
      color: #ea580c;
      font-weight: 700;
      font-size: 15px;
    }}
    .wide {{
      grid-column: span 3;
    }}
    footer {{
      margin-top: 18px;
      color: #94a3b8;
      font-size: 13px;
    }}
    @media (max-width: 860px) {{
      main {{ padding: 20px; }}
      header {{ display: block; }}
      .summary {{ text-align: left; margin-top: 16px; }}
      .grid {{ grid-template-columns: 1fr; }}
      .wide {{ grid-column: auto; }}
    }}
  </style>
</head>
<body>
  <main>
    <header>
      <div>
        <h1>智能家居状态看板</h1>
        <p class="sub">最近：{last_result} · 状态时间：{updated_at}</p>
      </div>
      <div class="summary">
        <b>{active_count}/{total_count}</b>
        <span>设备正在开启</span>
      </div>
    </header>
    <section class="grid">
      {"".join(cards).replace('<section class="room-card', '<section class="room-card wide', 1)}
    </section>
    <footer>页面每 2 秒自动刷新。生成时间：{generated_at}</footer>
  </main>
</body>
</html>
"""


def write_status_dashboard(
    output_path: Path,
    state: dict,
    devices_by_room: dict[str, list[str]],
    recent_keys: set[tuple[str, str]] | None = None,
) -> Path:
    """写出 HTML 看板文件，并返回输出路径。

    GUI 调用这个函数后，再用 webbrowser 打开返回的路径。
    """

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        render_status_dashboard(state, devices_by_room, recent_keys),
        encoding="utf-8",
    )
    return output_path
