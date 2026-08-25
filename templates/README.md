# 研报模板库

本目录定义所有持久化研究报告的最终呈现结构。研究流程、数据获取和判断规则属于 `skills/`；模板只定义读者可见的章节、表格和占位符。

> **规则**：所有报告型 Skill 必须按 [报告路由规则](../.claude/rules/report-output.md) 指定的模板生成最终报告。模板目录不维护输出路径、文件名或路由信息；这些信息只在路由规则中维护。

## 模板清单

| 模板文件 | 对应 Skill | 用途 |
|---------|-----------|------|
| [quality-screen.md](quality-screen.md) | `/quality-screen` | 7 项去劣筛选 |
| [investment-research.md](investment-research.md) | `/investment-research` | 四大师投资研究 |
| [investment-checklist.md](investment-checklist.md) | `/investment-checklist` | 巴菲特买入前 Checklist |
| [investment-team.md](investment-team.md) | `/investment-team` | 四角色并行研究团队 |
| [earnings-review.md](earnings-review.md) | `/earnings-review` | 财报精读 |
| [earnings-team.md](earnings-team.md) | `/earnings-team` | 财报团队分析 |
| [thesis-tracker.md](thesis-tracker.md) | `/thesis-tracker` | 投资论文长期追踪 |
| [thesis-drift.md](thesis-drift.md) | `/thesis-drift` | 投资论文漂移检测 |
| [news-pulse.md](news-pulse.md) | `/news-pulse` | 新闻脉搏与异动归因 |
| [management-deep-dive.md](management-deep-dive.md) | `/management-deep-dive` | 管理层纵深研究 |
| [industry-research.md](industry-research.md) | `/industry-research` | 产业链全景研究 |
| [industry-funnel.md](industry-funnel.md) | `/industry-funnel` | 漏斗式筛选 |
| [index-fund-research.md](index-fund-research.md) | `/index-fund-research` | 指数基金研究 |
| [active-fund-research.md](active-fund-research.md) | `/active-fund-research` | 主动基金研究 |
| [income-investment.md](income-investment.md) | `/income-investment` | 收益型股票分析 |
| [portfolio-review.md](portfolio-review.md) | `/portfolio-review` | 投资组合审视 |
| [private-company-research.md](private-company-research.md) | `/private-company-research` | 未上市公司研究 |
| [bottleneck-hunter.md](bottleneck-hunter.md) | `/bottleneck-hunter` | 供应链瓶颈扫描与状态文件 |

## 通用格式规范

所有报告模板共享以下规范：

### 元数据头
每份报告必须包含以下结构化头部（字段含义见路由规则的"无实质更新则不落盘"条款）：

```
**创建时间**：YYYY-MM-DD HH:MM
**最后修改**：YYYY-MM-DD HH:MM
**数据截止**：YYYY-MM-DD
**报告版本**：1.0 | 1.1 …
**公司/基金/行业**：XXX（代码）
**数据来源**：[列出实际使用的数据源]
```

- **创建时间**：本报告首次生成时间。
- **最后修改**：快照型报告=创建同日；活文档（论文/组合/状态文件）=每次实质更新改写。
- **数据截止**：所引用数据的最新日期，与生成日区分——报告"研究日期"可能早于今日，但数据滞后要如实标注。
- **报告版本**：活文档用递增版本号（1.0→1.1…）配合 Git 历史；快照型固定 `1.0`，其"版本"由文件名 `-{YYYYMMDD}` 承担。

### AI 声明
所有研究型报告必须在正文开头包含 AI 研究偏见自觉/局限性声明，模板中统一使用占位符 `{{AI_BIAS_DECLARATION}}`，agent 填入实际评级（A/B/C）和偏见类型。

### 评分体系
| 适用场景 | 格式 | 说明 |
|---------|------|------|
| 能力/质量评估 | ★1-5 | ★ 不含半星，★5=卓越 |
| 通过/不通过 | ✅ / ❌ | 用于筛选、Checklist |
| 状态追踪 | 🟢正常 / 🟡关注 / 🔴预警 | 用于假设追踪、论文健康度 |
| 事件权重 | 🔴高 / 🟡中 / ⚪低 | 用于新闻归因、风险 |
| 信息质量 | A级 / B级 / C级 | 用于数据可得性 |

### 表格规范
- 所有表格使用 Markdown 格式
- 关键数据表格必须包含“判断”列
- 金额单位统一（人民币/港币/美元/新台币），在表格标题或首行标注
- 百分比保留 1 位小数，倍数保留 1 位小数
- 数据来源、币种与口径须在每个数据表格下方或正文标注；不做强制双源比对。主源取数与合理性校验按 `.claude/skills/financial-data/SKILL.md` 执行。

### 引用规范
- 四大师语录用 `>` blockquote 格式
- 数据来源标注在表格下方或正文括号内
- 估计值必须注明"估计"
