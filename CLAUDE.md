# AI Berkshire — 项目指令

## 项目概述

基于 Claude Code 的价值投资研究 Skill 合集。四大师框架：巴菲特、芒格、段永平、李录。
GitHub: xbtlin/ai-berkshire

## 项目结构

```
skills/          — 投研 Skill 定义（.md），复制到 ~/.claude/commands/ 使用
tools/           — 辅助工具（financial_rigor.py 精确计算、twstock_data.py 台股FinMind取数）
reports/         — 投资研究报告输出
assets/          — 图片等静态资源
```

## 报告目录结构

```
reports/
├── 00-ETF-LOF/              — 指数基金/主动基金/ETF/LOF 研报统一存放
├── 01-单公司分析/            — 单公司Pipeline研报（quality-screen→research→checklist→thesis等）
│   ├── 腾讯/                — 腾讯所有研究报告
│   │   ├── README.md
│   │   ├── 腾讯-quality-screen-20260408.md
│   │   ├── 腾讯-research-20260408.md
│   │   ├── 腾讯-checklist-20260408.md
│   │   ├── 腾讯-earnings-2025Q4.md
│   │   ├── 腾讯-thesis.md
│   │   └── ...
│   ├── 分众传媒/
│   ├── 双汇发展/
│   └── ...（共65+家公司）
├── AI产业研究/              — AI产业链全景研究（行业/主题报告）
├── 核电-industry-20260409.md — 行业报告放根目录
├── AI算力-funnel-20260509.md  — 漏斗筛选报告放根目录
├── portfolio-latest.md       — 组合报告放根目录
└── ...
```

**关键规则**：走Pipeline流程（quality-screen → investment-research → investment-checklist → investment-team → earnings-review → thesis-tracker → news-pulse）的单公司研报，**一律输出到 `reports/01-单公司分析/{公司名}/`**。

## 报告命名规范

### 单公司Pipeline研报（输出到 `reports/01-单公司分析/{公司名}/`）

| Skill | 文件命名格式 | 示例 |
|------|---------|------|
| /quality-screen | `{公司名}-quality-screen-{YYYYMMDD}.md` | `reports/01-单公司分析/分众传媒/分众传媒-quality-screen-20260818.md` |
| /investment-research | `{公司名}-research-{YYYYMMDD}.md` | `reports/01-单公司分析/腾讯/腾讯-research-20260408.md` |
| /investment-checklist | `{公司名}-checklist-{YYYYMMDD}.md` | `reports/01-单公司分析/腾讯/腾讯-checklist-20260408.md` |
| /investment-team | `{公司名}/` 目录内含4个视角+最终报告 | `reports/01-单公司分析/拼多多/最终报告.md` |
| /earnings-review | `{公司名}-earnings-{期间}.md` | `reports/01-单公司分析/腾讯/腾讯-earnings-2025Q4.md` |
| /thesis-tracker | `{公司名}-thesis.md`（长期维护） | `reports/01-单公司分析/腾讯/腾讯-thesis.md` |
| /news-pulse | `{公司名}-news-{YYYYMMDD}.md` | `reports/01-单公司分析/分众传媒/分众传媒-news-20260818.md` |
| /management-deep-dive | `{公司名}-management-{YYYYMMDD}.md` | `reports/01-单公司分析/腾讯/腾讯-management-20260409.md` |
| /private-company-research | `{公司名}-private-{YYYYMMDD}.md` | `reports/01-单公司分析/字节跳动/字节跳动-private-20260408.md` |

### 行业/主题/组合研报（输出到 `reports/` 根目录或专属目录）

| Skill | 文件命名格式 | 示例 |
|------|---------|------|
| /industry-research | `{行业名}-industry-{YYYYMMDD}.md`（根目录） | `reports/核电-industry-20260409.md` |
| /industry-funnel | `{行业名}-funnel-{YYYYMMDD}.md`（根目录） | `reports/AI算力-funnel-20260509.md` |
| /portfolio-review | `portfolio-latest.md`（根目录，持续更新） | `reports/portfolio-latest.md` |
| /index-fund-research | `{基金名}-indexfund-{YYYYMMDD}.md`（`reports/00-ETF-LOF/`） | `reports/00-ETF-LOF/华泰柏瑞沪深300ETF-indexfund-20260806.md` |
| /active-fund-research | `{基金名}-activefund-{YYYYMMDD}.md`（`reports/00-ETF-LOF/`） | `reports/00-ETF-LOF/易方达蓝筹精选-activefund-20260806.md` |

## /investment-team 文件结构

```
reports/01-单公司分析/{公司名}/
├── README.md                         — 研究框架概览+核心结论
├── 01-商业模式分析-段永平视角.md
├── 02-财务估值分析-巴菲特视角.md
├── 03-行业竞争分析-芒格视角.md
├── 04-风险管理层评估-李录视角.md
└── 最终报告.md                       — Team Lead 综合报告
```

## 投研分析核心原则（最高优先级）

- **客观、客观、客观**——所有投研分析必须基于事实和数据，严禁主观臆断
- 严格区分"事实"与"观点"：事实用数据支撑，观点必须明确标注为"观点"或"推测"
- **不预设立场**：不预设看多或看空，先摆数据、再推逻辑、最后得结论。结论必须从数据中自然推出
- 禁止使用"我认为"、"我觉得"、"显然"等主观表述，改用"数据显示"、"证据表明"、"根据XX来源"
- **呈现正反两面**：每个核心判断都必须附带反面论据（"但另一方面..."），让读者自己权衡
- 对不确定的事情诚实说"不确定"或"数据不足"，不要用推测填充确定性
- 所有skill（investment-team、investment-research、earnings-review等）在执行时都必须遵守以上原则

## 报告语言与风格

- 所有报告使用**中文**
- 风格：直接、犀利、不说废话
- 数据必须标注来源，关键数据至少2个来源交叉验证
- 估计值必须注明"估计"
- 评分使用★符号（★1-5），不含半星
- 穿插巴菲特/芒格/段永平/李录的语录点评

## 研报模板规范（templates/）

**所有 Skill 生成的研报必须参照 `templates/` 下的对应模板**：

- 模板定义了每种报告的**标准结构**（章节顺序、表格格式、评分体系）
- 生成报告时，按模板的 `{{PLACEHOLDER}}` 填入实际数据和分析
- 可以根据实际情况**增补章节**（如特殊行业需要额外分析），但不得**删减**模板中的核心章节
- **新报告类型**：如果遇到 `templates/` 中没有的报告类型，先按合理结构完成报告，然后将该报告的结构提炼为模板存入 `templates/`，并更新 `templates/README.md` 索引
- 模板文件清单见 [templates/README.md](templates/README.md)

## GitHub 操作

- 本地克隆路径：`~/ai-berkshire/`
- **双 remote 配置**：
  - `origin` = 自己的 fork `git@github.com:whiteihat/ai-berkshire.git`（**推送目标**）
  - `upstream` = 原仓库 `git@github.com:xbtlin/ai-berkshire.git`（**同步源**，经常有新提交）
- 推送前先 `git pull --rebase upstream main`（同步原仓库新提交）
- commit message 用中文，描述清楚改了什么
- 不要推送中间过程文件（如 data_collection.md），只推最终报告

## 常用命令

```bash
# 推送报告到GitHub
cd ~/ai-berkshire
git add reports/xxx.md
git commit -m "添加xxx报告"
git pull --rebase upstream main   # 同步原仓库新提交
git push origin main              # 推送到自己的 fork
```

## 注意事项

- 市值必须手算校验：股价 × 总股本，与报告市值对比
- 货币单位要明确（港币/人民币/美元/新台币），防止混淆
- PE/ROE等指标用 tools/financial_rigor.py 精确计算
- 台股数据用 tools/twstock_data.py（FinMind）获取，并按 skills/financial-data.md 台股章节交叉验证
- A股/港股/美股数据优先用 tools/tushare_data.py（ttshare 代理优先、官方 API 兜底；无权限接口按 skills/financial-data.md 对应市场来源退化），依赖用 `uv run` 调用
- 报告写完后主动询问是否推送到GitHub
