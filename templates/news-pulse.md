# {{COMPANY_NAME}}（{{STOCK_CODE}}）新闻脉搏 — 股价异动归因

**侦察日期**：{{DATE}}
**时间窗口**：{{TIME_WINDOW}}
**股价背景**：{{PRICE_CONTEXT}}

---

## 一句话归因

> {{ONE_SENTENCE_ATTRIBUTION}}

---

## 完整事件时间线

| 日期 | 维度 | 事件 | 来源 | 异动归因权重 |
|:----:|:----:|------|------|:----------:|
| {{DATE_1}} | {{DIMENSION}} | {{EVENT}} | {{SOURCE}} | {{WEIGHT}} |
| {{DATE_2}} | {{DIMENSION}} | {{EVENT}} | {{SOURCE}} | {{WEIGHT}} |
| ... | ... | ... | ... | ... |

维度说明：公司事件 | 监管政策 | 行业竞争 | 市场情绪
权重说明：🔴高 | 🟡中 | ⚪低

---

## 各维度侦察摘要

### 公司事件侦察

{{COMPANY_EVENT_ANALYSIS}}

### 监管与政策

{{REGULATORY_ANALYSIS}}

### 行业与竞争对手

{{INDUSTRY_ANALYSIS}}

### 市场情绪

{{MARKET_SENTIMENT_ANALYSIS}}

---

## 异动归因表

| # | 候选解释 | 证据 | 反证 | 置信度 | 持续性 |
|:-:|---------|------|------|:-----:|:-----:|
| 1 | {{EXPLANATION_1}} | {{EVIDENCE}} | {{COUNTER}} | {{CONFIDENCE}} | {{DURATION}} |
| 2 | {{EXPLANATION_2}} | {{EVIDENCE}} | {{COUNTER}} | {{CONFIDENCE}} | {{DURATION}} |
| 3 | {{EXPLANATION_3}} | {{EVIDENCE}} | {{COUNTER}} | {{CONFIDENCE}} | {{DURATION}} |
| ... | ... | ... | ... | ... | ... |

置信度说明：高(>70%) | 中(40-70%) | 低(<40%)

---

## 性质判断

- [ ] 价值事件（影响基本面）
- [ ] 情绪/技术波动
- [ ] 真因不明
- [ ] 混合因素

**判断**：{{NATURE_JUDGMENT}}

---

## 后续动作

| 动作 | 是否触发 | 理由 |
|------|:--------:|------|
| 触发投资论文重审（`/thesis-tracker`） | {{YES_OR_NO}} | {{REASON}} |
| 触发深度财报研读（`/earnings-review`） | {{YES_OR_NO}} | {{REASON}} |
| 触发管理层重审（`/management-deep-dive`） | {{YES_OR_NO}} | {{REASON}} |
| 仅观察/暂不行动 | {{YES_OR_NO}} | {{REASON}} |

---

## 接下来7-30天跟踪清单

- [ ] {{TRACKING_ITEM_1}}
- [ ] {{TRACKING_ITEM_2}}
- [ ] {{TRACKING_ITEM_3}}
- [ ] {{TRACKING_ITEM_4}}
- [ ] {{TRACKING_ITEM_5}}

---

## 信息缺口声明

{{INFORMATION_GAP}}

---

> **免责声明**：本报告由AI生成，基于公开数据，不构成投资建议。

*侦察日期：{{DATE}} | 时间窗口：{{TIME_WINDOW}}*
