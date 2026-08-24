# AI Berkshire 项目指令

AI Berkshire 是一套仅在本仓库内由 Claude Code 执行的价值投资研究工作流。`.claude/skills/` 是 Claude Code 发现的项目本地 Skill（唯一工作流源），`templates/` 定义最终报告结构，`.claude/rules/report-output.md` 是模板与输出路径的唯一维护点，`reports/` 存放研究产出。

## 不可省略的规则

- 研究报告使用中文。将**事实**、**观点/分析判断**、**估计/假设**与**数据不足**明确区分；不得把推测写成事实。
- 重大结论应给出证据来源、最强反证与会改变结论的条件。数据不足时如实说明，不以套话填充确定性。
- 决策敏感财务数据须按 [财务数据规范](.claude/skills/financial-data/SKILL.md) 交叉验证；金额必须标明币种和单位；市值、估值、比例等计算使用 `tools/financial_rigor.py`，不得以心算替代。
- 所有持久化报告必须遵守 [报告路由规则](.claude/rules/report-output.md)；写作前读取匹配的 [模板](templates/README.md)。不得覆盖或迁移旧报告，除非用户明确要求。
- 不得提交或披露密钥、Token、`local/`、私人组合/账本或中间资料。未经用户明确要求，不执行 commit、push、破坏性删除或改写 Git 历史；Git 操作前先检查当前工作树和实际 remote。

## 规则与文档导航

自动加载的项目规则位于 [`.claude/rules/`](.claude/rules/)：

- [研究质量](.claude/rules/research-quality.md)
- [报告路由](.claude/rules/report-output.md)
- [仓库安全](.claude/rules/repository-safety.md)
- [Skill 维护](.claude/rules/skill-authoring.md)

面向使用者的安装、运行、工具与排障说明见 [运行指南](docs/运行指南.md)。数据源优先级、口径、误差阈值与退化路径以 [财务数据规范](.claude/skills/financial-data/SKILL.md) 为准。
