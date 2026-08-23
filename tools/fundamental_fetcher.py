#!/usr/bin/env python3
"""A股基本面数据批量落盘工具。

从 Tushare（cheapyun 代理优先）获取 A 股基本面数据，按规范目录结构保存到 local/ 下。
报告生成时直接从 local/ 读取落盘数据，不再实时调用接口。

用法：
    python tools/fundamental_fetcher.py fetch 600938 中国海油        # 单股落盘（含公告）
    python tools/fundamental_fetcher.py fetch 600938 中国海油 --years 10  # 指定年数
    python tools/fundamental_fetcher.py update 600938 中国海油       # 增量更新（只拉缺失期间）
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

    优先级：cheapyun（tushare_token_tmp.txt）→ 官方（tushare_token.txt）
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
    cheapyun_tok = _read("CHEAPYUN_TOKEN", "tushare_token_tmp.txt")
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


def _get_annual_periods(years=5):
    """生成近 N 年的报告期列表（年报 1231 + 中报 0630）。"""
    current_year = date.today().year
    periods = []
    for y in range(current_year - 1, current_year - years - 1, -1):
        periods.append(f"{y}1231")
        periods.append(f"{y}0630")
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


def fetch_stock(ts_code_6, name, years=5, skip_existing=True):
    """落盘单只 A 股的基本面数据。

    Args:
        ts_code_6: 6 位纯数字股票代码，如 "600938"
        name: 公司名称，如 "中国海油"
        years: 回溯年数
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
    logging.info("\n[2/4] 财务主表")
    fin_dir = os.path.join(stock_dir, "raw", "financial")
    periods = _get_annual_periods(years)
    for period in periods:
        for api in FINANCIAL_APIS:
            filepath = os.path.join(fin_dir, f"{api}_{period}.json")
            if skip_existing and os.path.exists(filepath):
                stats["skipped"] += 1
                continue

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
    _save_manifest(stock_dir, manifest)

    logging.info(f"\n{'=' * 60}")
    logging.info(f"落盘完成: {name} ({ts_code})")
    logging.info(f"  成功: {stats['success']}  空数据: {stats['empty']}  失败: {stats['failed']}  跳过: {stats['skipped']}")
    logging.info(f"  数据目录: {stock_dir}/raw/")
    logging.info(f"  Manifest: {stock_dir}/manifest.json")
    logging.info(f"{'=' * 60}")

    return stats


def update_stock(ts_code_6, name):
    """增量更新：只拉 manifest 中缺失的期间。"""
    stock_dir = os.path.join(_LOCAL_DIR, f"{name}_{ts_code_6}")
    manifest = _load_manifest(stock_dir)
    if not manifest.get("last_fetch"):
        logging.info("无 manifest 记录，执行完整落盘")
        return fetch_stock(ts_code_6, name)

    logging.info(f"上次落盘: {manifest['last_fetch']}")
    logging.info(f"已有期间: {len(manifest.get('periods', {}))} 个")
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
    p_fetch.add_argument("--years", type=int, default=5, help="回溯年数（默认5年）")
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
