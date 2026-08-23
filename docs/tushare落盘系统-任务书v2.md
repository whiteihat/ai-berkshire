# Tushare 基本面数据落盘系统 — 任务书 v2（批判性分析+润色版）

---

## 一、原文批判性分析

### 1. 与现有代码的冲突（最严重问题）

| 问题 | 说明 |
|------|------|
| **Token 管理重复** | 现有 `tools/tushare_data.py` 已实现完整的 token 读取链（环境变量 → `local/tushare_token.txt` / `local/ttshare_token.txt`），原文要求读 `local/tushare_token_tmp.txt`，文件名不一致，且 `_read_token()` 函数已存在可直接复用 |
| **代理初始化重复** | 现有 `_Client` 类已封装 ttshare 代理优先 + 官方 API 兜底 + 失败自动切换，原文要求"自行初始化 pro + 手动设置 `__http_url`"，等于废弃现有架构重写 |
| **限流机制已有** | 现有代码在每次 `client.call()` 内部已有 try/except + 重试逻辑，原文要求"每次请求间隔至少休眠 0.75 秒"但没说清楚是全局还是单次 |
| **报告生成路径冲突** | 现有项目规范明确：单公司报告输出到 `reports/01-单公司分析/{公司名}/`，原文的 `processed/combined_financial.parquet` 与现有 `tools/financial_rigor.py` 精确计算路径不一致 |

### 2. 过度设计

| 问题 | 说明 |
|------|------|
| **Parquet 格式** | 引入 pyarrow/fastparquet 依赖，但项目现有数据全用 JSON/TXT（`local/fund*/` 下全是 .html/.txt/.json），为落盘引入新格式增加环境复杂度 |
| **field_mapping.json 全局映射** | Tushare 字段名已经很规范（`total_operate_income`、`n_income_attr_p`），映射表增加了维护成本，实际用不到几次 |
| **processed/ 宽表层** | 原始数据落盘后，报告生成时 Claude 直接读 raw/ 的 parquet 就够了，额外的合并步骤增加了出错可能 |
| **manifest.json 增量管理** | 对于"只增不改"的落盘，文件名自带报告期就是天然去重，不需要额外的清单文件 |

### 3. 缺失的关键设计

| 缺失 | 说明 |
|------|------|
| **没有明确"哪些接口要落盘"** | Tushare 有 200+ 接口，原文只提了 income/balance/cashflow，没说 daily_basic、fina_indicator、dividend、forecast、express 等 |
| **没有与现有 tools/ 的集成方案** | 现有 `tushare_data.py` 的 `cmd_financials()` 已经在调用 income + fina_indicator，落盘系统应该复用而不是另起炉灶 |
| **tmp_*.py 的遗留处理** | 现有 `tmp_fetch_cnooc*.py` 用的是东方财富 API 而非 Tushare，落盘系统是否要统一数据源？ |
| **港股/美股落盘策略** | 原文只提了 A 股落盘，但项目覆盖 A/港/美三市场，港股/美股的 Tushare 接口权限不同，需要分别设计 |

### 4. 实施顺序不合理

原文建议"先写基础工具类 → 定义映射表 → 写落盘脚本 → 检查脚本 → 清洗脚本 → 报告生成"，共 6 步。但：

- 步骤 1（基础工具类）= 重写 `tools/tushare_data.py` 的 `_Client`，浪费已有代码
- 步骤 2（映射表）= 过早优化，实际用时再定义
- 步骤 5（清洗/合并）= 与步骤 3（落盘）割裂，应该边落盘边验证

---

## 二、润色后的任务书

### 项目目标

在 **现有 `tools/tushare_data.py` 架构基础上**，新增批量基本面数据落盘能力。核心原则：**复用已有代码，最小化新增依赖，数据落盘后供报告生成直接消费**。

### 前置条件

- `tools/tushare_data.py` 的 `_Client` 类已封装 Tushare 代理调用（ttshare → cheapyun → 官方三源自动切换）
- Token 已配置：`local/ttshare_token.txt`（ttshare，已过期）+ `local/tushare_token_tmp.txt`（cheapyun，全接口可用 ✅）+ `local/tushare_token.txt`（官方，部分接口）
- `python tools/tushare_data.py check` 可一键检测各 token 可用性
- `local/` 已被 `.gitignore` 排除，安全存放本地数据

### 第一步：定义落盘范围（接口清单）

**A 股基本面落盘**（核心，必做）：

| 接口 | 用途 | Tushare API | 落盘文件 |
|------|------|-------------|---------|
| 利润表 | 营收/净利/毛利率趋势 | `income` | `raw/financial/income_{period}.json` |
| 资产负债表 | 资产结构/负债率/ROE 分解 | `balancesheet` | `raw/financial/balance_{period}.json` |
| 现金流量表 | OCF/CapEx/FCF | `cashflow` | `raw/financial/cashflow_{period}.json` |
| 财务指标 | ROE/ROA/EPS/毛利率/净利率 | `fina_indicator` | `raw/financial/fina_indicator_{period}.json` |
| 业绩预告 | 净利预告区间（如有） | `forecast` | `raw/financial/forecast_{period}.json` |
| 业绩快报 | 净利快报值（如有） | `express` | `raw/financial/express_{period}.json` |
| 分红送配 | 现金分红/送转股 | `dividend` | `raw/financial/dividend.json` |
| 股票基本信息 | 行业/上市日期/总股本 | `stock_basic` | `raw/meta/stock_basic.json` |
| 每日指标 | PE/PB/市值/换手率 | `daily_basic` | `raw/daily/daily_basic_{date}.json` |

**港股/美股**：暂不考虑，后续需要时再扩展。

### 第二步：目录结构规范

```
local/
├── {ts_code}_{name}/                    # 例如 600938_中国海油
│   ├── raw/                             # 原始接口返回（只增不改，JSON 格式）
│   │   ├── financial/                   # 财务主表
│   │   │   ├── income_20231231.json     # 按报告期分文件
│   │   │   ├── balance_20231231.json
│   │   │   ├── cashflow_20231231.json
│   │   │   ├── fina_indicator_20231231.json
│   │   │   ├── forecast_20231231.json   # 可能为空（非每期都有预告）
│   │   │   ├── express_20231231.json    # 可能为空
│   │   │   └── dividend.json            # 全量分红记录
│   │   ├── daily/                       # 日线行情（按需，非必做）
│   │   │   └── daily_basic_20260822.json
│   │   └── meta/                        # 元数据
│   │       └── stock_basic.json
│   └── manifest.json                    # 落盘记录（已落盘的报告期列表 + 时间戳）
```

**格式选择**：JSON（非 Parquet）。理由：
- 与现有 `local/fund*/` 目录风格一致
- 零额外依赖（不需要 pyarrow）
- Claude 直接可读，报告生成时无需额外解析
- 文件体积对基本面数据（非日线行情）影响不大

### 第三步：核心脚本设计

**文件**：`tools/fundamental_fetcher.py`

**设计原则**：
1. 复用 `tools/tushare_data.py` 的 `_Client` 类（不重写）
2. 每次请求间隔 0.75s（全局 sleep，防限流）
3. 失败自动重试 3 次，仍失败记录日志继续
4. 每个接口调用结果落盘为 JSON
5. 支持单股模式和批量模式

**关键实现**：

```python
# tools/fundamental_fetcher.py 核心逻辑（伪代码）

import time
import json
import os
from tools.tushare_data import _Client, _read_token

# 全局限流器
_last_request_time = 0
REQUEST_INTERVAL = 0.75  # 秒

def rate_limited_call(client, api, **kwargs):
    """带限流的接口调用"""
    global _last_request_time
    elapsed = time.time() - _last_request_time
    if elapsed < REQUEST_INTERVAL:
        time.sleep(REQUEST_INTERVAL - elapsed)
    _last_request_time = time.time()
    return client.call(api, **kwargs)

def fetch_and_save(client, ts_code, name, api, period=None, save_dir=None):
    """获取数据并落盘"""
    kwargs = {"ts_code": ts_code}
    if period:
        kwargs["period"] = period
    label, df = rate_limited_call(client, api, **kwargs)
    if df is not None and len(df):
        records = df.to_dict(orient="records")
        filepath = os.path.join(save_dir, f"{api}_{period or 'latest'}.json")
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(records, f, ensure_ascii=False, indent=2, default=str)
        return True, len(records)
    return False, 0

def fetch_stock_fundamentals(ts_code, name, years=5):
    """落盘单只股票的基本面数据"""
    client = _Client()  # 复用现有 Client
    base_dir = f"local/{ts_code}_{name}"
    
    # 1. 股票基本信息（一次性）
    fetch_and_save(client, ts_code, name, "stock_basic", 
                   save_dir=f"{base_dir}/raw/meta")
    
    # 2. 财务主表（近 N 年年报 + 最新季报）
    current_year = datetime.now().year
    for y in range(current_year - 1, current_year - years - 1, -1):
        for period_suffix in ["1231", "0630", "0331"]:
            period = f"{y}{period_suffix}"
            for api in ["income", "balancesheet", "cashflow", "fina_indicator"]:
                ok, n = fetch_and_save(client, ts_code, name, api, period,
                                       save_dir=f"{base_dir}/raw/financial")
                if not ok:
                    break  # 该报告期无数据，跳过更早的
    
    # 3. 业绩预告/快报（可选）
    for api in ["forecast", "express"]:
        fetch_and_save(client, ts_code, name, api,
                       save_dir=f"{base_dir}/raw/financial")
    
    # 4. 分红（全量）
    fetch_and_save(client, ts_code, name, "dividend",
                   save_dir=f"{base_dir}/raw/financial")
    
    # 5. 更新 manifest
    update_manifest(base_dir, ts_code, name)
```

### 第四步：manifest.json 设计

```json
{
  "ts_code": "600938.SH",
  "name": "中国海油",
  "last_fetch": "2026-08-22T10:30:00",
  "periods": {
    "20251231": {"income": true, "balance": true, "cashflow": true, "fina_indicator": true},
    "20250630": {"income": true, "balance": true, "cashflow": true, "fina_indicator": true},
    "20241231": {"income": true, "balance": true, "cashflow": true, "fina_indicator": true}
  },
  "metadata": {"stock_basic": true, "dividend": true}
}
```

用途：
- 快速检查哪些报告期已落盘（避免重复拉取）
- 增量更新时只拉缺失的期间
- 不需要复杂的哈希校验（同名文件覆盖即可）

### 第五步：报告生成集成

报告生成时 **直接从 `local/{ts_code}_{name}/raw/` 读取 JSON**，不需要中间的 processed/ 层。

```python
# 报告生成时读取落盘数据
def load_financial_data(ts_code, name, period):
    """从落盘目录读取财务数据"""
    base = f"local/{ts_code}_{name}/raw/financial"
    data = {}
    for api in ["income", "balance", "cashflow", "fina_indicator"]:
        filepath = f"{base}/{api}_{period}.json"
        if os.path.exists(filepath):
            with open(filepath, "r", encoding="utf-8") as f:
                data[api] = json.load(f)
    return data
```

### 第六步：与现有 tmp_*.py 的关系

| 现有脚本 | 处理方式 |
|---------|---------|
| `tmp_fetch_cnooc.py`（东方财富 API） | 保留作为参考，不纳入落盘系统（数据源不同） |
| `tmp_fetch_cnooc2/3/4.py` | 同上 |
| `tmp_fetch_ann.py`（公告获取） | 可复用其东方财富/巨潮 API 逻辑，扩展为公告落盘 |

**建议**：tmp 脚本验证过的东方财富 API 逻辑，未来可整合到 `tools/eastmoney_data.py`，但本次落盘任务聚焦 Tushare 数据源。

### 第七步：日志与异常处理

```
local/{ts_code}_{name}/log/
├── fetch_20260822.log    # 每次运行一个日志文件
```

日志格式：
```
2026-08-22 10:30:01 [INFO] income 20251231 → OK (12 records, 0.8s)
2026-08-22 10:30:02 [INFO] balance 20251231 → OK (1 records, 0.7s)
2026-08-22 10:30:03 [WARN] forecast 20251231 → EMPTY (no data)
2026-08-22 10:30:04 [ERROR] cashflow 20251231 → FAILED (timeout), retry 1/3
2026-08-22 10:30:08 [INFO] cashflow 20251231 → OK (1 records, 0.9s, retry 1)
```

### 第八步：使用方式

```bash
# 单股落盘
python tools/fundamental_fetcher.py fetch 600938 中国海油

# 批量落盘（从文件读取股票列表）
python tools/fundamental_fetcher.py batch stocks.txt

# 增量更新（只拉 manifest 中缺失的期间）
python tools/fundamental_fetcher.py update 600938 中国海油

# 检查落盘完整性
python tools/fundamental_fetcher.py check 600938 中国海油
```

---

## 三、实施优先级

| 阶段 | 任务 | 预估工时 | 依赖 | 状态 |
|------|------|---------|------|------|
| P0 | `tools/fundamental_fetcher.py` 核心落盘逻辑 | 2-3h | 复用 `_Client` | ✅ 已完成 |
| P0 | 单股测试（选 1 只 A 股验证全流程） | 0.5h | P0 完成 | ✅ 600938 中国海油 43 条 |
| P1 | 批量模式 + manifest 增量更新 | 1h | P0 完成 | ✅ 已完成 |
| P1 | 日志系统 | 0.5h | P0 完成 | ✅ 已完成 |
| P1 | `_Client` cheapyun 代理 + check 命令 | 1h | — | ✅ 超额完成 |
| P1 | `stocks.txt` 批量样本 | 0.5h | — | ✅ 已创建 |
| P2 | 报告生成集成（`load_financial_data`） | 1h | P0 完成 | ✅ 已完成 |
| P3 | 公告落盘（东方财富 API） | 0.5h | 已集成 | ✅ 已完成 |

---

## 四、关键约束（保持不变）

1. **Token 安全**：`local/` 已被 `.gitignore` 排除，token 文件不提交
2. **限流**：每次请求间隔 ≥ 0.75s
3. **重试**：失败最多重试 3 次
4. **日志**：每次落盘操作记录到 `log/` 目录
5. **不修改原始数据**：raw/ 目录只增不改
6. **报告生成只读落盘数据**：不实时调用接口（除非明确需要增量更新）

---

## 五、与原方案的差异总结

| 维度 | 原方案 | v2 方案 |
|------|--------|---------|
| 基础工具类 | 重写 _Client | 复用现有 `_Client` |
| 数据格式 | Parquet | JSON（零依赖） |
| Token 管理 | 新文件名 `tushare_token_tmp.txt` | 复用 `tushare_token.txt` |
| 字段映射 | field_mapping.json | 不需要（Tushare 字段已规范） |
| processed/ 层 | 有 | 无（报告直接读 raw/） |
| manifest | 复杂哈希校验 | 简单 JSON 记录 |
| 落盘范围 | 只提 income/balance/cashflow | 完整 A 股接口清单（9 类） |
| 市场覆盖 | 只提 A 股 | 聚焦 A 股（港股/美股暂不考虑） |
| 与现有代码关系 | 忽略 | 明确复用 + 整合路径 |
