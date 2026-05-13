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

# ── 平台 API 单价表 (CNY / 百万 tokens) ────────────────────────
# 用于从费用反推 token 数量（估算）。价格以 2026-04-26 调整后为准。
_PLATFORM_PRICING = {
    "deepseek-chat":     {"cache_hit": 0.02, "cache_miss": 1.0,  "output": 2.0},
    "deepseek-v4-flash": {"cache_hit": 0.02, "cache_miss": 1.0,  "output": 2.0},
    "deepseek-v4-pro":   {"cache_hit": 0.025,"cache_miss": 3.0,  "output": 6.0},
    "deepseek-reasoner": {"cache_hit": 0.04, "cache_miss": 4.0,  "output": 16.0},
    "deepseek-r1":       {"cache_hit": 0.04, "cache_miss": 4.0,  "output": 16.0},
    "deepseek-v3":       {"cache_hit": 0.02, "cache_miss": 1.0,  "output": 2.0},
}
_DEFAULT_PLATFORM_PRICING = {"cache_hit": 0.1, "cache_miss": 2.0, "output": 4.0}


def _cost_to_tokens(cache_hit_cost, cache_miss_cost, output_cost, pricing):
    """根据费用和单价反推 token 数量（整数估算）。"""
    ch_p  = pricing.get("cache_hit",  _DEFAULT_PLATFORM_PRICING["cache_hit"])
    cm_p  = pricing.get("cache_miss", _DEFAULT_PLATFORM_PRICING["cache_miss"])
    out_p = pricing.get("output",     _DEFAULT_PLATFORM_PRICING["output"])
    ch_tokens  = int(cache_hit_cost  * 1_000_000 / ch_p)  if ch_p  > 0 else 0
    cm_tokens  = int(cache_miss_cost * 1_000_000 / cm_p)  if cm_p  > 0 else 0
    out_tokens = int(output_cost     * 1_000_000 / out_p) if out_p > 0 else 0
    return ch_tokens, cm_tokens, out_tokens


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
        从 platform.deepseek.com 下载月度用量 ZIP。
        先尝试各端点下载；失败时回退到缓存文件。
        返回 _parse_deepseek_csv 的聚合结果，或 None。
        """
        if target_date is None:
            target_date = date.today()
        ds = target_date.isoformat() if isinstance(target_date, date) else str(target_date)
        ym = ds[:7]   # "2026-05"
        y, m = ds[:4], ds[5:7]

        CSV_CACHE_DIR.mkdir(parents=True, exist_ok=True)

        # ── 平台端点（使用 platform_token）──
        # 按成功率从高到低排列；实际接口地址通过抓包确认后放首位
        platform_endpoints = [
            ("GET",  f"{self.platform_url}/api/v0/usage/export?month={m}&year={y}"),
            ("GET",  f"{self.platform_url}/api/v0/usage/download?month={m}&year={y}"),
            ("POST", f"{self.platform_url}/api/v0/usage/export",
             {"month": int(m), "year": int(y)}),
            ("GET",  f"{self.platform_url}/api/usage/export?year_month={ym}"),
            ("GET",  f"{self.platform_url}/api/usage/download?year_month={ym}"),
            ("GET",  f"{self.platform_url}/api/billing/usage/export?year_month={ym}"),
            ("POST", f"{self.platform_url}/api/usage/export", {"year_month": ym}),
        ]
        # ── API 端点（使用 api_key）──
        api_endpoints = [
            ("GET",  f"{self.base_url}/v1/usage/export?year_month={ym}"),
            ("GET",  f"{self.base_url}/billing/usage/export?year_month={ym}"),
        ]

        def _try_endpoints(endpoints, use_platform_headers):
            headers = self._platform_headers() if use_platform_headers else self._headers()
            last_status = None
            for endpoint in endpoints:
                method = endpoint[0]
                url = endpoint[1]
                body = endpoint[2] if len(endpoint) > 2 else None
                try:
                    if method == "GET":
                        resp = self.session.get(url, headers=headers, timeout=30)
                    else:
                        resp = self.session.post(url, headers=headers, json=body, timeout=30)

                    if resp.status_code == 200:
                        ct = resp.headers.get("content-type", "")
                        if "zip" in ct or "octet-stream" in ct or resp.content[:2] == b"PK":
                            logger.info("ZIP 下载成功: %s %s", method, url)
                            now_s = datetime.now().strftime("%d_%H%M%S")
                            cache_file = CSV_CACHE_DIR / f"usage_{ym}_{now_s}.zip"
                            try:
                                with open(cache_file, "wb") as fh:
                                    fh.write(resp.content)
                                _trim_cache()
                            except Exception:
                                logger.warning("缓存写入失败", exc_info=True)
                            try:
                                result = _parse_csv_zip(resp.content, target_date)
                                if result["total_calls"] > 0 or result["total_cost"] > 0:
                                    return result
                            except (ValueError, KeyError) as e:
                                logger.warning("ZIP 解析失败: %s", e)
                            continue
                        if "csv" in ct or "text/csv" in ct:
                            result = _parse_deepseek_csv(resp.text, "", target_date)
                            if result["total_calls"] > 0 or result["total_cost"] > 0:
                                return result
                            continue
                        try:
                            data = resp.json()
                            agg = _aggregate_usage(data)
                            if agg["total_calls"] > 0 or agg["total_cost"] > 0:
                                return agg
                        except (ValueError, KeyError, TypeError):
                            pass
                    else:
                        last_status = resp.status_code
                        logger.debug("CSV 端点 HTTP %s: %s %s", resp.status_code, method, url)
                except requests.RequestException as e:
                    logger.debug("CSV 请求失败: %s %s — %s", method, url, e)
            return last_status  # 无数据时返回最后 HTTP 状态码（int）或 None

        # ── 1. 先试平台端点（需要 platform_token）──
        if self.platform_token:
            r = _try_endpoints(platform_endpoints, use_platform_headers=True)
            if isinstance(r, dict):
                return r

        # ── 2. 再试 API 端点 ──
        r = _try_endpoints(api_endpoints, use_platform_headers=False)
        if isinstance(r, dict):
            return r

        # ── 3. 回退缓存（取最新匹配文件）──
        prefix = f"usage_{ym}_"
        try:
            candidates = sorted(
                [p for p in CSV_CACHE_DIR.iterdir() if p.is_file() and p.name.startswith(prefix)],
                key=lambda p: p.stat().st_mtime, reverse=True,
            )
        except Exception:
            candidates = []
        if candidates:
            logger.info("下载失败，回退缓存: %s", candidates[0].name)
            try:
                with open(candidates[0], "rb") as fh:
                    result = _parse_csv_zip(fh.read(), target_date)
                if result["total_calls"] > 0 or result["total_cost"] > 0:
                    return result
            except Exception:
                logger.warning("缓存损坏", exc_info=True)

        logger.warning("所有 CSV 端点均失败，且无可用缓存")
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
    解析 platform.deepseek.com /api/v0/usage/cost 返回的 JSON。
    实际结构: data.biz_data[0] = { total: [...], days: [{date, data: [...]}] }
    每日 data[] 中每项: {model, usage: [{type, amount}, ...]}
    amount 为费用 (CNY)。token 数量通过单价反推（估算）。
    """
    if target_date is None:
        target_date = date.today().isoformat()
    elif isinstance(target_date, date):
        target_date = target_date.isoformat()

    # 定位 biz_data
    biz_data = data
    if isinstance(data, dict):
        biz_data = data.get("biz_data") or data.get("data") or data
    if isinstance(biz_data, list):
        biz_data = biz_data[0] if biz_data else {}
    if not isinstance(biz_data, dict):
        logger.warning("平台 API biz_data 格式异常")
        return None

    days = biz_data.get("days") or []
    if not days:
        logger.warning("平台 API 返回无 days 数据")
        return None

    # ── 累计每日 + 按模型 ──
    daily_history = []
    by_model = {}
    month_cost = 0.0
    month_input = 0
    month_output = 0
    month_cache_hit = 0

    # 用于提取 selected_date 的 token 合计
    daily_tokens = {}   # {date: {"input": int, "output": int, "cache_hit": int}}

    for day in days:
        d = day.get("date", "").strip()
        if not d:
            continue

        day_cost = 0.0
        day_input = 0
        day_output = 0
        day_cache_hit = 0

        for entry in day.get("data", []):
            model = entry.get("model", "unknown")
            pricing = _PLATFORM_PRICING.get(model, _DEFAULT_PLATFORM_PRICING)
            mc_cost = 0.0
            mc_cache_hit_cost = 0.0
            mc_cache_miss_cost = 0.0
            mc_output_cost = 0.0

            for u in entry.get("usage", []):
                amt = float(u.get("amount", 0))
                t = u.get("type", "")
                if t == "PROMPT_CACHE_HIT_TOKEN":
                    mc_cache_hit_cost += amt
                elif t == "PROMPT_CACHE_MISS_TOKEN":
                    mc_cache_miss_cost += amt
                elif t == "RESPONSE_TOKEN":
                    mc_output_cost += amt
                elif t in ("PROMPT_TOKEN", "INPUT_TOKEN"):
                    mc_cache_miss_cost += amt   # 无缓存 prompt 按 miss 算
                mc_cost += amt

            day_cost += mc_cost

            if mc_cost <= 0:
                continue

            # 从费用反推 token 数（估算）
            ch_tok, cm_tok, out_tok = _cost_to_tokens(
                mc_cache_hit_cost, mc_cache_miss_cost, mc_output_cost, pricing
            )
            inp_tok = ch_tok + cm_tok

            day_input += inp_tok
            day_output += out_tok
            day_cache_hit += ch_tok

            if model not in by_model:
                by_model[model] = {"input": 0, "output": 0, "cache_hit": 0, "calls": 0, "cost": 0.0}
            by_model[model]["input"]     += inp_tok
            by_model[model]["output"]    += out_tok
            by_model[model]["cache_hit"] += ch_tok
            by_model[model]["cost"]      += mc_cost

        month_cost      += day_cost
        month_input     += day_input
        month_output    += day_output
        month_cache_hit += day_cache_hit
        daily_tokens[d] = {"input": day_input, "output": day_output, "cache_hit": day_cache_hit}
        daily_history.append({
            "date": d,
            "tokens": day_input + day_output,
            "cost": day_cost,
            "calls": 0,
        })

    all_dates = sorted(item["date"] for item in daily_history)
    latest_date = all_dates[-1]
    selected_date = target_date if target_date in all_dates else latest_date
    selected_cost = sum(item["cost"] for item in daily_history if item["date"] == selected_date)
    sel_tok = daily_tokens.get(selected_date, {"input": 0, "output": 0, "cache_hit": 0})

    return {
        "total_input":    sel_tok["input"],
        "total_output":   sel_tok["output"],
        "total_calls":    0,
        "total_cost":     selected_cost,
        "by_model":       by_model,
        "selected_date":  selected_date,
        "latest_date":    latest_date,
        "daily_history":  daily_history,
        "month_input":    month_input,
        "month_output":   month_output,
        "month_cache_hit":month_cache_hit,
        "month_calls":    0,
        "month_cost":     month_cost,
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

        calls = int(r.get("total_requests") or r.get("request_count") or
                    r.get("api_calls") or r.get("count") or 0)
        if calls <= 0:
            calls = 1

        result["total_input"] += pin
        result["total_output"] += pout
        result["total_calls"] += calls
        result["total_cost"] += cost

        if model not in result["by_model"]:
            result["by_model"][model] = {"input": 0, "output": 0, "cache_hit": 0, "calls": 0, "cost": 0.0}
        result["by_model"][model]["input"] += pin
        result["by_model"][model]["output"] += pout
        result["by_model"][model]["calls"] += calls
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

