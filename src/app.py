"""智能家居控制助手的 Tkinter 桌面界面。

新手阅读提示：
1. Tkinter 是 Python 自带的桌面界面库，可以用来创建窗口、按钮、输入框。
2. 这个文件主要做“界面”和“流程串联”，真正的中文理解逻辑在 intent_engine.py。
3. 用户点击按钮时，Tkinter 会调用 command= 后面绑定的函数。
   例如“分析指令”按钮绑定的是 self.analyze_text。
4. GUI 程序不能让网络请求或录音卡住主窗口，所以 API 和语音功能使用后台线程。
"""

from __future__ import annotations

# threading 用于开后台线程。没有线程时，API 请求或录音会让窗口卡住。
import threading
# tkinter 是 Python 自带 GUI 库；常用别名是 tk。
import tkinter as tk
# webbrowser 用来调用系统默认浏览器打开 HTML 看板。
import webbrowser
from pathlib import Path
from tkinter import messagebox, ttk

from .api_llm import ApiLLMError, ApiLLMParser
from .intent_engine import ParseResult, SmartHomeIntentEngine
from .state_bridge import DEVICES_BY_ROOM, apply_parse_result, ensure_state_file, load_state
from .status_dashboard import write_status_dashboard
from .trainer import train_all
from .voice_input import VoiceInputError, listen_once


ROOT = Path(__file__).resolve().parents[1]


class SmartHomeApp(tk.Tk):
    """主窗口：负责输入、解析按钮、结果展示、日志和状态看板入口。

    tk.Tk 是 Tkinter 的主窗口类。SmartHomeApp 继承它之后，
    就可以直接调用 title、geometry、mainloop 等窗口方法。
    """

    def __init__(self):
        # super().__init__() 先初始化 Tkinter 主窗口，这是继承类常见写法。
        super().__init__()
        self.title("智能家居控制助手")
        self.geometry("1180x720")
        self.minsize(1060, 660)
        self.configure(bg="#eef2f7")
        self.option_add("*Font", "{Microsoft YaHei} 10")

        # 本地解析引擎是默认路径；API 模型和语音输入都是可选增强。
        self.engine = self._load_engine()
        self.api_llm = ApiLLMParser()
        ensure_state_file()

        # StringVar 是 Tkinter 的“界面变量”。
        # Label 绑定 StringVar 后，只要 set 新值，界面文字会自动变化。
        self.status_var = tk.StringVar(value="系统已就绪")
        self.command_var = tk.StringVar(value="")
        self.confidence_var = tk.StringVar(value="0%")
        self.location_var = tk.StringVar(value="-")
        self.device_var = tk.StringVar(value="-")
        self.action_var = tk.StringVar(value="-")
        self.intent_var = tk.StringVar(value="等待输入")
        self.home_summary_var = tk.StringVar(value="设备状态加载中")
        # 保存最近几条日志文本，后面 add_log 会控制最多只留 8 条。
        self.log_lines: list[str] = []
        # 记录本次刚被控制的设备，用于看板上橙色高亮。
        self.recent_command_keys: set[tuple[str, str]] = set()
        # 独立状态看板窗口对象；None 表示还没有打开。
        self.status_window: HomeStatusWindow | None = None
        self.html_dashboard_path = ROOT / "runtime" / "home_status.html"

        # 初始化顺序：先配置样式，再创建控件，最后读取状态刷新看板。
        self._build_style()
        self._build_ui()
        self.refresh_home_panel()

    def _load_engine(self) -> SmartHomeIntentEngine:
        """加载本地模型；模型缺失时先自动训练，保证首次运行可用。

        required 列表里放的是程序启动必须存在的 4 个模型文件。
        如果缺少任何一个，就调用 train_all(ROOT) 重新生成数据并训练模型。
        """

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
        """统一配置 Tkinter/ttk 控件样式，避免各处重复设置颜色字体。

        ttk.Style 类似一个简单的“样式表”。
        例如 Primary.TButton 代表主要按钮样式，后面创建按钮时直接引用。
        """

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TFrame", background="#eef2f7")
        style.configure("Panel.TFrame", background="#ffffff", relief="flat")
        style.configure("Title.TLabel", background="#eef2f7", foreground="#172033", font=("Microsoft YaHei", 24, "bold"))
        style.configure("Sub.TLabel", background="#eef2f7", foreground="#64748b", font=("Microsoft YaHei", 10))
        style.configure("PanelTitle.TLabel", background="#ffffff", foreground="#172033", font=("Microsoft YaHei", 13, "bold"))
        style.configure("Text.TLabel", background="#ffffff", foreground="#334155", font=("Microsoft YaHei", 10))
        style.configure("Value.TLabel", background="#ffffff", foreground="#0f172a", font=("Microsoft YaHei", 18, "bold"))
        style.configure("Primary.TButton", font=("Microsoft YaHei", 10, "bold"), padding=(14, 9), background="#2563eb", foreground="#ffffff")
        style.map("Primary.TButton", background=[("active", "#1d4ed8")])
        style.configure("Soft.TButton", font=("Microsoft YaHei", 10), padding=(14, 9), background="#e2e8f0", foreground="#172033")
        style.map("Soft.TButton", background=[("active", "#cbd5e1")])

    def _build_ui(self) -> None:
        """搭建主界面布局：左侧输入与日志，右侧解析结果与看板入口。

        Tkinter 布局常见方法：
        - pack：按上下左右顺序摆放。
        - grid：按行列网格摆放。
        本文件中主区域用 grid 分左右两栏，栏内控件多数用 pack。
        """

        header = ttk.Frame(self, padding=(28, 24, 28, 10))
        header.pack(fill="x")
        ttk.Label(header, text="智能家居控制助手", style="Title.TLabel").pack(anchor="w")
        ttk.Label(header, text="支持文本输入、语音输入、意图判断和地点/设备/状态解析", style="Sub.TLabel").pack(anchor="w", pady=(6, 0))

        main = ttk.Frame(self, padding=(28, 10, 28, 18))
        main.pack(fill="both", expand=True)
        # weight 表示窗口变大时这一列/行跟着扩展的比例。
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
            font=("Microsoft YaHei", 14),
            bg="#f8fafc",
            fg="#0f172a",
            insertbackground="#2563eb",
            relief="flat",
        )
        self.input_box.pack(fill="x", pady=(14, 12))
        self.input_box.insert("1.0", "打开客厅空调")

        button_row = ttk.Frame(left, style="Panel.TFrame")
        button_row.pack(fill="x", pady=(0, 16))
        # command=... 表示点击按钮时调用哪个函数。
        # 这是 GUI 程序的核心：用户操作 -> 回调函数 -> 更新界面/状态。
        ttk.Button(button_row, text="分析指令", style="Primary.TButton", command=self.analyze_text).pack(side="left")
        ttk.Button(button_row, text="API模型解析", style="Soft.TButton", command=self.analyze_with_api_model).pack(side="left", padx=(10, 0))
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

        ttk.Label(right, text="家居状态看板", style="PanelTitle.TLabel").pack(anchor="w", pady=(12, 6))
        tk.Label(
            right,
            textvariable=self.home_summary_var,
            bg="#ffffff",
            fg="#64748b",
            font=("Microsoft YaHei", 11),
            anchor="w",
            wraplength=450,
        ).pack(fill="x", pady=(0, 12))

        dashboard_box = tk.Frame(right, bg="#f8fafc", highlightthickness=1, highlightbackground="#e2e8f0", padx=18, pady=18)
        dashboard_box.pack(fill="x")
        tk.Label(
            dashboard_box,
            text="状态详情已移到独立看板，避免主窗口右侧拥挤和文字裁切。",
            bg="#f8fafc",
            fg="#334155",
            font=("Microsoft YaHei", 11),
            anchor="w",
            justify="left",
            wraplength=430,
        ).pack(fill="x")
        dashboard_buttons = tk.Frame(dashboard_box, bg="#f8fafc")
        dashboard_buttons.pack(fill="x", pady=(16, 0))
        ttk.Button(
            dashboard_buttons,
            text="打开状态看板",
            style="Primary.TButton",
            command=self.open_status_window,
        ).pack(side="left")
        ttk.Button(
            dashboard_buttons,
            text="打开 HTML 看板",
            style="Soft.TButton",
            command=self.open_html_dashboard,
        ).pack(side="left", padx=(10, 0))

        status = ttk.Frame(self, padding=(28, 0, 28, 18))
        status.pack(fill="x")
        ttk.Label(status, textvariable=self.status_var, style="Sub.TLabel").pack(anchor="w")

    def _result_card(self, parent: ttk.Frame, label: str, variable: tk.StringVar, color: str) -> None:
        """旧版结果卡片样式，保留给后续界面调整复用。"""

        frame = tk.Frame(parent, bg="#f8fafc", highlightthickness=1, highlightbackground="#e2e8f0")
        frame.pack(fill="x", pady=(14, 0))
        stripe = tk.Frame(frame, bg=color, width=5)
        stripe.pack(side="left", fill="y")
        inner = tk.Frame(frame, bg="#f8fafc", padx=14, pady=10)
        inner.pack(side="left", fill="both", expand=True)
        tk.Label(inner, text=label, bg="#f8fafc", fg="#64748b", font=("Microsoft YaHei", 9)).pack(anchor="w")
        tk.Label(inner, textvariable=variable, bg="#f8fafc", fg="#0f172a", font=("Microsoft YaHei", 17, "bold")).pack(anchor="w", pady=(4, 0))

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
        """创建右侧“指令类型/置信度/位置/设备/动作”的小字段块。"""

        frame = tk.Frame(parent, bg="#f8fafc", highlightthickness=1, highlightbackground="#e2e8f0")
        frame.grid(row=row, column=column, columnspan=columnspan, sticky="ew", padx=4, pady=4)
        frame.columnconfigure(1, weight=1)
        tk.Frame(frame, bg=color, width=4).grid(row=0, column=0, sticky="nsw", rowspan=2)
        tk.Label(
            frame,
            text=label,
            bg="#f8fafc",
            fg="#64748b",
            font=("Microsoft YaHei", 8),
            anchor="w",
        ).grid(row=0, column=1, sticky="ew", padx=(8, 8), pady=(7, 0))
        tk.Label(
            frame,
            textvariable=variable,
            bg="#f8fafc",
            fg="#0f172a",
            font=("Microsoft YaHei", 11, "bold"),
            anchor="w",
            wraplength=210,
        ).grid(row=1, column=1, sticky="ew", padx=(8, 8), pady=(1, 7))

    def refresh_home_panel(self) -> None:
        """从共享状态文件刷新 GUI 摘要、弹窗看板和 HTML 看板。

        每次成功解析并执行指令后都要调用它。
        它做三件事：
        1. 读取 runtime/home_state.json。
        2. 更新右侧“开启几个设备”的摘要。
        3. 重新生成 HTML 看板；如果弹窗看板开着，也刷新弹窗。
        """

        state = load_state()
        self.home_summary_var.set(self._home_state_summary(state))
        write_status_dashboard(
            self.html_dashboard_path,
            state,
            DEVICES_BY_ROOM,
            self.recent_command_keys,
        )
        if self.status_window is not None and self.status_window.winfo_exists():
            self.status_window.refresh(state, self.recent_command_keys)

    @staticmethod
    def _home_state_summary(state: dict) -> str:
        """统计当前开启设备数量，并生成状态栏摘要。

        active_count：当前处于开启状态的设备数量。
        total_count：系统支持的设备总数量。
        """

        rooms = state.get("rooms", {})
        active_count = sum(
            1
            for room_devices in rooms.values()
            for is_on in room_devices.values()
            if is_on
        )
        total_count = sum(len(devices) for devices in DEVICES_BY_ROOM.values())
        last_result = state.get("last_result") or "暂无操作"
        return f"开启 {active_count}/{total_count} 个设备 | 最近：{last_result}"

    def open_status_window(self) -> None:
        """打开或激活独立 Tkinter 状态看板窗口。

        如果窗口已经打开，就不重复创建，而是刷新并把它提到前面。
        这样可以避免用户连续点击按钮打开很多重复窗口。
        """

        state = load_state()
        if self.status_window is not None and self.status_window.winfo_exists():
            self.status_window.refresh(state, self.recent_command_keys)
            self.status_window.lift()
            self.status_window.focus_force()
            return
        self.status_window = HomeStatusWindow(self)
        self.status_window.refresh(state, self.recent_command_keys)

    def open_html_dashboard(self) -> None:
        """生成并用浏览器打开 runtime/home_status.html 状态看板。"""

        state = load_state()
        path = write_status_dashboard(
            self.html_dashboard_path,
            state,
            DEVICES_BY_ROOM,
            self.recent_command_keys,
        )
        webbrowser.open(path.resolve().as_uri())
        self.status_var.set(f"已打开 HTML 状态看板：{path}")

    @staticmethod
    def _intent_label(result: ParseResult) -> str:
        """把解析结果中的内部意图代码显示成中文。"""

        labels = {
            "device_control": "单设备控制",
            "batch_control": "批量控制",
            "scene_mode": "场景模式",
            "environment_control": "环境语义控制",
            "out_of_scope": "非家居控制",
        }
        return labels.get(result.intent, "家居控制")

    def clear_input(self) -> None:
        """清空输入框。"""

        self.input_box.delete("1.0", "end")
        self.status_var.set("输入框已清空")

    def analyze_text(self) -> None:
        """使用本地规则和机器学习模型解析输入框文本。

        流程：
        1. 从输入框取出文本。
        2. 调用 self.engine.parse(text) 得到 ParseResult。
        3. 调用 show_result 把结果显示出来，并尝试更新状态文件。
        """

        text = self.input_box.get("1.0", "end").strip()
        if not text:
            messagebox.showinfo("提示", "请先输入一句中文指令。")
            return
        result = self.engine.parse(text)
        self.show_result(result)

    def analyze_with_api_model(self) -> None:
        """异步调用 API 模型解析，避免网络请求卡住界面。

        “异步”在这里的意思是：主窗口继续响应用户操作，
        API 请求放到另一个线程里慢慢执行。
        """

        text = self.input_box.get("1.0", "end").strip()
        if not text:
            messagebox.showinfo("提示", "请先输入一句中文指令。")
            return
        self.status_var.set(f"正在调用 API 模型 {self.api_llm.config.model} ...")
        # daemon=True 表示主程序退出时后台线程也跟着结束。
        thread = threading.Thread(target=self._api_llm_worker, args=(text,), daemon=True)
        thread.start()

    def _api_llm_worker(self, text: str) -> None:
        """后台线程执行 API 请求，结果通过 after 切回主线程更新 UI。

        Tkinter 有一个限制：界面控件最好只在主线程更新。
        所以后台线程拿到结果后，不能直接改界面，要用 self.after(...) 安排主线程执行。
        """

        try:
            result = self.api_llm.parse(text, fallback_engine=self.engine)
        except ApiLLMError as exc:
            self.after(0, lambda: self._show_api_llm_error(str(exc)))
            return
        self.after(0, lambda: self._apply_api_llm_result(result))

    def _apply_api_llm_result(self, result: ParseResult) -> None:
        """把 API 模型解析结果应用到界面和状态文件。"""

        self.show_result(result)
        self.status_var.set(f"API 模型 {self.api_llm.config.model} 解析完成")

    def _show_api_llm_error(self, message: str) -> None:
        """统一展示 API 不可用、Key 缺失或网络失败的提示。"""

        detail = (
            f"{message} 请确认已设置 DEEPSEEK_API_KEY，"
            f"当前模型：{self.api_llm.config.model}"
        )
        self.status_var.set(detail)
        messagebox.showwarning("API 模型不可用", detail)

    def show_result(self, result: ParseResult) -> None:
        """把解析结果显示到右侧面板，并同步写入家居状态文件。

        这是 GUI 和业务逻辑连接最紧的一步：
        - 如果不是家居控制，只显示拒识原因，不改状态。
        - 如果是家居控制，调用 apply_parse_result 修改 runtime/home_state.json。
        - 修改完成后刷新 GUI 看板和 HTML 看板。
        """

        self.confidence_var.set(f"{result.confidence * 100:.1f}%")
        if not result.is_control:
            # 非家居指令没有地点、设备、动作，所以界面上清空这些字段。
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

        # 只有可控制指令才会写入 runtime/home_state.json，并触发看板刷新。
        self.intent_var.set(self._intent_label(result))
        self.location_var.set(result.location or "-")
        self.device_var.set(result.device or "-")
        self.action_var.set(result.action or "-")
        synced = apply_parse_result(result)
        # recent_command_keys 是 {(房间, 设备)} 形式，给看板用来标记“刚刚操作过”。
        self.recent_command_keys = {(command.location, command.device) for command in result.commands}
        self.refresh_home_panel()
        summary = result.message or f"{result.location} / {result.device} / {result.action}"
        if synced:
            self.status_var.set(f"已更新家居状态：{summary}")
        else:
            self.status_var.set(f"已解析：{summary}")
        normalized = ""
        if result.normalized_text and result.normalized_text != result.text:
            normalized = f"\n归一化：{result.normalized_text}"
        self.add_log(f"输入：{result.text}{normalized}\n结果：{self._intent_label(result)} | {summary}")

    def add_log(self, text: str) -> None:
        """维护最近 8 条执行日志，防止日志框无限增长。

        Text 控件设置成 disabled 后不能编辑，所以写日志前临时改成 normal，
        写完再改回 disabled，避免用户误改日志内容。
        """

        self.log_lines.append(text)
        self.log_lines = self.log_lines[-8:]
        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.insert("1.0", "\n\n".join(self.log_lines))
        self.log_box.configure(state="disabled")

    def start_voice_thread(self) -> None:
        """启动语音识别后台线程，避免录音过程阻塞 GUI。

        录音会等待用户说话，如果放在主线程，整个窗口会像“假死”一样不能点击。
        """

        self.status_var.set("正在录音，请说出家居控制指令...")
        thread = threading.Thread(target=self._voice_worker, daemon=True)
        thread.start()

    def _voice_worker(self) -> None:
        """后台录音并调用语音识别服务。"""

        try:
            text = listen_once()
        except VoiceInputError as exc:
            self.after(0, lambda: self.status_var.set(str(exc)))
            return
        self.after(0, lambda: self._apply_voice_text(text))

    def _apply_voice_text(self, text: str) -> None:
        """把语音识别文本填入输入框，并复用本地文本解析流程。"""

        self.input_box.delete("1.0", "end")
        self.input_box.insert("1.0", text)
        self.status_var.set("语音识别完成，已自动分析")
        self.analyze_text()


class HomeStatusWindow(tk.Toplevel):
    """独立状态看板窗口，按房间显示各设备开关状态。

    tk.Toplevel 表示“子窗口”。它不是主窗口，但依附于主窗口存在。
    """

    def __init__(self, parent: SmartHomeApp):
        super().__init__(parent)
        self.parent = parent
        self.title("家居状态看板")
        self.geometry("980x680")
        self.minsize(860, 580)
        self.configure(bg="#eef2f7")
        self.option_add("*Font", "{Microsoft YaHei} 10")
        self.summary_var = tk.StringVar(value="状态加载中")
        self.room_cards: dict[str, dict[str, tk.Widget]] = {}
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._build_ui()

    def _build_ui(self) -> None:
        """搭建状态看板的房间网格。"""

        header = tk.Frame(self, bg="#eef2f7", padx=26, pady=22)
        header.pack(fill="x")
        tk.Label(
            header,
            text="家居状态看板",
            bg="#eef2f7",
            fg="#0f172a",
            font=("Microsoft YaHei", 24, "bold"),
            anchor="w",
        ).pack(anchor="w")
        tk.Label(
            header,
            textvariable=self.summary_var,
            bg="#eef2f7",
            fg="#64748b",
            font=("Microsoft YaHei", 12),
            anchor="w",
        ).pack(anchor="w", pady=(6, 0))

        grid = tk.Frame(self, bg="#eef2f7", padx=20, pady=0)
        grid.pack(fill="both", expand=True, pady=(0, 22))
        self.grid_frame = grid
        for column in range(2):
            grid.columnconfigure(column, weight=1, uniform="status_column")
        for row in range(4):
            grid.rowconfigure(row, weight=1, uniform="status_row", minsize=120)

        layout = [
            ("客厅", 0, 0, 2),
            ("卧室", 1, 0, 1),
            ("书房", 1, 1, 1),
            ("厨房", 2, 0, 1),
            ("餐厅", 2, 1, 1),
            ("卫生间", 3, 0, 1),
            ("阳台", 3, 1, 1),
        ]
        for room, row, column, columnspan in layout:
            self._create_room_card(room, row, column, columnspan)

    def _create_room_card(self, room: str, row: int, column: int, columnspan: int) -> None:
        """创建单个房间卡片，后续 refresh 只更新文字和颜色。"""

        frame = tk.Frame(
            self.grid_frame,
            bg="#ffffff",
            highlightthickness=1,
            highlightbackground="#dbe3ef",
            padx=20,
            pady=16,
        )
        frame.grid(row=row, column=column, columnspan=columnspan, sticky="nsew", padx=8, pady=8)
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=0)
        frame.rowconfigure(1, weight=1)

        name_label = tk.Label(
            frame,
            text=room,
            bg="#ffffff",
            fg="#0f172a",
            font=("Microsoft YaHei", 19, "bold"),
            anchor="w",
        )
        name_label.grid(row=0, column=0, sticky="ew")

        count_label = tk.Label(
            frame,
            text="开启 0/0",
            bg="#f1f5f9",
            fg="#64748b",
            font=("Microsoft YaHei", 12, "bold"),
            padx=12,
            pady=6,
        )
        count_label.grid(row=0, column=1, sticky="ne", padx=(14, 0))

        devices_label = tk.Label(
            frame,
            text="全部关闭",
            bg="#ffffff",
            fg="#94a3b8",
            font=("Microsoft YaHei", 14),
            anchor="nw",
            justify="left",
            wraplength=620 if columnspan > 1 else 330,
        )
        devices_label.grid(row=1, column=0, columnspan=2, sticky="nsew", pady=(18, 0))

        recent_label = tk.Label(
            frame,
            text="",
            bg="#ffffff",
            fg="#ea580c",
            font=("Microsoft YaHei", 11, "bold"),
            anchor="w",
            justify="left",
            wraplength=620 if columnspan > 1 else 330,
        )
        recent_label.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(10, 0))

        self.room_cards[room] = {
            "frame": frame,
            "name": name_label,
            "count": count_label,
            "devices": devices_label,
            "recent": recent_label,
        }

    def refresh(self, state: dict | None = None, recent_keys: set[tuple[str, str]] | None = None) -> None:
        """根据最新状态刷新每个房间卡片。

        state 是从 runtime/home_state.json 读出来的当前状态。
        recent_keys 是本次刚操作的设备，用于显示“本次操作”。
        """

        state = state or load_state()
        recent_keys = recent_keys or set()
        self.summary_var.set(SmartHomeApp._home_state_summary(state))
        rooms = state.get("rooms", {})
        for room, widgets in self.room_cards.items():
            devices = DEVICES_BY_ROOM.get(room, [])
            room_state = rooms.get(room, {})
            # active_devices：这个房间当前处于开启状态的设备。
            active_devices = [device for device in devices if room_state.get(device)]
            # recent_devices：这个房间本次刚被控制过的设备。
            recent_devices = [device for device in devices if (room, device) in recent_keys]
            self._update_room_card(widgets, active_devices, recent_devices, len(devices))

    @staticmethod
    def _update_room_card(
        widgets: dict[str, tk.Widget],
        active_devices: list[str],
        recent_devices: list[str],
        total_devices: int,
    ) -> None:
        """更新房间卡片的开启数量、开启设备列表和本次操作高亮。

        这里没有重新创建控件，只是修改已有 Label/Frame 的文字和颜色。
        这样刷新更快，也不会导致窗口闪烁。
        """

        frame = widgets["frame"]
        labels = [widgets["name"], widgets["devices"], widgets["recent"]]
        is_active = bool(active_devices)
        has_recent = bool(recent_devices)
        bg = "#f0fdf4" if is_active else "#ffffff"
        border = "#f97316" if has_recent else ("#22c55e" if is_active else "#dbe3ef")

        frame.configure(bg=bg, highlightbackground=border, highlightthickness=2 if has_recent else 1)
        for label in labels:
            label.configure(bg=bg)

        widgets["count"].configure(
            text=f"开启 {len(active_devices)}/{total_devices}",
            bg="#dcfce7" if is_active else "#f1f5f9",
            fg="#15803d" if is_active else "#64748b",
        )
        if active_devices:
            widgets["devices"].configure(
                text="开启：" + "、".join(active_devices),
                fg="#166534",
                font=("Microsoft YaHei", 14, "bold"),
            )
        else:
            widgets["devices"].configure(
                text="全部关闭",
                fg="#94a3b8",
                font=("Microsoft YaHei", 14),
            )

        if has_recent:
            widgets["recent"].configure(text="本次操作：" + "、".join(recent_devices))
        else:
            widgets["recent"].configure(text="")

    def _on_close(self) -> None:
        """关闭弹窗时清空主窗口保存的引用。"""

        self.parent.status_window = None
        self.destroy()


def main() -> None:
    """创建并启动 Tkinter 主循环。"""

    app = SmartHomeApp()
    app.mainloop()


if __name__ == "__main__":
    main()
