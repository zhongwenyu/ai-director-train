---
name: hit-short-drama
description: >-
  Generates high-retention AI short drama outlines (40-120 episodes floating) and
  continuous multi-episode screenplay arcs (1.5-2.5 min per episode) across ANY genre
  (urban, era/rural, ancient, fantasy/system, sci-fi/apocalypse, suspense) and ANY seed
  granularity (1-sentence seed or multi-paragraph creative brief). Preserves explicit seed
  identities/relationships/arcs (`seed_explicit_invariants`), enforces timepoint-specific
  character motivation sanity (`timepoint_motivation_map`), amplifies native interpersonal
  & emotional tension without dry accounting/legal filler, and grounds serial pacing in
  empirical Hongguo hit rhythm (~4-6 episodes per complete dramatic event). Powered 100%
  by context-isolated `agy` (`gemini-4-carbon-medium`) sub-agents (`write_drama.py` +
  `general_arena_judge.py`).
---

# 爆款 AI 短剧全赛道通用连载编剧 Skill (`hit-short-drama v6`)

本 Skill 基于红果 **142 部 / 6,968 集** 多题材真实爆款实证规律与跨赛道正反双盲对抗自回归进化而成，兼容 **一句话极简种子** 与 **多段式原创故事梗概**，覆盖都市情感、年代乡村、古装穿越、玄幻系统、末世科幻等全赛道。

## 四大泛化黄金准则（零套路绑架 · 零题材过拟合）

1. **原创意锚点 100% 保真（`seed_explicit_invariants`）**：
   - 用户明确给出的人物身份、核心人物关系、关键路线对照与终局爽点必须原汁原味保留并戏剧化放大，绝不用外部套路模板篡改主角身份或丢弃原创意的感情/对照副线；若仅给一句话极简种子，则顺应其原生世界观自然补齐鲜活人物与关系网。
2. **分时动机与人性渐变自洽（`timepoint_motivation_map`）**：
   - 严守每个时间节点（`T=0` 开局、中期拉扯、后期反转）的认知边界与人性心理惯性（如习以为常的傲慢赌气 → 短期虚假甜头膨胀 → 好面子硬撑加注 → 彻底崩盘悔恨），杜绝时间线悖论、未卜先知、读心术接话与无脑降智送人头。
3. **高浓度人情博弈与原生情绪兑现（`native_emotional_payoff_arc`）**：
   - 聚焦人与人之间的利益错位、情感失衡、体面拉扯、护短立威与预期反转；严禁把短剧大纲或台词写成枯燥的财税法务审计说明书。
4. **从容多集连载节奏（`~4–6 集` 共载 1 个完整事件）**：
   - 遵循红果爆款实证规律（中位 `5.56 集` 走完一个完整阶段事件，`90.1%` 首集蓄压立局，`62.2%` 跨集原场无缝续接），每集 `20～28` 句鲜活口语对白+精炼 `[VO]` 心声，把人物关系称谓与当期算计演透，集尾卡在紧绷未决的悬念钩子处。

## 核心脚本与隔离审查工具（全链路固定 `agy gemini-4-carbon-medium` 隔离子 Agent）

| 路径 | 作用 |
| --- | --- |
| [stage0_premise_lock.md](./prompts/stage0_premise_lock.md) | **Stage 0 原创意锚点保真与分时动机立项锁**：提炼不可篡改事实锚点、分时动机曲线、原生情绪弧线与首阶段多集连载规划 |
| [stage1_outline.md](./prompts/stage1_outline.md) | **Stage 1 全剧故事引擎与连载细纲**：每阶段 4～6 集，双线/多线交织递进，杜绝枯燥审计流水账 |
| [stage2_episodes.md](./prompts/stage2_episodes.md) | **Stage 2 高张力从容连载分集剧本**：每集 20～28 句自然口语短句 + 恰当气口 `[VO]`，裸看关系 100% 清晰 |
| [strip_to_screen.py](./scripts/strip_to_screen.py) | **去作者化屏幕实况剥离器**：剥离 `**人物**` 偷渡设定行，显式标记旁人听不见的 `[VO]`，核验裸看清晰度 |
| [script_check.py](./scripts/script_check.py) | **确定性时长、句长与屏幕清晰度体检**：拦截快进提纲、超长书面腔、未交代称谓角色与哑巴主角 |
| [general_arena_judge.py](./scripts/general_arena_judge.py) | **全赛道四维通用盲审与正反换位对抗裁判**：从原味保真、分时动机、情绪张力、连载节奏四维独立盲审及双盲 PK |
| [write_drama.py](./scripts/write_drama.py) | **一键全链路生成与隔离审查重构闭环**：`任意粒度创意 -> 立项锁 -> 连载大纲 -> 分集剧本 -> 四维通用盲审门禁` |
