#!/usr/bin/env python3
"""A股/港股/美股数据工具 — Tushare 数据源（ttshare 代理优先，官方 API 兜底）。

为 Claude Code Skills 提供 A股/港股/美股行情、估值、财务、分红、搜索数据。
设计原则：独立模块，不影响现有工具；与 twstock_data.py / ashare_data.py 同风格。

数据源优先级：
    1. ttshare（第三方代理，需授权码，接口覆盖更全）
    2. tushare 官方（需官方 token，部分接口有积分限制）
    代理调用失败或返回空时自动切换到官方重试；官方也无数据则输出退化提示。

依赖安装（uv 管理依赖，勿直接用 pip install）：
    uv add ttshare tushare      # 或直接 uv sync（ttshare 源已在 pyproject.toml 配置）

token 读取（token 只存本机，严禁提交到 git；local/ 已被 .gitignore 永久排除）：
    代理授权码（ttshare_token）：①环境变量 TTSHARE_TOKEN  ②本地文件 local/ttshare_token.txt
    官方 token（tushare_token）：①环境变量 TUSHARE_TOKEN  ②本地文件 local/tushare_token.txt
    两者都没配则报错退出（tushare 必须 token，不匿名访问）。
    命名与包名一致：ttshare_* 是代理授权码，tushare_* 是官方 token。
    TUSHARE_TOKEN 环境变量恰好也是官方 tushare 库的默认读取变量，语义一致，不会冲突。

用法（由 Skills 自动调用）：
    python3 tools/tushare_data.py quote 600519        # A股行情快照 + 市值验算
    python3 tools/tushare_data.py valuation 600519    # PE/PB/市值/52周高低
    python3 tools/tushare_data.py financials 600519   # 近5年年度核心财务
    python3 tools/tushare_data.py dividend 600519     # 分红送配记录
    python3 tools/tushare_data.py search 茅台          # 搜索股票代码（A股+港股+美股）
    python3 tools/tushare_data.py quote 00700.HK      # 港股行情
    python3 tools/tushare_data.py quote AAPL          # 美股行情

市场覆盖与权限退化：
    - A股：行情/估值/财务/分红/搜索全接口
    - 港股：行情(hk_daily)、搜索(hk_basic)；估值/财务视接口权限，无权限时输出
      明确提示与备选来源，不静默给空数据
    - 美股：行情(us_daily)、搜索(us_basic)；估值/财务同上
    - 台股不在覆盖范围（tushare 无台股接口，用 tools/twstock_data.py）

依赖：tushare/ttshare（含 pandas）。其余仅 stdlib。
"""

import argparse
import os
import sys
from datetime import date, timedelta

_LOCAL_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "local",
)

# Windows 控制台中文输出
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

_MARKET_LABEL = {"A": "A股", "HK": "港股", "US": "美股"}

# 无权限/无数据时的备选来源提示（指向 skills/financial-data.md）
_FALLBACK_HINT = {
    "A": "建议改用 skills/financial-data.md A股副源：东方财富 eastmoney.com（财务）+ 巨潮资讯 cninfo.com.cn（一手财报）",
    "HK": "建议改用 skills/financial-data.md 港股来源：aastocks（主）+ macrotrends ADR（副）+ HKEX 披露易（一手）",
    "US": "建议改用 skills/financial-data.md 美股来源：macrotrends（主）+ stockanalysis（副）+ SEC EDGAR（一手）",
}


def _read_token(env_name, filename):
    """读 token：环境变量优先，其次本地文件；都没有返回 None。"""
    t = os.environ.get(env_name, "").strip()
    if t:
        return t
    try:
        with open(os.path.join(_LOCAL_DIR, filename), encoding="utf-8") as f:
            return f.read().strip() or None
    except OSError:
        return None


class _Client:
    """Tushare 客户端：ttshare 代理优先、官方 API 兜底，调用失败自动换源重试。"""

    def __init__(self):
        # (来源标签, ts模块, token, token说明)
        self._sources = []
        self._last_error = None   # 最近一次调用失败原因（退化提示用）
        proxy = self._try_import("ttshare")
        if proxy:
            self._sources.append(
                (proxy, "ttshare代理", _read_token("TTSHARE_TOKEN", "ttshare_token.txt"),
                 "代理授权码：环境变量 TTSHARE_TOKEN 或 local/ttshare_token.txt"))
        official = self._try_import("tushare")
        if official:
            self._sources.append(
                (official, "tushare官方", _read_token("TUSHARE_TOKEN", "tushare_token.txt"),
                 "官方 token：环境变量 TUSHARE_TOKEN 或 local/tushare_token.txt"))
        if not self._sources:
            raise ConnectionError(
                "未安装 ttshare/tushare。请用 uv 安装依赖：uv add ttshare tushare（或 uv sync）")

    @staticmethod
    def _try_import(name):
        try:
            mod = __import__(name)
            return mod
        except ImportError:
            return None

    def call(self, api, **kwargs):
        """调用 tushare 接口：从第一个源开始，失败/空数据自动切下一个源重试。

        返回 (来源标签, DataFrame 或 None)。None 表示所有源均失败。
        """
        self._last_error = None
        for i, (mod, label, tok, _desc) in enumerate(self._sources):
            try:
                if tok:
                    mod.set_token(tok)
                pro = mod.pro_api()
                df = getattr(pro, api)(**kwargs)
                if df is not None and len(df):
                    return label, df
            except Exception as e:
                self._last_error = f"{label}: {type(e).__name__}: {str(e)[:100]}"
        return self._sources[0][1], None

    def token_hint(self):
        """输出 token 配置提示（两个源都失败时用）。"""
        missing = [desc for _mod, _label, tok, desc in self._sources if not tok]
        if missing:
            return "；".join(f"未配置{desc}" for desc in missing)
        return "token 可能无效或已过期（代理授权码有有效期）"


# ---------------------------------------------------------------------------
# 市场识别与辅助
# ---------------------------------------------------------------------------

def _a_suffix(code):
    """A股代码补后缀（与 ashare_data.py 同规则）。"""
    if code.startswith(("6", "9", "5")):
        return ".SH"
    if code.startswith(("0", "3", "2", "1")):
        return ".SZ"
    return ".BJ"


def _resolve_market(code):
    """识别市场并补全代码。返回 (市场键, 完整代码)。无法识别抛 ConnectionError。"""
    c = code.strip().upper()
    if c.endswith((".SH", ".SZ", ".BJ")):
        return "A", c
    if c.endswith(".HK"):
        return "HK", c
    if c.endswith(".US"):
        return "US", c[:-3]
    if c.isdigit():
        if len(c) == 6:
            return "A", c + _a_suffix(c)
        if len(c) == 5:
            return "HK", c + ".HK"
    if not c or not c.replace(".", "").isalnum() or len(c) > 8:
        raise ConnectionError(
            f"无法识别代码 '{code}' 的市场。支持：A股 600519 / 600519.SH、港股 00700.HK、美股 AAPL")
    return "US", c


def _days_ago(n):
    return (date.today() - timedelta(days=n)).strftime("%Y%m%d")


def _fmt_date(v):
    s = str(v or "")
    return f"{s[:4]}-{s[4:6]}-{s[6:8]}" if len(s) >= 8 else (s or "-")


def _fmt_num(v, suffix=""):
    if v is None or v == "" or (isinstance(v, float) and v != v):
        return "-"
    try:
        return f"{float(v):,.2f}{suffix}"
    except (ValueError, TypeError):
        return f"{v}{suffix}"


def _fmt_yi(v, unit="元"):
    """金额格式化为 亿/万。"""
    if v is None or v == "":
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


def _v(row, key):
    """取字典值（列名大小写容错）。"""
    if row is None:
        return None
    keys = row.keys() if hasattr(row, "keys") else []
    for k in keys:
        if str(k).lower() == str(key).lower():
            return row[k]
    return None


def _col(df, key):
    """取 DataFrame 列（列名大小写容错）。"""
    for c in df.columns:
        if str(c).lower() == str(key).lower():
            return df[c]
    return None


_name_cache = {}


def _stock_name(client, market, full):
    """从列表接口取股票名称（内存缓存，避免重复全量拉取）。

    full 为补全后的代码（如 600519.SH / 00700.HK / AAPL），直接与 ts_code 匹配。
    """
    key = (market, full)
    if key in _name_cache:
        return _name_cache[key]
    name = full
    list_api = {"A": "stock_basic", "HK": "hk_basic", "US": "us_basic"}[market]
    _src, df = client.call(list_api)
    if df is not None and len(df):
        name_col, code_col = _col(df, "name"), _col(df, "ts_code")
        if name_col is not None and code_col is not None:
            row = df[code_col.astype(str).str.upper() == full.upper()]
            if len(row):
                name = str(row.iloc[0][name_col.name])
    _name_cache[key] = name
    return name


def _degrade(client, market, api, hint=None):
    """权限退化提示：无权限/无数据时输出明确提示与备选来源，不静默。"""
    print(f"⚠️ {_MARKET_LABEL[market]}接口 {api} 无权限或不可用（数据为空/请求失败）")
    if client._last_error:
        print(f"  失败原因:   {client._last_error}")
    print(f"  {_FALLBACK_HINT[market]}")
    if hint:
        print(f"  {hint}")


def _year_high_low(client, market, full):
    """52 周最高/最低。"""
    api = {"A": "daily", "HK": "hk_daily", "US": "us_daily"}[market]
    _src, d = client.call(api, ts_code=full, start_date=_days_ago(380))
    if d is None or not len(d):
        return None, None
    hi, lo = _col(d, "high"), _col(d, "low")
    if hi is None or lo is None:
        return None, None
    return float(hi.max()), float(lo.min())


def _latest_daily(client, market, full, days=15):
    """最近一个交易日的日线行。返回 (来源, 行dict 或 None)。"""
    api = {"A": "daily", "HK": "hk_daily", "US": "us_daily"}[market]
    src, d = client.call(api, ts_code=full, start_date=_days_ago(days))
    if d is None or not len(d):
        return src, None
    return src, d.iloc[0].to_dict()


# ---------------------------------------------------------------------------
# 命令实现
# ---------------------------------------------------------------------------

def cmd_quote(code):
    market, full = _resolve_market(code)
    label = _MARKET_LABEL[market]
    client = _get_client()
    sep = "=" * 60
    name = _stock_name(client, market, full)

    if market == "A":
        # 优先实时快照，失败回退日线
        src, d = client.call("realtime_quote", ts_code=full)
        if d is not None and len(d):
            r = d.iloc[0].to_dict()
            print(sep)
            print(f"{label}行情: {_v(r, 'NAME') or name} ({full})  数据源: {src}")
            print(sep)
            print(f"  时间:       {_v(r, 'TIME')}")
            print(f"  最新价:     {_fmt_num(_v(r, 'PRICE'))}")
            print(f"  涨跌幅:     {_fmt_num(_v(r, 'PERCENT'), '%')}")
            print(f"  开/高/低:   {_fmt_num(_v(r, 'OPEN'))} / {_fmt_num(_v(r, 'HIGH'))} / {_fmt_num(_v(r, 'LOW'))}")
            print(f"  昨收:       {_fmt_num(_v(r, 'PRE_CLOSE'))}")
            print(f"  成交量:     {_fmt_yi(_v(r, 'VOLUME'))}股")
            print(f"  成交额:     {_fmt_yi(_v(r, 'AMOUNT'))}")
            print(f"  换手率:     {_fmt_num(_v(r, 'TURNOVER'), '%')}")
            price = _v(r, "PRICE")
            if price:
                _print_a_market_cap(client, full, price, src)
            return
        src, r = _latest_daily(client, market, full)
        if r is None:
            _degrade(client, market, "realtime_quote/daily")
            return
        print(sep)
        print(f"{label}行情(日线): {name} ({full})  数据源: {src}")
        print(sep)
        print(f"  日期:       {_fmt_date(_v(r, 'TRADE_DATE'))}")
        print(f"  收盘价:     {_fmt_num(_v(r, 'CLOSE'))}")
        print(f"  涨跌幅:     {_fmt_num(_v(r, 'PCT_CHG'), '%')}")
        print(f"  开/高/低:   {_fmt_num(_v(r, 'OPEN'))} / {_fmt_num(_v(r, 'HIGH'))} / {_fmt_num(_v(r, 'LOW'))}")
        print(f"  成交量:     {_fmt_yi(_v(r, 'VOL'))}手")
        print(f"  成交额:     {_fmt_yi(_v(r, 'AMOUNT') * 1000 if _v(r, 'AMOUNT') is not None else None)}")
        price = _v(r, "CLOSE")
        if price:
            _print_a_market_cap(client, full, price, src)
        return

    # 港股/美股：日线
    src, r = _latest_daily(client, market, full)
    if r is None:
        _degrade(client, market, {"HK": "hk_daily", "US": "us_daily"}[market])
        return
    print(sep)
    print(f"{label}行情: {name} ({full})  数据源: {src}")
    print(sep)
    print(f"  日期:       {_fmt_date(_v(r, 'TRADE_DATE'))}")
    print(f"  收盘价:     {_fmt_num(_v(r, 'CLOSE'))}")
    print(f"  涨跌幅:     {_fmt_num(_v(r, 'PCT_CHG'), '%')}")
    print(f"  开/高/低:   {_fmt_num(_v(r, 'OPEN'))} / {_fmt_num(_v(r, 'HIGH'))} / {_fmt_num(_v(r, 'LOW'))}")
    print(f"  昨收:       {_fmt_num(_v(r, 'PRE_CLOSE'))}")
    print(f"  成交量:     {_fmt_yi(_v(r, 'VOL'))}手")
    print(f"  成交额:     {_fmt_yi(_v(r, 'AMOUNT'))}")


def _print_a_market_cap(client, full, price, src):
    """A股市值验算：daily_basic 总市值 vs 价格×总股本。"""
    try:
        _s, d = client.call(
            "daily_basic", ts_code=full, start_date=_days_ago(30),
            fields="trade_date,total_mv,total_share")
        if d is None or not len(d):
            return
        r = d.iloc[0].to_dict()
        total_mv = _v(r, "TOTAL_MV")       # 万元
        total_share = _v(r, "TOTAL_SHARE")  # 万股
        if not total_mv or float(total_mv) <= 0:
            return
        mv_yi = float(total_mv) / 1e4       # → 亿元
        print(f"  总市值:     {mv_yi:,.0f}亿（daily_basic）")
        if total_share:
            shares_yi = float(total_share) / 1e4  # → 亿股
            calc_cap = float(price) * float(total_share) * 1e4  # 元
            diff = abs(calc_cap - float(total_mv) * 1e4) / (float(total_mv) * 1e4) * 100
            verdict = "✅ 一致" if diff <= 5 else "❌ 偏差过大，请核对"
            print(f"  市值验算:   {price} × {shares_yi:,.0f}亿股 = {calc_cap / 1e8:,.0f}亿，偏差 {diff:.1f}% {verdict}")
    except Exception:
        pass


def cmd_valuation(code):
    market, full = _resolve_market(code)
    label = _MARKET_LABEL[market]
    client = _get_client()
    sep = "=" * 60
    name = _stock_name(client, market, full)

    if market == "A":
        _s, d = client.call(
            "daily_basic", ts_code=full, start_date=_days_ago(40),
            fields="trade_date,close,pe,pb,total_mv,circ_mv,turnover_rate")
        if d is None or not len(d):
            _degrade(client, market, "daily_basic")
            return
        r = d.iloc[0].to_dict()
        print(sep)
        print(f"估值指标: {name} ({full})  数据源: {_s}")
        print(sep)
        print(f"  日期:       {_fmt_date(_v(r, 'TRADE_DATE'))}")
        print(f"  收盘价:     {_fmt_num(_v(r, 'CLOSE'))}")
        print(f"  PE(TTM):    {_fmt_num(_v(r, 'PE'))}")
        print(f"  PB:         {_fmt_num(_v(r, 'PB'))}")
        mv = _v(r, "TOTAL_MV")
        if mv:
            print(f"  总市值:     {float(mv) / 1e4:,.0f}亿")
        cmv = _v(r, "CIRC_MV")
        if cmv:
            print(f"  流通市值:   {float(cmv) / 1e4:,.0f}亿")
        print(f"  换手率:     {_fmt_num(_v(r, 'TURNOVER_RATE'), '%')}")
        hi, lo = _year_high_low(client, market, full)
        if hi is not None:
            print(f"  52周最高:   {hi}")
            print(f"  52周最低:   {lo}")
        return

    # 港股/美股：尝试估值接口（hk_daily_basic / us_daily_basic），无权限则退化
    api = {"HK": "hk_daily_basic", "US": "us_daily_basic"}[market]
    _s, d = client.call(api, ts_code=full, start_date=_days_ago(40))
    if d is None or not len(d):
        _degrade(client, market, api, hint="若代理未开放估值接口，请用备选来源取 PE/PB/市值")
        return
    r = d.iloc[0].to_dict()
    print(sep)
    print(f"估值指标: {name} ({full})  数据源: {_s}")
    print(sep)
    print(f"  日期:       {_fmt_date(_v(r, 'TRADE_DATE'))}")
    print(f"  收盘价:     {_fmt_num(_v(r, 'CLOSE'))}")
    print(f"  PE:         {_fmt_num(_v(r, 'PE'))}")
    print(f"  PB:         {_fmt_num(_v(r, 'PB'))}")
    mv = _v(r, "TOTAL_MV")
    if mv:
        print(f"  总市值:     {_fmt_yi(float(mv) * 1e4)}")
    hi, lo = _year_high_low(client, market, full)
    if hi is not None:
        print(f"  52周最高:   {hi}")
        print(f"  52周最低:   {lo}")


def cmd_financials(code):
    market, full = _resolve_market(code)
    label = _MARKET_LABEL[market]
    client = _get_client()
    sep = "=" * 60
    name = _stock_name(client, market, full)

    if market != "A":
        api = {"HK": "hk_income", "US": "us_income"}[market]
        _s, d = client.call(api, ts_code=full, start_date=f"{date.today().year - 5}0101")
        if d is None or not len(d):
            _degrade(client, market, api, hint="港股/美股财务接口需较高权限，若代理未开放请用备选来源")
            return
        print(sep)
        print(f"财务数据: {name} ({full})  数据源: {_s}")
        print(sep)
        print(f"  {'报告期':<12}{'营业总收入':>14}{'归母净利润':>14}")
        for _, row in d.head(6).iterrows():
            r = row.to_dict()
            end = str(_v(r, "END_DATE") or _v(r, "END"))[:8]
            rev = _v(r, "TOTAL_OPERATE_INCOME") or _v(r, "REVENUE") or _v(r, "TOTAL_REVENUE") or _v(r, "REVENUE_USD")
            ni = _v(r, "N_INCOME_ATTR_P") or _v(r, "NET_INCOME")
            print(f"  {_fmt_date(end):<12}{_fmt_yi(rev):>14}{_fmt_yi(ni):>14}")
        print(f"\n  注：{label}财务字段与 A 股口径可能不同，务必与 financial-data.md 副源交叉验证")
        return

    # A股：近5年年报
    print(sep)
    print(f"核心财务数据: {name} ({full})  数据源: ttshare代理/官方")
    print(sep)
    print("  单位：人民币。数据来自 tushare income（利润表）+ fina_indicator（财务指标）。")
    found = False
    for y in range(date.today().year - 1, date.today().year - 6, -1):
        period = f"{y}1231"
        _s, d = client.call(
            "income", ts_code=full, period=period,
            fields="end_date,total_operate_income,revenue,n_income_attr_p")
        if d is None or not len(d):
            continue
        r = d.iloc[0].to_dict()
        rev = _v(r, "TOTAL_OPERATE_INCOME") or _v(r, "REVENUE")
        ni = _v(r, "N_INCOME_ATTR_P")
        if rev is None and ni is None:
            continue
        _s2, fd = client.call(
            "fina_indicator", ts_code=full, period=period,
            fields="end_date,grossprofit_margin,netprofit_margin,roe,eps")
        fr = fd.iloc[0].to_dict() if fd is not None and len(fd) else {}
        found = True
        print(f"\n  --- {y}年 ---")
        print(f"  营业总收入: {_fmt_yi(rev)}")
        print(f"  归母净利润: {_fmt_yi(ni)}")
        gpm, npm = _v(fr, "GROSSPROFIT_MARGIN"), _v(fr, "NETPROFIT_MARGIN")
        if gpm is not None:
            print(f"  毛利率:     {_fmt_num(gpm, '%')}")
        if npm is not None:
            print(f"  净利率:     {_fmt_num(npm, '%')}")
        if _v(fr, "ROE") is not None:
            print(f"  ROE:        {_fmt_num(_v(fr, 'ROE'), '%')}")
        if _v(fr, "EPS") is not None:
            print(f"  EPS:        {_fmt_num(_v(fr, 'EPS'))}")
    if not found:
        _degrade(client, market, "income/fina_indicator")


def cmd_dividend(code):
    market, full = _resolve_market(code)
    client = _get_client()
    sep = "=" * 60

    if market != "A":
        print("⚠️ 分红数据仅 A 股有标准接口（tushare dividend）")
        print(f"  {_FALLBACK_HINT[market]}")
        return

    _s, d = client.call("dividend", ts_code=full)
    if d is None or not len(d):
        _degrade(client, market, "dividend")
        return
    print(sep)
    print(f"分红送配: {full}  数据源: {_s}")
    print(sep)
    print(f"\n  {'报告期':<12}{'现金股利(元/股)':>14}{'送转股(股/10股)':>14}  {'除权除息日':<12}{'方案进度':<8}")
    # 同一报告期有多条记录（预案→股东大会→实施），只展示已实施的发放
    rows = []
    for _, row in d.iterrows():
        r = row.to_dict()
        if str(_v(r, "DIV_PROC") or "") != "实施":
            continue
        rows.append(r)
    if not rows:
        print("  （该股票近期无已实施的分红记录）")
        return
    for r in rows[:12]:
        end = str(_v(r, "END_DATE") or "")[:8]
        cash = _v(r, "CASH_DIV")
        stk = _v(r, "STK_DIV")
        ex = str(_v(r, "EX_DATE") or "")[:8]
        print(f"  {_fmt_date(end):<12}{_fmt_num(cash):>14}{_fmt_num(stk):>14}  {_fmt_date(ex):<12}实施")


def cmd_search(keyword):
    client = _get_client()
    sep = "=" * 60
    print(sep)
    print(f"搜索结果: '{keyword}'（A股+港股+美股）  数据源: ttshare代理/官方")
    print(sep)
    found = 0
    for market in ("A", "HK", "US"):
        api = {"A": "stock_basic", "HK": "hk_basic", "US": "us_basic"}[market]
        _s, d = client.call(api)
        if d is None or not len(d):
            continue
        name_col, code_col = _col(d, "name"), _col(d, "ts_code")
        if name_col is None or code_col is None:
            continue
        mask = (name_col.astype(str).str.contains(keyword, case=False) |
                code_col.astype(str).str.contains(keyword, case=False))
        enname = _col(d, "enname")
        if enname is not None:
            mask = mask | enname.astype(str).str.contains(keyword, case=False)
        for _, row in d[mask].head(15).iterrows():
            r = row.to_dict()
            nm = _v(r, 'NAME') or _v(r, 'name')
            if not nm or str(nm) == 'nan':
                nm = _v(r, 'ENNAME') or _v(r, 'enname')
            print(f"  [{_MARKET_LABEL[market]}] {_v(r, 'TS_CODE') or _v(r, 'ts_code')}  {nm}")
            found += 1
    if not found:
        print(f"  ❌ 未找到匹配 '{keyword}' 的股票")


_client_singleton = None


def _get_client():
    global _client_singleton
    if _client_singleton is None:
        _client_singleton = _Client()
    return _client_singleton


# ---------------------------------------------------------------------------
# CLI 入口
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="A股/港股/美股数据工具 — Tushare 数据源（ttshare 代理优先，官方 API 兜底）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command")

    for cmd, help_text in [
        ("quote", "行情快照（A股实时/港股/美股日线）+ A股市值验算"),
        ("valuation", "估值指标（PE/PB/市值/52周高低）"),
        ("financials", "近5年年度核心财务（A股全量，港股/美股视权限）"),
        ("dividend", "分红送配记录（仅A股）"),
    ]:
        p = sub.add_parser(cmd, help=help_text)
        p.add_argument("code", help="股票代码，如 600519 / 00700.HK / AAPL")

    p_search = sub.add_parser("search", help="搜索股票代码（A股+港股+美股）")
    p_search.add_argument("keyword", help="公司名或代码")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    try:
        if args.command == "search":
            cmd_search(args.keyword)
        else:
            {
                "quote": cmd_quote,
                "valuation": cmd_valuation,
                "financials": cmd_financials,
                "dividend": cmd_dividend,
            }[args.command](args.code)
    except BrokenPipeError:
        # 输出被管道截断（如 | head），静默退出。
        # 注意 BrokenPipeError 是 ConnectionError 的子类，必须放在前面
        sys.stderr.close()
        sys.exit(0)
    except ConnectionError as e:
        print(f"❌ {e}")
        sys.exit(2)


if __name__ == "__main__":
    main()
