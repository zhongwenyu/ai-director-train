# Stage 3：视频动态表演、潜台词微表情与声画编译指南 (`detailed_action_and_dialogue` & `soundscape`)

用**纯英文**编写子镜头动态画面与表演提示词（仅 `<d>[Chinese] ...</d>` 内保留原始中文台词），在场角色统一使用 `<CHR_1>`、`<CHR_2>` 占位符指代（底层编译器会自动绑定 `<Subject k> (Sm)`，严禁手写具体人名或自行编造标签）。

## 1. 画内对白时码、呼吸气口与唇齿同步铁律
- **0.20s 立即开口与标准语法**：凡 `speaking_role_ids` 内的发声角色，必须从 `0.20s` 准时开口，严格采用以下精确语法结构（严禁改动冒号前后标签格式）：
  `<CHR_1> speaks (0.20s-X.XXs): <d>[Chinese] 中文台词原文</d>`
  结束时刻 `X.XXs` 必须比子镜头 `duration_s` 提前至少 `0.45s–0.60s`，确保尾字发音完整落地、绝不切点吞字。
- **人声演绎起伏与精准咬字**：紧接对白标签前后，用英文写明契合 `subtext_intent` 的**呼吸气口、嗓音质感、语速重音起伏与清晰唇齿开合同步**（例如：`After a quick shallow breath, <CHR_1> speaks (0.20s-2.45s): <d>[Chinese] ...</d>, delivering the words in a low, restrained tone with subtle vocal inflection on the key phrase and crisp syllable-accurate lip-sync`），彻底消除机械平淡朗读感。
- **无词尾段闭唇锁死**：在 `X.XXs` 至 `duration_s` 的句尾余量段，必须显式写明**双唇自然轻合静止、停止一切口型微动**，以眼神余韵或轻微呼吸承接切点（如 `From 2.45s to 3.00s, <CHR_1> settles lips cleanly closed without stray mouthing, holding a taut gaze`）。

## 2. 潜台词驱动的三段式饱满微表情弧光（零木讷·零崩坏显老）
摒弃僵硬面瘫与夸张挤脸伪影，在全程维持角色紧致自然面部骨相（严禁使用导致满脸褶皱苍老或五官畸变拉扯的极端词）的前提下，严格依据每句 `subtext_intent` 的真实情绪极性，写出连续鲜活的眼周、眉梢与口周微肌群演进：
- **`0.00s–0.20s` 瞬时受激起拍（零滞后转折）**：镜头切入瞬间即刻呈现潜台词生理反应——
  - *冷峻压迫/审视*：目光骤然定焦锁死，下眼睑微收，下颌微抬建立压迫气场；
  - *悲恸委屈/心碎*：眼底泛起清亮水光，内眉尖极轻微蹙动，伴随克制的轻吸气；
  - *慌乱受惊/心虚*：双眸瞬时微张、快速眨眼或瞳孔细微游移闪避，喉部轻咽；
  - *喜感欢愉/温情*：眼尾自然弯起柔和弧度，眼神光灵动提亮，嘴角自然轻扬；
  - *隐忍克制/暗流*：视线短暂微垂随即重新抬眸凝视，唇线轻抿，鼻翼极轻微起伏吐息。
- **`0.20s–X.XXs` 情绪递进拍**：随台词重音推进眉眼张力与微幅头颈倾角变化（如贴近视线轴线轻倾半寸施压，或微偏头流露迟疑），保持双眼高光鲜活。
- **无声反应镜与 `inner_os` 闭唇表演铁律**：当镜头无画内台词或仅承载 `inner_os` 时，严禁出现 `speaks` 与 `<d>` 标签，且**必须显式声明全程双唇闭合不发声（`keeps lips naturally closed throughout with zero lip flutter`）**，通过眼神焦点流转、呼吸胸廓起伏与眉眼微张力外化内心波澜。

## 3. 跨题材自然手部支点与物理状态连贯
- **触点支点优先**：避免双手悬空僵直或复杂易穿模的剧烈动作；结合时代与情境器物设计自然**手部触点支点（tactile anchor pivot）**——如指节轻抵或收紧台面边缘、轻拢衣袖/衣角、指尖稳扶手边器物外壁或扶手，以细微指尖力道变化呼应潜台词重音。
- **物理交互闭环与跨镜衔接**：若涉及放下/推开器物、交接物件或姿态转换，须写清手部真实接触受力与器物位移终态，并确保起止姿态与相邻子镜头首帧严丝合缝。

## 4. 克制电影运镜与纯净环境声场 (`soundscape`)
- **运镜控制**：贴视线浅景深近景主导采用 `Static locked-off camera`、`Subtle slow push-in`（情绪重音缓推）或极轻微实拍呼吸感（`imperceptible handheld breathing drift`），严禁急速摇移或大幅变焦造成面部模糊与背景几何扭曲。
- **`soundscape` 规范（纯英文）**：简述契合场景空间的自然环境底噪与细微动作/呼吸拟音（如 `quiet room tone, soft fabric rustle, gentle breath intake, subtle surface contact`），严禁出现任何背景音乐、曲风、乐器名称或无剧本杂音人声。
