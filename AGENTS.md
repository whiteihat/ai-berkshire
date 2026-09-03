# AI Berkshire — Codex 项目指令

本仓库同时支持 Claude Code 与 Codex。研究工作流的唯一正文源是
`.claude/skills/*/SKILL.md`；Codex 入口 `.agents/skills/*/SKILL.md` 只是由同步脚本生成的薄适配层，不要在其中复制或维护完整 workflow。

## 开始工作前

- 执行研究、写报告或修改仓库前，按任务需要读取 `.claude/rules/` 中的 canonical 规则：
  `repository-safety.md`、`research-quality.md`、`report-output.md`；修改 skill 或模板时再读取 `skill-authoring.md`。
- 研究“最新/当前”信息前确认系统日期，并在持久化报告中标明数据截止日期。
- 所有 Python 工具、同步脚本和测试必须使用项目 uv 环境，例如 `uv run python tools/data_loader.py ...`；不要调用系统级 `python3`。
- 标准库回归测试使用 `uv run python -m unittest discover -s tools -p '*_test.py'`；依赖 pytest 的测试模块使用 `uv run pytest ...`。

## Claude workflow 在 Codex 中的适配

- `$ARGUMENTS` 表示当前 Codex 请求及其参数；先读取对应的 `.claude/skills/<name>/SKILL.md` 再执行。
- 源文件中的 `/skill-name` 是 workflow 名称；在 Codex 中优先使用 `$skill-name`，或直接读取对应 skill。
- `Bash`、`Read`、`Write` 分别对应 Codex 的 shell、读取和编辑能力。
- `WebSearch`、`WebFetch` 使用 Codex 当前可用的联网搜索或浏览能力；不可用时必须明确标注资料缺口，不得用训练记忆伪装联网结果。
- `Task`、`TeamCreate`、`TeamDelete`、`run_in_background` 是 Claude 编排语法。有 Codex 子代理能力时可并行执行；没有时按角色顺序执行，并如实说明没有并行。
- `.claude/settings.local.json` 的 WebSearch 权限预检只适用于 Claude Code，不是 Codex 的前置条件；遵守当前 Codex 的 sandbox 与审批设置。

## Single source of truth

- 财务数据规范、研究质量、报告路由和仓库安全规则只维护在 `.claude/rules/` 或 canonical skill 中。
- 报告模板、共享工具和报告目录由两种客户端直接共用。
- 不创建 `codex-skills/`、`codex-prompts/`、`AGENT.md` 或项目级 `.codex/` 配置来复制已有规则。
- 新增或修改 skill 后，在仓库根目录运行 `uv run python scripts/sync-codex-skill-adapters.py`；删除或改名 skill 时加 `--prune` 清理旧 wrapper，再运行 `--check`；不要手工编辑生成的 wrapper。
