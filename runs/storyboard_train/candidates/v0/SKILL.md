---
name: hit-storyboard
description: >-
  Transforms AI short drama screenplays into director-grade, AI-video-ready
  storyboards with purposeful camera movement choreography, 180-degree spatial
  axis locks, 5-15s integer generation groups, and zero-memory group-seam
  anchors. Activate when splitting scripts into shot lists, storyboards, or
  designing camera movements for AI short dramas.
---

# 爆款 AI 短剧导演分镜与运镜调度 Skill (`hit-storyboard`)

本 Skill 基于 **166 部、7,670 集红果真实爆款 AI 短剧逆向分镜实证规律** 与跨模型对抗进化训练而成，将定稿分集剧本拆解为 **兼具导演运镜张力与 AI 视频模型（H3 / Seedance / Kling）高稳定可拍性** 的双层结构化分镜表（`剪辑子镜 1.5–6.0s` + `生成组 5–15 整数秒`）。

## 目录与必读参考

| 路径 | 职责 |
| --- | --- |
| [camera-choreography.md](./references/camera-choreography.md) | **核心必读**：12%–25% 承重拍运镜铁律、移动镜四要素、固定镜留白、八大叙事运镜与严禁复合运镜规范 |
| [grouping-and-continuity.md](./references/grouping-and-continuity.md) | **核心必读**：5–15s 整数生成组划分、180°轴线与机位编码、三手法六式切镜、跨组末态与首帧静态锚点 |
| [storyboard-anti-patterns.md](./references/storyboard-anti-patterns.md) | **核心必读**：十大典型 AI 分镜病灶（监控死机位、全集乱推炫技、跨组同机位跳切、吞字超载）正负改写 |
| [examples/](./examples/) | 提纯自真实红果爆款原片实拍调度的标准 14 列分镜示范 |
| [write_storyboard.py](./scripts/write_storyboard.py) | 并发调用 `agy (gemini-4-carbon-low)` 按集拆解分镜并自动执行物理体检 |
| [storyboard_check.py](./scripts/storyboard_check.py) | 确定性物理体检脚本（校验14列完整度、5–15s生成组守恒、语速容量、运镜合规、轴线与台词零漏拆） |

---

## 标准导演拆镜四步法

### Step 1：通读定稿剧本，锁定画幅、资产与承重拍
1. 确认本集画幅（默认 `9:16 竖屏`，若项目指定 `16:9 横屏` 则按横向三分构图设计）与角色/场景/核心道具编码（如 `CHR-叶寻`、`SCN-试菜厅`、`PRP-确认书`）。
2. 先标出本集 **4～6 个叙事承重拍**（前5秒反差钩子、权力换手/施压拍、关键底牌物证揭晓、决绝离场/关系断裂、集尾悬停定格）——**主动运镜优先且精准投放于此，拒绝在平庸寒暄过场里乱动摄影机**。

### Step 2：逐场建立空间轴线，拆解剪辑子镜并合成 5–15s 生成组
1. 每场开头必须写出三行场头台账：**场景与光影锚点**、**180°主轴线与站位（左A右B）**、**本场时长与生成组数**。
2. 按 **约 15～18 镜/分钟（均镜长 ASL 3.2～4.2 秒）** 的爆款呼吸密度拆解剪辑子镜（`1.5s–6.0s`，`0.5s` 精度），紧致景别（近景/中近景/特写/过肩）占 **70% 以上**，全景严格控制在 **10% 以内**。
3. 将**同一场内**连续的 2～5 个剪辑子镜合成为 **5～15 整数秒生成组**（对话交锋组优先 `10–14s` 容纳完整“出招—接招—微反应”，单动作冲击或集尾钩子可用 `5–8s` 短组；严禁跨场建组、严禁一句台词跨组硬劈）。

### Step 3：逐组落定【组末态与首帧静态锚点】
AI 视频模型每组零记忆：每个生成组表格下方（或组末）必须写出具体可拍的 **`> 【组 X-X-XX 末态与下组首帧锚点】`**（写明下组首帧静态画面主体位置姿态 + 本组结束冻结画面 + 跨组换机位/跳景别接缝式别，严禁写“严格继承上镜”空话）。

### Step 4：物理体检与交付
运行确定性检查脚本确保 0 硬性错误：
```bash
python3 skills/hit-storyboard/scripts/storyboard_check.py <分镜表.md> --screenplay <原剧本.md>
```
