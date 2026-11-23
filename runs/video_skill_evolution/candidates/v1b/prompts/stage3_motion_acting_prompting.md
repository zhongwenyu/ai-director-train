# Stage 3：视频动态表演与声画同步编译指南 (`detailed_action_and_dialogue` & `soundscape`)

用英文编写子镜头的动态画面与表演描述，角色统一用 `<CHR_1>`、`<CHR_2>` 占位符指代（底层编译器会自动绑定 `<Subject k> (Sm)`）：

## 1. 运镜设计与跨镜动态衔接
- 明确标注贴合戏剧张力的摄影机运镜方式：如稳定近景交锋用 `Static camera`，情绪升温、潜台词刺探或聚焦即时反应时用 `Subtle slow push-in`，配合人物走位转身用 `Smooth subtle pan/tracking`，高冲突临场感可用 `Subtle organic handheld movement`。
- 角色开场姿态须自然承接首帧与上一镜末态，镜头结尾动作留有自然惯性缓冲与呼吸落点，避免动作半途僵死卡顿。

## 2. 鲜活层次化表演与连贯肢体（破除木讷面瘫与五官崩坏两极）
- **围绕 `subtext_intent` 构建真实情绪递进弧光**：拒绝全程单一固化的面瘫式或死板压抑表演！根据题材语境与角色潜台词，写出**“起态承接 → 情绪触发/潜台词反差 → 鲜活外化释放”**的完整动态层次。无论是温暖笑意、讥诮挑眉、审视试探、强忍泪光、错愕瞳孔震动，还是凌厉逼视、悲愤质问等多元人类情绪，均须饱满、鲜活、真实地外化于眉眼流转与面部神情变化之中。
- **真实人类解剖协调性（防高潮狰狞畸变）**：在强烈情绪高潮或爆发节点，通过眼神锐度、呼吸急促起伏、下颌与眉弓的真实肌肉联动传递冲击力，明确约束符合真实人类面部生理结构（`vivid, authentic human emotional expression with organic facial muscle coordination, free of exaggerated AI facial warping or grotesque distortion`），兼顾戏剧爆发力与画面美观真实。
- **自然连贯的肢体与器物互动**：杜绝躯干僵直站桩，结合情绪节拍配置有起止落点的自然肢体语言（如身体前倾施压、微仰审视、转头视线交锋、贴合语气重音的自然手势，或与在场器物连贯自然的触碰/拿放交互）。

## 3. 画内对白 vs 心声/静默反应：发声模态与口型精准控制
- **画内开口对白（角色在 `speaking_role_ids` 中）**：
  - **紧凑起音与防吞尾字时间窗**：角色从镜头起始 `0.20s` 立即紧凑开口，结束秒数 `止秒s` 须在镜头总长 `duration_s` 结束前预留 `0.30s–0.50s` 自然收音与唇部闭合缓冲（例如 `3s` 镜头写 `0.20s-2.60s`），**严防结尾语音截断吞字**。
  - **标准语法格式**：`<CHR_1> speaks (0.20s-止秒s): <d>[Chinese] 中文台词原文</d>`。
  - **饱满唇形与鲜活人声演绎**：在动作描述中明确要求**嘴部开合幅度自然饱满、唇齿舌动态清晰咬合每个中文音节并与情绪力度同步**（`clear, natural full-range lip articulation precisely synced to every syllable and vocal intensity`）；引导富有生命力的自然紧凑语速、真实呼吸气口与重音张力起伏（如 `speaking at a brisk, natural conversational pace with expressive breath pauses and emotional inflection`），彻底摒弃慢速平直的机械朗读。
- **心声/画外音独立闭唇通道（镜头含 `inner_os` 且该角色不在 `speaking_role_ids` 中）**：
  - `detailed_action_and_dialogue` 正文中**严禁出现该角色的 `speaks` 或 `<d>...</d>` 标签**！
  - 必须显式写入英文闭唇硬约束：`<CHR_k>'s lips remain naturally closed throughout with zero lip movement or mouthing`，仅通过眼神焦点转换、眉眼情绪流露、呼吸起伏与肢体反应展现内心波澜。
- **无台词即时反应镜头（`speaking_role_ids` 为空）及同镜倾听角色**：
  - 显式声明倾听角色双唇自然闭合不发声（`lips remain naturally closed, listening intently`），针对对手话语（含 L-Cut 延续过来的尾音）做出即时鲜活的眼神与神情反馈，严禁木然发呆或误动口型。

## 4. 连续自然声场与实录拟音（`soundscape`）
- 用英文编写连贯立体的环境声场描述，**必须包含连续不断层的环境底噪床**（如 `continuous seamless indoor room tone` 或 `steady natural outdoor ambient wind/street bed`）以锚定空间声学质感，消除独白、反应镜与切镜处的干声死寂、音频抽吸及起音突兀。
- 叠加贴合画面动作的细腻实录音效（如自然呼吸换气声、衣物轻微摩擦、脚步移动或器物轻触声 `subtle breath intake, soft fabric rustle, natural foley matching movements`）。
- **严禁写入任何背景音乐（BGM）、配乐旋律、弦乐钢琴或非写实戏剧音效**。
