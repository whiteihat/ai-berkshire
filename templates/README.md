# 研报模板库

本目录包含所有投研 Skill 生成报告的标准模板。Agent 在生成报告时应参照对应模板的结构和格式，确保跨公司、跨时间的阅读一致性。

## 模板清单

| 模板文件 | 对应 Skill | 用途 | 文件命名 |
|---------|-----------|------|---------|
| [quality-screen.md](quality-screen.md) | `/quality-screen` | 7项去劣筛选 | `{公司名}-quality-screen-{YYYYMMDD}.md` |
| [investment-research.md](investment-research.md) | `/investment-research` | 四大师投资研究 | `{公司名}-research-{YYYYMMDD}.md` |
| [investment-checklist.md](investment-checklist.md) | `/investment-checklist` | 巴菲特买入前Checklist | `{公司名}-checklist-{YYYYMMDD}.md` |
| [investment-team.md](investment-team.md) | `/investment-team` | 四角色并行研究团队 | `{公司名}/` 目录（4个视角+最终报告） |
| [earnings-review.md](earnings-review.md) | `/earnings-review` | 财报精读 | `{公司名}-earnings-{期间}.md` |
| [earnings-team.md](earnings-team.md) | `/earnings-team` | 财报团队分析 | `{公司名}/` 目录（底稿+评审+公众号） |
| [thesis-tracker.md](thesis-tracker.md) | `/thesis-tracker` | 投资论文（长期维护） | `{公司名}-thesis.md` |
| [news-pulse.md](news-pulse.md) | `/news-pulse` | 新闻脉搏 | `{公司名}-news-{YYYYMMDD}.md` |
| [management-deep-dive.md](management-deep-dive.md) | `/management-deep-dive` | 管理层纵深研究 | `{公司名}-management-{YYYYMMDD}.md` |
| [industry-research.md](industry-research.md) | `/industry-research` | 产业链全景研究 | `{行业名}-industry-{YYYYMMDD}.md` |
| [industry-funnel.md](industry-funnel.md) | `/industry-funnel` | 漏斗式筛选 | `{行业名}-funnel-{YYYYMMDD}.md` |
| [index-fund-research.md](index-fund-research.md) | `/index-fund-research` | 指数基金研究 | `{基金名}-indexfund-{YYYYMMDD}.md` |
| [active-fund-research.md](active-fund-research.md) | `/active-fund-research` | 主动基金研究 | `{基金名}-activefund-{YYYYMMDD}.md` |
| [portfolio-review.md](portfolio-review.md) | `/portfolio-review` | 投资组合审视 | `portfolio-latest.md` |
| [private-company-research.md](private-company-research.md) | `/private-company-research` | 未上市公司研究 | `{公司名}-private-{YYYYMMDD}.md` |

## 通用格式规范

所有报告模板共享以下规范：

### 元数据头
每份报告必须包含：
```
**研究/报告日期**：YYYY年MM月DD日
**公司/基金/行业**：XXX（代码）
**数据来源**：[列出实际使用的数据源]
```

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
- 关键数据表格必须包含"判断"列
- 金额单位统一（人民币/港币/美元/新台币），在表格标题或首行标注
- 百分比保留1位小数，倍数保留1位小数

### 引用规范
- 四大师语录用 `>` blockquote 格式
- 数据来源标注在表格下方或正文括号内
- 估计值必须注明"估计"
