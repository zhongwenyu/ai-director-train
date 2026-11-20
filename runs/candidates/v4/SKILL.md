---
name: hit-short-drama
description: >-
  Generates high-retention AI short drama outlines (40-120 episodes floating) and
  screenplay episodes (1-3 minutes floating per episode, ~2 min average) from an
  ultra-short 1-sentence or simple creative brief. Enforces Stage 0.5 Premise
  Common-Sense & Zero-Detour Dopamine Lock, ultra-crisp human speech (<=28 chars avg),
  and an isolated cross-family Mobile Viewer Swipe-Away Hard Gate (`audience_agent.py`).
---

# 爆款 AI 短剧全链路编剧 Skill (`hit-short-drama v4`)

本 Skill 将 **一句话极简创意（50字～500字）** 转化为 **人设常识自洽、主线零跑偏、台词短促如刀** 的 **40～120 集长线大纲** 与 **单集 1.5～2.5 分钟高留存分集剧本**。

## 目录结构与核心模块

| 路径 | 作用 |
| --- | --- |
| [stage0_premise_lock.md](./prompts/stage0_premise_lock.md) | **Stage 0.5 立项锁（必过首关）**：动笔前焊死「身份—行为常识自洽」「反派同源危机」「前三集零路人支线」「盟友痛快信任零内耗」 |
| [story-engine.md](./references/story-engine.md) | **大纲引擎法则**：信息差矩阵、人物欲望底色、40–120 集波浪升级阶梯与付费卡点法则 |
| [playbooks.md](./references/playbooks.md) | **四大赛道打法**：都市逆袭/情感、年代致富、古装穿越、脑洞系统 |
| [episode-craft.md](./references/episode-craft.md) | **分集精写工艺**：活人短句交锋（句均 14–25 字）、信息差 `[VO]` 运用、集尾未决钩子 |
| [anti-patterns.md](./references/anti-patterns.md) | **16 大 AI 病灶红线**：含「985学生无故当厨工」「第2集路人恶霸水戏」「救场后盟友审讯添堵」「口播财务报表」正负对照 |
| [audience_agent.py](./scripts/audience_agent.py) | **校准认证的零上下文手机小白观众 Agent**：物理隔离大纲，按每 20 秒模拟真实观众弹幕与划走弃剧（`BINGE_NEXT` vs `SWIPE_AWAY`），支持正反换位双盲 PK |
| [script_check.py](./scripts/script_check.py) | **物理节奏硬门禁**：单集时长 `<=175s`、句均字数 `<=28字`、单句上限 `<=56字` |
| [write_drama.py](./scripts/write_drama.py) | **一键全链路驱动**：`一句话创意 -> Stage 0.5 立项锁 -> Stage 1 大纲 -> Stage 2 分集剧本 -> Stage 3 观众划走模拟打回重构闭环` |

---

## 标准四阶创作流程

1. **Stage 0.5：立项常识与爽点锁（`00_premise_lock.json`）**
   - 严禁给亲手干底层手艺活的主角强贴割裂的名校在读生标签；
   - 第 2 集盟友危机必须直接由第 1 集核心反派打压造成，严禁编造手伤巧合或临时工勒索；
   - 前 3 集火力 100% 锁定核心仇人，盟友痛快信任、绝不搞救场后冷脸审讯内耗。
2. **Stage 1：全剧故事引擎与分集大纲（`01_outline.md`）**
   - 严格继承 `00_premise_lock.json`，杜绝未演前史偷渡、时间线瞬移与多数字流水账。
3. **Stage 2：短句高能分集剧本（`episodes/epXXX-YYY.md`）**
   - 台词像真人在吵架/办事（句均 14～25 字，单句不超过 52 字），用单一刺眼锚点替代口播财务账本。
4. **Stage 3：物理体检 + 隔离手机观众划走门禁（Hard Gate）**
   ```bash
   python3 skills/hit-short-drama/scripts/script_check.py output/my_drama/combined_1-3.md
   python3 skills/hit-short-drama/scripts/audience_agent.py output/my_drama/combined_1-3.md --episodes 1-3
   ```
   任一集触发 `SWIPE_AWAY` 立即从源头重构桥段，直至全集 `BINGE_NEXT`（`0` 弃剧槽点）。
