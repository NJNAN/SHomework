"""Tkinter desktop UI for the smart home control assistant."""

from __future__ import annotations

import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from .intent_engine import ParseResult, SmartHomeIntentEngine
from .trainer import train_all
from .voice_input import VoiceInputError, listen_once


ROOT = Path(__file__).resolve().parents[1]


class SmartHomeApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("智能家居控制助手")
        self.geometry("980x640")
        self.minsize(900, 580)
        self.configure(bg="#eef2f7")

        self.engine = self._load_engine()
        self.status_var = tk.StringVar(value="系统已就绪")
        self.command_var = tk.StringVar(value="")
        self.confidence_var = tk.StringVar(value="0%")
        self.location_var = tk.StringVar(value="-")
        self.device_var = tk.StringVar(value="-")
        self.action_var = tk.StringVar(value="-")
        self.intent_var = tk.StringVar(value="等待输入")
        self.log_lines: list[str] = []

        self._build_style()
        self._build_ui()

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
        main.columnconfigure(1, weight=2)
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
        self._result_card(right, "指令类型", self.intent_var, "#2563eb")
        self._result_card(right, "设备位置", self.location_var, "#0891b2")
        self._result_card(right, "设备名称", self.device_var, "#16a34a")
        self._result_card(right, "控制状态", self.action_var, "#ea580c")
        self._result_card(right, "二分类置信度", self.confidence_var, "#7c3aed")

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
            self.intent_var.set("非家居控制")
            self.location_var.set("-")
            self.device_var.set("-")
            self.action_var.set("-")
            self.status_var.set("这句话不像家居控制指令")
            self.add_log(f"输入：{result.text}\n结果：非家居控制，置信度 {result.confidence * 100:.1f}%")
            return

        self.intent_var.set("家居控制")
        self.location_var.set(result.location or "-")
        self.device_var.set(result.device or "-")
        self.action_var.set(result.action or "-")
        action_text = "开启" if result.action == "打开" else "关闭"
        self.status_var.set(f"已解析：{result.location} / {result.device} / {action_text}")
        self.add_log(
            f"输入：{result.text}\n"
            f"结果：家居控制 | 地点={result.location} | 设备={result.device} | 状态={action_text}"
        )

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
