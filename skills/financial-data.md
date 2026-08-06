# 财务数据获取与交叉验证规范

本规范适用于所有涉及企业财务数据的研究。**每个关键数据必须来自两个独立来源，误差>1%须标记。**

---

## 数据源优先级

### 美股（PDD、腾讯ADR、网易ADR等）

| 优先级 | 来源 | URL | 获取方式 |
|--------|------|-----|---------|
| 1（主） | **Tushare** | `tools/tushare_data.py`（ttshare代理优先，官方API兜底） | 行情/搜索可用，财务视接口权限退化 |
| 2（副） | **macrotrends** | macrotrends.net/stocks/charts/{ticker} | 直接访问，无需注册 |
| 3（副） | **stockanalysis** | stockanalysis.com/stocks/{ticker}/financials | 直接访问，无需注册 |
| 原始一手 | SEC EDGAR | sec.gov/cgi-bin/browse-edgar | 10-K / 10-Q 原文 |

### 港股（腾讯0700、网易9999、美团3690等）

| 优先级 | 来源 | URL | 获取方式 |
|--------|------|-----|---------|
| 1（主） | **Tushare** | `tools/tushare_data.py`（ttshare代理优先，官方API兜底） | 行情/搜索可用，财务视接口权限退化 |
| 2（副） | **aastocks** | aastocks.com/tc/stocks/analysis/company-fundamental | 直接访问 |
| 3（副） | **macrotrends**（ADR代码） | 腾讯用TCEHY，网易用NTES | 直接访问 |
| 原始一手 | HKEX披露易 | hkexnews.hk | 年报PDF |

### A股（三七互娱、吉比特等）

| 优先级 | 来源 | URL | 获取方式 |
|--------|------|-----|---------|
| 1（主） | **Tushare** | `tools/tushare_data.py`（ttshare代理优先，官方API兜底） | 行情/估值/财务/分红/搜索全接口 |
| 2（副） | **东方财富** | eastmoney.com → 搜股票代码 → 财务报表 | 直接访问 |
| 原始一手 | **巨潮资讯** | cninfo.com.cn | 原始年报/季报PDF |

**Tushare 取数工具**（A股/港股/美股通用，分析三大市场时优先调用；依赖用 uv 管理）：

```bash
uv run python tools/tushare_data.py quote 600519        # A股行情 + 市值验算
uv run python tools/tushare_data.py valuation 600519    # PE/PB/市值/52周高低
uv run python tools/tushare_data.py financials 600519   # 近5年年度核心财务
uv run python tools/tushare_data.py dividend 600519     # 分红送配（仅A股有标准接口）
uv run python tools/tushare_data.py search 茅台          # 搜索代码（A股+港股+美股）
uv run python tools/tushare_data.py quote 00700.HK      # 港股行情
uv run python tools/tushare_data.py quote AAPL          # 美股行情
```

市场覆盖与权限退化：

1. **数据源优先级**：ttshare 代理（授权码）→ 官方 tushare（token）→ 两者都失败时工具输出明确退化提示与本节备选来源，**不静默给空数据**
2. **token 只存本机、严禁提交到 git**（`local/` 已被 `.gitignore` 永久排除）：代理授权码放 `local/ttshare_token.txt`（环境变量 `TTSHARE_TOKEN`）；官方 token 放 `local/tushare_token.txt`（环境变量 `TUSHARE_TOKEN`，与官方 tushare 库默认读取变量一致）
3. **A股全接口可用**；港股/美股行情、搜索可用，估值/财务接口视权限——无权限时回到对应市场副源交叉验证
4. 依赖安装：`uv add ttshare tushare`（ttshare 第三方源已在 pyproject.toml 配置，勿用 pip 直接装）

### 台股（台积电2330、联发科2454、大立光3008等）

| 优先级 | 来源 | URL | 获取方式 |
|--------|------|-----|---------|
| 1（主） | **FinMind API** | api.finmindtrade.com | `tools/twstock_data.py`（零依赖脚本，见下） |
| 2（副） | **Goodinfo台湾股市资讯网** | goodinfo.tw/tw/StockDetail.asp?STOCK_ID={代码} | 直接访问 |
| 原始一手 | 公开资讯观测站（MOPS） | mops.twse.com.tw | 财报原文/月营收公告 |

**FinMind 取数工具**（分析台股时优先调用，输出自带市值验算）：

```bash
python3 tools/twstock_data.py quote 2330        # 最新行情 + PER/PBR/殖利率 + 市值验算
python3 tools/twstock_data.py valuation 2330    # 估值指标 + PER一年区间 + 52周高低
python3 tools/twstock_data.py financials 2330   # 近5年年度核心财务（营收/毛利率/归母净利/EPS/ROE）
python3 tools/twstock_data.py revenue 2330      # 近13个月月营收及同比
python3 tools/twstock_data.py dividend 2330     # 近年股利政策（现金/股票股利、除息日）
python3 tools/twstock_data.py search 台積        # 搜索股票代码（注意台股名称为繁体）
```

台股特别注意：

1. **货币单位是新台币（TWD）**，与港币/人民币/美元混排时必须显式标注，跨市场对比先统一换算
2. **月营收是台股独有优势**：上市柜公司每月10日前强制披露上月营收，是跟踪基本面拐点最快的公开信号，earnings-review/thesis-tracker 类分析应优先利用（`revenue` 子命令）
3. FinMind 损益表为**单季值**，工具已自动加总为年度值；不足4季的年份会标注"仅前N季累计"
4. FinMind 未注册可直接用（有小时级限额）。注册后的 API token **只存本机、严禁提交到 git**，工具按优先级自动读取：①环境变量 `FINMIND_TOKEN`；②本地文件 `local/finmind_token.txt`（`local/` 已被 `.gitignore` 永久排除，把 token 单独一行写入该文件即可）。token 不得出现在报告、skill、commit 中
5. 交叉验证：FinMind 数值与 Goodinfo（或 macrotrends 上的 ADR，如 TSM）对照，误差规则同下；台积电等有 ADR 的公司注意 ADR 与台股原股的汇率/存托比率差异（1 TSM ADR = 5 股 2330）

### 基金与指数（ETF/LOF/主动基金，index-fund-research / active-fund-research 专用）

| 优先级 | 来源 | URL | 获取方式 |
|--------|------|-----|---------|
| 1（主） | **Tushare 基金/指数接口** | `tools/tushare_data.py`（ttshare代理优先，官方API兜底） | fundinfo/fundnav/funddaily/fundshares/fundholdings/fundmanager/fundholder/fundsearch/fundtracking/indexinfo/indexdaily/indexvaluation/indexweight |
| 2（副） | **TickFlow**（场内行情/指数K线备源） | `tools/tickflow_data.py`，免费层日K即可用 | 补 fund_daily/index_daily 无权限或盘中实时缺口；**只有行情类数据**（无净值/持仓/估值分位） |
| 3（副） | **天天基金** | fund.eastmoney.com（搜基金代码） | 净值/费率/规模/经理/持仓/持有人/限购——tushare 无权限接口（fund_basic/portfolio/manager/holder/share）的第一副源 |
| 4（副） | **东方财富数据中心** | data.eastmoney.com | 场内行情、ETF份额、基金规模 |
| 5（副） | **乐咕乐股** | legulegu.com | 指数估值与历史分位（index_dailybasic 无权限时） |
| 6（副） | **集思录** | jisilu.cn | 场内基金折溢价、申赎套利 |
| 原始一手 | **证监会基金信息披露平台** | fund.csrc.gov.cn | 基金合同/招募说明书/季报/半年报/年报 PDF |

**Tushare 基金/指数取数工具**（基金/指数分析时优先调用）：

```bash
uv run python tools/tushare_data.py fundinfo 510300     # 基金基本盘（类型/费率/经理/跟踪指数）
uv run python tools/tushare_data.py fundnav 012414.OF   # 净值与业绩（复权净值/区间收益/回撤）
uv run python tools/tushare_data.py funddaily 510300    # 场内行情/流动性/折溢价
uv run python tools/tushare_data.py fundshares 510300   # 份额与规模变动（近8期）
uv run python tools/tushare_data.py fundholdings 161725 # 季报前十大持仓
uv run python tools/tushare_data.py fundmanager 161725  # 历任基金经理档案
uv run python tools/tushare_data.py fundholder 161725   # 持有人结构
uv run python tools/tushare_data.py fundsearch 白酒      # 搜索基金与指数代码
uv run python tools/tushare_data.py fundtracking 012414.OF --index 399997.SZ  # 跟踪误差
uv run python tools/tushare_data.py indexinfo 000300.SH # 指数基本盘
uv run python tools/tushare_data.py indexdaily 000300.SH   # 指数行情与区间收益
uv run python tools/tushare_data.py indexvaluation 000300.SH  # 指数估值与历史分位
uv run python tools/tushare_data.py indexweight 000300.SH    # 成分权重与集中度
```

**接口权限退化表**（实测 ttshare 代理现状，随授权码变化）：

| 接口 | 命令 | 官方积分门槛 | ttshare 实测 | 无权限/无数据时的副源 |
|------|------|------------|-------------|---------------------|
| fund_daily | funddaily | ~2000 | ✅ 可用 | 东方财富数据中心；盘中实时 TickFlow |
| fund_nav | fundnav/fundtracking/折溢价 | ~2000 | ⚠️ 场外基金可用，**场内ETF返回空** | 天天基金历史净值页 |
| fund_basic | fundinfo | ~2000 | ❌ 无权限 | 天天基金基金档案页（费率/经理/基准/跟踪指数） |
| fund_share | fundshares | ~2000 | ❌ 无权限 | 天天基金规模变动页 |
| fund_portfolio | fundholdings | ~5000 | ❌ 无权限 | 天天基金持仓明细页 |
| fund_manager | fundmanager | ~5000 | ❌ 无权限 | 天天基金基金经理页 |
| fund_holder | fundholder | ~5000 | ❌ 无权限 | 天天基金持有人结构页 |
| index_daily | indexdaily/fundtracking | 免费 | ✅ 可用 | 中证指数官网；TickFlow 日K |
| index_basic | indexinfo | ~2000 | ✅ 可用 | 中证指数官网 csi.com.cn |
| index_dailybasic | indexvaluation | ~2000 | ✅ 可用 | 乐咕乐股指数估值页 |
| index_weight | indexweight | ~2000 | ✅ 可用 | 中证指数官网成分列表，或跟踪ETF的 fundholdings 兜底 |

**TickFlow 能力边界**（`tools/tickflow_data.py`）：只有 ETF/指数/个股**实时行情与日K**（免费层日K+标的信息，完整服务实时行情）；**没有**场外净值/持仓/份额/经理/指数估值分位/成分权重——那些仍走 tushare fund_* 命令或天天基金。token 放 `local/tickflow_key.txt`（环境变量 `TICKFLOW_API_KEY`），同 local/ 保密规则。

**基金特有规则**：

1. **场内价格实时、净值 T+1 披露**（QDII 更久）→ 折溢价基于 T-1 净值计算，必须标注滞后；盘中实时折溢价用 TickFlow 实时价 × tushare 净值
2. **基金业绩一律用复权净值（adj_nav）**口径（含分红再投）；指数收益为价格口径，长期对比注明"是否含股息"（全收益指数用中证指数官网副源）
3. **指数估值分位窗口必须标注**（1y/3y/5y/all），分位低≠便宜——盈利下滑时低分位是价值陷阱
4. **代码后缀规则**：基金接口（fund_*）ts_code 用 `.OF` 后缀；场内行情/指数用 `.SH/.SZ`；`5x→.SH`、`1x→.SZ`、`0x/2x/3x→场外`；H 开头指数为 `.CSI` 系列
5. tushare **无换手率/限购/申赎费**接口 → 一律用天天基金副源
6. 基金数据与股票数据**工具隔离**：`fund_*`/`index_*` 命令与股票命令（quote/valuation 等）完全独立，基金代码误传股票命令会得到引导提示

### 基金产品体检指标清单（index-fund-research / active-fund-research 共享）

两个基金 skill 的"产品体检"步骤统一按此清单执行，指标口径与健康阈值以本表为准：

| 指标 | 口径 | 健康阈值（参考） | 来源 |
|------|------|----------------|------|
| 综合费率 | 管理费+托管费+销售服务费 | 被动 ≤0.5%、主动 ≤1.5%（申赎费另计，副源） | fundinfo + 天天基金 |
| 规模 | 最新资产净值 | >2亿（防清盘）；主动 >100亿警惕策略容量 | fundshares + 天天基金 |
| 流动性 | 近20日日均成交额 | 场内 >1000万/日 | funddaily |
| 折溢价 | (场内价−T-1净值)/净值 | ±1%以内（T-1口径标注） | funddaily + 天天基金 |
| 跟踪误差 | 年化日收益差标准差 | 宽基 <1% | fundtracking |
| 持有人结构 | 机构/个人占比及趋势 | 机构占比适中且稳定（上升=机构认可信号） | fundholder + 天天基金 |
| 份额变动 | 近8期份额环比 | 无持续大幅净流出 | fundshares |
| 分红记录 | 历史分红金额/次数 | 与合同约定一致 | 天天基金 |

---

## 执行规范

### 第一步：获取数据

对每个财务指标（收入、净利润、毛利率、经营现金流、资产负债率等），分别从**来源1**和**来源2**取数。

### 第二步：误差计算与标记

```
误差率 = |来源1数值 - 来源2数值| / 来源1数值 × 100%
```

| 误差 | 处理方式 |
|------|---------|
| ≤ 1% | ✅ 一致，取来源1数值，标注两个来源 |
| 1% ~ 5% | ⚠️ 标记"数据存在差异"，注明两个数值，说明可能原因（汇率/会计口径） |
| > 5% | ❌ 标记"数据存在重大差异"，必须查原始财报核实，不得直接使用 |

### 第三步：数据呈现格式

每个关键数据必须按以下格式标注：

```
收入：1,239亿元 ✅
  - macrotrends: 1,241亿元
  - stockanalysis: 1,237亿元
  - 误差: 0.3%
```

差异示例：
```
净利润：245亿元 ⚠️ 数据存在差异
  - macrotrends: 245亿元（GAAP）
  - stockanalysis: 278亿元（Non-GAAP）
  - 误差: 13.5% — 原因：会计口径不同（GAAP vs Non-GAAP）
```

---

## 常见差异原因（不一定是数据错误）

| 原因 | 说明 |
|------|------|
| GAAP vs Non-GAAP | 最常见，尤其是利润类数据 |
| 汇率换算 | 港币/人民币/美元换算时间点不同 |
| 财年定义 | 自然年 vs 财年（如苹果财年10月结束） |
| 合并口径 | 是否含少数股东权益 |
| 数据更新滞后 | 某平台尚未更新最新一期财报 |

---

## 特别规则

1. **未上市公司**（米哈游、莉莉丝等）：只有一手数据来源时，数据前标记 `[估计]`，不执行交叉验证
2. **季度数据 vs 年度数据**：优先使用年度数据做交叉验证，季度数据部分来源可能有滞后
3. **原始财报优先**：若两个来源均与原始财报（10-K/年报PDF）不符，以原始财报为准，标记来源错误

---

## 股价与复权（历史序列必读）

价格有三种口径，混用会让历史股价位置、长期涨幅、历史估值分位全部失真：

| 口径 | 含义 | 用途 |
|------|------|------|
| 不复权 | 实际成交价，除权除息日跳空 | 仅用于"当前时点"快照 |
| 前复权 | 以最新价为基准回调历史价 | 历史股价对比、N年涨幅、历史PE band 一律用它 |
| 后复权 | 以上市首日为基准前推 | 计算历史总回报/年化收益 |

规则：

1. 涉及历史价格的分析统一用**前复权**，且同一分析内**不得混用**复权与不复权来源。
2. 当前市值/当前PE 用**当前实际股价 × 当前总股本**即可，与复权无关——复权只影响历史序列。
3. 跨越拆股/大比例送转的每股指标（历史EPS、历史股价），必须复权还原后再同比。
4. 总回报/年化收益需计入分红（后复权已含），只看价格涨幅会低估。
5. 增发/回购后市值验算以最新总股本为准（`financial_rigor.py verify-market-cap` 偏差>5% 会提示核对）。

---

## 快速索引

| 场景 | 主要来源 | 备用来源 |
|------|---------|---------|
| PDD / 拼多多 | tools/tushare_data.py（PDD，美股） | macrotrends（PDD）/ stockanalysis |
| 腾讯 | tools/tushare_data.py（00700.HK） | aastocks（0700.HK）/ macrotrends（TCEHY） |
| 网易 | tools/tushare_data.py（09999.HK） | aastocks（9999.HK）/ macrotrends（NTES） |
| 三七互娱 | tools/tushare_data.py（002555） | eastmoney.com（002555）/ cninfo.com.cn |
| 吉比特 | tools/tushare_data.py（603444） | eastmoney.com（603444）/ cninfo.com.cn |
| Nintendo | macrotrends.net/stocks/charts/NTDOY | stockanalysis.com/stocks/ntdoy |
| Capcom | macrotrends（CCOEY） | stockanalysis（CCOEY） |
| 台积电 | tools/twstock_data.py（2330） | goodinfo.tw / macrotrends（TSM，注意1 ADR=5股） |
| 联发科 | tools/twstock_data.py（2454） | goodinfo.tw |
| 沪深300ETF | tools/tushare_data.py（510300） | 天天基金 fund.eastmoney.com / TickFlow |
| 招商白酒LOF | tools/tushare_data.py（161725 / 012414.OF） | 天天基金 fund.eastmoney.com |
| 指数估值分位 | tools/tushare_data.py indexvaluation | 乐咕乐股 legulegu.com |
