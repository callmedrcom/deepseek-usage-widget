"""工具函数 — 日期格式化、错误消息、本地 ZIP 加载"""
from datetime import datetime, date
from pathlib import Path

from .models import logger, CSV_CACHE_DIR
from .api_client import _parse_csv_zip

def _short_date(value):
    if not value:
        return "--"
    try:
        dt = datetime.strptime(value, "%Y-%m-%d")
        return f"{dt.month}/{dt.day}"
    except ValueError:
        return value

def _chart_date(value):
    if not value:
        return "--"
    try:
        dt = datetime.strptime(value, "%Y-%m-%d")
        return f"{dt.month}.{dt.day}"
    except ValueError:
        return value

def _load_local_zip(target_date=None):
    """
    自动检测项目目录下的 DeepSeek 用量 ZIP 文件并解析。
    匹配: usage_data_*.zip 或任何包含 'usage' 的 .zip 文件。
    """
    if target_date is None:
        target_date = date.today()

    # 搜索目录：脚本所在目录 & 当前工作目录
    try:
        script_dir = Path(__file__).parent
    except NameError:
        script_dir = Path.cwd()
    search_dirs = [script_dir, Path.cwd()]

    for search_dir in search_dirs:
        try:
            candidates = []
            for p in search_dir.iterdir():
                if not p.is_file():
                    continue
                name = p.name.lower()
                if name.endswith(".zip") and ("usage" in name or "deepseek" in name):
                    candidates.append((p.stat().st_mtime, p))

            # 选最新的
            if candidates:
                candidates.sort(reverse=True)
                zip_path = candidates[0][1]
                logger.info("本地 ZIP 发现: %s", zip_path.name)
                with open(zip_path, "rb") as f:
                    raw = f.read()
                result = _parse_csv_zip(raw, target_date)
                if result["total_calls"] > 0 or result["total_cost"] > 0:
                    # 缓存到 csv_cache
                    try:
                        now_ts = datetime.now().strftime("%Y-%m_%d_%H%M%S")
                        CSV_CACHE_DIR.mkdir(parents=True, exist_ok=True)
                        dest = CSV_CACHE_DIR / f"usage_{now_ts}.zip"
                        with open(dest, "wb") as f:
                            f.write(raw)
                        logger.info("本地 ZIP 已缓存: %s", dest.name)
                    except Exception:
                        logger.warning("缓存写入失败", exc_info=True)
                    logger.info("本地 ZIP 解析成功: %s 次调用", result.get("total_calls", 0))
                    return result
        except Exception as e:
            logger.warning("本地 ZIP 搜索错误: %s", e)
            continue

    return None

def _api_error_msg(e):
    if hasattr(e, "response") and e.response is not None:
        try:
            body = e.response.json()
            if isinstance(body, dict):
                msg = body.get("message", body.get("error", str(e)))
            else:
                msg = str(e)
        except (ValueError, AttributeError):
            msg = str(e)
        return f"[{e.response.status_code}] {msg}"
    return str(e)
