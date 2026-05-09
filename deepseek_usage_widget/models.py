"""DeepSeek Usage Monitor — 常量与配置模型"""
import logging
from pathlib import Path

# ── 日志 ────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("deepseek_widget")

# ── 配置路径 ────────────────────────────────────────────────
CONFIG_DIR = Path.home() / ".deepseek_widget"
CONFIG_FILE = CONFIG_DIR / "config.json"
DAILY_FILE = CONFIG_DIR / "daily.json"
CSV_CACHE_DIR = CONFIG_DIR / "csv_cache"

# ── 默认配置 ────────────────────────────────────────────────
DEFAULT_CONFIG = {
    "api_key": "",
    "refresh_interval": 60,
    "opacity": 0.84,
    "model_pricing": {
        "deepseek-chat":         {"input": 2.0,  "output": 8.0,  "cache_hit": 0.2},
        "deepseek-reasoner":     {"input": 4.0,  "output": 16.0, "cache_hit": 0.4},
        "deepseek-v3":           {"input": 2.0,  "output": 8.0,  "cache_hit": 0.2},
        "deepseek-r1":           {"input": 4.0,  "output": 16.0, "cache_hit": 0.4},
        "deepseek-v4-flash":     {"input": 2.0,  "output": 8.0,  "cache_hit": 0.2},
        "deepseek-v4-pro":       {"input": 2.0,  "output": 8.0,  "cache_hit": 0.2},
    },
    "default_model": "deepseek-chat",
    "base_url": "https://api.deepseek.com",
    "platform_url": "https://platform.deepseek.com",
}


# ── UI 颜色主题（深色主题）──────────────────────────────────
THEME = {
    "bg":       "#99a3b2",
    "panel":    "#23272d",
    "shell":    "#c5ccd6",
    "panel_edge": "#eef2f7",
    "card":     "#15181d",
    "card_edge": "#323840",
    "surface0": "#20252c",
    "surface1": "#2b313a",
    "fg":       "#f5f7fb",
    "muted":    "#c4ccd8",
    "dim":      "#96a1af",
    "accent":   "#82a0ff",
    "accent_2": "#9c8cff",
    "green":    "#63d29c",
    "yellow":   "#ffbf5f",
    "red":      "#ff8b81",
    "bar_bg":   "#252b33",
    "bar_in":   "#7ea6ff",
    "bar_out":  "#7ad0ff",
    "bar_cache": "#c09aff",
    "grid":     "#313744",
    "shadow":   "#8d97a5",
    "highlight": "#dbe5ff",
    "mono_bar": "#82a0ff",
}


MODEL_META = {
    "deepseek-v4-flash": {"label": "V4 Flash", "accent": "#8babff", "badge": "高吞吐"},
    "deepseek-v4-pro": {"label": "V4 Pro", "accent": "#c09aff", "badge": "高质量"},
    "deepseek-chat": {"label": "DeepSeek Chat", "accent": "#8babff", "badge": "通用"},
    "deepseek-reasoner": {"label": "Reasoner", "accent": "#7ad0ff", "badge": "推理"},
    "deepseek-v3": {"label": "V3", "accent": "#8babff", "badge": "标准"},
    "deepseek-r1": {"label": "R1", "accent": "#ffbf8a", "badge": "推理"},
}

# ── 字体 ────────────────────────────────────────────────────
import tkinter.font as tkfont
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
