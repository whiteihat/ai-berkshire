# {{COMPANY_NAME}}（{{STOCK_CODE}}）投资论文漂移检测

**创建时间**：{{DATE}}
**最后修改**：{{DATE}}
**数据截止**：{{DATA_CUTOFF}}
**报告版本**：1.0
**公司/基金/行业**：{{COMPANY_NAME}}
**数据来源**：{{DATA_SOURCES}}


**报告日期**：{{DATE}}
**对比区间**：{{OLD_REPORT_DATE}} 至 {{NEW_REPORT_DATE}}
**旧报告**：{{OLD_REPORT_PATH}}
**新报告**：{{NEW_REPORT_PATH}}
**数据截至**：{{DATA_CUTOFF_DATE}}
**数据来源**：{{DATA_SOURCES}}

---

## 信息丰富度评级

**评级**：{{RATING}}级（{{RATING_EXPLANATION}}）

{{AI_BIAS_DECLARATION}}

---

## 一、对比对象与时间跨度

| 项目 | 旧报告 | 新报告 | 校验结果 |
|------|--------|--------|----------|
| 公司/代码 | {{OLD_COMPANY}} | {{NEW_COMPANY}} | {{ENTITY_MATCH}} |
| 报告日期 | {{OLD_REPORT_DATE}} | {{NEW_REPORT_DATE}} | {{DATE_VALIDATION}} |
| 数据截至日 | {{OLD_DATA_CUTOFF}} | {{NEW_DATA_CUTOFF}} | {{COVERAGE_COMPARISON}} |
| 结构完整性 | {{OLD_STRUCTURE_STATUS}} | {{NEW_STRUCTURE_STATUS}} | {{EXTRACTION_STATUS}} |

## 二、总体结论：论文是否漂移

> **漂移结论**：{{DRIFT_VERDICT}}

| 必答项 | 结论 | 证据与最强反证 |
|--------|------|----------------|
| 是否漂移 | {{DRIFT_VERDICT}} | {{OVERALL_EVIDENCE_AND_COUNTEREVIDENCE}} |
| 漂移来源 | {{DRIFT_SOURCE}} | {{DRIFT_SOURCE_EVIDENCE}} |
| 事实、估值、价格与措辞的区分 | {{FACT_PRICE_WORDING_SPLIT}} | {{CLASSIFICATION_BASIS}} |
| 建议动作迁移 | {{ACTION_MIGRATION}} | {{ACTION_EVIDENCE}} |
| 会改变结论的新事实 | {{REEVALUATION_CONDITION}} | {{REQUIRED_EVIDENCE}} |

## 三、维度漂移表

| 维度 | 旧判断 | 新判断 | 漂移方向 | 新触发证据 | 最强反证/信息缺口 | 置信度 |
|------|--------|--------|----------|------------|-------------------|--------|
| 估值锚点 | {{OLD_VALUATION_VIEW}} | {{NEW_VALUATION_VIEW}} | {{VALUATION_DRIFT}} | {{VALUATION_TRIGGER}} | {{VALUATION_COUNTER}} | {{CONFIDENCE}} |
| 核心假设清单 | {{OLD_ASSUMPTION_VIEW}} | {{NEW_ASSUMPTION_VIEW}} | {{ASSUMPTION_DRIFT}} | {{ASSUMPTION_TRIGGER}} | {{ASSUMPTION_COUNTER}} | {{CONFIDENCE}} |
| 红线清单 | {{OLD_RED_LINE_VIEW}} | {{NEW_RED_LINE_VIEW}} | {{RED_LINE_DRIFT}} | {{RED_LINE_TRIGGER}} | {{RED_LINE_COUNTER}} | {{CONFIDENCE}} |
| 管理层质量 | {{OLD_MANAGEMENT_VIEW}} | {{NEW_MANAGEMENT_VIEW}} | {{MANAGEMENT_DRIFT}} | {{MANAGEMENT_TRIGGER}} | {{MANAGEMENT_COUNTER}} | {{CONFIDENCE}} |
| 竞争护城河 | {{OLD_MOAT_VIEW}} | {{NEW_MOAT_VIEW}} | {{MOAT_DRIFT}} | {{MOAT_TRIGGER}} | {{MOAT_COUNTER}} | {{CONFIDENCE}} |

> 漂移方向只可使用 `Improved`、`Unchanged` 或 `Weakened`。`Unchanged` 行的触发证据写 `—`，不得为填表编造证据。

## 四、证据差异明细

| 维度 | 证据类别 | 旧报告证据 | 新报告证据 | 实质变化 | 来源/截至日 | 可验证性 | 对论文影响 |
|------|----------|------------|------------|----------|-------------|------------|------------|
| {{DIMENSION}} | 事实/估计/假设/分析判断/数据不足 | {{OLD_EVIDENCE}} | {{NEW_EVIDENCE}} | {{CHANGE}} | {{SOURCE}} | {{VERIFIABILITY}} | {{THESIS_IMPACT}} |

## 五、估值与数值验算

| 项目 | 旧值（日期、币种/单位） | 新值（日期、币种/单位） | 验算方法/工具结果 | 交叉来源 | 变化性质 | 判断 |
|------|--------------------------|--------------------------|-------------------|----------|----------|------|
| {{METRIC}} | {{OLD_VALUE}} | {{NEW_VALUE}} | {{FINANCIAL_RIGOR_RESULT}} | {{SOURCE_A_AND_B}} | {{CHANGE_NATURE}} | {{JUDGMENT}} |

## 六、建议动作迁移

| 旧动作 | 新动作 | 迁移原因 | 前提条件 | 不执行/反向动作条件 |
|--------|--------|----------|----------|---------------------|
| {{OLD_ACTION}} | {{NEW_ACTION}} | {{RATIONALE}} | {{PREREQUISITES}} | {{REVERSAL_CONDITIONS}} |

## 七、不确定项与需补充来源

| 缺口 | 对结论的影响 | 当前处理 | 需补充的一手来源 | 预计验证时间 |
|------|--------------|----------|------------------|--------------|
| {{GAP}} | {{IMPACT}} | {{INTERIM_TREATMENT}} | {{REQUIRED_SOURCE}} | {{EXPECTED_DATE}} |

## 八、下次跟踪重点

| 跟踪项 | 触发阈值/事件 | 验证来源 | 时间窗口 | 触发后的重审维度/动作 |
|--------|---------------|----------|----------|------------------------|
| {{TRACKING_ITEM}} | {{TRIGGER}} | {{SOURCE}} | {{TIMEFRAME}} | {{REASSESSMENT_ACTION}} |

## 来源、局限性与置信度

| 来源 | 类型 | 发布/报告期 | 访问日 | 用途 |
|------|------|-------------|--------|------|
| {{SOURCE_TITLE}} | 一手/二手 | {{PUBLICATION_OR_PERIOD}} | {{ACCESS_DATE}} | {{USAGE}} |

**AI 分析置信度**：{{AI_ANALYSIS_CONFIDENCE}}

**投资确定性**：{{INVESTMENT_CERTAINTY}}

**数据局限性**：{{DATA_LIMITATIONS}}

> **免责声明**：本报告由 AI 生成，基于公开资料，不构成投资建议。
