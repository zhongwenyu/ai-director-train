---
name: hit-short-drama
description: >-
  Generates high-retention AI short drama outlines (40-80 episodes floating) and
  continuous multi-episode screenplay arcs (1.5-2.5 min per episode) across ANY genre
  (urban, era/rural, ancient, fantasy/system, sci-fi/apocalypse, suspense, light comedy)
  and ANY seed granularity (1-sentence seed or multi-paragraph creative brief). Grounded
  in a zero-overfitting 4-step First-Principles Derivation Chain (World & Character Stakes
  -> Core Conflict & Retention Hook -> Escalating Action & State-Shift Dynamics -> Serial
  Outline & Episodes) + Stage 2.5 Colloquial Dialogue Doctor (`dialogue-voice.md`).
  Powered 100% by context-isolated `agy` (`gemini-4-carbon-medium`) sub-agents (`zero codex`).
---

# 爆款 AI 短剧全赛道第一性连载编剧 Skill (`hit-short-drama v7`)

本 Skill 基于红果 **142 部 / 6,968 集** 多题材真实爆款实证规律，经**三层信息论物理隔离防过拟合自回归引擎**（去剧情抽象瓶颈 → 盲态元进化器 → 独立反过拟合检察官）在「全剧戏剧张力」与「纯对白听感图灵」双竞技场联合进化而成。

## 核心架构：零过拟合四步第一性推导链 + Stage 2.5 盲听台词医生

1. **Stage 0 第一性叙事推导与原创意保真立项锁（`00_premise_lock.json`）**：
   - 正向因果推导：`① 原创意事实锚点保真 + 处境规则与人物欲求/底线` → `② 核心矛盾与追更情绪驱动力` → `③ 可见筹码反差与跨场实质变局机制（无封闭节奏枚举，严禁原地复读吵架）` → `④ 开局首阶段单事件边界与前 3 集逐级换挡规划`。
2. **Stage 1 精炼故事引擎与逐级变局大纲（`01_outline.md`）**：
   - 约 `4～6 集` 承载一个完整阶段事件，以可拍可见的视听行动推进翻转，严控分角色有限知情边界与全局连续性台账。
3. **Stage 2 高张力连载分集剧本（`episodes/epXXX-YYY.draft.md`）**：
   - 用具体视听行动推着对白走，每集 `1～3` 场、`24～34` 句对话，集集产生不可逆态势位移，集尾切在结果未决的紧绷临界点。
4. **Stage 2.5 真人口语与潜台词剧本医生（`episodes/epXXX-YYY.md`）**：
   - 锁死场次骨架与剧情事实不变，按「心智阅历 × 社会处境 × 当下生理情绪」三维动态声纹击碎对称双分句、剥离设定播报与掉书袋术语，还原参差呼吸、抢断吞吐与冰山潜台词。
5. **Stage 3 双维独立盲审门禁**：
   - 确定性体检（`script_check.py`）+ 全赛道四维张力盲审（`general_arena_judge.py`）+ 纯对白盲听图灵裁判（`dialogue_turing_judge.py`）。

## 核心模块索引

| 路径 | 作用 |
| --- | --- |
| [stage0_premise_lock.md](./prompts/stage0_premise_lock.md) | **Stage 0 第一性四步正向推导与原创意锚点立项锁** |
| [stage1_outline.md](./prompts/stage1_outline.md) | **Stage 1 具象行动驱动与分角色知情台账分集大纲** |
| [stage2_episodes.md](./prompts/stage2_episodes.md) | **Stage 2 视听行动推进与跨场实质变局分集剧本** |
| [stage2_5_dialogue_polish.md](./prompts/stage2_5_dialogue_polish.md) | **Stage 2.5 盲听去匠气真人口语与潜台词剧本医生** |
| [dialogue-voice.md](./references/dialogue-voice.md) | **三维动态声纹、参差呼吸节律与冰山潜台词通用法则** |
| [episode-craft.md](./references/episode-craft.md) | **分集交锋工艺、音画分工与时长卡点规范** |
| [anti-patterns.md](./references/anti-patterns.md) | **24 类跨赛道短剧常见病灶正负对照表** |
| [general_arena_judge.py](./scripts/general_arena_judge.py) | **全赛道四维戏剧张力盲审与正反换位对抗裁判** |
| [dialogue_turing_judge.py](./scripts/dialogue_turing_judge.py) | **去动作纯对白剥离与盲听图灵换位对抗裁判** |
| [write_drama.py](./scripts/write_drama.py) | **一键全链路生成驱动（`Stage 0 -> 1 -> 2 -> 2.5 -> Gate`）** |
