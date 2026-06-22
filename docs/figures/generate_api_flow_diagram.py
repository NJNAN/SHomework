from __future__ import annotations

from pathlib import Path
import textwrap

from PIL import Image, ImageDraw, ImageFont


OUT_DIR = Path(__file__).resolve().parent
PNG_PATH = OUT_DIR / "外部大模型API接入流程架构图.png"

W, H = 1800, 1080
FONT = "C:/Windows/Fonts/msyh.ttc"
FONT_BOLD = "C:/Windows/Fonts/msyhbd.ttc"


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(FONT_BOLD if bold else FONT, size)


def multiline(draw: ImageDraw.ImageDraw, text: str, box_width: int, size: int, bold: bool = False) -> list[str]:
    f = font(size, bold)
    lines: list[str] = []
    for part in text.split("\n"):
        line = ""
        for char in part:
            candidate = line + char
            if draw.textbbox((0, 0), candidate, font=f)[2] <= box_width:
                line = candidate
            else:
                if line:
                    lines.append(line)
                line = char
        lines.append(line)
    return lines


def rounded_box(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int, int, int],
    title: str,
    body: str,
    fill: str,
    outline: str,
    accent: str,
) -> None:
    x1, y1, x2, y2 = xy
    draw.rounded_rectangle(xy, radius=18, fill=fill, outline=outline, width=3)
    draw.rounded_rectangle((x1, y1, x2, y1 + 16), radius=18, fill=accent)
    draw.rectangle((x1, y1 + 8, x2, y1 + 18), fill=accent)

    title_font = font(27, True)
    body_font = font(22)
    draw.text((x1 + 28, y1 + 32), title, fill="#111827", font=title_font)

    lines = multiline(draw, body, x2 - x1 - 56, 22)
    y = y1 + 82
    for line in lines:
        draw.text((x1 + 28, y), line, fill="#374151", font=body_font)
        y += 31


def arrow(
    draw: ImageDraw.ImageDraw,
    start: tuple[int, int],
    end: tuple[int, int],
    color: str = "#475569",
    width: int = 5,
    dashed: bool = False,
) -> None:
    x1, y1 = start
    x2, y2 = end
    if dashed:
        steps = 16
        for i in range(steps):
            if i % 2 == 0:
                sx = x1 + (x2 - x1) * i / steps
                sy = y1 + (y2 - y1) * i / steps
                ex = x1 + (x2 - x1) * (i + 1) / steps
                ey = y1 + (y2 - y1) * (i + 1) / steps
                draw.line((sx, sy, ex, ey), fill=color, width=width)
    else:
        draw.line((x1, y1, x2, y2), fill=color, width=width)

    import math

    angle = math.atan2(y2 - y1, x2 - x1)
    head = 18
    left = (
        x2 - head * math.cos(angle - math.pi / 6),
        y2 - head * math.sin(angle - math.pi / 6),
    )
    right = (
        x2 - head * math.cos(angle + math.pi / 6),
        y2 - head * math.sin(angle + math.pi / 6),
    )
    draw.polygon([end, left, right], fill=color)


def group_label(draw: ImageDraw.ImageDraw, xy: tuple[int, int, int, int], text: str, fill: str) -> None:
    x1, y1, x2, y2 = xy
    draw.rounded_rectangle(xy, radius=24, outline=fill, width=2)
    draw.rounded_rectangle((x1 + 26, y1 - 24, x1 + 190, y1 + 18), radius=14, fill=fill)
    draw.text((x1 + 44, y1 - 18), text, fill="#ffffff", font=font(21, True))


def draw_diagram() -> None:
    img = Image.new("RGB", (W, H), "#f8fafc")
    draw = ImageDraw.Draw(img)

    draw.text((70, 52), "外部大模型 API 接入流程架构", fill="#0f172a", font=font(46, True))
    subtitle = "从用户指令输入，到 API 语义解析、结果校验、结构化意图输出，再到状态同步与看板展示。"
    draw.text((74, 116), subtitle, fill="#475569", font=font(24))

    groups = [
        ((58, 192, 380, 904), "输入层", "#2563eb"),
        ((422, 192, 744, 904), "API 调用层", "#ea580c"),
        ((786, 192, 1108, 904), "外部服务层", "#16a34a"),
        ((1150, 192, 1472, 904), "校验转换层", "#7c3aed"),
        ((1514, 192, 1768, 904), "输出层", "#0891b2"),
    ]
    for rect, label, color in groups:
        group_label(draw, rect, label, color)

    box_w, box_h = 258, 138
    boxes = {
        "user": (90, 260, 90 + box_w, 260 + box_h),
        "entry": (90, 560, 90 + box_w, 560 + box_h),
        "parser": (454, 230, 454 + box_w, 230 + box_h),
        "prompt": (454, 435, 454 + box_w, 435 + box_h),
        "request": (454, 640, 454 + box_w, 640 + box_h),
        "llm": (818, 330, 818 + box_w, 330 + box_h),
        "frame": (818, 610, 818 + box_w, 610 + box_h),
        "decode": (1182, 230, 1182 + box_w, 230 + box_h),
        "validate": (1182, 430, 1182 + box_w, 430 + box_h),
        "fallback": (1182, 675, 1182 + box_w, 675 + box_h),
        "state": (1546, 250, 1546 + 190, 250 + box_h),
        "json": (1546, 460, 1546 + 190, 460 + box_h),
        "view": (1546, 670, 1546 + 190, 670 + box_h),
    }

    rounded_box(draw, boxes["user"], "用户指令输入", "文本输入\n语音识别文本\n控制台命令", "#ffffff", "#93c5fd", "#dbeafe")
    rounded_box(draw, boxes["entry"], "触发 API 解析", "GUI：API模型解析按钮\n命令行：run_console --api", "#ffffff", "#93c5fd", "#dbeafe")

    rounded_box(draw, boxes["parser"], "ApiLLMParser.parse()", "src/api_llm.py\n接收原始中文指令", "#fffaf3", "#fdba74", "#ffedd5")
    rounded_box(draw, boxes["prompt"], "Prompt 约束", "限制 JSON 输出\n限定房间 / 设备 / 动作", "#fffaf3", "#fdba74", "#ffedd5")
    rounded_box(draw, boxes["request"], "请求组装", "model / url / key / timeout\nChat Completions", "#fffaf3", "#fdba74", "#ffedd5")

    rounded_box(draw, boxes["llm"], "外部大模型 API", "DeepSeek 或其他\nOpenAI-compatible 服务", "#f7fff8", "#86efac", "#dcfce7")
    rounded_box(draw, boxes["frame"], "JSON 语义帧", "is_control / intent / scene\ncommands 动作数组", "#f7fff8", "#86efac", "#dcfce7")

    rounded_box(draw, boxes["decode"], "解析 JSON", "_decode_frame()\n兼容少量多余文本", "#fcf8ff", "#c4b5fd", "#ede9fe")
    rounded_box(draw, boxes["validate"], "校验与归一", "_validated_commands()\n白名单过滤编造设备", "#fcf8ff", "#c4b5fd", "#ede9fe")
    rounded_box(draw, boxes["fallback"], "本地兜底", "无效 / 非家居 / API失败\n回退 src/intent_engine.py", "#fcf8ff", "#c4b5fd", "#ede9fe")

    rounded_box(draw, boxes["state"], "状态执行", "state_bridge.py\n执行设备动作", "#f2feff", "#67e8f9", "#cffafe")
    rounded_box(draw, boxes["json"], "状态文件", "runtime/home_state.json\n统一共享数据源", "#f2feff", "#67e8f9", "#cffafe")
    rounded_box(draw, boxes["view"], "结果输出", "GUI / HTML 看板\n大数据侧车分析", "#f2feff", "#67e8f9", "#cffafe")

    arrow(draw, (219, 398), (219, 560), "#2563eb")
    arrow(draw, (348, 629), (454, 299), "#475569")
    arrow(draw, (583, 368), (583, 435), "#ea580c")
    arrow(draw, (583, 573), (583, 640), "#ea580c")
    arrow(draw, (712, 709), (818, 399), "#475569")
    arrow(draw, (947, 468), (947, 610), "#16a34a")
    arrow(draw, (1076, 679), (1182, 299), "#475569")
    arrow(draw, (1311, 368), (1311, 430), "#7c3aed")
    arrow(draw, (1440, 499), (1546, 319), "#475569")
    arrow(draw, (1311, 568), (1311, 675), "#7c3aed", dashed=True)
    arrow(draw, (1440, 744), (1546, 319), "#7c3aed", dashed=True)
    arrow(draw, (1641, 388), (1641, 460), "#0891b2")
    arrow(draw, (1641, 598), (1641, 670), "#0891b2")

    draw.text((1340, 585), "异常路径", fill="#6d28d9", font=font(20, True))
    draw.text((1438, 520), "有效结构化意图", fill="#334155", font=font(20, True), anchor="mm")

    footer = "图示：外部大模型 API 接入的流程架构，展示从用户指令输入到结构化意图输出的完整数据流转链路。"
    wrapped = textwrap.fill(footer, width=64)
    draw.rounded_rectangle((70, 946, 1730, 1016), radius=18, fill="#e2e8f0", outline="#cbd5e1")
    draw.text((98, 966), wrapped, fill="#334155", font=font(24))

    img.save(PNG_PATH, optimize=True)
    print(PNG_PATH)


if __name__ == "__main__":
    draw_diagram()
