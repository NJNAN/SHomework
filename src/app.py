"""Tkinter desktop UI for the smart home control assistant."""

from __future__ import annotations

import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from .intent_engine import ParseResult, SmartHomeIntentEngine
from .state_bridge import DEVICES_BY_ROOM, apply_parse_result, ensure_state_file, load_state
from .trainer import train_all
from .voice_input import VoiceInputError, listen_once


ROOT = Path(__file__).resolve().parents[1]

ROOM_LAYOUT = {
    "卧室": (0.02, 0.04, 0.32, 0.32),
    "卫生间": (0.32, 0.04, 0.58, 0.32),
    "厨房": (0.58, 0.04, 0.98, 0.32),
    "书房": (0.02, 0.32, 0.32, 0.64),
    "餐厅": (0.32, 0.32, 0.66, 0.64),
    "阳台": (0.66, 0.32, 0.98, 0.64),
    "客厅": (0.02, 0.64, 0.98, 0.96),
}


class SmartHomeApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("智能家居控制助手")
        self.geometry("1180x720")
        self.minsize(1060, 660)
        self.configure(bg="#eef2f7")

        self.engine = self._load_engine()
        ensure_state_file()
        self.status_var = tk.StringVar(value="系统已就绪")
        self.command_var = tk.StringVar(value="")
        self.confidence_var = tk.StringVar(value="0%")
        self.location_var = tk.StringVar(value="-")
        self.device_var = tk.StringVar(value="-")
        self.action_var = tk.StringVar(value="-")
        self.intent_var = tk.StringVar(value="等待输入")
        self.home_summary_var = tk.StringVar(value="设备状态加载中")
        self.log_lines: list[str] = []
        self.recent_command_keys: set[tuple[str, str]] = set()

        self._build_style()
        self._build_ui()
        self.refresh_home_panel()

    def _load_engine(self) -> SmartHomeIntentEngine:
        required = [
            ROOT / "models" / "binary_intent_model.joblib",
            ROOT / "models" / "location_model.joblib",
            ROOT / "models" / "device_model.joblib",
            ROOT / "models" / "action_model.joblib",
        ]
        if not all(path.exists() for path in required):
            train_all(ROOT)
        return SmartHomeIntentEngine(ROOT / "models")

    def _build_style(self) -> None:
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TFrame", background="#eef2f7")
        style.configure("Panel.TFrame", background="#ffffff", relief="flat")
        style.configure("Title.TLabel", background="#eef2f7", foreground="#172033", font=("Microsoft YaHei UI", 24, "bold"))
        style.configure("Sub.TLabel", background="#eef2f7", foreground="#64748b", font=("Microsoft YaHei UI", 10))
        style.configure("PanelTitle.TLabel", background="#ffffff", foreground="#172033", font=("Microsoft YaHei UI", 13, "bold"))
        style.configure("Text.TLabel", background="#ffffff", foreground="#334155", font=("Microsoft YaHei UI", 10))
        style.configure("Value.TLabel", background="#ffffff", foreground="#0f172a", font=("Microsoft YaHei UI", 18, "bold"))
        style.configure("Primary.TButton", font=("Microsoft YaHei UI", 10, "bold"), padding=(14, 9), background="#2563eb", foreground="#ffffff")
        style.map("Primary.TButton", background=[("active", "#1d4ed8")])
        style.configure("Soft.TButton", font=("Microsoft YaHei UI", 10), padding=(14, 9), background="#e2e8f0", foreground="#172033")
        style.map("Soft.TButton", background=[("active", "#cbd5e1")])

    def _build_ui(self) -> None:
        header = ttk.Frame(self, padding=(28, 24, 28, 10))
        header.pack(fill="x")
        ttk.Label(header, text="智能家居控制助手", style="Title.TLabel").pack(anchor="w")
        ttk.Label(header, text="支持文本输入、语音输入、意图判断和地点/设备/状态解析", style="Sub.TLabel").pack(anchor="w", pady=(6, 0))

        main = ttk.Frame(self, padding=(28, 10, 28, 18))
        main.pack(fill="both", expand=True)
        main.columnconfigure(0, weight=3)
        main.columnconfigure(1, weight=3)
        main.rowconfigure(0, weight=1)

        left = ttk.Frame(main, style="Panel.TFrame", padding=22)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 14))
        right = ttk.Frame(main, style="Panel.TFrame", padding=22)
        right.grid(row=0, column=1, sticky="nsew")

        ttk.Label(left, text="输入指令", style="PanelTitle.TLabel").pack(anchor="w")
        self.input_box = tk.Text(
            left,
            height=5,
            wrap="word",
            bd=0,
            padx=14,
            pady=14,
            font=("Microsoft YaHei UI", 14),
            bg="#f8fafc",
            fg="#0f172a",
            insertbackground="#2563eb",
            relief="flat",
        )
        self.input_box.pack(fill="x", pady=(14, 12))
        self.input_box.insert("1.0", "打开客厅空调")

        button_row = ttk.Frame(left, style="Panel.TFrame")
        button_row.pack(fill="x", pady=(0, 16))
        ttk.Button(button_row, text="分析指令", style="Primary.TButton", command=self.analyze_text).pack(side="left")
        ttk.Button(button_row, text="语音输入", style="Soft.TButton", command=self.start_voice_thread).pack(side="left", padx=10)
        ttk.Button(button_row, text="清空", style="Soft.TButton", command=self.clear_input).pack(side="left")

        ttk.Label(left, text="执行日志", style="PanelTitle.TLabel").pack(anchor="w", pady=(12, 8))
        self.log_box = tk.Text(
            left,
            height=12,
            wrap="word",
            bd=0,
            padx=14,
            pady=12,
            font=("Consolas", 10),
            bg="#0f172a",
            fg="#dbeafe",
            relief="flat",
            state="disabled",
        )
        self.log_box.pack(fill="both", expand=True)

        ttk.Label(right, text="识别结果", style="PanelTitle.TLabel").pack(anchor="w")
        result_grid = tk.Frame(right, bg="#ffffff")
        result_grid.pack(fill="x", pady=(12, 14))
        result_grid.columnconfigure(0, weight=1)
        result_grid.columnconfigure(1, weight=1)
        self._summary_field(result_grid, 0, 0, "指令类型", self.intent_var, "#2563eb")
        self._summary_field(result_grid, 0, 1, "置信度", self.confidence_var, "#7c3aed")
        self._summary_field(result_grid, 1, 0, "设备位置", self.location_var, "#0891b2")
        self._summary_field(result_grid, 1, 1, "设备名称", self.device_var, "#16a34a")
        self._summary_field(result_grid, 2, 0, "控制状态", self.action_var, "#ea580c", columnspan=2)

        ttk.Label(right, text="2D 家居状态面板", style="PanelTitle.TLabel").pack(anchor="w", pady=(2, 8))
        tk.Label(
            right,
            textvariable=self.home_summary_var,
            bg="#ffffff",
            fg="#64748b",
            font=("Microsoft YaHei UI", 9),
            anchor="w",
        ).pack(fill="x", pady=(0, 8))
        canvas_frame = tk.Frame(right, bg="#f8fafc", highlightthickness=1, highlightbackground="#e2e8f0")
        canvas_frame.pack(fill="both", expand=True)
        self.home_canvas = tk.Canvas(
            canvas_frame,
            width=520,
            height=360,
            bg="#f8fafc",
            bd=0,
            highlightthickness=0,
        )
        self.home_canvas.pack(fill="both", expand=True)
        self.home_canvas.bind("<Configure>", lambda _event: self.refresh_home_panel())

        status = ttk.Frame(self, padding=(28, 0, 28, 18))
        status.pack(fill="x")
        ttk.Label(status, textvariable=self.status_var, style="Sub.TLabel").pack(anchor="w")

    def _result_card(self, parent: ttk.Frame, label: str, variable: tk.StringVar, color: str) -> None:
        frame = tk.Frame(parent, bg="#f8fafc", highlightthickness=1, highlightbackground="#e2e8f0")
        frame.pack(fill="x", pady=(14, 0))
        stripe = tk.Frame(frame, bg=color, width=5)
        stripe.pack(side="left", fill="y")
        inner = tk.Frame(frame, bg="#f8fafc", padx=14, pady=10)
        inner.pack(side="left", fill="both", expand=True)
        tk.Label(inner, text=label, bg="#f8fafc", fg="#64748b", font=("Microsoft YaHei UI", 9)).pack(anchor="w")
        tk.Label(inner, textvariable=variable, bg="#f8fafc", fg="#0f172a", font=("Microsoft YaHei UI", 17, "bold")).pack(anchor="w", pady=(4, 0))

    def _summary_field(
        self,
        parent: tk.Frame,
        row: int,
        column: int,
        label: str,
        variable: tk.StringVar,
        color: str,
        columnspan: int = 1,
    ) -> None:
        frame = tk.Frame(parent, bg="#f8fafc", highlightthickness=1, highlightbackground="#e2e8f0")
        frame.grid(row=row, column=column, columnspan=columnspan, sticky="ew", padx=4, pady=4)
        frame.columnconfigure(1, weight=1)
        tk.Frame(frame, bg=color, width=4).grid(row=0, column=0, sticky="nsw", rowspan=2)
        tk.Label(
            frame,
            text=label,
            bg="#f8fafc",
            fg="#64748b",
            font=("Microsoft YaHei UI", 8),
            anchor="w",
        ).grid(row=0, column=1, sticky="ew", padx=(8, 8), pady=(7, 0))
        tk.Label(
            frame,
            textvariable=variable,
            bg="#f8fafc",
            fg="#0f172a",
            font=("Microsoft YaHei UI", 11, "bold"),
            anchor="w",
            wraplength=210,
        ).grid(row=1, column=1, sticky="ew", padx=(8, 8), pady=(1, 7))

    def refresh_home_panel(self) -> None:
        if not hasattr(self, "home_canvas"):
            return

        state = load_state()
        rooms = state.get("rooms", {})
        active_count = sum(
            1
            for room_devices in rooms.values()
            for is_on in room_devices.values()
            if is_on
        )
        total_count = sum(len(devices) for devices in DEVICES_BY_ROOM.values())
        last_result = state.get("last_result") or "暂无操作"
        self.home_summary_var.set(f"开启 {active_count}/{total_count} 个设备 | 最近：{last_result}")

        canvas = self.home_canvas
        canvas.delete("all")
        width = max(canvas.winfo_width(), 420)
        height = max(canvas.winfo_height(), 320)
        canvas.create_rectangle(0, 0, width, height, fill="#f8fafc", outline="")
        self._draw_home_rooms(canvas, rooms, width, height)
        self._draw_home_legend(canvas, width, height)

    def _draw_home_rooms(self, canvas: tk.Canvas, rooms: dict, width: int, height: int) -> None:
        for room, bounds in ROOM_LAYOUT.items():
            x1 = bounds[0] * width
            y1 = bounds[1] * height
            x2 = bounds[2] * width
            y2 = bounds[3] * height
            devices = DEVICES_BY_ROOM.get(room, [])
            room_state = rooms.get(room, {})
            active_devices = [device for device in devices if room_state.get(device)]
            room_is_active = bool(active_devices)

            fill = "#fff7ed" if room_is_active else "#ffffff"
            outline = "#f97316" if room_is_active else "#cbd5e1"
            canvas.create_rectangle(x1, y1, x2, y2, fill=fill, outline=outline, width=2)
            canvas.create_text(
                x1 + 12,
                y1 + 12,
                text=room,
                anchor="nw",
                fill="#0f172a",
                font=("Microsoft YaHei UI", 10, "bold"),
            )
            canvas.create_text(
                x2 - 10,
                y1 + 13,
                text=f"ON {len(active_devices)}/{len(devices)}",
                anchor="ne",
                fill="#16a34a" if room_is_active else "#94a3b8",
                font=("Consolas", 8, "bold"),
            )
            self._draw_room_devices(canvas, room, devices, room_state, x1, y1, x2, y2)

    def _draw_room_devices(
        self,
        canvas: tk.Canvas,
        room: str,
        devices: list[str],
        room_state: dict,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
    ) -> None:
        room_width = x2 - x1
        columns = 2 if room_width >= 145 else 1
        cell_width = max((room_width - 24) / columns, 70)
        start_y = y1 + 42
        row_gap = 21

        for index, device in enumerate(devices):
            column = index % columns
            row = index // columns
            dot_x = x1 + 12 + column * cell_width
            dot_y = start_y + row * row_gap
            is_on = bool(room_state.get(device))
            is_recent = (room, device) in self.recent_command_keys
            dot_fill = "#22c55e" if is_on else "#cbd5e1"
            dot_outline = "#ea580c" if is_recent else "#ffffff"
            text_fill = "#166534" if is_on else "#475569"

            canvas.create_oval(
                dot_x,
                dot_y,
                dot_x + 10,
                dot_y + 10,
                fill=dot_fill,
                outline=dot_outline,
                width=2 if is_recent else 1,
            )
            canvas.create_text(
                dot_x + 16,
                dot_y + 5,
                text=device,
                anchor="w",
                fill=text_fill,
                font=("Microsoft YaHei UI", 8, "bold" if is_on else "normal"),
            )

    @staticmethod
    def _draw_home_legend(canvas: tk.Canvas, width: int, height: int) -> None:
        y = height - 17
        canvas.create_oval(14, y - 5, 24, y + 5, fill="#22c55e", outline="#ffffff")
        canvas.create_text(30, y, text="开启", anchor="w", fill="#475569", font=("Microsoft YaHei UI", 8))
        canvas.create_oval(74, y - 5, 84, y + 5, fill="#cbd5e1", outline="#ffffff")
        canvas.create_text(90, y, text="关闭", anchor="w", fill="#475569", font=("Microsoft YaHei UI", 8))
        canvas.create_oval(134, y - 5, 144, y + 5, fill="#22c55e", outline="#ea580c", width=2)
        canvas.create_text(150, y, text="本次操作", anchor="w", fill="#475569", font=("Microsoft YaHei UI", 8))

    @staticmethod
    def _intent_label(result: ParseResult) -> str:
        labels = {
            "device_control": "单设备控制",
            "batch_control": "批量控制",
            "scene_mode": "场景模式",
            "environment_control": "环境语义控制",
            "out_of_scope": "非家居控制",
        }
        return labels.get(result.intent, "家居控制")

    def clear_input(self) -> None:
        self.input_box.delete("1.0", "end")
        self.status_var.set("输入框已清空")

    def analyze_text(self) -> None:
        text = self.input_box.get("1.0", "end").strip()
        if not text:
            messagebox.showinfo("提示", "请先输入一句中文指令。")
            return
        result = self.engine.parse(text)
        self.show_result(result)

    def show_result(self, result: ParseResult) -> None:
        self.confidence_var.set(f"{result.confidence * 100:.1f}%")
        if not result.is_control:
            self.intent_var.set(self._intent_label(result))
            self.location_var.set("-")
            self.device_var.set("-")
            self.action_var.set("-")
            self.recent_command_keys = set()
            self.refresh_home_panel()
            reason = result.reason or "这句话不像家居控制指令"
            self.status_var.set(reason)
            self.add_log(f"输入：{result.text}\n结果：{reason}，置信度 {result.confidence * 100:.1f}%")
            return

        self.intent_var.set(self._intent_label(result))
        self.location_var.set(result.location or "-")
        self.device_var.set(result.device or "-")
        self.action_var.set(result.action or "-")
        synced = apply_parse_result(result)
        self.recent_command_keys = {(command.location, command.device) for command in result.commands}
        self.refresh_home_panel()
        summary = result.message or f"{result.location} / {result.device} / {result.action}"
        if synced:
            self.status_var.set(f"已更新家居面板：{summary}")
        else:
            self.status_var.set(f"已解析：{summary}")
        normalized = ""
        if result.normalized_text and result.normalized_text != result.text:
            normalized = f"\n归一化：{result.normalized_text}"
        self.add_log(f"输入：{result.text}{normalized}\n结果：{self._intent_label(result)} | {summary}")

    def add_log(self, text: str) -> None:
        self.log_lines.append(text)
        self.log_lines = self.log_lines[-8:]
        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.insert("1.0", "\n\n".join(self.log_lines))
        self.log_box.configure(state="disabled")

    def start_voice_thread(self) -> None:
        self.status_var.set("正在录音，请说出家居控制指令...")
        thread = threading.Thread(target=self._voice_worker, daemon=True)
        thread.start()

    def _voice_worker(self) -> None:
        try:
            text = listen_once()
        except VoiceInputError as exc:
            self.after(0, lambda: self.status_var.set(str(exc)))
            return
        self.after(0, lambda: self._apply_voice_text(text))

    def _apply_voice_text(self, text: str) -> None:
        self.input_box.delete("1.0", "end")
        self.input_box.insert("1.0", text)
        self.status_var.set("语音识别完成，已自动分析")
        self.analyze_text()


def main() -> None:
    app = SmartHomeApp()
    app.mainloop()


if __name__ == "__main__":
    main()
