#!/usr/bin/env python3
"""基金数据批量落盘工具（fund = 基金，非 fundamentals）。

从 Tushare（ttshare 代理优先 → cheapyun → 官方）获取基金数据，保存到 local/ 下。
与 fundamental_fetcher.py（个股基本面落盘）同风格，报告生成时直接从 local/ 读取。

用法：
    python tools/fund_data_fetcher.py fetch 510300              # 单只基金落盘
    python tools/fund_data_fetcher.py fetch 510300 --years 3    # 指定年数
    python tools/fund_data_fetcher.py update 510300             # 增量更新（只拉缺失期间）
    python tools/fund_data_fetcher.py check 510300              # 检查落盘完整性
    python tools/fund_data_fetcher.py list                      # 列出已落盘的基金
    python tools/fund_data_fetcher.py batch funds.txt           # 批量落盘

目录结构：
    local/fund_{code}/
    ├── raw/
    │   ├── meta/
    │   │   └── fund_basic.json         # 基金基本信息
    │   ├── nav/
    │   │   └── fund_nav_latest.json    # 近期净值（最近 N 天）
    │   ├── daily/
    │   │   └── fund_daily_latest.json  # 场内行情（近 40 天）
    │   ├── portfolio/
    │   │   └── fund_holdings_{period}.json  # 季报持仓（按报告期）
    │   ├── shares/
    │   │   └── fund_shares.json        # 份额与规模变动
    │   ├── manager/
    │   │   └── fund_manager.json       # 基金经理信息
    │   └── holder/
    │       └── fund_holder.json        # 持有人结构
    ├── manifest.json                   # 落盘记录
    └── log/                            # 日志
        └── fetch_YYYYMMDD.log

依赖：tushare/ttshare（含 pandas）。其余仅 stdlib。
"""

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime, date, timedelta

# Windows 控制台中文输出
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

# 项目根目录
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_LOCAL_DIR = os.path.join(_ROOT, "local")

# 全局限流器
_last_request_time = 0.0
REQUEST_INTERVAL = 0.75  # 秒

# 需要按报告期分文件的接口
PERIOD_APIS = ["fund_portfolio"]

# 全量/最新快照接口
SNAPSHOT_APIS = ["fund_basic", "fund_nav", "fund_share", "fund_manager", "fund_holder"]

# 近期净值拉取天数
NAV_LOOKBACK_DAYS = 180  # 近 6 个月


def _rate_limit():
    """全局限流：确保每次请求间隔 >= 0.75s。"""
    global _last_request_time
    elapsed = time.time() - _last_request_time
    if elapsed < REQUEST_INTERVAL:
        time.sleep(REQUEST_INTERVAL - elapsed)
    _last_request_time = time.time()


def _get_client():
    """获取 Tushare 多源客户端（ttshare → cheapyun → 官方）。

    复用 tushare_data.py 的多源模式，但独立实现以避免循环依赖。
    """
    sources = []

    # 1. ttshare 代理
    try:
        import ttshare as ts
        tok = _read_token("TTSHARE_TOKEN", "ttshare_token.txt")
        if tok:
            sources.append(("ttshare代理", ts, tok, None))
    except ImportError:
        pass

    # 2. cheapyun 代理
    try:
        import tushare as ts
        tok = _read_token("CHEAPYUN_TOKEN", "tushare_token_cheapyun.txt")
        if tok:
            sources.append(("cheapyun代理", ts, tok, "http://cheap-host1.cheapyun.com:42461"))
    except ImportError:
        pass

    # 3. tushare 官方
    try:
        import tushare as ts
        tok = _read_token("TUSHARE_TOKEN", "tushare_token.txt")
        if tok:
            sources.append(("tushare官方", ts, tok, None))
    except ImportError:
        pass

    if not sources:
        raise ConnectionError(
            "未安装 ttshare/tushare 或未配置 token。"
            "请用 uv 安装依赖：uv add ttshare tushare（或 uv sync）"
        )

    return sources


def _read_token(env_var, filename):
    """读取 token：环境变量优先，其次 local/ 文件。"""
    t = os.environ.get(env_var, "").strip()
    if t:
        return t
    try:
        with open(os.path.join(_LOCAL_DIR, filename), encoding="utf-8") as f:
            return f.read().strip() or None
    except OSError:
        return None


def _adapt_params_for_cheapyun(api, kwargs):
    """cheapyun 代理参数适配。

    cheapyun 基金接口的特殊行为：
    - fund_basic: 使用 .OF 后缀（与官方一致），但全量查询时返回所有基金
    - fund_nav/portfolio/share/manager/daily: 使用 .SH/.SZ 后缀（与官方不同）
    - fund_holder: 返回 500 错误（不支持）
    """
    adapted = dict(kwargs)
    if api == "fund_basic":
        # cheapyun fund_basic 不支持 ts_code 过滤，全量查询后本地匹配
        adapted.pop("ts_code", None)
    elif api == "fund_holder":
        # fund_holder cheapyun 返回 500，直接跳过
        pass
    elif "ts_code" in adapted:
        # 其他 fund 接口：.OF → .SH/.SZ
        code = adapted["ts_code"]
        if code.upper().endswith(".OF"):
            base = code[:-3]
            if base.startswith("5"):
                adapted["ts_code"] = f"{base}.SH"
            elif base.startswith("1"):
                adapted["ts_code"] = f"{base}.SZ"
    return adapted


def _call_api(sources, api, **kwargs):
    """带多源重试和限流的接口调用。返回 (来源标签, DataFrame 或 None)。"""
    for label, mod, tok, base_url in sources:
        _rate_limit()
        try:
            if tok:
                mod.set_token(tok)
            pro = mod.pro_api()
            if base_url:
                pro._DataApi__http_url = base_url
            # cheapyun 代理参数适配
            call_kwargs = _adapt_params_for_cheapyun(api, kwargs) if "cheapyun" in label else kwargs
            df = getattr(pro, api)(**call_kwargs)
            if df is not None and len(df):
                # 统一列名为大写（cheapyun 返回小写列名，官方返回大写）
                df.columns = [c.upper() for c in df.columns]
                return label, df
            logging.info(f"    {api} via {label} → 空数据（已尝试，该源无权限或无数据）")
        except Exception as e:
            logging.warning(f"  {api} via {label} 失败: {e}")
    return sources[0][0], None


def _resolve_fund_code(code):
    """解析基金代码 → (基础6位, fund_ts='xxx.OF', name_hint)。"""
    c = code.strip().upper()
    base = c.split(".")[0]
    return base, f"{base}.OF"


def _ensure_dir(path):
    """确保目录存在。"""
    os.makedirs(path, exist_ok=True)


def _save_json(records, filepath):
    """保存列表到 JSON 文件。"""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2, default=str)


def _load_manifest(fund_dir):
    """加载 manifest.json。"""
    path = os.path.join(fund_dir, "manifest.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"periods": {}, "metadata": {}, "last_fetch": None}


def _save_manifest(fund_dir, manifest):
    """保存 manifest.json。"""
    path = os.path.join(fund_dir, "manifest.json")
    _save_json(manifest, path)


def _setup_logging(fund_dir):
    """配置日志：同时输出到控制台和文件。"""
    log_dir = os.path.join(fund_dir, "log")
    _ensure_dir(log_dir)
    log_file = os.path.join(log_dir, f"fetch_{datetime.now().strftime('%Y%m%d')}.log")

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(logging.INFO)

    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setLevel(logging.INFO)
    fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    root_logger.addHandler(fh)

    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(logging.Formatter("  %(message)s"))
    root_logger.addHandler(ch)

    return log_file


def _df_to_records(df):
    """DataFrame → list[dict]，统一处理 NaN。"""
    return df.to_dict(orient="records")


def _get_annual_periods(years=3):
    """生成近 N 年的报告期列表（每年 1231 年报 + 0930 三季报 + 0630 中报 + 0331 一季报）
    并追加当年已结束的报告期（如 2026Q1、2026 中报，不占 N 年名额）。"""
    current_year = date.today().year
    periods = []
    for y in range(current_year - 1, current_year - years - 1, -1):
        periods.append(f"{y}1231")  # 年报
        periods.append(f"{y}0930")  # 三季报
        periods.append(f"{y}0630")  # 中报
        periods.append(f"{y}0331")  # 一季报
    today = date.today()
    for mm, dd in (("03", "31"), ("06", "30"), ("09", "30"), ("12", "31")):
        if date(current_year, int(mm), int(dd)) <= today:
            periods.append(f"{current_year}{mm}{dd}")
    return periods


# ---------------------------------------------------------------------------
# 核心落盘函数
# ---------------------------------------------------------------------------

def fetch_fund(code, years=3, skip_existing=True):
    """落盘单只基金的数据。

    Args:
        code: 基金代码（6 位数字），如 "510300"
        years: 回溯年数（用于 portfolio 按报告期分文件）
        skip_existing: 是否跳过已落盘的文件

    Returns:
        dict: 各接口的落盘统计
    """
    sources = _get_client()
    base6, of_ts = _resolve_fund_code(code)
    fund_dir = os.path.join(_LOCAL_DIR, f"fund_{base6}")

    _ensure_dir(os.path.join(fund_dir, "raw", "meta"))
    _ensure_dir(os.path.join(fund_dir, "raw", "nav"))
    _ensure_dir(os.path.join(fund_dir, "raw", "daily"))
    _ensure_dir(os.path.join(fund_dir, "raw", "portfolio"))
    _ensure_dir(os.path.join(fund_dir, "raw", "shares"))
    _ensure_dir(os.path.join(fund_dir, "raw", "manager"))
    _ensure_dir(os.path.join(fund_dir, "raw", "holder"))

    log_file = _setup_logging(fund_dir)
    manifest = _load_manifest(fund_dir)

    # 获取基金名称（用于日志）
    # cheapyun 不支持 ts_code 过滤，需全量查询后本地匹配
    fund_name = of_ts
    label, df = _call_api(sources, "fund_basic", ts_code=of_ts, fields="ts_code,name")
    if df is not None and len(df):
        if "TS_CODE" in df.columns:
            match = df[df["TS_CODE"].astype(str).str.upper() == of_ts.upper()]
            if len(match):
                fund_name = str(match.iloc[0].get("NAME", of_ts))
        elif len(df) == 1:
            fund_name = str(df.iloc[0].get("NAME", of_ts))

    sep = "=" * 60
    logging.info(sep)
    logging.info(f"开始落盘: {fund_name} ({of_ts})  数据源: 多源(ttshare/cheapyun/官方)")
    logging.info(f"回溯年数: {years}  跳过已存在: {skip_existing}")
    logging.info(f"日志文件: {log_file}")
    logging.info(sep)

    stats = {"success": 0, "empty": 0, "failed": 0, "skipped": 0}

    # 1. 基金基本信息（fund_basic）
    # cheapyun 不支持 ts_code 过滤，返回全量 → 需本地过滤
    logging.info("\n[1/7] 基金基本信息")
    filepath = os.path.join(fund_dir, "raw", "meta", "fund_basic.json")
    if not (skip_existing and os.path.exists(filepath)):
        label, df = _call_api(sources, "fund_basic", ts_code=of_ts)
        if df is not None and len(df):
            # 过滤：cheapyun 返回全量，需按 ts_code 筛选目标基金
            if len(df) > 1 and "TS_CODE" in df.columns:
                df = df[df["TS_CODE"].astype(str).str.upper() == of_ts.upper()]
            if len(df):
                _save_json(_df_to_records(df), filepath)
                manifest["metadata"]["fund_basic"] = True
                logging.info(f"  ✅ fund_basic → {len(df)} 条")
                stats["success"] += 1
            else:
                logging.warning(f"  ⚠️  fund_basic → 全量有数据但未匹配到 {of_ts}")
                stats["empty"] += 1
        else:
            logging.warning(f"  ⚠️  fund_basic → 无数据")
            stats["empty"] += 1
    else:
        logging.info(f"  ⏭️  fund_basic → 已存在，跳过")
        stats["skipped"] += 1

    # 2. 净值与业绩（fund_nav）— 近 N 天
    logging.info("\n[2/7] 净值与业绩")
    nav_dir = os.path.join(fund_dir, "raw", "nav")
    nav_path = os.path.join(nav_dir, "fund_nav_latest.json")
    if not (skip_existing and os.path.exists(nav_path)):
        start_str = (date.today() - timedelta(days=NAV_LOOKBACK_DAYS)).strftime("%Y%m%d")
        label, df = _call_api(sources, "fund_nav", ts_code=of_ts, start_date=start_str)
        if df is not None and len(df):
            # 按日期排序
            df = df.sort_values("NAV_DATE", ascending=True)
            _save_json(_df_to_records(df), nav_path)
            manifest["metadata"]["fund_nav"] = {
                "last_fetch": datetime.now().strftime("%Y-%m-%d"),
                "count": len(df),
                "start": str(df.iloc[0].get("NAV_DATE", "")),
                "end": str(df.iloc[-1].get("NAV_DATE", "")),
            }
            logging.info(f"  ✅ fund_nav → {len(df)} 条（{df.iloc[0].get('NAV_DATE', '?')} ~ {df.iloc[-1].get('NAV_DATE', '?')}）")
            stats["success"] += 1
        else:
            logging.warning(f"  ⚠️  fund_nav → 无数据")
            stats["empty"] += 1
    else:
        logging.info(f"  ⏭️  fund_nav → 已存在，跳过")
        stats["skipped"] += 1

    # 3. 场内行情与流动性（fund_daily）— 近 40 天
    logging.info("\n[3/7] 场内行情与流动性")
    daily_dir = os.path.join(fund_dir, "raw", "daily")
    daily_path = os.path.join(daily_dir, "fund_daily_latest.json")
    _ensure_dir(daily_dir)
    if not (skip_existing and os.path.exists(daily_path)):
        start_str = (date.today() - timedelta(days=40)).strftime("%Y%m%d")
        label, df = _call_api(sources, "fund_daily", ts_code=of_ts, start_date=start_str)
        if df is not None and len(df):
            df = df.sort_values("TRADE_DATE", ascending=True)
            _save_json(_df_to_records(df), daily_path)
            manifest["metadata"]["fund_daily"] = {
                "last_fetch": datetime.now().strftime("%Y-%m-%d"),
                "count": len(df),
            }
            logging.info(f"  ✅ fund_daily → {len(df)} 条（{df.iloc[0].get('TRADE_DATE', '?')} ~ {df.iloc[-1].get('TRADE_DATE', '?')}）")
            stats["success"] += 1
        else:
            logging.warning(f"  ⚠️  fund_daily → 无数据（可能为场外基金，无场内行情）")
            stats["empty"] += 1
    else:
        logging.info(f"  ⏭️  fund_daily → 已存在，跳过")
        stats["skipped"] += 1

    # 4. 季报持仓（fund_portfolio）— 按报告期分文件
    logging.info("\n[4/7] 季报持仓")
    portfolio_dir = os.path.join(fund_dir, "raw", "portfolio")
    label, df = _call_api(sources, "fund_portfolio", ts_code=of_ts)
    if df is not None and len(df):
        # 按报告期分组保存
        if "END_DATE" in df.columns:
            periods_in_data = df["END_DATE"].astype(str).str[:8].unique()
            for period in sorted(periods_in_data):
                filepath = os.path.join(portfolio_dir, f"fund_holdings_{period}.json")
                if skip_existing and os.path.exists(filepath):
                    stats["skipped"] += 1
                    continue
                period_df = df[df["END_DATE"].astype(str).str.startswith(period)]
                _save_json(_df_to_records(period_df), filepath)
                manifest["periods"].setdefault(period, {})["fund_portfolio"] = True
                logging.info(f"  ✅ fund_portfolio {period} → {len(period_df)} 条")
                stats["success"] += 1
        else:
            # 无 END_DATE 列，整体保存
            filepath = os.path.join(portfolio_dir, "fund_holdings_latest.json")
            if not (skip_existing and os.path.exists(filepath)):
                _save_json(_df_to_records(df), filepath)
                manifest["metadata"]["fund_portfolio"] = True
                logging.info(f"  ✅ fund_portfolio → {len(df)} 条")
                stats["success"] += 1
            else:
                stats["skipped"] += 1
    else:
        logging.warning(f"  ⚠️  fund_portfolio → 无数据")
        stats["empty"] += 1

    # 5. 份额与规模变动（fund_share）
    logging.info("\n[5/7] 份额与规模变动")
    filepath = os.path.join(fund_dir, "raw", "shares", "fund_shares.json")
    if not (skip_existing and os.path.exists(filepath)):
        label, df = _call_api(sources, "fund_share", ts_code=of_ts)
        if df is not None and len(df):
            df = df.sort_values("TRADE_DATE", ascending=True)
            _save_json(_df_to_records(df), filepath)
            manifest["metadata"]["fund_share"] = {
                "last_fetch": datetime.now().strftime("%Y-%m-%d"),
                "count": len(df),
            }
            logging.info(f"  ✅ fund_share → {len(df)} 条")
            stats["success"] += 1
        else:
            logging.warning(f"  ⚠️  fund_share → 无数据")
            stats["empty"] += 1
    else:
        logging.info(f"  ⏭️  fund_share → 已存在，跳过")
        stats["skipped"] += 1

    # 6. 基金经理（fund_manager）
    logging.info("\n[6/7] 基金经理")
    filepath = os.path.join(fund_dir, "raw", "manager", "fund_manager.json")
    if not (skip_existing and os.path.exists(filepath)):
        label, df = _call_api(sources, "fund_manager", ts_code=of_ts)
        if df is not None and len(df):
            _save_json(_df_to_records(df), filepath)
            manifest["metadata"]["fund_manager"] = True
            logging.info(f"  ✅ fund_manager → {len(df)} 条")
            stats["success"] += 1
        else:
            logging.warning(f"  ⚠️  fund_manager → 无数据")
            stats["empty"] += 1
    else:
        logging.info(f"  ⏭️  fund_manager → 已存在，跳过")
        stats["skipped"] += 1

    # 7. 持有人结构（fund_holder）
    logging.info("\n[7/7] 持有人结构")
    filepath = os.path.join(fund_dir, "raw", "holder", "fund_holder.json")
    if not (skip_existing and os.path.exists(filepath)):
        label, df = _call_api(sources, "fund_holder", ts_code=of_ts)
        if df is not None and len(df):
            df = df.sort_values("END_DATE", ascending=True)
            _save_json(_df_to_records(df), filepath)
            manifest["metadata"]["fund_holder"] = {
                "last_fetch": datetime.now().strftime("%Y-%m-%d"),
                "count": len(df),
            }
            logging.info(f"  ✅ fund_holder → {len(df)} 条")
            stats["success"] += 1
        else:
            logging.warning(f"  ⚠️  fund_holder → 无数据")
            stats["empty"] += 1
    else:
        logging.info(f"  ⏭️  fund_holder → 已存在，跳过")
        stats["skipped"] += 1

    # 更新 manifest
    manifest["last_fetch"] = datetime.now().isoformat()
    manifest["ts_code"] = of_ts
    manifest["name"] = fund_name
    manifest["code"] = base6
    _save_manifest(fund_dir, manifest)

    logging.info(f"\n{sep}")
    logging.info(f"落盘完成: {fund_name} ({of_ts})")
    logging.info(f"  成功: {stats['success']}  空数据: {stats['empty']}  失败: {stats['failed']}  跳过: {stats['skipped']}")
    logging.info(f"  数据目录: {fund_dir}/raw/")
    logging.info(f"  Manifest: {fund_dir}/manifest.json")
    logging.info(sep)

    return stats


def update_fund(code):
    """增量更新：跳过已存在的文件。"""
    fund_dir = os.path.join(_LOCAL_DIR, f"fund_{code}")
    manifest = _load_manifest(fund_dir)
    if not manifest.get("last_fetch"):
        logging.info("无 manifest 记录，执行完整落盘")
        return fetch_fund(code)

    logging.info(f"上次落盘: {manifest['last_fetch']}")
    return fetch_fund(code, skip_existing=True)


def check_fund(code):
    """检查落盘完整性。"""
    fund_dir = os.path.join(_LOCAL_DIR, f"fund_{code}")
    manifest = _load_manifest(fund_dir)

    sep = "=" * 60
    print(sep)
    print(f"落盘完整性检查: fund_{code}")
    print(sep)

    if not manifest.get("last_fetch"):
        print("❌ 未找到落盘记录，请先执行 fetch")
        return

    print(f"  上次落盘: {manifest['last_fetch']}")
    print(f"  基金名称: {manifest.get('name', '?')}")
    print()

    # 检查各模块
    checks = [
        ("meta/fund_basic.json", "基金基本信息", "fund_basic"),
        ("nav/fund_nav_latest.json", "净值与业绩", "fund_nav"),
        ("daily/fund_daily_latest.json", "场内行情", "fund_daily"),
        ("shares/fund_shares.json", "份额与规模", "fund_share"),
        ("manager/fund_manager.json", "基金经理", "fund_manager"),
        ("holder/fund_holder.json", "持有人结构", "fund_holder"),
    ]

    issues = []
    for rel_path, label, api_key in checks:
        path = os.path.join(fund_dir, "raw", rel_path)
        if os.path.exists(path):
            size = os.path.getsize(path)
            print(f"  ✅ {label:12s} → 已落盘 ({size:,} bytes)")
        else:
            print(f"  ❌ {label:12s} → 缺失")
            issues.append(api_key)

    # 检查持仓（按报告期）
    portfolio_dir = os.path.join(fund_dir, "raw", "portfolio")
    if os.path.exists(portfolio_dir):
        holdings = [f for f in os.listdir(portfolio_dir) if f.endswith(".json")]
        if holdings:
            print(f"  ✅ 季报持仓     → {len(holdings)} 个报告期")
        else:
            print(f"  ❌ 季报持仓     → 无报告期文件")
            issues.append("fund_portfolio")
    else:
        print(f"  ❌ 季报持仓     → 缺失目录")
        issues.append("fund_portfolio")

    print()
    if issues:
        print(f"⚠️  缺失 {len(issues)} 项: {', '.join(issues)}")
        print(f"  建议执行: python tools/fund_data_fetcher.py update {code}")
    else:
        print("✅ 数据完整")
    print(sep)


def list_funds():
    """列出 local/ 下已落盘的基金。"""
    if not os.path.exists(_LOCAL_DIR):
        print("local/ 目录不存在")
        return

    funds = []
    for d in os.listdir(_LOCAL_DIR):
        if not d.startswith("fund_"):
            continue
        full = os.path.join(_LOCAL_DIR, d)
        if not os.path.isdir(full):
            continue
        manifest_path = os.path.join(full, "manifest.json")
        if not os.path.exists(manifest_path):
            continue
        manifest = _load_manifest(full)
        funds.append({
            "dir": d,
            "code": manifest.get("code", d.replace("fund_", "")),
            "ts_code": manifest.get("ts_code", "?"),
            "name": manifest.get("name", "?"),
            "last_fetch": manifest.get("last_fetch", "?"),
            "periods": len(manifest.get("periods", {})),
        })

    if not funds:
        print("未找到已落盘的基金数据")
        return

    sep = "=" * 70
    print(sep)
    print(f"已落盘基金: {len(funds)} 只")
    print(sep)
    print(f"  {'代码':<8}{'名称':<20}{'期间数':>6}  {'上次落盘'}")
    print(f"  {'─' * 8}{'─' * 20}{'─' * 6}  {'─' * 20}")
    for f in funds:
        print(f"  {f['code']:<8}{f['name'][:18]:<20}{f['periods']:>6}  {f['last_fetch'][:19]}")
    print(sep)


def batch_fetch(funds_file):
    """批量落盘：从文件读取基金列表。

    文件格式（每行一个）：代码 [名称]
    示例：
        510300 沪深300ETF
        161725 招商中证白酒
    """
    with open(funds_file, "r", encoding="utf-8") as f:
        lines = [l.strip() for l in f if l.strip() and not l.startswith("#")]

    total = len(lines)
    print(f"批量落盘: {total} 只基金")
    for i, line in enumerate(lines, 1):
        parts = line.split()
        if not parts:
            continue
        code = parts[0]
        name = parts[1] if len(parts) > 1 else code
        print(f"\n[{i}/{total}] {name} ({code})")
        try:
            fetch_fund(code)
        except Exception as e:
            print(f"  ❌ 失败: {e}")


# ---------------------------------------------------------------------------
# 数据加载函数（供报告生成 Skill 调用）
# ---------------------------------------------------------------------------

def load_fund_basic(code):
    """从落盘目录读取基金基本信息。"""
    path = os.path.join(_LOCAL_DIR, f"fund_{code}", "raw", "meta", "fund_basic.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def load_fund_nav(code, limit=90):
    """从落盘目录读取近期净值。"""
    path = os.path.join(_LOCAL_DIR, f"fund_{code}", "raw", "nav", "fund_nav_latest.json")
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data[-limit:] if limit else data


def load_fund_daily(code, limit=40):
    """从落盘目录读取场内行情。"""
    path = os.path.join(_LOCAL_DIR, f"fund_{code}", "raw", "daily", "fund_daily_latest.json")
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data[-limit:] if limit else data


def load_fund_holdings(code, period=None):
    """从落盘目录读取季报持仓。

    Args:
        code: 基金代码（6 位）
        period: 报告期 YYYYMMDD，None 则返回最新一期

    Returns:
        list[dict]: 持仓记录
    """
    portfolio_dir = os.path.join(_LOCAL_DIR, f"fund_{code}", "raw", "portfolio")
    if not os.path.exists(portfolio_dir):
        return []

    files = sorted([f for f in os.listdir(portfolio_dir) if f.endswith(".json")], reverse=True)
    if not files:
        return []

    if period:
        # 查找匹配的报告期文件
        for f in files:
            if period in f:
                with open(os.path.join(portfolio_dir, f), "r", encoding="utf-8") as fh:
                    return json.load(fh)
        return []

    # 返回最新一期
    with open(os.path.join(portfolio_dir, files[0]), "r", encoding="utf-8") as f:
        return json.load(f)


def load_fund_shares(code):
    """从落盘目录读取份额与规模变动。"""
    path = os.path.join(_LOCAL_DIR, f"fund_{code}", "raw", "shares", "fund_shares.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def load_fund_manager(code):
    """从落盘目录读取基金经理信息。"""
    path = os.path.join(_LOCAL_DIR, f"fund_{code}", "raw", "manager", "fund_manager.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def load_fund_holder(code):
    """从落盘目录读取持有人结构。"""
    path = os.path.join(_LOCAL_DIR, f"fund_{code}", "raw", "holder", "fund_holder.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


# ---------------------------------------------------------------------------
# CLI 入口
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="基金数据批量落盘工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command")

    p_fetch = sub.add_parser("fetch", help="单只基金落盘")
    p_fetch.add_argument("code", help="6 位基金代码，如 510300")
    p_fetch.add_argument("--years", type=int, default=3, help="回溯年数（默认 3 年）")
    p_fetch.add_argument("--force", action="store_true", help="强制重新拉取（忽略已存在）")

    p_update = sub.add_parser("update", help="增量更新（只拉缺失文件）")
    p_update.add_argument("code", help="6 位基金代码")

    p_check = sub.add_parser("check", help="检查落盘完整性")
    p_check.add_argument("code", help="6 位基金代码")

    p_batch = sub.add_parser("batch", help="批量落盘")
    p_batch.add_argument("file", help="基金列表文件（每行：代码 [名称]）")

    sub.add_parser("list", help="列出已落盘的基金")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    try:
        if args.command == "fetch":
            fetch_fund(args.code, years=args.years, skip_existing=not args.force)
        elif args.command == "update":
            update_fund(args.code)
        elif args.command == "check":
            check_fund(args.code)
        elif args.command == "batch":
            batch_fetch(args.file)
        elif args.command == "list":
            list_funds()
    except ConnectionError as e:
        print(f"❌ {e}")
        sys.exit(2)


if __name__ == "__main__":
    main()
