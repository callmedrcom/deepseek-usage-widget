"""
Unit tests for DeepSeek Usage Widget core logic.
Run: python -m pytest test_deepseek_widget.py -v
Or:  python test_deepseek_widget.py
"""
import unittest
import io
import zipfile
import sys
import os
import tempfile
import shutil
from datetime import date
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from deepseek_usage_widget.api_client import (
    _parse_deepseek_csv,
    _parse_csv_zip,
    _aggregate_usage,
)
from deepseek_usage_widget.config import merge_daily_history
from deepseek_usage_widget.utils import _short_date, _chart_date
from crypto_utils import encrypt, decrypt


class TestCryptoUtils(unittest.TestCase):
    def test_encrypt_decrypt_roundtrip(self):
        original = "sk-test-api-key-12345"
        encrypted = encrypt(original)
        self.assertNotEqual(encrypted, original)
        self.assertNotEqual(encrypted, "")
        decrypted = decrypt(encrypted)
        self.assertEqual(decrypted, original)

    def test_encrypt_empty_string(self):
        self.assertEqual(encrypt(""), "")

    def test_decrypt_empty_string(self):
        self.assertEqual(decrypt(""), "")

    def test_decrypt_non_encrypted_falls_back(self):
        result = decrypt("plain-text-not-encrypted")
        self.assertEqual(result, "plain-text-not-encrypted")


class TestCSVParsing(unittest.TestCase):
    def setUp(self):
        self.amount_csv = (
            "utc_date,model,api_key_name,api_key,type,price,amount\n"
            "2026-05-10,deepseek-chat,key1,sk-xxx,output_tokens,8.0,5000\n"
            "2026-05-10,deepseek-chat,key1,sk-xxx,input_tokens,2.0,2000\n"
            "2026-05-10,deepseek-chat,key1,sk-xxx,input_cache_hit_tokens,0.2,1000\n"
            "2026-05-10,deepseek-chat,key1,sk-xxx,request_count,0,3\n"
        )

        self.cost_csv = (
            "user_id,utc_date,model,wallet_type,cost,currency\n"
            "user1,2026-05-10,deepseek-chat,granted,0.05,CNY\n"
        )

    def test_parse_amount_csv_basic(self):
        result = _parse_deepseek_csv(self.amount_csv, "", target_date="2026-05-10")
        self.assertEqual(result["total_input"], 3000)
        self.assertEqual(result["total_output"], 5000)
        self.assertEqual(result["total_calls"], 3)
        self.assertEqual(result["selected_date"], "2026-05-10")

    def test_parse_with_cost_csv(self):
        result = _parse_deepseek_csv(self.amount_csv, self.cost_csv, target_date="2026-05-10")
        self.assertAlmostEqual(result["total_cost"], 0.05)

    def test_parse_empty_csv(self):
        csv_text = "utc_date,model,api_key_name,api_key,type,price,amount\n"
        result = _parse_deepseek_csv(csv_text, "", target_date="2026-05-10")
        self.assertEqual(result["total_input"], 0)
        self.assertEqual(result["total_output"], 0)
        self.assertEqual(result["total_calls"], 0)

    def test_parse_missing_date_uses_latest(self):
        csv_text = (
            "utc_date,model,api_key_name,api_key,type,price,amount\n"
            "2026-05-08,deepseek-chat,key1,sk-xxx,output_tokens,8.0,100\n"
            "2026-05-09,deepseek-chat,key1,sk-xxx,output_tokens,8.0,200\n"
        )
        result = _parse_deepseek_csv(csv_text, "", target_date="2026-05-10")
        self.assertEqual(result["selected_date"], "2026-05-09")

    def test_parse_by_model(self):
        csv_text = (
            "utc_date,model,api_key_name,api_key,type,price,amount\n"
            "2026-05-10,deepseek-chat,key1,sk-xxx,output_tokens,8.0,500\n"
            "2026-05-10,deepseek-reasoner,key1,sk-xxx,output_tokens,16.0,300\n"
        )
        result = _parse_deepseek_csv(csv_text, "", target_date="2026-05-10")
        self.assertIn("deepseek-chat", result["by_model"])
        self.assertIn("deepseek-reasoner", result["by_model"])
        self.assertEqual(result["by_model"]["deepseek-chat"]["output"], 500)
        self.assertEqual(result["by_model"]["deepseek-reasoner"]["output"], 300)

    def test_parse_daily_history(self):
        csv_text = (
            "utc_date,model,api_key_name,api_key,type,price,amount\n"
            "2026-05-08,deepseek-chat,key1,sk-xxx,output_tokens,8.0,100\n"
            "2026-05-09,deepseek-chat,key1,sk-xxx,output_tokens,8.0,200\n"
        )
        result = _parse_deepseek_csv(csv_text, "")
        self.assertEqual(len(result["daily_history"]), 2)

    def test_monthly_aggregates(self):
        csv_text = (
            "utc_date,model,api_key_name,api_key,type,price,amount\n"
            "2026-05-08,deepseek-chat,key1,sk-xxx,output_tokens,8.0,100\n"
            "2026-05-09,deepseek-chat,key1,sk-xxx,input_tokens,2.0,200\n"
        )
        result = _parse_deepseek_csv(csv_text, "")
        self.assertEqual(result["month_input"], 200)
        self.assertEqual(result["month_output"], 100)
        self.assertEqual(result["month_input"] + result["month_output"], 300)


class TestCSVZipParsing(unittest.TestCase):
    def test_parse_zip_with_amount_csv(self):
        amount_csv = (
            "utc_date,model,api_key_name,api_key,type,price,amount\n"
            "2026-05-10,deepseek-chat,key1,sk-xxx,output_tokens,8.0,100\n"
        )
        cost_csv = (
            "user_id,utc_date,model,wallet_type,cost,currency\n"
            "user1,2026-05-10,deepseek-chat,granted,0.02,CNY\n"
        )

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("amount-2026-05.csv", amount_csv)
            zf.writestr("cost-2026-05.csv", cost_csv)

        result = _parse_csv_zip(buf.getvalue(), target_date=date(2026, 5, 10))
        self.assertEqual(result["total_output"], 100)
        self.assertAlmostEqual(result["total_cost"], 0.02)

    def test_zip_without_amount_raises(self):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("cost-2026-05.csv", "user_id,utc_date,model,wallet_type,cost,currency\n")

        with self.assertRaises(ValueError):
            _parse_csv_zip(buf.getvalue())


class TestDataAggregation(unittest.TestCase):
    def test_aggregate_already_aggregated(self):
        data = {"total_input": 100, "total_output": 200, "total_calls": 5,
                "total_cost": 0.01, "by_model": {}, "selected_date": "2026-05-10",
                "latest_date": "2026-05-10", "daily_history": [],
                "month_input": 100, "month_output": 200, "month_calls": 5, "month_cost": 0.01}
        result = _aggregate_usage(data)
        self.assertEqual(result["total_input"], 100)

    def test_aggregate_list_of_records(self):
        records = [
            {"prompt_tokens": 100, "completion_tokens": 50, "model": "deepseek-chat"},
            {"input_tokens": 200, "output_tokens": 100, "model": "deepseek-reasoner"},
        ]
        result = _aggregate_usage(records)
        self.assertEqual(result["total_input"], 300)
        self.assertEqual(result["total_output"], 150)
        self.assertEqual(result["total_calls"], 2)

    def test_aggregate_nested_data_dict(self):
        data = {"data": {"total_input_tokens": 500, "total_output_tokens": 300,
                          "total_requests": 10, "total_cost": 0.05}}
        result = _aggregate_usage(data)
        self.assertEqual(result["total_input"], 500)
        self.assertEqual(result["total_output"], 300)
        self.assertEqual(result["total_calls"], 10)


class TestHistoryMerge(unittest.TestCase):
    def test_merge_two_sources(self):
        source_a = [{"date": "2026-05-08", "tokens": 100, "cost": 0.1, "calls": 2}]
        source_b = [{"date": "2026-05-09", "tokens": 200, "cost": 0.2, "calls": 3}]
        merged = merge_daily_history(source_a, source_b)
        self.assertEqual(len(merged), 2)

    def test_merge_deduplicates_same_date(self):
        source_a = [{"date": "2026-05-08", "tokens": 100, "cost": 0.1, "calls": 2}]
        source_b = [{"date": "2026-05-08", "tokens": 999, "cost": 9.9, "calls": 99}]
        merged = merge_daily_history(source_a, source_b)
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["tokens"], 999)

    def test_merge_handles_empty_inputs(self):
        self.assertEqual(merge_daily_history(), [])
        self.assertEqual(merge_daily_history(None, []), [])

    def test_merge_dict_input(self):
        source = {"2026-05-08": {"date": "2026-05-08", "tokens": 50, "cost": 0.05, "calls": 1}}
        merged = merge_daily_history(source)
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["tokens"], 50)


class TestDateFormatters(unittest.TestCase):
    def test_short_date_valid(self):
        self.assertEqual(_short_date("2026-05-10"), "5/10")

    def test_short_date_empty(self):
        self.assertEqual(_short_date(""), "--")
        self.assertEqual(_short_date(None), "--")

    def test_short_date_invalid(self):
        self.assertEqual(_short_date("not-a-date"), "not-a-date")

    def test_chart_date_valid(self):
        self.assertEqual(_chart_date("2026-12-25"), "12.25")

    def test_chart_date_empty(self):
        self.assertEqual(_chart_date(""), "--")


class TestSettingsPersistence(unittest.TestCase):
    """v0.1.1: 设置保存/加载回归测试"""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self._orig_config_dir = None

    def tearDown(self):
        if self.tmpdir and os.path.isdir(self.tmpdir):
            shutil.rmtree(self.tmpdir, ignore_errors=True)
        if self._orig_config_dir is not None:
            from deepseek_usage_widget import models
            models.CONFIG_DIR = self._orig_config_dir

    def _patch_config_dir(self):
        from pathlib import Path
        from deepseek_usage_widget import models
        self._orig_config_dir = models.CONFIG_DIR
        models.CONFIG_DIR = Path(self.tmpdir)
        # 同步修正文件路径
        models.CONFIG_FILE = models.CONFIG_DIR / "config.json"
        models.DAILY_FILE = models.CONFIG_DIR / "daily.json"
        models.CSV_CACHE_DIR = models.CONFIG_DIR / "csv_cache"
        models.LOGO_FILE = models.CONFIG_DIR / "logo.png"

    def test_save_and_load_roundtrip(self):
        """保存后重新加载，关键字段值一致"""
        self._patch_config_dir()
        from deepseek_usage_widget.config import save_config, load_config

        cfg = load_config()
        cfg["api_key"] = "sk-test-roundtrip-key"
        cfg["platform_token"] = "test-platform-token-abc"
        cfg["refresh_interval"] = 120
        cfg["opacity"] = 0.75
        save_config(cfg)

        loaded = load_config()
        self.assertEqual(loaded["api_key"], "sk-test-roundtrip-key")
        self.assertEqual(loaded["platform_token"], "test-platform-token-abc")
        self.assertEqual(loaded["refresh_interval"], 120)
        self.assertAlmostEqual(loaded["opacity"], 0.75)

    def test_default_config_fills_missing_keys(self):
        """加载时缺失的 key 自动用默认值填充"""
        self._patch_config_dir()
        from deepseek_usage_widget.config import save_config, load_config

        partial = {"api_key": "sk-minimal", "refresh_interval": 30}
        save_config(partial)

        loaded = load_config()
        self.assertEqual(loaded["api_key"], "sk-minimal")
        self.assertEqual(loaded["refresh_interval"], 30)
        self.assertIn("opacity", loaded)
        self.assertIn("model_pricing", loaded)
        self.assertIn("base_url", loaded)

    def test_empty_keys_not_saved_as_encrypted(self):
        """空的 api_key / platform_token 不应被加密后写入磁盘"""
        self._patch_config_dir()
        from deepseek_usage_widget.config import save_config, load_config

        cfg = load_config()
        cfg["api_key"] = ""
        cfg["platform_token"] = ""
        save_config(cfg)

        loaded = load_config()
        self.assertEqual(loaded["api_key"], "")
        self.assertEqual(loaded["platform_token"], "")

    def test_daily_history_save_and_load(self):
        """日用量历史可正确保存和加载"""
        self._patch_config_dir()
        from deepseek_usage_widget.config import save_daily_history, load_daily_history

        data = {
            "2026-05-15": {"date": "2026-05-15", "tokens": 5000, "cost": 0.05, "calls": 10},
            "2026-05-16": {"date": "2026-05-16", "tokens": 3000, "cost": 0.03, "calls": 6},
        }
        save_daily_history(data)
        loaded = load_daily_history()
        self.assertEqual(len(loaded), 2)
        self.assertEqual(loaded["2026-05-15"]["tokens"], 5000)
        self.assertEqual(loaded["2026-05-16"]["calls"], 6)


class TestRefreshSourceTracking(unittest.TestCase):
    """v0.1.1: 刷新回退顺序与数据源追踪测试"""

    def test_source_labels_match_all_sources(self):
        """所有数据源标识都有对应的中文标签"""
        from deepseek_usage_widget.models import SOURCE_LABELS, FALLBACK_ORDER
        for source_id in FALLBACK_ORDER:
            self.assertIn(source_id, SOURCE_LABELS)
            self.assertTrue(len(SOURCE_LABELS[source_id]) > 0)

    def test_error_format_contains_source_and_action(self):
        """错误信息格式包含来源、错误描述和操作建议"""
        errors = [
            {"source": "API用量接口", "error": "连接超时", "action": "请检查网络连接"},
            {"source": "平台数据导出", "error": "401 Unauthorized", "action": "请检查 Platform Token 是否过期"},
        ]
        parts = []
        for err in errors:
            parts.append(f"{err['source']}失败: {err['error']}（{err['action']}）")
        error_text = "\n".join(parts)

        self.assertIn("API用量接口失败", error_text)
        self.assertIn("连接超时", error_text)
        self.assertIn("请检查网络连接", error_text)
        self.assertIn("平台数据导出失败", error_text)
        self.assertIn("401 Unauthorized", error_text)
        self.assertIn("Platform Token 是否过期", error_text)

    def test_fallback_order_is_declared(self):
        """刷新回退顺序声明与 ROADMAP 一致"""
        from deepseek_usage_widget.models import FALLBACK_ORDER
        self.assertEqual(FALLBACK_ORDER[0], "api")
        self.assertEqual(FALLBACK_ORDER[1], "zip_download")
        self.assertEqual(FALLBACK_ORDER[2], "platform_api")
        self.assertEqual(FALLBACK_ORDER[3], "local_zip")

    def test_no_key_error_message_is_actionable(self):
        """未配置 API Key 时给出可操作的提示"""
        has_key = False
        errors = []
        if not has_key:
            usage_error = "请设置 API Key 或 Platform Token 后开始获取数据"
        else:
            usage_error = " | ".join(str(e) for e in errors) if errors else "暂无用量数据"

        self.assertIn("API Key", usage_error)
        self.assertIn("Platform Token", usage_error)
        self.assertNotIn("暂无用量数据", usage_error)

    def test_multi_source_error_formatting(self):
        """多数据源全部失败时展示完整错误链"""
        errors = [
            {"source": "API用量接口", "error": "返回空数据", "action": "请确认账户存在用量记录"},
            {"source": "平台数据导出", "error": "所有下载端点均不可达", "action": "请检查 Platform Token 是否有效"},
            {"source": "平台费用接口", "error": "返回空数据", "action": "请确认平台账户存在消费记录"},
        ]
        parts = []
        for err in errors:
            parts.append(f"{err['source']}失败: {err['error']}（{err['action']}）")
        error_text = "\n".join(parts)

        self.assertEqual(len(parts), 3)
        self.assertIn("API用量接口失败", error_text)
        self.assertIn("平台数据导出失败", error_text)
        self.assertIn("平台费用接口失败", error_text)


class TestApiErrorMessages(unittest.TestCase):
    """v0.1.1: API 错误消息改进测试"""

    def test_error_msg_extracts_response_body(self):
        from deepseek_usage_widget.utils import _api_error_msg

        class MockResponse:
            status_code = 401
            def json(self):
                return {"message": "Invalid API key"}

        class MockError(Exception):
            def __init__(self):
                self.response = MockResponse()

        msg = _api_error_msg(MockError())
        self.assertIn("401", msg)
        self.assertIn("Invalid API key", msg)

    def test_error_msg_falls_back_to_str(self):
        from deepseek_usage_widget.utils import _api_error_msg

        msg = _api_error_msg(ValueError("parse error"))
        self.assertEqual(msg, "parse error")

    def test_error_msg_handles_non_json_response(self):
        from deepseek_usage_widget.utils import _api_error_msg

        class MockResponse:
            status_code = 502
            def json(self):
                raise ValueError("not json")

        class MockError(Exception):
            def __init__(self):
                self.response = MockResponse()

        msg = _api_error_msg(MockError())
        self.assertIn("502", msg)


if __name__ == "__main__":
    unittest.main()
