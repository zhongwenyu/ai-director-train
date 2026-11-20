# AI 短剧剧本与导演分镜双 Skill 自回归训练工程 (`ai-director-train`)

本仓库基于红果真实爆款 AI 短剧逆向语料（只读引用 `/home/zhongwenyu/project/ai-director-workstation/videos/红果AI短剧_800部_前50集/`，已覆盖 **166 部短剧、7,670 集有效样本**），采用**异族模型对抗自回归进化（`agy gemini-4-carbon-low` 生成 × `codex gpt-6.1-sol / medium` 评审与正反换位双盲竞技场）**训练出两套全独立 Antigravity 核心技能，并完成了 60 集长篇短剧《重回2005：撤回秘方后我带青梅沸腾全国》的全本剧本与全剧 60 集导演分镜实战验证。

---

## 一、两大训练成果 Skill 导航

| Skill 名称 | 路径 | 冠军版本 | 职责与核心能力 |
| --- | --- | :---: | --- |
| **`hit-short-drama`** | `.agents/skills/hit-short-drama/` | `v3` | `简单创意（一句话～500字） → 40～120集长线故事引擎大纲 → 单集1～3分钟滚动分集剧本` |
| **`hit-storyboard`** | `.agents/skills/hit-storyboard/` | `v2` | `定稿剧本 → 双层导演分镜表（1.5–6.0s剪辑子镜 + 5–15s整数生成组 + 四要素运镜调度 + 180°空间轴线 + 零记忆组间静态锚点）` |

### 快速调用命令

```bash
# 1. 生成大纲与分集剧本
python3 /home/zhongwenyu/project/ai-director-train/skills/hit-short-drama/scripts/write_drama.py \
  --idea-file idea.txt --out-dir runs/my_drama --episodes 1-12

# 2. 剧本物理体检
python3 /home/zhongwenyu/project/ai-director-train/skills/hit-short-drama/scripts/script_check.py \
  runs/my_drama/combined_1-12.md

# 3. 并发生成双层导演分镜（含运镜调度与5-15s生成组）
python3 /home/zhongwenyu/project/ai-director-train/skills/hit-storyboard/scripts/write_storyboard.py \
  --screenplay runs/my_drama/combined_1-12.md --out-dir runs/my_drama/storyboards --workers 4

# 4. 分镜与运镜确定性体检（核验14列、5-15s组守恒、语速窗口、运镜合规与台词100%覆盖）
python3 /home/zhongwenyu/project/ai-director-train/skills/hit-storyboard/scripts/storyboard_check.py \
  runs/my_drama/storyboards/combined_storyboard_1-12.md --screenplay runs/my_drama/combined_1-12.md
```

---

## 二、训练与未见测试集正反双盲战报总览

### 1. 编剧 Skill (`hit-short-drama v3`)
- **进化曲线**：`v0 (55.81)` → `v1 (59.00, 4胜0负)` → `v2 (单点虚高但双盲1胜2负被拦截回退)` → **`v3 (61.69, 3胜1负夺冠)`**。
- **未见测试集终局盲测**：
  - 对比同模型无 Skill 直出：**`3 战 3 胜`**（单集均分净增 **`+9.0 分`**）。
  - 同题正反换位双盲 PK 对比 Claude Code 最新 `r28`（《085》第1集）：**`62.0` vs `48.0`（大胜 `+14.0 分`）**。

### 2. 导演分镜与运镜 Skill (`hit-storyboard v2`)
- **7,670 集爆款运镜实证规律**（`corpus/storyboard_stats_report.md`）：每分钟切镜中位数 `15.99 镜/分`（均镜长 ASL `3.75s`），紧致景别占 `73.78%`（全景仅 `8.93%`），主动运镜中位数 `12.5%`（前推 `33.3%`、跟拍横移 `20.4%`、震颤 `14.2%`、摇摄 `14.0%`、后拉 `13.7%`）。
- **进化曲线**：Step 0 真爆款实拍盲测校准 `2 胜 1 平 0 负` → `v0 (65.25)` → `v1 (58.75, 拦截回退)` → **`v2 (66.75, 运镜均分 18.75/25, 正反双盲 3 胜 0 负 1 平夺冠)`**。
- **未见测试集终局盲测（`6 战 6 胜` 全满贯）**：
  - 对比无 Skill 直出：**`3 战 3 胜`**（`71.0 vs 49.0`、`68.0 vs 49.0`、`64.0 vs 45.0`）。
  - 同题正反换位双盲 PK 对比 Claude Code `drama-s4-shotlist`：**`3 战 3 胜`**（`71.0 vs 60.0`、`68.0 vs 61.0`、`64.0 vs 60.0`）！

---

## 三、全流程实战项目：《重回2005：撤回秘方后我带青梅沸腾全国》（全 60 集）

位于 `productions/2005_chongqing_hotpot/`：
- `01_outline.md`：60集五卷完整故事引擎与大纲（`codex` 终审 **`76.0 分`**）
- `02_assets_ledger.md`：统一角色（`CHR-*`）、场景机位（`SCN-*`）、叙事道具（`PRP-*`）编码圣经
- `combined_1-60.md`（及 `episodes/`）：**全剧 60 集完整定稿剧本**（60/60 集 `PASS`，0 错误 0 警告 0 时代穿帮）
- `storyboards/combined_storyboard_1-60.md`（及 `storyboards/ep001.md` ～ `ep060.md`）：**全剧 60 集双层结构化导演分镜总表**（共 **1,458 个子镜、518 个 5–15s 整数秒生成组**，总成片时长 **100.1 分钟**，ASL `4.12s`，主动运镜率 `21.6%`，60/60 集 `storyboard_check.py` **全绿 PASS**；关键集 `codex` 二审高达 **`68.0 ～ 73.0 分`**，运镜单项最高 **`21/25`**）
- `reviews/`：全部 `codex (gpt-6.1-sol / medium)` 初审与终审 JSON 审计报告
