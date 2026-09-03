#!/usr/bin/env python3
"""统一数据访问层 — 所有 Skill 的唯一数据取数入口。

设计原则（对应 .claude/skills/financial-data/SKILL.md）：
    1. 本地优先：先读 local/ 落盘缓存（fundamental_fetcher / fund_data_fetcher 写入）。
    2. 主源唯一、退化明确：缓存未命中或不足时，按资产类型的单一退化链取数并落盘。
    3. 落盘复用：复用到落盘工具自身（fundamental_fetcher / fund_data_fetcher），
       不重新实现数据源，也不解析 CLI 文本——直接调用各自的读侧 load_* 函数，
       更新时通过对应 fetcher 的 update 子命令触发（保留其限流与权限退化）。
    4. 合理性校验交给上层（financial-data 规范），本层只负责"取到结构化数据"。

范围边界：
    - 纯计算（financial_rigor.py）本层不管。
    - 内容抓取（xueqiu_scraper.py，雪球发言）本层不管，属独立内容通道。
    - 台股走 twstock_data.py（FinMind 单链），美股/港股/A股走 fundamental/tushare 链。

个股财务回溯：写侧 fundamental_fetcher 采用"10+N"模式——默认拉取近十年（含季报/中报/
年报）并自动纳入当年已披露的报告期（如 2026 中报，不占十年名额）。时间对齐由
_should_retry_period 结合法定披露截止日和公告元数据自动处理；口径见 _get_report_periods
和 fundamental_fetcher 模块文档。

用法（由 Skill 调用，Schema 见 financial-data/SKILL.md）：
    import sys; sys.path.insert(0, "tools")
    from data_loader import get, load_local, update, search, status
    data = get("stock", "600938", "中国海油")
    data = get("fund", "510300")
    rows = load_local("fund_holdings", "161725")

    uv run python tools/data_loader.py get stock 600938 中国海油
    uv run python tools/data_loader.py get fund 510300
    uv run python tools/data_loader.py search 茅台
    uv run python tools/data_loader.py status 600938 中国海油

依赖：纯 stdlib（复用 fetchers，不新增第三方依赖）。
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_LOCAL_DIR = os.path.join(_ROOT, "local")
_TOOLS_DIR = os.path.join(_ROOT, "tools")

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")


# ---------------------------------------------------------------------------
# 资产类型到数据源的映射（单一退化链 + 落盘工具 + 读侧函数）
# ---------------------------------------------------------------------------

# 每类资产的本地缓存读取函数签名：(code, **kw) -> list|dict|None
# 这些函数直接 import 现有 fetchers，避免文本解析。

_STOCK_LOADERS = {
    # 通过 fundamental_fetcher 封装
    "financial": lambda code, name, **kw: _stock_financial(code, name, **kw),
    "meta": lambda code, name, **kw: _stock_meta(code, name, **kw),
    "announcements": lambda code, name, **kw: _stock_anns(code, name, **kw),
}

_FUND_LOADERS = {
    "basic": lambda code, **kw: _fund_loader("basic", code, **kw),
    "nav": lambda code, **kw: _fund_loader("nav", code, **kw),
    "daily": lambda code, **kw: _fund_loader("daily", code, **kw),
    "holdings": lambda code, **kw: _fund_loader("holdings", code, **kw),
    "shares": lambda code, **kw: _fund_loader("shares", code, **kw),
    "manager": lambda code, **kw: _fund_loader("manager", code, **kw),
    "holder": lambda code, **kw: _fund_loader("holder", code, **kw),
}

# 持久化 vs 快照：持久化字段缺失时触发 update 落盘；快照字段允许直接缺失返回
_PERSISTENT_FIELDS = {
    "stock": {"financial", "meta"},
    "fund": {"basic", "nav", "daily", "holdings", "shares", "manager", "holder"},
}


def _load_fetcher(module_name):
    """动态 import tools 下的 fetcher 模块（避免循环依赖）。"""
    sys.path.insert(0, _TOOLS_DIR)
    try:
        return __import__("fundamental_fetcher" if module_name == "fundamental" else module_name)
    finally:
        sys.path.remove(_TOOLS_DIR)


# ---------------------------------------------------------------------------
# 本地读（复用现有 fetchers 的 load_*）
# ---------------------------------------------------------------------------

def _stock_financial(code, name, period=None):
    try:
        m = _load_fetcher("fundamental")
        if period:
            return m.load_financial_data(code, name, period)
        # 无 period 时读 manifest 中最新的年度期间
        manifest_path = os.path.join(_LOCAL_DIR, f"{name}_{code}", "manifest.json")
        latest = _latest_stock_period(name, code)
        if not latest:
            return {}
        return m.load_financial_data(code, name, latest)
    except Exception:
        return {}


def _latest_stock_period(name, code):
    manifest_path = os.path.join(_LOCAL_DIR, f"{name}_{code}", "manifest.json")
    if not os.path.exists(manifest_path):
        return None
    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
        periods = list(manifest.get("periods", {}).keys())
        return max(periods) if periods else None
    except Exception:
        return None


def _stock_meta(code, name, **_):
    try:
        return _load_fetcher("fundamental").load_stock_meta(code, name)
    except Exception:
        return None


def _stock_anns(code, name, limit=20, **_):
    try:
        return _load_fetcher("fundamental").load_announcements(code, name, limit=limit)
    except Exception:
        return []


def _fund_loader(field, code, limit=90, period=None, **_):
    try:
        m = _load_fetcher("fund")
    except Exception:
        return []
    fns = {
        "basic": m.load_fund_basic,
        "nav": m.load_fund_nav,
        "daily": m.load_fund_daily,
        "holdings": m.load_fund_holdings,
        "shares": m.load_fund_shares,
        "manager": m.load_fund_manager,
        "holder": m.load_fund_holder,
    }
    fn = fns.get(field)
    if fn is None:
        return None
    try:
        if field == "nav":
            return fn(code, limit=limit)
        if field == "daily":
            return fn(code, limit=limit)
        if field == "holdings":
            return fn(code, period=None) if not period else fn(code, period=period)
        return fn(code) or []
    except Exception:
        return None if field == "basic" else []


# ---------------------------------------------------------------------------
# 更新 / 落盘（复用 fetcher update 子命令，保留限流与权限退化）
# ---------------------------------------------------------------------------

def _run_fetcher_update(asset_type, code, name=None):
    """调用对应 fetcher 的 update 子命令，强制落盘缺失数据。

    Returns:
        bool: 更新是否成功
    """
    if asset_type == "stock":
        if not name:
            raise ValueError("个股 update 需要公司名 name")
        args = [sys.executable, os.path.join(_TOOLS_DIR, "fundamental_fetcher.py"), "update", code, name]
    elif asset_type == "fund":
        args = [sys.executable, os.path.join(_TOOLS_DIR, "fund_data_fetcher.py"), "update", code]
    else:
        return False
    try:
        # 关键：text=True 时必须显式指定 encoding（Windows 默认 GBK 会解码失败）；
        # errors="replace" 防止个别不可解码字节让整个取数崩溃。
        # timeout 适中：缓存未命中触发更新时，不应让整条流水线阻塞过久。
        res = subprocess.run(
            args, capture_output=True, text=True, encoding="utf-8",
            errors="replace", cwd=_ROOT, timeout=120,
        )
        return res.returncode == 0
    except subprocess.TimeoutExpired:
        return False
    except Exception:
        return False


def update(asset_type, code, name=None):
    """刷新本地落盘缓存（增量更新缺失期间）。详见 financial-data 规范。"""
    return _run_fetcher_update(asset_type, code, name)


# ---------------------------------------------------------------------------
# 统一取数入口：本地优先 -> 降级取数 -> 落盘
# ---------------------------------------------------------------------------

def get(asset_type, code, name=None, field=None, period=None, update_if_missing=True):
    """统一取数入口。

    Args:
        asset_type: "stock" | "fund"
        code: 标的代码（个股 6 位数字；基金 6 位数字）
        name: 个股名（读股票缓存必须，用于目录 local/{name}_{code}）
        field: 可选，读取子字段：
             stock: financial / meta / announcements
             fund : basic / nav / daily / holdings / shares / manager / holder
        period: 可选（fund holdings / stock financial 的报告期）
        update_if_missing: 缓存不足时是否触发 update 落盘

    Returns:
        dict | list | None: 结构化数据。持久化字段缺失且更新失败时返回 None。
    """
    # 1. 本地读
    if asset_type == "stock":
        if field is None or field == "financial":
            data = _stock_financial(code, name or "", period)
        elif field == "meta":
            data = _stock_meta(code, name or "")
        elif field == "announcements":
            data = _stock_anns(code, name or "")
        else:
            data = None
    elif asset_type == "fund":
        f = field or "basic"
        data = _fund_loader(f, code, period=period)
    else:
        raise ValueError(f"未知资产类型: {asset_type}")

    # 2. 命中且足够 -> 返回
    if _is_filled(data):
        return data

    # 3. 缓存不足 -> 若允许更新则落盘后重读
    if update_if_missing:
        ok = _run_fetcher_update(asset_type, code, name)
        if ok:
            if asset_type == "stock":
                if field in (None, "financial"):
                    data = _stock_financial(code, name or "", period)
                elif field == "meta":
                    data = _stock_meta(code, name or "")
                elif field == "announcements":
                    data = _stock_anns(code, name or "")
            else:
                data = _fund_loader(field or "basic", code, period=period)
            if _is_filled(data):
                return data

    # 4. 仍无数据
    return _empty_return(asset_type, field)


def _is_filled(data):
    if data is None:
        return False
    if isinstance(data, (list, tuple)):
        return len(data) > 0
    if isinstance(data, dict):
        return len(data) > 0
    return data != ""


def _empty_return(asset_type, field):
    # 快照类字段允许返回空不报错；持久化字段返回 None 表示"取数失败"
    if asset_type == "fund" and field in ("nav", "daily", "holdings", "shares", "manager", "holder"):
        return []
    if asset_type == "stock" and field == "announcements":
        return []
    return None


# ---------------------------------------------------------------------------
# 便捷封装
# ---------------------------------------------------------------------------

def load_local(asset_type, code, field=None, name=None, period=None):
    """仅读本地缓存，不触发更新。"""
    return get(asset_type, code, name=name, field=field, period=period, update_if_missing=False)


def search(keyword, market=None):
    """搜索公司/基金代码（复用 tushare_data.py search/fundsearch）。"""

    py = sys.executable
    tool = os.path.join(_TOOLS_DIR, "tushare_data.py")
    args = [py, tool, "search", keyword]
    try:
        res = subprocess.run(args, capture_output=True, text=True, encoding="utf-8",
                             errors="replace", cwd=_ROOT, timeout=120,
                             env={**os.environ, "PYTHONIOENCODING": "utf-8"})
        return res.stdout or res.stderr or ""
    except Exception as e:
        return f"搜索失败: {e}"


def status(asset_type, code, name=None):
    """列出本地已落盘的资产（校验缓存完整性）。"""
    if asset_type == "stock":
        if not name:
            return {"asset_type": "stock", "code": code, "cached": False}
        base = os.path.join(_LOCAL_DIR, f"{name}_{code}")
        return {
            "asset_type": "stock",
            "code": code,
            "name": name,
            "cached": os.path.exists(base),
            "manifest": _latest_stock_period(name, code),
        }
    base = os.path.join(_LOCAL_DIR, f"fund_{code}")
    return {"asset_type": "fund", "code": code, "cached": os.path.exists(base)}


def list_cached(asset_type=None):
    """列出 local/ 下已落盘的资产（目录名）。"""
    if not os.path.isdir(_LOCAL_DIR):
        return []
    out = []
    for entry in sorted(os.listdir(_LOCAL_DIR)):
        if entry.startswith("fund_") and (asset_type in (None, "fund")):
            out.append(("fund", entry[len("fund_"):]))
        elif "_" in entry and entry.count("_") == 1 and (asset_type in (None, "stock")):
            name, code = entry.rsplit("_", 1)
            if code.isdigit() and len(code) == 6:
                out.append(("stock", code, name))
    return out


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="AI Berkshire 统一数据访问层（本地优先->退化链->落盘）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_get = sub.add_parser("get", help="统一取数（本地优先，不足则取数落盘）")
    p_get.add_argument("asset_type", choices=["stock", "fund"])
    p_get.add_argument("code")
    p_get.add_argument("name", nargs="?", default=None)
    p_get.add_argument("--field", default=None, help="stock: financial/meta/announcements; fund: basic/nav/daily/holdings/shares/manager/holder")
    p_get.add_argument("--period", default=None, help="报告期 YYYYMMDD（可选）")
    p_get.add_argument("--no-update", action="store_true", help="只读本地，不触发更新")

    p_load = sub.add_parser("load", help="仅读本地缓存")
    p_load.add_argument("asset_type", choices=["stock", "fund"])
    p_load.add_argument("code")
    p_load.add_argument("name", nargs="?", default=None)
    p_load.add_argument("--field", default=None)
    p_load.add_argument("--period", default=None)

    p_upd = sub.add_parser("update", help="刷新本地落盘缓存")
    p_upd.add_argument("asset_type", choices=["stock", "fund"])
    p_upd.add_argument("code")
    p_upd.add_argument("name", nargs="?", default=None)

    p_search = sub.add_parser("search", help="搜索股票/基金代码")
    p_search.add_argument("keyword")

    p_status = sub.add_parser("status", help="查看某资产缓存状态")
    p_status.add_argument("asset_type", choices=["stock", "fund"])
    p_status.add_argument("code")
    p_status.add_argument("name", nargs="?", default=None)

    p_list = sub.add_parser("list", help="列出已落盘资产")
    p_list.add_argument("--type", dest="asset_type", choices=["stock", "fund"], default=None)

    args = parser.parse_args()

    if args.cmd == "get":
        print(json.dumps(get(args.asset_type, args.code, args.name, field=args.field,
                             period=args.period, update_if_missing=not args.no_update),
                         ensure_ascii=False, indent=2))
    elif args.cmd == "load":
        print(json.dumps(load_local(args.asset_type, args.code, args.field, args.name, args.period),
                         ensure_ascii=False, indent=2))
    elif args.cmd == "update":
        print(json.dumps(update(args.asset_type, args.code, args.name), ensure_ascii=False))
    elif args.cmd == "search":
        print(search(args.keyword))
    elif args.cmd == "status":
        print(json.dumps(status(args.asset_type, args.code, args.name), ensure_ascii=False, indent=2))
    elif args.cmd == "list":
        print(json.dumps(list_cached(args.asset_type), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
