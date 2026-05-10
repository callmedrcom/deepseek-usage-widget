"""DeepSeek Usage Monitor — 桌面悬浮窗主程序"""
import tkinter as tk
from tkinter import ttk
import tkinter.font as tkfont
import json
import sys
import threading
import os
from datetime import datetime, date

from .models import CONFIG_DIR, CONFIG_FILE, DEFAULT_CONFIG, THEME, MODEL_META, LOGO_FILE, logger
from .api_client import DeepSeekAPI, _aggregate_usage, _parse_csv_zip, _parse_deepseek_csv
from .config import load_config, save_config, load_daily_history, save_daily_history, merge_daily_history
from .utils import _short_date, _chart_date, _load_local_zip, _api_error_msg

_AF = None

def _available_fonts():
    return {f.lower() for f in tkfont.families()}

def _font(size=10, bold=False, fixed=False):
    global _AF
    if _AF is None:
        _AF = _available_fonts()
    if fixed:
        candidates = ["Consolas", "Cascadia Code", "Courier New", "monospace"]
    else:
        candidates = ["Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI", "Tahoma", "sans-serif"]
    weight = "bold" if bold else "normal"
    for name in candidates:
        if name.lower() in _AF:
            return (name, size, weight)
    return ("TkDefaultFont", size, weight)

class SettingsWindow(tk.Toplevel):
    def __init__(self, master, config, on_save, on_save_error):
        super().__init__(master)
        self.config = config
        self.on_save = on_save
        self.on_save_error = on_save_error
        self.title("DeepSeek Monitor — 设置")
        self.configure(bg=THEME["bg"])
        self.resizable(False, False)
        self.transient(master)

        w, h = 480, 520
        x = master.winfo_x() + (master.winfo_width() - w) // 2
        y = master.winfo_y() + (master.winfo_height() - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")

        self._build_ui()
        self.grab_set()
        self.focus_force()

    def _build_ui(self):
        root = self.master

        # API Key
        self._section("API Key")
        key_frame = tk.Frame(self, bg=THEME["bg"])
        key_frame.pack(fill="x", padx=18, pady=(0, 6))
        self.key_var = tk.StringVar(master=root, value=self.config.get("api_key", ""))
        self.key_entry = tk.Entry(key_frame, textvariable=self.key_var, show="*",
                                  bg=THEME["card"], fg=THEME["fg"],
                                  insertbackground=THEME["fg"],
                                  font=_font(10, fixed=True), relief="flat", bd=8)
        self.key_entry.pack(side="left", fill="x", expand=True)
        self._show_btn = tk.Button(key_frame, text="Show", width=5,
                                   bg=THEME["surface0"], fg=THEME["fg"],
                                   relief="flat", cursor="hand2", bd=0,
                                   font=_font(9),
                                   command=self._toggle_key_visibility)
        self._show_btn.pack(side="right", padx=(4, 0))

        # 刷新间隔
        self._section("刷新间隔（秒）")
        self.interval_var = tk.IntVar(master=root, value=self.config.get("refresh_interval", 60))
        tk.Scale(self, from_=10, to=600, orient="horizontal",
                 variable=self.interval_var, length=420, resolution=10,
                 bg=THEME["bg"], fg=THEME["fg"], highlightbackground=THEME["bg"],
                 troughcolor=THEME["card"], activebackground=THEME["accent"],
                 bd=0).pack(fill="x", padx=18)

        # 透明度
        self._section("窗口透明度")
        self.opacity_var = tk.DoubleVar(master=root, value=self.config.get("opacity", 0.90))
        tk.Scale(self, from_=0.3, to=1.0, orient="horizontal",
                 variable=self.opacity_var, length=420, resolution=0.05,
                 bg=THEME["bg"], fg=THEME["fg"], highlightbackground=THEME["bg"],
                 troughcolor=THEME["card"], activebackground=THEME["accent"],
                 bd=0).pack(fill="x", padx=18)

        # 默认计费模型
        self._section("默认计费模型")
        models = list(self.config.get("model_pricing", {}).keys())
        self.model_var = tk.StringVar(master=root,
                                      value=self.config.get("default_model", models[0] if models else ""))
        opt = tk.OptionMenu(self, self.model_var, *models)
        opt.configure(bg=THEME["card"], fg=THEME["fg"], relief="flat",
                      highlightthickness=0, bd=0, activebackground=THEME["surface0"])
        opt["menu"].configure(bg=THEME["card"], fg=THEME["fg"], bd=0)
        opt.pack(anchor="w", padx=18)

        # 定价参考
        pricing = self.config.get("model_pricing", {})
        lines = ["定价参考 (¥ / 百万 tokens):"]
        for model, rates in pricing.items():
            lines.append(f"  {model}: 输入 ¥{rates['input']} / 输出 ¥{rates['output']}")
        tk.Label(self, text="\n".join(lines),
                 bg=THEME["bg"], fg=THEME["dim"],
                 font=_font(9), justify="left"
                 ).pack(anchor="w", padx=22, pady=(6, 8))

        # 按钮
        btn_frame = tk.Frame(self, bg=THEME["bg"])
        btn_frame.pack(fill="x", padx=18, pady=(4, 14))
        tk.Button(btn_frame, text="保存", command=self._save,
                  bg=THEME["accent"], fg="#ffffff", relief="flat",
                  font=_font(11, bold=True), cursor="hand2",
                  padx=24, pady=6, bd=0, activebackground=THEME["accent"]
                  ).pack(side="right", padx=6)
        tk.Button(btn_frame, text="取消", command=self.destroy,
                  bg=THEME["surface0"], fg=THEME["fg"], relief="flat",
                  font=_font(11), cursor="hand2",
                  padx=24, pady=6, bd=0, activebackground=THEME["dim"]
                  ).pack(side="right", padx=6)

    def _section(self, text):
        tk.Label(self, text=text, bg=THEME["bg"], fg=THEME["accent"],
                 font=_font(11, bold=True)
                 ).pack(anchor="w", padx=18, pady=(10, 2))

    def _toggle_key_visibility(self):
        if self.key_entry.cget("show") == "*":
            self.key_entry.configure(show="")
            self._show_btn.configure(text="Hide")
        else:
            self.key_entry.configure(show="*")
            self._show_btn.configure(text="Show")

    def _save(self):
        self.config["api_key"] = self.key_var.get().strip()
        self.config["refresh_interval"] = self.interval_var.get()
        self.config["opacity"] = self.opacity_var.get()
        self.config["default_model"] = self.model_var.get()
        try:
            save_config(self.config)
            self.on_save()
        except Exception as e:
            self.on_save_error(str(e))
        self.destroy()

class DeepSeekWidget(tk.Tk):
    def __init__(self):
        super().__init__()

        self.config = load_config()
        self.api = DeepSeekAPI(self.config)

        # 数据状态
        self.balance_data = None
        self.balance_error = None
        self.usage_data = None       # 聚合后的用量
        self.usage_error = None
        self.last_refresh = None

        # 今日用量
        self.today_input = 0
        self.today_output = 0
        self.today_calls = 0
        self.today_cost = 0.0
        self.by_model = {}
        self.selected_date = date.today().isoformat()
        self.daily_history = merge_daily_history(load_daily_history())
        self.month_cost = 0.0
        self.month_calls = 0
        self.month_tokens = 0

        # TPM
        self._prev_total_tokens = 0
        self._prev_refresh_time = None
        self._current_tpm = 0
        self._tpm_samples = []
        self._brand_logo = self._load_brand_logo()

        # 窗口
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.attributes("-alpha", self.config.get("opacity", 0.90))
        self.configure(bg=THEME["bg"])
        self._position_window()

        # UI
        self._build_ui()
        self._build_context_menu()
        self._bind_events()
        self.after_idle(self._fit_window_to_content)

        # 定时刷新
        self._refresh_lock = threading.Lock()
        self._refresh_job_id = None
        self._settings_window = None
        self._closing = False
        self._initial_fit_done = False
        self.refresh_interval_ms = self.config.get("refresh_interval", 60) * 1000
        self.after(500, self._schedule_refresh)

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── 窗口定位 ──────────────────────────────────────────
    def _position_window(self):
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        ww = 940
        wh = min(780, sh - 90)
        wh = max(736, wh)
        self.geometry(f"{ww}x{wh}+{sw - ww - 20}+{sh - wh - 70}")

    def _fit_window_to_content(self):
        if self._closing:
            return
        self.update_idletasks()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        current_width = self.winfo_width()
        current_height = self.winfo_height()
        current_x = self.winfo_x()
        current_y = self.winfo_y()
        required_height = max(self.left_panel.winfo_reqheight(), self.right_panel.winfo_reqheight()) + 32
        required_width = self.left_panel.winfo_reqwidth() + self.right_panel.winfo_reqwidth() + 80
        target_height = max(680, current_height, min(sh - 70, required_height))
        width = max(940, current_width, min(sw - 40, required_width))
        if target_height <= current_height + 16 and abs(width - current_width) < 2:
            return
        if abs(target_height - current_height) < 2 and abs(width - current_width) < 2:
            return
        if current_x > 0:
            x = min(current_x - max(0, width - current_width), sw - width - 20)
        else:
            x = sw - width - 20
        if current_y > 0:
            y = min(current_y - max(0, target_height - current_height), sh - target_height - 70)
        else:
            y = sh - target_height - 70
        self.geometry(f"{width}x{target_height}+{x}+{max(10, y)}")

    # ── UI 构建 ───────────────────────────────────────────
    def _build_ui(self):
        shell = tk.Frame(self, bg=THEME["bg"])
        shell.pack(fill="both", expand=True, padx=12, pady=12)

        left_shell = self._panel_shell(shell)
        left_shell.pack(side="left", fill="both", expand=True, padx=(0, 8))
        self.left_panel = left_shell.body
        right_shell = self._panel_shell(shell)
        right_shell.pack(side="left", fill="both", expand=True, padx=(8, 0))
        self.right_panel = right_shell.body

        self._build_left_panel()
        self._build_right_panel()

    def _build_left_panel(self):
        header = tk.Frame(self.left_panel, bg=THEME["shell"], padx=14, pady=10)
        header.pack(fill="x")
        brand = tk.Frame(header, bg=THEME["shell"])
        brand.pack(side="left")
        if self._brand_logo is not None:
            logo = tk.Label(brand, image=self._brand_logo,
                            bg=THEME["shell"], bd=0)
        else:
            logo = tk.Label(brand, text="◈",
                            bg=THEME["surface0"], fg=THEME["accent_2"],
                            font=_font(11, bold=True), width=2)
        logo.pack(side="left", padx=(0, 10))
        title_box = tk.Frame(brand, bg=THEME["shell"])
        title_box.pack(side="left")
        tk.Label(title_box, text="DeepSeek Monitor",
                 bg=THEME["shell"], fg=THEME["fg"],
                 font=_font(13, bold=True)).pack(anchor="w")
        tk.Label(title_box, text="实时仪表盘",
                 bg=THEME["shell"], fg=THEME["muted"],
                 font=_font(8)).pack(anchor="w")

        actions = tk.Frame(header, bg=THEME["shell"])
        actions.pack(side="right")
        action_items = [
            ("↻", self._schedule_refresh, "立即刷新"),
            ("⚙", self._open_settings, "打开设置"),
            ("×", self._on_close, "关闭窗口"),
        ]
        self.action_buttons = []
        for text, command, tooltip in action_items:
            chip = tk.Button(actions, text=text,
                             command=command,
                             bg=THEME["surface0"], fg=THEME["muted"],
                             activebackground=THEME["surface1"], activeforeground=THEME["fg"],
                             relief="flat", bd=0, cursor="hand2",
                             font=_font(9, bold=True), width=2)
            chip._skip_drag_binding = True
            chip._tooltip_text = tooltip
            chip.pack(side="left", padx=3)
            self.action_buttons.append(chip)

        summary = self._card(self.left_panel, pady=12)
        summary.pack(fill="x", padx=12, pady=(10, 10))
        top = tk.Frame(summary.body, bg=THEME["card"])
        top.pack(fill="x", padx=14)

        balance_col = tk.Frame(top, bg=THEME["card"])
        balance_col.pack(side="left", fill="x", expand=True)
        self._card_kicker(balance_col, "账户余额", THEME["accent"])
        self.lbl_balance = tk.Label(balance_col, text="--",
                                    bg=THEME["card"], fg=THEME["accent"],
                                    font=_font(22, bold=True))
        self.lbl_balance.pack(anchor="w")
        self.lbl_balance_detail = tk.Label(balance_col, text="",
                                           bg=THEME["card"], fg=THEME["green"],
                                           font=_font(9))
        self.lbl_balance_detail.pack(anchor="w", pady=(4, 0))

        cost_col = tk.Frame(top, bg=THEME["card"])
        cost_col.pack(side="left", fill="x", expand=True)
        self._card_kicker(cost_col, "本月消费", THEME["yellow"])
        self.lbl_cost = tk.Label(cost_col, text="--",
                                 bg=THEME["card"], fg=THEME["yellow"],
                                 font=_font(22, bold=True))
        self.lbl_cost.pack(anchor="w")
        self.lbl_cost_sub = tk.Label(cost_col, text="",
                                     bg=THEME["card"], fg=THEME["dim"],
                                     font=_font(9))
        self.lbl_cost_sub.pack(anchor="w", pady=(4, 0))

        self.model_cards = []
        for _ in range(2):
            card = self._card(self.left_panel, pady=10)
            card.pack(fill="x", padx=12, pady=(0, 8))
            self.model_cards.append(self._build_model_card(card))

        self.model_legend = tk.Frame(self.left_panel, bg=THEME["panel"])
        self.model_legend.pack(fill="x", padx=16, pady=(0, 8))
        self._build_model_legend()

        chart_card = self._card(self.left_panel, pady=12)
        chart_card.pack(fill="both", expand=True, padx=12, pady=(2, 12))
        header_row = tk.Frame(chart_card.body, bg=THEME["card"])
        header_row.pack(fill="x", padx=14)
        title_group = tk.Frame(header_row, bg=THEME["card"])
        title_group.pack(side="left")
        self._card_kicker(title_group, "消费趋势", THEME["accent"])
        self.lbl_month_tokens = tk.Label(header_row, text="",
                                         bg=THEME["card"], fg=THEME["dim"],
                                         font=_font(9))
        self.lbl_month_tokens.pack(side="right")
        self.left_chart = tk.Canvas(chart_card.body, bg=THEME["card"], height=108,
                                    highlightthickness=0, bd=0)
        self.left_chart.pack(fill="x", padx=12, pady=(8, 4))

    def _build_right_panel(self):
        toolbar = tk.Frame(self.right_panel, bg=THEME["panel"])
        toolbar.pack(fill="x", padx=14, pady=(12, 4))
        tk.Label(toolbar, text="运行概览",
                 bg=THEME["panel"], fg=THEME["fg"],
                 font=_font(11, bold=True)).pack(side="left")
        tk.Label(toolbar, text="近 7 日",
                 bg=THEME["panel"], fg=THEME["dim"],
                 font=_font(8)).pack(side="right")

        top_row = tk.Frame(self.right_panel, bg=THEME["panel"])
        top_row.pack(fill="x", padx=12, pady=(0, 6))

        self.calls_stat = self._build_stat_card(top_row, "API 请求次数")
        self.calls_stat["frame"].pack(side="left", fill="x", expand=True, padx=(0, 6))
        self.tokens_stat = self._build_stat_card(top_row, "Tokens")
        self.tokens_stat["frame"].pack(side="left", fill="x", expand=True, padx=(6, 0))

        chart_card = self._card(self.right_panel, pady=10)
        chart_card.pack(fill="both", expand=True, padx=12, pady=(2, 8))
        head = tk.Frame(chart_card.body, bg=THEME["card"])
        head.pack(fill="x", padx=14)
        left = tk.Frame(head, bg=THEME["card"])
        left.pack(side="left")
        tk.Label(left, text="按日 Token 消耗",
                 bg=THEME["card"], fg=THEME["fg"],
                 font=_font(11, bold=True)).pack(anchor="w")
        self.lbl_date_range = tk.Label(left, text="",
                                       bg=THEME["card"], fg=THEME["dim"],
                                       font=_font(9))
        self.lbl_date_range.pack(anchor="w", pady=(2, 0))
        self.lbl_chart_peak = tk.Label(head, text="",
                                       bg=THEME["card"], fg=THEME["muted"],
                                       font=_font(9))
        self.lbl_chart_peak.pack(side="right", anchor="ne")

        self.right_chart = tk.Canvas(chart_card.body, bg=THEME["card"], height=182,
                                     highlightthickness=0, bd=0)
        self.right_chart.pack(fill="both", expand=True, padx=12, pady=(10, 10))

        footer = tk.Frame(self.right_panel, bg=THEME["panel"])
        footer.pack(fill="x", padx=14, pady=(0, 10))
        footer_top = tk.Frame(footer, bg=THEME["panel"])
        footer_top.pack(fill="x")
        self.lbl_tpm = tk.Label(footer_top, text="--",
                    bg=THEME["panel"], fg=THEME["fg"],
                    font=_font(11, bold=True), anchor="w")
        self.lbl_tpm.pack(side="left", fill="x", expand=True)
        self.lbl_status = tk.Label(footer, text="等待首次刷新...",
                       bg=THEME["panel"], fg=THEME["dim"],
                       font=_font(8), anchor="w", justify="left")
        self.lbl_status.pack(fill="x", pady=(4, 0))

    def _panel_shell(self, parent):
        outer = tk.Frame(parent, bg=THEME["shadow"], padx=2, pady=2)
        edge = tk.Frame(outer, bg=THEME["shell"], padx=2, pady=2)
        edge.pack(fill="both", expand=True)
        body = tk.Frame(edge, bg=THEME["panel"], highlightbackground=THEME["panel_edge"], highlightthickness=1)
        body.pack(fill="both", expand=True)
        outer.body = body
        return outer

    def _card(self, parent, pady=10):
        outer = tk.Frame(parent, bg=THEME["shadow"], padx=1, pady=1)
        edge = tk.Frame(outer, bg=THEME["card_edge"], padx=1, pady=1)
        edge.pack(fill="both", expand=True)
        body = tk.Frame(edge, bg=THEME["card"], padx=0, pady=pady)
        body.pack(fill="both", expand=True)
        outer.body = body
        return outer

    def _card_kicker(self, parent, text, color):
        tk.Label(parent, text=text,
                 bg=THEME["card"], fg=color,
                 font=_font(9, bold=True)).pack(anchor="w", pady=(0, 4))

    def _build_stat_card(self, parent, title):
        frame = self._card(parent, pady=10)
        head = tk.Frame(frame.body, bg=THEME["card"])
        head.pack(fill="x", padx=14, pady=(0, 6))
        tk.Label(head, text="●",
                 bg=THEME["card"], fg=THEME["accent"],
                 font=_font(8, bold=True)).pack(side="left")
        tk.Label(head, text=title,
                 bg=THEME["card"], fg=THEME["muted"],
                 font=_font(9, bold=True)).pack(side="left", padx=(5, 0))
        value = tk.Label(frame.body, text="--",
                         bg=THEME["card"], fg=THEME["accent"],
                         font=_font(19, bold=True))
        value.pack(anchor="w", padx=14, pady=(0, 1))
        sub = tk.Label(frame.body, text="",
                       bg=THEME["card"], fg=THEME["dim"],
                       font=_font(9))
        sub.pack(anchor="w", padx=14, pady=(4, 0))
        return {"frame": frame, "value": value, "sub": sub}

    def _build_model_card(self, parent):
        top = tk.Frame(parent.body, bg=THEME["card"])
        top.pack(fill="x", padx=12)
        icon = tk.Label(top, text="⚡",
                        bg=THEME["surface0"], fg=THEME["accent"],
                        width=2, font=_font(10, bold=True))
        icon.pack(side="left", pady=(2, 0))
        title_box = tk.Frame(top, bg=THEME["card"])
        title_box.pack(side="left", fill="x", expand=True, padx=(8, 0))
        title = tk.Label(title_box, text="--",
                         bg=THEME["card"], fg=THEME["fg"],
                         font=_font(12, bold=True))
        title.pack(anchor="w")
        meta = tk.Label(title_box, text="",
                        bg=THEME["card"], fg=THEME["dim"],
                        font=_font(8))
        meta.pack(anchor="w", pady=(1, 0))
        value = tk.Label(top, text="--",
                         bg=THEME["card"], fg=THEME["fg"],
                         font=_font(11, bold=True), justify="right")
        value.pack(side="right", padx=(8, 0))

        bar_canvas = tk.Canvas(parent.body, bg=THEME["card"], height=8,
                       highlightthickness=0, bd=0)
        bar_canvas.pack(fill="x", padx=12, pady=(9, 4))

        foot = tk.Label(parent.body, text="",
                        bg=THEME["card"], fg=THEME["muted"],
                        font=_font(8))
        foot.pack(anchor="w", padx=12, pady=(1, 0))
        return {
            "icon": icon,
            "title": title,
            "meta": meta,
            "value": value,
            "bar_canvas": bar_canvas,
            "foot": foot,
        }

    def _build_model_legend(self):
        for child in self.model_legend.winfo_children():
            child.destroy()
        items = [
            ("输入未命中", THEME["bar_in"]),
            ("输出", THEME["bar_out"]),
            ("缓存命中", THEME["bar_cache"]),
        ]
        for label, color in items:
            chip = tk.Frame(self.model_legend, bg=THEME["panel"])
            chip.pack(side="left", padx=(0, 12))
            dot = tk.Canvas(chip, width=12, height=12, bg=THEME["panel"], highlightthickness=0, bd=0)
            dot.pack(side="left")
            self._draw_rounded_bar(dot, 1, 1, 11, 11, color, radius=4)
            tk.Label(chip, text=label,
                     bg=THEME["panel"], fg=THEME["muted"],
                     font=_font(8)).pack(side="left", padx=(4, 0))

    def _build_history_table(self):
        headers = ["日期", "数据条", "调用", "费用"]
        self.history_table_header = tk.Frame(self.history_table, bg=THEME["surface0"])
        self.history_table_header.pack(fill="x", pady=(0, 2))
        widths = (6, 13, 6, 7)
        for idx, (title, width) in enumerate(zip(headers, widths)):
            label = tk.Label(self.history_table_header, text=title,
                             bg=THEME["surface0"], fg=THEME["muted"],
                             font=_font(8, bold=True), width=width,
                             anchor="w" if idx == 0 else "e")
            label.pack(side="left", padx=(8 if idx == 0 else 0, 8), pady=4)

        self.history_table_rows = []
        for _ in range(7):
            row = tk.Frame(self.history_table, bg=THEME["shadow"], padx=1, pady=1)
            row.pack(fill="x", pady=1)
            row_body = tk.Frame(row, bg=THEME["card"])
            row_body.pack(fill="x")

            top = tk.Frame(row_body, bg=THEME["card"])
            top.pack(fill="x", padx=8, pady=(3, 1))
            date_lbl = tk.Label(top, text="--",
                                bg=THEME["card"], fg=THEME["fg"],
                                font=_font(8, bold=True), width=6, anchor="w")
            date_lbl.pack(side="left")
            tokens_lbl = tk.Label(top, text="--",
                                  bg=THEME["card"], fg=THEME["accent"],
                                  font=_font(8, bold=True), width=8, anchor="e")
            tokens_lbl.pack(side="left", fill="x", expand=True)
            calls_lbl = tk.Label(top, text="--",
                                 bg=THEME["card"], fg=THEME["muted"],
                                 font=_font(8), width=6, anchor="e")
            calls_lbl.pack(side="left", padx=(6, 5))
            cost_lbl = tk.Label(top, text="--",
                                bg=THEME["card"], fg=THEME["yellow"],
                                font=_font(8, bold=True), width=7, anchor="e")
            cost_lbl.pack(side="left")

            bar_wrap = tk.Frame(row_body, bg=THEME["card"])
            bar_wrap.pack(fill="x", padx=8, pady=(0, 2))
            bar_canvas = tk.Canvas(bar_wrap, bg=THEME["card"], height=6,
                                   highlightthickness=0, bd=0)
            bar_canvas.pack(fill="x")

            self.history_table_rows.append({
                "row": row,
                "body": row_body,
                "date": date_lbl,
                "tokens": tokens_lbl,
                "calls": calls_lbl,
                "cost": cost_lbl,
                "bar_canvas": bar_canvas,
            })

    # ── 拖拽 ──────────────────────────────────────────────
    def _bind_events(self):
        self._drag_offset = (0, 0)
        self.bind("<Button-1>", self._drag_start)
        self.bind("<B1-Motion>", self._drag_move)

        def bind_children(w):
            for child in w.winfo_children():
                if not getattr(child, "_skip_drag_binding", False) and not self._is_interactive_widget(child):
                    child.bind("<Button-1>", self._drag_start)
                    child.bind("<B1-Motion>", self._drag_move)
                child.bind("<Button-3>", self._context_menu)
                bind_children(child)

        bind_children(self)
        self.bind("<Button-3>", self._context_menu)

    def _is_interactive_widget(self, widget):
        interactive_types = (tk.Button, tk.Entry, tk.Scale, tk.Menubutton, ttk.Button, ttk.Entry, ttk.Scale)
        return isinstance(widget, interactive_types)

    def _drag_start(self, event):
        self._drag_offset = (event.x_root - self.winfo_x(),
                             event.y_root - self.winfo_y())

    def _drag_move(self, event):
        x = event.x_root - self._drag_offset[0]
        y = event.y_root - self._drag_offset[1]
        self.geometry(f"+{x}+{y}")

    # ── 右键菜单 ──────────────────────────────────────────
    def _build_context_menu(self):
        self._ctx_menu = tk.Menu(self, tearoff=0,
                                 bg=THEME["card"], fg=THEME["fg"],
                                 activebackground=THEME["surface0"],
                                 activeforeground=THEME["accent"])
        self._ctx_menu.add_command(label="立即刷新", command=self._schedule_refresh)
        self._ctx_menu.add_command(label="导入 CSV...", command=self._import_csv)
        self._ctx_menu.add_command(label="设置...", command=self._open_settings)
        self._ctx_menu.add_separator()
        self._ctx_menu.add_command(label="退出", command=self._on_close)

    def _context_menu(self, event):
        if self._closing or not hasattr(self, "_ctx_menu"):
            return
        try:
            if not self.winfo_exists() or not self._ctx_menu.winfo_exists():
                return
            self._ctx_menu.tk_popup(event.x_root, event.y_root)
        except tk.TclError:
            if not self._closing:
                logger.debug("context menu dismissed during shutdown", exc_info=True)
        finally:
            try:
                if self._ctx_menu.winfo_exists():
                    self._ctx_menu.grab_release()
            except tk.TclError:
                pass

    # ── 数据刷新 ──────────────────────────────────────────
    def _schedule_refresh(self):
        if self._closing:
            return
        self._do_refresh()
        if self._refresh_job_id:
            self.after_cancel(self._refresh_job_id)
        self._refresh_job_id = self.after(self.refresh_interval_ms, self._schedule_refresh)

    def _do_refresh(self):
        has_key = bool(self.config.get("api_key"))

        def _build_snapshot(agg):
            tin = agg["total_input"]
            tout = agg["total_output"]
            tcalls = agg["total_calls"]
            tcost = agg["total_cost"]
            by_model = agg.get("by_model", {})
            sel_date = agg.get("selected_date") or date.today().isoformat()
            mcost = agg.get("month_cost", tcost)
            mcalls = agg.get("month_calls", tcalls)
            mtokens = agg.get("month_input", tin) + agg.get("month_output", tout)
            cache_history = load_daily_history()
            merged_history = merge_daily_history(cache_history, agg.get("daily_history", []))
            if sel_date:
                merged_history = merge_daily_history(merged_history, [{
                    "date": sel_date,
                    "tokens": tin + tout,
                    "cost": tcost,
                    "calls": tcalls,
                }])
            save_daily_history({item["date"]: item for item in merged_history})
            return {
                "today_input": tin, "today_output": tout,
                "today_calls": tcalls, "today_cost": tcost,
                "by_model": by_model, "selected_date": sel_date,
                "month_cost": mcost, "month_calls": mcalls,
                "month_tokens": mtokens, "daily_history": merged_history,
                "total_tokens": tin + tout,
            }

        def fetch():
            snapshot = {}
            with self._refresh_lock:
                if self._closing:
                    return
                snapshot["balance_data"] = None
                snapshot["balance_error"] = None
                if has_key:
                    try:
                        snapshot["balance_data"] = self.api.get_balance()
                    except Exception as e:
                        snapshot["balance_error"] = _api_error_msg(e)

                usage_error = None
                usage_data = None
                got_usage = False
                errors = []

                if has_key:
                    try:
                        raw = self.api.get_usage()
                        agg = _aggregate_usage(raw)
                        if agg["total_calls"] > 0 or agg["total_cost"] > 0:
                            usage_data = _build_snapshot(agg)
                            got_usage = True
                        else:
                            errors.append("API返回空数据")
                    except Exception as e:
                        errors.append(f"API: {_api_error_msg(e)}")

                    if not got_usage:
                        try:
                            csv_result = self.api.get_usage_csv()
                            if csv_result and (csv_result.get("total_calls", 0) > 0 or csv_result.get("total_cost", 0) > 0):
                                usage_data = _build_snapshot(csv_result)
                                got_usage = True
                            else:
                                errors.append("CSV下载: 所有端点均不可达")
                        except Exception as e:
                            errors.append(f"CSV下载: {_api_error_msg(e)}")

                if not got_usage:
                    try:
                        local_result = _load_local_zip()
                        if local_result and (local_result.get("total_calls", 0) > 0 or local_result.get("total_cost", 0) > 0):
                            usage_data = _build_snapshot(local_result)
                            got_usage = True
                    except Exception as e:
                        errors.append(f"本地ZIP: {e}")

                if not got_usage:
                    if not has_key:
                        usage_error = "请设置 API Key，或将用量 ZIP 放入程序目录"
                    else:
                        usage_error = " | ".join(errors) if errors else "暂无用量数据"

                snapshot["usage_data"] = usage_data
                snapshot["usage_error"] = usage_error
                snapshot["last_refresh"] = datetime.now()

                now = datetime.now()
                current_total = usage_data["total_tokens"] if usage_data else 0
                snapshot["tpm"] = self._update_tpm_state(current_total, now)

            if not self._closing:
                self.after(0, lambda s=snapshot: self._apply_snapshot(s))

        threading.Thread(target=fetch, daemon=True).start()

    def _apply_snapshot(self, snapshot):
        if self._closing:
            return
        self.balance_data = snapshot.get("balance_data")
        self.balance_error = snapshot.get("balance_error")
        self.usage_error = snapshot.get("usage_error")
        self.last_refresh = snapshot.get("last_refresh")
        self._current_tpm = snapshot.get("tpm", 0)

        usage = snapshot.get("usage_data")
        if usage:
            self.today_input = usage.get("today_input", 0)
            self.today_output = usage.get("today_output", 0)
            self.today_calls = usage.get("today_calls", 0)
            self.today_cost = usage.get("today_cost", 0.0)
            self.by_model = usage.get("by_model", {})
            self.selected_date = usage.get("selected_date", date.today().isoformat())
            self.month_cost = usage.get("month_cost", self.today_cost)
            self.month_calls = usage.get("month_calls", self.today_calls)
            self.month_tokens = usage.get("month_tokens", self.today_input + self.today_output)
            self.daily_history = usage.get("daily_history", [])
        self._full_render()

    def _apply_usage(self, agg):
        tin = agg["total_input"]
        tout = agg["total_output"]
        tcalls = agg["total_calls"]
        tcost = agg["total_cost"]
        by_model = agg.get("by_model", {})
        sel_date = agg.get("selected_date") or date.today().isoformat()
        mcost = agg.get("month_cost", tcost)
        mcalls = agg.get("month_calls", tcalls)
        mtokens = agg.get("month_input", tin) + agg.get("month_output", tout)
        cache_history = load_daily_history()
        merged_history = merge_daily_history(cache_history, agg.get("daily_history", []))
        if sel_date:
            merged_history = merge_daily_history(merged_history, [{
                "date": sel_date,
                "tokens": tin + tout,
                "cost": tcost,
                "calls": tcalls,
            }])
        save_daily_history({item["date"]: item for item in merged_history})

        self.today_input = tin
        self.today_output = tout
        self.today_calls = tcalls
        self.today_cost = tcost
        self.by_model = by_model
        self.selected_date = sel_date
        self.month_cost = mcost
        self.month_calls = mcalls
        self.month_tokens = mtokens
        self.daily_history = merged_history

    # ── UI 渲染 ───────────────────────────────────────────
    def _full_render(self):
        model = self.config.get("default_model", "deepseek-chat")
        pricing = self.config.get("model_pricing", {}).get(model,
                                   {"input": 2.0, "output": 8.0, "cache_hit": 0.2})

        # ── 余额 ──
        if self.balance_data:
            blist = self.balance_data.get("balances", [])
            if blist:
                b = blist[0]
                cur = b.get("currency", "CNY")
                sym = "¥" if cur == "CNY" else "$"
                total = float(b.get("total_balance", "0"))
                granted = b.get("granted_balance", "0")
                topped = b.get("topped_up_balance", "0")
                self.lbl_balance.config(
                    text=f"{sym}{total:,.2f}",
                    fg=THEME["accent"] if total > 0 else THEME["red"])
                self.lbl_balance_detail.config(
                    text=f"账户可用  赠送 {sym}{granted}  充值 {sym}{topped}")
            else:
                self.lbl_balance.config(text="无余额数据", fg=THEME["dim"])
                self.lbl_balance_detail.config(text="")
        elif self.balance_error:
            self.lbl_balance.config(text="获取失败", fg=THEME["red"])
            self.lbl_balance_detail.config(text=self.balance_error, wraplength=260)
        else:
            self.lbl_balance.config(text="--", fg=THEME["dim"])
            self.lbl_balance_detail.config(text="请配置 API Key")

        # ── 费用 ──
        has_usage = self.today_input > 0 or self.today_output > 0 or bool(self.daily_history)
        if has_usage:
            # 优先使用 API 返回的 cost，否则自行计算
            if self.today_cost > 0:
                cost = self.today_cost
            else:
                iprice = pricing.get("input", 2.0)
                oprice = pricing.get("output", 8.0)
                cost = (self.today_input / 1_000_000) * iprice + (self.today_output / 1_000_000) * oprice
            month_cost = self.month_cost if self.month_cost > 0 else cost
            self.lbl_cost.config(text=f"¥{month_cost:.2f}", fg=THEME["yellow"])
            display_day = self.selected_date or date.today().isoformat()
            self.lbl_cost_sub.config(text=f"当前展示 {display_day}  累计 {self.month_calls:,} 次调用")
        else:
            self.lbl_cost.config(text="--", fg=THEME["dim"])
            self.lbl_cost_sub.config(text="暂无消费数据")

        calls = self.today_calls
        total_tokens = self.today_input + self.today_output
        self.calls_stat["value"].config(text=f"{calls:,}" if calls else "--")
        self.calls_stat["sub"].config(text=f"展示日期 {self.selected_date}" if self.selected_date else "暂无数据")
        self.tokens_stat["value"].config(text=f"{self.month_tokens:,}" if self.month_tokens else f"{total_tokens:,}" if total_tokens else "--")
        self.tokens_stat["sub"].config(text="月累计 Tokens" if self.month_tokens else "当日 Tokens")

        recent_history = self.daily_history[-7:]
        self._render_model_cards()
        self._draw_history_chart(self.left_chart, recent_history, "cost")
        self._draw_history_chart(self.right_chart, recent_history, "tokens")
        self.lbl_month_tokens.config(text=f"合计 {self._format_axis_value(self.month_tokens)}")
        if recent_history:
            start = recent_history[0]["date"]
            end = recent_history[-1]["date"]
            self.lbl_date_range.config(text=f"{_short_date(start)} - {_short_date(end)}")
            peak_tokens = max(item.get("tokens", 0) for item in recent_history)
            self.lbl_chart_peak.config(text=f"峰值 {self._format_axis_value(peak_tokens)}")
        else:
            self.lbl_date_range.config(text="暂无历史数据")
            self.lbl_chart_peak.config(text="")

        # ── TPM ──
        if self._current_tpm > 0:
            self.lbl_tpm.config(text=f"实时速率 {self._current_tpm:,} T/min", fg=THEME["fg"])
        else:
            self.lbl_tpm.config(text="实时速率 --", fg=THEME["dim"])

        # ── 状态栏 ──
        parts = []
        if self.last_refresh:
            parts.append(f"刷新于 {self.last_refresh.strftime('%H:%M:%S')}")
        if self.usage_error:
            parts.append(self.usage_error)
        elif not has_usage and self.balance_data:
            parts.append("暂无用量数据")
        status_text = "  ".join(parts)
        wrap_width = max(180, self.right_panel.winfo_width() - 28) if self.right_panel.winfo_width() > 1 else 220
        self.lbl_status.config(text=status_text,
                       fg=THEME["red"] if self.usage_error else THEME["dim"],
                       wraplength=wrap_width)
        if not self._initial_fit_done:
            self._initial_fit_done = True
            self.after_idle(self._fit_window_to_content)

    def _render_model_cards(self):
        ranked = []
        for model, metrics in self.by_model.items():
            ranked.append((model, metrics, metrics.get("input", 0) + metrics.get("output", 0)))
        ranked.sort(key=lambda item: item[2], reverse=True)
        max_tokens = max((item[2] for item in ranked), default=1)

        for idx, card in enumerate(self.model_cards):
            if idx < len(ranked):
                model, metrics, tokens = ranked[idx]
                meta = MODEL_META.get(model, {})
                color = meta.get("accent", THEME["accent"])
                icon_text = "⚡" if idx == 0 else "✦"
                card["icon"].config(text=icon_text, fg=color)
                card["title"].config(text=meta.get("label", model.replace("deepseek-", "").upper()))
                badge = meta.get("badge", "模型")
                card["meta"].config(text=f"{tokens:,} Tokens")
                cost_value = metrics.get("cost", 0.0)
                calls_value = metrics.get("calls", 0)
                if cost_value > 0:
                    value_text = f"¥{cost_value:.2f}"
                elif calls_value > 0:
                    value_text = f"{calls_value:,} 次"
                else:
                    value_text = "--"
                card["value"].config(text=value_text)
                self._render_model_progress(card["bar_canvas"], metrics)
                input_tokens = metrics.get('input', 0)
                output_tokens = metrics.get('output', 0)
                cache_hit_tokens = metrics.get('cache_hit', 0)
                miss_tokens = max(0, input_tokens - cache_hit_tokens)
                card["foot"].config(text=f"{badge}  入 {self._format_axis_value(miss_tokens)}  出 {self._format_axis_value(output_tokens)}  缓 {self._format_axis_value(cache_hit_tokens)}")
            else:
                card["icon"].config(text="○", fg=THEME["dim"])
                card["title"].config(text="等待模型数据")
                card["meta"].config(text="导入 ZIP / CSV 或配置 API Key")
                card["value"].config(text="--")
                self._render_model_progress(card["bar_canvas"], {})
                card["foot"].config(text="")

    def _render_model_progress(self, canvas, metrics):
        canvas.delete("all")
        width = max(canvas.winfo_width(), 260)
        height = max(canvas.winfo_height(), 8)
        canvas.config(width=width, height=height, bg=THEME["card"])
        self._draw_rounded_bar(canvas, 0, 1, width, height - 1, THEME["bar_bg"], radius=4)

        input_tokens = max(0, metrics.get("input", 0))
        output_tokens = max(0, metrics.get("output", 0))
        cache_hit_tokens = max(0, metrics.get("cache_hit", 0))
        input_miss_tokens = max(0, input_tokens - cache_hit_tokens)
        total_tokens = input_miss_tokens + output_tokens + cache_hit_tokens
        if total_tokens <= 0:
            return

        segments = [
            (input_miss_tokens, THEME["bar_in"]),
            (output_tokens, THEME["bar_out"]),
            (cache_hit_tokens, THEME["bar_cache"]),
        ]
        start_x = 0
        for idx, (value, color) in enumerate(segments):
            if value <= 0:
                continue
            end_x = width if idx == len(segments) - 1 else start_x + int(width * (value / total_tokens))
            end_x = max(start_x + 6, min(width, end_x))
            self._draw_rounded_bar(canvas, start_x, 1, end_x, height - 1, color, radius=4)
            if end_x - start_x > 12:
                self._draw_rounded_bar(canvas, start_x + 1, 2, min(end_x - 1, start_x + max(4, int((end_x - start_x) * 0.18))), height - 2,
                                       THEME["highlight"], radius=3, stipple="gray50")
            start_x = end_x - 1

    def _render_history_table(self, history):
        padded_history = list(history)[-7:]
        padded_history = ([None] * max(0, 7 - len(padded_history))) + padded_history
        max_tokens = max((item.get("tokens", 0) for item in history), default=1)

        for idx, row in enumerate(self.history_table_rows):
            item = padded_history[idx]
            is_latest = item and idx == len(padded_history) - 1
            bg = THEME["surface0"] if is_latest else THEME["card"]
            fg = THEME["fg"] if item else THEME["dim"]
            row["row"].config(bg=THEME["panel_edge"] if is_latest else THEME["shadow"])
            row["body"].config(bg=bg)
            if not item:
                row["date"].config(text="--", bg=bg, fg=THEME["dim"])
                row["tokens"].config(text="--", bg=bg, fg=THEME["dim"])
                row["calls"].config(text="--", bg=bg, fg=THEME["dim"])
                row["cost"].config(text="--", bg=bg, fg=THEME["dim"])
                self._render_history_progress(row["bar_canvas"], 0, THEME["surface1"], bg)
                continue

            tokens = item.get("tokens", 0)
            calls = item.get("calls", 0)
            cost = item.get("cost", 0.0)
            ratio = (tokens / max_tokens) if max_tokens and tokens > 0 else 0
            accent = THEME["highlight"] if is_latest else THEME["accent"]
            row["date"].config(text=_short_date(item.get("date")), bg=bg, fg=fg)
            row["tokens"].config(text=self._format_axis_value(tokens), bg=bg, fg=accent)
            row["calls"].config(text=f"{calls:,}", bg=bg, fg=THEME["muted"])
            row["cost"].config(text=f"¥{cost:.2f}", bg=bg, fg=THEME["yellow"])
            self._render_history_progress(row["bar_canvas"], ratio, accent, bg)

    def _render_history_progress(self, canvas, ratio, accent, bg):
        canvas.delete("all")
        width = max(canvas.winfo_width(), 220)
        height = max(canvas.winfo_height(), 8)
        canvas.config(bg=bg, width=width, height=height)

        self._draw_rounded_bar(canvas, 0, 1, width, height - 1, THEME["bar_bg"], radius=4)
        if ratio <= 0:
            return

        fill_width = max(10, int(width * min(ratio, 1.0)))
        self._draw_rounded_bar(canvas, 0, 1, fill_width, height - 1, accent, radius=4)
        highlight_width = max(2, int(fill_width * 0.18))
        if fill_width > 8:
            self._draw_rounded_bar(canvas, 2, 2, min(fill_width - 2, 2 + highlight_width), height - 2,
                                   THEME["highlight"], radius=3, stipple="gray50")

    def _update_tpm_state(self, current_total, now):
        instant_tpm = None
        if self._prev_refresh_time is not None:
            delta_tokens = max(0, current_total - self._prev_total_tokens)
            delta_secs = max(1, (now - self._prev_refresh_time).total_seconds())
            if delta_tokens > 0:
                instant_tpm = int((delta_tokens / delta_secs) * 60)
        elif current_total > 0:
            refresh_secs = max(1, int(self.config.get("refresh_interval", 60)))
            instant_tpm = int((current_total / refresh_secs) * 60)

        self._prev_total_tokens = current_total
        self._prev_refresh_time = now

        if instant_tpm and instant_tpm > 0:
            self._tpm_samples.append(instant_tpm)
            self._tpm_samples = self._tpm_samples[-6:]

        if self._tpm_samples:
            weights = list(range(1, len(self._tpm_samples) + 1))
            weighted_avg = sum(sample * weight for sample, weight in zip(self._tpm_samples, weights)) / sum(weights)
            if self._current_tpm > 0:
                if instant_tpm and instant_tpm > 0:
                    self._current_tpm = int((self._current_tpm * 0.45) + (weighted_avg * 0.55))
                else:
                    self._current_tpm = int((self._current_tpm * 0.92) + (weighted_avg * 0.08))
            else:
                self._current_tpm = int(weighted_avg)
        elif instant_tpm and instant_tpm > 0:
            self._current_tpm = instant_tpm

        return max(0, int(self._current_tpm))

    def _draw_history_chart(self, canvas, history, metric):
        canvas.delete("all")
        width = max(canvas.winfo_width(), int(canvas.cget("width") or 0), 260)
        height = max(canvas.winfo_height(), int(canvas.cget("height") or 0), 120)
        canvas.config(width=width, height=height)

        if not history:
            canvas.create_text(width / 2, height / 2, text="暂无数据", fill=THEME["dim"], font=_font(10))
            return

        values = [max(0, item.get(metric, 0)) for item in history]
        max_val = max(values) or 1
        left_pad = 16
        right_pad = 14
        top_pad = 14
        bottom_pad = 26
        usable_h = height - top_pad - bottom_pad
        usable_w = width - left_pad - right_pad
        gap = 10
        count = len(history)
        computed_gap = 10 if count <= 5 else 8
        computed_bar_w = int((usable_w - computed_gap * (count - 1)) / max(count, 1)) if history else 18
        bar_w = max(14, min(34, computed_bar_w))
        gap = computed_gap
        accent = THEME["mono_bar"]

        for step in range(4):
            y = top_pad + int((usable_h / 3) * step)
            canvas.create_line(left_pad, y, width - right_pad, y, fill=THEME["grid"])

        for idx, item in enumerate(history):
            value = values[idx]
            x0 = left_pad + idx * (bar_w + gap)
            x1 = x0 + bar_w
            bar_h = 0 if max_val == 0 else int((value / max_val) * usable_h)
            y1 = top_pad + usable_h
            y0 = y1 - bar_h
            self._draw_rounded_bar(canvas, x0, top_pad + 8, x1, y1, THEME["bar_bg"], radius=7)
            self._draw_rounded_bar(canvas, x0, y0, x1, y1, accent, radius=7)
            value_y = max(top_pad - 2, y0 - 10)
            date_y = min(height - 8, y1 + 12)
            canvas.create_text((x0 + x1) / 2, date_y,
                               text=_chart_date(item["date"]),
                               fill=THEME["dim"], font=_font(8))
            canvas.create_text((x0 + x1) / 2, value_y,
                               text=self._format_axis_value(value),
                               fill=THEME["muted"], font=_font(8))

        canvas.create_line(left_pad, top_pad + usable_h, width - right_pad, top_pad + usable_h,
                           fill=THEME["surface1"], width=2)

    def _load_brand_logo(self):
        if not LOGO_FILE.exists():
            return None
        try:
            source = tk.PhotoImage(file=str(LOGO_FILE))
            crop_width = min(source.width(), max(source.height(), 180))
            icon = tk.PhotoImage()
            icon.tk.call(str(icon), "copy", str(source), "-from", 0, 0, crop_width, source.height())
            scale = max(1, round(source.height() / 24))
            return icon.subsample(scale, scale)
        except tk.TclError:
            return None

    def _draw_rounded_bar(self, canvas, x0, y0, x1, y1, color, radius=6, stipple=None):
        width = max(0, x1 - x0)
        height = max(0, y1 - y0)
        if width <= 0 or height <= 0:
            return
        radius = min(radius, int(width / 2), int(height / 2))
        if radius <= 1:
            canvas.create_rectangle(x0, y0, x1, y1, fill=color, outline=color, stipple=stipple)
            return

        canvas.create_rectangle(x0 + radius, y0, x1 - radius, y1, fill=color, outline=color, stipple=stipple)
        canvas.create_rectangle(x0, y0 + radius, x1, y1 - radius, fill=color, outline=color, stipple=stipple)
        canvas.create_oval(x0, y0, x0 + radius * 2, y0 + radius * 2, fill=color, outline=color, stipple=stipple)
        canvas.create_oval(x1 - radius * 2, y0, x1, y0 + radius * 2, fill=color, outline=color, stipple=stipple)
        canvas.create_oval(x0, y1 - radius * 2, x0 + radius * 2, y1, fill=color, outline=color, stipple=stipple)
        canvas.create_oval(x1 - radius * 2, y1 - radius * 2, x1, y1, fill=color, outline=color, stipple=stipple)

    def _format_axis_value(self, value):
        if value >= 1_000_000:
            return f"{value / 1_000_000:.2f}M"
        if value >= 1_000:
            return f"{value / 1_000:.1f}K"
        return str(int(value))

    def _set_status(self, msg, color=None):
        self.lbl_status.config(text=msg, fg=color or THEME["dim"])

    # ── CSV 导入 ──────────────────────────────────────────
    def _import_csv(self):
        """手动导入 CSV/ZIP 文件"""
        from tkinter import filedialog
        path = filedialog.askopenfilename(
            title="选择 DeepSeek 用量 CSV 或 ZIP 文件",
            filetypes=[("CSV/ZIP files", "*.csv *.zip"), ("All files", "*.*")]
        )
        if not path:
            return

        try:
            if path.lower().endswith(".zip"):
                with open(path, "rb") as f:
                    agg = _parse_csv_zip(f.read())
            else:
                with open(path, "r", encoding="utf-8-sig") as f:
                    agg = _parse_deepseek_csv(f.read(), "")

            self._apply_usage(agg)
            self.usage_error = None
            self.last_refresh = datetime.now()
            self._full_render()
            self._set_status(f"导入成功: {agg['selected_date'] or date.today().isoformat()}  {agg['total_calls']:,} 次调用", THEME["green"])
        except Exception as e:
            self._set_status(f"导入失败: {e}", THEME["red"])

    # ── 设置 ──────────────────────────────────────────────
    def _open_settings(self):
        if self._settings_window is not None and self._settings_window.winfo_exists():
            self._settings_window.lift()
            self._settings_window.focus_force()
            return
        self._settings_window = SettingsWindow(self, self.config,
                                               self._on_settings_saved,
                                               self._on_settings_save_error)

    def _on_settings_saved(self):
        self._settings_window = None
        self.config = load_config()
        self.api.update_key(self.config["api_key"])
        self.attributes("-alpha", self.config.get("opacity", 0.90))
        self.refresh_interval_ms = self.config.get("refresh_interval", 60) * 1000
        if self._refresh_job_id:
            self.after_cancel(self._refresh_job_id)
        self._schedule_refresh()
        self._set_status("设置已保存", THEME["green"])

    def _on_settings_save_error(self, err_msg):
        self._settings_window = None
        self._set_status(f"保存失败: {err_msg}", THEME["red"])

    # ── 退出 ──────────────────────────────────────────────
    def _on_close(self):
        if self._closing:
            return
        self._closing = True
        if hasattr(self, "_ctx_menu"):
            try:
                if self._ctx_menu.winfo_exists():
                    self._ctx_menu.unpost()
                    self._ctx_menu.grab_release()
            except tk.TclError:
                pass
        if self._refresh_job_id:
            self.after_cancel(self._refresh_job_id)
            self._refresh_job_id = None
        if self._settings_window is not None and self._settings_window.winfo_exists():
            try:
                self._settings_window.destroy()
            except tk.TclError:
                pass
        self.withdraw()
        self.after_idle(self.destroy)

def main():
    app = DeepSeekWidget()
    app.mainloop()

if __name__ == "__main__":
    main()
