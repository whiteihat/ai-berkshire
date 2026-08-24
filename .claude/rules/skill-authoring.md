---
paths:
  - ".claude/skills/**/*.md"
  - "templates/**/*.md"
---

# Skill 与模板维护规则

- 本项目只在仓库内运行；不得复制、安装或分发 `.claude/skills/*/SKILL.md` 到 Claude Code 的全局 commands 目录。
- `.claude/skills/*/SKILL.md` 只定义研究流程、取证标准、分析判断、协作分工与准出要求；不得定义最终报告的章节、表格、占位符、模板路径、输出目录或文件命名。
- 所有持久化报告的模板和路由只在 `.claude/rules/report-output.md` 维护。Skill 在生成报告前必须读取该规则及其中指定的模板。
- `templates/*.md` 只定义最终报告的读者可见结构、表格和占位符；不得重复研究流程、工具调用、数据获取方式、输出路径或文件名。
- 研究型 Skill 必须引用 `.claude/skills/financial-data/SKILL.md` 的数据规范；不要在多个 Skill 中维护相互矛盾的数据源优先级。
- 新增或改变报告类型时，必须同时新增/更新模板、路由表和模板索引；只有任务明确要求新增报告类型时才创建新模板。
- 固定本机路径或个人 remote 不得作为工作流的隐含依赖。变更 workflow/文档时，不重写历史报告；修改前确认目标不是用户已有的未提交成果。
