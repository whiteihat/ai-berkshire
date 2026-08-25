# {{INDUSTRY}}子赛道 — 漏斗式价值投资筛选研究

**创建时间**：{{DATE}}
**最后修改**：{{DATE}}
**数据截止**：{{DATA_CUTOFF}}
**报告版本**：1.0
**公司/基金/行业**：{{COMPANY_NAME}}
**数据来源**：{{DATA_SOURCES}}


**日期**：{{DATE}}
**子赛道定义**：{{SUB赛道定义}}

---

## 投研原则

> 先排除垃圾，再比较好坏，最后判断价格。
> **不预设立场，先摆数据、再推逻辑、最后得结论。**

---

## 第一层：全市场扫描

| # | 公司 | 代码 | 市值 | 一句话主业 | 产业链环节 |
|:-:|------|------|:----:|-----------|:---------:|
| 1 | {{NAME}} | {{CODE}} | {{CAP}} | {{DESCRIPTION}} | {{SEGMENT}} |
| 2 | {{NAME}} | {{CODE}} | {{CAP}} | {{DESCRIPTION}} | {{SEGMENT}} |
| ... | ... | ... | ... | ... | ... |

**扫描范围**：{{SCAN_SCOPE}}
**筛选后保留**：{{COUNT}}家公司

---

## 第二层：价值投资5条硬指标粗筛

| # | 公司 | PE合理? | ROE>15%? | 现金流>70%净利? | 负债率<60%? | 护城河>=★★★? | 得分 | 结果 |
|:-:|------|:------:|:-------:|:--------------:|:----------:|:-----------:|:---:|:----:|
| 1 | {{NAME}} | {{CHECK}} | {{CHECK}} | {{CHECK}} | {{CHECK}} | {{CHECK}} | {{SCORE}}/5 | {{RESULT}} |
| 2 | {{NAME}} | {{CHECK}} | {{CHECK}} | {{CHECK}} | {{CHECK}} | {{CHECK}} | {{SCORE}}/5 | {{RESULT}} |
| ... | ... | ... | ... | ... | ... | ... | ... | ... |

判断标准：每项满足记1分，≥4分保留进入下一层

**保留名单**：{{PASSED_COMPANIES}}

---

## 第三层：精细分析（{{COUNT}}家，每家300-500字）

### {{COMPANY_1_NAME}}（{{CODE}}）

**商业模式**：
{{BUSINESS_MODEL_300_WORDS}}

**财务质量**：
{{FINANCIAL_QUALITY_300_WORDS}}

**护城河**：
{{MOAT_300_WORDS}}

**主要风险**：
{{RISK_300_WORDS}}

**估值快评**：

| 指标 | 数值 | 判断 |
|------|------|:----:|
| PE | {{VALUE}} | {{JUDGMENT}} |
| PB | {{VALUE}} | {{JUDGMENT}} |
| 股息率 | {{VALUE}} | {{JUDGMENT}} |
| FCF Yield | {{VALUE}} | {{JUDGMENT}} |

---

### {{COMPANY_2_NAME}}（{{CODE}}）

**商业模式**：
{{BUSINESS_MODEL_300_WORDS}}

**财务质量**：
{{FINANCIAL_QUALITY_300_WORDS}}

**护城河**：
{{MOAT_300_WORDS}}

**主要风险**：
{{RISK_300_WORDS}}

**估值快评**：

| 指标 | 数值 | 判断 |
|------|------|:----:|
| PE | {{VALUE}} | {{JUDGMENT}} |
| PB | {{VALUE}} | {{JUDGMENT}} |
| 股息率 | {{VALUE}} | {{JUDGMENT}} |
| FCF Yield | {{VALUE}} | {{JUDGMENT}} |

---

（重复以上格式，每家保留公司一份分析）

---

## 最终排名

| 排名 | 公司 | 代码 | 综合评分 | 核心理由 | 建议动作 |
|:----:|------|------|:-------:|---------|---------|
| 1 | {{NAME}} | {{CODE}} | {{SCORE}} | {{REASON}} | {{ACTION}} |
| 2 | {{NAME}} | {{CODE}} | {{SCORE}} | {{REASON}} | {{ACTION}} |
| 3 | {{NAME}} | {{CODE}} | {{SCORE}} | {{REASON}} | {{ACTION}} |

### 建议下一步

1. 对第1名运行 `/investment-research` 深度研究
2. 对第2-3名运行 `/quality-screen` 去劣筛选
3. 建立投资论文（`/thesis-tracker`）

---

> **免责声明**：本报告由AI生成，基于公开数据，不构成投资建议。

*日期：{{DATE}} | 框架：漏斗式价值投资筛选*
