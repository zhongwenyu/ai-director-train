# Stage 3：视频动态表演与对白编译指南 (`detailed_action_and_dialogue` & `soundscape`)

用英文编写子镜头的动态画面与声画描述，在场角色统一使用 `<CHR_1>`、`<CHR_2>` 占位符指代（底层编译器会自动绑定 `<Subject k> (Sm)`，严禁手写角色真名或篡改标签格式）。

## 1. 运镜协同与多元潜台词情绪谱系校准
- **摄影机运动**：写明与戏剧呼吸匹配的运镜方式（如短促交锋或定格反应用 `Static camera`，情绪递进或内心触动用 `Subtle slow push-in`，视线联动用 `Gentle reframe`），全程严守 180° 轴线与空间透视稳定。
- **全谱系鲜活真人情绪释放**：依据 `subtext_intent` 展现丰富、生动、符合人类真实心理的多元眉眼起伏与表情层次——既严禁全程面无表情机械干念，也严禁将所有戏份窄化为冷脸紧绷，更杜绝五官失控扭曲狰狞：
  - *温情/喜悦/释然/调侃*：眉眼自然舒展弯起、眼底漾开真实笑意、唇角轻扬或温和颔首，神采鲜活松弛；
  - *错愕/顿悟/悬念冲击/动容*：瞳孔骤然聚焦、呼吸轻滞、神色微怔，或眼眶泛红含泪、眼神震动；
  - *玩味/反讽/试探/暗流周旋*：目光流转审视、唇角浮现似笑非笑的微妙弧度、头颈轻偏传递言外之意；
  - *悲恸/委屈/失落/隐忍*：目光缓垂、眉宇轻蹙、呼吸微沉或欲言又止，呈现细腻克制的情感重量；
  - *质问/急迫/决断/正面交锋*：眼神锐利锁定、眉宇凝聚张力、语气与神态果断外放，保持真人解剖级自然肌理（`expressive, lifelike facial dynamics without exaggerated facial contortion`）。

## 2. 镜长耦合的表演密度与人物肢体动机
- **短镜（`2s–3s`）聚焦单一鲜明落点**：集中刻画一个清晰利落的情绪峰值或即时反应（如听闻关键话语后的骤然定眸、会心展颜、玩味挑眉或轻叹垂目），避免在短时间内堆砌多段繁琐手势与大幅转身导致五官肢体慌乱。
- **中长说话镜（`4s–6s+`）构建自然递进与身体支点**：展现**“起势酝酿 → 台词重音处神态转折/潜台词反差 → 尾音余韵落点”**的完整层次，并融入符合人物身份、年代气质与心理动机的身体重心转移及手部/器物自然交互（如随话语轻舒手势、指尖轻触随身器物/衣袖、身体顺势微倾或坦然落靠），消除躯干僵直感，且镜末姿态须与下一镜首帧顺滑咬合。

## 3. 发声模态刚性控制、饱满口型与鲜活人声语态
- **画内对白模式（角色位于 `speaking_role_ids`）**：
  - 镜头起始 `0.20s` 立即紧凑开口，结束秒数须比 `duration_s` 提前 `0.25s–0.40s` 以留出完整收音气口，严格采用标准格式：
    `<CHR_1> speaks (0.20s-止秒s): <d>[Chinese] 中文台词原文</d>`
  - **唇形动态与情绪语态**：明确要求清晰饱满、贴合音节开合与情绪力度的真实口型（`with clear, expressive lip-sync matching syllable cadence and vocal intensity`）；搭配贴合潜台词的自然紧凑语速、真实呼吸换气与重音起伏描述（如轻快带笑、微颤动容、温润柔和、果决利落等随情境变化的语态修饰，彻底消除慢速平直机器腔）。
- **心声/画外音与静默倾听模式（`inner_os` 或非发声角色）**：
  - 严禁对非 `speaking_role_ids` 角色生成 `speaks` 或 `<d>` 标签；
  - 必须显式写明闭嘴静止约束（`keeping lips naturally closed with no speaking or mouth movement`），通过眼神变化、眉宇起伏、呼吸节律与细微头颈姿态展现内心独白或倾听反应。

## 4. 连续声场底噪与动作音效（`soundscape`）
- 用英文简述**跨镜连续一致的场景环境底噪**与**画面动作匹配的细微实拍音效**（格式：`Continuous [scene-matched ambient room tone / natural environmental air], with subtle [visible action foley]`）；独白镜与静默反应镜同样必须保持同源连续底噪以杜绝干声死寂、音频抽吸与起音突兀；严禁出现背景音乐（BGM）、旋律或任何乐器词。

## 5. 参数化编译范式（须按实际镜长、题材与潜台词极性动态实例化，严禁照搬单一套路）
- **画内说话镜**：`[Camera motion]. <CHR_1> [continues opening posture & eyeline], [subtext-driven brow-eye & facial progression from onset to emphasis beat] accompanied by [identity-matched body weight or hand/prop motivation]. <CHR_1> speaks (0.20s-[end_s]s) [emotion-matched brisk vocal cadence & breath inflection]: <d>[Chinese] 中文台词原文</d>, articulating clear, natural lip-sync for every syllable before settling into [coherent ending expression & posture]. [Optional <CHR_2> listens in-frame with lips naturally closed and authentic silent reaction].`
- **静默反应/心声镜**：`[Camera motion]. <CHR_2> keeps lips naturally closed with no speaking or mouth movement; [vivid listener/inner-monologue emotional arc across eyes, brows, breathing, and subtle head/postural response matching subtext_intent], landing cleanly on [expressive emotional beat].`
