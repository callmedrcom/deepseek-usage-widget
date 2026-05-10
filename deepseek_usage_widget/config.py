"""配置持久化 — 加载/保存配置与日用量历史"""
import json

from crypto_utils import encrypt, decrypt
from .models import CONFIG_DIR, CONFIG_FILE, DAILY_FILE, DEFAULT_CONFIG, logger

def load_config():
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        for k, v in DEFAULT_CONFIG.items():
            if k not in cfg:
                cfg[k] = v
        if cfg.get("api_key"):
            try:
                cfg["api_key"] = decrypt(cfg["api_key"])
            except Exception:
                logger.warning("API Key 解密失败，可能需要重新输入")
                cfg["api_key"] = ""
        return cfg
    save_config(DEFAULT_CONFIG)
    return dict(DEFAULT_CONFIG)

def save_config(cfg):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    to_save = dict(cfg)
    if to_save.get("api_key"):
        to_save["api_key"] = encrypt(to_save["api_key"])
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(to_save, f, indent=2, ensure_ascii=False)

def load_daily_history():
    if not DAILY_FILE.exists():
        return {}
    try:
        with open(DAILY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError, OSError):
        return {}

def save_daily_history(history):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(DAILY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)

def merge_daily_history(*sources):
    merged = {}
    for source in sources:
        if not source:
            continue
        if isinstance(source, dict):
            iterable = source.values()
        else:
            iterable = source
        for item in iterable:
            day = item.get("date")
            if not day:
                continue
            merged[day] = {
                "date": day,
                "tokens": int(item.get("tokens", 0)),
                "cost": float(item.get("cost", 0.0)),
                "calls": int(item.get("calls", 0)),
            }
    return [merged[key] for key in sorted(merged.keys())]
