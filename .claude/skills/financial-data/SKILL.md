---
description: "AI Berkshire 项目内工作流：财务数据获取规范与统一数据访问层"
disable-model-invocation: true
---

# 财务数据获取与统一数据访问规范

本规范是所有涉及财务数据研究的**唯一数据获取契约**。任何 Skill 不再内嵌可持续的数据源命令，只调用统一数据访问层 `tools/data_loader.py`，并按本节规则处理数据。

---

## 统一原则

1. **本地优先**：先读 `local/` 落盘缓存（由 `fundamental_fetcher` / `fund_data_fetcher` 写入）。命中且足够就直接用，不再调用外部接口。
2. **主源唯一、退化明确**：缓存不足时，按下方"数据源与退化链"的单一顺序取数，取到后**强制落盘**，确保后续任务复用。
3. **合理性校验（非双源比对）**：对主源数据做合理性校验——与前值同比是否合理、与行业常识是否冲突、市值≈股价×总股本、三表勾稽是否自洽。**明显偏离或口径冲突才启动人工核查**；不再强制"两个独立来源 + 误差标记"。
4. **持久化与快照分流**：财务、估值分位、基金持仓等**持久化指标**强制落盘；盘中实时行情等**快照**仅可选缓存，不必落盘防止无限增长。

> **调用方式**：Skill 生成报告时统一用
> ```python
> from tools.data_loader import get, load_local, update, search
> ```
> 或命令行 `python tools/data_loader.py get <type> <code> <name> [--field ...]`。不要直接散落 tushare/twstock/tickflow 命令；这些工具的细粒度命令仅供排查，不由 Skill 直接驱动。

> **个股财务回溯口径（"10+N"模式）**：`data_loader get stock` 的财务主表默认回溯**近十年**——以当前年份为基准往前推 10 个完整年度（如 2026 年为当前年，则 2016–2025 为完整十年），每年含一季报(0331)/中报(0630)/三季报(0930)/年报(1231)；**当年已披露的报告期**（如 2026 中报）一并自动纳入且不占用十年名额。实现见 `tools/fundamental_fetcher.py::_get_report_periods`，`--years` 可覆盖。
>
> **时间对齐机制**：`_get_report_periods` 只决定"拉取哪些期间"（按期间末日 ≤ 今天）；是否值得重试由 `_should_retry_period` 综合判断——空文件、核心接口（income/balancesheet/cashflow/fina_indicator）不完整、已过法定披露截止日但 manifest 无数据均触发重试。`_check_report_disclosed` 结合公告元数据（announcements.json）和法定截止日（年报次年4/30、中报当年8/31、季报下季度末）交叉验证披露状态。`update_stock` 在增量更新前先刷新公告列表，确保交叉验证使用最新信息。A股年报通常在次年 Q1 披露，中报在当年 Q3，季报在下一季度内——期间末日已过但报告尚未披露时，Tushare 返回空且不落盘文件，下次 update 自动重试。

---

## 统一数据访问层（tools/data_loader.py）

| 场景 | 调用 | 说明 |
|------|------|------|
| 个股财务 | `get("stock", code, name)` | 返回 {api: records}，自动落盘 |
| 个股元数据 | `get("stock", code, name, field="meta")` | 股票基本盘 |
| 个股公告 | `get("stock", code, name, field="announcements")` | 最近公告 |
| 基金基本盘 | `get("fund", code, field="basic")` | 类型/费率/经理/跟踪指数 |
| 基金净值/业绩 | `get("fund", code, field="nav")` | 复权净值与区间收益 |
| 基金场内行情 | `get("fund", code, field="daily")` | 流动性/折溢价 |
| 基金持仓 | `get("fund", code, field="holdings", period=...)` | 季报前十大持仓 |
| 份额/经理/持有人 | `get("fund", code, field="shares"\|"manager"\|"holder")` | 对应子项 |
| 仅读本地 | `load_local(type, code, name)` | 不触发更新 |
| 强制刷新 | `update(type, code, name)` | 增量更新缺失期间 |
| 搜索代码 | `search(keyword)` | 个股/基金/指数 |
| 缓存状态 | `status(type, code, name)` / `list()` | 排查 |

---

## 数据源与退化链（主源定义）

所有数据的取数链在 `data_loader` 内部已封装。此处仅记录各市场的**主源与备用来源**，供人工核查/排障时参考，不作为 Skill 的执行命令。

### 股票链（A股/港股/美股）

| 市场 | 主源 | 备用（人工核查） | 一手文件 |
|------|------|------------------|----------|
| A股 | Tushare（ttshare→cheapyun→官方） | 东方财富 eastmoney.com | 巨潮资讯 cninfo.com.cn |
| 港股 | Tushare（ttshare→cheapyun→官方） | aastocks / macrotrends（ADR） | 港交所披露易 hkexnews.hk |
| 美股 | Tushare（ttshare→cheapyun→官方） | macrotrends / stockanalysis | SEC EDGAR（10-K/10-Q） |

**退化链**（已实测 2026-08-24）：`ttshare 代理 → cheapyun 代理 → 官方 Tushare`。当前状态：ttshare 授权码已过期，cheapyun 在用；三源全失败时 `data_loader` 返回空并给出备用来源提示，**不静默给空数据**。

Token 只存本机（`local/` 下 token 文件或环境变量，见下述），严禁提交到 Git。

### 台股链

| 主源 | 备用 | 一手 |
|------|------|------|
| FinMind API（`twstock_data`，零依赖） | Goodinfo goodinfo.tw | MOPS 公开资讯观测站 |

- 台股人民币值单位是新台币（TWD），跨市场对比先换算。
- FinMind 未注册可直接用（小时级限额）；注册后 token 只存 `local/finmind_token.txt`。
- 月营收每月 10 日前强制披露，是跟踪基本面的最快信号（earnings/thesis 类优先用）。

### 基金/指数链

| 主源 | 备用 | 一手 |
|------|------|------|
| Tushare 基金/指数接口 | TickFlow（仅行情）；天天基金（净值/持仓/经理/持有人）；东方财富数据；乐咕乐股（指数估值分位）；集思录（折溢价） | 证监会基金信息披露平台 fund.csrc.gov.cn |

- 持久化字段（fund_basic/nav/holdings/shares/manager/holder）强制落盘；TickFlow 只补**行情类快照**（无净值/持仓/估值分位），且仅可选缓存。
- 基金代码后缀：`fund_*` 用 `.OF`；场内行情/指数用 `.SH/.SZ`（`5x→.SH`、`1x→.SZ`、`0x/2x/3x→场外`）；H 开头指数 `.CSI`，国证指数 `.CNI`。

---

## 市场与货币规则（历史序列必读）

- 历史价格统一**前复权**，且同一分析内不得混用复权/不复权来源；当前市值/PE 用当前实际股价×当前总股本，与复权无关。
- 跨拆股/送转的每股指标必须先复权还原再同比；总回报计分红（后复权已含）。
- 跨市场对比：先说明汇率、ADR/原股比价（如 1 TSM ADR=5 股 2330）或复权处理。
- 市值验算偏差>5% 触发核对（`financial_rigor.py verify-market-cap`）。
---

## 基金产品体检指标（index-fund / active-fund 共享）

两个基金 skill 的"产品体检"统一按此清单执行，口径与健康阈值以本表为准：

| 指标 | 口径 | 健康阈值（参考） | 主源/备用 |
|------|------|----------------|-----------|
| 综合费率 | 管理费+托管费+销售服务费 | 被动 ≤0.5%、主动 ≤1.5% | data_loader fund/basic + 天天基金 |
| 规模 | 最新资产净值 | >2亿（防清盘）；主动 >100亿警惕容量 | fund/shares + 天天基金 |
| 流动性 | 近20日日均成交额 | 场内 >1000万/日 | fund/daily |
| 折溢价 | (场内价−T-1净值)/净值 | ±1%以内（T-1口径标注） | fund/daily + 天天基金 |
| 跟踪误差 | 年化日收益差标准差 | 宽基 <1% | fund/daily（index 对照） |
| 持有人结构 | 机构/个人占比及趋势 | 机构适中且稳定 | fund/holder + 天天基金 |
| 份额变动 | 近8期份额环比 | 无持续大幅净流出 | fund/shares |
| 分红记录 | 历史分红金额/次数 | 与合同一致 | 天天基金 |

> 折溢价基于 T-1 净值计算并标注滞后；基金业绩一律用复权净值（adj_nav）口径。

---

## 合理性校验（替代"双源交叉验证"）

取到主源数据后，做以下**低成本合理性校验**；通过即用，不通过才人工核查：

1. **同比合理性**：本期 vs 上一期同类指标，是否在一个合理量级（如毛利率突变、净利润翻数倍但无公告）。
2. **常识一致性**：市值 ≈ 股价×总股本（偏差>5%触发核对）；负债/现金/营收量级与公司体量匹配。
3. **勾稽自洽**：营收/净利/经营现金流的大致关系（如经营现金流长期远小于净利需警惕）。
4. **口径敏感**：对高杠杆决策数据（净现金、负债、PE band、退出 PE），若与前值/常识冲突，启动 `financial_rigor.py cross-validate` 人工核查，并保留核查记录。

**不做**：不强制每个关键数据"两个独立来源双取 + 误差≤1%标记"。主源无误即用主源；只有明显异常才降级人工双查。

---

## 快速索引

| 场景 | 主源（经 data_loader） | 备用（人工核查） |
|------|------------------------|------------------|
| PDD | Tushare（PDD 美股） | macrotrends / stockanalysis |
| 腾讯 | Tushare（00700.HK） | aastocks / macrotrends（TCEHY） |
| 网易 | Tushare（09999.HK） | aastocks / macrotrends（NTES） |
| A股（三七/吉比特等） | Tushare（6位代码） | eastmoney / cninfo |
| 台积电 | FinMind（twstock, 2330） | goodinfo / macrotrends（TSM, 1 ADR=5股） |
| 沪深300ETF | Tushare（510300） | 天天基金 / TickFlow |
| 指数估值分位 | Tushare index/valuation | 乐咕乐股 legulegu.com |

---

## Token 与保密

- 所有 Token（ttshare/cheapyun/tushare/FinMind/TickFlow）只存本机，`local/` 已被 `.gitignore` 永久排除；严禁写入报告、Skill 或 commit。
- `data_loader` 自动读取 `local/` 下的 token 文件（或环境变量），不要求 Skill 显式传 token。
