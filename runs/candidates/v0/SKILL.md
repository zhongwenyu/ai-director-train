---
name: hit-short-drama
description: >-
  Generates high-retention AI short drama outlines (40-120 episodes floating) and
  screenplay episodes (1-3 minutes floating per episode, ~2 min average) from a
  simple creative brief (1 sentence to 500 words). Activate when the user asks to
  create, plan, outline, or write engaging AI short drama / playlet scripts.
---

# 爆款 AI 短剧全链路编剧 Skill (`hit-short-drama`)

本 Skill 将一段 **简单创意（一句话～500字）** 转化为 **40～120 集长线高留存大纲** 与 **单集 1～3 分钟浮动（均值约 2 分钟）的高吸引力分集剧本**。核心目标是最大化真实观众的 **前 5 秒停留率、中段信息差爽感与集尾“非点下一集不可”的断章成瘾度**。

## 目录结构与按需参考

| 路径 | 作用 |
| --- | --- |
| [story-engine.md](./references/story-engine.md) | **必读（大纲阶段）**：信息差矩阵、人物欲望底色、40–120 集波浪升级阶梯与付费卡点法则 |
| [playbooks.md](./references/playbooks.md) | **必读（两阶段）**：都市逆袭/情感、年代乡村致富、古装权谋穿越、脑洞系统四大赛道专属打法 |
| [episode-craft.md](./references/episode-craft.md) | **必读（剧本阶段）**：1–3 分钟动态配速、5 类自然开场抓手、活人潜台词交锋、爽点四拍与断章切点 |
| [anti-patterns.md](./references/anti-patterns.md) | **必读（剧本阶段）**：严禁出现的 AI 八股病灶（独处报数字、路人广播腔、生硬假推搡）正负对照 |
| [examples/](./examples/) | 提纯自真实红果爆款原片的标准创作态剧本切片（按题材参考，学习呼吸感与人物交锋） |
| [write_drama.py](./scripts/write_drama.py) | 端到端或分步调用 `agy (gemini-4-carbon-low)` 生成大纲、滚动批次剧本与 `state_ledger.json` |
| [script_check.py](./scripts/script_check.py) | 物理底线体检脚本（按真实短剧语速估算单集时长、检查集尾完整度与明显 AI 病灶） |

---

## 标准三阶创作流程

### Stage 1：简单创意 → 全剧故事引擎与分卷大纲 (`01_outline.md`)

1. 阅读 [story-engine.md](./references/story-engine.md) 与 [playbooks.md](./references/playbooks.md) 中对应赛道的策略。
2. 根据创意体量与冲突层级，确定 **全剧最佳总集数（40～120 集浮动）**：
   - 单线情感反击 / 快节奏家庭清算：**40～60 集**
   - 双线逆袭（事业/身份升级 + 感情拉扯）：**60～85 集**
   - 长线年代致富 / 朝堂权谋 / 系统横推多地图：**80～120 集**
3. 输出 `01_outline.md`，必须包含：
   - **剧名、赛道、总集数定位与核心爽感一句话钩子**
   - **核心信息差矩阵**（观众全知视角知道什么、主角手握什么底牌、反派因何盲目自信而不断误判）
   - **核心人物档案**（不超过 6 名核心角色：身份反差、真实欲望、软肋、**说话底色与口语习惯**）
   - **全剧 4～6 卷长程升级阶梯**（明确每卷集数区间、地图/对手升级、第 10–13 集免费转付费大卡点、中段身份反转与终局结算）
   - **逐集钩子细纲表**（先展开目标生成区间，或分卷展开全部集数）：每集列明 `集号 | 建议时长(60-180s浮动) | 开场前5秒抓手 | 核心筹码/关系位移 | 爽点或情绪峰值 | 集尾最后一秒断章悬念`。

### Stage 2：滚动窗口分集剧本精写 (`episodes/epXXX-YYY.md` + `state_ledger.json`)

1. 阅读 [episode-craft.md](./references/episode-craft.md)、[anti-patterns.md](./references/anti-patterns.md) 及 [examples/](./examples/) 中同赛道示范。
2. **按批次滚动精写（每批建议 3～5 集）**：
   - 单集时长根据本集戏剧容量在 **60～180 秒（1～3 分钟）自然浮动**，全剧均值控制在 **110～135 秒（约 2 分钟）**。快刀反转集可紧凑至 75–95 秒，重头对峙/大场面集可舒展至 140–180 秒，**绝不为凑时长灌水说车轱辘话**。
   - 写第 $N$ 批时，必须读取上一批剧本末尾与 `state_ledger.json`（记录已公开秘密、当前筹码归属、人物关系温度、待回收伏笔），第 $N$ 批首集前 5 秒无缝咬住上一批集尾定格画面！
3. 每批写完后更新 `state_ledger.json`，供下一批续写，保证写满 40～120 集不吃书、不原地踏步。

### Stage 3：轻量体检与观众留存自审

运行物理体检脚本验证格式与时长区间：

```bash
python3 skills/hit-short-drama/scripts/script_check.py <分集剧本.md>
```

或使用一键驱动脚本执行从创意到大纲再到分集剧本的自动化流水线：

```bash
python3 skills/hit-short-drama/scripts/write_drama.py \
  --idea-file idea.txt \
  --out-dir output/my_drama \
  --episodes 1-5
```
