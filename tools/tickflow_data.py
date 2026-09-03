#!/usr/bin/env python3
"""ETF/指数行情备源 — TickFlow（免费层提供日K与标的信息，完整服务提供实时行情）。

为 Claude Code 与 Codex 工作流提供场内行情补位：tushare fund_daily/index_daily 无权限
或需盘中实时行情时使用。与 tools/tushare_data.py 完全独立，互不影响。

能力边界（TickFlow 是行情服务，以下数据**没有**，勿当成基金产品数据源）：
    - 有：ETF/指数/个股 实时行情（完整服务）、日K含复权（免费层）、标的信息
    - 无：场外基金净值/持仓/份额/经理/持有人、指数估值分位、指数成分权重
      ——这些仍用 tools/tushare_data.py fund_* 命令或天天基金副源

token 读取（token 只存本机，严禁提交到 git；local/ 已被 .gitignore 永久排除）：
    完整服务 API Key（tickflow.org 注册）：环境变量 TICKFLOW_API_KEY 或
    local/tickflow_key.txt；免费层无需 token（仅日K/标的信息）。

用法（由 Skills 自动调用）：
    uv run python tools/tickflow_data.py daily 510300.SH     # 日K + 区间收益（免费层可用）
    uv run python tools/tickflow_data.py daily 000300.SH     # 指数日K（免费层可用）
    uv run python tools/tickflow_data.py quote 510300.SH     # 实时行情（需注册完整服务）

依赖：tickflow（uv 管理，uv add tickflow）。其余仅 stdlib + pandas。
"""

import argparse
import os
import sys
from datetime import date, datetime, timedelta

_LOCAL_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "local",
)

# Windows 控制台中文输出（tickflow SDK 内部打印 emoji，GBK 会崩）
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")


def _read_key():
    """读完整服务 API Key：环境变量优先，其次 local/tickflow_key.txt。无则 None。"""
    t = os.environ.get("TICKFLOW_API_KEY", "").strip()
    if t:
        return t
    try:
        with open(os.path.join(_LOCAL_DIR, "tickflow_key.txt"), encoding="utf-8") as f:
            return f.read().strip() or None
    except OSError:
        return None


def _get_tf():
    """返回 (TickFlow实例, 来源标签)。失败返回 (None, 错误信息)。"""
    key = _read_key()
    try:
        from tickflow import TickFlow
        if key:
            return TickFlow(api_key=key), "tickflow完整服务"
        return TickFlow.free(), "tickflow免费层"
    except Exception as e:
        return None, f"tickflow 不可用: {type(e).__name__}: {str(e)[:100]}"


def _fmt_num(v, suffix=""):
    if v is None:
        return "-"
    try:
        return f"{float(v):,.2f}{suffix}"
    except (ValueError, TypeError):
        return f"{v}{suffix}"


def _fmt_yi(v, unit="元"):
    if v is None:
        return "-"
    try:
        x = float(v)
    except (ValueError, TypeError):
        return str(v)
    if abs(x) >= 1e8:
        return f"{x / 1e8:,.2f}亿"
    if abs(x) >= 1e4:
        return f"{x / 1e4:,.2f}万"
    return f"{x:,.2f}"


def _parse_date(v):
    """'2026-08-04' 或 '20260804' → datetime。"""
    s = str(v).replace("-", "")[:8]
    try:
        return datetime.strptime(s, "%Y%m%d")
    except ValueError:
        return None


def _returns_by_windows(dates, closes, windows_days):
    """多窗口累计收益 %。dates/closes 升序；windows_days 为 [(标签, 回溯天数)]，None=全部。"""
    res, n, last = [], len(closes), closes[-1]
    last_d = dates[-1]
    for label, days in windows_days:
        base = 0
        if days is not None:
            target = last_d - timedelta(days=days)
            for i in range(n - 1, -1, -1):
                if dates[i] <= target:
                    base = i
                    break
        if base < n - 1 and closes[base] > 0:
            res.append((label, (last / closes[base] - 1) * 100))
    return res


def _max_drawdown(closes):
    """最大回撤 %（正数表示跌幅）。"""
    peak, mdd = None, 0.0
    for v in closes:
        if peak is None or v > peak:
            peak = v
        if peak and peak > 0:
            dd = (peak - v) / peak * 100
            if dd > mdd:
                mdd = dd
    return mdd


def cmd_daily(code):
    """日K + 区间收益 + 名称（免费层可用）。"""
    tf, label = _get_tf()
    if tf is None:
        print(f"⚠️ {label}")
        print("  备选：tools/tushare_data.py indexdaily / funddaily（ttshare 代理）")
        return
    try:
        d = tf.klines.get(symbol=code, period="1d", count=800, as_dataframe=True)
    except Exception as e:
        print(f"⚠️ 日K获取失败: {type(e).__name__}: {str(e)[:120]}")
        print("  备选：tools/tushare_data.py indexdaily / funddaily（ttshare 代理）")
        return
    if d is None or not len(d):
        print(f"⚠️ 未获取到 {code} 的日K数据（免费层覆盖不全时用 tushare 命令）")
        return
    d = d.sort_values("trade_date").reset_index(drop=True)
    name = str(d.iloc[0]["name"]) if "name" in d.columns else code
    r = d.iloc[-1]
    dates = [_parse_date(v) for v in d["trade_date"]]
    closes = [float(v) for v in d["close"]]
    dates = [x for x in dates if x]
    sep = "=" * 60
    print(sep)
    print(f"行情(日K): {name} ({code})  数据源: {label}")
    print(sep)
    print(f"  最新日期:   {str(r['trade_date'])[:10]}")
    print(f"  最新收盘:   {_fmt_num(r['close'])}")
    print(f"  开/高/低:   {_fmt_num(r['open'])} / {_fmt_num(r['high'])} / {_fmt_num(r['low'])}")
    print(f"  成交量:     {_fmt_yi(r['volume'])}手")
    print(f"  成交额:     {_fmt_yi(r['amount'])}")
    windows = [("近1年", 365), ("近3年", 365 * 3), ("近5年", 365 * 5)]
    print("\n  区间收益:")
    for lb, pct in _returns_by_windows(dates, closes, windows):
        print(f"    {lb}: {pct:+.2f}%")
    print(f"  区间最大回撤: -{_max_drawdown(closes):.2f}%")
    print("  注：免费层日K为历史数据，盘中不更新；实时行情用 quote 命令（需注册）")


def cmd_quote(code):
    """实时行情快照（需注册完整服务，tickflow.org 免费套餐）。"""
    tf, label = _get_tf()
    if tf is None:
        print(f"⚠️ {label}")
        print("  备选：tools/tushare_data.py funddaily / indexdaily（ttshare 代理）")
        return
    if not _read_key():
        print("⚠️ 实时行情需完整服务 API Key（免费层仅日K）")
        print("  注册：https://tickflow.org → 获取 API Key → 写入 local/tickflow_key.txt 或")
        print("  环境变量 TICKFLOW_API_KEY")
        print("  备选：tools/tushare_data.py funddaily / indexdaily（ttshare 代理，日线口径）")
        return
    try:
        q = tf.quotes.get(symbols=[code], as_dataframe=True)
    except Exception as e:
        print(f"⚠️ 实时行情获取失败: {type(e).__name__}: {str(e)[:120]}")
        print("  备选：tools/tushare_data.py funddaily / indexdaily（ttshare 代理）")
        return
    if q is None or not len(q):
        print(f"⚠️ 未获取到 {code} 的实时行情")
        return
    r = q.iloc[0]
    name = str(r.get("name", code))
    sep = "=" * 60
    print(sep)
    print(f"实时行情: {name} ({code})  数据源: {label}")
    print(sep)
    for k, zh in [("last", "最新价"), ("open", "开盘价"), ("high", "最高价"),
                  ("low", "最低价"), ("pre_close", "昨收"), ("volume", "成交量"),
                  ("amount", "成交额")]:
        v = r.get(k) if hasattr(r, "get") else None
        if v is not None:
            if k == "volume":
                print(f"  {zh}:     {_fmt_yi(v)}手")
            elif k == "amount":
                print(f"  {zh}:     {_fmt_yi(v)}")
            else:
                print(f"  {zh}:     {_fmt_num(v)}")
    print("  注：实时行情为盘中快照；与 T-1 净值比可算盘中折溢价（净值见 tushare fundnav）")


def main():
    parser = argparse.ArgumentParser(
        description="ETF/指数行情备源 — TickFlow（免费层日K，完整服务实时行情）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command")
    for cmd, help_text in [
        ("daily", "日K + 区间收益（免费层可用）"),
        ("quote", "实时行情快照（需注册完整服务）"),
    ]:
        p = sub.add_parser(cmd, help=help_text)
        p.add_argument("code", help="代码，如 510300.SH（ETF）/ 000300.SH（指数）")
    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)
    try:
        if args.command == "quote":
            cmd_quote(args.code)
        else:
            cmd_daily(args.code)
    except BrokenPipeError:
        sys.stderr.close()
        sys.exit(0)


if __name__ == "__main__":
    main()
