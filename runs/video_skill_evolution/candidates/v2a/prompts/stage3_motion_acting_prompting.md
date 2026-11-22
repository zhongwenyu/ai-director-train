# Stage 3：视频动态微表演、物理闭环与对白声场编译指南 (`detailed_action_and_dialogue` & `soundscape`)

用精准生动的英文编写子镜头动态描述（仅 `<d>` 标签内保留中文台词原文），画内角色统一用尖括号 `<CHR_1>`、`<CHR_2>` 占位符指代（严格对应本镜 `visible_role_ids`，底层编译器自动绑定 `<Subject k> (Sm)`）。

## 1. 克制稳健运镜与空间透视稳定
- 优先采用聚焦眼神戏的稳固克制运镜：常态对话与反应使用 `Static camera` 或极轻微自然呼吸稳拍 `Locked-off camera with subtle organic breathing`；潜台词施压或情绪攀向高点时使用平滑浅景深微推 `Slow subtle push-in keeping crisp focus on both eyes`。
- 严禁剧烈晃动或大幅横向越轴摇移，确保前中后景遮挡关系与背景几何结构全程稳定无畸变。

## 2. 潜台词极性驱动的三段式人类微表情弧光（方向 A 核心，反木讷与反假笑）
摒弃“木讷站桩念稿”与“五官过度挤压/僵硬扯嘴假笑”两端失真，严禁使用 `contorted`、`deeply wrinkled`、`exaggerated grin` 等破坏骨相显老的词汇；在保持角色真实骨相的基础上，严格依据 `subtext_intent` 的**真实情绪极性**写出细腻可感的三段式演进：
1. **起幅即时受激（`0.00s–0.25s`，零滞后）**：承接前镜尾音或起音前瞬间，瞳孔聚焦、眼睑或呼吸即刻产生本能生理微反应（如眸光骤凝、极轻吸气、视线微闪后锁死对侧），消除反应滞后。
2. **中段极性眼周微肌群展开（随台词或无声反应推进）**：精准匹配情绪底色——
   - **喜感/释然/暖意**：眼尾自然微弯漾起真挚眼神笑意（genuine warmth in the eyes），眉宇舒展，双肩柔和放松，拒绝眼冷嘴笑的假笑面具；
   - **悲恸/委屈/刺痛**：眼眶渐盈清亮水光（tear-rimmed glistening eyes），内眉梢微敛，下颌与唇角浮现极克制的细微轻颤；
   - **冷峻/审视/压迫**：上眼睑微沉，锐利目光钉死视线轴线对侧，面庞冷定，下颌线微绷；
   - **慌乱/心虚/受惊**：瞳孔微颤、咽喉轻咽、呼吸微促后勉力维持镇定；
   - **隐忍/克制/暗涌**：咬肌轻收、鼻翼随深吸气微动，短暂垂眸压下波澜旋即抬眼直视。
3. **尾段余韵落点（收音后至镜末）**：视线与神态稳稳停驻于潜台词终态焦点，情绪余波留在眼底直至切镜，严禁提前松懈出戏。

## 3. 情境化自然手部支点与接触物理因果闭环
- **真实支点微动作**：拒绝双手悬空乱挥或全身僵硬。依据当前年代情境、服装形制与环境表面赋予真实重力支点（如指腹轻按或摩挲扶手/台面边缘、指节随情绪收紧或松开衣袖/衣襟布料、稳持场内既有器物微调倾角、躯干贴轴线微前倾施压或微后仰防御），且起止姿态与前后镜平滑咬合。
- **接触物理因果闭环铁律**：凡发生手部或肢体与衣物、器物、接触表面的施力交互，必须完整写出**“接触建立 → 真实物理阻尼与施力过程 → 受作用表面同步产生形变/位移/痕迹演进并持续保持至镜末”**的因果链（如：`fingers press into the sleeve fabric, forming taut creases that remain held`；`sets the object firmly onto the surface where it rests stationary in its new position`），严禁穿模悬空、施力后受作用表面毫无物理变化或凭空弹回初始状态！

## 4. `0.20s` 准时开口、呼吸声线质感与静音锁唇铁律
- **标准对白格式与防吞字红线**：
  - 画内开口角色一律从 **`0.20s` 立即起音**，严格采用标准语法：`<CHR_1> speaks (0.20s-止秒s): <d>[Chinese] 中文台词原文</d>`（若单镜偶含同场紧凑接续短句，后句顺延起止秒数且保持语法一致）。
  - 最末 `止秒s` 必须贴合字数紧凑语速，且严格满足 **`止秒s <= duration_s - 0.35s`**，留足镜内收音缓冲，杜绝切镜硬截断吞字。
- **潜台词气口与颤音层次注入**：在 `speaks` 前后的英文描述中（严禁写入 `<d>` 内部），显式注入匹配 `subtext_intent` 的**呼吸气口与生理发声质感**（如 `after a quiet sharp breath catch, speaking in a low steady voice with icy restraint`、`voice carrying a subtle emotional tremor on the final syllables`、`crisp urgent delivery with natural breath phrasing`），消除平淡机械播音腔；同时要求清晰精准的唇齿舌同步咬字（`precise, natural lip and tongue articulation synced cleanly to each Chinese syllable without over-stretching the jaw`）。
- **静音尾段、反应镜与 `inner_os` 镜双唇锁死**：
  - 台词收音后的尾段（`止秒s` 至 `duration_s`），必须补写 `then naturally closes lips and holds steady eye contact, zero trailing mouth movement`。
  - 凡无画内开口的镜头（含受话方无声反应镜与带 `inner_os` 的心声镜），**严禁写入 `speaks` 或 `<d>` 标签**，必须明确声明 `<CHR_k>'s lips remain naturally closed and still throughout the entire shot, zero silent mouthing`，仅以眼神与呼吸传递潜台词。

## 5. `soundscape` 纯净实拍声场设计
- 用简练英文描述匹配当前空间的自然低底噪环境声（`subtle room tone, quiet spatial air`）及与肢体接触动作精准同步的轻微实拍音效（`soft fabric rustle, gentle tactile contact sound`）。
- 静音段与片尾须声明干净底噪（`clean quiet audio tail, zero vocal mumble or stray noise`），**严禁写入任何背景音乐、配乐风格或乐器名称**。
