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
from datetime import date

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


if __name__ == "__main__":
    unittest.main()
