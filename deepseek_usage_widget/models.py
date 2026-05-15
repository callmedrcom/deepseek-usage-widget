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
LOGO_FILE = CONFIG_DIR / "logo.png"
EVENT_LOG_FILE = CONFIG_DIR / "events.log"

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
    "platform_token": "",
}


# ── UI 颜色主题（Apple 暗色风格）──────────────────────────────
THEME = {
    "bg":        "#141416",   # 窗口底色（边框效果）
    "panel":     "#1C1C1E",   # 面板主色（Apple systemBackground）
    "shell":     "#1C1C1E",   # 与面板统一
    "panel_edge":"#38383A",   # 分割线 / 边框色
    "card":      "#2C2C2E",   # 卡片背景（Apple secondarySystemBackground）
    "card_edge": "#3A3A3C",   # 卡片边框
    "surface0":  "#3A3A3C",   # 三级表面
    "surface1":  "#48484A",   # 四级表面
    "fg":        "#FFFFFF",   # 主要文字
    "muted":     "#EBEBF5",   # 次要文字（苹果 label2）
    "dim":       "#8E8E93",   # 辅助文字（苹果 placeholderText）
    "accent":    "#0A84FF",   # Apple 蓝
    "accent_2":  "#5E5CE6",   # Apple 靛蓝
    "green":     "#30D158",   # Apple 绿
    "yellow":    "#FF9F0A",   # Apple 橙黄
    "red":       "#FF453A",   # Apple 红
    "bar_bg":    "#3A3A3C",
    "bar_in":    "#0A84FF",
    "bar_out":   "#30D158",
    "bar_cache": "#5E5CE6",
    "grid":      "#2C2C2E",
    "shadow":    "#000000",
    "highlight": "#FFFFFF",
    "mono_bar":  "#0A84FF",
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
