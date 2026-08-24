---
description: "AI Berkshire 项目内工作流：单基金分析标准流水线"
disable-model-invocation: true
---

# 单基金分析标准工作流（Fund Pipeline）

对 `$ARGUMENTS` 执行单只基金的标准分析流水线。**本 Skill 是编排器**——自身不产出独立报告，只按主动/被动两条子线调度现有 Skill、在用户决策点停下确认，并提示读取已生成报告。

**与单公司流水线（`/stock-pipeline`）的关键差异**：
1. 基金**不经过** quality-screen / investment-checklist（那些是公司财务硬指标，不适用于基金）。
2. 基金的"管理层 = 基金经理"，management-deep-dive 不直接调用，而是由 `/active-fund-research` 内部复用其"承诺/兑现/资本配置"框架。
3. 基金没有独立的财报精读（除季报走基金自身持仓+业绩分析）；没有股价异动归因（改看净值/份额/申赎）。

---

## 流水线总览

```
入口 → 分岔一（主动/被动）→ 基金深度研究 → 分岔二（可选下钻）→ 买入后跟踪
```

---

## 入口：先定主动/被动

基金必须先分岔，因为两条线的核心分析完全不同：

- **主动基金**（LOF/场外主动）：核心是基金经理能力圈 → `/active-fund-research`
- **指数/被动**（宽基/行业 ETF、指数 LOF）：核心是跟踪误差 + 估值分位 → `/index-fund-research`

若不明确：先用 `tools/data_loader.py search {基金名}` 查代码与类型，再分岔。

**共享**：两者的"产品体检"都按 `.claude/skills/financial-data/SKILL.md` 的"基金产品体检指标清单"执行（费率/规模/流动性/折溢价/份额/持有人等）。

---

## 分岔一：基金深度研究

| 线 | 用 | 核心判断 |
|----|-----|---------|
| 主动基金 | `/active-fund-research` | 经理能力圈、言行一致、任职稳定性、规模健康 |
| 指数/被动 | `/index-fund-research` | 跟踪误差、估值分位、前十大集中、行业暴露 |

输出落到 `reports/00-ETF-LOF/`（文件名见 [报告路由规则](../../rules/report-output.md)）。

**决策闸门**：向用户展示研究结论，确认"是否值得买入/持仓/管理层面有问题"。据此决定是否下钻或进入跟踪。

---

## 分岔二：可选下钻（仅在需要时）

| 情形 | 用 | 说明 |
|------|-----|------|
| 看好的重仓个股 | `/stock-pipeline` | 对单一重仓股走单公司流水线，判断其生意质量 |
| 主动 vs 被动对比 | 交叉跑 `/active-fund-research` + `/index-fund-research` | 买主动还是买被动的决策表 |
| 行业暴露/组合重叠 | `/portfolio-review` | 与现有组合的行业暴露叠加、集中度检查 |
| 净值/份额/申赎异常 | `tools/data_loader.py` fund 数据 | 直接查基金落盘数据，而非 news-pulse 股价归因 |

---

## 买入后跟踪

| 触发 | 用 | 说明 |
|------|-----|------|
| 买入/建立基线 | `/thesis-tracker` | 建基金论文（买入逻辑不是"买经理"就是"买指数"） |
| 基金季报披露 | `/active-fund-research` 或 `/index-fund-research` 的持仓/份额复查 | 看经理是否言行一致、份额是否净流出 |
| 净值/折溢价异常 | `tools/data_loader.py get fund {code}` | 不走新闻股价归因，直接看净值与折溢价 |
| 组合层面 | `/portfolio-review` | 基金在组合中的权重与重叠 |

---

## 与 stock-pipeline 的组合逻辑差异

| 维度 | stock-pipeline | fund-pipeline |
|------|----------------|---------------|
| 入口去劣 | quality-screen / checklist | 主动/被动分岔 |
| 管理层 | management-deep-dive（公司管理层） | active-fund-research 内复用（经理） |
| 财报 | earnings-review / earnings-team | 无独立财报精读 |
| 异动响应 | news-pulse（股价） | data_loader fund 净值/份额 |
| 下钻 | 单公司内的纵深 skill | 可下钻到重仓个股（stock-pipeline） |

---

## 输出与路由

- 本 Skill 不产出独立报告；各阶段由被调用 Skill 按 [报告路由规则](../../rules/report-output.md) 落盘到 `reports/00-ETF-LOF/`（基金）或 `reports/01-单公司分析/{公司}/`（下钻个股）。
- 不复制路由，以 `.claude/rules/report-output.md` 为唯一路径来源。
- 数据获取遵守 `.claude/skills/financial-data/SKILL.md`（统一走 `tools/data_loader.py`，基金产品体检清单共享）。
