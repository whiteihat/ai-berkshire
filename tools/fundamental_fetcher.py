#!/usr/bin/env python3
"""A股基本面数据批量落盘工具。

从 Tushare（cheapyun 代理优先）获取 A 股基本面数据，按规范目录结构保存到 local/ 下。
报告生成时直接从 local/ 读取落盘数据，不再实时调用接口。

财务主表回溯采用"10+N"模式：默认近十年（以当前年份往前推 10 个完整年度，
每年含一季报/中报/三季报/年报），并自动纳入当年已披露的报告期（如 2026 中报，
不占十年名额）；--years 可覆盖完整年度数。当年已发布期间排在最前优先拉取。

时间对齐机制：
  - _get_report_periods 决定"拉取哪些期间"（按期间末日 ≤ 今天）。
  - _should_retry_period 判断每个期间是否值得重试（空文件、核心接口不完整、
    已过披露截止日但无数据 → 重试；数据完整 → 跳过）。
  - _check_report_disclosed 结合公告元数据和法定披露截止日交叉验证披露状态。
  - update_stock 在增量更新前先刷新公告列表，确保使用最新披露信息。

用法：
    python tools/fundamental_fetcher.py fetch 600938 中国海油        # 单股落盘（含公告）
    python tools/fundamental_fetcher.py fetch 600938 中国海油 --years 10  # 指定年数
    python tools/fundamental_fetcher.py update 600938 中国海油       # 增量更新（智能重试）
    python tools/fundamental_fetcher.py anns 600938 中国海油         # 单独拉取公告
    python tools/fundamental_fetcher.py anns 600938 中国海油 --limit 50  # 指定条数
    python tools/fundamental_fetcher.py check 600938 中国海油        # 检查落盘完整性
    python tools/fundamental_fetcher.py batch stocks.txt            # 批量落盘
    python tools/fundamental_fetcher.py list                        # 列出已落盘的股票

目录结构：
    local/{name}_{ts_code}/
    ├── raw/
    │   ├── financial/       # 财务主表（income/balance/cashflow/fina_indicator/forecast/express/dividend）
    │   ├── daily/           # 日线行情（daily_basic）
    │   ├── meta/            # 元数据（stock_basic）
    │   └── announcements.json  # 公告元数据（东方财富 API）
    └── manifest.json        # 落盘记录

依赖：tushare（含 pandas）。其余仅 stdlib。
"""

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime, date

# Windows 控制台中文输出
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

# 项目根目录
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_LOCAL_DIR = os.path.join(_ROOT, "local")

# 全局限流器
_last_request_time = 0.0
REQUEST_INTERVAL = 0.75  # 秒

# 财务主表接口（按报告期分文件）
FINANCIAL_APIS = [
    "income",          # 利润表
    "balancesheet",    # 资产负债表
    "cashflow",        # 现金流量表
    "fina_indicator",  # 财务指标
    "forecast",        # 业绩预告
    "express",         # 业绩快报
]

# 其他接口
META_APIS = ["stock_basic"]
DIVIDEND_API = "dividend"
DAILY_API = "daily_basic"


def _rate_limit():
    """全局限流：确保每次请求间隔 >= 0.75s。"""
    global _last_request_time
    elapsed = time.time() - _last_request_time
    if elapsed < REQUEST_INTERVAL:
        time.sleep(REQUEST_INTERVAL - elapsed)
    _last_request_time = time.time()


def _get_pro():
    """获取 Tushare pro_api（cheapyun 代理优先，官方兜底）。

    优先级：cheapyun（tushare_token_cheapyun.txt）→ 官方（tushare_token.txt）
    """
    import tushare as ts

    # 读 token
    def _read(env, fname):
        t = os.environ.get(env, "").strip()
        if t:
            return t
        try:
            with open(os.path.join(_LOCAL_DIR, fname), encoding="utf-8") as f:
                return f.read().strip() or None
        except OSError:
            return None

    # cheapyun 代理
    cheapyun_tok = _read("CHEAPYUN_TOKEN", "tushare_token_cheapyun.txt")
    if cheapyun_tok:
        ts.set_token(cheapyun_tok)
        pro = ts.pro_api()
        pro._DataApi__http_url = "http://cheap-host1.cheapyun.com:42461"
        return pro, "cheapyun代理"

    # 官方
    official_tok = _read("TUSHARE_TOKEN", "tushare_token.txt")
    if official_tok:
        ts.set_token(official_tok)
        pro = ts.pro_api()
        return pro, "tushare官方"

    raise ConnectionError(
        "未配置 Tushare token。请设置环境变量 CHEAPYUN_TOKEN 或 TUSHARE_TOKEN，"
        "或在 local/ 下放置对应 token 文件。"
    )


# ---------------------------------------------------------------------------
# 东方财富公告 API（免费，无需 token）
# ---------------------------------------------------------------------------

_EASTMONEY_ANN_URL = "https://np-anotice-stock.eastmoney.com/api/security/ann"
_EASTMONEY_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://data.eastmoney.com/",
    "Accept": "application/json, text/plain, */*",
}


def _fetch_eastmoney_anns(ts_code_6, limit=30):
    """从东方财富获取公告列表（免费 API，无需 token）。

    Args:
        ts_code_6: 6位纯数字股票代码，如 "600938"
        limit: 获取条数（最大 50）

    Returns:
        list[dict]: 公告列表，每条包含 art_code/title/notice_date/columns/url
    """
    import urllib.request
    import urllib.parse

    params = urllib.parse.urlencode({
        "sr": "-1",
        "page_size": min(limit, 50),
        "page_index": "1",
        "ann_type": "A",
        "client_source": "web",
        "stock_list": ts_code_6,
        "f_node": "0",
        "s_node": "0",
    })
    url = f"{_EASTMONEY_ANN_URL}?{params}"
    req = urllib.request.Request(url, headers=_EASTMONEY_HEADERS)

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        logging.warning(f"  东方财富公告 API 请求失败: {e}")
        return []

    if not (data.get("success") and data.get("data") and data["data"].get("list")):
        return []

    anns = []
    for item in data["data"]["list"]:
        art_code = item.get("art_code", "")
        notice_date = item.get("notice_date", "")
        # 格式化日期：可能是 "2026-08-19 10:30:00" 或时间戳
        if " " in str(notice_date):
            notice_date = str(notice_date).split(" ")[0]
        elif isinstance(notice_date, (int, float)):
            notice_date = datetime.fromtimestamp(notice_date / 1000).strftime("%Y-%m-%d")

        anns.append({
            "art_code": art_code,
            "title": item.get("title", ""),
            "notice_date": str(notice_date),
            "columns": item.get("columns", ""),
            "url": f"https://data.eastmoney.com/notices/detail/{ts_code_6}/{art_code}.html",
        })
    return anns


def _call_with_retry(pro, api, max_retries=3, **kwargs):
    """带限流和重试的接口调用。返回 DataFrame 或 None。"""
    for attempt in range(max_retries):
        _rate_limit()
        try:
            df = getattr(pro, api)(**kwargs)
            return df
        except Exception as e:
            if attempt < max_retries - 1:
                wait = (attempt + 1) * 2
                logging.warning(f"  {api} 失败 (尝试 {attempt + 1}/{max_retries}): {e}, {wait}s 后重试")
                time.sleep(wait)
            else:
                logging.error(f"  {api} 失败 (已重试 {max_retries} 次): {e}")
                return None
    return None


def _ensure_dir(path):
    """确保目录存在。"""
    os.makedirs(path, exist_ok=True)


def _save_json(records, filepath):
    """保存列表到 JSON 文件。"""
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2, default=str)


def _load_manifest(stock_dir):
    """加载 manifest.json。"""
    path = os.path.join(stock_dir, "manifest.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"periods": {}, "metadata": {}, "last_fetch": None}


def _save_manifest(stock_dir, manifest):
    """保存 manifest.json。"""
    path = os.path.join(stock_dir, "manifest.json")
    _save_json(manifest, path)


def _listing_year(stock_dir):
    """从落盘的 stock_basic.json 读取上市年份。

    若无落盘数据或解析失败返回 None，由调用方决定是否截断。
    """
    path = os.path.join(stock_dir, "raw", "meta", "stock_basic.json")
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            records = json.load(f)
        if isinstance(records, list) and records:
            list_date = str(records[0].get("list_date", ""))
            if len(list_date) >= 4:
                return int(list_date[:4])
    except (json.JSONDecodeError, OSError, ValueError):
        pass
    return None


def _disclosure_deadline(period):
    """计算某报告期的法定披露截止日（A股）。

    规则（证监会《上市公司信息披露管理办法》）：
      - 年报(1231)：次年 4 月 30 日
      - 中报(0630)：当年 8 月 31 日
      - 一季报(0331)：当年 4 月 30 日
      - 三季报(0930)：当年 10 月 31 日

    Returns:
        date: 法定披露截止日；无法解析时返回 None
    """
    try:
        y = int(period[:4])
        mmdd = period[4:]
        if mmdd == "1231":
            return date(y + 1, 4, 30)
        elif mmdd == "0630":
            return date(y, 8, 31)
        elif mmdd == "0331":
            return date(y, 4, 30)
        elif mmdd == "0930":
            return date(y, 10, 31)
    except (ValueError, IndexError):
        pass
    return None


def _check_report_disclosed(period, announcements):
    """根据公告元数据判断某报告期是否已实际披露。

    识别逻辑：扫描公告标题中的关键词（年报/半年度报告/季度报告）和期间数字，
    若公告日期在法定披露截止日之前或附近（允许 3 天缓冲），则视为已披露。

    Args:
        period: 报告期字符串，如 "20251231"
        announcements: 公告列表（来自 announcements.json）

    Returns:
        bool | None: True=已披露, False=应披露但未见公告, None=无法判断
    """
    if not announcements:
        return None

    try:
        y = int(period[:4])
        mmdd = period[4:]
    except (ValueError, IndexError):
        return None

    # 期间关键词映射
    period_keywords = {
        "1231": [f"{y}年年度报告", f"{y}年报", f"{y}年度报告"],
        "0630": [f"{y}年半年度报告", f"{y}年中报", f"{y}半年度报告", f"{y}中期报告"],
        "0331": [f"{y}年第一季度报告", f"{y}年一季报", f"{y}Q1报告"],
        "0930": [f"{y}年第三季度报告", f"{y}年三季报", f"{y}Q3报告"],
    }

    keywords = period_keywords.get(mmdd, [])
    deadline = _disclosure_deadline(period)
    if not deadline:
        return None

    # 对已过披露截止日 3 年以上的历史期间，不做公告交叉验证
    # （公告列表通常只覆盖近 1-2 年，找不到不等于未披露）
    from datetime import timedelta
    buffer = timedelta(days=3)
    if deadline + buffer < date.today() - timedelta(days=365 * 3):
        return None

    # 扫描公告：标题含期间关键词且公告日期 ≤ 截止日+3天缓冲
    for ann in announcements:
        title = ann.get("title", "")
        notice_date_str = ann.get("notice_date", "")
        if not notice_date_str:
            continue
        try:
            notice_date = date.fromisoformat(notice_date_str)
        except ValueError:
            continue
        # 标题匹配
        if any(kw in title for kw in keywords):
            if notice_date <= deadline + buffer:
                return True
        # 备用：标题含"报告"且包含期间末日数字
        if "报告" in title and period in title:
            if notice_date <= deadline + buffer:
                return True

    # 已过截止日+缓冲仍未找到 → 视为未披露
    today = date.today()
    if deadline + buffer < today:
        return False
    return None


def _report_type(period):
    """根据报告期后缀判断报告类型。"""
    mmdd = period[4:] if len(period) >= 8 else ""
    return {"0331": "Q1", "0630": "semi", "0930": "Q3", "1231": "annual"}.get(mmdd, "unknown")


def _should_retry_period(period, stock_dir, fin_dir, manifest, announcements=None):
    """判断某报告期是否值得重新拉取。

    规则（按优先级）：
      1. 文件不存在 → 重试
      2. 文件存在但为空（0 字节或 JSON 空列表）→ 重试
      3. 核心接口不完整（income/balancesheet/cashflow/fina_indicator 任一缺失）→ 重试
      4. 报告已过法定披露截止日但未在 manifest 中标记为有数据 → 重试
      5. 以上均不满足 → 跳过

    Args:
        period: 报告期字符串
        stock_dir: 公司落盘根目录
        fin_dir: 财务数据目录
        manifest: 当前 manifest dict
        announcements: 公告列表（可选，用于判断实际披露状态）

    Returns:
        tuple[bool, str]: (是否重试, 跳过/重试原因)
    """
    import json as _json

    core_apis = ["income", "balancesheet", "cashflow", "fina_indicator"]

    # 检查各 API 文件状态
    existing = []
    empty_files = []
    missing = []
    for api in FINANCIAL_APIS:
        filepath = os.path.join(fin_dir, f"{api}_{period}.json")
        if os.path.exists(filepath):
            # 检查文件是否实际包含数据
            try:
                size = os.path.getsize(filepath)
                if size <= 2:  # 空 JSON: [] 或 {}
                    empty_files.append(api)
                else:
                    with open(filepath, "r", encoding="utf-8") as f:
                        data = _json.load(f)
                    if not data:
                        empty_files.append(api)
                    else:
                        existing.append(api)
            except (OSError, _json.JSONDecodeError):
                empty_files.append(api)
        else:
            missing.append(api)

    # 规则 1 & 2：全部文件缺失或全部为空
    if not existing:
        if missing:
            return True, f"所有文件缺失: {', '.join(missing[:4])}"
        if empty_files:
            return True, f"所有文件为空: {', '.join(empty_files[:4])}"

    # 规则 3：核心接口不完整
    core_missing = [a for a in core_apis if a in missing or a in empty_files]
    if core_missing:
        return True, f"核心接口不完整: {', '.join(core_missing)}"

    # 规则 4：已过披露截止日但无数据（优先检查实际文件，兼容 manifest 不完整的情况）
    deadline = _disclosure_deadline(period)
    today = date.today()
    if deadline and deadline < today:
        # 先检查 manifest，再检查实际文件（兼容之前不完整 fetch 创建了文件但未更新 manifest 的情况）
        period_data = manifest.get("periods", {}).get(period, {})
        manifest_has_data = any(period_data.get(api) for api in core_apis)
        file_has_data = any(
            os.path.exists(os.path.join(fin_dir, f"{api}_{period}.json"))
            and os.path.getsize(os.path.join(fin_dir, f"{api}_{period}.json")) > 2
            for api in core_apis
        )
        if not manifest_has_data and not file_has_data:
            return True, f"已过披露截止日 {deadline}，manifest 和文件均无数据"

    # 规则 5：使用公告数据做二次确认（仅当核心文件缺失或不完整时）
    # 如果核心文件已存在且有数据，即使公告中未找到也不重试（公告列表可能不覆盖该期间）
    core_files_ok = all(
        os.path.exists(os.path.join(fin_dir, f"{api}_{period}.json"))
        and os.path.getsize(os.path.join(fin_dir, f"{api}_{period}.json")) > 2
        for api in core_apis
    )
    if not core_files_ok and announcements is not None:
        disclosed = _check_report_disclosed(period, announcements)
        if disclosed is False:
            # 应已披露但公告中未找到 → 可能是延迟或遗漏，重试
            return True, f"公告中未找到 {period} 披露记录（核心文件不完整）"

    return False, f"数据完整: {len(existing)} 个接口有数据"


def _get_report_periods(years=10):
    """生成要拉取的报告期列表："10+N"模式 — 当年已披露期间优先 + 近 N 个完整年度。

    返回顺序：当年已发布的报告期排在最前，近 N 个完整年度紧随其后。
    最新数据对分析最重要，优先拉取确保最新季报/中报/年报最先落盘。

    "近十年"定义（以 2026 年为例）：
      - 完整十年 = 2016–2025，每年含 4 条报告期：0331（一季报）、0630（中报）、
        0930（三季报）、1231（年报）。
      - 当年（2026）已结束的报告期（如 2026Q1、2026 中报，即 0331/0630/0930/1231
        中"期间末日 ≤ 今天"者）一并纳入，且**不占用**上述 N 年名额。
      - 期间已结束但公司尚未披露时，Tushare 返回空 → 不落盘；下次 update 时由
        _should_retry_period 识别并自动重试，从而保证"所有已发布的报告期"（最新季报/
        中报/年报）都能被拉到。

    时间对齐注意：
      - 本函数只决定"拉取哪些期间"和"拉取顺序"，不涉及报告是否已实际披露的判断。
      - 披露状态由 fetch_stock/update_stock 中的 _should_retry_period 结合公告
        元数据（announcements.json）和法定披露截止日（_disclosure_deadline）判定。
      - 年报(1231)通常在次年 Q1 披露，中报(0630)在当年 Q3，季报在下一季度内。
        这意味着当前年份的 1231 期间在当年内可能无数据（直到次年年报季），
        这是正常行为——update 会在后续执行时自动重试。
    """
    current_year = date.today().year
    periods = []
    # 当年已结束的报告期排在最前（最新数据优先落盘）
    today = date.today()
    for mm, dd in (("03", "31"), ("06", "30"), ("09", "30"), ("12", "31")):
        if date(current_year, int(mm), int(dd)) <= today:
            periods.append(f"{current_year}{mm}{dd}")
    # 近 N 个完整年度紧随其后（最晚年份在前）
    for y in range(current_year - 1, current_year - years - 1, -1):
        periods += [f"{y}0331", f"{y}0630", f"{y}0930", f"{y}1231"]
    return periods


def _setup_logging(stock_dir):
    """配置日志：同时输出到控制台和文件。"""
    log_dir = os.path.join(stock_dir, "log")
    _ensure_dir(log_dir)
    log_file = os.path.join(log_dir, f"fetch_{datetime.now().strftime('%Y%m%d')}.log")

    # 清除已有的 handler
    root_logger = logging.getLogger()
    root_logger.handlers.clear()

    root_logger.setLevel(logging.INFO)

    # 文件 handler
    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setLevel(logging.INFO)
    fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    root_logger.addHandler(fh)

    # 控制台 handler
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(logging.Formatter("  %(message)s"))
    root_logger.addHandler(ch)

    return log_file


def fetch_stock(ts_code_6, name, years=10, skip_existing=True):
    """落盘单只 A 股的基本面数据。

    Args:
        ts_code_6: 6 位纯数字股票代码，如 "600938"
        name: 公司名称，如 "中国海油"
        years: 回溯年数（默认 10，指当前年份往前推的完整年度数；含季报/中报/年报，
               并自动纳入当年已披露的报告期，口径见 _get_report_periods）
        skip_existing: 是否跳过已落盘的期间（增量模式）

    Returns:
        dict: 各接口的落盘统计
    """
    pro, source_label = _get_pro()
    ts_code = f"{ts_code_6}.SH" if ts_code_6.startswith(("6", "9")) else f"{ts_code_6}.SZ"
    stock_dir = os.path.join(_LOCAL_DIR, f"{name}_{ts_code_6}")
    _ensure_dir(os.path.join(stock_dir, "raw", "financial"))
    _ensure_dir(os.path.join(stock_dir, "raw", "daily"))
    _ensure_dir(os.path.join(stock_dir, "raw", "meta"))

    log_file = _setup_logging(stock_dir)
    manifest = _load_manifest(stock_dir)

    logging.info(f"{'=' * 60}")
    logging.info(f"开始落盘: {name} ({ts_code})  数据源: {source_label}")
    logging.info(f"回溯年数: {years}  跳过已存在: {skip_existing}")
    logging.info(f"日志文件: {log_file}")
    logging.info(f"{'=' * 60}")

    stats = {"success": 0, "empty": 0, "failed": 0, "skipped": 0}

    # 1. 股票基本信息
    logging.info("\n[1/4] 股票基本信息")
    meta_dir = os.path.join(stock_dir, "raw", "meta")
    filepath = os.path.join(meta_dir, "stock_basic.json")
    if not (skip_existing and os.path.exists(filepath)):
        df = _call_with_retry(pro, "stock_basic",
                              ts_code=ts_code,
                              fields="ts_code,symbol,name,area,industry,market,list_date,fullname,enname,cnspell,exchange,curr_type,list_status,is_hs")
        if df is not None and len(df):
            _save_json(df.to_dict(orient="records"), filepath)
            manifest["metadata"]["stock_basic"] = True
            logging.info(f"  ✅ stock_basic → {len(df)} 条")
            stats["success"] += 1
        else:
            logging.warning(f"  ⚠️  stock_basic → 无数据")
            stats["empty"] += 1
    else:
        logging.info(f"  ⏭️  stock_basic → 已存在，跳过")
        stats["skipped"] += 1

    # 2. 财务主表（按报告期）
    #    用 _should_retry_period 做智能判断：空文件、核心接口不完整、
    #    已过披露截止日但无数据 → 自动重试；数据完整 → 跳过。
    logging.info("\n[2/4] 财务主表")
    fin_dir = os.path.join(stock_dir, "raw", "financial")

    # 预加载公告元数据，供 _should_retry_period 交叉验证披露状态
    announcements = None
    ann_path = os.path.join(stock_dir, "raw", "announcements.json")
    if os.path.exists(ann_path):
        try:
            with open(ann_path, "r", encoding="utf-8") as f:
                announcements = json.load(f)
        except (json.JSONDecodeError, OSError):
            announcements = None

    periods = _get_report_periods(years)

    # 上市时间截断：如果公司上市不足 N 年，丢弃上市前的空期间，避免反复无效重试
    _first_year = _listing_year(stock_dir)
    if _first_year is not None:
        before = len(periods)
        periods = [p for p in periods if int(p[:4]) >= _first_year]
        dropped = before - len(periods)
        if dropped > 0:
            logging.info(f"  公司上市年份为 {_first_year}，丢弃 {dropped} 个上市前空期间")

    retried_count = 0
    for period in periods:
        if skip_existing:
            should_retry, reason = _should_retry_period(
                period, stock_dir, fin_dir, manifest, announcements
            )
            if not should_retry:
                stats["skipped"] += 1
                continue
            if retried_count < 10 or "核心" in reason or "披露" in reason:
                logging.info(f"  🔄 {period} → 重试: {reason}")
            retried_count += 1

        for api in FINANCIAL_APIS:
            filepath = os.path.join(fin_dir, f"{api}_{period}.json")
            if skip_existing and os.path.exists(filepath):
                # 即使文件存在，也检查是否为空——空文件不跳过
                try:
                    if os.path.getsize(filepath) > 2:
                        stats["skipped"] += 1
                        continue
                except OSError:
                    pass

            # 部分接口不支持所有参数
            kwargs = {"ts_code": ts_code, "period": period}
            if api == "forecast":
                kwargs.pop("period", None)
                kwargs["start_date"] = period
                kwargs["end_date"] = period
            elif api == "express":
                kwargs.pop("period", None)
                kwargs["start_date"] = period
                kwargs["end_date"] = period

            df = _call_with_retry(pro, api, **kwargs)
            if df is not None and len(df):
                _save_json(df.to_dict(orient="records"), filepath)
                manifest["periods"].setdefault(period, {})[api] = True
                logging.info(f"  ✅ {api} {period} → {len(df)} 条")
                stats["success"] += 1
            else:
                logging.info(f"  ⚠️  {api} {period} → 无数据（正常，非每期都有）")
                stats["empty"] += 1

    # 3. 分红（全量）
    logging.info("\n[3/4] 分红数据")
    dividend_path = os.path.join(fin_dir, "dividend.json")
    if not (skip_existing and os.path.exists(dividend_path)):
        df = _call_with_retry(pro, DIVIDEND_API, ts_code=ts_code)
        if df is not None and len(df):
            _save_json(df.to_dict(orient="records"), dividend_path)
            manifest["metadata"]["dividend"] = True
            logging.info(f"  ✅ dividend → {len(df)} 条")
            stats["success"] += 1
        else:
            logging.warning(f"  ⚠️  dividend → 无数据")
            stats["empty"] += 1
    else:
        logging.info(f"  ⏭️  dividend → 已存在，跳过")
        stats["skipped"] += 1

    # 4. 近 30 天每日指标（daily_basic）
    logging.info("\n[4/5] 近期日线指标")
    daily_dir = os.path.join(stock_dir, "raw", "daily")
    today_str = date.today().strftime("%Y%m%d")
    from datetime import timedelta
    start_str = (date.today() - timedelta(days=40)).strftime("%Y%m%d")
    daily_path = os.path.join(daily_dir, f"daily_basic_latest.json")
    if not (skip_existing and os.path.exists(daily_path)):
        df = _call_with_retry(pro, DAILY_API,
                              ts_code=ts_code,
                              start_date=start_str,
                              end_date=today_str,
                              fields="ts_code,trade_date,close,turnover_rate,turnover_rate_f,volume_ratio,pe,pe_ttm,pb,ps,ps_ttm,dv_ratio,dv_ttm,total_share,float_share,free_share,total_mv,circ_mv")
        if df is not None and len(df):
            _save_json(df.to_dict(orient="records"), daily_path)
            manifest["metadata"]["daily_basic"] = True
            logging.info(f"  ✅ daily_basic → {len(df)} 条")
            stats["success"] += 1
        else:
            logging.warning(f"  ⚠️  daily_basic → 无数据")
            stats["empty"] += 1
    else:
        logging.info(f"  ⏭️  daily_basic → 已存在，跳过")
        stats["skipped"] += 1

    # 5. 公告列表（东方财富 API，免费）
    logging.info("\n[5/5] 公告列表")
    ann_path = os.path.join(stock_dir, "raw", "announcements.json")
    if not (skip_existing and os.path.exists(ann_path)):
        anns = _fetch_eastmoney_anns(ts_code_6, limit=30)
        if anns:
            _save_json(anns, ann_path)
            manifest["announcements"] = {
                "last_fetch": datetime.now().strftime("%Y-%m-%d"),
                "count": len(anns),
                "latest_date": anns[0]["notice_date"] if anns else None,
            }
            logging.info(f"  ✅ announcements → {len(anns)} 条（最新: {anns[0]['notice_date']}）")
            stats["success"] += 1
        else:
            logging.warning(f"  ⚠️  announcements → 无数据")
            stats["empty"] += 1
    else:
        logging.info(f"  ⏭️  announcements → 已存在，跳过")
        stats["skipped"] += 1

    # 更新 manifest
    manifest["last_fetch"] = datetime.now().isoformat()
    manifest["ts_code"] = ts_code
    manifest["name"] = name
    # 记录最新公告日期（供 _check_report_disclosed 交叉验证）
    ann_info = manifest.get("announcements", {})
    if ann_info.get("latest_date"):
        manifest["metadata"]["last_announcement_date"] = ann_info["latest_date"]
    _save_manifest(stock_dir, manifest)

    logging.info(f"\n{'=' * 60}")
    logging.info(f"落盘完成: {name} ({ts_code})")
    logging.info(f"  成功: {stats['success']}  空数据: {stats['empty']}  失败: {stats['failed']}  跳过: {stats['skipped']}")
    logging.info(f"  数据目录: {stock_dir}/raw/")
    logging.info(f"  Manifest: {stock_dir}/manifest.json")
    logging.info(f"{'=' * 60}")

    return stats


def update_stock(ts_code_6, name):
    """增量更新：智能重试缺失和不完整期间。

    与 fetch_stock(skip_existing=True) 配合，由 _should_retry_period 判断每个期间
    是否需要重试。以下情况会自动重试：
      - 文件不存在（从未成功拉取）
      - 文件为空（Tushare 返回空但文件已创建）
      - 核心接口（income/balancesheet/cashflow/fina_indicator）不完整
      - 已过法定披露截止日但 manifest 中无数据
      - 公告元数据中未找到对应报告期的披露记录

    此外，当前年份（当年）的已结束期间始终纳入重试候选，确保最新季报/中报
    在披露后能被及时拉取。
    """
    stock_dir = os.path.join(_LOCAL_DIR, f"{name}_{ts_code_6}")
    manifest = _load_manifest(stock_dir)
    if not manifest.get("last_fetch"):
        logging.info("无 manifest 记录，执行完整落盘")
        return fetch_stock(ts_code_6, name)

    logging.info(f"上次落盘: {manifest['last_fetch']}")
    logging.info(f"已有期间: {len(manifest.get('periods', {}))} 个")

    # 先更新公告列表（确保有最新披露信息用于交叉验证）
    ann_path = os.path.join(stock_dir, "raw", "announcements.json")
    try:
        anns = _fetch_eastmoney_anns(ts_code_6, limit=30)
        if anns:
            _save_json(anns, ann_path)
            manifest["announcements"] = {
                "last_fetch": datetime.now().strftime("%Y-%m-%d"),
                "count": len(anns),
                "latest_date": anns[0]["notice_date"] if anns else None,
            }
            manifest["metadata"]["last_announcement_date"] = anns[0]["notice_date"] if anns else None
    except Exception as e:
        logging.warning(f"公告更新失败（不影响财务数据更新）: {e}")

    return fetch_stock(ts_code_6, name, skip_existing=True)


def fetch_announcements(ts_code_6, name, limit=30):
    """单独拉取公告列表（东方财富 API）。"""
    stock_dir = os.path.join(_LOCAL_DIR, f"{name}_{ts_code_6}")
    _ensure_dir(os.path.join(stock_dir, "raw"))

    sep = "=" * 60
    print(sep)
    print(f"拉取公告: {name} ({ts_code_6})  条数: {limit}")
    print(sep)

    anns = _fetch_eastmoney_anns(ts_code_6, limit=limit)
    if not anns:
        print("  ⚠️  未获取到公告")
        return

    ann_path = os.path.join(stock_dir, "raw", "announcements.json")
    _save_json(anns, ann_path)

    # 更新 manifest
    manifest = _load_manifest(stock_dir)
    manifest["announcements"] = {
        "last_fetch": datetime.now().strftime("%Y-%m-%d"),
        "count": len(anns),
        "latest_date": anns[0]["notice_date"] if anns else None,
    }
    _save_manifest(stock_dir, manifest)

    print(f"  ✅ 已保存 {len(anns)} 条公告到 {ann_path}")
    print(f"\n  最近公告:")
    for i, ann in enumerate(anns[:10], 1):
        print(f"  {i:2d}. [{ann['notice_date']}] {ann['title'][:60]}")
    if len(anns) > 10:
        print(f"  ...共 {len(anns)} 条")
    print(sep)


def check_stock(ts_code_6, name):
    """检查落盘完整性。"""
    stock_dir = os.path.join(_LOCAL_DIR, f"{name}_{ts_code_6}")
    manifest = _load_manifest(stock_dir)

    sep = "=" * 60
    print(sep)
    print(f"落盘完整性检查: {name} ({ts_code_6})")
    print(sep)

    if not manifest.get("last_fetch"):
        print("❌ 未找到落盘记录，请先执行 fetch")
        return

    print(f"  上次落盘: {manifest['last_fetch']}")
    print(f"  已落盘期间: {len(manifest.get('periods', {}))} 个")
    print()

    # 检查文件是否存在
    fin_dir = os.path.join(stock_dir, "raw", "financial")
    meta_dir = os.path.join(stock_dir, "raw", "meta")

    # 核心接口（必须有数据）
    core_apis = ["income", "balancesheet", "cashflow", "fina_indicator"]
    # 可选接口（可能无数据，不标记为缺失）
    optional_apis = ["forecast", "express"]

    issues = []
    for api in core_apis + optional_apis:
        existing = [f for f in os.listdir(fin_dir) if f.startswith(f"{api}_") and f.endswith(".json")] if os.path.exists(fin_dir) else []
        if existing:
            is_optional = api in optional_apis
            icon = "✅" if not is_optional else "ℹ️ "
            print(f"  {icon} {api:20s} → {len(existing)} 个期间文件{'（可选接口，无数据正常）' if is_optional else ''}")
        else:
            if api in optional_apis:
                print(f"  ℹ️  {api:20s} → 无数据（可选接口，正常）")
            else:
                print(f"  ❌ {api:20s} → 缺失")
                issues.append(api)

    # 检查 meta
    for meta_api in META_APIS:
        path = os.path.join(meta_dir, f"{meta_api}.json")
        if os.path.exists(path):
            print(f"  ✅ {meta_api:20s} → 已落盘")
        else:
            print(f"  ❌ {meta_api:20s} → 缺失")
            issues.append(meta_api)

    # 检查 dividend
    path = os.path.join(fin_dir, "dividend.json")
    if os.path.exists(path):
        print(f"  ✅ {'dividend':20s} → 已落盘")
    else:
        print(f"  ❌ {'dividend':20s} → 缺失")
        issues.append("dividend")

    # 检查 announcements
    ann_path = os.path.join(stock_dir, "raw", "announcements.json")
    if os.path.exists(ann_path):
        with open(ann_path, "r", encoding="utf-8") as f:
            ann_count = len(json.load(f))
        ann_info = manifest.get("announcements", {})
        latest = ann_info.get("latest_date", "?")
        print(f"  ✅ {'announcements':20s} → {ann_count} 条（最新: {latest}）")
    else:
        print(f"  ℹ️  {'announcements':20s} → 未拉取（可选）")

    print()
    if issues:
        print(f"⚠️  缺失 {len(issues)} 项: {', '.join(issues)}")
        print("  建议执行: python tools/fundamental_fetcher.py update", ts_code_6, name)
    else:
        print("✅ 数据完整（核心接口全有，可选接口视公司情况）")
    print(sep)


def batch_fetch(stocks_file):
    """批量落盘：从文件读取股票列表。

    文件格式（每行一个）：ts_code_6 名称
    示例：
        600938 中国海油
        600519 贵州茅台
        000001 平安银行
    """
    with open(stocks_file, "r", encoding="utf-8") as f:
        lines = [l.strip() for l in f if l.strip() and not l.startswith("#")]

    total = len(lines)
    print(f"批量落盘: {total} 只股票")
    for i, line in enumerate(lines, 1):
        parts = line.split()
        if len(parts) < 2:
            print(f"  ⚠️  跳过格式错误的行: {line}")
            continue
        ts_code_6, name = parts[0], parts[1]
        print(f"\n[{i}/{total}] {name} ({ts_code_6})")
        try:
            fetch_stock(ts_code_6, name)
        except Exception as e:
            print(f"  ❌ 失败: {e}")


def list_stocks():
    """列出 local/ 下已落盘的股票。"""
    if not os.path.exists(_LOCAL_DIR):
        print("local/ 目录不存在")
        return

    stocks = []
    for d in os.listdir(_LOCAL_DIR):
        full = os.path.join(_LOCAL_DIR, d)
        if os.path.isdir(full) and os.path.exists(os.path.join(full, "manifest.json")):
            manifest = _load_manifest(full)
            stocks.append({
                "dir": d,
                "ts_code": manifest.get("ts_code", "?"),
                "name": manifest.get("name", "?"),
                "last_fetch": manifest.get("last_fetch", "?"),
                "periods": len(manifest.get("periods", {})),
            })

    if not stocks:
        print("未找到已落盘的股票数据")
        return

    sep = "=" * 70
    print(sep)
    print(f"已落盘股票: {len(stocks)} 只")
    print(sep)
    print(f"  {'目录':<25}{'代码':<12}{'名称':<10}{'期间数':>6}  {'上次落盘'}")
    print(f"  {'─' * 25}{'─' * 12}{'─' * 10}{'─' * 6}  {'─' * 20}")
    for s in stocks:
        print(f"  {s['dir']:<25}{s['ts_code']:<12}{s['name']:<10}{s['periods']:>6}  {s['last_fetch'][:19]}")
    print(sep)


def load_financial_data(ts_code_6, name, period):
    """从落盘目录读取财务数据（供报告生成 Skill 调用）。

    Args:
        ts_code_6: 6位代码，如 "600938"
        name: 公司名称，如 "中国海油"
        period: 报告期，如 "20241231"

    Returns:
        dict: {api_name: [record, ...], ...}，未找到的接口不包含在结果中
    """
    base = os.path.join(_LOCAL_DIR, f"{name}_{ts_code_6}", "raw", "financial")
    data = {}
    for api in FINANCIAL_APIS:
        filepath = os.path.join(base, f"{api}_{period}.json")
        if os.path.exists(filepath):
            with open(filepath, "r", encoding="utf-8") as f:
                data[api] = json.load(f)
    return data


def load_stock_meta(ts_code_6, name):
    """从落盘目录读取股票元数据。"""
    path = os.path.join(_LOCAL_DIR, f"{name}_{ts_code_6}", "raw", "meta", "stock_basic.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def load_announcements(ts_code_6, name, limit=20):
    """从落盘目录读取最近 N 条公告（供报告生成 Skill 调用）。

    Args:
        ts_code_6: 6位代码，如 "600938"
        name: 公司名称，如 "中国海油"
        limit: 返回条数（默认 20）

    Returns:
        list[dict]: 公告列表，按日期降序
    """
    path = os.path.join(_LOCAL_DIR, f"{name}_{ts_code_6}", "raw", "announcements.json")
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        anns = json.load(f)
    return anns[:limit]


def main():
    parser = argparse.ArgumentParser(
        description="A股基本面数据批量落盘工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command")

    p_fetch = sub.add_parser("fetch", help="单股落盘")
    p_fetch.add_argument("ts_code", help="6位股票代码，如 600938")
    p_fetch.add_argument("name", help="公司名称，如 中国海油")
    p_fetch.add_argument("--years", type=int, default=10, help="回溯年数（默认10年，含季报/中报/年报 + 当年已披露期间）")
    p_fetch.add_argument("--force", action="store_true", help="强制重新拉取（忽略已存在）")

    p_update = sub.add_parser("update", help="增量更新（只拉缺失期间）")
    p_update.add_argument("ts_code", help="6位股票代码")
    p_update.add_argument("name", help="公司名称")

    p_check = sub.add_parser("check", help="检查落盘完整性")
    p_check.add_argument("ts_code", help="6位股票代码")
    p_check.add_argument("name", help="公司名称")

    p_batch = sub.add_parser("batch", help="批量落盘")
    p_batch.add_argument("file", help="股票列表文件（每行：代码 名称）")

    sub.add_parser("list", help="列出已落盘的股票")

    p_anns = sub.add_parser("anns", help="单独拉取公告（东方财富 API）")
    p_anns.add_argument("ts_code", help="6位股票代码")
    p_anns.add_argument("name", help="公司名称")
    p_anns.add_argument("--limit", type=int, default=30, help="获取条数（默认30，最大50）")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    try:
        if args.command == "fetch":
            fetch_stock(args.ts_code, args.name, years=args.years, skip_existing=not args.force)
        elif args.command == "update":
            update_stock(args.ts_code, args.name)
        elif args.command == "check":
            check_stock(args.ts_code, args.name)
        elif args.command == "anns":
            fetch_announcements(args.ts_code, args.name, limit=args.limit)
        elif args.command == "batch":
            batch_fetch(args.file)
        elif args.command == "list":
            list_stocks()
    except ConnectionError as e:
        print(f"❌ {e}")
        sys.exit(2)


if __name__ == "__main__":
    main()
