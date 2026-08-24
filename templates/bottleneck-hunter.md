# 瓶颈猎手报告模板组

本文件定义 `/bottleneck-hunter` 的读者可见产物结构。趋势筛选、瓶颈判定、估值硬门槛、数据验证、增量更新和是否出报告的规则以 Skill 为准；文件位置与命名以 [报告路由规则](../.claude/rules/report-output.md) 为准。

---

# 变体 A：完整瓶颈扫描

# {{TREND_NAME}}供应链瓶颈扫描与机会看板

**扫描日期**：{{DATE}}
**数据截至**：{{DATA_CUTOFF_DATE}}
**扫描范围**：{{SCAN_SCOPE}}
**数据来源**：{{DATA_SOURCES}}

## 信息丰富度评级

**评级**：{{RATING}}级（{{RATING_EXPLANATION}}）

{{AI_BIAS_DECLARATION}}

## 一、执行摘要

{{EXECUTIVE_SUMMARY}}

## 二、超级趋势验证

| 验证维度 | 证据 | 来源/日期 | 判断 |
|----------|------|-----------|------|
| 持续性 | {{EVIDENCE}} | {{SOURCE}} | {{JUDGMENT}} |
| 物理性 | {{EVIDENCE}} | {{SOURCE}} | {{JUDGMENT}} |
| 规模性 | {{EVIDENCE}} | {{SOURCE}} | {{JUDGMENT}} |
| 加速性 | {{EVIDENCE}} | {{SOURCE}} | {{JUDGMENT}} |

## 三、供应链物理拆解

{{SUPPLY_CHAIN_MAP}}

| 层级 | 物理环节 | 上下游关系 | 当前约束 | 重点扫描理由 |
|------|----------|------------|----------|--------------|
| {{LAYER}} | {{STAGE}} | {{CONNECTION}} | {{CONSTRAINT}} | {{RATIONALE}} |

## 四、瓶颈地图与评级

| 环节 | Layer | 供给集中度 | 扩产周期 | 替代难度 | 利用率 | 需求增速 | 客户验证周期 | 评级 | 证据与反证 |
|------|-------|------------|----------|----------|--------|----------|--------------|------|------------|
| {{STAGE}} | {{LAYER}} | {{CONCENTRATION}} | {{EXPANSION_CYCLE}} | {{SUBSTITUTION_DIFFICULTY}} | {{UTILIZATION}} | {{DEMAND_GROWTH}} | {{VALIDATION_CYCLE}} | {{RATING}} | {{EVIDENCE_AND_COUNTEREVIDENCE}} |

## 五、候选公司初筛与估值检查

| 公司/代码 | 瓶颈业务占比 | 市值 | 年收入 | PS | PE | 估值灯号 | 长期收益验算 | 结果 |
|-----------|--------------|------|--------|----|----|----------|--------------|------|
| {{COMPANY_AND_CODE}} | {{BOTTLENECK_REVENUE_SHARE}} | {{MARKET_CAP}} | {{REVENUE}} | {{PS}} | {{PE}} | {{VALUATION_LIGHT}} | {{LONG_TERM_RETURN_CHECK}} | {{SCREENING_RESULT}} |

## 六、瓶颈机会看板与排名

| 排名 | 公司 | 代码 | 瓶颈环节 | 瓶颈评级 | 市场份额 | 收入增速 | 信号强度 | 估值判断 |
|------|------|------|----------|----------|----------|----------|----------|----------|
| {{RANK}} | {{COMPANY_NAME}} | {{STOCK_CODE}} | {{BOTTLENECK_STAGE}} | {{BOTTLENECK_RATING}} | {{MARKET_SHARE}} | {{REVENUE_GROWTH}} | {{SIGNAL_STRENGTH}} | {{VALUATION_JUDGMENT}} |

## 七、重点机会卡

### {{COMPANY_NAME}}（{{STOCK_CODE}}）— {{ONE_LINE_BOTTLENECK_POSITION}}

| 项目 | 内容 | 事实/分析/估计 | 来源/截至日 | 最强反证或改变条件 |
|------|------|-----------------|-------------|-------------------|
| 本次触发事件 | {{TRIGGER_EVENT}} | {{CLAIM_TYPE}} | {{SOURCE}} | {{COUNTERCASE}} |
| 瓶颈定位与评级 | {{BOTTLENECK_POSITION}} | {{CLAIM_TYPE}} | {{SOURCE}} | {{COUNTERCASE}} |
| 财务与估值 | {{FINANCIAL_SNAPSHOT}} | {{CLAIM_TYPE}} | {{SOURCE}} | {{COUNTERCASE}} |
| 看多逻辑 | {{BULL_CASE}} | {{CLAIM_TYPE}} | {{SOURCE}} | {{COUNTERCASE}} |
| 看空逻辑 | {{BEAR_CASE}} | {{CLAIM_TYPE}} | {{SOURCE}} | {{COUNTERCASE}} |
| 建议动作 | {{ACTION}} | {{CLAIM_TYPE}} | {{SOURCE}} | {{ACTION_CHANGE_CONDITION}} |

## 八、交叉验证与反证

| 判断 | 支持证据 | 最强反证 | 仍需验证的事实 | 结论置信度 |
|------|----------|----------|----------------|------------|
| {{CLAIM}} | {{SUPPORTING_EVIDENCE}} | {{COUNTEREVIDENCE}} | {{OPEN_QUESTION}} | {{CONFIDENCE}} |

## 九、行动建议与下一步

| 行动 | 条件 | 验证来源 | 时间窗口 |
|------|------|----------|----------|
| {{ACTION}} | {{CONDITION}} | {{SOURCE}} | {{TIMEFRAME}} |

## 十、信息缺口、来源与置信度

| 缺口 | 对结论影响 | 需要的来源 | 当前处理 |
|------|------------|------------|----------|
| {{GAP}} | {{IMPACT}} | {{REQUIRED_SOURCE}} | {{INTERIM_TREATMENT}} |

**AI 分析置信度**：{{AI_ANALYSIS_CONFIDENCE}}

**投资确定性**：{{INVESTMENT_CERTAINTY}}

---

# 变体 B：有明确标的的信号快报

# 瓶颈猎手 — {{SCAN_DATETIME}}

**扫描窗口**：{{TIME_WINDOW}}
**数据截至**：{{DATA_CUTOFF_DATE}}
**数据来源**：{{DATA_SOURCES}}

{{AI_BIAS_DECLARATION}}

## 明确标的

### {{COMPANY_NAME}}（{{STOCK_CODE}}）— {{ONE_LINE_BOTTLENECK_POSITION}}

| 项目 | 内容 | 来源/截至日 | 判断 |
|------|------|-------------|------|
| 本次触发事件 | {{TRIGGER_EVENT}} | {{SOURCE}} | {{JUDGMENT}} |
| 瓶颈定位与评级 | {{BOTTLENECK_POSITION}} | {{SOURCE}} | {{JUDGMENT}} |
| 市值/年收入/PS/PE/增速 | {{VALUATION_SNAPSHOT}} | {{SOURCE}} | {{JUDGMENT}} |
| 估值门槛与长期收益验算 | {{VALUATION_CHECK}} | {{FINANCIAL_RIGOR_RESULT}} | {{JUDGMENT}} |
| 看多逻辑 | {{BULL_CASE}} | {{SOURCE}} | {{JUDGMENT}} |
| 看空逻辑 | {{BEAR_CASE}} | {{SOURCE}} | {{JUDGMENT}} |
| 建议动作 | {{ACTION}} | {{ACTION_CONDITION}} | {{JUDGMENT}} |

## 其他信号

| 环节 | 信号 | 来源 | 初步判断 | 下一步 |
|------|------|------|----------|--------|
| {{STAGE}} | {{SIGNAL}} | {{SOURCE}} | {{JUDGMENT}} | {{NEXT_STEP}} |

## 观察名单状态变化

| 标的/环节 | 状态变化 | 证据 | 下一检查点 |
|-----------|----------|------|------------|
| {{ITEM}} | {{STATUS_CHANGE}} | {{EVIDENCE}} | {{NEXT_CHECK}} |

## 信息缺口与置信度

{{INFORMATION_GAPS_AND_CONFIDENCE}}

---

# 变体 C：仅信号扫描快报

# 瓶颈猎手信号扫描 — {{SCAN_DATETIME}}

**扫描窗口**：{{TIME_WINDOW}}
**数据截至**：{{DATA_CUTOFF_DATE}}
**数据来源**：{{DATA_SOURCES}}

{{AI_BIAS_DECLARATION}}

## 新信号

| 环节 | 信号描述 | 来源/时间 | 是否有可投资标的 | 初步判断 | 下一步 |
|------|----------|-----------|------------------|----------|--------|
| {{STAGE}} | {{SIGNAL_DESCRIPTION}} | {{SOURCE_AND_TIME}} | {{INVESTABLE_TARGET_STATUS}} | {{JUDGMENT}} | {{NEXT_STEP}} |

## 观察名单状态

| 标的/环节 | 当前状态 | 本次变化 | 证据 | 后续动作 |
|-----------|----------|----------|------|----------|
| {{ITEM}} | {{CURRENT_STATUS}} | {{STATUS_CHANGE}} | {{EVIDENCE}} | {{NEXT_ACTION}} |

## 信息缺口与置信度

{{INFORMATION_GAPS_AND_CONFIDENCE}}

---

# 变体 D：瓶颈总地图（持续维护）

# 全球供应链瓶颈总地图

**最后更新**：{{LAST_UPDATED}}
**覆盖趋势**：{{COVERED_TRENDS}}
**数据截至**：{{DATA_CUTOFF_DATE}}

## 当前状态摘要

| 超级趋势 | 状态 | S 级数量 | A 级数量 | B 级数量 | 本次关键变化 | 下次复核 |
|----------|------|----------|----------|----------|--------------|----------|
| {{TREND}} | {{STATUS}} | {{S_COUNT}} | {{A_COUNT}} | {{B_COUNT}} | {{KEY_CHANGE}} | {{NEXT_REVIEW}} |

## 全量瓶颈地图

| 趋势 | Layer | 环节 | 评级 | 供应商/集中度 | 解除窗口/替代路径 | 最近变化 | 关键证据 |
|------|-------|------|------|---------------|-------------------|----------|----------|
| {{TREND}} | {{LAYER}} | {{STAGE}} | {{RATING}} | {{SUPPLIERS_AND_CONCENTRATION}} | {{RELIEF_OR_SUBSTITUTION}} | {{LATEST_CHANGE}} | {{EVIDENCE}} |

## 变更日志

| 时间 | 环节 | 新增/升级/降级/解除 | 旧评级 | 新评级 | 证据 | 影响 |
|------|------|---------------------|--------|--------|------|------|
| {{DATE}} | {{STAGE}} | {{CHANGE_TYPE}} | {{OLD_RATING}} | {{NEW_RATING}} | {{EVIDENCE}} | {{IMPACT}} |

---

# 变体 E：观察名单（持续维护）

# 瓶颈猎手观察名单

**最后更新**：{{LAST_UPDATED}}
**数据截至**：{{DATA_CUTOFF_DATE}}

## 当前观察名单

| 公司/代码 | 趋势/Layer/环节 | 瓶颈评级 | 信号强度 | 市值 | PS | PE | 估值状态 | 核心催化剂 | 核心风险 | 当前动作 | 下次检查 |
|-----------|-----------------|----------|----------|------|----|----|----------|------------|----------|----------|----------|
| {{COMPANY_AND_CODE}} | {{BOTTLENECK_CONTEXT}} | {{BOTTLENECK_RATING}} | {{SIGNAL_STRENGTH}} | {{MARKET_CAP}} | {{PS}} | {{PE}} | {{VALUATION_STATUS}} | {{CATALYST}} | {{RISK}} | {{CURRENT_ACTION}} | {{NEXT_CHECK}} |

## 状态变更记录

| 日期 | 标的 | 旧状态 | 新状态 | 触发证据 | 后续动作 |
|------|------|--------|--------|----------|----------|
| {{DATE}} | {{ITEM}} | {{OLD_STATUS}} | {{NEW_STATUS}} | {{EVIDENCE}} | {{NEXT_ACTION}} |

## 监控日历与信息缺口

| 标的 | 指标/事件 | 阈值 | 来源 | 频率 | 缺口 |
|------|-----------|------|------|------|------|
| {{ITEM}} | {{MONITORING_ITEM}} | {{THRESHOLD}} | {{SOURCE}} | {{FREQUENCY}} | {{GAP}} |
