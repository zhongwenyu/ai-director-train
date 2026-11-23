# Stage 3：视频动态表演与声画编译指南 (`detailed_action_and_dialogue` & `soundscape`)

用英文编写子镜头的动态画面描述（中文台词置于 `<d>[Chinese] ...</d>` 内），仅对本镜 `visible_role_ids` 中的在场角色使用 `<CHR_1>`、`<CHR_2>` 占位符指代（底层编译器自动绑定 `<Subject k> (Sm)`），严格遵循“静帧干净起幅、动态鲜活外化、物理因果交互、精准唇形气口与净音收尾”准则：

## 1. 运镜方式与空间透视稳定
- 开篇写明契合景别与戏剧情绪的平顺运镜（如 `Static camera`、`Subtle slow push-in`、`Gentle slight panning following hand action`），保持前景虚化遮挡层、人物方位与背景建筑几何稳定，避免剧烈晃动引发空间畸变。

## 2. 受激即时反应与鲜活跨题材真人表演（防呆板木讷与防生硬伪影）
- **零滞后即时触发**：杜绝开场发呆前摇，从 `0.0s` 起即时响应对手刺激或自身 `subtext_intent`，形成“开场眼神/呼吸即时触动 → 中段鲜活眉眼与神态展开 → 尾段余韵定格”的流畅表演弧光。
- **鲜活外化多元人类情绪光谱（全题材通用，严禁锁死单一冷峻压抑模板）**：依剧情基调与 `subtext_intent`，用灵动眼神流转、真实眉眼舒展起伏、唇角弧度与自然呼吸释放丰满情感，自由适配跨题材演法：
  - **轻喜/俏皮**：眸光骤亮漾开笑意，眉梢轻扬，唇角俏皮弯起（`eyes brighten with playful warmth, brows lifting with a genuine/teasing smile`）；
  - **温情/动容**：目光柔化饱含暖意，神色舒展，轻缓呼气（`gaze softens with tender affection, expression warming with quiet relief`）；
  - **反讽/讥诮**：眼神骤利，单眉轻挑，浮现似笑非笑弧度（`eyes sharpen incisively, raising a brow with a wry, ironic half-smile`）；
  - **错愕/震惊**：双眸微睁定格，呼吸骤滞，流露震惊动摇（`eyes widen in sudden disbelief, catching in momentary shock`）；
  - **委屈/含泪**：眼眶泛起泪光，眉心轻蹙，神情脆弱动容（`eyes glisten with unshed tears, brows drawing together in vulnerability`）；
  - **高能爆发**：目光灼灼逼视，情绪高涨，强势正面出击（`locks a fiery gaze forward, expression surging with urgent intensity`）。
- **防两极失真与骨相稳固**：既杜绝面无波澜的僵硬木讷，也杜绝超出真人肌肉生理极限的五官拉扯伪影；鲜活表达情绪的同时保持角色核心骨相与设定年龄特征稳定（`maintaining <CHR_k>'s natural facial identity and age-accurate features without unnatural facial warping`）。

## 3. 手部物理因果交互与跨镜姿态接续
- 杜绝双手悬空机械比划；仅调用输入任务卡已有的在场器物、环境支点或自身衣袖衣角，写出**施力接触 → 物理状态真实改变**的完整因果（如握紧器物使其轻微位移、将物件轻放落定台面、指尖按实支点配合身体前倾、收拢手指令衣袖自然起皱），起止姿态与前后镜顺滑衔接。

## 4. 鲜活声线气口、精准唇形与防吞字闭唇控制
- **即时开口与标准语法**：画内发声角色默认从 `0.20s` 开口，严格保留标准格式：`<CHR_1> speaks (0.20s-止秒s): <d>[Chinese] 中文台词原文</d>`。
- **跨题材鲜活声线与呼吸导引**：在 `speaks` 前后写明贴合 `subtext_intent` 的**自然换气气口、语速轻重顿挫与鲜活声线质感**——随情境灵活选用清亮带笑（`bright, playful tone`）、温柔轻语（`warm, tender voice`）、酸楚微颤（`emotional, wavering voice`）、干脆犀利（`crisp, incisive tone`）、急促激昂（`urgent, fiery intensity`）或沉稳笃定（`clear, grounded cadence`），告别平淡机械朗读腔。
- **清晰唇形对焦**：发声期间严禁用手部、器物或大幅偏头遮挡双唇，明确要求逐音节精准对口型（`with clear, accurate lip-sync matching every Chinese syllable`）。
- **收尾余量防吞字与闭唇锁死**：止秒 `end_s` 须容纳完整台词发音，且**早于本镜 `duration_s` 至少 `0.30s–0.50s`**（即便设置了 `lcut_audio_hold_over_next_s`，单镜生成窗口内仍须留 `0.25s–0.45s` 余量确保尾字清晰不截断）；到达 `end_s` 时必须写明双唇自然闭合定格（`closes lips naturally at X.XXs with zero residual mouth movement`），根除尾段多余口型蠕动。
- **无台词反应镜与 `inner_os` 零口型铁律**：凡 `speaking_role_ids` 为空的反应镜或 `mode == "inner_os"` 独白镜，**严禁在 `detailed_action_and_dialogue` 中写 `<d>...</d>` 标签**，且必须显式声明全程闭唇不发声（`<CHR_k> keeps lips naturally closed throughout with zero speaking or mouth movement`），全凭眼神流转、鲜活神态与呼吸承载反应或心声。

## 5. 纯净环境音效 (`soundscape`)
- 用简明英文描述干净的空间环境底噪（`clean natural room tone` / `subtle outdoor ambience`）及与画面动作精准同步的物理实效音（如衣物轻擦、器物轻放、自然呼吸声），**严禁出现背景音乐、乐器声、人声碎语或杂乱底噪**。

## 6. 跨题材语法结构参考（按实际情境替换情绪、声线与动作）
- **画内对白镜（3s 示例）**：`Subtle slow push-in, Medium close-up. Maintaining <CHR_1>'s natural facial identity, <CHR_1>'s eyes brighten with lively warmth (or sharpen with intense emotion), brows lifting expressively while leaning slightly forward and gently creasing the sleeve. Drawing a natural breath, <CHR_1> speaks (0.20s-2.55s): <d>[Chinese] 中文台词原文</d>, in a vivid tone matching the subtext with clear, accurate lip-sync matching every Chinese syllable. At 2.55s, <CHR_1> closes lips naturally with zero residual mouth movement, holding an expressive gaze toward screen-right.`
- **无台词反应 / `inner_os` 镜（2s 示例）**：`Static camera, Close-up on <CHR_2>. <CHR_2> keeps lips naturally closed throughout with zero speaking or mouth movement. At 0.10s, <CHR_2>'s eyes widen with immediate surprise (or soften tenderly / narrow with wry realization), shifting into a vivid reaction toward screen-left while fingers tighten gently on the garment hem.`
