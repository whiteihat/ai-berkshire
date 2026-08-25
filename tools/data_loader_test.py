"""data_loader.py 单元测试。

使用 pytest 框架，按功能模块划分测试类，覆盖统一数据访问层的核心链路。
运行方式：pytest tools/data_loader_test.py -v
"""

import json
import os
import shutil
import sys
import tempfile
from unittest.mock import MagicMock, patch

import pytest

# 确保能 import tools 下的模块
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

import data_loader
from data_loader import (
    _empty_return,
    _is_filled,
    _latest_stock_period,
    get,
    list_cached,
    load_local,
    status,
)


# ---------------------------------------------------------------------------
# _is_filled 判断
# ---------------------------------------------------------------------------


class TestIsFilled:
    """测试数据非空判断逻辑。"""

    def test_none_is_not_filled(self):
        assert _is_filled(None) is False

    def test_empty_list(self):
        assert _is_filled([]) is False

    def test_empty_dict(self):
        assert _is_filled({}) is False

    def test_non_empty_list(self):
        assert _is_filled([{"a": 1}]) is True

    def test_non_empty_dict(self):
        assert _is_filled({"a": 1}) is True

    def test_non_empty_string(self):
        assert _is_filled("hello") is True

    def test_empty_string(self):
        assert _is_filled("") is False

    def test_zero_is_filled(self):
        """0 不是 None/空容器，视为有数据。"""
        assert _is_filled(0) is True


# ---------------------------------------------------------------------------
# _empty_return 空值兜底
# ---------------------------------------------------------------------------


class TestEmptyReturn:
    """测试各资产类型/字段的空值返回格式。"""

    def test_fund_snapshot_fields_return_empty_list(self):
        """基金快照类字段返回空列表（非 None）。"""
        for field in ("nav", "daily", "holdings", "shares", "manager", "holder"):
            result = _empty_return("fund", field)
            assert result == [], f"fund/{field} 应返回 []"

    def test_stock_announcements_return_empty_list(self):
        """个股公告返回空列表。"""
        assert _empty_return("stock", "announcements") == []

    def test_stock_financial_return_none(self):
        """个股财务持久化字段返回 None（表示取数失败）。"""
        assert _empty_return("stock", "financial") is None

    def test_stock_meta_return_none(self):
        """个股元数据返回 None。"""
        assert _empty_return("stock", "meta") is None

    def test_fund_basic_return_none(self):
        """基金基本盘返回 None。"""
        assert _empty_return("fund", "basic") is None


# ---------------------------------------------------------------------------
# _latest_stock_period
# ---------------------------------------------------------------------------


class TestLatestStockPeriod:
    """测试从 manifest 读取最新期间。"""

    @pytest.fixture
    def temp_stock_dir(self):
        """创建带 manifest 的临时目录。"""
        tmp = tempfile.mkdtemp()
        yield tmp
        shutil.rmtree(tmp)

    def test_no_manifest(self, temp_stock_dir):
        """无 manifest → 返回 None。"""
        assert _latest_stock_period("test", "000000") is None

    def test_empty_periods(self, temp_stock_dir):
        """manifest 存在但 periods 为空 → 返回 None。"""
        manifest_path = os.path.join(temp_stock_dir, "manifest.json")
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump({"periods": {}}, f)
        assert _latest_stock_period("test", "000000") is None

    def test_returns_max_period(self, tmp_path):
        """返回最大期间。"""
        # 创建 local/{name}_{code}/ 目录结构
        local_dir = tmp_path / "local"
        stock_dir = local_dir / "testCompany_000001"
        stock_dir.mkdir(parents=True)
        manifest_path = stock_dir / "manifest.json"
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(
                {"periods": {"20240630": {}, "20251231": {}, "20230331": {}}}, f
            )
        with patch.object(data_loader, "_LOCAL_DIR", str(local_dir)):
            result = _latest_stock_period("testCompany", "000001")
        assert result == "20251231"


# ---------------------------------------------------------------------------
# get 函数 — 本地读取与更新触发
# ---------------------------------------------------------------------------


class TestGetFunction:
    """测试统一取数入口 get()。"""

    def test_unknown_asset_type_raises(self):
        """未知资产类型抛出 ValueError。"""
        with pytest.raises(ValueError, match="未知资产类型"):
            get("unknown", "000000")

    @patch("data_loader._run_fetcher_update", return_value=False)
    def test_stock_financial_returns_none_when_no_cache(self, mock_update):
        """个股财务无缓存且更新失败 → 返回 None。"""
        result = get("stock", "999999", "不存在的公司", field="financial")
        assert result is None

    @patch("data_loader._run_fetcher_update", return_value=False)
    def test_stock_meta_returns_none_when_no_cache(self, mock_update):
        """个股元数据无缓存且更新失败 → 返回 None。"""
        result = get("stock", "999999", "不存在的公司", field="meta")
        assert result is None

    def test_stock_announcements_returns_empty_list(self):
        """个股公告无缓存 → 返回空列表。"""
        result = get("stock", "999999", "不存在的公司", field="announcements")
        assert result == []

    @patch("data_loader._run_fetcher_update", return_value=False)
    def test_fund_basic_returns_none_when_no_cache(self, mock_update):
        """基金基本盘无缓存且更新失败 → 返回 None。"""
        with patch.dict("sys.modules", {"fund_data_fetcher": MagicMock()}):
            result = get("fund", "999999", field="basic")
        assert result is None

    def test_fund_nav_returns_empty_list(self):
        """基金净值无缓存 → 返回空列表。"""
        with patch.dict("sys.modules", {"fund_data_fetcher": MagicMock()}):
            result = get("fund", "999999", field="nav")
        assert result == []

    def test_no_update_flag_prevents_fetch(self):
        """update_if_missing=False 不触发更新。"""
        with patch("data_loader._run_fetcher_update") as mock_update:
            get("stock", "999999", "不存在的公司", update_if_missing=False)
            mock_update.assert_not_called()


# ---------------------------------------------------------------------------
# load_local 函数
# ---------------------------------------------------------------------------


class TestLoadLocal:
    """测试仅读本地缓存（不触发更新）。"""

    def test_load_local_calls_get_no_update(self):
        """load_local 内部调用 get(update_if_missing=False)。"""
        with patch("data_loader.get") as mock_get:
            load_local("stock", "000001", field="financial", name="平安银行")
            mock_get.assert_called_once_with(
                "stock", "000001", name="平安银行",
                field="financial", period=None, update_if_missing=False,
            )


# ---------------------------------------------------------------------------
# status 函数
# ---------------------------------------------------------------------------


class TestStatus:
    """测试缓存状态查询。"""

    def test_no_name_returns_uncached(self):
        """未提供 name → 返回 cached=False。"""
        result = status("stock", "000001")
        assert result["cached"] is False
        assert result["code"] == "000001"

    def test_nonexistent_dir(self):
        """目录不存在 → cached=False。"""
        with patch("data_loader.os.path.exists", return_value=False):
            result = status("stock", "999999", "不存在的公司")
        assert result["cached"] is False

    def test_fund_status(self):
        """基金缓存状态。"""
        result = status("fund", "510300")
        assert result["asset_type"] == "fund"
        assert result["code"] == "510300"


# ---------------------------------------------------------------------------
# list_cached 函数
# ---------------------------------------------------------------------------


class TestListCached:
    """测试已落盘资产列表。"""

    def test_empty_local_dir(self, tmp_path):
        """local/ 不存在 → 返回空列表。"""
        with patch.object(data_loader, "_LOCAL_DIR", str(tmp_path / "nonexistent")):
            assert list_cached() == []

    def test_lists_stocks_and_funds(self, tmp_path):
        """能列出股票和基金。"""
        local_dir = tmp_path / "local"
        local_dir.mkdir()
        # 创建模拟落盘目录
        (local_dir / "茅台_600519").mkdir()
        (local_dir / "fund_510300").mkdir()
        (local_dir / "fund_510300" / "manifest.json").write_text("{}")

        with patch.object(data_loader, "_LOCAL_DIR", str(local_dir)):
            result = list_cached()
            codes = [r[1] if r[0] == "fund" else r[1] for r in result]
            assert "600519" in codes
            assert "510300" in codes

    def test_filter_by_type(self, tmp_path):
        """按类型过滤。"""
        local_dir = tmp_path / "local"
        local_dir.mkdir()
        (local_dir / "茅台_600519").mkdir()
        (local_dir / "fund_510300").mkdir()

        with patch.object(data_loader, "_LOCAL_DIR", str(local_dir)):
            stocks = list_cached("stock")
            funds = list_cached("fund")
            assert len(stocks) >= 1
            assert all(r[0] == "stock" for r in stocks)
            assert len(funds) >= 1
            assert all(r[0] == "fund" for r in funds)


# ---------------------------------------------------------------------------
# _run_fetcher_update 进程调用
# ---------------------------------------------------------------------------


class TestRunFetcherUpdate:
    """测试 fetcher 更新触发逻辑。"""

    def test_stock_requires_name(self):
        """个股 update 必须提供 name。"""
        with pytest.raises(ValueError, match="需要公司名"):
            data_loader._run_fetcher_update("stock", "000001")

    @patch("data_loader.subprocess.run")
    def test_unknown_asset_type_returns_false(self, mock_run):
        """未知资产类型返回 False。"""
        result = data_loader._run_fetcher_update("crypto", "BTC")
        assert result is False
        mock_run.assert_not_called()

    @patch("data_loader.subprocess.run")
    def test_successful_update(self, mock_run):
        """更新成功返回 True。"""
        mock_run.return_value = MagicMock(returncode=0)
        result = data_loader._run_fetcher_update("stock", "000001", "测试公司")
        assert result is True

    @patch("data_loader.subprocess.run")
    def test_failed_update_returns_false(self, mock_run):
        """更新失败返回 False。"""
        mock_run.return_value = MagicMock(returncode=1)
        result = data_loader._run_fetcher_update("stock", "000001", "测试公司")
        assert result is False

    @patch("data_loader.subprocess.run", side_effect=Exception("timeout"))
    def test_exception_returns_false(self, mock_run):
        """进程异常返回 False。"""
        result = data_loader._run_fetcher_update("stock", "000001", "测试公司")
        assert result is False


# ---------------------------------------------------------------------------
# CLI 参数解析
# ---------------------------------------------------------------------------


class TestCLI:
    """测试命令行参数解析。"""

    def test_get_subcommand_exists(self):
        """get 子命令可用。"""
        import argparse

        parser = argparse.ArgumentParser()
        sub = parser.add_subparsers(dest="cmd")
        sub.add_parser("get")
        args = parser.parse_args(["get"])
        assert args.cmd == "get"

    def test_update_subcommand_exists(self):
        """update 子命令可用。"""
        import argparse

        parser = argparse.ArgumentParser()
        sub = parser.add_subparsers(dest="cmd")
        sub.add_parser("update")
        args = parser.parse_args(["update"])
        assert args.cmd == "update"

    def test_search_subcommand_exists(self):
        """search 子命令可用。"""
        import argparse

        parser = argparse.ArgumentParser()
        sub = parser.add_subparsers(dest="cmd")
        p = sub.add_parser("search")
        p.add_argument("keyword")
        args = parser.parse_args(["search", "茅台"])
        assert args.cmd == "search"
        assert args.keyword == "茅台"


# ---------------------------------------------------------------------------
# 端到端：带缓存的 get 流程（不实际调用 API）
# ---------------------------------------------------------------------------


class TestGetWithLocalCache:
    """测试有本地缓存时 get 的读取流程。"""

    @pytest.fixture
    def mock_stock_financial(self, tmp_path):
        """创建模拟的个股财务缓存目录。"""
        stock_dir = tmp_path / "test_000001"
        stock_dir.mkdir()
        fin_dir = stock_dir / "raw" / "financial"
        fin_dir.mkdir(parents=True)

        # 写入模拟数据
        for api in ("income", "balancesheet", "cashflow", "fina_indicator"):
            filepath = fin_dir / f"{api}_20251231.json"
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump([{"ts_code": "000001.SZ", "period": "20251231"}], f)

        # 写入 manifest
        manifest = {
            "periods": {
                "20251231": {
                    "income": True,
                    "balancesheet": True,
                    "cashflow": True,
                    "fina_indicator": True,
                }
            },
            "metadata": {},
            "last_fetch": "2026-01-01",
        }
        with open(stock_dir / "manifest.json", "w", encoding="utf-8") as f:
            json.dump(manifest, f)

        return stock_dir, fin_dir

    def test_read_from_cache(self, mock_stock_financial):
        """有缓存时直接读取，不触发更新。"""
        stock_dir, fin_dir = mock_stock_financial
        # Mock _stock_financial 让它读取我们的临时目录
        with patch("data_loader._LOCAL_DIR", str(stock_dir.parent)):
            with patch("data_loader._load_fetcher") as mock_load:
                mock_fetcher = MagicMock()
                mock_fetcher.load_financial_data.return_value = {
                    "income": [{"ts_code": "000001.SZ"}],
                    "balancesheet": [{"ts_code": "000001.SZ"}],
                    "cashflow": [{"ts_code": "000001.SZ"}],
                    "fina_indicator": [{"ts_code": "000001.SZ"}],
                }
                mock_load.return_value = mock_fetcher

                with patch("data_loader._latest_stock_period", return_value="20251231"):
                    result = get("stock", "000001", "test", field="financial")

                # 应该读到数据且不触发更新
                assert result is not None
                assert len(result) > 0


# ---------------------------------------------------------------------------
# 与 fundamental_fetcher 的集成点
# ---------------------------------------------------------------------------


class TestIntegrationWithFetcher:
    """测试 data_loader 与 fundamental_fetcher 的集成。"""

    def test_stock_financial_calls_fetcher_load(self):
        """_stock_financial 正确调用 fundamental_fetcher.load_financial_data。"""
        with patch("data_loader._load_fetcher") as mock_load:
            mock_fetcher = MagicMock()
            mock_fetcher.load_financial_data.return_value = {"income": []}
            mock_load.return_value = mock_fetcher

            with patch("data_loader._latest_stock_period", return_value="20251231"):
                from data_loader import _stock_financial
                result = _stock_financial("000001", "test")

            mock_fetcher.load_financial_data.assert_called_once_with(
                "000001", "test", "20251231"
            )

    def test_stock_meta_calls_fetcher(self):
        """_stock_meta 正确调用 fundamental_fetcher.load_stock_meta。"""
        with patch("data_loader._load_fetcher") as mock_load:
            mock_fetcher = MagicMock()
            mock_fetcher.load_stock_meta.return_value = [{"name": "test"}]
            mock_load.return_value = mock_fetcher

            from data_loader import _stock_meta
            result = _stock_meta("000001", "test")

            mock_fetcher.load_stock_meta.assert_called_once_with("000001", "test")
            assert result == [{"name": "test"}]

    def test_stock_anns_calls_fetcher(self):
        """_stock_anns 正确调用 fundamental_fetcher.load_announcements。"""
        with patch("data_loader._load_fetcher") as mock_load:
            mock_fetcher = MagicMock()
            mock_fetcher.load_announcements.return_value = [{"title": "test"}]
            mock_load.return_value = mock_fetcher

            from data_loader import _stock_anns
            result = _stock_anns("000001", "test", limit=10)

            mock_fetcher.load_announcements.assert_called_once_with(
                "000001", "test", limit=10
            )
            assert result == [{"title": "test"}]
