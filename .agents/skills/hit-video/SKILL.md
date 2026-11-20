---
name: hit-video
description: 短剧多模态音视频一体生成技能（MiniMax H3 Pika / Pika-H3-Flex 专用生产版）。支持 480p 快速验证与 512p/768p 成片交付：强制提交前将所有输入参考图等比压缩至不大于 1K（≤1024px，保留项目库 2K 原图不变），多人同框场景先行生成占位关键帧锁定 180° 轴线与空间关系，视频提示词严格剔除一切人物外貌/发型/年龄/服装描述（100% 依赖参考图还原角色形象与服装），绑定角色 ≤3 秒音色参考音频与画外音双轨分离（vo_split），并通过多模态逐镜观感审片闭环持续迭代直到成片具备强吸引力与高一致性。
---

# 爆款短剧视频生成技能（hit-video · MiniMax H3 Pika 生产版）

本技能吸收导演工作台 `minimax-h3-video`、`h3-prompt-writing`、`drama-s4-keyframe`、`drama-s5-firstframe`、`drama-s5-prompt`、`drama-s5-take-score` 与 `agy-video-understand` 的核心经验，针对 **MiniMax H3 Pika（`Pika-H3-Flex`，6 步 LCM 音视频同生）** 建立标准化生产与质检闭环。

---

## 一、五条铁律（Hard Invariants）

1. **输入图片强制 `≤ 1K` 预压缩（项目资产库保留 2K 原图）**
   - 项目资产库（`studio_media`）中的人物五格图、正面基准图、场景图、道具图保持 **2K 原生高清**，绝不覆盖降质。
   - **提交给视频模型（`Pika-H3-Flex`）的每一张图片**（包括占位关键帧、人物五格参考图、场景图、道具图）必须在本地缓存目录先行按原比例 Lanczos 等比压缩至 **最长边 `≤ 1024px`（`1K`）**，严禁拉伸或裁切。
2. **提示词零人物形象/服装描述（Zero Appearance Text Rule）**
   - 视频提示词（`subject_definitions`、`summary`、`retention_analysis`、`detailed_description`）中 **严禁出现任何关于人物五官、年龄段、发型长短颜色、衣服款式颜色材质、鞋帽配饰的文字描述**！
   - 若上游剧本或分镜表残留旧服装描述（如“白总厨服”“高顶白厨帽”“花连衣裙”“格子衬衫”等），编译提示词与关键帧时 **必须彻底剥离**；若物理动作涉及旧服装特有部件（如“摘下白厨帽”），必须归口改写为通用肢体动作或绑定道具交互，让视频模型 **100% 依赖输入的参考图（`<Picture N>`）决定人物长相与穿着**。
3. **关键帧先行与“初始在场集（Initial Presence）”推导法则**
   - 凡同组存在多人空间交互或复杂起始构图的镜头组，先用“场景图 + `t=0.0s` 实际在场人物 `#front` 单人正面图（+ 关键道具图）”生成同画幅占位关键帧。
   - **严守跨镜时空连续性（杜绝人物瞬移）**：决定关键帧画哪几个人、站什么位置前，必须先核对上一镜末态与本镜动作链——**凡在剧情时间轴 `t > 0s` 才从画外迈步入画、推门进入或赶来介入的角色，严禁提前画进 `t = 0.0s` 首帧关键帧**！首帧只定格 `t = 0.0s` 已经在场的角色与初始态势，让介入者在视频生成中真实入画（而新入画角色的外貌与服装仍通过 `<Picture K>` 五格参考图精准锁定）。
   - 生成关键帧时 **只传人物 `#front` 单人正面图，严禁传人物五格拼图**（避免带入五格白边或无头躯干），且提示词同样不写具体衣服款式，只写保持对应参考图人物五官、发型与整套服装完全一致；出图后看图核验通过再压缩至 `≤ 1024px` 送入视频模型。
4. **画外音（VO/OS）代入感承载与双轨隔离（Voice Reference + `vo_split`）**
   - 每个开口说话或发心声的角色，必须挂载其绑定的 `≤ 3.0s` 干净原声样本作为 `reference_audio`（`<Audio 1>`～`<Audio 3>`），并与 `<Subject N> (Sx)` 精确绑定。
   - **主动核查叙事可理解度与代入感缺口**：由于视频生成阶段剥离了易乱码的 `[画面文字]` 花字，编译前若发现上游剧本把关键时空跨度、隐秘物证含义、人物心境转折或暗藏底牌单押在静音动作或未压制的字幕条上导致观众费解，应在回馈剧本/分镜层补充自然的第一人称 `[VO/OS]` 心声（音画互补，讲潜台词与认知判断，不复述表面动作）。
   - 画内同步台词原封不动写入 `<d>[Chinese] 原文</d>`，常态语速控制在 **≤ 5.5 字/秒**，严禁截断句尾。**`<d>...</d>` 纯净台词铁律：`<d>[Chinese] ... </d>` 标签内部只能放纯粹要念出口的中文台词原文，严禁在 `<d>` 内写 `(角色名 in Picture N speaks...):` 或中文冒号人名前缀**（否则模型会把括号里的中文角色名当成台词念出来！说话人 `<Subject N> (S1)` 与情绪语气描述必须写在 `<d>` 标签外部的英文引导句中）。
   - **所有内心独白（OS）、旁白、画外音（VO）严禁直接送入主画面生成**（否则画面人物会对口型把心声念出来）：主画面用 `prompt_novo`（人物嘴唇紧闭静默）在 5090 生成 `480p`，同时在 4070 `Pika-H3-Flex` 生成 `368p` 含 VO 版：
     - **情况 1（VO 落在露脸镜头）**：采用 `demucs_duck` 模式——经 Spark Demucs 提取人声并增益 `1.8x`，同时将主画面在该时间窗内的环境底噪自动压限至 `0.38x`（Ducking），防止宽频环境噪掩盖尾音；
     - **情况 2（VO 落在手部/物件特写等无嘴部入画子镜）**：采用 `splice_window` / `raw_slice` 模式——直接将 `368p` 原生干净语音切片在该子镜时间窗内通过交叉淡化无缝拼入主音轨，100% 保留人声气口与环境声融合度，避免宽频雨声等触发 Demucs 吞擦音；
     - **精准定位反漂移法则（`place_vo_segments` 短片段独立采音）**：当多子镜长镜头（11–15 秒）中 VO 位于中后段切镜时，整条 `368p` 多镜同生易出现切点漂移（挤占前序同步对白或贴边截断尾字）。此时优先单独生成 `5–7 秒` 纯净单镜 `368p` VO 干声条，测出实际语音起止 `[src_start, src_end]` 后用 `pika_runner.place_vo_segments()` 按毫秒级目标起点 `dst_start` 定点落位，实现零串音、零截尾。
   - **高烈度物理受创的“逼近—结果”蒙太奇法则（通用反柔化律）**：视频扩散模型对“高速冲击源与完整人体同框受创”（车撞、坠落、重击、气浪等）有强物理平滑与安全规避先验，同框全景直拍极易退化为“冲击源停住、人物自己松手退步”的假动作。凡此类高烈度受创戏，一律拆为 **① 冲击源扑面逼近 + 面部惊骇反应的极近景** 与 **② 硬切受创后的地面/局部结果态特写**（如人物已倒卧不起、无力垂落的手臂、脱手砸落的随身物），让物理受创结果在第二镜起始态即已成立，彻底杜绝假摔退步。
5. **先 `480p` 实拍验证，多模态逐镜审片迭代**
   - 首轮统一使用 **`Pika-H3-Flex` `480p`**（竖屏 `9:16` 为 `480×832`，横屏 `16:9` 为 `832×480`，6 步 LCM）生成。
   - 每条成片必须提取带精确秒点的关键帧序列拼板 + 完整音轨核验（调用多模态看片/`agy-video-understand`），从 **剧情动作、运镜切镜、人物五官与服装一致性、音色与口型同步、场景道具稳定性、观众爽感与钩子张力** 六大维度逐镜质检；发现共性缺陷先升级本技能规则与提示词模板，再重抽缺陷镜头。
6. **背景音（`audio-library`）与双层字幕分离存储铁律（保障下游无损高清化）**
   - **严禁将字幕/花字烧录进镜头视频或整集合成 MP4，严禁将跨镜背景配乐硬混入单镜视频音轨**：单镜 `shot.videoId` 后续需送入 Spark `LTX` 做 2× 高清化（烧录文字经扩散超分会产生笔画扭曲伪影，单镜硬混配乐会导致重抽或替换单镜时音乐断层）。
   - **标准后制流程（`scripts/post_bgm_subtitles.py`）**：
     1) **情绪分段选曲**：按场次情绪弧线从 `audio-library` 检索纯器乐曲目（先听审验证无抢戏人声），支持冲击静音留白（如撞击前骤停配乐）与悬念尾拍对齐（`align_end: true` 让鼓点渐强精准卡在集尾最后一秒），并对所有对白/心声区间自动施加包络闪避（Ducking `0.36x`），输出与成片等长的独立 `bgm.mp3`；
     2) **三态精准字幕轨**：基于 `ffprobe` 逐镜实测时长零漂移累加偏移量（`bgmOffset`），同步编译顶部花字条（`caption`，承接 `[画面文字]`）、底部同步台词（`dialogue`）与底部心声标签（`vo`），输出标准 `.vtt` 与结构化字幕数组；
     3) **工作台音画分离联播**：将独立 `bgmMediaId`、`subtitleMediaId`（`.vtt`）及结构化 `subtitles` 分别绑定至剧集与各分镜，后台播放器自动同步联播配乐与双层字幕，而底层视频流始终保持 100% 纯净可超分。
7. **按切镜类型分级守恒与整集连播切点验收（3-Tier Transition Continuity Gate）**
   - **不能把“首帧承接上一镜末态”一刀切套用到所有镜头**，必须按剪辑学把相邻分镜切点分为三类分别约束：
     1) **类型 A｜同场零时差连续切（Same-Scene Continuous Cut，`Δt ≈ 0s`，同空间连贯对话/动作）**：此时才执行严格的**上一镜末态继承 + 本镜核心动作前态（Pre-Action）**——桌面既有道具状态不能丢（如刚扔进凉水壶的碎纸必须还在），本镜台词触发的动作不能在 `t = 0.0s` 提前做完（杜绝“人已经坐进三轮车斗里才开口问明早怎么办”“单据不掏就凭空铺满桌”的因果倒置），并在上一镜末尾 `1.0s` 留出顺接动作（Match-on-Action）。
     2) **类型 B｜邻接空间动线切 / 同场微省略切（Adjacent-Space Motion Cut or Micro-Ellipsis，`Δt ≈ 1–30s`）**：空间转移时（如走出林记大门 → 跨过 6 米老街进对门夏记），首帧不继承上一镜室内陈设，只守恒**人物服装/手持物状态与运动方向矢量**，并用 `[Shot 1]` 拍出地理方位桥；同场微省略时（如迎客后切到桌前“字已写完、正沾印泥准备摁红手印”以跳过枯燥写字过程），允许省略冗余中间过程，只需保留“摁手印”这一核心戏剧动作本身的前态。
     3) **类型 C｜异场平行切 / 跨时空省略切（Cross-Scene Parallel Cut or Time Ellipsis，`Δt = 数分钟～次日`，如夜里骑三轮出发 → 次日清晨大锅已在熬油，或夏记门前 → 平行切入林记后厨）**：**严禁机械套用上一镜末态或强迫从零铺垫动作**！此类转场应遵循短剧快节奏叙事，在 `t = 0.0s` **直接切入新场景已展开的戏剧态势（In-Medias-Res）**，靠昼夜光线、门头/环境特征或顶部 `[画面文字]` 字幕条快速定向，仅需保证**该新镜头内部自身**不发生“未说先做”的因果倒置即可。
   - **整集连播切点审查硬关卡（Full-Episode Stitched Transition Audit）**：整集合成后运行 `scripts/check_transitions.py` 生成切点对照拼板，并将合成后的**完整整集 MP4** 输入多模态审片连播核验：对类型 A 查动作/道具跳切与因果倒置，对类型 B 查空间方位可理解度，对类型 C 查时空转换是否干脆利落。
8. **同场定场母图（Scene Master Plate）中心辐射法、Spark `MiniMax H3 Image` 首帧编辑契约与三维控制边界**
   - **严禁盲目用“上一镜 480p 尾帧”链式生成下一镜首帧**：当上一镜停在单人特写或局部过肩镜（背景已被浅景深裁掉），把 `480p` 尾帧喂给生图模型猜下一镜中全景时，模型丢失全局三维房间坐标，极易发生 **180° 越轴翻转、方桌变圆桌、吧台左右颠倒** 以及分辨率与肤质逐镜劣化（链式误差累积）。仅当相邻两镜机位高度重合且上一镜尾帧完整包含全局空间刚体时，尾帧才可作为辅助状态参考。
   - **标准架构：「2K 同场定场母图中心辐射（Hub-and-Spoke）+ 离散状态增量编辑 + `<Picture 2>` 组内锁空间」**：
     1) **建立同场定场母图（Scene Master Plate）**：每个连续场次（及重大刚体状态切换点，如撕毁图纸后、交接核心信物后）先在 **Spark `MiniMax H3 Image`**（`scripts/spark_h3_image.py`）生成 1 张高分辨率全景/中全景定场母图，一次性锁死房间建筑结构、核心家具几何（圆桌 vs 方桌、吧台在左 vs 在右、门框朝向）、光影方向与在场人物 180° 轴线坐标；
     2) **母图中心辐射派生各组首帧（Spark `MiniMax H3 Image` 三段式编辑提示词）**：同场所有分镜组的 `t = 0.0s` 首帧关键帧，一律以**定场母图作为 `<Picture 1>`**、人物 `#front` 单人正面图作为 `<Picture 2..K>`，遵循官方三段式连续英文提示词——① `<Subject N>` 自然绑定 `<Picture K>`；② `The target image shows ...` 加上显式守恒子句（`<Subject 1> is partially preserved; keep the exact table geometry, wall layout, and lighting...`）；③ 仅描述新机位景别与离散增量状态（如背包位于长凳上、某道具已被移除），不冗余复述已守恒背景；
     3) **视频生成组内双图锁死空间（`<Picture 1>` 首帧 + `<Picture 2>` 定场母图）**：当单条生成组内含 `[Shot 2..4]` 切镜（尤其 `[Shot 1]` 是人物特写、`[Shot 2]` 拉回多人同框或走廊/门口全景）时，必须在 `ref_images` 中将 **`<Picture 1>` 设为本组首帧**、**`<Picture 2>` 设为同场定场母图（或目标切镜空间母图，`≤1K`）**，防止组内切镜时模型凭空捏造陌生走廊、餐桌变形或站姿变坐姿。
   - **3D 预演（Blender）与视频控制的客观工程边界**：
     - **严禁将 Blender 灰白泥模/白模渲染视频直接塞入 `Ref2VA` 的 `reference_video`（`<Video k>`）**：`MiniMaxH3ReferenceToVideo` 的 `<Video k>` 走 Video VAE 全注意力语义/外观参考而非像素级空间网格锁，喂入灰白无纹理白模会导致严重的**灰塑料材质贴皮污染**且无法逐帧硬锁机位。
     - **何时启用 `Fun ControlNet Union`（Tier-2 重武器兜底）**：90% 的短剧室内外对手戏与动作交接靠「定场母图 + `<Picture 2>` 双图锚定」即可高保真锁死空间并保留细腻真人微表情与手指交互；仅当遇到 **360° 复杂环绕长镜头或 5 人以上高难度武打/走位调度** 时，才用 3D/Blender 导出标准 **`Z-Depth` 深度序列或 `OpenPose` 彩骨序列**（绝非灰白模渲染图），接入 `MiniMaxH3FunControlNetApply`（控制强度 `0.6–0.8` 并在末段适度释放以兼顾 `Ref2VA` 面部微表情与原生口型）。

---

## 二、参考素材编排契约（Ref2VA 顺序与映射）

每个生成组（5–15 整数秒）统一采用 `Ref2VA`（六字段全参考模式），参考图最多 9 张，参考音频最多 3 段：

1. **参考图上传顺序（`<Picture 1>` … `<Picture K>`，全部预先压缩至 `≤ 1024px`）**：
   - **情况 A（首镜 `[Shot 1]` 即为多人同框或需像素级锁起点）**：
     - `<Picture 1>`：本组 `[Shot 1]` 的起始占位关键帧（`first frame of [Shot 1]`）。
     - `<Picture 2..M>`：本组全体出镜人物的 **五格主图**（供后续切镜 `[Shot 2]`、`[Shot 3]` 切换机位或新人物入画时保持多角度服装与五官一致）。
     - `<Picture M+1>`：本场场景主图。
     - `<Picture M+2..>`：本组关键道具图（按需）。
   - **情况 B（首镜 `[Shot 1]` 为手部/道具特写，`[Shot 2]` 切入多人同框，如签字夺纸后切三人/四人同框）**：
     - `<Picture 1>`：`[Shot 2]` 的多人占位关键帧（在 `subject_definitions` 中声明 `<Picture 1> is the composition and blocking keyframe for [Shot 2]`，不在 `[Shot 1]` 强行套用）。
     - `<Picture 2..M>`：本组出镜人物五格主图。
     - `<Picture M+1>`：场景主图；`<Picture M+2..>`：关键道具图。
   - **情况 C（单人独角戏且空间动作跨度大，如雨夜街头行走被车灯刺入）**：
     - 可选配首帧关键帧，或直接传 `<Picture 1>` 人物五格主图 + `<Picture 2>` 场景主图，给足镜头调度弹性。

2. **六字段零外貌描述模板（Ref2VA Strict Zero-Appearance Template）**：

```text
subject_definitions:
<Picture 1> is the first frame of [Shot 1], locking the initial camera framing, lighting, and spatial blocking of the characters in the room.
<Subject 1> is the person from <Picture 2>, strictly preserving the exact facial features, hairstyle, and complete outfit from <Picture 2> without any modification.
<Subject 2> is the person from <Picture 3>, strictly preserving the exact facial features, hairstyle, and complete outfit from <Picture 3> without any modification.
<Subject 3> is the interior room from <Picture 4>, preserving its architectural layout, furniture geometry, and lighting atmosphere.
<Subject 4> is the document prop from <Picture 5>, preserving its paper structure and proportion without inventing readable text overlays.
All character reference sheets (<Picture 2>, <Picture 3>) provide 3D identity and outfit guidance only; never copy their white studio background or multi-panel borders into the video.
<Audio 1> is the voice-timbre reference for <Subject 1> (S1).
<Audio 2> is the voice-timbre reference for <Subject 2> (S2).

summary:
[keyframe completion + reference generation + audio reference] In <Subject 3>, starting from <Picture 1>, <Subject 1> and <Subject 2> confront each other across the table across three cuts, following <Audio 1> and <Audio 2> for vocal timbre.

retention_analysis:
<Picture 1> ([Shot 1] first frame): fully_preserved - [Shot 1] starts directly from <Picture 1>'s framing, lighting, and subject positions.
<Subject 1> (appears in [Shot 1], [Shot 2], [Shot 3]): fully_preserved - exact face, hair, and outfit from <Picture 2> are maintained across all cuts.
<Subject 2> (appears in [Shot 1], [Shot 2], [Shot 3]): fully_preserved - exact face, hair, and outfit from <Picture 3> are maintained across all cuts.
<Subject 3> (appears in [Shot 1], [Shot 2], [Shot 3]): fully_preserved - room geometry, table height, and lighting direction remain consistent across cuts.
<Subject 4> (appears in [Shot 1]): fully_preserved - prop shape and placement remain consistent.
<Audio 1>: reference - <Subject 1> follows <Audio 1>'s voice timbre without copying the source recording.
<Audio 2>: reference - <Subject 2> follows <Audio 2>'s voice timbre without copying the source recording.

detailed_description:
The target video is shot in bright, crisp, high-contrast live-action cinema quality with natural skin texture, realistic fabric folds, accurate 35mm-50mm lens depth of field, and clear facial lighting; no CG look, no plastic skin filter, no text overlays or subtitles.
[Shot 1] Starting from <Picture 1>, a medium two-shot at eye level frames <Subject 1> standing on screen-left facing screen-right beside the marble table, and <Subject 2> standing on screen-right facing screen-left...
[Shot 2] At 00:03.500, the camera cuts to a close over-the-shoulder shot from the same side of the 180-degree axis, with <Subject 2>'s blurred shoulder on the right foreground and <Subject 1> on the left-center facing screen-right...

overall_soundscape:
...

non_diegetic_music:
N/A
```

---

## 三、写实运动、镜头与短剧张力编译细则

1. **杜绝慢动作词汇**：除非导演稿明确要求升格慢镜，严禁使用 `slowly`、`gently`、`softly`、`gracefully`、`calmly`、`drifts`、`glides`。一律使用 `at natural real-time speed`、`briskly`、`decisively`、`firmly`、`in 0.6 seconds` 等明确时间窗与真实物理受力词。
2. **切镜必重写空间站位（严守 180° 轴线，零服装复述）**：
   - 每次 `[Shot k] At 00:SS.mmm, the camera cuts to ...` 必须写明新镜头的景别、机位角度、`from the same side of the 180-degree axis`，并用 `<Subject N>` + **画面左右方位（`on screen-left` / `on screen-right`）+ 场景刚体锚点（`beside the copper hotpot` / `in front of the wooden door`）** 重新锚定每个在场人物的位置与朝向。
   - **切镜重申人物时同样不写任何衣服或发型词**，只用 `<Subject N> (keeping the exact appearance from <Picture M>)`！
3. **短剧情绪分拍外化与听话人反应**：
   - 短剧黄金前三集必须抓人眼球：说话人写清 2–3 拍可见面部与肢体变化（如 `eyes widen sharply, jaw clenches, slams palm onto the table edge`），严禁写 `slight`、`subtle`、`tiny`。
   - 多人同框时，必须明确指定谁在动嘴说话（`<Subject 1> (S1), standing on screen-left, speaks at a brisk, emotionally charged pace: <d>[Chinese] ...</d> His lips move clearly with the complete line`），同时写明画面内听话人的非语言反应与闭口状态（`while <Subject 2> on screen-right narrows his eyes with lips closed`），防止台词串嘴！
   - **前置道具动作并发化、句尾余量与急喊防多嘴胡话锁（双向时间窗铁律）**：
     1) **防截断（过短）**：H3 Pika 遇到“先做多步道具动作再开口”会串行耗掉 `1.2–1.7s` 导致句尾被切；因此开口前动作必须与发声并发（`As <Subject N> sets the spoon down, he immediately speaks...`），常态语速按 `4.8–5.0 字/秒` 计，末镜预留 `0.8–1.0s` 余量。
     2) **防多嘴胡言乱语（过长）**：紧急奔跑报信、情绪爆发怒吼（`shouts urgently / breathlessly`）实际语速高达 **`5.6–6.0 字/秒`**（如 26 字急喊仅需 `4.4 秒`）！若说话子镜在说完整句后仍停留在该人物近景超过 `1.2 秒`，模型极易让演员继续张嘴胡乱编造乱码台词！因此急喊子镜必须按 `字数 / 5.6 + 0.8s` 收紧切点，并在 `<d>` 后紧跟闭口硬锁：*`Immediately upon finishing the sentence, <Subject N> presses his lips shut and pants silently without uttering another sound`*，随即切入对手反应镜。
   - **无意滑落道具禁写“展示”倾向**：若剧情是“口袋里的单据无意滑落而本人未察觉”，切忌在滑落镜对单据做 `fully_preserved` 大篇幅形态展开描述（否则模型会让角色双手掏出单据对着镜头微笑展示）；滑落镜只写“折角白纸从兜口擦落出下画框，本人视线始终看着对手毫不知情”，把完整单据形态留给下一镜地面特写。
4. **人体与桌椅物理比例锁**：
   - 有餐桌/会议桌的场景，显式写明标准桌高约 75cm：坐姿人物桌沿在其腰腹肚脐高度，双肩与完整上半身清晰露在桌面之上；站姿人物桌沿在其大腿上部高度，严禁把坐姿人物画成只露一颗头在桌面边缘。
5. **不画叠字字幕**：
   - 分镜备注里的 `[画面文字]`（如年代地点条、人物头衔花字）属于剪辑包装层，**严禁写进视频生成提示词**，并在风格句声明 `no text overlays, captions, watermarks, or split-screen borders`。
6. **跨空间切镜参考隔离、无名群演防串服与多音字口语化（实拍防穿帮三律）**：
   - **跨空间切镜锚点隔离**：同一生成组若跨越两个相邻物理空间（如从大堂掀帘进入后厨、从古旧前厅切入内室），严禁仅同时罗列两张纯场景图任由模型自由拼接（极易出现“在大堂餐桌上起明火炒大铁锅”或反打穿帮现代不锈钢冰柜等串景时代错位）；必须为第二空间单独提供含人物站位的目标空间关键帧（如 `<Picture 2> is the composition reference for [Shot 3]`）并在 `retention_analysis` 显式锁定空间排他性。
   - **无名群演防串穿主角工装**：当 `ref_images` 含有穿标志性制服/围裙的主配角（如穿黑围裙的店员），而同组另一子镜出现无独立设定图的无名路人/同桌同学时，模型极易把参考图里的制服/围裙复制到路人身上；此时优先改为有设定图角色的近景/单人构图向画外同伴互动，或为群演子镜单独生成占位关键帧。
   - **易混多音字/谐音词口语替换**：遇到在语境中易被 TTS 误读成荒谬谐音的书面短词（如“单摘出来”易被误读成“山寨出来”），编译台词与字幕时主动替换为零歧义自然口语（如“单独列出来”）。

---

## 四、配套工具脚本（`scripts/`）

| 脚本 | 功能 |
|---|---|
| `scripts/compress_1k.py` | 将任意 2K 图片或目录批量等比压缩至 `max(w, h) <= 1024`（Lanczos），输出尺寸核验清单，绝不改动原图 |
| `scripts/spark_h3_image.py` | 调用 Spark `MiniMax H3 Image`（`MiniMaxH3ImageConditioning` 多图参考编辑）生成同场定场母图与各分镜增量首帧关键帧，并自动导出 `≤1K` 副本 |
| `scripts/pika_runner.py` | 读取结构化分镜视频 JSON，自动校验“零人物外貌词禁令”与“`≤1K` 尺寸禁令”，调用本机 `Pika-H3-Flex` (`480p`) 并发/顺序执行视频生成及 `vo_split` 双轨混音，校核 `ffprobe` 与回执头 |
| `scripts/inspect_video.py` | 对生成的每条 MP4 自动抽取高密度带秒点采样帧拼板（Contact Sheet）与音频波形/时长诊断，供多模态审片 Agent 与 `agy-video-understand` 逐镜核验 |
| `scripts/post_bgm_subtitles.py` | 基于各分镜实测时长与 `audio-library` 选曲编译独立分离式配乐轨（自动人声闪避 + 悬念卡点对齐）与三态双层字幕（`caption`/`dialogue`/`vo` `.vtt` + JSON），保持原片零烧录可直接超分 |
| `scripts/upload_to_studio.py` | 将通过审片验收的关键帧、视频及分离式配乐/字幕一键上传并绑定至导演工作台对应剧集镜头，触发纯净整集合成 |
