---
paths:
  - "skills/**/*.md"
  - "templates/**/*.md"
  - "scripts/install-claude-commands.*"
---

# Skill 与文档维护规则

- `skills/*.md` 是 Claude Code 工作流源文件。修改 Skill 后，不存在需要同步的兼容层或生成物。
- 任何会持久化报告的 Skill 必须使用 `.claude/rules/report-output.md` 的路由，并在自身的“输出要求”中写出完整、可执行的仓库相对路径；不得保留与该路由冲突的 `~/...` 或旧根目录路径。单独安装后无法读取仓库规则时，Skill 内的完整路径是运行时兜底。
- 研究型 Skill 必须引用 `skills/financial-data.md` 的数据规范和匹配模板；不要在多个 Skill 中维护相互矛盾的数据源优先级。
- 新增或改变报告类型时，同时登记路由、模板和准出流程；只有任务明确要求新增报告类型时，才创建模板并更新模板索引。
- 固定本机路径或个人 remote 不得作为工作流的隐含依赖；安装脚本和 Skill 应基于当前仓库根目录和共享规则工作。
- 变更只影响 workflow/文档时，不重写历史报告；修改前先确认目标不是用户已有的未提交成果。
