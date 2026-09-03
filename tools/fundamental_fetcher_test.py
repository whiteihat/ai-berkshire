"""fundamental_fetcher.py 单元测试。

使用 pytest 框架，按功能模块划分测试类，覆盖核心链路的正常与异常场景。
运行方式：uv run pytest tools/fundamental_fetcher_test.py -v
"""

import json
import os
import shutil
import sys
import tempfile
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import pytest

# 确保能 import tools 下的模块
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from fundamental_fetcher import (
    FINANCIAL_APIS,
    _check_report_disclosed,
    _disclosure_deadline,
    _get_report_periods,
    _load_manifest,
    _report_type,
    _save_json,
    _save_manifest,
    _should_retry_period,
)


# ---------------------------------------------------------------------------
# 报告期生成（_get_report_periods）
# ---------------------------------------------------------------------------


class TestGetReportPeriods:
    """测试报告期列表生成逻辑。"""

    def test_10_years_plus_current(self):
        """10+N 模式：当年已发布期间 + 近10个完整年度。"""
        periods = _get_report_periods(10)
        current_year = date.today().year
        # 当年期间数取决于今天在年内位置
        today = date.today()
        expected_current = sum(
            1 for mm, dd in (("03", "31"), ("06", "30"), ("09", "30"), ("12", "31"))
            if date(current_year, int(mm), int(dd)) <= today
        )
        assert len(periods) == expected_current + 40  # 当年 + 10年×4期

    def test_current_year_periods_come_first(self):
        """当年已发布期间应排在列表最前面。"""
        periods = _get_report_periods(10)
        current_year = date.today().year
        current_periods = [p for p in periods if int(p[:4]) == current_year]
        assert periods[: len(current_periods)] == current_periods

    def test_historical_periods_in_descending_order(self):
        """历史期间按年份降序排列。"""
        periods = _get_report_periods(10)
        current_year = date.today().year
        historical = [p for p in periods if int(p[:4]) < current_year]
        years = [int(p[:4]) for p in historical]
        # 每4个期间同一年份，年份应递减
        for i in range(0, len(years), 4):
            chunk = years[i : i + 4]
            assert len(set(chunk)) == 1, f"同一组4个期间应为同一年份: {chunk}"
        # 年份组应递减
        year_groups = [years[i] for i in range(0, len(years), 4)]
        assert year_groups == sorted(year_groups, reverse=True)

    def test_custom_years(self):
        """--years 参数可自定义回溯年数。"""
        for n in [5, 3, 1]:
            periods = _get_report_periods(n)
            current_year = date.today().year
            historical = [p for p in periods if int(p[:4]) < current_year]
            assert len(historical) == n * 4

    def test_all_periods_have_valid_format(self):
        """所有期间格式为 YYYYMMDD。"""
        periods = _get_report_periods(10)
        for p in periods:
            assert len(p) == 8
            assert p.isdigit()
            assert p[4:6] in ("03", "06", "09", "12")
            assert p[6:8] in ("31", "30")

    def test_no_duplicate_periods(self):
        """期间列表无重复。"""
        periods = _get_report_periods(10)
        assert len(periods) == len(set(periods))


# ---------------------------------------------------------------------------
# 披露截止日（_disclosure_deadline）
# ---------------------------------------------------------------------------


class TestDisclosureDeadline:
    """测试 A 股法定披露截止日计算。"""

    def test_annual_report(self):
        """年报(1231)截止日为次年4月30日。"""
        assert _disclosure_deadline("20251231") == date(2026, 4, 30)
        assert _disclosure_deadline("20201231") == date(2021, 4, 30)

    def test_semi_annual_report(self):
        """中报(0630)截止日为当年8月31日。"""
        assert _disclosure_deadline("20260630") == date(2026, 8, 31)

    def test_q1_report(self):
        """一季报(0331)截止日为当年4月30日。"""
        assert _disclosure_deadline("20260331") == date(2026, 4, 30)

    def test_q3_report(self):
        """三季报(0930)截止日为当年10月31日。"""
        assert _disclosure_deadline("20260930") == date(2026, 10, 31)

    def test_invalid_period_returns_none(self):
        """无效期间格式返回 None。"""
        assert _disclosure_deadline("20260101") is None
        assert _disclosure_deadline("abc") is None
        assert _disclosure_deadline("") is None


# ---------------------------------------------------------------------------
# 报告类型（_report_type）
# ---------------------------------------------------------------------------


class TestReportType:
    """测试报告期类型判断。"""

    def test_all_types(self):
        assert _report_type("20251231") == "annual"
        assert _report_type("20260630") == "semi"
        assert _report_type("20260331") == "Q1"
        assert _report_type("20260930") == "Q3"

    def test_unknown_period(self):
        assert _report_type("20260101") == "unknown"
        assert _report_type("abc") == "unknown"


# ---------------------------------------------------------------------------
# 公告交叉验证（_check_report_disclosed）
# ---------------------------------------------------------------------------


class TestCheckReportDisclosed:
    """测试公告元数据交叉验证披露状态。"""

    def test_disclosed_by_keyword_match(self):
        """标题含期间关键词且日期在截止日前 → 已披露。"""
        anns = [
            {"title": "2025年年度报告", "notice_date": "2026-03-28"},
        ]
        assert _check_report_disclosed("20251231", anns) is True

    def test_disclosed_semi_annual(self):
        """中报关键词匹配。"""
        anns = [
            {"title": "2026年半年度报告", "notice_date": "2026-08-23"},
        ]
        assert _check_report_disclosed("20260630", anns) is True

    def test_not_yet_disclosed(self):
        """已过截止日但公告中未找到 → False。"""
        # 使用一个足够旧的期间确保已过截止日
        anns = [{"title": "其他公告", "notice_date": "2025-01-01"}]
        # 20230630 截止日 2023-08-31，今天远晚于该日
        result = _check_report_disclosed("20230630", anns)
        assert result is False

    def test_deadline_not_reached(self):
        """未过截止日 → None（无法判断）。"""
        # 构造一个未来的截止日场景
        future_year = date.today().year + 5
        period = f"{future_year}1231"
        anns = []
        result = _check_report_disclosed(period, anns)
        assert result is None

    def test_no_announcements(self):
        """无公告数据 → None。"""
        assert _check_report_disclosed("20251231", []) is None
        assert _check_report_disclosed("20251231", None) is None

    def test_historical_period_skipped(self):
        """超过3年的历史期间不做公告验证 → None。"""
        old_year = date.today().year - 5
        period = f"{old_year}1231"
        result = _check_report_disclosed(period, [])
        assert result is None

    def test_announcement_after_deadline(self):
        """公告日期在截止日之后（允许3天缓冲）→ 仍视为已披露。"""
        anns = [
            {"title": "2025年年度报告", "notice_date": "2026-05-02"},  # 截止日+2天
        ]
        assert _check_report_disclosed("20251231", anns) is True

    def test_announcement_far_after_deadline(self):
        """公告日期远超截止日+3天缓冲 → 不视为已披露。"""
        anns = [
            {"title": "2025年年度报告", "notice_date": "2026-06-01"},  # 截止日+32天
        ]
        # 已过截止日+缓冲且不在今天之前 → False
        result = _check_report_disclosed("20251231", anns)
        assert result is False


# ---------------------------------------------------------------------------
# 智能重试判断（_should_retry_period）
# ---------------------------------------------------------------------------


class TestShouldRetryPeriod:
    """测试期间智能重试决策逻辑。"""

    @pytest.fixture
    def temp_stock_dir(self):
        """创建临时落盘目录结构。"""
        tmp = tempfile.mkdtemp()
        fin_dir = os.path.join(tmp, "raw", "financial")
        os.makedirs(fin_dir)
        manifest = {"periods": {}}
        yield tmp, fin_dir, manifest
        shutil.rmtree(tmp)

    def test_all_files_missing(self, temp_stock_dir):
        """所有文件缺失 → 重试。"""
        stock_dir, fin_dir, manifest = temp_stock_dir
        ok, reason = _should_retry_period("20251231", stock_dir, fin_dir, manifest)
        assert ok is True
        assert "缺失" in reason

    def test_all_files_empty(self, temp_stock_dir):
        """所有文件为空 → 重试。"""
        stock_dir, fin_dir, manifest = temp_stock_dir
        for api in FINANCIAL_APIS:
            with open(os.path.join(fin_dir, f"{api}_20250930.json"), "w") as f:
                json.dump([], f)
        ok, reason = _should_retry_period("20250930", stock_dir, fin_dir, manifest)
        assert ok is True
        assert "空" in reason

    def test_core_api_incomplete(self, temp_stock_dir):
        """核心接口不完整 → 重试。"""
        stock_dir, fin_dir, manifest = temp_stock_dir
        for api in ["income", "balancesheet", "cashflow", "fina_indicator"]:
            with open(os.path.join(fin_dir, f"{api}_20241231.json"), "w") as f:
                json.dump([{"test": "data"}], f)
        # 删除 fina_indicator 模拟不完整
        os.remove(os.path.join(fin_dir, "fina_indicator_20241231.json"))
        ok, reason = _should_retry_period("20241231", stock_dir, fin_dir, manifest)
        assert ok is True
        assert "fina_indicator" in reason

    def test_all_complete(self, temp_stock_dir):
        """所有核心接口完整 → 跳过。"""
        stock_dir, fin_dir, manifest = temp_stock_dir
        for api in FINANCIAL_APIS:
            with open(os.path.join(fin_dir, f"{api}_20250630.json"), "w") as f:
                json.dump([{"test": "data"}], f)
        ok, reason = _should_retry_period("20250630", stock_dir, fin_dir, manifest)
        assert ok is False
        assert "完整" in reason

    def test_deadline_passed_no_data(self, temp_stock_dir):
        """已过披露截止日但 manifest 和文件均无数据 → 重试。"""
        stock_dir, fin_dir, manifest = temp_stock_dir
        # 20240331 截止日 2024-04-30，已过
        ok, reason = _should_retry_period("20240331", stock_dir, fin_dir, manifest)
        assert ok is True
        # 规则 1（文件缺失）优先于规则 4（截止日），两者都应触发重试
        assert "缺失" in reason or "截止日" in reason

    def test_deadline_passed_file_exists(self, temp_stock_dir):
        """已过截止日但文件实际存在（manifest 不完整）→ 跳过。"""
        stock_dir, fin_dir, manifest = temp_stock_dir
        for api in ["income", "balancesheet", "cashflow", "fina_indicator"]:
            with open(os.path.join(fin_dir, f"{api}_20240630.json"), "w") as f:
                json.dump([{"test": "data"}], f)
        # manifest 无记录
        ok, reason = _should_retry_period("20240630", stock_dir, fin_dir, manifest)
        assert ok is False
        assert "完整" in reason

    def test_partial_api_empty_file(self, temp_stock_dir):
        """部分 API 文件为空 → 重试。"""
        stock_dir, fin_dir, manifest = temp_stock_dir
        with open(os.path.join(fin_dir, "income_20250930.json"), "w") as f:
            json.dump([{"test": "data"}], f)
        # 其余核心 API 文件为空
        for api in ["balancesheet", "cashflow", "fina_indicator"]:
            with open(os.path.join(fin_dir, f"{api}_20250930.json"), "w") as f:
                json.dump([], f)
        ok, reason = _should_retry_period("20250930", stock_dir, fin_dir, manifest)
        assert ok is True
        assert "核心接口不完整" in reason

    def test_with_announcements_incomplete_core(self, temp_stock_dir):
        """核心文件不完整 + 公告中未找到 → 重试。"""
        stock_dir, fin_dir, manifest = temp_stock_dir
        # 只放 income，其余缺失
        with open(os.path.join(fin_dir, "income_20240930.json"), "w") as f:
            json.dump([{"test": "data"}], f)
        anns = [{"title": "2024年第三季度报告", "notice_date": "2024-10-28"}]
        ok, reason = _should_retry_period(
            "20240930", stock_dir, fin_dir, manifest, anns
        )
        assert ok is True


# ---------------------------------------------------------------------------
# Manifest 读写
# ---------------------------------------------------------------------------


class TestManifestIO:
    """测试 manifest.json 的读写。"""

    @pytest.fixture
    def temp_dir(self):
        tmp = tempfile.mkdtemp()
        yield tmp
        shutil.rmtree(tmp)

    def test_load_missing_manifest(self, temp_dir):
        """manifest 不存在 → 返回空结构。"""
        m = _load_manifest(temp_dir)
        assert m == {"periods": {}, "metadata": {}, "last_fetch": None}

    def test_save_and_load_manifest(self, temp_dir):
        """保存后能正确读回。"""
        data = {
            "periods": {"20251231": {"income": True}},
            "metadata": {"stock_basic": True},
            "last_fetch": "2026-01-01",
        }
        _save_manifest(temp_dir, data)
        loaded = _load_manifest(temp_dir)
        assert loaded["periods"]["20251231"]["income"] is True
        assert loaded["last_fetch"] == "2026-01-01"


# ---------------------------------------------------------------------------
# JSON 保存
# ---------------------------------------------------------------------------


class TestSaveJson:
    """测试 JSON 保存工具函数。"""

    def test_save_and_read_back(self, tmp_path):
        """保存 JSON 后能正确读回。"""
        filepath = str(tmp_path / "test.json")
        records = [{"name": "测试", "value": 123}]
        _save_json(records, filepath)
        with open(filepath, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        assert loaded == records

    def test_save_empty_list(self, tmp_path):
        """保存空列表。"""
        filepath = str(tmp_path / "empty.json")
        _save_json([], filepath)
        with open(filepath, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        assert loaded == []

    def test_save_non_ascii(self, tmp_path):
        """保存中文内容正确编码。"""
        filepath = str(tmp_path / "cn.json")
        _save_json({"公司": "美利云"}, filepath)
        with open(filepath, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        assert loaded["公司"] == "美利云"


# ---------------------------------------------------------------------------
# 端到端：fetch_stock 参数验证（不实际调用 API）
# ---------------------------------------------------------------------------


class TestFetchStockSignature:
    """验证 fetch_stock 函数签名和参数校验。"""

    def test_function_exists_and_accepts_years(self):
        """fetch_stock 接受 years 参数。"""
        from fundamental_fetcher import fetch_stock
        import inspect

        sig = inspect.signature(fetch_stock)
        assert "years" in sig.parameters
        assert sig.parameters["years"].default == 10

    def test_function_accepts_skip_existing(self):
        """fetch_stock 接受 skip_existing 参数。"""
        from fundamental_fetcher import fetch_stock
        import inspect

        sig = inspect.signature(fetch_stock)
        assert "skip_existing" in sig.parameters
        assert sig.parameters["skip_existing"].default is True
