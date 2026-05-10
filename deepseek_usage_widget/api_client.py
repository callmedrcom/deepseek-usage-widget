"""DeepSeek API 客户端 + CSV/ZIP 解析 + 数据聚合"""
import json
import csv
import io
import zipfile
import os as _os
from datetime import datetime, date

try:
    import requests
except ImportError:
    print("缺少依赖，请先运行: pip install requests")
    import sys
    sys.exit(1)

from .models import logger, CSV_CACHE_DIR

MAX_CACHE_FILES = 100


def _trim_cache():
    """保持 CSV_CACHE_DIR 下最多 MAX_CACHE_FILES 个文件，按修改时间删除最早的。"""
    try:
        files = sorted(
            [p for p in CSV_CACHE_DIR.iterdir() if p.is_file() and p.name.startswith("usage_")],
            key=lambda p: p.stat().st_mtime,
        )
        while len(files) > MAX_CACHE_FILES:
            oldest = files.pop(0)
            _os.unlink(oldest)
            logger.info("缓存淘汰: %s", oldest.name)
    except Exception:
        pass

class DeepSeekAPI:
    def __init__(self, config):
        self.api_key = config.get("api_key", "")
        self.platform_token = config.get("platform_token", "")
        self.base_url = config.get("base_url", "https://api.deepseek.com").rstrip("/")
        self.platform_url = config.get("platform_url", "https://platform.deepseek.com").rstrip("/")
        self.session = requests.Session()

    def _headers(self):
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
        }

    def _platform_headers(self):
        return {
            "Authorization": f"Bearer {self.platform_token}",
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/132.0.0.0 Safari/537.36",
            "Referer": f"{self.platform_url}/usage",
        }

    def get_balance(self):
        url = f"{self.base_url}/user/balance"
        resp = self.session.get(url, headers=self._headers(), timeout=15)
        resp.raise_for_status()
        data = resp.json()
        return {
            "is_available": data.get("is_available", False),
            "balances": data.get("balance_infos", []),
        }

    def get_usage(self, target_date=None):
        """
        GET /v1/usage?start_date=X&end_date=Y
        返回按请求明细的用量数据，需聚合。
        """
        if target_date is None:
            target_date = date.today()
        ds = target_date.isoformat() if isinstance(target_date, date) else str(target_date)

        url = f"{self.base_url}/v1/usage"
        params = {"start_date": ds, "end_date": ds}
        resp = self.session.get(url, headers=self._headers(), params=params, timeout=15)
        resp.raise_for_status()
        return resp.json()

    def get_platform_usage(self, target_date=None):
        """
        通过 platform.deepseek.com 内部 API 获取月用量数据。
        需要 platform_token（浏览器 LocalStorage → userToken）。
        返回 _aggregate_platform_cost 的聚合结果，或 None。
        """
        if not self.platform_token:
            return None

        if target_date is None:
            target_date = date.today()
        ds = target_date.isoformat() if isinstance(target_date, date) else str(target_date)
        y, m = ds[:4], ds[5:7]

        url = f"{self.platform_url}/api/v0/usage/cost?month={m}&year={y}"
        try:
            resp = self.session.get(url, headers=self._platform_headers(), timeout=30)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("code") == 0 and data.get("data"):
                    return _aggregate_platform_cost(data["data"], target_date)
                logger.warning("平台 API 返回异常: code=%s msg=%s", data.get("code"), data.get("msg"))
            else:
                logger.warning("平台 API HTTP %s: %s", resp.status_code, url)
        except requests.RequestException as e:
            logger.warning("平台 API 请求失败: %s — %s", url, e)
        return None

    def get_usage_csv(self, target_date=None):
        """
        从 DeepSeek 平台下载用量 CSV 导出 ZIP。
        先尝试下载最新数据；下载失败时才回退到缓存。
        返回 _parse_deepseek_csv 的聚合结果，或 None。
        """
        if target_date is None:
            target_date = date.today()
        ds = target_date.isoformat() if isinstance(target_date, date) else str(target_date)
        ym = ds[:7]  # "2026-05"

        CSV_CACHE_DIR.mkdir(parents=True, exist_ok=True)

        # ── 端点列表 ──
        endpoints = [
            ("GET", f"{self.platform_url}/api/usage/export?year_month={ym}"),
            ("GET", f"{self.platform_url}/api/usage/download?year_month={ym}"),
            ("GET", f"{self.platform_url}/api/billing/usage/export?year_month={ym}"),
            ("POST", f"{self.platform_url}/api/usage/export",
             {"year_month": ym}),
            ("POST", f"{self.platform_url}/api/billing/export",
             {"year_month": ym, "format": "csv"}),
            ("GET", f"{self.base_url}/v1/usage/export?year_month={ym}"),
            ("GET", f"{self.base_url}/billing/usage/export?year_month={ym}"),
        ]

        # ── 1. 先尝试下载 ──
        last_status = None
        for endpoint in endpoints:
            method = endpoint[0]
            url = endpoint[1]
            body = endpoint[2] if len(endpoint) > 2 else None
            try:
                if method == "GET":
                    resp = self.session.get(url, headers=self._headers(), timeout=30)
                else:
                    resp = self.session.post(url, headers=self._headers(),
                                             json=body, timeout=30)

                if resp.status_code == 200:
                    ct = resp.headers.get("content-type", "")
                    if "zip" in ct or "octet-stream" in ct or resp.content[:2] == b"PK":
                        logger.info("CSV 下载成功: %s %s", method, url)
                        now = datetime.now().strftime("%d_%H%M%S")
                        cache_file = CSV_CACHE_DIR / f"usage_{ym}_{now}.zip"
                        try:
                            with open(cache_file, "wb") as f:
                                f.write(resp.content)
                            _trim_cache()
                        except Exception:
                            logger.warning("缓存写入失败", exc_info=True)
                        try:
                            result = _parse_csv_zip(resp.content, target_date)
                            if result["total_calls"] > 0 or result["total_cost"] > 0:
                                return result
                        except (ValueError, KeyError) as e:
                            logger.warning("ZIP 解析失败: %s %s — %s", method, url, e)
                    if "csv" in ct or "text/csv" in ct:
                        text = resp.text
                        result = _parse_deepseek_csv(text, "", target_date)
                        if result["total_calls"] > 0 or result["total_cost"] > 0:
                            return result
                    try:
                        data = resp.json()
                        agg = _aggregate_usage(data)
                        if agg["total_calls"] > 0 or agg["total_cost"] > 0:
                            return agg
                    except (ValueError, KeyError, TypeError):
                        pass
                else:
                    last_status = resp.status_code
                    logger.warning("CSV 端点 HTTP %s: %s %s", resp.status_code, method, url)
            except requests.RequestException as e:
                logger.warning("CSV 请求失败: %s %s — %s", method, url, e)
                continue

        # ── 2. 下载失败，回退缓存（取最新匹配文件）──
        prefix = f"usage_{ym}_"
        candidates = sorted(
            [p for p in CSV_CACHE_DIR.iterdir() if p.is_file() and p.name.startswith(prefix)],
            key=lambda p: p.stat().st_mtime, reverse=True,
        )
        if candidates:
            cache_file = candidates[0]
            logger.info("下载失败，回退缓存: %s", cache_file.name)
            try:
                with open(cache_file, "rb") as f:
                    result = _parse_csv_zip(f.read(), target_date)
                if result["total_calls"] > 0 or result["total_cost"] > 0:
                    return result
            except Exception:
                logger.warning("缓存损坏", exc_info=True)

        logger.warning("所有 CSV 端点均失败%s",
                       f", 最后状态码: {last_status}" if last_status else "")
        return None

    def update_key(self, new_key):
        self.api_key = new_key

    def update_platform_token(self, new_token):
        self.platform_token = new_token


# ═══════════════════════════════════════════════════════════════
#  CSV 解析 — DeepSeek 导出格式
#  ZIP 内含:
#   amount-YYYY-M.csv: user_id,utc_date,model,api_key_name,api_key,type,price,amount
#     type = output_tokens | input_tokens | input_cache_hit_tokens
#           | input_cache_miss_tokens | request_count
#   cost-YYYY-M.csv:   user_id,utc_date,model,wallet_type,cost,currency
# ═══════════════════════════════════════════════════════════════

def _parse_csv_zip(zip_bytes, target_date=None):
    """解压 DeepSeek 导出的 ZIP 并聚合为用量数据"""
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        amount_text = None
        cost_text = None
        for name in zf.namelist():
            lower = name.lower()
            with zf.open(name) as f:
                text = f.read().decode("utf-8-sig", errors="replace")
            if "amount" in lower:
                amount_text = text
            elif "cost" in lower:
                cost_text = text

        if not amount_text:
            raise ValueError("ZIP 中未找到 amount-*.csv 文件")

        return _parse_deepseek_csv(amount_text, cost_text or "", target_date)


def _parse_deepseek_csv(amount_text, cost_text="", target_date=None):
    """
    解析 DeepSeek 官方导出的 amount CSV + cost CSV。
    返回 _aggregate_usage 兼容的 dict 或已聚合结果。
    """
    # ── 解析 amount CSV ──
    # 累计: {date: {model: {input, output, cache_hit, calls}}}
    daily = {}
    reader = csv.DictReader(io.StringIO(amount_text))
    for row in reader:
        try:
            utc_date = row.get("utc_date", "").strip()
            model = row.get("model", "").strip()
            rtype = row.get("type", "").strip()
            amount_str = row.get("amount", "0").strip()
            if not utc_date or not rtype:
                continue
            amount = int(float(amount_str)) if amount_str else 0
        except (ValueError, KeyError):
            continue

        if utc_date not in daily:
            daily[utc_date] = {}
        if model not in daily[utc_date]:
            daily[utc_date][model] = {"input": 0, "output": 0, "cache_hit": 0, "calls": 0}

        rtype_lower = rtype.lower().replace(" ", "_")
        if rtype_lower in ("output_tokens", "completion_tokens"):
            daily[utc_date][model]["output"] += amount
        elif "cache_hit" in rtype_lower:
            daily[utc_date][model]["cache_hit"] += amount
            daily[utc_date][model]["input"] += amount
        elif "input" in rtype_lower and "token" in rtype_lower:
            daily[utc_date][model]["input"] += amount
        elif rtype_lower in ("request_count", "api_calls", "total_requests"):
            daily[utc_date][model]["calls"] += amount

    # ── 解析 cost CSV ──
    cost_map = {}  # {(date, model): cost}
    if cost_text:
        reader = csv.DictReader(io.StringIO(cost_text))
        for row in reader:
            try:
                d = row.get("utc_date", "").strip()
                m = row.get("model", "").strip()
                c = float(row.get("cost", "0").strip())
                cost_map[(d, m)] = cost_map.get((d, m), 0.0) + c
            except (ValueError, KeyError):
                continue

    all_dates = sorted(daily.keys())
    latest_date = all_dates[-1] if all_dates else None

    # ── 筛选目标日期；若当天无记录，回退到最近有数据的一天 ──
    if target_date is None:
        target_date = date.today().isoformat()
    elif isinstance(target_date, date):
        target_date = target_date.isoformat()

    selected_date = target_date if target_date in daily else latest_date
    target_data = daily.get(selected_date or "", {})

    total_input = 0
    total_output = 0
    total_calls = 0
    total_cost = 0.0
    by_model = {}
    daily_history = []
    month_input = 0
    month_output = 0
    month_cache_hit = 0
    month_calls = 0
    month_cost = 0.0

    for day in all_dates:
        tokens = 0
        cost_total = 0.0
        calls_total = 0
        for model, metrics in daily[day].items():
            tokens += metrics["input"] + metrics["output"]
            calls_total += metrics["calls"]
            cost_total += cost_map.get((day, model), 0.0)
        month_input += sum(metrics["input"] for metrics in daily[day].values())
        month_output += sum(metrics["output"] for metrics in daily[day].values())
        month_cache_hit += sum(metrics.get("cache_hit", 0) for metrics in daily[day].values())
        month_calls += calls_total
        month_cost += cost_total
        daily_history.append({
            "date": day,
            "tokens": tokens,
            "cost": cost_total,
            "calls": calls_total,
        })

    for model, metrics in target_data.items():
        inp = metrics["input"]
        outp = metrics["output"]
        cache_hit = metrics.get("cache_hit", 0)
        calls = metrics["calls"]
        cost = cost_map.get((selected_date, model), 0.0)

        total_input += inp
        total_output += outp
        total_calls += calls
        total_cost += cost
        by_model[model] = {"input": inp, "output": outp, "cache_hit": cache_hit, "calls": calls, "cost": cost}

    return {
        "total_input": total_input,
        "total_output": total_output,
        "total_calls": total_calls,
        "total_cost": total_cost,
        "by_model": by_model,
        "selected_date": selected_date,
        "latest_date": latest_date,
        "daily_history": daily_history,
        "month_input": month_input,
        "month_output": month_output,
        "month_cache_hit": month_cache_hit,
        "month_calls": month_calls,
        "month_cost": month_cost,
    }


# ═══════════════════════════════════════════════════════════════
#  平台 API 响应解析
# ═══════════════════════════════════════════════════════════════

def _aggregate_platform_cost(data, target_date=None):
    """
    解析 platform.deepseek.com /api/v0/usage/cost 返回的 JSON 数据。
    data 可能是 list（每日记录）或 dict（含 daily_costs 等字段）。
    """
    if target_date is None:
        target_date = date.today().isoformat()
    elif isinstance(target_date, date):
        target_date = target_date.isoformat()

    # 提取每日记录列表
    records = []
    if isinstance(data, list):
        records = data
    elif isinstance(data, dict):
        records = data.get("daily_costs") or data.get("costs") or data.get("items") or []
        if not records and "cost" in data:
            records = [data]
    if not records:
        logger.warning("平台 API 返回数据格式无法识别: %s", type(data).__name__)
        return None

    total_cost = 0.0
    total_calls = 0
    daily_history = []
    by_model = {}
    all_dates = []
    month_cost = 0.0
    month_calls = 0

    for r in records:
        d = (r.get("date") or r.get("utc_date") or r.get("day", "")).strip()
        cost_raw = r.get("cost")
        if cost_raw is None:
            cost_raw = r.get("total_cost")
        if cost_raw is None:
            cost_raw = r.get("amount", 0)
        cost = float(cost_raw or 0)
        calls = int(r.get("calls") or r.get("request_count") or r.get("api_calls") or 0)

        if not d:
            continue

        all_dates.append(d)
        month_cost += cost
        month_calls += calls

        daily_history.append({
            "date": d,
            "tokens": 0,  # platform cost API 通常不含 token 数
            "cost": cost,
            "calls": calls,
        })

        # 按模型拆分可能嵌套在 models / details 字段中
        model_items = r.get("models") or r.get("details") or r.get("breakdown") or []
        if isinstance(model_items, dict):
            model_items = [{"model": k, **v} for k, v in model_items.items()]
        for mi in model_items:
            model = mi.get("model") or mi.get("model_name") or "unknown"
            mcost = float(mi.get("cost") or mi.get("amount") or 0)
            mcalls = int(mi.get("calls") or mi.get("request_count") or 0)
            if model not in by_model:
                by_model[model] = {"input": 0, "output": 0, "cache_hit": 0, "calls": 0, "cost": 0.0}
            by_model[model]["cost"] += mcost
            by_model[model]["calls"] += mcalls

    if not all_dates:
        logger.warning("平台 API 返回数据无日期字段")
        return None

    all_dates.sort()
    latest_date = all_dates[-1]
    selected_date = target_date if target_date in all_dates else latest_date

    selected_cost = sum(item["cost"] for item in daily_history if item["date"] == selected_date)

    return {
        "total_input": 0,
        "total_output": 0,
        "total_calls": month_calls,
        "total_cost": selected_cost,
        "by_model": by_model,
        "selected_date": selected_date,
        "latest_date": latest_date,
        "daily_history": daily_history,
        "month_input": 0,
        "month_output": 0,
        "month_cache_hit": 0,
        "month_calls": month_calls,
        "month_cost": month_cost,
    }


# ═══════════════════════════════════════════════════════════════
#  数据聚合
# ═══════════════════════════════════════════════════════════════

def _aggregate_usage(data_or_records):
    """
    将 API 返回的 JSON 聚合为统一格式。
    如果已经是 _parse_deepseek_csv 的输出则原样返回。
    """
    # 已经是聚合格式
    if isinstance(data_or_records, dict) and "total_input" in data_or_records:
        return data_or_records

    result = {
        "total_input": 0,
        "total_output": 0,
        "total_calls": 0,
        "total_cost": 0.0,
        "by_model": {},
        "selected_date": date.today().isoformat(),
        "latest_date": date.today().isoformat(),
        "daily_history": [],
        "month_input": 0,
        "month_output": 0,
        "month_cache_hit": 0,
        "month_calls": 0,
        "month_cost": 0.0,
    }

    records = []

    if isinstance(data_or_records, list):
        records = data_or_records
    elif isinstance(data_or_records, dict):
        d = data_or_records.get("data", data_or_records)
        if isinstance(d, list):
            records = d
        elif isinstance(d, dict):
            total_input = int(d.get("total_input_tokens") or d.get("prompt_tokens") or 0)
            total_output = int(d.get("total_output_tokens") or d.get("completion_tokens") or 0)
            total_calls = int(d.get("total_requests") or d.get("request_count") or d.get("api_calls") or 0)
            total_cost = float(d.get("total_cost") or d.get("cost") or 0.0)
            result["total_input"] = total_input
            result["total_output"] = total_output
            result["total_calls"] = total_calls
            result["total_cost"] = total_cost
            total_tokens = total_input + total_output
            result["daily_history"] = [{
                "date": date.today().isoformat(),
                "tokens": total_tokens,
                "cost": total_cost,
                "calls": total_calls,
            }]
            result["month_input"] = total_input
            result["month_output"] = total_output
            result["month_cache_hit"] = 0
            result["month_calls"] = total_calls
            result["month_cost"] = total_cost
            return result

    for r in records:
        if not isinstance(r, dict):
            continue
        pin = int(r.get("prompt_tokens") or r.get("input_tokens") or
                  r.get("total_input_tokens") or 0)
        pout = int(r.get("completion_tokens") or r.get("output_tokens") or
                   r.get("total_output_tokens") or 0)
        cost = float(r.get("cost") or r.get("cost_in_cents") or 0)
        model = r.get("model") or r.get("model_name") or "unknown"

        result["total_input"] += pin
        result["total_output"] += pout
        result["total_calls"] += 1
        result["total_cost"] += cost

        if model not in result["by_model"]:
            result["by_model"][model] = {"input": 0, "output": 0, "cache_hit": 0, "calls": 0, "cost": 0.0}
        result["by_model"][model]["input"] += pin
        result["by_model"][model]["output"] += pout
        result["by_model"][model]["calls"] += 1
        result["by_model"][model]["cost"] += cost

    total_tokens = result["total_input"] + result["total_output"]
    result["daily_history"] = [{
        "date": date.today().isoformat(),
        "tokens": total_tokens,
        "cost": result["total_cost"],
        "calls": result["total_calls"],
    }]
    result["month_input"] = result["total_input"]
    result["month_output"] = result["total_output"]
    result["month_cache_hit"] = 0
    result["month_calls"] = result["total_calls"]
    result["month_cost"] = result["total_cost"]

    return result

