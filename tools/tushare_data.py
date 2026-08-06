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
    # ---- 基金命令（fund_* 接口，ts_code 用 .OF 后缀；与股票命令完全隔离）----
    python3 tools/tushare_data.py fundinfo 510300     # 基金基本盘（类型/费率/经理/跟踪指数）
    python3 tools/tushare_data.py fundnav 510300      # 净值与业绩（复权净值/区间收益/回撤）
    python3 tools/tushare_data.py funddaily 510300    # 场内行情/流动性/折溢价（场内份额）
    python3 tools/tushare_data.py fundshares 510300   # 份额与规模变动（近8期）
    python3 tools/tushare_data.py fundholdings 161725 # 季报前十大持仓
    python3 tools/tushare_data.py fundmanager 161725  # 历任基金经理档案
    python3 tools/tushare_data.py fundholder 161725   # 持有人结构
    python3 tools/tushare_data.py fundsearch 沪深300   # 搜索基金与指数代码
    python3 tools/tushare_data.py fundtracking 510300 --index 000300.SH  # 跟踪误差
    # ---- 指数命令（index_* 接口）----
    python3 tools/tushare_data.py indexinfo 000300.SH # 指数基本盘（发布机构/基日/加权方式）
    python3 tools/tushare_data.py indexdaily 000300.SH   # 指数行情与区间收益
    python3 tools/tushare_data.py indexvaluation 000300.SH  # 指数估值与历史分位
    python3 tools/tushare_data.py indexweight 000300.SH    # 成分权重与集中度

市场覆盖与权限退化：
    - A股：行情/估值/财务/分红/搜索全接口
    - 港股：行情(hk_daily)、搜索(hk_basic)；估值/财务视接口权限，无权限时输出
      明确提示与备选来源，不静默给空数据
    - 美股：行情(us_daily)、搜索(us_basic)；估值/财务同上
    - 台股不在覆盖范围（tushare 无台股接口，用 tools/twstock_data.py）
    - 基金：fund_basic/nav/share/daily 需约2000积分，fund_portfolio/manager/holder
      需约5000积分；无权限时输出天天基金等副源提示（skills/financial-data.md 基金章节）
    - 指数：index_daily 免费，index_basic/dailybasic/weight 视权限
    - 场内行情实时补位可用 tools/tickflow_data.py（TickFlow 备源）

依赖：tushare/ttshare（含 pandas）。其余仅 stdlib。
"""

import argparse
import os
import sys
from datetime import date, datetime, timedelta

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

# 基金/指数接口无权限时的备选来源提示（指向 skills/financial-data.md 基金章节）
_FUND_FALLBACK = {
    "fund_basic": "天天基金基金档案页 fund.eastmoney.com（搜基金代码）",
    "fund_nav": "天天基金历史净值页（搜基金代码→历史净值）",
    "fund_daily": "东方财富数据中心 data.eastmoney.com（ETF行情）；盘中实时可用 tools/tickflow_data.py",
    "fund_share": "天天基金规模变动页（搜基金代码→规模变动）",
    "fund_portfolio": "天天基金持仓明细页（搜基金代码→持仓明细）",
    "fund_manager": "天天基金基金经理页（搜基金代码→基金经理）",
    "fund_holder": "天天基金持有人结构页（搜基金代码→持有人结构）",
    "index_basic": "中证指数官网 csi.com.cn / 国证指数 cnindex.com.cn",
    "index_daily": "中证指数官网行情页 csi.com.cn；盘中实时可用 tools/tickflow_data.py",
    "index_dailybasic": "乐咕乐股指数估值页 legulegu.com",
    "index_weight": "中证指数官网成分权重列表 csi.com.cn，或跟踪该指数的 ETF 用 fundholdings 兜底",
}


def _fund_code_hint(code):
    """代码形似基金/指数（6位5x/1x开头，或 H 开头指数）时返回引导提示。"""
    base = code.strip().upper().split(".")[0]
    if base.startswith("H"):
        return "提示：该代码可能为指数（H 开头为 CSI 系列），请用 indexinfo/indexdaily 等指数命令"
    if base.isdigit() and len(base) == 6 and base.startswith(("5", "1")):
        return "提示：该代码可能为场内基金（5x=.SH / 1x=.SZ），请用 fundinfo/funddaily 等基金命令"
    return None


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


def _degrade(client, market, api, hint=None, code=None):
    """权限退化提示：无权限/无数据时输出明确提示与备选来源，不静默。

    code 非空时自动检查是否形似基金/指数代码，附加命令引导（防误用）。
    """
    print(f"⚠️ {_MARKET_LABEL[market]}接口 {api} 无权限或不可用（数据为空/请求失败）")
    if client._last_error:
        print(f"  失败原因:   {client._last_error}")
    print(f"  {_FALLBACK_HINT[market]}")
    if hint:
        print(f"  {hint}")
    if code:
        fh = _fund_code_hint(code)
        if fh:
            print(f"  {fh}")


def _degrade_fund(client, api, hint=None):
    """基金/指数接口退化提示：指向 financial-data.md 基金章节副源，不静默。"""
    print(f"⚠️ 基金/指数接口 {api} 无权限或不可用（数据为空/请求失败）")
    if client._last_error:
        print(f"  失败原因:   {client._last_error}")
    print(f"  备选来源:   {_FUND_FALLBACK.get(api, '天天基金 fund.eastmoney.com')}")
    print("  数据源分层详见 skills/financial-data.md 基金与指数章节")
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
            _degrade(client, market, "realtime_quote/daily", code=code)
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
        _degrade(client, market, {"HK": "hk_daily", "US": "us_daily"}[market], code=code)
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
            _degrade(client, market, "daily_basic", code=code)
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
        _degrade(client, market, api, hint="若代理未开放估值接口，请用备选来源取 PE/PB/市值", code=code)
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
            _degrade(client, market, api, hint="港股/美股财务接口需较高权限，若代理未开放请用备选来源", code=code)
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
        _degrade(client, market, "income/fina_indicator", code=code)


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
        _degrade(client, market, "dividend", code=code)
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


# ---------------------------------------------------------------------------
# 基金/指数辅助（与股票 `_resolve_market` 完全隔离，不相互调用）
# ---------------------------------------------------------------------------

def _resolve_fund_code(code):
    """解析基金代码 → (基础6位, fund_ts="xxx.OF", exch_ts="xxx.SH/.SZ"或None)。

    规则：显式后缀优先；5x→.SH（沪市场内）、1x→.SZ（深市场内）、
    0x/2x/3x→场外（无场内行情，exch_ts=None）。
    """
    c = code.strip().upper()
    base = c.split(".")[0]
    suffix = c.split(".")[1] if "." in c else ""
    if suffix in ("SH", "SZ"):
        exch_ts = f"{base}.{suffix}"
    elif base.startswith("5"):
        exch_ts = f"{base}.SH"
    elif base.startswith("1"):
        exch_ts = f"{base}.SZ"
    else:
        exch_ts = None  # 场外：无场内行情
    return base, f"{base}.OF", exch_ts


def _resolve_index_code(code):
    """解析指数代码 → ts_code。规则：显式后缀优先（SH/SZ/CSI/CNI）；H 开头→.CSI；000xx/5x→.SH；其余→.SZ。"""
    c = code.strip().upper()
    base = c.split(".")[0]
    suffix = c.split(".")[1] if "." in c else ""
    if suffix in ("SH", "SZ", "CSI", "CNI"):
        return f"{base}.{suffix}"
    if base.startswith("H"):
        return f"{base}.CSI"
    if base.startswith(("000", "5")):
        return f"{base}.SH"
    return f"{base}.SZ"


_fund_name_cache = {}
_index_name_cache = {}


def _fund_name(client, of_ts):
    """基金名称反查（fund_basic 全量内存缓存，与 _stock_name 同模式）。"""
    if of_ts in _fund_name_cache:
        return _fund_name_cache[of_ts]
    name = of_ts
    _src, df = client.call("fund_basic", fields="ts_code,name")
    if df is not None and len(df):
        nm, cd = _col(df, "name"), _col(df, "ts_code")
        if nm is not None and cd is not None:
            row = df[cd.astype(str).str.upper() == of_ts.upper()]
            if len(row):
                name = str(row.iloc[0][nm.name])
    _fund_name_cache[of_ts] = name
    return name


def _index_name(client, ts_code):
    """指数名称反查（index_basic 全量内存缓存）。"""
    if ts_code in _index_name_cache:
        return _index_name_cache[ts_code]
    name = ts_code
    _src, df = client.call("index_basic")
    if df is not None and len(df):
        nm, cd = _col(df, "name"), _col(df, "ts_code")
        if nm is not None and cd is not None:
            row = df[cd.astype(str).str.upper() == ts_code.upper()]
            if len(row):
                name = str(row.iloc[0][nm.name])
    _index_name_cache[ts_code] = name
    return name


def _symbol_name(client, symbol):
    """fund_portfolio/index_weight 的股票代码 → 名称（复用 _stock_name 的 A股缓存）。"""
    return _stock_name(client, "A", symbol)


def _sort_by(df, colname, ascending=True):
    """按列排序（列名大小写容错，ttshare 返回小写列名）。列不存在返回原 df。"""
    c = _col(df, colname)
    if c is None:
        return df
    return df.sort_values(c.name, ascending=ascending).reset_index(drop=True)


def _mask_eq(df, colname, value, startswith=False):
    """按列过滤（列名大小写容错）。startswith=True 时用字符串前缀匹配。"""
    c = _col(df, colname)
    if c is None:
        return df
    s = c.astype(str)
    return df[s.str.startswith(value)] if startswith else df[s == value]


def _dates_from(df, col):
    """tushare 日期列（YYYYMMDD 字符串）→ datetime 列表（升序，列名大小写容错）。"""
    c = _col(df, col)
    if c is None:
        return []
    return [datetime.strptime(str(v)[:8], "%Y%m%d") for v in c]


def _returns_by_windows(dates, vals, windows_days):
    """多窗口累计收益 %。dates/vals 升序；windows_days 为 [(标签, 回溯天数)]，None=全部。"""
    if not vals or len(vals) < 2:
        return []
    res, n, last_v = [], len(vals), float(vals[-1])
    last_d = dates[-1]
    for label, days in windows_days:
        base = 0
        if days is not None:
            target = last_d - timedelta(days=days)
            for i in range(n - 1, -1, -1):
                if dates[i] <= target:
                    base = i
                    break
        if base < n - 1 and float(vals[base]) > 0:
            res.append((label, (last_v / float(vals[base]) - 1) * 100))
    return res


def _max_drawdown(vals):
    """最大回撤 %（正数表示跌幅）。"""
    peak, mdd = None, 0.0
    for v in vals:
        fv = float(v)
        if peak is None or fv > peak:
            peak = fv
        if peak and peak > 0:
            dd = (peak - fv) / peak * 100
            if dd > mdd:
                mdd = dd
    return mdd


def _annualized(pct, days):
    """收益率% → 年化%（days 为自然日）。"""
    if days <= 0:
        return None
    return ((1 + pct / 100) ** (365.0 / days) - 1) * 100


def _check_fund_size(a_yi):
    """规模健康提示（亿）。"""
    if a_yi is None:
        return ""
    if a_yi < 2:
        return " ⚠️ 低于2亿，注意清盘风险"
    if a_yi > 100:
        return " ⚠️ 超100亿，主动基金注意策略容量"
    return " ✅ 规模正常"


# ---------------------------------------------------------------------------
# 基金命令（fund_* 接口）
# ---------------------------------------------------------------------------

def cmd_fundinfo(code):
    """基金基本盘：类型/成立日/经理/费率/业绩基准/跟踪指数。"""
    _, of_ts, _ = _resolve_fund_code(code)
    client = _get_client()
    sep = "=" * 60
    _s, d = client.call("fund_basic", ts_code=of_ts)
    if d is None or not len(d):
        _degrade_fund(client, "fund_basic")
        return
    r = d.iloc[0].to_dict()
    name = _v(r, "NAME") or of_ts
    m_fee, c_fee, s_fee = _v(r, "M_FEE"), _v(r, "C_FEE"), _v(r, "S_FEE")
    total = sum(x for x in (m_fee, c_fee, s_fee) if x not in (None, ""))
    print(sep)
    print(f"基金基本盘: {name} ({of_ts})  数据源: {_s}")
    print(sep)
    print(f"  基金类型:   {_v(r, 'INVEST_TYPE') or _v(r, 'FUND_TYPE')}")
    print(f"  成立日期:   {_fmt_date(_v(r, 'FOUND_DATE'))}")
    print(f"  现任经理:   {_v(r, 'MANAGER')}")
    print(f"  托管人:     {_v(r, 'TRUSTEE')}")
    print(f"  管理费率:   {_fmt_num(m_fee, '%')}/年")
    print(f"  托管费率:   {_fmt_num(c_fee, '%')}/年")
    print(f"  销售服务费: {_fmt_num(s_fee, '%')}/年")
    if total:
        print(f"  综合费率:   {total:.2f}%/年 → 每万元年化成本 {total * 100:.0f}元（10年累计 {total * 1000:.0f}元）")
    bench = _v(r, "BENCH")
    if bench:
        print(f"  业绩基准:   {bench}")
    ti = _v(r, "TRACK_INDEX")
    if ti:
        print(f"  跟踪指数:   {ti}")
    print(f"\n  注：费率以基金合同为准（申赎费不在此列，见副源）；综合费率=管理费+托管费+销售服务费")


def cmd_fundnav(code, start):
    """净值与业绩：最新净值 + 区间收益（复权净值口径）+ 最大回撤。--start 限任职期。"""
    _, of_ts, _ = _resolve_fund_code(code)
    client = _get_client()
    sep = "=" * 60
    kwargs = {"ts_code": of_ts}
    if start:
        kwargs["start_date"] = start
    _s, d = client.call("fund_nav", **kwargs)
    if d is None or not len(d):
        _degrade_fund(client, "fund_nav")
        return
    d = _sort_by(d, "NAV_DATE")
    name = _fund_name(client, of_ts)
    r = d.iloc[-1].to_dict()
    print(sep)
    print(f"基金净值与业绩: {name} ({of_ts})  数据源: {_s}")
    print(sep)
    print(f"  最新净值日期: {_fmt_date(_v(r, 'NAV_DATE'))}")
    print(f"  单位净值:     {_fmt_num(_v(r, 'UNIT_NAV'))}")
    print(f"  累计净值:     {_fmt_num(_v(r, 'ACCUM_NAV'))}")
    print(f"  复权净值:     {_fmt_num(_v(r, 'ADJ_NAV'))}")
    adj_col = _col(d, "adj_nav")
    vcol = adj_col if adj_col is not None else _col(d, "unit_nav")
    if vcol is None:
        _degrade_fund(client, "fund_nav")
        return
    if adj_col is None:
        print("  ⚠️ 无复权净值列（接口权限不足），区间收益按单位净值计算，未计分红影响")
    dates = _dates_from(d, "NAV_DATE")
    vals = [float(v) for v in vcol]
    if len(vals) >= 2:
        windows = [("近1月", 30), ("近3月", 90), ("近6月", 180), ("近1年", 365), ("近3年", 365 * 3)]
        windows += [(("任职以来" if start else "成立以来"), None)]
        print("\n  区间收益（复权净值口径）:")
        for label, pct in _returns_by_windows(dates, vals, windows):
            print(f"    {label}: {pct:+.2f}%")
        print(f"  最大回撤:   -{_max_drawdown(vals):.2f}%")
        days = (dates[-1] - dates[0]).days
        ann = _annualized((vals[-1] / vals[0] - 1) * 100, days)
        if ann is not None:
            print(f"  区间年化:   {ann:+.2f}%")
    print("  注：业绩一律用复权净值口径（含分红再投）；与指数/基准对比建议同口径")


def cmd_funddaily(code):
    """场内行情 + 近20日日均成交额 + 折溢价率（T-1净值口径）。场外代码直接提示。"""
    _, of_ts, exch_ts = _resolve_fund_code(code)
    if exch_ts is None:
        print(f"⚠️ {of_ts} 为场外基金代码（无场内行情）")
        print("  场内价格/流动性请改用天天基金申赎数据；场外净值与业绩见 fundnav 命令")
        return
    client = _get_client()
    sep = "=" * 60
    _s, d = client.call("fund_daily", ts_code=exch_ts, start_date=_days_ago(40))
    if d is None or not len(d):
        _degrade_fund(client, "fund_daily")
        return
    d = _sort_by(d, "TRADE_DATE")
    r = d.iloc[-1].to_dict()
    name = _fund_name(client, of_ts)
    print(sep)
    print(f"场内行情: {name} ({exch_ts})  数据源: {_s}")
    print(sep)
    print(f"  日期:       {_fmt_date(_v(r, 'TRADE_DATE'))}")
    print(f"  最新价:     {_fmt_num(_v(r, 'CLOSE'))}")
    print(f"  涨跌幅:     {_fmt_num(_v(r, 'PCT_CHG'), '%')}")
    print(f"  开/高/低:   {_fmt_num(_v(r, 'OPEN'))} / {_fmt_num(_v(r, 'HIGH'))} / {_fmt_num(_v(r, 'LOW'))}")
    print(f"  成交量:     {_fmt_yi(_v(r, 'VOL'))}手")
    amount = _col(d, "amount")
    if amount is not None:
        amt_v = _v(r, "AMOUNT")
        if amt_v is not None:
            print(f"  成交额:     {_fmt_yi(float(amt_v) * 1000)}")
        if len(amount):
            avg = float(amount.tail(20).mean()) * 1000
            flag = "✅ 流动性充足" if avg >= 1e7 else "⚠️ 流动性不足(<1000万/日)"
            print(f"  近20日日均成交额: {avg / 1e4:,.0f}万元  {flag}")
    # 折溢价：场内价 vs 最新单位净值（fund_nav T-1 披露）
    _sn, dn = client.call("fund_nav", ts_code=of_ts, start_date=_days_ago(15))
    nav, nav_date = None, None
    if dn is not None and len(dn):
        dn = _sort_by(dn, "NAV_DATE")
        nr = dn.iloc[-1].to_dict()
        nav, nav_date = _v(nr, "UNIT_NAV"), _v(nr, "NAV_DATE")
    price = _v(r, "CLOSE")
    if nav and price:
        prem = (float(price) / float(nav) - 1) * 100
        flag = "✅ 正常" if abs(prem) <= 1 else "⚠️ 偏离较大，注意申赎套利/流动性风险"
        print(f"  折溢价率:   {prem:+.2f}%  {flag}")
        print(f"  （净值{_fmt_date(nav_date)}披露为T-1口径，折溢价有滞后；盘中实时用 tools/tickflow_data.py）")
    else:
        print("  （未取到最新单位净值，无法计算折溢价；见 fundnav 命令）")


def cmd_fundshares(code):
    """份额与规模变动：近8期季度 + 最新规模健康提示。"""
    _, of_ts, _ = _resolve_fund_code(code)
    client = _get_client()
    sep = "=" * 60
    _s, d = client.call("fund_share", ts_code=of_ts)
    if d is None or not len(d):
        _degrade_fund(client, "fund_share")
        return
    d = _sort_by(d, "TRADE_DATE")
    name = _fund_name(client, of_ts)
    print(sep)
    print(f"份额与规模: {name} ({of_ts})  数据源: {_s}")
    print(sep)
    print(f"\n  {'报告期':<12}{'份额(亿份)':>12}{'资产净值(亿)':>14}{'份额环比':>10}")
    prev, latest_a = None, None
    for _, row in d.tail(8).iterrows():
        r = row.to_dict()
        share = _v(r, "FD_SHARE") or _v(r, "TOTAL_SHARE")
        asset = _v(r, "TOTAL_ASSET")
        s_yi = float(share) / 1e4 if share not in (None, "") else None
        a_yi = float(asset) / 1e4 if asset not in (None, "") else None
        if a_yi is not None:
            latest_a = a_yi
        chg = ""
        if prev and s_yi is not None:
            chg = f"{(s_yi / prev - 1) * 100:+.1f}%"
        if s_yi is not None:
            prev = s_yi
        print(f"  {_fmt_date(_v(r, 'TRADE_DATE')):<12}{_fmt_num(s_yi):>12}{_fmt_num(a_yi):>14}{chg:>10}")
    if latest_a is not None:
        print(f"\n  最新资产净值: {latest_a:,.2f}亿元{_check_fund_size(latest_a)}")
    print("  注：份额持续大幅净流出 = 资金撤离信号，与清盘风险联动")


def cmd_fundholdings(code, period):
    """季报前十大持仓（fund_portfolio）。--period 指定报告期 YYYYMMDD。"""
    _, of_ts, _ = _resolve_fund_code(code)
    client = _get_client()
    sep = "=" * 60
    _s, d = client.call("fund_portfolio", ts_code=of_ts)
    if d is None or not len(d):
        _degrade_fund(client, "fund_portfolio")
        return
    if period:
        d = _mask_eq(d, "END_DATE", period, startswith=True)
    d = _sort_by(d, "END_DATE")
    end = str(_v(d.iloc[-1].to_dict(), "END_DATE"))[:8]
    d = _mask_eq(d, "END_DATE", end)
    d = _sort_by(d, "STK_MKV_RATIO", ascending=False)
    name = _fund_name(client, of_ts)
    print(sep)
    print(f"前十大持仓: {name} ({of_ts})  报告期 {_fmt_date(end)}  数据源: {_s}")
    print(sep)
    print(f"\n  {'#':<4}{'股票':<16}{'代码':<12}{'市值(亿)':>10}{'占净值比':>10}")
    for i, (_, row) in enumerate(d.head(10).iterrows(), 1):
        r = row.to_dict()
        sym = str(_v(r, "SYMBOL") or "")
        nm = _symbol_name(client, sym) if sym else "-"
        mkv = float(_v(r, "MKV") or 0) / 1e4 if _v(r, "MKV") not in (None, "") else None
        ratio = _v(r, "STK_MKV_RATIO")
        print(f"  {i:<4}{nm[:14]:<16}{sym:<12}{_fmt_num(mkv):>10}{_fmt_num(ratio, '%'):>10}")
    if len(d) > 10:
        print(f"  ...共 {len(d)} 只持仓，其余未列")
    top10 = sum(float(_v(r, "STK_MKV_RATIO") or 0) for _, r in d.head(10).iterrows())
    if top10:
        flag = "⚠️ 前十大占比高，集中度高" if top10 > 70 else "（分散度正常）"
        print(f"\n  前十大持仓合计占比: {top10:.1f}%  {flag}")
    print("  注：持仓为季报披露（季度滞后），最新变动以副源天天基金为准")


def cmd_fundmanager(code):
    """历任基金经理档案 + 现任经理任职起始（判断任期样本量）。"""
    _, of_ts, _ = _resolve_fund_code(code)
    client = _get_client()
    sep = "=" * 60
    _s, d = client.call("fund_manager", ts_code=of_ts)
    if d is None or not len(d):
        _degrade_fund(client, "fund_manager")
        return
    if _col(d, "EMPLOYMENT_DATE") is not None:
        d = _sort_by(d, "EMPLOYMENT_DATE")
    name = _fund_name(client, of_ts)
    print(sep)
    print(f"基金经理档案: {name} ({of_ts})  数据源: {_s}")
    print(sep)
    print(f"\n  {'姓名':<8}{'性别':<4}{'学历':<6}{'任职起始':<12}{'状态':<8}")
    for _, row in d.iterrows():
        r = row.to_dict()
        left = _v(r, "LEFT_DATE")
        status = "现任" if left in (None, "") else "离任"
        em = _v(r, "EMPLOYMENT_DATE") or _v(r, "ANN_DATE")
        print(f"  {str(_v(r, 'NAME') or '-')[:6]:<8}{str(_v(r, 'GENDER') or '-'):<4}{str(_v(r, 'EDU') or '-'):<6}{_fmt_date(em):<12}{status:<8}")
    left_col = _col(d, "LEFT_DATE")
    if left_col is not None:
        cur = d[left_col.isna()]
        if len(cur):
            r = cur.iloc[0].to_dict()
            em = _v(r, "EMPLOYMENT_DATE")
            if em:
                emd = datetime.strptime(str(em)[:8], "%Y%m%d")
                tenure = (date.today() - emd.date()).days
                warn = "✅ 任期≥3年" if tenure >= 1095 else f"⚠️ 任期仅{tenure}天，历史业绩样本不足，需降低结论置信度"
                print(f"\n  现任经理任职起始: {_fmt_date(em)}（{warn}）")


def cmd_fundholder(code):
    """持有人结构（户数/机构/个人占比）。"""
    _, of_ts, _ = _resolve_fund_code(code)
    client = _get_client()
    sep = "=" * 60
    _s, d = client.call("fund_holder", ts_code=of_ts)
    if d is None or not len(d):
        _degrade_fund(client, "fund_holder")
        return
    d = _sort_by(d, "END_DATE")
    name = _fund_name(client, of_ts)
    print(sep)
    print(f"持有人结构: {name} ({of_ts})  数据源: {_s}")
    print(sep)
    print(f"\n  {'报告期':<12}{'持有人户数':>10}{'机构占比':>10}{'个人占比':>10}")
    for _, row in d.tail(8).iterrows():
        r = row.to_dict()
        inst = (_v(r, "INSTITUTIONAL_RATIO") or _v(r, "INS_SHARE_RATIO")
                or _v(r, "INSTITUTIONAL_SHARE_RATIO") or _v(r, "FUND_SHARE_RATIO"))
        pers = _v(r, "PERSONAL_RATIO") or _v(r, "PERSONAL_SHARE_RATIO")
        print(f"  {_fmt_date(_v(r, 'END_DATE')):<12}{_fmt_num(_v(r, 'HOLDER_NUM')):>10}{_fmt_num(inst, '%'):>10}{_fmt_num(pers, '%'):>10}")
    print("  注：机构占比上升=机构认可信号；占比过高注意大额申赎对净值的冲击")


def cmd_fundsearch(keyword):
    """搜索基金与指数代码（fund_basic + index_basic 全量，与 cmd_search 隔离）。"""
    client = _get_client()
    sep = "=" * 60
    print(sep)
    print(f"搜索结果: '{keyword}'（基金 + 指数）  数据源: ttshare代理/官方")
    print(sep)
    found = 0
    _, df = client.call("fund_basic", fields="ts_code,name")
    if df is not None and len(df):
        nm, cd = _col(df, "name"), _col(df, "ts_code")
        if nm is not None and cd is not None:
            mask = nm.astype(str).str.contains(keyword, case=False) | cd.astype(str).str.contains(keyword, case=False)
            cnt = 0
            for _, row in df[mask].head(15).iterrows():
                r = row.to_dict()
                print(f"  [基金] {_v(r, 'TS_CODE')}  {_v(r, 'NAME')}")
                found += 1
                cnt += 1
            if cnt == 0:
                print("  [基金] 无匹配")
    _, di = client.call("index_basic")
    if di is not None and len(di):
        nm, cd = _col(di, "name"), _col(di, "ts_code")
        if nm is not None and cd is not None:
            mask = nm.astype(str).str.contains(keyword, case=False) | cd.astype(str).str.contains(keyword, case=False)
            for _, row in di[mask].head(15).iterrows():
                r = row.to_dict()
                print(f"  [指数] {_v(r, 'TS_CODE')}  {_v(r, 'NAME')}")
                found += 1
    if not found:
        print(f"  ❌ 未找到匹配 '{keyword}' 的基金或指数")


def cmd_fundtracking(code, index):
    """跟踪误差：基金复权净值日收益 vs 指数日收益（按日期对齐，近2年样本）。"""
    _, of_ts, _ = _resolve_fund_code(code)
    if not index:
        print("❌ fundtracking 需要 --index 参数，如：fundtracking 510300 --index 000300.SH")
        return
    idx_ts = _resolve_index_code(index)
    client = _get_client()
    sep = "=" * 60
    _s1, dn = client.call("fund_nav", ts_code=of_ts, start_date=_days_ago(370 * 2))
    _s2, di = client.call("index_daily", ts_code=idx_ts, start_date=_days_ago(370 * 2))
    if dn is None or not len(dn) or di is None or not len(di):
        _degrade_fund(client, "fund_nav/index_daily")
        return
    dn = _sort_by(dn, "NAV_DATE")
    di = _sort_by(di, "TRADE_DATE")
    adj = _col(dn, "adj_nav")
    vcol = adj if adj is not None else _col(dn, "unit_nav")
    iclose = _col(di, "close")
    if vcol is None or iclose is None:
        _degrade_fund(client, "fund_nav/index_daily")
        return
    nav_map = {dt.date(): float(v) for dt, v in zip(_dates_from(dn, "NAV_DATE"), vcol)}
    idx_map = {dt.date(): float(v) for dt, v in zip(_dates_from(di, "TRADE_DATE"), iclose)}
    common = sorted(set(nav_map) & set(idx_map))
    if len(common) < 30:
        print("⚠️ 净值与指数对齐样本不足（<30个交易日），无法计算可靠跟踪误差")
        return
    diffs, fund_ret, idx_ret = [], [], []
    prev_n = prev_i = None
    for dt in common:
        n, i = nav_map[dt], idx_map[dt]
        if prev_n and prev_i:
            fund_ret.append(n / prev_n - 1)
            idx_ret.append(i / prev_i - 1)
            diffs.append(n / prev_n - i / prev_i)
        prev_n, prev_i = n, i
    mean_d = sum(diffs) / len(diffs)
    te = (sum((x - mean_d) ** 2 for x in diffs) / len(diffs)) ** 0.5 * (252 ** 0.5) * 100
    name = _fund_name(client, of_ts)
    iname = _index_name(client, idx_ts)
    print(sep)
    print(f"跟踪误差: {name} vs {iname}  数据源: {_s1}/{_s2}")
    print(sep)
    print(f"  对齐样本:   {len(common)} 个交易日（近2年）")
    print(f"  年化跟踪误差: {te:.2f}%  {'✅ 宽基阈值<1%' if te < 1 else '⚠️ 偏离较大，检查申赎冲击/现金留存'}")
    print(f"  日均偏离:   {mean_d * 100:+.3f}%")
    print(f"  年化超额:   {mean_d * 252 * 100:+.2f}%  （正=基金跑赢指数，负=跑输）")
    cum_f = (float(vcol.iloc[-1]) / float(vcol.iloc[0]) - 1) * 100
    cum_i = (float(iclose.iloc[-1]) / float(iclose.iloc[0]) - 1) * 100
    print(f"  区间累计:   基金 {cum_f:+.2f}% / 指数 {cum_i:+.2f}%")
    print("  注：基金按复权净值、指数按价格口径（不含股息）；长期对比请用全收益指数")


# ---------------------------------------------------------------------------
# 指数命令（index_* 接口）
# ---------------------------------------------------------------------------

def cmd_indexinfo(code):
    """指数基本盘：发布机构/基日/基点/加权方式/编制说明。"""
    idx_ts = _resolve_index_code(code)
    client = _get_client()
    sep = "=" * 60
    _s, d = client.call("index_basic", ts_code=idx_ts)
    if d is None or not len(d):
        _degrade_fund(client, "index_basic")
        return
    r = d.iloc[0].to_dict()
    name = _v(r, "NAME") or idx_ts
    print(sep)
    print(f"指数基本盘: {name} ({idx_ts})  数据源: {_s}")
    print(sep)
    print(f"  全称:       {_v(r, 'FULLNAME')}")
    print(f"  发布机构:   {_v(r, 'PUBLISHER')}")
    print(f"  基日:       {_fmt_date(_v(r, 'BASE_DATE'))}")
    print(f"  基点:       {_fmt_num(_v(r, 'BASE_POINT'))}")
    print(f"  加权方式:   {_v(r, 'WEIGHT_RULE')}")
    desc = _v(r, "DESC")
    if desc:
        print(f"  编制说明:   {str(desc)[:120]}")


def cmd_indexdaily(code):
    """指数行情与区间收益（价格口径，不含股息）。"""
    idx_ts = _resolve_index_code(code)
    client = _get_client()
    sep = "=" * 60
    _s, d = client.call("index_daily", ts_code=idx_ts, start_date=_days_ago(365 * 10 + 60))
    if d is None or not len(d):
        _degrade_fund(client, "index_daily")
        return
    d = _sort_by(d, "TRADE_DATE")
    iclose = _col(d, "close")
    if iclose is None:
        _degrade_fund(client, "index_daily")
        return
    name = _index_name(client, idx_ts)
    r = d.iloc[-1].to_dict()
    print(sep)
    print(f"指数行情: {name} ({idx_ts})  数据源: {_s}")
    print(sep)
    print(f"  日期:       {_fmt_date(_v(r, 'TRADE_DATE'))}")
    print(f"  最新收盘:   {_fmt_num(_v(r, 'CLOSE'))}")
    print(f"  涨跌幅:     {_fmt_num(_v(r, 'PCT_CHG'), '%')}")
    dates = _dates_from(d, "TRADE_DATE")
    vals = [float(v) for v in iclose]
    windows = [("近1年", 365), ("近3年", 365 * 3), ("近5年", 365 * 5), ("近10年", 365 * 10)]
    print("\n  区间收益（价格口径，不含股息）:")
    for label, pct in _returns_by_windows(dates, vals, windows):
        print(f"    {label}: {pct:+.2f}%")
    print(f"  近10年最大回撤: -{_max_drawdown(vals):.2f}%")
    _, ib = client.call("index_basic", ts_code=idx_ts)
    if ib is not None and len(ib):
        rr = ib.iloc[0].to_dict()
        bd, bp = _v(rr, "BASE_DATE"), _v(rr, "BASE_POINT")
        close_v = _v(r, "CLOSE")
        if bd and bp and close_v is not None and float(bp) > 0:
            since = (float(close_v) / float(bp) - 1) * 100
            print(f"  成立以来(近似): {since:+.2f}%（基点{_fmt_num(bp)}@{_fmt_date(bd)}，价格口径）")
    print("  注：指数为价格口径；长期收益对比请用全收益指数（副源中证指数官网）")


def cmd_indexvaluation(code, window):
    """指数估值与历史分位（index_dailybasic pe_ttm 序列百分位）。"""
    idx_ts = _resolve_index_code(code)
    client = _get_client()
    sep = "=" * 60
    days = {"1y": 370, "3y": 370 * 3, "5y": 370 * 5}.get(window, None)
    kwargs = {"ts_code": idx_ts}
    if days:
        kwargs["start_date"] = _days_ago(days)
    _s, d = client.call("index_dailybasic", **kwargs)
    if d is None or not len(d):
        _degrade_fund(client, "index_dailybasic", hint="备选：乐咕乐股 legulegu.com 指数估值页（含历史分位）")
        return
    d = _sort_by(d, "TRADE_DATE")
    name = _index_name(client, idx_ts)
    r = d.iloc[-1].to_dict()
    print(sep)
    print(f"指数估值: {name} ({idx_ts})  数据源: {_s}")
    print(sep)
    print(f"  日期:       {_fmt_date(_v(r, 'TRADE_DATE'))}")
    print(f"  PE:         {_fmt_num(_v(r, 'PE'))}")
    print(f"  PE(TTM):    {_fmt_num(_v(r, 'PE_TTM'))}")
    print(f"  PB:         {_fmt_num(_v(r, 'PB'))}")
    pc = _col(d, "pe_ttm")
    if pc is None:
        pc = _col(d, "pe")
    if pc is not None:
        s = [float(v) for v in pc if v is not None and float(v) > 0]
        if len(s) >= 10:
            cur = s[-1]
            rank = sum(1 for v in s if v <= cur) / len(s) * 100
            zone = "🔻 低估区间" if rank <= 30 else ("🔺 高估区间" if rank >= 70 else "（中性区间）")
            print(f"  历史分位:   {rank:.0f}%（{window}窗口，{len(s)}个样本）  {zone}")
    print("  注：分位低≠便宜——盈利下滑时低分位是价值陷阱；窗口口径必须标注")


def cmd_indexweight(code):
    """指数成分权重与集中度（前30 + 前5/前10权重合计）。"""
    idx_ts = _resolve_index_code(code)
    client = _get_client()
    sep = "=" * 60
    _s, d = client.call("index_weight", index_code=idx_ts)
    if d is None or not len(d):
        _degrade_fund(client, "index_weight")
        return
    d = _sort_by(d, "TRADE_DATE")
    end = str(_v(d.iloc[-1].to_dict(), "TRADE_DATE"))[:8]
    d = _mask_eq(d, "TRADE_DATE", end)
    d = _sort_by(d, "WEIGHT", ascending=False)
    name = _index_name(client, idx_ts)
    print(sep)
    print(f"指数成分权重: {name} ({idx_ts})  截至 {_fmt_date(end)}  数据源: {_s}")
    print(sep)
    print(f"  成分数量:   {len(d)}")
    print(f"\n  {'#':<4}{'股票':<16}{'代码':<12}{'权重':>8}")
    for i, (_, row) in enumerate(d.head(30).iterrows(), 1):
        r = row.to_dict()
        sym = str(_v(r, "CON_CODE") or "")
        nm = _symbol_name(client, sym) if sym else "-"
        print(f"  {i:<4}{nm[:14]:<16}{sym:<12}{_fmt_num(_v(r, 'WEIGHT'), '%')}")
    w = [float(_v(r, "WEIGHT") or 0) for _, r in d.head(30).iterrows()]
    if w:
        top5, top10 = sum(w[:5]), sum(w[:10])
        print(f"\n  前5权重合计: {top5:.1f}% / 前10权重合计: {top10:.1f}%")
        if top10 > 60:
            print("  ⚠️ 前10权重>60%，集中度高——'指数=分散'是错觉，警惕权重股黑天鹅")
    if len(d) > 30:
        print(f"  ...共 {len(d)} 只成分，其余未列（全量成分见中证指数官网）")
    print("  注：指数权重接口无覆盖时，可用跟踪该指数的 ETF 的 fundholdings 兜底")


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

    # 基金命令（fund_* 接口；与股票命令完全隔离）
    for cmd, help_text in [
        ("fundinfo", "基金基本盘（类型/费率/经理/跟踪指数）"),
        ("fundnav", "净值与业绩（复权净值/区间收益/回撤）"),
        ("funddaily", "场内行情/流动性/折溢价"),
        ("fundshares", "份额与规模变动（近8期）"),
        ("fundholdings", "季报前十大持仓"),
        ("fundmanager", "历任基金经理档案"),
        ("fundholder", "持有人结构"),
        ("fundtracking", "跟踪误差（基金净值 vs 指数）"),
        ("indexinfo", "指数基本盘（发布机构/基日/加权方式）"),
        ("indexdaily", "指数行情与区间收益"),
        ("indexvaluation", "指数估值与历史分位"),
        ("indexweight", "指数成分权重与集中度"),
    ]:
        p = sub.add_parser(cmd, help=help_text)
        p.add_argument("code", help="基金代码（如 510300 / 161725 / 012414）或指数代码（如 000300.SH）")
        p.add_argument("--index", help="指数代码（fundtracking 用，如 000300.SH）")
        p.add_argument("--start", help="起始日期 YYYYMMDD（fundnav 用，限任职期）")
        p.add_argument("--period", help="报告期 YYYYMMDD（fundholdings 用）")
        p.add_argument("--window", choices=["1y", "3y", "5y", "all"], default="5y",
                       help="估值分位窗口（indexvaluation 用，默认 5y）")

    p_fundsearch = sub.add_parser("fundsearch", help="搜索基金与指数代码")
    p_fundsearch.add_argument("keyword", help="基金名/指数名或代码")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    try:
        if args.command == "search":
            cmd_search(args.keyword)
        elif args.command == "fundsearch":
            cmd_fundsearch(args.keyword)
        elif args.command == "fundnav":
            cmd_fundnav(args.code, args.start)
        elif args.command == "fundholdings":
            cmd_fundholdings(args.code, args.period)
        elif args.command == "fundtracking":
            cmd_fundtracking(args.code, args.index)
        elif args.command == "indexvaluation":
            cmd_indexvaluation(args.code, args.window)
        else:
            {
                "quote": cmd_quote,
                "valuation": cmd_valuation,
                "financials": cmd_financials,
                "dividend": cmd_dividend,
                "fundinfo": cmd_fundinfo,
                "funddaily": cmd_funddaily,
                "fundshares": cmd_fundshares,
                "fundmanager": cmd_fundmanager,
                "fundholder": cmd_fundholder,
                "indexinfo": cmd_indexinfo,
                "indexdaily": cmd_indexdaily,
                "indexweight": cmd_indexweight,
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
