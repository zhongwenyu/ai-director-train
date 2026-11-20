---
name: hit-short-drama
description: >-
  Generates high-retention AI short drama outlines (40-120 episodes floating) and
  continuous multi-episode screenplay arcs (1.5-2.5 min per episode) from a 1-sentence
  or simple creative brief. Grounded in empirical Hongguo hit pacing (median 5.56 episodes
  per complete dramatic event, 90.1% Ep 1 setup, 62.2% cross-episode same-scene next-second
  continuation). Uses isolated `agy` (`gemini-4-carbon-medium`) sub-agents with screen-stripped
  causal & pacing verification (`strip_to_screen.py` + `pacing_arena_judge.py`).
---

# 爆款 AI 短剧全链路连载编剧 Skill (`hit-short-drama v5`)

本 Skill 基于红果 **142 部 / 6,968 集** 真实爆款实证规律（见 `corpus/pacing_event_span_report.md`）自回归训练而成，彻底根治「把多集剧情快进塞成一集提纲、前因后果与人物关系没讲清、前世今生时间线悖论」三大通病。

## 核心实证铁律：3～6 集共同承载 1 个完整戏剧事件！

- **1 集根本承载不了 1 个完整戏剧事件**：红果爆款平均每 **`5.56 集`** 才走完 1 个完整的戏剧阶段（50 集仅约 9 个大事件）。
- **前 3 集连载分工**：
  - **第 1 集（`setup` 设局蓄压，占 90.1%）**：演明前世/过往痛点，回到核心现场把每个人物的称谓关系（爸/叔/师兄/厂长）自然叫响，把对方的虚伪画饼或步步紧逼铺足，**停在主角刺破假面的第一句反问或紧绷抉择瞬间原场切集**；
  - **第 2 集（原场下一秒无缝续接，占 62.2%）**：同一现场紧接第 1 集下一秒，层层剥开私情与旧账、收回底牌当众决裂、逼反派暴露误判底牌，主角抽身踏出大门遇新转机切集；
  - **第 3 集（谈透困局立军令状·迎击首波封锁）**：紧接第 2 集结尾，把新阵地为何同遭核心反派打压说清，主角亲口提出双向对赌军令状立据，正面接下反派首波封锁并亮出破局绝活，悬置第 4～5 集的大决战！

## 核心脚本与隔离审查工具（全链路固定 `agy gemini-4-carbon-medium` 隔离子 Agent）

| 路径 | 作用 |
| --- | --- |
| [stage0_premise_lock.md](./prompts/stage0_premise_lock.md) | **Stage 0.5 跨集连载与因果分叉立项锁**：锁死 5 集事件跨度、前世今生分叉方程与理性对赌底牌 |
| [stage1_outline.md](./prompts/stage1_outline.md) | **Stage 1 全剧分阶段引擎与连载细纲**：每阶段 4～6 集，相邻集标注原场续接切点 |
| [stage2_episodes.md](./prompts/stage2_episodes.md) | **Stage 2 慢工细活分集剧本**：每集 22～34 句活人大白话短句，前情关系 100% 清晰 |
| [strip_to_screen.py](./scripts/strip_to_screen.py) | **去作者化屏幕实况剥离器**：剥离 `**人物**` 偷渡名单，显式标记旁人听不见的 `[VO]`，统计未交代称谓与哑巴主角 |
| [script_check.py](./scripts/script_check.py) | **确定性反快进与屏幕清晰度体检**：拦截 `<18句` 快进提纲、未叫清身份角色与哑巴主角 |
| [write_drama.py](./scripts/write_drama.py) | **一键全链路生成与隔离审查重构闭环**：`一句话创意 -> 立项锁 -> 连载大纲 -> 分集剧本 -> 屏幕实况节奏与因果门禁` |
