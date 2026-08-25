# 报告输出与路由

本文件是所有持久化报告的模板与输出路径唯一维护点。报告写入前，先读取 [模板目录说明](../../templates/README.md) 和本表指定的模板；不要在 Skill 或模板索引中重复维护路由、文件名或输出目录。

## 路由表

| 研究类型                    | Skill                        | 模板                                      | 输出路径                                                                                                                                     |
| --------------------------- | ---------------------------- | ----------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------- |
| 单公司 Pipeline（深度研究） | `investment-research`      | `templates/investment-research.md`      | `reports/01-单公司分析/{公司名}/{公司名}-research-{YYYYMMDD}.md`                                                                           |
| 单公司 Pipeline（团队研究） | `investment-team`          | `templates/investment-team.md`          | `reports/01-单公司分析/{公司名}/`，包含四个视角文件和 `最终报告.md`                                                                      |
| 单公司 Pipeline（私营公司） | `private-company-research` | `templates/private-company-research.md` | `reports/01-单公司分析/{公司名}/{公司名}-private-{YYYYMMDD}.md`                                                                            |
| 行业研究                    | `industry-research`        | `templates/industry-research.md`        | `reports/02-行业分析/{行业名}-industry-{YYYYMMDD}.md`                                                                                      |
| 行业漏斗/筛选               | `industry-funnel`          | `templates/industry-funnel.md`          | `reports/02-行业分析/{行业名}-funnel-{YYYYMMDD}.md`                                                                                        |
| 质量筛选                    | `quality-screen`           | `templates/quality-screen.md`           | `reports/01-单公司分析/{公司名}/{公司名}-quality-screen-{YYYYMMDD}.md`（批量筛选时使用 `reports/{筛选名}-quality-screen-{YYYYMMDD}.md`） |
| 管理层深度研究              | `management-deep-dive`     | `templates/management-deep-dive.md`     | `reports/01-单公司分析/{公司名}/{公司名}-management-{YYYYMMDD}.md`                                                                         |
| 财报研读                    | `earnings-review`          | `templates/earnings-review.md`          | `reports/01-单公司分析/{公司名}/{公司名}-earnings-{期间}.md`                                                                               |
| 财报团队                    | `earnings-team`            | `templates/earnings-team.md`            | `reports/01-单公司分析/{公司名}/` 下保存底稿、视角稿、评审稿和最终稿                                                                       |
| 新闻脉冲                    | `news-pulse`               | `templates/news-pulse.md`               | `reports/01-单公司分析/{公司名}/{公司名}-news-{YYYYMMDD}.md`                                                                               |
| 主动基金研究                | `active-fund-research`     | `templates/active-fund-research.md`     | `reports/00-ETF-LOF/{基金名}-activefund-{YYYYMMDD}.md`                                                                                     |
| 指数基金研究                | `index-fund-research`      | `templates/index-fund-research.md`      | `reports/00-ETF-LOF/{基金名}-indexfund-{YYYYMMDD}.md`                                                                                      |
| 投资检查清单                | `investment-checklist`     | `templates/investment-checklist.md`     | `reports/01-单公司分析/{公司名}/{公司名}-checklist-{YYYYMMDD}.md`；多公司时逐公司写入各自目录，并可另存比较表                              |
| 组合回顾                    | `portfolio-review`         | `templates/portfolio-review.md`         | `reports/portfolio-latest.md`（持续更新）                                                                                                  |
| 论文追踪                    | `thesis-tracker`           | `templates/thesis-tracker.md`           | `reports/01-单公司分析/{公司名}/{公司名}-thesis.md`（长期维护；追踪快照放同目录）                                                          |
| 论文漂移                    | `thesis-drift`             | `templates/thesis-drift.md`              | `reports/01-单公司分析/{公司名}/{公司名}-thesis-drift-{YYYYMMDD}.md`                                                                       |
| 收益投资                    | `income-investment`        | `templates/income-investment.md`         | `reports/01-单公司分析/{公司名}/{公司名}-income-investment-{YYYYMMDD}.md`                                                                  |
| 瓶颈猎手                    | `bottleneck-hunter`        | `templates/bottleneck-hunter.md`（完整扫描、快报、总地图、观察名单变体） | `reports/bottleneck-map/`（总地图、观察名单和按日扫描） |

## 通用路由规则

- **研报生成硬原则**：任何流水线（`stock-pipeline` / `fund-pipeline`）中被执行的阶段 Skill，除数据准备和纯数据核验步骤外，都必须按本表路由路径落盘一份持久化研报；**未落盘不视为阶段完成**，编排 Skill 有责任在阶段结束后核对产出文件存在且非空（见两个 pipeline Skill 的"每阶段准出检查"）。数据不足导致跳过不算"执行"。
- **无实质更新则不落盘**：若同一对象当日已存在对应报告，且本轮无实质输入变化（无新财报、无显著价格变化、论文未漂移、数据截止日未变），视为"无实质更新"，不生成新文件、不改写已有文件，仅在阶段结果中注明"沿用 N 日前报告"。生成新报告时必须更新元数据头中的"最后修改"字段，将"创建时间"保持不变。
- `{YYYYMMDD}` 使用报告生成日；`{期间}` 使用财报期间，例如 `2025Q4`。
- `{公司名}`、`{基金名}`、`{行业名}` 和 `{标的名}` 先做安全化：去除路径分隔符、控制字符和会改变路径的 `..`；保留中文、英文、数字、空格、连字符和下划线。
- 同一对象同一日期已有报告时，默认创建草稿/新版本名或先询问，不覆盖已有文件。
- 报告正文应包含信息丰富度评级与 AI 局限性声明；结尾区分 AI 分析置信度和投资确定性（模板已有时按模板落地）。
- `reports/` 是发布产物目录；工具原始输出、抽检清单、临时下载文件写入 `tmp/` 或 `local/`，不混入发布目录。
- `bottleneck-hunter` 的完整扫描、标的快报、信号快报、总地图和观察名单均在 `reports/bottleneck-map/` 下维护；日内扫描使用 `{YYYY-MM-DD}/HH-MM-标的代码或信号扫描.md`，无新发现时不生成报告。
